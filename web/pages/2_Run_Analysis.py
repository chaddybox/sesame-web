"""
Run Analysis page — select a data table and preset, run the Sesame estimator,
display results in-browser, and save them to the user's history.
"""
import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st
from utils import (
    PRESETS,
    coef_to_df,
    download_file,
    fit_to_df,
    get_supabase,
    make_bar_chart,
    make_opportunity_plot,
    require_auth,
    run_analysis,
    show_sidebar_user,
    summarize_input,
    upload_file,
)

st.set_page_config(page_title="Run Analysis — Sesame", layout="wide")
user = require_auth()
show_sidebar_user()

sb = get_supabase()
user_id = str(user.id)

st.title("Run Analysis")

resp = (
    sb.table("data_tables")
    .select("id, name, created_at, storage_path")
    .eq("user_id", user_id)
    .order("created_at", desc=True)
    .execute()
)
tables = resp.data

if not tables:
    st.warning("No data tables found. Please add one on the **Data Tables** page first.")
    st.stop()

table_map = {t["name"]: t for t in tables}
selected_name = st.selectbox("Select feed library table for analysis", list(table_map.keys()))
selected_table = table_map[selected_name]

preset_idx = st.selectbox(
    "Select nutrient preset for analysis",
    range(len(PRESETS)),
    format_func=lambda i: PRESETS[i]["label"],
)
preset = PRESETS[preset_idx]

iterative = st.checkbox(
    "Iterative diagnostic screening",
    help="Run an initial fit, screen the calibration set using leverage / residual "
         "diagnostics, then refit on the retained feeds.",
)

st.divider()

if st.button("Run Estimator", type="primary"):
    with st.spinner("Loading data table…"):
        try:
            csv_bytes = download_file("data-tables", selected_table["storage_path"])
        except Exception as e:
            st.error(f"Could not load data table: {e}")
            st.stop()

    cols = preset["columns"]

    with st.spinner("Checking inputs…"):
        try:
            precheck = summarize_input(csv_bytes, cols)
            usable = precheck["usable"]
            n_params = len(cols) + 1
            st.info(
                f"**Input check:** {usable} feeds usable for this preset · "
                f"{precheck['skipped_missing_required_inputs']} feeds skipped (missing required columns)"
            )
            if usable <= n_params or usable < 10:
                st.error(
                    f"**Not enough feeds to run this preset.** "
                    f"This preset estimates {n_params} parameters and requires at least 10 feeds with complete data for a meaningful result — "
                    f"only {usable} were found.\n\n"
                    f"**Tip:** The SESAME method is designed to work with a full feed library (20+ feeds). "
                    f"Add a Default Library from the Data Tables page, fill in current market prices, and run the analysis on that."
                )
                st.stop()
        except Exception as e:
            st.warning(f"Pre-check skipped: {e}")

    with st.spinner("Running analysis…"):
        try:
            result = run_analysis(csv_bytes, cols, iterative)
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()

    st.success("Analysis complete!")
    fit = result.final_fit

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Feeds in regression", len(fit.rows))
    m2.metric("Adj. R²", f"{fit.adj_r2:.4f}" if fit.adj_r2 is not None else "—")
    m3.metric("σ²", f"{fit.sigma2:.4f}" if fit.sigma2 is not None else "—")
    m4.metric("Excluded by screening", len(result.excluded_feeds))

    tab_prices, tab_feeds, tab_charts, tab_diag = st.tabs(
        ["Shadow Prices", "Feed Results", "Charts", "Diagnostics"]
    )

    with tab_prices:
        st.subheader("Nutrient Shadow Prices")
        st.dataframe(coef_to_df(fit), use_container_width=True, hide_index=True)

    with tab_feeds:
        st.subheader("Feed-Level Results")
        st.dataframe(fit_to_df(fit), use_container_width=True, hide_index=True)

    with tab_charts:
        bar_png = make_bar_chart(fit)
        opp_png = make_opportunity_plot(fit)

        st.subheader("Actual vs Predicted Feed Prices")
        st.image(bar_png, use_container_width=True)
        st.download_button("Download chart (PNG)", data=bar_png,
                           file_name="bar_chart.png", mime="image/png", key="dl_bar")

        st.subheader("Opportunity Plot")
        st.image(opp_png, use_container_width=True)
        st.download_button("Download chart (PNG)", data=opp_png,
                           file_name="opportunity_plot.png", mime="image/png", key="dl_opp")

    with tab_diag:
        st.subheader("Excluded Feeds")
        if result.excluded_feeds:
            st.dataframe(
                pd.DataFrame([{
                    "Feed": x.name,
                    "Reason": x.reason,
                    "Leverage": x.leverage,
                    "Studentized Residual": x.student_residual,
                } for x in result.excluded_feeds]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No feeds were excluded by diagnostic screening.")

        st.subheader("Pre-Screen Removed Feeds")
        if result.pre_screen_removed_feeds:
            st.dataframe(
                pd.DataFrame([{
                    "Feed": r.get("feed_name", ""),
                    "Reason": r.get("reason", ""),
                } for r in result.pre_screen_removed_feeds]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No feeds removed during pre-screening.")

    with st.spinner("Saving results to history…"):
        try:
            run_id = str(uuid.uuid4())
            sb.table("analysis_runs").insert({
                "id": run_id,
                "user_id": user_id,
                "data_table_id": selected_table["id"],
                "preset_label": preset["summary_label"],
            }).execute()

            summary_csv = fit_to_df(fit).to_csv(index=False).encode()
            coef_csv = coef_to_df(fit).to_csv(index=False).encode()

            for file_type, fname, data, ct in [
                ("summary_csv",     f"{run_id}/summary.csv",         summary_csv, "text/csv"),
                ("coef_csv",        f"{run_id}/shadow_prices.csv",   coef_csv,    "text/csv"),
                ("bar_chart_png",   f"{run_id}/bar_chart.png",       bar_png,     "image/png"),
                ("opportunity_png", f"{run_id}/opportunity_plot.png", opp_png,    "image/png"),
            ]:
                upload_file("run-outputs", fname, data, ct)
                sb.table("run_outputs").insert({
                    "run_id": run_id,
                    "file_type": file_type,
                    "storage_path": fname,
                }).execute()

            st.success("Results saved — view them any time in **My Results**.")
        except Exception as e:
            st.warning(f"Results displayed but could not be saved to history: {e}")
