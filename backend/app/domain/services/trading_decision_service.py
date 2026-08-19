"""
Serviço de Domínio para Decisão de Trade

Encapsula toda a lógica de avaliação de um sinal de trade, desde a
análise técnica e de IA até a avaliação de risco e cálculo de parâmetros.
"""
import logging
from typing import Optional

from app.domain.entities.personality import Personality
from app.domain.entities.market import AccountState, Signal, SignalType
from app.domain.services.ia_filter_interface import AbstractAIFilter
# Importa o registro de estratégias
from app.domain.services.strategy_registry import StrategyRegistry
from app.domain.services.news_filter_interface import AbstractNewsFilter
from app.domain.services.risk_manager_interface import AbstractRiskManager
from app.application.dtos.trade_dto import TradingSignalDTO

logger = logging.getLogger(__name__)

class TradingDecisionService:
    def __init__(self, news_filter: AbstractNewsFilter, ai_filter: AbstractAIFilter, risk_manager: AbstractRiskManager):
        self.news_filter = news_filter
        self.ai_filter = ai_filter
        self.risk_manager = risk_manager

    async def evaluate(self,
                 personality: Personality,
                 account_state: AccountState,
                 df_candles, # pandas DataFrame com velas
                 tick, # Tick atual
                 atr: float) -> Optional[TradingSignalDTO]:
        """
        Avalia se um trade deve ser aberto para uma dada personalidade.
        Retorna um objeto TradingSignalDTO se o trade for aprovado, senao None.
        """

        # 1. Filtro de Segurança de Notícias (macro)
        if not self.news_filter.check_safety(tick.epoch)["safe"]:
            return None

        # 2. Avaliação de Estratégia
        strategy_func = StrategyRegistry.get(personality.strategy)
        if not strategy_func:
            logger.warning(f"Estratégia '{personality.strategy}' não encontrada no STRATEGY_MAP.")
            return None

        signal_type = strategy_func(df_candles)

        if not signal_type or signal_type == "NONE":
            return None

        # 3. Filtro de IA
        ai_decision = await self.ai_filter.make_decision(df_candles, personality.strategy)
        if ai_decision["decision"] == "BUY" and signal_type == "CALL" and ai_decision["confidence"] >= 0.7:
            pass # Aprovado
        elif ai_decision["decision"] == "SELL" and signal_type == "PUT" and ai_decision["confidence"] >= 0.7:
            pass # Aprovado
        else:
            return None

        signal_type = SignalType(signal_type)

        # 4. Avaliação de Risco da Conta (usando o RiskManager injetado)
        signal = Signal(type=signal_type, reason=ai_decision["reason"])
        risk_eval = self.risk_manager.evaluate_pre_trade_risk(signal, account_state, personality)
        if risk_eval.decision != "APPROVED":
            return None

        # 5. Cálculo de SL/TP
        sl_mult = personality.risk_config.get("sl_multiplier", 1.5)
        tp_mult = personality.risk_config.get("tp_multiplier", 8.0)
        sl_price = tick.quote - (atr * sl_mult) if signal_type == SignalType.CALL else tick.quote + (atr * sl_mult)
        tp_price = tick.quote + (atr * tp_mult) if signal_type == SignalType.CALL else tick.quote - (atr * tp_mult)

        strategy_info = f"M{personality.timeframe//60}/{personality.strategy} (Conf: {ai_decision['confidence']:.2f})"

        return TradingSignalDTO(
            direction=signal_type,
            entry_price=tick.quote,
            sl_price=sl_price,
            tp_price=tp_price,
            atr=atr,
            reason=signal.reason,
            strategy_info=strategy_info
        )
