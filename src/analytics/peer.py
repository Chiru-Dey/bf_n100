"""Peer group percentile ranking engine."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.ratios import DB_PATH

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PEER_GROUPS_PATH = PROJECT_ROOT / "data" / "supporting" / "peer_groups.xlsx"

METRICS_TO_RANK = (
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "pat_cagr_5yr",
    "revenue_cagr_5yr",
    "eps_cagr_5yr",
    "interest_coverage",
    "asset_turnover",
)

INVERTED_METRICS = {"debt_to_equity"}

NULL_LABELS = {"", "NAN", "NONE", "N/A"}

PERCENTILE_COLUMNS = (
    "company_id",
    "company_name",
    "peer_group_name",
    "metric",
    "value",
    "percentile_rank",
    "year",
    "is_benchmark",
)


def _detect_header_row(raw: pd.DataFrame) -> int:
    """Return the index of the first row that looks like a column header."""
    for index, row in raw.head(10).iterrows():
        cells = [str(value).strip().lower() for value in row.tolist()]
        has_group = any("peer" in cell or "group" in cell for cell in cells)
        has_member = any(
            "member" in cell or "company" in cell or cell == "id" for cell in cells
        )
        if has_group and has_member:
            return int(index)
    return 0


def load_peer_groups(path: Path = PEER_GROUPS_PATH) -> pd.DataFrame:
    """Load peer group mappings from the Excel file, normalising layout variants."""
    raw = pd.read_excel(path, header=None)
    header_row = _detect_header_row(raw)
    frame = raw.iloc[header_row + 1 :].copy()
    frame.columns = [
        str(cell).strip().lower().replace(" ", "_") for cell in raw.iloc[header_row]
    ]
    frame = frame.dropna(how="all")

    peer_col = next((c for c in frame.columns if "peer" in c or "group" in c), None)
    company_col = next(
        (c for c in frame.columns if "company" in c or "member" in c or "ticker" in c),
        None,
    )
    benchmark_col = next((c for c in frame.columns if "benchmark" in c), None)

    if not peer_col or not company_col:
        raise ValueError(f"Could not identify peer columns in {frame.columns.tolist()}")

    result = pd.DataFrame(
        {
            "peer_group_name": frame[peer_col].astype(str).str.strip(),
            "company_id": frame[company_col].astype(str).str.strip(),
            "benchmark_label": (
                frame[benchmark_col].astype(str).str.strip() if benchmark_col else ""
            ),
        }
    )
    result = result[~result["company_id"].str.upper().isin(NULL_LABELS)]
    if result["company_id"].str.contains(",").any():
        result = result.assign(
            company_id=result["company_id"].str.split(",")
        ).explode("company_id")
        result["company_id"] = result["company_id"].str.strip()
    result["company_id"] = result["company_id"].str.upper()
    bench = result["benchmark_label"].str.upper()
    result["is_benchmark"] = (bench == result["company_id"]) | bench.isin(
        ["Y", "YES", "1", "TRUE", "X"]
    )
    return result.drop(columns=["benchmark_label"]).dropna(
        subset=["peer_group_name", "company_id"]
    )


def _resolve_peer_company_ids(
    peer_groups: pd.DataFrame, db_path: Path
) -> pd.DataFrame:
    """Map peer member labels to tickers, falling back to company-name matching."""
    with sqlite3.connect(db_path) as conn:
        companies = pd.read_sql_query("SELECT id, company_name FROM companies", conn)
    if peer_groups["company_id"].isin(companies["id"]).any():
        return peer_groups
    name_map = companies.set_index(
        companies["company_name"].astype(str).str.strip().str.upper()
    )["id"]
    resolved = peer_groups.copy()
    resolved["company_id"] = resolved["company_id"].map(name_map).fillna(
        resolved["company_id"]
    )
    logger.warning("Peer member labels resolved via company_name mapping")
    return resolved


def compute_percent_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    """Compute SQL-style PERCENT_RANK: (rank - 1) / (count - 1)."""
    ranks = series.rank(method="average", ascending=ascending, na_option="keep")
    count = int(series.notna().sum())
    if count == 0:
        return pd.Series(float("nan"), index=series.index)
    if count == 1:
        return pd.Series(1.0, index=series.index)
    return (ranks - 1) / (count - 1)

def build_peer_percentiles(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Compute percentile ranks for all metrics across all peer groups."""
    peer_groups = _resolve_peer_company_ids(load_peer_groups(), db_path)

    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        companies = pd.read_sql_query("SELECT id, company_name FROM companies", conn)

    march = ratios[ratios["year"].astype(str).str.endswith("-03")]
    latest_ratios = march.sort_values("year").groupby("company_id").tail(1)
    missing = set(ratios["company_id"]) - set(latest_ratios["company_id"])
    if missing:
        fallback = (
            ratios[ratios["company_id"].isin(missing)]
            .sort_values("year")
            .groupby("company_id")
            .tail(1)
        )
        latest_ratios = pd.concat([latest_ratios, fallback])    
        merged = peer_groups.merge(latest_ratios, on="company_id", how="inner")
    merged = merged.merge(
        companies.rename(columns={"id": "company_id"}), on="company_id", how="left"
    )

    unassigned = set(companies["id"]) - set(peer_groups["company_id"])
    if unassigned:
        logger.info("No peer group assigned for %d companies", len(unassigned))

    rows: list[dict] = []
    for group_name, group_df in merged.groupby("peer_group_name"):
        for metric in METRICS_TO_RANK:
            if metric not in group_df.columns:
                continue
            series = group_df[metric].copy()
            if metric == "interest_coverage":
                series = series.fillna(999999.0)
            pcts = compute_percent_rank(series, ascending=True)
            if metric in INVERTED_METRICS:
                pcts = 1.0 - pcts
            for idx, pct in pcts.items():
                row_data = group_df.loc[idx]
                rows.append(
                    {
                        "company_id": row_data["company_id"],
                        "company_name": row_data.get("company_name", ""),
                        "peer_group_name": group_name,
                        "metric": metric,
                        "value": row_data[metric],
                        "percentile_rank": round(float(pct), 4)
                        if pd.notna(pct)
                        else None,
                        "year": row_data["year"],
                        "is_benchmark": int(bool(row_data.get("is_benchmark", False))),
                    }
                )
    return pd.DataFrame(rows)


def ensure_peer_schema(conn: sqlite3.Connection) -> None:
    """Create peer_percentiles table if it does not exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS peer_percentiles ("
        "company_id TEXT NOT NULL, "
        "company_name TEXT, "
        "peer_group_name TEXT NOT NULL, "
        "metric TEXT NOT NULL, "
        "value REAL, "
        "percentile_rank REAL, "
        "year TEXT, "
        "is_benchmark INTEGER, "
        "PRIMARY KEY (company_id, peer_group_name, metric))"
    )


def write_peer_percentiles(frame: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """Persist peer percentile rankings to the SQLite database."""
    if frame.empty:
        logger.error("Peer percentile frame is empty; table left untouched")
        return 0
    frame = frame.reindex(columns=list(PERCENTILE_COLUMNS))
    with sqlite3.connect(db_path) as conn:
        ensure_peer_schema(conn)
        conn.execute("DELETE FROM peer_percentiles")
        placeholders = ", ".join(["?"] * len(PERCENTILE_COLUMNS))
        col_str = ", ".join(PERCENTILE_COLUMNS)
        records = [
            tuple(
                None if pd.isna(v) else (int(v) if c == "is_benchmark" else v)
                for v, c in zip(row, PERCENTILE_COLUMNS)
            )
            for row in frame.itertuples(index=False, name=None)
        ]
        conn.executemany(
            f"INSERT INTO peer_percentiles ({col_str}) VALUES ({placeholders})",
            records,
        )
        conn.commit()
    logger.info("Wrote %d peer percentile records to database", len(frame))
    return len(frame)


def run_peer_ranking(db_path: Path = DB_PATH) -> int:
    """Execute the full peer ranking pipeline."""
    return write_peer_percentiles(build_peer_percentiles(db_path), db_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_peer_ranking()