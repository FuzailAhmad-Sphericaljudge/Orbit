from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .commander_operations import incident_analytics, recovery_readiness, report_content, role_briefing
from .models import (ActionItem, ActionStatus, AgentRun, AnalysisResult, ApprovalRequest,
                     BriefingAudience, BriefingRecord, EvidenceArtifact,
                     EvidenceClassification, EvidenceItem, Incident, IncidentMemory,
                     IncidentReport, IntelligenceFinding, KnowledgeEdge, KnowledgeNode,
                     Participant, PredictionRun, SimulationRun, TelemetryObservation, ForecastEvaluation,
                     RecoveryCheck, TimelineEvent, ToolExecution,
                     TranscriptTurn, UnknownItem, VoiceSession, VoiceSessionStatus)
from .telemetry_intelligence import early_warnings
from .telemetry_service import calibration
from .production_learning_service import learning_status
from .certification_service import latest_certification


def _value(value):
    return value.value if hasattr(value, "value") else value


def _iso(value):
    return value.isoformat() if value else None


def incident_snapshot(db: Session, incident: Incident) -> dict:
    evidence_rows = list(db.scalars(select(EvidenceItem).where(EvidenceItem.incident_id == incident.id).order_by(EvidenceItem.created_at)))
    action_rows = list(db.scalars(select(ActionItem).where(ActionItem.incident_id == incident.id).order_by(ActionItem.created_at)))
    unknown_rows = list(db.scalars(select(UnknownItem).where(UnknownItem.incident_id == incident.id).order_by(UnknownItem.created_at)))
    recovery_rows = list(db.scalars(select(RecoveryCheck).where(RecoveryCheck.incident_id == incident.id).order_by(RecoveryCheck.created_at)))
    timeline_rows = list(db.scalars(select(TimelineEvent).where(TimelineEvent.incident_id == incident.id).order_by(TimelineEvent.created_at)))
    approval_rows = list(db.scalars(select(ApprovalRequest).where(ApprovalRequest.incident_id == incident.id).order_by(ApprovalRequest.created_at)))
    tool_rows = list(db.scalars(select(ToolExecution).where(ToolExecution.incident_id == incident.id).order_by(ToolExecution.created_at)))
    now = datetime.now(timezone.utc)
    evidence = [{"id": item.id, "claim": item.claim, "classification": _value(item.classification), "confidence": item.confidence, "source": item.source, "created_at": _iso(item.created_at)} for item in evidence_rows]
    actions = [{"id": item.id, "task": item.task, "owner_id": item.owner_id, "status": _value(item.status), "due_at": _iso(item.due_at), "escalation_level": item.escalation_level, "overdue": bool(item.due_at and item.status != ActionStatus.complete and item.due_at.replace(tzinfo=item.due_at.tzinfo or timezone.utc) < now), "completed_at": _iso(item.completed_at)} for item in action_rows]
    unknowns = [{"id": item.id, "question": item.question, "priority": item.priority, "status": item.status} for item in unknown_rows]
    checks = [{"id": item.id, "criterion": item.criterion, "status": _value(item.status), "observation": item.observation, "evidence_ids": item.evidence_ids, "checked_by": item.checked_by} for item in recovery_rows]
    timeline = [{"id": item.id, "event_type": item.event_type, "summary": item.summary, "actor_id": item.actor_id, "payload": item.payload, "created_at": _iso(item.created_at)} for item in timeline_rows]
    decisions = [{"id": item.id, "claim": item.claim, "source": item.source, "confidence": item.confidence, "created_at": _iso(item.created_at)} for item in evidence_rows if item.classification == EvidenceClassification.decision]
    approvals = [{"id": item.id, "action": item.action, "status": _value(item.status), "decided_by": item.decided_by, "created_at": _iso(item.created_at)} for item in approval_rows]
    tools = [{"id": item.id, "provider": _value(item.provider), "operation": item.operation, "status": _value(item.status), "approval_id": item.approval_id, "external_id": item.external_id, "created_at": _iso(item.created_at)} for item in tool_rows]
    recovery = recovery_readiness(checks, actions, unknowns)
    analytics = incident_analytics(incident.created_at, now, evidence, actions, unknowns, decisions, approvals, len(timeline))
    incident_data = {"id": incident.id, "title": incident.title, "service": incident.service, "severity": incident.severity, "status": _value(incident.status), "customer_impact": incident.customer_impact, "affected_regions": incident.affected_regions, "recovery_criteria": incident.recovery_criteria, "commander_id": incident.commander_id, "created_at": _iso(incident.created_at)}
    return {"incident": incident_data, "evidence": evidence, "actions": actions, "unknowns": unknowns, "checks": checks, "timeline": timeline, "decisions": decisions, "approvals": approvals, "tools": tools, "recovery": recovery, "analytics": analytics}


def command_center_snapshot(db: Session, incident: Incident) -> dict:
    """Build the bounded, source-preserving read model used by the live command center."""
    snapshot = incident_snapshot(db, incident)
    participants = list(db.scalars(select(Participant).where(Participant.incident_id == incident.id).order_by(Participant.joined_at)))
    voice_sessions = list(db.scalars(select(VoiceSession).where(VoiceSession.incident_id == incident.id).order_by(VoiceSession.started_at.desc())))
    transcripts = list(db.scalars(select(TranscriptTurn).where(TranscriptTurn.incident_id == incident.id).order_by(TranscriptTurn.created_at.desc()).limit(100)))
    findings = list(db.scalars(select(IntelligenceFinding).where(IntelligenceFinding.incident_id == incident.id).order_by(IntelligenceFinding.created_at.desc())))
    artifacts = list(db.scalars(select(EvidenceArtifact).where(EvidenceArtifact.incident_id == incident.id).order_by(EvidenceArtifact.created_at.desc()).limit(50)))
    nodes = list(db.scalars(select(KnowledgeNode).where(KnowledgeNode.incident_id == incident.id)))
    edges = list(db.scalars(select(KnowledgeEdge).where(KnowledgeEdge.incident_id == incident.id)))
    analyses = list(db.scalars(select(AnalysisResult).where(AnalysisResult.incident_id == incident.id).order_by(AnalysisResult.created_at.desc()).limit(30)))
    agent_runs = list(db.scalars(select(AgentRun).where(AgentRun.incident_id == incident.id).order_by(AgentRun.started_at.desc()).limit(30)))
    briefings = list(db.scalars(select(BriefingRecord).where(BriefingRecord.incident_id == incident.id).order_by(BriefingRecord.created_at.desc()).limit(20)))
    reports = list(db.scalars(select(IncidentReport).where(IncidentReport.incident_id == incident.id).order_by(IncidentReport.created_at.desc()).limit(20)))
    predictions = list(db.scalars(select(PredictionRun).where(PredictionRun.incident_id == incident.id).order_by(PredictionRun.created_at.desc()).limit(10)))
    simulations = list(db.scalars(select(SimulationRun).where(SimulationRun.incident_id == incident.id).order_by(SimulationRun.created_at.desc()).limit(10)))
    telemetry = list(db.scalars(select(TelemetryObservation).where(TelemetryObservation.incident_id == incident.id).order_by(TelemetryObservation.observed_at.desc()).limit(500)))
    evaluations = list(db.scalars(select(ForecastEvaluation).where(ForecastEvaluation.incident_id == incident.id).order_by(ForecastEvaluation.evaluated_at.desc()).limit(20)))
    telemetry_rows = [{"metric": item.metric, "service": item.service, "region": item.region, "observed_at": item.observed_at, "value": item.value, "baseline": item.baseline, "threshold": item.threshold, "higher_is_worse": item.higher_is_worse, "source": item.source} for item in reversed(telemetry)]
    active_warnings = early_warnings(telemetry_rows)
    latest_event_at = snapshot["timeline"][-1]["created_at"] if snapshot["timeline"] else snapshot["incident"]["created_at"]
    open_findings = [item for item in findings if item.status == "open"]
    active_voice_sessions = [item for item in voice_sessions if item.status == VoiceSessionStatus.active]
    certification = latest_certification(db, incident.id)

    snapshot.update({
        "live_room": {
            "participants": [{"id": item.id, "agora_uid": item.agora_uid, "display_name": item.display_name, "role": item.role, "language": item.language, "joined_at": _iso(item.joined_at)} for item in participants],
            "voice_sessions": [{"id": item.id, "channel": item.channel, "language": item.language, "status": _value(item.status), "started_at": _iso(item.started_at), "stopped_at": _iso(item.stopped_at)} for item in voice_sessions],
            "active": bool(active_voice_sessions),
            "recent_transcripts": [{"id": item.id, "speaker_name": item.speaker_name, "speaker_role": item.speaker_role, "text": item.text, "language": item.language, "created_at": _iso(item.created_at)} for item in reversed(transcripts)],
        },
        "intelligence": {
            "findings": [{"id": item.id, "type": _value(item.finding_type), "title": item.title, "description": item.description, "severity": item.severity, "status": item.status, "related_evidence_ids": item.related_evidence_ids, "created_at": _iso(item.created_at)} for item in findings],
            "artifacts": [{"id": item.id, "type": _value(item.artifact_type), "title": item.title, "source_name": item.source_name, "analysis_status": item.analysis_status, "observed_at": _iso(item.observed_at), "created_at": _iso(item.created_at)} for item in artifacts],
            "knowledge_graph": {"nodes": len(nodes), "edges": len(edges), "contradiction_edges": sum(1 for item in edges if _value(item.relation) == "contradicts")},
            "analyses": [{"id": item.id, "kind": _value(item.kind), "summary": item.summary, "confidence": item.confidence, "limitations": item.limitations, "created_at": _iso(item.created_at)} for item in analyses],
            "agent_runs": [{"id": item.id, "agent": _value(item.agent_name), "status": item.status, "latency_ms": item.latency_ms, "started_at": _iso(item.started_at), "completed_at": _iso(item.completed_at)} for item in agent_runs],
        },
        "communications": {
            "briefings": [{"id": item.id, "audience": _value(item.audience), "message": item.message, "source_references": item.source_references, "spoken": item.spoken, "created_at": _iso(item.created_at)} for item in briefings],
        },
        "reports": [{"id": item.id, "type": _value(item.report_type), "status": _value(item.status), "title": item.title, "created_at": _iso(item.created_at), "updated_at": _iso(item.updated_at)} for item in reports],
        "prediction_engine": {
            "latest": ({"id": predictions[0].id, "horizon_minutes": predictions[0].horizon_minutes, "forecast": predictions[0].forecast, "graphs": predictions[0].graphs, "geospatial": predictions[0].geospatial, "limitations": predictions[0].limitations, "created_at": _iso(predictions[0].created_at)} if predictions else None),
            "history_count": len(predictions),
            "simulations": [{"id": item.id, "name": item.name, "prediction_run_id": item.prediction_run_id, "iterations": item.iterations, "result": item.result, "created_at": _iso(item.created_at)} for item in simulations],
            "advisory_only": True,
        },
        "telemetry_engine": {
            "observation_count": len(telemetry),
            "recent": [{**item, "observed_at": _iso(item["observed_at"])} for item in telemetry_rows[-100:]],
            "early_warnings": active_warnings[:20],
            "evaluations": [{"id": item.id, "prediction_run_id": item.prediction_run_id, "brier_score": item.brier_score, "mean_absolute_error": item.mean_absolute_error, "lead_time_minutes": item.lead_time_minutes, "quality": item.calibration.get("quality", "unknown"), "drift": item.drift.get("status", "unknown"), "evaluated_at": _iso(item.evaluated_at)} for item in evaluations],
            "calibration": calibration(db, incident.id),
            "automatic_forecasting": True,
        },
        "learning_engine": learning_status(db, incident.id),
        "certification_engine": ({"id": certification.id, "environment": certification.environment, "status": certification.status, "checklist": certification.checklist, "performance": certification.performance, "promotion_gates": certification.promotion_gates, "certified_by": certification.certified_by, "evaluated_at": _iso(certification.evaluated_at), "certified_at": _iso(certification.certified_at)} if certification else {"status": "not_started", "promotion_gates": {"promotion_allowed": False}}),
        "guardrails": {
            "root_cause_status": "unconfirmed",
            "may_claim_root_cause": False,
            "human_confirmation_required_for_critical_actions": True,
            "pending_approvals": sum(1 for item in snapshot["approvals"] if item["status"] == "pending"),
            "open_conflicts": sum(1 for item in open_findings if _value(item.finding_type) == "contradiction"),
            "open_unknowns": sum(1 for item in snapshot["unknowns"] if item["status"] == "open"),
        },
        "sync": {"generated_at": datetime.now(timezone.utc).isoformat(), "latest_event_at": latest_event_at, "timeline_event_count": len(snapshot["timeline"])},
    })
    return snapshot


def build_audience_briefing(db: Session, incident: Incident, audience: BriefingAudience) -> tuple[str, list[str]]:
    snapshot = incident_snapshot(db, incident)
    facts = [item["claim"] for item in snapshot["evidence"] if item["classification"] == "confirmed_fact"]
    hypotheses = [item["claim"] for item in snapshot["evidence"] if item["classification"] == "hypothesis"]
    decisions = [item["claim"] for item in snapshot["decisions"]]
    message = role_briefing(audience.value, snapshot["incident"], facts, hypotheses, decisions, snapshot["actions"], [item["question"] for item in snapshot["unknowns"] if item["status"] == "open"], snapshot["recovery"])
    references = [item["id"] for item in snapshot["evidence"][-10:]] + [item["id"] for item in snapshot["actions"] if item["status"] != "complete"] + [item["id"] for item in snapshot["unknowns"] if item["status"] == "open"]
    return message, references


def decision_audit(db: Session, incident: Incident) -> dict:
    snapshot = incident_snapshot(db, incident)
    return {"decisions": snapshot["decisions"], "approvals": snapshot["approvals"], "tool_executions": snapshot["tools"], "human_authority_preserved": True}


def build_report(db: Session, incident: Incident) -> dict:
    snapshot = incident_snapshot(db, incident)
    memory = db.scalar(select(IncidentMemory).where(IncidentMemory.incident_id == incident.id))
    return report_content(snapshot["incident"], snapshot["timeline"], snapshot["evidence"], snapshot["actions"], snapshot["unknowns"], snapshot["decisions"], snapshot["recovery"], snapshot["analytics"], memory.root_cause_status if memory else "unconfirmed", memory.root_cause if memory else None)
