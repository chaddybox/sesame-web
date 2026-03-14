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


if __name__ == "__main__":
    unittest.main()
