"""
Diagnóstico da estratégia BB_MA_MACD: verifica nomes das colunas e sinais.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # backend

from scripts.optimizer import download_history
from app.application.services.technical_analysis import candles_to_df, apply_indicators
import asyncio

async def main():
    history = await download_history("BTC/USDT", 300, 8640)
    if not history:
        print("Falha ao baixar histórico")
        return

    df = candles_to_df(history)
    df = apply_indicators(df)

    print("Colunas disponíveis:")
    print([c for c in df.columns])
    print()

    print("Última vela:")
    print(df.iloc[-1])
    print()

    # Procura por colunas relevantes
    bollinger_cols = [c for c in df.columns if "BBM" in c or "BBU" in c or "BBL" in c]
    macd_cols = [c for c in df.columns if "MACD" in c]
    ema_cols = [c for c in df.columns if "EMA" in c]

    print(f"Colunas Bollinger: {bollinger_cols}")
    print(f"Colunas MACD: {macd_cols}")
    print(f"Colunas EMA: {ema_cols}")

if __name__ == "__main__":
    asyncio.run(main())