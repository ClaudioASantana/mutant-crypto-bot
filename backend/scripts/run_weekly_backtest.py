#!/usr/bin/env python3
"""
🧬 Weekly Backtest - Mutant Crypto Bot
======================================
Executa backtest completo para a semana atual (últimos 7 dias)
avaliando todas as estratégias do bot em M1, M5 e M15 com dados reais da Binance.
"""

import sys
import os
import time
import requests
import json
import numpy as np
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
    apply_indicators,
    eval_ema_macd,
    eval_bollinger,
    eval_vwap,
    eval_vwap_zscore,
    eval_smc,
    eval_supertrend,
    eval_wyckoff_bollinger,
    eval_wyckoff_smc,
    eval_consecutive,
    eval_three_candles_composite,
    eval_pin_bar,
    eval_rsi_ema_confluence,
    eval_mean_reversion_exhaustion,
    eval_abcd,
    check_rsi_filter,
    check_volume_filter,
    check_trend_filter,
    check_mtf_alignment
)

STRATEGIES = {
    "SMC": eval_smc,
    "Bollinger": eval_bollinger,
    "EMA+MACD": eval_ema_macd,
    "VWAP": eval_vwap,
    "VWAP Z-Score": eval_vwap_zscore,
    "SuperTrend": eval_supertrend,
    "Wyckoff_SMC": eval_wyckoff_smc,
    "Wyckoff_Bbands": eval_wyckoff_bollinger,
    "3 Velas": eval_three_candles_composite,
    "Pin Bar": eval_pin_bar,
    "RSI+EMA": eval_rsi_ema_confluence,
    "Exaustão": eval_mean_reversion_exhaustion,
    "ABCD": eval_abcd,
}

TIMEFRAMES = {
    "M1":  ("1m",  60),
    "M5":  ("5m",  300),
    "M15": ("15m", 900),
}

DEFAULT_SYMBOL = "BTCUSDT"
DAYS = 7

# Parâmetros de Risco e Simulação
TP_MULTIPLIER = 3.0
SL_MULTIPLIER = 1.5
STAKE_USD     = 100.0
LEVERAGE      = 10
FEE_RATE      = 0.0004  # 0.04% por ponta (Binance Futures taker)
SLIPPAGE_BPS  = 1.0     # slippage por ponta, em basis points


def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Baixa os dados históricos dos últimos `days` dias via API pública da Binance."""
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days)
    end_ms = int(end_dt.timestamp() * 1000)
    start_ms = int(start_dt.timestamp() * 1000)
    url = "https://api.binance.com/api/v3/klines"

    all_rows = []
    current = start_ms

    print(f"   [Download] {symbol} {interval} ({start_dt.strftime('%d/%m/%Y')} a {end_dt.strftime('%d/%m/%Y')})...", end="\r", flush=True)
    while current < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current,
            "endTime": end_ms,
            "limit": 1000,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            rows = resp.json()
            if not rows or not isinstance(rows, list):
                break
            all_rows.extend(rows)
            current = rows[-1][6] + 1
            time.sleep(0.04)
        except Exception as e:
            print(f"\n   Aviso no download ({e}), tentando novamente...", flush=True)
            time.sleep(1)
            continue

    if not all_rows:
        raise ValueError(f"Não foi possível baixar dados para {symbol} {interval}")

    df = pd.DataFrame(all_rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_vol",
        "taker_buy_quote_vol", "ignore"
    ])
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df.set_index("open_time", inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    print(f"   [OK] {symbol} {interval}: {len(df)} candles carregados com sucesso.           ", flush=True)
    return df


def run_strategy_backtest(df_ind: pd.DataFrame, strategy_name: str, strategy_func, tf_name: str, df_m5_ind: pd.DataFrame = None) -> dict:
    """Executa o backtest com controle rigoroso de posições, taxas e drawdown."""
    start_idx = 60
    n_candles = len(df_ind)

    trades = []
    signals_count = 0
    in_position = False
    pos_direction = None
    pos_entry = 0.0
    pos_sl = 0.0
    pos_tp = 0.0
    pos_atr = 0.0
    pos_entry_idx = 0
    pos_entry_time = None

    notional = STAKE_USD * LEVERAGE
    cost_config = TradingCostConfig(fee_rate=FEE_RATE, slippage_bps=SLIPPAGE_BPS)

    # Para MTF no M1: mapear timestamps M1 para M5 de forma indexada
    m5_signal_map = {}
    if tf_name == "M1" and df_m5_ind is not None and len(df_m5_ind) > 0:
        for idx in range(30, len(df_m5_ind)):
            t = df_m5_ind.index[idx]
            sub_m5 = df_m5_ind.iloc[max(0, idx - 30): idx + 1]
            call_align = check_mtf_alignment(sub_m5, "CALL")
            put_align = check_mtf_alignment(sub_m5, "PUT")
            m5_signal_map[t] = {"CALL": call_align, "PUT": put_align}

    for i in range(start_idx, n_candles - 1):
        current_candle = df_ind.iloc[i]
        curr_close = current_candle["close"]
        curr_high = current_candle["high"]
        curr_low = current_candle["low"]
        curr_time = df_ind.index[i]

        # Verificar se posição aberta atingiu TP ou SL no candle atual
        if in_position:
            closed = False
            win = False
            exit_price = curr_close

            if pos_direction == "CALL":
                if curr_low <= pos_sl:
                    closed = True
                    win = False
                    exit_price = pos_sl
                elif curr_high >= pos_tp:
                    closed = True
                    win = True
                    exit_price = pos_tp
            elif pos_direction == "PUT":
                if curr_high >= pos_sl:
                    closed = True
                    win = False
                    exit_price = pos_sl
                elif curr_low <= pos_tp:
                    closed = True
                    win = True
                    exit_price = pos_tp

            # Time stop de segurança: max 24h sem fechar
            if not closed and (curr_time - pos_entry_time).total_seconds() > 86400:
                closed = True
                exit_price = curr_close
                if pos_direction == "CALL":
                    win = exit_price > pos_entry
                else:
                    win = exit_price < pos_entry

            if closed:
                trades.append({
                    "entry_time": str(pos_entry_time),
                    "exit_time": str(curr_time),
                    "direction": pos_direction,
                    "entry_price": pos_entry,
                    "exit_price": exit_price,
                    "qty": notional / pos_entry,
                })
                in_position = False

        # Se não estiver posicionado, avalia novos sinais
        if not in_position:
            sub = df_ind.iloc[max(0, i - 60): i + 1]
            try:
                sig = strategy_func(sub)
            except Exception:
                sig = "NONE"

            if sig in ("CALL", "PUT"):
                signals_count += 1

                # Filtros de Qualidade (Fases 1+2)
                pass_rsi = check_rsi_filter(sub, sig)
                pass_vol = check_volume_filter(sub)
                pass_trend = check_trend_filter(sub, sig)

                # MTF
                pass_mtf = True
                if tf_name == "M1" and m5_signal_map:
                    # Arredondar para o candle M5 anterior
                    floored_m5_time = curr_time.floor("5min")
                    if floored_m5_time in m5_signal_map:
                        pass_mtf = m5_signal_map[floored_m5_time].get(sig, True)

                if pass_rsi and pass_vol and pass_trend and pass_mtf:
                    entry = curr_close
                    atr_val = current_candle.get("ATRr_14", entry * 0.005)
                    if pd.isna(atr_val) or atr_val == 0:
                        atr_val = entry * 0.005

                    if sig == "CALL":
                        pos_tp = entry + atr_val * TP_MULTIPLIER
                        pos_sl = entry - atr_val * SL_MULTIPLIER
                    else:
                        pos_tp = entry - atr_val * TP_MULTIPLIER
                        pos_sl = entry + atr_val * SL_MULTIPLIER

                    in_position = True
                    pos_direction = sig
                    pos_entry = entry
                    pos_atr = atr_val
                    pos_entry_idx = i
                    pos_entry_time = curr_time

    # Métricas centralizadas: custo (fee + slippage) e agregação vêm do módulo.
    metrics = calculate_backtest_metrics(
        trades, starting_equity=1000.0, cost=cost_config
    )

    return {
        "strategy": strategy_name,
        "timeframe": tf_name,
        "signals": signals_count,
        "trades": metrics["total_trades"],
        "wins": metrics["wins"],
        "losses": metrics["losses"],
        "win_rate": round(metrics["win_rate"], 2),
        "net_pnl": round(metrics["net_pnl_usdt"], 2),
        "gross_pnl": round(metrics["gross_pnl_usdt"], 2),
        "total_cost": round(metrics["total_cost_usdt"], 2),
        "profit_factor": round(metrics["profit_factor"], 2),
        "max_drawdown_pct": round(metrics["max_drawdown_pct"], 2),
        "expectancy_usd": round(metrics["expectancy_usd"], 2),
        "payoff_ratio": round(metrics["payoff_ratio"], 2),
        "sharpe": round(metrics["sharpe"], 2),
        "sortino": round(metrics["sortino"], 2),
        "trade_samples": metrics["trades"][:5],
    }


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SYMBOL
    days = int(sys.argv[2]) if len(sys.argv) > 2 else DAYS

    now_utc = datetime.now(timezone.utc)
    week_start = now_utc - timedelta(days=days)

    print("\n" + "=" * 88, flush=True)
    print(f"🧬 MUTANT CRYPTO BOT -- BACKTEST SEMANAL (ÚLTIMOS {days} DIAS)", flush=True)
    print(f"   Período: {week_start.strftime('%d/%m/%Y %H:%M UTC')} até {now_utc.strftime('%d/%m/%Y %H:%M UTC')}", flush=True)
    print(f"   Ativo: {symbol} | Stake: ${STAKE_USD} | Alavancagem: {LEVERAGE}x | Fee: 0.04%/ponta", flush=True)
    print(f"   Gestão de Risco: TP = {TP_MULTIPLIER}x ATR | SL = {SL_MULTIPLIER}x ATR (R:R 1:2)", flush=True)
    print("=" * 88 + "\n", flush=True)

    # Baixar dados de todos os timeframes
    dfs_ind = {}
    for tf_name, (interval, _sec) in TIMEFRAMES.items():
        raw_df = fetch_klines(symbol, interval, days)
        print(f"   ⚙️ Calculando indicadores para {tf_name}...", flush=True)
        dfs_ind[tf_name] = apply_indicators(raw_df)

    df_m5_ind = dfs_ind.get("M5")

    results_by_tf = {}
    all_flat_results = []

    for tf_name in ["M15", "M5", "M1"]:
        print(f"\n📊 Analisando Timeframe {tf_name} ({TIMEFRAMES[tf_name][0]})...", flush=True)
        df_ind = dfs_ind[tf_name]
        results_by_tf[tf_name] = {}

        for strat_name, strat_func in STRATEGIES.items():
            res = run_strategy_backtest(df_ind, strat_name, strat_func, tf_name, df_m5_ind=df_m5_ind)
            results_by_tf[tf_name][strat_name] = res
            all_flat_results.append(res)
            pnl_badge = f"+${res['net_pnl']:.2f}" if res['net_pnl'] >= 0 else f"-${abs(res['net_pnl']):.2f}"
            pf_badge = f"{res['profit_factor']:.2f}" if res['profit_factor'] < 90 else "Inf"
            print(f"   ▶ {strat_name:<16} | Trades: {res['trades']:>3} | WR: {res['win_rate']:>5.1f}% | PnL: {pnl_badge:>9} | PF: {pf_badge:>5}", flush=True)

    # Relatório Consolidado
    report_lines = []
    report_lines.append("=" * 88)
    report_lines.append(f"🧬 RELATÓRIO DE PERFORMANCE SEMANAL -- {symbol}")
    report_lines.append(f"Período: {week_start.strftime('%d/%m/%Y %H:%M')} a {now_utc.strftime('%d/%m/%Y %H:%M')} UTC ({days} dias)")
    report_lines.append(f"Configuração: Stake ${STAKE_USD} x {LEVERAGE}x | TP {TP_MULTIPLIER}xATR | SL {SL_MULTIPLIER}xATR | Taxa Binance: 0.04%/lado")
    report_lines.append("=" * 88)

    for tf_name in ["M15", "M5", "M1"]:
        report_lines.append(f"\n--- TIMEFRAME: {tf_name} ---")
        report_lines.append(f"{'Estratégia':<16} {'Sinais':>7} {'Trades':>7} {'Wins':>5} {'Loss':>5} {'Win Rate':>9} {'PnL Líq (USD)':>14} {'Profit Factor':>14} {'Max DD':>8}")
        report_lines.append("-" * 88)
        for strat_name, data in results_by_tf[tf_name].items():
            pnl_s = f"+${data['net_pnl']:.2f}" if data['net_pnl'] >= 0 else f"-${abs(data['net_pnl']):.2f}"
            pf_s = f"{data['profit_factor']:.2f}" if data['profit_factor'] < 90 else "Inf"
            dd_s = f"{data['max_drawdown_pct']:.1f}%"
            report_lines.append(
                f"{strat_name:<16} {data['signals']:>7} {data['trades']:>7} {data['wins']:>5} {data['losses']:>5} "
                f"{data['win_rate']:>8.1f}% {pnl_s:>14} {pf_s:>14} {dd_s:>8}"
            )

    # Ranking Geral Consolidado
    all_flat_results.sort(key=lambda x: x["net_pnl"], reverse=True)

    report_lines.append("\n" + "=" * 88)
    report_lines.append("🏆 TOP ESTRATÉGIAS MAIS LUCRATIVAS DA SEMANA (Ranking Geral)")
    report_lines.append("=" * 88)
    for i, r in enumerate(all_flat_results[:10], 1):
        pnl_s = f"+${r['net_pnl']:.2f}" if r['net_pnl'] >= 0 else f"-${abs(r['net_pnl']):.2f}"
        pf_s = f"{r['profit_factor']:.2f}" if r['profit_factor'] < 90 else "Inf"
        report_lines.append(
            f"  {i:>2}. {r['strategy']:<15} ({r['timeframe']:>3}): {pnl_s:>10} | WR: {r['win_rate']:>5.1f}% | Trades: {r['trades']:>3} (W:{r['wins']} L:{r['losses']}) | PF: {pf_s:>5} | MaxDD: {r['max_drawdown_pct']:.1f}%"
        )

    best = all_flat_results[0]
    report_lines.append("-" * 88)
    report_lines.append(f"⭐ CAMPEÃ DA SEMANA: {best['strategy']} ({best['timeframe']}) com PnL de +${best['net_pnl']:.2f} (WR: {best['win_rate']}%, PF: {best['profit_factor']:.2f})")
    report_lines.append("=" * 88)

    full_report = "\n".join(report_lines)
    print("\n\n" + full_report, flush=True)

    # Salvar relatório em arquivo
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(os.path.dirname(__file__), f"weekly_backtest_report_{ts}.txt")
    json_file = os.path.join(os.path.dirname(__file__), f"weekly_backtest_result_{ts}.json")

    with open(report_file, "w") as f:
        f.write(full_report)
    with open(json_file, "w") as f:
        json.dump({"summary": results_by_tf, "ranking": all_flat_results}, f, indent=2, default=str)

    print(f"\n💾 Relatório salvo em: {report_file}", flush=True)
    print(f"💾 JSON completo salvo em: {json_file}\n", flush=True)


if __name__ == "__main__":
    main()
