import pandas as pd

from app.application.services.technical_analysis import (
    funding_state_at,
    funding_direction_filter,
)


def _funding_df():
    idx = pd.to_datetime(
        ["2026-01-01 00:00", "2026-01-01 08:00", "2026-01-01 16:00", "2026-01-02 00:00"],
        utc=True,
    )
    return pd.DataFrame({"fundingRate": [0.0001, 0.0002, -0.0001, -0.0003]}, index=idx)


# ---------------------------------------------------------------------------
# funding_state_at — sem lookahead
# ---------------------------------------------------------------------------

def test_funding_state_at_returns_none_without_prior_event():
    df = _funding_df()
    ts = pd.Timestamp("2025-12-31 23:00", tz="UTC")
    assert funding_state_at(df, ts) is None


def test_funding_state_at_uses_last_known_event_not_future_ones():
    df = _funding_df()
    # entre o 2º e o 3º evento -> deve pegar o 2º (0.0002), rising vs 1º (0.0001)
    ts = pd.Timestamp("2026-01-01 10:00", tz="UTC")
    state = funding_state_at(df, ts)
    assert state == {"rate": 0.0002, "rising": True}


def test_funding_state_at_detects_falling_rate():
    df = _funding_df()
    # após o 3º evento (-0.0001), que caiu em relação ao 2º (0.0002)
    ts = pd.Timestamp("2026-01-01 20:00", tz="UTC")
    state = funding_state_at(df, ts)
    assert state["rate"] == -0.0001
    assert state["rising"] is False


def test_funding_state_at_handles_empty_or_none_df():
    assert funding_state_at(None, pd.Timestamp.now(tz="UTC")) is None
    assert funding_state_at(pd.DataFrame(), pd.Timestamp.now(tz="UTC")) is None


# ---------------------------------------------------------------------------
# funding_direction_filter
# ---------------------------------------------------------------------------

def test_funding_direction_filter_passes_open_without_state():
    assert funding_direction_filter(None, "CALL", funding_state=None) is True
    assert funding_direction_filter(None, "PUT", funding_state=None) is True


def test_funding_direction_filter_allows_short_on_positive_rising_funding():
    state = {"rate": 0.0003, "rising": True}
    assert funding_direction_filter(None, "PUT", funding_state=state) is True


def test_funding_direction_filter_rejects_short_on_positive_falling_funding():
    state = {"rate": 0.0003, "rising": False}
    assert funding_direction_filter(None, "PUT", funding_state=state) is False


def test_funding_direction_filter_rejects_short_on_negative_funding():
    state = {"rate": -0.0001, "rising": True}
    assert funding_direction_filter(None, "PUT", funding_state=state) is False


def test_funding_direction_filter_allows_long_on_negative_funding():
    state = {"rate": -0.0002, "rising": False}
    assert funding_direction_filter(None, "CALL", funding_state=state) is True


def test_funding_direction_filter_allows_long_on_neutral_falling_funding():
    state = {"rate": 0.0, "rising": False}
    assert funding_direction_filter(None, "CALL", funding_state=state) is True


def test_funding_direction_filter_rejects_long_on_positive_funding():
    state = {"rate": 0.0003, "rising": True}
    assert funding_direction_filter(None, "CALL", funding_state=state) is False


def test_funding_direction_filter_passes_unknown_direction():
    state = {"rate": 0.0003, "rising": True}
    assert funding_direction_filter(None, "NONE", funding_state=state) is True
