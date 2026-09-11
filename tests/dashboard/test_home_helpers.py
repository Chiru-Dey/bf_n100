"""Unit tests for Home screen helper functions."""

import pandas as pd

from src.dashboard.utils.home_helpers import (
    build_sector_donut_data,
    compute_market_health,
    get_top_companies,
)


def _sample_home_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "company_id": ["A", "B", "C", "D"],
            "broad_sector": ["IT", "IT", "FMCG", "Banks"],
            "composite_quality_score": [80.0, 40.0, 60.0, 30.0],
        }
    )


def test_compute_market_health() -> None:
    df = _sample_home_df()
    above, below = compute_market_health(df)
    assert above == 2
    assert below == 2


def test_get_top_companies() -> None:
    df = _sample_home_df()
    top = get_top_companies(df, n=2)
    assert list(top["company_id"]) == ["A", "C"]


def test_build_sector_donut_data() -> None:
    df = _sample_home_df()
    donut = build_sector_donut_data(df)
    assert "IT" in donut["broad_sector"].values
    assert donut[donut["broad_sector"] == "IT"]["count"].iloc[0] == 2
