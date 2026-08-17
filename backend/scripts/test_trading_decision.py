#!/usr/bin/env python3
"""
Script de teste para verificar o funcionamento do TradingDecisionService
após a refatoração.
"""

import sys
import os
import pandas as pd

# Adicionar o caminho do backend ao sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)

from app.domain.entities.personality import Personality
from app.domain.entities.market import Tick, AccountState, SignalType
from app.domain.services.trading_decision_service import TradingDecisionService
from app.application.services.news import NewsFilter
from app.application.services.ai_filter import AIFilter

class MockAIFilter(AIFilter):
    """Mock do AI Filter que sempre aprova decisões de compra (CALL)."""
    async def make_decision(self, df_candles, strategy_name):
        return {
            "decision": "BUY",
            "confidence": 0.95,
            "reason": "Mock AI Filter"
        }

def create_mock_candles():
    """Cria um DataFrame de velas mock para teste."""
    # Criar 50 velas de exemplo com um padrão de 3 velas bullish no final
    epochs = [1609459200 + i*60 for i in range(50)]
    opens = [10000 + i*2 for i in range(50)]
    highs = [10010 + i*2 for i in range(50)]
    lows = [9990 + i*2 for i in range(50)]
    closes = [10005 + i*2 for i in range(50)]

    # Modificar as últimas 3 velas para formar um padrão de 3 velas bullish
    closes[-3] = opens[-3] - 50
    lows[-3] = closes[-3] - 10
    opens[-2] = closes[-3]
    closes[-2] = opens[-2] + 10
    highs[-2] = opens[-2] + 20
    lows[-2] = opens[-2] - 20
    opens[-1] = closes[-2]
    closes[-1] = opens[-1] + 80
    highs[-1] = closes[-1] + 10
    lows[-1] = opens[-1] - 10

    df = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': closes})
    df.index = pd.to_datetime(epochs, unit='s')
    df['ATRr_14'] = 50.0

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
    # A avaliação do AI filter agora é assíncrona, então precisamos de um loop de eventos
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