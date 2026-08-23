#!/usr/bin/env python3
"""Q19 — volatility compression breakout (BB squeeze + MACD) — série longa.

Pré-registro: docs/estrategias/q19-volatility-compression-breakout-design-20260822.md

Objetivo: testar se compressão extrema de volatilidade (Bollinger bandwidth)
com confirmação direcional do MACD carrega expansão curta do preço acima do
controle incondicional.

Nada é estratégia; nada vai para paper/live.
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
import pandas_ta  # noqa: F401  (registra accessor df.ta)
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ---- janelas / parâmetros de evento (travados pelo pré-registro) ----
SYMBOL = "BTCUSDT"
TIMEFRAME = "1h"
PANDAS_FREQ = "1h"
INTERVAL_MIN = 60
PCT_WINDOW = 384
HORIZONS_HOURS = [4, 8, 24]
PRIMARY_HORIZON_H = 8
COST = 0.0010

COMPRESSION_Q = 0.10

MIN_N_INDEP = 20
MAX_EPISODE_CONCENTRATION = 0.50
EPISODE_GAP_HOURS = 24
N_SLICES = 6
MIN_SLICE_CONFIRM_FRAC = 2 / 3
SIGN_REQUESTED = {"E1": +1, "E2": -1}

BUCKET_MONTHLY = "https://data.binance.vision/data/futures/um/monthly"
API_BASE = "https://fapi.binance.com"

KLINES_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_vol",
    "taker_buy_quote_vol", "ignore",
]

TS_DTYPE = "datetime64[ns, UTC]"
START_TS = pd.Timestamp("2020-01-01 00:00", tz="UTC")


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


def build_price_series(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    months = month_starts(start_ts, end_ts)
    current_month = pd.Timestamp(datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0))

    parts = []
    for m in months:
        month_str = m.strftime("%Y-%m")
        if m < current_month:
            print(f"   monthly {month_str} ...")
            try:
                parts.append(fetch_monthly_klines(month_str))
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status == 404:
                    print(f"      skip {month_str}: arquivo não disponível no bucket")
                    continue
                raise
        else:
            month_start = m.to_pydatetime()
            api_end = end_ts.to_pydatetime() + timedelta(minutes=INTERVAL_MIN)
            print(f"   API mês corrente parcial {month_str} ...")
            parts.append(fetch_api_klines(month_start, api_end))

    if not parts:
        raise RuntimeError("nenhuma série de preço disponível para o range pedido")

    k = pd.concat(parts).sort_index()
    k = k[~k.index.duplicated(keep="last")]
    k = k[(k.index >= start_ts) & (k.index <= end_ts)]
    return k


def build_dataset() -> pd.DataFrame:
    end_ts = pd.Timestamp(datetime.now(timezone.utc)).floor(PANDAS_FREQ)
    print(f"Range alvo H1: {START_TS:%Y-%m-%d %H:%M} → {end_ts:%Y-%m-%d %H:%M}")
    print("Montando klines H1...")
    return build_price_series(START_TS, end_ts)


def _causal_pct_apply(window: np.ndarray) -> float:
    return float((window <= window[-1]).mean())


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.ta.bbands(length=20, std=2, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df["bb_width"] = df["BBB_20_2.0_2.0"]
    df["macd_hist"] = df["MACDh_12_26_9"]
    df["bb_width_pct"] = df["bb_width"].rolling(PCT_WINDOW).apply(_causal_pct_apply, raw=True)
    return df


def detect_events(df: pd.DataFrame) -> dict:
    events_e1, events_e2 = [], []
    for i in range(len(df)):
        row = df.iloc[i]
        ts = df.index[i]
        if not np.isfinite(row["bb_width_pct"]) or not np.isfinite(row["macd_hist"]):
            continue
        if row["bb_width_pct"] <= COMPRESSION_Q and row["macd_hist"] > 0:
            events_e1.append((i, ts))
        elif row["bb_width_pct"] <= COMPRESSION_Q and row["macd_hist"] < 0:
            events_e2.append((i, ts))
    return {"E1": events_e1, "E2": events_e2}


def thin_independent(events: list, horizon_h: int) -> list:
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


def cluster_episodes(events: list, gap_hours: int = EPISODE_GAP_HOURS) -> list:
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


def t_stat(a: np.ndarray) -> float:
    if len(a) > 1 and a.std(ddof=1) > 0:
        return float(a.mean() / (a.std(ddof=1) / np.sqrt(len(a))))
    return 0.0


def eval_events(df: pd.DataFrame, events: list, horizon_h: int, label: str, window_start, window_end):
    steps = int(round(horizon_h * 60 / INTERVAL_MIN))
    indep = thin_independent(events, horizon_h)
    closes = df["close"].values

    raw_vals, indep_vals = [], []
    for i, _ts in events:
        j = i + steps
        if j < len(closes) and closes[i] > 0:
            raw_vals.append(closes[j] / closes[i] - 1.0)
    for i, _ts in indep:
        j = i + steps
        if j < len(closes) and closes[i] > 0:
            indep_vals.append(closes[j] / closes[i] - 1.0)

    ctrl = []
    idxs = np.where((df.index >= window_start) & (df.index <= window_end))[0]
    for i in idxs:
        j = i + steps
        if j < len(closes) and closes[i] > 0:
            ctrl.append(closes[j] / closes[i] - 1.0)

    raw = np.array(raw_vals)
    indep_arr = np.array(indep_vals)
    ctrl_arr = np.array(ctrl)
    net = indep_arr - COST if len(indep_arr) else indep_arr
    ctrl_net = ctrl_arr - COST if len(ctrl_arr) else ctrl_arr
    marginal = net.mean() - ctrl_net.mean() if len(net) and len(ctrl_net) else float("nan")

    print(f"\n[{label}] {horizon_h}h")
    print(f"  n_raw={len(raw):>4}  n_indep={len(indep_arr):>4}")
    if len(indep_arr):
        wr = 100 * (indep_arr > 0).mean() if "E1" in label else 100 * (indep_arr < 0).mean()
        print(f"  gross {indep_arr.mean():+.5f}  net {net.mean():+.5f}  ctrl_net {ctrl_net.mean():+.5f}  "
              f"marginal_net {marginal:+.5f}  WR {wr:5.1f}%  t={t_stat(indep_arr):+.2f}")
    return {
        "label": label, "horizon_h": horizon_h,
        "n_raw": len(raw), "n_indep": len(indep_arr),
        "marginal_net": float(marginal) if len(net) and len(ctrl_net) else float("nan"),
    }


def episode_dominance(df: pd.DataFrame, events: list, horizon_h: int) -> dict:
    steps = int(round(horizon_h * 60 / INTERVAL_MIN))
    closes = df["close"].values
    episodes = cluster_episodes(events)
    per_ep = []
    for ep_idx, ep in enumerate(episodes, start=1):
        vals = []
        for i, _ts in ep:
            j = i + steps
            if j < len(closes) and closes[i] > 0:
                vals.append(closes[j] / closes[i] - 1.0)
        if vals:
            per_ep.append((ep_idx, len(vals), float(np.mean(vals))))
    if not per_ep:
        return {"n_ep": 0, "max_ep_share": 0.0, "top_ep_ret": 0.0}
    total_obs = sum(k for _, k, _ in per_ep)
    by_share = sorted(per_ep, key=lambda t: t[1], reverse=True)
    max_share = by_share[0][1] / total_obs if total_obs else 0.0
    top_ret = by_share[0][2]
    print(f"    episódios={len(per_ep)} maior_share={100*max_share:.1f}% ret_ep_maior={top_ret:+.5f}")
    return {"n_ep": len(per_ep), "max_ep_share": max_share, "top_ep_ret": top_ret}


def main():
    print("🧪 Q19 — volatility compression breakout (BB squeeze + MACD) — série longa")
    print("   E1: compressão + MACD positivo → expansão (+) | E2: compressão + MACD negativo → expansão (-) | custo 10bp")
    print(f"   timeframe {TIMEFRAME} | primário {PRIMARY_HORIZON_H}h | coerência 4h/8h/24h | n_indep>=20 | slices={N_SLICES}\n")

    df = build_dataset()
    print(f"Dataset final: {len(df)} velas {TIMEFRAME.upper()} | range {df.index[0]:%Y-%m-%d %H:%M} → {df.index[-1]:%Y-%m-%d %H:%M}")

    df_aug = add_features(df)
    window_start = df_aug.index[0]
    window_end = df_aug.index[-1]

    events = detect_events(df_aug)
    print(f"Eventos E1 (compressão + MACD positivo): {len(events['E1'])}")
    print(f"Eventos E2 (compressão + MACD negativo): {len(events['E2'])}")

    all_results = {}
    for side in ("E1", "E2"):
        evs = events[side]
        if not evs:
            print(f"[{side}] sem eventos — não avaliado.")
            continue
        episodes = cluster_episodes(evs)
        ep_sizes = sorted((len(e) for e in episodes), reverse=True)
        conc = (ep_sizes[0] / len(evs)) if evs else 0.0
        print(f"\n[{side}] episódios(gap<24h)={len(episodes)} | maior={ep_sizes[0]} ({100*conc:.1f}% do raw)")
        episode_dominance(df_aug, evs, PRIMARY_HORIZON_H)

        slice_len = (window_end - window_start) / N_SLICES
        for h in HORIZONS_HOURS:
            all_results[(side, h, "cheia")] = eval_events(df_aug, evs, h, f"{side} janela cheia", window_start, window_end)

        print(f"\n--- {side} fatias ({N_SLICES}x ~{slice_len.days}d) no horizonte primário {PRIMARY_HORIZON_H}h ---")
        confirms = 0
        for idx in range(N_SLICES):
            s0 = window_start + idx * slice_len
            s1 = window_start + (idx + 1) * slice_len
            s_evs = [e for e in evs if s0 <= e[1] < s1]
            r = eval_events(df_aug, s_evs, PRIMARY_HORIZON_H, f"{side} fatia {idx+1}/{N_SLICES}", s0, s1)
            if r["n_indep"] > 0 and np.isfinite(r["marginal_net"]) and r["marginal_net"] * SIGN_REQUESTED[side] > 0:
                confirms += 1
        all_results[(side, PRIMARY_HORIZON_H, "slices")] = confirms

    print("\n--- Veredito pré-registrado ---")
    for side in ("E1", "E2"):
        sign = SIGN_REQUESTED[side]
        evs = events[side]
        if not evs:
            print(f"\n>>> {side}: sem eventos — ❌ sem veredito")
            continue

        res_primary = all_results.get((side, PRIMARY_HORIZON_H, "cheia"))
        cross = None
        if res_primary:
            horizons_ok = True
            for h in HORIZONS_HOURS:
                r = all_results.get((side, h, "cheia"))
                if not r or r["n_indep"] == 0 or not np.isfinite(r["marginal_net"]) or r["marginal_net"] * sign <= 0:
                    horizons_ok = False
                    break
            cross = horizons_ok

        confirms = all_results.get((side, PRIMARY_HORIZON_H, "slices"), 0)
        episodes = cluster_episodes(evs)
        ep_sizes = sorted((len(e) for e in episodes), reverse=True)
        conc = (ep_sizes[0] / len(evs)) if evs else 0.0

        if not res_primary:
            print(f"\n>>> {side}: sem resultado primário — ❌ sem veredito")
            continue

        n_ok = res_primary["n_indep"] >= MIN_N_INDEP
        sign_ok = res_primary["n_indep"] > 0 and np.isfinite(res_primary["marginal_net"]) and res_primary["marginal_net"] * sign > 0
        mag_ok = np.isfinite(res_primary["marginal_net"]) and abs(res_primary["marginal_net"]) > COST
        conc_ok = conc < MAX_EPISODE_CONCENTRATION
        slice_ok = confirms >= N_SLICES * MIN_SLICE_CONFIRM_FRAC

        if n_ok and sign_ok and mag_ok and conc_ok and slice_ok and cross:
            verdict = "✅ SOBREVIVE (candidato Camada A histórica — exige Camada B)"
        elif not n_ok:
            verdict = "🔵 INCONCLUSO"
        else:
            verdict = "❌ FALHA"

        print(f"\n>>> {side} {PRIMARY_HORIZON_H}h: {verdict}")
        print(f"    n_ok={n_ok}  sign_ok={sign_ok}  mag_ok={mag_ok}  conc_ok={conc_ok}  slice_ok={slice_ok}  cross_ok={cross}")
        print(f"    n_indep={res_primary['n_indep']}  marginal_net={res_primary['marginal_net']:+.5f}  conc_ep={100*conc:.1f}%  fatias={confirms}/{N_SLICES}")
        if "SOBREVIVE" in verdict:
            print("    ⚠️  Ainda NÃO é edge. Exige revalidação na série própria (Camada B) antes de qualquer promoção.")


if __name__ == "__main__":
    main()
