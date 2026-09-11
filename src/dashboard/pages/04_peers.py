import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.dashboard.utils.db import get_peers, get_all_ratios_latest
from src.analytics.peer import load_peer_groups, METRICS_TO_RANK

st.title("🤝 Peer Comparison")

groups = load_peer_groups()
group_names = sorted(groups["peer_group_name"].unique())
selected_group = st.selectbox("Select Peer Group", group_names)

peers = get_peers(selected_group)
ratios = get_all_ratios_latest()

if peers.empty:
    st.warning("No peer data available.")
    st.stop()

pivot = peers.pivot(index="company_id", columns="metric", values="percentile_rank")

st.subheader(f"Percentile Radar — {selected_group}")

fig = go.Figure()
labels = [m.replace("_pct", "").replace("_", " ").title() for m in METRICS_TO_RANK]

for company in pivot.index:
    is_bench = peers[peers["company_id"] == company]["is_benchmark"].max()
    vals = [pivot.loc[company, m] if m in pivot.columns else 0 for m in METRICS_TO_RANK]
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]],
        theta=labels + [labels[0]],
        fill="toself",
        name=f"{company} {'⭐' if is_bench else ''}",
        opacity=0.5 if not is_bench else 1.0
    ))

fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=True)
st.plotly_chart(fig, width="stretch")

st.subheader("Side-by-Side KPI Table")
group_companies = peers["company_id"].unique()
group_ratios = ratios[ratios["company_id"].isin(group_companies)]

benchmarks = peers[peers["is_benchmark"] == 1]["company_id"].tolist()
bench = benchmarks[0] if benchmarks else None

display_cols = ["company_id", "return_on_equity_pct", "return_on_capital_employed_pct", "net_profit_margin_pct", "debt_to_equity", "free_cash_flow_cr", "revenue_cagr_5yr", "composite_quality_score"]
display_cols = [c for c in display_cols if c in group_ratios.columns]

table_df = group_ratios[display_cols].copy()
if bench:
    table_df["is_benchmark"] = table_df["company_id"] == bench
    table_df = table_df.sort_values("is_benchmark", ascending=False).drop(columns=["is_benchmark"])

st.dataframe(table_df, width="stretch", hide_index=True)