from __future__ import annotations

import csv
import traceback
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Dict, Optional

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
)

from models.estimator import SesameEstimator, FitResult


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

        # Revised preset nutrient systems
        self._presets = [
            (
                "1) Basic Energy and Protein (DE, CP)",
                ["DE", "CP"],
            ),
            (
                "2) Energy, MP and Fiber (DE, MP, NDF)",
                ["DE", "MP", "NDF"],
            ),
            (
                "3) Energy, degradable and digestible protein with fiber (DE, RDP_prot, dRUP_prot, NDF)",
                ["DE", "RDP_prot", "dRUP_prot", "NDF"],
            ),
            (
                "4) Protein value, compact — protein feeds only (dRUP_prot, dMetLysHis_RUP_sum)",
                ["dRUP_prot", "dMetLysHis_RUP_sum"],
            ),
            (
                "5) Protein value, detailed — protein feeds only (dRUP_prot, dLys_RUP, dMet_RUP, dHis_RUP)",
                ["dRUP_prot", "dLys_RUP", "dMet_RUP", "dHis_RUP"],
            ),
        ]

        for title, _cols in self._presets:
            self.preset_box.addItem(title)

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

        v = QVBoxLayout()
        v.addLayout(preset_row)
        v.addSpacing(16)
        v.addWidget(self.banner, alignment=Qt.AlignTop)
        v.addSpacing(12)
        v.addWidget(self.hint)
        v.addSpacing(16)
        v.addWidget(self.run_button, alignment=Qt.AlignCenter)

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

    def _warn_if_protein_only_preset(self, preset_index: int):
        """Warn user that protein-only presets are not suitable for low-protein feeds."""
        if preset_index in (3, 4):  # presets 4 and 5 in 0-based indexing
            QMessageBox.information(
                self,
                "Protein-Only Preset Warning",
                "This preset is intended for protein supplements and other moderate- to high-protein feeds.\n\n"
                "Low-protein feeds should generally not be included in this analysis.\n\n"
                "Use with caution on mixed feed libraries containing grains, forages, or other low-protein ingredients.",
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
        _, cols = self._presets[idx]

        # Warning for protein-only presets
        self._warn_if_protein_only_preset(idx)

        try:
            fit = self._estimator.run_on_csv(csv_path, cols)
        except Exception as e:
            tb = traceback.format_exc(limit=8)
            QMessageBox.critical(self, "Estimator Error", f"{e}\n\n{tb}")
            return

        try:
            out_summary, out_breakeven, out_shadow = self._write_outputs(csv_path, fit)
            out_bar = self._write_bar_chart(csv_path, fit)
            out_scatter = self._write_opportunity_plot(csv_path, fit)

            msg = (
                "Saved:\n"
                f"• {out_summary}\n"
                f"• {out_breakeven}\n"
                f"• {out_shadow}\n"
                f"• {out_bar}\n"
                f"• {out_scatter}"
            )
            QMessageBox.information(self, "Done", msg)

        except Exception as e:
            tb = traceback.format_exc(limit=12)
            QMessageBox.critical(self, "Write Error", f"Failed to write outputs:\n{e}\n\n{tb}")

    def _write_outputs(self, input_csv: str, fit: FitResult):
        inp = Path(input_csv)
        out_dir = self._project_root / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)

        base = inp.stem
        summary_path = out_dir / f"{base}.summary.csv"
        breakeven_path = out_dir / f"{base}.breakeven.csv"
        shadow_path = out_dir / f"{base}.shadow_prices.csv"

        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "name",
                "actual_per_t",
                "predicted_per_t",
                "predicted_minus_actual",
                "residual",
                "leverage",
                "student_residual",
                "ci75_lo",
                "ci75_hi",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()

            for row in fit.rows:
                d = _row_as_dict(row)
                actual = d.get("actual_per_t")
                pred = d.get("predicted_per_t")
                pma = (pred - actual) if (pred is not None and actual is not None) else None

                w.writerow(
                    {
                        "name": d.get("name", ""),
                        "actual_per_t": actual,
                        "predicted_per_t": pred,
                        "predicted_minus_actual": pma,
                        "residual": d.get("residual"),
                        "leverage": d.get("leverage"),
                        "student_residual": d.get("student_residual"),
                        "ci75_lo": d.get("ci75_lo"),
                        "ci75_hi": d.get("ci75_hi"),
                    }
                )

        with open(breakeven_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["nutrient", "coef", "se", "vif"]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()

            vif: Dict[str, float] = fit.vif or {}
            for i, n in enumerate(fit.nutrients):
                coef = fit.coef[i] if i < len(fit.coef) else ""
                se = fit.se_coef[i] if i < len(fit.se_coef) else ""
                w.writerow({"nutrient": n, "coef": coef, "se": se, "vif": vif.get(n, "")})

            w.writerow({})
            w.writerow({"nutrient": "adj_r2", "coef": fit.adj_r2})
            w.writerow({"nutrient": "sigma2", "coef": fit.sigma2})

        with open(shadow_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["nutrient", "shadow_price", "se", "vif", "notes"]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()

            vif: Dict[str, float] = fit.vif or {}
            for i, n in enumerate(fit.nutrients):
                coef = fit.coef[i] if i < len(fit.coef) else ""
                se = fit.se_coef[i] if i < len(fit.se_coef) else ""
                w.writerow(
                    {
                        "nutrient": n,
                        "shadow_price": coef,
                        "se": se,
                        "vif": vif.get(n, ""),
                        "notes": "$/ton per unit of nutrient column",
                    }
                )

            w.writerow({})
            w.writerow({"nutrient": "adj_r2", "shadow_price": fit.adj_r2})
            w.writerow({"nutrient": "sigma2", "shadow_price": fit.sigma2})

        return str(summary_path), str(breakeven_path), str(shadow_path)

    def _write_bar_chart(self, input_csv: str, fit: FitResult) -> str:
        try:
            import matplotlib.pyplot as plt
            import numpy as np
        except Exception as e:
            raise RuntimeError(f"Matplotlib import failed: {e}")

        inp = Path(input_csv)
        out_dir = self._project_root / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)

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
        out_dir = self._project_root / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)

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
