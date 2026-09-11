"""Unit tests for the capital allocation YoY migration logic."""

import pandas as pd

from src.analytics.capital_allocation_report import (
    compute_pattern_changes,
    latest_year_frame,
)


def test_compute_pattern_changes_detects_migration() -> None:
    frame = pd.DataFrame(
        {
            "company_id": ["A", "A", "B", "B"],
            "year": ["2023-03", "2024-03", "2023-03", "2024-03"],
            "pattern_label": [
                "Reinvestor",
                "Distress Signal",
                "Reinvestor",
                "Reinvestor",
            ],
        }
    )
    changes = compute_pattern_changes(frame)
    assert len(changes) == 1
    assert changes.iloc[0]["company_id"] == "A"
    assert changes.iloc[0]["previous_pattern"] == "Reinvestor"
    assert changes.iloc[0]["current_pattern"] == "Distress Signal"


def test_compute_pattern_changes_empty_on_no_changes() -> None:
    frame = pd.DataFrame(
        {
            "company_id": ["A", "A"],
            "year": ["2023-03", "2024-03"],
            "pattern_label": ["Reinvestor", "Reinvestor"],
        }
    )
    assert compute_pattern_changes(frame).empty


def test_latest_year_frame_prefers_march_with_fallback() -> None:
    frame = pd.DataFrame(
        {
            "company_id": ["A", "A", "B"],
            "year": ["2023-03", "2024-03", "2024-09"],
            "pattern_label": ["Reinvestor", "Mixed", "Mixed"],
        }
    )
    latest = latest_year_frame(frame)
    years = dict(zip(latest["company_id"], latest["year"]))
    assert years == {"A": "2024-03", "B": "2024-09"}
