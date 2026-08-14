import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from scripts.backtester import download_history
from app.engines.cataloger import calculate_win_rate

async def main():
    print("== TESTE RÁPIDO: SMC (M5) vs ABCD (M15) ==")
    
    # M5 (300)
    history_m5 = await download_history("BTC/USDT", 300, 5000)
    res_smc = calculate_win_rate(history_m5, "SMC")
    print("\n--- SMC no M5 ---")
    print(f"Sinais: {res_smc['signals']} | Wins: {res_smc['wins']} | Losses: {res_smc['losses']} | Win Rate: {res_smc['win_rate']}% | PnL: ${res_smc['pnl_usdt']}")
    
    # M15 (900)
    history_m15 = await download_history("BTC/USDT", 900, 5000)
    res_abcd = calculate_win_rate(history_m15, "ABCD")
    print("\n--- ABCD no M15 ---")
    print(f"Sinais: {res_abcd['signals']} | Wins: {res_abcd['wins']} | Losses: {res_abcd['losses']} | Win Rate: {res_abcd['win_rate']}% | PnL: ${res_abcd['pnl_usdt']}")

if __name__ == "__main__":
    asyncio.run(main())
