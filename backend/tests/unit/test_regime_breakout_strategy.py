import pandas as pd

from app.application.services.technical_analysis import eval_regime_breakout


def _base_df(n=120, freq="15min"):
    idx = pd.date_range("2026-01-01", periods=n, freq=freq, tz="UTC")
    closes = [100.0 + (i % 5) * 0.1 for i in range(n)]
    # ATR alternando 1.0/3.0: dentro da janela de lookback (100), a leitura
    # mais recente cai perto do percentil 50 — passa a banda [0.40, 0.90]
    # sem precisar calibrar um cenário à parte em cada teste.
    atr = [1.0 if i % 2 == 0 else 3.0 for i in range(n)]

    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c + 0.5 for c in closes],
            "low": [c - 0.5 for c in closes],
            "close": closes,
            "volume": [100.0] * n,
            "ADX_14": [30.0] * n,
            "ATRr_14": atr,
            "DCU_55_55": [105.0] * n,
            "DCL_55_55": [95.0] * n,
        },
        index=idx,
    )
    return df


def test_eval_regime_breakout_returns_none_when_insufficient_data():
    df = _base_df(n=20)
    assert eval_regime_breakout(df) == "NONE"


def test_eval_regime_breakout_returns_none_when_donchian_missing():
    df = _base_df().drop(columns=["DCU_55_55", "DCL_55_55"])
    assert eval_regime_breakout(df) == "NONE"


def test_eval_regime_breakout_returns_none_when_adx_missing():
    df = _base_df().drop(columns=["ADX_14"])
    assert eval_regime_breakout(df) == "NONE"


def test_eval_regime_breakout_emits_call_on_fresh_upper_breakout():
    df = _base_df()
    # vela -3 e -2 ainda dentro do canal (< 105); vela atual rompe para cima
    df.iloc[-3, df.columns.get_loc("close")] = 104.0
    df.iloc[-2, df.columns.get_loc("close")] = 104.5
    df.iloc[-1, df.columns.get_loc("close")] = 106.0
    assert eval_regime_breakout(df) == "CALL"


def test_eval_regime_breakout_emits_put_on_fresh_lower_breakout():
    df = _base_df()
    df.iloc[-3, df.columns.get_loc("close")] = 96.0
    df.iloc[-2, df.columns.get_loc("close")] = 95.5
    df.iloc[-1, df.columns.get_loc("close")] = 94.0
    assert eval_regime_breakout(df) == "PUT"


def test_eval_regime_breakout_rejects_below_adx_threshold():
    df = _base_df()
    df.iloc[-3, df.columns.get_loc("close")] = 104.0
    df.iloc[-2, df.columns.get_loc("close")] = 104.5
    df.iloc[-1, df.columns.get_loc("close")] = 106.0
    df["ADX_14"] = [20.0] * len(df)
    assert eval_regime_breakout(df) == "NONE"


def test_eval_regime_breakout_rejects_atr_outside_band():
    df = _base_df()
    df.iloc[-3, df.columns.get_loc("close")] = 104.0
    df.iloc[-2, df.columns.get_loc("close")] = 104.5
    df.iloc[-1, df.columns.get_loc("close")] = 106.0
    df["ATRr_14"] = [1.0] * (len(df) - 1) + [0.01]
    assert eval_regime_breakout(df) == "NONE"


def test_eval_regime_breakout_rejects_stale_breakout():
    # já estava rompido duas velas atrás — não é um breakout fresco
    df = _base_df()
    df.iloc[-3, df.columns.get_loc("close")] = 106.0
    df.iloc[-2, df.columns.get_loc("close")] = 106.5
    df.iloc[-1, df.columns.get_loc("close")] = 107.0
    assert eval_regime_breakout(df) == "NONE"
