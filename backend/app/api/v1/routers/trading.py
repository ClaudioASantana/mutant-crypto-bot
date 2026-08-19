"""
Router de API para operações de trading.

Clean Architecture: esta é a camada de APRESENTAÇÃO (HTTP/controllers).
A lógica de negócio vive em app/domain/services e app/application/services.
As rotas aqui apenas orquestram a chamada às camadas internas e formatam a resposta.
"""
import logging
import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.state import bots, watching_symbol
from app.api.v1.schemas.trading import (
    AdvancedBacktestRequest, OptimizeRequest, RiskSettingsRequest
)
from app.application.dtos.backtest_dto import BacktestRequestDTO
# Importa os novos serviços de aplicação
from app.application.services.optimization_service import OptimizationService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status")
def get_status():
    if watching_symbol not in bots:
        return {"status": "running_swarm", "bots_active": len(bots)}

    b = bots[watching_symbol]

    # Collect states from all personalities using DTOs
    personalities_states = {}
    for p_name, trader in b.paper_traders.items():
        personality_state_dto = b._build_personality_state_dto(trader)
        # Convert back to dictionary for API response
        personalities_states[p_name] = personality_state_dto.dict()

    # Get the builder for the first personality's timeframe (for backward compatibility)
    first_personality = b.personalities.get(next(iter(b.personalities))) if b.personalities else None
    current_candle = None
    closed_candles_count = 0
    if first_personality:
        builder = b.get_builder_for_timeframe(first_personality.timeframe)
        if builder:
            current_candle = builder.current_candle
            closed_candles_count = len(builder.closed_candles)

    return {
        "status": "running",
        "watched_symbol": watching_symbol,
        "current_candle": current_candle,
        "closed_candles_count": closed_candles_count,
        "personalities": personalities_states,
        "auto_optimize": b.auto_optimize,
        "news_status": b.news_filter.check_safety(int(time.time()))
    }

@router.get("/portfolio")
def get_portfolio():
    # Retorna o saldo global somado de todos os bots e todas as suas personalidades
    total_balance = 0.0
    total_pnl = 0.0

    for bot in bots.values():
        for trader in bot.paper_traders.values():
            total_balance += trader.balance
            total_pnl += trader.get_pnl()

    return {
        "total_balance": total_balance,
        "total_pnl": total_pnl,
        "bots_count": len(bots)
    }

@router.get("/api/chart_history")
def get_chart_history(symbol: str):
    history_payload = []
    if symbol in bots:
        b = bots[symbol]
        # Use the timeframe of the first personality for chart history
        first_personality = b.personalities.get(next(iter(b.personalities))) if b.personalities else None
        if first_personality:
            active_b = b.get_builder_for_timeframe(first_personality.timeframe)
            seen_times = set()
            for c in sorted(active_b.closed_candles, key=lambda x: x.epoch):
                if c.epoch not in seen_times:
                    history_payload.append({
                        "time": c.epoch,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close
                    })
                    seen_times.add(c.epoch)

    return {"data": history_payload[-200:]}

@router.post("/api/optimize")
async def api_optimize(req: OptimizeRequest):
    # Delega a lógica complexa para o serviço de aplicação
    optimization_service = OptimizationService()
    return await optimization_service.execute(req.symbol)

@router.post("/api/backtest_advanced")
async def api_backtest_advanced(req: AdvancedBacktestRequest):
    # Converte schema da API para DTO da camada Application
    dto = BacktestRequestDTO(
        symbol=req.symbol,
        timeframe=req.timeframe,
        limit=req.limit,
        strategy=req.strategy
    )
    # Usa o backtest_service injetado pelo main.py
    return await router.backtest_service.execute(dto)

@router.get("/api/risk_settings")
def get_risk_settings():
    if bots:
        # Pega o primeiro bot e a primeira personalidade para compatibilidade com o frontend
        b = list(bots.values())[0]
        if b.personalities:
            first_personality_name = next(iter(b.personalities.keys()))
            first_trader = b.paper_traders[first_personality_name]
            return {
                "stake_initial": first_trader.stake_initial,
                "daily_stop_loss": first_trader.daily_stop_loss,
                "daily_stop_gain": first_trader.daily_stop_gain
            }
    return {
        "stake_initial": 10.0,
        "daily_stop_loss": 50.0,
        "daily_stop_gain": 50.0
    }

@router.post("/api/risk_settings")
def set_risk_settings(req: RiskSettingsRequest):
    settings = {
        "stake_initial": req.stake_initial,
        "daily_stop_loss": req.daily_stop_loss,
        "daily_stop_gain": req.daily_stop_gain
    }
    for bot in bots.values():
        for trader in bot.paper_traders.values():
            trader.stake_initial = req.stake_initial
            trader.daily_stop_loss = req.daily_stop_loss
            trader.daily_stop_gain = req.daily_stop_gain
            trader.save_state()
    return {"status": "ok", "settings": settings}