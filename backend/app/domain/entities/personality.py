"""
Entidade de Domínio: Personality.

Representa uma configuração de sub-bot (estratégia + timeframe + risco)
como um objeto de valor tipado. O campo `risk_profile` é tipado para
forçar validação e autocompletar em todo o código que depende dele.
"""
from pydantic import BaseModel, Field
from typing import Literal


class RiskProfile(BaseModel):
    """Configuração de risco de uma personalidade."""

    sl_multiplier: float = 1.5
    tp_multiplier: float = 8.0
    leverage: int = 10
    position_sizing_mode: Literal["fixed", "volatility_adjusted"] = "fixed"
    risk_percent: float = 2.0
    stake_initial: float = 10.0
    daily_stop_loss: float = 50.0
    daily_stop_gain: float = 50.0
    trailing_activation: float = 1.0
    trailing_distance: float = 0.5
    max_trade_duration_minutes: int = 240


class Personality(BaseModel):
    """Configuração de uma personalidade do enxame."""

    name: str
    strategy: str
    timeframe: int
    risk_profile: RiskProfile = Field(default_factory=RiskProfile)

    @property
    def risk_config(self) -> dict:
        """
        Retorna o risk_profile como dicionário para compatibilidade
        com código legado que ainda espera `risk_config`.
        """
        return self.risk_profile.model_dump()

    @risk_config.setter
    def risk_config(self, value: dict):
        """
        Permite atribuir um dicionário ao risk_profile (compatibilidade
        com carregamento via JSON).
        """
        self.risk_profile = RiskProfile(**value)