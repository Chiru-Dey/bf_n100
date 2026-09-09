import pandas as pd

from src.etl.validator import (
    CRITICAL,
    INFO,
    WARNING,
    validate_annual_pk,
    validate_bs_balance,
    validate_bs_strict_balance,
    validate_company_pk,
    validate_coverage,
    validate_dividend_cap,
    validate_document_urls,
    validate_eps_sign,
    validate_fixed_assets,
    validate_fk_integrity,
    validate_net_cash,
    validate_opm_crosscheck,
    validate_positive_sales,
    validate_tax_range,
    validate_ticker_format,
    validate_year_format,
)


def test_dq01_company_pk() -> None:
    frame = pd.DataFrame({"id": ["TCS", "TCS"]})
    failures = validate_company_pk(frame)
    assert failures[0].rule_id == "DQ-01"
    assert failures[0].severity == CRITICAL


def test_dq02_annual_pk() -> None:
    frame = pd.DataFrame({"company_id": ["TCS", "TCS"], "year": ["2023-03", "2023-03"]})
    failures = validate_annual_pk(frame, "profitandloss")
    assert len(failures) == 1
    assert failures[0].rule_id == "DQ-02"
    assert failures[0].severity == CRITICAL


def test_dq03_fk_integrity() -> None:
    companies = pd.DataFrame({"id": ["TCS"]})
    tables = {
        "companies": companies,
        "profitandloss": pd.DataFrame({"company_id": ["ZZZ"], "year": ["2023-03"]}),
    }
    failures = validate_fk_integrity(tables, companies)
    assert failures[0].rule_id == "DQ-03"
    assert failures[0].severity == CRITICAL


def test_dq04_bs_balance() -> None:
    bs = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "total_assets": [1000.0],
            "total_liabilities": [1020.0],
        }
    )
    failures = validate_bs_balance(bs)
    assert failures[0].rule_id == "DQ-04"
    assert failures[0].severity == WARNING


def test_dq05_opm_crosscheck() -> None:
    pl = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "sales": [1000.0],
            "operating_profit": [200.0],
            "opm_percentage": [25.0],
        }
    )
    failures = validate_opm_crosscheck(pl)
    assert failures[0].rule_id == "DQ-05"
    assert failures[0].severity == WARNING


def test_dq06_positive_sales() -> None:
    pl = pd.DataFrame({"company_id": ["TCS"], "year": ["2023-03"], "sales": [0.0]})
    failures = validate_positive_sales(pl)
    assert failures[0].rule_id == "DQ-06"
    assert failures[0].severity == WARNING
    assert validate_positive_sales(pl, financials={"TCS"}) == []


def test_dq07_year_format() -> None:
    tables = {
        "profitandloss": pd.DataFrame({"company_id": ["TCS"], "year": ["PARSE_ERROR"]})
    }
    failures = validate_year_format(tables)
    assert failures[0].rule_id == "DQ-07"
    assert failures[0].severity == CRITICAL


def test_dq08_ticker_format() -> None:
    companies = pd.DataFrame({"id": ["A"]})
    tables = {
        "companies": companies,
        "profitandloss": pd.DataFrame({"company_id": ["A"], "year": ["2023-03"]}),
    }
    failures = validate_ticker_format(tables, companies)
    assert failures
    assert all(failure.rule_id == "DQ-08" for failure in failures)
    assert all(failure.severity == CRITICAL for failure in failures)


def test_dq09_net_cash() -> None:
    cf = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "operating_activity": [100.0],
            "investing_activity": [-30.0],
            "financing_activity": [-20.0],
            "net_cash_flow": [80.0],
        }
    )
    failures = validate_net_cash(cf)
    assert failures[0].rule_id == "DQ-09"
    assert failures[0].severity == WARNING


def test_dq10_fixed_assets() -> None:
    bs = pd.DataFrame(
        {"company_id": ["TCS"], "year": ["2023-03"], "fixed_assets": [-5.0]}
    )
    failures = validate_fixed_assets(bs)
    assert failures[0].rule_id == "DQ-10"
    assert failures[0].severity == WARNING


def test_dq11_tax_range() -> None:
    pl = pd.DataFrame(
        {"company_id": ["TCS"], "year": ["2023-03"], "tax_percentage": [75.0]}
    )
    failures = validate_tax_range(pl)
    assert failures[0].rule_id == "DQ-11"
    assert failures[0].severity == WARNING


def test_dq12_dividend_cap() -> None:
    pl = pd.DataFrame(
        {"company_id": ["TCS"], "year": ["2023-03"], "dividend_payout": [250.0]}
    )
    failures = validate_dividend_cap(pl)
    assert failures[0].rule_id == "DQ-12"
    assert failures[0].severity == WARNING


def test_dq13_document_urls() -> None:
    documents = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "Year": [2024],
            "Annual_Report": ["https://example.com/report.pdf"],
        }
    )
    failures = validate_document_urls(documents, url_checker=lambda url: False)
    assert failures[0].rule_id == "DQ-13"
    assert failures[0].severity == WARNING


def test_dq14_eps_sign() -> None:
    pl = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "net_profit": [100.0],
            "eps": [-5.0],
        }
    )
    failures = validate_eps_sign(pl)
    assert failures[0].rule_id == "DQ-14"
    assert failures[0].severity == WARNING


def test_dq15_bs_strict_balance() -> None:
    bs = pd.DataFrame(
        {
            "company_id": ["TCS"],
            "year": ["2023-03"],
            "total_assets": [1000.0],
            "total_liabilities": [999.5],
        }
    )
    failures = validate_bs_strict_balance(bs)
    assert failures[0].rule_id == "DQ-15"
    assert failures[0].severity == INFO


def test_dq16_coverage() -> None:
    pl = pd.DataFrame(
        {
            "company_id": ["TCS"] * 3,
            "year": ["2021-03", "2022-03", "2023-03"],
        }
    )
    empty = pd.DataFrame({"company_id": [], "year": []})
    failures = validate_coverage(pl, empty, empty)
    assert failures[0].rule_id == "DQ-16"
    assert failures[0].severity == WARNING
