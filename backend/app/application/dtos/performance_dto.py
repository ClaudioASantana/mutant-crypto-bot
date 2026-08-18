from pydantic import BaseModel
from typing import Optional


class PersonalityPerformanceDTO(BaseModel):
    personality_name: str
    symbol: str
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    trades_count: int = 0
    consecutive_losses: int = 0
    win_rate: float = 0.0
    fitness: float = 0.0
    last_trade_epoch: Optional[int] = None
    last_update: Optional[float] = None
