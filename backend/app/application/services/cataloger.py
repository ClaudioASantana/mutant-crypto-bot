from typing import List
from app.domain.entities.market import Candle
from app.application.services.technical_analysis import (
    candles_to_df, apply_indicators,
    eval_ema_macd, eval_bollinger, eval_vwap, eval_smc, eval_supertrend, eval_pin_bar,
    eval_abcd, eval_consecutive, eval_rsi_ema_confluence, eval_mean_reversion_exhaustion
)

def calculate_win_rate(closed_candles: List[Candle], strategy_name: str) -> dict:
    """
    Simula entradas usando a estratégia técnica sobre o histórico de velas.
    Retorna o total de sinais gerados e a % de vitoria (Win Rate).
    Para simplificar o backtest no painel, consideramos WIN se a próxima vela fechar 
    a favor da direção do sinal.
    """
    if len(closed_candles) < 50:
        return {"signals": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl_usdt": 0.0}

    # Converter para df e aplicar todos os indicadores de uma vez
    df = candles_to_df(closed_candles)
    df = apply_indicators(df)

    signals_generated = 0
    wins = 0
    losses = 0
    pnl_usdt = 0.0
    trades = []
    
    # Mapeamento da estratégia
    strategy_func = None
    if strategy_name == "EMA+MACD":
        strategy_func = eval_ema_macd
    elif strategy_name == "Bollinger":
        strategy_func = eval_bollinger
    elif strategy_name == "VWAP":
        strategy_func = eval_vwap
    elif strategy_name == "SMC":
        strategy_func = eval_smc
    elif strategy_name == "SuperTrend":
        strategy_func = eval_supertrend
    elif strategy_name == "Pin Bar":
        strategy_func = eval_pin_bar
    elif strategy_name == "ABCD":
        strategy_func = eval_abcd
    elif strategy_name == "3 Velas":
        strategy_func = eval_consecutive
    elif strategy_name == "RSI+EMA":
        strategy_func = eval_rsi_ema_confluence
    elif strategy_name == "Exaustão":
        strategy_func = eval_mean_reversion_exhaustion
    else:
        return {"signals": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl_usdt": 0.0}

    # Padrão Crypto Futures Default Risco 1:2
    tp_multiplier = 3.0
    sl_multiplier = 1.5
    stake = 100.0
    leverage = 10

    for i in range(50, len(df) - 1):
        sub_df = df.iloc[:i+1]
        
        signal = strategy_func(sub_df)
        
        if signal != "NONE":
            signals_generated += 1
            entry_price = df.iloc[i]["close"]
            
            # Dynamic Target calculation using ATR (Default)
            atr_val = df.iloc[i].get("ATRr_14", entry_price * 0.005)

            if strategy_name == "3 Velas":
                #Wiki: SL na Barra 2 (resting bar), TP = amplitude da Barra 1 (igniting bar)
                c1 = df.iloc[i-2] # Igniting
                c2 = df.iloc[i-1] # Resting

                igniting_body = abs(c1["close"] - c1["open"])
                if signal == "CALL":
                    sl_price = c2["low"]
                    tp_price = entry_price + igniting_body
                else:
                    sl_price = c2["high"]
                    tp_price = entry_price - igniting_body
            else:
                if signal == "CALL":
                    sl_price = entry_price - (atr_val * sl_multiplier)
                    tp_price = entry_price + (atr_val * tp_multiplier)
                else:
                    sl_price = entry_price + (atr_val * sl_multiplier)
                    tp_price = entry_price - (atr_val * tp_multiplier)
                
            trade_won = False
            trade_closed = False
            
            # Variáveis para Trailing Stop (DESATIVADO)
            # highest_reached = entry_price
            # lowest_reached = entry_price

            for j in range(i+1, len(df)):
                c_high = df['high'].iloc[j]
                c_low = df['low'].iloc[j]
                c_close = df['close'].iloc[j]

                current_time = int(df.index[j].timestamp())
                entry_time = int(df.index[i].timestamp())
                duration_seconds = current_time - entry_time
                hit_time_stop = duration_seconds >= (240 * 60) # 4 hours

                if hit_time_stop:
                    trade_won = False
                    trade_closed = True
                    exit_price = c_close
                    break

                if signal == "CALL":
                    # Trailing Stop removido. Apenas SL e TP fixos.
                    if c_low <= sl_price:
                        trade_won = False
                        trade_closed = True
                        break
                    elif c_high >= tp_price:
                        trade_won = True
                        trade_closed = True
                        break
                else: # PUT
                    if c_high >= sl_price:
                        trade_won = False
                        trade_closed = True
                        break
                    elif c_low <= tp_price:
                        trade_won = True
                        trade_closed = True
                        break
                        
            if trade_closed:
                fee = stake * leverage * 0.001
                
                if hit_time_stop:
                    # Treat TIME_STOP like a partial close at current price
                    profit = (stake * leverage * ((exit_price - entry_price) / entry_price)) if signal == "CALL" else (stake * leverage * ((entry_price - exit_price) / entry_price))
                    profit -= fee
                    pnl_usdt += profit
                    if profit > 0:
                        wins += 1
                    else:
                        losses += 1
                elif trade_won:
                    wins += 1
                    # Calcula o lucro baseado no preço de saída (aproximado pelo TP ou SL móvel)
                    exit_price = tp_price if signal == "CALL" and c_high >= tp_price else sl_price
                    if signal == "PUT":
                        exit_price = tp_price if c_low <= tp_price else sl_price
                    
                    profit = (stake * leverage * (abs(entry_price - exit_price) / entry_price)) - fee
                    pnl_usdt += profit
                else:
                    losses += 1
                    exit_price = sl_price
                    # Perda no SL original ou parcial
                    profit = -(stake * leverage * (abs(entry_price - sl_price) / entry_price)) - fee
                    pnl_usdt += profit
                    
                entry_time = int(df.index[i].timestamp())
                exit_time = int(df.index[j].timestamp())
                trades.append({
                    "entry_time": entry_time,
                    "entry_price": float(entry_price),
                    "exit_time": exit_time,
                    "exit_price": float(exit_price),
                    "signal": signal,
                    "profit": float(profit)
                })
                
    win_rate = 0.0
    if wins + losses > 0:
        win_rate = round((wins / (wins + losses)) * 100, 2)
        
    return {
        "signals": signals_generated,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "pnl_usdt": round(pnl_usdt, 2),
        "trades": trades,
        "df": df
    }
