import logging
import asyncio

from app.domain.services.trade_executor_interface import AbstractTradeExecutor

logger = logging.getLogger(__name__)

class DerivExecutor(AbstractTradeExecutor):
    def __init__(self, deriv_client):
        self.deriv_client = deriv_client

    async def execute_entry(self, symbol: str, direction: str, stake_amount: float, duration_unit: str = "m", duration: int = 5):
        try:
            logger.info(f"🚀 [DerivExecutor] Executando ordem no simulador Deriv: {direction} | Ativo: {symbol} | Stake: ${stake_amount}")
            # The deriv_client's buy_contract method already handles sending the order
            await self.deriv_client.buy_contract(direction, stake_amount, duration_unit=duration_unit, duration=duration)
            logger.info(f"✅ [DerivExecutor] Ordem enviada para Deriv.")
            return {"status": "success", "message": "Order sent to Deriv."}
        except Exception as e:
            logger.error(f"❌ [DerivExecutor] Falha na execução da entrada no Deriv: {e}")
            return {"status": "error", "error": str(e)}

    async def execute_exit(self, symbol: str, direction: str, contract_id: str = None):
        # For binary options, "exiting" typically means waiting for the contract to expire.
        # However, if there's a sell_expired_early or similar, it would go here.
        # For now, we'll just log that there's no explicit exit for binary options like spot/futures.
        logger.info(f"🛑 [DerivExecutor] Não há execução de saída explícita para opções binárias (Deriv). Contrato {contract_id} expirará automaticamente.")
        return {"status": "success", "message": "No explicit exit for Deriv binary options."}
