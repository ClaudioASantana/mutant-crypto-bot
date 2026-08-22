"""
Enums do domínio de trading.

São persistidos como `String` no banco (nunca como `sa.Enum`), para que a
evolução do vocabulário não exija `ALTER TYPE` nem migration destrutiva.
"""

from enum import Enum


class TradeSide(str, Enum):
    """Direção da posição. Mantém o vocabulário histórico do simulador."""

    CALL = "CALL"   # LONG
    PUT = "PUT"     # SHORT


class TradeStatus(str, Enum):
    """Ciclo de vida da ordem/posição — independe do resultado financeiro."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TradeOutcome(str, Enum):
    """Resultado financeiro de um trade já fechado. `None` enquanto OPEN."""

    WIN = "WIN"
    LOSS = "LOSS"
    TIME_STOP = "TIME_STOP"


class TradeSource(str, Enum):
    """Proveniência do registro: quem o criou e sob qual regime."""

    SWARM = "SWARM"                          # loop autônomo (PaperTrader)
    MANUAL_CQRS = "MANUAL_CQRS"              # comando manual via API
    BACKTEST = "BACKTEST"                    # simulação offline
    MIGRATED_JOURNAL = "MIGRATED_JOURNAL"    # importado do journal.db legado
    MIGRATED_JSON = "MIGRATED_JSON"          # importado dos snapshots JSON legados
    UNKNOWN = "UNKNOWN"


#: Status em que o trade ainda ocupa risco na conta.
ACTIVE_STATUSES = (TradeStatus.OPEN,)

#: Status terminais — não voltam a ser ativos.
TERMINAL_STATUSES = (TradeStatus.CLOSED, TradeStatus.CANCELLED, TradeStatus.REJECTED)


#: Mapeia o `status` monolítico do simulador legado para o par (status, outcome).
LEGACY_STATUS_MAP: dict[str, tuple[TradeStatus, TradeOutcome | None]] = {
    "OPEN": (TradeStatus.OPEN, None),
    "WIN": (TradeStatus.CLOSED, TradeOutcome.WIN),
    "LOSS": (TradeStatus.CLOSED, TradeOutcome.LOSS),
    "TIME_STOP": (TradeStatus.CLOSED, TradeOutcome.TIME_STOP),
    "CANCELLED": (TradeStatus.CANCELLED, None),
    "REJECTED": (TradeStatus.REJECTED, None),
}


def split_legacy_status(raw_status: str | None) -> tuple[TradeStatus, TradeOutcome | None]:
    """
    Traduz o `status` legado (que misturava lifecycle e resultado) no par novo.

    Levanta `ValueError` para valores desconhecidos: importar lixo silenciosamente
    é pior do que falhar durante a migração.
    """
    if raw_status is None:
        raise ValueError("status legado ausente: não é possível inferir status/outcome.")
    key = str(raw_status).strip().upper()
    if key not in LEGACY_STATUS_MAP:
        raise ValueError(f"status legado desconhecido: {raw_status!r}.")
    return LEGACY_STATUS_MAP[key]
