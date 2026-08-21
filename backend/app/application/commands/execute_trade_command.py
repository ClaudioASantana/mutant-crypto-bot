from pydantic import BaseModel, Field

class ExecuteTradeCommand(BaseModel):
    """
    Comando que carrega a intenção do usuário ou do sistema de executar um trade.
    É imutável e contém apenas os dados brutos necessários para a ação.
    """
    symbol: str
    direction: str = Field(..., description="CALL ou PUT")
    timeframe: int
    strategy: str
    entry_price: float
    atr: float
