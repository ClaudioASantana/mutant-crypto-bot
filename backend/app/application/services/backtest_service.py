"""
Serviço de Aplicação para Backtesting Avançado.

Encapsula a lógica de execução de backtests, incluindo download de dados,
cálculo de win rate para múltiplas estratégias e formatação dos resultados
para a API.
"""
import logging
import asyncio
import math
from typing import List, Dict, Any

from app.application.dtos.backtest_dto import BacktestRequestDTO
from scripts.optimizer import download_history
from app.domain.services.backtest_simulation_interface import AbstractBacktestSimulator
from app.domain.entities.personality import Personality, RiskProfile # Necessário para criar Personality no backtest

logger = logging.getLogger(__name__)

class BacktestService:
    """
    Serviço para executar e gerenciar backtests avançados.
    """

    def __init__(self, simulator: AbstractBacktestSimulator):
        self._simulator = simulator

    async def execute(self, req: BacktestRequestDTO) -> dict:
        """
        Executa um backtest avançado conforme a requisição.
        """
        logger.info(f"[{req.symbol}] Baixando histórico para backtest avançado...")

        history = await download_history(req.symbol, req.timeframe, req.limit)
        if not history:
            return {"error": "Falha ao baixar o histórico"}

        res = await asyncio.to_thread(self._run_simulation, history, req.strategy)

        # A implementação do simulador agora não retorna mais o df.
        # Precisamos recriá-lo para a formatação do gráfico, se necessário.
        # Por enquanto, vamos simplificar e não retornar o histórico para o gráfico
        # quando o foco é a análise de PnL.
        res.pop("df", None)
        # res["history"] = self._format_history_for_chart(df, history)

        return res

    def _run_simulation(self, history: list, strategy: str) -> dict:
        """
        Executa a simulação para uma ou várias estratégias usando o simulador injetado.
        """
        if strategy == "Auto":
            strategies = [
                "Momentum Breakout"
            ]
            best_res = None
            best_pnl = -float('inf')
            best_strategy = None

            for strat in strategies:
                personality = Personality(
                    name=f"Backtest_{strat}",
                    strategy=strat,
                    timeframe=300, # Assumindo M5, pode ser parametrizado se necessário
                    risk_profile=RiskProfile() # Usando perfil de risco padrão
                )
                strat_res = self._simulator.simulate_strategy(history, personality)
                pnl = strat_res.get("pnl_usdt", 0)
                if pnl > best_pnl:
                    best_pnl = pnl
                    best_res = strat_res
                    best_strategy = strat

            res = best_res
            if res:
                res["optimal_strategy"] = best_strategy
            return res or {}
        else:
            personality = Personality(
                name=f"Backtest_{strategy}",
                strategy=strategy,
                timeframe=300,
                risk_profile=RiskProfile()
            )
            return self._simulator.simulate_strategy(history, personality)

