"""NLP parser for extracting structured CAGR metrics from analysis.xlsx text fields."""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cagr import cagr_ending_at
from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARSED_PATH = PROJECT_ROOT / "output" / "analysis_parsed.csv"
FAILURES_PATH = PROJECT_ROOT / "output" / "parse_failures.csv"
CROSS_VALIDATION_PATH = PROJECT_ROOT / "output" / "cagr_cross_validation.csv"

CAGR_PATTERN = re.compile(r"(\d+)\s*Years?\s*:?\s*([\d.]+)%", re.IGNORECASE)

TARGET_FIELDS = {
    "compounded_sales_growth": "revenue_cagr",
    "compounded_profit_growth": "pat_cagr",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}

SERIES_COLUMNS = {"revenue_cagr": "sales", "pat_cagr": "net_profit"}


def parse_text(text: str) -> tuple[int | None, float | None]:
    """Extract period (years) and value (%) from text like '10 Years: 21%'."""
    if pd.isna(text) or not isinstance(text, str):
        return None, None
    match = CAGR_PATTERN.search(text)
    if not match:
        return None, None
    try:
        return int(match.group(1)), float(match.group(2))
    except (ValueError, TypeError):
        return None, None


def parse_analysis_table(
    analysis_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse all target fields in the analysis DataFrame."""
    parsed_rows: list[dict] = []
    failure_rows: list[dict] = []
    for _, row in analysis_df.iterrows():
        company_id = row.get("company_id")
        if pd.isna(company_id):
            continue
        for raw_col, metric_type in TARGET_FIELDS.items():
            if raw_col not in row.index:
                continue
            text = row[raw_col]
            period, value = parse_text(text)
            if period is not None and value is not None:
                parsed_rows.append(
                    {
                        "company_id": company_id,
                        "metric_type": metric_type,
                        "period_years": period,
                        "value_pct": value,
                        "raw_text": text,
                    }
                )
            elif pd.notna(text) and str(text).strip():
                failure_rows.append(
                    {
                        "company_id": company_id,
                        "field": raw_col,
                        "raw_text": text,
                        "reason": "Regex pattern mismatch",
                    }
                )
    return pd.DataFrame(parsed_rows), pd.DataFrame(failure_rows)


def cross_validate_cagr(
    parsed_df: pd.DataFrame, db_path: Path = DB_PATH
) -> pd.DataFrame:
    """Compare parsed CAGR values against Ratio Engine computed CAGRs."""
    if parsed_df.empty:
        return pd.DataFrame()
    cagr_df = parsed_df[parsed_df["metric_type"].isin(SERIES_COLUMNS)].copy()
    if cagr_df.empty:
        return pd.DataFrame()
    with sqlite3.connect(db_path) as conn:
        pl = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit FROM profitandloss", conn
        )
    results: list[dict] = []
    for (ticker, metric), group in cagr_df.groupby(["company_id", "metric_type"]):
        company = pl[pl["company_id"] == ticker]
        if company.empty:
            continue
        series = (
            company.set_index("year")[SERIES_COLUMNS[metric]].dropna().sort_index()
        )
        if series.empty:
            continue
        end_label = str(series.index[-1])
        for _, row in group.iterrows():
            computed, flag = cagr_ending_at(series, end_label, int(row["period_years"]))
            if computed is None:
                results.append(
                    {
                        "company_id": ticker,
                        "metric": metric,
                        "period_years": int(row["period_years"]),
                        "parsed_value_pct": row["value_pct"],
                        "computed_value_pct": None,
                        "absolute_diff_pct": None,
                        "validation_flag": f"SKIPPED ({flag})",
                    }
                )
                continue
            diff = abs(float(row["value_pct"]) - computed)
            results.append(
                {
                    "company_id": ticker,
                    "metric": metric,
                    "period_years": int(row["period_years"]),
                    "parsed_value_pct": row["value_pct"],
                    "computed_value_pct": round(computed, 2),
                    "absolute_diff_pct": round(diff, 2),
                    "validation_flag": "DIVERGENCE > 5%" if diff > 5.0 else "MATCH",
                }
            )
    return pd.DataFrame(results)


def run_parser(db_path: Path = DB_PATH) -> None:
    """Execute the full NLP parsing and cross-validation pipeline."""
    with sqlite3.connect(db_path) as conn:
        analysis_df = pd.read_sql_query("SELECT * FROM analysis", conn)
    if analysis_df.empty:
        logger.warning("Analysis table is empty.")
        return
    parsed_df, failures_df = parse_analysis_table(analysis_df)
    PARSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    parsed_df.to_csv(PARSED_PATH, index=False)
    failures_df.to_csv(FAILURES_PATH, index=False)
    logger.info(
        "Parsed %d metrics, logged %d failures", len(parsed_df), len(failures_df)
    )
    cross_val_df = cross_validate_cagr(parsed_df, db_path)
    if not cross_val_df.empty:
        cross_val_df.to_csv(CROSS_VALIDATION_PATH, index=False)
        divergences = int((cross_val_df["validation_flag"] == "DIVERGENCE > 5%").sum())
        logger.info(
            "Cross-validated %d CAGRs, found %d divergences > 5%%",
            len(cross_val_df),
            divergences,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_parser()