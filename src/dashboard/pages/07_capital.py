"""Capital Allocation Map screen with squarify treemap."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import squarify
import streamlit as st

from src.analytics.cashflow_kpis import classify_capital_allocation
from src.dashboard.utils.db import (
    get_all_ratios_latest,
    get_cf_latest,
    get_cfo_pat_scores,
)

st.title("💰 Capital Allocation Map")

ratios = get_all_ratios_latest()
cf = get_cf_latest()

if ratios.empty or cf.empty:
    st.warning("Insufficient data for capital allocation mapping.")
    st.stop()

merged = ratios.merge(
    cf[
        ["company_id", "operating_activity", "investing_activity", "financing_activity"]
    ],
    on="company_id",
    how="left",
)

if merged["operating_activity"].isna().all():
    st.error("Cash flow merge produced no matches; check company_id keys.")
    st.stop()

merged = merged.merge(get_cfo_pat_scores(), on=["company_id", "year"], how="left")
merged["pattern"] = merged.apply(
    lambda row: classify_capital_allocation(
        row["operating_activity"],
        row["investing_activity"],
        row["financing_activity"],
        row["cfo_quality_score"],
    ),
    axis=1,
)

counts = merged["pattern"].value_counts().reset_index()
counts.columns = ["pattern", "count"]

st.subheader("Distribution of Capital Allocation Patterns")
fig, ax = plt.subplots(figsize=(10, 6.2), dpi=110)
labels = [
    f"{pattern}\n{count} companies"
    for pattern, count in zip(counts["pattern"], counts["count"])
]
squarify.plot(
    sizes=counts["count"].tolist(),
    label=labels,
    color=plt.cm.Set2(range(len(counts))),
    alpha=0.85,
    ax=ax,
    text_kwargs={"fontsize": 10},
)
ax.set_title("Nifty 100 Capital Allocation Treemap")
ax.axis("off")
st.pyplot(fig)

with st.expander("Pattern counts"):
    st.dataframe(counts, width="stretch", hide_index=True)

st.subheader("Company Breakdown by Pattern")
selected_pattern = st.selectbox(
    "Filter by Pattern", ["All"] + counts["pattern"].tolist(), key="cap_filter"
)
display_df = merged[
    [
        "company_id",
        "broad_sector",
        "pattern",
        "free_cash_flow_cr",
        "composite_quality_score",
    ]
]
if selected_pattern != "All":
    display_df = display_df[display_df["pattern"] == selected_pattern]
st.dataframe(display_df, width="stretch", hide_index=True)
