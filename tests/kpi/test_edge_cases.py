"""Unit tests for edge case categorisation rules."""

from src.analytics.edge_cases import (
    DATA_SOURCE_ISSUE,
    FORMULA_DISCREPANCY,
    VERSION_DIFFERENCE,
    categorise_anomaly,
)


def test_categorise_scale_anomaly_as_data_source_issue() -> None:
    assert (
        categorise_anomaly(50.94, 0.52, "Information Technology", 5.0)
        == DATA_SOURCE_ISSUE
    )


def test_categorise_financials_anomaly_as_formula_discrepancy() -> None:
    assert categorise_anomaly(30.0, 45.0, "Financials", 5.0) == FORMULA_DISCREPANCY


def test_categorise_other_sector_anomaly_as_version_difference() -> None:
    assert categorise_anomaly(20.0, 30.0, "Healthcare", 5.0) == VERSION_DIFFERENCE
