"""
My Results page — browse, view, and download outputs from past analysis runs.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st
from utils import download_file, get_supabase, require_auth, show_sidebar_user

st.set_page_config(page_title="My Results — Sesame", layout="wide")
user = require_auth()
show_sidebar_user()

sb = get_supabase()
user_id = str(user.id)

st.title("My Results")
st.caption("All of your past analysis runs, most recent first.")

resp = (
    sb.table("analysis_runs")
    .select("*, data_tables(name)")
    .eq("user_id", user_id)
    .order("created_at", desc=True)
    .execute()
)
runs = resp.data

if not runs:
    st.info("No runs yet — head to **Run Analysis** to get started.")
    st.stop()

for run in runs:
    table_info = run.get("data_tables") or {}
    table_name = table_info.get("name", "Unknown table")
    ts = run.get("created_at", "")[:16].replace("T", " ")
    label = f"**{run['preset_label']}**  ·  {table_name}  ·  {ts}"

    with st.expander(label):
        out_resp = (
            sb.table("run_outputs")
            .select("*")
            .eq("run_id", run["id"])
            .execute()
        )
        outputs = {o["file_type"]: o for o in out_resp.data}

        if not outputs:
            st.warning("No output files found for this run.")
            continue

        chart_tab, data_tab = st.tabs(["Charts", "Data"])

        with chart_tab:
            for key, title in [
                ("bar_chart_png", "Actual vs Predicted Feed Prices"),
                ("opportunity_png", "Opportunity Plot"),
            ]:
                if key not in outputs:
                    continue
                try:
                    img = download_file("run-outputs", outputs[key]["storage_path"])
                    st.subheader(title)
                    st.image(img, use_container_width=True)
                    st.download_button(
                        f"Download {title} (PNG)",
                        data=img,
                        file_name=f"{key}.png",
                        mime="image/png",
                        key=f"dl_{run['id']}_{key}",
                    )
                except Exception as e:
                    st.warning(f"Could not load {title}: {e}")

        with data_tab:
            for key, title, fname in [
                ("summary_csv", "Feed Results",  "feed_results.csv"),
                ("coef_csv",    "Shadow Prices", "shadow_prices.csv"),
            ]:
                if key not in outputs:
                    continue
                try:
                    csv_bytes = download_file("run-outputs", outputs[key]["storage_path"])
                    df = pd.read_csv(io.BytesIO(csv_bytes))
                    st.subheader(title)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button(
                        f"Download {title} (CSV)",
                        data=csv_bytes,
                        file_name=fname,
                        mime="text/csv",
                        key=f"dl_{run['id']}_{key}",
                    )
                except Exception as e:
                    st.warning(f"Could not load {title}: {e}")
