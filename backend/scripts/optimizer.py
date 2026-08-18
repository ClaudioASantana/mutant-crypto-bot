import os
import sys
import json
import asyncio
import ccxt.async_support as ccxt
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import sys
import os
# Adiciona o diretório 'backend' ao path para permitir imports do pacote 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.entities.market import Candle, CandleDirection
from app.application.services.indicators import calculate_rsi

load_dotenv()

SYMBOL = "BTC/USDT"

import sqlite3
import time

def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'market_history.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT,
            timeframe INTEGER,
            epoch INTEGER,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, timeframe, epoch)
        )
    ''')
    return conn

async def download_history(symbol, timeframe_seconds, limit):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check how many candles we have in DB for this symbol and timeframe
    c.execute('SELECT COUNT(*) FROM candles WHERE symbol = ? AND timeframe = ?', (symbol, timeframe_seconds))
    count = c.fetchone()[0]
    
    exchange = ccxt.binance()
    tf_map = {60: '1m', 300: '5m', 900: '15m', 3600: '1h'}
    tf = tf_map.get(timeframe_seconds, '1m')
    
    try:
        candles_needed = limit
        end_time = int(time.time() * 1000)
        
        # If we already have some data, we could just fetch the difference, but to be robust
        # and support "Deep Backtest", we will fetch backwards from NOW until we hit the requested limit.
        # SQLite's INSERT OR IGNORE will handle duplicates gracefully, acting as an instant cache if data exists.
        
        # To optimize, we check if the most recent data exists and if we have enough count
        # BUT fetching the latest is always good to update the cache.
        # We will paginate backwards.
        
        while candles_needed > 0:
            fetch_limit = min(1000, candles_needed)
            ohlcv = await exchange.fetch_ohlcv(symbol, tf, limit=fetch_limit, params={'endTime': end_time})
            
            if not ohlcv:
                break
                
            records = []
            for row in ohlcv:
                epoch = int(row[0] / 1000)
                open_p, high_p, low_p, close_p, volume = row[1], row[2], row[3], row[4], row[5]
                records.append((symbol, timeframe_seconds, epoch, open_p, high_p, low_p, close_p, volume))
            
            c.executemany('''
                INSERT OR IGNORE INTO candles (symbol, timeframe, epoch, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', records)
            conn.commit()
            
            # Update end_time to fetch previous chunk (earliest timestamp minus 1 ms)
            end_time = int(ohlcv[0][0]) - 1
            candles_needed -= len(ohlcv)
            
            # A void rate limits on Binance
            if candles_needed > 0:
                await asyncio.sleep(0.1)
                
        # Now query the database for the required limit
        c.execute('''
            SELECT epoch, open, high, low, close, volume 
            FROM candles 
            WHERE symbol = ? AND timeframe = ? 
            ORDER BY epoch DESC 
            LIMIT ?
        ''', (symbol, timeframe_seconds, limit))
        
        rows = c.fetchall()
        
        history = []
        for row in reversed(rows):
            history.append(Candle(
                epoch=row[0],
                open=row[1],
                high=row[2],
                low=row[3],
                close=row[4],
                volume=row[5]
            ))
            
        await exchange.close()
        return history
        
    except Exception as e:
        print(f"Erro no download: {e}")
        await exchange.close()
        # Fallback to DB if network fails
        c.execute('SELECT epoch, open, high, low, close, volume FROM candles WHERE symbol = ? AND timeframe = ? ORDER BY epoch DESC LIMIT ?', (symbol, timeframe_seconds, limit))
        rows = c.fetchall()
        history = []
        for row in reversed(rows):
            history.append(Candle(
                epoch=row[0], open=row[1], high=row[2], low=row[3], close=row[4], volume=row[5]
            ))
        return history

def run_simulation(history, consecutive_candles, rsi_oversold, rsi_overbought, stake, payout_rate, rsi_period=14):
    balance = 0.0
    wins = 0
    losses = 0

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
                balance += (stake * payout_rate)
                wins += 1
            else:
                balance -= stake
                losses += 1

            in_trade = False
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
            for rsi_combo in [(40, 60), (35, 65), (30, 70), (25, 75), (20, 80)]:
                rsi_over, rsi_under = rsi_combo
                res = run_simulation(
                    history,
                    consecutive_candles,
                    rsi_over,
                    rsi_under,
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
        print(f"{idx+1}. {r['timeframe']} | {r['candles']} Velas | RSI {r['rsi']} => PnL: ${r['pnl']:.2f} (WR: {r['win_rate']:.1f}% | Trades: {r['total_trades']})")

if __name__ == "__main__":
    asyncio.run(optimize())
