"""Nifty 100 Analytics — Streamlit Dashboard Entry Point."""

import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/01_home.py", title="Home", icon="🏠"),
    st.Page("pages/02_profile.py", title="Company Profile", icon="🏢"),
    st.Page("pages/03_screener.py", title="Financial Screener", icon="🔍"),
    st.Page("pages/04_peers.py", title="Peer Comparison", icon="🤝"),
    st.Page("pages/05_trends.py", title="Trend Analysis", icon="📈"),
    st.Page("pages/06_sectors.py", title="Sector Analysis", icon="🏭"),
    st.Page("pages/07_capital.py", title="Capital Allocation", icon="💰"),
    st.Page("pages/08_reports.py", title="Annual Reports", icon="📄"),
]

nav = st.navigation(pages)
nav.run()