from sqlalchemy import Column, Integer, String, Float, JSON
from app.infrastructure.database.database import Base

class PaperTraderStateModel(Base):
    __tablename__ = "paper_trader_states"

    identity = Column(String, primary_key=True, index=True)
    account_state = Column(JSON, nullable=False)
    personality = Column(JSON, nullable=False)
    active_trades = Column(JSON, nullable=False, default=list)
