#!/usr/bin/env python3
"""Q24 — viabilidade da confluência total de crowded squeeze (SEM retornos).

Pré-registro: docs/estrategias/q24-confluencia-crowded-squeeze-design-20260823.md

Objetivo desta rodada:
- detectar a frequência histórica da confluência extrema E1/E2;
- estimar quantos meses de amostra nova seriam necessários para acumular n_indep;
- NÃO calcular retorno forward, média, t-stat, controle ou veredito econômico.

Nada vai para paper/live.
"""

import csv
import io
import os
import sys
import time
import zipfile
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.technical_analysis import funding_state_at

SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"
PANDAS_FREQ = "15min"
INTERVAL_MIN = 15
LOOKBACK_BARS = 16
PCT_WINDOW = 384
PRIMARY_HORIZON_H = 8
N_TARGET_INDEP = 20

OI_PCT_HIGH = 0.90
PREMIUM_RICH_Q = 0.75
PREMIUM_CHEAP_Q = 0.25
TAKER_HIGH_Q = 0.90
TAKER_LOW_Q = 0.10
FUNDING_ABS_Q = 0.80
EPISODE_GAP_HOURS = 24

BUCKET_MONTHLY = "https://data.binance.vision/data/futures/um/monthly"
API_BASE = "https://fapi.binance.com"

KLINES_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_vol",
    "taker_buy_quote_vol", "ignore",
]

METRICS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "derivatives", "binance_vision", "metrics",
    f"{SYMBOL}_metrics_long.csv",
)
TS_DTYPE = "datetime64[ns, UTC]"


def _get(url: str, params: dict):
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=40)
    r.raise_for_status()
    return r.content


def month_starts(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> list[pd.Timestamp]:
    cur = pd.Timestamp(year=start_ts.year, month=start_ts.month, day=1, tz="UTC")
    last = pd.Timestamp(year=end_ts.year, month=end_ts.month, day=1, tz="UTC")
    out = []
    while cur <= last:
        out.append(cur)
        cur = cur + pd.offsets.MonthBegin(1)
    return out


def read_zip_csv_bytes(content: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            raw = f.read().decode("utf-8")
    return list(csv.reader(io.StringIO(raw)))


def _ms_to_ts(vals) -> pd.Series:
    return pd.to_datetime(pd.Series(vals).astype("int64"), unit="ms", utc=True).astype(TS_DTYPE)


def _rows_to_kline_df(rows: list[list[str]], value_name: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=[value_name])
    first = rows[0]
    body = rows[1:] if first and first[0] == "open_time" else rows
    df = pd.DataFrame(body, columns=KLINES_COLS)
    df = df[["open_time", "close"]].copy()
    df.columns = ["open_time", value_name]
    df["open_time"] = _ms_to_ts(df["open_time"]).to_numpy()
    df[value_name] = df[value_name].astype(float)
    return df.set_index("open_time").sort_index()


def fetch_monthly_klines(month: str) -> pd.DataFrame:
    url = f"{BUCKET_MONTHLY}/klines/{SYMBOL}/{TIMEFRAME}/{SYMBOL}-{TIMEFRAME}-{month}.zip"
    rows = read_zip_csv_bytes(fetch_bytes(url))
    return _rows_to_kline_df(rows, "close")


def fetch_monthly_premium(month: str) -> pd.DataFrame:
    url = f"{BUCKET_MONTHLY}/premiumIndexKlines/{SYMBOL}/{TIMEFRAME}/{SYMBOL}-{TIMEFRAME}-{month}.zip"
    rows = read_zip_csv_bytes(fetch_bytes(url))
    return _rows_to_kline_df(rows, "premium_close")


def fetch_monthly_funding(month: str) -> pd.DataFrame:
    url = f"{BUCKET_MONTHLY}/fundingRate/{SYMBOL}/{SYMBOL}-fundingRate-{month}.zip"
    rows = read_zip_csv_bytes(fetch_bytes(url))
    if not rows:
        return pd.DataFrame(columns=["fundingRate"])
    header = rows[0]
    body = rows[1:]
    if body and body[0] == header:
        body = body[1:]
    df = pd.DataFrame(body, columns=header)
    ts_col = "calc_time" if "calc_time" in df.columns else "fundingTime"
    rate_col = "last_funding_rate" if "last_funding_rate" in df.columns else "fundingRate"
    df["fundingTime"] = _ms_to_ts(df[ts_col]).to_numpy()
    df["fundingRate"] = df[rate_col].astype(float)
    return df[["fundingTime", "fundingRate"]].set_index("fundingTime").sort_index()


def fetch_api_klines(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    rows = []
    cur = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    while cur < end_ms:
        p = {"symbol": SYMBOL, "interval": TIMEFRAME, "startTime": cur, "endTime": end_ms, "limit": 1000}
        chunk = _get(f"{API_BASE}/fapi/v1/klines", p)
        if not chunk:
            break
        rows.extend(chunk)
        nxt = chunk[-1][6] + 1
        if nxt <= cur:
            break
        cur = nxt
        time.sleep(0.03)
        if len(chunk) < 1000:
            break
    seen, uniq = set(), []
    for row in rows:
        if row[0] in seen:
            continue
        seen.add(row[0])
        uniq.append(row)
    df = pd.DataFrame(uniq, columns=KLINES_COLS)
    df = df[["open_time", "close"]].copy()
    df["open_time"] = _ms_to_ts(df["open_time"]).to_numpy()
    df["close"] = df["close"].astype(float)
    return df.set_index("open_time").sort_index()


def fetch_api_premium(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    rows = []
    cur = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    while cur < end_ms:
        p = {"symbol": SYMBOL, "interval": TIMEFRAME, "startTime": cur, "endTime": end_ms, "limit": 1000}
        chunk = _get(f"{API_BASE}/fapi/v1/premiumIndexKlines", p)
        if not chunk:
            break
        rows.extend(chunk)
        nxt = chunk[-1][6] + 1
        if nxt <= cur:
            break
        cur = nxt
        time.sleep(0.03)
        if len(chunk) < 1000:
            break
    seen, uniq = set(), []
    for row in rows:
        if row[0] in seen:
            continue
        seen.add(row[0])
        uniq.append(row)
    df = pd.DataFrame(uniq, columns=KLINES_COLS)
    df = df[["open_time", "close"]].copy()
    df.columns = ["open_time", "premium_close"]
    df["open_time"] = _ms_to_ts(df["open_time"]).to_numpy()
    df["premium_close"] = df["premium_close"].astype(float)
    return df.set_index("open_time").sort_index()


def fetch_api_funding(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    rows = _get(
        f"{API_BASE}/fapi/v1/fundingRate",
        {"symbol": SYMBOL, "startTime": int(start_dt.timestamp() * 1000),
         "endTime": int(end_dt.timestamp() * 1000), "limit": 1000},
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["fundingRate"])
    df["fundingTime"] = _ms_to_ts(df["fundingTime"]).to_numpy()
    df["fundingRate"] = df["fundingRate"].astype(float)
    return df[["fundingTime", "fundingRate"]].set_index("fundingTime").sort_index()


def load_metrics_long() -> pd.DataFrame:
    if not os.path.exists(METRICS_PATH):
        raise FileNotFoundError(f"metrics long ausente: {METRICS_PATH}")
    df = pd.read_csv(METRICS_PATH, parse_dates=["create_time"])
    df["create_time"] = pd.to_datetime(df["create_time"], utc=True).astype(TS_DTYPE)
    df = df.sort_values("create_time").drop_duplicates("create_time", keep="last")
    return df.set_index("create_time")


def build_price_premium_funding(start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    months = month_starts(start_ts, end_ts)
    current_month = pd.Timestamp(datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0))

    k_parts, p_parts, f_parts = [], [], []
    for m in months:
        month_str = m.strftime("%Y-%m")
        if m < current_month:
            print(f"   monthly {month_str} ...")
            k_parts.append(fetch_monthly_klines(month_str))
            p_parts.append(fetch_monthly_premium(month_str))
            f_parts.append(fetch_monthly_funding(month_str))
        else:
            month_start = m.to_pydatetime()
            api_end = end_ts.to_pydatetime() + timedelta(minutes=INTERVAL_MIN)
            print(f"   API mês corrente parcial {month_str} ...")
            k_parts.append(fetch_api_klines(month_start, api_end))
            p_parts.append(fetch_api_premium(month_start, api_end))
            f_parts.append(fetch_api_funding(month_start, api_end))

    k = pd.concat(k_parts).sort_index()
    p = pd.concat(p_parts).sort_index()
    f = pd.concat(f_parts).sort_index()
    k = k[~k.index.duplicated(keep="last")]
    p = p[~p.index.duplicated(keep="last")]
    f = f[~f.index.duplicated(keep="last")]

    k = k[(k.index >= start_ts) & (k.index <= end_ts)]
    p = p[(p.index >= start_ts) & (p.index <= end_ts)]
    f = f[(f.index >= start_ts - timedelta(days=5)) & (f.index <= end_ts + timedelta(days=1))]
    return k, p, f


def build_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = load_metrics_long()
    start_ts = metrics.index.min().floor(PANDAS_FREQ)
    end_ts = metrics.index.max().floor(PANDAS_FREQ)

    print(f"Metrics long: {len(metrics)} linhas | {start_ts:%Y-%m-%d %H:%M} → {end_ts:%Y-%m-%d %H:%M}")
    print("Montando klines/premium/funding...")
    k, p, funding = build_price_premium_funding(start_ts, end_ts)

    df = k.join(p, how="inner")
    df["premium_rel"] = df["premium_close"] / df["close"]

    def _merge_asof_series(src: pd.Series) -> np.ndarray:
        x = src.dropna().sort_index()
        if x.empty:
            return np.full(len(df), np.nan)
        right = x.rename("_v").reset_index()
        right.columns = ["open_time", "_v"]
        merged = pd.merge_asof(
            df.index.to_frame(index=False, name="open_time"),
            right,
            on="open_time",
            direction="backward",
        )
        return merged["_v"].to_numpy()

    mapping = {
        "oi": "sum_open_interest",
        "top_ls": "sum_toptrader_long_short_ratio",
        "global_ls": "count_long_short_ratio",
        "taker_ls": "sum_taker_long_short_vol_ratio",
    }
    for out_col, src_col in mapping.items():
        df[out_col] = _merge_asof_series(metrics[src_col])

    return df.sort_index(), funding


def _causal_pct_apply(window: np.ndarray) -> float:
    return float((window <= window[-1]).mean())


def add_features(df: pd.DataFrame, funding_df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ret_lb"] = df["close"] / df["close"].shift(LOOKBACK_BARS) - 1.0
    df["oi_chg"] = df["oi"] / df["oi"].shift(LOOKBACK_BARS) - 1.0
    df["oi_pct"] = df["oi_chg"].rolling(PCT_WINDOW).apply(_causal_pct_apply, raw=True)
    df["prem_pct"] = df["premium_rel"].rolling(PCT_WINDOW).apply(_causal_pct_apply, raw=True)
    df["taker_pct"] = df["taker_ls"].rolling(PCT_WINDOW).apply(_causal_pct_apply, raw=True)

    # Funding causal por barra: sinal e percentil do valor absoluto do funding realizado.
    rates = []
    for ts in df.index:
        st = funding_state_at(funding_df, ts)
        rates.append(float(st["rate"]) if st else np.nan)
    df["funding_rate"] = np.array(rates, dtype=float)
    df["funding_abs"] = np.abs(df["funding_rate"])
    df["funding_abs_pct"] = df["funding_abs"].rolling(PCT_WINDOW).apply(_causal_pct_apply, raw=True)
    return df


def detect_events(df: pd.DataFrame) -> dict[str, list[tuple[int, pd.Timestamp]]]:
    events_e1, events_e2 = [], []
    for i in range(len(df)):
        row = df.iloc[i]
        ts = df.index[i]
        needed = [row["ret_lb"], row["oi_pct"], row["prem_pct"], row["taker_pct"], row["funding_rate"], row["funding_abs_pct"]]
        if not all(np.isfinite(v) for v in needed):
            continue

        if (
            row["ret_lb"] > 0 and
            row["oi_pct"] >= OI_PCT_HIGH and
            row["funding_rate"] > 0 and
            row["funding_abs_pct"] >= FUNDING_ABS_Q and
            row["prem_pct"] >= PREMIUM_RICH_Q and
            row["taker_pct"] >= TAKER_HIGH_Q
        ):
            events_e1.append((i, ts))
        elif (
            row["ret_lb"] < 0 and
            row["oi_pct"] >= OI_PCT_HIGH and
            row["funding_rate"] < 0 and
            row["funding_abs_pct"] >= FUNDING_ABS_Q and
            row["prem_pct"] <= PREMIUM_CHEAP_Q and
            row["taker_pct"] <= TAKER_LOW_Q
        ):
            events_e2.append((i, ts))
    return {"E1": events_e1, "E2": events_e2}


def thin_independent(events: list[tuple[int, pd.Timestamp]], horizon_h: int = PRIMARY_HORIZON_H) -> list[tuple[int, pd.Timestamp]]:
    if not events:
        return []
    out = [events[0]]
    gap = timedelta(hours=horizon_h)
    last = events[0][1]
    for ev in events[1:]:
        if ev[1] - last >= gap:
            out.append(ev)
            last = ev[1]
    return out


def cluster_episodes(events: list[tuple[int, pd.Timestamp]], gap_hours: int = EPISODE_GAP_HOURS) -> list[list[tuple[int, pd.Timestamp]]]:
    if not events:
        return []
    gap = timedelta(hours=gap_hours)
    eps = [[events[0]]]
    for ev in events[1:]:
        if ev[1] - eps[-1][-1][1] < gap:
            eps[-1].append(ev)
        else:
            eps.append([ev])
    return eps


def summarize_side(events: list[tuple[int, pd.Timestamp]], label: str):
    indep = thin_independent(events)
    by_month_raw = pd.Series([ts.to_period("M").strftime("%Y-%m") for _, ts in events]).value_counts().sort_index() if events else pd.Series(dtype=int)
    by_month_indep = pd.Series([ts.to_period("M").strftime("%Y-%m") for _, ts in indep]).value_counts().sort_index() if indep else pd.Series(dtype=int)
    episodes = cluster_episodes(events)
    ep_sizes = sorted((len(e) for e in episodes), reverse=True)
    max_share = (ep_sizes[0] / len(events)) if events else 0.0
    avg_indep_per_month = float(by_month_indep.mean()) if len(by_month_indep) else 0.0
    est_months_for_target = (N_TARGET_INDEP / avg_indep_per_month) if avg_indep_per_month > 0 else float("inf")

    print(f"\n[{label}]")
    print(f"  raw={len(events)}  indep(>=8h)={len(indep)}  episódios(gap<24h)={len(episodes)}  maior_share={100*max_share:.1f}%")
    print(f"  média indep/mês = {avg_indep_per_month:.2f}")
    if np.isfinite(est_months_for_target):
        print(f"  meses estimados para atingir n_indep>={N_TARGET_INDEP} fora-da-amostra: {est_months_for_target:.1f}")
    else:
        print(f"  meses estimados para atingir n_indep>={N_TARGET_INDEP} fora-da-amostra: inviável (freq≈0)")
    print("  por mês (raw):")
    if len(by_month_raw):
        for month, n in by_month_raw.items():
            print(f"    {month}: {int(n)}")
    else:
        print("    sem eventos")
    print("  por mês (indep):")
    if len(by_month_indep):
        for month, n in by_month_indep.items():
            print(f"    {month}: {int(n)}")
    else:
        print("    sem eventos")


def main():
    print("🧪 Q24 — viabilidade da confluência total de crowded squeeze")
    print("   Medindo frequência histórica (raw / indep / episódios) — SEM retorno forward\n")

    df, funding_df = build_dataset()
    print(f"Dataset final: {len(df)} velas M15 | range {df.index[0]:%Y-%m-%d %H:%M} → {df.index[-1]:%Y-%m-%d %H:%M}")
    print(f"Funding: {len(funding_df)} linhas | range {funding_df.index[0]:%Y-%m-%d %H:%M} → {funding_df.index[-1]:%Y-%m-%d %H:%M}")

    df_aug = add_features(df, funding_df)
    events = detect_events(df_aug)

    summarize_side(events["E1"], "E1 crowded long squeeze (confluência total)")
    summarize_side(events["E2"], "E2 crowded short squeeze (confluência total)")

    print("\n--- Conclusão desta rodada ---")
    print("Esta execução mede apenas VIABILIDADE DE FREQUÊNCIA.")
    print("Nenhum retorno forward foi calculado; nenhum veredito econômico foi emitido.")


if __name__ == "__main__":
    main()
