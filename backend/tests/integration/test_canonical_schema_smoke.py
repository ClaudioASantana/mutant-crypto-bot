import sqlite3
from pathlib import Path

from app.core.operational_config import load_operational_config


REQUIRED_TABLES = {"alembic_version", "paper_trader_states", "trades"}
EXPECTED_HEAD = "514a3e6ef167"


def test_canonical_schema_has_required_tables_and_head():
    """Smoke check do banco canônico configurado para este ambiente.

    Protege contra o caso já observado de `alembic current` apontar `head`, mas
    o arquivo SQLite conter apenas `alembic_version` (sem as tabelas canônicas).
    """
    cfg = load_operational_config()
    db_path = Path(cfg.sqlite_db_path)

    assert db_path.exists(), f"Banco canônico ausente: {db_path}"

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert REQUIRED_TABLES.issubset(tables), (
            f"Schema canônico incompleto em {db_path}. "
            f"Esperado pelo menos {sorted(REQUIRED_TABLES)}, encontrado {sorted(tables)}"
        )

        head_row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        assert head_row is not None, "Tabela alembic_version existe, mas sem revision registrada"
        assert head_row[0] == EXPECTED_HEAD, (
            f"Revision inesperada em {db_path}: {head_row[0]!r} != {EXPECTED_HEAD!r}"
        )
