#!/usr/bin/env python3
"""Q22 — pullback em tendência com BB + MACD em BTC (15m).

Pré-registro: docs/estrategias/q22-bb-macd-pullback-design-20260822.md

Hipótese: um setup objetivo de pullback em tendência + reaceleração de momentum,
usando Bollinger Bands e MACD, consegue capturar continuação curta com custo pago
sem depender de squeeze extremo.

Nada vai para paper/live.
"""

import csv
import io
import os
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.backtest_metrics import _max_drawdown, _sharpe, _sortino

SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"
PANDAS_FREQ = "15min"
INTERVAL_MIN = 15
START_TS = pd.Timestamp("2017-08-17 00:00", tz="UTC")
COST_ROUND_TRIP = 0.0010
COST_PER_FLIP = COST_ROUND_TRIP / 2

BUCKET_MONTHLY = "https://data.binance.vision/data/spot/monthly"
API_BASE = "https://api.binance.com"

KLINES_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "ignore",
]

TS_DTYPE = "datetime64[ns, UTC]"

# BB / MACD fixos, sem re-tune pós-resultado.
BB_LEN = 20
BB_STD = 2.0
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Variantes pré-registradas da mesma família.
VARIANT_SPECS = [
    "P1_MIDLINE_RECLAIM",
    "P2_TREND_PULLBACK",
    "P3_EXHAUSTION_EXIT",
]


@dataclass(frozen=True)
class VariantResult:
    name: str
    cagr_net: float
    cagr_gross: float
    vol_ann: float
    sharpe: float
    sortino: float
    max_dd_pct: float
    max_dd_days: int
    time_in_market_pct: float
    flips: int
    total_return_pct: float
    net_minus_gross_pp: float
    year_max_share_pct: float
    half_passes: int
    cycle_passes: int
    survives: bool


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


def _ts_to_dt(vals) -> pd.Series:
    s = pd.Series(vals).astype("int64")
    unit = "us" if (s.iloc[0] >= 1e15) else "ms"
    return pd.to_datetime(s, unit=unit, utc=True).astype(TS_DTYPE)


def _rows_to_kline_df(rows: list[list[str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["close"])
    first = rows[0]
    body = rows[1:] if first and first[0] == "open_time" else rows
    df = pd.DataFrame(body, columns=KLINES_COLS)
    df = df[["open_time", "close"]].copy()
    df["open_time"] = _ts_to_dt(df["open_time"]).to_numpy()
    df["close"] = df["close"].astype(float)
    return df.set_index("open_time").sort_index()


def fetch_monthly_klines(month: str) -> pd.DataFrame:
    url = f"{BUCKET_MONTHLY}/klines/{SYMBOL}/{TIMEFRAME}/{SYMBOL}-{TIMEFRAME}-{month}.zip"
    rows = read_zip_csv_bytes(fetch_bytes(url))
    return _rows_to_kline_df(rows)


def fetch_api_klines(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    rows = []
    cur = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    while cur < end_ms:
        p = {"symbol": SYMBOL, "interval": TIMEFRAME, "startTime": cur, "endTime": end_ms, "limit": 1000}
        chunk = _get(f"{API_BASE}/api/v3/klines", p)
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
    print(f"Range alvo 15m spot: {START_TS:%Y-%m-%d} → {end_ts:%Y-%m-%d}")
    print("Montando klines spot 15m...")
    return build_price_series(START_TS, end_ts)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    mid = close.rolling(BB_LEN).mean()
    std = close.rolling(BB_LEN).std(ddof=0)
    df["bb_mid"] = mid
    df["bb_upper"] = mid + BB_STD * std
    df["bb_lower"] = mid - BB_STD * std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / mid

    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
    hist = macd - signal

    df["macd"] = macd
    df["macd_signal"] = signal
    df["macd_hist"] = hist
    df["macd_hist_slope"] = hist.diff()
    df["macd_hist_slope2"] = hist.diff().diff()
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    return df


def _long_base_trend(df: pd.DataFrame) -> pd.Series:
    return (df["ema20"] > df["ema50"]) & (df["close"] > df["ema20"])


def _entry_p1(df: pd.DataFrame) -> pd.Series:
    # Midline reclaim after short pullback.
    pullback = (df["close"].shift(1) <= df["bb_mid"].shift(1)) | (df["close"].shift(2) <= df["bb_mid"].shift(2))
    reclaim = (df["close"] > df["bb_mid"]) & (df["close"].shift(1) <= df["bb_mid"].shift(1))
    macd_ok = (df["macd_hist"] > 0) & (df["macd_hist_slope"] > 0)
    return (pullback & reclaim & macd_ok).fillna(False)


def _entry_p2(df: pd.DataFrame) -> pd.Series:
    # Trend pullback continuation.
    trend = _long_base_trend(df)
    pullback = (df["close"] < df["bb_upper"]) & (df["close"] > df["bb_mid"] * 0.995)
    reclaim = (df["close"] > df["bb_mid"]) & (df["close"].shift(1) <= df["bb_mid"].shift(1))
    macd_ok = (df["macd_hist"] > df["macd_hist"].shift(1)) & (df["macd_hist_slope"] > 0)
    return (trend & pullback & reclaim & macd_ok).fillna(False)


def _entry_p3(df: pd.DataFrame) -> pd.Series:
    # Same entry as P2, but tighter quality on momentum turn.
    trend = _long_base_trend(df)
    pullback = (df["close"] <= df["bb_mid"] * 1.01) & (df["close"] >= df["bb_lower"])
    reclaim = (df["close"] > df["bb_mid"]) & (df["close"].shift(1) <= df["bb_mid"].shift(1))
    macd_ok = (df["macd_hist"] > 0) & (df["macd_hist_slope"] > 0) & (df["macd_hist_slope2"] >= 0)
    return (trend & pullback & reclaim & macd_ok).fillna(False)


def _entry_signal(df: pd.DataFrame, name: str) -> pd.Series:
    if name == "P1_MIDLINE_RECLAIM":
        return _entry_p1(df)
    if name == "P2_TREND_PULLBACK":
        return _entry_p2(df)
    if name == "P3_EXHAUSTION_EXIT":
        return _entry_p3(df)
    raise ValueError(name)


def _exit_signal(df: pd.DataFrame) -> pd.Series:
    # Exit on loss of the midline / loss of momentum / extension exhaustion.
    mid_loss = df["close"] < df["bb_mid"]
    momentum_loss = (df["macd_hist"] < 0) | (df["macd_hist_slope"] < 0)
    exhaustion = (df["close"] >= df["bb_upper"]) & (df["macd_hist_slope"] <= 0)
    return (mid_loss | momentum_loss | exhaustion).fillna(False)


def _max_drawdown_duration_days(equity_curve: pd.Series) -> int:
    peak = equity_curve.iloc[0]
    peak_date = equity_curve.index[0]
    worst = 0
    active_start = None
    for ts, equity in equity_curve.items():
        if equity >= peak:
            peak = equity
            peak_date = ts
            active_start = None
            continue
        if active_start is None:
            active_start = peak_date
        dd_days = (ts - active_start).days
        worst = max(worst, dd_days)
    return int(worst)


def _annualized_return(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2:
        return 0.0
    total = equity_curve.iloc[-1] / equity_curve.iloc[0]
    years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
    if years <= 0 or total <= 0:
        return 0.0
    return float(total ** (1 / years) - 1)


def _annualized_vol(daily_returns: pd.Series) -> float:
    if len(daily_returns) < 2:
        return 0.0
    return float(daily_returns.std(ddof=0) * np.sqrt(365 * 24 * 4))


def _yearly_returns(daily_returns: pd.Series) -> pd.Series:
    by_year = (1.0 + daily_returns).groupby(daily_returns.index.year).prod() - 1.0
    return by_year.astype(float)


def _subwindow_returns(daily_returns: pd.Series) -> dict[str, float]:
    out = {}
    if daily_returns.empty:
        return out
    mid = len(daily_returns) // 2
    halves = {
        "half_1": daily_returns.iloc[:mid],
        "half_2": daily_returns.iloc[mid:],
        "cycle_2017_2019": daily_returns[(daily_returns.index >= "2017-08-17") & (daily_returns.index <= "2019-12-31")],
        "cycle_2020_2022": daily_returns[(daily_returns.index >= "2020-01-01") & (daily_returns.index <= "2022-12-31")],
        "cycle_2023_now": daily_returns[daily_returns.index >= "2023-01-01"],
    }
    for key, s in halves.items():
        out[key] = float((1.0 + s).prod() - 1.0) if len(s) else 0.0
    return out


def simulate_variant(df: pd.DataFrame, name: str) -> tuple[VariantResult, dict]:
    entry = _entry_signal(df, name)
    exit_sig = _exit_signal(df)

    pos = pd.Series(0.0, index=df.index)
    holding = False
    for i in range(1, len(df)):
        if not holding and bool(entry.iloc[i - 1]):
            holding = True
        elif holding and bool(exit_sig.iloc[i - 1]):
            holding = False
        pos.iloc[i] = 1.0 if holding else 0.0

    ret = df["close"].pct_change().fillna(0.0)
    gross_ret = pos * ret
    flips = pos.diff().abs().fillna(pos.abs())
    cost_ret = flips * COST_PER_FLIP
    net_ret = gross_ret - cost_ret

    gross_equity = (1.0 + gross_ret).cumprod()
    net_equity = (1.0 + net_ret).cumprod()

    yearly = _yearly_returns(net_ret)
    yearly_positive = yearly[yearly > 0]
    total_return = float(net_equity.iloc[-1] - 1.0)
    year_max_share_pct = 0.0
    if total_return > 0 and len(yearly_positive):
        year_max_share_pct = float((yearly_positive.max() / total_return) * 100.0)

    half_windows = {k: v for k, v in _subwindow_returns(net_ret).items() if k.startswith("half_")}
    cycle_windows = {k: v for k, v in _subwindow_returns(net_ret).items() if k.startswith("cycle_")}
    half_passes = sum(v > 0 for v in half_windows.values())
    cycle_passes = sum(v > 0 for v in cycle_windows.values())

    _, max_dd_pct = _max_drawdown(net_equity.tolist(), 1.0)
    dd_days = _max_drawdown_duration_days(net_equity)
    cagr_net = _annualized_return(net_equity)
    cagr_gross = _annualized_return(gross_equity)
    vol_ann = _annualized_vol(net_ret)

    details = {
        "net_equity": net_equity,
        "gross_equity": gross_equity,
        "positions": pos,
        "net_returns": net_ret,
        "gross_returns": gross_ret,
        "yearly_returns": yearly,
        "half_windows": half_windows,
        "cycle_windows": cycle_windows,
    }

    result = VariantResult(
        name=name,
        cagr_net=cagr_net,
        cagr_gross=cagr_gross,
        vol_ann=vol_ann,
        sharpe=float(_sharpe(net_ret.tolist())),
        sortino=float(_sortino(net_ret.tolist())),
        max_dd_pct=float(max_dd_pct),
        max_dd_days=dd_days,
        time_in_market_pct=float(pos.mean() * 100.0),
        flips=int(flips.sum()),
        total_return_pct=float((net_equity.iloc[-1] - 1.0) * 100.0),
        net_minus_gross_pp=float((cagr_gross - cagr_net) * 100.0),
        year_max_share_pct=year_max_share_pct,
        half_passes=half_passes,
        cycle_passes=cycle_passes,
        survives=False,
    )
    return result, details


def benchmark_buy_hold(df: pd.DataFrame) -> dict:
    ret = df["close"].pct_change().fillna(0.0)
    equity = (1.0 + ret).cumprod()
    _, max_dd_pct = _max_drawdown(equity.tolist(), 1.0)
    return {
        "cagr": _annualized_return(equity),
        "vol_ann": _annualized_vol(ret),
        "sharpe": float(_sharpe(ret.tolist())),
        "sortino": float(_sortino(ret.tolist())),
        "max_dd_pct": float(max_dd_pct),
        "max_dd_days": _max_drawdown_duration_days(equity),
        "total_return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "yearly_returns": _yearly_returns(ret),
        "equity": equity,
    }


def apply_verdict(variant: VariantResult, bh: dict) -> VariantResult:
    crit1 = variant.cagr_net >= 0.40 * bh["cagr"]
    crit2 = variant.max_dd_pct <= 0.60 * bh["max_dd_pct"]
    crit3a = variant.year_max_share_pct < 50.0
    crit3b = (variant.half_passes >= 1) and (variant.cycle_passes >= 2)
    crit4 = variant.net_minus_gross_pp <= 1.0
    survives = crit1 and crit2 and crit3a and crit3b and crit4
    return VariantResult(**{**variant.__dict__, "survives": survives})


def print_yearly(name: str, yearly: pd.Series):
    print(f"   {name} por ano:")
    for year, value in yearly.items():
        print(f"      {year}: {value:+.2%}")


def main():
    print("🧪 Q22 — pullback em tendência com BB + MACD em BTC (15m)")
    print("   Variantes pré-registradas: P1 Midline Reclaim | P2 Trend Pullback | P3 Exhaustion Exit")
    print("   Custo: 10bp round-trip por flip | sem short sistemático | sem lookahead\n")

    df = build_dataset()
    print(f"Dataset final: {len(df)} velas 15m spot | range {df.index[0]:%Y-%m-%d %H:%M} → {df.index[-1]:%Y-%m-%d %H:%M}")
    df_aug = add_features(df)

    bh = benchmark_buy_hold(df_aug)
    print("\n[Benchmark] Buy & Hold")
    print(f"  CAGR {bh['cagr']:+.2%}  Vol {bh['vol_ann']:+.2%}  Sharpe {bh['sharpe']:+.2f}  Sortino {bh['sortino']:+.2f}")
    print(f"  Total {bh['total_return_pct']:+.2f}%  MaxDD {bh['max_dd_pct']:.2f}%  DD_dias {bh['max_dd_days']}")
    print_yearly("Buy & Hold", bh["yearly_returns"])

    raw_results = []
    all_details = {}
    for name in VARIANT_SPECS:
        variant, details = simulate_variant(df_aug, name)
        variant = apply_verdict(variant, bh)
        raw_results.append(variant)
        all_details[name] = details

        print(f"\n[{variant.name}]")
        print(f"  CAGR_net {variant.cagr_net:+.2%}  CAGR_gross {variant.cagr_gross:+.2%}  Vol {variant.vol_ann:+.2%}")
        print(f"  Sharpe {variant.sharpe:+.2f}  Sortino {variant.sortino:+.2f}  MaxDD {variant.max_dd_pct:.2f}%  DD_dias {variant.max_dd_days}")
        print(f"  Total {variant.total_return_pct:+.2f}%  tempo_em_mercado {variant.time_in_market_pct:.1f}%  flips {variant.flips}")
        print(f"  gross-net CAGR diff {variant.net_minus_gross_pp:.2f}pp  ano_max_share {variant.year_max_share_pct:.1f}%")
        print(f"  halves positivas {variant.half_passes}/2  cycles positivos {variant.cycle_passes}/3")
        print_yearly(variant.name, details["yearly_returns"])
        print(f"  veredito_individual: {'✅ PASSA' if variant.survives else '❌ FALHA'}")

    class_passes = sum(r.survives for r in raw_results)
    print("\n--- Veredito pré-registrado ---")
    print(f"Variantes individuais que passaram: {class_passes}/3")
    overall = class_passes >= 2
    print(f">>> Q22 classe bb-macd-pullback: {'✅ SOBREVIVE (candidata a validação posterior)' if overall else '❌ FALHA'}")


if __name__ == "__main__":
    main()