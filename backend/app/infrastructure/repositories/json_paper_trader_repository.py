"""Implementação do repositório de estado do PaperTrader usando arquivos JSON.

Clean Architecture: esta é a camada de INFRAESTRUTURA (Adapters).
Ela implementa o contrato (Port) definido na camada de DOMÍNIO.
"""
import json
import os
import logging
from abc import ABC, abstractmethod

from app.domain.repositories.paper_trader_repository import AbstractPaperTraderRepository

logger = logging.getLogger(__name__)

class JsonPaperTraderRepository(AbstractPaperTraderRepository):
    """Repositório que persiste o estado do PaperTrader em arquivos JSON."""

    def __init__(self, base_path: str = "data"):
        """
        Inicializa o repositório.
        Args:
            base_path: Caminho base onde os arquivos de estado serão salvos.
                       (e.g., 'data' que mapeia para /app/data no Docker)
        """
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True) # Garante que o diretório exista

    def _get_file_path(self, identity: str) -> str:
        """Retorna o caminho completo do arquivo de estado."""
        return os.path.join(self.base_path, identity)

    def load(self, identity: str) -> dict | None:
        file_path = self._get_file_path(identity)
        try:
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    state = json.load(f)
                    logger.info(f"💾 [PaperTraderRepo] Estado '{identity}' carregado de '{file_path}'.")
                    return state
            return None
        except Exception as e:
            logger.error(f"Erro ao carregar estado '{identity}' de '{file_path}': {e}")
            return None

    def save(self, identity: str, state: dict) -> None:
        file_path = self._get_file_path(identity)
        try:
            with open(file_path, "w") as f:
                json.dump(state, f, indent=4)
            logger.info(f"✅ [PaperTraderRepo] Estado '{identity}' salvo em '{file_path}'.")
        except Exception as e:
            logger.error(f"Erro ao salvar estado '{identity}' em '{file_path}': {e}")
