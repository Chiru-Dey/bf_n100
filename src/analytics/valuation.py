"""Valuation module: FCF yield, sector-relative P/E flags and export files."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

from src.analytics.ratios import DB_PATH, load_ratio_config

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = PROJECT_ROOT / "output" / "valuation_summary.xlsx"
FLAGS_PATH = PROJECT_ROOT / "output" / "valuation_flags.csv"

CAUTION = "Caution"
DISCOUNT = "Discount"
FAIR = "Fair"

SUMMARY_COLUMNS = (
    "company_id",
    "company_name",
    "sector",
    "P/E",
    "P/B",
    "EV/EBITDA",
    "FCF_yield_pct",
    "5yr_median_PE",
    "PE_vs_sector_median_pct",
    "flag",
)


def fcf_yield(
    fcf_cr: Optional[float], market_cap_cr: Optional[float]
) -> Optional[float]:
    """Return free cash flow yield in percent, or None when market cap is zero."""
    if fcf_cr is None or market_cap_cr is None:
        return None
    if pd.isna(fcf_cr) or pd.isna(market_cap_cr) or market_cap_cr == 0:
        return None
    return float(fcf_cr) / float(market_cap_cr) * 100.0


def valuation_flag(pe: Optional[float], sector_median_pe: Optional[float]) -> str:
    """Return Caution, Discount or Fair from P/E versus sector median bands."""
    if pe is None or sector_median_pe is None:
        return FAIR
    if pd.isna(pe) or pd.isna(sector_median_pe):
        return FAIR
    config = load_ratio_config()["valuation"]
    if float(pe) > float(sector_median_pe) * float(config["caution_multiplier"]):
        return CAUTION
    if float(pe) < float(sector_median_pe) * float(config["discount_multiplier"]):
        return DISCOUNT
    return FAIR


def fetch_valuation_inputs(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return latest-year company snapshot joined with market cap multiples."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        market_cap = pd.read_sql_query("SELECT * FROM market_cap", conn)
        companies = pd.read_sql_query("SELECT id, company_name FROM companies", conn)
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
    latest_mc = market_cap.sort_values("year").groupby("company_id").tail(1)
    median_pe = (
        market_cap.groupby("company_id")["pe_ratio"].median().rename("5yr_median_pe")
    )
    frame = latest.merge(latest_mc, on="company_id", how="left", suffixes=("", "_mc"))
    frame = frame.merge(median_pe, on="company_id", how="left")
    frame = frame.merge(
        companies.rename(columns={"id": "company_id"}), on="company_id", how="left"
    )
    return frame.merge(sectors, on="company_id", how="left")


def build_valuation_summary(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return the 92-company valuation summary with sector-relative flags."""
    frame = fetch_valuation_inputs(db_path)
    frame["fcf_yield_pct"] = frame.apply(
        lambda row: fcf_yield(row["free_cash_flow_cr"], row["market_cap_crore"]),
        axis=1,
    )
    sector_medians = (
        frame.groupby("broad_sector")["pe_ratio"].median().rename("sector_median_pe")
    )
    frame = frame.merge(sector_medians, on="broad_sector", how="left")
    frame["pe_vs_sector_median_pct"] = (
        (frame["pe_ratio"] - frame["sector_median_pe"])
        / frame["sector_median_pe"]
        * 100.0
    )
    frame["flag"] = frame.apply(
        lambda row: valuation_flag(row["pe_ratio"], row["sector_median_pe"]), axis=1
    )
    summary = frame.rename(
        columns={
            "broad_sector": "sector",
            "pe_ratio": "P/E",
            "pb_ratio": "P/B",
            "ev_ebitda": "EV/EBITDA",
            "5yr_median_pe": "5yr_median_PE",
            "fcf_yield_pct": "FCF_yield_pct",
            "pe_vs_sector_median_pct": "PE_vs_sector_median_pct",
        }
    )
    return summary[list(SUMMARY_COLUMNS)]


def write_valuation_outputs(
    frame: pd.DataFrame,
    summary_path: Path = SUMMARY_PATH,
    flags_path: Path = FLAGS_PATH,
) -> tuple[Path, Path]:
    """Write valuation_summary.xlsx and valuation_flags.csv, returning paths."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(summary_path, index=False)
    flags = frame[frame["flag"].isin([CAUTION, DISCOUNT])]
    flags.to_csv(flags_path, index=False)
    logger.info("Wrote %d valuation rows and %d flagged rows", len(frame), len(flags))
    return summary_path, flags_path


def run_valuation(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Build and persist the valuation summary, returning the summary frame."""
    frame = build_valuation_summary(db_path)
    write_valuation_outputs(frame)
    return frame


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_valuation()
    logger.info("Flag distribution:\n%s", result["flag"].value_counts().to_string())