from src.etl.normaliser import normalize_ticker, normalize_year


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
