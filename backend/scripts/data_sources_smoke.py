#!/usr/bin/env python3
"""Q4 — Smoketest do data backbone de microestrutura crypto.

Baixa uma amostra real das fontes do Q4 e valida o protocolo de qualidade
(§4 do design q4-data-backbone-design-20260822.md):

1. Binance Vision (mês mais recente completo): klines 15m BTCUSDT,
   fundingRate, premiumIndexKlines.
2. Binance Futures endpoints atuais: openInterest, globalLongShortAccountRatio,
   topLongShortAccountRatio, takerlongshortRatio.

Regras: integridade, continuidade, plausibilidade, consistência cruzada.
Falha em qualquer uma -> exit code != 0 (dataset não consome por study).
"""

import io
import os
import sys
import zipfile
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests

BUCKET = "https://data.binance.vision/data/futures/um/monthly"
SYMBOL = "BTCUSDT"

KLINES_HEADERS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "count", "taker_buy_vol", "taker_buy_quote_vol", "ignore",
]
PREM_HEADERS = KLINES_HEADERS


def latest_month(current: datetime) -> str:
    """Mês mais recente COMPLETO no bucket (exclui mês corrente em curso)."""
    if current.month == 1:
        return f"{current.year - 1}-12"
    return f"{current.year}-{current.month - 1:02d}"


def fetch_zip(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            return pd.read_csv(f)


def parse_vision_klines(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = KLINES_HEADERS
    df = df[df["open_time"].notna()]
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df = df.set_index("open_time")
    return df[~df.index.duplicated(keep="last")].sort_index()


def parse_vision_premium(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = PREM_HEADERS
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype(float)
    df = df.set_index("open_time")
    return df[~df.index.duplicated(keep="last")].sort_index()


def parse_vision_funding(df: pd.DataFrame) -> pd.DataFrame:
    # Esquema atual do Vision: calc_time, funding_interval_hours, last_funding_rate
    df = df.copy()
    df.columns = ["calc_time", "funding_interval_hours", "funding_rate"]
    df["calc_time"] = pd.to_datetime(df["calc_time"], unit="ms", utc=True)
    df["funding_rate"] = df["funding_rate"].astype(float)
    df = df.set_index("calc_time")
    return df[~df.index.duplicated(keep="last")].sort_index()


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {label} {('- ' + detail) if detail else ''}")
    return ok


def main() -> int:
    now = datetime.now(timezone.utc)
    month = latest_month(now)
    print(f"🧪 Q4 smoketest — fonte Binance Vision (mês {month}) + endpoints atuais")
    failures = 0

    # ---- 1. Klines 15m -------------------------------------------------------
    print("\n[1] Klines 15m BTCUSDT")
    try:
        k = parse_vision_klines(fetch_zip(f"{BUCKET}/klines/{SYMBOL}/15m/{SYMBOL}-15m-{month}.zip"))
        n_expected = 24 * 4 * (pd.Timestamp(month, tz="UTC").days_in_month)
        checks = [
            check("linhas plausíveis", len(k) > n_expected * 0.95, f"n={len(k)} esperado~{n_expected}"),
            check("sem NaN em OHLC", k[["open", "high", "low", "close"]].notna().all().all()),
            check(
                "high >= max(open,close)",
                (k["high"] >= k[["open", "close"]].max(axis=1)).all(),
                f"violações {(k['high'] < k[['open','close']].max(axis=1)).sum()}",
            ),
            check(
                "low <= min(open,close)",
                (k["low"] <= k[["open", "close"]].min(axis=1)).all(),
                f"violações {(k['low'] > k[['open','close']].min(axis=1)).sum()}",
            ),
        ]
        diffs = k.index.to_series().diff().dt.total_seconds().dropna()
        checks.append(check("intervalo médio ~900s", abs(diffs.mean() - 900) < 2, f"mean={diffs.mean():.1f}s"))
        checks.append(check("sem gaps > 2x intervalo", (diffs <= 1800).all(), f"max_gap={diffs.max():.0f}s"))
        failures += sum(1 for c in checks if not c)
    except Exception as e:
        print(f"  ❌ falha ao baixar/parsear klines: {e}")
        failures += 1

    # ---- 2. Funding rate -----------------------------------------------------
    print("\n[2] Funding rate (8h)")
    try:
        f = parse_vision_funding(fetch_zip(f"{BUCKET}/fundingRate/{SYMBOL}/{SYMBOL}-fundingRate-{month}.zip"))
        n_expected = 3 * (pd.Timestamp(month, tz="UTC").days_in_month)
        checks = [
            check("linhas plausíveis", len(f) >= n_expected * 0.8, f"n={len(f)} esperado≥{int(n_expected*0.8)}"),
            check("sem NaN", f["funding_rate"].notna().all()),
        ]
        rate = f["funding_rate"]
        checks.append(check("|funding| < 1% (plausível)", (rate.abs() < 0.01).all(), f"max={rate.abs().max():.6f}"))
        failures += sum(1 for c in checks if not c)
    except Exception as e:
        print(f"  ❌ falha ao baixar/parsear funding: {e}")
        failures += 1

    # ---- 3. Premium index klines (basis) -------------------------------------
    print("\n[3] Premium index klines (basis relativizado)")
    try:
        p = parse_vision_premium(fetch_zip(f"{BUCKET}/premiumIndexKlines/{SYMBOL}/15m/{SYMBOL}-15m-{month}.zip"))
        k_close = k["close"].reindex(p.index).ffill()
        basis_rel = (p["close"] / k_close).dropna()
        checks = [
            check("linhas plausíveis", len(p) > n_expected * 0.95, f"n={len(p)}"),
            check("sem NaN", p["close"].notna().all()),
            check("|basis| < 1% (plausível)", (basis_rel.abs() < 0.01).all(), f"max={basis_rel.abs().max():.6f}"),
        ]
        failures += sum(1 for c in checks if not c)
    except Exception as e:
        print(f"  ❌ falha ao baixar/parsear premium: {e}")
        failures += 1

    # ---- 4. Endpoints atuais -------------------------------------------------
    print("\n[4] Endpoints atuais (snapshot)")
    endpoints = {
        "openInterest": "https://fapi.binance.com/fapi/v1/openInterest",
        "globalLongShortAccountRatio": "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
        "topLongShortAccountRatio": "https://fapi.binance.com/futures/data/topLongShortAccountRatio",
        "takerlongshortRatio": "https://fapi.binance.com/futures/data/takerlongshortRatio",
    }
    ok_oi = False
    for name, url in endpoints.items():
        try:
            params = {"symbol": SYMBOL}
            if name != "openInterest":
                params["period"] = "15m"
                params["limit"] = 2
            r = requests.get(url, params=params, timeout=15)
            ok = r.status_code == 200 and len(r.text) > 10
            if name == "openInterest" and ok:
                oi = r.json().get("openInterest", "0")
                ok_oi = float(oi) > 0
                check(f"{name}", ok and ok_oi, f"OI={oi} contratos")
            else:
                check(name, ok, f"status {r.status_code}" if not ok else "")
            failures += 0 if ok else 1
        except Exception as e:
            check(name, False, str(e))
            failures += 1

    # ---- 5. Consistência cruzada: Vision vs endpoint (MESMO período) ---------
    print("\n[5] Consistência: Vision vs endpoint klines (mesma janela de julho)")
    try:
        last_ts = k.index[-1]
        start_ms = int((last_ts - timedelta(hours=1)).timestamp() * 1000)
        end_ms = int(last_ts.timestamp() * 1000)
        r = requests.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={"symbol": SYMBOL, "interval": "15m", "startTime": start_ms, "endTime": end_ms},
            timeout=15,
        )
        rows = r.json()
        live_close = float(rows[-1][4]) if isinstance(rows, list) and rows else None
        last_vision = float(k["close"].iloc[-1])
        if live_close is None:
            check("consistent cross", False, "endpoint vazio")
            failures += 1
        else:
            drift = abs(live_close / last_vision - 1)
            check("close difere < 0.1% (mesma janela)", drift < 0.001, f"drift={drift*100:.4f}%")
            failures += 0 if drift < 0.001 else 1
    except Exception as e:
        check("consistent cross", False, str(e))
        failures += 1

    print(f"\n{'✅ BACKBONE OK — dataset consumível' if failures == 0 else f'❌ {failures} check(s) falharam — ver reporte'}")
    return failures


if __name__ == "__main__":
    sys.exit(main())