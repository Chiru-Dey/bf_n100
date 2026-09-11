"""Unit tests for cash flow KPIs and capital allocation classification."""

import pandas as pd
import pytest

from src.analytics.cashflow_kpis import (
    ACCRUAL_RISK,
    ASSET_LIGHT,
    CAPITAL_INTENSIVE,
    DISTRESS_SIGNAL,
    GROWTH_FUNDED_BY_DEBT,
    HIGH_QUALITY,
    INSUFFICIENT_DATA,
    MODERATE,
    NO_DATA,
    REINVESTOR,
    SHAREHOLDER_RETURNS,
    capex_intensity_pct,
    capex_label,
    cfo_pat_ratio,
    cfo_quality_label,
    cfo_quality_score,
    classify_capital_allocation,
    compute_cashflow_kpis,
    fcf_conversion_pct,
    free_cash_flow,
)


def _frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    cashflow = pd.DataFrame(
        {
            "company_id": ["TCS"] * 2,
            "year": ["2023-03", "2024-03"],
            "operating_activity": [100.0, -50.0],
            "investing_activity": [-80.0, -60.0],
            "financing_activity": [-40.0, 70.0],
        }
    )
    profit_and_loss = pd.DataFrame(
        {
            "company_id": ["TCS"] * 2,
            "year": ["2023-03", "2024-03"],
            "sales": [500.0, 500.0],
            "net_profit": [50.0, 0.0],
            "operating_profit": [90.0, 0.0],
        }
    )
    return cashflow, profit_and_loss


def test_free_cash_flow_sums_operating_and_investing() -> None:
    assert free_cash_flow(100.0, -80.0) == pytest.approx(20.0)


def test_cfo_pat_ratio_zero_pat_returns_none() -> None:
    assert cfo_pat_ratio(100.0, 0.0) is None


def test_cfo_quality_score_five_year_mean() -> None:
    assert cfo_quality_score([1.2, 1.3, 1.1, 1.4, 1.0]) == pytest.approx(1.2)


def test_cfo_quality_score_current_zero_pat_returns_none() -> None:
    assert cfo_quality_score([1.2, 1.3, 1.1, 1.4, None]) is None


def test_cfo_quality_labels() -> None:
    assert cfo_quality_label(1.2) == HIGH_QUALITY
    assert cfo_quality_label(0.7) == MODERATE
    assert cfo_quality_label(0.3) == ACCRUAL_RISK


def test_capex_intensity_and_labels() -> None:
    assert capex_intensity_pct(-80.0, 500.0) == pytest.approx(16.0)
    assert capex_label(2.0) == ASSET_LIGHT
    assert capex_label(5.0) == MODERATE
    assert capex_label(16.0) == CAPITAL_INTENSIVE


def test_fcf_conversion_zero_operating_profit_returns_none() -> None:
    assert fcf_conversion_pct(20.0, 0.0) is None


def test_classify_reinvestor_vs_shareholder_returns() -> None:
    assert classify_capital_allocation(100.0, -80.0, -40.0, 0.8) == REINVESTOR
    assert classify_capital_allocation(100.0, -80.0, -40.0, 1.5) == SHAREHOLDER_RETURNS


def test_classify_distress_signal() -> None:
    assert classify_capital_allocation(-50.0, 60.0, 70.0) == DISTRESS_SIGNAL


def test_classify_missing_insufficient() -> None:
    assert classify_capital_allocation(None, -80.0, -40.0) == INSUFFICIENT_DATA


def test_compute_cashflow_kpis_patterns_and_signs() -> None:
    cashflow, profit_and_loss = _frames()
    result = compute_cashflow_kpis(cashflow, profit_and_loss)
    first = result[result["year"] == "2023-03"].iloc[0]
    second = result[result["year"] == "2024-03"].iloc[0]
    assert first["free_cash_flow_cr"] == pytest.approx(20.0)
    assert first["capex_cr"] == pytest.approx(80.0)
    assert first["fcf_conversion_pct"] == pytest.approx(20.0 / 90.0 * 100.0)
    assert first["cfo_sign"] == "+"
    assert first["pattern_label"] == SHAREHOLDER_RETURNS
    assert second["pattern_label"] == GROWTH_FUNDED_BY_DEBT
    assert second["cfo_quality_label"] == NO_DATA
