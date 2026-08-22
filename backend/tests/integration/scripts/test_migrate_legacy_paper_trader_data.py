import shutil
import sqlite3
from pathlib import Path

from scripts.migrate_legacy_paper_trader_data import migrate_legacy_data
from app.infrastructure.database.models.base import Base
import app.infrastructure.database.models.trade_model  # noqa: F401
import app.infrastructure.database.models.paper_trader_state_model  # noqa: F401
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.infrastructure.repositories.sqlalchemy_trade_repository import SqlAlchemyTradeRepository
from app.infrastructure.repositories.sqlalchemy_paper_trader_state_repository import (
    SqlAlchemyPaperTraderStateRepository,
)


FIXTURES_DIR = Path(__file__).resolve().parents[3] / "data"


def _create_schema(sqlite_path: Path):
    """Cria o schema canônico no banco de teste, espelhando `alembic upgrade head`.

    O script de migração legada exige que as tabelas já existam (Alembic é a
    única via de schema management); aqui reproduzimos isso de forma leve com
    `create_all`, que é o padrão aceito apenas em testes.
    """
    engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def _repo_pair(sqlite_path: Path):
    engine = _create_schema(sqlite_path)
    session_factory = sessionmaker(bind=engine)
    return (
        SqlAlchemyPaperTraderStateRepository(session_factory=session_factory),
        SqlAlchemyTradeRepository(session_factory=session_factory),
    )


def test_migrate_legacy_data_imports_snapshots_and_journal(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Copia o fixture real para um sandbox temporário — o teste valida a lógica
    # sem tocar no estado canônico do repositório do usuário.
    for path in FIXTURES_DIR.glob("simulator_state_*.json"):
        shutil.copy(path, data_dir / path.name)
    shutil.copy(FIXTURES_DIR / "journal.db", data_dir / "journal.db")

    sqlite_path = tmp_path / "canonical.db"
    _create_schema(sqlite_path)
    stats = migrate_legacy_data(
        data_dir=data_dir,
        journal_candidates=[data_dir / "journal.db"],
        sqlite_db_path=sqlite_path,
    )

    state_repo, trade_repo = _repo_pair(sqlite_path)

    assert stats.snapshots_seen == 6
    assert stats.states_upserted == 6
    assert stats.journal_rows_seen == 15
    assert stats.trades_inserted == 40
    assert stats.trades_updated == 0
    assert stats.trades_skipped == 0

    btc_state = state_repo.load("simulator_state_BTC_USDT.json")
    assert btc_state is not None
    assert btc_state.symbol == "BTC/USDT"
    assert btc_state.balance == 199.12
    assert btc_state.initial_balance == 200.0

    # Trade presente em JSON + journal: deve nascer enriquecido com proveniência do journal.
    enriched = trade_repo.get_by_id("5109a8f5")
    assert enriched is not None
    assert enriched.source.value == "MIGRATED_JOURNAL"
    assert enriched.symbol == "BTC/USDT"
    assert enriched.status.value == "CLOSED"
    assert enriched.outcome.value == "LOSS"
    assert enriched.strategy == "M15/AI (Conf: 0.78)"
    assert enriched.ai_reason is not None
    assert enriched.rsi == 50.0

    # OPEN órfão/ativo do conjunto legado deve permanecer OPEN, nunca receber
    # fechamento inventado durante a migração.
    still_open = trade_repo.get_by_id("34c4ce65")
    assert still_open is not None
    assert still_open.status.value == "OPEN"
    assert still_open.outcome is None


def test_migrate_legacy_data_is_idempotent(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for path in FIXTURES_DIR.glob("simulator_state_*.json"):
        shutil.copy(path, data_dir / path.name)
    shutil.copy(FIXTURES_DIR / "journal.db", data_dir / "journal.db")

    sqlite_path = tmp_path / "canonical.db"
    _create_schema(sqlite_path)
    first = migrate_legacy_data(
        data_dir=data_dir,
        journal_candidates=[data_dir / "journal.db"],
        sqlite_db_path=sqlite_path,
    )
    second = migrate_legacy_data(
        data_dir=data_dir,
        journal_candidates=[data_dir / "journal.db"],
        sqlite_db_path=sqlite_path,
    )

    _, trade_repo = _repo_pair(sqlite_path)

    with sqlite3.connect(sqlite_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        states = conn.execute("SELECT COUNT(*) FROM paper_trader_states").fetchone()[0]

    assert first.trades_inserted == 40
    assert second.trades_inserted == 0
    assert second.trades_updated == 0
    assert second.trades_skipped == 40
    assert total == 40
    assert states == 6

    # Amostra: o mesmo trade continua único e legível após a segunda execução.
    sample = trade_repo.get_by_id("5109a8f5")
    assert sample is not None
    assert sample.symbol == "BTC/USDT"
