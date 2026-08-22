import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.entities.trade import Trade
from app.domain.value_objects.enums import TradeOutcome, TradeSide, TradeSource
from app.infrastructure.database.models.base import Base
import app.infrastructure.database.models.trade_model  # noqa: F401
from app.infrastructure.repositories.sqlalchemy_trade_repository import SqlAlchemyTradeRepository


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def repo(session_factory):
    return SqlAlchemyTradeRepository(session_factory=session_factory)


def _open_trade(**overrides) -> Trade:
    payload = dict(
        identity="bot_BTC_USDT",
        symbol="BTC/USDT",
        side=TradeSide.CALL,
        entry_price=60000.0,
        entry_epoch=1000,
        source=TradeSource.SWARM,
    )
    payload.update(overrides)
    return Trade.open_new(**payload)


def test_add_then_get_by_id_round_trips(repo):
    trade = _open_trade(trade_id="abc123")

    repo.add(trade)
    fetched = repo.get_by_id("abc123")

    assert fetched is not None
    assert fetched.id == "abc123"
    assert fetched.symbol == "BTC/USDT"
    assert fetched.side is TradeSide.CALL
    assert fetched.is_active is True


def test_add_duplicate_id_raises(repo):
    trade = _open_trade(trade_id="dup1")
    repo.add(trade)

    with pytest.raises(ValueError):
        repo.add(_open_trade(trade_id="dup1"))


def test_update_missing_trade_raises(repo):
    ghost = _open_trade(trade_id="ghost")

    with pytest.raises(ValueError):
        repo.update(ghost)


def test_update_persists_close_transition(repo):
    trade = _open_trade(trade_id="close-me")
    repo.add(trade)

    trade.close(exit_price=61000.0, exit_epoch=1300, pnl=50.0, outcome=TradeOutcome.WIN)
    repo.update(trade)

    fetched = repo.get_by_id("close-me")
    assert fetched.status.value == "CLOSED"
    assert fetched.outcome is TradeOutcome.WIN
    assert fetched.pnl == 50.0


def test_list_active_filters_by_identity_and_status(repo):
    repo.add(_open_trade(trade_id="open-1", identity="ident-a"))
    other = _open_trade(trade_id="open-2", identity="ident-a")
    repo.add(other)
    repo.add(_open_trade(trade_id="open-other-identity", identity="ident-b"))

    other.close(exit_price=1.0, exit_epoch=2, pnl=0.0, outcome=TradeOutcome.LOSS)
    repo.update(other)

    active = repo.list_active("ident-a")
    assert [t.id for t in active] == ["open-1"]


def test_list_active_filters_by_symbol(repo):
    repo.add(_open_trade(trade_id="t1", identity="ident-a", symbol="BTC/USDT"))
    repo.add(_open_trade(trade_id="t2", identity="ident-a", symbol="ETH/USDT"))

    active_btc = repo.list_active("ident-a", symbol="BTC/USDT")
    assert [t.id for t in active_btc] == ["t1"]


def test_list_history_excludes_open_and_respects_limit(repo):
    for i in range(3):
        trade = _open_trade(trade_id=f"hist-{i}", identity="ident-a", entry_epoch=1000 + i)
        repo.add(trade)
        trade.close(exit_price=1.0, exit_epoch=2000 + i, pnl=1.0, outcome=TradeOutcome.WIN)
        repo.update(trade)
    repo.add(_open_trade(trade_id="still-open", identity="ident-a"))

    history = repo.list_history("ident-a", limit=2)

    assert len(history) == 2
    assert all(t.status.value != "OPEN" for t in history)
    # Mais recente primeiro (maior exit_epoch)
    assert history[0].id == "hist-2"
