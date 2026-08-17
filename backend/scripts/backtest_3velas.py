"""
Backtest comparativo: Estratégia "3 Velas" (padrões de 3 candles da wiki)
vs. as demais estratégias do bot, usando histórico local persistido.

Uso:
    ./backend/venv/bin/python backend/scripts/backtest_3velas.py [SIMBOLO] [LIMITE]

Exemplo:
    ./backend/venv/bin/python backend/scripts/backtest_3velas.py BTC/USDT 3000
"""
import os
import sys
import sqlite3
import time

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.models.market import Candle, CandleDirection
from app.engines.cataloger import calculate_win_rate
from app.engines.technical_analysis import candles_to_df, apply_indicators

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "market_history.db")

STRATEGIES = ["EMA+MACD", "Bollinger", "VWAP", "SMC", "SuperTrend", "Pin Bar", "ABCD", "3 Velas"]


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
        if close_p == open_p:
            direction = CandleDirection.NEUTRAL
        candles.append(Candle(
            epoch=epoch, open=open_p, high=high_p, low=low_p,
            close=close_p, volume=volume, direction=direction,
        ))
    return candles


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3000

    candles = load_candles(symbol, 300, limit)
    if not candles:
        print(f"❌ Nenhum dado encontrado para {symbol} em {DB_PATH}")
        return

    print(f"📊 Backtest em {symbol} (M5) — {len(candles)} velas")
    print("-" * 70)

    # Pré-computa o df com indicadores uma única vez
    df = candles_to_df(candles)
    df = apply_indicators(df)

    results = []
    for s in STRATEGIES:
        t0 = time.time()
        res = calculate_win_rate(candles, s)
        elapsed = time.time() - t0
        results.append((s, res, elapsed))
        print(
            f"  {s:<12} sinais={res['signals']:>4}  wins={res['wins']:>4}  "
            f"losses={res['losses']:>4}  WR={res['win_rate']:>6.2f}%  "
            f"PnL=${res['pnl_usdt']:>10.2f}  ({elapsed:.1f}s)"
        )

    print("-" * 70)
    print("\n🏆 Ranking por PnL:")
    for s, res, elapsed in sorted(results, key=lambda x: x[1]["pnl_usdt"], reverse=True):
        print(f"  {s:<12} PnL=${res['pnl_usdt']:>10.2f}  WR={res['win_rate']:.2f}%")


if __name__ == "__main__":
    main()