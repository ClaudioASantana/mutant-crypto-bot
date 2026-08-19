import os
import sys
import asyncio
import json

# Adiciona o diretório 'backend' ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.application.dtos.backtest_dto import BacktestRequestDTO
from app.application.services.backtest_service import BacktestService

async def run_strategy_analysis():
    """Executa backtest de 30 dias para cada estratégia individualmente."""
    limit_30d = 30 * 24 * 60 // 5  # 8640 velas M5
    strategies = [
        "3 Velas", "EMA+MACD", "Bollinger", "VWAP", "SMC",
        "SuperTrend", "Pin Bar", "ABCD", "RSI+EMA", "Exaustão"
    ]

    results = []
    service = BacktestService()

    for strategy in strategies:
        req = BacktestRequestDTO(
            symbol="BTC/USDT",
            timeframe=300,  # M5
            limit=limit_30d,
            strategy=strategy
        )

        print(f"Executando backtest para estratégia: {strategy}...")
        result = await service.execute(req)

        if "error" in result:
            print(f"  Erro: {result['error']}")
            continue

        results.append({
            "strategy": strategy,
            "signals": result.get("signals", 0),
            "wins": result.get("wins", 0),
            "losses": result.get("losses", 0),
            "win_rate": result.get("win_rate", 0.0),
            "pnl_usdt": result.get("pnl_usdt", 0.0),
        })

    # Ordenar por PnL descendente
    results.sort(key=lambda x: x["pnl_usdt"], reverse=True)

    print("\n=== Ranking de Estratégias (30 Dias, BTC/USDT, M5) ===")
    print(f"{'#':<3} {'Estratégia':<15} {'Sinais':<8} {'WR':<8} {'PNL (USD)':<12} {'Trades':<8}")
    print("-" * 65)
    for idx, r in enumerate(results, 1):
        print(f"{idx:<3} {r['strategy']:<15} {r['signals']:<8} {r['win_rate']:<8.2f} ${r['pnl_usdt']:<11.2f} {r['wins']+r['losses']:<8}")

    with open("strategy_ranking_30d.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nRanking completo salvo em 'strategy_ranking_30d.json'")

if __name__ == "__main__":
    asyncio.run(run_strategy_analysis())