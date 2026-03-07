from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import numpy as np

from .nutrients import canon_header
from .derived import add_derived


# ---------- robust value parsing ----------

NA_STRINGS = {"", "na", "n/a", "nan", "null", "-", "—", "--", "n.a.", "none"}

def to_float_safe(x):
    """Parse messy spreadsheet cells into float or None.
    Handles: empty strings, 'N/A', commas, percents like '12%', spaces."""
    if x is None:
        return None
    s = str(x).strip()
    if s.lower() in NA_STRINGS:
        return None
    s = s.replace(",", "")
    if s.endswith("%"):
        s = s[:-1]
        try:
            return float(s) / 100.0
        except Exception:
            return None
    try:
        return float(s)
    except Exception:
        return None


# ---------- result containers ----------

@dataclass
class ResultRow:
    name: str
    actual_per_t: float
    predicted_per_t: float
    residual: float
    leverage: float
    student_residual: float
    ci75_lo: float
    ci75_hi: float

@dataclass
class FitResult:
    nutrients: List[str]
    coef: List[float]
    se_coef: List[float]
    vif: Dict[str, float]
    adj_r2: float
    sigma2: float
    intercept_included: bool
    intercept_pvalue: Optional[float]
    rows: List[ResultRow]


# ---------- estimator ----------

class SesameEstimator:
    """Multiple linear regression Price = b0 + sum_j b_j * Nutrient_j.
    This implementation matches the data produced/consumed by the UI."""

    # ------------- public API -------------
    def run_on_csv(self, path: str, nutrient_cols: List[str]) -> FitResult:
        """
        Load a CSV, normalize headers, coerce numbers safely, add derived values,
        then fit the model with the chosen nutrients.
        Required columns: 'name', 'price_per_t' and all items in nutrient_cols.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")

        data: List[Dict[str, float]] = []

        # 1) parse CSV with safe conversion + header canonicalization
        with open(path, newline="", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            if not rdr.fieldnames:
                raise ValueError("CSV has no header row.")

            header_map = {h: canon_header(h) for h in rdr.fieldnames}

            for row in rdr:
                rec: Dict[str, float] = {}
                for h, v in row.items():
                    cname = header_map.get(h, h)
                    rec[cname] = v

                # canonical required id/price names
                if "name" not in rec:
                    # try common fallbacks
                    for alt in ("feed", "ingredient", "description", "feedname"):
                        if alt in rec:
                            rec["name"] = rec.get(alt)
                            break
                if "price_per_t" not in rec:
                    for alt in ("price", "price/ton", "price_per_ton", "price_usd_t", "priceton"):
                        if alt in rec:
                            rec["price_per_t"] = rec.get(alt)
                            break

                # convert non-name fields to floats robustly
                for k in list(rec.keys()):
                    if k != "name":
                        rec[k] = to_float_safe(rec[k])

                # optional derivations (AA %CP -> g/kg DM, etc.)
                rec = add_derived(rec)

                data.append(rec)

        # 2) filter to rows that have numeric values for all required fields
        required = ["price_per_t"] + list(nutrient_cols)
        clean: List[Dict[str, float]] = [
            r for r in data
            if r.get("name") not in (None, "") and all(r.get(c) is not None for c in required)
        ]
        if not clean:
            raise ValueError("No usable rows after cleaning. Check numeric values for: "
                             + ", ".join(required))

        # 3) fit model
        return self.fit(clean, nutrient_cols, include_intercept=True)

    # ------------- core fit -------------
    def fit(
        self,
        rows: List[Dict[str, float]],
        nutrients: List[str],
        include_intercept: bool = True,
    ) -> FitResult:

        n = len(rows)
        k = len(nutrients) + (1 if include_intercept else 0)
        if n <= k:
            raise ValueError(f"Not enough rows ({n}) for {k} parameters.")

        # Build y and X
        y = np.array([rows[i]["price_per_t"] for i in range(n)], dtype=float)
        X_cols: List[np.ndarray] = []
        if include_intercept:
            X_cols.append(np.ones(n))
        for name in nutrients:
            X_cols.append(np.array([rows[i][name] for i in range(n)], dtype=float))
        X = np.column_stack(X_cols)

        # OLS solution
        XtX = X.T @ X
        try:
            XtX_inv = np.linalg.inv(XtX)
        except np.linalg.LinAlgError:
            # fall back to pseudo-inverse if singular
            XtX_inv = np.linalg.pinv(XtX)
        beta = XtX_inv @ (X.T @ y)

        # predictions, residuals
        yhat = X @ beta
        resid = y - yhat
        dof = n - k
        sigma2 = float((resid @ resid) / dof)

        # standard errors
        var_beta = sigma2 * XtX_inv
        se = np.sqrt(np.diag(var_beta))

        # adjusted R^2
        ss_tot = float(((y - y.mean()) ** 2).sum())
        ss_res = float((resid ** 2).sum())
        r2 = 1.0 - (ss_res / ss_tot if ss_tot > 0 else 0.0)
        adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - k)

        # hat matrix diag (leverage)
        H_diag = np.sum(X * (X @ XtX_inv), axis=1)

        # studentized residuals (internally studentized)
        with np.errstate(invalid="ignore"):
            s_i = np.sqrt(np.maximum(1.0 - H_diag, 1e-12))
            stud = resid / (np.sqrt(sigma2) * s_i)

        # 75% CI for predictions (normal approx, z ~ 1.15)
        z75 = 1.15
        pred_se = np.sqrt(np.sum(X * (X @ XtX_inv), axis=1) * sigma2)
        ci_lo = yhat - z75 * pred_se
        ci_hi = yhat + z75 * pred_se

        # prepare rows output
        out_rows: List(ResultRow) = []
        for i in range(n):
            out_rows.append(
                ResultRow(
                    name=str(rows[i].get("name", "")),
                    actual_per_t=float(y[i]),
                    predicted_per_t=float(yhat[i]),
                    residual=float(resid[i]),
                    leverage=float(H_diag[i]),
                    student_residual=float(stud[i]),
                    ci75_lo=float(ci_lo[i]),
                    ci75_hi=float(ci_hi[i]),
                )
            )

        # VIFs (for each nutrient column, not including intercept)
        vif: Dict[str, float] = {}
        if len(nutrients) >= 2:
            # design matrix without intercept
            Xi = np.column_stack([np.array([r[n] for r in rows], dtype=float) for n in nutrients])
            for j, name in enumerate(nutrients):
                # regress column j on remaining columns to get R^2
                others = [c for c in range(Xi.shape[1]) if c != j]
                Xj = Xi[:, [j]]
                Xo = Xi[:, others]
                # add intercept for the aux regression
                Xo_aug = np.column_stack([np.ones(n), Xo])
                try:
                    b_aux = np.linalg.lstsq(Xo_aug, Xj, rcond=None)[0]
                    yj_hat = Xo_aug @ b_aux
                    ss_tot_j = float(((Xj - Xj.mean()) ** 2).sum())
                    ss_res_j = float(((Xj - yj_hat) ** 2).sum())
                    r2_j = 1.0 - (ss_res_j / ss_tot_j if ss_tot_j > 0 else 0.0)
                    vif[name] = float(1.0 / max(1.0 - r2_j, 1e-12))
                except Exception:
                    vif[name] = float("nan")
        else:
            for name in nutrients:
                vif[name] = 1.0

        # We don't compute intercept p-value here (kept for compatibility)
        intercept_p = None

        # pack results
        # beta ordering: [intercept?, nutrients...]
        coef = beta.tolist()[1:] if include_intercept else beta.tolist()
        se_coef = se.tolist()[1:] if include_intercept else se.tolist()

        return FitResult(
            nutrients=nutrients,
            coef=coef,
            se_coef=se_coef,
            vif=vif,
            adj_r2=float(adj_r2),
            sigma2=float(sigma2),
            intercept_included=include_intercept,
            intercept_pvalue=intercept_p,
            rows=out_rows,
        )
