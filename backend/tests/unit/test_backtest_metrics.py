"""Testes unitários para o módulo de métricas e custos de backtest."""

import pytest

from app.application.services.backtest_metrics import (
    TradingCostConfig,
    apply_costs,
    build_equity_curve,
    calculate_backtest_metrics,
    gross_pnl,
    normalize_runtime_trade,
)


def _trade(direction="CALL", entry=100.0, exit_=110.0, qty=1.0, **extra):
    trade = {
        "id": extra.pop("id", "t1"),
        "direction": direction,
        "entry_price": entry,
        "exit_price": exit_,
        "qty": qty,
        "entry_epoch": extra.pop("entry_epoch", 1_000),
        "exit_epoch": extra.pop("exit_epoch", 2_000),
        "status": extra.pop("status", "WIN"),
        "pnl": extra.pop("pnl", 0.0),
    }
    trade.update(extra)
    return trade


# ---------------------------------------------------------------- gross_pnl

def test_gross_pnl_call_long():
    assert gross_pnl("CALL", 100.0, 110.0, 2.0) == pytest.approx(20.0)


def test_gross_pnl_put_short():
    assert gross_pnl("PUT", 100.0, 90.0, 2.0) == pytest.approx(20.0)


def test_gross_pnl_unsupported_direction():
    with pytest.raises(ValueError):
        gross_pnl("SIDEWAYS", 100.0, 110.0, 1.0)


# ------------------------------------------------------- normalize_runtime_trade

def test_normalize_runtime_trade_closed():
    norm = normalize_runtime_trade(_trade())
    assert norm["direction"] == "CALL"
    assert norm["entry_price"] == 100.0
    assert norm["exit_price"] == 110.0
    assert norm["qty"] == 1.0


def test_normalize_runtime_trade_ignores_open():
    open_trade = _trade(exit_=None, exit_epoch=None)
    assert normalize_runtime_trade(open_trade) is None


def test_normalize_runtime_trade_ignores_missing_exit_price():
    assert normalize_runtime_trade(_trade(exit_=None)) is None


# ---------------------------------------------------------------- apply_costs

def test_apply_costs_zero_config_keeps_net_equal_to_gross():
    enriched = apply_costs(_trade(entry=100.0, exit_=110.0, qty=2.0), TradingCostConfig.zero())
    assert enriched["gross_pnl"] == pytest.approx(20.0)
    assert enriched["total_cost"] == pytest.approx(0.0)
    assert enriched["net_pnl"] == pytest.approx(20.0)


def test_apply_costs_notional_and_fee_round_numbers():
    # entry_notional = 100 * 2 = 200, exit_notional = 110 * 2 = 220, soma = 420
    cost = TradingCostConfig(fee_rate=0.001, slippage_bps=0.0, fixed_cost=0.0)
    enriched = apply_costs(_trade(entry=100.0, exit_=110.0, qty=2.0), cost)
    assert enriched["entry_notional"] == pytest.approx(200.0)
    assert enriched["exit_notional"] == pytest.approx(220.0)
    assert enriched["fees"] == pytest.approx(420.0 * 0.001)
    assert enriched["slippage_cost"] == pytest.approx(0.0)
    assert enriched["net_pnl"] == pytest.approx(20.0 - 0.42)


def test_apply_costs_slippage_round_numbers():
    # 100 bps = 1% sobre 420 -> 4.2
    cost = TradingCostConfig(fee_rate=0.0, slippage_bps=100.0, fixed_cost=0.0)
    enriched = apply_costs(_trade(entry=100.0, exit_=110.0, qty=2.0), cost)
    assert enriched["slippage_cost"] == pytest.approx(420.0 * 0.01)
    assert enriched["fees"] == pytest.approx(0.0)


def test_apply_costs_fixed_cost_per_side():
    cost = TradingCostConfig(fee_rate=0.0, slippage_bps=0.0, fixed_cost=1.0)
    enriched = apply_costs(_trade(entry=100.0, exit_=110.0, qty=2.0), cost)
    assert enriched["total_cost"] == pytest.approx(2.0)
    assert enriched["net_pnl"] == pytest.approx(20.0 - 2.0)


def test_gross_does_not_change_when_cost_is_enabled():
    cost = TradingCostConfig(fee_rate=0.001, slippage_bps=10.0, fixed_cost=0.5)
    gross_only = apply_costs(_trade(), TradingCostConfig.zero())["gross_pnl"]
    with_cost = apply_costs(_trade(), cost)
    assert with_cost["gross_pnl"] == pytest.approx(gross_only)
    assert with_cost["net_pnl"] < with_cost["gross_pnl"]


# ------------------------------------------------------------- build_equity_curve

def test_build_equity_curve_accumulates_net():
    trades = [apply_costs(_trade(exit_=110.0, qty=1.0), TradingCostConfig.zero())]
    curve = build_equity_curve(trades, starting_equity=200.0)
    assert curve == [pytest.approx(210.0)]


# ------------------------------------------------------ calculate_backtest_metrics

def test_metrics_empty_trades():
    metrics = calculate_backtest_metrics([], starting_equity=200.0)
    assert metrics["total_trades"] == 0
    assert metrics["net_pnl_usdt"] == 0.0
    assert metrics["win_rate"] == 0.0
    assert metrics["profit_factor"] == 0.0
    assert metrics["max_drawdown_pct"] == 0.0
    assert metrics["sharpe"] == 0.0
    assert metrics["sortino"] == 0.0


def test_metrics_winning_trade_zero_cost():
    trades = [_trade(entry=100.0, exit_=110.0, qty=1.0)]
    metrics = calculate_backtest_metrics(trades, starting_equity=200.0, cost=TradingCostConfig.zero())
    assert metrics["wins"] == 1
    assert metrics["losses"] == 0
    assert metrics["win_rate"] == pytest.approx(100.0)
    assert metrics["net_pnl_usdt"] == pytest.approx(10.0)
    assert metrics["gross_pnl_usdt"] == pytest.approx(10.0)
    assert metrics["expectancy_usd"] == pytest.approx(10.0)
    assert metrics["profit_factor"] == pytest.approx(99.0)


def test_metrics_losing_trade_with_cost():
    cost = TradingCostConfig(fee_rate=0.0, slippage_bps=0.0, fixed_cost=0.0)
    trades = [_trade(entry=100.0, exit_=90.0, qty=1.0, status="LOSS")]
    metrics = calculate_backtest_metrics(trades, starting_equity=200.0, cost=cost)
    assert metrics["wins"] == 0
    assert metrics["losses"] == 1
    assert metrics["net_pnl_usdt"] == pytest.approx(-10.0)
    assert metrics["profit_factor"] == 0.0


def test_metrics_mixed_profit_factor_and_expectancy():
    cost = TradingCostConfig.zero()
    trades = [
        _trade(id="w", entry=100.0, exit_=120.0, qty=1.0, status="WIN"),
        _trade(id="l", entry=100.0, exit_=95.0, qty=1.0, status="LOSS"),
    ]
    metrics = calculate_backtest_metrics(trades, starting_equity=200.0, cost=cost)
    # +20 e -5 -> profit factor 4.0, expectancy 7.5
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["profit_factor"] == pytest.approx(4.0)
    assert metrics["expectancy_usd"] == pytest.approx(7.5)
    assert metrics["payoff_ratio"] == pytest.approx(4.0)


def test_metrics_drawdown_on_equity():
    cost = TradingCostConfig.zero()
    trades = [
        _trade(id="win1", entry=100.0, exit_=110.0, qty=1.0, status="WIN"),
        _trade(id="loss", entry=100.0, exit_=85.0, qty=1.0, status="LOSS"),
    ]
    metrics = calculate_backtest_metrics(trades, starting_equity=200.0, cost=cost)
    # equity: 210 -> 195; pico 210, drawdown 15 -> 7.14%
    assert metrics["max_drawdown_usd"] == pytest.approx(15.0)
    assert metrics["max_drawdown_pct"] == pytest.approx(15.0 / 210.0 * 100.0)


def test_metrics_sharpe_sortino_short_series():
    cost = TradingCostConfig.zero()
    trades = [
        _trade(id="a", entry=100.0, exit_=105.0, qty=1.0, status="WIN"),
        _trade(id="b", entry=100.0, exit_=95.0, qty=1.0, status="LOSS"),
    ]
    metrics = calculate_backtest_metrics(trades, starting_equity=200.0, cost=cost)
    # série [5, -5]: média 0 -> sharpe 0; sortino usa apenas downside [-5]
    # com desvio populacional zero -> 0.0
    assert metrics["sharpe"] == pytest.approx(0.0)
    assert metrics["sortino"] == pytest.approx(0.0)


def test_metrics_sortino_varied_downside():
    cost = TradingCostConfig.zero()
    trades = [
        _trade(id="w1", entry=100.0, exit_=105.0, qty=1.0, status="WIN"),
        _trade(id="w2", entry=100.0, exit_=107.0, qty=1.0, status="WIN"),
        _trade(id="l1", entry=100.0, exit_=95.0, qty=1.0, status="LOSS"),
        _trade(id="l2", entry=100.0, exit_=97.0, qty=1.0, status="LOSS"),
    ]
    metrics = calculate_backtest_metrics(trades, starting_equity=200.0, cost=cost)
    # série [5, 7, -5, -3]: média 1.0; downside [-5, -3] -> sigma 1.0
    # sortino = 1.0 / 1.0 * sqrt(4) = 2.0
    assert metrics["sortino"] == pytest.approx(2.0)


def test_metrics_single_trade_sharpe_sortino_zero():
    metrics = calculate_backtest_metrics(
        [_trade(entry=100.0, exit_=110.0, qty=1.0)],
        starting_equity=200.0,
        cost=TradingCostConfig.zero(),
    )
    assert metrics["sharpe"] == 0.0
    assert metrics["sortino"] == 0.0
