"""Unit tests for the screener filter engine."""

import numpy as np
import pandas as pd

from src.screener.engine import apply_filters


def _universe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "company_id": ["TCS", "HDFCBANK", "RELIANCE"],
            "broad_sector": ["Information Technology", "Financials", "Energy"],
            "return_on_equity_pct": [50.0, 15.0, 12.0],
            "debt_to_equity": [0.1, 6.0, 0.8],
            "interest_coverage": [80.0, 2.0, np.inf],
            "icr_label": ["", "", "Debt Free"],
            "composite_quality_score": [75.0, 40.0, 60.0],
            "de_declining_flag": [True, False, True],
            "revenue_cagr_3yr": [15.0, 5.0, 12.0],
            "free_cash_flow_cr": [100.0, -50.0, 20.0],
        }
    )


def test_apply_filters_roe_min() -> None:
    df = apply_filters(_universe(), {"roe_min": 15.0})
    assert set(df["company_id"]) == {"TCS", "HDFCBANK"}


def test_apply_filters_de_max_skips_financials() -> None:
    df = apply_filters(_universe(), {"de_max": 1.0})
    assert "HDFCBANK" in set(df["company_id"])
    assert "RELIANCE" in set(df["company_id"])


def test_apply_filters_icr_min_passes_debt_free() -> None:
    df = apply_filters(_universe(), {"icr_min": 5.0})
    assert "RELIANCE" in set(df["company_id"])
    assert "HDFCBANK" not in set(df["company_id"])


def test_apply_filters_de_declining() -> None:
    df = apply_filters(_universe(), {"de_declining": True})
    assert set(df["company_id"]) == {"TCS", "RELIANCE"}
