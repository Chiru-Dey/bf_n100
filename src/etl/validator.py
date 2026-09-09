from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import requests

from src.etl.loader import (
    clean_tables,
    load_all_core,
    load_supporting_table,
)
from src.etl.normaliser import (
    MISSING,
    TICKER_MAX_LENGTH,
    TICKER_MIN_LENGTH,
)
from src.settings import get_settings

logger = logging.getLogger(__name__)

CRITICAL = "CRITICAL"
WARNING = "WARNING"
INFO = "INFO"

YEAR_PATTERN = re.compile(r"^\d{4}-\d{2}$")
BS_TOLERANCE = 0.01
OPM_TOLERANCE = 1.0
NET_CASH_TOLERANCE = 10.0
TAX_MIN = 0.0
TAX_MAX = 60.0
DIVIDEND_CAP = 200.0
MIN_COVERAGE_YEARS = 5
URL_TIMEOUT = 10

TIME_SERIES_TABLES = ("profitandloss", "balancesheet", "cashflow")
CHILD_TABLES = (
    "profitandloss",
    "balancesheet",
    "cashflow",
    "analysis",
    "documents",
    "prosandcons",
)

FAILURE_COLUMNS = [
    "rule_id",
    "table",
    "company_id",
    "year",
    "field",
    "issue",
    "severity",
]


@dataclass(frozen=True)
class ValidationFailure:
    """Single data quality violation record."""

    rule_id: str
    table: str
    company_id: str
    year: str
    field: str
    issue: str
    severity: str


def _text(value: object) -> str:
    """Render a cell value as empty-safe text."""
    if pd.isna(value):
        return ""
    return str(value)


def _row_failures(
    rule_id: str,
    table: str,
    rows: pd.DataFrame,
    field: str,
    issue: str,
    severity: str,
    id_column: str = "company_id",
) -> list[ValidationFailure]:
    """Convert flagged DataFrame rows into validation failure records."""
    return [
        ValidationFailure(
            rule_id=rule_id,
            table=table,
            company_id=_text(row.get(id_column)),
            year=_text(row.get("year")),
            field=field,
            issue=issue,
            severity=severity,
        )
        for row in rows.to_dict("records")
    ]


def validate_company_pk(companies: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-01: company primary key must be unique."""
    duplicated = companies[companies["id"].duplicated(keep=False)]
    return _row_failures(
        "DQ-01",
        "companies",
        duplicated,
        "id",
        "duplicate company primary key",
        CRITICAL,
        id_column="id",
    )


def validate_annual_pk(df: pd.DataFrame, table: str) -> list[ValidationFailure]:
    """DQ-02: (company_id, year) pairs must be unique in time-series tables."""
    duplicated = df[df.duplicated(subset=["company_id", "year"], keep="last")]
    return _row_failures(
        "DQ-02",
        table,
        duplicated,
        "company_id,year",
        "duplicate (company_id, year) key",
        CRITICAL,
    )


def validate_fk_integrity(
    tables: dict[str, pd.DataFrame],
    companies: pd.DataFrame,
) -> list[ValidationFailure]:
    """DQ-03: every child company_id must exist in companies.id."""
    valid = set(companies["id"])
    failures: list[ValidationFailure] = []
    for table in CHILD_TABLES:
        df = tables.get(table)
        if df is None or df.empty:
            continue
        orphans = df[~df["company_id"].isin(valid)]
        failures.extend(
            _row_failures(
                "DQ-03",
                table,
                orphans,
                "company_id",
                "orphan company_id not present in companies",
                CRITICAL,
            )
        )
    return failures


def validate_bs_balance(bs: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-04: total assets must equal total liabilities within 1%."""
    assets = pd.to_numeric(bs["total_assets"], errors="coerce")
    liabilities = pd.to_numeric(bs["total_liabilities"], errors="coerce")
    mask = (
        assets.notna()
        & liabilities.notna()
        & (assets != 0)
        & ((assets - liabilities).abs() / assets.abs() >= BS_TOLERANCE)
    )
    return _row_failures(
        "DQ-04",
        "balancesheet",
        bs.loc[mask],
        "total_assets",
        "balance sheet mismatch beyond 1% tolerance",
        WARNING,
    )


def validate_opm_crosscheck(pl: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-05: reported OPM must match computed OPM within 1 point."""
    sales = pd.to_numeric(pl["sales"], errors="coerce")
    operating_profit = pd.to_numeric(pl["operating_profit"], errors="coerce")
    reported = pd.to_numeric(pl["opm_percentage"], errors="coerce")
    computed = operating_profit / sales * 100
    mask = (
        sales.notna()
        & (sales != 0)
        & reported.notna()
        & computed.notna()
        & ((reported - computed).abs() >= OPM_TOLERANCE)
    )
    return _row_failures(
        "DQ-05",
        "profitandloss",
        pl.loc[mask],
        "opm_percentage",
        "reported OPM diverges from computed OPM by >= 1 point",
        WARNING,
    )


def validate_positive_sales(
    pl: pd.DataFrame,
    financials: set[str] | None = None,
) -> list[ValidationFailure]:
    """DQ-06: sales must be positive for non-financial companies."""
    sales = pd.to_numeric(pl["sales"], errors="coerce")
    mask = sales.notna() & (sales <= 0)
    if financials is not None:
        mask &= ~pl["company_id"].isin(financials)
    return _row_failures(
        "DQ-06",
        "profitandloss",
        pl.loc[mask],
        "sales",
        "non-positive sales for non-financial company",
        WARNING,
    )


def validate_year_format(tables: dict[str, pd.DataFrame]) -> list[ValidationFailure]:
    """DQ-07: normalised year labels must match YYYY-MM."""
    failures: list[ValidationFailure] = []
    for table in TIME_SERIES_TABLES:
        df = tables.get(table)
        if df is None or df.empty:
            continue
        mask = ~df["year"].astype(str).map(lambda v: bool(YEAR_PATTERN.match(v)))
        failures.extend(
            _row_failures(
                "DQ-07",
                table,
                df.loc[mask],
                "year",
                "year label failed normalisation",
                CRITICAL,
            )
        )
    return failures


def validate_ticker_format(
    tables: dict[str, pd.DataFrame],
    companies: pd.DataFrame,
) -> list[ValidationFailure]:
    """DQ-08: tickers must be present and 2-12 characters long."""
    failures: list[ValidationFailure] = []
    targets = [("companies", companies, "id")]
    targets += [(table, tables.get(table), "company_id") for table in CHILD_TABLES]
    for table, df, column in targets:
        if df is None or df.empty:
            continue
        values = df[column].astype(str)
        mask = values.map(
            lambda v: v == MISSING
            or not TICKER_MIN_LENGTH <= len(v) <= TICKER_MAX_LENGTH
        )
        failures.extend(
            _row_failures(
                "DQ-08",
                table,
                df.loc[mask],
                column,
                "ticker missing or length outside 2-12 characters",
                CRITICAL,
                id_column=column,
            )
        )
    return failures


def validate_net_cash(cf: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-09: net cash flow must equal component sum within 10 Cr."""
    cfo = pd.to_numeric(cf["operating_activity"], errors="coerce")
    cfi = pd.to_numeric(cf["investing_activity"], errors="coerce")
    cff = pd.to_numeric(cf["financing_activity"], errors="coerce")
    net = pd.to_numeric(cf["net_cash_flow"], errors="coerce")
    mask = (
        cfo.notna()
        & cfi.notna()
        & cff.notna()
        & net.notna()
        & ((net - (cfo + cfi + cff)).abs() > NET_CASH_TOLERANCE)
    )
    return _row_failures(
        "DQ-09",
        "cashflow",
        cf.loc[mask],
        "net_cash_flow",
        "net cash flow differs from component sum beyond 10 Cr",
        WARNING,
    )


def validate_fixed_assets(bs: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-10: fixed assets must not be negative."""
    fixed_assets = pd.to_numeric(bs["fixed_assets"], errors="coerce")
    mask = fixed_assets.notna() & (fixed_assets < 0)
    return _row_failures(
        "DQ-10",
        "balancesheet",
        bs.loc[mask],
        "fixed_assets",
        "negative fixed assets to be coerced to 0",
        WARNING,
    )


def validate_tax_range(pl: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-11: effective tax rate must lie between 0 and 60 percent."""
    tax = pd.to_numeric(pl["tax_percentage"], errors="coerce")
    mask = tax.notna() & ((tax < TAX_MIN) | (tax > TAX_MAX))
    return _row_failures(
        "DQ-11",
        "profitandloss",
        pl.loc[mask],
        "tax_percentage",
        "effective tax rate outside 0-60 percent range",
        WARNING,
    )


def validate_dividend_cap(pl: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-12: dividend payout must not exceed 200 percent."""
    dividend = pd.to_numeric(pl["dividend_payout"], errors="coerce")
    mask = dividend.notna() & (dividend > DIVIDEND_CAP)
    return _row_failures(
        "DQ-12",
        "profitandloss",
        pl.loc[mask],
        "dividend_payout",
        "dividend payout above 200 percent cap",
        WARNING,
    )


def _url_ok(url: str) -> bool:
    """Return True when a HEAD request on the URL returns HTTP 200."""
    try:
        response = requests.head(url, timeout=URL_TIMEOUT, allow_redirects=True)
        return response.status_code == 200
    except requests.RequestException:
        logger.warning("URL check failed for %s", url)
        return False


def validate_document_urls(
    documents: pd.DataFrame,
    url_checker=None,
) -> list[ValidationFailure]:
    """DQ-13: annual report URLs must be reachable."""
    checker = url_checker or _url_ok
    failures: list[ValidationFailure] = []
    urls = documents["Annual_Report"]
    for row in documents.loc[urls.notna()].to_dict("records"):
        url = row["Annual_Report"]
        if not checker(url):
            failures.append(
                ValidationFailure(
                    rule_id="DQ-13",
                    table="documents",
                    company_id=_text(row.get("company_id")),
                    year=_text(row.get("Year")),
                    field="Annual_Report",
                    issue=f"url unreachable: {url}",
                    severity=WARNING,
                )
            )
    return failures


def validate_eps_sign(pl: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-14: EPS must be positive whenever net profit is positive."""
    net_profit = pd.to_numeric(pl["net_profit"], errors="coerce")
    eps = pd.to_numeric(pl["eps"], errors="coerce")
    mask = net_profit.notna() & (net_profit > 0) & ~(eps.notna() & (eps > 0))
    return _row_failures(
        "DQ-14",
        "profitandloss",
        pl.loc[mask],
        "eps",
        "EPS not positive while net profit is positive",
        WARNING,
    )


def validate_bs_strict_balance(bs: pd.DataFrame) -> list[ValidationFailure]:
    """DQ-15: informational counter for strict assets-liabilities equality."""
    assets = pd.to_numeric(bs["total_assets"], errors="coerce")
    liabilities = pd.to_numeric(bs["total_liabilities"], errors="coerce")
    mask = assets.notna() & liabilities.notna() & (assets != liabilities)
    return _row_failures(
        "DQ-15",
        "balancesheet",
        bs.loc[mask],
        "total_liabilities",
        "total liabilities not strictly equal to total assets",
        INFO,
    )


def validate_coverage(
    pl: pd.DataFrame,
    bs: pd.DataFrame,
    cf: pd.DataFrame,
) -> list[ValidationFailure]:
    """DQ-16: each company needs at least 5 years per time-series table."""
    failures: list[ValidationFailure] = []
    for table, df in (("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)):
        if df is None or df.empty:
            continue
        valid_years = df["year"].astype(str).map(lambda v: bool(YEAR_PATTERN.match(v)))
        counts = df.loc[valid_years].groupby("company_id")["year"].nunique()
        short = counts[counts < MIN_COVERAGE_YEARS]
        for company_id, years in short.items():
            failures.append(
                ValidationFailure(
                    rule_id="DQ-16",
                    table=table,
                    company_id=str(company_id),
                    year="",
                    field="year",
                    issue=f"only {years} years of history, below {MIN_COVERAGE_YEARS}",
                    severity=WARNING,
                )
            )
    return failures


def validate_all(
    tables: dict[str, pd.DataFrame],
    financials: set[str] | None = None,
    check_urls: bool = False,
    url_checker=None,
) -> pd.DataFrame:
    """Run all 16 DQ rules and return failures as a DataFrame."""
    companies = tables.get("companies", pd.DataFrame())
    pl = tables.get("profitandloss", pd.DataFrame())
    bs = tables.get("balancesheet", pd.DataFrame())
    cf = tables.get("cashflow", pd.DataFrame())
    failures: list[ValidationFailure] = []
    failures.extend(validate_company_pk(companies))
    for table in TIME_SERIES_TABLES:
        failures.extend(validate_annual_pk(tables.get(table, pd.DataFrame()), table))
    failures.extend(validate_fk_integrity(tables, companies))
    failures.extend(validate_bs_balance(bs))
    failures.extend(validate_opm_crosscheck(pl))
    failures.extend(validate_positive_sales(pl, financials))
    failures.extend(validate_year_format(tables))
    failures.extend(validate_ticker_format(tables, companies))
    failures.extend(validate_net_cash(cf))
    failures.extend(validate_fixed_assets(bs))
    failures.extend(validate_tax_range(pl))
    failures.extend(validate_dividend_cap(pl))
    if check_urls:
        failures.extend(
            validate_document_urls(tables.get("documents", pd.DataFrame()), url_checker)
        )
    failures.extend(validate_eps_sign(pl))
    failures.extend(validate_bs_strict_balance(bs))
    failures.extend(validate_coverage(pl, bs, cf))
    return pd.DataFrame(
        [asdict(failure) for failure in failures],
        columns=FAILURE_COLUMNS,
    )


def write_failures(failures: pd.DataFrame, path: Path) -> Path:
    """Write the validation failure frame to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    failures.to_csv(path, index=False)
    logger.info("Wrote %s validation failures to %s", len(failures), path)
    return path


def _financial_tickers() -> set[str]:
    """Return tickers classified under the Financials broad sector."""
    try:
        sectors = load_supporting_table("sectors")
        mask = sectors["broad_sector"] == "Financials"
        return set(sectors.loc[mask, "company_id"].astype(str))
    except (KeyError, OSError, ValueError):
        logger.warning("Sectors unavailable; DQ-06 applies to all companies")
        return set()


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    loaded = load_all_core()
    financials = _financial_tickers()
    failures = validate_all(
        loaded,
        financials=financials,
        check_urls=get_settings().validate_urls,
    )
    write_failures(failures, get_settings().output_dir / "validation_failures.csv")
    for severity in (CRITICAL, WARNING, INFO):
        count = int((failures["severity"] == severity).sum())
        logger.info("Raw %s failures: %s", severity, count)
    cleaned = clean_tables(loaded)
    post = validate_all(
        cleaned,
        financials=financials,
        check_urls=get_settings().validate_urls,
    )
    post_critical = int((post["severity"] == CRITICAL).sum())
    logger.info(
        "Post-clean row counts: %s",
        {name: len(frame) for name, frame in cleaned.items()},
    )
    logger.info("Post-clean CRITICAL failures: %s", post_critical)
    if post_critical > 0:
        raise SystemExit(1)
