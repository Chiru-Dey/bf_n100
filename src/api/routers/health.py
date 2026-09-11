"""Health check endpoint returning DB row counts and uptime."""

import sqlite3
import time

from fastapi import APIRouter

from src.analytics.ratios import DB_PATH

router = APIRouter()

START_TIME = time.time()


@router.get("/health")
def get_health() -> dict:
    """Return server status, DB row counts, and uptime."""
    with sqlite3.connect(DB_PATH) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for (table,) in tables
        }

    return {
        "status": "ok",
        "db_row_counts": counts,
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "version": "1.0.0",
    }
