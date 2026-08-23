#!/usr/bin/env python3
"""Q8 — Cross-sectional relative value study.

Pré-registrado em docs/estrategias/q8-cross-sectional-design-20260822.md.
Hipótese: ativos com premium/basis relativo extremo dentro de um basket de perps
liquids revertem em relação ao basket.

Estudo causal/event-study:
- usa só candles fechados para definir o evento;
- usa preços futuros apenas para medir retorno relativo forward;
- rank é CROSS-SECTIONAL no timestamp t (sem série temporal) — não há
  lookahead: tudo que entra no evento é observável no close de t.

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

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
FETCH_DAYS = 130
WINDOW_DAYS = 90
RICH_Q = 0.75
CHEAP_Q = 0.25
COOLDOWN_CANDLES = 8  # 2h em M15
HORIZONS_HOURS = [1, 4, 8, 24]
COST_REL = 2 * 0.0010  # 2 patas × 10bp round-trip por pata = 20bp
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
    return _fetch_series(
        "https://fapi.binance.com/fapi/v1/klines", symbol, "close", days, f"{symbol}_close"
    )


def fetch_premium(symbol: str, days: int) -> pd.DataFrame:
    return _fetch_series(
        "https://fapi.binance.com/fapi/v1/premiumIndexKlines", symbol, "close", days, f"{symbol}_premium"
    )


def build_universe(days: int) -> pd.DataFrame:
    """Junta close e premium de todos os símbolos, alinhados pelo timestamp."""
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
    # remove duplicatas acidentais de colunas geradas por joins encadeados
    joined = joined.loc[:, ~joined.columns.duplicated()]
    return joined.sort_index()


def detect_events(uni: pd.DataFrame) -> dict:
    end = uni.index[-1]
    start = end - timedelta(days=WINDOW_DAYS)
    mask = uni.index >= start
    idx_range = np.where(mask)[0]

    events = {"RICH": [], "CHEAP": []}
    last_rich = {s: -10**9 for s in SYMBOLS}
    last_cheap = {s: -10**9 for s in SYMBOLS}

    for i in idx_range:
        row = uni.iloc[i]
        # rank cross-sectional 1..n (tie: min)
        ranks = {s: float(row[f"{s}_prem_rel"]) for s in SYMBOLS if f"{s}_prem_rel" in uni.columns}
        if len(ranks) < len(SYMBOLS):
            continue
        sorted_syms = sorted(ranks, key=lambda s: ranks[s])
        pos = {s: rank for rank, s in enumerate(sorted_syms, start=1)}
        for s in SYMBOLS:
            if s not in pos:
                continue
            norm = (pos[s] - 1) / (len(sorted_syms) - 1)
            if norm >= RICH_Q and i - last_rich[s] >= COOLDOWN_CANDLES:
                events["RICH"].append((i, s))
                last_rich[s] = i
            if norm <= CHEAP_Q and i - last_cheap[s] >= COOLDOWN_CANDLES:
                events["CHEAP"].append((i, s))
                last_cheap[s] = i
    return events


def rel_return_matrix(uni: pd.DataFrame, steps: int) -> pd.DataFrame:
    """Retorno relativo por símbolo em cada timestamp: ret_s - média dos demais.

    Market-neutral na média: para cada linha a média dos rel_returns é zero
    (por construção e por exclusão do próprio símbolo ser compensada).
    """
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
        other_mean = ret[others].mean(axis=1)
        out[s] = ret[col] - other_mean
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
    """Controle: retorno relativo incondicional de todos os pares (símbolo, ts)."""
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
    sign_ok = (marg < 0 and "RICH" in label) or (marg > 0 and "CHEAP" in label)
    print(
        f"    {label}: n={len(arr):>4}  rel {m:+.5f}  ctrl {c:+.5f}  marginal {marg:+.5f}  "
        f"t={t:+.2f}  {'✅' if sign_ok else '❌ contra previsão'}"
    )
    return {"n": len(arr), "mean": float(m), "ctrl": float(c), "marginal": float(marg)}


def main():
    print("🧪 Q8 — cross-sectional relative value")
    print(f"   Basket fixo: {', '.join(SYMBOLS)}")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d | custo relativo piso {COST_REL*1e4:.1f}bp")
    print(f"   Evento RICH >= {RICH_Q} | CHEAP <= {CHEAP_Q} | cooldown {COOLDOWN_CANDLES} candles\n")

    uni = build_universe(FETCH_DAYS)
    present = [s for s in SYMBOLS if f"{s}_close" in uni.columns]
    if len(present) < len(SYMBOLS):
        missing = [s for s in SYMBOLS if s not in present]
        print(f"⚠ símbolos sem dados alinhados: {missing}")
    if uni.empty or len(uni) < 3000:
        print("Dados insuficientes. Abortando.")
        return

    events = detect_events(uni)
    print(f"=== universe={len(present)}/{len(SYMBOLS)} | candles={len(uni)} | "
          f"eventos RICH={len(events['RICH'])} CHEAP={len(events['CHEAP'])} ===")

    verdicts = {"RICH": {}, "CHEAP": {}}
    for h in HORIZONS_HOURS:
        steps = int(round(h * 60 / INTERVAL_MIN))
        rel = rel_return_matrix(uni, steps)
        ctrl = control_stats(rel)

        print(f"\n  --- {h}h horizon | controle incondicional rel {ctrl.mean():+.5f} (n={len(ctrl)}) ---")
        rich = stats_events(rel, events["RICH"])
        cheap = stats_events(rel, events["CHEAP"])
        verdicts["RICH"][h] = summarize("RICH (hipótese: subperformance)", rich, ctrl)
        verdicts["CHEAP"][h] = summarize("CHEAP (hipótese: outperformance)", cheap, ctrl)

        # robustez por símbolo no horizonte 4h
        if h == 4:
            print("\n    [split por símbolo — 4h]")
            sym_rich, sym_cheap = {}, {}
            for i, s in events["RICH"]:
                if s in rel.columns and np.isfinite(rel.iloc[i][s]):
                    sym_rich.setdefault(s, []).append(float(rel.iloc[i][s]))
            for i, s in events["CHEAP"]:
                if s in rel.columns and np.isfinite(rel.iloc[i][s]):
                    sym_cheap.setdefault(s, []).append(float(rel.iloc[i][s]))
            for s in SYMBOLS:
                r = sym_rich.get(s, [])
                c = sym_cheap.get(s, [])
                rr = f"{np.mean(r):+.4f}(n={len(r)})" if r else "-"
                cc = f"{np.mean(c):+.4f}(n={len(c)})" if c else "-"
                print(f"      {s:>10}: RICH {rr}  |  CHEAP {cc}")

    print("\nRegra de veredito (pré-registrada): RICH e CHEAP × 4h em M15.")
    print("- Falha se n<30 por lado, OU sinal contrário ao previsto, OU |marginal| <= custo (20bp).")
    print("- Sobrevive se n>=30, sinal previsto consistente em 1h/4h/8h, e marginal > custo.")

    pr = verdicts["RICH"].get(4)
    pc = verdicts["CHEAP"].get(4)
    if pr and pc:
        n_ok = pr["n"] >= 30 and pc["n"] >= 30
        sign_ok = pr["marginal"] < 0 and pc["marginal"] > 0
        mag_ok = abs(pr["marginal"]) > COST_REL and abs(pc["marginal"]) > COST_REL
        survives = n_ok and sign_ok and mag_ok
        print(f"\n>>> VEREDITO M15 4h: {'✅ SOBREVIVE (fase seguinte)' if survives else '❌ FALHA'}")
        print(f"    n_ok={n_ok} sign_ok={sign_ok} mag_ok={mag_ok}")
    else:
        print("\n>>> VEREDITO M15 4h: ❌ FALHA (dados insuficientes)")


if __name__ == "__main__":
    main()