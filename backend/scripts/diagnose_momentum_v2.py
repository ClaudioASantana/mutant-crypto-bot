"""
Diagnóstico detalhado da estratégia Rompimento v2.
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

    v1_call = 0
    v1_put = 0
    v2_call = 0
    v2_put = 0

    for i in range(55, len(df)):
        sub = df.iloc[:i+1]
        last = sub.iloc[-1]

        atr = last.get("ATRr_14", last["close"] * 0.01)
        avg_vol = sub["volume"].iloc[-21:-1].mean()
        dcu = sub["high"].iloc[-21:-1].max()
        dcl = sub["low"].iloc[-21:-1].min()
        ema_20 = last.get("EMA_20", 0)
        ema_50 = last.get("EMA_50", 0)
        body = abs(last["close"] - last["open"])
        range_candle = last["high"] - last["low"]

        # V1 lógica
        if last["close"] > dcu and body > (atr * 1.2) and last["volume"] > (avg_vol * 1.3) and last["close"] > ema_20:
            v1_call += 1
        if last["close"] < dcl and body > (atr * 1.2) and last["volume"] > (avg_vol * 1.3) and last["close"] < ema_20:
            v1_put += 1

        # V2 lógica
        if range_candle == 0:
            continue
        upper_wick = last["high"] - max(last["open"], last["close"])
        lower_wick = min(last["open"], last["close"]) - last["low"]
        consolidation = sub.iloc[-6:-1]
        consolidation_range = consolidation["high"].max() - consolidation["low"].min()
        has_consolidation = consolidation_range <= (atr * 1.5)
        strong_body = body > (atr * 1.2)
        high_volume = last["volume"] > (avg_vol * 1.8)

        if (
            last["close"] > dcu
            and strong_body
            and high_volume
            and (upper_wick / range_candle) < 0.30
            and last["close"] > ema_20 > ema_50
            and has_consolidation
        ):
            v2_call += 1
        if (
            last["close"] < dcl
            and strong_body
            and high_volume
            and (lower_wick / range_candle) < 0.30
            and last["close"] < ema_20 < ema_50
            and has_consolidation
        ):
            v2_put += 1

    print(f"Sinais CALL V1: {v1_call}")
    print(f"Sinais PUT V1: {v1_put}")
    print(f"Sinais CALL V2: {v2_call}")
    print(f"Sinais PUT V2: {v2_put}")

if __name__ == "__main__":
    asyncio.run(main())