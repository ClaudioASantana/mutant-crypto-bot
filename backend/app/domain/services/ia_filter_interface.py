"""
Interface abstrata para filtros de IA (Inteligência Artificial).

Define o contrato que qualquer implementação de filtro de IA deve seguir,
garantindo que as camadas superiores do domínio dependam de abstrações
e não de implementações concretas.
"""
from abc import ABC, abstractmethod
from typing import Dict
import pandas as pd


class AbstractAIFilter(ABC):
    """Abstração para filtros de decisão baseados em IA."""

    @abstractmethod
    async def make_decision(self, df: pd.DataFrame, strategy_name: str) -> Dict:
        """
        Analisa o contexto técnico e decide se entra no trade ou espera.

        Args:
            df: DataFrame com as velas recentes e indicadores técnicos.
            strategy_name: Nome da estratégia sendo avaliada.

        Returns:
            Dicionário com as chaves:
                - decision: "BUY" | "SELL" | "WAIT"
                - reason: justificativa textual
                - confidence: float entre 0.0 e 1.0
        """
        pass