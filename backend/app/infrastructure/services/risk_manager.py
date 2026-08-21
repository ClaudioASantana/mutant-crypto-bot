"""
Implementação concreta do Gerenciador de Risco.

Centraliza toda a lógica de avaliação e cálculo de risco,
seguindo a interface AbstractRiskManager.
"""
import logging
import os
from typing import Dict, Any

from app.domain.entities.market import AccountState, RiskEvaluation, RiskDecision, Signal, SignalType
from app.domain.entities.personality import Personality
from app.domain.services.risk_manager_interface import AbstractRiskManager

logger = logging.getLogger(__name__)


class RiskManager(AbstractRiskManager):
    def __init__(self):
        pass # Por enquanto, não precisa de parâmetros de inicialização específicos

    def evaluate_pre_trade_risk(self, signal: Signal, account: AccountState, personality: Personality) -> RiskEvaluation:
        """
        Avalia o risco antes de abrir um trade, considerando o estado da conta
        e as configurações de risco da personalidade.
        """
        if signal.type == SignalType.NONE:
            return RiskEvaluation(
                decision=RiskDecision.BLOCKED,
                reason="No signal to execute",
                stake=0.0
            )

        # Regra 3: Circuit Breaker Global (Daily Drawdown)
        global_max_loss = float(os.getenv("GLOBAL_MAX_DAILY_LOSS", "-100.0"))
        if account.daily_pnl <= global_max_loss:
            logger.critical(f"CIRCUIT BREAKER ACIONADO! PnL diário ({account.daily_pnl}) atingiu o limite global ({global_max_loss}). O robô foi travado pelo resto do dia.")
            return RiskEvaluation(
                decision=RiskDecision.BLOCKED,
                reason=f"GLOBAL CIRCUIT BREAKER: Daily PnL ({account.daily_pnl}) reached limit ({global_max_loss})",
                stake=0.0
            )

        dynamic_stop = -personality.risk_profile.daily_stop_loss
        if account.highest_daily_pnl >= personality.risk_profile.daily_stop_gain:
            dynamic_stop = account.highest_daily_pnl - personality.risk_profile.daily_stop_gain

        if account.daily_pnl <= dynamic_stop:
            return RiskEvaluation(
                decision=RiskDecision.BLOCKED,
                reason=f"Daily dynamic stop reached: {account.daily_pnl} <= {dynamic_stop}",
                stake=0.0
            )

        return RiskEvaluation(
            decision=RiskDecision.APPROVED,
            reason="Risk constraints passed",
            stake=personality.risk_profile.stake_initial
        )

    def calculate_position_sizing(self, personality: Personality, current_balance: float, current_price: float, atr: float, symbol: str) -> Dict[str, Any]:
        """
        Calcula o tamanho da posição (margem, quantidade) com base na
        estratégia de dimensionamento da posição da personalidade.
        """
        profile = personality.risk_profile
        margin_usdt = 0.0

        if profile.position_sizing_mode == "volatility_adjusted":
            volatility_index = 1.10 if "BTC" in symbol else 1.51
            margin_usdt = profile.stake_initial / volatility_index
        else: # "fixed" ou qualquer outro modo que use risk_percent
            margin_usdt = current_balance * (profile.risk_percent / 100.0)

        if margin_usdt > current_balance:
            margin_usdt = current_balance

        position_size_usd = margin_usdt * profile.leverage
        qty = position_size_usd / current_price

        return {"margin_usdt": margin_usdt, "qty": qty}

    def calculate_sl_tp(self, personality: Personality, entry_price: float, atr: float, direction: str) -> Dict[str, float]:
        """
        Calcula os preços de Stop Loss (SL) e Take Profit (TP).
        """
        profile = personality.risk_profile
        sl_price = 0.0
        tp_price = 0.0

        if direction == SignalType.CALL: # LONG
            sl_price = entry_price - (atr * profile.sl_multiplier)
            tp_price = entry_price + (atr * profile.tp_multiplier)
        elif direction == SignalType.PUT: # SHORT
            sl_price = entry_price + (atr * profile.sl_multiplier)
            tp_price = entry_price - (atr * profile.tp_multiplier)

        return {"sl_price": sl_price, "tp_price": tp_price}

    def manage_trailing_stop(self, trade: Dict[str, Any], current_price: float, personality: Personality) -> Dict[str, Any]:
        """
        Gerencia a lógica de Trailing Stop para um trade aberto.
        """
        profile = personality.risk_profile
        atr_val = trade.get("atr", 0.0)

        if atr_val == 0:
            return trade # Não há ATR para calcular trailing stop

        if trade["direction"] == "CALL": # LONG
            if current_price > trade.get("highest_reached", current_price):
                trade["highest_reached"] = current_price

            if trade["highest_reached"] >= trade["entry_price"] + (atr_val * profile.trailing_activation):
                new_sl = trade["highest_reached"] - (atr_val * profile.trailing_distance)
                if new_sl > trade["sl"]:
                    trade["sl"] = new_sl
                    logger.info(f"📈 [RiskManager] Trailing Stop movido para ${new_sl:.2f} (COMPRA)")

        elif trade["direction"] == "PUT": # SHORT
            if current_price < trade.get("lowest_reached", current_price):
                trade["lowest_reached"] = current_price

            if trade["lowest_reached"] <= trade["entry_price"] - (atr_val * profile.trailing_activation):
                new_sl = trade["lowest_reached"] + (atr_val * profile.trailing_distance)
                if new_sl < trade["sl"]:
                    trade["sl"] = new_sl
                    logger.info(f"📉 [RiskManager] Trailing Stop movido para ${new_sl:.2f} (VENDA)")

        return trade

    def check_time_stop(self, trade: Dict[str, Any], current_epoch: int, personality: Personality) -> bool:
        """
        Verifica se um trade deve ser fechado por limite de tempo.
        """
        duration_seconds = current_epoch - trade["entry_epoch"]
        return duration_seconds >= (personality.risk_profile.max_trade_duration_minutes * 60)