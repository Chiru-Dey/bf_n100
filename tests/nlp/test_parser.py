"""Unit tests for the NLP analysis text parser."""

import pandas as pd

from src.nlp.parser import parse_analysis_table, parse_text


def test_parse_text_normal() -> None:
    period, value = parse_text("10 Years: 21%")
    assert period == 10
    assert value == 21.0


def test_parse_text_variant_spacing() -> None:
    period, value = parse_text("5 Years :  6.5%")
    assert period == 5
    assert value == 6.5


def test_parse_text_no_match() -> None:
    period, value = parse_text("No data available")
    assert period is None
    assert value is None


def test_parse_text_nan() -> None:
    period, value = parse_text(None)
    assert period is None
    assert value is None


def test_parse_analysis_table() -> None:
    df = pd.DataFrame(
        {
            "company_id": ["TCS", "INFY"],
            "compounded_sales_growth": ["10 Years: 21%", "5 Years: 15%"],
            "compounded_profit_growth": ["10 Years: 18%", "Garbage text"],
        }
    )
    parsed, failures = parse_analysis_table(df)
    assert len(parsed) == 3
    assert len(failures) == 1
    assert failures.iloc[0]["company_id"] == "INFY"