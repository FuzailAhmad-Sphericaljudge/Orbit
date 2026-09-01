import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commander_service import command_center_snapshot
from app.database import Base
from app.models import (ApprovalRequest, EvidenceClassification, EvidenceItem, FindingType,
                        Incident, IntelligenceFinding, Participant, TimelineEvent, UnknownItem,
                        TelemetryObservation, VoiceSession, VoiceSessionStatus)


class CommandCenterSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_snapshot_unifies_live_state_and_preserves_root_cause_guardrail(self):
        with self.Session() as db:
            incident = Incident(
                title="Payment authorization outage",
                service="payments-api",
                severity="SEV1",
                commander_id="commander-1",
                customer_impact="Card payments are failing",
            )
            db.add(incident)
            db.flush()
            db.add_all([
                TimelineEvent(incident_id=incident.id, event_type="incident.declared", summary="SEV1 declared", actor_id="commander-1"),
                EvidenceItem(incident_id=incident.id, claim="Authorization failures exceed 40%", classification=EvidenceClassification.confirmed_fact, confidence=98, source="payments-dashboard"),
                UnknownItem(incident_id=incident.id, question="Is the issuer network degraded?", normalized_key="issuer-network-degraded", category="dependency", priority="high"),
                ApprovalRequest(incident_id=incident.id, action="Fail over payment routing", rationale="Reduce customer impact"),
                Participant(incident_id=incident.id, agora_uid="1001", display_name="Maya", role="Incident Commander", language="en-US"),
                VoiceSession(incident_id=incident.id, channel="payments-sev1", agent_uid="9001", language="en-US", status=VoiceSessionStatus.active),
                IntelligenceFinding(incident_id=incident.id, finding_type=FindingType.contradiction, title="Conflicting error-rate reports", description="Dashboard sources disagree", severity="high"),
                TelemetryObservation(incident_id=incident.id, metric="payment_error_rate", service="payments-api", region="us-east", observed_at=datetime.now(timezone.utc) - timedelta(minutes=5), value=5, baseline=1, threshold=10, source="prometheus", source_event_id="metric-1"),
                TelemetryObservation(incident_id=incident.id, metric="payment_error_rate", service="payments-api", region="us-east", observed_at=datetime.now(timezone.utc), value=9, baseline=1, threshold=10, source="prometheus", source_event_id="metric-2"),
            ])
            db.commit()
            db.refresh(incident)

            result = command_center_snapshot(db, incident)

        self.assertEqual(result["incident"]["service"], "payments-api")
        self.assertTrue(result["live_room"]["active"])
        self.assertEqual(result["live_room"]["participants"][0]["role"], "Incident Commander")
        self.assertEqual(result["guardrails"]["root_cause_status"], "unconfirmed")
        self.assertFalse(result["guardrails"]["may_claim_root_cause"])
        self.assertEqual(result["guardrails"]["pending_approvals"], 1)
        self.assertEqual(result["guardrails"]["open_conflicts"], 1)
        self.assertEqual(result["guardrails"]["open_unknowns"], 1)
        self.assertEqual(result["sync"]["timeline_event_count"], 1)
        self.assertEqual(result["telemetry_engine"]["observation_count"], 2)
        self.assertEqual(len(result["telemetry_engine"]["early_warnings"]), 1)
        self.assertEqual(result["telemetry_engine"]["calibration"]["drift_status"], "stable")


if __name__ == "__main__":
    unittest.main()
