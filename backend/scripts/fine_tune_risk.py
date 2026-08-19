"""
Script de Ajuste Fino de Parâmetros de Risco (SL/TP).

Executa uma varredura (sweep) refinada sobre sl_multiplier e tp_multiplier para
estratégias específicas (SuperTrend, Exaustão), usando o BacktestService
com BacktestSimulatorImpl para obter resultados mais realistas e precisos.
"""
import os
import sys
import json
import itertools
import asyncio

# Adiciona o diretório 'backend' ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.optimizer import download_history
from app.application.services.backtest_service import BacktestService
from app.infrastructure.services.backtest_simulation_impl import BacktestSimulatorImpl
from app.infrastructure.services.risk_manager import RiskManager
from app.infrastructure.services.paper_trader_executor import PaperTrader
from app.infrastructure.repositories.in_memory_paper_trader_repository import InMemoryPaperTraderRepository
from app.domain.entities.personality import Personality, RiskProfile

import logging

# Reduz logs verbosos do PaperTrader durante a execução do script
logging.basicConfig(level=logging.WARNING)
logging.getLogger("app.infrastructure.services.paper_trader_executor").setLevel(logging.WARNING)

SYMBOL = "BTC/USDT"
TIMEFRAME = 300
LIMIT = 8640

def calculate_max_drawdown(trades):
    """Calcula o Drawdown Máximo (%) de uma série de trades."""
    if not trades:
        return 0.0

    balance = 200.0 # Banca inicial conforme PaperTrader
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

async def sweep_parameters(strategy: str, history: list):
    """Varre diferentes combinações de SL/TP para uma estratégia."""
    print(f"\n🔍 Varrendo parâmetros para {strategy}...")

    # Cria instâncias necessárias para o backtest
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
    backtest_service = BacktestService(simulator)

    # Range refinado de parâmetros
    sl_multipliers = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2]
    tp_multipliers = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5]

    results = []
    total_combinations = len(sl_multipliers) * len(tp_multipliers)
    current = 0

    for sl, tp in itertools.product(sl_multipliers, tp_multipliers):
        current += 1
        print(f"  Testando {current}/{total_combinations}: SL={sl}, TP={tp}")

        # Cria uma personalidade com os parâmetros de SL/TP específicos
        personality = Personality(
            name=f"Backtest_{strategy}",
            strategy=strategy,
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

        # Usa o simulador diretamente em vez do BacktestService
        res = simulator.simulate_strategy(history, personality)

        dd = calculate_max_drawdown(res['trades'])

        results.append({
            "strategy": strategy,
            "sl": sl, "tp": tp,
            "pnl": res['pnl_usdt'],
            "wr": res['win_rate'],
            "dd": round(dd, 2),
            "trades": len(res['trades'])
        })

    # Ordena por PNL descendente
    results.sort(key=lambda x: x['pnl'], reverse=True)
    return results[:10]

async def main():
    print("🚀 Iniciando otimização refinada de parâmetros de risco...")

    # Baixa o histórico uma vez para ambas as estratégias
    print(f"📥 Baixando histórico de {SYMBOL} ({TIMEFRAME}s) para {LIMIT} velas...")
    history = await download_history(SYMBOL, TIMEFRAME, LIMIT)
    if not history:
        print("❌ Falha ao baixar o histórico.")
        return

    # Varre parâmetros para ambas as estratégias
    s1 = await sweep_parameters("SuperTrend", history)
    s2 = await sweep_parameters("Exaustão", history)

    print("\n🏆 === TOP 5 SuperTrend Refinado ===")
    for i, r in enumerate(s1[:5], 1):
        print(f"{i}. SL:{r['sl']} TP:{r['tp']} | PNL:${r['pnl']} | WR:{r['wr']}% | DD:{r['dd']}% | Trades:{r['trades']}")

    print("\n🎯 === TOP 5 Exaustão Refinado ===")
    for i, r in enumerate(s2[:5], 1):
        print(f"{i}. SL:{r['sl']} TP:{r['tp']} | PNL:${r['pnl']} | WR:{r['wr']}% | DD:{r['dd']}% | Trades:{r['trades']}")

    # Salva resultados completos
    with open("fine_tuned_risk_results.json", "w") as f:
        json.dump({"SuperTrend": s1, "Exaustão": s2}, f, indent=2)
    print("\n💾 Resultados completos salvos em 'fine_tuned_risk_results.json'")

if __name__ == "__main__":
    asyncio.run(main())