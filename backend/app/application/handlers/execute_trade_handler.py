import logging
from typing import Dict, Any

from app.application.commands.execute_trade_command import ExecuteTradeCommand
from app.domain.entities.market import Signal, SignalType
from app.domain.services.risk_manager_interface import AbstractRiskManager
from app.domain.repositories.paper_trader_repository import AbstractPaperTraderRepository
from app.domain.exceptions import RiskLimitExceededException

logger = logging.getLogger(__name__)

class ExecuteTradeHandler:
    """
    Handler para o ExecuteTradeCommand.
    Aplica as regras de negócio através de Domain Services (RiskManager) e
    persiste o estado através do Repository (PaperTraderRepository).
    """
    def __init__(
        self,
        risk_manager: AbstractRiskManager,
        paper_trader_repo: AbstractPaperTraderRepository
    ):
        self.risk_manager = risk_manager
        self.paper_trader_repo = paper_trader_repo

    def handle(self, command: ExecuteTradeCommand, identity: str = "default") -> Dict[str, Any]:
        logger.info(f"Processando comando de trade para {command.symbol} ({command.direction})")
        
        # 1. Recupera o estado (Conta, trades abertos, personalidade)
        state_dict = self.paper_trader_repo.load(identity)
        if not state_dict:
            # Estado inicial se não existir
            state_dict = {
                "account_state": {
                    "balance": 10000.0,
                    "daily_pnl": 0.0,
                    "highest_daily_pnl": 0.0,
                    "daily_stop_loss": 50.0,
                    "daily_stop_gain": 50.0,
                    "stake_initial": 10.0
                },
                "active_trades": [],
                "personality": {
                    "id": "default",
                    "name": "Default AI",
                    "strategy": "3 Velas",
                    "timeframe": 300,
                    "risk_profile": {
                        "daily_stop_loss": 50.0,
                        "daily_stop_gain": 50.0,
                        "stake_initial": 10.0,
                        "position_sizing_mode": "fixed",
                        "risk_percent": 1.0,
                        "leverage": 1,
                        "sl_multiplier": 1.5,
                        "tp_multiplier": 2.0,
                        "trailing_activation": 1.0,
                        "trailing_distance": 0.5,
                        "max_trade_duration_minutes": 60
                    }
                }
            }

        # Converte dicionários para Entidades para usar regras de negócio limpas
        from app.domain.entities.market import AccountState
        from app.domain.entities.personality import Personality
        
        account = AccountState(**state_dict["account_state"])
        personality = Personality(**state_dict["personality"])
        
        signal = Signal(type=SignalType(command.direction.upper()), reason=f"Strategy: {command.strategy}")

        # 2. Executa a regra de negócio do Domínio (Risk Manager)
        risk_evaluation = self.risk_manager.evaluate_pre_trade_risk(signal, account, personality)
        
        if risk_evaluation.decision.value == "BLOCKED":
            logger.warning(f"Trade bloqueado pelo RiskManager: {risk_evaluation.reason}")
            raise RiskLimitExceededException(risk_evaluation.reason)
            
        # 3. Calcula SL/TP e dimensionamento
        sizing = self.risk_manager.calculate_position_sizing(
            personality, account.balance, command.entry_price, command.atr, command.symbol
        )
        
        sl_tp = self.risk_manager.calculate_sl_tp(
            personality, command.entry_price, command.atr, command.direction.upper()
        )
        
        # 4. Registra o Trade
        import time
        new_trade = {
            "symbol": command.symbol,
            "direction": command.direction.upper(),
            "entry_price": command.entry_price,
            "margin": sizing["margin_usdt"],
            "qty": sizing["qty"],
            "sl": sl_tp["sl_price"],
            "tp": sl_tp["tp_price"],
            "entry_epoch": int(time.time()),
            "atr": command.atr
        }
        
        state_dict["active_trades"].append(new_trade)
        
        # 5. Persiste a alteração
        self.paper_trader_repo.save(identity, state_dict)
        logger.info(f"Trade salvo com sucesso: {new_trade}")
        
        return {"status": "SUCCESS", "trade": new_trade}
