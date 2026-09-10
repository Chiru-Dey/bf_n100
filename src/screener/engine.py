"""Screener filter engine applying threshold rules to the financial universe."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.analytics.ratios import DB_PATH, DEBT_FREE_LABEL

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "screener_config.yaml"
FINANCIALS_SECTOR = "Financials"

METRIC_MAP = {
    "roe_min": ("return_on_equity_pct", ">="),
    "de_max": ("debt_to_equity", "<="),
    "fcf_min": ("free_cash_flow_cr", ">="),
    "revenue_cagr_5yr_min": ("revenue_cagr_5yr", ">="),
    "revenue_cagr_3yr_min": ("revenue_cagr_3yr", ">="),
    "pat_cagr_5yr_min": ("pat_cagr_5yr", ">="),
    "opm_min": ("operating_profit_margin_pct", ">="),
    "pe_max": ("pe_ratio", "<="),
    "pb_max": ("pb_ratio", "<="),
    "dividend_yield_min": ("dividend_yield_pct", ">="),
    "dividend_payout_max": ("dividend_payout_ratio_pct", "<="),
    "icr_min": ("interest_coverage", ">="),
    "market_cap_min": ("market_cap_crore", ">="),
    "net_profit_min": ("net_profit", ">="),
    "eps_cagr_5yr_min": ("eps_cagr_5yr", ">="),
    "asset_turnover_min": ("asset_turnover", ">="),
    "sales_min": ("sales", ">="),
    "de_declining": ("de_declining_flag", "=="),
}

def _latest_annual(frame: pd.DataFrame) -> pd.DataFrame:
    """Return latest March year per company, falling back to company max year."""
    march = frame[frame["year"].astype(str).str.endswith("-03")]
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


def load_screener_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load screener thresholds from the YAML configuration file."""
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_screener_universe(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Join latest-year ratios, market cap, P&L and sectors into one screener frame."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        market_cap = pd.read_sql_query("SELECT * FROM market_cap", conn)
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
        pl = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit FROM profitandloss", conn
        )

    annual = ratios[ratios["year"].astype(str).str.endswith("-03")].copy()
    missing = set(ratios["company_id"]) - set(annual["company_id"])
    if missing:
        fallback = (
            ratios[ratios["company_id"].isin(missing)]
            .sort_values(["company_id", "year"])
            .groupby("company_id")
            .tail(2)
        )
        annual = pd.concat([annual, fallback])
    annual = annual.sort_values(["company_id", "year"])
    annual["de_prev"] = annual.groupby("company_id")["debt_to_equity"].shift(1)
    annual["de_declining_flag"] = (
        annual["debt_to_equity"] < annual["de_prev"]
    ) & annual["de_prev"].notna()
    latest_ratios = annual.groupby("company_id").tail(1)
    latest_mc = market_cap.sort_values("year").groupby("company_id").tail(1)
    latest_pl = _latest_annual(pl)
    universe = latest_ratios.merge(
        latest_mc, on="company_id", how="left", suffixes=("", "_mc")
    )
    universe = universe.merge(
        latest_pl, on="company_id", how="left", suffixes=("", "_pl")
    )
    
    if "net_profit" not in universe.columns:
        universe["net_profit"] = pd.NA
    if "sales" not in universe.columns:
        universe["sales"] = pd.NA
        
    if "net_profit_pl" in universe.columns:
        universe["net_profit"] = universe["net_profit_pl"]
    if "sales_pl" in universe.columns:
        universe["sales"] = universe["sales_pl"]

    universe = universe.merge(sectors, on="company_id", how="left")

    mask_debt_free = universe["icr_label"] == DEBT_FREE_LABEL
    universe.loc[mask_debt_free, "interest_coverage"] = np.inf
    
    return universe


def apply_filters(frame: pd.DataFrame, filters: dict[str, float | bool]) -> pd.DataFrame:
    """Apply threshold filters to the universe, honouring sector carve-outs."""
    if not filters:
        return frame.copy()

    df = frame.copy()
    for key, value in filters.items():
        if key not in METRIC_MAP:
            continue
        column, op = METRIC_MAP[key]
        if column not in df.columns:
            continue

        if key == "de_max":
            mask_financials = df["broad_sector"] == FINANCIALS_SECTOR
            mask_fail = df[column] > value
            df = df[~(~mask_financials & mask_fail)]
        elif op == ">=":
            df = df[df[column] >= value]
        elif op == "<=":
            df = df[df[column] <= value]
        elif op == "==":
            df = df[df[column] == value]

    return df


def run_screener(
    filters: dict[str, float | bool],
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """Build the universe, apply filters, and return results sorted by composite score."""
    universe = build_screener_universe(db_path)
    filtered = apply_filters(universe, filters)
    if "composite_quality_score" in filtered.columns:
        return filtered.sort_values("composite_quality_score", ascending=False)
    return filtered


def run_preset(preset_name: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Run a named preset screener from the configuration file."""
    config = load_screener_config()
    presets = config.get("presets", {})
    if preset_name not in presets:
        raise KeyError(f"Unknown preset: {preset_name}. Available: {list(presets)}")
    return run_screener(presets[preset_name], db_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = load_screener_config()
    
    logger.info("Running all 6 presets...")
    for name in config.get("presets", {}):
        preset_results = run_preset(name)
        logger.info("Preset '%s' returned %d companies", name, len(preset_results))