"""Shared cached database loader for the Streamlit dashboard."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"


def _get_conn() -> sqlite3.Connection:
    """Return a SQLite connection to the Nifty 100 database."""
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    """Return the full companies master table."""
    with _get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM companies", conn)


@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    """Return the sectors mapping table."""
    with _get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM sectors", conn)


@st.cache_data(ttl=600)
def get_ratios(ticker: str, year: str | None = None) -> pd.DataFrame:
    """Return financial ratios for a ticker, optionally filtered by year."""
    with _get_conn() as conn:
        if year:
            return pd.read_sql_query(
                "SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?",
                conn,
                params=(ticker, year),
            )
        return pd.read_sql_query(
            "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )


@st.cache_data(ttl=600)
def get_pl(ticker: str) -> pd.DataFrame:
    """Return P&L history for a ticker."""
    with _get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )


@st.cache_data(ttl=600)
def get_bs(ticker: str) -> pd.DataFrame:
    """Return Balance Sheet history for a ticker."""
    with _get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )


@st.cache_data(ttl=600)
def get_cf(ticker: str) -> pd.DataFrame:
    """Return Cash Flow history for a ticker."""
    with _get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM cashflow WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )


@st.cache_data(ttl=600)
def get_peers(group_name: str) -> pd.DataFrame:
    """Return peer percentile data for a specific peer group."""
    with _get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM peer_percentiles WHERE peer_group_name = ?",
            conn,
            params=(group_name,),
        )


@st.cache_data(ttl=600)
def get_valuation(ticker: str) -> pd.DataFrame:
    """Return historical valuation multiples for a ticker."""
    with _get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM market_cap WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )
        
@st.cache_data(ttl=600)
def get_all_ratios_latest() -> pd.DataFrame:
    """Return latest annual ratios per company with sector, March-preferred."""
    with _get_conn() as conn:
        ratios = pd.read_sql_query(
            "SELECT r.*, s.broad_sector FROM financial_ratios r "
            "JOIN sectors s ON r.company_id = s.company_id",
            conn,
        )
    march = ratios[ratios["year"].str.endswith("-03")]
    latest = march.sort_values("year").groupby("company_id").tail(1)
    missing = set(ratios["company_id"]) - set(latest["company_id"])
    if missing:
        fallback = (
            ratios[ratios["company_id"].isin(missing)]
            .sort_values("year")
            .groupby("company_id")
            .tail(1)
        )
        latest = pd.concat([latest, fallback])
    return latest

@st.cache_data(ttl=600)
def get_screener_universe() -> pd.DataFrame:
    from src.screener.engine import build_screener_universe
    return build_screener_universe()

@st.cache_data(ttl=600)
def get_cf_latest() -> pd.DataFrame:
    """Return the latest cash flow row per company."""
    with _get_conn() as conn:
        return pd.read_sql_query(
            "SELECT c1.* FROM cashflow c1 "
            "INNER JOIN (SELECT company_id, MAX(year) as max_year FROM cashflow GROUP BY company_id) c2 "
            "ON c1.company_id = c2.company_id AND c1.year = c2.max_year",
            conn,
        )
@st.cache_data(ttl=600)
def get_pl_latest() -> pd.DataFrame:
    """Return the latest P&L row per company."""
    with _get_conn() as conn:
        return pd.read_sql_query(
            "SELECT p1.company_id, p1.year, p1.sales, p1.net_profit "
            "FROM profitandloss p1 "
            "INNER JOIN (SELECT company_id, MAX(year) AS max_year "
            "FROM profitandloss GROUP BY company_id) p2 "
            "ON p1.company_id = p2.company_id AND p1.year = p2.max_year",
            conn,
        )

@st.cache_data(ttl=600)
def get_cfo_pat_scores() -> pd.DataFrame:
    """Return trailing five-year mean CFO/PAT score per company-year."""
    with _get_conn() as conn:
        frame = pd.read_sql_query(
            "SELECT c.company_id, c.year, c.operating_activity AS cfo, p.net_profit "
            "FROM cashflow c JOIN profitandloss p "
            "ON c.company_id = p.company_id AND c.year = p.year",
            conn,
        )

    def _ratio(row):
        if pd.isna(row["net_profit"]) or row["net_profit"] == 0:
            return None
        if pd.isna(row["cfo"]):
            return None
        return float(row["cfo"]) / float(row["net_profit"])

    frame["ratio"] = frame.apply(_ratio, axis=1)
    frame = frame.sort_values(["company_id", "year"])
    scores: list[dict] = []
    for company, group in frame.groupby("company_id"):
        ratios = list(group["ratio"])
        for offset, (_, row) in enumerate(group.iterrows()):
            window = [v for v in ratios[max(0, offset - 4) : offset + 1] if pd.notna(v)]
            current = ratios[offset]
            scores.append(
                {
                    "company_id": company,
                    "year": row["year"],
                    "cfo_quality_score": sum(window) / len(window)
                    if pd.notna(current) and window
                    else None,
                }
            )
    return pd.DataFrame(scores)