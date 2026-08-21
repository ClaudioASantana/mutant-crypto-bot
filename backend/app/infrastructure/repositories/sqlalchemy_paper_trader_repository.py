from sqlalchemy.orm import Session
from app.domain.repositories.paper_trader_repository import AbstractPaperTraderRepository
from app.infrastructure.database.models import PaperTraderStateModel

from app.infrastructure.database.database import engine, Base

class SqlAlchemyPaperTraderRepository(AbstractPaperTraderRepository):
    """
    Implementação concreta usando SQLAlchemy para persistência no banco SQLite.
    Garante ACID e substitui os arquivos JSON fraturáveis.
    """
    def __init__(self, db_session: Session):
        self.db = db_session
        Base.metadata.create_all(bind=engine)

    def load(self, identity: str) -> dict | None:
        db_state = self.db.query(PaperTraderStateModel).filter(PaperTraderStateModel.identity == identity).first()
        if not db_state:
            return None
        
        return {
            "account_state": db_state.account_state,
            "personality": db_state.personality,
            "active_trades": db_state.active_trades
        }

    def save(self, identity: str, state: dict) -> None:
        db_state = self.db.query(PaperTraderStateModel).filter(PaperTraderStateModel.identity == identity).first()
        
        if not db_state:
            db_state = PaperTraderStateModel(identity=identity)
            self.db.add(db_state)
            
        db_state.account_state = state.get("account_state", {})
        db_state.personality = state.get("personality", {})
        db_state.active_trades = state.get("active_trades", [])
        
        self.db.commit()
