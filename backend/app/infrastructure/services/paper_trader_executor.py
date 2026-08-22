import logging
from typing import Optional, Protocol

from app.domain.entities.paper_trader_state import PaperTraderState, RiskSettings
from app.domain.entities.personality import Personality
from app.domain.entities.trade import Trade
from app.domain.services.trade_executor_interface import AbstractTradeExecutor
from app.domain.services.risk_manager_interface import AbstractRiskManager
from app.domain.value_objects.enums import TradeSide, TradeSource, split_legacy_status

logger = logging.getLogger(__name__)


class PaperTraderRepository(Protocol):
    """
    Repositório composto que o PaperTrader exige: snapshot + ciclo de vida de trades.

    Implementado pelo composto SQLAlchemy/InMemory/JSON. Exige os dois ports
    tipados atrás de um único objeto para preservar
    `PaperTrader(repository=...)` como assinatura única — os ~10 scripts de
    backtest e o cataloger dependem dela.
    """

    def load(self, identity: str) -> Optional[PaperTraderState]: ...

    def save(self, state: PaperTraderState) -> None: ...

    def add(self, trade: Trade) -> Trade: ...

    def update(self, trade: Trade) -> Trade: ...

    def get_by_id(self, trade_id: str) -> Optional[Trade]: ...

    def list_active(self, identity: str, symbol: Optional[str] = None) -> list[Trade]: ...

    def list_history(self, identity: str, limit: int = 50) -> list[Trade]: ...


class PaperTrader(AbstractTradeExecutor):
    def __init__(self, symbol: str, identity: str, repository: PaperTraderRepository, risk_manager: AbstractRiskManager, initial_balance: float = 200.0, leverage: int = 10, position_sizing_mode: str = "fixed", max_history_trades: int = 50):
        self.symbol = symbol.replace("/", "_")
        self.market_symbol = symbol
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

    # ------------------------------------------------------------------ #
    # Persistência canônica: snapshot (`paper_trader_states`) + trades    #
    # (`trades`). O runtime (`open_positions`/`history_trades`) é um read  #
    # model derivado — o formato canônico persistido é o par tipado.       #
    # ------------------------------------------------------------------ #

    def load_state(self):
        try:
            state = self.repository.load(self.identity)
            if state is not None:
                self.balance = state.balance
                self.initial_balance = state.initial_balance
                self.consecutive_losses = state.consecutive_losses
                self.highest_daily_pnl = state.highest_daily_pnl
                self.leverage = state.leverage
                rs = state.risk_settings
                self.daily_stop_loss = rs.daily_stop_loss
                self.daily_stop_gain = rs.daily_stop_gain
                self.stake_initial = rs.stake_initial
                self.trailing_activation = rs.trailing_activation
                self.trailing_distance = rs.trailing_distance
                self.position_sizing_mode = rs.position_sizing_mode
                self.risk_percent = rs.risk_percent
                self.max_trade_duration_minutes = rs.max_trade_duration_minutes

            # Posições ativas e histórico vivem na tabela `trades`, não mais no
            # snapshot JSON (que agora guarda apenas conta/risco).
            self.open_positions = [
                t.to_runtime_dict() for t in self.repository.list_active(self.identity)
            ]
            self.history_trades = [
                t.to_runtime_dict()
                for t in self.repository.list_history(self.identity, limit=self.max_history_trades)
            ]
            logger.info(f"💾 [CryptoSimulator - {self.symbol}] Estado carregado via repositório. Saldo: ${self.balance:.2f}")
        except Exception as e:
            logger.error(f"Erro ao processar estado carregado do simulador para {self.symbol}: {e}")

    def save_state(self):
        try:
            state = PaperTraderState(
                identity=self.identity,
                symbol=self.market_symbol,
                balance=self.balance,
                initial_balance=self.initial_balance,
                consecutive_losses=self.consecutive_losses,
                highest_daily_pnl=self.highest_daily_pnl,
                leverage=self.leverage,
                risk_settings=RiskSettings(
                    daily_stop_loss=self.daily_stop_loss,
                    daily_stop_gain=self.daily_stop_gain,
                    stake_initial=self.stake_initial,
                    trailing_activation=self.trailing_activation,
                    trailing_distance=self.trailing_distance,
                    position_sizing_mode=self.position_sizing_mode,
                    risk_percent=self.risk_percent,
                    max_trade_duration_minutes=self.max_trade_duration_minutes,
                ),
            )
            self.repository.save(state)
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

    @staticmethod
    def _normalize_side(direction: str) -> TradeSide:
        return TradeSide.CALL if str(direction).upper() in ("CALL", "LONG") else TradeSide.PUT

    def open_trade(
        self,
        direction: str,
        tf: int,
        current_epoch: int,
        current_price: float,
        sl_price: float,
        tp_price: float,
        atr: float = 0.0,
        personality: Personality = None,
        strategy: Optional[str] = None,
        ai_reason: Optional[str] = None,
        ai_confidence: Optional[float] = None,
        ai_context: Optional[str] = None,
    ):
        # TODO: Passar a personalidade correta aqui
        if personality is None:
            raise ValueError("Personality must be provided to open_trade")

        # Usar o RiskManager para calcular o tamanho da posição
        sizing_result = self.risk_manager.calculate_position_sizing(
            personality, self.balance, current_price, atr, self.symbol
        )
        margin_usdt = sizing_result["margin_usdt"]
        qty = sizing_result["qty"]

        # Persiste o trade canônico logo no nascimento — é aqui que o trade
        # ganha id, vira linha na tabela `trades` e passa a ter provenance.
        # `strategy`/`ai_*` são o que o `journal.db` legado guardava sozinho;
        # agora nascem junto com o trade em vez de numa gravação paralela.
        trade = Trade.open_new(
            identity=self.identity,
            symbol=self.market_symbol,
            personality_name=personality.name,
            timeframe_seconds=tf,
            side=self._normalize_side(direction),
            entry_price=current_price,
            entry_epoch=current_epoch,
            source=TradeSource.SWARM,
            qty=qty,
            margin=margin_usdt,
            leverage=self.leverage,
            sl=sl_price,
            tp=tp_price,
            atr=atr,
            highest_reached=current_price,
            lowest_reached=current_price,
            strategy=strategy,
            ai_reason=ai_reason,
            ai_confidence=ai_confidence,
            ai_context=ai_context,
        )
        self.repository.add(trade)

        # Read model derivado que a UI/WebSocket já consome hoje.
        runtime_trade = trade.to_runtime_dict()
        self.open_positions.append(runtime_trade)
        self.save_state()
        logger.info(f"📊 [CryptoSimulator - {self.symbol}] Posição Aberta: {direction} | Margem: ${margin_usdt} | Alavancagem: {self.leverage}x | Entry: {current_price} | TP: {tp_price} | SL: {sl_price}")

    def _trade_from_runtime(self, trade_dict: dict) -> Trade:
        """Reconstrói um `Trade` (já fechado) a partir do dict de runtime.

        Caminho de robustez para trades que chegaram ao runtime sem linha na
        tabela `trades` (ex.: estado legado de JSON). No fluxo canônico o trade
        já existe e `_persist_closed_trade` faz `update` no registro aberto.
        """
        status, outcome = split_legacy_status(trade_dict.get("status"))
        return Trade(
            id=trade_dict["id"],
            identity=self.identity,
            symbol=self.market_symbol,
            side=self._normalize_side(trade_dict.get("direction", "CALL")),
            status=status,
            outcome=outcome,
            source=TradeSource.SWARM,
            entry_price=trade_dict.get("entry_price", 0.0),
            entry_epoch=trade_dict.get("entry_epoch", 0),
            qty=trade_dict.get("qty", 0.0),
            margin=trade_dict.get("margin", 0.0),
            leverage=trade_dict.get("leverage", self.leverage),
            sl=trade_dict.get("sl"),
            tp=trade_dict.get("tp"),
            exit_price=trade_dict.get("exit_price"),
            exit_epoch=trade_dict.get("exit_epoch"),
            pnl=trade_dict.get("pnl", 0.0),
            atr=trade_dict.get("atr"),
            highest_reached=trade_dict.get("highest_reached"),
            lowest_reached=trade_dict.get("lowest_reached"),
        )

    def _persist_closed_trade(self, trade_dict: dict) -> None:
        """Fecha o trade na tabela `trades` no ponto real do lifecycle."""
        try:
            existing = self.repository.get_by_id(trade_dict["id"])
            if existing is not None:
                _, outcome = split_legacy_status(trade_dict.get("status"))
                if outcome is None:
                    logger.warning(f"[{self.symbol}] Trade {trade_dict['id']} fechado sem outcome: {trade_dict.get('status')!r}")
                    return
                existing.close(
                    exit_price=trade_dict.get("exit_price", 0.0),
                    exit_epoch=trade_dict.get("exit_epoch", 0),
                    pnl=trade_dict.get("pnl", 0.0),
                    outcome=outcome,
                    close_reason=trade_dict.get("status"),
                )
                # Trailing stop pode ter movido SL e extremes desde a abertura.
                existing.sl = trade_dict.get("sl")
                existing.highest_reached = trade_dict.get("highest_reached")
                existing.lowest_reached = trade_dict.get("lowest_reached")
                self.repository.update(existing)
            else:
                self.repository.add(self._trade_from_runtime(trade_dict))
        except Exception as e:
            logger.error(f"[{self.symbol}] Falha ao persistir fechamento do trade {trade_dict.get('id')}: {e}")

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
            # O fechamento canônico acontece na tabela `trades` — o orchestrator
            # não precisa mais de journal próprio nem de `active_trade_ids` para
            # registrar saídas.
            for trade_dict in finished:
                self._persist_closed_trade(trade_dict)
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