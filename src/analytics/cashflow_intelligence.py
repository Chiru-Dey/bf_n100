"""Cash flow intelligence: CFO quality, CapEx intensity, distress and deleveraging."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cagr import cagr_ending_at
from src.analytics.cashflow_kpis import (
    capex_intensity_pct,
    capex_label,
    cfo_pat_ratio,
    cfo_quality_label,
    cfo_quality_score,
    classify_capital_allocation,
    fcf_conversion_pct,
    resolve_cashflow_columns,
)
from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "output" / "cashflow_intelligence.xlsx"
ALERTS_PATH = PROJECT_ROOT / "output" / "distress_alerts.csv"

OUTPUT_COLUMNS = (
    "company_id",
    "sector",
    "cfo_quality_score",
    "cfo_quality_label",
    "capex_intensity_pct",
    "capex_label",
    "fcf_cagr_5yr",
    "fcf_conversion_pct",
    "distress_flag",
    "deleveraging_flag",
    "capital_allocation_label",
)

ALERT_COLUMNS = (
    "company_id",
    "sector",
    "year",
    "cfo",
    "cff",
    "net_profit",
    "capital_allocation_label",
)


def _round(value: float | None) -> float | None:
    """Round a value to two decimals, preserving None."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), 2)


def fetch_intelligence_inputs(
    db_path: Path = DB_PATH,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Return per-company cash flow histories and the sector map."""
    with sqlite3.connect(db_path) as conn:
        cashflow = pd.read_sql_query("SELECT * FROM cashflow", conn)
        pl = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit, operating_profit "
            "FROM profitandloss",
            conn,
        )
        bs = pd.read_sql_query(
            "SELECT company_id, year, borrowings FROM balancesheet", conn
        )
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
    resolved = resolve_cashflow_columns(cashflow)
    frame = cashflow.rename(
        columns={source: logical for logical, source in resolved.items()}
    )
    frame = frame.merge(pl, on=["company_id", "year"], how="left")
    frame = frame.merge(bs, on=["company_id", "year"], how="left")
    frame["fcf"] = frame["cfo"] + frame["cfi"]
    histories = {
        company_id: group.sort_values("year")
        for company_id, group in frame.groupby("company_id")
    }
    sector_map = dict(zip(sectors["company_id"], sectors["broad_sector"]))
    return histories, sector_map


def cfo_quality(hist: pd.DataFrame) -> tuple[float | None, str]:
    """Return the 5-year average CFO/PAT score and its quality label."""
    ratios = [
        cfo_pat_ratio(row["cfo"], row["net_profit"])
        for _, row in hist.tail(5).iterrows()
    ]
    score = cfo_quality_score(ratios)
    return score, cfo_quality_label(score)


def fcf_cagr_5yr(hist: pd.DataFrame) -> float | None:
    """Return 5-year FCF CAGR at the latest year, None when not computable."""
    series = hist.set_index("year")["fcf"].dropna().sort_index()
    if series.empty:
        return None
    value, _ = cagr_ending_at(series, str(series.index[-1]), 5)
    return value


def distress_flag(hist: pd.DataFrame) -> bool:
    """Return True when the latest year shows negative CFO and positive CFF."""
    latest = hist.tail(1)
    if latest.empty:
        return False
    row = latest.iloc[0]
    if pd.isna(row["cfo"]) or pd.isna(row["cff"]):
        return False
    return float(row["cfo"]) < 0.0 and float(row["cff"]) > 0.0


def deleveraging_flag(hist: pd.DataFrame) -> bool:
    """Return True when latest CFF is negative and borrowings declined YoY."""
    latest = hist.tail(1)
    if latest.empty:
        return False
    row = latest.iloc[0]
    borrowings = hist["borrowings"].dropna()
    if pd.isna(row["cff"]) or float(row["cff"]) >= 0.0 or len(borrowings) < 2:
        return False
    last_two = borrowings.tail(2).tolist()
    return float(last_two[1]) < float(last_two[0])


def evaluate_company(company_id: str, sector: str, hist: pd.DataFrame) -> dict:
    """Return the cash flow intelligence record for one company history."""
    latest = hist.tail(1).iloc[0]
    score, quality = cfo_quality(hist)
    intensity = capex_intensity_pct(latest["cfi"], latest["sales"])
    conversion = fcf_conversion_pct(latest["fcf"], latest["operating_profit"])
    return {
        "company_id": company_id,
        "sector": sector,
        "cfo_quality_score": _round(score),
        "cfo_quality_label": quality,
        "capex_intensity_pct": _round(intensity),
        "capex_label": capex_label(intensity),
        "fcf_cagr_5yr": _round(fcf_cagr_5yr(hist)),
        "fcf_conversion_pct": _round(conversion),
        "distress_flag": distress_flag(hist),
        "deleveraging_flag": deleveraging_flag(hist),
        "capital_allocation_label": classify_capital_allocation(
            latest["cfo"], latest["cfi"], latest["cff"], score
        ),
    }


def build_cashflow_intelligence(
    db_path: Path = DB_PATH,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Return the intelligence frame and per-company histories."""
    histories, sector_map = fetch_intelligence_inputs(db_path)
    rows = [
        evaluate_company(company_id, sector_map.get(company_id, ""), hist)
        for company_id, hist in histories.items()
    ]
    frame = pd.DataFrame(rows, columns=list(OUTPUT_COLUMNS))
    return frame.sort_values("company_id").reset_index(drop=True), histories


def build_distress_alerts(
    frame: pd.DataFrame, histories: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Return distress-flagged companies with supporting cash flow values."""
    rows = []
    for _, record in frame[frame["distress_flag"]].iterrows():
        latest = histories[record["company_id"]].tail(1).iloc[0]
        rows.append(
            {
                "company_id": record["company_id"],
                "sector": record["sector"],
                "year": latest["year"],
                "cfo": latest["cfo"],
                "cff": latest["cff"],
                "net_profit": latest["net_profit"],
                "capital_allocation_label": record["capital_allocation_label"],
            }
        )
    return pd.DataFrame(rows, columns=list(ALERT_COLUMNS))


def run_cashflow_intelligence(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Build and persist the cash flow intelligence deliverables."""
    frame, histories = build_cashflow_intelligence(db_path)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(OUTPUT_PATH, index=False)
    alerts = build_distress_alerts(frame, histories)
    alerts.to_csv(ALERTS_PATH, index=False)
    logger.info(
        "Wrote %d intelligence rows and %d distress alerts", len(frame), len(alerts)
    )
    return frame


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_cashflow_intelligence()
