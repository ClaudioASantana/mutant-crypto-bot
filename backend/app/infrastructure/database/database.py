"""
Engine e sessão SQLAlchemy do storage canônico.

A URL vem exclusivamente de `OperationalConfig.sqlalchemy_database_url`
(fail-closed, path absoluto ancorado em `BACKEND_DIR`) — não há mais uma
variável de ambiente lida diretamente aqui, para que o path do banco tenha uma
única fonte de verdade.

O schema é gerenciado por Alembic (`backend/alembic.ini`); nenhum caminho de
produção deste módulo chama `Base.metadata.create_all`.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.operational_config import load_operational_config

_cfg = load_operational_config()

engine = create_engine(
    _cfg.sqlalchemy_database_url, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency FastAPI para injetar uma sessão por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
