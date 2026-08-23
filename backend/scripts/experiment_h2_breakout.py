#!/usr/bin/env python3
"""H2 (P2): breakout de regime com Donchian 55 + ADX + banda de ATR.

Valida a hipótese de que um sinal de continuação em TF maior (M15/H1),
com seleção de regime e volatilidade, sobrevive melhor que o zoo de reversão
refutado em P1/H1.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.backtest_metrics import TradingCostConfig, calculate_backtest_metrics
from app.application.services.technical_analysis import apply_indicators, eval_regime_breakout

FEE_RATE = 0.0004
SLIPPAGE_BPS = 1.0
STAKE_USD = 100.0
LEVERAGE = 10
DAYS = 90
TP_MULTIPLIER = 3.0
SL_MULTIPLIER = 1.5

TRAIN_DAYS = 30
TEST_DAYS = 7
STEP_DAYS = 7

MIN_POSITIVE_FOLDS = 5
MIN_PF = 1.3

TIMEFRAMES = {"M15": "15m", "H1": "1h"}


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


def run_strategy(df_ind: pd.DataFrame) -> dict:
    notional = STAKE_USD * LEVERAGE
    trades = []
    start_idx = 60 if len(df_ind) >= 120 else 30

    in_position = False
    pos_direction = None
    pos_entry = 0.0
    pos_sl = 0.0
    pos_tp = 0.0
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

        sub = df_ind.iloc[max(0, i - 120): i + 1]
        sig = eval_regime_breakout(sub)
        if sig not in ("CALL", "PUT"):
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
        pos_entry_time = curr_time

    return calculate_backtest_metrics(
        trades,
        starting_equity=1000.0,
        cost=TradingCostConfig(fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS),
    )


def walk_forward(df_ind: pd.DataFrame) -> list:
    start = df_ind.index[0]
    end = df_ind.index[-1]

    folds = []
    for w in range(0, DAYS - TRAIN_DAYS - TEST_DAYS + 1, STEP_DAYS):
        test_start = start + timedelta(days=TRAIN_DAYS + w, hours=1)
        test_end = test_start + timedelta(days=TEST_DAYS)
        if test_end > end - timedelta(hours=1):
            break
        window = df_ind[test_start:test_end]
        if len(window) < 100:
            continue
        metrics = run_strategy(window)
        folds.append(metrics)
    return folds


def aggregate(folds: list) -> dict:
    total_pnl = sum(f["net_pnl_usdt"] for f in folds)
    positive = sum(1 for f in folds if f["net_pnl_usdt"] > 0)
    total_trades = sum(f["total_trades"] for f in folds)
    gross_wins = sum(f["net_pnl_usdt"] for f in folds if f["net_pnl_usdt"] > 0)
    gross_losses = sum(f["net_pnl_usdt"] for f in folds if f["net_pnl_usdt"] < 0)
    pf = (gross_wins / abs(gross_losses)) if gross_losses < 0 else (99.0 if gross_wins > 0 else 0.0)
    return {
        "n_folds": len(folds),
        "positive_folds": positive,
        "total_pnl": round(total_pnl, 2),
        "total_trades": total_trades,
        "pf_approx": round(pf, 2),
        "avg_trades_per_fold": round(total_trades / len(folds), 2) if folds else 0.0,
    }


def verdict(agg: dict) -> str:
    if agg["n_folds"] == 0:
        return "sem dados"
    admitted = (
        agg["positive_folds"] >= MIN_POSITIVE_FOLDS
        and agg["total_pnl"] > 0
        and agg["pf_approx"] > MIN_PF
    )
    return "✅ ADMITIDA" if admitted else "❌ reprovada"


def main():
    symbol = "BTCUSDT"
    print("🧪 H2 — breakout de regime (Donchian 55 + ADX + banda de ATR)")
    print(f"   Walk-forward: {DAYS}d, janelas OOS {TEST_DAYS}d, passo {STEP_DAYS}d, warmup {TRAIN_DAYS}d")
    print(f"   Custos: fee {FEE_RATE:.4f} + slippage {SLIPPAGE_BPS:.1f}bp | TP {TP_MULTIPLIER}x ATR | SL {SL_MULTIPLIER}x ATR")
    print(f"   Admissão: >= {MIN_POSITIVE_FOLDS}/8 janelas+, PnL agregado > 0, PF > {MIN_PF}\n")

    for tf_name, interval in TIMEFRAMES.items():
        df = apply_indicators(fetch_klines(symbol, interval, DAYS))
        folds = walk_forward(df)
        agg = aggregate(folds)

        print(f"=== {tf_name} ({interval}) ===")
        print(f"  folds+  : {agg['positive_folds']}/{agg['n_folds']}")
        print(f"  pnl oos : {agg['total_pnl']:>9.2f}")
        print(f"  pf oos  : {agg['pf_approx']:>9.2f}")
        print(f"  trades  : {agg['total_trades']} (média {agg['avg_trades_per_fold']}/fold)")
        print(f"  veredito: {verdict(agg)}\n")

    print("Conclusão: só sobrevive se bater simultaneamente frequência mínima, PnL agregado e PF.")


if __name__ == "__main__":
    main()
