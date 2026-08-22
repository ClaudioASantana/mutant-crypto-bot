"""
Modelo SQLAlchemy do agregado `Trade`: ciclo de vida + journal operacional unificado.

Substitui os três shapes paralelos (snapshot do PaperTrader, blob do CQRS,
linha do `journal.db`). `status`/`outcome` são colunas `String` (não `sa.Enum`)
para não exigir `ALTER TYPE` a cada novo valor de vocabulário.
"""

from sqlalchemy import Column, Float, Integer, String, Text

from .base import BaseModel


class TradeModel(BaseModel):
    __tablename__ = "trades"

    # Identidade lógica — `identity` é a chave legada (nome do arquivo de
    # snapshot); os campos decompostos preparam a aposentadoria dela.
    identity = Column(String(160), nullable=False, index=True)
    symbol = Column(String(30), nullable=False, index=True)
    personality_name = Column(String(80), nullable=True)
    timeframe_seconds = Column(Integer, nullable=True)

    side = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="OPEN", index=True)
    outcome = Column(String(20), nullable=True)
    source = Column(String(30), nullable=False, default="UNKNOWN")

    entry_price = Column(Float, nullable=False)
    entry_epoch = Column(Integer, nullable=False, index=True)
    qty = Column(Float, nullable=False, default=0.0)
    margin = Column(Float, nullable=False, default=0.0)
    leverage = Column(Integer, nullable=False, default=1)
    sl = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)

    exit_price = Column(Float, nullable=True)
    exit_epoch = Column(Integer, nullable=True)
    pnl = Column(Float, nullable=False, default=0.0)
    close_reason = Column(Text, nullable=True)

    atr = Column(Float, nullable=True)
    rsi = Column(Float, nullable=True)
    highest_reached = Column(Float, nullable=True)
    lowest_reached = Column(Float, nullable=True)

    strategy = Column(String(80), nullable=True)
    ai_reason = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_context = Column(Text, nullable=True)

    notes = Column(Text, nullable=True)
