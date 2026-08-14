import asyncio
import logging
import os
from typing import Dict, Any

from app.services.binance_client import BinanceClient
from app.engines.candle_builder import CandleBuilder
from app.engines.simulator import PaperTrader
from app.engines.cataloger import calculate_win_rate
from app.engines.technical_analysis import (
    candles_to_df, apply_indicators, 
    eval_ema_macd, eval_bollinger, eval_vwap, eval_smc,
    eval_consecutive, eval_supertrend, eval_pin_bar, eval_abcd,
    check_signal_quality
)
from app.models.market import Tick, Signal, SignalType, AccountState, CandleDirection
from app.engines.news import NewsFilter
from app.engines.indicators import calculate_rsi
from app.engines.risk import evaluate_risk
from app.rag.agent import explain_signal
from app.engines.ai_filter import AIFilter
from app.engines.executor import BinanceExecutor
from app.engines.journal import TradeJournal

logger = logging.getLogger(__name__)

class BotInstance:
    def __init__(self, symbol: str, token: str, news_filter: NewsFilter, manager, swarm_bots: dict = None):
        self.symbol = symbol
        self.token = token
        self.news_filter = news_filter
        self.manager = manager  # WebSocket manager for broadcasting
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
        
        self.active_config = {"timeframe": 900, "strategy": "ABCD", "gale": 2, "rsi_oversold": 25, "rsi_overbought": 75}
        self.auto_optimize = False
        self.global_catalog = []
        
        self.tick_count = 0
        self.last_signal_direction = None
        self.daily_loss_limit = -20.0  # Stop diário em -$20 (10% da banca de $200)
        self.last_atr_cache = {}  # Cache ATR por timeframe: {300: 88.5, ...}

    def get_active_builder(self):
        if self.active_config["timeframe"] == 60:
            return self.builder_m1
        elif self.active_config["timeframe"] == 300:
            return self.builder_m5
        return self.builder_m15

    def check_macro_correlation(self, direction: str) -> bool:
        """
        Verifica se a maioria das outras moedas está na mesma direção do sinal.
        """
        if not self.swarm_bots:
            return True
            
        confirming_assets = 0
        total_assets = 0
        
        for sym, bot in self.swarm_bots.items():
            if sym == self.symbol:
                continue
                
            b = bot.get_active_builder()
            if not b.closed_candles:
                continue
                
            last_candle = b.closed_candles[-1]
            
            # Veto do Rei: Se o BTC estiver contra a operação, aborta na hora.
            if sym == "BTC/USDT":
                if direction == "CALL" and last_candle.direction.value == "BEARISH":
                    return False
                if direction == "PUT" and last_candle.direction.value == "BULLISH":
                    return False
                    
            total_assets += 1
            
            if direction == "CALL" and last_candle.direction.value == "BULLISH":
                confirming_assets += 1
            elif direction == "PUT" and last_candle.direction.value == "BEARISH":
                confirming_assets += 1
                
        # Exige que pelo menos 50% das outras moedas concordem
        if total_assets > 0 and confirming_assets < (total_assets / 2):
            return False
        return True

    async def on_history(self, granularity: int, candles: list):
        from app.models.market import Candle
        b = self.builder_m1 if granularity == 60 else (self.builder_m5 if granularity == 300 else self.builder_m15)
        b.closed_candles = []
        for c in candles:
            direction = CandleDirection.BULLISH if c["close"] >= c["open"] else CandleDirection.BEARISH
            b.closed_candles.append(Candle(
                epoch=c["epoch"],
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                direction=direction
            ))
        logger.info(f"[{self.symbol}] Builder M{granularity//60} inicializado com {len(b.closed_candles)} velas históricas.")

    async def broadcast_catalog(self):
        catalog = []
        for timeframe, b in [(60, self.builder_m1), (300, self.builder_m5), (900, self.builder_m15)]:
            for strategy_name in ["EMA+MACD", "Bollinger", "VWAP", "SMC", "SuperTrend", "3 Velas", "Pin Bar", "ABCD"]:
                stats = await asyncio.to_thread(calculate_win_rate, b.closed_candles, strategy_name)
                stats.pop("df", None)
                catalog.append({
                    "timeframe": timeframe,
                    "strategy": strategy_name,
                    "stats": stats
                })
        results = catalog
        self.global_catalog = results
        # We only broadcast if this bot is currently being watched by the UI
        # This logic will be handled by the manager in main.py, so we just send the message 
        # with our symbol attached.
        await self.manager.broadcast({"event": "catalog", "symbol": self.symbol, "data": {"catalog": results, "active_config": self.active_config, "auto_optimize": self.auto_optimize, "simulator": self.paper_trader.get_state()}})

    async def on_tick(self, tick: Tick):
        self.tick_count += 1
        if self.tick_count % 100 == 0:
            logger.info(f"[{self.symbol}] Received {self.tick_count} ticks. Quote: {tick.quote}")
        c1 = self.builder_m1.process_tick(tick)
        c5 = self.builder_m5.process_tick(tick)
        c15 = self.builder_m15.process_tick(tick)
        
        active_builder = self.get_active_builder()
        
        if active_builder.current_candle:
            await self.manager.broadcast({
                "event": "tick",
                "symbol": self.symbol,
                "data": {
                    "quote": tick.quote,
                    "epoch": tick.epoch,
                    "candle": active_builder.current_candle.model_dump()
                }
            })
            
        if c1 or c5 or c15:
            asyncio.create_task(self.broadcast_catalog())
            
        finished_trades = self.paper_trader.check_positions(tick.epoch, tick.quote)
        if finished_trades:
            await self.manager.broadcast({"event": "simulator", "symbol": self.symbol, "data": self.paper_trader.get_state()})

            import os
            for trade in finished_trades:
                if self.active_trade_id:
                    self.journal.log_exit(self.active_trade_id, trade["exit_epoch"], trade["exit_price"], trade["pnl"], trade["status"])
                    
                if os.getenv("LIVE_TRADING") == "True" and getattr(self, "live_qty", 0) > 0:
                    async def run_live_exit(sym, dir, qty):
                        res = await self.executor.execute_exit(sym, dir, qty)
                        if res["status"] == "error":
                            await self.manager.broadcast({
                                "event": "agent_message",
                                "symbol": sym,
                                "data": {"analysis": f"❌ ERRO CRÍTICO (Binance): Falha ao fechar ordem real. Motivo: {res.get('error')}"}
                            })
                    asyncio.create_task(run_live_exit(self.symbol, trade["direction"], self.live_qty))
                    self.live_qty = 0
                    
            self.active_trade_id = None

        # Broadcast live trade_preview a cada tick com preço atual + ATR cacheado
        if self.last_atr_cache:
            tf = self.active_config["timeframe"]
            atr_live = self.last_atr_cache.get(tf, tick.quote * 0.005)
            if self.paper_trader.position_sizing_mode == "gale":
                margin_live = self.paper_trader.stake_initial * (2 ** self.paper_trader.consecutive_losses)
            else:
                margin_live = self.paper_trader.balance * (self.paper_trader.risk_percent / 100.0)
                
            margin_live = min(margin_live, self.paper_trader.balance)
            strategy_live = self.active_config.get("strategy", "SMC")
            await self.manager.broadcast({"event": "trade_preview", "symbol": self.symbol, "data": {
                "strategy": strategy_live,
                "timeframe": f"M{tf // 60}",
                "current_price": round(tick.quote, 2),
                "atr": round(float(atr_live), 4),
                "call_sl": round(tick.quote - atr_live * 1.5, 2),
                "call_tp": round(tick.quote + atr_live * 3.0, 2),
                "put_sl":  round(tick.quote + atr_live * 1.5, 2),
                "put_tp":  round(tick.quote - atr_live * 3.0, 2),
                "margin":  round(margin_live, 2),
                "exposure": round(margin_live * self.paper_trader.leverage, 2),
                "leverage": self.paper_trader.leverage,
                "rr_ratio": "1:2 (SL 1.5\u00d7ATR | TP 3.0\u00d7ATR)"
            }})

        # Strategy Logic
        approved_configs = []
        if self.auto_optimize and len(self.global_catalog) > 0:
            # Filtro: Apenas M5 (comprovado como mais lucrativo após filtros de qualidade no backtest de 30 dias)
            # EMA+MACD M5: WR 43.75% | SMC M5: WR 38.48% — superior ao M1 com filtros aplicados
            m5_catalog = [c for c in self.global_catalog if c["timeframe"] == 300]
            pool = m5_catalog if m5_catalog else self.global_catalog
            best_config = max(pool, key=lambda x: x["stats"]["pnl_usdt"])
            approved_configs = [best_config]
            self.active_config = {"timeframe": best_config["timeframe"], "strategy": best_config["strategy"]}
        else:
            approved_configs = [self.active_config]
            
        for config in approved_configs:
            tf = config["timeframe"]
            req_strategy = config.get("strategy", "EMA+MACD")
            builder = self.builder_m1 if tf == 60 else (self.builder_m5 if tf == 300 else self.builder_m15)
            
            seconds_in_cycle = builder.get_seconds_in_cycle(tick)
            if seconds_in_cycle >= (tf - 2):
                if len(builder.closed_candles) >= 30:
                    df = candles_to_df(builder.closed_candles)
                    df = apply_indicators(df)
                    
                    # === Pre-Trade Preview — atualiza cache do ATR ===
                    atr_preview = df.iloc[-1].get("ATRr_14", tick.quote * 0.005)
                    import math
                    if atr_preview is None or (isinstance(atr_preview, float) and math.isnan(atr_preview)):
                        atr_preview = tick.quote * 0.005
                    # Salva ATR no cache para uso pelo broadcast por tick
                    self.last_atr_cache[tf] = float(atr_preview)
                    
                    sig_val = "NONE"
                    if req_strategy == "EMA+MACD":
                        sig_val = eval_ema_macd(df)
                    elif req_strategy == "Bollinger":
                        sig_val = eval_bollinger(df)
                    elif req_strategy == "VWAP":
                        sig_val = eval_vwap(df)
                    elif req_strategy == "SMC":
                        sig_val = eval_smc(df)
                    elif req_strategy == "SuperTrend":
                        sig_val = eval_supertrend(df)
                    elif req_strategy == "3 Velas":
                        sig_val = eval_consecutive(df, num_candles=3)
                    elif req_strategy == "Pin Bar":
                        sig_val = eval_pin_bar(df)
                    elif req_strategy == "ABCD":
                        sig_val = eval_abcd(df)
                        
                    signal = Signal(type=SignalType.NONE, reason="")
                    if sig_val == "CALL":
                        signal = Signal(type=SignalType.CALL, reason=f"Estratégia {req_strategy} indicou COMPRA no M{tf//60}")
                    elif sig_val == "PUT":
                        signal = Signal(type=SignalType.PUT, reason=f"Estratégia {req_strategy} indicou VENDA no M{tf//60}")
                        
                    if signal.type.value != "NONE":
                        strategy_info = f"M{tf//60}/{req_strategy}"

                    # === Stop Diário Automático (Trailing Floor) ===
                    dynamic_stop = -self.paper_trader.daily_stop_loss
                    if self.paper_trader.highest_daily_pnl >= self.paper_trader.daily_stop_gain:
                        dynamic_stop = self.paper_trader.highest_daily_pnl - self.paper_trader.daily_stop_gain
                        
                    if self.paper_trader.get_pnl() <= dynamic_stop:
                        if signal.type.value != "NONE":
                            logger.warning(f"🛑 [{self.symbol}] STOP DIÁRIO ATINGIDO (PnL: ${self.paper_trader.get_pnl():.2f} <= Piso: ${dynamic_stop:.2f}). Trades pausados.")
                            signal.type = SignalType.NONE

                    # === Filtros de Qualidade de Sinal (Fases 1+2) ===
                    if signal.type.value != "NONE":
                        # MTF: M5 usa M15 como referência superior; M1 usa M5
                        if tf == 300:
                            mtf_builder = self.builder_m15
                        else:
                            mtf_builder = self.builder_m5
                        df_mtf = candles_to_df(mtf_builder.closed_candles) if len(mtf_builder.closed_candles) >= 26 else None
                        if df_mtf is not None:
                            df_mtf = apply_indicators(df_mtf)
                        approved, block_reason = check_signal_quality(df, df_mtf, signal.type.value)
                        
                        # Macro Correlation Filter (Fase extra)
                        if approved and not self.check_macro_correlation(signal.type.value):
                            approved = False
                            block_reason = "Falta de correlação Macro com outras moedas (Swarm)"
                            
                        if not approved:
                            logger.info(f"🔎 [{self.symbol} - {strategy_info}] FILTRADO: {block_reason}")
                            signal.type = SignalType.NONE
                        else:
                            # === Filtro de Inteligência Artificial ===
                            ai_approved = await self.ai_filter.evaluate_signal(df, signal.type.value, req_strategy)
                            if not ai_approved:
                                logger.info(f"🤖 [{self.symbol} - {strategy_info}] FILTRADO: Rejeitado pela IA")
                                signal.type = SignalType.NONE
                            
                    if signal.type.value != "NONE":
                        # Update paper trader gale max before opening trade
                        self.paper_trader.max_gale = config.get("gale", 3)
                        self.last_signal_direction = "CALL" if signal.type.value == "BUY" else "PUT"
                        news_status = self.news_filter.check_safety(tick.epoch)
                        if not news_status["safe"]:
                            logger.warning(f"⛔ [{self.symbol} - {strategy_info}] BLOQUEADO NOTÍCIA: {news_status['reason']}")
                            signal.type = SignalType.NONE
                            
                    if signal.type.value != "NONE":
                        logger.info(f"🎯 [{self.symbol} - {strategy_info}] SINAL DETECTADO: {signal.type.value}")
                        await self.manager.broadcast({"event": "signal", "symbol": self.symbol, "data": {"type": signal.type.value, "reason": signal.reason, "strategy": strategy_info}})
                        
                        account_state = AccountState(
                            balance=self.paper_trader.balance, 
                            current_consecutive_losses=self.paper_trader.consecutive_losses, 
                            daily_pnl=self.paper_trader.get_pnl(),
                            highest_daily_pnl=self.paper_trader.highest_daily_pnl,
                            current_gale_level=self.paper_trader.consecutive_losses, 
                            daily_stop_loss=self.paper_trader.daily_stop_loss, 
                            daily_stop_gain=self.paper_trader.daily_stop_gain,
                            max_gale=self.paper_trader.max_gale, 
                            stake_initial=self.paper_trader.stake_initial
                        )
                        risk_eval = evaluate_risk(signal, account_state)
                        
                        try:
                            explanation = await explain_signal(signal, risk_eval.reason)
                            await self.manager.broadcast({"event": "agent_message", "symbol": self.symbol, "data": explanation})
                            
                            if risk_eval.decision.value == "BLOCKED":
                                logger.warning(f"⛔ [{self.symbol} - {strategy_info}] BLOQUEADO GESTOR: {risk_eval.reason}")
                            else:
                                atr_val = df.iloc[-1].get("ATRr_14", tick.quote * 0.005)
                                tp_multiplier = 3.0
                                sl_multiplier = 1.5
                                
                                if signal.type.value == "CALL":
                                    sl_price = tick.quote - (atr_val * sl_multiplier)
                                    tp_price = tick.quote + (atr_val * tp_multiplier)
                                else:
                                    sl_price = tick.quote + (atr_val * sl_multiplier)
                                    tp_price = tick.quote - (atr_val * tp_multiplier)
                                    
                                self.paper_trader.open_trade(signal.type.value, tf, tick.epoch, tick.quote, sl_price=sl_price, tp_price=tp_price, atr=atr_val)
                                await self.manager.broadcast({"event": "simulator", "symbol": self.symbol, "data": self.paper_trader.get_state()})
                                await self.manager.broadcast({"event": "trade_opened", "symbol": self.symbol, "data": {"direction": signal.type.value, "price": tick.quote}})
                                
                                import os
                                live_margin = self.paper_trader.get_current_margin_usdt()
                                
                                rsi_val = df.iloc[-1].get("RSI_14", 50.0)
                                if str(rsi_val) == "nan": rsi_val = 50.0
                                ai_text = explanation.get("analysis", str(explanation))
                                
                                if os.getenv("LIVE_TRADING") == "True":
                                    async def run_live_entry():
                                        res = await self.executor.execute_entry(self.symbol, signal.type.value, live_margin, self.paper_trader.leverage, tick.quote)
                                        if res["status"] == "success":
                                            self.live_qty = res.get("qty", 0)
                                            t_id = str(res["order"].get("id", f"live_{tick.epoch}"))
                                            self.active_trade_id = t_id
                                            self.journal.log_entry(t_id, self.symbol, signal.type.value, strategy_info, ai_text, tick.epoch, tick.quote, atr_val, float(rsi_val), live_margin, self.paper_trader.leverage)
                                        else:
                                            await self.manager.broadcast({
                                                "event": "agent_message",
                                                "symbol": self.symbol,
                                                "data": {"analysis": f"❌ ERRO CRÍTICO (Binance): Não foi possível abrir a ordem real. A API retornou: {res.get('error')}"}
                                            })
                                    asyncio.create_task(run_live_entry())
                                else:
                                    t_id = f"paper_{tick.epoch}"
                                    self.active_trade_id = t_id
                                    self.journal.log_entry(t_id, self.symbol, signal.type.value, strategy_info, ai_text, tick.epoch, tick.quote, atr_val, float(rsi_val), live_margin, self.paper_trader.leverage)
                        except Exception as e:
                            logger.error(f"Erro IA [{self.symbol}]: {e}")

    async def start(self):
        async def delayed_broadcast():
            await asyncio.sleep(5)
            await self.broadcast_catalog()
        asyncio.create_task(delayed_broadcast())
        await self.client.connect_and_listen()
        
    def stop(self):
        self.client.stop()
