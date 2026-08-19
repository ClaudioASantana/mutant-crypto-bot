"""
Script de Ajuste de Parâmetros de Risco (SL/TP).

Executa uma varredura (sweep) sobre sl_multiplier e tp_multiplier para uma
estratégia, no histórico de 30 dias (M5), e ordena os resultados pelo PNL
para encontrar a melhor combinação de risco/retorno.
"""
import os
import sys
import json
import asyncio
import itertools

# Adiciona o diretório 'backend' ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.application.services.cataloger import calculate_win_rate
from scripts.optimizer import download_history


DEFAULT_STRATEGY = "SuperTrend"
SYMBOL = "BTC/USDT"
TIMEFRAME = 300  # M5
LIMIT = 30 * 24 * 60 // 5  # 8640 velas (30 dias)


async def tune():
    print(f"Baixando histórico de {SYMBOL} ({TIMEFRAME}s) para {LIMIT} velas...")
    history = await download_history(SYMBOL, TIMEFRAME, LIMIT)
    if not history:
        print("Falha ao baixar o histórico.")
        return

    sl_multipliers = [1.0, 1.5, 2.0, 2.5]
    tp_multipliers = [1.5, 2.0, 3.0, 4.0, 5.0, 6.0]

    results = []
    for sl, tp in itertools.product(sl_multipliers, tp_multipliers):
        res = calculate_win_rate(
            history,
            DEFAULT_STRATEGY,
            sl_multiplier=sl,
            tp_multiplier=tp,
        )
        results.append({
            "sl_multiplier": sl,
            "tp_multiplier": tp,
            "signals": res["signals"],
            "wins": res["wins"],
            "losses": res["losses"],
            "win_rate": res["win_rate"],
            "pnl_usdt": res["pnl_usdt"],
        })

    # Ordena por PNL descendente
    results.sort(key=lambda r: r["pnl_usdt"], reverse=True)

    print("\n=== Ranking SL/TP (30 dias, M5, " + DEFAULT_STRATEGY + ") ===")
    print(f"{'SL':<6} {'TP':<6} {'WR%':<8} {'PNL (USD)':<12} {'Trades':<8}")
    print("-" * 45)
    for r in results:
        print(f"{r['sl_multiplier']:<6.1f} {r['tp_multiplier']:<6.1f} "
              f"{r['win_rate']:<8.2f} ${r['pnl_usdt']:<11.2f} "
              f"{r['wins'] + r['losses']:<8}")

    with open("tuned_risk_parameters.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResultado completo salvo em 'tuned_risk_parameters.json'")


if __name__ == "__main__":
    asyncio.run(tune())