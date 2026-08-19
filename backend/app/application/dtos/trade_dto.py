from pydantic import BaseModel, Field
from typing import Optional

from app.domain.entities.market import SignalType


class TradingSignalDTO(BaseModel):
    """DTO que representa um sinal de trade aprovado para execução."""

    direction: SignalType
    entry_price: float
    sl_price: float
    tp_price: float
    atr: float
    reason: str
    strategy_info: str
    ai_confidence: float = 0.0
    ai_context: str = ""


class TradeDTO(BaseModel):
    """
    DTO que representa uma operação de trade completa.

    Pode representar tanto uma posição aberta quanto uma posição já encerrada,
    pois os campos de saída são opcionais.
    """

    id: str
    direction: str
    entry_price: float
    margin: float = 0.0
    qty: float = 0.0
    sl: float = Field(..., description="Preço do stop loss")
    tp: float = Field(..., description="Preço do take profit")
    entry_epoch: int
    status: str
    pnl: float = 0.0
    atr: float = 0.0
    highest_reached: float = 0.0
    lowest_reached: float = 0.0
    exit_price: Optional[float] = None
    exit_epoch: Optional[int] = None
