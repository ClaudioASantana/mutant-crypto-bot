"""
Modelo SQLAlchemy do snapshot operacional (`PaperTraderState`).

Diferente de `TradeModel`, a chave é a `identity` lógica — não há um UUID
próprio, então este modelo não herda `BaseModel` (que impõe `id`). Os campos de
`RiskSettings` são achatados em colunas (Value Object flattening), como no
baseline, em vez de um blob JSON opaco.
"""

from sqlalchemy import Column, Float, Integer, String

from .base import Base, TimestampMixin


class PaperTraderStateModel(TimestampMixin, Base):
    __tablename__ = "paper_trader_states"

    identity = Column(String(160), primary_key=True)
    symbol = Column(String(30), nullable=False)
    personality_name = Column(String(80), nullable=True)
    timeframe_seconds = Column(Integer, nullable=True)

    balance = Column(Float, nullable=False)
    initial_balance = Column(Float, nullable=False)
    consecutive_losses = Column(Integer, nullable=False, default=0)
    highest_daily_pnl = Column(Float, nullable=False, default=0.0)
    leverage = Column(Integer, nullable=False, default=10)

    # RiskSettings achatado
    daily_stop_loss = Column(Float, nullable=False, default=50.0)
    daily_stop_gain = Column(Float, nullable=False, default=50.0)
    stake_initial = Column(Float, nullable=False, default=10.0)
    trailing_activation = Column(Float, nullable=False, default=1.0)
    trailing_distance = Column(Float, nullable=False, default=0.5)
    position_sizing_mode = Column(String(30), nullable=False, default="fixed")
    risk_percent = Column(Float, nullable=False, default=2.0)
    max_trade_duration_minutes = Column(Integer, nullable=False, default=240)
