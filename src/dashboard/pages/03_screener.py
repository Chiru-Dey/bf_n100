import streamlit as st

from src.dashboard.utils.db import get_screener_universe
from src.screener.engine import apply_filters

st.title("🔍 Financial Screener")

DEFAULTS = {
    "roe_min": 15.0,
    "de_max": 1.0,
    "fcf_min": 0.0,
    "rev_cagr_min": 10.0,
    "pat_cagr_min": 10.0,
    "opm_min": 15.0,
    "pe_max": 30.0,
    "pb_max": 5.0,
    "div_yield_min": 1.0,
    "icr_min": 3.0,
}

PRESETS = {
    "Quality": dict(DEFAULTS),
    "Value": {
        "roe_min": 0.0,
        "de_max": 2.0,
        "fcf_min": 0.0,
        "rev_cagr_min": 0.0,
        "pat_cagr_min": 0.0,
        "opm_min": 0.0,
        "pe_max": 25.0,
        "pb_max": 6.0,
        "div_yield_min": 1.0,
        "icr_min": 0.0,
    },
    "Growth": {
        "roe_min": 0.0,
        "de_max": 2.0,
        "fcf_min": 0.0,
        "rev_cagr_min": 15.0,
        "pat_cagr_min": 20.0,
        "opm_min": 0.0,
        "pe_max": 100.0,
        "pb_max": 20.0,
        "div_yield_min": 0.0,
        "icr_min": 0.0,
    },
}

for key, default in DEFAULTS.items():
    st.session_state.setdefault(key, default)


def apply_preset(preset_name: str) -> None:
    """Callback updating slider state before widgets render on rerun."""
    for key, value in PRESETS[preset_name].items():
        st.session_state[key] = value


universe = get_screener_universe()

with st.sidebar:
    st.header("Filters")
    roe_min = st.slider("ROE Min (%)", 0.0, 50.0, key="roe_min")
    de_max = st.slider("D/E Max", 0.0, 10.0, key="de_max")
    fcf_min = st.slider("FCF Min (Cr)", -10000.0, 50000.0, key="fcf_min")
    rev_cagr_min = st.slider("Rev CAGR 5yr Min (%)", -20.0, 50.0, key="rev_cagr_min")
    pat_cagr_min = st.slider("PAT CAGR 5yr Min (%)", -20.0, 50.0, key="pat_cagr_min")
    opm_min = st.slider("OPM Min (%)", 0.0, 50.0, key="opm_min")
    pe_max = st.slider("P/E Max", 0.0, 100.0, key="pe_max")
    pb_max = st.slider("P/B Max", 0.0, 20.0, key="pb_max")
    div_yield_min = st.slider("Div Yield Min (%)", 0.0, 10.0, key="div_yield_min")
    icr_min = st.slider("ICR Min", 0.0, 20.0, key="icr_min")

    st.divider()
    st.subheader("Presets")
    c1, c2, c3 = st.columns(3)
    c1.button("Quality", on_click=apply_preset, args=("Quality",))
    c2.button("Value", on_click=apply_preset, args=("Value",))
    c3.button("Growth", on_click=apply_preset, args=("Growth",))

filters = {
    "roe_min": roe_min,
    "de_max": de_max,
    "fcf_min": fcf_min,
    "revenue_cagr_5yr_min": rev_cagr_min,
    "pat_cagr_5yr_min": pat_cagr_min,
    "opm_min": opm_min,
    "pe_max": pe_max,
    "pb_max": pb_max,
    "dividend_yield_min": div_yield_min,
    "icr_min": icr_min,
}

results = apply_filters(universe, filters)

st.subheader(f"{len(results)} companies match your filters")

cols = [
    "company_id",
    "broad_sector",
    "composite_quality_score",
    "return_on_equity_pct",
    "debt_to_equity",
    "free_cash_flow_cr",
    "revenue_cagr_5yr",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct",
]
display_cols = [c for c in cols if c in results.columns]

st.dataframe(results[display_cols], width="stretch", hide_index=True)

csv = results[display_cols].to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", csv, "screener_results.csv", "text/csv")
