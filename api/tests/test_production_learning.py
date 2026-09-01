import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ForecastEvaluation, Incident, PredictionRun, TelemetryObservation
from app.production_learning import alert_quality, build_learned_prior, normalize_prometheus_matrix
from app.production_learning_service import evaluate_mature


class ProductionLearningTests(unittest.TestCase):
    def test_alert_policy_measures_false_positives_and_false_negatives(self):
        result = alert_quality([{"outcomes": [
            {"predicted_probability": 85, "actual_breach": True},
            {"predicted_probability": 75, "actual_breach": False},
            {"predicted_probability": 45, "actual_breach": True},
            {"predicted_probability": 30, "actual_breach": False},
        ]}], threshold=60)
        self.assertEqual(result["current"]["true_positive"], 1)
        self.assertEqual(result["current"]["false_positive"], 1)
        self.assertEqual(result["current"]["false_negative"], 1)
        self.assertEqual(result["sample_count"], 4)
        self.assertEqual(result["policy"], "review")

    def test_learned_prior_uses_evaluated_outcomes_and_reliability(self):
        result = build_learned_prior([
            {"incident_id": "accurate", "similarity": .9, "severity": "SEV2", "evaluation_count": 8, "actual_breach_rate": 80, "mean_brier_score": .08},
            {"incident_id": "weak", "similarity": .7, "severity": "SEV3", "evaluation_count": 1, "actual_breach_rate": 10, "mean_brier_score": .6},
        ])
        self.assertGreater(result["probability"], 60)
        self.assertGreater(result["incidents"][0]["weight"], result["incidents"][1]["weight"])
        self.assertIn("reliability", result["method"])

    def test_prometheus_matrix_is_normalized_with_stable_source_ids(self):
        payload = {"status": "success", "data": {"result": [{"metric": {"__name__": "payment_errors", "service": "payments", "region": "us-east"}, "values": [[1000, "2.5"], [1060, "7.5"]]}]}}
        query = {"query": "rate(payment_errors[5m])", "baseline": 1, "threshold": 10, "higher_is_worse": True}
        first = normalize_prometheus_matrix(payload, query)
        second = normalize_prometheus_matrix(payload, query)
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0]["service"], "payments")
        self.assertEqual(first[0]["source_event_id"], second[0]["source_event_id"])


class ForecastMaturityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_mature_forecast_is_evaluated_once_against_actuals(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=30)
        with self.Session() as db:
            incident = Incident(title="Payment outage", service="payments", severity="SEV1", commander_id="commander")
            db.add(incident)
            db.flush()
            prediction = PredictionRun(incident_id=incident.id, horizon_minutes=10, input_snapshot={}, forecast={"metric_forecasts": [{"metric": "error_rate", "service": "payments", "region": "us-east", "threshold": 10, "breach_probability": 80, "predicted": 12}]}, created_by="scheduler", created_at=start)
            db.add(prediction)
            db.flush()
            db.add_all([
                TelemetryObservation(incident_id=incident.id, metric="error_rate", service="payments", region="us-east", observed_at=start + timedelta(minutes=5), value=8, baseline=1, threshold=10, source="prometheus", source_event_id="actual-1"),
                TelemetryObservation(incident_id=incident.id, metric="error_rate", service="payments", region="us-east", observed_at=start + timedelta(minutes=8), value=11, baseline=1, threshold=10, source="prometheus", source_event_id="actual-2"),
            ])
            db.commit()
            result = evaluate_mature(db, incident.id, datetime.now(timezone.utc), 0, "scheduler")
            repeated = evaluate_mature(db, incident.id, datetime.now(timezone.utc), 0, "scheduler")
            evaluation = db.query(ForecastEvaluation).one()
        self.assertEqual(result["evaluated"], 1)
        self.assertEqual(repeated["evaluated"], 0)
        self.assertEqual(evaluation.lead_time_minutes, 8)
        self.assertAlmostEqual(evaluation.brier_score, .04)


if __name__ == "__main__":
    unittest.main()
