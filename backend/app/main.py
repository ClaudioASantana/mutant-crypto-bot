import asyncio
import logging
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from app.application.services.trading_orchestrator import TradingOrchestrator
from app.infrastructure.services.news_filter import NewsFilter
from app.infrastructure.market_data.market_data_provider import MarketDataProvider
from app.infrastructure.repositories.json_paper_trader_repository import JsonPaperTraderRepository
from app.infrastructure.ai_filter_openai import OpenAIFilter
from app.infrastructure.config_loader import ConfigurationLoader
from app.infrastructure.websocket.connection_manager import ConnectionManager
from app.api.v1.routers.trading import router as trading_router
from app.core.state import bots, watching_symbol, set_watching_symbol

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instâncias de infraestrutura (escopo de módulo — usadas pelo lifespan e WS endpoint)
manager = ConnectionManager()

# Carrega a configuração dos portfólios a partir do arquivo JSON
config_loader = ConfigurationLoader()
active_portfolios = config_loader.load_portfolios_from_json("config/portfolios.json")
active_symbols = list(active_portfolios.keys())

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando o ENXAME (Swarm)... Levantando bots com personalidades!")

    # Composition Root: instancia as implementações concretas (infraestrutura)
    market_provider = MarketDataProvider()
    repository = JsonPaperTraderRepository("data")
    news_filter = NewsFilter()
    ai_filter = OpenAIFilter()

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
            repository=repository,
            swarm_bots=bots
        )
        bots[sym] = bot
        asyncio.create_task(bot.start())
        await market_provider.start_client_for_symbol(sym)

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
