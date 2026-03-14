from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .derived import add_derived
from .nutrients import canon_header


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
    intercept_coef: Optional[float]
    intercept_se: Optional[float]
    intercept_tvalue: Optional[float]
    intercept_pvalue: Optional[float]
    rows: List[ResultRow]


@dataclass
class ScreeningConfig:
    """User-editable thresholds for SESAME-style diagnostics.

    Defaults follow common SESAME diagnostic heuristics and can be adjusted
    without changing the core fitting algorithm.
    """

    enable_iterative_screening: bool = False
    exclude_extreme_studentized: bool = False
    auto_remove_nonsignificant_intercept: bool = False
    intercept_alpha: float = 0.05
    studentized_abs_threshold: float = 2.5
    leverage_high_multiplier: float = 2.0
    leverage_very_high_multiplier: float = 3.0
    vif_concerning_threshold: float = 10.0
    vif_unacceptable_threshold: float = 20.0


@dataclass
class ExclusionRecord:
    name: str
    reason: str
    leverage: float
    student_residual: float


@dataclass
class ScreeningResult:
    initial_fit: FitResult
    final_fit: FitResult
    excluded_feeds: List[ExclusionRecord]
    diagnostic_rows: List[Dict[str, object]]
    config: ScreeningConfig


# ---------- estimator ----------


class SesameEstimator:
    """Multiple linear regression Price = b0 + sum_j b_j * Nutrient_j.
    This implementation matches the data produced/consumed by the UI."""

    # ------------- public API -------------
    def run_on_csv(
        self,
        path: str,
        nutrient_cols: List[str],
        include_intercept: bool = True,
        screening: Optional[ScreeningConfig] = None,
    ) -> ScreeningResult:
        """
        Load a CSV, normalize headers, coerce numbers safely, add derived values,
        then fit the model with chosen nutrients.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")

        data: List[Dict[str, float]] = []

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

                if "name" not in rec:
                    for alt in ("feed", "ingredient", "description", "feedname"):
                        if alt in rec:
                            rec["name"] = rec.get(alt)
                            break
                if "price_per_t" not in rec:
                    for alt in ("price", "price/ton", "price_per_ton", "price_usd_t", "priceton"):
                        if alt in rec:
                            rec["price_per_t"] = rec.get(alt)
                            break

                for k in list(rec.keys()):
                    if k != "name":
                        rec[k] = to_float_safe(rec[k])

                rec = add_derived(rec)
                data.append(rec)

        required = ["price_per_t"] + list(nutrient_cols)
        clean: List[Dict[str, float]] = [
            r
            for r in data
            if r.get("name") not in (None, "") and all(r.get(c) is not None for c in required)
        ]
        if not clean:
            raise ValueError(
                "No usable rows after cleaning. Check numeric values for: " + ", ".join(required)
            )

        cfg = screening or ScreeningConfig()
        initial_fit = self.fit(clean, nutrient_cols, include_intercept=include_intercept)

        if not cfg.enable_iterative_screening:
            diagnostic_rows = self._build_diagnostic_rows(initial_fit, cfg)
            return ScreeningResult(
                initial_fit=initial_fit,
                final_fit=initial_fit,
                excluded_feeds=[],
                diagnostic_rows=diagnostic_rows,
                config=cfg,
            )

        return self._run_iterative_screening(clean, nutrient_cols, cfg, include_intercept)

    def _run_iterative_screening(
        self,
        rows: List[Dict[str, float]],
        nutrients: List[str],
        config: ScreeningConfig,
        include_intercept: bool,
    ) -> ScreeningResult:
        """SESAME-style two-stage fit with explicit exclusion logging."""
        initial_fit = self.fit(rows, nutrients, include_intercept=include_intercept)
        diagnostic_rows = self._build_diagnostic_rows(initial_fit, config)

        exclusions: List[ExclusionRecord] = []
        keep_names = {r["name"] for r in diagnostic_rows}

        for d in diagnostic_rows:
            reasons: List[str] = []
            if d["is_very_high_leverage"]:
                reasons.append("very_high_leverage")
            if config.exclude_extreme_studentized and d["is_extreme_studentized"]:
                reasons.append("extreme_studentized_residual")
            if reasons:
                keep_names.discard(d["name"])
                exclusions.append(
                    ExclusionRecord(
                        name=str(d["name"]),
                        reason=";".join(reasons),
                        leverage=float(d["leverage"]),
                        student_residual=float(d["student_residual"]),
                    )
                )

        refined_rows = [r for r in rows if str(r.get("name", "")) in keep_names]
        if not refined_rows:
            raise ValueError("Iterative screening removed all feeds; adjust thresholds.")

        final_include_intercept = include_intercept
        final_fit = self.fit(refined_rows, nutrients, include_intercept=final_include_intercept)

        if (
            config.auto_remove_nonsignificant_intercept
            and final_include_intercept
            and final_fit.intercept_pvalue is not None
            and final_fit.intercept_pvalue > config.intercept_alpha
        ):
            final_include_intercept = False
            final_fit = self.fit(refined_rows, nutrients, include_intercept=False)

        return ScreeningResult(
            initial_fit=initial_fit,
            final_fit=final_fit,
            excluded_feeds=exclusions,
            diagnostic_rows=diagnostic_rows,
            config=config,
        )

    def _build_diagnostic_rows(self, fit: FitResult, cfg: ScreeningConfig) -> List[Dict[str, object]]:
        n = max(len(fit.rows), 1)
        p = len(fit.nutrients)
        # SESAME-style leverage cutoffs scale with model dimension and n.
        high_lev = cfg.leverage_high_multiplier * (p + 1) / n
        very_high_lev = cfg.leverage_very_high_multiplier * (p + 1) / n

        out: List[Dict[str, object]] = []
        for r in fit.rows:
            abs_student = abs(float(r.student_residual))
            lev = float(r.leverage)
            out.append(
                {
                    "name": r.name,
                    "leverage": lev,
                    "student_residual": float(r.student_residual),
                    "abs_student_residual": abs_student,
                    "is_high_leverage": lev > high_lev,
                    "is_very_high_leverage": lev > very_high_lev,
                    "is_extreme_studentized": abs_student > cfg.studentized_abs_threshold,
                }
            )
        return out

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

        y = np.array([rows[i]["price_per_t"] for i in range(n)], dtype=float)
        X_cols: List[np.ndarray] = []
        if include_intercept:
            X_cols.append(np.ones(n))
        for name in nutrients:
            X_cols.append(np.array([rows[i][name] for i in range(n)], dtype=float))
        X = np.column_stack(X_cols)

        XtX = X.T @ X
        try:
            XtX_inv = np.linalg.inv(XtX)
        except np.linalg.LinAlgError:
            XtX_inv = np.linalg.pinv(XtX)
        beta = XtX_inv @ (X.T @ y)

        yhat = X @ beta
        resid = y - yhat
        dof = n - k
        sigma2 = float((resid @ resid) / dof)

        var_beta = sigma2 * XtX_inv
        se = np.sqrt(np.diag(var_beta))

        ss_tot = float(((y - y.mean()) ** 2).sum())
        ss_res = float((resid ** 2).sum())
        r2 = 1.0 - (ss_res / ss_tot if ss_tot > 0 else 0.0)
        adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / (n - k)

        H_diag = np.sum(X * (X @ XtX_inv), axis=1)

        with np.errstate(invalid="ignore"):
            s_i = np.sqrt(np.maximum(1.0 - H_diag, 1e-12))
            stud = resid / (np.sqrt(sigma2) * s_i)

        z75 = 1.15
        pred_se = np.sqrt(np.sum(X * (X @ XtX_inv), axis=1) * sigma2)
        ci_lo = yhat - z75 * pred_se
        ci_hi = yhat + z75 * pred_se

        out_rows: List[ResultRow] = []
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

        vif: Dict[str, float] = {}
        if len(nutrients) >= 2:
            Xi = np.column_stack([np.array([r[n] for r in rows], dtype=float) for n in nutrients])
            for j, name in enumerate(nutrients):
                others = [c for c in range(Xi.shape[1]) if c != j]
                Xj = Xi[:, [j]]
                Xo = Xi[:, others]
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

        intercept_coef = None
        intercept_se = None
        intercept_t = None
        intercept_p = None
        if include_intercept:
            intercept_coef = float(beta[0])
            intercept_se = float(se[0])
            if intercept_se > 0:
                intercept_t = intercept_coef / intercept_se
                intercept_p = 2.0 * (1.0 - self._normal_cdf(abs(intercept_t)))

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
            intercept_coef=intercept_coef,
            intercept_se=intercept_se,
            intercept_tvalue=intercept_t,
            intercept_pvalue=intercept_p,
            rows=out_rows,
        )

    @staticmethod
    def _normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
