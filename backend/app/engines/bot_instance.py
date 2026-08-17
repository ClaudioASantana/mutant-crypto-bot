import asyncio
import logging

from app.services.binance_client import BinanceClient
from app.engines.candle_builder import CandleBuilder
from app.engines.simulator import PaperTrader
from app.engines.cataloger import calculate_win_rate
from app.engines.technical_analysis import (
    candles_to_df, apply_indicators, eval_three_candles_composite
)
from app.models.market import Tick, Signal, SignalType, AccountState, CandleDirection
from app.engines.news import NewsFilter
from app.engines.risk import evaluate_risk
from app.engines.ai_filter import AIFilter
from app.engines.executor import BinanceExecutor
from app.engines.journal import TradeJournal

logger = logging.getLogger(__name__)

class BotInstance:
    def __init__(self, symbol: str, token: str, news_filter: NewsFilter, manager, swarm_bots: dict = None):
        self.symbol = symbol
        self.token = token
        self.news_filter = news_filter
        self.manager = manager
        self.swarm_bots = swarm_bots or {}

        self.client = BinanceClient(symbol=symbol)
        self.client.add_tick_callback(self.on_tick)
        self.client.add_history_callback(self.on_history)
        self.executor = BinanceExecutor(self.client.exchange)

        self.builder_m1 = CandleBuilder(60)
        self.builder_m5 = CandleBuilder(300)
        self.builder_m15 = CandleBuilder(900)

        self.paper_trader = PaperTrader(symbol=self.symbol, initial_balance=200.0, leverage=10)
        self.paper_trader.position_sizing_mode = "volatility_adjusted"
        self.ai_filter = AIFilter()
        self.journal = TradeJournal()
        self.live_qty = 0
        self.active_trade_id = None

        self.active_config = {"timeframe": 900, "strategy": "ABCD", "rsi_oversold": 25, "rsi_overbought": 75}
        self.auto_optimize = False
        self.global_catalog = []

        self.tick_count = 0
        self.last_signal_direction = None
        self.daily_loss_limit = -20.0
        self.last_atr_cache = {}

    def get_active_builder(self):
        if self.active_config["timeframe"] == 60:
            return self.builder_m1
        elif self.active_config["timeframe"] == 300:
            return self.builder_m5
        return self.builder_m15

    def check_macro_correlation(self, direction: str) -> bool:
        if not self.swarm_bots:
            return True
        confirming_assets = 0
        total_assets = 0
        for sym, bot in self.swarm_bots.items():
            if sym == self.symbol: continue
            b = bot.get_active_builder()
            if not b.closed_candles: continue
            last_candle = b.closed_candles[-1]
            if sym == "BTC/USDT":
                if direction == "CALL" and last_candle.direction.value == "BEARISH": return False
                if direction == "PUT" and last_candle.direction.value == "BULLISH": return False
            total_assets += 1
            if direction == "CALL" and last_candle.direction.value == "BULLISH": confirming_assets += 1
            elif direction == "PUT" and last_candle.direction.value == "BEARISH": confirming_assets += 1
        if total_assets > 0 and confirming_assets < (total_assets / 2): return False
        return True

    async def on_history(self, granularity: int, candles: list):
        from app.models.market import Candle
        b = self.builder_m1 if granularity == 60 else (self.builder_m5 if granularity == 300 else self.builder_m15)
        b.closed_candles = []
        for c in candles:
            direction = CandleDirection.BULLISH if c["close"] >= c["open"] else CandleDirection.BEARISH
            b.closed_candles.append(Candle(epoch=c["epoch"], open=c["open"], high=c["high"], low=c["low"], close=c["close"], direction=direction))
        logger.info(f"[{self.symbol}] Builder M{granularity//60} inicializado com {len(b.closed_candles)} velas.")

    async def broadcast_catalog(self):
        catalog = []
        for timeframe, b in [(60, self.builder_m1), (300, self.builder_m5), (900, self.builder_m15)]:
            for strategy_name in ["EMA+MACD", "Bollinger", "VWAP", "SMC", "SuperTrend", "3 Velas", "Pin Bar", "ABCD", "RSI+EMA", "Exaustão"]:
                stats = await asyncio.to_thread(calculate_win_rate, b.closed_candles, strategy_name)
                stats.pop("df", None)
                catalog.append({"timeframe": timeframe, "strategy": strategy_name, "stats": stats})
        self.global_catalog = catalog
        await self.manager.broadcast({"event": "catalog", "symbol": self.symbol, "data": {"catalog": catalog, "active_config": self.active_config, "auto_optimize": self.auto_optimize, "simulator": self.paper_trader.get_state()}})

    async def on_tick(self, tick: Tick):
        self.tick_count += 1
        active_builder = self.get_active_builder()
        c1 = self.builder_m1.process_tick(tick)
        c5 = self.builder_m5.process_tick(tick)
        c15 = self.builder_m15.process_tick(tick)

        if active_builder.current_candle:
            await self.manager.broadcast({"event": "tick", "symbol": self.symbol, "data": {"quote": tick.quote, "epoch": tick.epoch, "candle": active_builder.current_candle.model_dump()}})
        if c1 or c5 or c15: asyncio.create_task(self.broadcast_catalog())

        finished_trades = self.paper_trader.check_positions(tick.epoch, tick.quote)
        if finished_trades:
            await self.manager.broadcast({"event": "simulator", "symbol": self.symbol, "data": self.paper_trader.get_state()})
            for trade in finished_trades:
                if self.active_trade_id:
                    self.journal.log_exit(self.active_trade_id, trade["exit_epoch"], trade["exit_price"], trade["pnl"], trade["status"])
            self.active_trade_id = None

        tf = self.active_config["timeframe"]
        builder = self.builder_m1 if tf == 60 else (self.builder_m5 if tf == 300 else self.builder_m15)

        # Guarda: Se já temos trade ativo ou já processamos esta vela, não re-entramos
        if self.active_trade_id or (builder.current_candle and builder.current_candle.epoch == getattr(self, 'last_signal_epoch', None)):
             return

        if builder.get_seconds_in_cycle(tick) >= (tf - 2) and len(builder.closed_candles) >= 30:
            # Marca que esta vela já foi avaliada
            self.last_signal_epoch = builder.current_candle.epoch if builder.current_candle else tick.epoch

            df = candles_to_df(builder.closed_candles)
            df = apply_indicators(df)
            atr = df.iloc[-1].get("ATRr_14", tick.quote * 0.005)
            self.last_atr_cache[tf] = float(atr)

            # AI Decision
            ai_decision = await self.ai_filter.make_decision(df, self.active_config["strategy"])
            signal_type = SignalType.NONE
            if ai_decision["decision"] == "BUY" and ai_decision["confidence"] >= 0.7: signal_type = SignalType.CALL
            elif ai_decision["decision"] == "SELL" and ai_decision["confidence"] >= 0.7: signal_type = SignalType.PUT

            if signal_type != SignalType.NONE:
                # Nova confluência: Validar padrão de 3 velas (filtro positivo)
                # Só entra se a estratégia for "3 Velas" ou se tivermos um padrão de reversão/continuação
                pattern_signal = eval_three_candles_composite(df, require_confluence=True)
                if pattern_signal != "NONE" and ((pattern_signal == "CALL" and signal_type == SignalType.CALL) or (pattern_signal == "PUT" and signal_type == SignalType.PUT)):
                    signal = Signal(type=signal_type, reason=ai_decision["reason"] + " | 3V-Confirmed")
                    strategy_info = f"M{tf//60}/AI+3V (Conf: {ai_decision['confidence']:.2f})"

                    # Risk Checks
                    if self.news_filter.check_safety(tick.epoch)["safe"]:
                        account_state = AccountState(
                            balance=self.paper_trader.balance, daily_pnl=self.paper_trader.get_pnl(),
                            highest_daily_pnl=self.paper_trader.highest_daily_pnl,
                            daily_stop_loss=self.paper_trader.daily_stop_loss,
                            daily_stop_gain=self.paper_trader.daily_stop_gain,
                            stake_initial=self.paper_trader.stake_initial
                        )
                        risk_eval = evaluate_risk(signal, account_state)
                        if risk_eval.decision == "APPROVED":
                            # Ajuste de risco otimizado para o backtest: SL 1.5 / TP 8.0
                            sl_mult = 1.5
                            tp_mult = 8.0
                            sl_price = tick.quote - (atr * sl_mult) if signal_type == SignalType.CALL else tick.quote + (atr * sl_mult)
                            tp_price = tick.quote + (atr * tp_mult) if signal_type == SignalType.CALL else tick.quote - (atr * tp_mult)

                            self.paper_trader.open_trade(signal_type.value, tf, tick.epoch, tick.quote, sl_price, tp_price, atr)
                            t_id = self.paper_trader.open_positions[-1]["id"]
                            self.active_trade_id = t_id
                            self.journal.log_entry(t_id, self.symbol, signal_type.value, strategy_info, ai_decision["reason"], tick.epoch, tick.quote, atr, 50.0, self.paper_trader.get_current_margin_usdt(), self.paper_trader.leverage)
                            await self.manager.broadcast({"event": "trade_opened", "symbol": self.symbol, "data": {"direction": signal_type.value, "price": tick.quote}})
                            await self.broadcast_state()

        self.last_tick_time = tick.epoch

    async def start(self):
        await self.client.connect_and_listen()

    def stop(self):
        self.client.stop()
        self.journal.close()

    async def broadcast_state(self):
        state = self.paper_trader.get_state()
        state["risk"]["atr"] = self.last_atr_cache.get(self.active_config["timeframe"], 0.0)
        await self.manager.broadcast({"event": "simulator", "symbol": self.symbol, "data": state})
