"""Unit tests for valuation formulas and flag bands."""

import pytest

from src.analytics.valuation import (
    CAUTION,
    DISCOUNT,
    FAIR,
    fcf_yield,
    valuation_flag,
)


def test_fcf_yield_normal() -> None:
    assert fcf_yield(300.0, 10000.0) == pytest.approx(3.0)


def test_fcf_yield_zero_market_cap_returns_none() -> None:
    assert fcf_yield(300.0, 0.0) is None


def test_valuation_flag_caution() -> None:
    assert valuation_flag(30.0, 15.0) == CAUTION


def test_valuation_flag_discount() -> None:
    assert valuation_flag(9.0, 15.0) == DISCOUNT


def test_valuation_flag_fair() -> None:
    assert valuation_flag(15.0, 15.0) == FAIR
