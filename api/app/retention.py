from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EvidenceArtifact, Incident, IncidentStatus, TranscriptTurn


def apply_retention(db: Session, retention_days: int, confirm: bool = False) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    incident_ids = list(db.scalars(select(Incident.id).where(Incident.status == IncidentStatus.resolved, Incident.updated_at < cutoff)))
    transcripts = list(db.scalars(select(TranscriptTurn).where(TranscriptTurn.incident_id.in_(incident_ids)))) if incident_ids else []
    artifacts = list(db.scalars(select(EvidenceArtifact).where(EvidenceArtifact.incident_id.in_(incident_ids)))) if incident_ids else []
    result = {"cutoff": cutoff.isoformat(), "incidents": len(incident_ids), "transcripts_to_delete": len(transcripts), "artifacts_to_redact": len(artifacts), "applied": confirm}
    if not confirm:
        return result
    for transcript in transcripts:
        db.delete(transcript)
    for artifact in artifacts:
        artifact.extracted_text = None
        artifact.storage_uri = None
        artifact.source_uri = None
        artifact.artifact_metadata = {**artifact.artifact_metadata, "retention_redacted_at": datetime.now(timezone.utc).isoformat()}
        artifact.analysis_status = "retention_redacted"
    db.commit()
    return result
