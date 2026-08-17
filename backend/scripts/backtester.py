import os
import sys
import asyncio
import ccxt.async_support as ccxt
from datetime import datetime

# Ensure we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.models.market import Candle, CandleDirection
from app.engines.indicators import calculate_rsi
from app.engines.cataloger import calculate_win_rate

SYMBOL = "BNB/USDT"
GRANULARITY = 300 # M5
COUNT = 5000 # ~17 days of history

# Strategy params
CONSECUTIVE_CANDLES = 3
RSI_PERIOD = 14
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65

# Money Management
INITIAL_BALANCE = 10000.0
STAKE = 10.0
PAYOUT_RATE = 0.95 # Payout simulated 95%

async def download_history(symbol: str, timeframe_seconds: int, limit: int):
    exchange = ccxt.binance()
    tf_map = {60: '1m', 300: '5m', 900: '15m', 3600: '1h'}
    tf = tf_map.get(timeframe_seconds, '1m')
    
    print(f"🔄 Conectando na Binance para baixar histórico de {symbol} ({limit} velas de {tf})...")
    
    try:
        now_ms = exchange.milliseconds()
        since = now_ms - (limit * timeframe_seconds * 1000)
        
        all_ohlcv = []
        while len(all_ohlcv) < limit:
            fetch_limit = min(1000, limit - len(all_ohlcv))
            ohlcv = await exchange.fetch_ohlcv(symbol, tf, since=since, limit=fetch_limit)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            print(f"   {len(all_ohlcv)} velas carregadas...", end="\r")
            await asyncio.sleep(0.1)
            
        history = []
        for c in all_ohlcv:
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
        print(f"\n✅ Download concluído! {len(history)} velas recebidas.")
        await exchange.close()
        return history
    except Exception as e:
        print(f"\n❌ Erro baixando histórico: {e}")
        await exchange.close()
        return []

async def run_backtest():
    history = await download_history(SYMBOL, GRANULARITY, COUNT)
    if not history:
        return

    # RUN BACKTEST
    balance = INITIAL_BALANCE
    wins = 0
    losses = 0

    in_trade = False
    trade_direction = None

    print("🚀 Iniciando Simulação Cripto...")
    print("-" * 50)

    for i in range(len(history)):
        if i < RSI_PERIOD + CONSECUTIVE_CANDLES:
            continue

        current_candle = history[i]

        if in_trade:
            won = False
            if trade_direction == "CALL" and current_candle.direction == CandleDirection.BULLISH:
                won = True
            elif trade_direction == "PUT" and current_candle.direction == CandleDirection.BEARISH:
                won = True

            dt = datetime.fromtimestamp(current_candle.epoch).strftime('%Y-%m-%d %H:%M')
            if won:
                profit = STAKE * PAYOUT_RATE
                balance += profit
                wins += 1
                print(f"✅ WIN no {dt} | Lucro: +${profit:.2f} | Saldo: ${balance:.2f}")
            else:
                balance -= STAKE
                losses += 1
                print(f"❌ LOSS no {dt} | Prejuízo: -${STAKE:.2f} | Saldo: ${balance:.2f}")

            in_trade = False
            continue
            
        slice_history = history[:i+1]
        last_n = slice_history[-CONSECUTIVE_CANDLES:]
        
        signal = None
        if all(c.direction == CandleDirection.BEARISH for c in last_n):
            signal = "CALL"
        elif all(c.direction == CandleDirection.BULLISH for c in last_n):
            signal = "PUT"
            
        if signal:
            rsi_val = calculate_rsi(slice_history, RSI_PERIOD)
            
            if signal == "CALL" and rsi_val >= RSI_OVERSOLD:
                pass
            elif signal == "PUT" and rsi_val <= RSI_OVERBOUGHT:
                pass
            else:
                in_trade = True
                trade_direction = signal
                
    print("-" * 50)
    print("📊 RELATÓRIO FINAL DO BACKTEST")
    print(f"Ativo: {SYMBOL} | Velas: {len(history)} (M{GRANULARITY//60})")
    print(f"Estratégia: {CONSECUTIVE_CANDLES} Velas Consecutivas")
    print(f"Filtro RSI: CALL < {RSI_OVERSOLD} | PUT > {RSI_OVERBOUGHT}")
    print(f"Vitórias: {wins}")
    print(f"Derrotas: {losses}")

    total_cycles = wins + losses
    win_rate = (wins / total_cycles * 100) if total_cycles > 0 else 0
    print(f"Win Rate: {win_rate:.2f}%")

    pnl = balance - INITIAL_BALANCE
    print(f"Saldo Inicial: ${INITIAL_BALANCE:.2f}")
    print(f"Saldo Final: ${balance:.2f}")
    print(f"Lucro Líquido (PnL): ${pnl:.2f}")
    
    print("\n" + "=" * 50)
    print("📈 TESTE DOS NOVOS MOTORES (CRYPTO FUTURES)")
    print("=" * 50)
    print("Testando estratégias avançadas com Trailing Stop e Real Volume (Risco/Retorno dinâmico).")
    strategies = ["EMA+MACD", "Bollinger", "VWAP", "SMC", "SuperTrend", "Pin Bar", "ABCD", "3 Velas", "RSI+EMA", "Exaustão"]
    for s in strategies:
        res = calculate_win_rate(history, s)
        print(f"\nEstratégia: {s}")
        print(f"Sinais Gerados: {res['signals']}")
        print(f"Wins: {res['wins']} | Losses: {res['losses']} | Win Rate: {res['win_rate']}%")
        print(f"PnL USDT Estimado: ${res['pnl_usdt']}")


if __name__ == "__main__":
    asyncio.run(run_backtest())
