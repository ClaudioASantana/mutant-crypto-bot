"""
Compat shim para o port legado do PaperTrader.

O runtime novo está migrando para ports tipados separados:
- `AbstractPaperTraderStateRepository`
- `AbstractTradeRepository`

Este arquivo é mantido temporariamente para não quebrar scripts/testes legados
num único commit grande. Novo código não deve depender dele.
"""

from abc import ABC, abstractmethod


class AbstractPaperTraderRepository(ABC):
    """Contrato legado frouxo (`dict`) — manter apenas durante a transição."""

    @abstractmethod
    def load(self, identity: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, identity: str, state: dict) -> None:
        raise NotImplementedError
