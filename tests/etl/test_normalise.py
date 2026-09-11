import pandas as pd
import pytest

from src.etl.normaliser import (
    normalize_ticker,
    normalize_year,
    repair_pl_column_rotation,
)


def _pl_row(**overrides: float) -> pd.DataFrame:
    row = {
        "company_id": "CIPLA",
        "year": "2024-03",
        "sales": 25774.0,
        "expenses": 90.0,
        "operating_profit": 19483.0,
        "opm_percentage": 6291.0,
        "other_income": 24.0,
        "interest": 552.0,
        "depreciation": 1051.0,
        "profit_before_tax": 5702.0,
    }
    row.update(overrides)
    return pd.DataFrame([row])


class TestNormalizeYear:
    def test_year_mar23(self) -> None:
        assert normalize_year("Mar-23") == "2023-03"

    def test_year_mar_space_23(self) -> None:
        assert normalize_year("Mar 23") == "2023-03"

    def test_year_march_2023(self) -> None:
        assert normalize_year("March-2023") == "2023-03"

    def test_year_mar_2023(self) -> None:
        assert normalize_year("Mar-2023") == "2023-03"

    def test_year_uppercase(self) -> None:
        assert normalize_year("MAR-23") == "2023-03"

    def test_year_whitespace(self) -> None:
        assert normalize_year("  Mar-23  ") == "2023-03"

    def test_year_dec22(self) -> None:
        assert normalize_year("Dec-22") == "2022-12"

    def test_year_jun23(self) -> None:
        assert normalize_year("Jun-23") == "2023-06"

    def test_year_full_month_lower(self) -> None:
        assert normalize_year("december-2022") == "2022-12"

    def test_year_two_digit_old(self) -> None:
        assert normalize_year("Apr-05") == "2005-04"

    def test_year_integer(self) -> None:
        assert normalize_year(2023) == "2023-03"

    def test_year_float(self) -> None:
        assert normalize_year(2023.0) == "2023-03"

    def test_year_string_integer(self) -> None:
        assert normalize_year("2023") == "2023-03"

    def test_year_fy23(self) -> None:
        assert normalize_year("FY23") == "2023-03"

    def test_year_fy2024(self) -> None:
        assert normalize_year("FY2024") == "2024-03"

    def test_year_normalised_passthrough(self) -> None:
        assert normalize_year("2023-03") == "2023-03"

    def test_year_garbage(self) -> None:
        assert normalize_year("xyz") == "PARSE_ERROR"

    def test_year_unknown_month(self) -> None:
        assert normalize_year("Abc-23") == "PARSE_ERROR"

    def test_year_invalid_month_number(self) -> None:
        assert normalize_year("2023-13") == "PARSE_ERROR"

    def test_year_none(self) -> None:
        assert normalize_year(None) == "PARSE_ERROR"


class TestNormalizeTicker:
    def test_ticker_strip(self) -> None:
        assert normalize_ticker(" TCS ") == "TCS"

    def test_ticker_lower(self) -> None:
        assert normalize_ticker("tcs") == "TCS"

    def test_ticker_mixed_case(self) -> None:
        assert normalize_ticker("Reliance") == "RELIANCE"

    def test_ticker_idempotent(self) -> None:
        assert normalize_ticker("TCS") == "TCS"

    def test_ticker_hyphen(self) -> None:
        assert normalize_ticker("BAJAJ-AUTO") == "BAJAJ-AUTO"

    def test_ticker_hyphen_lower(self) -> None:
        assert normalize_ticker("bajaj-auto") == "BAJAJ-AUTO"

    def test_ticker_ampersand(self) -> None:
        assert normalize_ticker("M&M") == "M&M"

    def test_ticker_ampersand_padded(self) -> None:
        assert normalize_ticker("  m&m  ") == "M&M"

    def test_ticker_newline(self) -> None:
        assert normalize_ticker("HDFCBANK\n") == "HDFCBANK"

    def test_ticker_tabs(self) -> None:
        assert normalize_ticker("\tITC\t") == "ITC"

    def test_ticker_long(self) -> None:
        assert normalize_ticker("HINDUNILVR") == "HINDUNILVR"

    def test_ticker_empty(self) -> None:
        assert normalize_ticker("") == "MISSING"

    def test_ticker_whitespace(self) -> None:
        assert normalize_ticker("   ") == "MISSING"

    def test_ticker_none(self) -> None:
        assert normalize_ticker(None) == "MISSING"

    def test_ticker_nan(self) -> None:
        assert normalize_ticker(float("nan")) == "MISSING"

    def _pl_row(**overrides: float) -> pd.DataFrame:
        row = {
            "company_id": "CIPLA",
            "year": "2024-03",
            "sales": 25774.0,
            "expenses": 90.0,
            "operating_profit": 19483.0,
            "opm_percentage": 6291.0,
            "other_income": 24.0,
            "interest": 552.0,
            "depreciation": 1051.0,
            "profit_before_tax": 5702.0,
        }
        row.update(overrides)
        return pd.DataFrame([row])

    def test_repair_pl_column_rotation_rotated_row(self) -> None:
        repaired = repair_pl_column_rotation(_pl_row())
        assert repaired.loc[0, "expenses"] == pytest.approx(19483.0)
        assert repaired.loc[0, "operating_profit"] == pytest.approx(6291.0)
        assert repaired.loc[0, "opm_percentage"] == pytest.approx(24.41, abs=0.01)
        assert repaired.loc[0, "other_income"] == pytest.approx(552.0)
        assert repaired.loc[0, "interest"] == pytest.approx(1051.0)
        assert repaired.loc[0, "depreciation"] == pytest.approx(90.0)

    def test_repair_pl_column_rotation_clean_row_unchanged(self) -> None:
        frame = _pl_row(
            expenses=19483.0,
            operating_profit=6291.0,
            opm_percentage=24.41,
            other_income=552.0,
            interest=90.0,
            depreciation=1051.0,
        )
        pd.testing.assert_frame_equal(repair_pl_column_rotation(frame), frame)

    def test_repair_pl_column_rotation_bank_row_unchanged(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "company_id": "AXISBANK",
                    "year": "2024-03",
                    "sales": 109369.0,
                    "expenses": 59474.0,
                    "operating_profit": 37943.0,
                    "opm_percentage": 11952.0,
                    "other_income": 11.0,
                    "interest": 22442.0,
                    "depreciation": 1334.0,
                    "profit_before_tax": 33060.0,
                }
            ]
        )
        pd.testing.assert_frame_equal(repair_pl_column_rotation(frame), frame)
