#!/usr/bin/env python3
"""Q6 — Event study de carry / funding capture.

Pré-registrado em docs/estrategias/q6-carry-capture-design-20260822.md.
Hipótese: sob confluência de premium extremo + funding do mesmo sinal, uma
estrutura delta-neutral idealizada pode capturar o próximo funding com valor
líquido positivo, mesmo após custo mínimo de round-trip.

Esta rodada mede APENAS a componente de carry:
- entrada no close do candle de evento;
- saída econômica no próximo funding conhecido após a entrada;
- payoff idealizado por unidade de notional = abs(next_funding_rate) - custo.

Não modela convergência/divergência de basis no hold, nem borrow/short spot.
É um upper bound research-only da perna de funding.
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

PCT_WINDOW_M15 = 384
PCT_WINDOW_H1 = 96
P_HIGH = 0.95
P_LOW = 0.05
COOLDOWN_HOURS = 8

COST_ROUNDTRIP = 2 * (0.0004 + 0.0001)  # 10bp
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


def next_funding_after(funding_df: pd.DataFrame, ts: pd.Timestamp):
    if funding_df is None or funding_df.empty:
        return None
    pos = funding_df.index.searchsorted(ts, side="right")
    if pos >= len(funding_df):
        return None
    row = funding_df.iloc[pos]
    return {
        "ts": funding_df.index[pos],
        "rate": float(row["fundingRate"]),
    }


def detect_events(df: pd.DataFrame, funding_df: pd.DataFrame, interval_min: int) -> dict:
    end = df.index[-1]
    start = end - timedelta(days=WINDOW_DAYS)
    idx_range = np.where(df.index >= start)[0]
    cooldown = max(1, int(COOLDOWN_HOURS * 60 / interval_min))

    events = {"C+": [], "C-": []}
    last_pos = last_neg = -10**9

    for i in idx_range:
        ts = df.index[i]
        pct = df["premium_pct"].iloc[i]
        if not np.isfinite(pct):
            continue
        state = funding_state_at(funding_df, ts)
        if not state:
            continue
        rate = float(state["rate"])

        if pct >= P_HIGH and rate > 0 and i - last_pos >= cooldown:
            events["C+"].append(i)
            last_pos = i
        if pct <= P_LOW and rate < 0 and i - last_neg >= cooldown:
            events["C-"] .append(i)
            last_neg = i
    return events


def carry_stats(df: pd.DataFrame, funding_df: pd.DataFrame, indices: list) -> dict:
    gross, net, hours_to_next = [], [], []
    for i in indices:
        ts = df.index[i]
        nxt = next_funding_after(funding_df, ts)
        if not nxt:
            continue
        g = abs(float(nxt["rate"]))
        gross.append(g)
        net.append(g - COST_ROUNDTRIP)
        hours_to_next.append((nxt["ts"] - ts).total_seconds() / 3600.0)
    return {
        "gross": np.array(gross),
        "net": np.array(net),
        "hours_to_next": np.array(hours_to_next),
    }


def control_stats(df: pd.DataFrame, funding_df: pd.DataFrame) -> dict:
    start = df.index[-1] - timedelta(days=WINDOW_DAYS)
    idx_range = np.where(df.index >= start)[0]
    gross, net = [], []
    for i in idx_range:
        ts = df.index[i]
        nxt = next_funding_after(funding_df, ts)
        if not nxt:
            continue
        g = abs(float(nxt["rate"]))
        gross.append(g)
        net.append(g - COST_ROUNDTRIP)
    return {"gross": np.array(gross), "net": np.array(net)}


def summarize(stats: dict, control: dict, label: str):
    g = stats["gross"]
    n = stats["net"]
    h = stats["hours_to_next"]
    if len(n) == 0:
        print(f"\n  --- {label} ---\n    sem dados")
        return None
    ctrl_net = control["net"].mean() if len(control["net"]) else float("nan")
    marginal = n.mean() - ctrl_net
    t_stat = 0.0
    if len(n) > 1 and n.std(ddof=1) > 0:
        t_stat = n.mean() / (n.std(ddof=1) / np.sqrt(len(n)))
    print(f"\n  --- {label} ---")
    print(
        f"    n={len(n):>3}  carry_gross {g.mean():+.5f}  carry_net {n.mean():+.5f}  "
        f"ctrl_net {ctrl_net:+.5f}  marginal {marginal:+.5f}  "
        f"time_to_next {h.mean():.2f}h  t={t_stat:+.2f}"
    )
    return {
        "n": len(n),
        "carry_net": float(n.mean()),
        "ctrl_net": float(ctrl_net),
        "marginal": float(marginal),
    }


def main():
    print("🧪 Q6 — event study: carry / funding capture")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d | custo round-trip {COST_ROUNDTRIP*1e4:.1f}bp")
    print(f"   Eventos: C+ = premium_pct>={P_HIGH} & funding>0 | C- = premium_pct<={P_LOW} & funding<0")
    print("   Hold: até o próximo funding conhecido\n")

    funding_df = fetch_funding(SYMBOL, FETCH_DAYS)
    primary = None

    for tf_name, (interval_min, interval, pct_window) in TIMEFRAMES.items():
        close_df = fetch_klines(SYMBOL, interval, FETCH_DAYS)
        premium_df = fetch_premium(SYMBOL, interval, FETCH_DAYS)
        df = prepare(close_df, premium_df, pct_window)
        if df.empty:
            print(f"=== {tf_name}: dados insuficientes ===")
            continue

        events = detect_events(df, funding_df, interval_min)
        ctrl = control_stats(df, funding_df)
        print(f"=== {tf_name} | velas {len(df)} | eventos C+={len(events['C+'])} C-={len(events['C-'])} ===")
        if len(ctrl["net"]):
            print(f"  [controle] n={len(ctrl['net'])} carry_gross {ctrl['gross'].mean():+.5f} carry_net {ctrl['net'].mean():+.5f}")

        s_pos = summarize(carry_stats(df, funding_df, events["C+"]), ctrl, "Evento C+ (short perp / long spot idealizado)")
        s_neg = summarize(carry_stats(df, funding_df, events["C-"]), ctrl, "Evento C- (long perp / short spot idealizado)")

        if tf_name == "M15":
            primary = (s_pos, s_neg)

    print("\nRegra de veredito (pré-registrada): C+ e C- em M15, hold até próximo funding.")
    print("- Falha se n<30 em qualquer lado, OU mean(carry_net)<=0 em qualquer lado, OU mean(carry_net)<=control_net em qualquer lado.")
    print("- Sobrevive se n>=30 em ambos os lados, mean(carry_net)>0 em ambos, e acima do controle em ambos.")

    if primary and primary[0] and primary[1]:
        cp, cn = primary
        n_ok = cp["n"] >= 30 and cn["n"] >= 30
        pos_ok = cp["carry_net"] > 0 and cn["carry_net"] > 0
        ctrl_ok = cp["carry_net"] > cp["ctrl_net"] and cn["carry_net"] > cn["ctrl_net"]
        survives = n_ok and pos_ok and ctrl_ok
        print(f"\n>>> VEREDITO M15: {'✅ SOBREVIVE (vale modelagem mais realista)' if survives else '❌ FALHA (encerrar hipótese simples)'}")
        print(f"    n_ok={n_ok} pos_ok={pos_ok} ctrl_ok={ctrl_ok}")
    else:
        print("\n>>> VEREDITO M15: ❌ FALHA (dados insuficientes para julgar)")


if __name__ == "__main__":
    main()
