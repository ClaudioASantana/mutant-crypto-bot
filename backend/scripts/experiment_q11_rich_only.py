#!/usr/bin/env python3
"""Q11 — RICH-only cross-sectional continuation.

Pré-registrado em docs/estrategias/q11-rich-only-design-20260822.md.
Hipótese: o subcaso rich + funding positivo é o único pedaço mais promissor da
família cross-sectional, então esta rodada testa SOMENTE esse lado.

Evento:
- RICH+ : premium_rel rank >= 0.75 E funding > +1bp

SINAL-PREDIÇÃO:
- RICH+ -> retorno relativo forward POSITIVO, especialmente em 8h/24h.

Nada é estratégia; nada vai para paper/live.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.technical_analysis import funding_state_at

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
FETCH_DAYS = 130
WINDOW_DAYS = 90
RICH_Q = 0.75
FUNDING_THR = 0.0001
COOLDOWN_CANDLES = 8
HORIZONS_HOURS = [1, 4, 8, 24]
PRIMARY_H = 8
COST_REL = 2 * 0.0010  # 20bp
TIMEFRAME = "15m"
INTERVAL_MIN = 15

KLINES_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_vol",
    "taker_buy_quote_vol", "ignore",
]


def _paginate(url: str, params: dict, extract_next_ms) -> list:
    end_ms = params["endTime"]
    current = params["startTime"]
    rows_all = []
    while current < end_ms:
        p = dict(params)
        p["startTime"] = current
        resp = requests.get(url, params=p, timeout=15)
        rows = resp.json()
        if not rows or not isinstance(rows, list):
            break
        rows_all.extend(rows)
        next_ms = extract_next_ms(rows[-1])
        if next_ms <= current:
            break
        current = next_ms + 1
        time.sleep(0.03)
        if len(rows) < params.get("limit", 1000):
            break
    return rows_all


def _fetch_series(url: str, symbol: str, value_col: str, days: int, rename_to: str) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows = _paginate(
        url,
        {
            "symbol": symbol,
            "interval": TIMEFRAME,
            "startTime": int(start_dt.timestamp() * 1000),
            "endTime": int(end_dt.timestamp() * 1000),
            "limit": 1000,
        },
        lambda row: row[6],
    )
    if not rows:
        return pd.DataFrame(columns=[rename_to])
    seen, uniq = set(), []
    for row in rows:
        if row[0] in seen:
            continue
        seen.add(row[0])
        uniq.append(row)
    df = pd.DataFrame(uniq, columns=KLINES_COLS)
    df = df[["open_time", value_col]].copy()
    df.columns = ["open_time", rename_to]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df[rename_to] = df[rename_to].astype(float)
    df = df.set_index("open_time")
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_klines(symbol: str, days: int) -> pd.DataFrame:
    return _fetch_series("https://fapi.binance.com/fapi/v1/klines", symbol, "close", days, f"{symbol}_close")


def fetch_premium(symbol: str, days: int) -> pd.DataFrame:
    return _fetch_series("https://fapi.binance.com/fapi/v1/premiumIndexKlines", symbol, "close", days, f"{symbol}_premium")


def fetch_funding(symbol: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows = _paginate(
        "https://fapi.binance.com/fapi/v1/fundingRate",
        {
            "symbol": symbol,
            "startTime": int(start_dt.timestamp() * 1000),
            "endTime": int(end_dt.timestamp() * 1000),
            "limit": 1000,
        },
        lambda row: row["fundingTime"],
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["fundingRate"] = df["fundingRate"].astype(float)
    df = df[["fundingTime", "fundingRate"]].set_index("fundingTime")
    return df[~df.index.duplicated(keep="last")].sort_index()


def build_universe(days: int) -> pd.DataFrame:
    frames = {}
    for s in SYMBOLS:
        c = fetch_klines(s, days)
        p = fetch_premium(s, days)
        df = c.join(p, how="inner")
        if df.empty:
            print(f"⚠ {s}: sem dados")
            continue
        df[f"{s}_prem_rel"] = df[f"{s}_premium"] / df[f"{s}_close"]
        frames[s] = df
    if not frames:
        return pd.DataFrame()

    joined = None
    for s, df in frames.items():
        joined = df if joined is None else joined.join(df, how="inner", rsuffix="_dup")
    joined = joined.loc[:, ~joined.columns.duplicated()]
    return joined.sort_index()


def detect_rich_events(uni: pd.DataFrame, funding_by_symbol: dict):
    end = uni.index[-1]
    start = end - timedelta(days=WINDOW_DAYS)
    idx_range = np.where(uni.index >= start)[0]
    events = []
    baseline_q10 = []
    last_rich = {s: -10**9 for s in SYMBOLS}
    last_rich_f = {s: -10**9 for s in SYMBOLS}

    for i in idx_range:
        row = uni.iloc[i]
        ts = uni.index[i]
        ranks = {s: float(row[f"{s}_prem_rel"]) for s in SYMBOLS if f"{s}_prem_rel" in uni.columns}
        if len(ranks) < len(SYMBOLS):
            continue
        sorted_syms = sorted(ranks, key=lambda s: ranks[s])
        pos = {s: r for r, s in enumerate(sorted_syms, start=1)}
        for s in SYMBOLS:
            if s not in pos:
                continue
            norm = (pos[s] - 1) / (len(sorted_syms) - 1)
            if norm >= RICH_Q and i - last_rich[s] >= COOLDOWN_CANDLES:
                baseline_q10.append((i, s))
                last_rich[s] = i
                fdf = funding_by_symbol.get(s)
                if fdf is None or fdf.empty:
                    continue
                st = funding_state_at(fdf, ts)
                if st and float(st["rate"]) > FUNDING_THR and i - last_rich_f[s] >= COOLDOWN_CANDLES:
                    events.append((i, s))
                    last_rich_f[s] = i
    return events, baseline_q10


def rel_return_matrix(uni: pd.DataFrame, steps: int) -> pd.DataFrame:
    cols = [f"{s}_close" for s in SYMBOLS if f"{s}_close" in uni.columns]
    closes = uni[cols]
    fwd = closes.shift(-steps)
    ret = fwd / closes - 1.0
    out = {}
    for s in SYMBOLS:
        col = f"{s}_close"
        if col not in closes.columns:
            continue
        others = [c for c in cols if c != col]
        out[s] = ret[col] - ret[others].mean(axis=1)
    return pd.DataFrame(out)


def stats_events(rel: pd.DataFrame, events: list) -> np.ndarray:
    vals = []
    for i, s in events:
        if s in rel.columns:
            v = rel.iloc[i][s]
            if np.isfinite(v):
                vals.append(float(v))
    return np.array(vals)


def control_stats(rel: pd.DataFrame) -> np.ndarray:
    return rel.values[rel.notna().values]


def summarize(label: str, arr: np.ndarray, ctrl: np.ndarray):
    if len(arr) == 0:
        print(f"    {label}: sem dados")
        return None
    m = arr.mean()
    c = ctrl.mean() if len(ctrl) else float("nan")
    marg = m - c
    t = 0.0
    if len(arr) > 1 and arr.std(ddof=1) > 0:
        t = m / (arr.std(ddof=1) / np.sqrt(len(arr)))
    print(f"    {label}: n={len(arr):>4}  rel {m:+.5f}  ctrl {c:+.5f}  marginal {marg:+.5f}  t={t:+.2f}")
    return {"n": len(arr), "mean": float(m), "ctrl": float(c), "marginal": float(marg)}


def main():
    print("🧪 Q11 — RICH-only cross-sectional continuation")
    print(f"   Basket fixo: {', '.join(SYMBOLS)}")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d | custo relativo piso {COST_REL*1e4:.1f}bp")
    print(f"   Evento RICH+ >= {RICH_Q} E funding > {FUNDING_THR}")
    print("   Hipótese: rich+ continua outperformando, sobretudo em 8h/24h\n")

    uni = build_universe(FETCH_DAYS)
    present = [s for s in SYMBOLS if f"{s}_close" in uni.columns]
    if uni.empty or len(uni) < 3000:
        print("Dados insuficientes. Abortando.")
        return

    funding_by_symbol = {s: fetch_funding(s, FETCH_DAYS) for s in present}
    rich_events, baseline_rich = detect_rich_events(uni, funding_by_symbol)
    print(f"=== universe={len(present)}/{len(SYMBOLS)} | candles={len(uni)} | baseline_RICH={len(baseline_rich)} | RICH+={len(rich_events)} ===")

    verdicts = {}
    for h in HORIZONS_HOURS:
        steps = int(round(h * 60 / INTERVAL_MIN))
        rel = rel_return_matrix(uni, steps)
        ctrl = control_stats(rel)

        print(f"\n  --- {h}h horizon | controle incondicional rel {ctrl.mean():+.5f} (n={len(ctrl)}) ---")
        v_base = summarize("RICH baseline (sem funding)", stats_events(rel, baseline_rich), ctrl)
        v_rich = summarize("RICH+ (funding confirmado)", stats_events(rel, rich_events), ctrl)
        verdicts[f"base_{h}"] = v_base
        verdicts[f"rich_{h}"] = v_rich

        if h == 8:
            print("\n    [split por símbolo — RICH+ 8h]")
            by_symbol = {}
            for i, s in rich_events:
                if s in rel.columns and np.isfinite(rel.iloc[i][s]):
                    by_symbol.setdefault(s, []).append(float(rel.iloc[i][s]))
            for s in SYMBOLS:
                arr = by_symbol.get(s, [])
                txt = f"{np.mean(arr):+.4f}(n={len(arr)})" if arr else "-"
                print(f"      {s:>10}: {txt}")

    print("\nRegra de veredito (pré-registrada): RICH+ × 8h × M15 é o par primário.")
    print("- Falha se n<30, OU sinal não positivo, OU marginal <= 20bp.")
    print("- Sobrevive se n>=30, sinal positivo em 4h/8h/24h, e marginal > 20bp em 8h.")

    vp = verdicts.get(f"rich_{PRIMARY_H}")
    v4 = verdicts.get("rich_4")
    v24 = verdicts.get("rich_24")
    if vp and v4 and v24:
        n_ok = vp["n"] >= 30
        sign_ok = v4["marginal"] > 0 and vp["marginal"] > 0 and v24["marginal"] > 0
        mag_ok = vp["marginal"] > COST_REL
        survives = n_ok and sign_ok and mag_ok
        print(f"\n>>> VEREDITO M15 8h: {'✅ SOBREVIVE (fase seguinte)' if survives else '❌ FALHA'}")
        print(f"    n_ok={n_ok} sign_ok={sign_ok} mag_ok={mag_ok}")
    else:
        print("\n>>> VEREDITO M15 8h: ❌ FALHA (dados insuficientes)")


if __name__ == "__main__":
    main()