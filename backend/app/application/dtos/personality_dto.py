from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class RiskSettingsDTO(BaseModel):
    consecutive_losses: int
    next_margin: float
    stop_loss: float
    stop_gain: float
    leverage: int
    trailing_activation: float
    trailing_distance: float
    position_sizing_mode: str
    risk_percent: float
    max_trade_duration_minutes: int

class TradeDTO(BaseModel):
    id: str
    direction: str
    entry_price: float
    margin: float
    qty: float
    sl: float
    tp: float
    entry_epoch: int
    status: str
    pnl: float
    atr: float
    highest_reached: float
    lowest_reached: float
    exit_price: Optional[float] = None
    exit_epoch: Optional[int] = None

class PersonalityStateDTO(BaseModel):
    balance: float
    pnl: float
    pending: List[TradeDTO]
    history: List[TradeDTO]
    risk: RiskSettingsDTO
