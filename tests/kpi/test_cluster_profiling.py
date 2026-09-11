"""Unit tests for cluster profiling and outlier detection."""

import numpy as np
import pandas as pd

from src.analytics.cluster_profiling import detect_outliers, portfolio_statistics


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    size = 60
    return pd.DataFrame(
        {
            "company_id": [f"C{i:02d}" for i in range(size)],
            "broad_sector": ["Information Technology", "Financials", "Energy"] * 20,
            "return_on_equity_pct": rng.normal(20, 5, size),
            "return_on_capital_employed_pct": rng.normal(25, 6, size),
            "net_profit_margin_pct": rng.normal(12, 4, size),
            "debt_to_equity": rng.normal(1, 0.5, size),
            "revenue_cagr_5yr": rng.normal(10, 3, size),
            "fcf_cagr_5yr": rng.normal(8, 4, size),
            "operating_profit_margin_pct": rng.normal(20, 6, size),
        }
    )


def test_detect_outliers_flags_extreme_z_score() -> None:
    frame = _frame()
    frame.loc[0, "return_on_equity_pct"] = 100.0
    outliers = detect_outliers(frame)
    assert len(outliers) >= 1
    assert outliers.iloc[0]["company_id"] == "C00"
    assert outliers.iloc[0]["metric"] == "return_on_equity_pct"


def test_portfolio_statistics_columns() -> None:
    frame = _frame()
    stats = portfolio_statistics(frame)
    assert list(stats.columns) == [
        "Metric",
        "P10",
        "P25",
        "P50",
        "P75",
        "P90",
        "Mean",
        "Std",
    ]
    assert len(stats) == 5
