"""Two-page company tearsheet PDF generator using ReportLab."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.analytics.cashflow_kpis import (
    cfo_pat_ratio,
    cfo_quality_score,
    classify_capital_allocation,
)
from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)
logging.getLogger("matplotlib.category").setLevel(logging.WARNING)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "reports" / "tearsheets"
CHART_DIR = PROJECT_ROOT / "reports" / "_tearsheet_charts"
SKIPPED_PATH = PROJECT_ROOT / "output" / "skipped_tearsheets.csv"

NAVY = colors.HexColor("#1F3864")
GREEN = colors.HexColor("#2E7D32")
RED = colors.HexColor("#C62828")
LIGHT = colors.HexColor("#F2F2F2")

MARGIN = 2.2 * cm
USABLE_WIDTH = A4[0] - 2 * MARGIN
CHART_HEIGHT = USABLE_WIDTH * 3.0 / 7.4

_styles = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle(
    "TearsheetTitle", parent=_styles["Title"], textColor=colors.white, fontSize=15
)
TILE_LABEL = ParagraphStyle(
    "TileLabel", parent=_styles["Normal"], fontSize=8, textColor=colors.grey
)
TILE_VALUE = ParagraphStyle(
    "TileValue", parent=_styles["Normal"], fontSize=13, fontName="Helvetica-Bold"
)
BULLET_PRO = ParagraphStyle(
    "ProBullet", parent=_styles["Normal"], fontSize=9, textColor=GREEN
)
BULLET_CON = ParagraphStyle(
    "ConBullet", parent=_styles["Normal"], fontSize=9, textColor=RED
)
SECTION = ParagraphStyle("Section", parent=_styles["Heading2"], fontSize=12)


def _fmt(value: float | None, suffix: str = "%", precision: int = 1) -> str:
    """Format a numeric KPI for display, returning N/A when missing."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{precision}f}{suffix}"


def _empty_chart(path: Path, title: str) -> Path:
    """Render a placeholder chart PNG when source data is missing."""
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=110)
    ax.text(0.5, 0.5, "No data available", ha="center", fontsize=9)
    ax.set_title(title, fontsize=9)
    ax.axis("off")
    fig.savefig(path)
    plt.close(fig)
    return path


def fetch_tearsheet_data(ticker: str, db_path: Path = DB_PATH) -> dict:
    """Return all frames needed to render one company tearsheet."""
    with sqlite3.connect(db_path) as conn:
        company = pd.read_sql_query(
            "SELECT * FROM companies WHERE id = ?", conn, params=(ticker,)
        )
        sector = pd.read_sql_query(
            "SELECT * FROM sectors WHERE company_id = ?", conn, params=(ticker,)
        )
        ratios = pd.read_sql_query(
            "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )
        pl = pd.read_sql_query(
            "SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )
        bs = pd.read_sql_query(
            "SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )
        cf = pd.read_sql_query(
            "SELECT * FROM cashflow WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )
    return {
        "company": company,
        "sector": sector,
        "ratios": ratios,
        "pl": pl,
        "bs": bs,
        "cf": cf,
    }


def build_kpi_tiles(ratios: pd.DataFrame) -> list[tuple[str, str]]:
    """Return six latest-year KPI label/value pairs for the tile grid."""

    def get(key: str) -> float | None:
        if ratios.empty:
            return None
        return ratios.tail(1).iloc[0].get(key)

    return [
        ("ROE", _fmt(get("return_on_equity_pct"))),
        ("ROCE", _fmt(get("return_on_capital_employed_pct"))),
        ("Net Margin", _fmt(get("net_profit_margin_pct"))),
        ("D/E", _fmt(get("debt_to_equity"), suffix="", precision=2)),
        ("Rev CAGR 5yr", _fmt(get("revenue_cagr_5yr"))),
        ("FCF (Cr)", _fmt(get("free_cash_flow_cr"), suffix="", precision=0)),
    ]


def latest_pattern(cf: pd.DataFrame, pl: pd.DataFrame) -> str:
    """Return the capital allocation label for the latest cash flow year."""
    if cf.empty:
        return "N/A"
    merged = cf.merge(pl[["year", "net_profit"]], on="year", how="left")
    merged = merged.sort_values("year")
    row = merged.tail(1).iloc[0]
    scores = [
        cfo_pat_ratio(hist_row["operating_activity"], hist_row["net_profit"])
        for _, hist_row in merged.tail(5).iterrows()
    ]
    return classify_capital_allocation(
        row["operating_activity"],
        row["investing_activity"],
        row["financing_activity"],
        cfo_quality_score(scores),
    )


def chart_revenue_profit(pl: pd.DataFrame, path: Path) -> Path:
    """Render the 10-year revenue and net profit bar chart to PNG."""
    if pl.empty:
        return _empty_chart(path, "Revenue vs Net Profit (Cr)")
    data = pl.tail(10)
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=110)
    positions = list(range(len(data)))
    width = 0.4
    ax.bar(
        [i - width / 2 for i in positions],
        data["sales"],
        width,
        label="Sales",
        color="#1F3864",
    )
    ax.bar(
        [i + width / 2 for i in positions],
        data["net_profit"],
        width,
        label="Net Profit",
        color="#4472C4",
    )
    ax.set_xticks(positions)
    ax.set_xticklabels(data["year"].str[:4], fontsize=7, rotation=45)
    ax.set_title("Revenue vs Net Profit (Cr)", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def chart_returns(ratios: pd.DataFrame, path: Path) -> Path:
    """Render the ROE and ROCE dual-axis line chart to PNG."""
    if ratios.empty:
        return _empty_chart(path, "ROE vs ROCE (%)")
    data = ratios.tail(10)
    fig, ax1 = plt.subplots(figsize=(7.4, 3.0), dpi=110)
    years = data["year"].str[:4]
    ax1.plot(
        years, data["return_on_equity_pct"], marker="o", color="#1F3864", label="ROE"
    )
    ax1.set_ylabel("ROE %", fontsize=8)
    ax2 = ax1.twinx()
    ax2.plot(
        years,
        data["return_on_capital_employed_pct"],
        marker="s",
        color="#ED7D31",
        label="ROCE",
    )
    ax2.set_ylabel("ROCE %", fontsize=8)
    ax1.tick_params(labelsize=7)
    ax2.tick_params(labelsize=7)
    ax1.set_title("ROE vs ROCE (%)", fontsize=9)
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def chart_bs_composition(bs: pd.DataFrame, path: Path) -> Path:
    """Render the balance sheet composition stacked bar chart to PNG."""
    if bs.empty:
        return _empty_chart(path, "Balance Sheet Composition (Cr)")
    data = bs.tail(10)
    equity = data["equity_capital"] + data["reserves"].fillna(0)
    borrowings = data["borrowings"].fillna(0)
    other = data["other_liabilities"].fillna(0)
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=110)
    years = data["year"].str[:4]
    ax.bar(years, equity, label="Equity", color="#2E7D32")
    ax.bar(years, borrowings, bottom=equity, label="Borrowings", color="#C62828")
    ax.bar(
        years,
        other,
        bottom=equity + borrowings,
        label="Other Liabilities",
        color="#9E9E9E",
    )
    ax.set_title("Balance Sheet Composition (Cr)", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def chart_cf_waterfall(cf: pd.DataFrame, path: Path) -> Path:
    """Render the latest-year cash flow waterfall chart to PNG."""
    if cf.empty:
        return _empty_chart(path, "Cash Flow Waterfall (Cr)")
    row = cf.tail(1).iloc[0]
    steps = [
        float(row["operating_activity"]),
        float(row["investing_activity"]),
        float(row["financing_activity"]),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=110)
    cumulative = 0.0
    for index, value in enumerate(steps):
        ax.bar(
            index,
            value,
            bottom=cumulative,
            width=0.6,
            color="#2E7D32" if value >= 0 else "#C62828",
        )
        cumulative += value
    ax.bar(3, cumulative, width=0.6, color="#1F3864")
    ax.set_xticks([0, 1, 2, 3])
    ax.set_xticklabels(["CFO", "CFI", "CFF", "Net Cash"], fontsize=8)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Cash Flow Waterfall - Latest Year (Cr)", fontsize=9)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def load_pros_cons(ticker: str) -> tuple[list[str], list[str]]:
    """Return top pros and cons texts for a company from the generated CSV."""
    csv_path = PROJECT_ROOT / "output" / "pros_cons_generated.csv"
    if not csv_path.exists():
        return [], []
    frame = pd.read_csv(csv_path)
    subset = frame[frame["company_id"] == ticker]
    pros = (
        subset[subset["type"] == "pro"]
        .sort_values("confidence_pct", ascending=False)["text"]
        .head(5)
        .tolist()
    )
    cons = (
        subset[subset["type"] == "con"]
        .sort_values("confidence_pct", ascending=False)["text"]
        .head(5)
        .tolist()
    )
    return pros, cons


def generate_tearsheet(ticker: str, output_dir: Path = OUTPUT_DIR) -> Path:
    """Render the two-page tearsheet PDF for one company and return its path."""
    data = fetch_tearsheet_data(ticker)
    if data["company"].empty:
        raise ValueError(f"Unknown ticker: {ticker}")
    name = data["company"].iloc[0]["company_name"]
    sector = (
        data["sector"].iloc[0]["broad_sector"] if not data["sector"].empty else "N/A"
    )
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{ticker}_tearsheet.pdf"

    story = []
    header = Table(
        [
            [
                Paragraph(f"{name} ({ticker})", TITLE_STYLE),
                Paragraph(sector, TITLE_STYLE),
            ]
        ],
        colWidths=[USABLE_WIDTH * 0.7, USABLE_WIDTH * 0.3],
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

    cells = [
        [Paragraph(label, TILE_LABEL), Paragraph(value, TILE_VALUE)]
        for label, value in build_kpi_tiles(data["ratios"])
    ]
    grid = Table([cells[0:3], cells[3:6]], colWidths=[USABLE_WIDTH / 3] * 3)
    grid.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(grid)
    story.append(Spacer(1, 0.3 * cm))

    for chart in (
        chart_revenue_profit(data["pl"], CHART_DIR / f"{ticker}_rev.png"),
        chart_returns(data["ratios"], CHART_DIR / f"{ticker}_ret.png"),
    ):
        story.append(Image(str(chart), width=USABLE_WIDTH, height=CHART_HEIGHT))
        story.append(Spacer(1, 0.2 * cm))

    story.append(PageBreak())

    story.append(Paragraph("Balance Sheet & Cash Flow", SECTION))
    for chart in (
        chart_bs_composition(data["bs"], CHART_DIR / f"{ticker}_bs.png"),
        chart_cf_waterfall(data["cf"], CHART_DIR / f"{ticker}_cf.png"),
    ):
        story.append(Image(str(chart), width=USABLE_WIDTH, height=CHART_HEIGHT))
        story.append(Spacer(1, 0.2 * cm))

    pros, cons = load_pros_cons(ticker)
    story.append(Paragraph("Pros", SECTION))
    for text in pros:
        story.append(Paragraph(f"&bull; {text}", BULLET_PRO))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Cons", SECTION))
    for text in cons:
        story.append(Paragraph(f"&bull; {text}", BULLET_CON))
    story.append(Spacer(1, 0.3 * cm))

    badge = Table(
        [
            [
                Paragraph(
                    f"Capital Allocation: {latest_pattern(data['cf'], data['pl'])}",
                    TILE_VALUE,
                )
            ]
        ],
        colWidths=[USABLE_WIDTH],
    )
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(badge)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"{ticker} Tearsheet",
    )
    doc.build(story)
    logger.info("Generated tearsheet for %s at %s", ticker, pdf_path)
    return pdf_path


def run_batch_tearsheets(
    output_dir: Path = OUTPUT_DIR,
    db_path: Path = DB_PATH,
    min_years: int = 3,
) -> tuple[int, list[str]]:
    """Generate tearsheets for all companies, skipping short histories."""
    with sqlite3.connect(db_path) as conn:
        companies = pd.read_sql_query("SELECT id FROM companies ORDER BY id", conn)
        coverage = pd.read_sql_query(
            "SELECT company_id, COUNT(*) AS years FROM profitandloss "
            "GROUP BY company_id",
            conn,
        )
    years_by_company = dict(zip(coverage["company_id"], coverage["years"]))
    skipped: list[str] = []
    generated = 0
    for ticker in companies["id"]:
        if int(years_by_company.get(ticker, 0)) < min_years:
            skipped.append(ticker)
            continue
        generate_tearsheet(ticker, output_dir)
        generated += 1
    skipped_frame = pd.DataFrame(
        {"company_id": skipped, "reason": "fewer than 3 years of data"}
    )
    SKIPPED_PATH.parent.mkdir(parents=True, exist_ok=True)
    skipped_frame.to_csv(SKIPPED_PATH, index=False)
    logger.info("Generated %d tearsheets, skipped %d", generated, len(skipped))
    return generated, skipped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_batch_tearsheets()
