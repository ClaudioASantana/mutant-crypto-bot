"""Repositório SQLAlchemy canônico para `Trade`.

Abre uma sessão curta por operação via `session_factory`, seguindo o padrão do
baseline `mutante-opcoes-acoes`: nada de `Session` singleton retida no loop do
swarm, e commit acontece dentro do repositório.
"""

from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.domain.entities.trade import Trade
from app.domain.repositories.trade_repository import AbstractTradeRepository
from app.domain.value_objects.enums import ACTIVE_STATUSES, TradeOutcome, TradeSide, TradeSource, TradeStatus
from app.infrastructure.database.database import SessionLocal
from app.infrastructure.database.models.trade_model import TradeModel


class SqlAlchemyTradeRepository(AbstractTradeRepository):
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal):
        self._session_factory = session_factory

    def add(self, trade: Trade) -> Trade:
        with self._session_factory() as session:
            existing = session.get(TradeModel, trade.id)
            if existing is not None:
                raise ValueError(f"Trade {trade.id} already exists")

            model = self._to_model(trade)
            session.add(model)
            session.commit()
            return self._to_domain(model)

    def update(self, trade: Trade) -> Trade:
        with self._session_factory() as session:
            model = session.get(TradeModel, trade.id)
            if model is None:
                raise ValueError(f"Trade {trade.id} does not exist")

            self._apply_domain_to_model(trade, model)
            session.commit()
            return self._to_domain(model)

    def get_by_id(self, trade_id: str) -> Optional[Trade]:
        with self._session_factory() as session:
            model = session.get(TradeModel, trade_id)
            if model is None:
                return None
            return self._to_domain(model)

    def list_active(self, identity: str, symbol: Optional[str] = None) -> list[Trade]:
        with self._session_factory() as session:
            query = session.query(TradeModel).filter(
                TradeModel.identity == identity,
                TradeModel.status.in_([status.value for status in ACTIVE_STATUSES]),
            )
            if symbol:
                query = query.filter(TradeModel.symbol == symbol)
            rows = query.order_by(TradeModel.entry_epoch.desc()).all()
            return [self._to_domain(row) for row in rows]

    def list_history(self, identity: str, limit: int = 50) -> list[Trade]:
        with self._session_factory() as session:
            rows = (
                session.query(TradeModel)
                .filter(
                    TradeModel.identity == identity,
                    TradeModel.status != TradeStatus.OPEN.value,
                )
                .order_by(TradeModel.exit_epoch.desc(), TradeModel.entry_epoch.desc())
                .limit(limit)
                .all()
            )
            return [self._to_domain(row) for row in rows]

    def _to_domain(self, model: TradeModel) -> Trade:
        return Trade(
            id=model.id,
            identity=model.identity,
            symbol=model.symbol,
            personality_name=model.personality_name,
            timeframe_seconds=model.timeframe_seconds,
            side=TradeSide(model.side),
            status=TradeStatus(model.status),
            outcome=TradeOutcome(model.outcome) if model.outcome else None,
            source=TradeSource(model.source),
            entry_price=model.entry_price,
            entry_epoch=model.entry_epoch,
            qty=model.qty,
            margin=model.margin,
            leverage=model.leverage,
            sl=model.sl,
            tp=model.tp,
            exit_price=model.exit_price,
            exit_epoch=model.exit_epoch,
            pnl=model.pnl,
            close_reason=model.close_reason,
            atr=model.atr,
            rsi=model.rsi,
            highest_reached=model.highest_reached,
            lowest_reached=model.lowest_reached,
            strategy=model.strategy,
            ai_reason=model.ai_reason,
            ai_confidence=model.ai_confidence,
            ai_context=model.ai_context,
            notes=model.notes,
        )

    def _to_model(self, trade: Trade) -> TradeModel:
        model = TradeModel(id=trade.id)
        self._apply_domain_to_model(trade, model)
        return model

    def _apply_domain_to_model(self, trade: Trade, model: TradeModel) -> None:
        model.identity = trade.identity
        model.symbol = trade.symbol
        model.personality_name = trade.personality_name
        model.timeframe_seconds = trade.timeframe_seconds
        model.side = trade.side.value
        model.status = trade.status.value
        model.outcome = trade.outcome.value if trade.outcome is not None else None
        model.source = trade.source.value
        model.entry_price = trade.entry_price
        model.entry_epoch = trade.entry_epoch
        model.qty = trade.qty
        model.margin = trade.margin
        model.leverage = trade.leverage
        model.sl = trade.sl
        model.tp = trade.tp
        model.exit_price = trade.exit_price
        model.exit_epoch = trade.exit_epoch
        model.pnl = trade.pnl
        model.close_reason = trade.close_reason
        model.atr = trade.atr
        model.rsi = trade.rsi
        model.highest_reached = trade.highest_reached
        model.lowest_reached = trade.lowest_reached
        model.strategy = trade.strategy
        model.ai_reason = trade.ai_reason
        model.ai_confidence = trade.ai_confidence
        model.ai_context = trade.ai_context
        model.notes = trade.notes
