import asyncio
import sys
import os
sys.path.append(os.getcwd())
from app.services.binance_client import BinanceClient
from app.engines.bot_instance import BotInstance
from app.engines.cataloger import calculate_win_rate

async def run():
    client = BinanceClient("BTC/USDT")
    bot = BotInstance("BTC/USDT", "", None, None)
    await client.fetch_history(60, 1000)
    
    print("M1 Candles loaded:", len(bot.builder_m1.closed_candles))
    for req in [3, 5, 7, 9]:
        res = calculate_win_rate(bot.builder_m1.closed_candles, req)
        print(f"Req {req}:", res)
    await client.exchange.close()

asyncio.run(run())
