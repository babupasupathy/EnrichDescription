"""EnrichDescription Streamlit entry point: loads secrets and sets up the sidebar pages."""

import os

import streamlit as st

# Streamlit Community Cloud keeps secrets in st.secrets; expose them as env vars for
# pydantic-settings and LangSmith. Locally, a .env file is used instead.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k.upper(), _v)
except FileNotFoundError:
    pass

st.set_page_config(page_title="EnrichDescription", page_icon="🏷️", layout="centered")

st.navigation([
    st.Page("app_pages/generate.py", title="Generate listings", icon="🏷️", default=True),
    st.Page("app_pages/prd.py", title="Product requirements", icon="📄"),
    st.Page("app_pages/architecture.py", title="Architecture", icon="🧩"),
    st.Page("app_pages/rules.py", title="Marketplace rules", icon="⚖️"),
], position="sidebar").run()
