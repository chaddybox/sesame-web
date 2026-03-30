"""
Sesame — Modernized  |  Web App
Main entry point. Shows a login gate, then the home/dashboard page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from utils import require_auth, show_sidebar_user

st.set_page_config(
    page_title="Sesame — Modernized",
    page_icon="🌱",
    layout="wide",
)

user = require_auth()
show_sidebar_user()

st.markdown(
    "<div style='font-size:96px; line-height:1.1; padding: 12px 0;'>🌱</div>",
    unsafe_allow_html=True,
)
st.title("Sesame — Modernized")
st.markdown("##### Nutrient Economics for Dairy Nutritionists")
st.divider()

st.markdown("""
Welcome! Use the navigation on the left to get started:

| Page | What it does |
|---|---|
| **Data Tables** | Upload, view, and edit your feed ingredient / nutrient tables |
| **Run Analysis** | Select a table and preset, then run the Sesame estimator |
| **My Results** | Browse and download outputs from past runs |
| **About** | Background, workflow guide, and scientific references |
""")

st.info("👋 **New user?** Start by heading to the **About** section for background and instructions.")
st.markdown("""
<style>
[data-testid="stPageLink"] a {
    background-color: rgba(28, 131, 225, 0.1);
    border: 1px solid rgba(28, 131, 225, 0.3);
    border-radius: 0.5rem;
    padding: 0.4rem 1rem;
    display: inline-block;
    margin-top: -8px;
}
</style>
""", unsafe_allow_html=True)
st.page_link("pages/4_About.py", label="Go to About")
