"""
Script de Ajuste Fino de SL/TP para a estratégia SMC (v3).
"""
import os
import sys
import json
import itertools
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
logging.getLogger("app.infrastructure.services.paper_trader_executor").setLevel(logging.WARNING)

SYMBOL = "BTC/USDT"
TIMEFRAME = 300
LIMIT = 8640

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

async def sweep_parameters(history: list):
    print("\n🔍 Ajustando SL/TP para SMC v3...")
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
    sl_multipliers = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2]
    tp_multipliers = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5]

    results = []
    total_combinations = len(sl_multipliers) * len(tp_multipliers)
    current = 0

    for sl, tp in itertools.product(sl_multipliers, tp_multipliers):
        current += 1
        print(f"  Testando {current}/{total_combinations}: SL={sl}, TP={tp}")
        personality = Personality(
            name="Backtest_SMC_v3",
            strategy="SMC",
            timeframe=TIMEFRAME,
            risk_profile=RiskProfile(
                sl_multiplier=sl,
                tp_multiplier=tp,
                leverage=10,
                position_sizing_mode="fixed",
                risk_percent=5.0,
                max_trade_duration_minutes=240
            )
        )
        res = simulator.simulate_strategy(history, personality)
        dd = calculate_max_drawdown(res['trades'])
        results.append({
            "strategy": "SMC",
            "sl": sl, "tp": tp,
            "pnl": res['pnl_usdt'],
            "wr": res['win_rate'],
            "dd": round(dd, 2),
            "trades": len(res['trades'])
        })

    results.sort(key=lambda x: x['pnl'], reverse=True)
    return results[:10]

async def main():
    print("🚀 Iniciando otimização de SL/TP para SMC v3...")
    print(f"📥 Baixando histórico de {SYMBOL} ({TIMEFRAME}s) para {LIMIT} velas...")
    history = await download_history(SYMBOL, TIMEFRAME, LIMIT)
    if not history:
        print("❌ Falha ao baixar o histórico.")
        return

    results = await sweep_parameters(history)
    print("\n🏆 === TOP 10 SMC v3 ===")
    for i, r in enumerate(results, 1):
        print(f"{i}. SL:{r['sl']} TP:{r['tp']} | PNL:${r['pnl']} | WR:{r['wr']}% | DD:{r['dd']}% | Trades:{r['trades']}")

    with open("fine_tuned_risk_results_smc_v3.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n💾 Resultados salvos em 'fine_tuned_risk_results_smc_v3.json'")

if __name__ == "__main__":
    asyncio.run(main())
