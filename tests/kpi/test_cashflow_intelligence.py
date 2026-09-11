"""Unit tests for cash flow intelligence rules."""

import pandas as pd
import pytest

from src.analytics.cashflow_intelligence import (
    deleveraging_flag,
    distress_flag,
    evaluate_company,
    fcf_cagr_5yr,
)


def _hist(**overrides) -> pd.DataFrame:
    base = {
        "company_id": ["TCS"] * 6,
        "year": [
            "2019-03",
            "2020-03",
            "2021-03",
            "2022-03",
            "2023-03",
            "2024-03",
        ],
        "cfo": [150.0, 165.0, 180.0, 195.0, 210.0, 225.0],
        "cfi": [-80.0, -85.0, -90.0, -95.0, -100.0, -105.0],
        "cff": [-40.0, -40.0, -40.0, -40.0, -40.0, -40.0],
        "fcf": [70.0, 80.0, 90.0, 100.0, 110.0, 120.0],
        "sales": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0, 1500.0],
        "net_profit": [100.0, 110.0, 120.0, 130.0, 140.0, 150.0],
        "operating_profit": [200.0, 220.0, 240.0, 260.0, 280.0, 300.0],
        "borrowings": [500.0, 480.0, 460.0, 440.0, 420.0, 400.0],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_distress_flag_cfo_negative_cff_positive() -> None:
    hist = _hist(
        cfo=[-10.0, -20.0, -30.0, -40.0, -50.0, -60.0],
        cff=[10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
    )
    assert distress_flag(hist) is True


def test_distress_flag_false_when_cfo_positive() -> None:
    assert distress_flag(_hist()) is False


def test_deleveraging_flag_cff_negative_borrowings_down() -> None:
    assert deleveraging_flag(_hist()) is True


def test_deleveraging_flag_false_when_cff_positive() -> None:
    assert deleveraging_flag(_hist(cff=[40.0] * 6)) is False


def test_cfo_quality_high_quality() -> None:
    record = evaluate_company("TCS", "Information Technology", _hist())
    assert record["cfo_quality_score"] == pytest.approx(1.5)
    assert record["cfo_quality_label"] == "High Quality"


def test_capex_intensity_and_label() -> None:
    record = evaluate_company("TCS", "Information Technology", _hist())
    assert record["capex_intensity_pct"] == pytest.approx(7.0)
    assert record["capex_label"] == "Moderate"


def test_fcf_cagr_5yr_computable() -> None:
    assert fcf_cagr_5yr(_hist()) == pytest.approx(11.38, abs=0.05)


def test_fcf_cagr_5yr_insufficient_history() -> None:
    assert fcf_cagr_5yr(_hist().head(3)) is None


def test_evaluate_company_conversion_and_pattern() -> None:
    record = evaluate_company("TCS", "Information Technology", _hist())
    assert record["fcf_conversion_pct"] == pytest.approx(40.0)
    assert record["capital_allocation_label"] == "Shareholder Returns"