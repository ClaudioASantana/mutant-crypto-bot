import asyncio
import sys
import os
sys.path.append(os.getcwd())
from app.engines.bot_instance import BotInstance

async def run():
    bot = BotInstance("BTC/USDT", "", None, None)
    await bot.client.fetch_history(60, 1000)
    
    print("M1 Candles loaded:", len(bot.builder_m1.closed_candles))
    from app.engines.cataloger import calculate_win_rate
    for req in [3, 5, 7, 9]:
        res = calculate_win_rate(bot.builder_m1.closed_candles, req)
        print(f"Req {req}:", res)
    await bot.client.exchange.close()

asyncio.run(run())
