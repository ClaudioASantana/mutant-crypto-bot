"""
Script de Benchmarking de Todas as Estratégias Registradas.

Roda um backtest de referência (SL/TP fixos) para cada estratégia e
gera um ranking consolidado: Estratégia | PNL | WR | DD | # Trades.
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.optimizer import download_history
from app.infrastructure.services.backtest_simulation_impl import BacktestSimulatorImpl
from app.infrastructure.services.risk_manager import RiskManager
from app.infrastructure.services.paper_trader_executor import PaperTrader
from app.infrastructure.repositories.in_memory_paper_trader_repository import InMemoryPaperTraderRepository
from app.domain.entities.personality import Personality, RiskProfile

import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("app.infrastructure.services.paper_trader_executor").setLevel(logging.ERROR)

SYMBOL = "BTC/USDT"
TIMEFRAME = 300
LIMIT = 8640

# Parâmetros de risco fixos do benchmark
SL_MULT = 2.0
TP_MULT = 2.0

# Estratégias a testar (as registradas no BacktestSimulatorImpl)
STRATEGIES = [
    "EMA+MACD", "Bollinger", "VWAP", "SMC", "SuperTrend", "Pin Bar",
    "ABCD", "3 Velas", "RSI+EMA", "Exaustão"
]


def calculate_max_drawdown(trades):
    if not trades:
        return 0.0
    balance = 200.0
    peak = balance
    max_dd = 0.0
    for t in trades:
        balance += t['pnl']
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd * 100


async def run_single_benchmark(history, strategy_name, simulator):
    print(f"  ▶ {strategy_name}...")

    personality = Personality(
        name=f"Benchmark_{strategy_name}",
        strategy=strategy_name,
        timeframe=TIMEFRAME,
        risk_profile=RiskProfile(
            sl_multiplier=SL_MULT,
            tp_multiplier=TP_MULT,
            leverage=10,
            position_sizing_mode="fixed",
            risk_percent=5.0,
            max_trade_duration_minutes=240
        )
    )

    res = simulator.simulate_strategy(history, personality)
    dd = calculate_max_drawdown(res['trades'])
    return {
        "strategy": strategy_name,
        "sl": SL_MULT,
        "tp": TP_MULT,
        "pnl": res['pnl_usdt'],
        "wr": res['win_rate'],
        "dd": round(dd, 2),
        "trades": len(res['trades'])
    }


async def main():
    print("🚀 Iniciando Benchmarking de Estratégias...")
    print(f"📥 Baixando histórico de {SYMBOL} ({TIMEFRAME}s) para {LIMIT} velas...")
    history = await download_history(SYMBOL, TIMEFRAME, LIMIT)
    if not history:
        print("❌ Falha ao baixar o histórico.")
        return

    risk_manager = RiskManager()

    def trader_factory(identity: str):
        return PaperTrader(
            symbol="BTC/USDT_BACKTEST",
            identity=identity,
            repository=InMemoryPaperTraderRepository(),
            risk_manager=risk_manager,
            initial_balance=200.0,
            leverage=10,
            position_sizing_mode="fixed"
        )

    simulator = BacktestSimulatorImpl(risk_manager, trader_factory)

    results = []
    for strat in STRATEGIES:
        r = await run_single_benchmark(history, strat, simulator)
        results.append(r)

    # Ordena por PNL (melhor para pior)
    results.sort(key=lambda x: x['pnl'], reverse=True)

    print("\n\n📊 ============ RANKING DE ESTRATÉGIAS (SL 2.0 / TP 2.0) ============")
    print(f"{'#':<3}{'Estratégia':<14}{'PNL':>10}{'WR%':>8}{'DD%':>8}{'Trades':>8}")
    print("-" * 52)
    for i, r in enumerate(results, 1):
        print(f"{i:<3}{r['strategy']:<14}{r['pnl']:>10.2f}{r['wr']:>8.2f}{r['dd']:>8.2f}{r['trades']:>8}")

    # Resumo qualitativo
    print("\n📌 Leitura:")
    for i, r in enumerate(results, 1):
        if r["pnl"] > 0:
            verdict = "✅ Lucrativa"
        elif r["pnl"] > -5:
            verdict = "🟡 Próxima do zero (ajustável)"
        else:
            verdict = "🔴 Prejuízo"
        print(f"  {i}. {r['strategy']}: {verdict}")

    with open("benchmark_all_strategies.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n💾 Relatório salvo em 'benchmark_all_strategies.json'")


if __name__ == "__main__":
    asyncio.run(main())
