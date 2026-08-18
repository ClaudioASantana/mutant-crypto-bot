#!/usr/bin/env python3
"""
Script de teste para verificar o funcionamento do TradingDecisionService
após a refatoração.
"""

import sys
import os
import pandas as pd
import logging

# Configurar logging para DEBUG
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

# Adicionar o caminho do backend ao sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)

from app.domain.entities.personality import Personality
from app.domain.entities.market import Tick, AccountState, SignalType
from app.domain.services.trading_decision_service import TradingDecisionService
from app.application.services.news import NewsFilter
from app.application.services.ai_filter import AIFilter

class MockAIFilter:
    """Mock do AI Filter que sempre aprova decisões de compra (CALL)."""
    async def make_decision(self, df_candles, strategy_name):
        return {
            "decision": "BUY",
            "confidence": 0.95,
            "reason": "Mock AI Filter"
        }

def create_mock_candles():
    """Cria um DataFrame de velas mock para teste, com um padrão de Wyckoff SMC no final."""
    epochs = [1609459200 + i*60 for i in range(50)]
    base_price = 10000

    # Dados base
    opens = [base_price + i*2 for i in range(50)]
    highs = [base_price + 10 + i*2 for i in range(50)]
    lows = [base_price - 10 + i*2 for i in range(50)]
    closes = [base_price + 5 + i*2 for i in range(50)]
    volumes = [100 + i for i in range(50)]

    # Criar um padrão de Wyckoff SMC (reteste de rompimento)
    # 1. Rompimento recente do canal Donchian superior
    dcu = [base_price + 10 + i*2 - 5 for i in range(50)] # Canal Donchian superior
    closes[-3] = dcu[-3] + 10 # Rompe o canal

    # 2. Reteste e reação na última vela
    lows[-1] = dcu[-2] - 2 # Mínima toca a resistência rompida
    closes[-1] = dcu[-2] + 5 # Fechamento acima da resistência

    df = pd.DataFrame({
        'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volumes
    })
    df.index = pd.to_datetime(epochs, unit='s')

    # Adicionar Donchian Channel, ATR e Volume mock
    df['DCU_20_20'] = dcu
    df['DCL_20_20'] = [base_price - 10 + i*2 - 5 for i in range(50)]
    df['ATRr_14'] = 10.0

    return df

async def test_trading_decision():
    # Criar objetos mock
    personality = Personality(
        name="Teste_M5",
        strategy="Wyckoff_SMC",
        timeframe=300,
        risk_config={"sl_multiplier": 1.5, "tp_multiplier": 8.0}
    )

    account_state = AccountState(
        balance=1000.0,
        daily_pnl=0.0,
        highest_daily_pnl=0.0,
        daily_stop_loss=50.0,
        daily_stop_gain=50.0,
        stake_initial=10.0
    )

    df_candles = create_mock_candles()
    tick = Tick(epoch=1609459200 + 50*60, quote=10100.0, symbol="BTCUSDT")
    atr = 50.0

    # Criar os serviços com o mock
    news_filter = NewsFilter()
    mock_ai_filter = MockAIFilter()
    trading_service = TradingDecisionService(news_filter, mock_ai_filter)

    # Testar a avaliação
    decision = await trading_service.evaluate(
        personality=personality,
        account_state=account_state,
        df_candles=df_candles,
        tick=tick,
        atr=atr
    )

    if decision:
        print("✅ Decisão de trade gerada:")
        print(f"  Direção: {decision.direction}")
        assert decision.direction == SignalType.CALL, "A direção da decisão deveria ser CALL"
    else:
        print("❌ Nenhuma decisão de trade foi gerada.")

    return decision is not None

if __name__ == "__main__":
    import asyncio
    try:
        success = asyncio.run(test_trading_decision())
        if success:
            print("\n🎉 Teste de decisão de trade PASSOU!")
            sys.exit(0)
        else:
            print("\n❌ Teste de decisão de trade FALHOU (não gerou decisão).")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Teste FALHOU: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)