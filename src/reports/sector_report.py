"""Sector report PDF generator using ReportLab."""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "reports" / "sector"

NAVY = colors.HexColor("#1F3864")
LIGHT = colors.HexColor("#F2F2F2")

MARGIN = 1.5 * cm
USABLE_WIDTH = A4[0] - 2 * MARGIN

_styles = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle(
    "SectorTitle", parent=_styles["Title"], textColor=colors.white, fontSize=15
)
CELL = ParagraphStyle("Cell", parent=_styles["Normal"], fontSize=8)
HEADER_CELL = ParagraphStyle(
    "HeaderCell",
    parent=_styles["Normal"],
    fontSize=8,
    fontName="Helvetica-Bold",
    textColor=colors.white,
)
MEDIAN_CELL = ParagraphStyle(
    "MedianCell", parent=_styles["Normal"], fontSize=8, fontName="Helvetica-Bold"
)
SECTION = ParagraphStyle("SectorSection", parent=_styles["Heading2"], fontSize=12)

METRIC_COLUMNS = (
    ("return_on_equity_pct", "ROE %"),
    ("return_on_capital_employed_pct", "ROCE %"),
    ("net_profit_margin_pct", "NPM %"),
    ("debt_to_equity", "D/E"),
    ("revenue_cagr_5yr", "Rev CAGR 5y"),
    ("pat_cagr_5yr", "PAT CAGR 5y"),
    ("free_cash_flow_cr", "FCF Cr"),
    ("composite_quality_score", "Composite"),
)


def _fmt(value: float | None, precision: int = 1) -> str:
    """Format a metric for table display, returning N/A when missing."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{precision}f}"


def _safe_filename(sector: str) -> str:
    """Return a filesystem-safe filename stem for a sector name."""
    return re.sub(r"[^A-Za-z0-9]+", "_", sector).strip("_")


def fetch_sector_data(db_path: Path = DB_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return latest-year ratios joined with sectors and the sector table."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
    march = ratios[ratios["year"].str.endswith("-03")]
    latest = march.sort_values("year").groupby("company_id").tail(1)
    missing = set(ratios["company_id"]) - set(latest["company_id"])
    if missing:
        fallback = (
            ratios[ratios["company_id"].isin(missing)]
            .sort_values("year")
            .groupby("company_id")
            .tail(1)
        )
        latest = pd.concat([latest, fallback])
    return latest.merge(sectors, on="company_id", how="left"), sectors


def build_sector_story(sector: str, frame: pd.DataFrame) -> list:
    """Return the platypus story for one sector report."""
    members = frame[frame["broad_sector"] == sector].sort_values("company_id")
    story: list = []
    header = Table(
        [[Paragraph(f"{sector} - Sector Report", TITLE_STYLE)]],
        colWidths=[USABLE_WIDTH],
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"Companies in sector: {len(members)}", SECTION))
    story.append(Spacer(1, 0.2 * cm))
    labels = [label for _, label in METRIC_COLUMNS]
    data = [
        [Paragraph("Company", HEADER_CELL)]
        + [Paragraph(t, HEADER_CELL) for t in labels]
    ]
    median_cells = ["Sector Median"] + [
        _fmt(members[column].median()) for column, _ in METRIC_COLUMNS
    ]
    data.append([Paragraph(text, MEDIAN_CELL) for text in median_cells])
    for _, row in members.iterrows():
        data.append(
            [Paragraph(str(row["company_id"]), CELL)]
            + [Paragraph(_fmt(row[column]), CELL) for column, _ in METRIC_COLUMNS]
        )
    table = Table(
        data,
        colWidths=[USABLE_WIDTH * 0.20] + [USABLE_WIDTH * 0.80 / 8] * 8,
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("BACKGROUND", (0, 1), (-1, 1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    return story


def generate_sector_report(
    sector: str, frame: pd.DataFrame, output_dir: Path = OUTPUT_DIR
) -> Path:
    """Render one sector report PDF and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{_safe_filename(sector)}_report.pdf"
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"{sector} Sector Report",
    )
    doc.build(build_sector_story(sector, frame))
    logger.info("Generated sector report for %s at %s", sector, path)
    return path


def generate_all_sector_reports(
    db_path: Path = DB_PATH, output_dir: Path = OUTPUT_DIR
) -> int:
    """Render sector report PDFs for all broad sectors and return the count."""
    frame, sectors = fetch_sector_data(db_path)
    count = 0
    for sector in sorted(sectors["broad_sector"].unique()):
        generate_sector_report(sector, frame, output_dir)
        count += 1
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_all_sector_reports()
