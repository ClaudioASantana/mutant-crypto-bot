#!/usr/bin/env python3
"""Q3 — Event study de post-liquidation fade (flush and fade).

Pré-registrado em docs/estrategias/q3-liquidation-fade-design-20260822.md.
Evento definido de forma CAUSAL (só dados conhecidos no fechamento do candle).
Event study primeiro — não é estratégia, nada vai para paper/live ainda.

Evento A — climatic_drop : vela bearish, corpo >= 2.5x ATR(14), volume >= 2x MA(50).
Evento B — wick_reclaim  : pavio inferior >= 2.0x ATR(14) e fechamento bullish.

Mede retorno forward (1h/4h/8h/24h) a partir do close do candle de evento,
líquido de custo round-trip (10bp), com controle incondicional (todas as velas)
para subtrair o drift do mercado.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.technical_analysis import (
    apply_indicators,
    funding_state_at,
)

# --- parâmetros pré-registrados (não varrer de propósito) ---------------------
SYMBOL = "BTCUSDT"
FETCH_DAYS = 130   # 40 de warmup + 90 de janela de evento
WINDOW_DAYS = 90   # janela de evento (os últimos 90)
COOLDOWN_MIN = 240 # 4 horas entre eventos do mesmo tipo

BODY_MULT = 2.5
VOL_MULT = 2.0
WICK_MULT = 2.0
VOL_MA_WINDOW = 50

HORIZONS_HOURS = [1, 4, 8, 24]

COST_ROUNDTRIP = 2 * (0.0004 + 0.0001)  # fee 4bp + slippage 1bp, por ponta

TIMEFRAMES = {"M15": (15, "15m"), "H1": (60, "1h")}


def fetch_klines_futures(symbol: str, interval: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    end_ms = int(end_dt.timestamp() * 1000)
    start_ms = int(start_dt.timestamp() * 1000)
    url = "https://fapi.binance.com/fapi/v1/klines"

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
        last_close_time = rows[-1][6]
        if last_close_time <= current:
            break
        current = last_close_time + 1
        time.sleep(0.05)

        # se a página veio truncada (<limit), já consumimos todo o intervalo
        if len(rows) < 1000:
            break

    if not rows_all:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    # dedup defensivo: as bordas entre páginas podem repetir 1 vela em alguns casos
    seen = set()
    uniq = []
    for row in rows_all:
        key = row[0]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    rows_all = uniq

    # Sanity cap: alguns endpoints futures recusam ranges longos silenciosamente;
    # com paginação correta, 130d de H1 deve passar de 1000 velas.
    # O print fica a cargo do main().


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


def fetch_funding(symbol: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    end_ms = int(end_dt.timestamp() * 1000)
    start_ms = int(start_dt.timestamp() * 1000)
    url = "https://fapi.binance.com/fapi/v1/fundingRate"

    rows_all = []
    current = start_ms
    while current < end_ms:
        resp = requests.get(
            url,
            params={"symbol": symbol, "startTime": current, "endTime": end_ms, "limit": 1000},
            timeout=15,
        )
        rows = resp.json()
        if not rows or not isinstance(rows, list):
            break
        rows_all.extend(rows)
        last_time = rows[-1]["fundingTime"]
        if last_time <= current:
            break
        current = last_time + 1
        time.sleep(0.05)

    df = pd.DataFrame(rows_all)
    if df.empty:
        return df
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["fundingRate"] = df["fundingRate"].astype(float)
    df = df[["fundingTime", "fundingRate"]].set_index("fundingTime")
    return df[~df.index.duplicated(keep="last")].sort_index()


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Indicadores + colunas auxiliares (causais: vol_ma e atr prévios)."""
    if df.empty or len(df) < 40:
        return df
    df = apply_indicators(df)
    df["vol_ma50_prev"] = df["volume"].rolling(VOL_MA_WINDOW).mean().shift(1)
    df["body"] = (df["close"] - df["open"]).abs()
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    return df


def detect_events(df: pd.DataFrame, interval_min: int, wick_mult: float = WICK_MULT) -> dict:
    """Retorna dict tipo -> lista de índices (todas as velas da janela)."""
    end = df.index[-1]
    start = end - timedelta(days=WINDOW_DAYS)
    mask = df.index >= start
    idx_range = np.where(mask)[0]

    cooldown = max(1, int(COOLDOWN_MIN / interval_min))
    events = {"A": [], "B": []}

    last_a = last_b = -10**9
    for i in idx_range:
        if i < VOL_MA_WINDOW + 5:
            continue
        c = df.iloc[i]
        atr = c.get("ATRr_14", np.nan)
        vol_ma = c.get("vol_ma50_prev", np.nan)
        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(vol_ma) or vol_ma <= 0:
            continue

        is_a = (
            c["close"] < c["open"]
            and c["body"] >= BODY_MULT * atr
            and c["volume"] >= VOL_MULT * vol_ma
        )
        is_b = (
            c["lower_wick"] >= wick_mult * atr
            and c["close"] > c["open"]
        )

        if is_a and i - last_a >= cooldown:
            events["A"].append(i)
            last_a = i
        if is_b and i - last_b >= cooldown:
            events["B"].append(i)
            last_b = i

    return events


def forward_stats(df: pd.DataFrame, indices: list, interval_min: int) -> dict:
    """Retorno forward por horizonte (gross e net) sobre índices dados."""
    closes = df["close"].values
    n = len(closes)
    out = {}
    for h in HORIZONS_HOURS:
        steps = int(round(h * 60 / interval_min))
        fwd_gross, fwd_net = [], []
        for i in indices:
            j = i + steps
            if j < n and closes[i] > 0:
                g = closes[j] / closes[i] - 1.0
                fwd_gross.append(g)
                fwd_net.append(g - COST_ROUNDTRIP)
        out[h] = {
            "gross": fwd_gross,
            "net": fwd_net,
        }
    return out


def summarize(fwd: dict, label: str) -> None:
    print(f"\n  --- {label} ---")
    for h in HORIZONS_HOURS:
        g = np.array(fwd[h]["gross"])
        net = np.array(fwd[h]["net"])
        if len(g) == 0:
            print(f"    {h:>2}h: sem dados")
            continue
        t_stat = 0.0
        if len(net) > 1 and net.std(ddof=1) > 0:
            t_stat = net.mean() / (net.std(ddof=1) / np.sqrt(len(net)))
        print(
            f"    {h:>2}h: n={len(g):>3}  gross {g.mean():+.4f}  net {net.mean():+.4f}  "
            f"WR {100*(g>0).mean():5.1f}%  t={t_stat:+.2f}"
        )


def control_stats(df: pd.DataFrame, interval_min: int) -> dict:
    """Retorno forward incondicional de TODAS as velas (controle/ drif7t)."""
    start = df.index[-1] - timedelta(days=WINDOW_DAYS)
    idx_range = np.where(df.index >= start)[0]
    closes = df["close"].values
    n = len(closes)
    out = {}
    for h in HORIZONS_HOURS:
        steps = int(round(h * 60 / interval_min))
        vals = []
        for i in idx_range:
            j = i + steps
            if j < n and closes[i] > 0:
                vals.append(closes[j] / closes[i] - 1.0)
        out[h] = np.array(vals)
    return out


def main():
    print("🧪 Q3 — event study: post-liquidation fade (flush and fade)")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d | custo round-trip {COST_ROUNDTRIP*1e4:.1f}bp")
    print(f"   Evento A: corpo>={BODY_MULT}xATR + vol>={VOL_MULT}xMA50 (cascata proxy)")
    print(f"   Evento B: pavio inferior>={WICK_MULT}xATR + close>open (wick reclaim)\n")

    funding_df = fetch_funding(SYMBOL, FETCH_DAYS)

    for tf_name, (interval_min, interval) in TIMEFRAMES.items():
        raw = fetch_klines_futures(SYMBOL, interval, FETCH_DAYS)
        df = prepare(raw)
        if df is None or len(df) < 60:
            print(f"=== {tf_name}: dados insuficientes ===")
            continue

        events = detect_events(df, interval_min)
        print(f"=== {tf_name} | velas {len(df)} | eventos A={len(events['A'])} B={len(events['B'])} ===")

        ctrl = control_stats(df, interval_min)
        print("  [controle incondicional]")
        for h in HORIZONS_HOURS:
            arr = ctrl[h]
            if len(arr):
                print(f"    {h:>2}h: n={len(arr):>4}  gross {arr.mean():+.4f}  WR {100*(arr>0).mean():5.1f}%")

        summarize(forward_stats(df, events["A"], interval_min), "Evento A (climatic_drop)")
        summarize(forward_stats(df, events["B"], interval_min), "Evento B (wick_reclaim)")

        # contexto: funding no momento do evento (Evento B, causal)
        if events["B"] and not funding_df.empty:
            print("\n  [contexto funding — Evento B, 4h]")
            pos, nonpos = [], []
            for i in events["B"]:
                ts = df.index[i]
                st = funding_state_at(funding_df, ts)
                steps = int(round(4 * 60 / interval_min))
                j = i + steps
                if j >= len(df):
                    continue
                ret = df["close"].values[j] / df["close"].values[i] - 1.0
                (pos if (st and st["rate"] > 0) else nonpos).append(ret)
            for lbl, arr in [("funding>0 ", pos), ("funding<=0", nonpos)]:
                if len(arr):
                    a = np.array(arr)
                    print(f"    {lbl}: n={len(a):>3}  gross {a.mean():+.4f}")

        # sensibilidade do threshold de wick (exploratório, declarado)
        if tf_name == "M15":
            print("\n  [sensibilidade wick_mult — Evento B, 4h (exploratório)]")
            for wm in [1.0, 1.5, 2.0]:
                ev = detect_events(df, interval_min, wick_mult=wm)["B"]
                fwd = forward_stats(df, ev, interval_min)[4]["net"]
                if fwd:
                    a = np.array(fwd)
                    print(f"    wick>={wm}xATR: n={len(a):>3}  net {a.mean():+.4f}  WR {100*(np.array(forward_stats(df, ev, interval_min)[4]['gross'])>0).mean():5.1f}%")
                else:
                    print(f"    wick>={wm}xATR: n=0")

    print("\nRegra de veredito (pré-registrada): Evento B x 4h em M15 é o par primário.")
    print("- Falha se n<20, net<=0, ou net <= controle net.")
    print("- Sobrevive à fase de event study se n>=20, net>0 e net>controle net.")


if __name__ == "__main__":
    main()