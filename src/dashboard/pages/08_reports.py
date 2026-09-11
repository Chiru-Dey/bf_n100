import streamlit as st
import pandas as pd
from src.dashboard.utils.db import get_companies, get_sectors

st.title("📄 Annual Reports & Investor Relations")

companies = get_companies()
sectors = get_sectors()

if companies.empty:
    st.warning("No company directory available.")
    st.stop()

df = companies.merge(sectors, left_on="id", right_on="company_id", how="left", suffixes=("", "_sec"))

df["bse_link"] = df["id"].apply(lambda x: f"https://www.bseindia.com/corporates/List_Scrip.html?scripcode={x}")
df["nse_link"] = df["id"].apply(lambda x: f"https://www.nseindia.com/get-quotes/equity?symbol={x}")

cols = ["id", "company_name", "broad_sector", "website", "bse_link", "nse_link"]
display_df = df[cols].rename(columns={"id": "Ticker", "company_name": "Company Name", "broad_sector": "Sector", "website": "Website"})

st.subheader("Company Directory")
st.dataframe(
    display_df, 
    width="stretch", 
    hide_index=True, 
    column_config={
        "bse_link": st.column_config.LinkColumn("BSE Profile", display_text="View"),
        "nse_link": st.column_config.LinkColumn("NSE Profile", display_text="View"),
        "website": st.column_config.LinkColumn("Website", display_text="Visit")
    }
)