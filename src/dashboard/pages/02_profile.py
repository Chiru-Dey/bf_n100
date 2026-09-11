"""Company Profile — KPI tiles and 10-year historical charts."""

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_companies, get_pl, get_ratios
from src.dashboard.utils.profile_helpers import format_kpi_tile

st.title("🏢 Company Profile")

companies = get_companies()
if companies.empty:
    st.error("Companies table is empty.")
    st.stop()

tickers = sorted(companies["id"].tolist())
selected_ticker = st.sidebar.selectbox("Select a Company", tickers, index=tickers.index("TCS") if "TCS" in tickers else 0)

st.header(selected_ticker)

ratios = get_ratios(selected_ticker)
pl = get_pl(selected_ticker)

if ratios.empty:
    st.warning(f"No ratio data available for {selected_ticker}.")
    st.stop()

latest = ratios.sort_values("year").tail(1).iloc[0]

st.subheader("Latest KPI Snapshot")
col1, col2, col3, col4 = st.columns(4)
col1.metric("ROE (%)", format_kpi_tile(latest.get("return_on_equity_pct")))
col2.metric("ROCE (%)", format_kpi_tile(latest.get("return_on_capital_employed_pct")))
col3.metric("Debt / Equity", format_kpi_tile(latest.get("debt_to_equity"), suffix="", precision=2))
col4.metric("Asset Turnover", format_kpi_tile(latest.get("asset_turnover"), suffix="x", precision=2))

col5, col6, col7, col8 = st.columns(4)
col5.metric("OPM (%)", format_kpi_tile(latest.get("operating_profit_margin_pct")))
col6.metric("NPM (%)", format_kpi_tile(latest.get("net_profit_margin_pct")))
col7.metric("FCF (Cr)", format_kpi_tile(latest.get("free_cash_flow_cr"), suffix="", precision=0))
col8.metric("Composite Score", format_kpi_tile(latest.get("composite_quality_score"), suffix="/100", precision=1))

st.subheader("📊 10-Year Financial Trends")

if not pl.empty:
    fig_sales_pat = px.bar(
        pl,
        x="year",
        y=["sales", "net_profit"],
        barmode="group",
        title="Sales vs Net Profit (Cr)",
    )
    st.plotly_chart(fig_sales_pat, width="stretch")

    fig_margins = px.line(
        ratios,
        x="year",
        y=["operating_profit_margin_pct", "net_profit_margin_pct"],
        title="Profit Margins (%)",
        markers=True,
    )
    st.plotly_chart(fig_margins, width="stretch")
    
    fig_returns = px.line(
        ratios,
        x="year",
        y=["return_on_equity_pct", "return_on_capital_employed_pct"],
        title="Return Ratios (ROE vs ROCE %)",
        markers=True,
    )
    st.plotly_chart(fig_returns, width="stretch")
else:
    st.info("No P&L history available for charting.")