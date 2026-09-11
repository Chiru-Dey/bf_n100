"""Valuation and Market Cap API endpoints."""

import sqlite3

from fastapi import APIRouter, HTTPException

from src.analytics.ratios import DB_PATH

router = APIRouter()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/market-cap/{ticker}")
def get_market_cap(ticker: str) -> list[dict]:
    """Return historical valuation multiples for a company."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT year, market_cap_crore, pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct "
            "FROM market_cap WHERE company_id = ? ORDER BY year",
            (ticker,),
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Market cap data not found")
    return [dict(r) for r in rows]
