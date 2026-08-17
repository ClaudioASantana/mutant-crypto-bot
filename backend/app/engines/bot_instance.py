import asyncio
import logging
import os
import time
from typing import List, Dict
from app.models.personality import Personality
from app.models.performance import PersonalityPerformance
from app.services.market_data_provider import MarketDataProvider
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
from app.engines.journal import TradeJournal

logger = logging.getLogger(__name__)

# Constantes do Seletor Dinamico de Personalidades
SELECTOR_RESET_AFTER_SECONDS = 4 * 3600  # Reinicia janela de performance a cada 4h
SELECTOR_MAX_WINDOW_TRADES = 15          # Considera as ultimas 15 operacoes
SELECTOR_MIN_TRADES = 3                  # Exige minimo de trades antes de penalizar
SELECTOR_MAX_CONSECUTIVE_LOSSES = 4      # Apos 4 perdas seguidas, personalidade e desativada
SELECTOR_HYSTERESIS = 5.0                # Margem de fitness para trocar a personalidade ativa


class BotInstance:
    def __init__(self, symbol: str, token: str, news_filter: NewsFilter, manager, personalities: List[Personality], swarm_bots: dict = None):
        self.symbol = symbol
        self.token = token
        self.news_filter = news_filter
        self.manager = manager
        self.swarm_bots = swarm_bots or {}
        self.personalities = {p.name: p for p in personalities}  # Dict for fast lookup

        # Subscribe to MarketDataProvider instead of creating own client
        self.market_provider = MarketDataProvider()
        self.market_provider.subscribe(self.symbol, self.on_tick)

        # Initialize builders
        self.builder_m1 = CandleBuilder(60)
        self.builder_m5 = CandleBuilder(300)
        self.builder_m15 = CandleBuilder(900)

        # Create one PaperTrader per personality with unique state files
        self.paper_traders: Dict[str, PaperTrader] = {}
        for personality in personalities:
            state_filename = f"simulator_state_{self.symbol.replace('/', '_')}_{personality.name}_{personality.timeframe//60}m.json"
            trader = PaperTrader(symbol=self.symbol, initial_balance=200.0, leverage=10)
            trader._state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", state_filename))
            trader.position_sizing_mode = "volatility_adjusted"
            self.paper_traders[personality.name] = trader

        self.ai_filter = AIFilter()
        self.journal = TradeJournal()
        self.live_qty = 0
        self.active_trade_ids = {}  # Track active trade IDs per personality

        # --- Dynamic Personality Selector ---
        self.performance_trackers: Dict[str, PersonalityPerformance] = {}
        for p_name in self.personalities:
            self.performance_trackers[p_name] = PersonalityPerformance(personality_name=p_name, symbol=self.symbol)
        self.active_personality_name: str = next(iter(self.personalities.keys())) # Inicia com a primeira por padrao


        self.auto_optimize = False
        self.global_catalog = []
        self.tick_count = 0
        self.last_signal_direction = None
        self.daily_loss_limit = -20.0
        self.last_atr_cache = {}

    def get_builder_for_timeframe(self, timeframe: int):
        if timeframe == 60:
            return self.builder_m1
        elif timeframe == 300:
            return self.builder_m5
        elif timeframe == 900:
            return self.builder_m15
        return None

    def check_macro_correlation(self, _direction: str) -> bool:
        # TODO: A lógica de correlação entre ativos (swarm) precisa ser redesenhada
        # para a arquitetura de portfólio, considerando qual personalidade de cada
        # ativo deve ser usada para a correlação. Desativado por enquanto.
        return True

    def _select_best_personality(self) -> str:
        """
        Seleciona a personalidade com melhor aptidao (fitness) para operar.
        Penaliza fortemente personalidades com muitas perdas consecutivas.
        """
        if not self.performance_trackers:
            logger.warning(f"[{self.symbol}] Nenhuma personalidade para selecionar.")
            return next(iter(self.personalities.keys())) if self.personalities else None

        # 1. Reset de janela de performance se for muito antiga
        now = time.time()
        for perf in self.performance_trackers.values():
            if perf.last_update and (now - perf.last_update) > SELECTOR_RESET_AFTER_SECONDS:
                logger.info(f"[{self.symbol}] Reiniciando janela de performance para {perf.personality_name} (muito tempo sem operar).")
                perf.wins = 0
                perf.losses = 0
                perf.total_pnl = 0.0
                perf.trades_count = 0
                perf.consecutive_losses = 0
                perf.last_update = now

        # 2. Filtrar personalidades elegiveis (com minimo de trades ou sem perdas consecutivas excessivas)
        eligible = []
        for name, perf in self.performance_trackers.items():
            if perf.consecutive_losses >= SELECTOR_MAX_CONSECUTIVE_LOSSES:
                logger.info(f"[{self.symbol}] Personalidade '{name}' desativada por {perf.consecutive_losses} perdas seguidas.")
                continue
            if perf.trades_count < SELECTOR_MIN_TRADES:
                # Personalidades novas ainda sao elegiveis
                eligible.append((name, 0.0))  # Fitness neutro
            else:
                eligible.append((name, perf.fitness))

        if not eligible:
            logger.warning(f"[{self.symbol}] Nenhuma personalidade elegivel. Usando a primeira disponivel.")
            return next(iter(self.personalities.keys())) if self.personalities else None

        # 3. Selecionar a de maior fitness com Histerese
        best_name, best_fitness = max(eligible, key=lambda x: x[1])

        # Se ja temos uma ativa, aplicar a margem de histerese
        if self.active_personality_name in self.performance_trackers:
            current_active_fitness = self.performance_trackers[self.active_personality_name].fitness
            if (best_fitness - current_active_fitness) < SELECTOR_HYSTERESIS:
                best_name = self.active_personality_name
                logger.debug(f"[{self.symbol}] Histerese ativa: mantendo '{best_name}' (diferenca de fitness < {SELECTOR_HYSTERESIS})")

        # 4. Atualizar nome da personalidade ativa para logging
        self.active_personality_name = best_name
        return best_name

    async def on_history(self, granularity: int, candles: list):
        from app.models.market import Candle
        b = self.get_builder_for_timeframe(granularity)
        if b:
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

        # Broadcast combined state of all personalities
        combined_state = {
            "catalog": catalog,
            "auto_optimize": self.auto_optimize,
            "personalities": {name: trader.get_state() for name, trader in self.paper_traders.items()}
        }
        await self.manager.broadcast({"event": "catalog", "symbol": self.symbol, "data": combined_state})

    async def on_tick(self, tick: Tick):
        self.tick_count += 1

        # Process tick for all builders
        c1 = self.builder_m1.process_tick(tick)
        c5 = self.builder_m5.process_tick(tick)
        c15 = self.builder_m15.process_tick(tick)

        # Broadcast current tick data
        # We need to decide which personality's active_config/timeframe candle to broadcast.
        # For now, let's pick the first one, or the one with the smallest timeframe
        # This will need to be refined for the frontend to display individual personality candles.

        # Determine the smallest active timeframe among personalities for broadcasting
        smallest_timeframe = None
        for p in self.personalities.values():
            if smallest_timeframe is None or p.timeframe < smallest_timeframe:
                smallest_timeframe = p.timeframe

        if smallest_timeframe:
            active_builder = self.get_builder_for_timeframe(smallest_timeframe)
            if active_builder and active_builder.current_candle:
                await self.manager.broadcast({"event": "tick", "symbol": self.symbol, "data": {"quote": tick.quote, "epoch": tick.epoch, "candle": active_builder.current_candle.model_dump()}})

        if c1 or c5 or c15:
            # Re-calculate catalog and broadcast whenever a candle closes in any timeframe
            asyncio.create_task(self.broadcast_catalog())
            # Check positions for all paper traders whenever a candle closes
            for p_name, trader in self.paper_traders.items():
                finished_trades = trader.check_positions(tick.epoch, tick.quote)
                if finished_trades:
                    # Update journal and broadcast state for the specific personality
                    for trade in finished_trades:
                        if p_name in self.active_trade_ids and self.active_trade_ids[p_name] == trade["id"]:
                            self.journal.log_exit(trade["id"], trade["exit_epoch"], trade["exit_price"], trade["pnl"], trade["status"])

                            # Atualizar metricas de performance da personalidade
                            perf_tracker = self.performance_trackers[p_name]
                            is_win = trade["status"] == "WIN"
                            perf_tracker.record_trade(is_win, trade["pnl"])
                            perf_tracker.last_trade_epoch = trade["exit_epoch"]
                            perf_tracker.last_update = time.time()

                            del self.active_trade_ids[p_name] # Remove trade id if closed
                    await self.broadcast_state() # Broadcast combined state for all personalities

        # --- Dynamic Personality Selector ---
        # Before evaluating new trades, select the best personality based on recent performance
        best_personality_name = self._select_best_personality()

        # --- Personalities Decision Loop ---
        # Iterate over all personalities and check for trade signals if a candle has just closed for their timeframe
        for p_name, personality in self.personalities.items():

            # *** Dynamic Selector Guard ***
            # Only the BEST personality is allowed to trade
            if p_name != best_personality_name:
                continue

            trader = self.paper_traders[p_name]
            builder = self.get_builder_for_timeframe(personality.timeframe)
            if not builder:
                logger.warning(f"[{self.symbol}] Builder for timeframe {personality.timeframe} not found for personality {p_name}.")
                continue


            # Check if a trade is already active for this personality OR if the current candle has already been evaluated
            if personality.name in self.active_trade_ids or (builder.current_candle and builder.current_candle.epoch == getattr(self, f'last_signal_epoch_{p_name}', None)):
                continue

            # Only evaluate if enough candles are present for indicators and we are near the end of a candle cycle
            if builder.get_seconds_in_cycle(tick) >= (personality.timeframe - 2) and len(builder.closed_candles) >= 30:
                # Mark that this candle has been evaluated for this personality
                setattr(self, f'last_signal_epoch_{p_name}', builder.current_candle.epoch if builder.current_candle else tick.epoch)

                df = candles_to_df(builder.closed_candles)
                df = apply_indicators(df)
                atr = df.iloc[-1].get("ATRr_14", tick.quote * 0.005) # Default ATR if not found
                self.last_atr_cache[personality.timeframe] = float(atr)

                # AI Decision
                ai_decision = await self.ai_filter.make_decision(df, personality.strategy)
                signal_type = SignalType.NONE
                if ai_decision["decision"] == "BUY" and ai_decision["confidence"] >= 0.7: signal_type = SignalType.CALL
                elif ai_decision["decision"] == "SELL" and ai_decision["confidence"] >= 0.7: signal_type = SignalType.PUT

                if signal_type != SignalType.NONE:
                    # Confluence: Validate 3-candle pattern (positive filter)
                    pattern_signal = eval_three_candles_composite(df, require_confluence=True)
                    if pattern_signal != "NONE" and ((pattern_signal == "CALL" and signal_type == SignalType.CALL) or (pattern_signal == "PUT" and signal_type == SignalType.PUT)):
                        signal = Signal(type=signal_type, reason=ai_decision["reason"] + " | 3V-Confirmed")
                        strategy_info = f"M{personality.timeframe//60}/{personality.strategy} (Conf: {ai_decision['confidence']:.2f})"

                        # Risk Checks
                        if self.news_filter.check_safety(tick.epoch)["safe"]:
                            account_state = AccountState(
                                balance=trader.balance, daily_pnl=trader.get_pnl(),
                                highest_daily_pnl=trader.highest_daily_pnl,
                                daily_stop_loss=trader.daily_stop_loss,
                                daily_stop_gain=trader.daily_stop_gain,
                                stake_initial=trader.stake_initial
                            )
                            # TODO: Use risk_config from personality
                            risk_eval = evaluate_risk(signal, account_state)
                            if risk_eval.decision == "APPROVED":
                                # Optimized risk adjustment for backtest: SL 1.5 / TP 8.0
                                sl_mult = personality.risk_config.get("sl_multiplier", 1.5)
                                tp_mult = personality.risk_config.get("tp_multiplier", 8.0)
                                sl_price = tick.quote - (atr * sl_mult) if signal_type == SignalType.CALL else tick.quote + (atr * sl_mult)
                                tp_price = tick.quote + (atr * tp_mult) if signal_type == SignalType.CALL else tick.quote - (atr * tp_mult)

                                trader.open_trade(signal_type.value, personality.timeframe, tick.epoch, tick.quote, sl_price, tp_price, atr)
                                t_id = trader.open_positions[-1]["id"]
                                self.active_trade_ids[p_name] = t_id
                                self.journal.log_entry(t_id, self.symbol, signal_type.value, strategy_info, ai_decision["reason"], tick.epoch, tick.quote, atr, 50.0, trader.get_current_margin_usdt(), trader.leverage)
                                await self.manager.broadcast({"event": "trade_opened", "symbol": self.symbol, "data": {"direction": signal_type.value, "price": tick.quote, "personality": p_name}})
                                await self.broadcast_state()

        self.last_tick_time = tick.epoch

    async def start(self):
        # Start Binance client via MarketDataProvider
        await self.market_provider.start_client_for_symbol(self.symbol)

    def stop(self):
        # Unsubscribe from MarketDataProvider
        self.market_provider.unsubscribe(self.symbol, self.on_tick)
        self.journal.close()

    async def broadcast_state(self):
        # Broadcast combined state of all personalities
        combined_state = {
            "personalities": {name: trader.get_state() for name, trader in self.paper_traders.items()},
            "risk": {"atr": self.last_atr_cache},  # Store ATR for all timeframes
            "selector": {
                "active_personality": self.active_personality_name,
                "performances": {name: perf.model_dump() for name, perf in self.performance_trackers.items()}
            }
        }
        await self.manager.broadcast({"event": "simulator", "symbol": self.symbol, "data": combined_state})
