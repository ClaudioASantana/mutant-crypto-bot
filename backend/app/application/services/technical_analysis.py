import pandas as pd
import pandas_ta  # noqa: F401  (registra o accessor df.ta usado em apply_indicators)
from typing import List
from app.domain.entities.market import Candle
from app.domain.services.strategy_registry import register_strategy

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
    df.ta.ema(length=15, append=True)
    df.ta.ema(length=20, append=True)
    df.ta.ema(length=21, append=True)
    df.ta.ema(length=50, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    
    # Bollinger
    df.ta.bbands(length=20, std=2, append=True)
    
    # Keltner Channels (for Volatility Squeeze)
    try:
        df.ta.kc(length=20, scalar=1.5, append=True)
    except Exception:
        pass
    
    # VWAP
    try:
        df.ta.vwap(append=True)
    except:
        df.ta.ema(length=50, append=True)
        
    # ATR for Dynamic SL/TP (Crypto Futures 1:2 R:R)
    df.ta.atr(length=14, append=True)
        
    # SMC (Donchian - manter para retrocompatibilidade)
    df.ta.donchian(lower_length=20, upper_length=20, append=True)

    # Donchian 55 — base do breakout de regime (P2/H2)
    try:
        df.ta.donchian(lower_length=55, upper_length=55, append=True)
    except Exception:
        pass
    
    # SuperTrend
    df.ta.supertrend(length=10, multiplier=4.0, append=True)
    
    # === Fase 1: Filtros de Qualidade de Sinal ===
    # RSI(14) — detectar zonas de exaustão
    df.ta.rsi(length=14, append=True)
    
    # EMA(200) — referência de tendência macro
    if len(df) >= 200:
        df.ta.ema(length=200, append=True)

    # ADX(14) — força de tendência, usado por filter_regime_adx (P2/H1)
    try:
        df.ta.adx(length=14, append=True)
    except Exception:
        pass

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

def filter_session_utc(df: pd.DataFrame, direction: str, sessions: list = None) -> bool:
    """
    Filtro de sessão (H1/P2): só aceita sinal DENTRO das janelas de alta
    liquidez configuradas em UTC.

    `sessions` é uma lista de tuplas (hora_inicio, hora_fim) em UTC,
    com `inicio <= hora < fim`. Default: overlap Londres/NY (12h–17h UTC).
    O índice do df é UTC por construção (epoch ou tz-aware).

    Se o df não tiver índice datável, deixa passar (fail-open de forma).
    """
    if df is None or df.empty:
        return True
    last_ts = df.index[-1]
    if not hasattr(last_ts, "hour"):
        return True

    if sessions is None:
        sessions = [(12, 17)]

    hour = last_ts.hour
    for start, end in sessions:
        if start <= hour < end:
            return True
    return False


def filter_atr_percentile(
    df: pd.DataFrame,
    direction: str,
    percentile_min: float = 0.40,
    percentile_max: float = 0.90,
    lookback: int = 100,
) -> bool:
    """
    Filtro de volatilidade (H1/P2): exige que o ATR do candle de sinal esteja
    no percentil empírico [min, max] dos últimos `lookback` candles.

    Evita entrar com volatilidade comprimida demais (movimento improvável)
    ou esticada demais (saída ruim). Sem dados suficientes, deixa passar.
    """
    if df is None or df.empty or len(df) < 30:
        return True
    if "ATRr_14" not in df.columns:
        return True

    atr = df["ATRr_14"]
    last = atr.iloc[-1]
    if pd.isna(last):
        return True

    window = atr.iloc[-lookback:].dropna()
    if len(window) < 20:
        return True

    pct = float((window < last).mean())
    return bool(percentile_min <= pct <= percentile_max)


def filter_regime_adx(df: pd.DataFrame, direction: str, threshold: float = 25.0) -> bool:
    """
    Filtro de regime de tendência (H1/P2): exige ADX(14) >= `threshold`
    no candle de sinal. Sem ADX disponível (coluna ausente/NaN), deixa passar.
    """
    if df is None or df.empty:
        return True
    if "ADX_14" not in df.columns:
        return True

    adx = df["ADX_14"].iloc[-1]
    if pd.isna(adx):
        return True
    return bool(adx >= threshold)


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

@register_strategy("EMA+MACD")
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

@register_strategy("Bollinger")
def eval_bollinger(df: pd.DataFrame) -> str:
    if df.empty or len(df) < 20: return "NONE"
    last = df.iloc[-1]
    close = last["close"]
    upper = last.get("BBU_20_2.0_2.0", 0)
    lower = last.get("BBL_20_2.0_2.0", 0)
    if upper > 0 and close >= upper: return "PUT"
    if lower > 0 and close <= lower: return "CALL"
    return "NONE"

@register_strategy("Volatility Squeeze")
def eval_volatility_squeeze(df: pd.DataFrame) -> str:
    """
    Squeeze Breakout:
    - Squeeze occurs when Bollinger Bands are completely inside Keltner Channels.
    - Release (breakout) occurs when BB expands outside KC.
    - We look for a breakout with volume and MACD alignment.
    """
    if df.empty or len(df) < 25: return "NONE"
    
    # Check if we have the necessary columns
    bbu = df.columns.intersection(["BBU_20_2.0_2.0"]).empty == False
    kcu = df.columns.intersection(["KCUe_20_1.5"]).empty == False
    
    if not bbu or not kcu:
        return "NONE"

    # A squeeze is ON when BB is inside KC (BB upper < KC upper AND BB lower > KC lower)
    # We define squeeze_on series
    bb_up = df["BBU_20_2.0_2.0"]
    bb_low = df["BBL_20_2.0_2.0"]
    kc_up = df["KCUe_20_1.5"]
    kc_low = df["KCLe_20_1.5"]
    
    squeeze_on = (bb_up < kc_up) & (bb_low > kc_low)
    
    # We want a recent squeeze that just fired (squeeze turned OFF)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Was it squeezing recently? (e.g., in the last 5 candles before the current one)
    recent_squeeze = squeeze_on.iloc[-5:-1].any()
    currently_squeezing = squeeze_on.iloc[-1]
    
    if recent_squeeze and not currently_squeezing:
        # Breakout occurred! Check direction
        macd = last.get("MACDh_12_26_9", 0)
        close = last["close"]
        
        # Volume spike check (last volume > 1.5x average)
        vol_avg = df["volume"].iloc[-21:-1].mean()
        vol_spike = last["volume"] > (vol_avg * 1.5)
        
        # CALL: Price breaks above upper KC and MACD is positive
        if close > kc_up.iloc[-1] and macd > 0 and vol_spike:
            return "CALL"
            
        # PUT: Price breaks below lower KC and MACD is negative
        if close < kc_low.iloc[-1] and macd < 0 and vol_spike:
            return "PUT"

    return "NONE"

@register_strategy("Regime Switch")
def eval_regime_switch(df: pd.DataFrame) -> str:
    """
    Regime-Switching Strategy using ADX(14).
    - If ADX > 25 (Trending): uses Volatility Squeeze (Breakout) or EMA+MACD.
    - If ADX < 25 (Ranging): uses Bollinger (Mean Reversion).
    """
    if df.empty or len(df) < 30: return "NONE"
    
    adx_col = next((c for c in df.columns if "ADX" in c), None)
    if not adx_col:
        # Fallback se não tiver ADX
        return eval_ema_macd(df)
        
    adx_val = df.iloc[-1][adx_col]
    if pd.isna(adx_val):
        return "NONE"
        
    if adx_val > 25:
        # Mercado em Tendência
        sig = eval_volatility_squeeze(df)
        if sig == "NONE":
            sig = eval_ema_macd(df)
        return sig
    else:
        # Mercado Lateral / Range
        return eval_bollinger(df)

@register_strategy("Momentum Breakout")
def eval_momentum_breakout(df: pd.DataFrame) -> str:
    """ 
    Estratégia Agressiva de Momentum: 
    Cruza as EMAs curtas a favor da tendência macro e exige força no RSI.
    """
    if df.empty or len(df) < 50: return "NONE"
    
    last = df.iloc[-1]
    close = last["close"]
    ema9 = last.get("EMA_9", 0)
    ema21 = last.get("EMA_21", 0)
    ema50 = last.get("EMA_50", 0)
    rsi = last.get("RSI_14", 50)
    
    # Comprar (CALL) quando a tendência de curto prazo (EMA9 > EMA21) 
    # está acima da tendência média (EMA50) e o momentum é forte (RSI > 55)
    if ema9 > ema21 and close > ema50 and rsi > 55:
        return "CALL"
        
    # Vender (PUT) quando a tendência de curto prazo é de baixa
    # e está abaixo da média (EMA50) com momentum fraco (RSI < 45)
    if ema9 < ema21 and close < ema50 and rsi < 45:
        return "PUT"
        
    return "NONE"

@register_strategy("VWAP")
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

@register_strategy("VWAP Z-Score")
def eval_vwap_zscore(df: pd.DataFrame) -> str:
    """
    Mean reversion em torno da VWAP com gatilho por z-score.

    CALL:
    - candle anterior estava muito abaixo da VWAP (z <= -1.5)
    - candle atual mostra reversão (z subindo e close > close anterior)
    - evita compra contra tendência macro quando EMA200 estiver descendente

    PUT:
    - candle anterior estava muito acima da VWAP (z >= +1.5)
    - candle atual mostra reversão (z caindo e close < close anterior)
    - evita venda contra tendência macro quando EMA200 estiver ascendente
    """
    if df.empty or len(df) < 30:
        return "NONE"

    vwap_col = next((c for c in df.columns if "VWAP" in c), None)
    if vwap_col is None:
        return "NONE"

    window = 20
    closes = df["close"]
    distance = closes - df[vwap_col]
    distance_std = distance.rolling(window=window).std(ddof=0)
    zscore = distance / distance_std.replace(0, pd.NA)

    if len(zscore.dropna()) < 2:
        return "NONE"

    last = df.iloc[-1]
    prev = df.iloc[-2]
    last_z = zscore.iloc[-1]
    prev_z = zscore.iloc[-2]

    if pd.isna(last_z) or pd.isna(prev_z):
        return "NONE"

    ema200_last = last.get("EMA_200")
    ema200_prev = prev.get("EMA_200")
    ema200_up = (
        ema200_last is not None and ema200_prev is not None
        and not pd.isna(ema200_last) and not pd.isna(ema200_prev)
        and ema200_last >= ema200_prev
    )
    ema200_down = (
        ema200_last is not None and ema200_prev is not None
        and not pd.isna(ema200_last) and not pd.isna(ema200_prev)
        and ema200_last <= ema200_prev
    )

    if prev_z <= -1.5 and last_z > prev_z and last["close"] > prev["close"]:
        if ema200_last is not None and not pd.isna(ema200_last) and not ema200_up:
            return "NONE"
        return "CALL"

    if prev_z >= 1.5 and last_z < prev_z and last["close"] < prev["close"]:
        if ema200_last is not None and not pd.isna(ema200_last) and not ema200_down:
            return "NONE"
        return "PUT"

    return "NONE"

@register_strategy("SuperTrend")
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

@register_strategy("SMC")
def eval_smc(df: pd.DataFrame) -> str:
    """
    SMC 3.0 - Detecção de Fair Value Gap (FVG) com Contexto de Mercado.
    - Filtros: Estrutura de Mercado (Higher Highs/Lows), Volume Institucional, RSI e EMA20.
    """
    if len(df) < 55:
        return "NONE"

    # Contexto de mercado
    structure = _get_market_structure(df)
    trend = _get_market_trend(structure)

    # Detectar FVG nas últimas 3 velas
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    is_bullish_fvg = c1["high"] < c3["low"] and c2["close"] > c2["open"]
    is_bearish_fvg = c1["low"] > c3["high"] and c2["close"] < c2["open"]

    # Volume do candle de ignição (c2)
    avg_vol = df["volume"].iloc[-21:-1].mean()
    volume_ok = c2["volume"] > (avg_vol * 1.2)

    # Confluência: EMA 20 e RSI
    ema20 = df["EMA_20"].iloc[-1]
    rsi = df["RSI_14"].iloc[-1]

    # CALL: FVG Bullish + Tendência Bullish/Range + Filtros
    if is_bullish_fvg and trend != "BEARISH" and volume_ok and 25 < rsi < 70 and c2["close"] > ema20:
        return "CALL"

    # PUT: FVG Bearish + Tendência Bearish/Range + Filtros
    if is_bearish_fvg and trend != "BULLISH" and volume_ok and 30 < rsi < 75 and c2["close"] < ema20:
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

@register_strategy("Wyckoff_SMC")
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

def _is_bullish_candle(candle) -> bool:
    return candle["close"] > candle["open"]


def _is_bearish_candle(candle) -> bool:
    return candle["close"] < candle["open"]

def _detect_swing_high(df: pd.DataFrame, index: int, lookback: int = 2, lookforward: int = 2) -> bool:
    """
    Detecta um Swing High no `index` dado.
    Um Swing High é um ponto onde o preço [`high`] é o maior dentro de
    `lookback` velas anteriores e `lookforward` velas seguintes.
    """
    if index < lookback or index + lookforward >= len(df):
        return False
    window = df.iloc[index - lookback: index + lookforward + 1]
    return bool(df.iloc[index]["high"] == window["high"].max())

def _detect_swing_low(df: pd.DataFrame, index: int, lookback: int = 2, lookforward: int = 2) -> bool:
    """
    Detecta um Swing Low no `index` dado.
    Um Swing Low é um ponto onde o preço [`low`] é o menor dentro de
    `lookback` velas anteriores e `lookforward` velas seguintes.
    """
    if index < lookback or index + lookforward >= len(df):
        return False
    window = df.iloc[index - lookback: index + lookforward + 1]
    return bool(df.iloc[index]["low"] == window["low"].min())

def _get_market_structure(df: pd.DataFrame, num_candles: int = 50) -> list:
    """
    Constrói uma lista de swings (pontos de estrutura de mercado) sobre as
    últimas `num_candles` velas.
    Cada elemento é um dict: {"index": int, "type": "high"|"low", "price": float}.
    """
    structure = []
    start = max(2, len(df) - num_candles)
    end = len(df) - 3  # Garante 2 velas de confirmação à frente
    for i in range(start, end):
        if _detect_swing_high(df, i):
            structure.append({"index": i, "type": "high", "price": df.iloc[i]["high"]})
        elif _detect_swing_low(df, i):
            structure.append({"index": i, "type": "low", "price": df.iloc[i]["low"]})
    return structure

def _get_market_trend(structure: list) -> str:
    """
    Determina a tendência dominante baseada na sequência de swings.
    - "BULLISH": Higher Highs (HH) e Higher Lows (HL).
    - "BEARISH": Lower Lows (LL) e Lower Highs (LH).
    - "RANGE": Ambíguo / lateral.
    """
    highs = [s for s in structure if s["type"] == "high"]
    lows = [s for s in structure if s["type"] == "low"]

    if len(highs) < 2 or len(lows) < 2:
        return "RANGE"

    # Verifica se os highs estão subindo (Higher Highs)
    highs_prices = [h["price"] for h in highs]
    higher_high_sequence = highs_prices[-1] > highs_prices[-2]

    # Verifica se os lows estão subindo (Higher Lows)
    lows_prices = [l["price"] for l in lows]
    higher_low_sequence = lows_prices[-1] > lows_prices[-2]

    # Verifica se os lows estão caindo (Lower Lows)
    lower_low_sequence = lows_prices[-1] < lows_prices[-2]

    # Verifica se os highs estão caindo (Lower Highs)
    lower_high_sequence = highs_prices[-1] < highs_prices[-2]

    if higher_high_sequence and higher_low_sequence:
        return "BULLISH"
    if lower_low_sequence and lower_high_sequence:
        return "BEARISH"
    # Prioriza o alinhamento da última direção se apenas um confirma
    if higher_high_sequence and not lower_high_sequence:
        return "BULLISH"
    if lower_low_sequence and not higher_low_sequence:
        return "BEARISH"
    return "RANGE"

def _get_candle_body_range(candle):
    return abs(candle["close"] - candle["open"])

def _get_midpoint(candle):
    return (candle["high"] + candle["low"]) / 2

def _get_candle_body_midpoint(candle):
    return (candle["open"] + candle["close"]) / 2

def _check_confluence_filters(df: pd.DataFrame, direction: str, require_confluence: bool = True) -> bool:
    """
    Aplica filtros de volume e EMA para validar sinais de 3 velas.
    - Volume: Última vela deve ter volume > 1.0 * volume médio das últimas 20.
    - EMA: Para CALL, preço deve estar acima da EMA 20. Para PUT, abaixo da EMA 20.
    require_confluence=False desativa os filtros (usado para isolar a geometria
    do padrão durante auditorias/backtests).
    """
    if not require_confluence:
        return True  # Isola apenas a geometria do padrão

    if len(df) < 21: # Mínimo para EMA20 e volume médio
        return False

    # Filtro de Volume
    last_volume = df["volume"].iloc[-1]
    avg_volume = df["volume"].iloc[-21:-1].mean() # Últimas 20 velas, excluindo a atual
    if last_volume < avg_volume * 1.0: # Apenas 1x a média
        return False

    # Filtro de EMA (Média Móvel Exponencial de 20 períodos)
    if "EMA_20" not in df.columns or df["EMA_20"].isnull().iloc[-1]:
        return False

    last_close = df["close"].iloc[-1]
    ema_20 = df["EMA_20"].iloc[-1]

    if direction == "CALL":
        if last_close < ema_20:
            return False
    elif direction == "PUT":
        if last_close > ema_20:
            return False

    return True

def eval_three_white_soldiers(df: pd.DataFrame, require_confluence: bool = True) -> str:
    """
    Detects Three White Soldiers pattern.
    Structure: Three consecutive long bullish candles with progressively higher closes.
               Each opens within the previous candle's body, minimal upper shadows.
    Filters:
    - Volume: Third candle has above average volume.
    - EMA: Price (last close) is above EMA 20.
    """
    if len(df) < 3:
        return "NONE"

    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

    # All three must be bullish
    if not (_is_bullish_candle(c1) and _is_bullish_candle(c2) and _is_bullish_candle(c3)):
        return "NONE"

    # Progressively higher closes
    if not (c3["close"] > c2["close"] > c1["close"]):
        return "NONE"

    # Opens within previous body
    if not (c1["open"] <= c2["open"] <= c1["close"] and c2["open"] <= c3["open"] <= c2["close"]):
        return "NONE"

    # Apply confluence filters
    if not _check_confluence_filters(df, "CALL", require_confluence):
        return "NONE"

    return "CALL"

def eval_three_black_crows(df: pd.DataFrame, require_confluence: bool = True) -> str:
    """
    Detects Three Black Crows pattern.
    Structure: Three consecutive long bearish candles with progressively lower closes.
               Each opens within the previous candle's body, minimal lower shadows.
    """
    if len(df) < 3:
        return "NONE"

    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

    # All three must be bearish
    if not (_is_bearish_candle(c1) and _is_bearish_candle(c2) and _is_bearish_candle(c3)):
        return "NONE"

    # Progressively lower closes
    if not (c3["close"] < c2["close"] < c1["close"]):
        return "NONE"

    # Opens within previous body
    if not (c1["open"] >= c2["open"] >= c1["close"] and c2["open"] >= c3["open"] >= c2["close"]):
        return "NONE"

    # Aplica filtros de confluência (volume + EMA 20)
    if not _check_confluence_filters(df, "PUT", require_confluence):
        return "NONE"

    return "PUT"

def eval_morning_star(df: pd.DataFrame, require_confluence: bool = True) -> str:
    """
    Detects Morning Star pattern.
    Structure: Bearish candle, small body candle (Doji/Spinning Top) with gap down,
               bullish candle closing above 50% of the first candle.
    """
    if len(df) < 3:
        return "NONE"

    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

    # 1. First candle is long bearish
    if not _is_bearish_candle(c1):
        return "NONE"
    # To be "long", the body should be substantial. Let's say, at least 50% of its high-low range.
    if _get_candle_body_range(c1) / (c1["high"] - c1["low"] + 1e-9) < 0.5:
        return "NONE"

    # 2. Second candle is small body (Doji or Spinning Top) and gaps down
    body_c2_ratio = _get_candle_body_range(c2) / (c2["high"] - c2["low"] + 1e-9)
    if body_c2_ratio > 0.5 or body_c2_ratio == 0: # Body too large or is a perfect Doji
        return "NONE"

    # Gap down check
    if not (c2["open"] < c1["close"] and c2["close"] < c1["close"]):
        return "NONE"

    # 3. Third candle is bullish and closes above the midpoint of the first candle
    if not _is_bullish_candle(c3):
        return "NONE"

    midpoint_c1_body = _get_candle_body_midpoint(c1) # Using body midpoint as per wiki for validation
    if c3["close"] <= midpoint_c1_body:
        return "NONE"

    # Aplica filtros de confluência (volume + EMA 20)
    if not _check_confluence_filters(df, "CALL", require_confluence):
        return "NONE"

    return "CALL"

def eval_evening_star(df: pd.DataFrame, require_confluence: bool = True) -> str:
    """
    Detects Evening Star pattern.
    Structure: Bullish candle, small body candle (Doji/Spinning Top) with gap up,
               bearish candle closing below 50% of the first candle.
    """
    if len(df) < 3:
        return "NONE"

    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

    # 1. First candle is long bullish
    if not _is_bullish_candle(c1):
        return "NONE"
    # To be "long", the body should be substantial.
    if _get_candle_body_range(c1) / (c1["high"] - c1["low"] + 1e-9) < 0.5:
        return "NONE"

    # 2. Second candle is small body (Doji or Spinning Top) and gaps up
    body_c2_ratio = _get_candle_body_range(c2) / (c2["high"] - c2["low"] + 1e-9)
    if body_c2_ratio > 0.5 or body_c2_ratio == 0: # Body too large or is a perfect Doji
        return "NONE"

    # Gap up check
    if not (c2["open"] > c1["close"] and c2["close"] > c1["close"]):
        return "NONE"

    # 3. Third candle is bearish and closes below the midpoint of the first candle
    if not _is_bearish_candle(c3):
        return "NONE"

    midpoint_c1_body = _get_candle_body_midpoint(c1)
    if c3["close"] >= midpoint_c1_body:
        return "NONE"

    # Aplica filtros de confluência (volume + EMA 20)
    if not _check_confluence_filters(df, "PUT", require_confluence):
        return "NONE"

    return "PUT"

def eval_three_bar_play(df: pd.DataFrame, require_confluence: bool = True) -> str:
    """
    Detects 3 Bar Play pattern (continuation).
    Structure: Igniting bar (strong directional), Resting bar (small, inside), Trigger bar (breaks resting bar).
    """
    if len(df) < 3:
        return "NONE"

    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1] # c1=Igniting, c2=Resting, c3=Trigger

    # For Igniting bar (c1), we need a strong directional candle.
    # Let's define strong as body being at least 70% of the candle's total range.
    is_c1_strong_bull = _is_bullish_candle(c1) and (_get_candle_body_range(c1) / (c1["high"] - c1["low"] + 1e-9) > 0.7)
    is_c1_strong_bear = _is_bearish_candle(c1) and (_get_candle_body_range(c1) / (c1["high"] - c1["low"] + 1e-9) > 0.7)

    if is_c1_strong_bull: # Bullish 3 Bar Play
        # Resting bar (c2) must be small and within the upper half of c1's body
        # Small body: body_c2_ratio < 0.5
        # Inside c1: c2 high < c1 high AND c2 low > c1 low
        # Closes in upper half of c1: c2 close > c1_body_midpoint
        if not (
            c2["high"] < c1["high"] and c2["low"] > c1["low"] and # c2 is inside c1
            _get_candle_body_range(c2) / (c2["high"] - c2["low"] + 1e-9) < 0.5 and # Small body
            c2["close"] > _get_candle_body_midpoint(c1) # Closes in upper half of c1's body
        ):
            return "NONE"

        # Trigger bar (c3) breaks above c2's high
        if c3["close"] > c2["high"]:
            # Aplica filtros de confluência (volume + EMA 20)
            if not _check_confluence_filters(df, "CALL", require_confluence):
                return "NONE"
            return "CALL"

    elif is_c1_strong_bear: # Bearish 3 Bar Play
        # Resting bar (c2) must be small and within the lower half of c1's body
        # Small body: body_c2_ratio < 0.5
        # Inside c1: c2 high < c1 high AND c2 low > c1 low
        # Closes in lower half of c1: c2 close < c1_body_midpoint
        if not (
            c2["low"] > c1["low"] and c2["high"] < c1["high"] and # c2 is inside c1
            _get_candle_body_range(c2) / (c2["high"] - c2["low"] + 1e-9) < 0.5 and # Small body
            c2["close"] < _get_candle_body_midpoint(c1) # Closes in lower half of c1's body
        ):
            return "NONE"

        # Trigger bar (c3) breaks below c2's low
        if c3["close"] < c2["low"]:
            # Aplica filtros de confluência (volume + EMA 20)
            if not _check_confluence_filters(df, "PUT", require_confluence):
                return "NONE"
            return "PUT"

    return "NONE"

@register_strategy("3 Velas")
def eval_three_candles_composite(df: pd.DataFrame, require_confluence: bool = True) -> str:
    """
    Composite evaluation for various 3-candle patterns.
    This function will be called as "3 Velas" strategy.
    It prioritizes continuation over reversal if both are present in the same candle context.
    require_confluence=False isola a geometria (auditorias/backtests).
    """
    if len(df) < 3:
        return "NONE"

    # Check for continuation first (3 Bar Play is a strong continuation signal)
    signal = eval_three_bar_play(df, require_confluence)
    if signal != "NONE":
        return signal

    # Then check for reversals
    signal = eval_three_white_soldiers(df, require_confluence)
    if signal != "NONE":
        return signal

    signal = eval_three_black_crows(df, require_confluence)
    if signal != "NONE":
        return signal

    signal = eval_morning_star(df, require_confluence)
    if signal != "NONE":
        return signal

    signal = eval_evening_star(df, require_confluence)
    if signal != "NONE":
        return signal

    return "NONE"


def eval_consecutive(df: pd.DataFrame) -> str:
    """
    Evaluates for specific 3-candle patterns (composite strategy from the wiki).
    This function acts as the entry point for the new 3-candle composite logic
    when the strategy is named "3 Velas".
    """
    return eval_three_candles_composite(df)

@register_strategy("Pin Bar")
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

def eval_rsi_ema_confluence(df: pd.DataFrame) -> str:
    """
    Estratégia de Confluência RSI + EMA (Trend-Pullback):
    Opera a favor da tendência de curto prazo, entrando apenas em retrocessos
    (pullbacks) que o RSI mostra serem saudáveis — não sobrecomprados/sobrevendidos.

    Confluência exigida para CALL:
      - EMA_21 em alta (atual > anterior) → tendência bullish.
      - Preço acima da EMA_21 → momentum a favor da compra.
      - RSI_14 em zona de retrocesso (40–65) e subindo → impulso saudável.

    Confluência exigida para PUT (espelho):
      - EMA_21 em queda (atual < anterior) → tendência bearish.
      - Preço abaixo da EMA_21 → momentum a favor da venda.
      - RSI_14 em zona de retrocesso (35–60) e caindo → impulso saudável.

    Retorna "CALL", "PUT" ou "NONE".
    """
    if df.empty or len(df) < 25:
        return "NONE"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    ema21 = last.get("EMA_21", None)
    ema21_prev = prev.get("EMA_21", None)
    rsi = last.get("RSI_14", None)
    rsi_prev = prev.get("RSI_14", None)

    if pd.isna(ema21) or pd.isna(ema21_prev) or pd.isna(rsi) or pd.isna(rsi_prev):
        return "NONE"

    close = last["close"]

    # Filtros de Volume Institucional (mínimo 1.2x a média de 50)
    avg_vol = df["volume"].iloc[-51:-1].mean()
    if last["volume"] < avg_vol * 1.2:
        return "NONE"

    # CALL: tendência de alta forte + pullback em zona de respiro específica
    # Exigimos inclinação na EMA (diferença positiva significativa)
    ema_slope = (ema21 - ema21_prev)
    if ema21 > ema21_prev and ema_slope > (ema21 * 0.0001) and close > ema21 and 40 <= rsi <= 60 and rsi > rsi_prev:
        return "CALL"

    # PUT: tendência de baixa forte + pullback em zona de respiro específica
    if ema21 < ema21_prev and ema_slope < -(ema21 * 0.0001) and close < ema21 and 40 <= rsi <= 60 and rsi < rsi_prev:
        return "PUT"

    return "NONE"

def eval_mean_reversion_exhaustion(df: pd.DataFrame) -> str:
    """
    Estratégia de Mean Reversion (Exaustão):
    Focada em capturar reversões após movimentos climáticos.

    Lógica:
    - Identifica 'Candle Climático': Tamanho do corpo > 2x a média das últimas 10 velas.
    - RSI Extremo: < 20 (sobrevendido) para CALL ou > 80 (sobrecomprado) para PUT.
    - Gatilho: Reversão imediata na próxima vela.
    """
    if len(df) < 20: return "NONE"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Candle climático é o anterior
    prev_body = abs(prev["close"] - prev["open"])
    last_10 = df.iloc[-11:-1]  # 10 velas anteriores (sem a atual)
    avg_body = (abs(last_10["close"] - last_10["open"])).mean()

    rsi = prev.get("RSI_14", 50)

    is_climactic = prev_body > (avg_body * 2.0) if avg_body > 0 else False

    # CALL: Queda climática + RSI sobrevendido, com reversão na vela atual
    if is_climactic and prev["close"] < prev["open"] and rsi < 20 and last["close"] > last["open"]:
        return "CALL"

    # PUT: Alta climática + RSI sobrecomprado, com reversão na vela atual
    if is_climactic and prev["close"] > prev["open"] and rsi > 80 and last["close"] < last["open"]:
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

    # c4 = df.iloc[-5] # A (Início do movimento)
    c3 = df.iloc[-4] # B (Suporte/Resistência a ser manipulada)
    # c2 = df.iloc[-3] # C (Respiro / Correção complexa)
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

def eval_regime_breakout(df: pd.DataFrame, donchian_len: int = 55, adx_threshold: float = 25.0,
                         atr_pct_min: float = 0.40, atr_pct_max: float = 0.90,
                         atr_lookback: int = 100) -> str:
    """H2 — Breakout de regime (Donchian longa + ADX + banda de ATR, M15/H1).

    Sinais de continuação de tendência em vez de reversão:
    - CALL: vela atual fecha acima do canal Donchian de `donchian_len` velas,
      com regime de tendência (ADX_14 >= threshold) e ATR no percentil
      [atr_pct_min, atr_pct_max] da janela (nem morto, nem louco).
    - PUT: simétrico para fechamento abaixo do canal inferior.

    Alvo/saída por ATR e time stop ficam a cargo do harness (mesma régua das
    rodadas P1), para comparabilidade. Função pura — não toca o executor.
    """
    if df is None or df.empty or len(df) < donchian_len:
        return "NONE"

    upper_col = f"DCU_{donchian_len}_{donchian_len}"
    lower_col = f"DCL_{donchian_len}_{donchian_len}"
    if upper_col not in df.columns or lower_col not in df.columns:
        return "NONE"

    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = last["close"]

    if "ADX_14" not in df.columns:
        return "NONE"
    adx = last["ADX_14"]
    if pd.isna(adx) or adx < adx_threshold:
        return "NONE"

    band = filter_atr_percentile(df, "CALL", percentile_min=atr_pct_min,
                                 percentile_max=atr_pct_max, lookback=atr_lookback)
    if not band:
        return "NONE"

    # Canal calculado ATÉ A VELA ANTERIOR (exclui a vela de sinal do próprio
    # cálculo) — usar o canal da vela atual seria trapaça: o high/low da
    # própria vela de rompimento alargaria o canal para sempre "contê-la".
    upper = prev[upper_col]
    lower = prev[lower_col]
    prev_prev_close = df.iloc[-3]["close"] if len(df) >= 3 else prev["close"]

    if pd.isna(upper) or pd.isna(lower):
        return "NONE"

    if close > upper > 0 and prev_prev_close <= upper:
        return "CALL"
    if close < lower and prev_prev_close >= lower:
        return "PUT"

    return "NONE"

def funding_state_at(funding_df, ts):
    """Último evento de funding conhecido em `ts` (sem lookahead).

    Retorna `{"rate": float, "rising": bool}` ou None se não há evento <= ts.
    Sem lookahead: só considera a série de funding já realizada naquele
    instante — eventos futuros não entram.
    """
    if funding_df is None or funding_df.empty or ts is None:
        return None
    try:
        pos = funding_df.index.searchsorted(ts, side="right") - 1
    except Exception:
        return None
    if pos < 0:
        return None
    rate = funding_df["fundingRate"].iloc[pos]
    prev_rate = funding_df["fundingRate"].iloc[pos - 1] if pos >= 1 else rate
    return {"rate": float(rate), "rising": bool(rate > prev_rate)}


def funding_direction_filter(df, direction, funding_state=None, neutral_eps: float = 1e-5) -> bool:
    """H3 — funding rate como filtro direcional (microestrutura, P3).

    - short (PUT): funding **positivo e crescendo** — posição long sobrecarregada;
    - long  (CALL): funding **negativo** ou **neutro decrescente**;
    - fail-open sem estado de funding (mesmo padrão dos demais filtros).

    Função pura — o estado causal é computado por `funding_state_at`, que fica
    a cargo de quem chama. Não toca o executor.
    """
    if not funding_state or "rate" not in funding_state:
        return True
    rate = float(funding_state["rate"])
    rising = bool(funding_state.get("rising", False))

    if direction == "PUT":
        return bool(rate > 0 and rising)
    if direction == "CALL":
        neutral = abs(rate) <= neutral_eps
        return bool(rate < 0 or (neutral and not rising))
    return True


@register_strategy("Regime Breakout")
def eval_regime_breakout_(df: pd.DataFrame) -> str:
    """Wrapper registrado no registry para o simulador."""
    return eval_regime_breakout(df)



# ─────────────────────────────────────────────────────────────────────────────
# Filtros de Qualidade de Sinal (Fase 1)
# ─────────────────────────────────────────────────────────────────────────────
