"""CAGR engine with sign and coverage edge-case handling."""

from __future__ import annotations

import logging

import pandas as pd

from src.analytics.ratios import fetch_profitability_inputs, load_ratio_config

logger = logging.getLogger(__name__)

NO_FLAG = ""
DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
TURNAROUND = "TURNAROUND"
BOTH_NEGATIVE = "BOTH_NEGATIVE"
ZERO_BASE = "ZERO_BASE"
INSUFFICIENT = "INSUFFICIENT"

CAGR_METRICS = (("revenue", "sales"), ("pat", "net_profit"), ("eps", "eps"))


def cagr_windows() -> tuple[int, ...]:
    """Return the configured CAGR window lengths in years."""
    return tuple(load_ratio_config()["cagr"]["windows_years"])


def compute_cagr(
    start_value: float | None,
    end_value: float | None,
    years: int,
) -> tuple[float | None, str]:
    """Return CAGR in percent with an edge-case flag for a start/end pair."""
    if start_value is None or end_value is None or years <= 0:
        return None, INSUFFICIENT
    if bool(pd.isna(start_value)) or bool(pd.isna(end_value)):
        return None, INSUFFICIENT
    start = float(start_value)
    end = float(end_value)
    if start == 0:
        return None, ZERO_BASE
    if start > 0 and end < 0:
        return None, DECLINE_TO_LOSS
    if start < 0 and end > 0:
        return None, TURNAROUND
    if start < 0 and end < 0:
        return None, BOTH_NEGATIVE
    return ((end / start) ** (1.0 / years) - 1.0) * 100.0, NO_FLAG


def cagr_ending_at(
    series: pd.Series,
    end_label: str,
    years: int,
) -> tuple[float | None, str]:
    """Return CAGR and flag for a calendar window ending at a year label."""
    if end_label not in series.index:
        return None, INSUFFICIENT
    start_label = f"{int(end_label[:4]) - years}-{end_label[5:7]}"
    if start_label not in series.index:
        return None, INSUFFICIENT
    return compute_cagr(series.loc[start_label], series.loc[end_label], years)


def cagr_from_series(series: pd.Series, years: int) -> tuple[float | None, str]:
    """Return CAGR and flag for a window ending at the latest year of a series."""
    ordered = series.dropna().sort_index()
    if ordered.empty:
        return None, INSUFFICIENT
    return cagr_ending_at(ordered, str(ordered.index[-1]), years)


def compute_cagr_ratios(profit_and_loss: pd.DataFrame) -> pd.DataFrame:
    """Compute revenue, PAT and EPS CAGR columns with flags per company-year."""
    windows = cagr_windows()
    rows: list[dict] = []
    for company_id, company in profit_and_loss.groupby("company_id"):
        series_by_metric = {
            metric: company.set_index("year")[column].dropna().sort_index()
            for metric, column in CAGR_METRICS
        }
        for year in company["year"]:
            row: dict = {"company_id": company_id, "year": year}
            for metric, _ in CAGR_METRICS:
                for window in windows:
                    value, flag = cagr_ending_at(series_by_metric[metric], year, window)
                    row[f"{metric}_cagr_{window}yr"] = value
                    row[f"{metric}_cagr_{window}yr_flag"] = flag
            rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pl_frame, _, _ = fetch_profitability_inputs()
    cagr_frame = compute_cagr_ratios(pl_frame)
    logger.info("Computed CAGR metrics for %d company-years", len(cagr_frame))
