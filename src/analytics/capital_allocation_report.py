"""Capital allocation report: pattern distribution and YoY migrations."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cashflow_kpis import (
    cfo_pat_ratio,
    cfo_quality_score,
    classify_capital_allocation,
    resolve_cashflow_columns,
)
from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DISTRIBUTION_PATH = PROJECT_ROOT / "output" / "pattern_distribution_latest.csv"
CHANGES_PATH = PROJECT_ROOT / "output" / "pattern_changes.csv"


def fetch_capital_allocation(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return the full capital allocation matrix for all company-years."""
    with sqlite3.connect(db_path) as conn:
        cashflow = pd.read_sql_query("SELECT * FROM cashflow", conn)
        pl = pd.read_sql_query(
            "SELECT company_id, year, net_profit FROM profitandloss", conn
        )
    resolved = resolve_cashflow_columns(cashflow)
    frame = cashflow.rename(
        columns={source: logical for logical, source in resolved.items()}
    )
    frame = frame.merge(pl, on=["company_id", "year"], how="left")
    frame = frame.sort_values(["company_id", "year"])
    rows: list[dict] = []
    for company_id, group in frame.groupby("company_id"):
        group = group.sort_values("year")
        for idx, row in group.iterrows():
            ratios = [
                cfo_pat_ratio(hist_row["cfo"], hist_row["net_profit"])
                for _, hist_row in group.loc[:idx].tail(5).iterrows()
            ]
            score = cfo_quality_score(ratios)
            cfo, cfi, cff = row["cfo"], row["cfi"], row["cff"]
            rows.append(
                {
                    "company_id": company_id,
                    "year": row["year"],
                    "cfo_sign": "+" if cfo > 0 else ("-" if cfo < 0 else "0"),
                    "cfi_sign": "+" if cfi > 0 else ("-" if cfi < 0 else "0"),
                    "cff_sign": "+" if cff > 0 else ("-" if cff < 0 else "0"),
                    "pattern_label": classify_capital_allocation(cfo, cfi, cff, score),
                }
            )
    return pd.DataFrame(rows)


def latest_year_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the latest annual row per company, March-preferred with fallback."""
    march = frame[frame["year"].str.endswith("-03")]
    latest = march.sort_values("year").groupby("company_id").tail(1)
    missing = set(frame["company_id"]) - set(latest["company_id"])
    if missing:
        fallback = (
            frame[frame["company_id"].isin(missing)]
            .sort_values("year")
            .groupby("company_id")
            .tail(1)
        )
        latest = pd.concat([latest, fallback])
    return latest


def compute_pattern_changes(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of companies that changed their pattern YoY."""
    sorted_frame = frame.sort_values(["company_id", "year"])
    sorted_frame["prev_pattern"] = sorted_frame.groupby("company_id")[
        "pattern_label"
    ].shift(1)
    changes = sorted_frame[
        sorted_frame["pattern_label"] != sorted_frame["prev_pattern"]
    ].copy()
    changes = changes.dropna(subset=["prev_pattern"])
    return changes[["company_id", "year", "prev_pattern", "pattern_label"]].rename(
        columns={
            "prev_pattern": "previous_pattern",
            "pattern_label": "current_pattern",
        }
    )


def run_capital_allocation_report(db_path: Path = DB_PATH) -> None:
    """Generate the distribution summary and YoY pattern changes CSVs."""
    frame = fetch_capital_allocation(db_path)
    company_years = frame.groupby("company_id")["year"].count()
    logger.info(
        "Capital allocation matrix covers %d companies, avg %.1f years each",
        len(company_years),
        company_years.mean(),
    )
    latest = latest_year_frame(frame)
    latest_dist = latest["pattern_label"].value_counts().reset_index()
    latest_dist.columns = ["pattern_label", "company_count"]
    DISTRIBUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    latest_dist.to_csv(DISTRIBUTION_PATH, index=False)
    changes = compute_pattern_changes(frame)
    changes.to_csv(CHANGES_PATH, index=False)
    logger.info(
        "Wrote latest-year distribution for %d companies and %d YoY changes",
        len(latest),
        len(changes),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_capital_allocation_report()