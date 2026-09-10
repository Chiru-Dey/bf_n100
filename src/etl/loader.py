from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.etl.normaliser import (
    MISSING,
    PARSE_ERROR,
    TICKER_MAX_LENGTH,
    TICKER_MIN_LENGTH,
    normalize_ticker,
    normalize_year,
    repair_pl_column_rotation,
)
from src.settings import get_settings

logger = logging.getLogger(__name__)

CORE_HEADER = 1
SUPPORTING_HEADER = 0

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

CORE_FILES = {
    "companies": "companies.xlsx",
    "profitandloss": "profitandloss.xlsx",
    "balancesheet": "balancesheet.xlsx",
    "cashflow": "cashflow.xlsx",
    "analysis": "analysis.xlsx",
    "documents": "documents.xlsx",
    "prosandcons": "prosandcons.xlsx",
}

SUPPORTING_FILES = {
    "sectors": "sectors.xlsx",
    "stock_prices": "stock_prices.xlsx",
    "market_cap": "market_cap.xlsx",
    "financial_ratios": "financial_ratios.xlsx",
    "peer_groups": "peer_groups.xlsx",
}

PERSISTED_SUPPORTING = ("sectors", "stock_prices", "market_cap")

REFERENCE_ONLY_TABLES = ("financial_ratios", "peer_groups")

REFERENCE_ONLY_NOTES = {
    "financial_ratios": "reference-only: repopulated by Ratio Engine in Sprint 2",
    "peer_groups": "reference-only: consumed by Peer Engine in Sprint 3",
}

TICKER_COLUMNS = {
    "companies": "id",
    "profitandloss": "company_id",
    "balancesheet": "company_id",
    "cashflow": "company_id",
    "analysis": "company_id",
    "documents": "company_id",
    "prosandcons": "company_id",
}

YEAR_COLUMNS = {
    "profitandloss": "year",
    "balancesheet": "year",
    "cashflow": "year",
}

UNIQUE_KEYS = {
    "analysis": ("company_id",),
    "documents": ("company_id", "Year"),
    "prosandcons": ("id",),
    "stock_prices": ("company_id", "date"),
    "market_cap": ("company_id", "year"),
}

LOAD_ORDER = (
    "companies",
    "sectors",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "analysis",
    "documents",
    "prosandcons",
    "stock_prices",
    "market_cap",
)

AUDIT_COLUMNS = (
    "source_file",
    "table",
    "rows_in",
    "rows_out",
    "rejected",
    "timestamp",
    "runtime_s",
    "note",
)

TABLE_COLUMNS = {
    "companies": (
        "id",
        "company_logo",
        "company_name",
        "chart_link",
        "about_company",
        "website",
        "nse_profile",
        "bse_profile",
        "face_value",
        "book_value",
        "roce_percentage",
        "roe_percentage",
    ),
    "profitandloss": (
        "id",
        "company_id",
        "year",
        "sales",
        "expenses",
        "operating_profit",
        "opm_percentage",
        "other_income",
        "interest",
        "depreciation",
        "profit_before_tax",
        "tax_percentage",
        "net_profit",
        "eps",
        "dividend_payout",
    ),
    "balancesheet": (
        "id",
        "company_id",
        "year",
        "equity_capital",
        "reserves",
        "borrowings",
        "other_liabilities",
        "total_liabilities",
        "fixed_assets",
        "cwip",
        "investments",
        "other_asset",
        "total_assets",
    ),
    "cashflow": (
        "id",
        "company_id",
        "year",
        "operating_activity",
        "investing_activity",
        "financing_activity",
        "net_cash_flow",
    ),
    "analysis": (
        "id",
        "company_id",
        "compounded_sales_growth",
        "compounded_profit_growth",
        "stock_price_cagr",
        "roe",
    ),
    "documents": ("id", "company_id", "Year", "Annual_Report"),
    "prosandcons": ("id", "company_id", "pros", "cons"),
    "sectors": (
        "company_id",
        "broad_sector",
        "sub_sector",
        "index_weight_pct",
        "market_cap_category",
    ),
    "stock_prices": (
        "company_id",
        "date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "adjusted_close",
    ),
    "market_cap": (
        "company_id",
        "year",
        "market_cap_crore",
        "enterprise_value_crore",
        "pe_ratio",
        "pb_ratio",
        "ev_ebitda",
        "dividend_yield_pct",
    ),
}

NUMERIC_COLUMNS = {
    "companies": (
        "face_value",
        "book_value",
        "roce_percentage",
        "roe_percentage",
    ),
    "profitandloss": (
        "sales",
        "expenses",
        "operating_profit",
        "opm_percentage",
        "other_income",
        "interest",
        "depreciation",
        "profit_before_tax",
        "tax_percentage",
        "net_profit",
        "eps",
        "dividend_payout",
    ),
    "balancesheet": (
        "equity_capital",
        "reserves",
        "borrowings",
        "other_liabilities",
        "total_liabilities",
        "fixed_assets",
        "cwip",
        "investments",
        "other_asset",
        "total_assets",
    ),
    "cashflow": (
        "operating_activity",
        "investing_activity",
        "financing_activity",
        "net_cash_flow",
    ),
    "analysis": ("id",),
    "documents": ("id", "Year"),
    "prosandcons": ("id",),
}

TEXT_COLUMNS = {
    "companies": ("company_name", "about_company"),
}


def read_excel(path: Path, header: int) -> pd.DataFrame:
    """Read an Excel worksheet into a DataFrame, logging read failures."""
    try:
        return pd.read_excel(path, header=header)
    except Exception:
        logger.exception("Failed to read %s", path)
        return pd.DataFrame()


def clean_text(value: object) -> str | None:
    """Collapse embedded whitespace in free-text fields."""
    if pd.isna(value):
        return None
    return " ".join(str(value).split())


def normalize_frame(
    df: pd.DataFrame,
    ticker_column: str | None,
    year_column: str | None,
) -> pd.DataFrame:
    """Normalise ticker and year columns of a raw DataFrame."""
    frame = df.copy()
    if ticker_column and ticker_column in frame.columns:
        frame[ticker_column] = frame[ticker_column].map(normalize_ticker)
    if year_column and year_column in frame.columns:
        raw = frame[year_column]
        mapped = raw.map(normalize_year)
        unparseable = raw[mapped == PARSE_ERROR]
        if not unparseable.empty:
            logger.warning(
                "Unparseable year values in %s: %s",
                year_column,
                unparseable.tolist(),
            )
        frame[year_column] = mapped
    return frame


def coerce_numeric(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    """Coerce declared numeric columns to numeric dtype."""
    frame = df.copy()
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_core_table(name: str) -> pd.DataFrame:
    """Load and normalise one core Excel dataset by table name."""
    path = get_settings().raw_data_dir / CORE_FILES[name]
    frame = read_excel(path, CORE_HEADER)
    if frame.empty:
        return frame
    frame = normalize_frame(
        frame,
        TICKER_COLUMNS.get(name),
        YEAR_COLUMNS.get(name),
    )
    if name == "profitandloss":
        frame = repair_pl_column_rotation(frame)
    frame = coerce_numeric(frame, NUMERIC_COLUMNS.get(name, ()))
    for column in TEXT_COLUMNS.get(name, ()):
        if column in frame.columns:
            frame[column] = frame[column].map(clean_text)
    logger.info("Loaded %s rows from %s", len(frame), name)
    return frame


def load_all_core() -> dict[str, pd.DataFrame]:
    """Load all seven core datasets as normalised DataFrames."""
    return {name: load_core_table(name) for name in CORE_FILES}


def load_supporting_table(name: str) -> pd.DataFrame:
    """Load and normalise one supplementary Excel dataset by table name."""
    path = get_settings().supporting_data_dir / SUPPORTING_FILES[name]
    frame = read_excel(path, SUPPORTING_HEADER)
    if frame.empty:
        return frame
    if "company_id" in frame.columns:
        frame["company_id"] = frame["company_id"].map(normalize_ticker)
    logger.info("Loaded %s rows from %s", len(frame), name)
    return frame


def load_all_supporting() -> dict[str, pd.DataFrame]:
    """Load all five supplementary datasets as normalised DataFrames."""
    return {name: load_supporting_table(name) for name in SUPPORTING_FILES}


def reject_unparseable_years(df: pd.DataFrame, year_column: str) -> pd.DataFrame:
    """Drop rows whose normalised year label is PARSE_ERROR (DQ-07)."""
    if year_column not in df.columns:
        return df
    return df[df[year_column] != PARSE_ERROR].copy()


def reject_invalid_tickers(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Drop rows with missing or out-of-range ticker labels (DQ-08)."""
    if column not in df.columns:
        return df
    values = df[column].astype(str)
    mask = values.map(
        lambda v: v == MISSING or not TICKER_MIN_LENGTH <= len(v) <= TICKER_MAX_LENGTH
    )
    return df[~mask].copy()


def dedup_annual_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate (company_id, year) rows keeping last (DQ-02)."""
    if df.empty or "company_id" not in df.columns or "year" not in df.columns:
        return df
    return df.drop_duplicates(subset=["company_id", "year"], keep="last").copy()


def clean_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Apply DQ-02, DQ-03, DQ-07, DQ-08 row actions to all tables."""
    companies = reject_invalid_tickers(tables.get("companies", pd.DataFrame()), "id")
    cleaned = {"companies": companies}
    valid = set(companies["id"])
    for name, frame in tables.items():
        if name == "companies":
            continue
        df = frame.copy()
        ticker_column = TICKER_COLUMNS.get(name)
        if ticker_column:
            df = reject_invalid_tickers(df, ticker_column)
        if name in YEAR_COLUMNS:
            df = reject_unparseable_years(df, YEAR_COLUMNS[name])
            df = dedup_annual_keys(df)
        if ticker_column and not df.empty:
            df = df[df[ticker_column].isin(valid)].copy()
        if name in UNIQUE_KEYS and not df.empty:
            df = df.drop_duplicates(subset=list(UNIQUE_KEYS[name]), keep="last")
        cleaned[name] = df.copy()
    return cleaned


def connect_db() -> sqlite3.Connection:
    """Open a SQLite connection with foreign key enforcement enabled."""
    conn = sqlite3.connect(get_settings().db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create database tables from db/schema.sql."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def _native(value: object) -> object:
    """Convert pandas scalars to SQLite-compatible native Python values."""
    if pd.isna(value):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def write_table(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> int:
    """Replace table rows with DataFrame contents and return row count."""
    columns = TABLE_COLUMNS[table]
    frame = df.reindex(columns=list(columns))
    column_clause = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO {table} ({column_clause}) VALUES ({placeholders})"
    rows = [
        tuple(_native(value) for value in record)
        for record in frame.itertuples(index=False, name=None)
    ]
    with conn:
        conn.execute(f"DELETE FROM {table}")
        conn.executemany(sql, rows)
    return len(rows)


def load_database(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Full-refresh tables in dependency order and return row counts."""
    conn = connect_db()
    try:
        init_schema(conn)
        with conn:
            for name in reversed(LOAD_ORDER):
                conn.execute(f"DELETE FROM {name}")
        counts = {}
        for name in LOAD_ORDER:
            if name in tables:
                counts[name] = write_table(conn, name, tables[name])
        return counts
    finally:
        conn.close()


def check_foreign_keys() -> list[tuple]:
    """Return PRAGMA foreign_key_check violations for the project database."""
    conn = connect_db()
    try:
        return conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _audit_row(
    source_file: str,
    table: str,
    rows_in: int,
    runtime_s: float,
    note: str,
) -> dict[str, object]:
    """Build one load audit record."""
    return {
        "source_file": source_file,
        "table": table,
        "rows_in": rows_in,
        "rows_out": 0,
        "rejected": 0,
        "timestamp": _utc_now(),
        "runtime_s": round(runtime_s, 3),
        "note": note,
    }


def write_load_audit(audit: pd.DataFrame) -> Path:
    """Write the load audit frame to output/load_audit.csv."""
    path = get_settings().output_dir / "load_audit.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(path, index=False)
    logger.info("Wrote load audit for %s files to %s", len(audit), path)
    return path


def run_full_load() -> pd.DataFrame:
    """Load all 12 source files, persist 10 tables, and write the audit."""
    audit: list[dict[str, object]] = []
    tables: dict[str, pd.DataFrame] = {}
    for name, source_file in CORE_FILES.items():
        started = time.perf_counter()
        tables[name] = load_core_table(name)
        elapsed = time.perf_counter() - started
        audit.append(_audit_row(source_file, name, len(tables[name]), elapsed, ""))
    for name in PERSISTED_SUPPORTING:
        started = time.perf_counter()
        tables[name] = load_supporting_table(name)
        elapsed = time.perf_counter() - started
        audit.append(
            _audit_row(SUPPORTING_FILES[name], name, len(tables[name]), elapsed, "")
        )
    for name in REFERENCE_ONLY_TABLES:
        started = time.perf_counter()
        frame = load_supporting_table(name)
        elapsed = time.perf_counter() - started
        audit.append(
            _audit_row(
                SUPPORTING_FILES[name],
                name,
                len(frame),
                elapsed,
                REFERENCE_ONLY_NOTES[name],
            )
        )
    cleaned = clean_tables(tables)
    counts = load_database(cleaned)
    for row in audit:
        table = str(row["table"])
        if table in counts:
            row["rows_out"] = counts[table]
            row["rejected"] = int(row["rows_in"]) - counts[table]
    audit_frame = pd.DataFrame(audit, columns=list(AUDIT_COLUMNS))
    write_load_audit(audit_frame)
    return audit_frame


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    audit = run_full_load()
    for row in audit.to_dict("records"):
        logger.info(
            "%s: in=%s out=%s rejected=%s",
            row["table"],
            row["rows_in"],
            row["rows_out"],
            row["rejected"],
        )
    violations = check_foreign_keys()
    logger.info("Foreign key violations: %s", len(violations))
    if violations:
        raise SystemExit(1)
