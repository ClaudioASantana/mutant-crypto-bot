"""
Diagnóstico da estratégia Rompimento: quantos sinais cada condição filtra.
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
    print(f"Total de velas: {len(df)}")

    candidates = 0
    full_call = 0
    full_put = 0

    for i in range(25, len(df)):
        sub = df.iloc[:i+1]
        last = sub.iloc[-1]

        atr = last.get("ATRr_14", last["close"] * 0.01)
        avg_vol = sub["volume"].iloc[-21:-1].mean()
        dcu = sub["high"].iloc[-21:-1].max()
        dcl = sub["low"].iloc[-21:-1].min()
        ema_20 = last.get("EMA_20", 0)
        body = abs(last["close"] - last["open"])

        broke_high = last["close"] > dcu
        broke_low = last["close"] < dcl

        if broke_high or broke_low:
            candidates += 1

        call_ok = (
            broke_high
            and body > (atr * 1.2)
            and last["volume"] > (avg_vol * 1.3)
            and last["close"] > ema_20
        )

        put_ok = (
            broke_low
            and body > (atr * 1.2)
            and last["volume"] > (avg_vol * 1.3)
            and last["close"] < ema_20
        )

        if call_ok:
            full_call += 1
        if put_ok:
            full_put += 1

    print(f"Velas que romperam Donchian(20): {candidates}")
    print(f"Sinais CALL completos: {full_call}")
    print(f"Sinais PUT completos: {full_put}")

    # Inspecionar uma janela dos dados
    print("\nAmostra das últimas velas:")
    print(df[["open", "high", "low", "close", "volume", "ATRr_14", "EMA_20"]].tail(3))

if __name__ == "__main__":
    asyncio.run(main())