"""Peer comparison API endpoints."""

import sqlite3

from fastapi import APIRouter, HTTPException

from src.analytics.ratios import DB_PATH

router = APIRouter()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/peers/{group_name}")
def get_peer_group(group_name: str) -> list[dict]:
    """Return all companies in a peer group with percentile ranks."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT company_id, metric, percentile_rank "
            "FROM peer_percentiles WHERE peer_group_name = ?",
            (group_name,),
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Peer group not found")

    peers: dict[str, dict] = {}
    for r in rows:
        cid = r["company_id"]
        if cid not in peers:
            peers[cid] = {"company_id": cid}
        peers[cid][r["metric"]] = r["percentile_rank"]

    return list(peers.values())


@router.get("/companies/{ticker}/peers/compare")
def compare_peers(ticker: str) -> dict:
    """Return radar data: company vs peer group average."""
    with _get_conn() as conn:
        group = conn.execute(
            "SELECT peer_group_name FROM peer_groups WHERE company_id = ?", (ticker,)
        ).fetchone()
        if not group:
            raise HTTPException(status_code=404, detail="Company not in any peer group")

        group_name = group["peer_group_name"]
        rows = conn.execute(
            "SELECT company_id, metric, value FROM peer_percentiles "
            "WHERE peer_group_name = ?",
            (group_name,),
        ).fetchall()

    pivot: dict[str, dict] = {}
    for r in rows:
        cid = r["company_id"]
        if cid not in pivot:
            pivot[cid] = {"company_id": cid}
        pivot[cid][r["metric"]] = r["value"]

    return {"group": group_name, "companies": list(pivot.values())}
