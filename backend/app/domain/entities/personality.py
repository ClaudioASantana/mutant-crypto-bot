from pydantic import BaseModel
from typing import Dict, Any

class Personality(BaseModel):
    name: str
    strategy: str
    timeframe: int
    risk_config: Dict[str, Any]
