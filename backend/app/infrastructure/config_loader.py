import json
import os
from typing import Any, Callable, Dict, List, Type
from app.domain.entities.personality import Personality, RiskProfile


class ServiceResolver:
    """
    Resolve implementações concretas por nome a partir de um registro interno.

    Permite que a escolha de repositórios, filtros, provedores de dados e executores
    seja feita exclusivamente via configuração externa, sem alterar o Composition Root.
    """

    _REGISTRY: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str, impl_class: Type) -> None:
        """Registra uma implementação concreta sob um nome amigável."""
        cls._REGISTRY[name] = impl_class

    @classmethod
    def get(cls, name: str) -> Type:
        """Retorna a classe registrada para o nome informado."""
        if name not in cls._REGISTRY:
            raise ValueError(f"Implementação '{name}' não registrada no ServiceResolver.")
        return cls._REGISTRY[name]


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
            personalities = []
            for p_data in personalities_data:
                # Extrair risk_config e criar RiskProfile primeiro
                risk_config_data = p_data.pop("risk_config", {})
                risk_profile = RiskProfile(**risk_config_data)
                # Criar Personality com o RiskProfile
                personalities.append(Personality(risk_profile=risk_profile, **p_data))
            portfolios[symbol] = personalities

        return portfolios

    @staticmethod
    def load_service_configs_from_json(file_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Carrega a configuração de serviços a partir de um arquivo JSON.

        Args:
            file_path: Caminho para o arquivo JSON de configuração.

        Returns:
            Um dicionário mapeando nomes de serviço para suas configurações
            (implementação e parâmetros).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Arquivo de configuração de serviços não encontrado: {file_path}"
            )

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    @staticmethod
    def build_services(service_configs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Instancia serviços concretos a partir das configurações carregadas.

        Args:
            service_configs: Dicionário retornado por `load_service_configs_from_json`.

        Returns:
            Um dicionário mapeando nomes de serviço para instâncias criadas.
            Serviços sem `params` são registrados no resolver, mas não instanciados
            automaticamente (útil para executores que precisam de parâmetros
            somente disponíveis em runtime).
        """
        services: Dict[str, Any] = {}
        for service_name, config in service_configs.items():
            impl_name = config.get("implementation")
            params = config.get("params")
            impl_class = ServiceResolver.get(impl_name)
            if params is None:
                # Serviço configurado, mas precisa de parâmetros em runtime
                # (ex: PaperTrader). Apenas validamos que a implementação existe.
                continue
            services[service_name] = impl_class(**params)
        return services
