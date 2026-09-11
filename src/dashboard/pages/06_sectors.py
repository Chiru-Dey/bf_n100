import streamlit as st
import plotly.express as px
from src.dashboard.utils.db import get_all_ratios_latest, get_pl_latest

st.title("🏭 Sector Analysis")

df = get_all_ratios_latest()
if df.empty:
    st.warning("No cross-sectional data available.")
    st.stop()

df = df.merge(get_pl_latest(), on="company_id", how="left", suffixes=("", "_pl"))

st.subheader("Sector Medians")
medians = df.groupby("broad_sector").agg(
    roe_median=("return_on_equity_pct", "median"),
    roce_median=("return_on_capital_employed_pct", "median"),
    de_median=("debt_to_equity", "median"),
    npm_median=("net_profit_margin_pct", "median"),
    composite_median=("composite_quality_score", "median"),
    sales_median=("sales", "median"),
).round(2).reset_index()
st.dataframe(medians, width="stretch", hide_index=True)

st.subheader("Sector Bubble Chart (ROE vs ROCE)")
st.caption("Bubble size represents Sales (Cr) as a proxy for scale.")
plot_df = df.dropna(
    subset=["sales", "return_on_equity_pct", "return_on_capital_employed_pct"]
)
fig = px.scatter(
    plot_df,
    x="return_on_equity_pct",
    y="return_on_capital_employed_pct",
    size="sales",
    color="broad_sector",
    hover_name="company_id",
    title="Company Positioning by Sector",
    labels={
        "return_on_equity_pct": "ROE (%)",
        "return_on_capital_employed_pct": "ROCE (%)",
    },
    size_max=60,
)
fig.update_traces(marker_line_width=1, marker_line_color="DarkSlateGrey")
st.plotly_chart(fig, width="stretch")