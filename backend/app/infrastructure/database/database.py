import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Por padrão salva no diretório raiz do backend
DB_PATH = os.getenv("SQLITE_DB_PATH", "sqlite:///./crypto_bot.db")

engine = create_engine(
    DB_PATH, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency para injetar sessões do banco de dados no FastAPI ou handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
