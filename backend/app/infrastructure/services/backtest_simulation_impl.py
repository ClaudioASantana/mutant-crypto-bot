"""
Implementação concreta de um Simulador de Backtest.

Clean Architecture: esta é a camada de INFRAESTRUTURA.
Esta implementação depende de abstrações do domínio, mas não do contrário.
"""
import uuid
from typing import List, Dict, Any, Callable, Optional

from app.domain.services.backtest_simulation_interface import AbstractBacktestSimulator
from app.domain.entities.market import Candle, SignalType
from app.domain.entities.personality import Personality
from app.domain.services.risk_manager_interface import AbstractRiskManager
from app.infrastructure.services.paper_trader_executor import PaperTrader

from app.application.services.backtest_metrics import (
    TradingCostConfig,
    apply_costs,
    calculate_backtest_metrics,
    normalize_runtime_trade,
)
from app.application.services.technical_analysis import (
    candles_to_df, apply_indicators, eval_ema_macd, eval_bollinger, eval_vwap, eval_vwap_zscore, eval_smc,
    eval_supertrend, eval_pin_bar, eval_abcd, eval_consecutive, eval_regime_breakout_,
    eval_rsi_ema_confluence, eval_mean_reversion_exhaustion, eval_momentum_breakout
)

class BacktestSimulatorImpl(AbstractBacktestSimulator):
    """
    Implementa a simulação de estratégias usando PaperTrader e RiskManager reais.
    """

    def __init__(
        self,
        risk_manager: AbstractRiskManager,
        paper_trader_factory: callable,
        cost_config: Optional[TradingCostConfig] = None,
    ):
        self._risk_manager = risk_manager
        self._paper_trader_factory = paper_trader_factory
        self._cost_config = cost_config

    def simulate_strategy(
        self,
        history: List[Candle],
        personality: Personality
    ) -> Dict[str, Any]:
        if len(history) < 50:
            return {"signals": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl_usdt": 0.0, "trades": []}

        df = candles_to_df(history)
        df = apply_indicators(df)

        strategy_name = personality.strategy
        strategy_func = self._get_strategy_func(strategy_name)

        if not strategy_func:
            return {"signals": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl_usdt": 0.0, "trades": []}

        trader = self._paper_trader_factory(
            identity=f"backtest_{strategy_name}_{uuid.uuid4()}"
        )

        for i in range(50, len(df) - 1):
            sub_df = df.iloc[:i+1]
            signal_direction_str = strategy_func(sub_df)

            if signal_direction_str != "NONE" and not trader.open_positions:
                entry_price = df.iloc[i]["close"]
                entry_epoch = int(df.index[i].timestamp())
                atr_val = df.iloc[i].get("ATRr_14", entry_price * 0.005)

                sl_tp = self._risk_manager.calculate_sl_tp(
                    personality, entry_price, atr_val, SignalType(signal_direction_str)
                )

                trader.open_trade(
                    direction=signal_direction_str, tf=300, current_epoch=entry_epoch,
                    current_price=entry_price, sl_price=sl_tp["sl_price"],
                    tp_price=sl_tp["tp_price"], atr=atr_val, personality=personality
                )

                for j in range(i + 1, len(df)):
                    current_candle = df.iloc[j]
                    current_price = current_candle["close"]
                    current_epoch = int(df.index[j].timestamp())
                    if trader.check_positions(current_epoch, current_price, personality):
                        break

        final_state = trader.get_state()
        history_trades = final_state["history"]

        normalized = [
            trade
            for trade in (normalize_runtime_trade(t) for t in history_trades)
            if trade is not None
        ]
        metrics = calculate_backtest_metrics(
            normalized,
            starting_equity=getattr(trader, "initial_balance", 200.0),
            cost=self._cost_config,
        )

        cost_config = self._cost_config or TradingCostConfig()
        enriched_trades = [apply_costs(t, cost_config) for t in history_trades]

        return {
            "signals": len(history_trades),
            "wins": metrics["wins"],
            "losses": metrics["losses"],
            "win_rate": round(metrics["win_rate"], 2),
            "pnl_usdt": round(metrics["net_pnl_usdt"], 2),
            "gross_pnl_usdt": round(metrics["gross_pnl_usdt"], 2),
            "net_pnl_usdt": round(metrics["net_pnl_usdt"], 2),
            "total_cost_usdt": round(metrics["total_cost_usdt"], 2),
            "profit_factor": metrics["profit_factor"],
            "expectancy_usd": metrics["expectancy_usd"],
            "payoff_ratio": metrics["payoff_ratio"],
            "avg_win_usd": metrics["avg_win_usd"],
            "avg_loss_usd": metrics["avg_loss_usd"],
            "max_drawdown_pct": metrics["max_drawdown_pct"],
            "max_drawdown_usd": metrics["max_drawdown_usd"],
            "sharpe": metrics["sharpe"],
            "sortino": metrics["sortino"],
            "turnover_usdt": metrics["turnover_usdt"],
            "metrics": metrics,
            "trades": enriched_trades,
        }

    def _get_strategy_func(self, name: str) -> Optional[Callable]:
        return {
            "Momentum Breakout": eval_momentum_breakout,
            "EMA+MACD": eval_ema_macd, "Bollinger": eval_bollinger, "VWAP": eval_vwap,
            "VWAP Z-Score": eval_vwap_zscore,
            "SMC": eval_smc, "SuperTrend": eval_supertrend, "Pin Bar": eval_pin_bar,
            "ABCD": eval_abcd, "3 Velas": eval_consecutive, "RSI+EMA": eval_rsi_ema_confluence,
            "Exaustão": eval_mean_reversion_exhaustion,
            "Regime Breakout": eval_regime_breakout_,
        }.get(name)