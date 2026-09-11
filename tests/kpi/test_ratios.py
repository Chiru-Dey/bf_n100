"""Unit tests for profitability ratio formulas."""

import logging

import pytest
from _pytest.logging import LogCaptureFixture

from src.analytics.ratios import (
    ABOVE_BENCHMARK,
    BELOW_BENCHMARK,
    evaluate_roce,
    net_profit_margin,
    operating_profit_margin,
    return_on_assets,
    return_on_capital_employed,
    return_on_equity,
)


def test_net_profit_margin_normal() -> None:
    assert net_profit_margin(20.0, 100.0) == pytest.approx(20.0)


def test_net_profit_margin_zero_sales_returns_none() -> None:
    assert net_profit_margin(20.0, 0.0) is None


def test_operating_profit_margin_cross_check_mismatch_logs_warning(
    caplog: LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        computed = operating_profit_margin(
            50.0,
            100.0,
            source_opm_pct=45.0,
            tolerance_pct=1.0,
            company_id="TCS",
            year="2023-03",
        )
    assert computed == pytest.approx(50.0)
    assert len(caplog.records) == 1
    assert "OPM cross-check divergence" in caplog.records[0].message


def test_return_on_equity_normal() -> None:
    assert return_on_equity(100.0, 200.0, 300.0) == pytest.approx(20.0)


def test_return_on_equity_negative_equity_returns_none() -> None:
    assert return_on_equity(100.0, -50.0, -20.0) is None


def test_return_on_capital_employed_normal() -> None:
    computed = return_on_capital_employed(120.0, 20.0, 300.0, 200.0, 100.0)
    assert computed == pytest.approx(100.0 / 600.0 * 100.0)


def test_return_on_assets_zero_total_assets_returns_none() -> None:
    assert return_on_assets(50.0, 0.0) is None


def test_evaluate_roce_financials_uses_sector_relative_benchmark() -> None:
    assert evaluate_roce(13.0, "Financials", 12.0) == ABOVE_BENCHMARK
    assert evaluate_roce(14.0, "Information Technology", 12.0) == BELOW_BENCHMARK
