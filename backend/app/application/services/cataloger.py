import math
import uuid
from typing import List
from app.domain.entities.market import Candle, CandleDirection, Tick, SignalType, Signal, RiskDecision, RiskEvaluation
from app.application.services.technical_analysis import (
    candles_to_df, apply_indicators,
    eval_ema_macd, eval_bollinger, eval_vwap, eval_smc, eval_supertrend, eval_pin_bar,
    eval_abcd, eval_consecutive, eval_rsi_ema_confluence, eval_mean_reversion_exhaustion
)

# Novas importações para a simulação com PaperTrader e RiskManager
from app.infrastructure.services.paper_trader_executor import PaperTrader
from app.infrastructure.services.risk_manager import RiskManager
from app.domain.entities.personality import Personality, RiskProfile




def calculate_win_rate(
    closed_candles: List[Candle],
    strategy_name: str,
    sl_multiplier: float = 1.5,
    tp_multiplier: float = 3.0,
) -> dict:
    """
    Simula entradas usando a estratégia técnica sobre o histórico de velas.
    Retorna o total de sinais gerados e a % de vitoria (Win Rate).
    Para simplificar o backtest no painel, consideramos WIN se a próxima vela fechar
    a favor da direção do sinal.
    """
    if len(closed_candles) < 50:
        return {"signals": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl_usdt": 0.0}

    # Converter para df e aplicar todos os indicadores de uma vez
    df = candles_to_df(closed_candles)
    df = apply_indicators(df)

    # Inicialização das variáveis de contagem
    signals_generated = 0
    wins = 0
    losses = 0
    pnl_usdt = 0.0
    trades = []

    # Mapeamento da estratégia
    strategy_func = None
    if strategy_name == "EMA+MACD":
        strategy_func = eval_ema_macd
    elif strategy_name == "Bollinger":
        strategy_func = eval_bollinger
    elif strategy_name == "VWAP":
        strategy_func = eval_vwap
    elif strategy_name == "SMC":
        strategy_func = eval_smc
    elif strategy_name == "SuperTrend":
        strategy_func = eval_supertrend
    elif strategy_name == "Pin Bar":
        strategy_func = eval_pin_bar
    elif strategy_name == "ABCD":
        strategy_func = eval_abcd
    elif strategy_name == "3 Velas":
        strategy_func = eval_consecutive
    elif strategy_name == "RSI+EMA":
        strategy_func = eval_rsi_ema_confluence
    elif strategy_name == "Exaustão":
        strategy_func = eval_mean_reversion_exhaustion
    else:
        return {"signals": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl_usdt": 0.0}

    # SIMULAÇÃO AVANÇADA COM RISKMANAGER E PAPERTRADER
    # ====================================================

    # Cria uma instância do RiskManager real
    risk_manager = RiskManager()

    # Cria uma personalidade de backtest que usa os parâmetros de SL/TP
    backtest_personality = Personality(
        name="Backtest",
        strategy=strategy_name,
        timeframe=300, # Fixo em M5 para este exemplo
        risk_profile=RiskProfile(
            sl_multiplier=sl_multiplier,
            tp_multiplier=tp_multiplier,
            leverage=10,
            position_sizing_mode="fixed",
            risk_percent=5.0, # Risco fixo de 5% da banca por trade
            max_trade_duration_minutes=240 # 4 horas
        )
    )

    # Cria um PaperTrader com um repositório em memória, isolado para este backtest
    trader = PaperTrader(
        symbol="BTC/USDT_BACKTEST",
        identity=f"backtest_{strategy_name}_{uuid.uuid4()}",
        repository=InMemoryPaperTraderRepository(),
        risk_manager=risk_manager,
        initial_balance=200.0, # Banca inicial para o backtest
        leverage=10,
        position_sizing_mode="fixed"
    )

    for i in range(50, len(df) - 1):
        sub_df = df.iloc[:i+1]
        signal_direction_str = strategy_func(sub_df)

        # Só processa se não houver trade aberto no simulador
        if signal_direction_str != "NONE" and not trader.open_positions:
            signals_generated += 1
            entry_price = df.iloc[i]["close"]
            entry_epoch = int(df.index[i].timestamp())
            atr_val = df.iloc[i].get("ATRr_14", entry_price * 0.005)

            # Usar o RiskManager para calcular SL/TP
            sl_tp_prices = risk_manager.calculate_sl_tp(
                backtest_personality,
                entry_price,
                atr_val,
                SignalType(signal_direction_str)
            )

            # Abrir o trade no simulador
            trader.open_trade(
                direction=signal_direction_str,
                tf=300,
                current_epoch=entry_epoch,
                current_price=entry_price,
                sl_price=sl_tp_prices["sl_price"],
                tp_price=sl_tp_prices["tp_price"],
                atr=atr_val,
                personality=backtest_personality
            )

            # Loop de simulação do trade
            for j in range(i + 1, len(df)):
                current_candle = df.iloc[j]
                current_price = current_candle["close"] # Usamos o fechamento como preço corrente
                current_epoch = int(df.index[j].timestamp())

                finished_trades = trader.check_positions(
                    current_epoch,
                    current_price,
                    backtest_personality
                )

                if finished_trades:
                    # O trade foi fechado, podemos sair do loop de simulação
                    break

    # Após o loop, coletar os resultados do trader
    final_state = trader.get_state()
    # Atualizar as variáveis de contagem com os resultados do trader
    signals_generated = len(final_state["history"])
    wins = sum(1 for t in final_state["history"] if t["status"] == "WIN")
    losses = sum(1 for t in final_state["history"] if t["status"] == "LOSS")
    trades = final_state["history"]
    # O PNL já está calculado no trader
    pnl_usdt = final_state["pnl"]

    win_rate = 0.0
    if wins + losses > 0:
        win_rate = round((wins / (wins + losses)) * 100, 2)

    return {
        "signals": signals_generated,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "pnl_usdt": round(pnl_usdt, 2),
        "trades": trades,
        "df": df
    }
