#!/usr/bin/env python3
"""Q4 — Downloader do Binance Vision para backfill histórico gratuito.

Baixa arquivos mensais do bucket público data.binance.vision para o backbone:
- klines/<symbol>/<tf>
- fundingRate/<symbol>
- premiumIndexKlines/<symbol>/<tf>

Destino:
    backend/data/derivatives/binance_vision/monthly/<YYYY-MM>/

Uso exemplo:
    venv/bin/python scripts/download_binance_vision.py --symbol BTCUSDT --tf 15m --months 2026-06 2026-07
"""

import argparse
import io
import os
import sys
import zipfile

import requests

BUCKET = "https://data.binance.vision/data/futures/um/monthly"


def fetch_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def unzip_first(content: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            return f.read()


def write_bytes(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def download_month(symbol: str, tf: str, month: str, out_dir: str):
    jobs = [
        (
            f"{BUCKET}/klines/{symbol}/{tf}/{symbol}-{tf}-{month}.zip",
            os.path.join(out_dir, month, f"klines_{symbol}_{tf}.csv"),
        ),
        (
            f"{BUCKET}/premiumIndexKlines/{symbol}/{tf}/{symbol}-{tf}-{month}.zip",
            os.path.join(out_dir, month, f"premiumIndexKlines_{symbol}_{tf}.csv"),
        ),
        (
            f"{BUCKET}/fundingRate/{symbol}/{symbol}-fundingRate-{month}.zip",
            os.path.join(out_dir, month, f"fundingRate_{symbol}.csv"),
        ),
    ]

    for url, path in jobs:
        data = unzip_first(fetch_bytes(url))
        write_bytes(path, data)
        print(f"✅ {month}: {os.path.basename(path)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--tf", default="15m")
    ap.add_argument("--months", nargs="+", required=True, help="YYYY-MM YYYY-MM ...")
    ap.add_argument("--out-dir", default=None,
                    help="default: <repo>/backend/data/derivatives/binance_vision/monthly")
    args = ap.parse_args()

    if args.out_dir:
        out_dir = args.out_dir
    else:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "data", "derivatives", "binance_vision", "monthly")

    for month in args.months:
        download_month(args.symbol, args.tf, month, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())