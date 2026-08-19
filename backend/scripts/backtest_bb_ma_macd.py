"""
Script de Backtest da Estratégia do Usuário (BB_MA_MACD).

Executa um backtest da nova estratégia "BB_MA_MACD" usando o BacktestSimulatorImpl
com PaperTrader e RiskManager reais para obter resultados precisos.
"""
import os
import sys
import asyncio
import json

# Adiciona o diretório 'backend' ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.optimizer import download_history
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
LIMIT = 8640  # 30 dias de velas M5

def calculate_max_drawdown(trades):
    """Calcula o Drawdown Máximo (%) de uma série de trades."""
    if not trades:
        return 0.0

    balance = 200.0  # Banca inicial conforme PaperTrader
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

async def run_backtest(strategy: str, history: list):
    """Executa o backtest para uma estratégia."""
    print(f"\n🔍 Backtestando {strategy}...")

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
            position_sizing_mode="fixed",
            max_history_trades=None
        )

    simulator = BacktestSimulatorImpl(risk_manager, trader_factory)

    # Cria uma personalidade com os parâmetros padrão (SL/TP do fine-tune)
    # Vamos usar SL=1.5, TP=3.0 como ponto de partida
    personality = Personality(
        name=f"Backtest_{strategy}",
        strategy=strategy,
        timeframe=TIMEFRAME,
        risk_profile=RiskProfile(
            sl_multiplier=1.5,
            tp_multiplier=3.0,
            leverage=10,
            position_sizing_mode="fixed",
            risk_percent=5.0,
            max_trade_duration_minutes=240
        )
    )

    # Usa o simulador diretamente
    res = simulator.simulate_strategy(history, personality)

    dd = calculate_max_drawdown(res['trades'])

    result = {
        "strategy": strategy,
        "pnl": res['pnl_usdt'],
        "wr": res['win_rate'],
        "dd": round(dd, 2),
        "trades": len(res['trades']),
        "wins": res['wins'],
        "losses": res['losses']
    }

    print(f"  Resultado: PNL:${result['pnl']} | WR:{result['wr']}% | DD:{result['dd']}% | Trades:{result['trades']}")
    return result

async def main():
    print("🚀 Iniciando backtest da estratégia BB_MA_MACD...")

    # Baixa o histórico
    print(f"📥 Baixando histórico de {SYMBOL} ({TIMEFRAME}s) para {LIMIT} velas...")
    history = await download_history(SYMBOL, TIMEFRAME, LIMIT)
    if not history:
        print("❌ Falha ao baixar o histórico.")
        return

    # Executa o backtest da nova estratégia
    bb_ma_macd_result = await run_backtest("BB_MA_MACD", history)

    print("\n🏆 === Resultado do Backtest de BB_MA_MACD ===")
    print(f"PNL: ${bb_ma_macd_result['pnl']}")
    print(f"Win Rate: {bb_ma_macd_result['wr']}%")
    print(f"Drawdown Máximo: {bb_ma_macd_result['dd']}%")
    print(f"Total de Trades: {bb_ma_macd_result['trades']}")
    print(f"Wins: {bb_ma_macd_result['wins']}, Losses: {bb_ma_macd_result['losses']}")

    # Salva resultado
    with open("backtest_bb_ma_macd_result.json", "w") as f:
        json.dump(bb_ma_macd_result, f, indent=2)
    print("\n💾 Resultado salvo em 'backtest_bb_ma_macd_result.json'")

if __name__ == "__main__":
    asyncio.run(main())