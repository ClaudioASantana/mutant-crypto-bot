"""Importa dados legados (journal.db + snapshots JSON) para o storage canônico.

Uso típico:
    venv/bin/python scripts/migrate_legacy_paper_trader_data.py

Fluxo:
- lê `data/journal.db` e/ou `app/data/journal.db`;
- lê `data/simulator_state_*.json`;
- upserta snapshots operacionais em `paper_trader_states`;
- insere/atualiza trades em `trades`, preservando ids quando existirem;
- deduplica por `trade.id`, com fallback estrutural
  `(identity, symbol, side, entry_epoch, entry_price)`;
- privilegia proveniência do journal para `strategy` / `ai_*` / `rsi` /
  `leverage`, mas usa dados operacionais do JSON (`sl`, `tp`, `qty`, extremos,
  fechamento) quando o journal estiver incompleto ou divergente.

O script é idempotente: reexecutar não deve duplicar trades.
"""

from __future__ import annotations

import os
import sys

# Bootstrap: permite rodar `python scripts/migrate_legacy_paper_trader_data.py`
# direto do diretório `backend/`, sem depender de `PYTHONPATH` ou de instalação.
_BACKEND_DIR_BOOTSTRAP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR_BOOTSTRAP not in sys.path:
    sys.path.insert(0, _BACKEND_DIR_BOOTSTRAP)

import glob
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.core.operational_config import load_operational_config
from app.domain.entities.paper_trader_state import PaperTraderState
from app.domain.entities.trade import Trade
from app.domain.value_objects.enums import TradeOutcome, TradeSide, TradeSource, TradeStatus, split_legacy_status
from app.infrastructure.repositories.sqlalchemy_paper_trader_state_repository import (
    SqlAlchemyPaperTraderStateRepository,
)
from app.infrastructure.repositories.sqlalchemy_trade_repository import SqlAlchemyTradeRepository

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BACKEND_DIR / "data"
DEFAULT_JOURNAL_CANDIDATES = [
    DEFAULT_DATA_DIR / "journal.db",
    BACKEND_DIR / "app" / "data" / "journal.db",
]


@dataclass
class ImportStats:
    snapshots_seen: int = 0
    states_upserted: int = 0
    journal_rows_seen: int = 0
    trades_inserted: int = 0
    trades_updated: int = 0
    trades_skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "snapshots_seen": self.snapshots_seen,
            "states_upserted": self.states_upserted,
            "journal_rows_seen": self.journal_rows_seen,
            "trades_inserted": self.trades_inserted,
            "trades_updated": self.trades_updated,
            "trades_skipped": self.trades_skipped,
        }


def _normalize_side(raw: str) -> TradeSide:
    return TradeSide.CALL if str(raw).upper() in {"CALL", "LONG"} else TradeSide.PUT


def _derive_symbol_from_identity(identity: str) -> str:
    stem = identity.removesuffix(".json")
    if stem.startswith("simulator_state_"):
        stem = stem[len("simulator_state_") :]
    if stem == "global":
        return "GLOBAL"
    if "_" in stem:
        base, quote, *rest = stem.split("_")
        if quote:
            return f"{base}/{quote}"
    return stem.replace("_", "/")


def _find_snapshot_files(data_dir: Path) -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(data_dir / "simulator_state_*.json")))


def _require_canonical_schema(engine, canonical_db: Path) -> None:
    """Falha se as tabelas canônicas não existirem no banco de destino.

    O schema é gerido exclusivamente por Alembic (`alembic upgrade head`).
    Este script importa *dados*, não estrutura — por isso recusa-se a
    bootstrapar tabelas via `create_all`, que deixaria o banco num estado
    inconsistente com o histórico de migrations.
    """
    required = {"paper_trader_states", "trades"}
    present = set(inspect(engine).get_table_names())
    missing = required - present
    if missing:
        raise RuntimeError(
            f"Tabelas canônicas ausentes em {canonical_db}: {sorted(missing)}. "
            "Rode `cd backend && venv/bin/alembic upgrade head` antes de importar dados legados."
        )


def _existing_trade_by_structural_key(
    trade_repo: SqlAlchemyTradeRepository,
    identity: str,
    symbol: str,
    side: TradeSide,
    entry_epoch: int,
    entry_price: float,
) -> Optional[Trade]:
    candidates = trade_repo.list_active(identity, symbol=symbol) + trade_repo.list_history(identity, limit=10000)
    for candidate in candidates:
        if (
            candidate.symbol == symbol
            and candidate.side is side
            and candidate.entry_epoch == entry_epoch
            and abs(candidate.entry_price - entry_price) < 1e-9
        ):
            return candidate
    return None


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"Snapshot inválido em {path}: esperado objeto JSON na raiz")
    return payload


def _load_journal_rows(path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM trades").fetchall()]
        return rows
    finally:
        conn.close()


def _journal_row_by_id(paths: list[Path]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        for row in _load_journal_rows(path):
            by_id[row["id"]] = row
    return by_id


def _trade_from_snapshot(
    *,
    identity: str,
    symbol: str,
    trade_dict: dict[str, Any],
    journal_row: Optional[dict[str, Any]],
) -> Trade:
    legacy_status = trade_dict.get("status", "OPEN")
    status, outcome = split_legacy_status(legacy_status)

    source = TradeSource.MIGRATED_JSON
    if journal_row is not None:
        source = TradeSource.MIGRATED_JOURNAL

    trade = Trade(
        id=trade_dict["id"],
        identity=identity,
        symbol=symbol,
        side=_normalize_side(trade_dict.get("direction", "CALL")),
        status=status,
        outcome=outcome,
        source=source,
        entry_price=float(trade_dict.get("entry_price", journal_row.get("entry_price") if journal_row else 0.0)),
        entry_epoch=int(trade_dict.get("entry_epoch", journal_row.get("entry_time") if journal_row else 0)),
        qty=float(trade_dict.get("qty", 0.0) or 0.0),
        margin=float(trade_dict.get("margin", journal_row.get("margin") if journal_row else 0.0) or 0.0),
        leverage=int(trade_dict.get("leverage", journal_row.get("leverage") if journal_row else 10) or 10),
        sl=trade_dict.get("sl"),
        tp=trade_dict.get("tp"),
        exit_price=trade_dict.get("exit_price") if trade_dict.get("exit_price") is not None else (journal_row.get("exit_price") if journal_row else None),
        exit_epoch=trade_dict.get("exit_epoch") if trade_dict.get("exit_epoch") is not None else (journal_row.get("exit_time") if journal_row else None),
        pnl=float(trade_dict.get("pnl", journal_row.get("net_pnl") if journal_row else 0.0) or 0.0),
        close_reason=legacy_status if status is not TradeStatus.OPEN else None,
        atr=trade_dict.get("atr") if trade_dict.get("atr") is not None else (journal_row.get("atr") if journal_row else None),
        rsi=journal_row.get("rsi") if journal_row else None,
        highest_reached=trade_dict.get("highest_reached"),
        lowest_reached=trade_dict.get("lowest_reached"),
        strategy=journal_row.get("strategy") if journal_row else None,
        ai_reason=journal_row.get("ai_reason") if journal_row else None,
        ai_confidence=(journal_row.get("ai_confidence") if journal_row else None),
        ai_context=(journal_row.get("ai_context") if journal_row else None),
        notes=(
            "Imported from snapshot JSON with journal enrichment"
            if journal_row is not None
            else "Imported from snapshot JSON"
        ),
    )

    # `split_legacy_status` preserva OPEN/CLOSED semanticamente. Se o journal
    # estiver OPEN mas o JSON já trouxe fechamento real, o JSON vence.
    return trade


def _trade_from_orphan_journal(row: dict[str, Any]) -> Trade:
    journal_status = str(row.get("status") or "OPEN").upper()
    status, outcome = split_legacy_status(journal_status)
    notes = "Imported from orphan journal row"
    if status is TradeStatus.OPEN:
        notes = "Imported from orphan journal row kept OPEN"

    return Trade(
        id=row["id"],
        identity=f"migrated_{str(row.get('symbol', 'UNKNOWN')).replace('/', '_')}.json",
        symbol=row.get("symbol") or "UNKNOWN",
        side=_normalize_side(row.get("direction", "CALL")),
        status=status,
        outcome=outcome,
        source=TradeSource.MIGRATED_JOURNAL,
        entry_price=float(row.get("entry_price") or 0.0),
        entry_epoch=int(row.get("entry_time") or 0),
        margin=float(row.get("margin") or 0.0),
        leverage=int(row.get("leverage") or 10),
        exit_price=row.get("exit_price"),
        exit_epoch=row.get("exit_time"),
        pnl=float(row.get("net_pnl") or 0.0),
        close_reason=journal_status if status is not TradeStatus.OPEN else None,
        atr=row.get("atr"),
        rsi=row.get("rsi"),
        strategy=row.get("strategy"),
        ai_reason=row.get("ai_reason"),
        ai_confidence=row.get("ai_confidence"),
        ai_context=row.get("ai_context"),
        notes=notes,
    )


def _upsert_trade(
    trade_repo: SqlAlchemyTradeRepository,
    trade: Trade,
    stats: ImportStats,
    *,
    structural_fallback: bool = False,
) -> None:
    """Insere ou atualiza um trade legado.

    A deduplicação primária é por `trade.id`, que é exato: tanto o journal
    quanto os snapshots JSON carregam id próprio. O fallback estrutural
    `(identity, symbol, side, entry_epoch, entry_price)` só é habilitado para
    registros sem id estável — no conjunto legado real existem trades
    distintos que compartilham entrada idêntica (3 CALL BTC em 1786627379 e
    3 CALL SOL em 1786930199), e colapsá-los perderia dados reais.
    """
    existing = trade_repo.get_by_id(trade.id)
    matched_by_structural_key = False
    if existing is None and structural_fallback:
        existing = _existing_trade_by_structural_key(
            trade_repo,
            trade.identity,
            trade.symbol,
            trade.side,
            trade.entry_epoch,
            trade.entry_price,
        )
        matched_by_structural_key = existing is not None

    if existing is None:
        trade_repo.add(trade)
        stats.trades_inserted += 1
        return

    changed = False
    for field in Trade.model_fields.keys():
        if field == "id" and matched_by_structural_key:
            # Um match estrutural com id diferente indica colisão/duplicata
            # histórica. Preservamos o id já canônico no destino em vez de
            # tentar renomear a PK da linha existente.
            continue
        new_value = getattr(trade, field)
        old_value = getattr(existing, field)
        if old_value != new_value and new_value is not None:
            setattr(existing, field, new_value)
            changed = True

    if changed:
        trade_repo.update(existing)
        stats.trades_updated += 1
    else:
        stats.trades_skipped += 1


def migrate_legacy_data(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    journal_candidates: Optional[list[Path]] = None,
    sqlite_db_path: Optional[Path] = None,
) -> ImportStats:
    cfg = load_operational_config()
    canonical_db = Path(sqlite_db_path or cfg.sqlite_db_path)
    canonical_db.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{canonical_db}", connect_args={"check_same_thread": False})
    _require_canonical_schema(engine, canonical_db)
    session_factory = sessionmaker(bind=engine)
    state_repo = SqlAlchemyPaperTraderStateRepository(session_factory=session_factory)
    trade_repo = SqlAlchemyTradeRepository(session_factory=session_factory)

    stats = ImportStats()
    journal_paths = [p for p in (journal_candidates or DEFAULT_JOURNAL_CANDIDATES) if p.exists()]
    journal_by_id = _journal_row_by_id(journal_paths)
    seen_journal_ids = set(journal_by_id.keys())
    stats.journal_rows_seen = len(seen_journal_ids)

    for snapshot_path in _find_snapshot_files(data_dir):
        payload = _load_json(snapshot_path)
        identity = snapshot_path.name
        symbol = _derive_symbol_from_identity(identity)
        stats.snapshots_seen += 1

        state = PaperTraderState.from_legacy_dict(
            identity=identity,
            symbol=symbol,
            payload=payload,
        )
        state_repo.save(state)
        stats.states_upserted += 1

        for trade_dict in payload.get("history_trades", []) + payload.get("open_positions", []):
            journal_row = journal_by_id.get(trade_dict["id"])
            trade = _trade_from_snapshot(
                identity=identity,
                symbol=symbol,
                trade_dict=trade_dict,
                journal_row=journal_row,
            )
            _upsert_trade(trade_repo, trade, stats)
            seen_journal_ids.discard(trade.id)

    # Journal órfão: existe no journal, mas nenhum snapshot o carregou.
    for trade_id in sorted(seen_journal_ids):
        trade = _trade_from_orphan_journal(journal_by_id[trade_id])
        _upsert_trade(trade_repo, trade, stats)

    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = migrate_legacy_data()
    print(json.dumps(stats.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
