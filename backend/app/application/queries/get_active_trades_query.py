from pydantic import BaseModel
from typing import Optional

class GetActiveTradesQuery(BaseModel):
    """
    Query (CQRS) que expressa a intenção de buscar os trades ativos no momento.
    """
    identity: str = "default"
    symbol: Optional[str] = None
