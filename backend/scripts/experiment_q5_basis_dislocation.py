#!/usr/bin/env python3
"""Q5 — Event study de basis/premium dislocation.

Pré-registrado em docs/estrategias/q5-basis-event-study-design-20260822.md.
Evento definido de forma CAUSAL: percentil rolante de premium_rel(t) usando
só os últimos 384 candles ATÉ t (sem lookahead).
Event study primeiro — não é estratégia, nada vai para paper/live ainda.

premium_rel(t) = premiumIndexKlines.close(t) / perp.close(t)
Evento P+ : pct(t) >= 0.95  -> hipótese: retorno forward NEGATIVO (fade)
Evento P- : pct(t) <= 0.05  -> hipótese: retorno forward POSITIVO (fade)

Mede retorno forward (1h/4h/8h/24h) a partir do close do candle de evento,
líquido de custo round-trip (10bp), com controle incondicional (todas as velas
da janela) para subtrair o drift do mercado.
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

# --- parâmetros pré-registrados (não varrer de propósito) ---------------------
SYMBOL = "BTCUSDT"
FETCH_DAYS = 130   # 40 de warmup (janela do percentil) + 90 de janela de evento
WINDOW_DAYS = 90   # janela de evento (os últimos 90)
COOLDOWN_MIN = 240 # 4 horas entre eventos do mesmo sinal

PCT_WINDOW = 384   # candles p/ percentil causal (~4 dias em M15)
P_HIGH = 0.95
P_LOW = 0.05

HORIZONS_HOURS = [1, 4, 8, 24]

COST_ROUNDTRIP = 2 * (0.0004 + 0.0001)  # fee 4bp + slippage 1bp, por ponta

TIMEFRAMES = {"M15": (15, "15m"), "H1": (60, "1h")}


def _paginate(url: str, params: dict, time_key_start: str, extract_next_ms) -> list:
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


def fetch_klines_futures(symbol: str, interval: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows_all = _paginate(
        "https://fapi.binance.com/fapi/v1/klines",
        {"symbol": symbol, "interval": interval,
         "startTime": int(start_dt.timestamp() * 1000), "endTime": int(end_dt.timestamp() * 1000),
         "limit": 1000},
        "open_time",
        lambda row: row[6],  # close_time
    )
    if not rows_all:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    seen, uniq = set(), []
    for row in rows_all:
        if row[0] in seen:
            continue
        seen.add(row[0])
        uniq.append(row)

    df = pd.DataFrame(uniq, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_vol",
        "taker_buy_quote_vol", "ignore",
    ])
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df.set_index("open_time", inplace=True)
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_premium_index_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """premiumIndexKlines: OHLC do índice de prêmio (mark-index), causal por candle."""
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows_all = _paginate(
        "https://fapi.binance.com/fapi/v1/premiumIndexKlines",
        {"symbol": symbol, "interval": interval,
         "startTime": int(start_dt.timestamp() * 1000), "endTime": int(end_dt.timestamp() * 1000),
         "limit": 1000},
        "open_time",
        lambda row: row[6],
    )
    if not rows_all:
        return pd.DataFrame(columns=["premium_close"])

    seen, uniq = set(), []
    for row in rows_all:
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
    df.set_index("open_time", inplace=True)
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_funding(symbol: str, days: int) -> pd.DataFrame:
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    rows_all = _paginate(
        "https://fapi.binance.com/fapi/v1/fundingRate",
        {"symbol": symbol, "startTime": int(start_dt.timestamp() * 1000),
         "endTime": int(end_dt.timestamp() * 1000), "limit": 1000},
        "fundingTime",
        lambda row: row["fundingTime"],
    )
    df = pd.DataFrame(rows_all)
    if df.empty:
        return df
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["fundingRate"] = df["fundingRate"].astype(float)
    df = df[["fundingTime", "fundingRate"]].set_index("fundingTime")
    return df[~df.index.duplicated(keep="last")].sort_index()


def prepare(perp: pd.DataFrame, prem: pd.DataFrame) -> pd.DataFrame:
    """Junta perp + premium, calcula premium_rel e percentil causal rolante."""
    if perp.empty or prem.empty:
        return pd.DataFrame()
    df = perp.join(prem, how="inner")
    if len(df) < PCT_WINDOW + 10:
        return pd.DataFrame()

    df["premium_rel"] = df["premium_close"] / df["close"]

    # percentil causal: para cada t, fração de valores em [t-383, t] <= valor em t.
    # janela termina no próprio candle t (dado já fechado nesse instante) — nenhum
    # dado futuro entra no cálculo.
    def _causal_pct(arr: np.ndarray) -> float:
        return float((arr <= arr[-1]).mean())

    df["premium_pct"] = df["premium_rel"].rolling(PCT_WINDOW).apply(_causal_pct, raw=True)
    return df


def detect_events(df: pd.DataFrame, interval_min: int) -> dict:
    end = df.index[-1]
    start = end - timedelta(days=WINDOW_DAYS)
    mask = df.index >= start
    idx_range = np.where(mask)[0]

    cooldown = max(1, int(COOLDOWN_MIN / interval_min))
    events = {"P+": [], "P-": []}
    last_pos = last_neg = -10**9

    for i in idx_range:
        pct = df["premium_pct"].iloc[i]
        if not np.isfinite(pct):
            continue
        if pct >= P_HIGH and i - last_pos >= cooldown:
            events["P+"].append(i)
            last_pos = i
        if pct <= P_LOW and i - last_neg >= cooldown:
            events["P-"].append(i)
            last_neg = i

    return events


def forward_stats(df: pd.DataFrame, indices: list, interval_min: int) -> dict:
    closes = df["close"].values
    n = len(closes)
    out = {}
    for h in HORIZONS_HOURS:
        steps = int(round(h * 60 / interval_min))
        fwd_gross, fwd_net = [], []
        for i in indices:
            j = i + steps
            if j < n and closes[i] > 0:
                g = closes[j] / closes[i] - 1.0
                fwd_gross.append(g)
                fwd_net.append(g - COST_ROUNDTRIP)
        out[h] = {"gross": fwd_gross, "net": fwd_net}
    return out


def control_stats(df: pd.DataFrame, interval_min: int) -> dict:
    start = df.index[-1] - timedelta(days=WINDOW_DAYS)
    idx_range = np.where(df.index >= start)[0]
    closes = df["close"].values
    n = len(closes)
    out = {}
    for h in HORIZONS_HOURS:
        steps = int(round(h * 60 / interval_min))
        vals = []
        for i in idx_range:
            j = i + steps
            if j < n and closes[i] > 0:
                vals.append(closes[j] / closes[i] - 1.0)
        out[h] = np.array(vals)
    return out


def summarize(fwd: dict, ctrl: dict, label: str, predicted_sign: int) -> dict:
    """predicted_sign: +1 se hipótese prevê retorno positivo, -1 se negativo."""
    print(f"\n  --- {label} (sinal previsto: {'+' if predicted_sign > 0 else '-'}) ---")
    verdicts = {}
    for h in HORIZONS_HOURS:
        g = np.array(fwd[h]["gross"])
        net = np.array(fwd[h]["net"])
        c = ctrl[h]
        if len(net) == 0:
            print(f"    {h:>2}h: sem dados")
            verdicts[h] = None
            continue
        t_stat = 0.0
        if len(net) > 1 and net.std(ddof=1) > 0:
            t_stat = net.mean() / (net.std(ddof=1) / np.sqrt(len(net)))
        ctrl_net_mean = (c.mean() - COST_ROUNDTRIP) if len(c) else float("nan")
        marginal = net.mean() - ctrl_net_mean
        sign_ok = (marginal > 0 and predicted_sign > 0) or (marginal < 0 and predicted_sign < 0)
        verdicts[h] = {"n": len(net), "marginal": marginal, "sign_ok": sign_ok}
        print(
            f"    {h:>2}h: n={len(g):>3}  gross {g.mean():+.4f}  net {net.mean():+.4f}  "
            f"ctrl_net {ctrl_net_mean:+.4f}  marginal {marginal:+.4f}  "
            f"WR {100*(g>0).mean():5.1f}%  t={t_stat:+.2f}  {'✅ sinal previsto' if sign_ok else '❌ contra previsão'}"
        )
    return verdicts


def main():
    print("🧪 Q5 — event study: basis/premium dislocation")
    print(f"   Janela: últimos {WINDOW_DAYS}d de {FETCH_DAYS}d | custo round-trip {COST_ROUNDTRIP*1e4:.1f}bp")
    print(f"   Percentil causal: janela {PCT_WINDOW} candles | P+ >= {P_HIGH} | P- <= {P_LOW}\n")

    funding_df = fetch_funding(SYMBOL, FETCH_DAYS)
    primary_verdict = None

    for tf_name, (interval_min, interval) in TIMEFRAMES.items():
        perp = fetch_klines_futures(SYMBOL, interval, FETCH_DAYS)
        prem = fetch_premium_index_klines(SYMBOL, interval, FETCH_DAYS)
        df = prepare(perp, prem)
        if df.empty or len(df) < 60:
            print(f"=== {tf_name}: dados insuficientes (perp={len(perp)}, premium={len(prem)}) ===")
            continue

        events = detect_events(df, interval_min)
        print(f"=== {tf_name} | velas {len(df)} | eventos P+={len(events['P+'])} P-={len(events['P-'])} ===")

        ctrl = control_stats(df, interval_min)
        print("  [controle incondicional]")
        for h in HORIZONS_HOURS:
            arr = ctrl[h]
            if len(arr):
                print(f"    {h:>2}h: n={len(arr):>4}  gross {arr.mean():+.4f}  WR {100*(arr>0).mean():5.1f}%")

        fwd_pos = forward_stats(df, events["P+"], interval_min)
        fwd_neg = forward_stats(df, events["P-"], interval_min)
        v_pos = summarize(fwd_pos, ctrl, "Evento P+ (basis extremo alto -> hipótese: retorno NEGATIVO)", predicted_sign=-1)
        v_neg = summarize(fwd_neg, ctrl, "Evento P- (basis extremo baixo -> hipótese: retorno POSITIVO)", predicted_sign=+1)

        # contexto: funding no momento do evento (causal), confluência com basis extremo
        if events["P+"] and not funding_df.empty:
            print("\n  [contexto funding — Evento P+, 4h]")
            pos, nonpos = [], []
            for i in events["P+"]:
                ts = df.index[i]
                st = funding_state_at(funding_df, ts)
                steps = int(round(4 * 60 / interval_min))
                j = i + steps
                if j >= len(df):
                    continue
                ret = df["close"].values[j] / df["close"].values[i] - 1.0
                (pos if (st and st["rate"] > 0) else nonpos).append(ret)
            for lbl, arr in [("funding>0 ", pos), ("funding<=0", nonpos)]:
                if len(arr):
                    a = np.array(arr)
                    print(f"    {lbl}: n={len(a):>3}  gross {a.mean():+.4f}")

        if tf_name == "M15":
            primary_verdict = (v_pos.get(4), v_neg.get(4))

    print("\nRegra de veredito (pré-registrada): P+ e P- x 4h em M15 é o par primário.")
    print("- Falha se n<50 em qualquer lado, OU marginal sem o sinal previsto em qualquer lado, OU |marginal|<=custo.")
    print("- Sobrevive à fase de event study se n>=50 em ambos os lados E sinal previsto consistente em 1h/4h/8h.")

    if primary_verdict and primary_verdict[0] and primary_verdict[1]:
        vp, vn = primary_verdict
        n_ok = vp["n"] >= 50 and vn["n"] >= 50
        sign_ok = vp["sign_ok"] and vn["sign_ok"]
        mag_ok = abs(vp["marginal"]) > COST_ROUNDTRIP and abs(vn["marginal"]) > COST_ROUNDTRIP
        survives = n_ok and sign_ok and mag_ok
        print(f"\n>>> VEREDITO M15 4h: {'✅ SOBREVIVE (ir para fase seguinte)' if survives else '❌ FALHA (encerrar aqui)'}")
        print(f"    n_ok={n_ok} sign_ok={sign_ok} mag_ok(> custo)={mag_ok}")
    else:
        print("\n>>> VEREDITO M15 4h: ❌ FALHA (dados insuficientes para julgar)")


if __name__ == "__main__":
    main()
