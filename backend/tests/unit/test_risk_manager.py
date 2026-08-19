"""
Testes unitários para o RiskManager.

Garante que a lógica de avaliação e cálculo de risco esteja correta.
"""
import pytest
from unittest.mock import Mock

from app.domain.entities.market import AccountState, RiskEvaluation, RiskDecision, Signal, SignalType
from app.domain.entities.personality import Personality, RiskProfile
from app.infrastructure.services.risk_manager import RiskManager


@pytest.fixture
def risk_manager():
    """Fixture que retorna uma instância de RiskManager."""
    return RiskManager()


@pytest.fixture
def sample_personality():
    """Fixture que cria uma personalidade de exemplo."""
    return Personality(
        name="Teste_M5",
        strategy="Wyckoff_SMC",
        timeframe=300,
        risk_profile=RiskProfile(
            sl_multiplier=1.5,
            tp_multiplier=8.0,
            leverage=10,
            position_sizing_mode="fixed",
            risk_percent=2.0,
            stake_initial=10.0,
            daily_stop_loss=50.0,
            daily_stop_gain=50.0,
            trailing_activation=1.0,
            trailing_distance=0.5,
            max_trade_duration_minutes=240
        )
    )


@pytest.fixture
def sample_account_state():
    """Fixture que cria um estado de conta de exemplo."""
    return AccountState(
        balance=1000.0,
        daily_pnl=0.0,
        highest_daily_pnl=0.0,
        daily_stop_loss=50.0,
        daily_stop_gain=50.0,
        stake_initial=10.0
    )


def test_evaluate_pre_trade_risk_approved(risk_manager, sample_personality, sample_account_state):
    """Deve aprovar um trade se os limites de risco forem respeitados."""
    signal = Signal(type=SignalType.CALL, reason="Test signal")

    evaluation = risk_manager.evaluate_pre_trade_risk(signal, sample_account_state, sample_personality)

    assert isinstance(evaluation, RiskEvaluation)
    assert evaluation.decision == RiskDecision.APPROVED
    assert evaluation.stake == sample_personality.risk_profile.stake_initial


def test_evaluate_pre_trade_risk_blocked_by_dynamic_stop(risk_manager, sample_personality, sample_account_state):
    """Deve bloquear um trade se o stop dinâmico for atingido."""
    signal = Signal(type=SignalType.CALL, reason="Test signal")
    # Simula uma conta com PnL negativo que atinge o stop loss
    sample_account_state.daily_pnl = -60.0

    evaluation = risk_manager.evaluate_pre_trade_risk(signal, sample_account_state, sample_personality)

    assert isinstance(evaluation, RiskEvaluation)
    assert evaluation.decision == RiskDecision.BLOCKED
    assert "Daily dynamic stop reached" in evaluation.reason


def test_calculate_position_sizing_fixed(risk_manager, sample_personality):
    """Deve calcular o tamanho da posição corretamente para modo 'fixed'."""
    sample_personality.risk_profile.position_sizing_mode = "fixed"
    sample_personality.risk_profile.risk_percent = 2.0
    current_balance = 1000.0
    current_price = 50000.0
    atr = 500.0
    symbol = "BTC/USDT"

    result = risk_manager.calculate_position_sizing(sample_personality, current_balance, current_price, atr, symbol)

    expected_margin = current_balance * (sample_personality.risk_profile.risk_percent / 100.0)
    expected_qty = (expected_margin * sample_personality.risk_profile.leverage) / current_price

    assert result["margin_usdt"] == expected_margin
    assert result["qty"] == expected_qty


def test_calculate_position_sizing_volatility_adjusted(risk_manager, sample_personality):
    """Deve calcular o tamanho da posição corretamente para modo 'volatility_adjusted'."""
    sample_personality.risk_profile.position_sizing_mode = "volatility_adjusted"
    sample_personality.risk_profile.stake_initial = 10.0
    current_balance = 1000.0
    current_price = 50000.0
    atr = 500.0
    symbol = "BTC/USDT" # BTC

    result = risk_manager.calculate_position_sizing(sample_personality, current_balance, current_price, atr, symbol)

    volatility_index = 1.10 # Para BTC
    expected_margin = sample_personality.risk_profile.stake_initial / volatility_index
    expected_qty = (expected_margin * sample_personality.risk_profile.leverage) / current_price

    assert result["margin_usdt"] == expected_margin
    assert result["qty"] == expected_qty


def test_calculate_sl_tp(risk_manager, sample_personality):
    """Deve calcular os preços de SL e TP corretamente."""
    entry_price = 50000.0
    atr = 500.0
    direction = SignalType.CALL

    result = risk_manager.calculate_sl_tp(sample_personality, entry_price, atr, direction)

    expected_sl = entry_price - (atr * sample_personality.risk_profile.sl_multiplier)
    expected_tp = entry_price + (atr * sample_personality.risk_profile.tp_multiplier)

    assert result["sl_price"] == expected_sl
    assert result["tp_price"] == expected_tp


def test_manage_trailing_stop_long(risk_manager, sample_personality):
    """Deve mover o SL para cima em uma posição LONG se as condições forem atendidas."""
    trade = {
        "direction": "CALL",
        "entry_price": 50000.0,
        "sl": 49500.0, # SL inicial
        "atr": 500.0,
        "highest_reached": 50600.0 # Preço mais alto atingido
    }
    current_price = 50700.0 # Preço atual acima do mais alto

    # Ativa trailing stop (highest_reached >= entry_price + atr * trailing_activation)
    # 50600 >= 50000 + 500 * 1.0 = 50500 -> True

    original_sl = trade["sl"]

    updated_trade = risk_manager.manage_trailing_stop(trade, current_price, sample_personality)

    # Novo SL = highest_reached - (atr * trailing_distance)
    # Novo SL = 50700 - (500 * 0.5) = 50700 - 250 = 50450
    expected_new_sl = 50700 - (500 * sample_personality.risk_profile.trailing_distance)

    assert updated_trade["sl"] == expected_new_sl
    assert updated_trade["sl"] > original_sl # SL deve ter subido


def test_check_time_stop_hit(risk_manager, sample_personality):
    """Deve retornar True se o limite de tempo for atingido."""
    trade = {
        "entry_epoch": 1000000
    }
    current_epoch = 1000000 + (sample_personality.risk_profile.max_trade_duration_minutes * 60) + 1

    hit = risk_manager.check_time_stop(trade, current_epoch, sample_personality)

    assert hit is True


def test_check_time_stop_not_hit(risk_manager, sample_personality):
    """Deve retornar False se o limite de tempo não for atingido."""
    trade = {
        "entry_epoch": 1000000
    }
    current_epoch = 1000000 + (sample_personality.risk_profile.max_trade_duration_minutes * 60) - 1

    hit = risk_manager.check_time_stop(trade, current_epoch, sample_personality)

    assert hit is False