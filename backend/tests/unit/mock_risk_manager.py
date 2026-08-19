"""
Mock para o RiskManager, usado nos testes unitários.

Permite isolar a lógica de teste de outras camadas.
"""
from typing import Dict, Any
from unittest.mock import Mock

from app.domain.entities.market import AccountState, RiskEvaluation, RiskDecision, Signal
from app.domain.entities.personality import Personality


class MockRiskManager:
    """
    Mock do RiskManager para testes.
    Fornece implementações básicas que retornam valores previsíveis.
    """

    def evaluate_pre_trade_risk(self, signal: Signal, account: AccountState, personality: Personality) -> RiskEvaluation:
        """
        Avaliação de risco mockada: Aprova todos os trades por padrão,
        a menos que o PnL da conta esteja abaixo do stop loss.
        """
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
            reason="Risk constraints passed (mock)",
            stake=personality.risk_profile.stake_initial
        )

    def calculate_position_sizing(self, personality: Personality, current_balance: float, current_price: float, atr: float, symbol: str) -> Dict[str, Any]:
        """
        Cálculo de dimensionamento mockado.
        """
        margin_usdt = current_balance * 0.02  # 2% do saldo
        qty = (margin_usdt * 10) / current_price  # Alavancagem 10x
        return {"margin_usdt": margin_usdt, "qty": qty}

    def calculate_sl_tp(self, personality: Personality, entry_price: float, atr: float, direction: str) -> Dict[str, float]:
        """
        Cálculo de SL/TP mockado.
        """
        if direction == "CALL":
            sl_price = entry_price - 500
            tp_price = entry_price + 2000
        else: # PUT
            sl_price = entry_price + 500
            tp_price = entry_price - 2000
        return {"sl_price": sl_price, "tp_price": tp_price}

    def manage_trailing_stop(self, trade: Dict[str, Any], current_price: float, personality: Personality) -> Dict[str, Any]:
        """
        Gestão de trailing stop mockada (sem alteração).
        """
        return trade

    def check_time_stop(self, trade: Dict[str, Any], current_epoch: int, personality: Personality) -> bool:
        """
        Verificação de time stop mockada (nunca atinge).
        """
        return False