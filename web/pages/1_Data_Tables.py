"""
Data Tables page — upload, view, edit, and delete feed ingredient/nutrient tables.
"""
import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st
from utils import download_file, get_supabase, require_auth, show_sidebar_user, upload_file

st.set_page_config(page_title="Data Tables — Sesame", layout="wide")
user = require_auth()
show_sidebar_user()

sb = get_supabase()
user_id = str(user.id)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

st.title("Data Tables")
st.caption("Manage the feed ingredient / nutrient CSVs used in your analyses.")

# ---------------------------------------------------------------------------
# Default libraries
# ---------------------------------------------------------------------------
st.subheader("Default Libraries")
st.caption("These tables are provided out of the box. Click **Add to My Tables** to copy one into your account so you can use it in Run Analysis or edit it.")

DEFAULT_LIBRARIES = [
    {
        "filename": "beta_NASEM_feed_library.csv",
        "name": "NASEM Feed Library (Core)",
        "description": "Core NASEM commodity ingredients. Contains nutrient profiles for common dairy feeds. Add it to your tables and fill in current market prices to run an analysis.",
    },
    {
        "filename": "Feed_Testing_Library.csv",
        "name": "NASEM Feed Library (Expanded)",
        "description": "Comprehensive table of common dairy feeds. Contains an extended set of ingredient nutrient profiles. Add it to your tables and fill in current market prices to run an analysis.",
    },
]

for lib in DEFAULT_LIBRARIES:
    csv_path = _DATA_DIR / lib["filename"]
    if not csv_path.exists():
        continue

    with st.expander(f"**{lib['name']}**  —  {lib['description']}"):
        raw = csv_path.read_bytes()
        df = pd.read_csv(io.BytesIO(raw))
        st.dataframe(df, use_container_width=True, hide_index=True)

        add_col, dl_col, _ = st.columns([1, 1, 5])
        with add_col:
            if st.button("Add to My Tables", key=f"add_{lib['filename']}", type="primary"):
                try:
                    table_id = str(uuid.uuid4())
                    storage_path = f"{user_id}/{table_id}.csv"
                    upload_file("data-tables", storage_path, raw, "text/csv")
                    sb.table("data_tables").insert({
                        "id": table_id,
                        "user_id": user_id,
                        "name": lib["name"],
                        "description": lib["description"],
                        "storage_path": storage_path,
                    }).execute()
                    st.success(f"**{lib['name']}** added to your tables.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add table: {e}")
        with dl_col:
            st.download_button(
                "Download CSV",
                data=raw,
                file_name=lib["filename"],
                mime="text/csv",
                key=f"dl_default_{lib['filename']}",
            )

st.divider()

# ---------------------------------------------------------------------------
# CSV template download
# ---------------------------------------------------------------------------
st.subheader("Download a Blank Template")
st.markdown(
    "Use this template to build your own feed library outside the app. "
    "It contains all required column headers in the correct format. "
    "Fill in your feed names, prices, and nutrient values, then upload it above. "
    "Columns used by the estimator presets (e.g. **DE**, **CP**, **MP**, **NDFd**) "
    "are computed automatically from the raw nutrient columns — just fill in what you have."
)
st.warning(
    "**Note:** The Sesame estimator is a regression model and requires a sufficiently large feed library "
    "to produce reliable results. **20 or more feeds with prices** is a reasonable floor for trustworthy estimates — "
    "a library with only 4–5 priced feeds will yield statistically unreliable shadow prices. "
    "Consider starting from one of the Default Libraries above and adding your own feeds and prices, "
    "rather than building a table from scratch.",
    icon="⚠️",
)

TEMPLATE_HEADERS = [
    "UID", "name", "Price", "DM", "Ash", "CP", "A Fraction", "B Fraction",
    "C Fraction", "Kd of B", "RUP", "dRUP", "Soluble Protein", "ADIP", "NDIP",
    "ADF", "NDF", "NDFD48", "Lignin", "Starch", "WSC", "Total Fatty Acids",
    "Crude Fat", "DE, Base", "Ca", "P", "Mg", "K", "Na", "Cl", "S", "Cu",
    "Fe", "Mn", "Zn", "Mo", "Co", "Cr", "I", "Se",
    "Arg, % CP", "His, % CP", "Ile, % CP", "Leu, % CP", "Lys, % CP",
    "Met, % CP", "Phe, % CP", "Thr, % CP", "Trp, % CP", "Val, % CP",
    "TFA, % DM", "C12:0, % TFA", "C14:0, % TFA", "C16:0, % TFA",
    "C16:1, % TFA", "C18:0, % TFA", "C18:1 trans, % TFA", "C18:1 cis, % TFA",
    "C18:2, % TFA", "C18:3, % TFA", "Other Fatty Acids, % TFA",
]
template_csv = pd.DataFrame(columns=TEMPLATE_HEADERS).to_csv(index=False).encode()

st.download_button(
    "Download Blank Template (CSV)",
    data=template_csv,
    file_name="sesame_feed_library_template.csv",
    mime="text/csv",
)

st.divider()

# ---------------------------------------------------------------------------
# Upload a new table
# ---------------------------------------------------------------------------
st.subheader("Upload a New Table")
with st.form("upload_form", clear_on_submit=True):
    name = st.text_input("Table name", placeholder="e.g. My Custom Feed Library")
    description = st.text_area("Description (optional)", height=80)
    uploaded_file = st.file_uploader("CSV file", type=["csv"])
    submitted = st.form_submit_button("Upload", type="primary")

if submitted:
    if not name.strip():
        st.error("Please enter a table name.")
    elif uploaded_file is None:
        st.error("Please select a CSV file.")
    else:
        try:
            table_id = str(uuid.uuid4())
            csv_bytes = uploaded_file.read()
            storage_path = f"{user_id}/{table_id}.csv"
            upload_file("data-tables", storage_path, csv_bytes, "text/csv")
            sb.table("data_tables").insert({
                "id": table_id,
                "user_id": user_id,
                "name": name.strip(),
                "description": description.strip(),
                "storage_path": storage_path,
            }).execute()
            st.success(f"Table **{name}** uploaded successfully.")
            st.rerun()
        except Exception as e:
            st.error(f"Upload failed: {e}")

st.divider()

# ---------------------------------------------------------------------------
# User's own tables
# ---------------------------------------------------------------------------
st.subheader("Your Tables")

resp = (
    sb.table("data_tables")
    .select("*")
    .eq("user_id", user_id)
    .order("created_at", desc=True)
    .execute()
)
tables = resp.data

if not tables:
    st.info("No tables yet — add a default library above, or upload your own.")
else:
    for t in tables:
        created = t.get("created_at", "")[:10]
        desc = t.get("description") or ""
        header = f"**{t['name']}**" + (f"  —  {desc}" if desc else "") + f"  *(added {created})*"

        with st.expander(header):
            load_key = f"loaded_{t['id']}"

            col_view, col_del, _ = st.columns([1, 1, 6])
            with col_view:
                if st.button("View / Edit", key=f"view_{t['id']}"):
                    st.session_state[load_key] = True
            with col_del:
                if st.button("Delete", key=f"del_{t['id']}", type="secondary"):
                    st.session_state[f"confirm_del_{t['id']}"] = True

            if st.session_state.get(f"confirm_del_{t['id']}"):
                st.warning(f"Are you sure you want to delete **{t['name']}**? This cannot be undone.")
                yes, no, _ = st.columns([1, 1, 6])
                with yes:
                    if st.button("Yes, delete", key=f"yes_{t['id']}", type="primary"):
                        try:
                            sb.storage.from_("data-tables").remove([t["storage_path"]])
                            sb.table("data_tables").delete().eq("id", t["id"]).execute()
                            st.success("Table deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")
                with no:
                    if st.button("Cancel", key=f"no_{t['id']}"):
                        st.session_state.pop(f"confirm_del_{t['id']}", None)
                        st.rerun()

            if st.session_state.get(load_key):
                try:
                    raw = download_file("data-tables", t["storage_path"])
                    df = pd.read_csv(io.BytesIO(raw))
                except Exception as e:
                    st.error(f"Could not load table: {e}")
                    continue

                st.markdown("**Edit the table below, then click Save Changes.**")
                edited_df = st.data_editor(
                    df,
                    key=f"editor_{t['id']}",
                    use_container_width=True,
                    num_rows="dynamic",
                )

                save_col, dl_col, _ = st.columns([1, 1, 5])
                with save_col:
                    if st.button("Save Changes", key=f"save_{t['id']}", type="primary"):
                        new_bytes = edited_df.to_csv(index=False).encode()
                        try:
                            upload_file("data-tables", t["storage_path"], new_bytes, "text/csv")
                            st.success("Saved successfully.")
                        except Exception as e:
                            st.error(f"Save failed: {e}")
                with dl_col:
                    st.download_button(
                        "Download CSV",
                        data=raw,
                        file_name=f"{t['name']}.csv",
                        mime="text/csv",
                        key=f"dl_{t['id']}",
                    )
