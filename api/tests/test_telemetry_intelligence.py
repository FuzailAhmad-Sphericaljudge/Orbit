import unittest
from datetime import datetime, timedelta, timezone

from app.telemetry_intelligence import calibration_summary, early_warnings, evaluate_prediction, forecast_rows


class TelemetryIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 30, 6, 0, tzinfo=timezone.utc)

    def point(self, minute: int, value: float) -> dict:
        return {"metric": "payment_error_rate", "service": "payments", "region": "us-east", "observed_at": self.start + timedelta(minutes=minute), "value": value, "baseline": 1, "threshold": 10, "higher_is_worse": True}

    def test_early_warning_reports_velocity_progress_and_eta(self):
        warnings = early_warnings([self.point(0, 2), self.point(5, 8)])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["metric"], "payment_error_rate")
        self.assertGreater(warnings[0]["threshold_progress"], 70)
        self.assertLess(warnings[0]["threshold_eta_minutes"], 2)

    def test_forecast_rows_preserve_series_and_relative_time(self):
        result = forecast_rows([self.point(5, 4), self.point(15, 7)])
        self.assertEqual([item["minute"] for item in result], [0, 10])
        self.assertEqual(result[1]["service"], "payments")

    def test_forecast_evaluation_measures_probability_error_and_lead_time(self):
        forecast = {"metric_forecasts": [{"metric": "payment_error_rate", "service": "payments", "region": "us-east", "threshold": 10, "breach_probability": 80, "predicted": 12}]}
        result = evaluate_prediction(forecast, [self.point(5, 8), self.point(10, 11), self.point(15, 13), self.point(20, 14)], self.start)
        self.assertAlmostEqual(result["brier_score"], 0.04)
        self.assertEqual(result["lead_time_minutes"], 10)
        self.assertEqual(result["mean_absolute_error"], 2)
        self.assertEqual(result["drift"]["status"], "watch")

    def test_calibration_summary_compares_forecast_and_observed_frequency(self):
        result = calibration_summary([{"outcomes": [{"predicted_probability": 82, "actual_breach": True}, {"predicted_probability": 86, "actual_breach": False}]}])
        self.assertEqual(result[0]["bucket"], "80-90")
        self.assertEqual(result[0]["observed_frequency"], 50)
        self.assertEqual(result[0]["count"], 2)


if __name__ == "__main__":
    unittest.main()
