"""Home Overview — Market health, sector donut, and top companies."""

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_all_ratios_latest
from src.dashboard.utils.home_helpers import (
    build_sector_donut_data,
    compute_market_health,
    get_top_companies,
)

st.title("🏠 Market Health Overview")

df = get_all_ratios_latest()
if df.empty:
    st.warning("No data available. Run the ETL and Ratio Engine first.")
    st.stop()

above, below = compute_market_health(df)

col1, col2 = st.columns(2)
col1.metric("🟢 Companies Above Benchmark (Score >= 50)", above)
col2.metric("🔴 Companies Below Benchmark (Score < 50)", below)

st.subheader("Sector Distribution")
donut_data = build_sector_donut_data(df)
fig = px.pie(
    donut_data,
    values="count",
    names="broad_sector",
    hole=0.4,
    title="Nifty 100 Sector Breakdown",
)
fig.update_traces(textposition="inside", textinfo="percent+label")
st.plotly_chart(fig, width="stretch")

st.subheader("🏆 Top 5 Quality Compounders")
top_df = get_top_companies(df, n=5)
st.dataframe(top_df, width="stretch", hide_index=True)
