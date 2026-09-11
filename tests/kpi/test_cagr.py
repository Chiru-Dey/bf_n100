"""Unit tests for the CAGR engine edge-case handlers."""

import pandas as pd
import pytest

from src.analytics.cagr import (
    BOTH_NEGATIVE,
    DECLINE_TO_LOSS,
    INSUFFICIENT,
    NO_FLAG,
    TURNAROUND,
    ZERO_BASE,
    cagr_ending_at,
    cagr_from_series,
    compute_cagr,
    compute_cagr_ratios,
)


def _series() -> pd.Series:
    return pd.Series(
        [100.0, 110.0, 121.0, 133.1, 146.41, 161.051],
        index=["2019-03", "2020-03", "2021-03", "2022-03", "2023-03", "2024-03"],
    )


def test_cagr_normal() -> None:
    value, flag = compute_cagr(100.0, 161.051, 5)
    assert value == pytest.approx(10.0, abs=0.01)
    assert flag == NO_FLAG


def test_cagr_turnaround_flag() -> None:
    assert compute_cagr(-100.0, 200.0, 5) == (None, TURNAROUND)


def test_cagr_decline_to_loss() -> None:
    assert compute_cagr(100.0, -50.0, 5) == (None, DECLINE_TO_LOSS)


def test_cagr_both_negative() -> None:
    assert compute_cagr(-100.0, -50.0, 5) == (None, BOTH_NEGATIVE)


def test_cagr_zero_base() -> None:
    assert compute_cagr(0.0, 100.0, 5) == (None, ZERO_BASE)


def test_cagr_insufficient_history() -> None:
    assert cagr_from_series(_series().head(3), 5) == (None, INSUFFICIENT)


def test_cagr_zero_end_computes_full_decline() -> None:
    value, flag = compute_cagr(100.0, 0.0, 5)
    assert value == pytest.approx(-100.0)
    assert flag == NO_FLAG


def test_cagr_ending_at_uses_calendar_window() -> None:
    value, flag = cagr_ending_at(_series(), "2024-03", 3)
    assert value == pytest.approx(10.0, abs=0.01)
    assert flag == NO_FLAG


def test_cagr_from_series_latest_window() -> None:
    value, flag = cagr_from_series(_series(), 5)
    assert value == pytest.approx(10.0, abs=0.01)
    assert flag == NO_FLAG


def test_compute_cagr_ratios_columns_and_flags() -> None:
    frame = pd.DataFrame(
        {
            "company_id": ["TCS"] * 6,
            "year": _series().index,
            "sales": _series().to_numpy(),
            "net_profit": _series().to_numpy(),
            "eps": _series().to_numpy(),
        }
    )
    result = compute_cagr_ratios(frame)
    latest = result[result["year"] == "2024-03"].iloc[0]
    early = result[result["year"] == "2021-03"].iloc[0]
    assert latest["revenue_cagr_5yr"] == pytest.approx(10.0, abs=0.01)
    assert latest["pat_cagr_5yr_flag"] == NO_FLAG
    assert latest["eps_cagr_3yr_flag"] == NO_FLAG
    assert pd.isna(early["revenue_cagr_5yr"])
    assert early["revenue_cagr_5yr_flag"] == INSUFFICIENT
