from __future__ import annotations

import csv
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .derived import add_derived
from .nutrients import canon_header


NA_STRINGS = {"", "na", "n/a", "nan", "null", "-", "—", "--", "n.a.", "none"}


def to_float_safe(x):
    """Parse messy spreadsheet cells into float or None."""
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
    final_weight: float = 1.0
    abs_student_residual: float = 0.0


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
    iteration_count: int = 1
    max_iter_reached: bool = False


@dataclass
class ScreeningConfig:
    enable_iterative_screening: bool = True
    exclude_extreme_studentized: bool = False
    auto_remove_nonsignificant_intercept: bool = False
    intercept_alpha: float = 0.05
    studentized_abs_threshold: float = 2.5
    leverage_high_multiplier: float = 2.0
    leverage_very_high_multiplier: float = 3.0
    vif_concerning_threshold: float = 10.0
    vif_unacceptable_threshold: float = 20.0
    max_iter: int = 10


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
    pre_screen_removed_feeds: List[Dict[str, str]]
    diagnostic_rows: List[Dict[str, object]]
    config: ScreeningConfig
    iteration_log: Optional[List[Dict[str, object]]] = None


class SesameEstimator:
    """Multiple linear regression Price = b0 + sum_j b_j * Nutrient_j."""

    _logger = logging.getLogger(__name__)

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

        Sesame 4 behavior is iterative reweighted least squares by default.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")

        data = self._load_input_rows(path)
        clean, pre_screen_removed_feeds = self._split_usable_rows(data, nutrient_cols)
        required = ["price_per_t"] + list(nutrient_cols)

        if not clean:
            raise ValueError(
                "No usable rows after cleaning. Check numeric values for: " + ", ".join(required)
            )

        cfg = screening or ScreeningConfig()

        return self._run_iterative_screening(
            clean,
            nutrient_cols,
            cfg,
            include_intercept,
            pre_screen_removed_feeds=pre_screen_removed_feeds,
        )

    def summarize_input_rows(self, path: str, nutrient_cols: List[str]) -> Dict[str, int]:
        data = self._load_input_rows(path)
        clean, removed = self._split_usable_rows(data, nutrient_cols)
        return {
            "usable": len(clean),
            "skipped_missing_required_inputs": len(removed),
        }

    def _load_input_rows(self, path: str) -> List[Dict[str, float]]:
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

                data.append(add_derived(rec))
        return data

    def _split_usable_rows(
        self, rows: List[Dict[str, float]], nutrient_cols: List[str]
    ) -> tuple[List[Dict[str, float]], List[Dict[str, str]]]:
        clean: List[Dict[str, float]] = []
        pre_screen_removed_feeds: List[Dict[str, str]] = []
        required = ["price_per_t"] + list(nutrient_cols)

        for row in rows:
            has_required = all(row.get(c) is not None for c in required)
            has_name = row.get("name") not in (None, "")

            if has_name and has_required:
                clean.append(row)
                continue

            missing_predictors = [col for col in nutrient_cols if row.get(col) is None]
            if missing_predictors:
                feed_name = str(row.get("name") or "")
                reason = f"missing_predictor_values:{';'.join(missing_predictors)}"
                pre_screen_removed_feeds.append({"feed_name": feed_name, "reason": reason})
                self._logger.info("Pre-screen removed feed '%s' (%s)", feed_name, reason)

        return clean, pre_screen_removed_feeds

    def _run_iterative_screening(
        self,
        rows: List[Dict[str, float]],
        nutrients: List[str],
        config: ScreeningConfig,
        include_intercept: bool,
        pre_screen_removed_feeds: Optional[List[Dict[str, str]]] = None,
    ) -> ScreeningResult:
        """
        Sesame 4 style iterative reweighting using studentized residuals.
        All feeds stay in the model and are progressively downweighted.
        """
        if not config.enable_iterative_screening:
            single_fit = self.fit(
                rows,
                nutrients,
                include_intercept=include_intercept,
                row_weights=np.ones(len(rows), dtype=float),
                iteration_count=1,
                max_iter_reached=False,
            )
            iteration_log = self._fit_rows_to_iteration_log(1, single_fit)
            return ScreeningResult(
                initial_fit=single_fit,
                final_fit=single_fit,
                excluded_feeds=[],
                pre_screen_removed_feeds=pre_screen_removed_feeds or [],
                diagnostic_rows=self._build_diagnostic_rows(single_fit, config),
                config=config,
                iteration_log=iteration_log,
            )

        initial_fit, final_fit, iteration_log = self._run_iterative_reweighting(
            rows,
            nutrients,
            include_intercept=include_intercept,
            max_iter=config.max_iter,
        )

        if (
            config.auto_remove_nonsignificant_intercept
            and include_intercept
            and final_fit.intercept_pvalue is not None
            and final_fit.intercept_pvalue > config.intercept_alpha
        ):
            initial_fit, final_fit, iteration_log = self._run_iterative_reweighting(
                rows,
                nutrients,
                include_intercept=False,
                max_iter=config.max_iter,
            )

        return ScreeningResult(
            initial_fit=initial_fit,
            final_fit=final_fit,
            excluded_feeds=[],
            pre_screen_removed_feeds=pre_screen_removed_feeds or [],
            diagnostic_rows=self._build_diagnostic_rows(final_fit, config),
            config=config,
            iteration_log=iteration_log,
        )

    def _build_diagnostic_rows(self, fit: FitResult, cfg: ScreeningConfig) -> List[Dict[str, object]]:
        n = max(len(fit.rows), 1)
        p = len(fit.nutrients)
        high_lev = cfg.leverage_high_multiplier * (p + 1) / n
        very_high_lev = cfg.leverage_very_high_multiplier * (p + 1) / n

        out: List[Dict[str, object]] = []
        for r in fit.rows:
            abs_student = float(getattr(r, "abs_student_residual", abs(float(r.student_residual))))
            lev = float(r.leverage)
            final_weight = float(getattr(r, "final_weight", 1.0))
            out.append(
                {
                    "name": r.name,
                    "leverage": lev,
                    "student_residual": float(r.student_residual),
                    "abs_student_residual": abs_student,
                    "final_weight": final_weight,
                    "weight": final_weight,
                    "is_high_leverage": lev > high_lev,
                    "is_very_high_leverage": lev > very_high_lev,
                    "is_extreme_studentized": abs_student > cfg.studentized_abs_threshold,
                }
            )
        return out

    def fit(
        self,
        rows: List[Dict[str, float]],
        nutrients: List[str],
        include_intercept: bool = True,
        row_weights: Optional[np.ndarray] = None,
        iteration_count: int = 1,
        max_iter_reached: bool = False,
    ) -> FitResult:
        n = len(rows)
        k = len(nutrients) + (1 if include_intercept else 0)
        if n <= k:
            raise ValueError(f"Not enough rows ({n}) for {k} parameters.")

        y, X = self._build_design_matrix(rows, nutrients, include_intercept=include_intercept)
        weights = self._normalize_row_weights(n, row_weights)

        return self._fit_weighted_system(
            rows,
            nutrients,
            X,
            y,
            include_intercept=include_intercept,
            row_weights=weights,
            iteration_count=iteration_count,
            max_iter_reached=max_iter_reached,
        )

    def _run_iterative_reweighting(
        self,
        rows: List[Dict[str, float]],
        nutrients: List[str],
        include_intercept: bool,
        max_iter: int = 10,
    ) -> tuple[FitResult, FitResult, List[Dict[str, object]]]:
        n = len(rows)
        weights = np.ones(n, dtype=float)
        iteration_log: List[Dict[str, object]] = []

        initial_fit = self.fit(
            rows,
            nutrients,
            include_intercept=include_intercept,
            row_weights=weights,
            iteration_count=1,
            max_iter_reached=False,
        )
        iteration_log.extend(self._fit_rows_to_iteration_log(1, initial_fit))
        current_fit = initial_fit

        for iteration in range(2, max_iter + 1):
            new_weights = self._update_weights_from_studentized(current_fit.rows, weights)
            weights_changed = not np.allclose(new_weights, weights, atol=1e-12, rtol=0.0)

            weights = new_weights
            current_fit = self.fit(
                rows,
                nutrients,
                include_intercept=include_intercept,
                row_weights=weights,
                iteration_count=iteration,
                max_iter_reached=False,
            )
            iteration_log.extend(self._fit_rows_to_iteration_log(iteration, current_fit))

            if not weights_changed:
                current_fit.max_iter_reached = False
                break
        else:
            current_fit.max_iter_reached = True

        return initial_fit, current_fit, iteration_log

    def _fit_weighted_system(
        self,
        rows: List[Dict[str, float]],
        nutrients: List[str],
        X: np.ndarray,
        y: np.ndarray,
        include_intercept: bool,
        row_weights: np.ndarray,
        iteration_count: int,
        max_iter_reached: bool,
    ) -> FitResult:
        n = len(rows)
        k = X.shape[1]

        sqrt_w = np.sqrt(row_weights)
        Xw = X * sqrt_w[:, None]
        yw = y * sqrt_w

        XtWX = Xw.T @ Xw
        XtWX_inv = np.linalg.pinv(XtWX)

        beta = XtWX_inv @ (Xw.T @ yw)

        yhat = X @ beta
        resid = y - yhat
        dof = max(n - k, 1)

        weighted_sse = float((row_weights * (resid ** 2)).sum())
        sigma2 = float(weighted_sse / dof)

        var_beta = sigma2 * XtWX_inv
        se = np.sqrt(np.maximum(np.diag(var_beta), 0.0))

        weighted_mean = float(np.average(y, weights=row_weights))
        ss_tot = float((row_weights * ((y - weighted_mean) ** 2)).sum())
        ss_res = weighted_sse
        r2 = 1.0 - (ss_res / ss_tot if ss_tot > 0 else 0.0)
        adj_r2 = 1.0 - (1.0 - r2) * (n - 1) / max(n - k, 1)

        # Hat diagonal from whitened WLS system
        H_diag = np.sum((Xw @ XtWX_inv) * Xw, axis=1)
        H_diag = np.clip(H_diag, 0.0, 0.999999)

        # Internally studentized residuals for WLS
        with np.errstate(invalid="ignore", divide="ignore"):
            denom = np.sqrt(np.maximum(sigma2, 1e-12)) * np.sqrt(np.maximum(1.0 - H_diag, 1e-12))
            stud = (sqrt_w * resid) / denom

        z75 = 1.15

        # Approximate x'(X'WX)^-1x on original scale
        x_var = H_diag / np.maximum(row_weights, 1e-12)
        pred_se = np.sqrt(np.maximum(x_var, 0.0) * max(sigma2, 0.0))
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
                    final_weight=float(row_weights[i]),
                    abs_student_residual=float(abs(stud[i])),
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
            intercept_pvalue=intercept_pvalue if False else intercept_p,
            rows=out_rows,
            iteration_count=iteration_count,
            max_iter_reached=max_iter_reached,
        )

    def _build_design_matrix(
        self,
        rows: List[Dict[str, float]],
        nutrients: List[str],
        include_intercept: bool,
    ) -> tuple[np.ndarray, np.ndarray]:
        n = len(rows)
        y = np.array([rows[i]["price_per_t"] for i in range(n)], dtype=float)
        X_cols: List[np.ndarray] = []
        if include_intercept:
            X_cols.append(np.ones(n))
        for name in nutrients:
            X_cols.append(np.array([rows[i][name] for i in range(n)], dtype=float))
        X = np.column_stack(X_cols)
        return y, X

    @staticmethod
    def _normalize_row_weights(n: int, row_weights: Optional[np.ndarray]) -> np.ndarray:
        if row_weights is None:
            return np.ones(n, dtype=float)
        weights = np.array(row_weights, dtype=float).reshape(-1)
        if len(weights) != n:
            raise ValueError(f"Expected {n} row weights, received {len(weights)}.")
        return np.clip(weights, 1e-12, None)

    @staticmethod
    def _update_weights_from_studentized(rows: List[ResultRow], old_weights: np.ndarray) -> np.ndarray:
        """
        Sesame 4 reweighting rules.
        Weights can be reduced repeatedly:
        1.0 -> 0.5 -> 0.25 -> 0.025, etc.
        """
        new_weights = old_weights.copy()
        for i, row in enumerate(rows):
            abs_student = abs(float(row.student_residual))
            multiplier = 1.0

            if 1.5 <= abs_student < 2.0:
                multiplier = 0.5
            elif 2.0 < abs_student < 2.5:
                multiplier = 0.25
            elif abs_student > 2.5:
                multiplier = 0.1

            new_weights[i] = old_weights[i] * multiplier

        return new_weights

    @staticmethod
    def _fit_rows_to_iteration_log(iteration: int, fit: FitResult) -> List[Dict[str, object]]:
        return [
            {
                "iteration": iteration,
                "feed_name": row.name,
                "weight": float(getattr(row, "final_weight", 1.0)),
                "residual": float(row.residual),
                "student_residual": float(row.student_residual),
                "abs_student_residual": float(getattr(row, "abs_student_residual", abs(row.student_residual))),
            }
            for row in fit.rows
        ]

    @staticmethod
    def _normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))