"""
Módulo para carregar configurações externas, como a definição de portfólios e personalidades.
"""

import json
import os
from typing import Dict, List
from app.domain.entities.personality import Personality


class ConfigurationLoader:
    """Carrega configurações de arquivos externos."""

    @staticmethod
    def load_portfolios_from_json(file_path: str) -> Dict[str, List[Personality]]:
        """
        Carrega a configuração de portfólios a partir de um arquivo JSON.

        Args:
            file_path: Caminho para o arquivo JSON de configuração.

        Returns:
            Um dicionário mapeando símbolos para listas de objetos Personality.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        portfolios = {}
        for symbol, personalities_data in data.items():
            personalities = [Personality(**p) for p in personalities_data]
            portfolios[symbol] = personalities

        return portfolios