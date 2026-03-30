"""
About page — overview, workflow, background, and acknowledgments.
"""
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from utils import require_auth, show_sidebar_user

_ASSETS = Path(__file__).resolve().parents[1] / "assets"

st.set_page_config(page_title="About — Sesame", layout="wide")
user = require_auth()
show_sidebar_user()


def _img_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


st.title("About Sesame — Modernized")
st.markdown("##### Nutrient Economics for Dairy Nutritionists")
st.divider()

# ---------------------------------------------------------------------------
st.subheader("What This Application Does")
st.markdown("""
Sesame is a tool for evaluating feed ingredient prices based on nutrient composition.
It helps nutritionists and feed analysts:

- Load a feed library containing ingredient prices and nutrient profiles
- Estimate **nutrient shadow prices** — the implicit market value of each nutrient
- Calculate **break-even nutrient values** for individual ingredients
- Compare **actual feed prices** against model-predicted prices
- Identify potential **purchase opportunities** (undervalued ingredients)
- Export summary tables and charts for further review
""")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Typical Workflow")
st.markdown("""
1. Go to **Data Tables** and add the NASEM Feed Library to your account (or upload your own).
2. Fill in current market prices for the feeds you want to evaluate.
3. Go to **Run Analysis**, select your table and a preset nutrient combination.
4. Review the shadow prices, feed results, and opportunity charts in your browser.
5. Download any outputs you need, or revisit them later in **My Results**.
""")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Presets")
st.markdown("""
Presets define which nutrients are included in the regression model.
Choose a preset that matches the nutrients you have reliable data for:

| # | Preset | Nutrients |
|---|---|---|
| 1 | Basic Energy + Protein | DE, CP |
| 2 | Energy + Digestible RUP Protein | DE, dRUP_prot |
| 3 | Energy + Digestible RUP Protein + Digestible NDF | DE, dRUP_prot, NDFd |
| 4 | Energy + Digestible RUP Protein + Digestible NDF + Fat | DE, dRUP_prot, NDFd, TFA |
| 5 | NASEM Eq. 6-6 Milk Protein Yield *(locked)* | NASEM MP composite |
| 6 | Branched-Chain Amino Acids (dRUP) | Leu, Ile, Val |
| 7 | Lys, Met, His (dRUP) | Lys, Met, His |
| 8 | Fat (TFA, % DM) | Total Fatty Acids |

The **iterative diagnostic screening** option uses Sesame 4-style iterative reweighting.
Rather than removing outlier feeds entirely, unusual feeds are progressively downweighted
based on their studentized residuals — keeping all data in the model while reducing the
influence of feeds that don't fit the overall trend.
""")

st.divider()

# ---------------------------------------------------------------------------
st.subheader("Scientific Background")
st.markdown("""
The method implemented here is based on:

> **St-Pierre, N.R., and D. Glamocic. (2000).**
> *Estimating unit costs of nutrients from market prices of feedstuffs.*
> Journal of Dairy Science, 83:1402–1411.
> https://doi.org/10.3168/jds.S0022-0302(00)75009-0

The original SESAME software was developed at **The Ohio State University**.
This modern implementation was developed at the **University of Nebraska–Lincoln**
in collaboration with **Standard Dairy Consultants**.
""")

ne_logo = _ASSETS / "NE_logo.png"
sdc_logo = _ASSETS / "SDC_logo.png"
if ne_logo.exists() and sdc_logo.exists():
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:32px; padding-top:12px;">
            <img src="data:image/png;base64,{_img_b64(ne_logo)}"
                 style="height:72px; width:auto;">
            <img src="data:image/png;base64,{_img_b64(sdc_logo)}"
                 style="height:72px; width:auto;">
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ---------------------------------------------------------------------------
st.subheader("License")
st.markdown("This software is intended for research and educational use.")
