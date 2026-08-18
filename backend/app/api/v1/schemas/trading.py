from pydantic import BaseModel

class OptimizeRequest(BaseModel):
    symbol: str

class AdvancedBacktestRequest(BaseModel):
    symbol: str
    timeframe: int
    limit: int
    strategy: str

class RiskSettingsRequest(BaseModel):
    stake_initial: float
    daily_stop_loss: float
    daily_stop_gain: float
