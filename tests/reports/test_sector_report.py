"""Unit tests for the sector report generator."""

import pandas as pd
from reportlab.platypus import Table

from src.reports.sector_report import (
    _safe_filename,
    build_sector_story,
    generate_sector_report,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "company_id": ["TCS", "INFY"],
            "broad_sector": ["Information Technology", "Information Technology"],
            "return_on_equity_pct": [50.0, 30.0],
            "return_on_capital_employed_pct": [60.0, 40.0],
            "net_profit_margin_pct": [19.0, 17.0],
            "debt_to_equity": [0.1, 0.0],
            "revenue_cagr_5yr": [10.0, 12.0],
            "pat_cagr_5yr": [8.0, 9.0],
            "free_cash_flow_cr": [50000.0, 20000.0],
            "composite_quality_score": [71.0, 65.0],
        }
    )


def test_safe_filename() -> None:
    assert _safe_filename("Conglomerates/Other") == "Conglomerates_Other"
    assert _safe_filename("Information Technology") == "Information_Technology"


def test_build_sector_story_has_table() -> None:
    story = build_sector_story("Information Technology", _frame())
    assert any(isinstance(item, Table) for item in story)


def test_generate_sector_report_pdf(tmp_path) -> None:
    path = generate_sector_report(
        "Information Technology", _frame(), output_dir=tmp_path
    )
    assert path.exists()
    assert path.stat().st_size > 2_000