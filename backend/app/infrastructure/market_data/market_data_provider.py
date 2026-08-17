import asyncio
import logging
from typing import Dict, List, Callable
from app.infrastructure.market_data.binance_client import BinanceClient
from app.domain.entities.market import Tick

logger = logging.getLogger(__name__)

class MarketDataProvider:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MarketDataProvider, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.clients: Dict[str, BinanceClient] = {}
            self.subscribers: Dict[str, List[Callable[[Tick], None]]] = {}
            self._initialized = True

    async def _on_tick_received(self, tick: Tick):
        """Callback for when a new tick is received from a BinanceClient."""
        if tick.symbol in self.subscribers:
            for callback in self.subscribers[tick.symbol]:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(tick))
                else:
                    callback(tick)

    async def start_client_for_symbol(self, symbol: str):
        """Starts a BinanceClient for a given symbol if not already running."""
        if symbol not in self.clients:
            logger.info(f"[MarketDataProvider] Iniciando cliente Binance para {symbol}...")
            client = BinanceClient(symbol=symbol)
            client.add_tick_callback(self._on_tick_received)
            self.clients[symbol] = client
            asyncio.create_task(client.connect_and_listen())
        else:
            logger.info(f"[MarketDataProvider] Cliente Binance para {symbol} já está ativo.")

    def subscribe(self, symbol: str, callback: Callable[[Tick], None]):
        """Registers a callback to receive ticks for a specific symbol."""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = []
        self.subscribers[symbol].append(callback)
        logger.info(f"[MarketDataProvider] Callback registrado para {symbol}.")

    def unsubscribe(self, symbol: str, callback: Callable[[Tick], None]):
        """Unregisters a callback for a specific symbol."""
        if symbol in self.subscribers and callback in self.subscribers[symbol]:
            self.subscribers[symbol].remove(callback)
            if not self.subscribers[symbol]:
                del self.subscribers[symbol]
            logger.info(f"[MarketDataProvider] Callback removido para {symbol}.")

    async def stop_all_clients(self):
        """Stops all active BinanceClients."""
        for symbol, client in self.clients.items():
            logger.info(f"[MarketDataProvider] Parando cliente Binance para {symbol}...")
            client.stop()
        self.clients.clear()
        self.subscribers.clear()

