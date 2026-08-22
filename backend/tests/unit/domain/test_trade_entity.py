import pytest
from pydantic import ValidationError

from app.domain.entities.trade import Trade
from app.domain.value_objects.enums import (
    TradeOutcome,
    TradeSide,
    TradeSource,
    TradeStatus,
    split_legacy_status,
)


def _open_trade(**overrides) -> Trade:
    payload = dict(
        identity="simulator_state_BTC_USDT_Aggressive_5m.json",
        symbol="BTC/USDT",
        side=TradeSide.CALL,
        entry_price=50000.0,
        entry_epoch=1_700_000_000,
        source=TradeSource.SWARM,
    )
    payload.update(overrides)
    return Trade.open_new(**payload)


def test_open_new_creates_open_trade_without_outcome():
    trade = _open_trade()

    assert trade.status is TradeStatus.OPEN
    assert trade.outcome is None
    assert trade.is_active is True
    assert trade.id  # gerado automaticamente


def test_open_new_preserves_legacy_id():
    trade = _open_trade(trade_id="ab12cd34")

    assert trade.id == "ab12cd34"


def test_close_transitions_to_closed_with_outcome():
    trade = _open_trade()

    trade.close(exit_price=51000.0, exit_epoch=1_700_000_300, pnl=12.5, outcome=TradeOutcome.WIN)

    assert trade.status is TradeStatus.CLOSED
    assert trade.outcome is TradeOutcome.WIN
    assert trade.is_active is False
    assert trade.pnl == 12.5


def test_close_twice_raises_value_error():
    trade = _open_trade()
    trade.close(exit_price=51000.0, exit_epoch=1_700_000_300, pnl=12.5, outcome=TradeOutcome.WIN)

    with pytest.raises(ValueError, match="Cannot close trade in status CLOSED"):
        trade.close(exit_price=52000.0, exit_epoch=1_700_000_600, pnl=5.0, outcome=TradeOutcome.WIN)


def test_cancel_open_trade():
    trade = _open_trade()

    trade.cancel("shutdown limpo do swarm")

    assert trade.status is TradeStatus.CANCELLED
    assert trade.outcome is None
    assert trade.close_reason == "shutdown limpo do swarm"


def test_rejected_factory_persists_reason_without_opening_position():
    trade = Trade.rejected(
        identity="default",
        symbol="BTC/USDT",
        side=TradeSide.PUT,
        entry_price=50000.0,
        entry_epoch=1_700_000_000,
        source=TradeSource.MANUAL_CQRS,
        reason="daily_stop_loss atingido",
    )

    assert trade.status is TradeStatus.REJECTED
    assert trade.outcome is None
    assert trade.close_reason == "daily_stop_loss atingido"


def test_closed_trade_without_outcome_is_invalid():
    with pytest.raises(ValidationError, match="outcome"):
        Trade(
            identity="default",
            symbol="BTC/USDT",
            side=TradeSide.CALL,
            status=TradeStatus.CLOSED,
            entry_price=50000.0,
            entry_epoch=1_700_000_000,
        )


def test_open_trade_with_outcome_is_invalid():
    with pytest.raises(ValidationError, match="outcome"):
        Trade(
            identity="default",
            symbol="BTC/USDT",
            side=TradeSide.CALL,
            status=TradeStatus.OPEN,
            outcome=TradeOutcome.WIN,
            entry_price=50000.0,
            entry_epoch=1_700_000_000,
        )


@pytest.mark.parametrize(
    "raw,expected_status,expected_outcome",
    [
        ("OPEN", TradeStatus.OPEN, None),
        ("WIN", TradeStatus.CLOSED, TradeOutcome.WIN),
        ("LOSS", TradeStatus.CLOSED, TradeOutcome.LOSS),
        ("TIME_STOP", TradeStatus.CLOSED, TradeOutcome.TIME_STOP),
    ],
)
def test_split_legacy_status_maps_simulator_vocabulary(raw, expected_status, expected_outcome):
    status, outcome = split_legacy_status(raw)

    assert status is expected_status
    assert outcome is expected_outcome


def test_split_legacy_status_rejects_unknown_value():
    with pytest.raises(ValueError, match="status legado desconhecido"):
        split_legacy_status("BOGUS")


def test_to_runtime_dict_projects_legacy_shape_for_open_trade():
    trade = _open_trade(qty=0.02, margin=10.0, sl=49000.0, tp=53000.0, atr=120.0)

    runtime = trade.to_runtime_dict()

    assert runtime["status"] == "OPEN"
    assert runtime["direction"] == "CALL"
    assert runtime["qty"] == 0.02
    assert runtime["sl"] == 49000.0
    assert runtime["tp"] == 53000.0


def test_to_runtime_dict_projects_outcome_as_status_for_closed_trade():
    trade = _open_trade()
    trade.close(exit_price=48000.0, exit_epoch=1_700_000_300, pnl=-5.0, outcome=TradeOutcome.LOSS)

    runtime = trade.to_runtime_dict()

    # Compat: a UI hoje espera WIN/LOSS/TIME_STOP no campo `status`.
    assert runtime["status"] == "LOSS"
    assert runtime["pnl"] == -5.0
    assert runtime["exit_price"] == 48000.0
