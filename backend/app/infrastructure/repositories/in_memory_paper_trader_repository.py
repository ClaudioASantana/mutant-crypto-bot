"""Repositório composto em memória: `PaperTraderState` + `Trade`.

Usado por backtest/fine-tune e testes — nunca pelo runtime principal do swarm,
que usa o par SQLAlchemy canônico. Implementa os dois ports tipados atrás de um
único objeto, pelo mesmo motivo do composto SQLAlchemy: preservar
`PaperTrader(repository=InMemoryPaperTraderRepository())` como assinatura única,
sem editar os ~10 scripts de backtest que a usam.
"""

from typing import Optional

from app.domain.entities.paper_trader_state import PaperTraderState
from app.domain.entities.trade import Trade
from app.domain.repositories.paper_trader_state_repository import AbstractPaperTraderStateRepository
from app.domain.repositories.trade_repository import AbstractTradeRepository
from app.domain.value_objects.enums import TradeStatus


class InMemoryPaperTraderRepository(AbstractPaperTraderStateRepository, AbstractTradeRepository):
    """Repositório em memória para uso em testes e backtesting."""

    def __init__(self):
        self._states: dict[str, PaperTraderState] = {}
        self._trades: dict[str, Trade] = {}

    # --- AbstractPaperTraderStateRepository ---

    def load(self, identity: str) -> Optional[PaperTraderState]:
        return self._states.get(identity)

    def save(self, state: PaperTraderState) -> None:
        self._states[state.identity] = state

    # --- AbstractTradeRepository ---

    def add(self, trade: Trade) -> Trade:
        if trade.id in self._trades:
            raise ValueError(f"Trade {trade.id} already exists")
        self._trades[trade.id] = trade
        return trade

    def update(self, trade: Trade) -> Trade:
        if trade.id not in self._trades:
            raise ValueError(f"Trade {trade.id} does not exist")
        self._trades[trade.id] = trade
        return trade

    def get_by_id(self, trade_id: str) -> Optional[Trade]:
        return self._trades.get(trade_id)

    def list_active(self, identity: str, symbol: Optional[str] = None) -> list[Trade]:
        return [
            t
            for t in self._trades.values()
            if t.identity == identity
            and t.status is TradeStatus.OPEN
            and (symbol is None or t.symbol == symbol)
        ]

    def list_history(self, identity: str, limit: int = 50) -> list[Trade]:
        closed = [
            t
            for t in self._trades.values()
            if t.identity == identity and t.status is not TradeStatus.OPEN
        ]
        closed.sort(key=lambda t: t.exit_epoch or t.entry_epoch, reverse=True)
        return closed[:limit]
