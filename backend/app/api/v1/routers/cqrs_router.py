from fastapi import APIRouter, Depends, HTTPException

from app.core.operational_config import load_operational_config
from app.core.security import require_api_key
from app.infrastructure.repositories.sqlalchemy_paper_trader_state_repository import (
    SqlAlchemyPaperTraderStateRepository,
)
from app.infrastructure.repositories.sqlalchemy_trade_repository import SqlAlchemyTradeRepository
from app.infrastructure.services.risk_manager import RiskManager
from app.application.queries.get_active_trades_query import GetActiveTradesQuery
from app.application.handlers.get_active_trades_handler import GetActiveTradesHandler
from app.application.commands.execute_trade_command import ExecuteTradeCommand
from app.application.handlers.execute_trade_handler import ExecuteTradeHandler
from app.domain.exceptions import DomainException

router = APIRouter(prefix="/api/cqrs", tags=["CQRS Trades"])

# Os repositórios canônicos abrem uma sessão curta por operação via
# `SessionLocal` (default de cada construtor) — não retêm uma `Session` de
# longa duração. Não usamos `Depends(get_db)` aqui de propósito: envolver a
# sessão de request num `with` dentro do repositório a fecharia cedo demais
# se o handler fizer mais de uma operação na mesma request.


@router.get("/active_trades")
def get_active_trades(identity: str = "default"):
    """
    Query CQRS: Retorna a lista de trades ativos no banco canônico SQLite.
    """
    repo = SqlAlchemyTradeRepository()
    handler = GetActiveTradesHandler(repo)
    query = GetActiveTradesQuery(identity=identity)

    trades = handler.handle(query)
    return {"status": "success", "trades": trades}


@router.post("/execute_trade")
def execute_trade(
    command: ExecuteTradeCommand,
    identity: str = "default",
    _auth: None = Depends(require_api_key),
):
    """
    Command CQRS: Solicita a entrada numa nova posição.
    O Handler avalia os limites de risco e grava um trade canônico em `trades`.
    """
    cfg = load_operational_config()
    if not cfg.allow_manual_trade:
        raise HTTPException(
            status_code=403,
            detail="Execução manual desativada pela configuração operacional.",
        )

    state_repo = SqlAlchemyPaperTraderStateRepository()
    trade_repo = SqlAlchemyTradeRepository()
    risk_manager = RiskManager()
    handler = ExecuteTradeHandler(risk_manager, state_repo, trade_repo)

    try:
        result = handler.handle(command, identity=identity)
        return result
    except DomainException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
