#!/usr/bin/env python3
"""Q20 — trend participation lenta em BTC (long/flat diário).

Pré-registro: docs/estrategias/q20-trend-participation-design-20260822.md

Objetivo: testar se regras públicas e lentas de tendência preservam uma fração
relevante do upside de BTC enquanto reduzem drawdown de forma material.

Nada é estratégia; nada vai para paper/live.
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
TIMEFRAME = "1d"
PANDAS_FREQ = "1d"
INTERVAL_MIN = 24 * 60
START_TS = pd.Timestamp("2017-08-17 00:00", tz="UTC")
COST_ROUND_TRIP = 0.0010
COST_PER_FLIP = COST_ROUND_TRIP / 2

SMA_FAST = 50
SMA_SLOW = 200
MOM_LOOKBACK_DAYS = 365
MOM_SKIP_DAYS = 30

BUCKET_MONTHLY = "https://data.binance.vision/data/spot/monthly"
API_BASE = "https://api.binance.com"

KLINES_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "ignore",
]

TS_DTYPE = "datetime64[ns, UTC]"


@dataclass(frozen=True)
class RuleResult:
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
    # Binance Vision monthly klines trocou o formato em 2025-01:
    #   <= 2024-12 -> milissegundos (13 dígitos)
    #   >= 2025-01 -> microssegundos (16 dígitos)
    # A API /api/v3/klines segue em milissegundos. Detecção por magnitude.
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
    print(f"Range alvo 1d spot: {START_TS:%Y-%m-%d} → {end_ts:%Y-%m-%d}")
    print("Montando klines spot 1d...")
    return build_price_series(START_TS, end_ts)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sma50"] = df["close"].rolling(SMA_FAST).mean()
    df["sma200"] = df["close"].rolling(SMA_SLOW).mean()
    df["mom_12_1"] = df["close"].shift(MOM_SKIP_DAYS) / df["close"].shift(MOM_LOOKBACK_DAYS) - 1.0
    return df


def _apply_signals(df: pd.DataFrame, rule_name: str) -> pd.Series:
    if rule_name == "R1_SMA200":
        sig = (df["close"] > df["sma200"]).astype(float)
    elif rule_name == "R2_GOLDEN_CROSS":
        sig = (df["sma50"] > df["sma200"]).astype(float)
    elif rule_name == "R3_TSMOM_12_1":
        sig = (df["mom_12_1"] > 0).astype(float)
    else:
        raise ValueError(rule_name)
    return sig.fillna(0.0)


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
    return float(daily_returns.std(ddof=0) * np.sqrt(365))


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


def simulate_rule(df: pd.DataFrame, rule_name: str) -> tuple[RuleResult, dict]:
    sig = _apply_signals(df, rule_name)
    pos = sig.shift(1).fillna(0.0)
    spot_ret = df["close"].pct_change().fillna(0.0)
    gross_ret = pos * spot_ret
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
        "net_returns": net_ret,
        "gross_returns": gross_ret,
        "yearly_returns": yearly,
        "half_windows": half_windows,
        "cycle_windows": cycle_windows,
    }

    result = RuleResult(
        name=rule_name,
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


def apply_verdict(rule: RuleResult, bh: dict) -> RuleResult:
    crit1 = rule.cagr_net >= 0.40 * bh["cagr"]
    crit2 = rule.max_dd_pct <= 0.60 * bh["max_dd_pct"]
    crit3a = rule.year_max_share_pct < 50.0
    crit3b = (rule.half_passes >= 1) and (rule.cycle_passes >= 2)
    crit4 = rule.net_minus_gross_pp <= 1.0
    survives = crit1 and crit2 and crit3a and crit3b and crit4
    return RuleResult(**{**rule.__dict__, "survives": survives})


def print_yearly(name: str, yearly: pd.Series):
    print(f"   {name} por ano:")
    for year, value in yearly.items():
        print(f"      {year}: {value:+.2%}")


def main():
    print("🧪 Q20 — trend participation lenta em BTC (long/flat diário)")
    print("   Regras: SMA200 | Golden Cross | TSMOM 12-1 | custo 10bp round-trip por flip")
    print("   Lente: curva de equity (CAGR, DD, Sharpe, Sortino, tempo em mercado, turnover)\n")

    df = build_dataset()
    print(f"Dataset final: {len(df)} velas 1D spot | range {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}")
    df_aug = add_features(df)

    bh = benchmark_buy_hold(df_aug)
    print("\n[Benchmark] Buy & Hold")
    print(f"  CAGR {bh['cagr']:+.2%}  Vol {bh['vol_ann']:+.2%}  Sharpe {bh['sharpe']:+.2f}  Sortino {bh['sortino']:+.2f}")
    print(f"  Total {bh['total_return_pct']:+.2f}%  MaxDD {bh['max_dd_pct']:.2f}%  DD_dias {bh['max_dd_days']}")
    print_yearly("Buy & Hold", bh["yearly_returns"])

    raw_results = []
    all_details = {}
    for rule_name in ("R1_SMA200", "R2_GOLDEN_CROSS", "R3_TSMOM_12_1"):
        rule, details = simulate_rule(df_aug, rule_name)
        rule = apply_verdict(rule, bh)
        raw_results.append(rule)
        all_details[rule_name] = details

        print(f"\n[{rule.name}]")
        print(f"  CAGR_net {rule.cagr_net:+.2%}  CAGR_gross {rule.cagr_gross:+.2%}  Vol {rule.vol_ann:+.2%}")
        print(f"  Sharpe {rule.sharpe:+.2f}  Sortino {rule.sortino:+.2f}  MaxDD {rule.max_dd_pct:.2f}%  DD_dias {rule.max_dd_days}")
        print(f"  Total {rule.total_return_pct:+.2f}%  tempo_em_mercado {rule.time_in_market_pct:.1f}%  flips {rule.flips}")
        print(f"  gross-net CAGR diff {rule.net_minus_gross_pp:.2f}pp  ano_max_share {rule.year_max_share_pct:.1f}%")
        print(f"  halves positivas {rule.half_passes}/2  cycles positivos {rule.cycle_passes}/3")
        print_yearly(rule.name, details["yearly_returns"])
        print(f"  veredito_individual: {'✅ PASSA' if rule.survives else '❌ FALHA'}")

    class_passes = sum(r.survives for r in raw_results)
    print("\n--- Veredito pré-registrado ---")
    print(f"Regras individuais que passaram: {class_passes}/3")
    overall = class_passes >= 2
    print(f">>> Q20 classe trend participation: {'✅ SOBREVIVE (candidata a validação posterior)' if overall else '❌ FALHA'}")


if __name__ == "__main__":
    main()
