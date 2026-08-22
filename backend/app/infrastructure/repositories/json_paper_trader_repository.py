"""Repositório composto em JSON: `PaperTraderState` + `Trade`.

Mantido apenas para compatibilidade temporária/backfill e para o período de
cutover. O runtime principal deve migrar para o par SQLAlchemy canônico.
"""

import json
import logging
import os
from typing import Optional

from app.domain.entities.paper_trader_state import PaperTraderState
from app.domain.entities.trade import Trade
from app.domain.repositories.paper_trader_state_repository import AbstractPaperTraderStateRepository
from app.domain.repositories.trade_repository import AbstractTradeRepository
from app.domain.value_objects.enums import TradeStatus

logger = logging.getLogger(__name__)


class JsonPaperTraderRepository(AbstractPaperTraderStateRepository, AbstractTradeRepository):
    """Repositório composto em JSON para transição/backtest manual."""

    def __init__(self, base_path: str = "data"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _get_state_file_path(self, identity: str) -> str:
        return os.path.join(self.base_path, identity)

    def _get_trades_file_path(self, identity: str) -> str:
        return os.path.join(self.base_path, f"{identity}.trades.json")

    # --- AbstractPaperTraderStateRepository ---

    def load(self, identity: str) -> Optional[PaperTraderState]:
        file_path = self._get_state_file_path(identity)
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                logger.info(f"💾 [PaperTraderRepo] Estado '{identity}' carregado de '{file_path}'.")
                return PaperTraderState.model_validate(payload)
            return None
        except Exception as e:
            logger.error(f"Erro ao carregar estado '{identity}' de '{file_path}': {e}")
            return None

    def save(self, state: PaperTraderState) -> None:
        file_path = self._get_state_file_path(state.identity)
        tmp_file_path = file_path + ".tmp"
        try:
            with open(tmp_file_path, "w", encoding="utf-8") as f:
                json.dump(state.model_dump(mode="json"), f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file_path, file_path)
            logger.info(f"✅ [PaperTraderRepo] Estado '{state.identity}' salvo em '{file_path}' (Atômico).")
        except Exception as e:
            logger.error(f"Erro ao salvar estado '{state.identity}' em '{file_path}': {e}")
            if os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except OSError:
                    pass

    # --- AbstractTradeRepository ---

    def add(self, trade: Trade) -> Trade:
        trades = self._load_trades(trade.identity)
        if any(item.id == trade.id for item in trades):
            raise ValueError(f"Trade {trade.id} already exists")
        trades.append(trade)
        self._save_trades(trade.identity, trades)
        return trade

    def update(self, trade: Trade) -> Trade:
        trades = self._load_trades(trade.identity)
        for index, existing in enumerate(trades):
            if existing.id == trade.id:
                trades[index] = trade
                self._save_trades(trade.identity, trades)
                return trade
        raise ValueError(f"Trade {trade.id} does not exist")

    def get_by_id(self, trade_id: str) -> Optional[Trade]:
        for filename in os.listdir(self.base_path):
            if not filename.endswith(".trades.json"):
                continue
            identity = filename[: -len(".trades.json")]
            for trade in self._load_trades(identity):
                if trade.id == trade_id:
                    return trade
        return None

    def list_active(self, identity: str, symbol: Optional[str] = None) -> list[Trade]:
        trades = self._load_trades(identity)
        return [
            t
            for t in trades
            if t.status is TradeStatus.OPEN and (symbol is None or t.symbol == symbol)
        ]

    def list_history(self, identity: str, limit: int = 50) -> list[Trade]:
        trades = [t for t in self._load_trades(identity) if t.status is not TradeStatus.OPEN]
        trades.sort(key=lambda t: t.exit_epoch or t.entry_epoch, reverse=True)
        return trades[:limit]

    def _load_trades(self, identity: str) -> list[Trade]:
        file_path = self._get_trades_file_path(identity)
        try:
            if not os.path.exists(file_path):
                return []
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return [Trade.model_validate(item) for item in payload]
        except Exception as e:
            logger.error(f"Erro ao carregar trades '{identity}' de '{file_path}': {e}")
            return []

    def _save_trades(self, identity: str, trades: list[Trade]) -> None:
        file_path = self._get_trades_file_path(identity)
        tmp_file_path = file_path + ".tmp"
        try:
            with open(tmp_file_path, "w", encoding="utf-8") as f:
                json.dump([trade.model_dump(mode="json") for trade in trades], f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file_path, file_path)
        except Exception as e:
            logger.error(f"Erro ao salvar trades '{identity}' em '{file_path}': {e}")
            if os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except OSError:
                    pass
