import asyncio
import pandas as pd
import pandas_ta as ta
import sys
import os

sys.path.append(os.path.abspath('.'))

from backend.app.services.binance_client import BinanceClient
from backend.app.engines.technical_analysis import candles_to_df

def apply_st(df: pd.DataFrame, length: int, multiplier: float):
    # Clear previous ST cols to avoid overlap if running in place
    cols_to_drop = [c for c in df.columns if "SUPERT" in c]
    if cols_to_drop:
        df.drop(columns=cols_to_drop, inplace=True)
    df.ta.supertrend(length=length, multiplier=multiplier, append=True)
    df.ta.atr(length=14, append=True)
    return df

def eval_supertrend_custom(df: pd.DataFrame, length: int, multiplier: float) -> str:
    st_dir_col = [c for c in df.columns if "SUPERTd" in c]
    if not st_dir_col:
        return "NONE"
    last_dir = df.iloc[-1].get(st_dir_col[0], 0)
    prev_dir = df.iloc[-2].get(st_dir_col[0], 0)
    if prev_dir < 0 and last_dir > 0: return "CALL"
    if prev_dir > 0 and last_dir < 0: return "PUT"
    return "NONE"

async def grid_search():
    print("Baixando histórico de 2000 velas de BTC/USDT (15m)...")
    
    candles = []
    def on_history(tf, c):
        nonlocal candles
        candles = c
        
    client = BinanceClient("BTC/USDT")
    client.add_history_callback(on_history)
    
    await client.fetch_history(timeframe_seconds=900, limit=2000)
    await client.exchange.close()
    
    print(f"Obtidas {len(candles)} velas.")
    df_base = pd.DataFrame(candles)
    if not df_base.empty:
        df_base.set_index("epoch", inplace=True)
        df_base = df_base[~df_base.index.duplicated(keep='last')]
        df_base.index = pd.to_datetime(df_base.index, unit='s')
    
    lengths = [7, 10, 14, 21]
    multipliers = [1.5, 2.0, 3.0, 4.0]
    
    results = []
    
    tp_multiplier = 3.0
    sl_multiplier = 1.5
    stake = 100.0
    leverage = 10
    
    print(f"{'Length':<8} | {'Mult':<6} | {'Signals':<8} | {'Win Rate':<10} | {'PnL (USDT)':<10}")
    print("-" * 55)
    
    for l in lengths:
        for m in multipliers:
            # Prepare dataframe with ST parameters
            df = df_base.copy()
            df = apply_st(df, l, m)
            
            signals_generated = 0
            wins = 0
            losses = 0
            pnl_usdt = 0.0
            
            for i in range(50, len(df) - 1):
                sub_df = df.iloc[:i+1]
                signal = eval_supertrend_custom(sub_df, l, m)
                
                if signal != "NONE":
                    signals_generated += 1
                    entry_price = df.iloc[i]["close"]
                    atr_val = df.iloc[i].get("ATRr_14", entry_price * 0.005)
                    
                    if signal == "CALL":
                        sl_price = entry_price - (atr_val * sl_multiplier)
                        tp_price = entry_price + (atr_val * tp_multiplier)
                    else:
                        sl_price = entry_price + (atr_val * sl_multiplier)
                        tp_price = entry_price - (atr_val * tp_multiplier)
                        
                    trade_won = False
                    trade_closed = False
                    highest_reached = entry_price
                    lowest_reached = entry_price
                    
                    for j in range(i+1, len(df)):
                        c_high = df.iloc[j]["high"]
                        c_low = df.iloc[j]["low"]
                        c_close = df.iloc[j]["close"]
                        
                        if signal == "CALL":
                            if c_high > highest_reached:
                                highest_reached = c_high
                                if highest_reached >= entry_price + atr_val:
                                    new_sl = highest_reached - atr_val
                                    if new_sl > sl_price: sl_price = new_sl
                            if c_low <= sl_price:
                                trade_closed = True
                                if sl_price >= entry_price: trade_won = True
                                break
                            elif c_high >= tp_price:
                                trade_won = True
                                trade_closed = True
                                break
                        else:
                            if c_low < lowest_reached:
                                lowest_reached = c_low
                                if lowest_reached <= entry_price - atr_val:
                                    new_sl = lowest_reached + atr_val
                                    if new_sl < sl_price: sl_price = new_sl
                            if c_high >= sl_price:
                                trade_closed = True
                                if sl_price <= entry_price: trade_won = True
                                break
                            elif c_low <= tp_price:
                                trade_won = True
                                trade_closed = True
                                break
                                
                    if trade_closed:
                        if trade_won:
                            wins += 1
                            exit_price = tp_price if signal == "CALL" and c_high >= tp_price else sl_price
                            exit_price = tp_price if signal == "PUT" and c_low <= tp_price else sl_price
                            pnl_usdt += (stake * leverage * (abs(entry_price - exit_price) / entry_price))
                        else:
                            losses += 1
                            pnl_usdt -= (stake * leverage * (abs(entry_price - sl_price) / entry_price))
                            
            win_rate = 0.0
            if wins + losses > 0: win_rate = round((wins / (wins + losses)) * 100, 2)
            results.append({"Length": l, "Mult": m, "Signals": signals_generated, "Win Rate": win_rate, "PnL": round(pnl_usdt, 2)})
            print(f"{l:<8} | {m:<6} | {signals_generated:<8} | {win_rate:<9}% | {round(pnl_usdt, 2):<10}")

    best = max(results, key=lambda x: x['PnL'])
    print("-" * 55)
    print(f"🏆 MELHOR PARAMETRIZAÇÃO: Length={best['Length']}, Multiplier={best['Mult']}, PnL={best['PnL']} USDT (Win Rate {best['Win Rate']}%)")

if __name__ == "__main__":
    asyncio.run(grid_search())
