"""
Testes unitários para o carregador de configuração (ConfigurationLoader).

Garante que portfólios e personalidades são carregados corretamente de
arquivos JSON externos.
"""

import json
import os
import pytest
import tempfile

from app.infrastructure.config_loader import ConfigurationLoader, ServiceResolver
from app.domain.entities.personality import RiskProfile
from app.domain.entities.personality import RiskProfile # Importar RiskProfile

@pytest.fixture
def sample_portfolio_file():
    """Fixture que cria um arquivo JSON temporário com um portfólio de exemplo."""
    portfolio = {
        "BTC/USDT": [
            {
                "name": "Cirurgiao_M15",
                "strategy": "Wyckoff_SMC",
                "timeframe": 900,
                "risk_config": {"sl_multiplier": 1.5, "tp_multiplier": 8.0}
            },
            {
                "name": "Trabalhador_M5",
                "strategy": "SMC",
                "timeframe": 300,
                "risk_config": {"sl_multiplier": 1.5, "tp_multiplier": 3.0}
            }
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(portfolio, f)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def sample_services_file():
    """Fixture que cria um arquivo JSON temporário com configurações de serviços."""
    services = {
        "paper_trader_repository": {
            "implementation": "FakeRepository",
            "params": {"base_path": "test_data"}
        },
        "news_filter": {
            "implementation": "FakeNewsFilter",
            "params": {"block_minutes_before": 3}
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(services, f)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def clear_registry():
    """Limpa o registro antes e depois do teste para evitar poluição."""
    ServiceResolver._REGISTRY.clear()
    yield
    ServiceResolver._REGISTRY.clear()


class FakeRepository:
    def __init__(self, base_path: str = "data"):
        self.base_path = base_path


class FakeNewsFilter:
    def __init__(self, block_minutes_before: int = 5, block_minutes_after: int = 5):
        self.block_before = block_minutes_before * 60
        self.block_after = block_minutes_after * 60


def test_load_portfolios_success(sample_portfolio_file):
    """Deve carregar portfólios de um arquivo JSON válido."""
    config_loader = ConfigurationLoader()
    portfolios = config_loader.load_portfolios_from_json(sample_portfolio_file)

    assert "BTC/USDT" in portfolios
    assert len(portfolios["BTC/USDT"]) == 2

    p1 = portfolios["BTC/USDT"][0]
    assert p1.name == "Cirurgiao_M15"
    assert p1.strategy == "Wyckoff_SMC"
    assert p1.timeframe == 900
    assert p1.risk_profile.sl_multiplier == 1.5
    assert p1.risk_profile.tp_multiplier == 8.0

    p2 = portfolios["BTC/USDT"][1]
    assert p2.name == "Trabalhador_M5"
    assert p2.timeframe == 300
    assert p2.risk_profile.tp_multiplier == 3.0
    assert p2.risk_profile.position_sizing_mode == "fixed" # Default value


def test_load_portfolios_file_not_found():
    """Deve levantar FileNotFoundError se o arquivo não existir."""
    config_loader = ConfigurationLoader()
    with pytest.raises(FileNotFoundError):
        config_loader.load_portfolios_from_json("caminho/inexistente.json")


def test_load_service_configs_success(sample_services_file):
    """Deve carregar configurações de serviços de um arquivo JSON válido."""
    config_loader = ConfigurationLoader()
    configs = config_loader.load_service_configs_from_json(sample_services_file)

    assert "paper_trader_repository" in configs
    assert configs["paper_trader_repository"]["implementation"] == "FakeRepository"
    assert configs["paper_trader_repository"]["params"]["base_path"] == "test_data"

    assert configs["news_filter"]["implementation"] == "FakeNewsFilter"
    assert configs["news_filter"]["params"]["block_minutes_before"] == 3


def test_load_service_configs_file_not_found():
    """Deve levantar FileNotFoundError se o arquivo de serviços não existir."""
    config_loader = ConfigurationLoader()
    with pytest.raises(FileNotFoundError):
        config_loader.load_service_configs_from_json("caminho/inexistente.json")


def test_service_resolver_register_and_get():
    """Deve registrar e resolver implementações por nome."""
    ServiceResolver.register("FakeRepository", FakeRepository)
    assert ServiceResolver.get("FakeRepository") is FakeRepository


def test_service_resolver_unknown_name():
    """Deve levantar ValueError ao resolver um nome não registrado."""
    with pytest.raises(ValueError, match="Implementação 'Desconhecido' não registrada"):
        ServiceResolver.get("Desconhecido")


def test_build_services(sample_services_file, clear_registry):
    """Deve instanciar serviços concretos a partir das configurações carregadas."""
    ServiceResolver.register("FakeRepository", FakeRepository)
    ServiceResolver.register("FakeNewsFilter", FakeNewsFilter)

    config_loader = ConfigurationLoader()
    configs = config_loader.load_service_configs_from_json(sample_services_file)
    services = config_loader.build_services(configs)

    assert isinstance(services["paper_trader_repository"], FakeRepository)
    assert services["paper_trader_repository"].base_path == "test_data"

    assert isinstance(services["news_filter"], FakeNewsFilter)
    assert services["news_filter"].block_before == 3 * 60


def test_build_services_with_deferred_params(clear_registry):
    """Deve registrar serviços que precisam de parâmetros em runtime."""
    service_configs = {
        "trade_executor": {
            "implementation": "FakeTradeExecutor"
            # Sem "params" - não é instanciado automaticamente
        }
    }
    ServiceResolver.register("FakeTradeExecutor", FakeTradeExecutor)

    config_loader = ConfigurationLoader()
    services = config_loader.build_services(service_configs)

    # O serviço não deve estar no dicionário de instâncias criadas
    assert "trade_executor" not in services
    # Mas a implementação deve estar registrada e resolvível
    assert ServiceResolver.get("FakeTradeExecutor") is FakeTradeExecutor


class FakeTradeExecutor:
    def __init__(self, symbol: str, identity: str, repository):
        self.symbol = symbol
        self.identity = identity
        self.repository = repository