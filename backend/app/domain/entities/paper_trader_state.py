"""
Snapshot operacional tipado de uma conta de simulação.

Antes isto era um `dict` livre que trafegava por um port genérico, o que permitiu
dois shapes incompatíveis (simulador e CQRS) conviverem sob o mesmo contrato.
Aqui o snapshot guarda apenas o que é conta/risco; as posições vivem em `Trade`.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class RiskSettings(BaseModel):
    """Limites de risco efetivos da conta, já resolvidos para o runtime."""

    daily_stop_loss: float = 50.0
    daily_stop_gain: float = 50.0
    stake_initial: float = 10.0
    trailing_activation: float = 1.0
    trailing_distance: float = 0.5
    position_sizing_mode: Literal["fixed", "volatility_adjusted"] = "fixed"
    risk_percent: float = 2.0
    max_trade_duration_minutes: int = 240


class PaperTraderState(BaseModel):
    """Estado de conta persistido por `identity`."""

    identity: str
    symbol: str
    personality_name: Optional[str] = None
    timeframe_seconds: Optional[int] = None

    balance: float
    initial_balance: float
    consecutive_losses: int = 0
    highest_daily_pnl: float = 0.0
    leverage: int = 10

    risk_settings: RiskSettings = Field(default_factory=RiskSettings)

    @property
    def pnl(self) -> float:
        """Lucro/prejuízo acumulado desde o saldo inicial."""
        return round(self.balance - self.initial_balance, 2)

    @classmethod
    def from_legacy_dict(
        cls,
        identity: str,
        symbol: str,
        payload: dict[str, Any],
        *,
        leverage: int = 10,
    ) -> "PaperTraderState":
        """
        Reconstrói o snapshot a partir do shape JSON legado do `PaperTrader`.

        Campos ausentes caem nos defaults de `RiskSettings` — os snapshots antigos
        foram gravados por versões diferentes do simulador e nem todos têm tudo.
        """
        raw_risk = payload.get("risk_settings") or {}
        known = set(RiskSettings.model_fields.keys())
        risk = RiskSettings(**{k: v for k, v in raw_risk.items() if k in known})

        initial_balance = float(payload.get("initial_balance", payload.get("balance", 0.0)))
        return cls(
            identity=identity,
            symbol=symbol,
            balance=float(payload.get("balance", initial_balance)),
            initial_balance=initial_balance,
            consecutive_losses=int(payload.get("consecutive_losses", 0)),
            highest_daily_pnl=float(payload.get("highest_daily_pnl", 0.0)),
            leverage=int(payload.get("leverage", leverage)),
            risk_settings=risk,
        )
