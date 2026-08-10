import logging
import uuid
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class PaperTrader:
    def __init__(self, symbol: str = "BTCUSDT", initial_balance: float = 200.0, leverage: int = 10):
        self.symbol = symbol.replace("/", "_")
        self.state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", f"simulator_state_{self.symbol}.json"))
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        
        self.open_positions = []
        self.history_trades = []
        
        # Risk settings
        self.consecutive_losses = 0
        self.daily_stop_loss = 50.0
        self.daily_stop_gain = 50.0
        self.max_gale = 2
        self.stake_initial = 10.0 # Initial margin in USDT
        
        self.load_state()
        
    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    self.balance = state.get("balance", self.initial_balance)
                    self.consecutive_losses = state.get("consecutive_losses", 0)
                    self.history_trades = state.get("history_trades", [])
                    self.open_positions = state.get("open_positions", [])
                    logger.info(f"💾 [CryptoSimulator - {self.symbol}] Estado carregado com sucesso. Saldo: ${self.balance:.2f}, Histórico: {len(self.history_trades)} trades.")
        except Exception as e:
            logger.error(f"Erro ao carregar estado do simulador para {self.symbol}: {e}")

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            state = {
                "balance": self.balance,
                "consecutive_losses": self.consecutive_losses,
                "history_trades": self.history_trades,
                "open_positions": self.open_positions
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            logger.error(f"Erro ao salvar estado do simulador para {self.symbol}: {e}")

    def get_pnl(self) -> float:
        return round(self.balance - self.initial_balance, 2)
        
    def open_trade(self, direction: str, tf: int, current_epoch: int, current_price: float, sl_price: float, tp_price: float):
        # Apply Martingale logic
        multiplier = 2 ** self.consecutive_losses
        if self.consecutive_losses > self.max_gale:
            multiplier = 1
            
        margin_usdt = self.stake_initial * multiplier
        if margin_usdt > self.balance:
            margin_usdt = self.balance # All in if insufficient balance, just for simulation
            
        position_size_usd = margin_usdt * self.leverage
        qty = position_size_usd / current_price
        
        # SL/TP provided in arguments
        trade = {
            "id": str(uuid.uuid4())[:8],
            "direction": direction, # "CALL" for LONG, "PUT" for SHORT
            "entry_price": current_price,
            "margin": margin_usdt,
            "qty": qty,
            "sl": sl_price,
            "tp": tp_price,
            "entry_epoch": current_epoch,
            "status": "OPEN",
            "pnl": 0.0
        }
        
        self.open_positions.append(trade)
        logger.info(f"📊 [CryptoSimulator] Posição Aberta: {direction} | Margem: ${margin_usdt} | Alavancagem: {self.leverage}x | Entry: {current_price} | TP: {tp_price} | SL: {sl_price}")
        
    def check_positions(self, current_epoch: int, current_price: float) -> list:
        finished = []
        for trade in self.open_positions[:]:
            # Calculate floating PnL
            if trade["direction"] == "CALL": # LONG
                price_diff = current_price - trade["entry_price"]
            else: # SHORT
                price_diff = trade["entry_price"] - current_price
                
            floating_pnl = price_diff * trade["qty"]
            trade["pnl"] = round(floating_pnl, 2)
            
            # Check TP / SL hit
            hit_tp = (trade["direction"] == "CALL" and current_price >= trade["tp"]) or (trade["direction"] == "PUT" and current_price <= trade["tp"])
            hit_sl = (trade["direction"] == "CALL" and current_price <= trade["sl"]) or (trade["direction"] == "PUT" and current_price >= trade["sl"])
            
            if hit_tp or hit_sl:
                trade["exit_price"] = current_price
                trade["exit_epoch"] = current_epoch
                trade["status"] = "WIN" if hit_tp else "LOSS"
                
                self.balance += trade["pnl"]
                
                if hit_tp:
                    self.consecutive_losses = 0
                    logger.info(f"✅ [CryptoSimulator] WIN! PnL: +${trade['pnl']} | Balanço: ${self.balance:.2f}")
                else:
                    self.consecutive_losses += 1
                    logger.warning(f"❌ [CryptoSimulator] LOSS! PnL: -${abs(trade['pnl'])} | Balanço: ${self.balance:.2f}")
                    
                self.open_positions.remove(trade)
                self.history_trades.insert(0, trade)
                finished.append(trade)
                
        # Trim history
        if len(self.history_trades) > 50:
            self.history_trades = self.history_trades[:50]
            
        return finished

    def get_state(self) -> dict:
        return {
            "balance": self.balance,
            "pnl": self.get_pnl(),
            "pending": self.open_positions,
            "history": self.history_trades,
            "risk": {
                "consecutive_losses": self.consecutive_losses,
                "next_margin": self.stake_initial * (2 ** min(self.consecutive_losses, self.max_gale)),
                "stop_loss": self.daily_stop_loss,
                "stop_gain": self.daily_stop_gain,
                "max_gale": self.max_gale,
                "leverage": self.leverage
            }
        }
