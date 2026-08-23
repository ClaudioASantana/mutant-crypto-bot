#!/usr/bin/env python3
"""Varredura comparativa das candidatas da shortlist P1.

Metodologia idêntica à do `experiment_vwap_zscore.py`:
- dados Binance, 30 dias, split temporal 70/30 (treino/teste);
- mesmo harness ATR (TP=3xATR, SL=1.5xATR), uma posição por vez, + time stop;
- filtros de qualidade (RSI, volume, tendência EMA200) como no weekly;
- métricas com `TradingCostConfig` (fee 0.04% + slippage 1bp por ponta).

Serve para comparar a robustez out-of-sample de Exaustão, 3 Velas e ABCD.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.backtest_metrics import TradingCostConfig, calculate_backtest_metrics
from app.application.services.technical_analysis import (
    apply_indicators,
    eval_mean_reversion_exhaustion,
    eval_three_candles_composite,
    eval_abcd,
    check_rsi_filter,
    check_volume_filter,
    check_trend_filter,
)

FEE_RATE = 0.0004
SLIPPAGE_BPS = 1.0
STAKE_USD = 100.0
LEVERAGE = 10
DAYS = 30
TP_MULTIPLIER = 3.0
SL_MULTIPLIER = 1.5

TIMEFRAMES = {"M5": "5m", "M15": "15m"}

STRATEGIES = {
    "Exaustão": eval_mean_reversion_exhaustion,
    "3 Velas": eval_three_candles_composite,
    "ABCD": eval_abcd,
}


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
    return apply_indicators(df.iloc[:cut].copy()), apply_indicators(df.iloc[cut:].copy())


def run_strategy(df_ind: pd.DataFrame, strategy_func) -> dict:
    """Harness ATR idêntico ao weekly: uma posição por vez, TP/SL no intra-candle."""
    notional = STAKE_USD * LEVERAGE
    trades = []
    start_idx = 60 if len(df_ind) >= 120 else 30

    in_position = False
    pos_direction = None
    pos_entry = 0.0
    pos_sl = 0.0
    pos_tp = 0.0
    pos_entry_idx = 0
    pos_entry_time = None

    for i in range(start_idx, len(df_ind) - 1):
        current_candle = df_ind.iloc[i]
        curr_close = current_candle["close"]
        curr_high = current_candle["high"]
        curr_low = current_candle["low"]
        curr_time = df_ind.index[i]

        if in_position:
            closed = False
            exit_price = curr_close
            if pos_direction == "CALL":
                if curr_low <= pos_sl:
                    closed, exit_price = True, pos_sl
                elif curr_high >= pos_tp:
                    closed, exit_price = True, pos_tp
            else:
                if curr_high >= pos_sl:
                    closed, exit_price = True, pos_sl
                elif curr_low <= pos_tp:
                    closed, exit_price = True, pos_tp

            if not closed and (curr_time - pos_entry_time).total_seconds() > 86400:
                closed, exit_price = True, curr_close

            if closed:
                trades.append({
                    "direction": pos_direction,
                    "entry_price": pos_entry,
                    "exit_price": exit_price,
                    "qty": notional / pos_entry,
                })
                in_position = False

        if in_position:
            continue

        sub = df_ind.iloc[max(0, i - 60): i + 1]
        try:
            sig = strategy_func(sub)
        except Exception:
            sig = "NONE"
        if sig not in ("CALL", "PUT"):
            continue
        if not check_rsi_filter(sub, sig) or not check_volume_filter(sub) or not check_trend_filter(sub, sig):
            continue

        entry = curr_close
        atr_val = current_candle.get("ATRr_14", entry * 0.005)
        if pd.isna(atr_val) or atr_val == 0:
            atr_val = entry * 0.005

        if sig == "CALL":
            pos_tp = entry + atr_val * TP_MULTIPLIER
            pos_sl = entry - atr_val * SL_MULTIPLIER
        else:
            pos_tp = entry - atr_val * TP_MULTIPLIER
            pos_sl = entry + atr_val * SL_MULTIPLIER

        in_position = True
        pos_direction = sig
        pos_entry = entry
        pos_entry_idx = i
        pos_entry_time = curr_time

    return calculate_backtest_metrics(
        trades,
        starting_equity=1000.0,
        cost=TradingCostConfig(fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS),
    )


def main():
    print("🧪 Candidatas P1 — sweep 70/30 (treino/teste), 30 dias")
    symbol = "BTCUSDT"

    for tf_name, interval in TIMEFRAMES.items():
        print(f"\n=== {tf_name} ({interval}) ===")
        df = fetch_klines(symbol, interval, DAYS)
        train_df, test_df = split_df(df)
        print(f"  velas: {len(df)} | treino {len(train_df)} | teste {len(test_df)}")

        print(f"  {'Estratégia':<10} {'train_pnl':>10} {'train_pf':>8} {'train_wr':>9} {'train_n':>8} "
              f"{'test_pnl':>9} {'test_pf':>8} {'test_wr':>8} {'test_n':>7}")
        print("  " + "-" * 80)

        rows = []
        for name, func in STRATEGIES.items():
            train = run_strategy(train_df, func)
            test = run_strategy(test_df, func)
            rows.append({
                "name": name,
                "train": train,
                "test": test,
            })
            print(
                f"  {name:<10} {train['net_pnl_usdt']:>10.2f} {train['profit_factor']:>8.2f} "
                f"{train['win_rate']:>9.2f} {train['total_trades']:>8} "
                f"{test['net_pnl_usdt']:>9.2f} {test['profit_factor']:>8.2f} "
                f"{test['win_rate']:>8.2f} {test['total_trades']:>7}"
            )

        rows.sort(key=lambda r: r["test"]["net_pnl_usdt"], reverse=True)
        best = rows[0]
        print(f"\n  Melhor OOS: {best['name']} → test_pnl {best['test']['net_pnl_usdt']:.2f} | "
              f"PF {best['test']['profit_factor']:.2f} | WR {best['test']['win_rate']:.2f}% | "
              f"{best['test']['total_trades']} trades")


if __name__ == "__main__":
    main()