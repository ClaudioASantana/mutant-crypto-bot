import logging

from app.core.operational_config import load_operational_config

logger = logging.getLogger(__name__)

class BinanceExecutor:
    def __init__(self, exchange):
        self.exchange = exchange

    def _assert_live_allowed(self) -> bool:
        """Fail-closed: só permite ordem real quando o modo operacional autoriza explicitamente."""
        cfg = load_operational_config()
        if not cfg.live_execution_allowed:
            logger.error(f"[BinanceExecutor] Bloqueado: execution_mode={cfg.execution_mode.value} "
                         f"live_trading_enabled={cfg.live_trading_enabled}. Ordem real não autorizada.")
            return False
        return True

    async def set_leverage(self, symbol: str, leverage: int):
        try:
            # Em CCXT Binance Futures, set_leverage requer o símbolo convertido ou formatado
            await self.exchange.set_leverage(leverage, symbol)
            logger.info(f"[{symbol}] Alavancagem confirmada para {leverage}x na Binance")
        except Exception as e:
            logger.warning(f"[{symbol}] Falha ao ajustar alavancagem para {leverage}x (pode já estar ajustada): {e}")

    async def execute_entry(self, symbol: str, direction: str, margin_usdt: float, leverage: int, current_price: float):
        if not self._assert_live_allowed():
            return {"status": "error", "error": "execution_blocked_live_not_authorized"}

        try:
            await self.set_leverage(symbol, leverage)

            # Position size em dólares alavancados
            position_usd = margin_usdt * leverage

            # Quantidade da moeda a comprar/vender
            qty = position_usd / current_price

            # Ajuste rápido de precisão (Binance Testnet aceita 3 casas decimais para BTC)
            # Idealmente isso vem do self.exchange.markets[symbol]['precision']
            qty = round(qty, 3)
            if qty == 0:
                logger.error(f"[{symbol}] Quantidade 0 após arredondamento. Margem insuficiente.")
                return {"status": "error", "error": "qty_zero"}

            side = "buy" if direction == "CALL" else "sell"

            logger.info(f"🚀 [{symbol}] Executando entrada LIVE: {side.upper()} | Margem: ${margin_usdt:.2f} | Qtd: {qty}")
            order = await self.exchange.create_market_order(symbol, side, qty)
            logger.info(f"✅ [{symbol}] Ordem LIVE preenchida! ID: {order['id']}")
            return {"status": "success", "qty": qty, "order": order}
        except Exception as e:
            logger.error(f"❌ [{symbol}] Falha na execução da entrada LIVE: {e}")
            return {"status": "error", "error": str(e)}

    async def execute_exit(self, symbol: str, direction: str, qty: float):
        if not self._assert_live_allowed():
            return {"status": "error", "error": "execution_blocked_live_not_authorized"}

        try:
            # Para sair de um CALL (Long), fazemos uma ordem de SELL. Para sair de PUT, BUY.
            side = "sell" if direction == "CALL" else "buy"

            logger.info(f"🛑 [{symbol}] Executando saída LIVE: {side.upper()} | Qtd: {qty}")

            # Em Binance hedging mode (padrão costuma ser one-way, mas às vezes exige 'reduceOnly')
            # Vamos usar reduceOnly para garantir que não inverta a posição acidentalmente
            params = {'reduceOnly': True}

            order = await self.exchange.create_market_order(symbol, side, qty, params)
            logger.info(f"✅ [{symbol}] Ordem de saída LIVE preenchida! ID: {order['id']}")
            return {"status": "success", "order": order}
        except Exception as e:
            logger.error(f"❌ [{symbol}] Falha na execução da saída LIVE: {e}")
            return {"status": "error", "error": str(e)}
