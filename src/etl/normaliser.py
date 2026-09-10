from __future__ import annotations

import math
import re
import logging
import pandas as pd

logger = logging.getLogger(__name__)

PARSE_ERROR = "PARSE_ERROR"
MISSING = "MISSING"
TICKER_MIN_LENGTH = 2
TICKER_MAX_LENGTH = 12
DEFAULT_FISCAL_MONTH = 3

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_FULL_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_NORMALISED = re.compile(r"^(\d{4})-(\d{2})$")
_MONTH_YEAR = re.compile(r"^([A-Za-z]+)[\s-]+(\d{2,4})$")
_FY_PREFIX = re.compile(r"^FY(\d{2,4})$")
_PLAIN_YEAR = re.compile(r"^\d{4}$")


def _expand_year(token: str) -> int:
    """Expand a two or four digit year token to a four digit year."""
    year = int(token)
    return year + 2000 if year < 100 else year


def _month_number(token: str) -> int | None:
    """Resolve an abbreviated or full month name to its month number."""
    key = token.lower()
    if key in _MONTHS:
        return _MONTHS[key]
    return _FULL_MONTHS.get(key)


def normalize_year(value: object) -> str:
    """Standardise any source year label to YYYY-MM or PARSE_ERROR."""
    if value is None:
        return PARSE_ERROR
    if isinstance(value, float):
        if math.isnan(value) or not value.is_integer():
            return PARSE_ERROR
        value = int(value)
    if isinstance(value, int):
        if not 1900 <= value <= 2100:
            return PARSE_ERROR
        return f"{value:04d}-{DEFAULT_FISCAL_MONTH:02d}"
    text = str(value).strip()
    if not text:
        return PARSE_ERROR
    normalised = _NORMALISED.match(text)
    if normalised:
        month = int(normalised.group(2))
        return text if 1 <= month <= 12 else PARSE_ERROR
    if _PLAIN_YEAR.match(text):
        return f"{text}-{DEFAULT_FISCAL_MONTH:02d}"
    fiscal = _FY_PREFIX.match(text.upper())
    if fiscal:
        return f"{_expand_year(fiscal.group(1)):04d}-{DEFAULT_FISCAL_MONTH:02d}"
    month_year = _MONTH_YEAR.match(text)
    if month_year:
        month = _month_number(month_year.group(1))
        if month is None:
            return PARSE_ERROR
        return f"{_expand_year(month_year.group(2)):04d}-{month:02d}"
    return PARSE_ERROR


def normalize_ticker(value: object) -> str:
    """Normalise a company identifier to an uppercase stripped ticker."""
    if value is None:
        return MISSING
    if isinstance(value, float) and math.isnan(value):
        return MISSING
    text = str(value).strip().upper()
    return text if text else MISSING

PL_ROTATION_COLUMNS = (
    "expenses",
    "operating_profit",
    "opm_percentage",
    "other_income",
    "interest",
    "depreciation",
)


def repair_pl_column_rotation(frame: pd.DataFrame) -> pd.DataFrame:
    """Restore rotated P&L middle-block columns detected via PBT identity checks."""
    repaired = frame.copy()
    sales = repaired["sales"]
    expenses = repaired["expenses"]
    operating_profit = repaired["operating_profit"]
    opm_percentage = repaired["opm_percentage"]
    interest = repaired["interest"]
    depreciation = repaired["depreciation"]
    pbt = repaired["profit_before_tax"]
    broken_core = (sales - expenses - operating_profit).abs() > 0.01 * sales.abs()
    op_holds_expenses = (operating_profit - (sales - opm_percentage)).abs() <= (
        0.01 * sales.abs()
    )
    rotated_pbt = opm_percentage + interest - depreciation - expenses
    pbt_matches = (pbt - rotated_pbt).abs() <= 0.01 * pbt.abs().clip(lower=1.0)
    required = ["sales", "profit_before_tax", *PL_ROTATION_COLUMNS]
    mask = (
        broken_core
        & op_holds_expenses
        & pbt_matches
        & repaired[required].notna().all(axis=1)
    )
    if not mask.any():
        return repaired
    repaired.loc[mask, "expenses"] = operating_profit[mask]
    repaired.loc[mask, "operating_profit"] = opm_percentage[mask]
    repaired.loc[mask, "opm_percentage"] = (
        repaired.loc[mask, "operating_profit"]
        / repaired.loc[mask, "sales"]
        * 100.0
    ).round(2)
    repaired.loc[mask, "other_income"] = interest[mask]
    repaired.loc[mask, "interest"] = depreciation[mask]
    repaired.loc[mask, "depreciation"] = expenses[mask]
    for company_id, year in repaired.loc[mask, ["company_id", "year"]].itertuples(
        index=False
    ):
        logger.debug("Repaired rotated P&L columns for %s %s", company_id, year)
    logger.warning(
        "Repaired rotated P&L column block for %d of %d rows", mask.sum(), len(repaired)
    )
    return repaired