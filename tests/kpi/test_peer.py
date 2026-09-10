"""Unit tests for the peer percentile ranking engine."""
import numpy as np
import pandas as pd
import pytest

from src.analytics.peer import INVERTED_METRICS, compute_percent_rank


def test_compute_percent_rank_normal() -> None:
    series = pd.Series([10.0, 20.0, 30.0])
    pcts = compute_percent_rank(series, ascending=True)
    assert pcts.iloc[0] == pytest.approx(0.0)
    assert pcts.iloc[1] == pytest.approx(0.5)
    assert pcts.iloc[2] == pytest.approx(1.0)


def test_compute_percent_rank_single_value() -> None:
    series = pd.Series([15.0])
    pcts = compute_percent_rank(series, ascending=True)
    assert pcts.iloc[0] == 1.0


def test_compute_percent_rank_with_nan() -> None:
    series = pd.Series([10.0, np.nan, 30.0])
    pcts = compute_percent_rank(series, ascending=True)
    assert pcts.iloc[0] == pytest.approx(0.0)
    assert pd.isna(pcts.iloc[1])
    assert pcts.iloc[2] == pytest.approx(1.0)


def test_inverted_metric_is_de() -> None:
    assert "debt_to_equity" in INVERTED_METRICS
    assert "return_on_equity_pct" not in INVERTED_METRICS