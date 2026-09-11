import streamlit as st
import plotly.express as px
from src.dashboard.utils.db import get_companies, get_pl, get_ratios

st.title("📈 Trend Analysis")

companies = get_companies()
if companies.empty:
    st.error("Companies table is empty.")
    st.stop()

tickers = sorted(companies["id"].tolist())
selected_ticker = st.sidebar.selectbox(
    "Select a Company", tickers, index=tickers.index("TCS") if "TCS" in tickers else 0, key="trend_ticker"
)

st.header(f"{selected_ticker} — 10-Year Historical Trends")

ratios = get_ratios(selected_ticker)
pl = get_pl(selected_ticker)

if ratios.empty and pl.empty:
    st.warning(f"No historical data available for {selected_ticker}.")
    st.stop()

st.subheader("Profitability Margins (%)")
if not ratios.empty:
    fig_margins = px.line(
        ratios, x="year", y=["operating_profit_margin_pct", "net_profit_margin_pct"], 
        markers=True, title="OPM vs NPM"
    )
    st.plotly_chart(fig_margins, width="stretch")

st.subheader("Return Ratios (%)")
if not ratios.empty:
    fig_returns = px.line(
        ratios, x="year", y=["return_on_equity_pct", "return_on_capital_employed_pct"], 
        markers=True, title="ROE vs ROCE"
    )
    st.plotly_chart(fig_returns, width="stretch")

st.subheader("Growth Metrics (5-Year CAGR %)")
if not ratios.empty:
    fig_growth = px.line(
        ratios, x="year", y=["revenue_cagr_5yr", "pat_cagr_5yr", "eps_cagr_5yr"], 
        markers=True, title="Revenue, PAT, and EPS Growth"
    )
    st.plotly_chart(fig_growth, width="stretch")

st.subheader("Absolute Scale (Cr)")
if not pl.empty:
    fig_scale = px.bar(
        pl, x="year", y=["sales", "net_profit"], barmode="group", title="Sales vs Net Profit"
    )
    st.plotly_chart(fig_scale, width="stretch")