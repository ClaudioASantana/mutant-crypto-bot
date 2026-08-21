from typing import List, Dict, Any

from app.application.queries.get_active_trades_query import GetActiveTradesQuery
from app.domain.repositories.paper_trader_repository import AbstractPaperTraderRepository

class GetActiveTradesHandler:
    """
    Handler para resolver a consulta GetActiveTradesQuery.
    No CQRS puro, handlers de consulta não disparam regras de negócio ou mutações.
    Eles apenas lêem os dados do repositório da forma mais eficiente possível para leitura.
    """
    def __init__(self, paper_trader_repo: AbstractPaperTraderRepository):
        self.paper_trader_repo = paper_trader_repo

    def handle(self, query: GetActiveTradesQuery) -> List[Dict[str, Any]]:
        state = self.paper_trader_repo.load(query.identity)
        if not state or "active_trades" not in state:
            return []
            
        trades = state["active_trades"]
        
        if query.symbol:
            trades = [t for t in trades if t.get("symbol") == query.symbol]
            
        return trades
