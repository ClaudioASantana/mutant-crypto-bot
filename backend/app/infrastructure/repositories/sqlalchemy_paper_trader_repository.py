"""Repositório composto SQLAlchemy: `PaperTraderState` + `Trade`.

Default de runtime do swarm principal. Implementa os dois ports tipados atrás
de um único objeto — pelo mesmo motivo dos compostos JSON/InMemory: preservar
`PaperTrader(repository=...)` como assinatura única, sem editar os scripts de
backtest nem a composition root.

Internamente delega para os dois repositórios canônicos já testados
isoladamente (`SqlAlchemyPaperTraderStateRepository` e
`SqlAlchemyTradeRepository`), cada um abrindo sua própria sessão curta por
operação via `session_factory` — nenhuma `Session` é retida entre chamadas.
"""

from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.domain.entities.paper_trader_state import PaperTraderState
from app.domain.entities.trade import Trade
from app.domain.repositories.paper_trader_state_repository import AbstractPaperTraderStateRepository
from app.domain.repositories.trade_repository import AbstractTradeRepository
from app.infrastructure.database.database import SessionLocal
from app.infrastructure.repositories.sqlalchemy_paper_trader_state_repository import (
    SqlAlchemyPaperTraderStateRepository,
)
from app.infrastructure.repositories.sqlalchemy_trade_repository import SqlAlchemyTradeRepository


class SqlAlchemyPaperTraderRepository(AbstractPaperTraderStateRepository, AbstractTradeRepository):
    """Repositório composto canônico para uso no runtime principal do swarm."""

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal):
        self._state_repo = SqlAlchemyPaperTraderStateRepository(session_factory=session_factory)
        self._trade_repo = SqlAlchemyTradeRepository(session_factory=session_factory)

    # --- AbstractPaperTraderStateRepository ---

    def load(self, identity: str) -> Optional[PaperTraderState]:
        return self._state_repo.load(identity)

    def save(self, state: PaperTraderState) -> None:
        self._state_repo.save(state)

    # --- AbstractTradeRepository ---

    def add(self, trade: Trade) -> Trade:
        return self._trade_repo.add(trade)

    def update(self, trade: Trade) -> Trade:
        return self._trade_repo.update(trade)

    def get_by_id(self, trade_id: str) -> Optional[Trade]:
        return self._trade_repo.get_by_id(trade_id)

    def list_active(self, identity: str, symbol: Optional[str] = None) -> list[Trade]:
        return self._trade_repo.list_active(identity, symbol=symbol)

    def list_history(self, identity: str, limit: int = 50) -> list[Trade]:
        return self._trade_repo.list_history(identity, limit=limit)
