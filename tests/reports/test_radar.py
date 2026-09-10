"""Unit tests for radar chart normalisation helpers."""

import pandas as pd

from src.reports.radar import add_fcf_margin, min_max_normalise


def test_min_max_normalise() -> None:
    series = pd.Series([10.0, 20.0, 30.0])
    scaled = min_max_normalise(series)
    assert scaled.iloc[0] == 0.0
    assert scaled.iloc[2] == 1.0


def test_min_max_normalise_inverted() -> None:
    series = pd.Series([1.0, 2.0, 3.0])
    scaled = min_max_normalise(series, inverted=True)
    assert scaled.iloc[0] == 1.0
    assert scaled.iloc[2] == 0.0


def test_min_max_normalise_degenerate() -> None:
    series = pd.Series([5.0, 5.0, 5.0])
    assert min_max_normalise(series).iloc[0] == 0.5


def test_add_fcf_margin() -> None:
    frame = pd.DataFrame(
        {"free_cash_flow_cr": [100.0, -50.0], "sales": [1000.0, 500.0]}
    )
    enriched = add_fcf_margin(frame)
    assert enriched["fcf_margin_pct"].iloc[0] == 10.0
    assert enriched["fcf_margin_pct"].iloc[1] == -10.0