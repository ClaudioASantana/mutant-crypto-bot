import logging
import uuid
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class PaperTrader:
    def __init__(self, symbol: str = "BTCUSDT", initial_balance: float = 200.0, leverage: int = 10):
        self.symbol = symbol.replace("/", "_")
        self.initial_balance = initial_balance
        self.leverage = leverage
        
        self.balance = initial_balance
        self.consecutive_losses = 0
        self.history_trades = []
        self.open_positions = []
        self.highest_daily_pnl = 0.0
        
        self.daily_stop_loss = 50.0
        self.daily_stop_gain = 50.0
        self.max_gale = 2
        self.stake_initial = 10.0
        self.trailing_activation = 1.0
        self.trailing_distance = 0.5
        self.position_sizing_mode = "fixed"
        self.risk_percent = 2.0
        self.max_trade_duration_minutes = 240
        
        self._state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", f"simulator_state_{self.symbol}.json"))
        self.load_state()

    def load_state(self):
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, "r") as f:
                    state = json.load(f)
                    self.balance = state.get("balance", self.initial_balance)
                    self.initial_balance = state.get("initial_balance", self.initial_balance)
                    self.consecutive_losses = state.get("consecutive_losses", 0)
                    self.highest_daily_pnl = state.get("highest_daily_pnl", 0.0)
                    self.history_trades = state.get("history_trades", [])
                    self.open_positions = state.get("open_positions", [])
                    if "risk_settings" in state:
                        rs = state["risk_settings"]
                        self.daily_stop_loss = rs.get("daily_stop_loss", self.daily_stop_loss)
                        self.daily_stop_gain = rs.get("daily_stop_gain", self.daily_stop_gain)
                        self.max_gale = rs.get("max_gale", self.max_gale)
                        self.stake_initial = rs.get("stake_initial", self.stake_initial)
                        self.trailing_activation = rs.get("trailing_activation", self.trailing_activation)
                        self.trailing_distance = rs.get("trailing_distance", self.trailing_distance)
                        self.position_sizing_mode = rs.get("position_sizing_mode", self.position_sizing_mode)
                        self.risk_percent = rs.get("risk_percent", self.risk_percent)
                        self.max_trade_duration_minutes = rs.get("max_trade_duration_minutes", self.max_trade_duration_minutes)
                    logger.info(f"💾 [CryptoSimulator - {self.symbol}] Estado carregado. Saldo: ${self.balance:.2f}, Histórico: {len(self.history_trades)}")
        except Exception as e:
            logger.error(f"Erro ao carregar estado do simulador para {self.symbol}: {e}")

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            state = {
                "balance": self.balance,
                "initial_balance": self.initial_balance,
                "consecutive_losses": self.consecutive_losses,
                "highest_daily_pnl": self.highest_daily_pnl,
                "history_trades": self.history_trades,
                "open_positions": self.open_positions,
                "risk_settings": {
                    "daily_stop_loss": self.daily_stop_loss,
                    "daily_stop_gain": self.daily_stop_gain,
                    "max_gale": self.max_gale,
                    "stake_initial": self.stake_initial,
                    "trailing_activation": self.trailing_activation,
                    "trailing_distance": self.trailing_distance,
                    "position_sizing_mode": self.position_sizing_mode,
                    "risk_percent": self.risk_percent,
                    "max_trade_duration_minutes": self.max_trade_duration_minutes
                }
            }
            with open(self._state_file, "w") as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            logger.error(f"Erro ao salvar estado do simulador para {self.symbol}: {e}")

    def get_pnl(self) -> float:
        return round(self.balance - self.initial_balance, 2)
        
    def get_current_margin_usdt(self) -> float:
        if self.position_sizing_mode == "gale":
            multiplier = 2 ** self.consecutive_losses
            if self.consecutive_losses > self.max_gale:
                multiplier = 1
            margin_usdt = self.stake_initial * multiplier
        elif self.position_sizing_mode == "volatility_adjusted":
            volatility_index = 1.10 if "BTC" in self.symbol else 1.51
            margin_usdt = self.stake_initial / volatility_index
        else:
            margin_usdt = self.balance * (self.risk_percent / 100.0)
            
        if margin_usdt > self.balance:
            margin_usdt = self.balance
        return margin_usdt

    def open_trade(self, direction: str, tf: int, current_epoch: int, current_price: float, sl_price: float, tp_price: float, atr: float = 0.0):
        margin_usdt = self.get_current_margin_usdt()
            
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
        logger.info(f"📊 [CryptoSimulator - {self.symbol}] Posição Aberta: {direction} | Margem: ${margin_usdt} | Alavancagem: {self.leverage}x | Entry: {current_price} | TP: {tp_price} | SL: {sl_price}")
        
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
                activation = self.trailing_activation
                distance = self.trailing_distance
                if atr_val > 0 and trade["highest_reached"] >= trade["entry_price"] + (atr_val * activation):
                    new_sl = trade["highest_reached"] - (atr_val * distance)
                    if new_sl > trade["sl"]:
                        trade["sl"] = new_sl
                        logger.info(f"📈 [CryptoSimulator - {self.symbol}] Trailing Stop movido para ${new_sl:.2f} (COMPRA)")

            else: # SHORT
                price_diff = trade["entry_price"] - current_price
                # Update lowest reached
                if current_price < trade.get("lowest_reached", current_price):
                    trade["lowest_reached"] = current_price
                    
                # Trailing Stop Logic for PUT
                atr_val = trade.get("atr", 0.0)
                activation = self.trailing_activation
                distance = self.trailing_distance
                if atr_val > 0 and trade["lowest_reached"] <= trade["entry_price"] - (atr_val * activation):
                    new_sl = trade["lowest_reached"] + (atr_val * distance)
                    if new_sl < trade["sl"]:
                        trade["sl"] = new_sl
                        logger.info(f"📉 [CryptoSimulator - {self.symbol}] Trailing Stop movido para ${new_sl:.2f} (VENDA)")
                
            floating_pnl = price_diff * trade["qty"]
            
            # Desconto das taxas (0.1% sobre o volume total da posição alavancada)
            position_size_usd = trade["qty"] * trade["entry_price"]
            fee_usdt = position_size_usd * 0.001
            
            trade["pnl"] = round(floating_pnl - fee_usdt, 2)
            
            # Check TP / SL hit
            hit_tp = (trade["direction"] == "CALL" and current_price >= trade["tp"]) or (trade["direction"] == "PUT" and current_price <= trade["tp"])
            hit_sl = (trade["direction"] == "CALL" and current_price <= trade["sl"]) or (trade["direction"] == "PUT" and current_price >= trade["sl"])
            
            duration_seconds = current_epoch - trade["entry_epoch"]
            hit_time_stop = duration_seconds >= (self.max_trade_duration_minutes * 60)
            
            if hit_tp or hit_sl or hit_time_stop:
                trade["exit_price"] = current_price
                trade["exit_epoch"] = current_epoch
                if hit_time_stop:
                    trade["status"] = "TIME_STOP"
                else:
                    trade["status"] = "WIN" if hit_tp else "LOSS"
                
                self.balance += trade["pnl"]
                self.balance = round(self.balance, 2)
                
                # Logging apropriado
                if hit_time_stop:
                    logger.info(f"⏳ [CryptoSimulator - {self.symbol}] Trade {trade['direction']} fechado por TIME_STOP (4h) - PnL: ${trade['pnl']:.2f} (Preço: {current_price})")
                elif hit_tp:
                    self.consecutive_losses = 0
                    logger.info(f"✅ [CryptoSimulator - {self.symbol}] Trade {trade['direction']} deu WIN - PnL: +${trade['pnl']:.2f} (Preço: {current_price})")
                else:
                    self.consecutive_losses += 1
                    logger.warning(f"❌ [CryptoSimulator - {self.symbol}] LOSS! PnL: -${abs(trade['pnl'])} | Balanço: ${self.balance:.2f}")
                    
                self.open_positions.remove(trade)
                self.history_trades.insert(0, trade)
                finished.append(trade)
                
                # DAILY TRAILING STOP TRACKING
                if self.get_pnl() > self.highest_daily_pnl:
                    self.highest_daily_pnl = self.get_pnl()
                    logger.info(f"🚀 [{self.symbol}] Novo pico de PnL Diário: +${self.highest_daily_pnl:.2f}")
                
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
                "next_margin": self.stake_initial * (2 ** min(self.consecutive_losses, self.max_gale)) if self.position_sizing_mode == "gale" else self.balance * (self.risk_percent / 100.0),
                "stop_loss": self.daily_stop_loss,
                "stop_gain": self.daily_stop_gain,
                "max_gale": self.max_gale,
                "leverage": self.leverage,
                "trailing_activation": self.trailing_activation,
                "trailing_distance": self.trailing_distance,
                "position_sizing_mode": self.position_sizing_mode,
                "risk_percent": self.risk_percent,
                "max_trade_duration_minutes": self.max_trade_duration_minutes
            }
        }
