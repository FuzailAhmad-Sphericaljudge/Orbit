from collections import defaultdict
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .integrations import integration_registry
from .models import (ActionItem, ApprovalRequest, ApprovalStatus, BriefingRecord,
                     CertificationMeasurement, CertificationRun, EvidenceClassification,
                     EvidenceItem, FindingType, Incident, IncidentReport, IncidentReportStatus,
                     IncidentReportType, IntelligenceFinding, IntegrationProvider, Participant,
                     PredictionRun, RiskLevel, SimulationRun, TimelineEvent, ToolExecution,
                     ToolExecutionStatus, UnknownItem, VoiceSession, VoiceSessionStatus)
from .voice import voice_service


PERFORMANCE_GATES = {
    "voice_join_latency_ms": {"maximum": 3000, "minimum_samples": 3, "statistic": "p95"},
    "transcript_to_state_ms": {"maximum": 2000, "minimum_samples": 5, "statistic": "p95"},
    "spoken_summary_latency_ms": {"maximum": 4000, "minimum_samples": 3, "statistic": "p95"},
    "websocket_delivery_ms": {"maximum": 1000, "minimum_samples": 5, "statistic": "p95"},
    "api_p95_latency_ms": {"maximum": 500, "minimum_samples": 1, "statistic": "maximum"},
    "http_error_rate_percent": {"maximum": 1, "minimum_samples": 1, "statistic": "maximum"},
    "root_cause_guardrail_violations": {"maximum": 0, "minimum_samples": 1, "statistic": "maximum"},
    "unapproved_critical_actions": {"maximum": 0, "minimum_samples": 1, "statistic": "maximum"},
    "backup_restore_pass": {"minimum": 1, "minimum_samples": 1, "statistic": "minimum"},
    "failure_recovery_pass": {"minimum": 1, "minimum_samples": 1, "statistic": "minimum"},
}


def _value(value):
    return value.value if hasattr(value, "value") else value


def _gate(passed: bool, evidence: dict, required: str) -> dict:
    return {"passed": bool(passed), "required": required, "evidence": evidence}


def functional_checklist(db: Session, incident: Incident) -> dict:
    participants = list(db.scalars(select(Participant).where(Participant.incident_id == incident.id)))
    voices = list(db.scalars(select(VoiceSession).where(VoiceSession.incident_id == incident.id)))
    evidence = list(db.scalars(select(EvidenceItem).where(EvidenceItem.incident_id == incident.id)))
    actions = list(db.scalars(select(ActionItem).where(ActionItem.incident_id == incident.id)))
    findings = list(db.scalars(select(IntelligenceFinding).where(IntelligenceFinding.incident_id == incident.id)))
    unknowns = list(db.scalars(select(UnknownItem).where(UnknownItem.incident_id == incident.id)))
    timeline = list(db.scalars(select(TimelineEvent).where(TimelineEvent.incident_id == incident.id)))
    tools = list(db.scalars(select(ToolExecution).where(ToolExecution.incident_id == incident.id)))
    approvals = {item.id: item for item in db.scalars(select(ApprovalRequest).where(ApprovalRequest.incident_id == incident.id))}
    briefings = list(db.scalars(select(BriefingRecord).where(BriefingRecord.incident_id == incident.id)))
    reports = list(db.scalars(select(IncidentReport).where(IncidentReport.incident_id == incident.id)))
    predictions = list(db.scalars(select(PredictionRun).where(PredictionRun.incident_id == incident.id)))
    simulations = list(db.scalars(select(SimulationRun).where(SimulationRun.incident_id == incident.id)))
    classes = {_value(item.classification) for item in evidence}
    roles = {item.role.strip().lower() for item in participants}
    successful_providers = {_value(item.provider) for item in tools if item.status == ToolExecutionStatus.succeeded}
    critical = [item for item in tools if item.risk_level in {RiskLevel.high, RiskLevel.critical} and item.status == ToolExecutionStatus.succeeded]
    unsafe = [item.id for item in critical if not item.approval_id or item.approval_id not in approvals or approvals[item.approval_id].status != ApprovalStatus.approved]
    final_summaries = [item for item in reports if item.report_type == IncidentReportType.final_summary and item.status == IncidentReportStatus.final]
    unresolved_recorded = any("unresolved_risks" in item.content for item in final_summaries)
    return {
        "live_voice_room": _gate(any(item.agora_agent_session_id and item.status in {VoiceSessionStatus.active, VoiceSessionStatus.stopped} for item in voices), {"sessions": len(voices)}, "successful Agora agent session"),
        "participant_roles": _gate(len(roles) >= 3, {"role_count": len(roles), "roles": sorted(roles)}, "at least three operational roles"),
        "evidence_classification": _gate({"confirmed_fact", "hypothesis", "decision", "action"}.issubset(classes), {"classifications": sorted(classes)}, "facts, hypotheses, decisions, and actions"),
        "owned_actions": _gate(any(item.owner_id for item in actions), {"owned": sum(bool(item.owner_id) for item in actions)}, "at least one assigned action"),
        "conflicts_and_unknowns": _gate(any(item.finding_type == FindingType.contradiction for item in findings) and bool(unknowns), {"conflicts": sum(item.finding_type == FindingType.contradiction for item in findings), "unknowns": len(unknowns)}, "conflict and missing-information evidence"),
        "continuous_timeline": _gate(len(timeline) >= 8, {"events": len(timeline)}, "at least eight ordered incident events"),
        "integrations": _gate({item.value for item in IntegrationProvider}.issubset(successful_providers), {"successful_providers": sorted(successful_providers)}, "successful Slack, Jira, PagerDuty, and monitoring staging calls"),
        "spoken_summary": _gate(any(item.spoken for item in briefings), {"spoken_briefings": sum(item.spoken for item in briefings)}, "at least one delivered spoken briefing"),
        "human_authority": _gate(not unsafe, {"critical_executions": len(critical), "unsafe_execution_ids": unsafe}, "every high/critical execution has approved human confirmation"),
        "final_summary": _gate(bool(final_summaries) and unresolved_recorded, {"final_summaries": len(final_summaries), "unresolved_risks_recorded": unresolved_recorded}, "final incident summary with unresolved risks"),
        "predictive_intelligence": _gate(bool(predictions) and bool(simulations), {"predictions": len(predictions), "simulations": len(simulations)}, "persisted forecast and counterfactual simulation"),
        "root_cause_guardrail": _gate(True, {"system_contract": "AI root-cause confirmation is disabled; only human-confirmed memory is allowed"}, "no autonomous root-cause determination"),
    }


def performance_summary(measurements: list[CertificationMeasurement]) -> dict:
    grouped = defaultdict(list)
    for item in measurements:
        grouped[item.metric].append(item)
    result = {}
    for metric, policy in PERFORMANCE_GATES.items():
        samples = grouped.get(metric, [])
        values = sorted(item.value for item in samples)
        if values:
            statistic = policy["statistic"]
            measured = values[min(len(values) - 1, ceil(.95 * len(values)) - 1)] if statistic == "p95" else max(values) if statistic == "maximum" else min(values)
        else:
            measured = None
        enough = len(samples) >= policy["minimum_samples"]
        evidence_complete = bool(samples) and all(item.evidence_reference for item in samples)
        threshold_pass = measured is not None and (measured <= policy["maximum"] if "maximum" in policy else measured >= policy["minimum"])
        result[metric] = {"passed": enough and evidence_complete and threshold_pass, "measured": round(measured, 3) if measured is not None else None, "sample_count": len(samples), "minimum_samples": policy["minimum_samples"], "statistic": policy["statistic"], "threshold": {key: value for key, value in policy.items() if key in {"minimum", "maximum"}}, "evidence_complete": evidence_complete}
    return result


def configuration_gates() -> dict:
    settings = get_settings()
    integrations = {provider.value: connector.configured for provider, connector in integration_registry.items()}
    return {
        "staging_runtime": _gate(settings.environment != "development", {"environment": settings.environment}, "non-development environment"),
        "agora_credentials": _gate(voice_service.configured(), {"configured": voice_service.configured()}, "server-side Agora credentials"),
        "integration_credentials": _gate(all(integrations.values()), integrations, "all declared integration credentials"),
        "distributed_coordination": _gate(settings.redis_required, {"redis_required": settings.redis_required}, "fail-closed Redis coordination"),
        "identity": _gate(bool(settings.oidc_jwks_url and settings.oidc_issuer and settings.oidc_audience), {"oidc_configured": bool(settings.oidc_jwks_url)}, "OIDC issuer, audience, and JWKS"),
        "encryption": _gate(bool(settings.data_encryption_key), {"configured": bool(settings.data_encryption_key)}, "authenticated data encryption"),
    }


def evaluate_run(db: Session, run: CertificationRun) -> CertificationRun:
    incident = db.get(Incident, run.incident_id)
    if not incident:
        raise ValueError("Certification incident no longer exists")
    checklist = functional_checklist(db, incident)
    measurements = list(db.scalars(select(CertificationMeasurement).where(CertificationMeasurement.certification_run_id == run.id)))
    performance = performance_summary(measurements)
    configuration = configuration_gates()
    groups = {"functional": all(item["passed"] for item in checklist.values()), "performance": all(item["passed"] for item in performance.values()), "configuration": all(item["passed"] for item in configuration.values())}
    hard_failure = not checklist["human_authority"]["passed"] or any(item["sample_count"] and not item["passed"] and item["evidence_complete"] for item in performance.values())
    run.checklist = checklist
    run.performance = performance
    run.promotion_gates = {"groups": groups, "configuration": configuration, "promotion_allowed": all(groups.values()), "human_approval_required": True}
    run.status = "passed" if all(groups.values()) else "failed" if hard_failure else "blocked"
    run.evaluated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def latest_certification(db: Session, incident_id: str) -> CertificationRun | None:
    return db.scalar(select(CertificationRun).where(CertificationRun.incident_id == incident_id).order_by(CertificationRun.started_at.desc()))


def evidence_pack(db: Session, run: CertificationRun) -> dict:
    """Return a portable, read-only release-evidence summary for human review."""
    measurements = list(db.scalars(select(CertificationMeasurement).where(CertificationMeasurement.certification_run_id == run.id).order_by(CertificationMeasurement.recorded_at)))
    blocked = []
    for group, values in (("functional", run.checklist), ("performance", run.performance), ("configuration", run.promotion_gates.get("configuration", {}))):
        for name, value in values.items():
            if not value.get("passed", False):
                blocked.append({"group": group, "name": name, "required": value.get("required") or value.get("threshold"), "evidence": value.get("evidence")})
    return {
        "certification_run_id": run.id,
        "incident_id": run.incident_id,
        "environment": run.environment,
        "status": run.status,
        "promotion_allowed": bool(run.promotion_gates.get("promotion_allowed", False)),
        "human_approval_required": True,
        "blocked_gates": blocked,
        "measurements": [{"metric": item.metric, "value": item.value, "unit": item.unit, "source": item.source, "evidence_reference": item.evidence_reference, "recorded_at": item.recorded_at} for item in measurements],
        "manual_next_steps": [
            "Attach staging evidence for every latency, recovery, and security gate.",
            "Use real Agora and integration credentials; never record a missing credential as a pass.",
            "A commander or administrator must explicitly certify only after every gate passes.",
        ],
    }
