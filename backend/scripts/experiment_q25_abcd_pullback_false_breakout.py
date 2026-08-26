#!/usr/bin/env python3
"""Q25 — ABCD pullback com falso rompimento em BTC (15m).

Pré-registro: docs/estrategias/design/q25-abcd-pullback-falso-rompimento-design-20260826.md

Hipótese: uma formulação objetiva de continuação de tendência com correção ABCD,
sweep de liquidez e candle de força consegue capturar retomadas táticas em BTC
spot 15m com custo pago, operando long e short sem lookahead.

Nada vai para paper/live.
"""

import csv
import io
import os
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.backtest_metrics import _max_drawdown, _sharpe, _sortino
from app.application.services.technical_analysis import _detect_swing_high, _detect_swing_low

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

EMA_LEN = 21
SWING_LOOKBACK = 2
SWING_LOOKFORWARD = 2
STRUCTURE_WINDOW = 80
ABCD_RATIO_MIN = 0.80
ABCD_RATIO_MAX = 1.20
MAX_PATTERN_AGE_BARS = 24
MAX_HOLD_BARS = 16
MIN_BODY_RATIO = 0.50
LONG_CLOSE_LOCATION_MIN = 0.66
SHORT_CLOSE_LOCATION_MAX = 0.34
VOLUME_LOOKBACK = 20
YEAR_MAX_SHARE_LIMIT = 55.0
MIN_TRADES = 30


@dataclass(frozen=True)
class TradeRecord:
    direction: str
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_price: float
    exit_price: float
    gross_return: float
    net_return: float
    hold_bars: int
    exit_reason: str


@dataclass(frozen=True)
class ResultSummary:
    cagr_net: float
    cagr_gross: float
    vol_ann: float
    sharpe: float
    sortino: float
    max_dd_pct: float
    max_dd_days: int
    total_return_pct: float
    net_minus_gross_pp: float
    year_max_share_pct: float
    half_passes: int
    cycle_passes: int
    n_trades: int
    win_rate_pct: float
    payoff_ratio: float
    avg_hold_bars: float
    survives: bool


@dataclass(frozen=True)
class PendingSignal:
    direction: str
    signal_idx: int
    entry_idx: int
    stop_price: float
    target_price: float


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
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    first = rows[0]
    body = rows[1:] if first and first[0] == "open_time" else rows
    df = pd.DataFrame(body, columns=KLINES_COLS)
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df["open_time"] = _ts_to_dt(df["open_time"]).to_numpy()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
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
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df["open_time"] = _ms_to_ts(df["open_time"]).to_numpy()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
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
    df["ema21"] = df["close"].ewm(span=EMA_LEN, adjust=False).mean()
    df["ema21_slope"] = df["ema21"].diff()

    rng = (df["high"] - df["low"]).replace(0.0, np.nan)
    body = (df["close"] - df["open"]).abs()
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    close_location = (df["close"] - df["low"]) / rng

    df["range"] = rng.fillna(0.0)
    df["body"] = body
    df["body_ratio"] = (body / (rng + 1e-9)).fillna(0.0)
    df["upper_wick"] = upper_wick.fillna(0.0)
    df["lower_wick"] = lower_wick.fillna(0.0)
    df["close_location"] = close_location.fillna(0.5)
    df["avg_volume20"] = df["volume"].shift(1).rolling(VOLUME_LOOKBACK).mean()
    return df


def detect_pivots(df: pd.DataFrame) -> list[dict]:
    pivots: list[dict] = []
    for i in range(len(df)):
        if _detect_swing_high(df, i, lookback=SWING_LOOKBACK, lookforward=SWING_LOOKFORWARD):
            pivots.append({
                "index": i,
                "confirm_index": i + SWING_LOOKFORWARD,
                "type": "high",
                "price": float(df.iloc[i]["high"]),
            })
        elif _detect_swing_low(df, i, lookback=SWING_LOOKBACK, lookforward=SWING_LOOKFORWARD):
            pivots.append({
                "index": i,
                "confirm_index": i + SWING_LOOKFORWARD,
                "type": "low",
                "price": float(df.iloc[i]["low"]),
            })
    return pivots


def _latest_confirmed_pivots(pivots: list[dict], bar_index: int, count: int = 4) -> list[dict]:
    confirmed = [p for p in pivots if p["confirm_index"] <= bar_index]
    if len(confirmed) < count:
        return []
    return confirmed[-count:]


def _prior_pivot_of_type(pivots: list[dict], before_index: int, ptype: str) -> dict | None:
    candidates = [p for p in pivots if p["index"] < before_index and p["type"] == ptype]
    if not candidates:
        return None
    return candidates[-1]


def _is_bullish_trend(df: pd.DataFrame, pivots: list[dict], signal_idx: int, a: dict, b: dict) -> bool:
    """Tendência de alta = filtro EMA21 + estrutura PRÉVIA à correção ABCD.

    Importante: usa o pivot anterior a `a`/`b` (fora do próprio padrão ABCD)
    para confirmar topos/fundos ascendentes. Reusar os mesmos pontos A-B-C-D
    do padrão corretivo aqui seria contraditório — a correção por definição
    exige C < A e D < B, o oposto de uma estrutura de alta.
    """
    row = df.iloc[signal_idx]
    if pd.isna(row["ema21"]) or pd.isna(row["ema21_slope"]):
        return False
    if not (row["close"] > row["ema21"] and row["ema21_slope"] > 0):
        return False

    prev_high = _prior_pivot_of_type(pivots, a["index"], "high")
    prev_low = _prior_pivot_of_type(pivots, b["index"], "low")
    if prev_high is None or prev_low is None:
        return False
    return bool(a["price"] > prev_high["price"] and b["price"] > prev_low["price"])


def _is_bearish_trend(df: pd.DataFrame, pivots: list[dict], signal_idx: int, a: dict, b: dict) -> bool:
    """Tendência de baixa = filtro EMA21 + estrutura PRÉVIA à correção ABCD (espelhado)."""
    row = df.iloc[signal_idx]
    if pd.isna(row["ema21"]) or pd.isna(row["ema21_slope"]):
        return False
    if not (row["close"] < row["ema21"] and row["ema21_slope"] < 0):
        return False

    prev_low = _prior_pivot_of_type(pivots, a["index"], "low")
    prev_high = _prior_pivot_of_type(pivots, b["index"], "high")
    if prev_low is None or prev_high is None:
        return False
    return bool(a["price"] < prev_low["price"] and b["price"] < prev_high["price"])


def _valid_volume(row: pd.Series) -> bool:
    avg = row.get("avg_volume20")
    if pd.isna(avg) or avg <= 0:
        return False
    return bool(row["volume"] >= avg)


def _strong_bullish_candle(row: pd.Series, sweep_high: float) -> bool:
    return bool(
        row["close"] > row["open"]
        and row["body_ratio"] >= MIN_BODY_RATIO
        and row["close_location"] >= LONG_CLOSE_LOCATION_MIN
        and row["close"] > sweep_high
        and _valid_volume(row)
    )


def _strong_bearish_candle(row: pd.Series, sweep_low: float) -> bool:
    return bool(
        row["close"] < row["open"]
        and row["body_ratio"] >= MIN_BODY_RATIO
        and row["close_location"] <= SHORT_CLOSE_LOCATION_MAX
        and row["close"] < sweep_low
        and _valid_volume(row)
    )


def _ratio_ok(ab: float, cd: float) -> bool:
    if ab <= 0 or cd <= 0:
        return False
    ratio = cd / ab
    return ABCD_RATIO_MIN <= ratio <= ABCD_RATIO_MAX


def _build_long_signal(df: pd.DataFrame, pivots: list[dict], signal_idx: int) -> PendingSignal | None:
    if signal_idx < 1:
        return None
    latest = _latest_confirmed_pivots(pivots, signal_idx, count=4)
    if len(latest) < 4:
        return None
    if [p["type"] for p in latest] != ["high", "low", "high", "low"]:
        return None

    a, b, c, d = latest
    if not (a["index"] < b["index"] < c["index"] < d["index"]):
        return None
    if signal_idx - d["index"] > MAX_PATTERN_AGE_BARS:
        return None
    if not _is_bullish_trend(df, pivots, signal_idx, a, b):
        return None

    ab = a["price"] - b["price"]
    cd = c["price"] - d["price"]
    if not _ratio_ok(ab, cd):
        return None
    if c["price"] >= a["price"]:
        return None
    if d["price"] >= b["price"]:
        return None

    sweep_idx = d["index"]
    trigger = df.iloc[signal_idx]
    sweep = df.iloc[sweep_idx]
    if not _strong_bullish_candle(trigger, float(sweep["high"])):
        return None

    stop_price = min(float(sweep["low"]), float(trigger["low"]))
    target_price = a["price"]
    entry_idx = signal_idx + 1
    if entry_idx >= len(df):
        return None
    entry_open = float(df.iloc[entry_idx]["open"])
    if not (stop_price < entry_open < target_price):
        return None
    return PendingSignal("LONG", signal_idx, entry_idx, stop_price, target_price)


def _build_short_signal(df: pd.DataFrame, pivots: list[dict], signal_idx: int) -> PendingSignal | None:
    if signal_idx < 1:
        return None
    latest = _latest_confirmed_pivots(pivots, signal_idx, count=4)
    if len(latest) < 4:
        return None
    if [p["type"] for p in latest] != ["low", "high", "low", "high"]:
        return None

    a, b, c, d = latest
    if not (a["index"] < b["index"] < c["index"] < d["index"]):
        return None
    if signal_idx - d["index"] > MAX_PATTERN_AGE_BARS:
        return None
    if not _is_bearish_trend(df, pivots, signal_idx, a, b):
        return None

    ab = b["price"] - a["price"]
    cd = d["price"] - c["price"]
    if not _ratio_ok(ab, cd):
        return None
    if c["price"] <= a["price"]:
        return None
    if d["price"] <= b["price"]:
        return None

    sweep_idx = d["index"]
    trigger = df.iloc[signal_idx]
    sweep = df.iloc[sweep_idx]
    if not _strong_bearish_candle(trigger, float(sweep["low"])):
        return None

    stop_price = max(float(sweep["high"]), float(trigger["high"]))
    target_price = a["price"]
    entry_idx = signal_idx + 1
    if entry_idx >= len(df):
        return None
    entry_open = float(df.iloc[entry_idx]["open"])
    if not (target_price < entry_open < stop_price):
        return None
    return PendingSignal("SHORT", signal_idx, entry_idx, stop_price, target_price)


def collect_signals(df: pd.DataFrame, pivots: list[dict]) -> dict[int, PendingSignal]:
    signals: dict[int, PendingSignal] = {}
    for signal_idx in range(len(df) - 1):
        long_signal = _build_long_signal(df, pivots, signal_idx)
        if long_signal is not None:
            signals[signal_idx] = long_signal
            continue
        short_signal = _build_short_signal(df, pivots, signal_idx)
        if short_signal is not None:
            signals[signal_idx] = short_signal
    return signals


def _resolve_exit(bar: pd.Series, direction: str, stop_price: float, target_price: float) -> tuple[float | None, str | None]:
    high = float(bar["high"])
    low = float(bar["low"])
    if direction == "LONG":
        stop_hit = low <= stop_price
        target_hit = high >= target_price
        if stop_hit and target_hit:
            return stop_price, "stop_same_bar"
        if stop_hit:
            return stop_price, "stop"
        if target_hit:
            return target_price, "target"
        return None, None

    stop_hit = high >= stop_price
    target_hit = low <= target_price
    if stop_hit and target_hit:
        return stop_price, "stop_same_bar"
    if stop_hit:
        return stop_price, "stop"
    if target_hit:
        return target_price, "target"
    return None, None


def simulate(df: pd.DataFrame, signals: dict[int, PendingSignal]) -> tuple[list[TradeRecord], pd.Series, pd.Series, dict[str, int]]:
    trades: list[TradeRecord] = []
    gross_returns = pd.Series(0.0, index=df.index)
    net_returns = pd.Series(0.0, index=df.index)
    signal_counts = {"LONG": 0, "SHORT": 0}

    active: PendingSignal | None = None
    entry_price = 0.0
    entry_idx = -1

    i = 1
    while i < len(df):
        if active is None:
            prev_idx = i - 1
            signal = signals.get(prev_idx)
            if signal is not None and signal.entry_idx == i:
                active = signal
                entry_idx = i
                entry_price = float(df.iloc[i]["open"])
                signal_counts[signal.direction] += 1
            i += 1
            continue

        bar = df.iloc[i]
        exit_price, exit_reason = _resolve_exit(bar, active.direction, active.stop_price, active.target_price)
        timed_out = (i - entry_idx) >= MAX_HOLD_BARS
        if exit_price is None and timed_out:
            exit_price = float(bar["close"])
            exit_reason = "time_stop"

        if exit_price is not None:
            if active.direction == "LONG":
                gross_ret = (exit_price / entry_price) - 1.0
            else:
                gross_ret = (entry_price / exit_price) - 1.0
            net_ret = gross_ret - COST_ROUND_TRIP
            gross_returns.iloc[i] = gross_ret
            net_returns.iloc[i] = net_ret
            trades.append(
                TradeRecord(
                    direction=active.direction,
                    entry_ts=df.index[entry_idx],
                    exit_ts=df.index[i],
                    entry_price=entry_price,
                    exit_price=float(exit_price),
                    gross_return=float(gross_ret),
                    net_return=float(net_ret),
                    hold_bars=int(i - entry_idx),
                    exit_reason=str(exit_reason),
                )
            )
            active = None
            entry_price = 0.0
            entry_idx = -1
        i += 1

    return trades, gross_returns, net_returns, signal_counts


def _equity_curve(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).cumprod()


def _annualized_return(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2:
        return 0.0
    total = equity_curve.iloc[-1] / equity_curve.iloc[0]
    years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
    if years <= 0 or total <= 0:
        return 0.0
    return float(total ** (1 / years) - 1)


def _annualized_vol(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    return float(returns.std(ddof=0) * np.sqrt(365 * 24 * 4))


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


def _yearly_returns(returns: pd.Series) -> pd.Series:
    return ((1.0 + returns).groupby(returns.index.year).prod() - 1.0).astype(float)


def _subwindow_returns(returns: pd.Series) -> dict[str, float]:
    out = {}
    if returns.empty:
        return out
    mid = len(returns) // 2
    windows = {
        "half_1": returns.iloc[:mid],
        "half_2": returns.iloc[mid:],
        "cycle_2017_2019": returns[(returns.index >= "2017-08-17") & (returns.index <= "2019-12-31")],
        "cycle_2020_2022": returns[(returns.index >= "2020-01-01") & (returns.index <= "2022-12-31")],
        "cycle_2023_now": returns[returns.index >= "2023-01-01"],
    }
    for key, series in windows.items():
        out[key] = float((1.0 + series).prod() - 1.0) if len(series) else 0.0
    return out


def _payoff_ratio(trades: list[TradeRecord]) -> float:
    wins = [t.net_return for t in trades if t.net_return > 0]
    losses = [t.net_return for t in trades if t.net_return < 0]
    if not wins:
        return 0.0
    if not losses:
        return 99.0
    return float((sum(wins) / len(wins)) / abs(sum(losses) / len(losses)))


def benchmark_buy_hold(df: pd.DataFrame) -> dict:
    ret = df["close"].pct_change().fillna(0.0)
    equity = _equity_curve(ret)
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


def evaluate(trades: list[TradeRecord], gross_returns: pd.Series, net_returns: pd.Series, bh: dict) -> ResultSummary:
    gross_equity = _equity_curve(gross_returns)
    net_equity = _equity_curve(net_returns)
    _, max_dd_pct = _max_drawdown(net_equity.tolist(), 1.0)
    yearly = _yearly_returns(net_returns)
    yearly_positive = yearly[yearly > 0]
    total_return = float(net_equity.iloc[-1] - 1.0)
    year_max_share_pct = 0.0
    if total_return > 0 and len(yearly_positive):
        year_max_share_pct = float((yearly_positive.max() / total_return) * 100.0)

    windows = _subwindow_returns(net_returns)
    half_passes = sum(v > 0 for k, v in windows.items() if k.startswith("half_"))
    cycle_passes = sum(v > 0 for k, v in windows.items() if k.startswith("cycle_"))
    win_rate = (sum(t.net_return > 0 for t in trades) / len(trades) * 100.0) if trades else 0.0
    avg_hold = float(np.mean([t.hold_bars for t in trades])) if trades else 0.0

    cagr_net = _annualized_return(net_equity)
    cagr_gross = _annualized_return(gross_equity)
    survives = bool(
        cagr_net >= 0.30 * bh["cagr"]
        and float(max_dd_pct) <= 0.70 * bh["max_dd_pct"]
        and year_max_share_pct < YEAR_MAX_SHARE_LIMIT
        and half_passes >= 1
        and cycle_passes >= 2
        and (cagr_gross - cagr_net) * 100.0 <= 1.5
        and len(trades) >= MIN_TRADES
    )

    return ResultSummary(
        cagr_net=float(cagr_net),
        cagr_gross=float(cagr_gross),
        vol_ann=float(_annualized_vol(net_returns)),
        sharpe=float(_sharpe(net_returns.tolist())),
        sortino=float(_sortino(net_returns.tolist())),
        max_dd_pct=float(max_dd_pct),
        max_dd_days=_max_drawdown_duration_days(net_equity),
        total_return_pct=float((net_equity.iloc[-1] - 1.0) * 100.0),
        net_minus_gross_pp=float((cagr_gross - cagr_net) * 100.0),
        year_max_share_pct=float(year_max_share_pct),
        half_passes=int(half_passes),
        cycle_passes=int(cycle_passes),
        n_trades=len(trades),
        win_rate_pct=float(win_rate),
        payoff_ratio=float(_payoff_ratio(trades)),
        avg_hold_bars=float(avg_hold),
        survives=survives,
    )


def print_yearly(name: str, yearly: pd.Series):
    print(f"   {name} por ano:")
    for year, value in yearly.items():
        print(f"      {year}: {value:+.2%}")


def main():
    print("🧪 Q25 — ABCD pullback com falso rompimento em BTC (15m)")
    print("   Long + Short | EMA21 + swings confirmados + sweep + candle de força")
    print("   Custo: 10bp round-trip por trade | sem lookahead | nada vai para paper/live\n")

    df = build_dataset()
    print(f"Dataset final: {len(df)} velas 15m spot | range {df.index[0]:%Y-%m-%d %H:%M} → {df.index[-1]:%Y-%m-%d %H:%M}")
    df = add_features(df)
    pivots = detect_pivots(df)
    signals = collect_signals(df, pivots)
    trades, gross_returns, net_returns, signal_counts = simulate(df, signals)

    bh = benchmark_buy_hold(df)
    summary = evaluate(trades, gross_returns, net_returns, bh)
    yearly = _yearly_returns(net_returns)

    print("\n[Benchmark] Buy & Hold")
    print(f"  CAGR {bh['cagr']:+.2%}  Vol {bh['vol_ann']:+.2%}  Sharpe {bh['sharpe']:+.2f}  Sortino {bh['sortino']:+.2f}")
    print(f"  Total {bh['total_return_pct']:+.2f}%  MaxDD {bh['max_dd_pct']:.2f}%  DD_dias {bh['max_dd_days']}")
    print_yearly("Buy & Hold", bh["yearly_returns"])

    print("\n[Q25]")
    print(f"  pivots detectados {len(pivots)}  sinais long {signal_counts['LONG']}  sinais short {signal_counts['SHORT']}")
    print(f"  trades {summary.n_trades}  win_rate {summary.win_rate_pct:.1f}%  payoff {summary.payoff_ratio:.2f}  hold_médio {summary.avg_hold_bars:.1f} velas")
    print(f"  CAGR_net {summary.cagr_net:+.2%}  CAGR_gross {summary.cagr_gross:+.2%}  Vol {summary.vol_ann:+.2%}")
    print(f"  Sharpe {summary.sharpe:+.2f}  Sortino {summary.sortino:+.2f}  MaxDD {summary.max_dd_pct:.2f}%  DD_dias {summary.max_dd_days}")
    print(f"  Total {summary.total_return_pct:+.2f}%  gross-net CAGR diff {summary.net_minus_gross_pp:.2f}pp  ano_max_share {summary.year_max_share_pct:.1f}%")
    print(f"  halves positivas {summary.half_passes}/2  cycles positivos {summary.cycle_passes}/3")
    print_yearly("Q25", yearly)
    print(f"\n>>> Q25: {'✅ SOBREVIVE (candidata a validação posterior)' if summary.survives else '❌ FALHA'}")


if __name__ == "__main__":
    main()
