"""Helper functions for the Company Profile screen."""

from __future__ import annotations

from typing import Any

import pandas as pd


def format_kpi_tile(value: Any, suffix: str = "%", precision: int = 1) -> str:
    """Format a numeric value for a KPI tile, returning 'N/A' if missing."""
    if pd.isna(value):
        return "N/A"
    try:
        return f"{float(value):.{precision}f}{suffix}"
    except (ValueError, TypeError):
        return "N/A"