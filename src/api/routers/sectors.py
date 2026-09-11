"""Sector API endpoints."""

import sqlite3

from fastapi import APIRouter, HTTPException

from src.analytics.ratios import DB_PATH

router = APIRouter()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/sectors")
def list_sectors() -> list[dict]:
    """Return all sectors with company count and median KPIs."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT s.broad_sector, COUNT(c.id) as company_count, "
            "AVG(r.return_on_equity_pct) as median_roe, "
            "AVG(m.pe_ratio) as median_pe, "
            "AVG(r.debt_to_equity) as median_de "
            "FROM sectors s "
            "JOIN companies c ON s.company_id = c.id "
            "LEFT JOIN (SELECT company_id, return_on_equity_pct, debt_to_equity "
            "FROM financial_ratios WHERE year = (SELECT MAX(year) FROM financial_ratios)) r "
            "ON s.company_id = r.company_id "
            "LEFT JOIN (SELECT company_id, pe_ratio FROM market_cap "
            "WHERE year = (SELECT MAX(year) FROM market_cap)) m "
            "ON s.company_id = m.company_id "
            "GROUP BY s.broad_sector"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/sectors/{sector}/companies")
def get_sector_companies(sector: str) -> list[dict]:
    """Return all companies in a specific sector."""
    with _get_conn() as conn:
        companies = conn.execute(
            "SELECT c.id, c.company_name, s.sub_sector "
            "FROM companies c JOIN sectors s ON c.id = s.company_id "
            "WHERE s.broad_sector = ?",
            (sector,),
        ).fetchall()
    if not companies:
        raise HTTPException(status_code=404, detail="Sector not found")
    return [dict(c) for c in companies]
