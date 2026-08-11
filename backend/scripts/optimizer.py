import os
import sys
import json
import asyncio
import ccxt.async_support as ccxt
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.models.market import Candle, CandleDirection
from app.engines.indicators import calculate_rsi

load_dotenv()

SYMBOL = "BTC/USDT"

async def download_history(symbol, timeframe_seconds, limit):
    exchange = ccxt.binance()
    tf_map = {60: '1m', 300: '5m', 900: '15m', 3600: '1h'}
    tf = tf_map.get(timeframe_seconds, '1m')
    
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, tf, limit=limit)
        history = []
        for c in ohlcv:
            open_p, high_p, low_p, close_p = c[1], c[2], c[3], c[4]
            direction = CandleDirection.BULLISH if close_p > open_p else CandleDirection.BEARISH
            if close_p == open_p:
                direction = CandleDirection.NEUTRAL
            history.append(Candle(
                epoch=int(c[0] / 1000),
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                direction=direction
            ))
        await exchange.close()
        return history
    except Exception as e:
        print(f"Erro no download: {e}")
        await exchange.close()
        return []

def run_simulation(history, consecutive_candles, rsi_oversold, rsi_overbought, max_gale, stake, payout_rate, rsi_period=14):
    balance = 0.0
    wins = 0
    losses = 0
    current_gale = 0
    current_stake = stake
    
    in_trade = False
    trade_direction = None
    
    for i in range(len(history)):
        if i < rsi_period + consecutive_candles:
            continue
            
        current_candle = history[i]
        
        if in_trade:
            won = False
            if trade_direction == "CALL" and current_candle.direction == CandleDirection.BULLISH:
                won = True
            elif trade_direction == "PUT" and current_candle.direction == CandleDirection.BEARISH:
                won = True
                
            if won:
                balance += (current_stake * payout_rate)
                wins += 1
                in_trade = False
                current_stake = stake
                current_gale = 0
            else:
                balance -= current_stake
                if current_gale < max_gale:
                    current_gale += 1
                    current_stake *= 2.0
                else:
                    losses += 1
                    in_trade = False
                    current_stake = stake
                    current_gale = 0
            continue
            
        slice_history = history[:i+1]
        last_n = slice_history[-consecutive_candles:]
        
        signal = None
        if all(c.direction == CandleDirection.BEARISH for c in last_n):
            signal = "CALL"
        elif all(c.direction == CandleDirection.BULLISH for c in last_n):
            signal = "PUT"
            
        if signal:
            rsi_val = calculate_rsi(slice_history, rsi_period)
            if signal == "CALL" and rsi_val >= rsi_oversold:
                pass
            elif signal == "PUT" and rsi_val <= rsi_overbought:
                pass
            else:
                in_trade = True
                trade_direction = signal
                
    return {
        "wins": wins,
        "losses": losses,
        "pnl": balance
    }

async def optimize():
    results = []
    print(f"Baixando histórico M5 e M1 da Binance para {SYMBOL} (5000 velas)...")
    history_m5 = await download_history(SYMBOL, 300, 5000)
    history_m1 = await download_history(SYMBOL, 60, 5000)
    
    print("Testando 108 configurações possíveis...")
    for history, timeframe_name in [(history_m5, "M5"), (history_m1, "M1")]:
        if not history: continue
        for consecutive_candles in [2, 3, 4, 5]:
            for max_gale in [0, 1, 2]: # 0 = Without Gale
                for rsi_combo in [(40, 60), (35, 65), (30, 70), (25, 75), (20, 80)]:
                    rsi_over, rsi_under = rsi_combo
                    res = run_simulation(
                        history,
                        consecutive_candles,
                        rsi_over,
                        rsi_under,
                        max_gale,
                        stake=10.0,
                        payout_rate=0.95
                    )
                    total = res['wins'] + res['losses']
                    if total < 10:
                        continue # Ignore setups that don't trigger enough entries
                        
                    win_rate = (res['wins'] / total * 100) if total > 0 else 0
                    results.append({
                        "timeframe": timeframe_name,
                        "candles": consecutive_candles,
                        "gale": max_gale,
                        "rsi": f"{rsi_over}/{rsi_under}",
                        "wins": res['wins'],
                        "losses": res['losses'],
                        "total_trades": total,
                        "win_rate": win_rate,
                        "pnl": res['pnl']
                    })
                    
    # Sort by PNL
    results.sort(key=lambda x: x['pnl'], reverse=True)
    
    with open("optimization_results.json", "w") as f:
        json.dump(results[:20], f, indent=4)
        
    print("\n🏆 Top 5 Melhores Configurações (Cripto):")
    for idx, r in enumerate(results[:5]):
        print(f"{idx+1}. {r['timeframe']} | {r['candles']} Velas | Gale {r['gale']} | RSI {r['rsi']} => PnL: ${r['pnl']:.2f} (WR: {r['win_rate']:.1f}% | Trades: {r['total_trades']})")

if __name__ == "__main__":
    asyncio.run(optimize())
