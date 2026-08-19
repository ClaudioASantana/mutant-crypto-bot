"""Implementação de um repositório de estado em memória.

Clean Architecture: esta é a camada de INFRAESTRUTURA.
Esta implementação concreta depende apenas de abstrações do domínio.
"""
from app.domain.repositories.paper_trader_repository import AbstractPaperTraderRepository

class InMemoryPaperTraderRepository(AbstractPaperTraderRepository):
    """Repositório em memória para uso em testes e backtesting."""

    def __init__(self):
        self._store = {}

    def load(self, identity: str):
        return self._store.get(identity)

    def save(self, identity: str, state: dict) -> None:
        self._store[identity] = state