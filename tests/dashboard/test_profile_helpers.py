"""Unit tests for Company Profile helper functions."""

import numpy as np

from src.dashboard.utils.profile_helpers import format_kpi_tile


def test_format_kpi_tile_normal() -> None:
    assert format_kpi_tile(25.456) == "25.5%"


def test_format_kpi_tile_missing() -> None:
    assert format_kpi_tile(np.nan) == "N/A"
    assert format_kpi_tile(None) == "N/A"


def test_format_kpi_tile_custom() -> None:
    assert format_kpi_tile(1.25, suffix="x", precision=2) == "1.25x"