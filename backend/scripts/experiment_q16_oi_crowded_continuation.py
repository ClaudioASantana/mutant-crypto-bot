#!/usr/bin/env python3
"""Q16 — OI crowded continuation — Camada A (flip test pré-registrado).

Pré-registrado em docs/estrategias/q16-oi-crowded-continuation-design-20260822.md.

Flip test da Q15: lá a hipótese era unwind/reversão; o resultado no primário
veio na direção oposta (continuação). Esta rodada testa a leitura alternativa
com os MESMOS parâmetros (sem re-tuning) e guardrails mais rígidos porque é
um flip test:

- coerência cross-horizonte obrigatória (4h AND 8h AND 24h no mesmo sinal);
- n_indep >= 20 no primário (senão: INCONCLUSO, não aprovação);
- magnitude > 10bp;
- concentração de episódio < 50%;
- >= 2/3 fatias no sentido da hipótese;
- reporta dominância por episódio no primário.

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

# ---- janelas (idênticas à Q15) ----
TIMEFRAME = "15m"
INTERVAL_MIN = 15
FETCH_HISTORY_DAYS = 30
LOOKBACK_BARS = 16
PCT_WINDOW = 384
HORIZONS_HOURS = [4, 8, 24]
PRIMARY_HORIZON_H = 8
COST = 0.0010

# ---- definição de eventos (idêntica à Q15) ----
OI_PCT_HIGH = 0.90
PREMIUM_RICH_Q = 0.75
PREMIUM_CHEAP_Q = 0.25

# ---- guardrails (mais rígidos) ----
MIN_N_INDEP = 20
MAX_EPISODE_CONCENTRATION = 0.50
EPISODE_GAP_HOURS = 24
N_SLICES = 3
MIN_SLICE_CONFIRM_FRAC = 2 / 3
SIGN_REQUESTED = {"E1": +1, "E2": -1}  # direção da hipótese desta rodada

KLINES_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_vol",
    "taker_buy_quote_vol", "ignore",
]


# ------------------------- fetch helpers ------------------------------
def base() -> str:
    return "https://fapi.binance.com"


def _get(url: str, params: dict):
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _paginate_hist(url: str, symbol: str, period: str, days: int, key: str) -> list:
    end_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(days=days)
    rows_all, seen = [], set()

    while end_dt > start_dt:
        params = {
            "symbol": symbol,
            "period": period,
            "limit": 500,
            "endTime": int(end_dt.timestamp() * 1000),
        }
        rows = _get(f"{base()}/futures/data/{url}", params)
        if not rows or not isinstance(rows, list):
            break
        first_ts = rows[0][key]
        for row in rows:
            if row[key] not in seen:
                seen.add(row[key])
                rows_all.append(row)
        if len(rows) < 500:
            break
        next_end = first_ts - 1
        end_dt = datetime.fromtimestamp(next_end / 1000, tz=timezone.utc)
        time.sleep(0.05)

    uniq = {r[key]: r for r in rows_all}
    return list(uniq.values())


def fetch_klines_symbol(symbol: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows = []
    cur = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    while cur < end_ms:
        p = {"symbol": symbol, "interval": TIMEFRAME, "startTime": cur, "endTime": end_ms, "limit": 1000}
        chunk = _get(f"{base()}/fapi/v1/klines", p)
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
    df.columns = ["open_time", "close"]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close"] = df["close"].astype(float)
    return df.set_index("open_time").sort_index()


def fetch_premium_symbol(symbol: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows = []
    cur = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    while cur < end_ms:
        p = {"symbol": symbol, "interval": TIMEFRAME, "startTime": cur, "endTime": end_ms, "limit": 1000}
        chunk = _get(f"{base()}/fapi/v1/premiumIndexKlines", p)
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
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["premium_close"] = df["premium_close"].astype(float)
    return df.set_index("open_time").sort_index()


def fetch_funding_symbol(symbol: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows = _get(
        f"{base()}/fapi/v1/fundingRate",
        {"symbol": symbol, "startTime": int(start_dt.timestamp() * 1000),
         "endTime": int(end_dt.timestamp() * 1000), "limit": 1000},
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["fundingRate"] = df["fundingRate"].astype(float)
    return df[["fundingTime", "fundingRate"]].set_index("fundingTime").sort_index()


def fetch_hist_series(url: str, symbol: str, period: str, days: int, rename_to: str) -> pd.DataFrame:
    rows = _paginate_hist(url, symbol, period, days, key="timestamp")
    if not rows:
        return pd.DataFrame(columns=[rename_to])

    value_col_by_endpoint = {
        "openInterestHist": "sumOpenInterest",
        "globalLongShortAccountRatio": "longShortRatio",
        "topLongShortAccountRatio": "longShortRatio",
        "takerlongshortRatio": "buySellRatio",
    }
    value_col = value_col_by_endpoint[url]

    df = pd.DataFrame(rows)[["timestamp", value_col]].copy()
    df.columns = ["open_time", rename_to]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df[rename_to] = df[rename_to].astype(float)
    return df.set_index("open_time").sort_index()


# ------------------------- data assembly ------------------------------
def build_dataset(days: int = FETCH_HISTORY_DAYS) -> pd.DataFrame:
    k = fetch_klines_symbol("BTCUSDT", days)
    p = fetch_premium_symbol("BTCUSDT", days)
    df = k.join(p, how="inner")
    if df.empty:
        return pd.DataFrame()

    df["premium_rel"] = df["premium_close"] / df["close"]

    oi = fetch_hist_series("openInterestHist", "BTCUSDT", TIMEFRAME, days, "oi")
    gl = fetch_hist_series("globalLongShortAccountRatio", "BTCUSDT", TIMEFRAME, days, "global_ls")
    tp = fetch_hist_series("topLongShortAccountRatio", "BTCUSDT", TIMEFRAME, days, "top_ls")
    tk = fetch_hist_series("takerlongshortRatio", "BTCUSDT", TIMEFRAME, days, "taker_ls")

    def _merge_asof(col: pd.DataFrame | pd.Series) -> pd.Series:
        x = col.iloc[:, 0] if isinstance(col, pd.DataFrame) else col
        x = x.rename("_v").dropna()
        if x.empty:
            return pd.Series(np.nan, index=df.index)
        merged = pd.merge_asof(
            df.index.to_frame(index=False, name="open_time"),
            x.to_frame(),
            on="open_time",
            direction="backward",
        )
        return merged["_v"].to_numpy()

    for name, s in [("oi", oi), ("global_ls", gl), ("top_ls", tp), ("taker_ls", tk)]:
        if not s.empty:
            df[name] = _merge_asof(s)
        else:
            df[name] = np.nan

    if df["oi"].isna().sum() > len(df) * 0.5:
        print("⚠️  Cobertura de OI insuficiente na janela. Camada A comprometida.")
    return df


# ------------------------- event detection ----------------------------
def _causal_pct_apply(window: np.ndarray) -> float:
    return float((window <= window[-1]).mean())


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ret_lb"] = df["close"] / df["close"].shift(LOOKBACK_BARS) - 1.0
    df["oi_chg"] = df["oi"] / df["oi"].shift(LOOKBACK_BARS) - 1.0
    df["oi_pct"] = df["oi_chg"].rolling(PCT_WINDOW).apply(_causal_pct_apply, raw=True)
    df["prem_pct"] = df["premium_rel"].rolling(PCT_WINDOW).apply(_causal_pct_apply, raw=True)
    return df


def detect_events(df: pd.DataFrame, funding_df: pd.DataFrame) -> dict:
    events_e1, events_e2 = [], []
    for i in range(len(df)):
        row = df.iloc[i]
        ts = df.index[i]
        if not (np.isfinite(row["ret_lb"]) and np.isfinite(row["oi_pct"]) and np.isfinite(row["prem_pct"])):
            continue
        st = funding_state_at(funding_df, ts)
        f_rate = float(st["rate"]) if st else 0.0

        if row["ret_lb"] > 0 and row["oi_pct"] >= OI_PCT_HIGH and f_rate > 0 and row["prem_pct"] >= PREMIUM_RICH_Q:
            events_e1.append((i, ts))
        elif row["ret_lb"] < 0 and row["oi_pct"] >= OI_PCT_HIGH and f_rate < 0 and row["prem_pct"] <= PREMIUM_CHEAP_Q:
            events_e2.append((i, ts))
    return {"E1": events_e1, "E2": events_e2}


# ------------------------- measurements -------------------------------
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
    print(f"  n_raw={len(raw):>3}  n_indep={len(indep_arr):>3}")
    if len(indep_arr):
        print(f"  gross {indep_arr.mean():+.5f}  net {net.mean():+.5f}  ctrl_net {ctrl_net.mean():+.5f}  "
              f"marginal_net {marginal:+.5f}  WR {100*(indep_arr<0).mean():5.1f}%  t={t_stat(indep_arr):+.2f}")
    return {
        "label": label, "horizon_h": horizon_h,
        "n_raw": len(raw), "n_indep": len(indep_arr),
        "marginal_net": float(marginal) if len(net) and len(ctrl_net) else float("nan"),
    }


def episode_dominance(df: pd.DataFrame, events: list, horizon_h: int) -> dict:
    """Retorno médio por episódio no primário (gross, sem custo) + dominância."""
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
    print(f"    episódios={len(per_ep)} maior_share={100*max_share:.0f}% ret_ep_maior={top_ret:+.5f}")
    return {"n_ep": len(per_ep), "max_ep_share": max_share, "top_ep_ret": top_ret}


# ------------------------- main -------------------------------
def main():
    print("🧪 Q16 — OI crowded continuation — Camada A (flip test pré-registrado)")
    print(f"   E1: crowded long → continuação (+) | E2: crowded short → continuação (-) | custo 10bp")
    print(f"   primário {PRIMARY_HORIZON_H}h | coerência 4h/8h/24h | n_indep>=20 senão INCONCLUSO\n")

    df = build_dataset(FETCH_HISTORY_DAYS)
    if df.empty:
        print("❌ Sem dados. Abortando.")
        return
    print(f"Dataset: {len(df)} velas M15 | range {df.index[0]:%m-%d %H:%M} → {df.index[-1]:%m-%d %H:%M}")

    funding_df = fetch_funding_symbol("BTCUSDT", FETCH_HISTORY_DAYS + 10)
    df_aug = add_features(df)

    window_end = df_aug.index[-1]
    window_start = max(df_aug.index[0], window_end - timedelta(days=FETCH_HISTORY_DAYS))

    events = detect_events(df_aug, funding_df)
    print(f"Eventos E1 (crowded long, continuação):  {len(events['E1'])}")
    print(f"Eventos E2 (crowded short, continuação): {len(events['E2'])}")

    all_results = {}
    for side in ("E1", "E2"):
        evs = events[side]
        if not evs:
            print(f"[{side}] sem eventos — não avaliado.")
            continue
        episodes = cluster_episodes(evs)
        ep_sizes = sorted((len(e) for e in episodes), reverse=True)
        conc = (ep_sizes[0] / len(evs)) if evs else 0.0
        print(f"\n[{side}] episódios(gap<24h)={len(episodes)} | maior={ep_sizes[0]} "
              f"({100*conc:.1f}% do raw)")
        episode_dominance(df_aug, evs, PRIMARY_HORIZON_H)

        slice_len = (window_end - window_start) / N_SLICES
        for h in HORIZONS_HOURS:
            all_results[(side, h, "cheia")] = eval_events(
                df_aug, evs, h, f"{side} janela cheia", window_start, window_end)

        print(f"\n--- {side} fatias ({N_SLICES}x ~{slice_len.days}d) no horizonte primário {PRIMARY_HORIZON_H}h ---")
        confirms = 0
        for idx in range(N_SLICES):
            s0 = window_start + idx * slice_len
            s1 = window_start + (idx + 1) * slice_len
            s_evs = [e for e in evs if s0 <= e[1] < s1]
            r = eval_events(df_aug, s_evs, PRIMARY_HORIZON_H, f"{side} fatia {idx+1}/{N_SLICES}", s0, s1)
            if r["n_indep"] > 0 and np.isfinite(r["marginal_net"]) and \
                    r["marginal_net"] * SIGN_REQUESTED[side] > 0:
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
        # coerência cross-horizonte
        cross = None
        if res_primary:
            horizons_ok = True
            for h in HORIZONS_HOURS:
                r = all_results.get((side, h, "cheia"))
                if not r or r["n_indep"] == 0 or not np.isfinite(r["marginal_net"]) or \
                        r["marginal_net"] * sign <= 0:
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
        sign_ok = res_primary["n_indep"] > 0 and np.isfinite(res_primary["marginal_net"]) and \
            res_primary["marginal_net"] * sign > 0
        mag_ok = np.isfinite(res_primary["marginal_net"]) and abs(res_primary["marginal_net"]) > COST
        conc_ok = conc < MAX_EPISODE_CONCENTRATION
        slice_ok = confirms >= N_SLICES * MIN_SLICE_CONFIRM_FRAC

        if not n_ok:
            verdict = "🔵 INCONCLUSO (n_indep insuficiente na Camada A)"
        elif n_ok and sign_ok and mag_ok and conc_ok and slice_ok and cross:
            verdict = "✅ SOBREVIVE (candidato Camada A — exige revalidação Camada B)"
        else:
            verdict = "❌ FALHA"

        print(f"\n>>> {side} {PRIMARY_HORIZON_H}h: {verdict}")
        print(f"    n_ok={n_ok}  sign_ok={sign_ok}  mag_ok={mag_ok}  conc_ok={conc_ok}  "
              f"slice_ok={slice_ok}  cross_ok={cross}")
        print(f"    n_indep={res_primary['n_indep']}  marginal_net={res_primary['marginal_net']:+.5f}  "
              f"conc_ep={100*conc:.1f}%  fatias={confirms}/{N_SLICES}")
        if "SOBREVIVE" in verdict:
            print("    ⚠️  Ainda NÃO é edge. Exige revalidação na série própria acumulada (Camada B) antes de qualquer promoção.")


if __name__ == "__main__":
    main()