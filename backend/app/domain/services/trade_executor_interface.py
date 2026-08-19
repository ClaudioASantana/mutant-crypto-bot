from abc import ABC, abstractmethod
from typing import Dict, List, Any


class AbstractTradeExecutor(ABC):
    """Abstração para executores de trades."""

    @abstractmethod
    def open_trade(self, direction: str, tf: int, current_epoch: int, current_price: float, sl_price: float, tp_price: float, atr: float = 0.0, personality: Any = None) -> None:
        """Abre uma nova posição."""
        pass

    @abstractmethod
    def check_positions(self, current_epoch: int, current_price: float, personality: Any = None) -> List[Dict[str, Any]]:
        """Verifica as posições abertas e as fecha se necessário."""
        pass

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Retorna o estado atual do executor."""
        pass

    @abstractmethod
    def save_state(self) -> None:
        """Salva o estado atual do executor."""
        pass

    @abstractmethod
    def load_state(self) -> None:
        """Carrega o estado do executor."""
        pass

    @abstractmethod
    def get_pnl(self) -> float:
        """Retorna o PnL (Profit and Loss) atual."""
        pass
