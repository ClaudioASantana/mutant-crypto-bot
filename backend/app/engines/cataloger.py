from typing import List
from app.models.market import Candle
from app.engines.technical_analysis import (
    candles_to_df, apply_indicators, 
    eval_ema_macd, eval_bollinger, eval_vwap, eval_smc
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
            
            # Dynamic Target calculation using ATR
            atr_val = df.iloc[i].get("ATRr_14", entry_price * 0.005) # Fallback se não existir
            
            if signal == "CALL":
                tp_price = entry_price + (atr_val * tp_multiplier)
                sl_price = entry_price - (atr_val * sl_multiplier)
            else:
                tp_price = entry_price - (atr_val * tp_multiplier)
                sl_price = entry_price + (atr_val * sl_multiplier)
                
            trade_won = False
            trade_closed = False
            
            for j in range(i+1, len(df)):
                c_high = df.iloc[j]["high"]
                c_low = df.iloc[j]["low"]
                
                if signal == "CALL":
                    if c_low <= sl_price:
                        trade_closed = True
                        break
                    elif c_high >= tp_price:
                        trade_won = True
                        trade_closed = True
                        break
                else: # PUT
                    if c_high >= sl_price:
                        trade_closed = True
                        break
                    elif c_low <= tp_price:
                        trade_won = True
                        trade_closed = True
                        break
                        
            if trade_closed:
                if trade_won:
                    wins += 1
                    pnl_usdt += (stake * leverage * ((atr_val * tp_multiplier) / entry_price))
                else:
                    losses += 1
                    pnl_usdt -= (stake * leverage * ((atr_val * sl_multiplier) / entry_price))
                
    win_rate = 0.0
    if wins + losses > 0:
        win_rate = round((wins / (wins + losses)) * 100, 2)
        
    return {
        "signals": signals_generated,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "pnl_usdt": round(pnl_usdt, 2)
    }
