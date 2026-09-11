"""Unit tests for leverage and efficiency ratio formulas."""

import pytest

from src.analytics.ratios import (
    DEBT_FREE_LABEL,
    asset_turnover,
    debt_to_equity,
    high_leverage_flag,
    icr_label,
    icr_warning_flag,
    interest_coverage,
    net_debt,
)


def test_debt_to_equity_normal() -> None:
    assert debt_to_equity(200.0, 100.0, 300.0) == pytest.approx(0.5)


def test_debt_to_equity_debt_free_returns_zero() -> None:
    assert debt_to_equity(0.0, 100.0, 300.0) == 0.0


def test_debt_to_equity_negative_equity_returns_none() -> None:
    assert debt_to_equity(100.0, -50.0, -20.0) is None


def test_high_leverage_flag_non_financials() -> None:
    assert high_leverage_flag(6.0, "Information Technology") is True


def test_high_leverage_flag_financials_suppressed() -> None:
    assert high_leverage_flag(6.0, "Financials") is False


def test_interest_coverage_zero_interest_returns_none() -> None:
    assert interest_coverage(500.0, 50.0, 0.0) is None


def test_icr_label_debt_free() -> None:
    assert icr_label(0.0) == DEBT_FREE_LABEL
    assert icr_label(120.0) == ""


def test_icr_warning_flag_below_threshold() -> None:
    assert icr_warning_flag(1.2) is True
    assert icr_warning_flag(3.0) is False


def test_net_debt_uses_investments_as_liquid_proxy() -> None:
    assert net_debt(500.0, 200.0) == pytest.approx(300.0)
    assert net_debt(500.0, None) == pytest.approx(500.0)


def test_asset_turnover_zero_assets_returns_none() -> None:
    assert asset_turnover(1000.0, 0.0) is None
    assert asset_turnover(1000.0, 500.0) == pytest.approx(2.0)
