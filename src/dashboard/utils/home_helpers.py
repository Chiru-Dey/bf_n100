"""Helper functions for the Home screen (testable without Streamlit)."""

from __future__ import annotations

import pandas as pd


def compute_market_health(df: pd.DataFrame) -> tuple[int, int]:
    """Return counts of companies above and below the composite score benchmark of 50."""
    above = int((df["composite_quality_score"] >= 50).sum())
    below = len(df) - above
    return above, below


def get_top_companies(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Return the top N companies sorted by composite quality score."""
    return df.sort_values("composite_quality_score", ascending=False).head(n)[
        ["company_id", "broad_sector", "composite_quality_score"]
    ]


def build_sector_donut_data(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of sector counts for the Plotly donut chart."""
    return (
        df["broad_sector"]
        .value_counts()
        .reset_index(name="count")
        .rename(columns={"index": "broad_sector"})
    )
