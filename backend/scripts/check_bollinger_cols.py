import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # backend

from scripts.optimizer import download_history
from app.application.services.technical_analysis import candles_to_df, apply_indicators
import asyncio

async def main():
    history = await download_history("BTC/USDT", 300, 200)
    df = candles_to_df(history)
    df = apply_indicators(df)
    print("Colunas de Bollinger:")
    print([c for c in df.columns if 'BB' in c])
    print("\nAmostra de valores:")
    print(df[[c for c in df.columns if 'BB' in c]].tail(3))

if __name__ == "__main__":
    asyncio.run(main())
