import asyncio
import json
import logging
import websockets
import ccxt.async_support as ccxt
import time
from typing import Callable, List, Dict

logger = logging.getLogger(__name__)

class BinanceClient:
    def __init__(self, symbol: str = "BTC/USDT"):
        self.symbol = symbol
        # Convert ccxt symbol to binance stream symbol (e.g. BTC/USDT -> btcusdt)
        self.stream_symbol = symbol.replace("/", "").lower()
        self.tick_callbacks: List[Callable] = []
        self.history_callbacks: List[Callable] = []
        self._running = False
        self.exchange = ccxt.binance()

    def add_tick_callback(self, callback: Callable):
        self.tick_callbacks.append(callback)

    def add_history_callback(self, callback: Callable):
        self.history_callbacks.append(callback)

    async def fetch_history(self, timeframe_seconds: int = 60, limit: int = 1000):
        # Map seconds to binance timeframes
        tf_map = {60: '1m', 300: '5m', 900: '15m', 3600: '1h'}
        tf = tf_map.get(timeframe_seconds, '1m')
        
        try:
            ohlcv = await self.exchange.fetch_ohlcv(self.symbol, tf, limit=limit)
            candles = []
            for c in ohlcv:
                candles.append({
                    "epoch": int(c[0] / 1000),
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4]
                })
            
            for cb in self.history_callbacks:
                if asyncio.iscoroutinefunction(cb):
                    await cb(timeframe_seconds, candles)
                else:
                    cb(timeframe_seconds, candles)
                    
        except Exception as e:
            logger.error(f"Erro baixando historico Binance para {self.symbol}: {e}")

    async def connect_and_listen(self):
        self._running = True
        
        # Download historical data before starting live stream
        logger.info(f"[{self.symbol}] Baixando historico...")
        await self.fetch_history(60)
        await self.fetch_history(300)
        await self.fetch_history(900)
        await self.exchange.close()
        
        stream_url = f"wss://stream.binance.com:9443/ws/{self.stream_symbol}@trade"
        logger.info(f"[{self.symbol}] Conectando ao websocket da Binance: {stream_url}")
        
        while self._running:
            try:
                async with websockets.connect(stream_url) as ws:
                    logger.info(f"[{self.symbol}] Binance WS Conectado!")
                    while self._running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        # Binance trade stream payload:
                        # "p": "0.001", "T": 123456785, ...
                        from app.models.market import Tick
                        
                        price = float(data['p'])
                        epoch = int(data['T'] / 1000)
                        tick = Tick(epoch=epoch, quote=price, symbol=self.symbol)
                        
                        for cb in self.tick_callbacks:
                            if asyncio.iscoroutinefunction(cb):
                                await cb(tick)
                            else:
                                cb(tick)
                                
            except Exception as e:
                if self._running:
                    logger.error(f"[{self.symbol}] Binance WS Error: {e}. Reconectando em 5s...")
                    await asyncio.sleep(5)
                
    def stop(self):
        self._running = False
