"""Port de persistência para o snapshot operacional `PaperTraderState`."""

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.entities.paper_trader_state import PaperTraderState


class AbstractPaperTraderStateRepository(ABC):
    """
    Contrato de persistência do estado de uma conta de simulação.

    Substitui `AbstractPaperTraderRepository.load/save(dict)`: o contrato agora é
    tipado, então Shape A e Shape B não podem mais conviver silenciosamente sob a
    mesma interface — divergir vira erro de tipo, não corrupção de dado.
    """

    @abstractmethod
    def load(self, identity: str) -> Optional[PaperTraderState]:
        """Carrega o snapshot persistido. Retorna None se não existir."""
        raise NotImplementedError

    @abstractmethod
    def save(self, state: PaperTraderState) -> None:
        """Persiste o snapshot (idempotente / upsert por `identity`)."""
        raise NotImplementedError
