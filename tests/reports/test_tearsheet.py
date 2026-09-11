"""Unit and integration tests for the company tearsheet generator."""

import re

import pandas as pd

from src.reports.tearsheet import build_kpi_tiles, generate_tearsheet


def test_build_kpi_tiles_formats_and_na() -> None:
    ratios = pd.DataFrame(
        {
            "year": ["2024-03"],
            "return_on_equity_pct": [25.0],
            "return_on_capital_employed_pct": [30.0],
            "net_profit_margin_pct": [18.0],
            "debt_to_equity": [0.0],
            "revenue_cagr_5yr": [None],
            "free_cash_flow_cr": [1200.0],
        }
    )
    tiles = build_kpi_tiles(ratios)
    assert tiles[0] == ("ROE", "25.0%")
    assert tiles[3] == ("D/E", "0.00")
    assert tiles[4] == ("Rev CAGR 5yr", "N/A")


def test_build_kpi_tiles_empty_ratios() -> None:
    tiles = build_kpi_tiles(pd.DataFrame())
    assert len(tiles) == 6
    assert all(value == "N/A" for _, value in tiles)


def test_generate_tearsheet_two_page_pdf(tmp_path) -> None:
    pdf = generate_tearsheet("TCS", output_dir=tmp_path)
    assert pdf.exists()
    assert pdf.stat().st_size > 30_000
    pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
    assert pages == 2