"""Document repository API endpoint."""

import sqlite3

from fastapi import APIRouter, HTTPException

from src.analytics.ratios import DB_PATH

router = APIRouter()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/companies/{ticker}/documents")
def get_documents(ticker: str) -> list[dict]:
    """Return annual report links with validation flag."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT Year, Annual_Report FROM documents "
            "WHERE company_id = ? ORDER BY Year DESC",
            (ticker,),
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Documents not found")

    return [
        {
            "year": r["Year"],
            "url": r["Annual_Report"],
            "is_url_valid": bool(r["Annual_Report"]),
        }
        for r in rows
    ]
