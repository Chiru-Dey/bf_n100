"""Portfolio statistics API endpoint."""

from fastapi import APIRouter

from src.analytics.cluster_profiling import (
    fetch_latest_ratios,
    portfolio_statistics,
)

router = APIRouter()


@router.get("/portfolio/stats")
def get_portfolio_stats() -> list[dict]:
    """Return P10 through P90 percentile table for core KPIs."""
    latest = fetch_latest_ratios()
    stats = portfolio_statistics(latest)
    return stats.to_dict(orient="records")
