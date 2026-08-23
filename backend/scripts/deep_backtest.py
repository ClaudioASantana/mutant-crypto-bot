#!/usr/bin/env python3
"""
🧬 Deep Backtest - Mutant Crypto Bot
=====================================
Baixa 30 dias de dados históricos da Binance e executa o backtest
completo das 4 estratégias (EMA+MACD, Bollinger, VWAP, SMC)
para os 3 timeframes (M1, M5, M15).

Uso: python scripts/deep_backtest.py
"""

import sys
import os
import time
import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timezone, timedelta

# Adicionar o backend ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.application.services.backtest_metrics import (
    TradingCostConfig,
    calculate_backtest_metrics,
)
from app.application.services.technical_analysis import (
    apply_indicators, eval_ema_macd, eval_bollinger, eval_vwap, eval_vwap_zscore, eval_smc,
    check_rsi_filter, check_volume_filter, check_trend_filter, check_mtf_alignment,
    eval_wyckoff_bollinger, eval_wyckoff_smc
)

STRATEGIES = {
    "EMA+MACD": eval_ema_macd,
    "Bollinger": eval_bollinger,
    "VWAP":     eval_vwap,
    "VWAP Z-Score": eval_vwap_zscore,
    "SMC":      eval_smc,
    "Wyckoff_Bbands": eval_wyckoff_bollinger,
    "Wyckoff_SMC":    eval_wyckoff_smc,
}

TIMEFRAMES = {
    "M1":  ("1m",  60),
    "M5":  ("5m",  300),
    "M15": ("15m", 900),
}

SYMBOL = "BTCUSDT"
DAYS   = 30

# Risk management constants (Risco 1:2)
TP_MULTIPLIER = 3.0
SL_MULTIPLIER = 1.5
STAKE_USD     = 100.0
LEVERAGE      = 10
FEE_RATE      = 0.0004  # 0.04% por ponta (Binance Futures taker)
SLIPPAGE_BPS  = 1.0     # slippage por ponta, em basis points

# ─────────────────────────────────────────────────────────────────────────────
# Data Download
# ─────────────────────────────────────────────────────────────────────────────

def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Baixa os dados históricos paginando até cobrir `days` dias."""
    end_ms   = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    url      = "https://api.binance.com/api/v3/klines"

    all_rows = []
    current  = start_ms

    print(f"\n⏬  Baixando {interval} | {symbol} | últimos {days} dias...")
    while current < end_ms:
        params = {
            "symbol":    symbol,
            "interval":  interval,
            "startTime": current,
            "endTime":   end_ms,
            "limit":     1000,
        }
        resp = requests.get(url, params=params, timeout=15)
        rows = resp.json()
        if not rows:
            break
        all_rows.extend(rows)
        current = rows[-1][6] + 1          # close_time of the last candle + 1ms
        print(f"   {len(all_rows):>6} velas carregadas...", end="\r")
        time.sleep(0.12)                   # Respeitar rate-limit da Binance

    print(f"   {len(all_rows)} velas totais baixadas.          ")

    df = pd.DataFrame(all_rows, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_volume","trades","taker_buy_vol",
        "taker_buy_quote_vol","ignore"
    ])
    df = df[["open_time","open","high","low","close","volume"]].copy()
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    df.set_index("open_time", inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Backtest Engine
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, strategy_name: str) -> dict:
    """Executa o backtest de 1 estrategia sobre o DataFrame de 30 dias."""
    strategy_func = STRATEGIES[strategy_name]

    # Aplicar indicadores no DataFrame completo de uma vez (mais rapido)
    df_ind = apply_indicators(df.copy())

    signals_generated = 0
    trades = []
    notional = STAKE_USD * LEVERAGE

    start_idx = 50  # Aguardar indicadores estabilizarem

    for i in range(start_idx, len(df_ind) - 1):
        sub = df_ind.iloc[:i + 1]
        signal = strategy_func(sub)

        if signal == "NONE":
            continue

        # === Filtros de Qualidade (Fases 1+2) ===
        if not check_rsi_filter(sub, signal):
            continue
        if not check_volume_filter(sub):
            continue
        if not check_trend_filter(sub, signal):
            continue
        # MTF: usar o df M5 equivalente (fatia temporal dos mesmos dados em granularidade maior)
        # No backtest usamos o df principal como proxy do M5 (sem dados separados)
        # Para backtest fiel ao live, o MTF usará os dados resampleados
        df_m5_proxy = sub.resample("5min").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna() if hasattr(sub.index, 'freq') or isinstance(sub.index, pd.DatetimeIndex) else None
        if df_m5_proxy is not None and len(df_m5_proxy) >= 26:
            df_m5_proxy = apply_indicators(df_m5_proxy)
            if not check_mtf_alignment(df_m5_proxy, signal):
                continue

        signals_generated += 1
        entry = df_ind.iloc[i]["close"]

        # ATR dinamico
        atr_val = df_ind.iloc[i].get("ATRr_14", entry * 0.005)
        if pd.isna(atr_val) or atr_val == 0:
            atr_val = entry * 0.005

        if signal == "CALL":
            tp_price = entry + atr_val * TP_MULTIPLIER
            sl_price = entry - atr_val * SL_MULTIPLIER
        else:
            tp_price = entry - atr_val * TP_MULTIPLIER
            sl_price = entry + atr_val * SL_MULTIPLIER

        trade_won    = False
        trade_closed = False

        for j in range(i + 1, len(df_ind)):
            h  = df_ind.iloc[j]["high"]
            lo = df_ind.iloc[j]["low"]

            if signal == "CALL":
                if lo <= sl_price:
                    trade_closed = True
                    break
                elif h >= tp_price:
                    trade_won    = True
                    trade_closed = True
                    break
            else:
                if h >= sl_price:
                    trade_closed = True
                    break
                elif lo <= tp_price:
                    trade_won    = True
                    trade_closed = True
                    break

        if trade_closed:
            exit_price = tp_price if trade_won else sl_price
            trades.append({
                "direction": signal,
                "entry_price": entry,
                "exit_price": exit_price,
                "qty": notional / entry,
            })

    metrics = calculate_backtest_metrics(
        trades,
        starting_equity=1000.0,
        cost=TradingCostConfig(fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS),
    )
    return {
        "signals": signals_generated,
        "wins":    metrics["wins"],
        "losses":  metrics["losses"],
        "win_rate": round(metrics["win_rate"], 2),
        "pnl_usdt": round(metrics["net_pnl_usdt"], 2),
        "gross_pnl_usdt": round(metrics["gross_pnl_usdt"], 2),
        "total_cost_usdt": round(metrics["total_cost_usdt"], 2),
        "profit_factor": round(metrics["profit_factor"], 2),
        "max_drawdown_pct": round(metrics["max_drawdown_pct"], 2),
        "expectancy_usd": round(metrics["expectancy_usd"], 2),
        "trades": metrics["trades"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def format_report(results: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"  RELATORIO DE DEEP BACKTEST -- {SYMBOL} | ULTIMOS {DAYS} DIAS")
    lines.append(f"  Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    lines.append(f"  Gestao de Risco: Stake ${STAKE_USD} x {LEVERAGE}x | TP={TP_MULTIPLIER}xATR | SL={SL_MULTIPLIER}xATR")
    lines.append("=" * 70)

    for tf_name, tf_data in results.items():
        lines.append(f"\n  TIMEFRAME: {tf_name}")
        lines.append(f"  {'Estrategia':<15} {'Sinais':>8} {'Wins':>6} {'Losses':>8} {'Win Rate':>10} {'PnL (USD)':>12} {'PF':>7} {'MaxDD':>8} {'Exp':>8}")
        lines.append(f"  {'-'*85}")
        for strat_name, stats in tf_data.items():
            pnl_str = f"+${stats['pnl_usdt']:.2f}" if stats['pnl_usdt'] >= 0 else f"-${abs(stats['pnl_usdt']):.2f}"
            lines.append(
                f"  {strat_name:<15} {stats['signals']:>8} {stats['wins']:>6} "
                f"{stats['losses']:>8} {stats['win_rate']:>9.2f}% {pnl_str:>12} "
                f"{stats['profit_factor']:>7.2f} {stats['max_drawdown_pct']:>7.1f}% {stats['expectancy_usd']:>8.2f}"
            )

    # Ranking geral por PnL
    lines.append(f"\n{'='*70}")
    lines.append("  RANKING GERAL (por PnL Liquido)")
    lines.append(f"  {'-'*50}")

    flat = []
    for tf_name, tf_data in results.items():
        for strat_name, stats in tf_data.items():
            flat.append((tf_name, strat_name, stats))

    flat.sort(key=lambda x: x[2]["pnl_usdt"], reverse=True)
    for rank, (tf, strat, stats) in enumerate(flat, 1):
        medal = "1." if rank == 1 else (f"2." if rank == 2 else (f"3." if rank == 3 else f"{rank}."))
        pnl_str = f"+${stats['pnl_usdt']:.2f}" if stats['pnl_usdt'] >= 0 else f"-${abs(stats['pnl_usdt']):.2f}"
        lines.append(f"  {medal}  {strat} ({tf}): {pnl_str}  |  WR: {stats['win_rate']}%  |  Trades: {stats['wins']+stats['losses']}  |  PF: {stats['profit_factor']:.2f}")

    best = flat[0]
    lines.append(f"\n  ESTRATEGIA RECOMENDADA: {best[1]} no {best[0]}")
    lines.append(f"  PnL: ${best[2]['pnl_usdt']:.2f} | Win Rate: {best[2]['win_rate']}% | Trades: {best[2]['wins']+best[2]['losses']}")
    lines.append("=" * 70)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\nMutant Crypto Bot -- Deep Backtest Engine iniciado!")
    print(f"   Simbolo: {SYMBOL} | Periodo: {DAYS} dias | Risco 1:2 com ATR dinamico\n")

    results = {}

    for tf_name, (interval, _seconds) in TIMEFRAMES.items():
        df = fetch_klines(SYMBOL, interval, DAYS)
        results[tf_name] = {}

        for strat_name in STRATEGIES:
            print(f"   Rodando {strat_name} no {tf_name}...", end="\r")
            stats = run_backtest(df, strat_name)
            results[tf_name][strat_name] = stats
            pnl_str = f"+${stats['pnl_usdt']:.2f}" if stats['pnl_usdt'] >= 0 else f"-${abs(stats['pnl_usdt']):.2f}"
            print(f"   OK {strat_name:12} | {tf_name} | {stats['signals']} sinais | WR {stats['win_rate']}% | {pnl_str}   ")

    report = format_report(results)
    print("\n" + report)

    # Salvar relatorio
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(os.path.dirname(__file__), f"backtest_report_{ts}.txt")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nRelatorio salvo em: {report_path}\n")


if __name__ == "__main__":
    main()
