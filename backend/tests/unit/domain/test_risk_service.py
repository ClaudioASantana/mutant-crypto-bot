import pytest
from app.domain.entities.market import Signal, SignalType, AccountState
from app.domain.entities.personality import Personality, RiskProfile
from app.infrastructure.services.risk_manager import RiskManager
from app.domain.exceptions import RiskLimitExceededException

@pytest.fixture
def base_account():
    return AccountState(
        balance=10000.0,
        daily_pnl=0.0,
        highest_daily_pnl=0.0,
        daily_stop_loss=100.0,
        daily_stop_gain=200.0,
        stake_initial=50.0
    )

@pytest.fixture
def base_personality():
    profile = RiskProfile(
        daily_stop_loss=100.0,
        daily_stop_gain=200.0,
        stake_initial=50.0,
        position_sizing_mode="fixed",
        risk_percent=1.0,
        leverage=1,
        sl_multiplier=1.5,
        tp_multiplier=2.0,
        trailing_activation=1.0,
        trailing_distance=0.5,
        max_trade_duration_minutes=60
    )
    return Personality(
        id="default",
        name="Default AI",
        strategy="3 Velas",
        timeframe=300,
        description="Test",
        risk_profile=profile
    )

def test_risk_manager_approves_valid_trade(base_account, base_personality):
    manager = RiskManager()
    signal = Signal(type=SignalType.CALL, reason="Test")
    
    # Simulate positive environment
    eval_result = manager.evaluate_pre_trade_risk(signal, base_account, base_personality)
    
    assert eval_result.decision.value == "APPROVED"
    assert eval_result.stake == 50.0

def test_risk_manager_blocks_on_daily_stop_loss(base_account, base_personality, monkeypatch):
    manager = RiskManager()
    signal = Signal(type=SignalType.CALL, reason="Test")
    
    # Force account to be exactly at the stop loss
    base_account.daily_pnl = -100.0
    
    # Mocking os.getenv for global stop loss to avoid triggering it instead of personality stop loss
    monkeypatch.setenv("GLOBAL_MAX_DAILY_LOSS", "-500.0")
    
    eval_result = manager.evaluate_pre_trade_risk(signal, base_account, base_personality)
    
    assert eval_result.decision.value == "BLOCKED"
    assert "Daily dynamic stop reached" in eval_result.reason

def test_global_circuit_breaker_blocks_trade(base_account, base_personality, monkeypatch):
    manager = RiskManager()
    signal = Signal(type=SignalType.CALL, reason="Test")
    
    # Force account to be below global stop loss
    base_account.daily_pnl = -501.0
    
    monkeypatch.setenv("GLOBAL_MAX_DAILY_LOSS", "-500.0")
    
    eval_result = manager.evaluate_pre_trade_risk(signal, base_account, base_personality)
    
    assert eval_result.decision.value == "BLOCKED"
    assert "GLOBAL CIRCUIT BREAKER" in eval_result.reason
