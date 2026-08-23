#!/usr/bin/env python3
"""Q13 — Swing horizon study (48h / 72h / 7d).

Pré-registrado em docs/estrategias/q13-swing-horizon-design-20260822.md.
Testa se sinais que já mostraram direção correta, mas perderam para o custo em
horizontes curtos, sobrevivem em horizontes swing.

Sinais elegíveis:
- S1: BTC basis extremo positivo (Q5 lado P+)
- S2: RICH+ cross-sectional com funding positivo (Q11/Q12)

Reporta:
- n_raw e n_indep (cooldown = horizonte)
- retorno bruto/líquido
- controle equivalente
- marginal líquido
- concentração por símbolo (S2)

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

# Universo / janelas
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
FETCH_DAYS = 130
WINDOW_DAYS = 90
TIMEFRAME = "15m"
INTERVAL_MIN = 15
HORIZONS_HOURS = [48, 72, 24 * 7]

# S1: BTC basis extremo positivo (Q5)
P_HIGH = 0.95
PCT_WINDOW_BTC = 384
COST_S1 = 0.0010  # 10bp

# S2: rich+ com funding positivo (Q11)
RICH_Q = 0.75
FUNDING_THR = 0.0001
COOLDOWN_BASE = 8  # 2h para gerar eventos raw
COST_S2 = 0.0020  # 20bp

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


# ------------------------------- S1 -------------------------------------------
def prepare_btc(days: int) -> pd.DataFrame:
    close_df = fetch_klines("BTCUSDT", days)
    prem_df = fetch_premium("BTCUSDT", days)
    df = close_df.join(prem_df, how="inner")
    if df.empty or len(df) < PCT_WINDOW_BTC + 10:
        return pd.DataFrame()
    df["premium_rel"] = df["BTCUSDT_premium"] / df["BTCUSDT_close"]

    def _causal_pct(arr: np.ndarray) -> float:
        return float((arr <= arr[-1]).mean())

    df["premium_pct"] = df["premium_rel"].rolling(PCT_WINDOW_BTC).apply(_causal_pct, raw=True)
    return df


def detect_s1_events(df: pd.DataFrame) -> list:
    end = df.index[-1]
    start = end - timedelta(days=WINDOW_DAYS)
    idx_range = np.where(df.index >= start)[0]
    events = []
    for i in idx_range:
        pct = df["premium_pct"].iloc[i]
        if np.isfinite(pct) and pct >= P_HIGH:
            events.append((i, df.index[i]))
    return events


# ------------------------------- S2 -------------------------------------------
def build_universe(days: int) -> pd.DataFrame:
    frames = {}
    for s in SYMBOLS:
        c = fetch_klines(s, days)
        p = fetch_premium(s, days)
        df = c.join(p, how="inner")
        if df.empty:
            continue
        df[f"{s}_prem_rel"] = df[f"{s}_premium"] / df[f"{s}_close"]
        frames[s] = df
    if not frames:
        return pd.DataFrame()

    joined = None
    for _s, df in frames.items():
        joined = df if joined is None else joined.join(df, how="inner", rsuffix="_dup")
    joined = joined.loc[:, ~joined.columns.duplicated()]
    return joined.sort_index()


def detect_s2_events(uni: pd.DataFrame, funding_by_symbol: dict) -> list:
    end = uni.index[-1]
    start = end - timedelta(days=WINDOW_DAYS)
    idx_range = np.where(uni.index >= start)[0]
    events = []
    last_seen = {s: -10**9 for s in SYMBOLS}

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
            if norm < RICH_Q or i - last_seen[s] < COOLDOWN_BASE:
                continue
            fdf = funding_by_symbol.get(s)
            if fdf is None or fdf.empty:
                continue
            st = funding_state_at(fdf, ts)
            if st and float(st["rate"]) > FUNDING_THR:
                events.append((i, ts, s))
                last_seen[s] = i
    return events


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


# --------------------------- helpers comuns -----------------------------------
def thin_independent_events(events: list, horizon_hours: int, ts_index: int = 1) -> list:
    """Mantém só eventos espaçados pelo menos pelo horizonte de hold.

    ts_index=1 para tuples (i, ts) e ts_index=1 para (i, ts, s) também.
    """
    if not events:
        return []
    out = [events[0]]
    min_gap = timedelta(hours=horizon_hours)
    last_ts = events[0][ts_index]
    for ev in events[1:]:
        if ev[ts_index] - last_ts >= min_gap:
            out.append(ev)
            last_ts = ev[ts_index]
    return out


def t_stat(arr: np.ndarray) -> float:
    if len(arr) > 1 and arr.std(ddof=1) > 0:
        return float(arr.mean() / (arr.std(ddof=1) / np.sqrt(len(arr))))
    return 0.0


def summarize_s1(df: pd.DataFrame, events: list, horizon_h: int):
    steps = int(round(horizon_h * 60 / INTERVAL_MIN))
    indep = thin_independent_events(events, horizon_h)

    raw_vals, indep_vals = [], []
    closes = df["BTCUSDT_close"].values
    for i, _ts in events:
        j = i + steps
        if j < len(closes) and closes[i] > 0:
            raw_vals.append(closes[j] / closes[i] - 1.0)
    for i, _ts in indep:
        j = i + steps
        if j < len(closes) and closes[i] > 0:
            indep_vals.append(closes[j] / closes[i] - 1.0)

    # controle incondicional equivalente
    ctrl = []
    window_start = df.index[-1] - timedelta(days=WINDOW_DAYS)
    idxs = np.where(df.index >= window_start)[0]
    for i in idxs:
        j = i + steps
        if j < len(closes) and closes[i] > 0:
            ctrl.append(closes[j] / closes[i] - 1.0)

    raw = np.array(raw_vals)
    indep_arr = np.array(indep_vals)
    ctrl_arr = np.array(ctrl)
    net = indep_arr - COST_S1 if len(indep_arr) else indep_arr
    ctrl_net = ctrl_arr - COST_S1 if len(ctrl_arr) else ctrl_arr
    marginal_net = net.mean() - ctrl_net.mean() if len(net) and len(ctrl_net) else float("nan")

    print(f"\n[S1 BTC basis+ extreme] {horizon_h}h")
    print(f"  n_raw={len(raw):>3}  n_indep={len(indep_arr):>3}")
    if len(indep_arr):
        print(f"  gross {indep_arr.mean():+.5f}  net {net.mean():+.5f}  ctrl_net {ctrl_net.mean():+.5f}  "
              f"marginal_net {marginal_net:+.5f}  WR {100*(indep_arr<0).mean():5.1f}%  t={t_stat(indep_arr):+.2f}")
    return {"n_indep": len(indep_arr), "marginal_net": float(marginal_net), "sign_ok": bool(len(indep_arr) and marginal_net < 0)}


def summarize_s2(uni: pd.DataFrame, events: list, horizon_h: int):
    steps = int(round(horizon_h * 60 / INTERVAL_MIN))
    indep = thin_independent_events(events, horizon_h)
    rel = rel_return_matrix(uni, steps)

    raw_vals, indep_vals = [], []
    sym_indep = []
    for i, _ts, s in events:
        if s in rel.columns and i < len(rel) and np.isfinite(rel.iloc[i][s]):
            raw_vals.append(float(rel.iloc[i][s]))
    for i, _ts, s in indep:
        if s in rel.columns and i < len(rel) and np.isfinite(rel.iloc[i][s]):
            indep_vals.append(float(rel.iloc[i][s]))
            sym_indep.append(s)

    ctrl = rel.values[rel.notna().values]
    raw = np.array(raw_vals)
    indep_arr = np.array(indep_vals)
    ctrl_arr = np.array(ctrl)
    net = indep_arr - COST_S2 if len(indep_arr) else indep_arr
    ctrl_net = ctrl_arr - COST_S2 if len(ctrl_arr) else ctrl_arr
    marginal_net = net.mean() - ctrl_net.mean() if len(net) and len(ctrl_net) else float("nan")

    conc = 0.0
    if sym_indep:
        counts = pd.Series(sym_indep).value_counts(normalize=True)
        conc = float(counts.iloc[0])

    print(f"\n[S2 RICH+ cross-sectional] {horizon_h}h")
    print(f"  n_raw={len(raw):>3}  n_indep={len(indep_arr):>3}  max_symbol_conc={100*conc:4.1f}%")
    if len(indep_arr):
        print(f"  gross {indep_arr.mean():+.5f}  net {net.mean():+.5f}  ctrl_net {ctrl_net.mean():+.5f}  "
              f"marginal_net {marginal_net:+.5f}  WR {100*(indep_arr>0).mean():5.1f}%  t={t_stat(indep_arr):+.2f}")
    return {
        "n_indep": len(indep_arr),
        "marginal_net": float(marginal_net),
        "sign_ok": bool(len(indep_arr) and marginal_net > 0),
        "concentration": conc,
    }


def main():
    print("🧪 Q13 — swing horizon study (48h / 72h / 7d)")
    print("   S1: BTC basis extremo positivo (Q5 P+)")
    print("   S2: RICH+ cross-sectional com funding positivo (Q11/Q12)")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d | custos: S1=10bp, S2=20bp\n")

    btc = prepare_btc(FETCH_DAYS)
    s1_events = detect_s1_events(btc) if not btc.empty else []

    uni = build_universe(FETCH_DAYS)
    funding_by_symbol = {s: fetch_funding(s, FETCH_DAYS) for s in SYMBOLS}
    s2_events = detect_s2_events(uni, funding_by_symbol) if not uni.empty else []

    print(f"S1 eventos raw={len(s1_events)} | S2 eventos raw={len(s2_events)}")

    s1_results, s2_results = {}, {}
    for h in HORIZONS_HOURS:
        s1_results[h] = summarize_s1(btc, s1_events, h) if not btc.empty else None
        s2_results[h] = summarize_s2(uni, s2_events, h) if not uni.empty else None

    print("\nRegra de veredito (pré-registrada):")
    print("S1 primário = 48h | falha se n_indep<20, sinal não negativo, ou |marginal_net|<=10bp")
    print("S2 primário = 72h | falha se n_indep<20, sinal não positivo, marginal_net<=20bp, ou concentração>=60%")

    s1 = s1_results.get(48)
    if s1:
        s1_survives = s1["n_indep"] >= 20 and s1["sign_ok"] and abs(s1["marginal_net"]) > COST_S1
        print(f"\n>>> S1 BTC basis+ 48h: {'✅ SOBREVIVE' if s1_survives else '❌ FALHA'}")
        print(f"    n_ok={s1['n_indep'] >= 20} sign_ok={s1['sign_ok']} mag_ok={abs(s1['marginal_net']) > COST_S1}")

    s2 = s2_results.get(72)
    if s2:
        s2_survives = s2["n_indep"] >= 20 and s2["sign_ok"] and s2["marginal_net"] > COST_S2 and s2["concentration"] < 0.60
        print(f"\n>>> S2 RICH+ 72h: {'✅ SOBREVIVE' if s2_survives else '❌ FALHA'}")
        print(f"    n_ok={s2['n_indep'] >= 20} sign_ok={s2['sign_ok']} mag_ok={s2['marginal_net'] > COST_S2} conc_ok={s2['concentration'] < 0.60}")


if __name__ == "__main__":
    main()