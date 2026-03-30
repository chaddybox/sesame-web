"""
Shared utilities for the Sesame web app.
Provides: Supabase client, auth helpers, estimator runner, chart generators.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Path setup — ensure repo root is importable so SesameModernized is found
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from SesameModernized.models.estimator import (
    FitResult,
    ScreeningConfig,
    ScreeningResult,
    SesameEstimator,
)
from SesameModernized.models.nutrient_catalog import PRESETS

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------
def get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def require_auth():
    params = st.query_params
    if params.get("type") == "recovery" and params.get("token_hash"):
        _show_reset_password(params.get("token_hash", ""))
        st.stop()
    if "user" not in st.session_state:
        _show_login()
        st.stop()
    return st.session_state["user"]


def _show_login():
    st.set_page_config(page_title="Sesame — Sign In", layout="centered")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            "<div style='text-align:center; font-size:96px; line-height:1.1; padding: 8px 0;'>🌱</div>",
            unsafe_allow_html=True,
        )
        st.title("Sesame — Modernized")
        st.caption("Nutrient Economics for Dairy Nutritionists")
        st.divider()
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)
        if submitted:
            try:
                sb = get_supabase()
                resp = sb.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = resp.user
                st.rerun()
            except Exception:
                st.error("Sign in failed. Check your email and password.")


def _show_reset_password(token_hash: str):
    st.set_page_config(page_title="Sesame — Reset Password", layout="centered")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            "<div style='text-align:center; font-size:96px; line-height:1.1; padding: 8px 0;'>🌱</div>",
            unsafe_allow_html=True,
        )
        st.title("Reset Password")
        st.caption("Enter a new password for your account.")
        st.divider()
        with st.form("reset_password"):
            new_password = st.text_input("New Password", type="password")
            confirm = st.text_input("Confirm New Password", type="password")
            submitted = st.form_submit_button("Update Password", use_container_width=True)
        if submitted:
            if not new_password:
                st.error("Please enter a new password.")
            elif new_password != confirm:
                st.error("Passwords do not match.")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                try:
                    sb = get_supabase()
                    response = sb.auth.verify_otp({"token_hash": token_hash, "type": "recovery"})
                    session = response.session
                    sb.auth.set_session(session.access_token, session.refresh_token)
                    sb.auth.update_user({"password": new_password})
                    st.success("Password updated! You can now sign in.")
                    st.query_params.clear()
                except Exception as e:
                    st.error(f"Could not update password: {e}")


def logout():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()


def show_sidebar_user():
    user = st.session_state.get("user")
    if user:
        st.sidebar.caption(f"Signed in as **{user.email}**")
        if st.sidebar.button("Sign out"):
            logout()


# ---------------------------------------------------------------------------
# Estimator helpers
# ---------------------------------------------------------------------------
def run_analysis(csv_bytes: bytes, columns: list[str], iterative_screening: bool) -> ScreeningResult:
    estimator = SesameEstimator()
    screening = ScreeningConfig(
        enable_iterative_screening=iterative_screening,
        exclude_extreme_studentized=False,
    )
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
        f.write(csv_bytes)
        tmp_path = f.name
    try:
        return estimator.run_on_csv(tmp_path, columns, screening=screening)
    finally:
        os.unlink(tmp_path)


def summarize_input(csv_bytes: bytes, columns: list[str]) -> dict:
    estimator = SesameEstimator()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
        f.write(csv_bytes)
        tmp_path = f.name
    try:
        return estimator.summarize_input_rows(tmp_path, columns)
    finally:
        os.unlink(tmp_path)


def fit_to_df(fit: FitResult) -> pd.DataFrame:
    rows = []
    for r in fit.rows:
        actual = r.actual_per_t
        pred = r.predicted_per_t
        rows.append({
            "Feed": r.name,
            "Actual ($/t)": actual,
            "Predicted ($/t)": pred,
            "Predicted − Actual": (pred - actual) if pred is not None and actual is not None else None,
            "Residual": r.residual,
            "Leverage": r.leverage,
            "Studentized Residual": r.student_residual,
            "CI75 Low": r.ci75_lo,
            "CI75 High": r.ci75_hi,
        })
    return pd.DataFrame(rows)


def coef_to_df(fit: FitResult) -> pd.DataFrame:
    vif = fit.vif or {}
    return pd.DataFrame([
        {
            "Nutrient": n,
            "Shadow Price ($/t per unit)": fit.coef[i] if i < len(fit.coef) else None,
            "Std Error": fit.se_coef[i] if i < len(fit.se_coef) else None,
            "VIF": vif.get(n),
        }
        for i, n in enumerate(fit.nutrients)
    ])


# ---------------------------------------------------------------------------
# Chart generators
# ---------------------------------------------------------------------------
def make_bar_chart(fit: FitResult) -> bytes:
    names = [r.name for r in fit.rows]
    actual = np.array([r.actual_per_t for r in fit.rows], dtype=float)
    predicted = np.array([r.predicted_per_t for r in fit.rows], dtype=float)
    value = predicted - actual

    order = np.argsort(value)
    names = [names[i] for i in order]
    actual, predicted, value = actual[order], predicted[order], value[order]

    x = np.arange(len(names))
    width = 0.28
    fig, ax = plt.subplots(figsize=(max(12, min(36, 0.55 * len(names))), 6))
    ax.bar(x - width, actual, width, label="Actual ($/t)")
    ax.bar(x, predicted, width, label="Predicted ($/t)")
    ax.bar(x + width, value, width, label="Predicted − Actual ($/t)")
    ax.axhline(0, linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=55, ha="right")
    ax.set_ylabel("$/ton")
    ax.set_title("Sesame: Actual vs Predicted Feed Prices (sorted by value)")
    ax.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def make_opportunity_plot(fit: FitResult) -> bytes:
    names = [r.name for r in fit.rows]
    actual = np.array([r.actual_per_t for r in fit.rows], dtype=float)
    predicted = np.array([r.predicted_per_t for r in fit.rows], dtype=float)
    value = predicted - actual

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(predicted, value)
    for i, name in enumerate(names):
        ax.annotate(name, (predicted[i], value[i]),
                    textcoords="offset points", xytext=(5, 3), ha="left")
    ax.axhline(0, linewidth=1)
    ax.set_xlabel("Predicted price ($/t)")
    ax.set_ylabel("Predicted − Actual ($/t)  [positive = undervalued]")
    ax.set_title("Sesame Opportunity Plot")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Supabase storage helpers
# ---------------------------------------------------------------------------
def upload_file(bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream"):
    get_supabase().storage.from_(bucket).upload(
        path=path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )


def download_file(bucket: str, path: str) -> bytes:
    return get_supabase().storage.from_(bucket).download(path)
