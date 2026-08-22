import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.entities.paper_trader_state import PaperTraderState, RiskSettings
from app.infrastructure.database.models.base import Base
import app.infrastructure.database.models.paper_trader_state_model  # noqa: F401
from app.infrastructure.repositories.sqlalchemy_paper_trader_state_repository import (
    SqlAlchemyPaperTraderStateRepository,
)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def repo(session_factory):
    return SqlAlchemyPaperTraderStateRepository(session_factory=session_factory)


def test_load_missing_identity_returns_none(repo):
    assert repo.load("nobody") is None


def test_save_then_load_round_trips(repo):
    state = PaperTraderState(
        identity="bot_BTC_USDT_Sniper_5m",
        symbol="BTC/USDT",
        personality_name="Sniper",
        timeframe_seconds=300,
        balance=210.5,
        initial_balance=200.0,
        consecutive_losses=1,
        highest_daily_pnl=15.0,
        leverage=10,
        risk_settings=RiskSettings(risk_percent=3.0, position_sizing_mode="volatility_adjusted"),
    )

    repo.save(state)
    loaded = repo.load("bot_BTC_USDT_Sniper_5m")

    assert loaded is not None
    assert loaded.balance == 210.5
    assert loaded.pnl == 10.5
    assert loaded.risk_settings.risk_percent == 3.0
    assert loaded.risk_settings.position_sizing_mode == "volatility_adjusted"


def test_save_is_idempotent_upsert(repo):
    state = PaperTraderState(identity="ident-1", symbol="BTC/USDT", balance=200.0, initial_balance=200.0)
    repo.save(state)

    state.balance = 250.0
    state.consecutive_losses = 2
    repo.save(state)

    loaded = repo.load("ident-1")
    assert loaded.balance == 250.0
    assert loaded.consecutive_losses == 2
