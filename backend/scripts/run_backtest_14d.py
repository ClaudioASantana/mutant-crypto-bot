import os
import sys
import asyncio
import json

# Adiciona o diretório 'backend' ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.application.dtos.backtest_dto import BacktestRequestDTO
from app.application.services.backtest_service import BacktestService

async def run_backtest_14d():
    """Executa um backtest de 14 dias para BTC/USDT no modo Auto."""
    # 14 dias em velas de 5 minutos
    limit_14d = 14 * 24 * 60 // 5  # 4032 velas

    req = BacktestRequestDTO(
        symbol="BTC/USDT",
        timeframe=300,  # M5
        limit=limit_14d,
        strategy="Auto"
    )

    service = BacktestService()
    print(f"Executando backtest de 14 dias para {req.symbol}...")
    result = await service.execute(req)

    if "error" in result:
        print(f"Erro no backtest: {result['error']}")
        return

    print("\n=== Resultado do Backtest de 14 Dias (Modo Auto) ===")
    print(f"Estratégia Ótima: {result.get('optimal_strategy', 'N/A')}")
    print(f"Sinais Gerados: {result.get('signals', 0)}")
    print(f"Win Rate: {result.get('win_rate', 0.0):.2f}%")
    print(f"PNL (USD): ${result.get('pnl_usdt', 0.0):.2f}")
    print(f"Total de Trades: {result.get('wins', 0) + result.get('losses', 0)}")
    print(f"Wins: {result.get('wins', 0)} | Losses: {result.get('losses', 0)}")

    # Salvar resultado detalhado
    with open("backtest_14d_result.json", "w") as f:
        json.dump(result, f, indent=2, default=str)
    print("\nResultado completo salvo em 'backtest_14d_result.json'")

if __name__ == "__main__":
    asyncio.run(run_backtest_14d())