"""
Varredura de multiplicadores TP x SL (Edge Puro, sem trailing stop).

Para cada estratégia E cada combinação de (sl_mult, tp_mult),
simula a entrada com SL/TP fixos e taxa realista (0.1% por lado sobre o volume alavancado).
Objetivo: encontrar a relação risco:retorno que maximiza a expectativa (PnL) —
não a que tem o "win rate mais bonito".

Uso:
    venv/bin/python scripts/sweep_tp_sl.py [SYMBOL] [TIMEFRAME_SEC] [LIMIT]
"""
import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.engines.technical_analysis import (  # noqa: E402
    candles_to_df, apply_indicators,
    eval_rsi_ema_confluence, eval_consecutive, eval_ema_macd,
    eval_mean_reversion_exhaustion,
)
from scripts.backtester import download_history  # noqa: E402

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "BNB/USDT"
TF = int(sys.argv[2]) if len(sys.argv) > 2 else 300
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 5000

STAKE = 100.0
LEVERAGE = 10
FEE_RATE = 0.001  # 0.1% por lado, alavancado

STRATEGIES = {
    "Exaustão": eval_mean_reversion_exhaustion,
    "RSI+EMA": eval_rsi_ema_confluence,
    "3 Velas": eval_consecutive,
    "EMA+MACD": eval_ema_macd,
}

SL_MULTS = [0.75, 1.0, 1.25, 1.5, 2.0]
TP_MULTS = [1.0, 1.5, 2.0, 2.5, 3.0]

def simulate(df, strategy_func, sl_mult, tp_mult):
    """Retorna (signals, wins, losses, pnl). Edge puro, sem trailing."""
    signals = wins = losses = 0
    pnl = 0.0

    for i in range(50, len(df) - 1):
        sub_df = df.iloc[:i + 1]
        signal = strategy_func(sub_df)
        if signal != "NONE":
            signals += 1
            entry = df.iloc[i]["close"]
            atr = df.iloc[i].get("ATRr_14", entry * 0.005)
            if atr <= 0:
                continue
            sl = entry - (atr * sl_mult) if signal == "CALL" else entry + (atr * sl_mult)
            tp = entry + (atr * tp_mult) if signal == "CALL" else entry - (atr * tp_mult)

            closed = None
            exit_price = None
            for j in range(i + 1, len(df)):
                hi = df["high"].iloc[j]
                lo = df["low"].iloc[j]
                if (signal == "CALL" and lo <= sl) or (signal == "PUT" and hi >= sl):
                    closed = "LOSS"
                    exit_price = sl
                    break
                if (signal == "CALL" and hi >= tp) or (signal == "PUT" and lo <= tp):
                    closed = "WIN"
                    exit_price = tp
                    break
                dur = int(df.index[j].timestamp()) - int(df.index[i].timestamp())
                if dur >= 240 * 60:  # time stop 4h
                    closed = "TIME"
                    exit_price = df["close"].iloc[j]
                    break

            if not closed:
                continue

            pos_usd = STAKE * LEVERAGE
            fee = pos_usd * FEE_RATE
            if signal == "CALL":
                profit = pos_usd * ((exit_price - entry) / entry)
            else:
                profit = pos_usd * ((entry - exit_price) / entry)
            profit -= fee * 2  # abrir + fechar
            pnl += profit

            if closed == "WIN":
                wins += 1
            elif closed == "LOSS":
                losses += 1
            else:
                if profit > 0:
                    wins += 1
                else:
                    losses += 1

    total = wins + losses
    wr = (wins / total * 100) if total else 0.0
    return signals, wins, losses, wr, pnl

async def main():
    print(f"🔄 Baixando {LIMIT} velas de {SYMBOL} (M{TF//60})...")
    history = await download_history(SYMBOL, TF, LIMIT)
    if not history:
        print("Erro ao baixar histórico.")
        return

    df = candles_to_df(history)
    df = apply_indicators(df)
    print(f"✅ {len(df)} velas prontas. Rodando varredura TP x SL...\n")

    for name, func in STRATEGIES.items():
        print(f"\n{'=' * 68}")
        print(f"📊 {name}")
        print(f"{'=' * 68}")
        rows = []
        for sl_mult in SL_MULTS:
            for tp_mult in TP_MULTS:
                signals, wins, losses, wr, pnl = simulate(df, func, sl_mult, tp_mult)
                if signals < 5:
                    continue
                rows.append((pnl, signals, wins, losses, wr, sl_mult, tp_mult))

        rows.sort(key=lambda r: r[0], reverse=True)
        print(f"{'SL':>5} {'TP':>5} {'Trades':>6} {'WR%':>6} {'PnL$':>10}")
        for pnl, signals, wins, losses, wr, sl_mult, tp_mult in rows[:10]:
            print(f"{sl_mult:>5.2f} {tp_mult:>5.2f} {signals:>6} {wr:>6.1f} {pnl:>10.2f}")

    # O que precisaríamos ganhar para bater as taxas (payout 95% no modo binário):
    print("\n" + "-" * 68)
    print("Referência: no modo binário com payout 95% e stake fixo, o break-even")
    print("de WR fica em ~51.3% (sem contar taxas) ou ~53% com taxas.")
    print("No modo futuros com RR 1:2 (SL 1.5 / TP 3.0), o break-even de WR é 33.3%.")
    print("A varredura acima mostra que WR alto ≠ PnL alto — a relação TP/SL manda.")

asyncio.run(main())