from typing import List, Dict, Any

from app.application.queries.get_active_trades_query import GetActiveTradesQuery
from app.domain.repositories.trade_repository import AbstractTradeRepository


class GetActiveTradesHandler:
    """
    Handler para resolver a consulta GetActiveTradesQuery.

    No CQRS puro, handlers de consulta não disparam regras de negócio nem
    mutações. Eles apenas projetam o read model mais conveniente para leitura.
    """

    def __init__(self, trade_repo: AbstractTradeRepository):
        self.trade_repo = trade_repo

    def handle(self, query: GetActiveTradesQuery) -> List[Dict[str, Any]]:
        trades = self.trade_repo.list_active(query.identity, symbol=query.symbol)
        result = []
        for trade in trades:
            payload = trade.to_runtime_dict()
            payload["symbol"] = trade.symbol
            result.append(payload)
        return result
