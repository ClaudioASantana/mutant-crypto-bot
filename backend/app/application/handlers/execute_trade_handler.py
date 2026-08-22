import logging
import time
from typing import Dict, Any

from app.application.commands.execute_trade_command import ExecuteTradeCommand
from app.domain.entities.market import AccountState, Signal, SignalType
from app.domain.entities.paper_trader_state import PaperTraderState, RiskSettings
from app.domain.entities.personality import Personality, RiskProfile
from app.domain.entities.trade import Trade
from app.domain.exceptions import RiskLimitExceededException
from app.domain.repositories.paper_trader_state_repository import AbstractPaperTraderStateRepository
from app.domain.repositories.trade_repository import AbstractTradeRepository
from app.domain.services.risk_manager_interface import AbstractRiskManager
from app.domain.value_objects.enums import TradeSource

logger = logging.getLogger(__name__)


class ExecuteTradeHandler:
    """
    Handler para o ExecuteTradeCommand.

    Aplica as regras de negócio via `RiskManager`, lê o snapshot de conta pelo
    `AbstractPaperTraderStateRepository` e persiste a ordem manual no storage
    canônico via `AbstractTradeRepository`.
    """

    def __init__(
        self,
        risk_manager: AbstractRiskManager,
        paper_trader_state_repo: AbstractPaperTraderStateRepository,
        trade_repo: AbstractTradeRepository,
    ):
        self.risk_manager = risk_manager
        self.paper_trader_state_repo = paper_trader_state_repo
        self.trade_repo = trade_repo

    def handle(self, command: ExecuteTradeCommand, identity: str = "default") -> Dict[str, Any]:
        logger.info(f"Processando comando de trade para {command.symbol} ({command.direction})")

        # 1. Recupera o snapshot da conta. Se não existir, cria um snapshot seed
        # compatível com a antiga convenção do CQRS, mas agora tipado/canônico.
        state = self.paper_trader_state_repo.load(identity)
        if state is None:
            state = PaperTraderState(
                identity=identity,
                symbol=command.symbol,
                balance=10000.0,
                initial_balance=10000.0,
                highest_daily_pnl=0.0,
                leverage=1,
                risk_settings=RiskSettings(
                    daily_stop_loss=50.0,
                    daily_stop_gain=50.0,
                    stake_initial=10.0,
                    position_sizing_mode="fixed",
                    risk_percent=1.0,
                    trailing_activation=1.0,
                    trailing_distance=0.5,
                    max_trade_duration_minutes=60,
                ),
            )
            self.paper_trader_state_repo.save(state)

        # O CQRS manual ainda não tem uma personalidade real persistida nesta
        # rodada, então materializamos a personalidade default equivalente ao
        # comportamento antigo, mas sem cair no blob Shape B.
        personality = Personality(
            name="Default AI",
            strategy=command.strategy,
            timeframe=command.timeframe,
            risk_profile=RiskProfile(
                daily_stop_loss=state.risk_settings.daily_stop_loss,
                daily_stop_gain=state.risk_settings.daily_stop_gain,
                stake_initial=state.risk_settings.stake_initial,
                position_sizing_mode=state.risk_settings.position_sizing_mode,
                risk_percent=state.risk_settings.risk_percent,
                leverage=state.leverage,
                sl_multiplier=1.5,
                tp_multiplier=2.0,
                trailing_activation=state.risk_settings.trailing_activation,
                trailing_distance=state.risk_settings.trailing_distance,
                max_trade_duration_minutes=state.risk_settings.max_trade_duration_minutes,
            ),
        )

        account = AccountState(
            balance=state.balance,
            daily_pnl=state.pnl,
            highest_daily_pnl=state.highest_daily_pnl,
            daily_stop_loss=state.risk_settings.daily_stop_loss,
            daily_stop_gain=state.risk_settings.daily_stop_gain,
            stake_initial=state.risk_settings.stake_initial,
        )
        signal = Signal(type=SignalType(command.direction.upper()), reason=f"Strategy: {command.strategy}")

        # 2. Executa a regra de negócio do Domínio (Risk Manager)
        risk_evaluation = self.risk_manager.evaluate_pre_trade_risk(signal, account, personality)

        if risk_evaluation.decision.value == "BLOCKED":
            logger.warning(f"Trade bloqueado pelo RiskManager: {risk_evaluation.reason}")
            raise RiskLimitExceededException(risk_evaluation.reason)

        # 3. Calcula SL/TP e dimensionamento
        sizing = self.risk_manager.calculate_position_sizing(
            personality, account.balance, command.entry_price, command.atr, command.symbol
        )

        sl_tp = self.risk_manager.calculate_sl_tp(
            personality, command.entry_price, command.atr, command.direction.upper()
        )

        # 4. Persiste o trade canônico. Nesta rodada o CQRS manual só cria
        # `status=OPEN` / `source=MANUAL_CQRS`; o fechamento desse fluxo fica
        # explicitamente fora do escopo.
        trade = Trade.open_new(
            identity=identity,
            symbol=command.symbol,
            personality_name=personality.name,
            timeframe_seconds=command.timeframe,
            side=signal.type,
            entry_price=command.entry_price,
            entry_epoch=int(time.time()),
            source=TradeSource.MANUAL_CQRS,
            qty=sizing["qty"],
            margin=sizing["margin_usdt"],
            leverage=state.leverage,
            sl=sl_tp["sl_price"],
            tp=sl_tp["tp_price"],
            atr=command.atr,
            strategy=command.strategy,
            ai_reason=signal.reason,
            highest_reached=command.entry_price,
            lowest_reached=command.entry_price,
        )
        trade = self.trade_repo.add(trade)

        runtime_trade = trade.to_runtime_dict()
        runtime_trade["symbol"] = trade.symbol
        logger.info(f"Trade salvo com sucesso: {runtime_trade}")

        return {"status": "SUCCESS", "trade": runtime_trade}
