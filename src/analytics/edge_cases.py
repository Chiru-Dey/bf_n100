"""Edge case collection and return-metric cross-check logging for the ratio engine."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.analytics.cagr import compute_cagr_ratios
from src.analytics.ratios import (
    DB_PATH,
    DEBT_FREE_LABEL,
    is_financials_sector,
    load_ratio_config,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EDGE_LOG_PATH = PROJECT_ROOT / "output" / "ratio_edge_cases.log"
SECTOR_ROCE_NOTES_PATH = PROJECT_ROOT / "output" / "sector_roce_notes.csv"

DATA_SOURCE_ISSUE = "data source issue"
VERSION_DIFFERENCE = "version difference"
FORMULA_DISCREPANCY = "formula discrepancy"
HANDLED_EDGE_CASE = "handled edge case"

CAGR_SIGN_FLAGS = ("TURNAROUND", "DECLINE_TO_LOSS", "BOTH_NEGATIVE", "ZERO_BASE")


def categorise_anomaly(
    computed: float, source: float, broad_sector: str, tolerance: float
) -> str:
    """Return the documented category for a return-metric cross-check anomaly."""
    if abs(computed - source * 100.0) <= tolerance:
        return DATA_SOURCE_ISSUE
    if is_financials_sector(broad_sector):
        return FORMULA_DISCREPANCY
    return VERSION_DIFFERENCE


def fetch_latest_ratios(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return latest-year computed ratios joined with source returns and sectors."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        companies = pd.read_sql_query(
            "SELECT id, roce_percentage, roe_percentage FROM companies", conn
        )
        sectors = pd.read_sql_query("SELECT company_id, broad_sector FROM sectors", conn)
    latest = ratios.sort_values("year").groupby("company_id").tail(1)
    merged = latest.merge(
        companies.rename(columns={"id": "company_id"}), on="company_id", how="left"
    )
    return merged.merge(sectors, on="company_id", how="left")


def cross_check_returns(frame: pd.DataFrame) -> list[dict]:
    """Return ROCE and ROE cross-check anomalies exceeding the configured tolerance."""
    tolerance = float(
        load_ratio_config()["edge_cases"]["cross_check_tolerance_pct"]
    )
    records: list[dict] = []
    pairs = (
        ("return_on_capital_employed_pct", "roce_percentage"),
        ("return_on_equity_pct", "roe_percentage"),
    )
    for metric, source_column in pairs:
        for row in frame.itertuples(index=False):
            computed = getattr(row, metric)
            source = getattr(row, source_column)
            if pd.isna(computed) or pd.isna(source):
                continue
            diff = abs(float(computed) - float(source))
            if diff <= tolerance:
                continue
            records.append(
                {
                    "company_id": row.company_id,
                    "year": row.year,
                    "metric": metric,
                    "computed": round(float(computed), 2),
                    "source": round(float(source), 2),
                    "diff": round(diff, 2),
                    "category": categorise_anomaly(
                        float(computed), float(source), row.broad_sector, tolerance
                    ),
                }
            )
    return records


def collect_cagr_edge_cases(db_path: Path = DB_PATH) -> list[dict]:
    """Return all sign-based CAGR edge case events across growth metrics."""
    with sqlite3.connect(db_path) as conn:
        pl = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit, eps FROM profitandloss", conn
        )
    cagr = compute_cagr_ratios(pl)
    records: list[dict] = []
    for window in load_ratio_config()["cagr"]["windows_years"]:
        for metric in ("revenue", "pat", "eps"):
            flag_column = f"{metric}_cagr_{window}yr_flag"
            subset = cagr[cagr[flag_column].isin(CAGR_SIGN_FLAGS)]
            for row in subset.itertuples(index=False):
                records.append(
                    {
                        "company_id": row.company_id,
                        "year": row.year,
                        "metric": f"{metric}_cagr_{window}yr",
                        "flag": getattr(row, flag_column),
                    }
                )
    return records


def collect_debt_free_events(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return every company-year where ICR was substituted with the Debt Free label."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query(
            "SELECT company_id, year, icr_label FROM financial_ratios", conn
        )
    return ratios[ratios["icr_label"] == DEBT_FREE_LABEL]


def collect_zero_denominator_counts(db_path: Path = DB_PATH) -> dict[str, int]:
    """Return aggregate counts of zero-denominator substitutions per metric."""
    with sqlite3.connect(db_path) as conn:
        pl = pd.read_sql_query("SELECT sales, interest FROM profitandloss", conn)
        bs = pd.read_sql_query(
            "SELECT equity_capital, reserves, total_assets FROM balancesheet", conn
        )
    equity = bs["equity_capital"] + bs["reserves"]
    return {
        "net_profit_margin_pct (sales=0)": int((pl["sales"] == 0).sum()),
        "operating_profit_margin_pct (sales=0)": int((pl["sales"] == 0).sum()),
        "return_on_equity_pct (equity+reserves<=0)": int((equity <= 0).sum()),
        "return_on_assets_pct (total_assets=0)": int((bs["total_assets"] == 0).sum()),
        "asset_turnover (total_assets=0)": int((bs["total_assets"] == 0).sum()),
        f"interest_coverage (interest=0 -> {DEBT_FREE_LABEL})": int(
            (pl["interest"] == 0).sum()
        ),
    }


def financials_company_count(db_path: Path = DB_PATH) -> int:
    """Return the number of companies in the Financials broad sector."""
    with sqlite3.connect(db_path) as conn:
        sectors = pd.read_sql_query("SELECT broad_sector FROM sectors", conn)
    return int((sectors["broad_sector"] == load_ratio_config()["financials_sector"]).sum())


def write_ratio_edge_cases(
    cross_checks: list[dict],
    cagr_events: list[dict],
    debt_free: pd.DataFrame,
    zero_counts: dict[str, int],
    financials_count: int,
    path: Path = EDGE_LOG_PATH,
) -> Path:
    """Write the ratio edge case log deliverable and return its path."""
    stamp = datetime.now().isoformat(timespec="seconds")
    lines = [
        f"Nifty 100 ratio engine edge case log - generated {stamp}",
        "",
        f"[1] RETURN CROSS-CHECK ANOMALIES - {len(cross_checks)}",
    ]
    lines += [
        f"{r['company_id']} {r['year']} {r['metric']}: computed={r['computed']} "
        f"source={r['source']} diff={r['diff']} category={r['category']}"
        for r in cross_checks
    ]
    lines += ["", f"[2] CAGR SIGN EDGE CASES - {len(cagr_events)}"]
    lines += [
        f"{r['company_id']} {r['year']} {r['metric']}: flag={r['flag']} "
        f"category={HANDLED_EDGE_CASE}"
        for r in cagr_events
    ]
    lines += ["", f"[3] DEBT-FREE ICR SUBSTITUTIONS - {len(debt_free)}"]
    lines += [
        f"{row.company_id} {row.year}: interest=0 icr_label={DEBT_FREE_LABEL} "
        f"category={HANDLED_EDGE_CASE}"
        for row in debt_free.itertuples(index=False)
    ]
    lines += ["", "[4] ZERO-DENOMINATOR SUBSTITUTION COUNTS"]
    lines += [
        f"{metric}: {count} rows category={HANDLED_EDGE_CASE}"
        for metric, count in zero_counts.items()
    ]
    lines += ["", "[5] FINANCIALS CARVE-OUT"]
    lines.append(
        f"D/E high-leverage flag suppressed for {financials_count} Financials "
        f"companies; sector-relative ROCE benchmark active; category="
        f"{FORMULA_DISCREPANCY} (by design)"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(
        "Wrote %s edge case records to %s",
        len(cross_checks) + len(cagr_events) + len(debt_free),
        path,
    )
    return path


def write_sector_roce_notes(
    frame: pd.DataFrame, path: Path = SECTOR_ROCE_NOTES_PATH
) -> Path:
    """Write the Financials sector-relative ROCE notes CSV and return its path."""
    financials = frame[
        frame["broad_sector"] == load_ratio_config()["financials_sector"]
    ].copy()
    financials["diff"] = (
        financials["return_on_capital_employed_pct"] - financials["roce_percentage"]
    ).abs()
    financials["benchmark"] = "sector_relative_median"
    columns = [
        "company_id",
        "broad_sector",
        "year",
        "return_on_capital_employed_pct",
        "roce_percentage",
        "diff",
        "benchmark",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    financials[columns].to_csv(path, index=False)
    logger.info("Wrote sector ROCE notes for %d companies to %s", len(financials), path)
    return path


def run_edge_case_review(db_path: Path = DB_PATH) -> Path:
    """Collect all edge case evidence and write the Day 13 deliverables."""
    frame = fetch_latest_ratios(db_path)
    cross_checks = cross_check_returns(frame)
    cagr_events = collect_cagr_edge_cases(db_path)
    debt_free = collect_debt_free_events(db_path)
    zero_counts = collect_zero_denominator_counts(db_path)
    financials_count = financials_company_count(db_path)
    write_sector_roce_notes(frame)
    return write_ratio_edge_cases(
        cross_checks, cagr_events, debt_free, zero_counts, financials_count
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_edge_case_review()