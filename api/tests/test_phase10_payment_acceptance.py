import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commander_service import command_center_snapshot
from app.database import Base
from app.models import EvidenceClassification, EvidenceItem, Incident, PredictionRun, TelemetryObservation
from app.production_learning_service import evaluate_mature
from app.telemetry_service import ingest


class PaymentOutageProductionLearningAcceptance(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_signal_to_warning_to_forecast_to_learning_to_command_center(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=40)
        with self.Session() as db:
            incident = Incident(title="Payment authorization failures", service="payments", severity="SEV1", commander_id="fuzail", affected_regions=["us-east"], customer_impact="Card payments intermittently fail")
            db.add(incident)
            db.flush()
            db.add(EvidenceItem(incident_id=incident.id, claim="Payment error rate increased in us-east", classification=EvidenceClassification.confirmed_fact, confidence=97, source="prometheus"))
            db.commit()
            observations = [{"metric": "payment_error_rate", "service": "payments", "region": "us-east", "observed_at": start + timedelta(minutes=index * 3), "value": value, "baseline": 1, "threshold": 10, "higher_is_worse": True, "source_event_id": f"signal-{index}", "labels": {"environment": "production"}} for index, value in enumerate([1.2, 2.0, 3.1, 4.4, 5.8, 7.0, 8.0, 9.0])]
            result = ingest(db, incident, {"source": "prometheus", "observations": observations, "auto_forecast": True, "forecast_horizon_minutes": 15, "dependency_map": {"payments": ["checkout", "orders"]}, "region_catalog": [{"code": "us-east", "latitude": 37, "longitude": -78, "traffic_share": .6, "customers": 100000, "services": ["payments"]}]}, "orbit-scheduler")
            prediction = db.get(PredictionRun, result["prediction_run_id"])
            prediction.created_at = start + timedelta(minutes=22)
            db.add_all([
                TelemetryObservation(incident_id=incident.id, metric="payment_error_rate", service="payments", region="us-east", observed_at=start + timedelta(minutes=25), value=9.5, baseline=1, threshold=10, source="prometheus", source_event_id="actual-1"),
                TelemetryObservation(incident_id=incident.id, metric="payment_error_rate", service="payments", region="us-east", observed_at=start + timedelta(minutes=29), value=11.4, baseline=1, threshold=10, source="prometheus", source_event_id="actual-2"),
            ])
            db.commit()
            learning = evaluate_mature(db, incident.id, datetime.now(timezone.utc), 0, "orbit-scheduler")
            snapshot = command_center_snapshot(db, incident)
        self.assertGreaterEqual(len(result["early_warnings"]), 1)
        self.assertIsNotNone(result["prediction_run_id"])
        self.assertGreater(prediction.forecast["incident_escalation_probability"], 60)
        self.assertGreater(snapshot["prediction_engine"]["latest"]["geospatial"]["customers_at_risk"], 0)
        self.assertEqual(learning["evaluated"], 1)
        self.assertEqual(snapshot["learning_engine"]["evaluation_count"], 1)
        self.assertEqual(snapshot["guardrails"]["root_cause_status"], "unconfirmed")
        self.assertFalse(snapshot["guardrails"]["may_claim_root_cause"])
        self.assertTrue(snapshot["guardrails"]["human_confirmation_required_for_critical_actions"])


if __name__ == "__main__":
    unittest.main()
