"""
Interface abstrata para provedores de dados de mercado.

Clean Architecture: define o contrato (Port) que qualquer implementação
de market data deve seguir. A camada de aplicação depende desta abstração,
e a implementação concreta vive em app/infrastructure/market_data/.
"""
from abc import ABC, abstractmethod
from typing import Callable

from app.domain.entities.market import Tick


class AbstractMarketDataProvider(ABC):
    """Abstração para provedores de dados de mercado em tempo real."""

    @abstractmethod
    def subscribe(self, symbol: str, callback: Callable[[Tick], None]) -> None:
        """Registra um callback para receber ticks de um símbolo específico."""
        ...

    @abstractmethod
    def unsubscribe(self, symbol: str, callback: Callable[[Tick], None]) -> None:
        """Remove o registro de um callback para um símbolo específico."""
        ...

    @abstractmethod
    async def start_client_for_symbol(self, symbol: str) -> None:
        """Inicia a conexão de dados de mercado para um símbolo."""
        ...

    @abstractmethod
    async def stop_all_clients(self) -> None:
        """Para todas as conexões ativas de dados de mercado."""
        ...
