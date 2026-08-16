import pandas as pd
import pandas_ta as ta
from typing import List
from app.models.market import Candle

def candles_to_df(candles: List[Candle]) -> pd.DataFrame:
    data = []
    for c in candles:
        data.append({
            "time": c.epoch,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df.set_index("time", inplace=True)
        df = df[~df.index.duplicated(keep='last')]
        # Ensure datetime index for VWAP
        df.index = pd.to_datetime(df.index, unit='s', utc=True)
    return df

def apply_indicators(df: pd.DataFrame):
    if df.empty or len(df) < 30:
        return df
    # EMA + MACD
    df.ta.ema(length=9, append=True)
    df.ta.ema(length=21, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)

    # EMA + MACD
    df.ta.ema(length=9, append=True)
    df.ta.ema(length=21, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)

    # Bollinger
    df.ta.bbands(length=21, std=2, append=True)

    return df

# ─────────────────────────────────────────────────────────────────────────────
# Filtros de Qualidade de Sinal (Fase 1)
# ─────────────────────────────────────────────────────────────────────────────

def check_volume_filter(df: pd.DataFrame) -> bool:
    """
    Volume Filter: Só aceita sinal quando o volume da vela de sinal
    está acima da média das últimas 20 velas.
    """
    if df.empty or len(df) < 20:
        return True

    avg_volume = df["volume"].iloc[-20:-1].mean()
    last_volume = df["volume"].iloc[-1]

    # Aceita se a vela de sinal tem volume >= 80% da média
    return last_volume >= (avg_volume * 0.8)

def check_signal_quality(df_m1: pd.DataFrame, df_m5: pd.DataFrame, direction: str) -> tuple[bool, str]:
    """
    Filtro de qualidade: Mantém apenas o filtro de volume.
    """
    if not check_volume_filter(df_m1):
        return False, "Volume/amplitude abaixo da média (sinal fraco)"
    return True, "OK"

# ─────────────────────────────────────────────────────────────────────────────
# Estratégias de Sinal
# ─────────────────────────────────────────────────────────────────────────────

def eval_ema_macd(df: pd.DataFrame) -> str:
    """ EMA 9 cruza EMA 21 + MACD > 0 """
    if df.empty or len(df) < 30: return "NONE"
    last = df.iloc[-1]
    prev = df.iloc[-2]

    ema9, ema21 = last.get("EMA_9", 0), last.get("EMA_21", 0)
    p_ema9, p_ema21 = prev.get("EMA_9", 0), prev.get("EMA_21", 0)
    macd = last.get("MACDh_12_26_9", 0)

    if p_ema9 <= p_ema21 and ema9 > ema21 and macd > 0: return "CALL"
    if p_ema9 >= p_ema21 and ema9 < ema21 and macd < 0: return "PUT"
    return "NONE"

def eval_bollinger(df: pd.DataFrame) -> str:
    if df.empty or len(df) < 21: return "NONE"
    last = df.iloc[-1]
    close = last["close"]
    upper = last.get("BBU_21_2.0", 0)
    lower = last.get("BBL_21_2.0", 0)
    if close > upper and upper > 0: return "CALL"
    if close < lower and lower > 0: return "PUT"
    return "NONE"

def eval_consecutive(df: pd.DataFrame, num_candles: int = 3) -> str:
    """
    3 Velas Consecutivas:
    Entra a favor da tendência quando houver N velas seguidas da mesma cor.
    """
    if df.empty or len(df) < num_candles: return "NONE"

    last_n = df.iloc[-num_candles:]
    is_all_bullish = all((row["close"] > row["open"]) for idx, row in last_n.iterrows())
    is_all_bearish = all((row["close"] < row["open"]) for idx, row in last_n.iterrows())

    if is_all_bearish:
        return "CALL"
    if is_all_bullish:
        return "PUT"

    return "NONE"

def eval_pin_bar(df: pd.DataFrame) -> str:
    """
    Estratégia Pin Bar com Bollinger (21) e Volume.
    """
    if df.empty or len(df) < 21: return "NONE"

    last = df.iloc[-1]

    open_p = last["open"]
    close_p = last["close"]
    high_p = last["high"]
    low_p = last["low"]
    curr_vol = last["volume"]

    # Médias e Bandas
    avg_vol = df["volume"].iloc[-21:-1].mean()
    lower_band = last.get("BBL_21_2.0", 0)
    upper_band = last.get("BBU_21_2.0", 999999)

    body = abs(close_p - open_p)
    if body == 0:
        body = 0.000001

    lower_wick = min(open_p, close_p) - low_p
    upper_wick = high_p - max(open_p, close_p)

    # Bullish Pin Bar (Martelo)
    if lower_wick >= (2.0 * body) and upper_wick <= max(body, lower_wick * 0.25):
        if low_p <= (lower_band * 1.01) and curr_vol >= (1.1 * avg_vol):
            return "CALL"

    # Bearish Pin Bar (Estrela Cadente)
    if upper_wick >= (2.0 * body) and lower_wick <= max(body, upper_wick * 0.25):
        if high_p >= (upper_band * 0.99) and curr_vol >= (1.1 * avg_vol):
            return "PUT"

    return "NONE"

def eval_abcd(df: pd.DataFrame) -> str:
    """
    Estratégia ABCD: Stop Run.
    """
    if df.empty or len(df) < 6: return "NONE"

    c4 = df.iloc[-5]
    c3 = df.iloc[-4]
    c2 = df.iloc[-3]
    c1 = df.iloc[-2]
    c0 = df.iloc[-1]

    ema21_atual = c0.get("EMA_21", 0)
    ema21_prev = c1.get("EMA_21", 0)

    tendencia_alta = (ema21_atual > ema21_prev) and (ema21_atual > 0)
    manipulacao_fundo = c1["low"] < c3["low"]
    gatilho_compra = c0["close"] > c1["high"]

    if tendencia_alta and manipulacao_fundo and gatilho_compra:
        return "CALL"

    tendencia_baixa = (ema21_atual < ema21_prev) and (ema21_atual > 0)
    manipulacao_topo = c1["high"] > c3["high"]
    gatilho_venda = c0["close"] < c1["low"]

    if tendencia_baixa and manipulacao_topo and gatilho_venda:
        return "PUT"

    return "NONE"

def eval_bollinger_ema_macd(df: pd.DataFrame) -> str:
    """ Bollinger(21) + EMA + MACD """
    if df.empty or len(df) < 30: return "NONE"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = last["close"]
    upper = last.get("BBU_21_2.0", 0)
    lower = last.get("BBL_21_2.0", 0)

    ema9, ema21 = last.get("EMA_9", 0), last.get("EMA_21", 0)
    p_ema9, p_ema21 = prev.get("EMA_9", 0), prev.get("EMA_21", 0)
    macd = last.get("MACDh_12_26_9", 0)

    if close <= lower and p_ema9 <= p_ema21 and ema9 > ema21 and macd > 0:
        return "CALL"

    if close >= upper and p_ema9 >= p_ema21 and ema9 < ema21 and macd < 0:
        return "PUT"

    return "NONE"

def eval_triple_confluence(df: pd.DataFrame) -> str:
    """
    Confluência: Bollinger(21) + MACD.
    """
    if df.empty or len(df) < 30: return "NONE"

    last = df.iloc[-1]
    close = last["close"]

    bbu = last.get("BBU_21_2.0", 0)
    bbl = last.get("BBL_21_2.0", 0)
    macd_hist = last.get("MACDh_12_26_9", 0)

    if close <= bbl and macd_hist > 0:
        return "CALL"

    if close >= bbu and macd_hist < 0:
        return "PUT"

    return "NONE"
