"""Port de persistência para o agregado `Trade` (ciclo de vida + journal)."""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.entities.trade import Trade


class AbstractTradeRepository(ABC):
    """Contrato de persistência de trades. Substitui o `journal.db` write-only."""

    @abstractmethod
    def add(self, trade: Trade) -> Trade:
        """Persiste um trade novo (INSERT). Não faz upsert."""
        raise NotImplementedError

    @abstractmethod
    def update(self, trade: Trade) -> Trade:
        """Persiste alterações de um trade existente (ex.: fechamento)."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, trade_id: str) -> Optional[Trade]:
        raise NotImplementedError

    @abstractmethod
    def list_active(self, identity: str, symbol: Optional[str] = None) -> List[Trade]:
        """Trades com `status=OPEN` para a identidade (e símbolo, se informado)."""
        raise NotImplementedError

    @abstractmethod
    def list_history(self, identity: str, limit: int = 50) -> List[Trade]:
        """Trades encerrados (CLOSED/CANCELLED/REJECTED), mais recentes primeiro."""
        raise NotImplementedError
