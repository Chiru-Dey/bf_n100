"""Profitability, leverage and efficiency ratio computations for the ratio engine."""

from __future__ import annotations

import logging
import os
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "ratio_config.yaml"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
DB_PATH = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH)))

ABOVE_BENCHMARK = "ABOVE_BENCHMARK"
BELOW_BENCHMARK = "BELOW_BENCHMARK"
NO_BENCHMARK = "NO_BENCHMARK"
DEBT_FREE_LABEL = "Debt Free"

_UNIT_ANOMALY_REPORTED: set[str] = set()


@lru_cache(maxsize=1)
def load_ratio_config(path: str = str(DEFAULT_CONFIG_PATH)) -> dict:
    """Load ratio engine thresholds from the YAML configuration file."""
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _is_missing(*values: Optional[float]) -> bool:
    """Return True when any supplied value is None or NaN."""
    return any(value is None or bool(pd.isna(value)) for value in values)


def is_financials_sector(broad_sector: str) -> bool:
    """Return True when the sector matches the configured Financials broad sector."""
    return broad_sector == load_ratio_config()["financials_sector"]


def net_profit_margin(net_profit: float, sales: float) -> Optional[float]:
    """Return net profit margin in percent, or None when sales is zero."""
    if _is_missing(net_profit, sales) or sales == 0:
        return None
    return net_profit / sales * 100.0


def operating_profit_margin(
    operating_profit: float,
    sales: float,
    source_opm_pct: Optional[float] = None,
    tolerance_pct: Optional[float] = None,
    company_id: str = "",
    year: str = "",
) -> Optional[float]:
    """Return computed operating margin and log source divergence above tolerance."""
    if _is_missing(operating_profit, sales) or sales == 0:
        return None
    computed_pct = operating_profit / sales * 100.0
    if not _is_missing(source_opm_pct):
        config = load_ratio_config()["opm"]
        limit = (
            config["cross_check_tolerance_pct"]
            if tolerance_pct is None
            else tolerance_pct
        )
        source_value = float(source_opm_pct)
        if abs(source_value) > float(config["max_plausible_pct"]):
            if company_id not in _UNIT_ANOMALY_REPORTED:
                _UNIT_ANOMALY_REPORTED.add(company_id)
                logger.warning(
                    "OPM source unit anomaly for %s: opm_percentage=%s not in "
                    "percentage units; cross-check suppressed",
                    company_id,
                    source_value,
                )
        else:
            divergence = abs(computed_pct - source_value)
            if divergence > limit:
                logger.warning(
                    "OPM cross-check divergence %.2f pct for %s %s: "
                    "computed=%.2f source=%.2f",
                    divergence,
                    company_id,
                    year,
                    computed_pct,
                    source_value,
                )
    return computed_pct


def return_on_equity(
    net_profit: float,
    equity_capital: float,
    reserves: float,
) -> Optional[float]:
    """Return return on equity in percent, or None when total equity is not positive."""
    if _is_missing(net_profit, equity_capital, reserves):
        return None
    equity = equity_capital + reserves
    if equity <= 0:
        return None
    return net_profit / equity * 100.0


def return_on_capital_employed(
    operating_profit: float,
    depreciation: float,
    equity_capital: float,
    reserves: float,
    borrowings: float,
) -> Optional[float]:
    """Return ROCE in percent using EBIT over capital employed, None if not positive."""
    if _is_missing(operating_profit, depreciation, equity_capital, reserves, borrowings):
        return None
    capital_employed = equity_capital + reserves + borrowings
    if capital_employed <= 0:
        return None
    ebit = operating_profit - depreciation
    return ebit / capital_employed * 100.0


def return_on_assets(net_profit: float, total_assets: float) -> Optional[float]:
    """Return return on assets in percent, or None when total assets is zero."""
    if _is_missing(net_profit, total_assets) or total_assets == 0:
        return None
    return net_profit / total_assets * 100.0


def roce_benchmark_pct(
    broad_sector: str,
    sector_median_roce_pct: Optional[float],
) -> Optional[float]:
    """Return sector median benchmark for Financials else the absolute threshold."""
    if is_financials_sector(broad_sector):
        return sector_median_roce_pct
    return float(load_ratio_config()["roce"]["absolute_threshold_pct"])


def evaluate_roce(
    roce_pct: Optional[float],
    broad_sector: str,
    sector_median_roce_pct: Optional[float],
) -> str:
    """Return the ROCE benchmark label for a company within its sector context."""
    benchmark = roce_benchmark_pct(broad_sector, sector_median_roce_pct)
    if _is_missing(roce_pct) or benchmark is None or bool(pd.isna(benchmark)):
        return NO_BENCHMARK
    return ABOVE_BENCHMARK if roce_pct >= benchmark else BELOW_BENCHMARK


def debt_to_equity(
    borrowings: float,
    equity_capital: float,
    reserves: float,
) -> Optional[float]:
    """Return D/E ratio, 0.0 for debt-free companies, None if equity not positive."""
    if _is_missing(borrowings, equity_capital, reserves):
        return None
    if borrowings == 0:
        return 0.0
    equity = equity_capital + reserves
    if equity <= 0:
        return None
    return borrowings / equity


def high_leverage_flag(de_ratio: Optional[float], broad_sector: str) -> bool:
    """Return True when D/E exceeds the threshold for a non-Financials company."""
    if _is_missing(de_ratio) or is_financials_sector(broad_sector):
        return False
    threshold = float(load_ratio_config()["leverage"]["high_de_threshold"])
    return bool(de_ratio > threshold)


def interest_coverage(
    operating_profit: float,
    other_income: Optional[float],
    interest: float,
) -> Optional[float]:
    """Return interest coverage ratio, or None when interest is zero."""
    if _is_missing(operating_profit, interest) or interest == 0:
        return None
    income = 0.0 if _is_missing(other_income) else float(other_income)
    return (float(operating_profit) + income) / float(interest)


def icr_label(interest: Optional[float]) -> str:
    """Return the Debt Free display label when interest is zero, else empty string."""
    if not _is_missing(interest) and interest == 0:
        return DEBT_FREE_LABEL
    return ""


def icr_warning_flag(icr: Optional[float]) -> bool:
    """Return True when interest coverage falls below the warning threshold."""
    if _is_missing(icr):
        return False
    threshold = float(load_ratio_config()["leverage"]["icr_warning_threshold"])
    return bool(icr < threshold)


def net_debt(borrowings: float, investments: Optional[float]) -> Optional[float]:
    """Return net debt as borrowings less investments, missing investments as zero."""
    if _is_missing(borrowings):
        return None
    invested = 0.0 if _is_missing(investments) else float(investments)
    return float(borrowings) - invested


def asset_turnover(sales: float, total_assets: float) -> Optional[float]:
    """Return asset turnover ratio, or None when total assets is zero."""
    if _is_missing(sales, total_assets) or total_assets == 0:
        return None
    return sales / total_assets


def _merge_inputs(
    profit_and_loss: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    sectors: pd.DataFrame,
) -> pd.DataFrame:
    """Merge P&L, balance sheet and sector frames on company and year keys."""
    merged = profit_and_loss.merge(
        balance_sheet, on=["company_id", "year"], how="outer", suffixes=("_pl", "_bs")
    )
    return merged.merge(
        sectors[["company_id", "broad_sector"]], on="company_id", how="left"
    )


def compute_profitability_ratios(
    profit_and_loss: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    sectors: pd.DataFrame,
) -> pd.DataFrame:
    """Compute profitability KPIs for every company-year in P&L and balance sheet."""
    merged = _merge_inputs(profit_and_loss, balance_sheet, sectors)
    merged["net_profit_margin_pct"] = merged.apply(
        lambda row: net_profit_margin(row["net_profit"], row["sales"]), axis=1
    )
    merged["operating_profit_margin_pct"] = merged.apply(
        lambda row: operating_profit_margin(
            row["operating_profit"],
            row["sales"],
            row["opm_percentage"],
            company_id=row["company_id"],
            year=row["year"],
        ),
        axis=1,
    )
    merged["return_on_equity_pct"] = merged.apply(
        lambda row: return_on_equity(
            row["net_profit"], row["equity_capital"], row["reserves"]
        ),
        axis=1,
    )
    merged["return_on_capital_employed_pct"] = merged.apply(
        lambda row: return_on_capital_employed(
            row["operating_profit"],
            row["depreciation"],
            row["equity_capital"],
            row["reserves"],
            row["borrowings"],
        ),
        axis=1,
    )
    merged["return_on_assets_pct"] = merged.apply(
        lambda row: return_on_assets(row["net_profit"], row["total_assets"]), axis=1
    )
    sector_medians = (
        merged.groupby(["broad_sector", "year"])["return_on_capital_employed_pct"]
        .median()
        .rename("sector_median_roce_pct")
        .reset_index()
    )
    merged = merged.merge(sector_medians, on=["broad_sector", "year"], how="left")
    merged["roce_benchmark_flag"] = merged.apply(
        lambda row: evaluate_roce(
            row["return_on_capital_employed_pct"],
            row["broad_sector"],
            row["sector_median_roce_pct"],
        ),
        axis=1,
    )
    return merged


def compute_leverage_ratios(
    profit_and_loss: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    sectors: pd.DataFrame,
) -> pd.DataFrame:
    """Compute leverage and efficiency KPIs for every company-year."""
    merged = _merge_inputs(profit_and_loss, balance_sheet, sectors)
    merged["debt_to_equity"] = merged.apply(
        lambda row: debt_to_equity(
            row["borrowings"], row["equity_capital"], row["reserves"]
        ),
        axis=1,
    )
    merged["high_leverage_flag"] = merged.apply(
        lambda row: high_leverage_flag(row["debt_to_equity"], row["broad_sector"]),
        axis=1,
    )
    merged["interest_coverage"] = merged.apply(
        lambda row: interest_coverage(
            row["operating_profit"], row["other_income"], row["interest"]
        ),
        axis=1,
    )
    merged["icr_label"] = merged.apply(lambda row: icr_label(row["interest"]), axis=1)
    merged["icr_warning_flag"] = merged.apply(
        lambda row: icr_warning_flag(row["interest_coverage"]), axis=1
    )
    merged["net_debt_cr"] = merged.apply(
        lambda row: net_debt(row["borrowings"], row["investments"]), axis=1
    )
    merged["asset_turnover"] = merged.apply(
        lambda row: asset_turnover(row["sales"], row["total_assets"]), axis=1
    )
    return merged


def fetch_profitability_inputs(
    db_path: Path = DB_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read P&L, balance sheet and sector tables from the SQLite database."""
    with sqlite3.connect(db_path) as conn:
        profit_and_loss = pd.read_sql_query("SELECT * FROM profitandloss", conn)
        balance_sheet = pd.read_sql_query("SELECT * FROM balancesheet", conn)
        sectors = pd.read_sql_query("SELECT * FROM sectors", conn)
    return profit_and_loss, balance_sheet, sectors


if __name__ == "__main__":
    from src.analytics.engine import run_engine

    logging.basicConfig(level=logging.INFO)
    run_engine()