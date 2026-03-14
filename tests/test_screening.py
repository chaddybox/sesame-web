import csv
import tempfile
from pathlib import Path

import unittest

from SesameModernized.models.estimator import SesameEstimator, ScreeningConfig


class TestIterativeScreening(unittest.TestCase):
    def setUp(self):
        self.estimator = SesameEstimator()
        self.rows = []
        for i in range(1, 13):
            self.rows.append(
                {
                    "name": f"Feed{i}",
                    "price_per_t": 80.0 + 2.0 * i,
                    "x1": float(i),
                    "x2": float((i % 5) + 0.5 * i),
                }
            )
        self.rows.append({"name": "OUTLIER", "price_per_t": 150.0, "x1": 200.0, "x2": 1.0})

    def test_excludes_very_high_leverage_and_logs_reason(self):
        cfg = ScreeningConfig(enable_iterative_screening=True)

        result = self.estimator._run_iterative_screening(
            self.rows,
            nutrients=["x1", "x2"],
            config=cfg,
            include_intercept=True,
        )

        excluded_names = {r.name for r in result.excluded_feeds}
        self.assertIn("OUTLIER", excluded_names)
        self.assertGreaterEqual(len(result.initial_fit.rows), len(result.final_fit.rows))

        outlier_reasons = [r.reason for r in result.excluded_feeds if r.name == "OUTLIER"]
        self.assertTrue(any("very_high_leverage" in reason for reason in outlier_reasons))


class TestPreScreenTransparency(unittest.TestCase):
    def setUp(self):
        self.estimator = SesameEstimator()

    def test_logs_and_tracks_removed_rows_with_missing_predictors(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "feeds.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["name", "price_per_t", "x1", "x2"])
                w.writeheader()
                w.writerow({"name": "Good1", "price_per_t": 100, "x1": 1, "x2": 2})
                w.writerow({"name": "BadMissingX1", "price_per_t": 110, "x1": "", "x2": 3})
                w.writerow({"name": "BadMissingX2", "price_per_t": 120, "x1": 4, "x2": ""})
                w.writerow({"name": "Good2", "price_per_t": 130, "x1": 5, "x2": 6})
                w.writerow({"name": "Good3", "price_per_t": 140, "x1": 7, "x2": 8})
                w.writerow({"name": "Good4", "price_per_t": 150, "x1": 9, "x2": 10})

            with self.assertLogs("SesameModernized.models.estimator", level="INFO") as logs:
                result = self.estimator.run_on_csv(str(csv_path), ["x1", "x2"])

            removed = result.pre_screen_removed_feeds
            self.assertEqual(len(removed), 2)
            self.assertEqual({r["feed_name"] for r in removed}, {"BadMissingX1", "BadMissingX2"})
            self.assertTrue(any("missing_predictor_values:x1" in r["reason"] for r in removed))
            self.assertTrue(any("missing_predictor_values:x2" in r["reason"] for r in removed))
            self.assertEqual(len(result.final_fit.rows), 4)
            self.assertIn("Pre-screen removed feed 'BadMissingX1'", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
