"""Repositório SQLAlchemy canônico para `PaperTraderState`.

Persistência por snapshot operacional (upsert por `identity`), separada do ciclo
de vida dos trades, que mora em `TradeRepository`.
"""

from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.domain.entities.paper_trader_state import PaperTraderState, RiskSettings
from app.domain.repositories.paper_trader_state_repository import AbstractPaperTraderStateRepository
from app.infrastructure.database.database import SessionLocal
from app.infrastructure.database.models.paper_trader_state_model import PaperTraderStateModel


class SqlAlchemyPaperTraderStateRepository(AbstractPaperTraderStateRepository):
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal):
        self._session_factory = session_factory

    def load(self, identity: str) -> Optional[PaperTraderState]:
        with self._session_factory() as session:
            model = session.get(PaperTraderStateModel, identity)
            if model is None:
                return None
            return self._to_domain(model)

    def save(self, state: PaperTraderState) -> None:
        with self._session_factory() as session:
            model = session.get(PaperTraderStateModel, state.identity)
            if model is None:
                model = PaperTraderStateModel(identity=state.identity)
                session.add(model)

            self._apply_domain_to_model(state, model)
            session.commit()

    def _to_domain(self, model: PaperTraderStateModel) -> PaperTraderState:
        return PaperTraderState(
            identity=model.identity,
            symbol=model.symbol,
            personality_name=model.personality_name,
            timeframe_seconds=model.timeframe_seconds,
            balance=model.balance,
            initial_balance=model.initial_balance,
            consecutive_losses=model.consecutive_losses,
            highest_daily_pnl=model.highest_daily_pnl,
            leverage=model.leverage,
            risk_settings=RiskSettings(
                daily_stop_loss=model.daily_stop_loss,
                daily_stop_gain=model.daily_stop_gain,
                stake_initial=model.stake_initial,
                trailing_activation=model.trailing_activation,
                trailing_distance=model.trailing_distance,
                position_sizing_mode=model.position_sizing_mode,
                risk_percent=model.risk_percent,
                max_trade_duration_minutes=model.max_trade_duration_minutes,
            ),
        )

    def _apply_domain_to_model(self, state: PaperTraderState, model: PaperTraderStateModel) -> None:
        risk = state.risk_settings
        model.symbol = state.symbol
        model.personality_name = state.personality_name
        model.timeframe_seconds = state.timeframe_seconds
        model.balance = state.balance
        model.initial_balance = state.initial_balance
        model.consecutive_losses = state.consecutive_losses
        model.highest_daily_pnl = state.highest_daily_pnl
        model.leverage = state.leverage
        model.daily_stop_loss = risk.daily_stop_loss
        model.daily_stop_gain = risk.daily_stop_gain
        model.stake_initial = risk.stake_initial
        model.trailing_activation = risk.trailing_activation
        model.trailing_distance = risk.trailing_distance
        model.position_sizing_mode = risk.position_sizing_mode
        model.risk_percent = risk.risk_percent
        model.max_trade_duration_minutes = risk.max_trade_duration_minutes
