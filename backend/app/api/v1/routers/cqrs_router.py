from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.infrastructure.database.database import get_db
from app.infrastructure.repositories.sqlalchemy_paper_trader_repository import SqlAlchemyPaperTraderRepository
from app.infrastructure.services.risk_manager import RiskManager
from app.application.queries.get_active_trades_query import GetActiveTradesQuery
from app.application.handlers.get_active_trades_handler import GetActiveTradesHandler
from app.application.commands.execute_trade_command import ExecuteTradeCommand
from app.application.handlers.execute_trade_handler import ExecuteTradeHandler
from app.domain.exceptions import DomainException

router = APIRouter(prefix="/api/cqrs", tags=["CQRS Trades"])

@router.get("/active_trades")
def get_active_trades(identity: str = "default", db: Session = Depends(get_db)):
    """
    Query CQRS: Retorna a lista de trades ativos no banco SQLite.
    """
    repo = SqlAlchemyPaperTraderRepository(db)
    handler = GetActiveTradesHandler(repo)
    query = GetActiveTradesQuery(identity=identity)
    
    trades = handler.handle(query)
    return {"status": "success", "trades": trades}

@router.post("/execute_trade")
def execute_trade(command: ExecuteTradeCommand, identity: str = "default", db: Session = Depends(get_db)):
    """
    Command CQRS: Solicita a entrada numa nova posição.
    O Handler avaliará os limites de risco e gravará no SQLite.
    """
    repo = SqlAlchemyPaperTraderRepository(db)
    risk_manager = RiskManager()
    handler = ExecuteTradeHandler(risk_manager, repo)
    
    try:
        result = handler.handle(command, identity=identity)
        return result
    except DomainException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
