import pytest

from app.application.services.deriv_executor import DerivExecutor
from app.application.services.executor import BinanceExecutor


class DummyExchange:
    async def set_leverage(self, leverage, symbol):
        raise AssertionError("set_leverage não deveria ser chamado quando LIVE está bloqueado")

    async def create_market_order(self, *args, **kwargs):
        raise AssertionError("create_market_order não deveria ser chamado quando LIVE está bloqueado")


class DummyDerivClient:
    async def buy_contract(self, *args, **kwargs):
        raise AssertionError("buy_contract não deveria ser chamado quando LIVE está bloqueado")


@pytest.mark.asyncio
async def test_binance_executor_blocks_live_when_not_authorized(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    config_path = tmp_path / "operational_config.json"
    config_path.write_text('{"execution_mode": "PAPER", "live_trading_enabled": false}', encoding="utf-8")
    monkeypatch.setattr(
        "app.application.services.executor.load_operational_config",
        lambda: _load(str(config_path)),
    )

    executor = BinanceExecutor(DummyExchange())
    result = await executor.execute_entry(
        symbol="BTC/USDT",
        direction="CALL",
        margin_usdt=10.0,
        leverage=10,
        current_price=50000.0,
    )

    assert result["status"] == "error"
    assert result["error"] == "execution_blocked_live_not_authorized"


@pytest.mark.asyncio
async def test_binance_executor_blocks_exit_when_not_authorized(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    config_path = tmp_path / "operational_config.json"
    config_path.write_text('{"execution_mode": "PAPER", "live_trading_enabled": false}', encoding="utf-8")
    monkeypatch.setattr(
        "app.application.services.executor.load_operational_config",
        lambda: _load(str(config_path)),
    )

    executor = BinanceExecutor(DummyExchange())
    result = await executor.execute_exit(symbol="BTC/USDT", direction="CALL", qty=0.01)

    assert result["status"] == "error"
    assert result["error"] == "execution_blocked_live_not_authorized"


def test_deriv_executor_assert_live_blocks_when_not_authorized(tmp_path, monkeypatch):
    """DerivExecutor herda de uma ABC com métodos abstratos ainda não implementados
    (open_trade/check_positions/get_state/...), então não pode ser instanciado.
    Testamos o gate fail-closed diretamente, sem instanciar a classe."""
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    config_path = tmp_path / "operational_config.json"
    config_path.write_text('{"execution_mode": "PAPER", "live_trading_enabled": false}', encoding="utf-8")
    monkeypatch.setattr(
        "app.application.services.deriv_executor.load_operational_config",
        lambda: _load(str(config_path)),
    )

    # `_assert_live_allowed` não usa `self`; chamada desvinculada verifica o gate.
    assert DerivExecutor._assert_live_allowed(None) is False


def _load(path: str):
    from app.core.operational_config import load_operational_config

    return load_operational_config(path)
