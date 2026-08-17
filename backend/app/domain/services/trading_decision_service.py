"""
Serviço de Domínio para Decisão de Trade

Encapsula toda a lógica de avaliação de um sinal de trade, desde a
análise técnica e de IA até a avaliação de risco e cálculo de parâmetros.
"""
import logging
from typing import Optional
from pydantic import BaseModel

from app.domain.entities.personality import Personality
from app.domain.entities.market import AccountState, Signal, SignalType
from app.application.services.ai_filter import AIFilter
from app.application.services.risk import evaluate_risk
from app.application.services.technical_analysis import eval_three_candles_composite

logger = logging.getLogger(__name__)

class TradeDecision(BaseModel):
    """Objeto que representa uma decisão de trade aprovada."""
    direction: SignalType
    entry_price: float
    sl_price: float
    tp_price: float
    atr: float
    reason: str
    strategy_info: str

class TradingDecisionService:
    def __init__(self, news_filter, ai_filter: AIFilter):
        self.news_filter = news_filter
        self.ai_filter = ai_filter

    async def evaluate(self,
                 personality: Personality,
                 account_state: AccountState,
                 df_candles, # pandas DataFrame com velas
                 tick, # Tick atual
                 atr: float) -> Optional[TradeDecision]:
        """
        Avalia se um trade deve ser aberto para uma dada personalidade.
        Retorna um objeto TradeDecision se o trade for aprovado, senao None.
        """

        # 1. Filtro de Segurança de Notícias (macro)
        if not self.news_filter.check_safety(tick.epoch)["safe"]:
            return None

        # 2. Avaliação de Estratégia + Confirmação de 3 Velas
        signal_type = eval_three_candles_composite(df_candles, require_confluence=True)

        if not signal_type or signal_type == "NONE":
            return None

        # 3. Filtro de IA
        ai_decision = await self.ai_filter.make_decision(df_candles, personality.strategy)
        if ai_decision["decision"] == "BUY" and signal_type == SignalType.CALL and ai_decision["confidence"] >= 0.7:
            pass # Aprovado
        elif ai_decision["decision"] == "SELL" and signal_type == SignalType.PUT and ai_decision["confidence"] >= 0.7:
            pass # Aprovado
        else:
            return None

        # 4. Avaliação de Risco da Conta
        signal = Signal(type=signal_type, reason=ai_decision["reason"] + " | 3V-Confirmed")
        risk_eval = evaluate_risk(signal, account_state)
        if risk_eval.decision != "APPROVED":
            return None

        # 5. Cálculo de SL/TP
        sl_mult = personality.risk_config.get("sl_multiplier", 1.5)
        tp_mult = personality.risk_config.get("tp_multiplier", 8.0)
        sl_price = tick.quote - (atr * sl_mult) if signal_type == SignalType.CALL else tick.quote + (atr * sl_mult)
        tp_price = tick.quote + (atr * tp_mult) if signal_type == SignalType.CALL else tick.quote - (atr * tp_mult)

        strategy_info = f"M{personality.timeframe//60}/{personality.strategy} (Conf: {ai_decision['confidence']:.2f})"

        return TradeDecision(
            direction=signal_type,
            entry_price=tick.quote,
            sl_price=sl_price,
            tp_price=tp_price,
            atr=atr,
            reason=signal.reason,
            strategy_info=strategy_info
        )
