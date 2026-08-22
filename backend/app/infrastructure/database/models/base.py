"""
Base declarativa e mixins compartilhados pelos modelos SQLAlchemy.

Segue o mesmo padrão do baseline `mutante-opcoes-acoes`: `Base` isolada em
`models/base.py` (para o `env.py` do Alembic importar sem puxar o resto da
infraestrutura) e um mixin de timestamps reutilizável.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """`created_at`/`updated_at` padrão, sem impor uma chave primária própria."""

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BaseModel(TimestampMixin, Base):
    """Base para agregados sem chave natural: gera `id` (UUID) automaticamente."""

    __abstract__ = True

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
