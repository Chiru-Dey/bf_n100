"""Unit tests for the portfolio summary trend arrow logic."""

from src.reports.portfolio_report import _trend_arrow


def test_trend_arrow_up() -> None:
    arrow, color = _trend_arrow(120.0, 100.0)
    assert arrow == "↑"
    assert color == "#2E7D32"


def test_trend_arrow_down() -> None:
    arrow, color = _trend_arrow(80.0, 100.0)
    assert arrow == "↓"
    assert color == "#C62828"


def test_trend_arrow_flat() -> None:
    arrow, color = _trend_arrow(101.0, 100.0)
    assert arrow == "→"
    assert color == "#757575"


def test_trend_arrow_inverted_de() -> None:
    arrow, color = _trend_arrow(0.8, 1.0, invert=True)
    assert arrow == "↑"
    assert color == "#2E7D32"
