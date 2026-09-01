import unittest

from app.forecasting import build_prediction, simulate


class ForecastingTests(unittest.TestCase):
    def test_prediction_propagates_service_and_geo_risk(self):
        observations = [{"metric": "error_rate", "service": "payments", "region": "us-east", "minute": minute, "value": value, "baseline": 1, "threshold": 10, "higher_is_worse": True} for minute, value in [(0, 1), (5, 4), (10, 8)]]
        result = build_prediction(observations, {"payments": ["checkout"], "checkout": ["orders"]}, [{"code": "us-east", "latitude": 37, "longitude": -78, "traffic_share": .6, "customers": 100000, "services": ["payments"]}], 30)
        self.assertGreater(result["service_risks"]["payments"], result["service_risks"]["checkout"])
        self.assertGreater(result["geospatial"]["customers_at_risk"], 0)
        self.assertEqual(result["graphs"]["service_dependency"]["edges"][0]["relation"], "may_propagate_to")

    def test_simulator_is_deterministic_and_advisory(self):
        prediction = {"incident_escalation_probability": 82}
        first = simulate(prediction, {"effectiveness_percent": 50, "failure_probability_percent": 5}, {}, 500, "seed")
        second = simulate(prediction, {"effectiveness_percent": 50, "failure_probability_percent": 5}, {}, 500, "seed")
        self.assertEqual(first, second)
        self.assertLess(first["simulated_risk"], first["baseline_risk"])
        self.assertTrue(first["advisory_only"])

    def test_historical_prior_is_bounded_and_explained(self):
        observations = [{"metric": "errors", "service": "payments", "minute": minute, "value": value, "baseline": 1, "threshold": 10, "higher_is_worse": True} for minute, value in [(0, 1), (5, 2), (10, 3)]]
        result = build_prediction(observations, {}, [], 30, {"probability": 90, "confidence": 80, "incidents": [{"incident_id": "past-sev1"}]})
        self.assertGreater(result["incident_escalation_probability"], result["live_signal_probability"])
        self.assertEqual(result["historical_prior"]["incidents"][0]["incident_id"], "past-sev1")


if __name__ == "__main__":
    unittest.main()
