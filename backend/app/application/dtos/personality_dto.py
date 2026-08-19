"""
DTOs relacionados à entidade Personality.

Usados para transferir dados de estado e configuração de uma personalidade
entre as camadas da aplicação, principalmente para a API.
"""
from pydantic import BaseModel
from typing import List

from app.application.dtos.trade_dto import TradeDTO


class RiskSettingsDTO(BaseModel):
    """DTO para as configurações de risco de uma personalidade."""

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


class PersonalityStateDTO(BaseModel):
    """
    DTO que representa o estado completo e atual de uma personalidade.
    Agrega o saldo, PnL, trades e configurações de risco.
    """

    balance: float
    pnl: float
    pending: List[TradeDTO]
    history: List[TradeDTO]
    risk: RiskSettingsDTO
