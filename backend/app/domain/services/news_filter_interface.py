"""
Interface abstrata para filtros de segurança baseados em notícias.

Define o contrato que qualquer implementação de filtro de notícias deve
seguir, garantindo que as camadas superiores do domínio dependam de
abstrações e não de implementações concretas.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional


class AbstractNewsFilter(ABC):
    """Abstração para filtros de segurança por notícias."""

    @abstractmethod
    def check_safety(self, current_epoch: int) -> Dict:
        """
        Verifica se o mercado está na zona proibida de alguma notícia.

        Args:
            current_epoch: Timestamp atual em segundos.

        Returns:
            Dicionário com as chaves:
                - safe: bool indicando se pode operar
                - reason: justificativa textual
                - next_event: dict ou None com informações do próximo evento
        """
        pass