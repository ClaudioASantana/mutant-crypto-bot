"""Testes unitários do BacktestSimulatorImpl com métricas centralizadas."""

from app.application.services.backtest_metrics import TradingCostConfig
from app.domain.entities.market import Candle
from app.domain.entities.personality import Personality, RiskProfile
from app.infrastructure.repositories.in_memory_paper_trader_repository import InMemoryPaperTraderRepository
from app.infrastructure.services.backtest_simulation_impl import BacktestSimulatorImpl
from app.infrastructure.services.paper_trader_executor import PaperTrader
from tests.unit.mock_risk_manager import MockRiskManager


class StubSimulator(BacktestSimulatorImpl):
    """Simulador determinístico para testar apenas o pós-processamento."""

    def _get_strategy_func(self, name):  # pragma: no cover - API compat
        return lambda _df: "NONE"

    def simulate_strategy(self, history, personality):  # pragma: no cover - unused
        return super().simulate_strategy(history, personality)


def _build_history(n=60, start=1_700_000_000):
    candles = []
    price = 100.0
    for i in range(n):
        candles.append(
            Candle(
                epoch=start + (i * 300),
                open=price,
                high=price + 2.0,
                low=price - 2.0,
                close=price + 1.0,
                volume=1000.0,
            )
        )
        price += 1.0
    return candles


def test_simulator_returns_enriched_metrics_shape():
    history = _build_history()
    risk_manager = MockRiskManager()

    def trader_factory(identity: str):
        return PaperTrader(
            symbol="BTC/USDT_BACKTEST",
            identity=identity,
            repository=InMemoryPaperTraderRepository(),
            risk_manager=risk_manager,
            initial_balance=200.0,
            leverage=10,
            position_sizing_mode="fixed",
        )

    simulator = BacktestSimulatorImpl(
        risk_manager,
        trader_factory,
        cost_config=TradingCostConfig.zero(),
    )

    personality = Personality(
        name="TestMomentum",
        strategy="Momentum Breakout",
        timeframe=300,
        risk_profile=RiskProfile(
            sl_multiplier=1.0,
            tp_multiplier=1.0,
            leverage=10,
            position_sizing_mode="fixed",
            risk_percent=2.0,
            max_trade_duration_minutes=240,
        ),
    )

    result = simulator.simulate_strategy(history, personality)

    expected_keys = {
        "signals",
        "wins",
        "losses",
        "win_rate",
        "pnl_usdt",
        "gross_pnl_usdt",
        "net_pnl_usdt",
        "total_cost_usdt",
        "profit_factor",
        "expectancy_usd",
        "payoff_ratio",
        "avg_win_usd",
        "avg_loss_usd",
        "max_drawdown_pct",
        "max_drawdown_usd",
        "sharpe",
        "sortino",
        "turnover_usdt",
        "metrics",
        "trades",
    }
    assert expected_keys.issubset(result.keys())
    assert result["pnl_usdt"] == result["net_pnl_usdt"]
    assert isinstance(result["metrics"], dict)
    assert isinstance(result["trades"], list)

    if result["trades"]:
        first_trade = result["trades"][0]
        assert "gross_pnl" in first_trade
        assert "net_pnl" in first_trade
        assert "fees" in first_trade
        assert "slippage_cost" in first_trade
