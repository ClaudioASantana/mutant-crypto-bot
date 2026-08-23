#!/usr/bin/env python3
"""Q12 — BNBUSDT single-name rich+ study.

Pré-registrado em docs/estrategias/q12-bnb-single-name-design-20260822.md.
O teste mais perigoso da trilha por risco de data-snooping: a Q11 descobriu BNB
sobre os dados. Guardrails pré-registrados:
- A. independência temporal: agrupar eventos em episódios (<24h); se 1 episódio
     domina >= 60% dos eventos -> Q12 vazia independente do PnL.
- B. subperíodos: efeito positivo em >= 2 das 3 fatias de 30 dias.
- C. controle relativo CONDICIONAL: retorno relativo médio do BNB em todos os
     timestamps da janela (superar momentum-ingênuo).
- D. custo piso 20bp no horizonte primário de 8h.

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
TARGET = "BNBUSDT"
FETCH_DAYS = 130
WINDOW_DAYS = 90
RICH_Q = 0.75
FUNDING_THR = 0.0001
COOLDOWN_CANDLES = 8
EPISODE_GAP_HOURS = 24
SLICES = 3
PRIMARY_H = 8
COST_REL = 2 * 0.0010  # 20bp
TIMEFRAME = "15m"
INTERVAL_MIN = 15
HORIZONS_HOURS = [1, 4, 8, 24]

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


def detect_target_events(uni: pd.DataFrame, funding_df: pd.DataFrame) -> list:
    """Eventually (i, ts) para BNB RICH+, com cooldown de 2h."""
    end = uni.index[-1]
    start = end - timedelta(days=WINDOW_DAYS)
    idx_range = np.where(uni.index >= start)[0]

    events = []
    last = -10**9
    for i in idx_range:
        ts = uni.index[i]
        row = uni.iloc[i]
        ranks = {s: float(row[f"{s}_prem_rel"]) for s in SYMBOLS if f"{s}_prem_rel" in uni.columns}
        if len(ranks) < len(SYMBOLS):
            continue
        sorted_syms = sorted(ranks, key=lambda s: ranks[s])
        pos = {s: r for r, s in enumerate(sorted_syms, start=1)}
        if TARGET not in pos:
            continue
        norm = (pos[TARGET] - 1) / (len(sorted_syms) - 1)
        if norm < RICH_Q:
            continue
        if i - last < COOLDOWN_CANDLES:
            continue
        fdf = funding_df
        if fdf is None or fdf.empty:
            continue
        st = funding_state_at(fdf, ts)
        if not st or float(st["rate"]) <= FUNDING_THR:
            continue
        events.append((i, ts))
        last = i
    return events


def cluster_episodes(events: list) -> list:
    """Agrupa eventos cujos timestamps distam < EPISODE_GAP_HOURS."""
    if not events:
        return []
    sorted_ev = sorted(events, key=lambda x: x[1])
    episodes = [[sorted_ev[0]]]
    for ev in sorted_ev[1:]:
        if (ev[1] - episodes[-1][-1][1]).total_seconds() < EPISODE_GAP_HOURS * 3600:
            episodes[-1].append(ev)
        else:
            episodes.append([ev])
    return [sorted(e, key=lambda x: x[1]) for e in episodes]


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


def slice_buckets(events: list, window_start: pd.Timestamp, window_end: pd.Timestamp, k: int) -> list:
    """Distribui eventos em k fatias temporais por intervalo de timestamp."""
    span = (window_end - window_start) / k
    buckets = [[] for _ in range(k)]
    for ev in events:
        i, ts = ev
        idx = min(int((ts - window_start) / span), k - 1)
        buckets[idx].append(ev)
    return buckets


def main():
    print("🧪 Q12 — BNBUSDT single-name rich+ study (guardrails anti-snooping)")
    print(f"   Basket de referência: {', '.join(SYMBOLS)} | ativo estudado: {TARGET}")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d | custo piso {COST_REL*1e4:.1f}bp")
    print(f"   Evento: rank BNB >= {RICH_Q} E funding > {FUNDING_THR} | cooldown {COOLDOWN_CANDLES}c")
    print(f"   Guardrail A: episódios < {EPISODE_GAP_HOURS}h | Guardrail B: {SLICES} fatias de 30d\n")

    uni = build_universe(FETCH_DAYS)
    if uni.empty or len(uni) < 3000:
        print("Dados insuficientes. Abortando.")
        return
    funding_df = fetch_funding(TARGET, FETCH_DAYS)

    events = detect_target_events(uni, funding_df)
    episodes = cluster_episodes(events)
    n_episodes_total = len(episodes)

    window_start = uni.index[-1] - timedelta(days=WINDOW_DAYS)
    window_end = uni.index[-1]

    print(f"=== candles={len(uni)} | BNB RICH+ events={len(events)} | episódios={len(episodes)} ===")
    if events:
        sizes = sorted([len(e) for e in episodes], reverse=True)
        max_ep = 100 * sizes[0] / len(events) if sizes else 0
        print(f"    distribuição por episódio: {sizes}")
        print(f"    concentração no maior episódio: {max_ep:.1f}%")

    verdicts = {}
    for h in HORIZONS_HOURS:
        steps = int(round(h * 60 / INTERVAL_MIN))
        rel = rel_return_matrix(uni, steps)

        # controle RELATIVO CONDICIONAL: retorno relativo do BNB em todos os timestamps da janela
        bnb_col = rel[TARGET]
        msk = uni.index >= window_start
        ctrl_cond = bnb_col[msk].values
        ctrl_cond = ctrl_cond[np.isfinite(ctrl_cond)]

        event_vals = [float(rel.iloc[i][TARGET]) for i, _ts in events
                      if TARGET in rel.columns and i < len(rel) and np.isfinite(rel.iloc[i][TARGET])]
        arr = np.array(event_vals)
        marg = arr.mean() - ctrl_cond.mean() if len(arr) else float("nan")

        t = 0.0
        if len(arr) > 1 and arr.std(ddof=1) > 0:
            t = arr.mean() / (arr.std(ddof=1) / np.sqrt(len(arr)))

        print(f"\n  --- {h}h | controle rel condicional {ctrl_cond.mean():+.5f} (n={len(ctrl_cond)}) ---")
        if len(arr):
            print(f"    BNB RICH+: n={len(arr):>4}  rel {arr.mean():+.5f}  marginal({arr.mean()-ctrl_cond.mean():+.5f})  "
                  f"marg-ctrl {marg:+.5f}  WR {100*(arr>0).mean():5.1f}%  t={t:+.2f}")
            if h == PRIMARY_H:
                buckets = slice_buckets(events, window_start, window_end, SLICES)
                print("    [por fatia de 30 dias]")
                for bi, bucket in enumerate(buckets):
                    vals = [float(rel.iloc[i][TARGET]) for i, _ in bucket
                            if i < len(rel) and np.isfinite(rel.iloc[i][TARGET])]
                    if vals:
                        a = np.array(vals)
                        print(f"      fatia {bi+1}: n={len(a):>3}  rel {a.mean():+.5f}  WR {100*(a>0).mean():5.1f}%")
                    else:
                        print(f"      fatia {bi+1}: sem eventos")
        verdicts[h] = {"n": len(arr), "marg": float(marg), "rel": arr.mean() if len(arr) else float("nan")}

    print("\nRegra de veredito (pré-registrada) — primário BNB RICH+ × 8h × M15:")
    print("- Falha se n<30; OU 1 episódio domina >=60% dos eventos; OU sinal <= controle condicional;")
    print("  OU positivo em <2 das 3 fatias; OU marginal <= 20bp.")

    vp = verdicts.get(PRIMARY_H)
    if not vp or vp["n"] == 0:
        print("\n>>> VEREDITO: ❌ FALHA (dados insuficientes)")
        return

    steps = int(round(PRIMARY_H * 60 / INTERVAL_MIN))
    rel = rel_return_matrix(uni, steps)
    bnb_col = rel[TARGET]
    msk = uni.index >= window_start
    ctrl_cond = bnb_col[msk].values
    ctrl_cond = ctrl_cond[np.isfinite(ctrl_cond)]
    buckets = slice_buckets(events, window_start, window_end, SLICES)
    slice_signs = []
    for bucket in buckets:
        vals = [float(rel.iloc[i][TARGET]) for i, _ in bucket if i < len(rel) and np.isfinite(rel.iloc[i][TARGET])]
        if vals:
            slice_signs.append(np.mean(vals) > ctrl_cond.mean())

    n_ok = vp["n"] >= 30
    max_ep_pct = 100 * max(len(e) for e in episodes) / vp["n"] if episodes else 0
    ep_ok = max_ep_pct < 60
    ctrl_ok = vp["marg"] > 0
    slices_ok = sum(slice_signs) >= 2
    mag_ok = vp["marg"] > COST_REL

    survives = n_ok and ep_ok and ctrl_ok and slices_ok and mag_ok
    print(f"\n>>> VEREDITO M15 8h: {'✅ SOBREVIVE' if survives else '❌ FALHA'}")
    print(f"    n_ok={n_ok} ep_ok=<60%={ep_ok} (max {max_ep_pct:.1f}%) ctrl_ok={ctrl_ok} "
          f"slices>=2/3={slices_ok} mag_ok={mag_ok}")


if __name__ == "__main__":
    main()