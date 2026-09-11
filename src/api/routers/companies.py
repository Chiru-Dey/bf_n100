"""Company-specific API endpoints."""

import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.analytics.ratios import DB_PATH
from src.api.schemas import CompanyBase, CompanyDetail, CompanyList

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEARSHEET_DIR = PROJECT_ROOT / "reports" / "tearsheets"


def _get_conn() -> sqlite3.Connection:
    """Return a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/companies", response_model=CompanyList)
def list_companies(
    sector: str | None = Query(None, description="Filter by broad sector"),
) -> CompanyList:
    """Return a list of all companies, optionally filtered by sector."""
    with _get_conn() as conn:
        if sector:
            rows = conn.execute(
                "SELECT c.id, c.company_name, s.broad_sector "
                "FROM companies c JOIN sectors s ON c.id = s.company_id "
                "WHERE s.broad_sector = ? ORDER BY c.id",
                (sector,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT c.id, c.company_name, s.broad_sector "
                "FROM companies c JOIN sectors s ON c.id = s.company_id ORDER BY c.id"
            ).fetchall()

    companies = [CompanyBase(**dict(row)) for row in rows]
    return CompanyList(count=len(companies), companies=companies)


@router.get("/companies/{ticker}", response_model=CompanyDetail)
def get_company(ticker: str) -> CompanyDetail:
    """Return detailed company profile including latest KPIs and valuation."""
    with _get_conn() as conn:
        company = conn.execute(
            "SELECT c.id, c.company_name, s.broad_sector "
            "FROM companies c JOIN sectors s ON c.id = s.company_id WHERE c.id = ?",
            (ticker,),
        ).fetchone()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Prefer latest March year; fallback to absolute latest if no March data
        ratios = conn.execute(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND year LIKE '%-03' "
            "ORDER BY year DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        if not ratios:
            ratios = conn.execute(
                "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year DESC LIMIT 1",
                (ticker,),
            ).fetchone()

        mc = conn.execute(
            "SELECT * FROM market_cap WHERE company_id = ? ORDER BY year DESC LIMIT 1",
            (ticker,),
        ).fetchone()

    return CompanyDetail(
        id=company["id"],
        company_name=company["company_name"],
        broad_sector=company["broad_sector"],
        roe=ratios["return_on_equity_pct"] if ratios else None,
        roce=ratios["return_on_capital_employed_pct"] if ratios else None,
        debt_to_equity=ratios["debt_to_equity"] if ratios else None,
        pe_ratio=mc["pe_ratio"] if mc else None,
        market_cap_crore=mc["market_cap_crore"] if mc else None,
    )


@router.get("/companies/{ticker}/tearsheet")
def get_tearsheet(ticker: str) -> FileResponse:
    """Download the generated PDF tearsheet for a specific company."""
    path = TEARSHEET_DIR / f"{ticker}_tearsheet.pdf"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Tearsheet PDF not found. Run batch tearsheet generation first.",
        )
    return FileResponse(
        path, media_type="application/pdf", filename=f"{ticker}_tearsheet.pdf"
    )
