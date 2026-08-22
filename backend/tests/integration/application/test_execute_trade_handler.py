import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models.base import Base
import app.infrastructure.database.models.trade_model  # noqa: F401
import app.infrastructure.database.models.paper_trader_state_model  # noqa: F401
from app.infrastructure.repositories.sqlalchemy_paper_trader_state_repository import (
    SqlAlchemyPaperTraderStateRepository,
)
from app.infrastructure.repositories.sqlalchemy_trade_repository import SqlAlchemyTradeRepository
from app.infrastructure.services.risk_manager import RiskManager
from app.application.commands.execute_trade_command import ExecuteTradeCommand
from app.application.handlers.execute_trade_handler import ExecuteTradeHandler
from app.domain.entities.paper_trader_state import PaperTraderState, RiskSettings
from app.domain.exceptions import RiskLimitExceededException


@pytest.fixture
def session_factory():
    # Setup In-Memory SQLite para os testes de integração. `StaticPool` faz
    # com que múltiplas sessões (state_repo e trade_repo abrem cada uma a
    # sua) compartilhem a mesma conexão em memória.
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def state_repo(session_factory):
    return SqlAlchemyPaperTraderStateRepository(session_factory=session_factory)


@pytest.fixture
def trade_repo(session_factory):
    return SqlAlchemyTradeRepository(session_factory=session_factory)


@pytest.fixture
def handler(state_repo, trade_repo):
    risk_manager = RiskManager()
    return ExecuteTradeHandler(
        risk_manager=risk_manager,
        paper_trader_state_repo=state_repo,
        trade_repo=trade_repo,
    )


def test_execute_trade_handler_success(handler, trade_repo):
    cmd = ExecuteTradeCommand(
        symbol="BTC/USDT",
        direction="CALL",
        timeframe=300,
        strategy="Test Strat",
        entry_price=60000.0,
        atr=100.0,
    )

    result = handler.handle(cmd, identity="test_user")

    assert result["status"] == "SUCCESS"
    assert result["trade"]["symbol"] == "BTC/USDT"

    # Verifica se persistiu como Trade canônico com source=MANUAL_CQRS
    active = trade_repo.list_active("test_user")
    assert len(active) == 1
    assert active[0].symbol == "BTC/USDT"
    assert active[0].source.value == "MANUAL_CQRS"


def test_execute_trade_handler_blocked_by_risk(handler, state_repo, monkeypatch):
    # Força o bloqueio global
    monkeypatch.setenv("GLOBAL_MAX_DAILY_LOSS", "100.0")  # Positive means any negative PnL blocks

    # Cria o estado inicial ruim: saldo já abaixo do inicial o suficiente
    # para que `daily_pnl` (balance - initial_balance) dispare o circuit breaker.
    bad_state = PaperTraderState(
        identity="blocked_user",
        symbol="ETH/USDT",
        balance=9900.0,
        initial_balance=10000.0,
        risk_settings=RiskSettings(
            daily_stop_loss=50.0,
            daily_stop_gain=50.0,
            stake_initial=10.0,
        ),
    )
    state_repo.save(bad_state)

    cmd = ExecuteTradeCommand(
        symbol="ETH/USDT",
        direction="PUT",
        timeframe=300,
        strategy="Test Strat",
        entry_price=3000.0,
        atr=50.0,
    )

    with pytest.raises(RiskLimitExceededException):
        handler.handle(cmd, identity="blocked_user")
