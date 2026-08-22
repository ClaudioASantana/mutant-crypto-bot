import json

import pytest

from app.core.operational_config import (
    ExecutionMode,
    OperationalConfigError,
    load_operational_config,
)


def test_load_operational_config_defaults_to_paper(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    monkeypatch.delenv("USE_DERIV_SIMULATOR", raising=False)
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)

    config_path = tmp_path / "operational_config.json"
    config_path.write_text("{}", encoding="utf-8")

    cfg = load_operational_config(str(config_path))

    assert cfg.execution_mode == ExecutionMode.PAPER
    assert cfg.live_trading_enabled is False
    assert cfg.live_execution_allowed is False


def test_load_operational_config_rejects_live_without_enable_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING", raising=False)

    config_path = tmp_path / "operational_config.json"
    config_path.write_text(
        json.dumps({
            "execution_mode": "BINANCE_LIVE",
            "live_trading_enabled": False,
        }),
        encoding="utf-8",
    )

    with pytest.raises(OperationalConfigError, match="live_trading_enabled=true"):
        load_operational_config(str(config_path))


def test_load_operational_config_rejects_invalid_execution_mode(tmp_path):
    config_path = tmp_path / "operational_config.json"
    config_path.write_text(json.dumps({"execution_mode": "INVALID_MODE"}), encoding="utf-8")

    with pytest.raises(OperationalConfigError, match="execution_mode inválido"):
        load_operational_config(str(config_path))
