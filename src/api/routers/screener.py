"""Screener API endpoint."""

from fastapi import APIRouter, Query

from src.screener.engine import apply_filters, build_screener_universe

router = APIRouter()


@router.get("/screener")
def screen_companies(
    min_roe: float | None = Query(None, ge=0),
    max_de: float | None = Query(None, ge=0),
    min_fcf: float | None = Query(None),
    sector: str | None = Query(None),
    min_rev_cagr_5yr: float | None = Query(None),
    min_pat_cagr_5yr: float | None = Query(None),
    max_pe: float | None = Query(None, ge=0),
) -> list[dict]:
    """Return ranked company list based on dynamic filter thresholds."""
    universe = build_screener_universe()
    filters = {}
    if min_roe is not None:
        filters["roe_min"] = min_roe
    if max_de is not None:
        filters["de_max"] = max_de
    if min_fcf is not None:
        filters["fcf_min"] = min_fcf
    if min_rev_cagr_5yr is not None:
        filters["revenue_cagr_5yr_min"] = min_rev_cagr_5yr
    if min_pat_cagr_5yr is not None:
        filters["pat_cagr_5yr_min"] = min_pat_cagr_5yr
    if max_pe is not None:
        filters["pe_max"] = max_pe

    results = apply_filters(universe, filters)
    if sector:
        results = results[results["broad_sector"] == sector]

    return results.to_dict(orient="records")
