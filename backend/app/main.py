import asyncio
import logging
import time
import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from app.application.services.bot_instance import BotInstance
from app.application.services.news import NewsFilter

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        # Defaults to watching R_100
        self.active_connections[websocket] = "R_100"

    def set_watched_symbol(self, websocket: WebSocket, symbol: str):
        if websocket in self.active_connections:
            self.active_connections[websocket] = symbol

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, message: dict):
        try:
            msg_str = json.dumps(message)
        except Exception as e:
            print(f"FAILED TO DUMP JSON: {e}")
            print(message)
            return
            
        msg_symbol = message.get("symbol")
        for connection, watched_symbol in list(self.active_connections.items()):
            # Se a mensagem pertence a um simbolo, enviar so se o client estiver assistindo
            if msg_symbol and msg_symbol != watched_symbol:
                continue
            try:
                await connection.send_text(msg_str)
            except Exception:
                pass

manager = ConnectionManager()
news_filter = NewsFilter()


# --- SWARM STATE ---
bots: dict[str, BotInstance] = {}
from app.domain.entities.personality import Personality

# Define active portfolios - each symbol has multiple personalities
active_portfolios = {
    "BTC/USDT": [
        Personality(name="Cirurgiao_M15", strategy="Wyckoff_SMC", timeframe=900, risk_config={"sl_multiplier": 1.5, "tp_multiplier": 8.0}),
        Personality(name="Trabalhador_M5", strategy="SMC", timeframe=300, risk_config={"sl_multiplier": 1.5, "tp_multiplier": 3.0}),
    ],
    "ETH/USDT": [
        Personality(name="Cirurgiao_M15", strategy="Wyckoff_SMC", timeframe=900, risk_config={"sl_multiplier": 1.5, "tp_multiplier": 8.0}),
        Personality(name="Trabalhador_M5", strategy="SMC", timeframe=300, risk_config={"sl_multiplier": 1.5, "tp_multiplier": 3.0}),
    ],
    "SOL/USDT": [
        Personality(name="Cirurgiao_M15", strategy="Wyckoff_SMC", timeframe=900, risk_config={"sl_multiplier": 1.5, "tp_multiplier": 8.0}),
        Personality(name="Trabalhador_M5", strategy="SMC", timeframe=300, risk_config={"sl_multiplier": 1.5, "tp_multiplier": 3.0}),
    ],
    "BNB/USDT": [
        Personality(name="Cirurgiao_M15", strategy="Wyckoff_SMC", timeframe=900, risk_config={"sl_multiplier": 1.5, "tp_multiplier": 8.0}),
        Personality(name="Trabalhador_M5", strategy="SMC", timeframe=300, risk_config={"sl_multiplier": 1.5, "tp_multiplier": 3.0}),
    ]
}

# Get active symbols from portfolio keys
active_symbols = list(active_portfolios.keys())

watching_symbol = "BTC/USDT" # Global state for what the frontend is watching (for backward compatibility of /status)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando o ENXAME (Swarm)... Levantando bots com personalidades!")

    # Initialize MarketDataProvider
    from app.infrastructure.market_data.market_data_provider import MarketDataProvider
    market_provider = MarketDataProvider()

    for sym in active_symbols:
        # Create BotInstance with personalities for this symbol
        personalities = active_portfolios[sym]
        bot = BotInstance(symbol=sym, token="", news_filter=news_filter, manager=manager, personalities=personalities, swarm_bots=bots)
        bots[sym] = bot
        asyncio.create_task(bot.start())
        # Start Binance client via MarketDataProvider
        await market_provider.start_client_for_symbol(sym)


    yield
    # Shutdown
    logger.info("Desligando o ENXAME...")
    for bot in bots.values():
        bot.stop()
    await market_provider.stop_all_clients()

from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://0.0.0.0:3000", "http://192.168.1.9:3010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    global watching_symbol
    
    if watching_symbol in bots:
        b = bots[watching_symbol]
        # Send state for all personalities
        for p_name, trader in b.paper_traders.items():
            state = trader.get_state()
            state["personality_name"] = p_name # Add personality name to state
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
                        watching_symbol = new_sym
                        await manager.broadcast({"event": "active_symbol", "data": new_sym})
                        # Mandar o estado mais recente desse bot pro frontend
                        b = bots[new_sym]

                        # Fetch history and map to lightweight-charts format
                        # Find the personality with the smallest timeframe to display its history
                        first_personality = b.personalities.get(next(iter(b.personalities))) if b.personalities else None
                        if first_personality:
                            active_b = b.get_builder_for_timeframe(first_personality.timeframe)
                            history_payload = []
                            seen_times = set()
                            sorted_candles = sorted(active_b.closed_candles, key=lambda x: x.epoch)
                            for c in sorted_candles:
                                if c.epoch not in seen_times:
                                    history_payload.append({
                                        "time": c.epoch,
                                        "open": c.open,
                                        "high": c.high,
                                        "low": c.low,
                                        "close": c.close
                                    })
                                    seen_times.add(c.epoch)
                            await websocket.send_json({"event": "chart_history", "symbol": new_sym, "data": history_payload})

                        for p_name, trader in b.paper_traders.items():
                             state = trader.get_state()
                             state["personality_name"] = p_name
                             await websocket.send_json({"event": "simulator", "symbol": new_sym, "data": state})

                        # TODO: active_config is deprecated, catalog should not send it.
                        await websocket.send_json({"event": "catalog", "symbol": new_sym, "data": {"catalog": b.global_catalog, "auto_optimize": b.auto_optimize}})

                # elif cmd.get("command") == "SET_CONFIG":
                #     # TODO: This needs to be refactored to target a specific personality
                #     logger.warning("SET_CONFIG command is temporarily disabled due to multi-personality architecture.")

                elif cmd.get("command") == "TOGGLE_AUTO_OPTIMIZE":
                    target_symbol = manager.active_connections.get(websocket, watching_symbol)
                    if target_symbol in bots:
                        b = bots[target_symbol]
                        b.auto_optimize = not b.auto_optimize
                        logger.info(f"[{target_symbol}] Auto-Optimize: {b.auto_optimize}")
                        asyncio.create_task(b.broadcast_catalog())
                elif cmd.get("command") == "TOGGLE_AUTO_OPTIMIZE_ALL":
                    is_active = cmd.get("active", True)
                    for sym, bot_inst in bots.items():
                        bot_inst.auto_optimize = is_active
                        logger.info(f"[{sym}] Auto-Optimize Global: {bot_inst.auto_optimize}")
                        asyncio.create_task(bot_inst.broadcast_catalog())
            except Exception as e:
                logger.error(f"Erro processando WS: {e}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/status")
def get_status():
    if watching_symbol not in bots:
        return {"status": "running_swarm", "bots_active": len(bots)}

    b = bots[watching_symbol]

    # Collect states from all personalities
    personalities_states = {}
    for p_name, trader in b.paper_traders.items():
        personalities_states[p_name] = trader.get_state()

    # Get the builder for the first personality's timeframe (for backward compatibility)
    first_personality = b.personalities.get(next(iter(b.personalities))) if b.personalities else None
    current_candle = None
    closed_candles_count = 0
    if first_personality:
        builder = b.get_builder_for_timeframe(first_personality.timeframe)
        if builder:
            current_candle = builder.current_candle
            closed_candles_count = len(builder.closed_candles)

    return {
        "status": "running",
        "watched_symbol": watching_symbol,
        "current_candle": current_candle,
        "closed_candles_count": closed_candles_count,
        "personalities": personalities_states,
        "auto_optimize": b.auto_optimize,
        "news_status": news_filter.check_safety(int(time.time()))
    }

@app.get("/portfolio")
def get_portfolio():
    # Retorna o saldo global somado de todos os bots e todas as suas personalidades
    total_balance = 0.0
    total_pnl = 0.0

    for bot in bots.values():
        for trader in bot.paper_traders.values():
            total_balance += trader.balance
            total_pnl += trader.get_pnl()

    return {
        "total_balance": total_balance,
        "total_pnl": total_pnl,
        "bots_count": len(bots)
    }

@app.get("/api/chart_history")
def get_chart_history(symbol: str):
    history_payload = []
    if symbol in bots:
        b = bots[symbol]
        # Use the timeframe of the first personality for chart history
        first_personality = b.personalities.get(next(iter(b.personalities))) if b.personalities else None
        if first_personality:
            active_b = b.get_builder_for_timeframe(first_personality.timeframe)
            seen_times = set()
            for c in sorted(active_b.closed_candles, key=lambda x: x.epoch):
                if c.epoch not in seen_times:
                    history_payload.append({
                        "time": c.epoch,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "close": c.close
                    })
                    seen_times.add(c.epoch)

    return {"data": history_payload[-200:]}

from pydantic import BaseModel
class OptimizeRequest(BaseModel):
    symbol: str

@app.post("/api/optimize")
async def api_optimize(req: OptimizeRequest):
    import sys
    import os
    scripts_path = os.path.join(os.path.dirname(__file__), '..', 'scripts')
    if scripts_path not in sys.path:
        sys.path.append(scripts_path)
    from optimizer import download_history, run_simulation
    
    results = []
    logger.info(f"[{req.symbol}] Baixando histórico para otimização...")
    history_m5 = await download_history(req.symbol, 300, 5000)
    history_m1 = await download_history(req.symbol, 60, 5000)
    
    for history, timeframe_name in [(history_m5, "M5"), (history_m1, "M1")]:
        if not history: continue
        for consecutive_candles in [3, 5, 7, 9]:
            for rsi_combo in [(35, 65), (30, 70), (25, 75)]:
                rsi_over, rsi_under = rsi_combo
                res = run_simulation(
                    history,
                    consecutive_candles,
                    rsi_over,
                    rsi_under,
                    stake=10.0,
                    payout_rate=0.95
                )
                total = res['wins'] + res['losses']
                win_rate = (res['wins'] / total * 100) if total > 0 else 0
                results.append({
                    "timeframe": 300 if timeframe_name == "M5" else 60,
                    "timeframe_label": timeframe_name,
                    "candles": consecutive_candles,
                    "rsi_oversold": rsi_over,
                    "rsi_overbought": rsi_under,
                    "rsi_label": f"{rsi_over}/{rsi_under}",
                    "wins": res['wins'],
                    "losses": res['losses'],
                    "win_rate": win_rate,
                    "pnl": res['pnl']
                })

        results.sort(key=lambda x: x['pnl'], reverse=True)
    return {"results": results[:5]}

class AdvancedBacktestRequest(BaseModel):
    symbol: str
    timeframe: int
    limit: int
    strategy: str

@app.post("/api/backtest_advanced")
async def api_backtest_advanced(req: AdvancedBacktestRequest):
    import sys
    import os
    scripts_path = os.path.join(os.path.dirname(__file__), '..', 'scripts')
    if scripts_path not in sys.path:
        sys.path.append(scripts_path)
    from optimizer import download_history
    from app.application.services.cataloger import calculate_win_rate
    
    logger.info(f"[{req.symbol}] Baixando histórico para backtest avançado...")
    
    # Executa o block sync (download + DB insert + calculo pandas) em uma thread separada!
    def run_heavy_backtest():
        # download_history is async, but wait, if it's async we can't just run it in a thread easily
        # Actually, download_history is async, so we await it normally.
        # But wait, download_history is async! We can await it.
        # The blocking part is calculate_win_rate (pandas).
        pass

    history = await download_history(req.symbol, req.timeframe, req.limit)
    if not history:
        return {"error": "Falha ao baixar o histórico"}
        
    def _compute_win_rate():
        if req.strategy == "Auto":
            strategies = ["3 Velas", "EMA+MACD", "Bollinger", "VWAP", "SMC", "SuperTrend", "Pin Bar"]
            best_res = None
            best_pnl = -float('inf')
            best_strategy = None
            
            for strat in strategies:
                strat_res = calculate_win_rate(history, strat)
                pnl = strat_res.get("pnl_usdt", 0)
                if pnl > best_pnl:
                    best_pnl = pnl
                    best_res = strat_res
                    best_strategy = strat
                    
            res = best_res
            res["optimal_strategy"] = best_strategy
            return res
        else:
            return calculate_win_rate(history, req.strategy)
            
    # Executa o cálculo pesado no pandas em outra thread (desbloqueia o Event Loop!)
    res = await asyncio.to_thread(_compute_win_rate)
    
    import math
    df = res.pop("df", None)
    
    # Mapear o histórico para o formato do lightweight-charts
    history_payload = []
    seen_times = set()
    
    if df is not None and not df.empty:
        if len(df) > 1000:
            df = df.tail(1000)
            
        for timestamp, row in df.iterrows():
            epoch = int(timestamp.timestamp())
            if epoch not in seen_times:
                payload = {
                    "time": epoch,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"])
                }
                
                # Volume
                if "volume" in row and not math.isnan(row["volume"]):
                    payload["volume"] = float(row["volume"])
                    
                # Bollinger Bands
                bbu_col = next((col for col in row.index if col.startswith("BBU_")), None)
                bbm_col = next((col for col in row.index if col.startswith("BBM_")), None)
                bbl_col = next((col for col in row.index if col.startswith("BBL_")), None)
                
                if bbu_col and not math.isnan(row[bbu_col]):
                    payload["bb_upper"] = float(row[bbu_col])
                if bbm_col and not math.isnan(row[bbm_col]):
                    payload["bb_middle"] = float(row[bbm_col])
                if bbl_col and not math.isnan(row[bbl_col]):
                    payload["bb_lower"] = float(row[bbl_col])
                
                # MACD
                macd_line = next((col for col in row.index if col.startswith("MACD_")), None)
                macd_hist = next((col for col in row.index if col.startswith("MACDh_")), None)
                macd_signal = next((col for col in row.index if col.startswith("MACDs_")), None)
                
                if macd_line and not math.isnan(row[macd_line]):
                    payload["macd_line"] = float(row[macd_line])
                if macd_hist and not math.isnan(row[macd_hist]):
                    payload["macd_hist"] = float(row[macd_hist])
                if macd_signal and not math.isnan(row[macd_signal]):
                    payload["macd_signal"] = float(row[macd_signal])
                    
                history_payload.append(payload)
                seen_times.add(epoch)
    else:
        # Fallback if no df
        for c in history:
            if c.epoch not in seen_times:
                history_payload.append({
                    "time": c.epoch,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close
                })
                seen_times.add(c.epoch)
            
    res["history"] = history_payload
    return res

class RiskSettingsRequest(BaseModel):
    stake_initial: float
    daily_stop_loss: float
    daily_stop_gain: float

@app.get("/api/risk_settings")
def get_risk_settings():
    if bots:
        # Pega o primeiro bot e a primeira personalidade para compatibilidade com o frontend
        b = list(bots.values())[0]
        if b.personalities:
            first_personality_name = next(iter(b.personalities.keys()))
            first_trader = b.paper_traders[first_personality_name]
            return {
                "stake_initial": first_trader.stake_initial,
                "daily_stop_loss": first_trader.daily_stop_loss,
                "daily_stop_gain": first_trader.daily_stop_gain
            }
    return {
        "stake_initial": 10.0,
        "daily_stop_loss": 50.0,
        "daily_stop_gain": 50.0
    }

@app.post("/api/risk_settings")
def set_risk_settings(req: RiskSettingsRequest):
    settings = {
        "stake_initial": req.stake_initial,
        "daily_stop_loss": req.daily_stop_loss,
        "daily_stop_gain": req.daily_stop_gain
    }
    for bot in bots.values():
        for trader in bot.paper_traders.values():
            trader.stake_initial = req.stake_initial
            trader.daily_stop_loss = req.daily_stop_loss
            trader.daily_stop_gain = req.daily_stop_gain
            trader.save_state()
    return {"status": "ok", "settings": settings}
