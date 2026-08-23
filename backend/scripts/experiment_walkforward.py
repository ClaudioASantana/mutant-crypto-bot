#!/usr/bin/env python3
"""Walk-forward + split por regime para Exaustão e ABCD.

Metodologia:
- 90 dias de candles (M5 e M15) da Binance.
- Walk-forward: janelas out-of-sample de 7 dias, passo 7 dias, com 30 dias de
  warmup de indicadores antes de cada janela (indicadores causais, sem
  lookahead).
- Regime por ADX(14): trend (ADX >= 25) vs range (ADX < 25). Cada trade é
  classificado pelo regime do candle de entrada.
- Métricas com `TradingCostConfig` (fee 0.04% + slippage 1bp por ponta).

Responde: o OOS positivo recente era sorte de regime ou persiste?
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
    eval_abcd,
    check_rsi_filter,
    check_volume_filter,
    check_trend_filter,
)

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

ADX_TREND_THRESHOLD = 25.0

TIMEFRAMES = {"M5": "5m", "M15": "15m"}

STRATEGIES = {
    "Exaustão": eval_mean_reversion_exhaustion,
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


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Indicadores causais sobre o dataset completo + ADX para regime."""
    df = apply_indicators(df.copy())
    try:
        df.ta.adx(length=14, append=True)
    except Exception:
        pass
    return df


def regime_at(df: pd.DataFrame, idx) -> str:
    adx = df.at[idx, "ADX_14"] if "ADX_14" in df.columns else pd.NA
    if pd.isna(adx):
        return "range_warmup"
    return "trend" if adx >= ADX_TREND_THRESHOLD else "range"


def run_strategy(df_ind: pd.DataFrame, strategy_func) -> dict:
    """Harness ATR do weekly: uma posição por vez, TP/SL intra-candle."""
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
                    "regime": regime_at(df_ind, pos_entry_time),
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
        pos_entry_time = curr_time

    metrics = calculate_backtest_metrics(
        trades,
        starting_equity=1000.0,
        cost=TradingCostConfig(fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS),
    )
    return {"metrics": metrics, "trades": trades}


def walk_forward(df_ind: pd.DataFrame, strategy_func) -> dict:
    """Roda janelas OOS de 7d (passo 7d) e agrega os resultados."""
    start = df_ind.index[0]
    end = df_ind.index[-1]

    folds = []
    for w in range(0, DAYS - TRAIN_DAYS - TEST_DAYS + 1, STEP_DAYS):
        test_start = start + timedelta(days=TRAIN_DAYS + w, hours=1)  # 1h de folga p/ warmup cruzado
        test_end = test_start + timedelta(days=TEST_DAYS)
        if test_end > end - timedelta(hours=1):
            break
        window = df_ind[test_start:test_end]
        if len(window) < 100:
            continue
        res = run_strategy(window, strategy_func)
        folds.append({
            "start": test_start,
            "end": test_end,
            "metrics": res["metrics"],
            "trades": res["trades"],
        })
    return {"folds": folds}


def summarize(result: dict) -> dict:
    folds = result["folds"]
    all_trades = [t for f in folds for t in f["trades"]]
    metrics = calculate_backtest_metrics(
        all_trades,
        starting_equity=1000.0,
        cost=TradingCostConfig(fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS),
    )

    positive_folds = sum(1 for f in folds if f["metrics"]["net_pnl_usdt"] > 0)
    total_pnl = sum(f["metrics"]["net_pnl_usdt"] for f in folds)

    by_regime = {}
    for t in all_trades:
        r = t["regime"]
        by_regime.setdefault(r, []).append(t)
    regime_stats = {}
    for r, ts in by_regime.items():
        rm = calculate_backtest_metrics(
            ts,
            starting_equity=1000.0,
            cost=TradingCostConfig(fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS),
        )
        regime_stats[r] = {
            "pnl": round(rm["net_pnl_usdt"], 2),
            "pf": round(rm["profit_factor"], 2),
            "wr": round(rm["win_rate"], 2),
            "n": rm["total_trades"],
        }

    return {
        "n_folds": len(folds),
        "positive_folds": positive_folds,
        "total_pnl": round(total_pnl, 2),
        "net_pnl": round(metrics["net_pnl_usdt"], 2),
        "pf": round(metrics["profit_factor"], 2),
        "wr": round(metrics["win_rate"], 2),
        "trades": metrics["total_trades"],
        "regime_stats": regime_stats,
    }


def main():
    symbol = "BTCUSDT"
    print(f"🧪 Walk-forward {DAYS} dias — janelas OOS {TEST_DAYS}d (passo {STEP_DAYS}d), warmup {TRAIN_DAYS}d")
    print(f"   Regime: ADX(14) >= {ADX_TREND_THRESHOLD} → trend | < → range")
    print(f"   Custos: fee {FEE_RATE} + slippage {SLIPPAGE_BPS}bps por ponta | TP {TP_MULTIPLIER}xATR / SL {SL_MULTIPLIER}xATR")

    for tf_name, interval in TIMEFRAMES.items():
        df = build_features(fetch_klines(symbol, interval, DAYS))
        print(f"\n=== {tf_name} ({interval}) ===")

        for name, func in STRATEGIES.items():
            result = walk_forward(df, func)
            s = summarize(result)
            print(f"\n  ▶ {name}")
            print(f"    janelas OOS: {s['n_folds']} ({s['positive_folds']} positivas)")
            print(f"    total OOS:   pnl {s['net_pnl']:>9.2f} | PF {s['pf']:>5.2f} | WR {s['wr']:>5.2f}% | {s['trades']} trades")
            for r, stats in s["regime_stats"].items():
                print(f"      {r:<12} pnl {stats['pnl']:>8.2f} | PF {stats['pf']:>5.2f} | WR {stats['wr']:>5.1f}% | {stats['n']:>3} trades")


if __name__ == "__main__":
    main()