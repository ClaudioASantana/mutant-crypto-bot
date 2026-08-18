"""
Interface abstrata para executores de ordens em brokers.

Clean Architecture: define o contrato (Port) que qualquer implementação
de execução de ordens deve seguir (Binance, Deriv, etc.).
"""
from abc import ABC, abstractmethod
from typing import Optional


class AbstractTradeExecutor(ABC):
    """Abstração para executores de ordens em brokers."""

    @abstractmethod
    async def execute_entry(self, symbol: str, direction: str, **kwargs) -> dict:
        """Executa a entrada de uma ordem no broker."""
        ...

    @abstractmethod
    async def execute_exit(self, symbol: str, direction: str, **kwargs) -> dict:
        """Executa a saída de uma ordem no broker."""
        ...
