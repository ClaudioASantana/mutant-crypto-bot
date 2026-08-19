"""Interface (Port) para Simuladores de Backtest.

Clean Architecture: esta é uma interface do domínio.
Define o contrato para qualquer implementação de simulação de backtest,
seguindo o Princípio de Inversão de Dependência (DIP).
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from app.domain.entities.market import Candle
from app.domain.entities.personality import Personality


class AbstractBacktestSimulator(ABC):
    """Define os métodos que um simulador de backtest deve implementar."""

    @abstractmethod
    def simulate_strategy(
        self,
        history: List[Candle],
        personality: Personality
    ) -> Dict[str, Any]:
        """
        Simula a execução de uma estratégia sobre um histórico de velas.

        Args:
            history: Lista de velas (Candle) representando o histórico do ativo.
            personality: A personalidade contendo a estratégia e parâmetros de risco.

        Returns:
            Um dicionário contendo os resultados da simulação:
            - signals: Número total de sinais gerados.
            - wins: Número de trades vencedores.
            - losses: Número de trades perdedores.
            - win_rate: Porcentagem de trades vencedores.
            - pnl_usdt: PnL (Profit and Loss) total em USD.
            - trades: Lista detalhada de trades executados.
        """
        pass