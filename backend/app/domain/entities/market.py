from enum import Enum
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import List

class CandleDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class Tick(BaseModel):
    epoch: int
    quote: float
    symbol: str
    volume: float = 0.0

class Candle(BaseModel):
    epoch: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    @property
    def direction(self) -> CandleDirection:
        if self.close > self.open:
            return CandleDirection.BULLISH
        elif self.close < self.open:
            return CandleDirection.BEARISH
        return CandleDirection.NEUTRAL

class SignalType(str, Enum):
    PUT = "PUT"
    CALL = "CALL"
    NONE = "NONE"

class Signal(BaseModel):
    type: SignalType
    reason: str

class RiskDecision(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"

class RiskEvaluation(BaseModel):
    decision: RiskDecision
    reason: str
    stake: float

class AccountState(BaseModel):
    balance: float
    daily_pnl: float = 0.0
    highest_daily_pnl: float = 0.0
    daily_stop_loss: float
    daily_stop_gain: float
    stake_initial: float

    def record_trade_result(self, pnl: float) -> None:
        """
        [DDD] Regra de negócio: Atualiza o estado da conta com o resultado de um trade.
        Mantém o tracking do highest_daily_pnl para o Trailing Stop Diário Global.
        """
        self.balance += pnl
        self.daily_pnl += pnl
        if self.daily_pnl > self.highest_daily_pnl:
            self.highest_daily_pnl = self.daily_pnl
