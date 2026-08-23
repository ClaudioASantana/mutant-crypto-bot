#!/usr/bin/env python3
"""Q23 — operador contextual com checklist (pullback em tendência) em BTC (15m).

Pré-registro: docs/estrategias/q23-operator-contextual-pullback-design-20260823.md
(seção 13 congela todos os números antes da execução).

Hipótese: um checklist contextual determinístico (tendência, localização,
momentum, regime) consegue separar entradas boas de entradas ruins do mesmo
setup-base de pullback em tendência, melhorando o processo vs operar o setup
sozinho.

Nada vai para paper/live.
"""

import csv
import io
import os
import sys
import time
import zipfile
from dataclasses import dataclass, field
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

# Custo: 10bp round-trip por trade = 5bp por flip.
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

# --- Features fixas (sem re-tune) ---
BB_LEN = 20
BB_STD = 2.0
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
RSI_LEN = 14
ATR_LEN = 14
ADX_LEN = 14

# --- Setup-base (pullback em tendência) ---
PULLBACK_BARS = 6          # min(close, últimas 6) tocou a banda média
EMA_FAST = 20
EMA_MID = 50
EMA_SLOW = 200

# --- Checklist contextual (pré-registrado) ---
ENTER_SCORE = 6
WAIT_MIN = 3
VETO_MAX = 2
VETO_FLOOR = 3             # blocka score <= 2
ATR_EXTREME_Q = 0.95       # D1: atr <= quantil 0.95 (últimas 200)
ADX_TREND_MIN = 18.0       # D2: não-chop
ADX_CHOP_MAX = 15.0        # D3: chop
BB_WIDTH_CHOP_Q = 0.25     # D3: compressão
ATR_Q_WINDOW = 200
BBQ_Q_WINDOW = 100

# --- Modos ---
MODES = ["BASE", "CHECKLIST", "VETO"]


@dataclass
class Trade:
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    hold_bars: int
    score_decision: float
    gross_return: float
    net_return: float


@dataclass(frozen=True)
class ModeResult:
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
    n_trades: int
    avg_trade_gross: float
    avg_trade_net: float
    win_rate_gross: float
    payoff_gross: float
    avg_hold_bars: float
    year_max_share_calc: float = 0.0


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
    df = df[["open_time", "open", "high", "low", "close"]].copy()
    df["open_time"] = _ts_to_dt(df["open_time"]).to_numpy()
    for col in ("open", "high", "low", "close"):
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
    df = df[["open_time", "open", "high", "low", "close"]].copy()
    df["open_time"] = _ms_to_ts(df["open_time"]).to_numpy()
    for col in ("open", "high", "low", "close"):
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
    close, high, low = df["close"], df["high"], df["low"]

    # Bollinger 20/2
    mid = close.rolling(BB_LEN).mean()
    std = close.rolling(BB_LEN).std(ddof=0)
    df["bb_mid"] = mid
    df["bb_upper"] = mid + BB_STD * std
    df["bb_lower"] = mid - BB_STD * std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / mid

    # MACD 12/26/9
    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
    hist = macd - signal
    df["macd_hist"] = hist
    df["macd_hist_slope"] = hist.diff()

    # EMAs do setup-base e do bloco tendência
    df["ema20"] = close.ewm(span=EMA_FAST, adjust=False).mean()
    df["ema50"] = close.ewm(span=EMA_MID, adjust=False).mean()
    df["ema200"] = close.ewm(span=EMA_SLOW, adjust=False).mean()

    # RSI 14 (Wilder)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / RSI_LEN, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / RSI_LEN, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    df["rsi14"] = 100.0 - 100.0 / (1.0 + rs)

    # ATR 14 (Wilder)
    hl = high - low
    hc = (high - close.shift(1)).abs()
    lc = (low - close.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / ATR_LEN, adjust=False).mean()
    df["atr14"] = atr

    # ADX 14 (Wilder)
    up = high.diff()
    dn = -low.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / ADX_LEN, adjust=False).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / ADX_LEN, adjust=False).mean() / atr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    df["adx14"] = dx.ewm(alpha=1.0 / ADX_LEN, adjust=False).mean()

    return df


# ---------------------------------------------------------------- checklist --

def checklist_score(df: pd.DataFrame) -> pd.Series:
    """Score determinístico pré-registrado (seção 13.5). Item NaN → 0."""
    a1 = (df["ema20"] > df["ema50"]).fillna(False).astype(int)
    a2 = (df["close"] > df["ema20"]).fillna(False).astype(int)
    a3 = (df["ema50"] > df["ema200"]).fillna(False).astype(int)

    b1 = (df["close"] > df["bb_mid"]).fillna(False).astype(int)
    b2 = (df["close"].rolling(PULLBACK_BARS).min() <= df["bb_mid"]).fillna(False).astype(int)
    b3 = ((df["close"] >= df["bb_upper"]) & (df["macd_hist_slope"] <= 0)).fillna(False).astype(int)

    c1 = (df["macd_hist"] > 0).fillna(False).astype(int)
    c2 = ((df["macd_hist"] > df["macd_hist"].shift(1)) &
          (df["macd_hist"].shift(1) > df["macd_hist"].shift(2))).fillna(False).astype(int)
    c3 = ((df["rsi14"] > 40) & (df["rsi14"] < 72)).fillna(False).astype(int)

    d1 = (df["atr14"] <= df["atr14"].rolling(ATR_Q_WINDOW).quantile(ATR_EXTREME_Q)).fillna(False).astype(int)
    d2 = (df["adx14"] >= ADX_TREND_MIN).fillna(False).astype(int)
    d3 = ((df["adx14"] <= ADX_CHOP_MAX) &
          (df["bb_width"] <= df["bb_width"].rolling(BBQ_Q_WINDOW).quantile(BB_WIDTH_CHOP_Q))).fillna(False).astype(int)

    score = a1 + a2 + a3 + b1 + b2 - b3 + c1 + c2 + c3 + d1 + d2 - d3
    return score.astype(float)


def setup_signal(df: pd.DataFrame) -> pd.Series:
    """Setup-base de pullback em tendência (seção 13.3)."""
    trend = (df["ema20"] > df["ema50"]) & (df["close"] > df["ema20"])
    pullback = df["close"].rolling(PULLBACK_BARS).min() <= df["bb_mid"]
    reclaim = (df["close"] > df["bb_mid"]) & (df["close"].shift(1) <= df["bb_mid"].shift(1))
    momentum = df["macd_hist"] > 0
    return (trend & pullback & reclaim & momentum).fillna(False)


def exit_signal(df: pd.DataFrame) -> pd.Series:
    """Saída (seção 13.4) — idêntica nos três modos."""
    mid_loss = df["close"] < df["bb_mid"]
    momentum_loss = df["macd_hist"] < 0
    exhaustion = (df["close"] >= df["bb_upper"]) & (df["macd_hist_slope"] <= 0)
    return (mid_loss | momentum_loss | exhaustion).fillna(False)


# ------------------------------------------------- simulation / metrics --

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


def trades_from_positions(df: pd.DataFrame, pos: pd.Series, score: pd.Series) -> list[Trade]:
    ret = df["close"].pct_change().fillna(0.0)
    segs = []
    in_trade = False
    for i in range(len(df)):
        p = bool(pos.iloc[i])
        if p and not in_trade:
            start = i
            in_trade = True
        elif not p and in_trade:
            segs.append((start, i - 1))
            in_trade = False
    if in_trade:
        segs.append((start, len(df) - 1))

    trades = []
    for start, end in segs:
        seg_ret = ret.iloc[start:end + 1]
        gross = float((1.0 + seg_ret).prod() - 1.0)
        net = gross - COST_ROUND_TRIP
        entry_ts = df.index[start]
        exit_ts = df.index[end]
        decision_score = float(score.iloc[start - 1]) if start > 0 else float("nan")
        trades.append(Trade(
            entry_ts=entry_ts,
            exit_ts=exit_ts,
            hold_bars=int(end - start + 1),
            score_decision=decision_score,
            gross_return=gross,
            net_return=net,
        ))
    return trades


def simulate_mode(df: pd.DataFrame, name: str) -> tuple[ModeResult, dict]:
    setup = setup_signal(df)
    exit_sig = exit_signal(df)
    score = checklist_score(df)

    if name == "BASE":
        def gate(i: int) -> bool:
            return True
    elif name == "CHECKLIST":
        def gate(i: int) -> bool:
            return bool(score.iloc[i] >= ENTER_SCORE)
    elif name == "VETO":
        def gate(i: int) -> bool:
            return bool(score.iloc[i] >= VETO_FLOOR)
    else:
        raise ValueError(name)

    pos = pd.Series(0.0, index=df.index)
    holding = False
    for i in range(1, len(df)):
        if not holding and bool(setup.iloc[i - 1]) and gate(i - 1):
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

    trades = trades_from_positions(df, pos, score)
    gross_values = np.array([t.gross_return for t in trades]) if trades else np.array([0.0])
    net_values = np.array([t.net_return for t in trades]) if trades else np.array([0.0])
    n_trades = len(trades)
    avg_trade_gross = float(gross_values.mean()) if n_trades else 0.0
    avg_trade_net = float(net_values.mean()) if n_trades else 0.0
    wins_gross = gross_values[gross_values > 0]
    losses_gross = gross_values[gross_values < 0]
    win_rate_gross = float(len(wins_gross) / n_trades) if n_trades else 0.0
    avg_win = float(wins_gross.mean()) if len(wins_gross) else 0.0
    avg_loss_abs = float(abs(losses_gross.mean())) if len(losses_gross) else 0.0
    payoff_gross = (avg_win / avg_loss_abs) if avg_loss_abs > 0 else (99.0 if avg_win > 0 else 0.0)
    avg_hold_bars = float(np.mean([t.hold_bars for t in trades])) if n_trades else 0.0

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

    result = ModeResult(
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
        n_trades=n_trades,
        avg_trade_gross=avg_trade_gross,
        avg_trade_net=avg_trade_net,
        win_rate_gross=win_rate_gross,
        payoff_gross=payoff_gross,
        avg_hold_bars=avg_hold_bars,
    )
    details = {
        "net_equity": net_equity,
        "gross_equity": gross_equity,
        "net_returns": net_ret,
        "gross_returns": gross_ret,
        "positions": pos,
        "trades": trades,
        "yearly_returns": yearly,
    }
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


def verdict_vs_base(variant: ModeResult, base: ModeResult) -> dict[str, bool]:
    process = (variant.avg_trade_gross > base.avg_trade_gross) and (variant.win_rate_gross > base.win_rate_gross)
    cost_ok = (variant.flips <= base.flips) and (variant.net_minus_gross_pp <= base.net_minus_gross_pp)
    at_least_one = (
        (variant.max_dd_pct <= base.max_dd_pct)
        or (variant.avg_trade_net > base.avg_trade_net)
        or (variant.payoff_gross > base.payoff_gross)
    )
    return {"process": process, "cost_ok": cost_ok, "at_least_one": at_least_one, "beats": process and cost_ok and at_least_one}


def print_yearly(name: str, yearly: pd.Series):
    print(f"   {name} por ano:")
    for year, value in yearly.items():
        print(f"      {year}: {value:+.2%}")


def main():
    print("🧪 Q23 — operador contextual (pullback em tendência + checklist) em BTC (15m)")
    print("   Modos: BASE sozinho | CHECKLIST (score>=6) | VETO (score>=3)")
    print("   Custo: 10bp round-trip por trade | saída idêntica nos 3 modos | sem lookahead\n")

    df = build_dataset()
    print(f"Dataset final: {len(df)} velas 15m spot | range {df.index[0]:%Y-%m-%d %H:%M} → {df.index[-1]:%Y-%m-%d %H:%M}")
    df_aug = add_features(df)

    # Processo: distribuição do score sobre todos os candidatos do setup-base
    setup = setup_signal(df_aug)
    score = checklist_score(df_aug)
    cand_mask = setup & ~setup.shift(1, fill_value=False)
    cand_scores = score[cand_mask]
    n_cand = int(cand_mask.sum())
    pct = lambda c: (float((cand_scores[c]).count()) / n_cand * 100.0) if n_cand else 0.0
    print(f"\n[Processo] candidatos do setup-base: {n_cand}")
    print(f"   score médio dos candidatos: {cand_scores.mean():.2f} (faixa {score.min():.0f}..{score.max():.0f})")
    print(f"   ENTER (score>=6): {pct(cand_scores >= ENTER_SCORE):.1f}%")
    print(f"   WAIT  (3..5):     {pct((cand_scores >= WAIT_MIN) & (cand_scores <= 5)):.1f}%")
    print(f"   VETO  (<=2):      {pct(cand_scores <= VETO_MAX):.1f}%")

    bh = benchmark_buy_hold(df_aug)
    print("\n[Benchmark] Buy & Hold")
    print(f"  CAGR {bh['cagr']:+.2%}  Vol {bh['vol_ann']:+.2%}  Sharpe {bh['sharpe']:+.2f}  Sortino {bh['sortino']:+.2f}")
    print(f"  Total {bh['total_return_pct']:+.2f}%  MaxDD {bh['max_dd_pct']:.2f}%  DD_dias {bh['max_dd_days']}")
    print_yearly("Buy & Hold", bh["yearly_returns"])

    results = {}
    all_details = {}
    for name in MODES:
        variant, details = simulate_mode(df_aug, name)
        results[name] = variant
        all_details[name] = details

        print(f"\n[{variant.name}]")
        print(f"  CAGR_net {variant.cagr_net:+.2%}  CAGR_gross {variant.cagr_gross:+.2%}  Vol {variant.vol_ann:+.2%}")
        print(f"  Sharpe {variant.sharpe:+.2f}  Sortino {variant.sortino:+.2f}  MaxDD {variant.max_dd_pct:.2f}%  DD_dias {variant.max_dd_days}")
        print(f"  Total {variant.total_return_pct:+.2f}%  tempo_em_mercado {variant.time_in_market_pct:.1f}%  flips {variant.flips}")
        print(f"  gross-net CAGR diff {variant.net_minus_gross_pp:.2f}pp  ano_max_share {variant.year_max_share_pct:.1f}%")
        print(f"  halves positivas {variant.half_passes}/2  cycles positivos {variant.cycle_passes}/3")
        print(f"  trades {variant.n_trades}  avg_trade_gross {variant.avg_trade_gross:+.4%}  avg_trade_net {variant.avg_trade_net:+.4%}")
        print(f"  win_rate_gross {variant.win_rate_gross:.1%}  payoff_gross {variant.payoff_gross:.2f}  avg_hold {variant.avg_hold_bars:.1f} barras")
        print_yearly(variant.name, details["yearly_returns"])

        # buckets de score dos trades (métricas de processo)
        dec = np.array([t.score_decision for t in details["trades"]], dtype=float)
        if len(dec):
            print(f"  trades por faixa de score-decisão: ENTER {int((dec >= ENTER_SCORE).sum())} | WAIT {int(((dec >= WAIT_MIN) & (dec <= 5)).sum())} | VETO {int((dec <= VETO_MAX).sum())} | outros {int(((dec < ENTER_SCORE) & (dec > 5)).sum())}")

    base = results["BASE"]
    print("\n[Sane de discriminação — dentro da BASE]")
    base_trades = all_details["BASE"]["trades"]
    dec = np.array([t.score_decision for t in base_trades], dtype=float)
    for label, mask in (("ENTER (score>=6)", dec >= ENTER_SCORE), ("VETO (score<=2)", dec <= VETO_MAX), ("WAIT (3..5)", (dec >= WAIT_MIN) & (dec <= 5))):
        sub = [t.gross_return for t, m in zip(base_trades, mask) if m]
        if sub:
            vals = np.array(sub)
            print(f"   {label}: n={len(vals):>5}  avg_trade_gross {vals.mean():+.4%}  win {float((vals>0).mean()):.1%}")

    verdicts = {}
    print("\n--- Veredito pré-registrado (vs BASE) ---")
    for name in ("CHECKLIST", "VETO"):
        v = verdict_vs_base(results[name], base)
        verdicts[name] = v
        flag = "✅ SUPERA BASE" if v["beats"] else "❌ NÃO SUPERA"
        print(f"  {name}: processo={v['process']} custo_nao_piora={v['cost_ok']} pelo_menos_um={v['at_least_one']} → {flag}")

    class_survives = verdicts["CHECKLIST"]["beats"] or verdicts["VETO"]["beats"]
    print(f">>> Q23 classe operador-contextual: {'✅ SOBREVIVE (candidata a validação posterior)' if class_survives else '❌ FALHA'}")


if __name__ == "__main__":
    main()