"""Portfolio summary PDF generator: one page per company with trend arrows."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "reports" / "portfolio"
OUTPUT_PATH = OUTPUT_DIR / "portfolio_summary.pdf"

NAVY = colors.HexColor("#1F3864")
MARGIN = 1.5 * cm
USABLE_WIDTH = A4[0] - 2 * MARGIN

_styles = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle(
    "PortfolioTitle", parent=_styles["Title"], textColor=colors.white, fontSize=16
)
COMPANY_STYLE = ParagraphStyle(
    "CompanyStyle", parent=_styles["Heading1"], fontSize=14, textColor=NAVY
)
SECTOR_STYLE = ParagraphStyle(
    "SectorStyle", parent=_styles["Normal"], fontSize=10, textColor=colors.grey
)
KPI_LABEL = ParagraphStyle(
    "KpiLabel", parent=_styles["Normal"], fontSize=9, textColor=colors.grey
)
KPI_VALUE = ParagraphStyle(
    "KpiValue", parent=_styles["Normal"], fontSize=12, fontName="Helvetica-Bold"
)

METRICS = [
    ("return_on_equity_pct", "ROE (%)", False),
    ("return_on_capital_employed_pct", "ROCE (%)", False),
    ("net_profit_margin_pct", "Net Margin (%)", False),
    ("debt_to_equity", "Debt / Equity", True),
    ("revenue_cagr_5yr", "Rev CAGR 5yr (%)", False),
    ("free_cash_flow_cr", "FCF (Cr)", False),
]


def _fmt(value: float | None, precision: int = 1) -> str:
    """Format a metric for display, returning N/A when missing."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{precision}f}"


def _trend_arrow(
    latest: float | None, previous: float | None, invert: bool = False
) -> tuple[str, str]:
    """Return the trend arrow and hex colour based on YoY change."""
    if (
        latest is None
        or previous is None
        or pd.isna(latest)
        or pd.isna(previous)
        or previous == 0
    ):
        return "→", "#757575"

    change_pct = (latest - previous) / abs(previous)

    if invert:
        if change_pct < -0.02:
            return "↑", "#2E7D32"
        if change_pct > 0.02:
            return "↓", "#C62828"
        return "→", "#757575"

    if change_pct > 0.02:
        return "↑", "#2E7D32"
    if change_pct < -0.02:
        return "↓", "#C62828"
    return "→", "#757575"


def fetch_portfolio_data(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return latest and previous year KPIs for all companies, sorted by ticker."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
        companies = pd.read_sql_query("SELECT id, company_name FROM companies", conn)

    ratios = ratios.sort_values(["company_id", "year"])
    rows: list[dict] = []
    for company_id, group in ratios.groupby("company_id"):
        latest = group.iloc[-1]
        prev = group.iloc[-2] if len(group) >= 2 else pd.Series()
        row = {"company_id": company_id}
        for col, _, _ in METRICS:
            row[f"{col}_latest"] = latest.get(col)
            row[f"{col}_prev"] = prev.get(col)
        rows.append(row)

    frame = pd.DataFrame(rows)
    frame = frame.merge(
        companies.rename(columns={"id": "company_id"}), on="company_id", how="left"
    )
    frame = frame.merge(sectors, on="company_id", how="left")
    return frame.sort_values("company_id")


def build_company_story(row: pd.Series) -> list:
    """Return the platypus story elements for one company page."""
    story = [
        Paragraph(str(row["company_name"]), COMPANY_STYLE),
        Paragraph(str(row.get("broad_sector", "N/A")), SECTOR_STYLE),
        Spacer(1, 0.5 * cm),
    ]
    data = [
        [
            Paragraph("Metric", KPI_LABEL),
            Paragraph("Latest", KPI_LABEL),
            Paragraph("Trend", KPI_LABEL),
        ]
    ]
    for col, label, invert in METRICS:
        latest_val = row.get(f"{col}_latest")
        prev_val = row.get(f"{col}_prev")
        arrow, color_hex = _trend_arrow(latest_val, prev_val, invert)
        precision = 2 if col == "debt_to_equity" else 1
        data.append(
            [
                Paragraph(label, KPI_LABEL),
                Paragraph(_fmt(latest_val, precision), KPI_VALUE),
                Paragraph(f"<font color='{color_hex}'>{arrow}</font>", KPI_VALUE),
            ]
        )
    table = Table(
        data,
        colWidths=[USABLE_WIDTH * 0.5, USABLE_WIDTH * 0.3, USABLE_WIDTH * 0.2],
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(table)
    story.append(PageBreak())
    return story


def generate_portfolio_summary(
    db_path: Path = DB_PATH, output_path: Path = OUTPUT_PATH
) -> Path:
    """Render the multi-page portfolio summary PDF and return its path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame = fetch_portfolio_data(db_path)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Nifty 100 Portfolio Summary",
    )
    story = []
    title_table = Table(
        [[Paragraph("Nifty 100 Portfolio Summary", TITLE_STYLE)]],
        colWidths=[USABLE_WIDTH],
    )
    title_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(title_table)
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(f"Total Companies: {len(frame)}", _styles["Heading2"]))
    story.append(PageBreak())
    for _, row in frame.iterrows():
        story.extend(build_company_story(row))
    doc.build(story)
    logger.info(
        "Generated portfolio summary for %d companies at %s", len(frame), output_path
    )
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_portfolio_summary()
