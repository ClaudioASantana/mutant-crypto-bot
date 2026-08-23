"""
Testes unitários para o PaperTrader (TradeExecutor concreto).

Garante que o executor de trades de papel abre, fecha e persiste
estado corretamente através do repositório composto em memória.
"""

import pytest

from app.application.services.backtest_metrics import TradingCostConfig
from app.infrastructure.services.paper_trader_executor import PaperTrader
from app.infrastructure.repositories.in_memory_paper_trader_repository import InMemoryPaperTraderRepository
from app.domain.entities.personality import Personality, RiskProfile
from tests.unit.mock_risk_manager import MockRiskManager # Importar o mock


@pytest.fixture
def repository():
    return InMemoryPaperTraderRepository()


@pytest.fixture
def paper_trader(repository):
    mock_risk_manager = MockRiskManager()
    return PaperTrader(
        symbol="BTC/USDT",
        identity="BTCUSDT_test",
        repository=repository,
        risk_manager=mock_risk_manager,
        initial_balance=1000.0,
        leverage=10,
        position_sizing_mode="fixed"
    )


@pytest.fixture
def sample_personality():
    return Personality(
        name="Teste_M5",
        strategy="Wyckoff_SMC",
        timeframe=300,
        risk_profile=RiskProfile()
    )


def test_paper_trader_initial_state(paper_trader):
    """Deve começar com saldo inicial e nenhuma posição aberta."""
    state = paper_trader.get_state()
    assert state["balance"] == pytest.approx(1000.0)
    assert state["pnl"] == pytest.approx(0.0)
    assert state["pending"] == []
    assert state["history"] == []


def test_paper_trader_open_trade(paper_trader, sample_personality):
    """Deve abrir uma posição e salvá-la no repositório."""
    paper_trader.open_trade(
        direction="CALL",
        tf=300,
        current_epoch=1234567890,
        current_price=50000.0,
        sl_price=49000.0,
        tp_price=52000.0,
        atr=100.0,
        personality=sample_personality
    )

    state = paper_trader.get_state()
    assert len(state["pending"]) == 1
    assert state["pending"][0]["direction"] == "CALL"

    # Persistiu como Trade canônico na tabela `trades` (aqui, o composto em memória)
    active = repository_trades_for(paper_trader)
    assert len(active) == 1
    assert active[0].status.value == "OPEN"


def repository_trades_for(paper_trader):
    return paper_trader.repository.list_active(paper_trader.identity)


def test_paper_trader_winning_trade(repository, sample_personality):
    """Deve fechar uma posição vencedora e atualizar o saldo."""
    mock_risk_manager = MockRiskManager()
    paper_trader = PaperTrader(
        symbol="BTC/USDT",
        identity="BTCUSDT_win",
        repository=repository,
        risk_manager=mock_risk_manager,
        initial_balance=1000.0,
        leverage=10,
        position_sizing_mode="fixed"
    )

    paper_trader.open_trade(
        direction="CALL",
        tf=300,
        current_epoch=1234567890,
        current_price=50000.0,
        sl_price=49000.0,
        tp_price=52000.0,
        atr=100.0,
        personality=sample_personality
    )

    # Preço atinge o Take Profit
    finished = paper_trader.check_positions(
        current_epoch=1234567890 + 300,
        current_price=52000.0,
        personality=sample_personality
    )

    assert len(finished) == 1
    assert finished[0]["status"] == "WIN"
    assert paper_trader.balance > 1000.0

    # O fechamento foi persistido como Trade canônico com outcome=WIN
    history = repository.list_history("BTCUSDT_win")
    assert len(history) == 1
    assert history[0].outcome.value == "WIN"
    assert history[0].status.value == "CLOSED"


def test_paper_trader_losing_trade(repository, sample_personality):
    """Deve fechar uma posição perdedora e atualizar o saldo."""
    mock_risk_manager = MockRiskManager()
    paper_trader = PaperTrader(
        symbol="BTC/USDT",
        identity="BTCUSDT_loss",
        repository=repository,
        risk_manager=mock_risk_manager,
        initial_balance=1000.0,
        leverage=10,
        position_sizing_mode="fixed"
    )

    paper_trader.open_trade(
        direction="CALL",
        tf=300,
        current_epoch=1234567890,
        current_price=50000.0,
        sl_price=49000.0,
        tp_price=52000.0,
        atr=100.0,
        personality=sample_personality
    )

    # Preço atinge o Stop Loss
    finished = paper_trader.check_positions(
        current_epoch=1234567890 + 300,
        current_price=49000.0,
        personality=sample_personality
    )

    assert len(finished) == 1
    assert finished[0]["status"] == "LOSS"
    assert paper_trader.balance < 1000.0

    history = repository.list_history("BTCUSDT_loss")
    assert len(history) == 1
    assert history[0].outcome.value == "LOSS"


def test_paper_trader_persists_state(repository, sample_personality):
    """Deve persistir e recarregar o estado através do repositório."""
    mock_risk_manager = MockRiskManager()
    paper_trader = PaperTrader(
        symbol="BTC/USDT",
        identity="BTCUSDT_persist",
        repository=repository,
        risk_manager=mock_risk_manager,
        initial_balance=1000.0,
        leverage=10,
        position_sizing_mode="fixed"
    )
    paper_trader.open_trade(
        direction="CALL",
        tf=300,
        current_epoch=1234567890,
        current_price=50000.0,
        sl_price=49000.0,
        tp_price=52000.0,
        atr=100.0,
        personality=sample_personality
    )

    # Recria com o mesmo identity e repositório — deve carregar o estado salvo
    paper_trader_2 = PaperTrader(
        symbol="BTC/USDT",
        identity="BTCUSDT_persist",
        repository=repository,
        risk_manager=mock_risk_manager,
        initial_balance=1000.0,
        leverage=10,
        position_sizing_mode="fixed"
    )

    assert len(paper_trader_2.open_positions) == 1


def test_paper_trader_zero_cost_realizes_pure_pnl(repository, sample_personality):
    """Com custo zero, o PnL realizado deve ser o preço puro (sem fricção)."""
    mock_risk_manager = MockRiskManager()
    paper_trader = PaperTrader(
        symbol="BTC/USDT",
        identity="BTCUSDT_zero_cost",
        repository=repository,
        risk_manager=mock_risk_manager,
        initial_balance=1000.0,
        leverage=10,
        position_sizing_mode="fixed",
        cost_config=TradingCostConfig.zero(),
    )
    paper_trader.open_trade(
        direction="CALL",
        tf=300,
        current_epoch=1234567890,
        current_price=50000.0,
        sl_price=49000.0,
        tp_price=52000.0,
        atr=100.0,
        personality=sample_personality,
    )

    paper_trader.check_positions(
        current_epoch=1234567890 + 300,
        current_price=52000.0,
        personality=sample_personality,
    )

    # MockRiskManager: margin = 1000*0.02 = 20; qty = 20*10/50000 = 0.004.
    # gross CALL = (52000 - 50000) * 0.004 = 8.0, sem custo.
    assert paper_trader.balance == pytest.approx(1008.0, abs=0.01)


def test_paper_trader_fee_charged_on_both_legs(repository, sample_personality):
    """O custo deve ser cobrado sobre o notional de entrada E saída."""
    mock_risk_manager = MockRiskManager()
    paper_trader = PaperTrader(
        symbol="BTC/USDT",
        identity="BTCUSDT_fee_legs",
        repository=repository,
        risk_manager=mock_risk_manager,
        initial_balance=1000.0,
        leverage=10,
        position_sizing_mode="fixed",
        cost_config=TradingCostConfig(fee_rate=0.001, slippage_bps=0.0),
    )
    paper_trader.open_trade(
        direction="CALL",
        tf=300,
        current_epoch=1234567890,
        current_price=50000.0,
        sl_price=49000.0,
        tp_price=52000.0,
        atr=100.0,
        personality=sample_personality,
    )

    paper_trader.check_positions(
        current_epoch=1234567890 + 300,
        current_price=52000.0,
        personality=sample_personality,
    )

    # entry_notional = 200, exit_notional = 208; fees = 408 * 0.001 = 0.408.
    # net = 8.0 - 0.408 = 7.592.
    assert paper_trader.balance == pytest.approx(1007.592, abs=0.01)

