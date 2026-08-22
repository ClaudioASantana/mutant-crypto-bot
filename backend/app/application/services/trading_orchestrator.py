import asyncio
import logging
import time
from typing import List, Dict, Callable
from app.domain.entities.personality import Personality
from app.domain.entities.performance import PersonalityPerformance
from app.domain.services.market_data_interface import AbstractMarketDataProvider
from app.application.services.candle_builder import CandleBuilder
from app.domain.services.personality_selector_service import PersonalitySelectorService
from app.domain.services.trading_decision_service import TradingDecisionService
from app.application.services.cataloger import calculate_win_rate
from app.application.services.technical_analysis import (
    candles_to_df, apply_indicators
)
from app.application.dtos.personality_dto import PersonalityStateDTO, RiskSettingsDTO, TradeDTO
from app.application.dtos.performance_dto import PersonalityPerformanceDTO
from app.application.dtos.trade_dto import TradingSignalDTO
from app.domain.entities.market import Tick, AccountState, CandleDirection
from app.domain.services.news_filter_interface import AbstractNewsFilter
from app.domain.services.ia_filter_interface import AbstractAIFilter
from app.domain.services.trade_executor_interface import AbstractTradeExecutor
from app.domain.services.risk_manager_interface import AbstractRiskManager

logger = logging.getLogger(__name__)

# Constantes do Seletor Dinamico de Personalidades
SELECTOR_RESET_AFTER_SECONDS = 4 * 3600  # Reinicia janela de performance a cada 4h
SELECTOR_MAX_WINDOW_TRADES = 15          # Considera as ultimas 15 operacoes
SELECTOR_MIN_TRADES = 3                  # Exige minimo de trades antes de penalizar
SELECTOR_MAX_CONSECUTIVE_LOSSES = 4      # Apos 4 perdas seguidas, personalidade e desativada
SELECTOR_HYSTERESIS = 5.0                # Margem de fitness para trocar a personalidade ativa


class TradingOrchestrator:
    def __init__(self,
                 symbol: str,
                 token: str,
                 news_filter: AbstractNewsFilter,
                 manager,
                 personalities: List[Personality],
                 ai_filter: AbstractAIFilter,
                 market_provider: AbstractMarketDataProvider,
                 trade_executor_factory: Callable[..., AbstractTradeExecutor],
                 risk_manager: AbstractRiskManager,
                 swarm_bots: dict = None):
        self.symbol = symbol
        self.token = token
        self.news_filter = news_filter
        self.manager = manager
        self.swarm_bots = swarm_bots or {}
        self.personalities = {p.name: p for p in personalities}  # Dict for fast lookup

        # Dependências injetadas (Dependency Inversion Principle)
        self.market_provider = market_provider
        self.market_provider.subscribe(self.symbol, self.on_tick)

        # Initialize builders
        self.builder_m1 = CandleBuilder(60)
        self.builder_m5 = CandleBuilder(300)
        self.builder_m15 = CandleBuilder(900)

        # Create one TradeExecutor per personality with unique state files
        self.paper_traders: Dict[str, AbstractTradeExecutor] = {}
        for personality in personalities:
            state_filename = f"simulator_state_{self.symbol.replace('/', '_')}_{personality.name}_{personality.timeframe//60}m.json"
            trader = trade_executor_factory(
                symbol=self.symbol,
                identity=state_filename,
                initial_balance=200.0,
                leverage=10,
                position_sizing_mode=personality.risk_profile.position_sizing_mode,
                risk_manager=risk_manager
            )
            self.paper_traders[personality.name] = trader

        self.ai_filter = ai_filter
        self.live_qty = 0
        # Trava lógica: no máximo um trade ativo por personalidade. A
        # persistência do lifecycle do trade (abertura/fechamento) já
        # acontece dentro do próprio `trader` (tabela `trades` canônica);
        # isto aqui não é mais um journal, é só um guard-rail em memória.
        self.active_trade_ids = {}  # Track active trade IDs per personality

        # --- Dynamic Personality Selector ---
        self.performance_trackers: Dict[str, PersonalityPerformance] = {}
        for p_name in self.personalities:
            self.performance_trackers[p_name] = PersonalityPerformance(personality_name=p_name, symbol=self.symbol)
        self.active_personality_name: str = next(iter(self.personalities.keys())) # Inicia com a primeira por padrao

        # Serviço de seleção de personalidade (injetado)
        self.selector_service = PersonalitySelectorService(
            reset_after_seconds=SELECTOR_RESET_AFTER_SECONDS,
            min_trades_for_fitness=SELECTOR_MIN_TRADES,
            max_consecutive_losses=SELECTOR_MAX_CONSECUTIVE_LOSSES,
            hysteresis_margin=SELECTOR_HYSTERESIS
        )

        # Serviço de decisão de trade (injetado)
        self.trading_decision_service = TradingDecisionService(self.news_filter, self.ai_filter, risk_manager)


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


    async def on_history(self, granularity: int, candles: list):
        from app.domain.entities.market import Candle
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
                personality = self.personalities[p_name]
                finished_trades = trader.check_positions(tick.epoch, tick.quote, personality)
                if finished_trades:
                    # Update journal and broadcast state for the specific personality
                    for trade in finished_trades:
                        if p_name in self.active_trade_ids and self.active_trade_ids[p_name] == trade["id"]:
                            # O fechamento já foi persistido na tabela `trades`
                            # canônica dentro de `trader.check_positions(...)`.

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
        best_personality_name = self.selector_service.select_best(
            self.performance_trackers,
            self.active_personality_name
        )
        # Atualizar o nome da personalidade ativa para logging
        self.active_personality_name = best_personality_name

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

                # Avaliar decisão de trade usando o serviço de domínio
                account_state = AccountState(
                    balance=trader.balance, daily_pnl=trader.get_pnl(),
                    highest_daily_pnl=trader.highest_daily_pnl,
                    daily_stop_loss=trader.daily_stop_loss,
                    daily_stop_gain=trader.daily_stop_gain,
                    stake_initial=trader.stake_initial
                )

                decision: TradingSignalDTO = await self.trading_decision_service.evaluate(
                    personality=personality,
                    account_state=account_state,
                    df_candles=df,
                    tick=tick,
                    atr=atr
                )

                if decision:
                    # Abrir trade se a decisão foi aprovada
                    trader.open_trade(
                        direction=decision.direction.value,
                        tf=personality.timeframe,
                        current_epoch=tick.epoch,
                        current_price=decision.entry_price,
                        sl_price=decision.sl_price,
                        tp_price=decision.tp_price,
                        atr=decision.atr,
                        personality=personality,
                        strategy=decision.strategy_info,
                        ai_reason=decision.reason,
                        ai_confidence=decision.ai_confidence,
                        ai_context=decision.ai_context,
                    )

                    # Trava lógica em memória: a abertura em si já foi
                    # persistida na tabela `trades` canônica dentro de
                    # `trader.open_trade(...)`.
                    t_id = trader.open_positions[-1]["id"]
                    self.active_trade_ids[p_name] = t_id
                    await self.manager.broadcast({
                        "event": "trade_opened",
                        "symbol": self.symbol,
                        "data": {
                            "direction": decision.direction.value,
                            "price": decision.entry_price,
                            "personality": p_name
                        }
                    })
                    await self.broadcast_state()

        self.last_tick_time = tick.epoch

    async def start(self):
        # Start Binance client via MarketDataProvider
        await self.market_provider.start_client_for_symbol(self.symbol)

    def stop(self):
        # Unsubscribe from MarketDataProvider
        self.market_provider.unsubscribe(self.symbol, self.on_tick)

    def _build_personality_state_dto(self, trader) -> PersonalityStateDTO:
        """
        Constrói um PersonalityStateDTO a partir do estado bruto de um TradeExecutor.

        Args:
            trader: Instância de AbstractTradeExecutor.

        Returns:
            PersonalityStateDTO preenchido com os dados do trader.
        """
        state_dict = trader.get_state()
        # Convert the state dictionary to PersonalityStateDTO
        risk_dict = state_dict.pop('risk')
        risk_settings = RiskSettingsDTO(**risk_dict)
        pending_trades = [TradeDTO(**trade) for trade in state_dict.pop('pending')]
        history_trades = [TradeDTO(**trade) for trade in state_dict.pop('history')]
        return PersonalityStateDTO(
            risk=risk_settings,
            pending=pending_trades,
            history=history_trades,
            **state_dict
        )

    async def broadcast_state(self):
        # Broadcast combined state of all personalities
        personalities_state = {}
        for name, trader in self.paper_traders.items():
            personality_state_dto = self._build_personality_state_dto(trader)
            personalities_state[name] = personality_state_dto.dict()

        performances_state = {}
        for name, perf in self.performance_trackers.items():
            # Create PersonalityPerformanceDTO from PersonalityPerformance entity
            perf_dto = PersonalityPerformanceDTO(
                personality_name=perf.personality_name,
                symbol=perf.symbol,
                wins=perf.wins,
                losses=perf.losses,
                total_pnl=perf.total_pnl,
                trades_count=perf.trades_count,
                consecutive_losses=perf.consecutive_losses,
                win_rate=perf.win_rate,
                fitness=perf.fitness,
                last_trade_epoch=perf.last_trade_epoch,
                last_update=perf.last_update
            )
            performances_state[name] = perf_dto.dict()

        combined_state = {
            "personalities": personalities_state,
            "risk": {"atr": self.last_atr_cache},  # Store ATR for all timeframes
            "selector": {
                "active_personality": self.active_personality_name,
                "performances": performances_state
            }
        }
        await self.manager.broadcast({"event": "simulator", "symbol": self.symbol, "data": combined_state})
