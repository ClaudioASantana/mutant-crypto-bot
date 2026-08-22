import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(BACKEND_DIR, "config", "operational_config.json")

# Storage canônico: dentro de `data/`, que é o diretório montado como volume Docker
# (`./backend/data:/app/data`). Um path CWD-relativo (o que existia antes) resolvia
# fora do volume e perdia o banco a cada rebuild do container.
DEFAULT_SQLITE_DB_PATH = os.path.join(BACKEND_DIR, "data", "app.db")


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    BINANCE_TESTNET = "BINANCE_TESTNET"
    BINANCE_LIVE = "BINANCE_LIVE"
    DERIV_SIM = "DERIV_SIM"
    DERIV_LIVE = "DERIV_LIVE"


@dataclass(frozen=True)
class OperationalConfig:
    execution_mode: ExecutionMode
    live_trading_enabled: bool
    api_auth_token: str
    allow_manual_trade: bool
    allow_runtime_risk_update: bool
    global_max_daily_loss: float
    default_stake_initial: float
    default_daily_stop_loss: float
    default_daily_stop_gain: float
    default_risk_percent: float
    sqlite_db_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_mode": self.execution_mode.value,
            "live_trading_enabled": self.live_trading_enabled,
            "api_auth_token": self.api_auth_token,
            "allow_manual_trade": self.allow_manual_trade,
            "allow_runtime_risk_update": self.allow_runtime_risk_update,
            "global_max_daily_loss": self.global_max_daily_loss,
            "default_stake_initial": self.default_stake_initial,
            "default_daily_stop_loss": self.default_daily_stop_loss,
            "default_daily_stop_gain": self.default_daily_stop_gain,
            "default_risk_percent": self.default_risk_percent,
            "sqlite_db_path": self.sqlite_db_path,
        }

    @property
    def live_execution_allowed(self) -> bool:
        return self.execution_mode in {ExecutionMode.BINANCE_LIVE, ExecutionMode.DERIV_LIVE} and self.live_trading_enabled

    @property
    def is_paper_mode(self) -> bool:
        return self.execution_mode == ExecutionMode.PAPER

    @property
    def sqlalchemy_database_url(self) -> str:
        """DSN SQLite derivado do path tipado — fonte única para engine e Alembic."""
        return f"sqlite:///{self.sqlite_db_path}"

    @property
    def migrations_command(self) -> str:
        """Comando de migration explícito. Nunca roda implicitamente no startup."""
        return "alembic upgrade head"


class OperationalConfigError(ValueError):
    pass


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def _coerce_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in TRUE_VALUES:
            return True
        if normalized in FALSE_VALUES:
            return False
    raise OperationalConfigError(f"Campo '{field_name}' inválido: esperado booleano, recebido {value!r}.")


def _coerce_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise OperationalConfigError(f"Campo '{field_name}' inválido: esperado número, recebido {value!r}.") from exc


def _coerce_execution_mode(value: Any) -> ExecutionMode:
    if isinstance(value, ExecutionMode):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        try:
            return ExecutionMode(normalized)
        except ValueError as exc:
            raise OperationalConfigError(f"execution_mode inválido: {value!r}.") from exc
    raise OperationalConfigError(f"execution_mode inválido: {value!r}.")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return _coerce_bool(raw, name)


def _resolve_sqlite_path(raw: str | None) -> str:
    """
    Resolve o path do SQLite para absoluto, ancorado em `BACKEND_DIR`.

    Um path relativo dependeria do CWD do processo (uvicorn local vs. container
    vs. teste), que é exatamente o bug que tirou o `journal.db` do volume.
    """
    if not raw or not raw.strip():
        return DEFAULT_SQLITE_DB_PATH
    candidate = raw.strip()
    if os.path.isabs(candidate):
        return candidate
    return os.path.join(BACKEND_DIR, candidate)


def _default_execution_mode() -> ExecutionMode:
    live_trading = _env_bool("LIVE_TRADING", False)
    use_deriv = _env_bool("USE_DERIV_SIMULATOR", False)

    if use_deriv:
        return ExecutionMode.DERIV_SIM
    if live_trading:
        return ExecutionMode.BINANCE_TESTNET
    return ExecutionMode.PAPER


def default_operational_config() -> OperationalConfig:
    api_auth_token = os.getenv("API_AUTH_TOKEN", "").strip()

    return OperationalConfig(
        execution_mode=_default_execution_mode(),
        live_trading_enabled=_env_bool("LIVE_TRADING", False),
        api_auth_token=api_auth_token,
        allow_manual_trade=_env_bool("ALLOW_MANUAL_TRADE", True),
        allow_runtime_risk_update=_env_bool("ALLOW_RUNTIME_RISK_UPDATE", True),
        global_max_daily_loss=_coerce_float(os.getenv("GLOBAL_MAX_DAILY_LOSS", "-100.0"), "GLOBAL_MAX_DAILY_LOSS"),
        default_stake_initial=_coerce_float(os.getenv("DEFAULT_STAKE_INITIAL", "10.0"), "DEFAULT_STAKE_INITIAL"),
        default_daily_stop_loss=_coerce_float(os.getenv("DEFAULT_DAILY_STOP_LOSS", "50.0"), "DEFAULT_DAILY_STOP_LOSS"),
        default_daily_stop_gain=_coerce_float(os.getenv("DEFAULT_DAILY_STOP_GAIN", "50.0"), "DEFAULT_DAILY_STOP_GAIN"),
        default_risk_percent=_coerce_float(os.getenv("DEFAULT_RISK_PERCENT", "2.0"), "DEFAULT_RISK_PERCENT"),
        sqlite_db_path=_resolve_sqlite_path(os.getenv("SQLITE_DB_PATH")),
    )


def load_operational_config(config_file: str | None = None) -> OperationalConfig:
    merged = default_operational_config().to_dict()
    path = config_file or CONFIG_FILE

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            persisted = json.load(fh)
        if not isinstance(persisted, dict):
            raise OperationalConfigError("operational_config.json inválido: esperado objeto JSON na raiz.")
        merged.update(persisted)

    cfg = OperationalConfig(
        execution_mode=_coerce_execution_mode(merged.get("execution_mode", ExecutionMode.PAPER.value)),
        live_trading_enabled=_coerce_bool(merged.get("live_trading_enabled", False), "live_trading_enabled"),
        api_auth_token=str(merged.get("api_auth_token", "") or "").strip(),
        allow_manual_trade=_coerce_bool(merged.get("allow_manual_trade", True), "allow_manual_trade"),
        allow_runtime_risk_update=_coerce_bool(merged.get("allow_runtime_risk_update", True), "allow_runtime_risk_update"),
        global_max_daily_loss=_coerce_float(merged.get("global_max_daily_loss", -100.0), "global_max_daily_loss"),
        default_stake_initial=_coerce_float(merged.get("default_stake_initial", 10.0), "default_stake_initial"),
        default_daily_stop_loss=_coerce_float(merged.get("default_daily_stop_loss", 50.0), "default_daily_stop_loss"),
        default_daily_stop_gain=_coerce_float(merged.get("default_daily_stop_gain", 50.0), "default_daily_stop_gain"),
        default_risk_percent=_coerce_float(merged.get("default_risk_percent", 2.0), "default_risk_percent"),
        sqlite_db_path=_resolve_sqlite_path(merged.get("sqlite_db_path")),
    )

    if cfg.execution_mode in {ExecutionMode.BINANCE_LIVE, ExecutionMode.DERIV_LIVE} and not cfg.live_trading_enabled:
        raise OperationalConfigError(
            "execution_mode LIVE exige live_trading_enabled=true. Bloqueando por fail-closed."
        )

    return cfg
