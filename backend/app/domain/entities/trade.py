"""
Entidade `Trade`: agregado canônico de ciclo de vida + journal operacional.

Substitui os três shapes de `dict` que circulavam antes (snapshot do PaperTrader,
blob do CQRS e linha do `journal.db`). As transições são guardadas: fechar um trade
já fechado é erro de programação, não uma sobrescrita silenciosa.
"""

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.domain.value_objects.enums import (
    TradeOutcome,
    TradeSide,
    TradeSource,
    TradeStatus,
)


class Trade(BaseModel):
    """Um trade, do nascimento ao encerramento, com sua proveniência."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Identidade lógica. `identity` é a chave legada (nome do arquivo de snapshot);
    # os campos decompostos existem para permitir aposentá-la sem migration destrutiva.
    identity: str
    symbol: str
    personality_name: Optional[str] = None
    timeframe_seconds: Optional[int] = None

    side: TradeSide
    status: TradeStatus = TradeStatus.OPEN
    outcome: Optional[TradeOutcome] = None
    source: TradeSource = TradeSource.UNKNOWN

    # Entrada
    entry_price: float
    entry_epoch: int
    qty: float = 0.0
    margin: float = 0.0
    leverage: int = 1
    sl: Optional[float] = None
    tp: Optional[float] = None

    # Saída
    exit_price: Optional[float] = None
    exit_epoch: Optional[int] = None
    pnl: float = 0.0
    close_reason: Optional[str] = None

    # Telemetria de mercado no momento da decisão
    atr: Optional[float] = None
    rsi: Optional[float] = None
    highest_reached: Optional[float] = None
    lowest_reached: Optional[float] = None

    # Proveniência de IA/estratégia (o que o journal legado guardava sozinho)
    strategy: Optional[str] = None
    ai_reason: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_context: Optional[str] = None

    notes: Optional[str] = None

    @model_validator(mode="after")
    def _check_status_outcome_coherence(self) -> "Trade":
        """`outcome` só existe em trade CLOSED, e todo CLOSED precisa de um."""
        if self.status is TradeStatus.CLOSED and self.outcome is None:
            raise ValueError("Trade CLOSED exige um outcome (WIN/LOSS/TIME_STOP).")
        if self.status is not TradeStatus.CLOSED and self.outcome is not None:
            raise ValueError(
                f"Trade em status {self.status.value} não pode ter outcome {self.outcome.value}."
            )
        return self

    # --- Consultas ---

    @property
    def is_active(self) -> bool:
        return self.status is TradeStatus.OPEN

    @property
    def is_win(self) -> bool:
        return self.outcome is TradeOutcome.WIN

    # --- Construtores ---

    @classmethod
    def open_new(
        cls,
        *,
        identity: str,
        symbol: str,
        side: TradeSide,
        entry_price: float,
        entry_epoch: int,
        source: TradeSource,
        trade_id: Optional[str] = None,
        **kwargs: Any,
    ) -> "Trade":
        """Cria um trade já aberto. `trade_id` permite preservar ids legados."""
        payload: dict[str, Any] = {
            "identity": identity,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "entry_epoch": entry_epoch,
            "source": source,
            "status": TradeStatus.OPEN,
            "outcome": None,
            **kwargs,
        }
        if trade_id is not None:
            payload["id"] = trade_id
        return cls(**payload)

    @classmethod
    def rejected(
        cls,
        *,
        identity: str,
        symbol: str,
        side: TradeSide,
        entry_price: float,
        entry_epoch: int,
        source: TradeSource,
        reason: str,
        **kwargs: Any,
    ) -> "Trade":
        """
        Cria a linha de uma tentativa recusada.

        Recusa é fato operacional auditável — precisa ficar persistida com motivo,
        não sumir num `raise` que só vira log.
        """
        return cls(
            identity=identity,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            entry_epoch=entry_epoch,
            source=source,
            status=TradeStatus.REJECTED,
            outcome=None,
            close_reason=reason,
            **kwargs,
        )

    # --- Transições ---

    def close(
        self,
        *,
        exit_price: float,
        exit_epoch: int,
        pnl: float,
        outcome: TradeOutcome,
        close_reason: Optional[str] = None,
    ) -> "Trade":
        """Encerra um trade aberto. Fechar duas vezes é erro."""
        if self.status is not TradeStatus.OPEN:
            raise ValueError(f"Cannot close trade in status {self.status.value}")
        self.exit_price = exit_price
        self.exit_epoch = exit_epoch
        self.pnl = pnl
        self.outcome = outcome
        self.status = TradeStatus.CLOSED
        self.close_reason = close_reason
        return self

    def cancel(self, reason: str) -> "Trade":
        """Cancela um trade aberto sem resultado financeiro (ex.: shutdown limpo)."""
        if self.status is not TradeStatus.OPEN:
            raise ValueError(f"Cannot cancel trade in status {self.status.value}")
        self.status = TradeStatus.CANCELLED
        self.close_reason = reason
        return self

    # --- Interop com o shape legado do simulador ---

    def to_runtime_dict(self) -> dict[str, Any]:
        """
        Projeta o trade no shape que a UI/WebSocket já consome hoje.

        Read model derivado — não é o formato canônico persistido.
        `status` volta a ser o campo monolítico legado para não quebrar o frontend
        nesta rodada; o banco continua guardando status/outcome separados.
        """
        legacy_status = self.outcome.value if self.outcome is not None else self.status.value
        return {
            "id": self.id,
            "direction": self.side.value,
            "entry_price": self.entry_price,
            "margin": self.margin,
            "qty": self.qty,
            "sl": self.sl,
            "tp": self.tp,
            "entry_epoch": self.entry_epoch,
            "status": legacy_status,
            "pnl": self.pnl,
            "atr": self.atr,
            "highest_reached": self.highest_reached,
            "lowest_reached": self.lowest_reached,
            "exit_price": self.exit_price,
            "exit_epoch": self.exit_epoch,
        }
