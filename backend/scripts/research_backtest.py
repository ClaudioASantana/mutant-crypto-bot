"""
Harness de avaliação de estratégias (research-grade).

Regras honestas:
- Entrada no fechamento do candle de sinal.
- Taxas Binance Futures: 0.04% taker em cada lado (entrada + saída) sobre o nocional.
- SL/TP por ATR ou customizado pela estratégia; trailing opcional; time-stop opcional.
- Métricas: trades, win rate, PnL total, profit factor, expectância (R), max drawdown.
"""
import os
import sys
import sqlite3
from dataclasses import dataclass, field
from typing import Callable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from app.models.market import Candle, CandleDirection
from app.engines.technical_analysis import candles_to_df, apply_indicators

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "market_history.db")

FEE_RATE = 0.0004   # 0.04% taker por lado (Binance Futures VIP0)
STAKE = 100.0       # margem em USDT
LEVERAGE = 10.0


@dataclass
class TradeResult:
    idx: int
    direction: str
    entry: float
    exit: float
    pnl: float
    status: str  # TP / SL / TRAIL / TIME
    r_multiple: float


@dataclass
class StrategyResult:
    name: str
    trades: list = field(default_factory=list)

    @property
    def n_trades(self):
        return len(self.trades)

    @property
    def wins(self):
        return sum(1 for t in self.trades if t.pnl > 0)

    @property
    def losses(self):
        return sum(1 for t in self.trades if t.pnl <= 0)

    @property
    def win_rate(self):
        return (self.wins / self.n_trades * 100) if self.n_trades else 0.0

    @property
    def total_pnl(self):
        return sum(t.pnl for t in self.trades)

    @property
    def profit_factor(self):
        gross_win = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = -sum(t.pnl for t in self.trades if t.pnl < 0)
        return (gross_win / gross_loss) if gross_loss > 0 else float("inf")

    @property
    def avg_r(self):
        return np.mean([t.r_multiple for t in self.trades]) if self.trades else 0.0

    @property
    def max_drawdown(self):
        eq = 0.0
        peak = 0.0
        mdd = 0.0
        for t in self.trades:
            eq += t.pnl
            peak = max(peak, eq)
            mdd = min(mdd, eq - peak)
        return mdd

    @property
    def expectancy_per_trade(self):
        return (self.total_pnl / self.n_trades) if self.n_trades else 0.0


def load_candles(symbol: str, timeframe: int, limit: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT epoch, open, high, low, close, volume FROM candles "
        "WHERE symbol=? AND timeframe=? ORDER BY epoch DESC LIMIT ?",
        (symbol, timeframe, limit),
    )
    rows = cur.fetchall()
    conn.close()
    candles = []
    for epoch, open_p, high_p, low_p, close_p, volume in reversed(rows):
        direction = CandleDirection.BULLISH if close_p > open_p else CandleDirection.BEARISH
        candles.append(Candle(
            epoch=epoch, open=open_p, high=high_p, low=low_p,
            close=close_p, volume=volume, direction=direction,
        ))
    return candles


class Backtest:
    """Executa uma estratégia de sinais sobre velas com gestão de risco parametrizada."""

    def __init__(self, candles, fee_rate=FEE_RATE, stake=STAKE, leverage=LEVERAGE,
                 sl_mult=1.5, tp_mult=3.0, use_trailing=False,
                 trail_activation=1.0, trail_distance=0.5,
                 time_stop_minutes=240):
        self.candles = candles
        self.fee_rate = fee_rate
        self.stake = stake
        self.leverage = leverage
        self.sl_mult = sl_mult
        self.tp_mult = tp_mult
        self.use_trailing = use_trailing
        self.trail_activation = trail_activation
        self.trail_distance = trail_distance
        self.time_stop_seconds = time_stop_minutes * 60
        self.df = candles_to_df(candles)
        self.df = apply_indicators(self.df)
        self.warmup = 50

    def _notional(self):
        return self.stake * self.leverage

    def _fees(self, n_sides=2):
        return self._notional() * self.fee_rate * n_sides

    def run(self, signal_fn: Callable, name: str, min_index: int = None,
            one_position: bool = True) -> StrategyResult:
        res = StrategyResult(name=name)
        df = self.df
        start = max(self.warmup, min_index or self.warmup)
        open_until = -1  # índice do último candle usado pela posição em aberto
        for i in range(start, len(df) - 1):
            if one_position and i < open_until:
                continue
            signal = signal_fn(df.iloc[: i + 1])
            if signal == "NONE":
                continue
            entry = df.iloc[i]["close"]

            # SL/TP base
            atr = df.iloc[i].get("ATRr_14", entry * 0.005)
            if signal == "CALL":
                sl = entry - atr * self.sl_mult
                tp = entry + atr * self.tp_mult
            else:
                sl = entry + atr * self.sl_mult
                tp = entry - atr * self.tp_mult
            initial_sl = sl  # SL original, usado no cálculo de R

            hi = lo = entry
            exit_price = None
            status = None
            entry_ts = int(df.index[i].timestamp())

            for j in range(i + 1, len(df)):
                ch = df.iloc[j]["high"]
                cl = df.iloc[j]["low"]
                cc = df.iloc[j]["close"]
                ts = int(df.index[j].timestamp())

                if (ts - entry_ts) >= self.time_stop_seconds:
                    exit_price, status = cc, "TIME"
                    open_until = j
                    break

                if signal == "CALL":
                    hi = max(hi, ch)
                    if self.use_trailing and hi >= entry + atr * self.trail_activation:
                        new_sl = hi - atr * self.trail_distance
                        if new_sl > sl:
                            sl = new_sl
                    if cl <= sl:
                        exit_price, status = sl, ("TRAIL" if sl >= entry else "SL")
                        open_until = j
                        break
                    if ch >= tp:
                        exit_price, status = tp, "TP"
                        open_until = j
                        break
                else:
                    lo = min(lo, cl)
                    if self.use_trailing and lo <= entry - atr * self.trail_activation:
                        new_sl = lo + atr * self.trail_distance
                        if new_sl < sl:
                            sl = new_sl
                    if ch >= sl:
                        exit_price, status = sl, ("TRAIL" if sl <= entry else "SL")
                        open_until = j
                        break
                    if cl <= tp:
                        exit_price, status = tp, "TP"
                        open_until = j
                        break

            if exit_price is None:
                continue

            raw_pnl = (exit_price - entry) if signal == "CALL" else (entry - exit_price)
            pnl = raw_pnl * self._notional() / entry - self._fees()
            risk_per_unit = abs(entry - initial_sl)
            r = raw_pnl / risk_per_unit if risk_per_unit > 0 else 0.0
            res.trades.append(TradeResult(i, signal, entry, exit_price, pnl, status, r))

        return res


def print_result(r: StrategyResult):
    extra = ""
    if r.n_trades:
        extra = (f"  PF={r.profit_factor:.2f}  avgR={r.avg_r:+.2f}  "
                 f"exp/trade=${r.expectancy_per_trade:+.2f}  MDD=${r.max_drawdown:.2f}")
    print(f"{r.name:<42} n={r.n_trades:>4}  WR={r.win_rate:>6.2f}%  "
          f"PnL=${r.total_pnl:>10.2f}{extra}")


# ─── Estratégias candidatas (sinais) ─────────────────────────────────────────

def sig_donchian_breakout(df, n=20):
    """DONCHIAN/TRTLE: rompeu a máxima (CALL) ou mínima (PUT) dos últimos n candles."""
    if len(df) < n + 2:
        return "NONE"

    # last é a vela de sinal.
    last = df.iloc[-1]
    # A janela para procurar max/min é de n velas *antes* da vela de sinal.
    # Exemplo: df.iloc[-21:-1] para n=20
    window = df.iloc[-(n + 1) : -1]

    if not window.empty:
        upper = window["high"].max()
        lower = window["low"].min()

        if last["close"] > last["open"] and last["close"] > upper:
            return "CALL"
        if last["close"] < last["open"] and last["close"] < lower:
            return "PUT"
    return "NONE"


def make_donchian(n=20):
    def fn(df):
        return sig_donchian_breakout(df, n)
    return fn


def sig_ema_breakout(df, fast=9, slow=21):
    if len(df) < slow + 2:
        return "NONE"
    ema_f = df["close"].ewm(span=fast, adjust=False).mean()
    ema_s = df["close"].ewm(span=slow, adjust=False).mean()
    if df['close'].iloc[-1] > ema_f.iloc[-1] > ema_s.iloc[-1] and ema_f.iloc[-2] <= ema_s.iloc[-2]:
        return "CALL"
    if df['close'].iloc[-1] < ema_f.iloc[-1] < ema_s.iloc[-1] and ema_f.iloc[-2] >= ema_s.iloc[-2]:
        return "PUT"
    return "NONE"


def sig_ema_trend_with_slope(df, ema_len=50):
    """EMA slope: só compra quando EMA50 sobe e preço acima; vende quando desce."""
    if len(df) < ema_len + 3:
        return "NONE"
    ema = df["close"].ewm(span=ema_len, adjust=False).mean()
    if df["close"].iloc[-1] > ema.iloc[-1] and ema.iloc[-1] > ema.iloc[-2]:
        return "CALL"
    if df["close"].iloc[-1] < ema.iloc[-1] and ema.iloc[-1] < ema.iloc[-2]:
        return "PUT"
    return "NONE"


def sig_rsi2_reversion(df):
    """RSI(2) mean reversion: compra abaixo de 10, vende acima de 90."""
    if len(df) < 15:
        return "NONE"
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    last = rsi.iloc[-1]
    if last < 10:
        return "CALL"
    if last > 90:
        return "PUT"
    return "NONE"


def sig_bollinger_reversion(df):
    """BB reversion: preço toca banda inferior e fecha acima → CALL; toca superior e fecha abaixo → PUT."""
    if len(df) < 25:
        return "NONE"
    last, prev = df.iloc[-1], df.iloc[-2]
    bb_u = last.get("BBU_20_2.0_2.0", np.nan)
    bb_l = last.get("BBL_20_2.0_2.0", np.nan)
    if pd.isna(bb_l) or pd.isna(bb_u):
        return "NONE"
    if prev["close"] < bb_l and last["close"] > bb_l:
        return "CALL"
    if prev["close"] > bb_u and last["close"] < bb_u:
        return "PUT"
    return "NONE"


def sig_abberation(df):
    """Stoller: rompimento da banda de Keltner (prox de 3xATR)."""
    if len(df) < 30:
        return "NONE"
    last, prev = df.iloc[-1], df.iloc[-2]
    atr = df["ATRr_14"].iloc[-1] if "ATRr_14" in df.columns else 0.01
    ma = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
    upper = ma + 2.0 * atr
    lower = ma - 2.0 * atr
    if prev["close"] < lower and last["close"] > lower:
        return "CALL"
    if prev["close"] > upper and last["close"] < upper:
        return "PUT"
    return "NONE"


def sig_pivot_reversion(df, lb=10):
    """
    Reversão em pivô: fractal de lb velas re-testado com retorno.
    Pivô baixo = mínima de um bloco de ±lb velas. Sinal CALL quando a última
    vela re-testa esse pivô e fecha de volta acima (engolfo de retomada).
    """
    n = len(df)
    if n < lb * 2 + 3:
        return "NONE"
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Pivôs baixos recentes: candidatos nas posições n-3 ... n-lb-2
    for k in range(3, lb + 3):
        p = n - k
        if p - lb < 0 or p + lb >= n:
            continue
        seg = df.iloc[p - lb : p + lb + 1]
        if seg["low"].iloc[lb] != seg["low"].min():
            continue
        pivot_low = seg["low"].iloc[lb]
        # tocou o pivô (ou furou) e fechou acima dele → rejeição
        if last["low"] <= pivot_low and last["close"] > pivot_low:
            if last["close"] > prev["close"]:
                return "CALL"

    # Pivôs altos recentes
    for k in range(3, lb + 3):
        p = n - k
        if p - lb < 0 or p + lb >= n:
            continue
        seg = df.iloc[p - lb : p + lb + 1]
        if seg["high"].iloc[lb] != seg["high"].max():
            continue
        pivot_high = seg["high"].iloc[lb]
        if last["high"] >= pivot_high and last["close"] < pivot_high:
            if last["close"] < prev["close"]:
                return "PUT"

    return "NONE"


# ─── Estratégias da pesquisa (alta probabilidade) ────────────────────────────

def sig_donchian_ema200(df, n=20):
    """
    Donchian Breakout com filtro de tendência macro (EMA 200).
    Só opera rompimento na direção da EMA 200.
    """
    if len(df) < 205:
        return "NONE"

    last = df.iloc[-1]
    prev = df.iloc[-2]
    # Usa a janela anterior para o rompimento
    window = df.iloc[-(n + 1) : -1]

    dcu = window["high"].max()
    dcl = window["low"].min()

    ema200 = df["EMA_200"].iloc[-2]

    if pd.isna(ema200) or pd.isna(dcu) or pd.isna(dcl):
        return "NONE"

    # Filtro de tendência: preço acima/abaixo da EMA200
    if prev["close"] > ema200 and last["close"] > dcu:
        return "CALL"
    if prev["close"] < ema200 and last["close"] < dcl:
        return "PUT"
    return "NONE"


def sig_bollinger_reversion_regime(df, bandwidth_pct=30.0):
    """
    Bollinger Mean Reversion correto, com gate de regime.
    - Só opera quando o mercado está lateral: largura das bandas (bandwidth) no percentil baixo.
    - CALL: preço toca/rompe a banda inferior e fecha de volta acima → rejeição.
    - PUT:  preço toca/rompe a banda superior e fecha de volta abaixo → rejeição.
    """
    if len(df) < 100:
        return "NONE"
    last = df.iloc[-1]
    prev = df.iloc[-2]

    bb_mid = last.get("BBM_20_2.0_2.0", np.nan)
    bb_up = last.get("BBU_20_2.0_2.0", np.nan)
    bb_low = last.get("BBL_20_2.0_2.0", np.nan)
    if pd.isna(bb_mid) or pd.isna(bb_up) or pd.isna(bb_low):
        return "NONE"

    # Filtro de regime: bandwidth histórico (últimas 100 velas)
    hist_mid = df.get("BBM_20_2.0_2.0", pd.Series(dtype=float)).iloc[-100:]
    hist_up = df.get("BBU_20_2.0_2.0", pd.Series(dtype=float)).iloc[-100:]
    hist_low = df.get("BBL_20_2.0_2.0", pd.Series(dtype=float)).iloc[-100:]
    hist_bw = (hist_up - hist_low) / hist_mid.replace(0, np.nan)
    hist_bw.dropna(inplace=True)

    if len(hist_bw) < 30:
        return "NONE"

    current_bw = (bb_up - bb_low) / bb_mid if bb_mid else 0
    percentile = np.percentile(hist_bw, bandwidth_pct)

    # Só opera se bandwidth ≤ percentil baixo (mercado lateral)
    if current_bw > percentile:
        return "NONE"

    if prev["close"] < bb_low and last["close"] > bb_low:
        return "CALL"
    if prev["close"] > bb_up and last["close"] < bb_up:
        return "PUT"
    return "NONE"


def sig_trend_pullback(df):
    """
    Trend-Pullback Confluence ("Estratégia de Ouro"):
    - Macro: preço acima da EMA 200 (OU abaixo) → tendência.
    - Momentum: EMA 9 > EMA 21 (ou inversa) → direção.
    - Pullback: a mínima (CALL) toca/fura a EMA 20 ou VWAP e o candle fecha acima → retomada.
    - RSExaustão: RS[40,55] para CALL, RS[45,60] para PUT (não sobrecomprado/sobrevendido).
    """
    if len(df) < 205:
        return "NONE"

    last = df.iloc[-1]  # vela de sinal
    prev = df.iloc[-2] # vela anterior

    ema200 = df["EMA_200"].iloc[-1]
    ema9 = df["EMA_9"].iloc[-1]
    ema21 = df["EMA_21"].iloc[-1]
    rsi = df["RSI_14"].iloc[-1]
    ema20 = df["EMA_20"].iloc[-1]

    # VWAP might not be present, default to EMA20 as fallback
    vwap_col = [c for c in df.columns if "VWAP" in c]
    vwap = df[vwap_col[0]].iloc[-1] if vwap_col and vwap_col[0] in df.columns else ema20

    if any(pd.isna(v) for v in [ema200, ema9, ema21, rsi, ema20, vwap]):
        return "NONE"

    # CALL
    is_uptrend = last["close"] > ema200 and ema9 > ema21
    pullback_buy = last["low"] <= ema20 or last["low"] <= vwap
    rsi_ok_buy = 40 <= rsi <= 55
    reversal_candle_buy = last["close"] > prev["low"] and last["close"] > last["open"]

    if is_uptrend and pullback_buy and rsi_ok_buy and reversal_candle_buy:
        return "CALL"

    # PUT
    is_downtrend = last["close"] < ema200 and ema9 < ema21
    pullback_sell = last["high"] >= ema20 or last["high"] >= vwap
    rsi_ok_sell = 45 <= rsi <= 60
    reversal_candle_sell = last["close"] < prev["high"] and last["close"] < last["open"]

    if is_downtrend and pullback_sell and rsi_ok_sell and reversal_candle_sell:
        return "PUT"

    return "NONE"


if __name__ == "__main__":
    use_trailing = "--no-trailing" not in sys.argv
    symbol = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "BTC/USDT"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 10000
    candles = load_candles(symbol, 300, limit)
    mode = "TRAILING" if use_trailing else "SL/TP puro (1:2)"
    print(f"Backtest honesto em {symbol} M5 — {len(candles)} velas (taxa {FEE_RATE*100:.2f}%/lado) — modo {mode}")
    print("-" * 110)

    strategies = [
        ("Donchian 20", make_donchian(20)),
        ("Donchian 55 (Turtle D1)", make_donchian(55)),
        ("Donchian+EMA200", sig_donchian_ema200),
        ("EMA 9/21 cross", sig_ema_breakout),
        ("EMA 50 slope", sig_ema_trend_with_slope),
        ("RSI-2 mean reversion", sig_rsi2_reversion),
        ("Bollinger reversion", sig_bollinger_reversion),
        ("BB reversion+regime (30pct)", lambda df: sig_bollinger_reversion_regime(df, bandwidth_pct=30.0)),
        ("Trend-Pullback Confluence", sig_trend_pullback),
        ("Abberation Keltner", sig_abberation),
    ]

    bt = Backtest(candles, use_trailing=use_trailing, sl_mult=1.5, tp_mult=3.0)
    results = []
    for name, fn in strategies:
        r = bt.run(fn, name)
        results.append(r)
        print_result(r)

    print("-" * 110)
    print("\nRanking por PnL Final:")
    for r in sorted(results, key=lambda x: x.total_pnl, reverse=True):
        print(f"  {r.name:<42} PnL=${r.total_pnl:>10.2f}  WR={r.win_rate:.2f}%  PF={r.profit_factor:.2f}  Trades={r.n_trades}")
