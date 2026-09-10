"""Ratio engine orchestration: build and persist the financial_ratios table."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

from src.analytics.cagr import cagr_ending_at, compute_cagr_ratios
from src.analytics.cashflow_kpis import compute_cashflow_kpis, fetch_cashflow_inputs
from src.analytics.composite import compute_composite_score
from src.analytics.ratios import (
    DB_PATH,
    compute_leverage_ratios,
    compute_profitability_ratios,
    fetch_profitability_inputs,
)

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS = (
    "company_id",
    "year",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "return_on_assets_pct",
    "debt_to_equity",
    "interest_coverage",
    "icr_label",
    "asset_turnover",
    "free_cash_flow_cr",
    "capex_cr",
    "cash_from_operations_cr",
    "total_debt_cr",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "revenue_cagr_5yr",
    "revenue_cagr_5yr_flag",
    "pat_cagr_5yr",
    "pat_cagr_5yr_flag",
    "eps_cagr_5yr",
    "eps_cagr_5yr_flag",
    "composite_quality_score",
)

SCHEMA_TYPES = {column: "REAL" for column in OUTPUT_COLUMNS[2:]}
SCHEMA_TYPES["icr_label"] = "TEXT"
SCHEMA_TYPES["revenue_cagr_5yr_flag"] = "TEXT"
SCHEMA_TYPES["pat_cagr_5yr_flag"] = "TEXT"
SCHEMA_TYPES["eps_cagr_5yr_flag"] = "TEXT"

def book_value_per_share(
    equity_capital: Optional[float],
    reserves: Optional[float],
    face_value: Optional[float],
) -> Optional[float]:
    """Return book value per share, or None when equity capital is zero."""
    if equity_capital is None or reserves is None or face_value is None:
        return None
    if pd.isna(equity_capital) or pd.isna(reserves) or pd.isna(face_value):
        return None
    if equity_capital == 0:
        return None
    return (equity_capital + reserves) * face_value / equity_capital


def _fcf_cagr_frame(cashflow_kpis: pd.DataFrame) -> pd.DataFrame:
    """Return five-year FCF CAGR per company-year from cash flow KPI rows."""
    rows: list[dict] = []
    for company_id, company in cashflow_kpis.groupby("company_id"):
        series = (
            company.set_index("year")["free_cash_flow_cr"].dropna().sort_index()
        )
        for year in company["year"]:
            value, _ = cagr_ending_at(series, year, 5)
            rows.append({"company_id": company_id, "year": year, "fcf_cagr_5yr": value})
    return pd.DataFrame(rows)


def build_financial_ratios(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Assemble every computed KPI into one company-year frame for persistence."""
    pl, bs, sectors = fetch_profitability_inputs(db_path)
    profitability = compute_profitability_ratios(pl, bs, sectors)
    leverage = compute_leverage_ratios(pl, bs, sectors)
    merged = profitability.merge(
        leverage[
            [
                "company_id",
                "year",
                "debt_to_equity",
                "interest_coverage",
                "icr_label",
                "asset_turnover",
            ]
        ],
        on=["company_id", "year"],
        how="left",
    )
    merged = merged.merge(
        compute_cagr_ratios(pl), on=["company_id", "year"], how="left"
    )
    cashflow, _ = fetch_cashflow_inputs(db_path)
    cf_kpis = compute_cashflow_kpis(cashflow, pl)
    merged = merged.merge(
        cf_kpis[
            [
                "company_id",
                "year",
                "free_cash_flow_cr",
                "capex_cr",
                "cash_from_operations_cr",
                "cfo_quality_score",
            ]
        ],
        on=["company_id", "year"],
        how="left",
    )
    merged = merged.merge(
        _fcf_cagr_frame(cf_kpis), on=["company_id", "year"], how="left"
    )
    with sqlite3.connect(db_path) as conn:
        companies = pd.read_sql_query("SELECT id, face_value FROM companies", conn)
    merged = merged.merge(
        companies.rename(columns={"id": "company_id"}), on="company_id", how="left"
    )
    merged["earnings_per_share"] = merged["eps"]
    merged["dividend_payout_ratio_pct"] = merged["dividend_payout"]
    merged["total_debt_cr"] = merged["borrowings"]
    merged["book_value_per_share"] = merged.apply(
        lambda row: book_value_per_share(
            row["equity_capital"], row["reserves"], row["face_value"]
        ),
        axis=1,
    )
    merged["composite_quality_score"] = compute_composite_score(merged)
    return merged[list(OUTPUT_COLUMNS)]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create financial_ratios if absent and add any missing KPI columns."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS financial_ratios ("
        "company_id TEXT NOT NULL REFERENCES companies(id), "
        "year TEXT NOT NULL, "
        "PRIMARY KEY (company_id, year)"
        ")"
    )
    existing = {row[1] for row in conn.execute("PRAGMA table_info(financial_ratios)")}
    for column in OUTPUT_COLUMNS:
        if column not in existing:
            conn.execute(
                f"ALTER TABLE financial_ratios ADD COLUMN {column} "
                f"{SCHEMA_TYPES.get(column, 'REAL')}"
            )

def write_financial_ratios(frame: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """Replace the financial_ratios table contents with the computed KPI frame."""
    with sqlite3.connect(db_path) as conn:
        ensure_schema(conn)
        conn.execute("DELETE FROM financial_ratios")
        placeholders = ", ".join("?" for _ in OUTPUT_COLUMNS)
        conn.executemany(
            f"INSERT INTO financial_ratios ({', '.join(OUTPUT_COLUMNS)}) "
            f"VALUES ({placeholders})",
            [
                tuple(None if pd.isna(value) else value for value in row)
                for row in frame.itertuples(index=False, name=None)
            ],
        )
        conn.commit()
    logger.info("Wrote %d rows to financial_ratios", len(frame))
    return len(frame)


def run_engine(db_path: Path = DB_PATH) -> int:
    """Build and persist the financial_ratios table, returning the row count."""
    return write_financial_ratios(build_financial_ratios(db_path))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_engine()