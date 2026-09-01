import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.certification_service import evidence_pack
from app.database import Base
from app.models import CertificationMeasurement, CertificationRun, Incident


class CertificationEvidencePackTests(unittest.TestCase):
    def test_pack_keeps_blocked_gates_and_evidence_separate(self):
        engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)
        with session() as db:
            incident = Incident(title="Payment outage", service="payments", severity="SEV1", commander_id="commander")
            db.add(incident)
            db.flush()
            run = CertificationRun(incident_id=incident.id, environment="staging", started_by="commander", checklist={"human_authority": {"passed": True}}, performance={"voice_join_latency_ms": {"passed": False, "threshold": {"maximum": 3000}}}, promotion_gates={"promotion_allowed": False, "configuration": {"agora_credentials": {"passed": False, "required": "server-side Agora credentials"}}})
            db.add(run)
            db.flush()
            db.add(CertificationMeasurement(certification_run_id=run.id, metric="api_p95_latency_ms", value=320, unit="ms", source="locust", evidence_reference="staging-load-2026-08-30", recorded_by="commander"))
            db.commit()
            pack = evidence_pack(db, run)
        self.assertFalse(pack["promotion_allowed"])
        self.assertEqual(len(pack["measurements"]), 1)
        self.assertTrue(any(item["name"] == "agora_credentials" for item in pack["blocked_gates"]))
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
