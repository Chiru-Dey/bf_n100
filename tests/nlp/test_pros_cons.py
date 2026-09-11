"""Unit tests for the pros and cons rule engine."""

import pandas as pd

from src.nlp.pros_cons_generator import (
    CON,
    PRO,
    con_de_elevated,
    con_roce_low,
    evaluate_company,
    pro_debt_free,
    pro_roe_sustained,
)


def _hist(**overrides) -> pd.DataFrame:
    base = {
        "year": ["2022-03", "2023-03", "2024-03"],
        "roe": [22.0, 24.0, 26.0],
        "roce": [18.0, 19.0, 20.0],
        "opm": [26.0, 27.0, 28.0],
        "de": [0.0, 0.0, 0.0],
        "fcf": [100.0, 120.0, 140.0],
        "icr": [None, None, None],
        "icr_label": ["Debt Free", "Debt Free", "Debt Free"],
        "payout": [40.0, 42.0, 45.0],
        "eps": [10.0, 11.0, 12.0],
        "sales": [1000.0, 1100.0, 1200.0],
        "net_profit": [100.0, 110.0, 120.0],
        "total_assets": [800.0, 900.0, 1000.0],
        "borrowings": [0.0, 0.0, 0.0],
        "investments": [0.0, 0.0, 0.0],
        "operating_profit": [260.0, 297.0, 336.0],
        "cfo": [110.0, 130.0, 150.0],
        "rev_cagr_5yr": [12.0, 13.0, 14.0],
        "pat_cagr_5yr": [15.0, 16.0, 18.0],
        "eps_cagr_5yr": [14.0, 15.0, 16.0],
        "div_yield": [1.0, 1.1, 1.2],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_pro_roe_sustained_text_and_confidence() -> None:
    rule_id, text, confidence = pro_roe_sustained(_hist(), "Information Technology")
    assert rule_id == "PRO-01"
    assert text.startswith("Consistently high return on equity")
    assert confidence > 60.0


def test_pro_roe_sustained_not_triggered_at_threshold() -> None:
    hist = _hist(roe=[20.0, 20.0, 20.0])
    assert pro_roe_sustained(hist, "Information Technology") is None


def test_pro_debt_free() -> None:
    rule_id, _, confidence = pro_debt_free(_hist(), "Information Technology")
    assert rule_id == "PRO-03"
    assert confidence == 90.0


def test_con_de_elevated_skips_financials() -> None:
    hist = _hist(de=[3.0, 3.2, 3.5])
    assert con_de_elevated(hist, "Financials") is None
    rule_id, text, _ = con_de_elevated(hist, "Materials")
    assert rule_id == "CON-01"
    assert "3.50" in text


def test_con_roce_low() -> None:
    hist = _hist(roce=[8.0, 7.5, 7.0])
    rule_id, _, confidence = con_roce_low(hist, "Materials")
    assert rule_id == "CON-10"
    assert confidence > 60.0


def test_evaluate_company_guarantees_pro_and_con() -> None:
    rows = evaluate_company("TCS", "Information Technology", _hist())
    types = {row["type"] for row in rows}
    assert PRO in types and CON in types
    assert all(row["confidence_pct"] > 60.0 for row in rows)


def test_evaluate_company_uses_fallback_con_for_clean_company() -> None:
    rows = evaluate_company("TCS", "Information Technology", _hist())
    con_ids = [row["rule_id"] for row in rows if row["type"] == CON]
    assert con_ids == ["CON-13"]
