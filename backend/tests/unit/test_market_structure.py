import pandas as pd
import pytest

from backend.app.application.services.technical_analysis import (
    _detect_swing_high,
    _detect_swing_low,
    _get_market_structure,
    _get_market_trend,
    eval_smc
)

@pytest.fixture
def sample_df_swing_high():
    data = {
        "high": [10, 11, 15, 12, 11, 10, 14],
        "low":  [8, 9, 10, 10, 9, 8, 9],
        "open": [9, 10, 11, 11, 10, 9, 10],
        "close":[10, 11, 12, 10, 10, 9, 13]
    }
    return pd.DataFrame(data)

def test_detect_swing_high_is_true(sample_df_swing_high):
    """ Testa a detecção de um Swing High válido. """
    assert _detect_swing_high(sample_df_swing_high, 2) is True

def test_detect_swing_high_is_false(sample_df_swing_high):
    """ Testa um ponto que não é um Swing High. """
    assert _detect_swing_high(sample_df_swing_high, 3) is False
    assert _detect_swing_high(sample_df_swing_high, 6) is False

def test_detect_swing_high_at_edges(sample_df_swing_high):
    """ Testa que a detecção falha nas bordas do dataframe. """
    assert _detect_swing_high(sample_df_swing_high, 0) is False
    assert _detect_swing_high(sample_df_swing_high, 1) is False
    assert _detect_swing_high(sample_df_swing_high, len(sample_df_swing_high) - 1) is False

@pytest.fixture
def sample_df_swing_low():
    data = {
        "high": [15, 14, 10, 11, 12, 13, 11],
        "low":  [10, 9, 5, 6, 7, 8, 6],
        "open": [12, 11, 9, 10, 11, 12, 10],
        "close":[10, 9, 6, 10, 11, 12, 7]
    }
    return pd.DataFrame(data)

def test_detect_swing_low_is_true(sample_df_swing_low):
    """ Testa a detecção de um Swing Low válido. """
    assert _detect_swing_low(sample_df_swing_low, 2) is True

def test_detect_swing_low_is_false(sample_df_swing_low):
    """ Testa um ponto que não é um Swing Low. """
    assert _detect_swing_low(sample_df_swing_low, 3) is False
    assert _detect_swing_low(sample_df_swing_low, 6) is False

def test_detect_swing_low_at_edges(sample_df_swing_low):
    """ Testa que a detecção falha nas bordas do dataframe. """
    assert _detect_swing_low(sample_df_swing_low, 0) is False
    assert _detect_swing_low(sample_df_swing_low, 1) is False
    assert _detect_swing_low(sample_df_swing_low, len(sample_df_swing_low) - 1) is False

@pytest.fixture
def sample_df_market_structure():
    # Dados que criam 2 HH (índices 2 e 6) e 2 LL (índices 0 e 4)
    data = {
        "high": [10, 9, 15, 12, 8, 9, 16],
        "low":  [5, 6, 7, 6, 3, 4, 5],
        "open": [7, 8, 10, 11, 5, 6, 10],
        "close":[8, 7, 12, 8, 4, 7, 13]
    }
    return pd.DataFrame(data)

def test_get_market_structure(sample_df_market_structure):
    """ Testa a extração da estrutura de mercado. """
    structure = _get_market_structure(sample_df_market_structure, num_candles=7)

    # Com os dados de amostra, apenas o swing high no índice 2 é confirmado
    # por 2 candles à esquerda e 2 à direita (índices 0, 1 e 3, 4).
    # O swing low no índice 0 não é detectado porque não há 2 candles à esquerda.
    # O swing high no índice 6 não é detectado porque não há 2 candles à direita.
    # O swing low no índice 4 é detectado pois está entre 2, 3 e 5, 6.

    assert len(structure) >= 1
    # Verifica se o high no índice 2 foi detectado
    assert any(s["index"] == 2 and s["type"] == "high" for s in structure)

def test_get_market_trend_bullish():
    """ Testa a detecção de tendência de alta. """
    structure = [
        {"index": 0, "type": "low", "price": 100},
        {"index": 2, "type": "high", "price": 110},
        {"index": 4, "type": "low", "price": 105},
        {"index": 6, "type": "high", "price": 115}
    ]
    assert _get_market_trend(structure) == "BULLISH"

def test_get_market_trend_bearish():
    """ Testa a detecção de tendência de baixa. """
    structure = [
        {"index": 0, "type": "high", "price": 110},
        {"index": 2, "type": "low", "price": 100},
        {"index": 4, "type": "high", "price": 105},
        {"index": 6, "type": "low", "price": 95}
    ]
    assert _get_market_trend(structure) == "BEARISH"

def test_get_market_trend_range():
    """ Testa a detecção de tendência lateral. """
    structure = [
        {"index": 0, "type": "low", "price": 100},
        {"index": 2, "type": "high", "price": 110},
        {"index": 4, "type": "low", "price": 102},
        {"index": 6, "type": "high", "price": 108}
    ]
    assert _get_market_trend(structure) == "RANGE"

def test_get_market_trend_insufficient_data():
    """ Testa com dados insuficientes. """
    structure = [{"index": 0, "type": "low", "price": 100}]
    assert _get_market_trend(structure) == "RANGE"

    structure = []
    assert _get_market_trend(structure) == "RANGE"
