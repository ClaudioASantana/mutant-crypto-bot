"""
Backtest do AIFilter (Decisor Primário).

Simula a entrada de trades baseada nas decisões da IA (BUY/SELL)
com Stop Loss e Take Profit baseados em múltiplos de ATR,
seguindo a estrutura de custos realista do simulador (0.1% de taxa por lado).

Como cada decisão só depende do contexto ATÉ a vela i, todas as chamadas à IA
são disparadas em paralelo (asyncio.gather, com semáforo para não sobrecarregar
o servidor) e a simulação de SL/TP é reproduzida depois, puramente offline.

Uso:
    venv/bin/python scripts/backtest_ai.py [SYMBOL] [TF] [LIMIT] [CONCURRENCY]
"""
import asyncio
import sys
import os
import json
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Carrega MANIFEST_API_KEY / BASE_URL do backend/.env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.engines.technical_analysis import candles_to_df, apply_indicators
from app.engines.ai_filter import AIFilter
from scripts.backtester import download_history

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"
TF = int(sys.argv[2]) if len(sys.argv) > 2 else 900  # M15
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
CONCURRENCY = int(sys.argv[4]) if len(sys.argv) > 4 else 10
START_IDX = 30  # contexto mínimo (20 velas) + folga

STAKE = 50.0
LEVERAGE = 10
FEE_RATE = 0.001  # 0.1% por lado (abrir+fechar = 0.2%)
CONFIDENCE_THRESHOLD = 0.7
SL_MULT = 1.5
TP_MULT = 3.0


def cache_path() -> str:
    safe = SYMBOL.replace("/", "").replace("USDT", "").upper()
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", f"ai_decisions_{safe}_{TF}.json")


def load_cache() -> dict:
    path = cache_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Cache corrompido ({e}), recriando...", flush=True)
    return {}


def save_cache(cache: dict):
    path = cache_path()
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


async def collect_decisions(ai: AIFilter, df, start: int, end: int, strategy: str, concurrency: int):
    """Dispara make_decision para cada vela, com concorrência limitada e cache em disco."""
    cache = load_cache()
    sem = asyncio.Semaphore(concurrency)
    pending = []

    for i in range(start, end):
        epoch = int(df.index[i].timestamp()) if hasattr(df.index[i], "timestamp") else int(df.index[i])
        key = str(epoch)
        if key in cache:
            continue  # já decidido numa execução anterior — reutiliza
        pending.append((i, key))

    print(f"⚡ {len(pending)} novas decisões para coletar ({len(cache)} em cache)...", flush=True)

    async def one(i: int, key: str):
        async with sem:
            decision = await ai.make_decision(df.iloc[: i + 1], strategy)
            cache[key] = decision
            return i, decision

    tasks = [one(i, key) for i, key in pending]
    results = []
    for task in asyncio.as_completed(tasks):
        i, decision = await task
        results.append((i, decision))
        if len(results) % 25 == 0:
            save_cache(cache)
    save_cache(cache)

    # União: decisões cacheadas (sem chamada à API) + novas
    all_results = []
    for i in range(start, end):
        epoch = int(df.index[i].timestamp()) if hasattr(df.index[i], "timestamp") else int(df.index[i])
        all_results.append((i, cache[str(epoch)]))
    return all_results


def simulate(df, decisions, threshold: float = CONFIDENCE_THRESHOLD) -> dict:
    """Reproduz trades para as decisões BUY/SELL acima do limiar (puramente offline)."""
    wins = losses = signals = 0
    pnl = 0.0
    trades_log = []

    for i, decision in decisions:
        d = decision["decision"]
        conf = decision["confidence"]
        if d not in ("BUY", "SELL") or conf < threshold:
            continue

        signals += 1
        entry = df["close"].iloc[i]
        atr = float(df["ATRr_14"].iloc[i]) if "ATRr_14" in df.columns and not pd_na(df["ATRr_14"].iloc[i]) else entry * 0.005
        if atr <= 0:
            atr = entry * 0.005

        direction = "CALL" if d == "BUY" else "PUT"
        sl = entry - (atr * SL_MULT) if direction == "CALL" else entry + (atr * SL_MULT)
        tp = entry + (atr * TP_MULT) if direction == "CALL" else entry - (atr * TP_MULT)

        # Procura pelo primeiro toque de SL/TP; se nenhum, fecha no último preço.
        result = None
        exit_price = None
        j_exit = None
        for j in range(i + 1, len(df)):
            high = df["high"].iloc[j]
            low = df["low"].iloc[j]
            if (direction == "CALL" and low <= sl) or (direction == "PUT" and high >= sl):
                result, exit_price, j_exit = "LOSS", sl, j
                break
            if (direction == "CALL" and high >= tp) or (direction == "PUT" and low <= tp):
                result, exit_price, j_exit = "WIN", tp, j
                break

        if result is None and i + 1 < len(df):
            result = "TIME"
            exit_price = df["close"].iloc[-1]
            j_exit = len(df) - 1

        pos_usd = STAKE * LEVERAGE
        fee = pos_usd * FEE_RATE * 2

        if direction == "CALL":
            profit = pos_usd * ((exit_price - entry) / entry)
        else:
            profit = pos_usd * ((entry - exit_price) / entry)

        final_pnl = profit - fee
        pnl += final_pnl

        if result == "WIN":
            wins += 1
        elif result == "LOSS":
            losses += 1
        else:
            if final_pnl > 0:
                wins += 1
            else:
                losses += 1

        trades_log.append(f"{result:>4} | {d:<4} @ {entry:9.2f} -> {exit_price:9.2f} | PnL: {final_pnl:+8.2f} | Conf: {conf:.2f}")

    total = wins + losses
    return {
        "signals": signals,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / total * 100) if total else 0.0,
        "pnl": pnl,
        "trades": trades_log,
    }


def pd_na(v) -> bool:
    """pd.isna que não quebra se v for numpy float nan já convertido."""
    try:
        return bool(v != v)
    except Exception:
        import pandas as pd
        return bool(pd.isna(v))


async def main():
    ai = AIFilter()
    if not ai.client:
        print("❌ AI Filter não configurado (API Key ausente).")
        return

    print(f"🔄 Baixando {LIMIT} velas de {SYMBOL} (M{TF // 60})...", flush=True)
    history = await download_history(SYMBOL, TF, LIMIT)
    if not history or len(history) < START_IDX + 2:
        print("Erro: Histórico insuficiente.")
        return

    df = candles_to_df(history)
    df = apply_indicators(df)

    print(f"🚀 Coletando decisões da IA ({len(df) - START_IDX - 1} velas, {CONCURRENCY} paralelas)...", flush=True)
    decisions = await collect_decisions(ai, df, START_IDX, len(df) - 1, "Backtest-IA", CONCURRENCY)

    print(f"📊 Reproduzindo simulações de trades para SL {SL_MULT} / TP {TP_MULT}", flush=True)

    for t in [0.70, 0.75, 0.80, 0.85, 0.90]:
        report = simulate(df, decisions, threshold=t)
        print(f"Conf >= {t:.2f} | Sinais: {report['signals']:>3} | "
              f"Wins: {report['wins']:>3} | Losses: {report['losses']:>3} | "
              f"WR: {report['win_rate']:>6.2f}% | PnL: ${report['pnl']:>9.2f}", flush=True)

    print("\n" + "-" * 72)
    print(f"📈 RESUMO | {SYMBOL} M{TF // 60} ({len(df)} velas) — conf >= 0.70")
    report = simulate(df, decisions, threshold=0.70)
    for t in report["trades"]:
        print(t)


if __name__ == "__main__":
    asyncio.run(main())