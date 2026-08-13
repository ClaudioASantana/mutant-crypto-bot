import asyncio
import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.engines.simulator import PaperTrader
from app.engines.ai_filter import AIFilter
from app.engines.candle_builder import CandleBuilder
from app.engines.technical_analysis import apply_indicators, eval_ema_macd, eval_vwap, eval_smc, candles_to_df
from scripts.backtester import download_history
from dotenv import load_dotenv

load_dotenv()

async def run_24h_test():
    symbol = "BTC/USDT"
    print(f"🚀 Iniciando simulação das últimas 24h para {symbol} com Novas Regras...")
    
    # 24 horas em M5 = 288 velas. Vamos baixar um pouco mais para os indicadores (ex: +30)
    history = await download_history(symbol, 300, 350)
    if not history:
        print("Erro ao baixar histórico.")
        return
        
    ai_filter = AIFilter()
    # Usamos symbol "TEST_BTC" para não sobrescrever a carteira real do bot
    trader = PaperTrader(symbol="TEST_BTC", initial_balance=200.0, leverage=10)
    trader.position_sizing_mode = "gale"
    trader.max_gale = 2
    trader.stake_initial = 10.0
    trader.daily_stop_gain = 50.0
    
    # Reseta o estado para garantir que começa zerado
    trader.balance = 200.0
    trader.initial_balance = 200.0
    trader.consecutive_losses = 0
    trader.open_positions = []
    trader.history_trades = []
    
    # Strategy to test: SMC or EMA+MACD
    strategy_name = "EMA+MACD"
    
    closed_candles = []
    total_signals = 0
    approved_by_ai = 0
    
    # Simula o passar do tempo
    for i, candle in enumerate(history):
        closed_candles.append(candle)
        
        # Só começa a analisar depois de ter 30 velas de histórico para os indicadores
        if len(closed_candles) < 30:
            continue
            
        current_price = candle.close
        current_epoch = candle.epoch
        
        # Atualiza posições abertas
        finished = trader.check_positions(current_epoch, current_price)
        
        # Se não há posição aberta, procura sinal
        if len(trader.open_positions) == 0:
            df = candles_to_df(closed_candles)
            df = apply_indicators(df)
            
            sig_val = "NONE"
            if strategy_name == "EMA+MACD":
                sig_val = eval_ema_macd(df)
            elif strategy_name == "SMC":
                sig_val = eval_smc(df)
                
            if sig_val != "NONE":
                total_signals += 1
                print(f"\n[{datetime.fromtimestamp(current_epoch)}] SINAL DETECTADO: {sig_val}")
                
                # AI Filter
                is_approved = await ai_filter.evaluate_signal(df, sig_val, strategy_name)
                
                if is_approved:
                    approved_by_ai += 1
                    print(f"🤖 IA APROVOU o sinal {sig_val}!")
                    atr_val = df.iloc[-1].get("ATRr_14", current_price * 0.005)
                    
                    sl_multiplier = 1.5
                    tp_multiplier = 3.0
                    if sig_val == "CALL":
                        sl_price = current_price - (atr_val * sl_multiplier)
                        tp_price = current_price + (atr_val * tp_multiplier)
                    else:
                        sl_price = current_price + (atr_val * sl_multiplier)
                        tp_price = current_price - (atr_val * tp_multiplier)
                        
                    trader.open_trade(sig_val, 300, current_epoch, current_price, sl_price, tp_price, atr_val)
                else:
                    print(f"🤖 IA REJEITOU o sinal {sig_val}.")
                    
    print("\n" + "=" * 50)
    print("📊 RESULTADO DA SIMULAÇÃO (Últimas 24h)")
    print("=" * 50)
    print(f"Sinais Gerados: {total_signals}")
    print(f"Sinais Aprovados pela IA: {approved_by_ai}")
    print(f"Trades Finalizados: {len(trader.history_trades)}")
    
    wins = sum(1 for t in trader.history_trades if t['status'] == 'WIN')
    losses = sum(1 for t in trader.history_trades if t['status'] == 'LOSS')
    
    print(f"Vitórias: {wins} | Derrotas: {losses}")
    print(f"Balanço Final: ${trader.balance:.2f} (Iniciou com $200.00)")
    print(f"Lucro Líquido Real: ${trader.balance - 200.0:.2f}")

if __name__ == "__main__":
    asyncio.run(run_24h_test())
