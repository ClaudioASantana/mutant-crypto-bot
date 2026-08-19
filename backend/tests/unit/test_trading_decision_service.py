import pytest
import pandas as pd
from unittest.mock import patch

from app.domain.entities.personality import Personality, RiskProfile
from app.domain.entities.market import Tick, AccountState, SignalType
from app.domain.services.trading_decision_service import TradingDecisionService
from app.domain.services.news_filter_interface import AbstractNewsFilter
from app.domain.services.ia_filter_interface import AbstractAIFilter
from app.domain.services.strategy_registry import StrategyRegistry
from tests.unit.mock_risk_manager import MockRiskManager # Importar o mock



class MockNewsFilter(AbstractNewsFilter):
    def __init__(self, safe: bool = True):
        self.safe = safe

    def check_safety(self, epoch: int):
        return {"safe": self.safe, "reason": "mock"}


class MockAIFilter(AbstractAIFilter):
    def __init__(self, decision: str = "BUY", confidence: float = 0.95):
        self.decision = decision
        self.confidence = confidence

    async def make_decision(self, df_candles, strategy_name):
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reason": "Mock AI Filter"
        }



@pytest.fixture
def mock_candles():
    """Cria um DataFrame de velas mock para teste."""
    epochs = [1609459200 + i * 60 for i in range(50)]
    base_price = 10000

    opens = [base_price + i * 2 for i in range(50)]
    highs = [base_price + 10 + i * 2 for i in range(50)]
    lows = [base_price - 10 + i * 2 for i in range(50)]
    closes = [base_price + 5 + i * 2 for i in range(50)]
    volumes = [100 + i for i in range(50)]

    dcu = [base_price + 10 + i * 2 - 5 for i in range(50)]
    closes[-3] = dcu[-3] + 10
    lows[-1] = dcu[-2] - 2
    closes[-1] = dcu[-2] + 5

    df = pd.DataFrame({
        'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volumes
    })
    df.index = pd.to_datetime(epochs, unit='s')
    # df['DCU_20_20'] = dcu
    # df['DCL_20_20'] = [base_price - 10 + i * 2 - 5 for i in range(50)]
    # df['ATRr_14'] = 10.0

    # Aplicar indicadores para simular o comportamento real
    from app.application.services.technical_analysis import apply_indicators
    df_with_indicators = apply_indicators(df)
    df_with_indicators['ATRr_14'] = 10.0 # Mock ATR, pois é usado diretamente no serviço

    return df_with_indicators


@pytest.fixture
def personality():
    return Personality(
        name="Teste_M5",
        strategy="Wyckoff_SMC",
        timeframe=300,
        risk_profile=RiskProfile(sl_multiplier=1.5, tp_multiplier=8.0)
    )


@pytest.fixture
def account_state():
    return AccountState(
        balance=1000.0,
        daily_pnl=0.0,
        highest_daily_pnl=0.0,
        daily_stop_loss=50.0,
        daily_stop_gain=50.0,
        stake_initial=10.0
    )


@pytest.fixture
def tick():
    return Tick(epoch=1609459200 + 50 * 60, quote=10100.0, symbol="BTCUSDT")


@pytest.mark.asyncio
async def test_trading_decision_call_success(mock_candles, personality, account_state, tick):
    # Mock da estratégia para sempre retornar CALL
    with patch.dict(StrategyRegistry._strategies, {"Wyckoff_SMC": lambda df: "CALL"}):
        service = TradingDecisionService(
            news_filter=MockNewsFilter(safe=True),
            ai_filter=MockAIFilter(decision="BUY", confidence=0.95),
            risk_manager=MockRiskManager()
        )

        decision = await service.evaluate(
            personality=personality,
            account_state=account_state,
            df_candles=mock_candles,
            tick=tick,
            atr=50.0
        )

        assert decision is not None
        assert decision.direction == SignalType.CALL
        assert decision.entry_price == tick.quote
        assert decision.sl_price == pytest.approx(tick.quote - 50.0 * 1.5)
        assert decision.tp_price == pytest.approx(tick.quote + 50.0 * 8.0)
        assert decision.reason == "Mock AI Filter"


@pytest.mark.asyncio
async def test_trading_decision_put_success(mock_candles, personality, account_state, tick):
    # Mock da estratégia para sempre retornar PUT
    with patch.dict(StrategyRegistry._strategies, {"Wyckoff_SMC": lambda df: "PUT"}):
        service = TradingDecisionService(
            news_filter=MockNewsFilter(safe=True),
            ai_filter=MockAIFilter(decision="SELL", confidence=0.95),
            risk_manager=MockRiskManager()
        )

        decision = await service.evaluate(
            personality=personality,
            account_state=account_state,
            df_candles=mock_candles,
            tick=tick,
            atr=50.0
        )

        assert decision is not None
        assert decision.direction == SignalType.PUT
        assert decision.sl_price == pytest.approx(tick.quote + 50.0 * 1.5)
        assert decision.tp_price == pytest.approx(tick.quote - 50.0 * 8.0)


@pytest.mark.asyncio
async def test_trading_decision_blocked_by_news(mock_candles, personality, account_state, tick):
    service = TradingDecisionService(
        news_filter=MockNewsFilter(safe=False),
        ai_filter=MockAIFilter(decision="BUY", confidence=0.95),
        risk_manager=MockRiskManager()
    )

    decision = await service.evaluate(
        personality=personality,
        account_state=account_state,
        df_candles=mock_candles,
        tick=tick,
        atr=50.0
    )

    assert decision is None


@pytest.mark.asyncio
async def test_trading_decision_blocked_by_ai_filter(mock_candles, personality, account_state, tick):
    service = TradingDecisionService(
        news_filter=MockNewsFilter(safe=True),
        ai_filter=MockAIFilter(decision="HOLD", confidence=0.95),
        risk_manager=MockRiskManager()
    )

    decision = await service.evaluate(
        personality=personality,
        account_state=account_state,
        df_candles=mock_candles,
        tick=tick,
        atr=50.0
    )

    assert decision is None


@pytest.mark.asyncio
async def test_trading_decision_blocked_by_risk(mock_candles, personality, tick):
    account_state_blocked = AccountState(
        balance=1000.0,
        daily_pnl=-60.0,
        highest_daily_pnl=0.0,
        daily_stop_loss=50.0,
        daily_stop_gain=50.0,
        stake_initial=10.0
    )

    service = TradingDecisionService(
        news_filter=MockNewsFilter(safe=True),
        ai_filter=MockAIFilter(decision="BUY", confidence=0.95),
        risk_manager=MockRiskManager()
    )

    decision = await service.evaluate(
        personality=personality,
        account_state=account_state_blocked,
        df_candles=mock_candles,
        tick=tick,
        atr=50.0
    )

    assert decision is None


@pytest.mark.asyncio
async def test_trading_decision_no_signal(mock_candles, personality, account_state, tick):
    # Remove os indicadores necessários para o sinal
    mock_candles = mock_candles.drop(columns=['DCU_20_20', 'DCL_20_20'])

    service = TradingDecisionService(
        news_filter=MockNewsFilter(safe=True),
        ai_filter=MockAIFilter(decision="BUY", confidence=0.95),
        risk_manager=MockRiskManager()
    )

    decision = await service.evaluate(
        personality=personality,
        account_state=account_state,
        df_candles=mock_candles,
        tick=tick,
        atr=50.0
    )

    assert decision is None
