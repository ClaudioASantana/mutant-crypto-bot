#!/usr/bin/env python3
"""Q4 — Coletor de snapshot de microestrutura (100% gratuito, sem API key).

Grava UM registro por execução com o estado atual de:
- open interest (contratos)
- funding rate (último conhecido) + mark/index price
- global long/short account ratio
- top long/short account ratio
- taker buy/sell ratio (proxy de order flow)

Ao longo do tempo, isso constrói NOSSO PRÓPRIO histórico de OI/ratios a partir
de hoje — o dado que faltava para as hipóteses de OI divergence e post-flush.

Destino (append-only, idempotente por timestamp):
    <DATA_DIR>/live_snapshot/oi_funding_ratios.csv

Rodar de forma periódica (ex.: a cada 15min via cron/loop) acumula a série.
Uso: venv/bin/python scripts/collect_snapshot.py [--symbol BTCUSDT] [--data-dir ...]
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://fapi.binance.com"


def _get(url: str, params: dict):
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _last_ratio(endpoint: str, symbol: str):
    data = _get(f"{BASE}{endpoint}", {"symbol": symbol, "period": "15m", "limit": 1})
    if isinstance(data, list) and data:
        return data[-1]
    return {}


def collect(symbol: str) -> dict:
    oi = _get(f"{BASE}/fapi/v1/openInterest", {"symbol": symbol})
    prem = _get(f"{BASE}/fapi/v1/premiumIndex", {"symbol": symbol})
    global_ratio = _last_ratio("/futures/data/globalLongShortAccountRatio", symbol)
    top_ratio = _last_ratio("/futures/data/topLongShortAccountRatio", symbol)
    taker = _last_ratio("/futures/data/takerlongshortRatio", symbol)

    row = {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open_interest": float(oi.get("openInterest", "nan")),
        "mark_price": float(prem.get("markPrice", "nan")),
        "index_price": float(prem.get("indexPrice", "nan")),
        "last_funding_rate": float(prem.get("lastFundingRate", "nan")),
        "global_long_short_ratio": float(global_ratio.get("longShortRatio", "nan")),
        "top_long_short_ratio": float(top_ratio.get("longShortRatio", "nan")),
        "taker_buy_sell_ratio": float(taker.get("buySellRatio", "nan")),
        "taker_buy_vol": float(taker.get("buyVol", "nan")),
        "taker_sell_vol": float(taker.get("sellVol", "nan")),
    }
    return row


def append_row(row: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = pd.DataFrame([row])
    if os.path.exists(path):
        old = pd.read_csv(path)
        # idempotência: descarta registro já existente com o mesmo timestamp
        old = old[old["ts_utc"] != row["ts_utc"]]
        combined = pd.concat([old, new], ignore_index=True)
    else:
        combined = new
    combined.sort_values("ts_utc").to_csv(path, index=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--data-dir", default=None,
                    help="diretório base; default: <repo>/backend/data/derivatives")
    args = ap.parse_args()

    if args.data_dir:
        data_dir = args.data_dir
    else:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "derivatives")

    path = os.path.join(data_dir, "live_snapshot", "oi_funding_ratios.csv")
    row = collect(args.symbol)
    append_row(row, path)

    print(f"📸 snapshot {args.symbol} gravado em {path}")
    for k, v in row.items():
        print(f"   {k:>26}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())