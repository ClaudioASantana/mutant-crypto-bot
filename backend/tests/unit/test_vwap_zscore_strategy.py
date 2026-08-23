import pandas as pd
import pytest

from app.application.services.technical_analysis import apply_indicators, eval_vwap_zscore


def _build_df(closes, volumes=None):
    if volumes is None:
        volumes = [100.0] * len(closes)
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": volumes,
        },
        index=idx,
    )


def test_eval_vwap_zscore_returns_none_with_insufficient_data():
    df = _build_df([100 + i for i in range(20)])
    df = apply_indicators(df)
    assert eval_vwap_zscore(df) == "NONE"


def test_eval_vwap_zscore_emits_call_on_deep_discount_reversion_setup():
    closes = [100.0] * 28 + [95.0, 93.0, 92.0, 94.0]
    df = apply_indicators(_build_df(closes))
    assert eval_vwap_zscore(df) == "CALL"


def test_eval_vwap_zscore_emits_put_on_stretched_premium_reversion_setup():
    closes = [100.0] * 28 + [105.0, 107.0, 108.0, 106.0]
    df = apply_indicators(_build_df(closes))
    assert eval_vwap_zscore(df) == "PUT"


def test_eval_vwap_zscore_respects_trend_filter_for_calls():
    closes = [140.0 - (i * 0.1) for i in range(205)]
    closes[-4:] = [125.0, 122.0, 120.0, 123.0]
    df = apply_indicators(_build_df(closes))
    assert eval_vwap_zscore(df) == "NONE"


def test_eval_vwap_zscore_no_signal_when_move_is_not_extreme_enough():
    # Baseline com ruído realista (amplitude ~0.7), para que um recuo
    # modesto de ~0.5 não represente múltiplos desvios-padrão.
    base = [
        100.0, 100.6, 99.4, 100.4, 99.2, 100.8, 99.0, 100.9, 98.9, 101.0,
        99.1, 100.7, 99.3, 100.5, 99.0, 100.8, 98.8, 100.9, 99.2, 100.6,
        99.1, 100.5, 99.3, 100.4, 99.0, 100.7, 99.2, 100.6, 99.1, 100.5,
    ]
    tail = [99.6, 99.4, 99.5, 99.7]
    df = apply_indicators(_build_df(base + tail))
    assert eval_vwap_zscore(df) == "NONE"
