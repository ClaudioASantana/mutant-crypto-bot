"""
Serviço de Aplicação para Otimização de Estratégias.

Esta camada contém a lógica de negócio para a otimização,
separando-a da camada de apresentação (API).
"""
import logging
from scripts.optimizer import download_history, run_simulation

logger = logging.getLogger(__name__)

class OptimizationService:
    """
    Serviço responsável por executar a otimização de parâmetros para estratégias.
    """

    async def execute(self, symbol: str) -> dict:
        """
        Executa a otimização para um determinado símbolo.

        Args:
            symbol (str): O símbolo do ativo a ser otimizado (ex: "BTC/USDT").

        Returns:
            dict: Um dicionário contendo os resultados da otimização.
        """
        results = []
        logger.info(f"[{symbol}] Baixando histórico para otimização...")
        history_m5 = await download_history(symbol, 300, 5000)
        history_m1 = await download_history(symbol, 60, 5000)

        for history, timeframe_name in [(history_m5, "M5"), (history_m1, "M1")]:
            if not history:
                continue
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
