from __future__ import annotations

import csv
import traceback
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Dict, Optional, List

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QComboBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

from models.estimator import (
    SesameEstimator,
    FitResult,
    ScreeningConfig,
    ScreeningResult,
)


PRESETS = [
    {
        "label": "1) Basic Energy + Protein (DE, CP)",
        "summary_label": "Basic Energy + Protein (DE, CP)",
        "columns": ["DE", "CP"],
    },
    {
        "label": "2) Energy + Metabolizable Protein (DE, MP)",
        "summary_label": "Energy + Metabolizable Protein (DE, MP)",
        "columns": ["DE", "MP"],
    },
    {
        "label": "3) Energy + MP + Digestible Fiber (DE, MP, NDFd)",
        "summary_label": "Energy + MP + Digestible Fiber (DE, MP, NDFd)",
        "columns": ["DE", "MP", "NDFd"],
    },
    {
        "label": "4) Energy + MP + Fiber + Fat (DE, MP, NDFd, Fat)",
        "summary_label": "Energy + MP + Fiber + Fat (DE, MP, NDFd, Fat)",
        "columns": ["DE", "MP", "NDFd", "Fat"],
    },
    {
        "label": "5) NASEM Eq. 6-6 Milk Protein Yield",
        "summary_label": "NASEM Eq. 6-6 Milk Protein Yield",
        "columns": ["NASEM_MP_6_6_perkgDM", "DE", "NDFd"],
    },
]


def _row_as_dict(r):
    if isinstance(r, dict):
        return r
    if is_dataclass(r):
        return asdict(r)
    return {
        "name": getattr(r, "name", ""),
        "actual_per_t": getattr(r, "actual_per_t", None),
        "predicted_per_t": getattr(r, "predicted_per_t", None),
        "residual": getattr(r, "residual", None),
        "leverage": getattr(r, "leverage", None),
        "student_residual": getattr(r, "student_residual", None),
        "ci75_lo": getattr(r, "ci75_lo", None),
        "ci75_hi": getattr(r, "ci75_hi", None),
    }


class MainWindow(QMainWindow):
    def __init__(self, app_icon_path: Optional[str] = None):
        super().__init__()

        self.setWindowTitle("Sesame — Modernized")
        self._assets = Path(__file__).resolve().parent.parent / "assets"
        self._project_root = Path(__file__).resolve().parents[2]

        if app_icon_path and Path(app_icon_path).exists():
            self.setWindowIcon(QIcon(app_icon_path))
        else:
            icon_path = self._assets / "sesame_icon_multi.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))

        self.preset_box = QComboBox()

        self._presets = PRESETS
        for preset in self._presets:
            self.preset_box.addItem(preset["label"])

        preset_row = QHBoxLayout()
        preset_label = QLabel("Preset:")
        preset_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        preset_row.addWidget(preset_label)
        preset_row.addWidget(self.preset_box, stretch=1)
        preset_row.addStretch(10)

        self.banner = QLabel()
        self.banner.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self._banner_pixmap: QPixmap | None = None
        banner_path = self._assets / "sesame_banner.png"
        if banner_path.exists():
            pm = QPixmap(str(banner_path))
            if not pm.isNull():
                self._banner_pixmap = pm
                self.banner.setPixmap(pm)
        else:
            self.banner.setText(
                "<div style='font-size:40px; font-weight:700; color:#0f4e3a;'>Sesame — Modernized</div>"
                "<div style='font-size:20px; color:#1d6b55; margin-top:8px;'>Nutrient Economics for Dairy Nutritionists</div>"
            )
            self.banner.setAlignment(Qt.AlignCenter)

        self.hint = QLabel("Use File → Run Estimator (CSV…)  — outputs go to /outputs")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("color:#2a6f58; font-size:14px; margin-top:16px;")

        self.run_button = QPushButton("Run Estimator (CSV…)")
        self.run_button.clicked.connect(self.on_run_clicked)
        self.run_button.setFixedHeight(36)

        self.iterative_screening_checkbox = QCheckBox("Iterative diagnostic screening")
        self.iterative_screening_checkbox.setToolTip(
            "Run an initial fit, screen the calibration set using leverage/residual diagnostics, then refit."
        )

        v = QVBoxLayout()
        v.addLayout(preset_row)
        v.addSpacing(16)
        v.addWidget(self.banner, alignment=Qt.AlignTop)
        v.addSpacing(12)
        v.addWidget(self.hint)
        v.addSpacing(16)
        v.addWidget(self.run_button, alignment=Qt.AlignCenter)
        v.addSpacing(8)
        v.addWidget(self.iterative_screening_checkbox, alignment=Qt.AlignCenter)

        c = QWidget()
        c.setLayout(v)
        self.setCentralWidget(c)

        file_menu = self.menuBar().addMenu("&File")
        act_run = QAction("Run Estimator (CSV…)", self)
        act_run.triggered.connect(self.on_run_clicked)
        file_menu.addAction(act_run)

        file_menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        help_menu = self.menuBar().addMenu("&Help")
        act_about = QAction("About Sesame…", self)
        act_about.triggered.connect(self.on_about)
        help_menu.addAction(act_about)

        self._estimator = SesameEstimator()
        self._last_dir = str(self._project_root / "data" / "raw")

        self.resize(980, 680)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._banner_pixmap:
            w = max(400, int(self.width() * 0.7))
            pm = self._banner_pixmap.scaled(QSize(w, w), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.banner.setPixmap(pm)

    def on_about(self):
        QMessageBox.information(
            self,
            "About Sesame — Modernized",
            "Sesame — Modernized\n"
            "Version 1.2\n"
            "Nutrient Economics for Dairy Nutritionists\n\n"
            "This software is a modern Python implementation inspired by the SESAME "
            "method described in:\n\n"
            "St-Pierre, N.R., and D. Glamocic. 2000. Estimating unit costs of nutrients "
            "from market prices of feedstuffs. Journal of Dairy Science 83:1402–1411.\n"
            "https://doi.org/10.3168/jds.S0022-0302(00)75009-0\n\n"
            "Original SESAME software is available from:\n"
            "https://dairy.osu.edu/node/23\n\n"
            "Modernized Python implementation developed at the University of "
            "Nebraska–Lincoln.\n\n"
            "Use File → Run Estimator (CSV…) to run an analysis.\n"
            "Outputs are written to the /outputs folder.",
        )

    def on_run_clicked(self):
        csv_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select feed library CSV",
            self._last_dir,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not csv_path:
            return
        self._last_dir = str(Path(csv_path).parent)

        idx = self.preset_box.currentIndex()
        preset = self._presets[idx]
        preset_label = preset["summary_label"]
        cols = preset["columns"]

        try:
            precheck = self._estimator.summarize_input_rows(csv_path, cols)
        except Exception as e:
            tb = traceback.format_exc(limit=8)
            QMessageBox.critical(self, "Input Check Error", f"{e}\n\n{tb}")
            return

        precheck_msg = (
            f"Preset requires: {', '.join(cols)}\n"
            f"{precheck['usable']} feeds usable for this preset.\n"
            f"{precheck['skipped_missing_required_inputs']} feeds will be skipped due to missing required inputs."
        )
        QMessageBox.information(self, "Pre-Run Input Check", precheck_msg)

        try:
            screening = ScreeningConfig(
                enable_iterative_screening=self.iterative_screening_checkbox.isChecked(),
                exclude_extreme_studentized=False,
            )
            result = self._estimator.run_on_csv(csv_path, cols, screening=screening)
        except Exception as e:
            tb = traceback.format_exc(limit=8)
            QMessageBox.critical(self, "Estimator Error", f"{e}\n\n{tb}")
            return

        try:
            out_summary, _, _ = self._write_outputs(csv_path, result.final_fit)
            self._write_diagnostic_outputs(csv_path, result)
            self._write_pre_screen_removed_feeds_output(result)
            self._write_bar_chart(csv_path, result.final_fit)
            self._write_opportunity_plot(csv_path, result.final_fit)

            output_dir = Path(out_summary).parent
            msg = self._build_run_summary(
                preset_label=preset_label,
                result=result,
                output_dir=output_dir,
            )
            QMessageBox.information(self, "Run Complete", msg)

        except Exception as e:
            tb = traceback.format_exc(limit=12)
            QMessageBox.critical(self, "Write Error", f"Failed to write outputs:\n{e}\n\n{tb}")

    def _write_csv_rows(self, path: Path, fieldnames: List[str], rows: List[Dict[str, object]]):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in rows:
                w.writerow(row)

    def _fit_rows_for_csv(self, fit: FitResult) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        for row in fit.rows:
            d = _row_as_dict(row)
            actual = d.get("actual_per_t")
            pred = d.get("predicted_per_t")
            student_residual = d.get("student_residual")
            out.append(
                {
                    "name": d.get("name", ""),
                    "actual_per_t": actual,
                    "predicted_per_t": pred,
                    "predicted_minus_actual": (pred - actual) if (pred is not None and actual is not None) else None,
                    "residual": d.get("residual"),
                    "leverage": d.get("leverage"),
                    "student_residual": student_residual,
                    "abs_student_residual": abs(student_residual) if student_residual is not None else None,
                    "excluded": False,
                    "ci75_lo": d.get("ci75_lo"),
                    "ci75_hi": d.get("ci75_hi"),
                }
            )
        return out

    def _write_outputs(self, input_csv: str, fit: FitResult):
        inp = Path(input_csv)
        out_dir = self._ensure_output_dir()

        base = inp.stem
        summary_path = out_dir / f"{base}.summary.csv"
        breakeven_path = out_dir / f"{base}.breakeven.csv"
        shadow_path = out_dir / f"{base}.shadow_prices.csv"

        self._write_summary_file(summary_path, fit)

        vif: Dict[str, float] = fit.vif or {}
        breakeven_rows: List[Dict[str, object]] = []
        shadow_rows: List[Dict[str, object]] = []
        for i, n in enumerate(fit.nutrients):
            coef = fit.coef[i] if i < len(fit.coef) else ""
            se = fit.se_coef[i] if i < len(fit.se_coef) else ""
            breakeven_rows.append({"nutrient": n, "coef": coef, "se": se, "vif": vif.get(n, "")})
            shadow_rows.append(
                {
                    "nutrient": n,
                    "shadow_price": coef,
                    "se": se,
                    "vif": vif.get(n, ""),
                    "notes": "$/ton per unit of nutrient column",
                }
            )

        breakeven_rows.extend([{}, {"nutrient": "adj_r2", "coef": fit.adj_r2}, {"nutrient": "sigma2", "coef": fit.sigma2}])
        shadow_rows.extend([{}, {"nutrient": "adj_r2", "shadow_price": fit.adj_r2}, {"nutrient": "sigma2", "shadow_price": fit.sigma2}])

        self._write_csv_rows(breakeven_path, ["nutrient", "coef", "se", "vif"], breakeven_rows)
        self._write_csv_rows(shadow_path, ["nutrient", "shadow_price", "se", "vif", "notes"], shadow_rows)

        return str(summary_path), str(breakeven_path), str(shadow_path)

    def _write_diagnostic_outputs(self, input_csv: str, result: ScreeningResult):
        out_dir = self._ensure_output_dir()

        initial_path = out_dir / "initial_fit.summary.csv"
        final_path = out_dir / "final_fit.summary.csv"
        excluded_path = out_dir / "excluded_feeds.csv"
        report_path = out_dir / "diagnostic_report.csv"

        self._write_summary_file(initial_path, result.initial_fit)
        self._write_summary_file(final_path, result.final_fit)

        excluded_rows = [asdict(r) for r in result.excluded_feeds]
        self._write_csv_rows(excluded_path, ["name", "reason", "leverage", "student_residual"], excluded_rows)

        report_rows: List[Dict[str, object]] = []
        excluded_map = {x.name: x.reason for x in result.excluded_feeds}
        for row in result.diagnostic_rows:
            name = str(row.get("name", ""))
            out = {
                "name": name,
                "leverage": row.get("leverage"),
                "student_residual": row.get("student_residual"),
                "abs_student_residual": row.get("abs_student_residual"),
                "excluded": name in excluded_map,
                "exclusion_reason": excluded_map.get(name, ""),
            }
            report_rows.append(out)

        report_rows.extend(
            [
                {},
                {"name": "intercept_included_final", "leverage": result.final_fit.intercept_included},
                {"name": "intercept_pvalue_final", "leverage": result.final_fit.intercept_pvalue},
            ]
        )

        for nutrient, vif in (result.final_fit.vif or {}).items():
            concern = "ok"
            if vif > result.config.vif_unacceptable_threshold:
                concern = "unacceptable"
            elif vif > result.config.vif_concerning_threshold:
                concern = "concerning"
            report_rows.append({"name": f"vif:{nutrient}", "leverage": vif, "exclusion_reason": concern})

        self._write_csv_rows(
            report_path,
            [
                "name",
                "leverage",
                "student_residual",
                "abs_student_residual",
                "excluded",
                "exclusion_reason",
            ],
            report_rows,
        )

        return str(initial_path), str(final_path), str(excluded_path), str(report_path)

    def _write_summary_file(self, path: Path, fit: FitResult):
        fieldnames = [
            "name",
            "actual_per_t",
            "predicted_per_t",
            "predicted_minus_actual",
            "residual",
            "leverage",
            "student_residual",
            "abs_student_residual",
            "excluded",
            "ci75_lo",
            "ci75_hi",
        ]
        self._write_csv_rows(path, fieldnames, self._fit_rows_for_csv(fit))

    def _write_pre_screen_removed_feeds_output(self, result: ScreeningResult) -> str:
        out_dir = self._ensure_output_dir()
        out_path = out_dir / "pre_screen_removed_feeds.csv"

        rows = [
            {
                "name": row.get("feed_name", ""),
                "reason": row.get("reason", ""),
            }
            for row in result.pre_screen_removed_feeds
        ]
        self._write_csv_rows(out_path, ["name", "reason"], rows)

        return str(out_path)

    def _build_run_summary(self, preset_label: str, result: ScreeningResult, output_dir: Path) -> str:
        return (
            f"Preset used: {preset_label}\n"
            f"• Feeds used in regression: {len(result.final_fit.rows)}\n"
            f"• Feeds skipped due to missing inputs: {len(result.pre_screen_removed_feeds)}\n"
            f"• Excluded by diagnostic screening: {len(result.excluded_feeds)}\n"
            "\n"
            f"Output files saved in: {output_dir}"
        )

    def _ensure_output_dir(self) -> Path:
        out_dir = self._project_root / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def _write_bar_chart(self, input_csv: str, fit: FitResult) -> str:
        try:
            import matplotlib.pyplot as plt
            import numpy as np
        except Exception as e:
            raise RuntimeError(f"Matplotlib import failed: {e}")

        inp = Path(input_csv)
        out_dir = self._ensure_output_dir()

        names = [r.name for r in fit.rows]
        actual = np.array([r.actual_per_t for r in fit.rows], dtype=float)
        predicted = np.array([r.predicted_per_t for r in fit.rows], dtype=float)

        value = predicted - actual

        order = np.argsort(value)
        names = [names[i] for i in order]
        actual = actual[order]
        predicted = predicted[order]
        value = value[order]

        x = np.arange(len(names))
        width = 0.28

        fig_w = max(12, min(36, 0.55 * len(names)))
        plt.figure(figsize=(fig_w, 6))

        plt.bar(x - width, actual, width, label="Actual ($/t)")
        plt.bar(x, predicted, width, label="Predicted ($/t)")
        plt.bar(x + width, value, width, label="Predicted − Actual ($/t)")

        plt.axhline(0, linewidth=1)
        plt.xticks(x, names, rotation=55, ha="right")
        plt.ylabel("$/ton")
        plt.title("Sesame: Actual vs Predicted Feed Prices (sorted by value)")
        plt.legend()
        plt.tight_layout()

        chart_path = out_dir / f"{inp.stem}.chart.png"
        plt.savefig(chart_path, dpi=160, bbox_inches="tight")
        plt.close()

        return str(chart_path)

    def _write_opportunity_plot(self, input_csv: str, fit: FitResult) -> str:
        """
        Classic Sesame-style plot:
          x = predicted price ($/t)
          y = predicted - actual ($/t)  (positive = undervalued)
        """
        try:
            import matplotlib.pyplot as plt
            import numpy as np
        except Exception as e:
            raise RuntimeError(f"Matplotlib import failed: {e}")

        inp = Path(input_csv)
        out_dir = self._ensure_output_dir()

        names = [r.name for r in fit.rows]
        actual = np.array([r.actual_per_t for r in fit.rows], dtype=float)
        predicted = np.array([r.predicted_per_t for r in fit.rows], dtype=float)
        value = predicted - actual

        plt.figure(figsize=(10, 6))
        plt.scatter(predicted, value)

        for i, name in enumerate(names):
            plt.annotate(
                name,
                (predicted[i], value[i]),
                textcoords="offset points",
                xytext=(5, 3),
                ha="left",
            )

        plt.axhline(0, linewidth=1)
        plt.xlabel("Predicted price ($/t)")
        plt.ylabel("Predicted − Actual ($/t)  (positive = undervalued)")
        plt.title("Sesame Opportunity Plot (Predicted vs Value Opportunity)")
        plt.tight_layout()

        out_path = out_dir / f"{inp.stem}.opportunity.png"
        plt.savefig(out_path, dpi=160, bbox_inches="tight")
        plt.close()

        return str(out_path)
