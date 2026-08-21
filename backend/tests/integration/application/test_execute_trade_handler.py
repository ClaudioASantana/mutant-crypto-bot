import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.database import Base
from app.infrastructure.repositories.sqlalchemy_paper_trader_repository import SqlAlchemyPaperTraderRepository
from app.infrastructure.services.risk_manager import RiskManager
from app.application.commands.execute_trade_command import ExecuteTradeCommand
from app.application.handlers.execute_trade_handler import ExecuteTradeHandler
from app.domain.exceptions import RiskLimitExceededException

@pytest.fixture
def db_session():
    # Setup In-Memory SQLite para os testes de integração
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def handler(db_session):
    repo = SqlAlchemyPaperTraderRepository(db_session)
    risk_manager = RiskManager()
    return ExecuteTradeHandler(risk_manager=risk_manager, paper_trader_repo=repo)

def test_execute_trade_handler_success(handler, db_session):
    cmd = ExecuteTradeCommand(
        symbol="BTC/USDT",
        direction="CALL",
        timeframe=300,
        strategy="Test Strat",
        entry_price=60000.0,
        atr=100.0
    )
    
    result = handler.handle(cmd, identity="test_user")
    
    assert result["status"] == "SUCCESS"
    assert result["trade"]["symbol"] == "BTC/USDT"
    
    # Verifica se persistiu no DB
    repo = SqlAlchemyPaperTraderRepository(db_session)
    state = repo.load("test_user")
    assert state is not None
    assert len(state["active_trades"]) == 1
    assert state["active_trades"][0]["symbol"] == "BTC/USDT"

def test_execute_trade_handler_blocked_by_risk(handler, db_session, monkeypatch):
    # Força o bloqueio global
    monkeypatch.setenv("GLOBAL_MAX_DAILY_LOSS", "100.0") # Positive means any negative PnL blocks
    
    # Cria o estado inicial ruim
    repo = SqlAlchemyPaperTraderRepository(db_session)
    bad_state = {
        "account_state": {
            "balance": 10000.0,
            "daily_pnl": -100.0,
            "highest_daily_pnl": 0.0,
            "daily_stop_loss": 50.0,
            "daily_stop_gain": 50.0,
            "stake_initial": 10.0
        },
        "personality": {
            "id": "default",
            "name": "Tester",
            "strategy": "Strat",
            "timeframe": 300,
            "risk_profile": {
                "daily_stop_loss": 50.0,
                "daily_stop_gain": 50.0,
                "stake_initial": 10.0,
                "position_sizing_mode": "fixed",
                "risk_percent": 1.0,
                "leverage": 1,
                "sl_multiplier": 1.5,
                "tp_multiplier": 2.0,
                "trailing_activation": 1.0,
                "trailing_distance": 0.5,
                "max_trade_duration_minutes": 60
            }
        },
        "active_trades": []
    }
    repo.save("blocked_user", bad_state)
    
    cmd = ExecuteTradeCommand(
        symbol="ETH/USDT",
        direction="PUT",
        timeframe=300,
        strategy="Test Strat",
        entry_price=3000.0,
        atr=50.0
    )
    
    with pytest.raises(RiskLimitExceededException):
        handler.handle(cmd, identity="blocked_user")
