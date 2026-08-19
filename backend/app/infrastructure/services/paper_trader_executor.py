import logging
import uuid

from app.domain.repositories.paper_trader_repository import AbstractPaperTraderRepository
from app.domain.services.trade_executor_interface import AbstractTradeExecutor
from app.domain.services.risk_manager_interface import AbstractRiskManager
from app.domain.entities.personality import Personality

logger = logging.getLogger(__name__)


class PaperTrader(AbstractTradeExecutor):
    def __init__(self, symbol: str, identity: str, repository: AbstractPaperTraderRepository, risk_manager: AbstractRiskManager, initial_balance: float = 200.0, leverage: int = 10, position_sizing_mode: str = "fixed", max_history_trades: int = 50):
        self.symbol = symbol.replace("/", "_")
        self.identity = identity
        self.repository = repository
        self.risk_manager = risk_manager
        self.max_history_trades = max_history_trades

        self.initial_balance = initial_balance
        self.leverage = leverage

        self.balance = initial_balance
        self.consecutive_losses = 0
        self.history_trades = []
        self.open_positions = []
        self.highest_daily_pnl = 0.0

        # Fallbacks mantidos para compatibilidade com estados salvos antigos.
        # A lógica primária de risco agora vem do risk_manager injetado.
        self.daily_stop_loss = 50.0
        self.daily_stop_gain = 50.0
        self.stake_initial = 10.0
        self.trailing_activation = 1.0
        self.trailing_distance = 0.5
        self.position_sizing_mode = position_sizing_mode
        self.risk_percent = 2.0
        self.max_trade_duration_minutes = 240

        self.load_state()

    def load_state(self):
        state = self.repository.load(self.identity)
        if state:
            try:
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
                    self.stake_initial = rs.get("stake_initial", self.stake_initial)
                    self.trailing_activation = rs.get("trailing_activation", self.trailing_activation)
                    self.trailing_distance = rs.get("trailing_distance", self.trailing_distance)
                    self.position_sizing_mode = rs.get("position_sizing_mode", self.position_sizing_mode)
                    self.risk_percent = rs.get("risk_percent", self.risk_percent)
                    self.max_trade_duration_minutes = rs.get("max_trade_duration_minutes", self.max_trade_duration_minutes)
                logger.info(f"💾 [CryptoSimulator - {self.symbol}] Estado carregado via repositório. Saldo: ${self.balance:.2f}")
            except Exception as e:
                logger.error(f"Erro ao processar estado carregado do simulador para {self.symbol}: {e}")

    def save_state(self):
        try:
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
                    "stake_initial": self.stake_initial,
                    "trailing_activation": self.trailing_activation,
                    "trailing_distance": self.trailing_distance,
                    "position_sizing_mode": self.position_sizing_mode,
                    "risk_percent": self.risk_percent,
                    "max_trade_duration_minutes": self.max_trade_duration_minutes
                }
            }
            self.repository.save(self.identity, state)
        except Exception as e:
            logger.error(f"Erro ao salvar estado do simulador para {self.symbol} via repositório: {e}")

    def get_pnl(self) -> float:
        return round(self.balance - self.initial_balance, 2)
        
    def get_current_margin_usdt(self) -> float:
        """
        Calcula a margem usando o RiskManager injetado.
        Mantém a assinatura original para compatibilidade.
        """
        # TODO: Refatorar para receber a personality aqui também.
        # Por enquanto, retorna um valor padrão conservador baseado no saldo.
        return self.balance * (self.risk_percent / 100.0)


    def open_trade(self, direction: str, tf: int, current_epoch: int, current_price: float, sl_price: float, tp_price: float, atr: float = 0.0, personality: Personality = None):
        # TODO: Passar a personalidade correta aqui
        if personality is None:
            raise ValueError("Personality must be provided to open_trade")

        # Usar o RiskManager para calcular o tamanho da posição
        sizing_result = self.risk_manager.calculate_position_sizing(
            personality, self.balance, current_price, atr, self.symbol
        )
        margin_usdt = sizing_result["margin_usdt"]
        qty = sizing_result["qty"]
        
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
        
    def check_positions(self, current_epoch: int, current_price: float, personality: Personality = None) -> list:
        finished = []
        for trade in self.open_positions[:]:
            # TODO: Passar a personalidade correta aqui quando possível
            # Calcula PnL flutuante
            if trade["direction"] == "CALL": # LONG
                price_diff = current_price - trade["entry_price"]
                if current_price > trade.get("highest_reached", current_price):
                    trade["highest_reached"] = current_price

                if personality is not None:
                    trade = self.risk_manager.manage_trailing_stop(trade, current_price, personality)
                else:
                    # Fallback legado
                    atr_val = trade.get("atr", 0.0)
                    if atr_val > 0 and trade["highest_reached"] >= trade["entry_price"] + (atr_val * self.trailing_activation):
                        new_sl = trade["highest_reached"] - (atr_val * self.trailing_distance)
                        if new_sl > trade["sl"]:
                            trade["sl"] = new_sl
                            logger.info(f"📈 [CryptoSimulator - {self.symbol}] Trailing Stop movido para ${new_sl:.2f} (COMPRA)")

            else: # SHORT
                price_diff = trade["entry_price"] - current_price
                if current_price < trade.get("lowest_reached", current_price):
                    trade["lowest_reached"] = current_price

                if personality is not None:
                    trade = self.risk_manager.manage_trailing_stop(trade, current_price, personality)
                else:
                    # Fallback legado
                    atr_val = trade.get("atr", 0.0)
                    if atr_val > 0 and trade["lowest_reached"] <= trade["entry_price"] - (atr_val * self.trailing_activation):
                        new_sl = trade["lowest_reached"] + (atr_val * self.trailing_distance)
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

            # Verifica time stop usando o RiskManager se a personality for fornecida
            if personality is not None:
                hit_time_stop = self.risk_manager.check_time_stop(trade, current_epoch, personality)
            else:
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
                    logger.info(f"⏳ [CryptoSimulator - {self.symbol}] Trade {trade['direction']} fechado por TIME_STOP - PnL: ${trade['pnl']:.2f} (Preço: {current_price})")
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
        if self.max_history_trades is not None and len(self.history_trades) > self.max_history_trades:
            self.history_trades = self.history_trades[:self.max_history_trades]

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
                "next_margin": self.balance * (self.risk_percent / 100.0),
                "stop_loss": self.daily_stop_loss,
                "stop_gain": self.daily_stop_gain,
                "leverage": self.leverage,
                "trailing_activation": self.trailing_activation,
                "trailing_distance": self.trailing_distance,
                "position_sizing_mode": self.position_sizing_mode,
                "risk_percent": self.risk_percent,
                "max_trade_duration_minutes": self.max_trade_duration_minutes
            }
        }
