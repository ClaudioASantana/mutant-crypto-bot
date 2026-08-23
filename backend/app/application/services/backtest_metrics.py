"""Métricas e custos reutilizáveis para backtests.

Centraliza o cálculo de fricção (fee/slippage) e de métricas institucionais
para evitar duplicação e rankings inconsistentes entre harnesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Any, Optional


_PROFIT_FACTOR_CAP = 99.0


@dataclass(frozen=True)
class TradingCostConfig:
    """Configuração de custo por ponta para um trade.

    Attributes:
        fee_rate: taxa percentual por ponta (ex.: 0.0004 = 0.04%).
        slippage_bps: slippage em basis points por ponta.
        fixed_cost: custo fixo absoluto por ponta.
    """

    fee_rate: float = 0.0004
    slippage_bps: float = 1.0
    fixed_cost: float = 0.0

    @classmethod
    def zero(cls) -> "TradingCostConfig":
        """Retorna uma configuração sem qualquer fricção."""
        return cls(fee_rate=0.0, slippage_bps=0.0, fixed_cost=0.0)


def gross_pnl(direction: str, entry_price: float, exit_price: float, qty: float) -> float:
    """Calcula o PnL bruto a partir dos preços e do lado do trade."""
    side = str(direction).upper()
    if side in ("CALL", "LONG"):
        return (exit_price - entry_price) * qty
    if side in ("PUT", "SHORT"):
        return (entry_price - exit_price) * qty
    raise ValueError(f"Unsupported trade direction: {direction!r}")


def normalize_runtime_trade(trade: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Normaliza o shape legado do runtime do PaperTrader.

    Retorna None para trades ainda abertos ou sem dados mínimos de fechamento.
    """
    exit_price = trade.get("exit_price")
    exit_epoch = trade.get("exit_epoch")
    entry_price = trade.get("entry_price")
    qty = trade.get("qty")
    direction = trade.get("direction")

    if exit_price is None or exit_epoch is None:
        return None
    if entry_price is None or qty is None or direction is None:
        return None

    return {
        "id": trade.get("id"),
        "direction": direction,
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "qty": float(qty),
        "entry_epoch": trade.get("entry_epoch"),
        "exit_epoch": exit_epoch,
        "status": trade.get("status"),
        "pnl": float(trade.get("pnl", 0.0)),
    }


def apply_costs(trade: dict[str, Any], cost: TradingCostConfig) -> dict[str, Any]:
    """Enriquece um trade fechado com gross/net e custo detalhado."""
    entry_notional = float(trade["entry_price"]) * float(trade["qty"])
    exit_notional = float(trade["exit_price"]) * float(trade["qty"])
    gross = gross_pnl(
        direction=str(trade["direction"]),
        entry_price=float(trade["entry_price"]),
        exit_price=float(trade["exit_price"]),
        qty=float(trade["qty"]),
    )
    fees = (entry_notional + exit_notional) * cost.fee_rate + (2 * cost.fixed_cost)
    slippage_cost = (entry_notional + exit_notional) * (cost.slippage_bps / 10_000)
    total_cost = fees + slippage_cost
    net = gross - total_cost

    enriched = dict(trade)
    enriched.update(
        {
            "entry_notional": round(entry_notional, 10),
            "exit_notional": round(exit_notional, 10),
            "gross_pnl": round(gross, 10),
            "fees": round(fees, 10),
            "slippage_cost": round(slippage_cost, 10),
            "total_cost": round(total_cost, 10),
            "net_pnl": round(net, 10),
        }
    )
    return enriched


def build_equity_curve(trades: list[dict[str, Any]], starting_equity: float) -> list[float]:
    """Retorna a curva de equity acumulando o net_pnl dos trades."""
    equity = float(starting_equity)
    curve: list[float] = []
    for trade in trades:
        equity += float(trade.get("net_pnl", 0.0))
        curve.append(round(equity, 10))
    return curve


def _profit_factor(win_values: list[float], loss_values: list[float]) -> float:
    gross_wins = sum(win_values)
    gross_losses = abs(sum(loss_values))
    if gross_losses == 0:
        return _PROFIT_FACTOR_CAP if gross_wins > 0 else 0.0
    return gross_wins / gross_losses


def _max_drawdown(equity_curve: list[float], starting_equity: float) -> tuple[float, float]:
    peak = float(starting_equity)
    max_dd_usd = 0.0
    max_dd_pct = 0.0

    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown_usd = peak - equity
        drawdown_pct = (drawdown_usd / peak * 100.0) if peak > 0 else 0.0
        if drawdown_usd > max_dd_usd:
            max_dd_usd = drawdown_usd
        if drawdown_pct > max_dd_pct:
            max_dd_pct = drawdown_pct

    return max_dd_usd, max_dd_pct


def _sharpe(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    sigma = pstdev(values)
    if sigma == 0:
        return 0.0
    return (mean(values) / sigma) * sqrt(len(values))


def _sortino(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    downside = [v for v in values if v < 0]
    if not downside:
        return _PROFIT_FACTOR_CAP if any(v > 0 for v in values) else 0.0
    downside_sigma = pstdev(downside)
    if downside_sigma == 0:
        return 0.0
    return (mean(values) / downside_sigma) * sqrt(len(values))


def aggregate_trade_metrics(
    trades: list[dict[str, Any]],
    *,
    starting_equity: float = 200.0,
) -> dict[str, Any]:
    """Agrega métricas sobre trades que já carregam `net_pnl` (e, se presentes,
    `gross_pnl`, `total_cost` e notional para turnover).

    Uso em harnesses com modelo de custo próprio: o consumo é `aggregate_trade_metrics`
    após construir os registros; quem prefere o custo centralizado usa
    `calculate_backtest_metrics` com `cost`.

    Convenções:
    - profit factor usa soma dos ganhos sobre soma absoluta das perdas;
    - se não houver perdas, retorna 99.0 quando houver ganhos, senão 0.0;
    - sharpe/sortino operam sobre a série de `net_pnl` por trade;
    - drawdown é calculado sobre a curva de equity a partir de `starting_equity`.
    """
    net_values = [float(trade["net_pnl"]) for trade in trades]
    gross_values = [float(trade.get("gross_pnl", trade["net_pnl"])) for trade in trades]
    wins = [value for value in net_values if value > 0]
    losses = [value for value in net_values if value < 0]

    total_trades = len(trades)
    equity_curve = build_equity_curve(trades, starting_equity)
    max_dd_usd, max_dd_pct = _max_drawdown(equity_curve, starting_equity)

    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss_abs = abs(sum(losses) / len(losses)) if losses else 0.0
    payoff_ratio = (avg_win / avg_loss_abs) if avg_loss_abs > 0 else (_PROFIT_FACTOR_CAP if avg_win > 0 else 0.0)

    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round((len(wins) / total_trades * 100.0), 10) if total_trades > 0 else 0.0,
        "gross_pnl_usdt": round(sum(gross_values), 10),
        "net_pnl_usdt": round(sum(net_values), 10),
        "total_cost_usdt": round(sum(float(trade.get("total_cost", 0.0)) for trade in trades), 10),
        "turnover_usdt": round(
            sum(
                float(trade.get("entry_notional", 0.0)) + float(trade.get("exit_notional", 0.0))
                for trade in trades
            ),
            10,
        ),
        "avg_win_usd": round(avg_win, 10),
        "avg_loss_usd": round(avg_loss_abs, 10),
        "payoff_ratio": round(payoff_ratio, 10),
        "expectancy_usd": round((sum(net_values) / total_trades), 10) if total_trades > 0 else 0.0,
        "profit_factor": round(_profit_factor(wins, losses), 10),
        "max_drawdown_usd": round(max_dd_usd, 10),
        "max_drawdown_pct": round(max_dd_pct, 10),
        "sharpe": round(_sharpe(net_values), 10),
        "sortino": round(_sortino(net_values), 10),
        "equity_curve": equity_curve,
        "trades": trades,
    }


def calculate_backtest_metrics(
    trades: list[dict[str, Any]],
    *,
    starting_equity: float = 200.0,
    cost: Optional[TradingCostConfig] = None,
) -> dict[str, Any]:
    """Calcula métricas agregadas aplicando o custo configurado aos trades fechados.

    Os trades devem carregar `direction`, `entry_price`, `exit_price` e `qty`
    para que o custo seja derivado por ponta.
    """
    cost_config = cost or TradingCostConfig()
    enriched = [apply_costs(trade, cost_config) for trade in trades]
    return aggregate_trade_metrics(enriched, starting_equity=starting_equity)
