"""Port do repositório de estado do PaperTrader.

Clean Architecture: o domínio define APENAS o contrato (interfaces/ports).
A implementação concreta vive em app/infrastructure/repositories/.
"""
from abc import ABC, abstractmethod


class AbstractPaperTraderRepository(ABC):
    """Contrato de persistência do estado de uma conta de simulação."""

    @abstractmethod
    def load(self, identity: str) -> dict | None:
        """Carrega o estado persistido. Retorna None se não existir."""
        raise NotImplementedError

    @abstractmethod
    def save(self, identity: str, state: dict) -> None:
        """Persiste o estado (idempotente, cria dirs se preciso)."""
        raise NotImplementedError