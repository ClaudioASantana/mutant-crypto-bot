#!/usr/bin/env python3
"""Varredura curta da VWAP Z-Score no M15.

Compara thresholds e alvos com split temporal simples (70/30) para
ver se existe alguma configuração que sobreviva fora da amostra.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.backtest_metrics import TradingCostConfig, calculate_backtest_metrics
from app.application.services.technical_analysis import apply_indicators, eval_vwap_zscore

SYMBOL = "BTCUSDT"
INTERVAL = "15m"
DAYS = 30
FEE_RATE = 0.0004
SLIPPAGE_BPS = 1.0
STAKE_USD = 100.0
LEVERAGE = 10

THRESHOLDS = [1.2, 1.5, 1.8, 2.0]
TARGET_MODES = ["vwap", "atr"]


def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    end_ms = int(end_dt.timestamp() * 1000)
    start_ms = int(start_dt.timestamp() * 1000)
    url = "https://api.binance.com/api/v3/klines"

    rows_all = []
    current = start_ms
    while current < end_ms:
        resp = requests.get(
            url,
            params={"symbol": symbol, "interval": interval, "startTime": current, "endTime": end_ms, "limit": 1000},
            timeout=15,
        )
        rows = resp.json()
        if not rows or not isinstance(rows, list):
            break
        rows_all.extend(rows)
        current = rows[-1][6] + 1
        time.sleep(0.05)

    df = pd.DataFrame(rows_all, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_vol",
        "taker_buy_quote_vol", "ignore",
    ])
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df.set_index("open_time", inplace=True)
    return df[~df.index.duplicated(keep="last")]


def split_df(df: pd.DataFrame):
    cut = int(len(df) * 0.7)
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


def compute_vwap_target_trade(entry, exit_price, qty):
    return (exit_price - entry) * qty


def run_on_df(df: pd.DataFrame, threshold: float, target_mode: str) -> dict:
    df = apply_indicators(df.copy())
    notional = STAKE_USD * LEVERAGE
    trades = []

    for i in range(30, len(df) - 2):
        sub = df.iloc[: i + 1]
        if "VWAP" not in "".join(sub.columns):
            continue

        # Puxa o z-score usando a função já registrada; ajustamos o threshold
        # por inspeção do contexto e do último valor.
        # Reaproveitamos a lógica de direção, mas filtramos com threshold local.
        vwap_col = next((c for c in sub.columns if "VWAP" in c), None)
        if vwap_col is None:
            continue

        closes = sub["close"]
        distance = closes - sub[vwap_col]
        distance_std = distance.rolling(window=20).std(ddof=0)
        zscore = distance / distance_std.replace(0, pd.NA)
        if len(zscore.dropna()) < 2:
            continue

        last = sub.iloc[-1]
        prev = sub.iloc[-2]
        last_z = zscore.iloc[-1]
        prev_z = zscore.iloc[-2]
        if pd.isna(last_z) or pd.isna(prev_z):
            continue

        ema200_last = last.get("EMA_200")
        ema200_prev = prev.get("EMA_200")
        ema200_up = (
            ema200_last is not None and ema200_prev is not None
            and not pd.isna(ema200_last) and not pd.isna(ema200_prev)
            and ema200_last >= ema200_prev
        )
        ema200_down = (
            ema200_last is not None and ema200_prev is not None
            and not pd.isna(ema200_last) and not pd.isna(ema200_prev)
            and ema200_last <= ema200_prev
        )

        direction = None
        if prev_z <= -threshold and last_z > prev_z and last["close"] > prev["close"] and ema200_up:
            direction = "CALL"
        elif prev_z >= threshold and last_z < prev_z and last["close"] < prev["close"] and ema200_down:
            direction = "PUT"

        if direction is None:
            continue

        entry = float(last["close"])
        atr = float(last.get("ATRr_14", entry * 0.005))
        if pd.isna(atr) or atr == 0:
            atr = entry * 0.005

        if target_mode == "vwap":
            vwap = float(last[vwap_col])
            if direction == "CALL":
                tp = vwap
                sl = entry - atr * 1.5
                if tp <= entry:
                    continue
            else:
                tp = vwap
                sl = entry + atr * 1.5
                if tp >= entry:
                    continue
        else:
            if direction == "CALL":
                tp = entry + atr * 3.0
                sl = entry - atr * 1.5
            else:
                tp = entry - atr * 3.0
                sl = entry + atr * 1.5

        exit_price = None
        for j in range(i + 1, len(df)):
            cur = df.iloc[j]
            if direction == "CALL":
                if cur["low"] <= sl:
                    exit_price = sl
                    break
                if cur["high"] >= tp:
                    exit_price = tp
                    break
            else:
                if cur["high"] >= sl:
                    exit_price = sl
                    break
                if cur["low"] <= tp:
                    exit_price = tp
                    break
        if exit_price is None:
            continue

        trades.append({
            "direction": direction,
            "entry_price": entry,
            "exit_price": float(exit_price),
            "qty": notional / entry,
        })

    return calculate_backtest_metrics(
        trades,
        starting_equity=1000.0,
        cost=TradingCostConfig(fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS),
    )


def main():
    print("🧪 VWAP Z-Score sweep (M15, 30 dias, split 70/30)")
    df = fetch_klines(SYMBOL, INTERVAL, DAYS)
    train_df, test_df = split_df(df)

    rows = []
    for threshold in THRESHOLDS:
        for target_mode in TARGET_MODES:
            train = run_on_df(train_df, threshold, target_mode)
            test = run_on_df(test_df, threshold, target_mode)
            rows.append({
                "threshold": threshold,
                "target_mode": target_mode,
                "train_pnl": round(train["net_pnl_usdt"], 2),
                "train_pf": round(train["profit_factor"], 2),
                "train_wr": round(train["win_rate"], 2),
                "train_trades": train["total_trades"],
                "test_pnl": round(test["net_pnl_usdt"], 2),
                "test_pf": round(test["profit_factor"], 2),
                "test_wr": round(test["win_rate"], 2),
                "test_trades": test["total_trades"],
            })

    rows.sort(key=lambda r: (r["test_pnl"], r["test_pf"], r["test_wr"]), reverse=True)

    print("\nthreshold target  train_pnl train_pf train_wr train_n  test_pnl test_pf test_wr test_n")
    for r in rows:
        print(
            f"{r['threshold']:>8} {r['target_mode']:<6} "
            f"{r['train_pnl']:>9.2f} {r['train_pf']:>8.2f} {r['train_wr']:>8.2f} {r['train_trades']:>7} "
            f"{r['test_pnl']:>8.2f} {r['test_pf']:>7.2f} {r['test_wr']:>7.2f} {r['test_trades']:>6}"
        )

    best = rows[0]
    print("\nBest out-of-sample:")
    print(best)


if __name__ == "__main__":
    main()
