#!/usr/bin/env python3
"""Q7 — Estudo de regime persistente de funding/basis.

Pré-registrado em docs/estrategias/q7-funding-basis-regime-design-20260822.md.

Difere de Q5 (evento único direcional) e Q6 (captura do próximo funding):
aqui o objeto é um REGIME persistente definido sobre funding events sucessivos.

Definição (causal):
- pct(t) = percentil causal rolante (janela ~4 dias em M15 / ~4 dias em H1) de
  premium_rel = premium_index_close / perp_close.
- R+ : pct >= 0.80  e fundingRate > 0  (crowding long)
- R- : pct <= 0.20  e fundingRate < 0  (crowding short)
- Regime = run de >= 3 funding events CONSECUTIVOS no mesmo lado.

Mede, por regime (por lado, por timeframe):
- distribuição de duração (n funding events);
- carry acumulado bruto/líquido (upper bound, custo round-trip 10bp uma vez);
- retorno do underlying durante o regime, comparado ao controle incondicional
  (retorno 8h médio da janela, normalizado por evento).

Nada é estratégia; nada vai a paper/live.
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

SYMBOL = "BTCUSDT"
FETCH_DAYS = 130
WINDOW_DAYS = 90
FUNDING_HOURS = 8.0  # BTC perp

PCT_WINDOW_M15 = 384
PCT_WINDOW_H1 = 96
P_REGIME_HIGH = 0.80
P_REGIME_LOW = 0.20
MIN_RUN = 3  # funding events consecutivos no mesmo lado

COST_ROUNDTRIP = 2 * (0.0004 + 0.0001)  # 10bp, uma vez por regime
TIMEFRAMES = {"M15": (15, "15m", PCT_WINDOW_M15), "H1": (60, "1h", PCT_WINDOW_H1)}


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
        time.sleep(0.05)
        if len(rows) < params.get("limit", 1000):
            break
    return rows_all


def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows = _paginate(
        "https://fapi.binance.com/fapi/v1/klines",
        {
            "symbol": symbol,
            "interval": interval,
            "startTime": int(start_dt.timestamp() * 1000),
            "endTime": int(end_dt.timestamp() * 1000),
            "limit": 1000,
        },
        lambda row: row[6],
    )
    if not rows:
        return pd.DataFrame(columns=["close"])
    seen, uniq = set(), []
    for row in rows:
        if row[0] in seen:
            continue
        seen.add(row[0])
        uniq.append(row)
    df = pd.DataFrame(uniq, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_vol",
        "taker_buy_quote_vol", "ignore",
    ])
    df = df[["open_time", "close"]].copy()
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close"] = df["close"].astype(float)
    df = df.set_index("open_time")
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_premium(symbol: str, interval: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows = _paginate(
        "https://fapi.binance.com/fapi/v1/premiumIndexKlines",
        {
            "symbol": symbol,
            "interval": interval,
            "startTime": int(start_dt.timestamp() * 1000),
            "endTime": int(end_dt.timestamp() * 1000),
            "limit": 1000,
        },
        lambda row: row[6],
    )
    if not rows:
        return pd.DataFrame(columns=["premium_close"])
    seen, uniq = set(), []
    for row in rows:
        if row[0] in seen:
            continue
        seen.add(row[0])
        uniq.append(row)
    df = pd.DataFrame(uniq, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_vol",
        "taker_buy_quote_vol", "ignore",
    ])
    df = df[["open_time", "close"]].copy()
    df.columns = ["open_time", "premium_close"]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["premium_close"] = df["premium_close"].astype(float)
    df = df.set_index("open_time")
    return df[~df.index.duplicated(keep="last")].sort_index()


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


def prepare(close_df: pd.DataFrame, premium_df: pd.DataFrame, pct_window: int) -> pd.DataFrame:
    df = close_df.join(premium_df, how="inner")
    if df.empty or len(df) < pct_window + 5:
        return pd.DataFrame()
    df["premium_rel"] = df["premium_close"] / df["close"]

    def _causal_pct(arr: np.ndarray) -> float:
        return float((arr <= arr[-1]).mean())

    df["premium_pct"] = df["premium_rel"].rolling(pct_window).apply(_causal_pct, raw=True)
    return df


def label_funding_events(df: pd.DataFrame, funding_df: pd.DataFrame, window_start: pd.Timestamp) -> pd.DataFrame:
    """Rótulo de cada funding event na janela: 'R+', 'R-' ou '.'."""
    labels = []
    for ts, rate in funding_df["fundingRate"].items():
        if ts < window_start:
            continue
        # último candle FECHADO até o instante do funding (sem lookahead)
        pos = df.index.searchsorted(ts, side="right") - 1
        if pos < 0:
            labels.append(".")
            continue
        pct = df["premium_pct"].iloc[pos]
        if not np.isfinite(pct):
            labels.append(".")
            continue
        if pct >= P_REGIME_HIGH and rate > 0:
            labels.append("R+")
        elif pct <= P_REGIME_LOW and rate < 0:
            labels.append("R-")
        else:
            labels.append(".")
    out = funding_df[funding_df.index >= window_start].copy()
    out["label"] = labels
    return out


def find_runs(labelled: pd.DataFrame) -> dict:
    """Runs de >= MIN_RUN funding events no mesmo lado, dentro da janela.

    Cada run tem entry (primeiro evento) e exit (último evento + 8h).
    """
    runs = {"R+": [], "R-": []}

    def close_run(side, start_ts, end_ts, rates):
        if side is not None and end_ts is not None and len(rates) >= MIN_RUN:
            runs[side].append({
                "entry": start_ts,
                "exit": end_ts + timedelta(hours=FUNDING_HOURS),
                "n_events": len(rates),
                "rates": list(rates),
            })

    cur_side = None
    cur_start = None
    cur_end = None
    cur_rates = []

    for ts, row in labelled.iterrows():
        label = row["label"]
        side = label if label in ("R+", "R-") else None
        if side is not None and side == cur_side:
            cur_rates.append(row["fundingRate"])
            cur_end = ts
            continue

        close_run(cur_side, cur_start, cur_end, cur_rates)
        cur_side = side
        cur_rates = [row["fundingRate"]] if side is not None else []
        cur_start = ts
        cur_end = ts if side is not None else None

    close_run(cur_side, cur_start, cur_end, cur_rates)
    return runs


def _last_ts_of(labelled: pd.DataFrame, start_ts, rates) -> pd.Timestamp:
    """Compat shim mantido apenas para evitar quebra de contexto antigo."""
    events = list(labelled.loc[start_ts:].index)
    if len(events) >= len(rates):
        return events[len(rates) - 1] + timedelta(hours=FUNDING_HOURS)
    return events[-1] + timedelta(hours=FUNDING_HOURS)


def close_at(df: pd.DataFrame, ts: pd.Timestamp):
    """Close asof causal: último close conhecido até ts."""
    pos = df.index.searchsorted(ts, side="right") - 1
    if pos < 0:
        return None
    return float(df["close"].iloc[pos])


def control_8h_return(df: pd.DataFrame, interval_min: int) -> float:
    steps = int(FUNDING_HOURS * 60 / interval_min)
    closes = df["close"].values
    n = len(closes)
    vals = []
    for i in range(0, n - steps):
        if i + steps < n and closes[i] > 0:
            vals.append(closes[i + steps] / closes[i] - 1.0)
    return float(np.mean(vals)) if vals else 0.0


def main():
    print("🧪 Q7 — funding/basis regime persistence")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d | custo round-trip {COST_ROUNDTRIP*1e4:.1f}bp (1x por regime)")
    print(f"   Regime R+: pct>={P_REGIME_HIGH} & funding>0 | R-: pct<={P_REGIME_LOW} & funding<0")
    print(f"   Requer run de >= {MIN_RUN} funding events consecutivos no mesmo lado\n")

    funding_df = fetch_funding(SYMBOL, FETCH_DAYS)
    if funding_df.empty:
        print("Sem dados de funding. Abortando.")
        return

    for tf_name, (interval_min, interval, pct_window) in TIMEFRAMES.items():
        close_df = fetch_klines(SYMBOL, interval, FETCH_DAYS)
        premium_df = fetch_premium(SYMBOL, interval, FETCH_DAYS)
        df = prepare(close_df, premium_df, pct_window)
        if df.empty:
            print(f"=== {tf_name}: dados insuficientes ===")
            continue

        # controle: retorno 8h médio incondicional (todas as velas da janela)
        ctrl = control_8h_return(df, interval_min)
        window_start = df.index[-1] - timedelta(days=WINDOW_DAYS)

        labelled = label_funding_events(df, funding_df, window_start)
        runs = find_runs(labelled)
        print(f"=== {tf_name} | velas {len(df)} | funding events na janela {len(labelled)} | regimes R+={len(runs['R+'])} R-={len(runs['R-'])} ===")
        print(f"    controle retorno 8h: {ctrl:+.5f}")

        for side in ("R+", "R-"):
            r = runs[side]
            if not r:
                print(f"\n  --- {side}: sem regime persistente ---")
                continue
            n_events_all = [x["n_events"] for x in r]
            dur_arr = np.array(n_events_all)
            carry_gross = [sum(abs(x) for x in xr["rates"]) for xr in r]
            rets = []
            for xr in r:
                p0 = close_at(df, xr["entry"])
                p1 = close_at(df, xr["exit"])
                if p0 and p1 and p0 > 0:
                    rets.append(p1 / p0 - 1.0)
            ret_arr = np.array(rets)
            carry_arr = np.array(carry_gross)
            net_carry = carry_arr - COST_ROUNDTRIP
            per8h = ret_arr / np.array(n_events_all, dtype=float) if len(rets) else np.array([])

            print(f"\n  --- {side} ({len(r)} regimes) ---")
            print(f"    duração eventos: med {np.median(dur_arr):.0f} | média {dur_arr.mean():.1f} | >=3: {100*(dur_arr>=3).mean():.0f}%")
            print(f"    carry bruto médio: {carry_arr.mean():+.5f} | carry líquido upper-bound: {net_carry.mean():+.5f}")
            if len(rets):
                print(f"    retorno underlying/regime: med {np.median(ret_arr):+.4f} | média {ret_arr.mean():+.4f}")
                print(f"    por 8h (vs controle {ctrl:+.5f}): {per8h.mean():+.5f}")

    print("\nRegra de veredito (pré-registrada):")
    print("- Falha se n<30 regimes em qualquer lado, OU duração mediana < 3 funding events, OU")
    print("  retorno/regime não supera controle, OU carry líquido upper-bound <= 0.")
    print("- Sobrevive se n>=30, persistência clara, desvio do controle e carry líquido > 0.")


if __name__ == "__main__":
    main()