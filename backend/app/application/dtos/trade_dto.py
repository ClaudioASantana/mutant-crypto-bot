from pydantic import BaseModel
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


class TradeResultDTO(BaseModel):
    """DTO que representa o resultado de um trade encerrado."""
    id: str
    direction: str
    entry_price: float
    exit_price: Optional[float] = None
    exit_epoch: Optional[int] = None
    pnl: float
    status: str
