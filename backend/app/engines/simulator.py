import logging
import uuid
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class PaperTrader:
    _global_state = {
        "balance": None,
        "consecutive_losses": 0,
        "history_trades": [],
        "open_positions": [],
        "risk_settings": {
            "daily_stop_loss": 50.0,
            "daily_stop_gain": 50.0,
            "max_gale": 2,
            "stake_initial": 10.0
        }
    }
    _state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "simulator_state_global.json"))

    @classmethod
    def load_state(cls, initial_balance):
        if cls._global_state["balance"] is None:
            cls._global_state["balance"] = initial_balance
            try:
                if os.path.exists(cls._state_file):
                    with open(cls._state_file, "r") as f:
                        state = json.load(f)
                        cls._global_state["balance"] = state.get("balance", initial_balance)
                        cls._global_state["consecutive_losses"] = state.get("consecutive_losses", 0)
                        cls._global_state["history_trades"] = state.get("history_trades", [])
                        cls._global_state["open_positions"] = state.get("open_positions", [])
                        if "risk_settings" in state:
                            cls._global_state["risk_settings"].update(state["risk_settings"])
                        logger.info(f"💾 [CryptoSimulator - GLOBAL] Estado carregado. Saldo: ${cls._global_state['balance']:.2f}, Histórico: {len(cls._global_state['history_trades'])}")
            except Exception as e:
                logger.error(f"Erro ao carregar estado global do simulador: {e}")

    @classmethod
    def save_state_global(cls):
        try:
            os.makedirs(os.path.dirname(cls._state_file), exist_ok=True)
            with open(cls._state_file, "w") as f:
                json.dump(cls._global_state, f, indent=4)
        except Exception as e:
            logger.error(f"Erro ao salvar estado global do simulador: {e}")

    def __init__(self, symbol: str = "BTCUSDT", initial_balance: float = 200.0, leverage: int = 10):
        self.symbol = symbol.replace("/", "_")
        self.initial_balance = initial_balance
        self.leverage = leverage
        
        # Risk settings are now globally managed via properties

        
        PaperTrader.load_state(initial_balance)
        
    @property
    def balance(self):
        return PaperTrader._global_state["balance"]
        
    @balance.setter
    def balance(self, value):
        PaperTrader._global_state["balance"] = value
        
    @property
    def consecutive_losses(self):
        return PaperTrader._global_state["consecutive_losses"]
        
    @consecutive_losses.setter
    def consecutive_losses(self, value):
        PaperTrader._global_state["consecutive_losses"] = value
        
    @property
    def history_trades(self):
        return PaperTrader._global_state["history_trades"]
        
    @history_trades.setter
    def history_trades(self, value):
        PaperTrader._global_state["history_trades"] = value
        
    @property
    def open_positions(self):
        return PaperTrader._global_state["open_positions"]

    @open_positions.setter
    def open_positions(self, value):
        PaperTrader._global_state["open_positions"] = value

    @property
    def daily_stop_loss(self):
        return PaperTrader._global_state["risk_settings"]["daily_stop_loss"]

    @daily_stop_loss.setter
    def daily_stop_loss(self, value):
        PaperTrader._global_state["risk_settings"]["daily_stop_loss"] = float(value)

    @property
    def daily_stop_gain(self):
        return PaperTrader._global_state["risk_settings"]["daily_stop_gain"]

    @daily_stop_gain.setter
    def daily_stop_gain(self, value):
        PaperTrader._global_state["risk_settings"]["daily_stop_gain"] = float(value)

    @property
    def max_gale(self):
        return PaperTrader._global_state["risk_settings"]["max_gale"]

    @max_gale.setter
    def max_gale(self, value):
        PaperTrader._global_state["risk_settings"]["max_gale"] = int(value)

    @property
    def stake_initial(self):
        return PaperTrader._global_state["risk_settings"]["stake_initial"]

    @stake_initial.setter
    def stake_initial(self, value):
        PaperTrader._global_state["risk_settings"]["stake_initial"] = float(value)

    def save_state(self):
        PaperTrader.save_state_global()

    def get_pnl(self) -> float:
        return round(self.balance - self.initial_balance, 2)
        
    def open_trade(self, direction: str, tf: int, current_epoch: int, current_price: float, sl_price: float, tp_price: float, atr: float = 0.0):
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
            "pnl": 0.0,
            "atr": atr,
            "highest_reached": current_price,
            "lowest_reached": current_price
        }
        
        self.open_positions.append(trade)
        self.save_state()
        logger.info(f"📊 [CryptoSimulator] Posição Aberta: {direction} | Margem: ${margin_usdt} | Alavancagem: {self.leverage}x | Entry: {current_price} | TP: {tp_price} | SL: {sl_price}")
        
    def check_positions(self, current_epoch: int, current_price: float) -> list:
        finished = []
        for trade in self.open_positions[:]:
            # Calculate floating PnL
            if trade["direction"] == "CALL": # LONG
                price_diff = current_price - trade["entry_price"]
                # Update highest reached
                if current_price > trade.get("highest_reached", current_price):
                    trade["highest_reached"] = current_price
                
                # Trailing Stop Logic for CALL
                atr_val = trade.get("atr", 0.0)
                if atr_val > 0 and trade["highest_reached"] >= trade["entry_price"] + atr_val:
                    new_sl = trade["highest_reached"] - atr_val
                    if new_sl > trade["sl"]:
                        trade["sl"] = new_sl
                        logger.info(f"📈 [CryptoSimulator] Trailing Stop movido para ${new_sl:.2f} (COMPRA)")

            else: # SHORT
                price_diff = trade["entry_price"] - current_price
                # Update lowest reached
                if current_price < trade.get("lowest_reached", current_price):
                    trade["lowest_reached"] = current_price
                    
                # Trailing Stop Logic for PUT
                atr_val = trade.get("atr", 0.0)
                if atr_val > 0 and trade["lowest_reached"] <= trade["entry_price"] - atr_val:
                    new_sl = trade["lowest_reached"] + atr_val
                    if new_sl < trade["sl"]:
                        trade["sl"] = new_sl
                        logger.info(f"📉 [CryptoSimulator] Trailing Stop movido para ${new_sl:.2f} (VENDA)")
                
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
            
        if finished:
            self.save_state()
            
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
