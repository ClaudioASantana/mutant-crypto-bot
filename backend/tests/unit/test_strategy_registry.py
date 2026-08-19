"""
Testes unitários para o registro de estratégias (StrategyRegistry).

Garante que estratégias podem ser registradas dinamicamente e resolvidas
em tempo de execução, validando o princípio OCP.
"""

import pytest

from app.domain.services.strategy_registry import StrategyRegistry, register_strategy
from app.domain.entities.market import CandleDirection


def test_register_and_get_strategy():
    """Deve registrar uma estratégia e recuperá-la pelo nome."""
    registry = StrategyRegistry()
    registry._strategies.clear()

    @registry.register("Estrategia_Teste")
    def estrategia_teste(df_candles):
        return "CALL"

    strategy = registry.get("Estrategia_Teste")
    assert strategy is not None
    assert strategy(None) == "CALL"


def test_get_unregistered_strategy_returns_none():
    """Deve retornar None ao buscar uma estratégia não registrada."""
    registry = StrategyRegistry()
    registry._strategies.clear()

    assert registry.get("Nao_Existe") is None


def test_register_strategy_decorator_alias():
    """O alias register_strategy deve funcionar como decorator global."""
    StrategyRegistry._strategies.clear()

    @register_strategy("SMC_Alias")
    def smc_alias(df_candles):
        return "PUT"

    recovered = StrategyRegistry.get("SMC_Alias")
    assert recovered is not None
    assert recovered(None) == "PUT"


def test_list_all_strategies():
    """Deve listar todas as estratégias registradas."""
    StrategyRegistry._strategies.clear()

    @register_strategy("A")
    def strategy_a(df_candles):
        return "CALL"

    @register_strategy("B")
    def strategy_b(df_candles):
        return "PUT"

    all_strategies = StrategyRegistry.list_all()
    assert "A" in all_strategies
    assert "B" in all_strategies
    assert len(all_strategies) >= 2