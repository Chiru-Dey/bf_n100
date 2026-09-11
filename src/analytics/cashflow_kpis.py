"""Cash flow KPIs, CFO quality and capital allocation pattern classification."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from src.analytics.ratios import DB_PATH, load_ratio_config

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "output" / "capital_allocation.csv"

REINVESTOR = "Reinvestor"
SHAREHOLDER_RETURNS = "Shareholder Returns"
LIQUIDATING_ASSETS = "Liquidating Assets"
DISTRESS_SIGNAL = "Distress Signal"
GROWTH_FUNDED_BY_DEBT = "Growth Funded by Debt"
CASH_ACCUMULATOR = "Cash Accumulator"
PRE_REVENUE = "Pre-Revenue"
MIXED = "Mixed"
INSUFFICIENT_DATA = "Insufficient Data"

HIGH_QUALITY = "High Quality"
MODERATE = "Moderate"
ACCRUAL_RISK = "Accrual Risk"
ASSET_LIGHT = "Asset Light"
CAPITAL_INTENSIVE = "Capital Intensive"
NO_DATA = "N/A"

POSITIVE = "+"
NEGATIVE = "-"
UNKNOWN = "?"

PATTERN_MAP = {
    (True, True, True): CASH_ACCUMULATOR,
    (True, True, False): LIQUIDATING_ASSETS,
    (True, False, True): MIXED,
    (False, True, True): DISTRESS_SIGNAL,
    (False, True, False): LIQUIDATING_ASSETS,
    (False, False, True): GROWTH_FUNDED_BY_DEBT,
    (False, False, False): PRE_REVENUE,
}

OUTPUT_COLUMNS = (
    "company_id",
    "year",
    "cfo_sign",
    "cfi_sign",
    "cff_sign",
    "pattern_label",
)


def _is_missing(*values: float | None) -> bool:
    """Return True when any supplied value is None or NaN."""
    return any(value is None or bool(pd.isna(value)) for value in values)


def _cashflow_config() -> dict:
    """Return the cash flow section of the ratio configuration."""
    return load_ratio_config()["cashflow"]


def resolve_cashflow_columns(frame: pd.DataFrame) -> dict[str, str]:
    """Map logical cash flow fields to the first matching column alias present."""
    aliases = _cashflow_config()["columns"]
    resolved = {}
    for logical, candidates in aliases.items():
        for candidate in candidates:
            if candidate in frame.columns:
                resolved[logical] = candidate
                break
    missing = sorted(set(aliases) - set(resolved))
    if missing:
        raise KeyError(
            f"Missing cashflow columns {missing}; available: {frame.columns.tolist()}"
        )
    return resolved


def free_cash_flow(cfo: float | None, cfi: float | None) -> float | None:
    """Return free cash flow as CFO plus investing flow, negative allowed."""
    if _is_missing(cfo, cfi):
        return None
    return float(cfo) + float(cfi)


def cfo_pat_ratio(cfo: float | None, net_profit: float | None) -> float | None:
    """Return CFO over PAT, or None when PAT is zero."""
    if _is_missing(cfo, net_profit) or net_profit == 0:
        return None
    return float(cfo) / float(net_profit)


def cfo_quality_score(ratios: Sequence[float | None]) -> float | None:
    """Return trailing five-year mean CFO/PAT, None when current year PAT is zero."""
    if not ratios or ratios[-1] is None:
        return None
    valid = [value for value in ratios if value is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def cfo_quality_label(score: float | None) -> str:
    """Return the CFO quality band label for a five-year score."""
    if score is None or bool(pd.isna(score)):
        return NO_DATA
    config = _cashflow_config()
    if score > float(config["cfo_quality_high"]):
        return HIGH_QUALITY
    if score >= float(config["cfo_quality_moderate"]):
        return MODERATE
    return ACCRUAL_RISK


def capex_intensity_pct(cfi: float | None, sales: float | None) -> float | None:
    """Return CapEx intensity as abs investing flow over sales in percent."""
    if _is_missing(cfi, sales) or sales == 0:
        return None
    return abs(float(cfi)) / float(sales) * 100.0


def capex_label(intensity: float | None) -> str:
    """Return the CapEx intensity band label for a percentage value."""
    if intensity is None or bool(pd.isna(intensity)):
        return NO_DATA
    config = _cashflow_config()
    if intensity < float(config["capex_light_pct"]):
        return ASSET_LIGHT
    if intensity <= float(config["capex_intensive_pct"]):
        return MODERATE
    return CAPITAL_INTENSIVE


def fcf_conversion_pct(
    fcf: float | None, operating_profit: float | None
) -> float | None:
    """Return FCF conversion as FCF over operating profit in percent."""
    if _is_missing(fcf, operating_profit) or operating_profit == 0:
        return None
    return float(fcf) / float(operating_profit) * 100.0


def cash_flow_sign(value: float | None) -> str:
    """Return the +, - or ? sign label for a cash flow value."""
    if _is_missing(value):
        return UNKNOWN
    return POSITIVE if float(value) > 0 else NEGATIVE


def classify_capital_allocation(
    cfo: float | None,
    cfi: float | None,
    cff: float | None,
    score: float | None = None,
) -> str:
    """Return the capital allocation pattern label from CFO/CFI/CFF signs."""
    if _is_missing(cfo, cfi, cff):
        return INSUFFICIENT_DATA
    key = (float(cfo) > 0, float(cfi) > 0, float(cff) > 0)
    if key == (True, False, False):
        threshold = float(_cashflow_config()["shareholder_returns_cfo_pat_min"])
        if score is not None and not bool(pd.isna(score)) and score > threshold:
            return SHAREHOLDER_RETURNS
        return REINVESTOR
    return PATTERN_MAP[key]


def _quality_scores(frame: pd.DataFrame) -> pd.Series:
    """Return trailing five-year CFO/PAT scores aligned to the frame index."""
    scores: dict = {}
    for _, company in frame.groupby("company_id"):
        ordered = company.sort_values("year")
        ratios = list(ordered["cfo_pat_ratio"])
        for offset, index in enumerate(ordered.index):
            window = ratios[max(0, offset - 4) : offset + 1]
            scores[index] = cfo_quality_score(window)
    return pd.Series(scores, dtype="float64")


def compute_cashflow_kpis(
    cashflow: pd.DataFrame, profit_and_loss: pd.DataFrame
) -> pd.DataFrame:
    """Compute cash flow KPIs and allocation pattern per company-year."""
    resolved = resolve_cashflow_columns(cashflow)
    frame = cashflow.rename(
        columns={source: logical for logical, source in resolved.items()}
    )
    merged = frame.merge(
        profit_and_loss[
            ["company_id", "year", "sales", "net_profit", "operating_profit"]
        ],
        on=["company_id", "year"],
        how="left",
        suffixes=("", "_pl"),
    )
    merged["free_cash_flow_cr"] = merged.apply(
        lambda row: free_cash_flow(row["cfo"], row["cfi"]), axis=1
    )
    merged["capex_cr"] = merged["cfi"].abs()
    merged["cash_from_operations_cr"] = merged["cfo"]
    merged["cfo_pat_ratio"] = merged.apply(
        lambda row: cfo_pat_ratio(row["cfo"], row["net_profit"]), axis=1
    )
    merged["cfo_quality_score"] = _quality_scores(merged)
    merged["cfo_quality_label"] = merged["cfo_quality_score"].map(cfo_quality_label)
    merged["capex_intensity_pct"] = merged.apply(
        lambda row: capex_intensity_pct(row["cfi"], row["sales"]), axis=1
    )
    merged["capex_label"] = merged["capex_intensity_pct"].map(capex_label)
    merged["fcf_conversion_pct"] = merged.apply(
        lambda row: fcf_conversion_pct(
            row["free_cash_flow_cr"], row["operating_profit"]
        ),
        axis=1,
    )
    merged["cfo_sign"] = merged["cfo"].map(cash_flow_sign)
    merged["cfi_sign"] = merged["cfi"].map(cash_flow_sign)
    merged["cff_sign"] = merged["cff"].map(cash_flow_sign)
    merged["pattern_label"] = merged.apply(
        lambda row: classify_capital_allocation(
            row["cfo"], row["cfi"], row["cff"], row["cfo_quality_score"]
        ),
        axis=1,
    )
    return merged


def write_capital_allocation(frame: pd.DataFrame, path: Path = OUTPUT_PATH) -> Path:
    """Write the capital allocation deliverable CSV and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame[list(OUTPUT_COLUMNS)].to_csv(path, index=False)
    logger.info("Wrote capital allocation for %d company-years to %s", len(frame), path)
    return path


def fetch_cashflow_inputs(
    db_path: Path = DB_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read cash flow and P&L tables from the SQLite database."""
    with sqlite3.connect(db_path) as conn:
        cashflow = pd.read_sql_query("SELECT * FROM cashflow", conn)
        profit_and_loss = pd.read_sql_query("SELECT * FROM profitandloss", conn)
    return cashflow, profit_and_loss


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cf_frame, pl_frame = fetch_cashflow_inputs()
    kpis = compute_cashflow_kpis(cf_frame, pl_frame)
    write_capital_allocation(kpis)
    logger.info(
        "Pattern distribution:\n%s", kpis["pattern_label"].value_counts().to_string()
    )
