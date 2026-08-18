"""
Serviço de Aplicação para Backtesting Avançado.

Encapsula a lógica de execução de backtests, incluindo download de dados,
cálculo de win rate para múltiplas estratégias e formatação dos resultados
para a API.
"""
import logging
import asyncio
import math

from app.api.v1.schemas.trading import AdvancedBacktestRequest
from scripts.optimizer import download_history
from app.application.services.cataloger import calculate_win_rate

logger = logging.getLogger(__name__)

class BacktestService:
    """
    Serviço para executar e gerenciar backtests avançados.
    """

    async def execute(self, req: AdvancedBacktestRequest) -> dict:
        """
        Executa um backtest avançado conforme a requisição.

        Args:
            req (AdvancedBacktestRequest): O objeto de requisição com os parâmetros
                                           do backtest.

        Returns:
            dict: Os resultados do backtest, incluindo o histórico formatado.
        """
        logger.info(f"[{req.symbol}] Baixando histórico para backtest avançado...")

        history = await download_history(req.symbol, req.timeframe, req.limit)
        if not history:
            return {"error": "Falha ao baixar o histórico"}

        # Executa o cálculo pesado em outra thread para não bloquear o event loop
        res = await asyncio.to_thread(self._compute_win_rate, history, req.strategy)

        df = res.pop("df", None)
        res["history"] = self._format_history_for_chart(df, history)

        return res

    def _compute_win_rate(self, history: list, strategy: str) -> dict:
        """
        Calcula o win rate para uma ou várias estratégias.
        """
        if strategy == "Auto":
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
            if res:
                res["optimal_strategy"] = best_strategy
            return res or {}
        else:
            return calculate_win_rate(history, strategy)

    def _format_history_for_chart(self, df, fallback_history: list) -> list:
        """
        Formata o histórico (DataFrame ou lista) para o formato do lightweight-charts.
        """
        history_payload = []
        seen_times = set()

        if df is not None and not df.empty:
            df_to_process = df.tail(1000) if len(df) > 1000 else df

            for timestamp, row in df_to_process.iterrows():
                epoch = int(timestamp.timestamp())
                if epoch not in seen_times:
                    payload = self._create_candle_payload(row)
                    history_payload.append(payload)
                    seen_times.add(epoch)
        else:
            for c in fallback_history:
                if c.epoch not in seen_times:
                    history_payload.append({
                        "time": c.epoch, "open": c.open, "high": c.high,
                        "low": c.low, "close": c.close
                    })
                    seen_times.add(c.epoch)

        return history_payload

    def _create_candle_payload(self, row) -> dict:
        """Cria o payload de uma vela individual com todos os indicadores."""
        payload = {
            "time": int(row.name.timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }

        # Adiciona indicadores se existirem e não forem NaN
        if "volume" in row and not math.isnan(row["volume"]):
            payload["volume"] = float(row["volume"])

        self._add_indicator_payload(payload, row, "bb_upper", "BBU_")
        self._add_indicator_payload(payload, row, "bb_middle", "BBM_")
        self._add_indicator_payload(payload, row, "bb_lower", "BBL_")
        self._add_indicator_payload(payload, row, "macd_line", "MACD_")
        self._add_indicator_payload(payload, row, "macd_hist", "MACDh_")
        self._add_indicator_payload(payload, row, "macd_signal", "MACDs_")

        return payload

    def _add_indicator_payload(self, payload: dict, row, payload_key: str, col_prefix: str):
        """Adiciona um valor de indicador ao payload se ele existir."""
        col = next((c for c in row.index if c.startswith(col_prefix)), None)
        if col and not math.isnan(row[col]):
            payload[payload_key] = float(row[col])
