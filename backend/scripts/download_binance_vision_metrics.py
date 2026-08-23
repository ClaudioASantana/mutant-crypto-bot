#!/usr/bin/env python3
"""Downloader do Binance Vision — daily/metrics (OI + ratios históricos).

Backfill gratuito e profundo do dump diário de métricas de derivativos:
- sum_open_interest
- sum_open_interest_value
- sum_toptrader_long_short_ratio (count + sum)
- sum_long_short_ratio (count + sum)
- sum_taker_long_short_vol_ratio

Fonte: https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/
Granularidade real: amostras aproximadamente a cada 5min (não é grid fixo).

Destino (um CSV único, merge) e um staging dir por dia:
    <DATA_DIR>/derivatives/binance_vision/metrics/{symbol}_metrics_long.csv
    <DATA_DIR>/derivatives/binance_vision/metrics/{symbol}/daily/<date>.csv

Idempotente: arquivos diários já baixados são pulados; colunas ausentes em dias
antigos viram NaN; linhas são deduplicadas por create_time (keep=last).

Uso:
    venv/bin/python scripts/download_binance_vision_metrics.py --symbol BTCUSDT
    venv/bin/python scripts/download_binance_vision_metrics.py --symbol BTCUSDT --start 2025-01-01 --limit 5
"""

import argparse
import io
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests
from xml.etree import ElementTree as ET

BUCKET = "https://data.binance.vision"
S3_LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def list_daily_metric_files(symbol: str) -> list:
    """Lista .zip (sem CHECKSUM) do prefixo, paginando por Marker."""
    prefix = f"data/futures/um/daily/metrics/{symbol}/"
    keys = []
    marker = None
    for _ in range(20):
        params = {"delimiter": "/", "prefix": prefix}
        if marker:
            params["marker"] = marker
        r = requests.get(S3_LIST, params=params, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        keys.extend(k.text for k in root.findall(".//s3:Key", S3_NS))
        nm = root.find(".//s3:NextMarker", S3_NS)
        marker = nm.text if nm is not None else None
        truncated = root.find(".//s3:IsTruncated", S3_NS)
        if truncated is None or truncated.text != "true" or not marker:
            break
    return sorted(f for f in keys if f.endswith(".zip") and "CHECKSUM" not in f)


def fetch_bytes(url: str, retries: int = 3) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=40)
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"download falhou após {retries}t: {url}: {last}")


def read_daily_csv(content: bytes, date_str: str) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            df = pd.read_csv(f)
    df = df.rename(columns={df.columns[0]: "create_time"})
    df["create_time"] = pd.to_datetime(df["create_time"], utc=True)
    # símbolo/lixo colapsado: mantém somente útil e numérico
    for col in df.columns:
        if col in ("symbol",):
            continue
        if col != "create_time":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.drop(columns=["symbol"], errors="ignore")
    df = df[~df["create_time"].duplicated(keep="last")]
    return df.sort_values("create_time").reset_index(drop=True)


def download_one(url: str, out_csv: str, date_str: str) -> tuple:
    if os.path.exists(out_csv) and os.path.getsize(out_csv) > 0:
        return (date_str, "skip", 0)
    content = fetch_bytes(url)
    df = read_daily_csv(content, date_str)
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df.to_csv(out_csv, index=False)
    return (date_str, "ok", len(df))


def merge_staging(staging_dir: str, out_long: str):
    """Concatena todos os CSVs diários em um único, alinhando colunas."""
    files = sorted(
        os.path.join(staging_dir, f)
        for f in os.listdir(staging_dir)
        if f.endswith(".csv") and os.path.getsize(os.path.join(staging_dir, f)) > 0
    )
    if not files:
        print("❌ staging vazio — nada a merge.")
        return
    frames = [pd.read_csv(f) for f in files]
    merged = pd.concat(frames, ignore_index=True)
    merged["create_time"] = pd.to_datetime(merged["create_time"], utc=True)
    merged = merged.sort_values("create_time")
    merged = merged[~merged["create_time"].duplicated(keep="last")]
    merged.to_csv(out_long, index=False)
    print(f"✅ merge: {len(frames)} dias → {len(merged)} linhas → {out_long}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--start", default="2020-09-01", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (inclusive); default=today")
    ap.add_argument("--limit", type=int, default=None, help="limita nº de arquivos (teste)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--merge", action="store_true", default=True,
                    help="merge dos diários num CSV único ao final")
    ap.add_argument("--no-merge", action="store_false", dest="merge")
    ap.add_argument("--out-dir", default=None,
                    help="default: <repo>/backend/data/derivatives/binance_vision/metrics")
    args = ap.parse_args()

    if args.out_dir:
        out_dir = args.out_dir
    else:
        out_dir = os.path.join(
            os.path.dirname(__file__), "..", "data", "derivatives", "binance_vision", "metrics"
        )
    staging_dir = os.path.join(out_dir, args.symbol, "daily")
    out_long = os.path.join(out_dir, f"{args.symbol}_metrics_long.csv")

    print(f"📡 Binance Vision daily/metrics — {args.symbol}")
    files = list_daily_metric_files(args.symbol)
    print(f"   arquivos disponíveis: {len(files)}")

    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = (datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
              if args.end else datetime.now(timezone.utc))

    selected = []
    for f in files:
        filename = f.split("/")[-1]
        stem = filename.removesuffix(".zip")
        prefix = f"{args.symbol}-metrics-"
        if not stem.startswith(prefix):
            continue
        date_part = stem[len(prefix):]  # YYYY-MM-DD
        try:
            d = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if start_dt <= d <= end_dt:
            selected.append((d, f))
    selected.sort(key=lambda t: t[0])

    if args.limit:
        selected = selected[: args.limit]
    if not selected:
        print("   nenhum arquivo selecionado para a janela pedida.")
        return 1
    print(f"   selecionados: {len(selected)} arquivos "
          f"({selected[0][1].split('/')[-1]} → {selected[-1][1].split('/')[-1]})")

    jobs = []
    for d, f in selected:
        url = f"{BUCKET}/{f}"
        date_str = d.strftime("%Y-%m-%d")
        out_csv = os.path.join(staging_dir, f"{date_str}.csv")
        jobs.append((url, out_csv, date_str))

    results = {"ok": 0, "skip": 0, "err": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(download_one, u, c, ds): ds for u, c, ds in jobs}
        for fut in as_completed(futs):
            ds = futs[fut]
            try:
                _date, status, nrows = fut.result()
                if status == "ok":
                    print(f"   ✅ {ds}: {nrows} linhas")
            except Exception as e:  # noqa: BLE001
                print(f"   ❌ {ds}: {e}")
                status = "err"
            results[status if status in results else "err"] += 1

    print(f"\n   baixados={results['ok']}  pulados={results['skip']}  erros={results['err']}")

    if args.merge:
        merge_staging(staging_dir, out_long)
    return 0


if __name__ == "__main__":
    sys.exit(main())