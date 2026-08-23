#!/usr/bin/env python3
"""Q14 — BTC basis swing study (48h / 72h / 7d), com guardrails temporais.

Pré-registrado em docs/estrategias/q14-btc-basis-swing-design-20260822.md.

Continuação disciplinada do sinal S1 da Q13 (basis extremo positivo do
BTCUSDT, herdado da Q5). A Q13 já encerrou 48h como par primário (falhou).
Esta rodada pré-registra 72h como novo par primário e adiciona dois
guardrails que a Q13 não tinha:

1. concentração por episódio (gap < 24h) — evita que o efeito seja, na
   prática, um único pump/dump replicado como "vários eventos";
2. fatias temporais (3 fatias de ~63 dias) — evita promover um efeito que só
   existe num único subperíodo favorável (o erro que a Q12 expôs no BNB).

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

# Janelas
FETCH_DAYS = 220
WINDOW_DAYS = 190
N_SLICES = 3
TIMEFRAME = "15m"
INTERVAL_MIN = 15
HORIZONS_HOURS = [48, 72, 24 * 7]
PRIMARY_HORIZON_H = 72

# Sinal (idêntico à Q5/Q13)
P_HIGH = 0.95
PCT_WINDOW_BTC = 384
COST_S1 = 0.0010  # 10bp round-trip

# Guardrails
MIN_N_INDEP = 20
MAX_EPISODE_CONCENTRATION = 0.50
EPISODE_GAP_HOURS = 24
MIN_SLICE_CONFIRM_FRAC = 2 / 3

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


def detect_events(df: pd.DataFrame, window_start, window_end) -> list:
    idx_range = np.where((df.index >= window_start) & (df.index <= window_end))[0]
    events = []
    for i in idx_range:
        pct = df["premium_pct"].iloc[i]
        if np.isfinite(pct) and pct >= P_HIGH:
            events.append((i, df.index[i]))
    return events


def thin_independent_events(events: list, horizon_hours: int) -> list:
    if not events:
        return []
    out = [events[0]]
    min_gap = timedelta(hours=horizon_hours)
    last_ts = events[0][1]
    for ev in events[1:]:
        if ev[1] - last_ts >= min_gap:
            out.append(ev)
            last_ts = ev[1]
    return out


def cluster_episodes(events: list, gap_hours: int = EPISODE_GAP_HOURS) -> list:
    """Agrupa eventos brutos em episódios contíguos (gap < gap_hours)."""
    if not events:
        return []
    gap = timedelta(hours=gap_hours)
    episodes = [[events[0]]]
    for ev in events[1:]:
        if ev[1] - episodes[-1][-1][1] < gap:
            episodes[-1].append(ev)
        else:
            episodes.append([ev])
    return episodes


def t_stat(arr: np.ndarray) -> float:
    if len(arr) > 1 and arr.std(ddof=1) > 0:
        return float(arr.mean() / (arr.std(ddof=1) / np.sqrt(len(arr))))
    return 0.0


def eval_horizon(df: pd.DataFrame, events: list, horizon_h: int, window_start, window_end, label: str = ""):
    steps = int(round(horizon_h * 60 / INTERVAL_MIN))
    indep = thin_independent_events(events, horizon_h)
    closes = df["BTCUSDT_close"].values

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
    net = indep_arr - COST_S1 if len(indep_arr) else indep_arr
    ctrl_net = ctrl_arr - COST_S1 if len(ctrl_arr) else ctrl_arr
    marginal_net = net.mean() - ctrl_net.mean() if len(net) and len(ctrl_net) else float("nan")
    sign_ok = bool(len(indep_arr) and marginal_net < 0)

    tag = f" [{label}]" if label else ""
    print(f"\n[S1 BTC basis+ extreme]{tag} {horizon_h}h")
    print(f"  n_raw={len(raw):>3}  n_indep={len(indep_arr):>3}")
    if len(indep_arr):
        print(f"  gross {indep_arr.mean():+.5f}  net {net.mean():+.5f}  ctrl_net {ctrl_net.mean():+.5f}  "
              f"marginal_net {marginal_net:+.5f}  WR {100*(indep_arr<0).mean():5.1f}%  t={t_stat(indep_arr):+.2f}")
    return {
        "n_raw": len(raw),
        "n_indep": len(indep_arr),
        "marginal_net": float(marginal_net) if len(net) and len(ctrl_net) else float("nan"),
        "sign_ok": sign_ok,
    }


def main():
    print("🧪 Q14 — BTC basis swing study (48h / 72h / 7d) — guardrails temporais")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d buscados | custo: 10bp | primário: {PRIMARY_HORIZON_H}h\n")

    btc = prepare_btc(FETCH_DAYS)
    if btc.empty:
        print("❌ Sem dados suficientes de BTCUSDT. Abortando.")
        return

    window_end = btc.index[-1]
    window_start = window_end - timedelta(days=WINDOW_DAYS)
    events = detect_events(btc, window_start, window_end)
    print(f"Eventos brutos no estudo (premium_pct >= {P_HIGH}): {len(events)}")

    # 1) Resultados por horizonte na janela cheia
    results = {}
    for h in HORIZONS_HOURS:
        results[h] = eval_horizon(btc, events, h, window_start, window_end)

    # 2) Guardrail de concentração por episódio (sobre eventos brutos da janela)
    episodes = cluster_episodes(events)
    ep_sizes = sorted((len(e) for e in episodes), reverse=True)
    max_episode_conc = (ep_sizes[0] / len(events)) if events else 0.0
    print(f"\nEpisódios (gap < {EPISODE_GAP_HOURS}h): {len(episodes)} | maior episódio = "
          f"{ep_sizes[0] if ep_sizes else 0} eventos ({100*max_episode_conc:.1f}% do total)")

    # 3) Guardrail de fatias temporais no horizonte primário
    slice_len = (window_end - window_start) / N_SLICES
    slice_bounds = [(window_start + i * slice_len, window_start + (i + 1) * slice_len) for i in range(N_SLICES)]
    slice_results = []
    print(f"\n--- Fatias temporais ({N_SLICES}x ~{slice_len.days}d) no horizonte primário {PRIMARY_HORIZON_H}h ---")
    for idx, (s_start, s_end) in enumerate(slice_bounds, start=1):
        s_events = detect_events(btc, s_start, s_end)
        r = eval_horizon(btc, s_events, PRIMARY_HORIZON_H, s_start, s_end, label=f"fatia {idx}/{N_SLICES}")
        slice_results.append(r)

    slices_confirm = sum(1 for r in slice_results if r["sign_ok"]) if slice_results else 0
    slice_frac = slices_confirm / N_SLICES

    # 4) Veredito pré-registrado
    print("\nRegra de veredito (pré-registrada):")
    print(f"Primário = {PRIMARY_HORIZON_H}h | falha se n_indep<{MIN_N_INDEP}, sinal não-negativo, "
          f"|marginal_net|<=10bp, concentração de episódio>={int(100*MAX_EPISODE_CONCENTRATION)}%, "
          f"ou <2/3 fatias confirmando")

    primary = results[PRIMARY_HORIZON_H]
    n_ok = primary["n_indep"] >= MIN_N_INDEP
    sign_ok = primary["sign_ok"]
    mag_ok = np.isfinite(primary["marginal_net"]) and abs(primary["marginal_net"]) > COST_S1
    conc_ok = max_episode_conc < MAX_EPISODE_CONCENTRATION
    slice_ok = slice_frac >= MIN_SLICE_CONFIRM_FRAC
    confirm_48h = results[48]["sign_ok"]
    confirm_7d = results[24 * 7]["sign_ok"]

    survives = n_ok and sign_ok and mag_ok and conc_ok and slice_ok and confirm_48h and confirm_7d

    print(f"\n>>> Q14 S1 BTC basis+ {PRIMARY_HORIZON_H}h (primário): {'✅ SOBREVIVE' if survives else '❌ FALHA'}")
    print(f"    n_ok={n_ok} (n_indep={primary['n_indep']})")
    print(f"    sign_ok={sign_ok}")
    print(f"    mag_ok={mag_ok} (marginal_net={primary['marginal_net']:+.5f})")
    print(f"    conc_ok={conc_ok} (maior episódio={100*max_episode_conc:.1f}%)")
    print(f"    slice_ok={slice_ok} ({slices_confirm}/{N_SLICES} fatias confirmaram)")
    print(f"    confirm_48h={confirm_48h}  confirm_7d={confirm_7d}")


if __name__ == "__main__":
    main()
