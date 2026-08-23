import pandas as pd
import pytest

from app.application.services.technical_analysis import (
    apply_indicators,
    filter_session_utc,
    filter_atr_percentile,
    filter_regime_adx,
)


def _build_df(n=220, seed_amplitude=1.0, freq="15min"):
    idx = pd.date_range("2026-01-01", periods=n, freq=freq, tz="UTC")
    closes = [100.0 + (i % 7) * seed_amplitude - (3 * seed_amplitude) for i in range(n)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + 1.0 for c in closes],
            "low": [c - 1.0 for c in closes],
            "close": closes,
            "volume": [100.0] * n,
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# filter_session_utc
# ---------------------------------------------------------------------------

def test_filter_session_utc_accepts_inside_window():
    idx = pd.date_range("2026-01-01 13:00", periods=1, freq="15min", tz="UTC")
    df = pd.DataFrame({"close": [100.0]}, index=idx)
    assert filter_session_utc(df, "CALL", sessions=[(12, 17)]) is True


def test_filter_session_utc_rejects_outside_window():
    idx = pd.date_range("2026-01-01 03:00", periods=1, freq="15min", tz="UTC")
    df = pd.DataFrame({"close": [100.0]}, index=idx)
    assert filter_session_utc(df, "CALL", sessions=[(12, 17)]) is False


def test_filter_session_utc_passes_open_without_datetime_index():
    df = pd.DataFrame({"close": [100.0, 101.0]})
    assert filter_session_utc(df, "CALL", sessions=[(12, 17)]) is True


def test_filter_session_utc_boundary_is_inclusive_start_exclusive_end():
    idx_start = pd.date_range("2026-01-01 12:00", periods=1, freq="15min", tz="UTC")
    idx_end = pd.date_range("2026-01-01 17:00", periods=1, freq="15min", tz="UTC")
    assert filter_session_utc(pd.DataFrame({"close": [1]}, index=idx_start), "CALL", [(12, 17)]) is True
    assert filter_session_utc(pd.DataFrame({"close": [1]}, index=idx_end), "CALL", [(12, 17)]) is False


# ---------------------------------------------------------------------------
# filter_atr_percentile
# ---------------------------------------------------------------------------

def test_filter_atr_percentile_passes_when_column_missing():
    df = _build_df(n=10)
    assert filter_atr_percentile(df, "CALL") is True


def test_filter_atr_percentile_rejects_extreme_low_atr():
    # ATR quase constante e baixo -> última leitura fica no percentil baixo
    n = 150
    df = _build_df(n=n)
    df["ATRr_14"] = [1.0] * (n - 1) + [0.01]
    assert filter_atr_percentile(df, "CALL", percentile_min=0.40, percentile_max=0.90) is False


def test_filter_atr_percentile_accepts_mid_range_atr():
    # janela padrão = últimos 100 valores; dentro dela, metade abaixo (1.0),
    # metade acima (3.0), e a leitura atual (2.0) fica exatamente no meio
    # -> percentil ~0.50, dentro de [0.30, 0.70].
    atr_series = [1.0] * 100 + [3.0] * 49 + [2.0]
    df = _build_df(n=len(atr_series))
    df["ATRr_14"] = atr_series
    assert filter_atr_percentile(df, "CALL", percentile_min=0.30, percentile_max=0.70) is True


# ---------------------------------------------------------------------------
# filter_regime_adx
# ---------------------------------------------------------------------------

def test_filter_regime_adx_passes_when_column_missing():
    df = _build_df(n=10)
    assert filter_regime_adx(df, "CALL") is True


def test_filter_regime_adx_rejects_below_threshold():
    df = _build_df(n=10)
    df["ADX_14"] = [10.0] * 10
    assert filter_regime_adx(df, "CALL", threshold=25.0) is False


def test_filter_regime_adx_accepts_above_threshold():
    df = _build_df(n=10)
    df["ADX_14"] = [30.0] * 10
    assert filter_regime_adx(df, "CALL", threshold=25.0) is True


# ---------------------------------------------------------------------------
# integração: apply_indicators calcula ADX_14
# ---------------------------------------------------------------------------

def test_apply_indicators_computes_adx_column():
    df = _build_df(n=60)
    df_ind = apply_indicators(df)
    assert "ADX_14" in df_ind.columns
