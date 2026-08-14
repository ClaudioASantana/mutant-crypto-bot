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
        
    # SMC (Donchian - manter para retrocompatibilidade)
    df.ta.donchian(lower_length=20, upper_length=20, append=True)
    
    # SuperTrend
    df.ta.supertrend(length=10, multiplier=4.0, append=True)
    
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
    """
    if df.empty or len(df) < 20:
        return True
    
    avg_volume = df["volume"].iloc[-20:-1].mean()
    last_volume = df["volume"].iloc[-1]
    
    # Aceita se a vela de sinal tem volume >= 80% da média
    return last_volume >= (avg_volume * 0.8)

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

def eval_supertrend(df: pd.DataFrame) -> str:
    """ SuperTrend strategy """
    if df.empty or len(df) < 15: return "NONE"
    
    # pandas_ta supertrend outputs columns like SUPERTd_10_4.0 (direction)
    st_dir_col = [c for c in df.columns if "SUPERTd" in c]
    if not st_dir_col:
        return "NONE"
        
    last_dir = df.iloc[-1].get(st_dir_col[0], 0)
    prev_dir = df.iloc[-2].get(st_dir_col[0], 0)
    
    # Sinal quando a direção muda
    if prev_dir < 0 and last_dir > 0:
        return "CALL"
    if prev_dir > 0 and last_dir < 0:
        return "PUT"
        
    return "NONE"

def eval_smc(df: pd.DataFrame) -> str:
    """ SMC 2.0 - Detecção de Fair Value Gap (FVG) """
    if df.empty or len(df) < 5: return "NONE"
    
    # Pega as últimas 3 velas fechadas para buscar um FVG
    c1 = df.iloc[-3]
    c2 = df.iloc[-2]
    c3 = df.iloc[-1]
    
    # Bullish FVG: A mínima da vela 3 é MAIOR que a máxima da vela 1
    # A vela 2 é um candle direcional forte (bullish)
    if c1["high"] < c3["low"] and c2["close"] > c2["open"]:
        # Se a FVG formou, a zona entre c1.high e c3.low é suporte.
        # Nós operamos o rompimento do momento (CALL).
        return "CALL"
        
    # Bearish FVG: A máxima da vela 3 é MENOR que a mínima da vela 1
    # A vela 2 é direcional forte (bearish)
    if c1["low"] > c3["high"] and c2["close"] < c2["open"]:
        return "PUT"
        
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
    Estratégia Pin Bar (Martelo / Estrela Cadente) Elite:
    - Identifica rejeição de preço através de pavios longos.
    - Exige Contexto: Tocar/romper as Bandas de Bollinger.
    - Exige Volume Institucional: Volume da vela deve ser > 1.5x a média de volume recente.
    """
    if df.empty or len(df) < 20: return "NONE"
    
    last = df.iloc[-1]
    
    open_p = last["open"]
    close_p = last["close"]
    high_p = last["high"]
    low_p = last["low"]
    curr_vol = last["volume"]
    
    # Médias e Bandas
    avg_vol = df["volume"].iloc[-20:-1].mean()
    lower_band = last.get("BBL_20_2.0_2.0", 0)
    upper_band = last.get("BBU_20_2.0_2.0", 999999)
    
    body = abs(close_p - open_p)
    if body == 0:
        body = 0.000001
        
    lower_wick = min(open_p, close_p) - low_p
    upper_wick = high_p - max(open_p, close_p)
    
    # Bullish Pin Bar (Martelo)
    if lower_wick >= (2.0 * body) and upper_wick <= max(body, lower_wick * 0.25):
        # Contexto: Mínima próxima da banda inferior (1% de folga)
        if low_p <= (lower_band * 1.01) and curr_vol >= (1.1 * avg_vol):
            return "CALL"
        
    # Bearish Pin Bar (Estrela Cadente)
    if upper_wick >= (2.0 * body) and lower_wick <= max(body, upper_wick * 0.25):
        # Contexto: Máxima próxima da banda superior (1% de folga)
        if high_p >= (upper_band * 0.99) and curr_vol >= (1.1 * avg_vol):
            return "PUT"
        
    return "NONE"


def eval_abcd(df: pd.DataFrame) -> str:
    """
    Estratégia ABCD (Estratégia N - Stop Run):
    Opera manipulações institucionais a favor da inércia.
    - A (Início), B (Suporte/Resistência), C (Respiro), D (Rompimento Falso de B).
    - Gatilho: Preço fecha rompendo o candle D após a armadilha.
    - Validação: EMA 21 deve estar inclinada na direção da operação.
    """
    if df.empty or len(df) < 6: return "NONE"
    
    c4 = df.iloc[-5] # A (Início do movimento)
    c3 = df.iloc[-4] # B (Suporte/Resistência a ser manipulada)
    c2 = df.iloc[-3] # C (Respiro / Correção complexa)
    c1 = df.iloc[-2] # D (O Falso Rompimento)
    c0 = df.iloc[-1] # Candle Gatilho (Atual)
    
    ema21_atual = c0.get("EMA_21", 0)
    ema21_prev = c1.get("EMA_21", 0)
    
    # Condição para CALL (Stop Run de Fundo)
    # 1. Inércia de Alta (EMA 21 apontando pra cima)
    tendencia_alta = (ema21_atual > ema21_prev) and (ema21_atual > 0)
    # 2. Rompimento Falso (D viola a mínima de B)
    manipulacao_fundo = c1["low"] < c3["low"]
    # 3. Gatilho (Vela atual fecha acima da máxima da vela que violou o fundo)
    gatilho_compra = c0["close"] > c1["high"]
    
    if tendencia_alta and manipulacao_fundo and gatilho_compra:
        return "CALL"
        
    # Condição para PUT (Stop Run de Topo)
    # 1. Inércia de Baixa (EMA 21 apontando pra baixo)
    tendencia_baixa = (ema21_atual < ema21_prev) and (ema21_atual > 0)
    # 2. Rompimento Falso (D viola a máxima de B)
    manipulacao_topo = c1["high"] > c3["high"]
    # 3. Gatilho (Vela atual fecha abaixo da mínima da vela que violou o topo)
    gatilho_venda = c0["close"] < c1["low"]
    
    if tendencia_baixa and manipulacao_topo and gatilho_venda:
        return "PUT"
        
    return "NONE"
