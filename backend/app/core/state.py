from typing import Dict
from app.application.services.trading_orchestrator import TradingOrchestrator
# O ConnectionManager é usado pelo main para WS, pode ficar no main ou ser movido depois

bots: Dict[str, TradingOrchestrator] = {}
watching_symbol: str = "BTC/USDT"

def set_watching_symbol(symbol: str):
    global watching_symbol
    watching_symbol = symbol
