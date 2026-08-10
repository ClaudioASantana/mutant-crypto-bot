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
            "volume": 1.0 # mock volume as it is missing in the model
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df.set_index("time", inplace=True)
        df = df[~df.index.duplicated(keep='last')]
        # Ensure datetime index for VWAP
        df.index = pd.to_datetime(df.index, unit='s')
    return df

def apply_indicators(df: pd.DataFrame):
    if df.empty or len(df) < 30:
        return df
    # EMA + MACD
    df.ta.ema(length=9, append=True)
    df.ta.ema(length=21, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    
    # Bollinger
    df.ta.bbands(length=20, std=2, append=True)
    
    # VWAP
    try:
        df.ta.vwap(append=True)
    except:
        df.ta.ema(length=50, append=True)
        
    # ATR for Dynamic SL/TP (Crypto Futures 1:2 R:R)
    df.ta.atr(length=14, append=True)
        
    # SMC (Donchian)
    df.ta.donchian(lower_length=20, upper_length=20, append=True)
    
    # === Fase 1: Filtros de Qualidade de Sinal ===
    # RSI(14) — detectar zonas de exaustão
    df.ta.rsi(length=14, append=True)
    
    # EMA(200) — referência de tendência macro
    if len(df) >= 200:
        df.ta.ema(length=200, append=True)
    
    return df

# ─────────────────────────────────────────────────────────────────────────────
# Filtros de Qualidade de Sinal (Fase 1)
# ─────────────────────────────────────────────────────────────────────────────

def check_rsi_filter(df: pd.DataFrame, direction: str) -> bool:
    """
    RSI Filter: Evita entrar em zonas de exaustão.
    CALL: RSI deve estar abaixo de 70 (não sobrecomprado)
    PUT:  RSI deve estar acima de 30 (não sobrevendido)
    """
    if df.empty or len(df) < 15:
        return True  # Se não há dados suficientes, deixa passar
    rsi = df.iloc[-1].get("RSI_14", 50)
    if pd.isna(rsi):
        return True
    if direction == "CALL" and rsi >= 70:
        return False  # Sobrecomprado, risco de reversão
    if direction == "PUT" and rsi <= 30:
        return False  # Sobrevendido, risco de reversão
    return True

def check_volume_filter(df: pd.DataFrame) -> bool:
    """
    Volume Filter: Só aceita sinal quando o volume da vela de sinal
    está acima da média das últimas 20 velas.
    (Como usamos volume mock=1.0, este filtro detecta padrões de preço
    com alta amplitude como proxy de volume real)
    """
    if df.empty or len(df) < 20:
        return True
    # Proxy de volume: amplitude da vela (high-low) vs média das últimas 20
    df_copy = df.copy()
    df_copy["range"] = df_copy["high"] - df_copy["low"]
    avg_range = df_copy["range"].iloc[-20:-1].mean()
    last_range = df_copy["range"].iloc[-1]
    # Aceita se a vela de sinal tem amplitude ≥ 80% da média (ligeiramente permissivo)
    return last_range >= (avg_range * 0.8)

def check_trend_filter(df: pd.DataFrame, direction: str) -> bool:
    """
    EMA 200 Trend Filter: Só opera na direção da tendência macro.
    CALL: EMA200 deve estar em alta (última > penúltima)
    PUT:  EMA200 deve estar em queda (última < penúltima)
    Se EMA200 não estiver disponível (< 200 velas), deixa passar.
    """
    if df.empty or len(df) < 201:
        return True  # Não há EMA200 ainda, deixa passar
    last = df.iloc[-1]
    prev = df.iloc[-2]
    ema200_last = last.get("EMA_200", None)
    ema200_prev = prev.get("EMA_200", None)
    if ema200_last is None or ema200_prev is None or pd.isna(ema200_last) or pd.isna(ema200_prev):
        return True
    if direction == "CALL" and ema200_last < ema200_prev:
        return False  # Tendência macro de baixa, não compra
    if direction == "PUT" and ema200_last > ema200_prev:
        return False  # Tendência macro de alta, não vende
    return True

def check_mtf_alignment(df_m5: pd.DataFrame, direction: str) -> bool:
    """
    MTF Confirmation (Fase 2): Verifica se o M5 está alinhado com o sinal M1.
    Usa o MACD do M5 como indicador de momentum:
    - CALL no M1: MACD M5 deve ser positivo (histograma > 0)
    - PUT no M1:  MACD M5 deve ser negativo (histograma < 0)
    """
    if df_m5 is None or df_m5.empty or len(df_m5) < 26:
        return True  # Sem dados M5, deixa passar
    df_m5_ind = apply_indicators(df_m5.copy()) if "MACDh_12_26_9" not in df_m5.columns else df_m5
    last = df_m5_ind.iloc[-1]
    macd_h = last.get("MACDh_12_26_9", 0)
    if pd.isna(macd_h):
        return True
    if direction == "CALL" and macd_h < 0:
        return False  # M5 ainda bearish
    if direction == "PUT" and macd_h > 0:
        return False  # M5 ainda bullish
    return True

def check_signal_quality(df_m1: pd.DataFrame, df_m5: pd.DataFrame, direction: str) -> tuple[bool, str]:
    """
    Filtro composto: Aplica todos os filtros de qualidade em sequência.
    Retorna (aprovado: bool, motivo_bloqueio: str)
    """
    if not check_rsi_filter(df_m1, direction):
        return False, f"RSI em exaustão para {direction}"
    if not check_volume_filter(df_m1):
        return False, "Volume/amplitude abaixo da média (sinal fraco)"
    if not check_trend_filter(df_m1, direction):
        return False, f"Contra-tendência EMA200 para {direction}"
    if not check_mtf_alignment(df_m5, direction):
        return False, f"MTF M5 não confirma direção {direction}"
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
    if df.empty or len(df) < 20: return "NONE"
    last = df.iloc[-1]
    close = last["close"]
    upper = last.get("BBU_20_2.0_2.0", 0)
    lower = last.get("BBL_20_2.0_2.0", 0)
    if close > upper and upper > 0: return "CALL"
    if close < lower and lower > 0: return "PUT"
    return "NONE"

def eval_vwap(df: pd.DataFrame) -> str:
    if df.empty or len(df) < 10: return "NONE"
    vwap_col = [c for c in df.columns if "VWAP" in c]
    if not vwap_col:
        vwap_col = ["EMA_50"]
    last_vwap = df.iloc[-1].get(vwap_col[0], 0)
    prev_vwap = df.iloc[-2].get(vwap_col[0], 0)
    
    close, p_close = df.iloc[-1]["close"], df.iloc[-2]["close"]
    if p_close <= prev_vwap and close > last_vwap: return "CALL"
    if p_close >= prev_vwap and close < last_vwap: return "PUT"
    return "NONE"

def eval_smc(df: pd.DataFrame) -> str:
    if df.empty or len(df) < 25: return "NONE"
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    close, p_close = last["close"], prev["close"]
    upper = prev.get("DCU_20_20", 0)
    lower = prev.get("DCL_20_20", 0)
    
    if p_close <= upper and close > upper and upper > 0: return "CALL"
    if p_close >= lower and close < lower and lower > 0: return "PUT"
    return "NONE"

def eval_wyckoff_bollinger(df: pd.DataFrame) -> str:
    """
    Reteste Wyckoff com Bollinger:
    1. Rompeu a banda superior/inferior nas últimas 2 a 5 velas.
    2. A vela atual faz um recuo (reteste) tocando a banda, mas fechando a favor da tendência.
    """
    if df.empty or len(df) < 25: return "NONE"
    last = df.iloc[-1]
    
    upper = last.get("BBU_20_2.0_2.0", 0)
    lower = last.get("BBL_20_2.0_2.0", 0)
    if upper == 0 or lower == 0:
        return "NONE"
        
    # Verificar se rompeu para fora nas últimas velas (sem contar a atual)
    was_overbought = any(df.iloc[-i]["close"] > df.iloc[-i].get("BBU_20_2.0_2.0", 999999) for i in range(2, 6))
    was_oversold = any(df.iloc[-i]["close"] < df.iloc[-i].get("BBL_20_2.0_2.0", 0) for i in range(2, 6))
    
    # Reteste de compra: mínima da vela atual toca ou fica abaixo da banda superior, mas fecha acima
    if was_overbought and last["low"] <= upper and last["close"] > upper:
        return "CALL"
        
    # Reteste de venda: máxima da vela atual toca ou fica acima da banda inferior, mas fecha abaixo
    if was_oversold and last["high"] >= lower and last["close"] < lower:
        return "PUT"
        
    return "NONE"

def eval_wyckoff_smc(df: pd.DataFrame) -> str:
    """
    Reteste Wyckoff com SMC (Donchian):
    1. Rompeu o canal Donchian superior/inferior nas últimas 2 a 5 velas.
    2. A vela atual retesta o nível rompido (canal anterior) e reage.
    """
    if df.empty or len(df) < 25: return "NONE"
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    dcu = prev.get("DCU_20_20", 0)
    dcl = prev.get("DCL_20_20", 0)
    if dcu == 0 or dcl == 0:
        return "NONE"
        
    # Verificar rompimento nas últimas velas
    broke_above = any(df.iloc[-i]["close"] > df.iloc[-i-1].get("DCU_20_20", 999999) for i in range(2, 6))
    broke_below = any(df.iloc[-i]["close"] < df.iloc[-i-1].get("DCL_20_20", 0) for i in range(2, 6))
    
    # Reteste compra: mínima testa a resistência rompida (dcu) e o fechamento se mantém acima
    if broke_above and last["low"] <= dcu and last["close"] > dcu:
        return "CALL"
        
    # Reteste venda: máxima testa o suporte rompido (dcl) e o fechamento se mantém abaixo
    if broke_below and last["high"] >= dcl and last["close"] < dcl:
        return "PUT"
        
    return "NONE"

