import asyncio
import logging
import json
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

from app.application.services.trading_orchestrator import TradingOrchestrator
from app.infrastructure.services.news_filter import NewsFilter
from app.infrastructure.market_data.market_data_provider import MarketDataProvider
from app.infrastructure.repositories.json_paper_trader_repository import JsonPaperTraderRepository
from app.infrastructure.ai_filter_openai import OpenAIFilter
from app.infrastructure.config_loader import ConfigurationLoader, ServiceResolver
from app.infrastructure.websocket.connection_manager import ConnectionManager
from app.api.v1.routers.trading import router as trading_router
from app.core.state import bots, watching_symbol, set_watching_symbol
from app.infrastructure.services.paper_trader_executor import PaperTrader
from app.infrastructure.services.risk_manager import RiskManager
from app.infrastructure.repositories.in_memory_paper_trader_repository import InMemoryPaperTraderRepository
from app.infrastructure.services.backtest_simulation_impl import BacktestSimulatorImpl
from app.application.services.backtest_service import BacktestService

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Registro de Implementações Concretas ---
ServiceResolver.register("JsonPaperTraderRepository", JsonPaperTraderRepository)
ServiceResolver.register("NewsFilter", NewsFilter)
ServiceResolver.register("OpenAIFilter", OpenAIFilter)
ServiceResolver.register("MarketDataProvider", MarketDataProvider)
ServiceResolver.register("PaperTrader", PaperTrader)
ServiceResolver.register("RiskManager", RiskManager)
ServiceResolver.register("BacktestSimulator", BacktestSimulatorImpl)
# ---------------------------------------------

# Instâncias de infraestrutura (escopo de módulo — usadas pelo lifespan e WS endpoint)
manager = ConnectionManager()

# Carrega a configuração dos portfólios a partir do arquivo JSON
config_loader = ConfigurationLoader()
active_portfolios = config_loader.load_portfolios_from_json("config/portfolios.json")
active_symbols = list(active_portfolios.keys())

# Carrega e constrói os serviços de infraestrutura
service_configs = config_loader.load_service_configs_from_json("config/services.json")
services = config_loader.build_services(service_configs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando o ENXAME (Swarm)... Levantando bots com personalidades!")

    # Composition Root: usa os serviços instanciados via configuração
    market_provider = services["market_data_provider"]
    repository = services["paper_trader_repository"]
    news_filter = services["news_filter"]
    ai_filter = services["ai_filter"]
    risk_manager = services["risk_manager"]
    TradeExecutorImpl = ServiceResolver.get(service_configs["trade_executor"]["implementation"])

    # Factory para o Trade Executor
    def trade_executor_factory(**kwargs):
        return TradeExecutorImpl(repository=repository, **kwargs)

    for sym in active_symbols:
        personalities = active_portfolios[sym]
        bot = TradingOrchestrator(
            symbol=sym,
            token="",
            news_filter=news_filter,
            manager=manager,
            personalities=personalities,
            ai_filter=ai_filter,
            market_provider=market_provider,
            trade_executor_factory=trade_executor_factory,
            risk_manager=risk_manager,
            swarm_bots=bots
        )
        bots[sym] = bot
        asyncio.create_task(bot.start())
        await market_provider.start_client_for_symbol(sym)

    # Injeta o BacktestService no app state para uso pelas rotas da API
    # Factory para criar PaperTrader com repositório em memória para backtesting
    def backtest_trader_factory(identity: str):
        return PaperTrader(
            symbol="BTC/USDT_BACKTEST",
            identity=identity,
            repository=InMemoryPaperTraderRepository(),
            risk_manager=risk_manager,
            initial_balance=200.0,
            leverage=10,
            position_sizing_mode="fixed"
        )

    backtest_simulator = BacktestSimulatorImpl(risk_manager, backtest_trader_factory)
    backtest_service = BacktestService(backtest_simulator)

    # Injeta o backtest_service no router. Uma abordagem mais robusta usaria
    # o sistema de dependências do FastAPI com Depends().
    trading_router.backtest_service = backtest_service

    yield
    logger.info("Desligando o ENXAME...")
    for bot in bots.values():
        bot.stop()
    await market_provider.stop_all_clients()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://0.0.0.0:3000", "http://192.168.1.9:3010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trading_router)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket, watching_symbol)

    # Envia estado inicial para o símbolo assistido
    if watching_symbol in bots:
        b = bots[watching_symbol]
        for p_name, trader in b.paper_traders.items():
            state = trader.get_state()
            state["personality_name"] = p_name
            await websocket.send_json({"event": "simulator", "symbol": watching_symbol, "data": state})

    await websocket.send_json({"event": "active_symbol", "data": watching_symbol})

    try:
        while True:
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("command") == "WATCH_SYMBOL" or cmd.get("command") == "SET_SYMBOL":
                    new_sym = cmd.get("symbol")
                    if new_sym and new_sym in bots:
                        manager.set_watched_symbol(websocket, new_sym)
                        set_watching_symbol(new_sym)
                        await manager.broadcast({"event": "active_symbol", "data": new_sym})

                        b = bots[new_sym]

                        first_p = next(iter(b.personalities.values()), None)
                        if first_p:
                            builder = b.get_builder_for_timeframe(first_p.timeframe)
                            if builder:
                                history = [{"time": c.epoch, "open": c.open, "high": c.high, "low": c.low, "close": c.close} for c in builder.closed_candles]
                                await websocket.send_json({"event": "chart_history", "symbol": new_sym, "data": history[-200:]})

                        for p_name, trader in b.paper_traders.items():
                             state = trader.get_state()
                             state["personality_name"] = p_name
                             await websocket.send_json({"event": "simulator", "symbol": new_sym, "data": state})

                        if hasattr(b, 'global_catalog'):
                            await websocket.send_json({"event": "catalog", "symbol": new_sym, "data": {"catalog": b.global_catalog, "auto_optimize": b.auto_optimize}})

                elif cmd.get("command") == "TOGGLE_AUTO_OPTIMIZE":
                    target_symbol = manager.active_connections.get(websocket, watching_symbol)
                    if target_symbol in bots:
                        b = bots[target_symbol]
                        b.auto_optimize = not b.auto_optimize
                        logger.info(f"[{target_symbol}] Auto-Optimize: {b.auto_optimize}")
                        if hasattr(b, 'broadcast_catalog'):
                           asyncio.create_task(b.broadcast_catalog())

                elif cmd.get("command") == "TOGGLE_AUTO_OPTIMIZE_ALL":
                    is_active = cmd.get("active", True)
                    for sym, bot_inst in bots.items():
                        bot_inst.auto_optimize = is_active
                        logger.info(f"[{sym}] Auto-Optimize Global: {bot_inst.auto_optimize}")
                        if hasattr(bot_inst, 'broadcast_catalog'):
                            asyncio.create_task(bot_inst.broadcast_catalog())

            except Exception as e:
                logger.error(f"Erro processando WS: {e}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
