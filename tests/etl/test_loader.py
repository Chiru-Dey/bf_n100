import sqlite3

import pandas as pd
import pytest

from src.etl.loader import (
    clean_tables,
    dedup_annual_keys,
    reject_invalid_tickers,
    reject_unparseable_years,
    write_table,
)


def test_reject_unparseable_years() -> None:
    frame = pd.DataFrame(
        {"company_id": ["TCS", "TCS"], "year": ["2023-03", "PARSE_ERROR"]}
    )
    cleaned = reject_unparseable_years(frame, "year")
    assert cleaned["year"].tolist() == ["2023-03"]


def test_reject_invalid_tickers_missing() -> None:
    frame = pd.DataFrame(
        {"company_id": ["TCS", "MISSING"], "year": ["2023-03", "2023-03"]}
    )
    cleaned = reject_invalid_tickers(frame, "company_id")
    assert cleaned["company_id"].tolist() == ["TCS"]


def test_reject_invalid_tickers_length() -> None:
    frame = pd.DataFrame({"company_id": ["TCS", "A"], "year": ["2023-03", "2023-03"]})
    cleaned = reject_invalid_tickers(frame, "company_id")
    assert cleaned["company_id"].tolist() == ["TCS"]


def test_dedup_annual_keys_keeps_last() -> None:
    frame = pd.DataFrame(
        {
            "company_id": ["TCS", "TCS"],
            "year": ["2023-03", "2023-03"],
            "sales": [1.0, 2.0],
        }
    )
    cleaned = dedup_annual_keys(frame)
    assert cleaned["sales"].tolist() == [2.0]


def test_clean_tables_removes_orphans() -> None:
    tables = {
        "companies": pd.DataFrame({"id": ["TCS"]}),
        "profitandloss": pd.DataFrame(
            {"company_id": ["TCS", "ZZZ"], "year": ["2023-03", "2023-03"]}
        ),
    }
    cleaned = clean_tables(tables)
    assert cleaned["profitandloss"]["company_id"].tolist() == ["TCS"]


def test_clean_tables_dedups_annual_keys() -> None:
    tables = {
        "companies": pd.DataFrame({"id": ["TCS"]}),
        "profitandloss": pd.DataFrame(
            {
                "company_id": ["TCS", "TCS"],
                "year": ["2023-03", "2023-03"],
                "sales": [1.0, 2.0],
            }
        ),
    }
    cleaned = clean_tables(tables)
    assert cleaned["profitandloss"]["sales"].tolist() == [2.0]


def test_init_schema_creates_ten_tables(db_conn) -> None:
    names = [
        row[0]
        for row in db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    assert len(names) == 10


def test_foreign_keys_enabled(db_conn) -> None:
    assert db_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_write_table_roundtrip(db_conn) -> None:
    frame = pd.DataFrame(
        {
            "id": ["TCS"],
            "company_name": ["Tata Consultancy Services Ltd"],
            "face_value": [1.0],
        }
    )
    count = write_table(db_conn, "companies", frame)
    assert count == 1
    row = db_conn.execute(
        "SELECT id, company_name, face_value FROM companies"
    ).fetchone()
    assert row == ("TCS", "Tata Consultancy Services Ltd", 1.0)


def test_write_table_rejects_orphan(db_conn) -> None:
    frame = pd.DataFrame({"company_id": ["ZZZ"], "year": ["2023-03"], "sales": [1.0]})
    with pytest.raises(sqlite3.IntegrityError):
        write_table(db_conn, "profitandloss", frame)
