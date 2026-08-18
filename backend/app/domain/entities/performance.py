from pydantic import BaseModel
from typing import Optional, ClassVar

class PersonalityPerformance(BaseModel):
    """Metricas de performance de curto prazo para uma personalidade."""
    # Constantes ajustáveis para tune
    WEIGHT_WR: ClassVar[float] = 40.0
    WEIGHT_PNL: ClassVar[float] = 60.0
    LOSS_PENALTY_FACTOR: ClassVar[float] = 2.0 # Exponencial: 2^losses

    personality_name: str
    symbol: str
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    trades_count: int = 0
    consecutive_losses: int = 0
    last_trade_epoch: Optional[int] = None
    last_update: Optional[float] = None

    @property
    def win_rate(self) -> float:
        if self.trades_count == 0:
            return 0.0
        return round((self.wins / self.trades_count) * 100, 2)

    @property
    def fitness(self) -> float:
        """
        Função de aptidão (fitness) robusta que combina Win Rate e PnL relativo.
        """
        if self.trades_count == 0:
            return 0.0

        # Normalização do WR (0 a 1)
        wr_score = (self.win_rate / 100) * self.WEIGHT_WR

        # PnL como ROI relativo (simplificado: PnL / (stake_fixo * trades_count))
        # Isso impede viés por "tempo de vida"
        # Usamos 10.0 como stake base (valor padrão configurado no PaperTrader)
        roi = self.total_pnl / (10.0 * self.trades_count)
        pnl_score = min(max(roi * 10, -50.0), 50.0) * (self.WEIGHT_PNL / 50.0)

        # Penalidade exponencial por perdas consecutivas
        # 1 perda = 1pt, 2 perdas = 3pts, 3 perdas = 7pts, 4 perdas = 15pts
        loss_penalty = (self.LOSS_PENALTY_FACTOR ** self.consecutive_losses) - 1

        return round(wr_score + pnl_score - loss_penalty, 2)

    def record_trade(self, is_win: bool, pnl: float) -> None:
        """Registra o resultado de um trade e atualiza as métricas de performance."""
        self.trades_count += 1
        self.total_pnl += pnl
        if is_win:
            self.wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1

    def reset_performance(self):
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.trades_count = 0
        self.consecutive_losses = 0
        self.last_trade_epoch = None
        self.last_update = None