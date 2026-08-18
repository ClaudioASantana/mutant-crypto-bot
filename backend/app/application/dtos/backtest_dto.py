"""
Data Transfer Objects da camada Application.

Clean Architecture: DTOs são usados para transferir dados entre camadas
sem criar dependências diretas. A camada de aplicação define seus próprios
DTOs em vez de reutilizar schemas da API.
"""
from pydantic import BaseModel


class BacktestRequestDTO(BaseModel):
    """DTO para requisição de backtest avançado."""
    symbol: str
    timeframe: int
    limit: int
    strategy: str
