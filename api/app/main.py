import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import secrets
import zlib
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .auth import CurrentUser, current_user, decode_access_token, require_roles
from .alerting import alert_key, service_from_labels, severity_from_labels
from .agents import AGENT_CATALOG
from .config import get_settings
from .commander_operations import replay_events, required_escalation_level
from .commander_service import (build_audience_briefing, build_report, command_center_snapshot,
                                decision_audit, incident_snapshot)
from .coordination import CoordinationBusy, CoordinationUnavailable, coordination
from .database import Base, engine, get_db
from .intelligence import build_status_briefing, classify_turn, detect_findings, extract_action
from .integrations import integration_registry
from .investigation import text_embedding
from .investigation_service import run_investigation
from .forecasting_service import run_prediction, run_simulation
from .telemetry_service import calibration, evaluate, ingest
from .production_learning_service import learning_status, run_learning_cycle
from .certification_service import evaluate_run, evidence_pack
from .memory_search import nearest_memories
from .middleware import ProductionGuardMiddleware
from .models import (ActionItem, ActionStatus, AgentRun, AnalysisResult, ApprovalRequest, ApprovalStatus,
                     BriefingRecord, EvidenceArtifact, EvidenceClassification, EvidenceItem, Incident,
                     IncidentMemory, IncidentReport, IncidentReportStatus, IncidentReportType,
                     IncidentStatus, IntelligenceFinding, KnowledgeEdge, KnowledgeNode, Participant,
                     PredictionRun, SimulationRun, TelemetryObservation, ForecastEvaluation, ProductionLearningRun,
                     CertificationRun, CertificationMeasurement, RecoveryCheck, RecoveryCheckStatus, RiskLevel, Runbook, TimelineEvent,
                     ToolExecution, ToolExecutionStatus, TranscriptTurn, UnknownItem, VoiceSession,
                     VoiceSessionStatus)
from .observability import (ACTION_ESCALATIONS, BRIEFINGS, INVESTIGATION_RUNS, RECOVERIES, REPORTS,
                            TOOL_CALLS, TELEMETRY_INGESTED, EARLY_WARNINGS, FORECAST_EVALUATIONS, LEARNING_CYCLES,
                            configure_logging, metrics_app, metrics_middleware)
from .realtime import hub
from .retention import apply_retention
from .job_queue import job_queue
from .incident_templates import TEMPLATES
from .schemas import (ActionCreate, ActionRead, ActionUpdate, AgentRunRead, AnalysisRead, ApprovalCreate,
                      ApprovalDecision, ApprovalRead, BriefingGenerateRequest, BriefingRead, CommandCenterRead,
                      EscalationResult, EscalationRunRequest, EvidenceArtifactCreate,
                      EvidenceArtifactRead, EvidenceCreate, EvidenceRead, FindingRead, IncidentCreate, TemplateIncidentCreate,
                      IncidentRead, IncidentReportRead, GrafanaAlertWebhook, IntegrationStatus, InvestigationReport,
                      InvestigationRunRequest, KnowledgeEdgeRead, KnowledgeNodeRead, MemoryIndexRequest,
                      ParticipantCreate, ParticipantRead, RecoveryCheckCreate, RecoveryCheckRead,
                      PredictionRunRequest, PredictionRunRead, SimulationRunRequest, SimulationRunRead,
                      TelemetryBatchCreate, TelemetryIngestResult, ForecastEvaluationRead, CalibrationRead,
                      ProductionLearningRead, LearningCycleRequest,
                      CertificationStartRequest, CertificationMeasurementCreate, CertificationRunRead, CertificationEvidencePackRead,
                      RecoveryCheckUpdate, RecoveryReadinessRead, ReplayEventRead, ReportFinalizeRequest,
                      ReportGenerateRequest, ResolveIncidentRequest, RunbookCreate, RunbookRead,
                      SimilarIncidentRead, SpokenBriefingRequest, TimelineRead, ToolExecutionPrepare,
                      ToolExecutionRead, TranscriptCreate, TranscriptRead, UnknownRead,
                      VoiceSessionCreate, VoiceSessionRead, RtcTokenRequest, RtcTokenRead, RetentionRunRequest, AdminJobRequest)
from .services import add_timeline_event
from .tool_policy import effective_risk, sanitized_payload
from .voice import voice_service
from agora_agent.agentkit import generate_rtc_token, expires_in_minutes


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    configure_logging()
    if settings.auto_create_schema and engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    await hub.start()
    try:
        yield
    finally:
        await hub.stop()
        await coordination.close()
        await job_queue.close()


settings = get_settings()
app = FastAPI(title="ORBIT Incident Engine", version="0.11.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(ProductionGuardMiddleware)
app.middleware("http")(metrics_middleware)
app.mount("/metrics", metrics_app)
logger = logging.getLogger("orbit.tools")


def fetch_incident(db: Session, incident_id: str) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident


def validate_evidence_references(db: Session, incident_id: str, reference_ids: list[str]) -> None:
    for reference_id in reference_ids:
        evidence = db.get(EvidenceItem, reference_id)
        artifact = db.get(EvidenceArtifact, reference_id)
        if not ((evidence and evidence.incident_id == incident_id) or (artifact and artifact.incident_id == incident_id)):
            raise HTTPException(422, f"Evidence reference does not belong to this incident: {reference_id}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "orbit-incident-engine", "environment": settings.environment, "agora_configured": voice_service.configured()}


@app.get("/api/status")
def public_status(db: Session = Depends(get_db)):
    active = list(db.scalars(select(Incident).where(Incident.status != IncidentStatus.resolved)))
    components: dict[str, str] = {}
    for incident in active:
        current = components.get(incident.service, "operational")
        next_status = "major_outage" if incident.severity == "SEV1" else "degraded"
        components[incident.service] = "major_outage" if "major_outage" in (current, next_status) else "degraded"
    overall = "major_outage" if "major_outage" in components.values() else ("degraded" if components else "operational")
    return {"status": overall, "updated_at": datetime.now(timezone.utc), "components": [{"name": name, "status": state} for name, state in sorted(components.items())]}


@app.get("/ready")
async def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, "Database is unavailable") from exc
    redis_ready = await coordination.ping()
    if settings.redis_required and not redis_ready:
        raise HTTPException(503, "Redis is unavailable")
    return {"status": "ready", "database": True, "redis": redis_ready, "redis_required": settings.redis_required}


@app.get("/api/agents")
def list_agents(_: CurrentUser = Depends(current_user)):
    return [{"name": spec.name.value, "responsibility": spec.responsibility, "may_execute_external_actions": spec.may_execute_external_actions} for spec in AGENT_CATALOG.values()]


@app.post("/api/incidents", response_model=IncidentRead, status_code=201)
async def create_incident(payload: IncidentCreate, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    incident = Incident(**payload.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)
    if incident.recovery_criteria:
        db.add(RecoveryCheck(incident_id=incident.id, criterion=incident.recovery_criteria, status=RecoveryCheckStatus.pending, automated=False))
        db.commit()
    event = add_timeline_event(db, incident.id, "incident.declared", f"Incident declared: {incident.title}", incident.commander_id, {"severity": incident.severity})
    await hub.publish(incident.id, "timeline.created", {"id": event.id, "summary": event.summary})
    return incident


@app.get("/api/incident-templates")
def list_incident_templates(_: CurrentUser = Depends(current_user)):
    return [{"id": template_id, **{key: value for key, value in template.items() if key != "actions"}} for template_id, template in TEMPLATES.items()]


@app.post("/api/incident-templates/{template_id}/incidents", response_model=IncidentRead, status_code=201)
async def create_incident_from_template(template_id: str, payload: TemplateIncidentCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    template = TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(404, "Incident template not found")
    incident = Incident(title=payload.title or template["name"], service=template["service"], severity=template["severity"], commander_id=user.user_id, customer_impact=template["customer_impact"], affected_regions=payload.affected_regions, recovery_criteria=template["recovery_criteria"])
    db.add(incident)
    db.commit()
    db.refresh(incident)
    db.add(RecoveryCheck(incident_id=incident.id, criterion=incident.recovery_criteria, status=RecoveryCheckStatus.pending, automated=False))
    db.add_all([ActionItem(incident_id=incident.id, task=task, owner_id=user.user_id) for task in template["actions"]])
    db.commit()
    event = add_timeline_event(db, incident.id, "incident.declared", f"Incident declared from template: {incident.title}", user.user_id, {"severity": incident.severity, "template": template_id})
    await hub.publish(incident.id, "timeline.created", {"id": event.id, "summary": event.summary})
    return incident


@app.post("/api/alerts/grafana")
async def ingest_grafana_alert(payload: GrafanaAlertWebhook, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Accept Grafana Alerting webhooks and create or update internal incidents only."""
    expected = settings.monitoring_webhook_token
    if not expected or not authorization or not secrets.compare_digest(authorization, f"Bearer {expected}"):
        raise HTTPException(401, "Invalid Grafana webhook credentials")

    created: list[str] = []
    updated: list[str] = []
    deduplicated: list[str] = []
    for alert in payload.alerts:
        labels = {**payload.commonLabels, **(alert.get("labels") or {})}
        annotations = {**payload.commonAnnotations, **(alert.get("annotations") or {})}
        alert_name = str(labels.get("alertname") or "Grafana alert").strip()[:160]
        service = service_from_labels(labels)
        title = f"{alert_name} ({service})"
        existing = db.scalar(select(Incident).where(Incident.title == title, Incident.service == service, Incident.status != IncidentStatus.resolved).order_by(Incident.created_at.desc()))
        summary = str(annotations.get("summary") or annotations.get("description") or alert_name).strip()[:2000]
        alert_status = str(alert.get("status") or payload.status).lower()
        key = alert_key(alert, labels)
        if existing:
            previous = next((event for event in reversed(list(db.scalars(select(TimelineEvent).where(TimelineEvent.incident_id == existing.id).order_by(TimelineEvent.created_at)))) if event.payload.get("alert_key") == key), None)
            if previous and previous.payload.get("alert_status") == alert_status:
                deduplicated.append(existing.id)
                continue
        metadata = {"labels": labels, "alert_key": key, "alert_status": alert_status}
        if alert_status == "resolved":
            if existing:
                event = add_timeline_event(db, existing.id, "alert.resolved", f"Grafana alert resolved: {summary}", "grafana-alerting", metadata)
                await hub.publish(existing.id, "timeline.created", {"id": event.id, "summary": event.summary})
                updated.append(existing.id)
            continue

        if existing:
            event = add_timeline_event(db, existing.id, "alert.firing", f"Grafana alert firing: {summary}", "grafana-alerting", metadata)
            await hub.publish(existing.id, "timeline.created", {"id": event.id, "summary": event.summary})
            updated.append(existing.id)
            continue

        severity = severity_from_labels(labels)
        incident = Incident(title=title, service=service, severity=severity, commander_id="grafana-alerting", customer_impact=summary, affected_regions=[])
        db.add(incident)
        db.commit()
        db.refresh(incident)
        event = add_timeline_event(db, incident.id, "incident.declared", f"Incident declared from Grafana alert: {summary}", "grafana-alerting", metadata)
        await hub.publish(incident.id, "timeline.created", {"id": event.id, "summary": event.summary})
        created.append(incident.id)
    return {"created_incident_ids": created, "updated_incident_ids": updated, "deduplicated_incident_ids": deduplicated}


@app.get("/api/incidents", response_model=list[IncidentRead])
def list_incidents(db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    return list(db.scalars(select(Incident).order_by(Incident.created_at.desc())))


@app.get("/api/incidents/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    return fetch_incident(db, incident_id)


@app.get("/api/incidents/{incident_id}/command-center", response_model=CommandCenterRead)
def get_command_center(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    incident = fetch_incident(db, incident_id)
    snapshot = command_center_snapshot(db, incident)
    snapshot["integrations"] = [
        IntegrationStatus(provider=provider, configured=connector.configured, supported_operations=connector.supported_operations)
        for provider, connector in integration_registry.items()
    ]
    snapshot["agora_configured"] = voice_service.configured()
    return snapshot


@app.get("/api/incidents/{incident_id}/timeline", response_model=list[TimelineRead])
def get_timeline(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(TimelineEvent).where(TimelineEvent.incident_id == incident_id).order_by(TimelineEvent.created_at)))


@app.post("/api/incidents/{incident_id}/evidence", response_model=EvidenceRead, status_code=201)
async def add_evidence(incident_id: str, payload: EvidenceCreate, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin", "voice_agent"))):
    fetch_incident(db, incident_id)
    evidence = EvidenceItem(incident_id=incident_id, **payload.model_dump())
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    event = add_timeline_event(db, incident_id, "evidence.created", f"{payload.classification.value}: {payload.claim}", payload.source, {"evidence_id": evidence.id, "confidence": payload.confidence})
    await hub.publish(incident_id, "evidence.created", {"id": evidence.id, "claim": evidence.claim, "classification": evidence.classification.value})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return evidence


@app.get("/api/incidents/{incident_id}/evidence", response_model=list[EvidenceRead])
def list_evidence(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(EvidenceItem).where(EvidenceItem.incident_id == incident_id).order_by(EvidenceItem.created_at)))


@app.post("/api/incidents/{incident_id}/actions", response_model=ActionRead, status_code=201)
async def add_action(incident_id: str, payload: ActionCreate, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin", "voice_agent"))):
    fetch_incident(db, incident_id)
    action = ActionItem(incident_id=incident_id, **payload.model_dump())
    db.add(action)
    db.commit()
    db.refresh(action)
    event = add_timeline_event(db, incident_id, "action.assigned", f"Assigned to {action.owner_id}: {action.task}", action.owner_id, {"action_id": action.id})
    await hub.publish(incident_id, "action.created", {"id": action.id, "task": action.task, "owner_id": action.owner_id})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return action


@app.get("/api/incidents/{incident_id}/actions", response_model=list[ActionRead])
def list_actions(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(ActionItem).where(ActionItem.incident_id == incident_id).order_by(ActionItem.created_at)))


@app.patch("/api/incidents/{incident_id}/actions/{action_id}", response_model=ActionRead)
async def update_action(
    incident_id: str,
    action_id: str,
    payload: ActionUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    fetch_incident(db, incident_id)
    action = db.get(ActionItem, action_id)
    if not action or action.incident_id != incident_id:
        raise HTTPException(404, "Action not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(action, key, value)
    if payload.status == ActionStatus.complete:
        action.completed_at = datetime.now(timezone.utc)
    elif payload.status is not None:
        action.completed_at = None
    db.commit()
    db.refresh(action)
    event = add_timeline_event(db, incident_id, "action.updated", f"Action {action.status.value}: {action.task}", user.user_id, {"action_id": action.id, "owner_id": action.owner_id, "status": action.status.value})
    await hub.publish(incident_id, "action.updated", {"id": action.id, "status": action.status.value, "owner_id": action.owner_id, "escalation_level": action.escalation_level})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return action


@app.post("/api/incidents/{incident_id}/actions/escalate", response_model=EscalationResult)
async def escalate_actions(
    incident_id: str,
    payload: EscalationRunRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    fetch_incident(db, incident_id)
    if any(item <= 0 for item in payload.thresholds_minutes):
        raise HTTPException(422, "Escalation thresholds must be positive minutes")
    actions = list(db.scalars(select(ActionItem).where(ActionItem.incident_id == incident_id, ActionItem.status != ActionStatus.complete)))
    now = datetime.now(timezone.utc)
    escalated = []
    for action in actions:
        target = required_escalation_level(action.due_at, now, payload.thresholds_minutes)
        if target > action.escalation_level:
            action.escalation_level = target
            action.last_escalated_at = now
            escalated.append(action)
            ACTION_ESCALATIONS.labels(str(target)).inc()
    db.commit()
    for action in escalated:
        event = add_timeline_event(db, incident_id, "action.escalated", f"Escalation level {action.escalation_level}: {action.owner_id} — {action.task}", user.user_id, {"action_id": action.id, "level": action.escalation_level, "due_at": action.due_at.isoformat() if action.due_at else None})
        await hub.publish(incident_id, "action.escalated", {"id": action.id, "owner_id": action.owner_id, "level": action.escalation_level})
        await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return {"evaluated": len(actions), "escalated_action_ids": [item.id for item in escalated]}


@app.post("/api/incidents/{incident_id}/approvals", response_model=ApprovalRead, status_code=201)
async def request_approval(incident_id: str, payload: ApprovalCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    fetch_incident(db, incident_id)
    approval = ApprovalRequest(incident_id=incident_id, **payload.model_dump())
    db.add(approval)
    db.commit()
    db.refresh(approval)
    add_timeline_event(db, incident_id, "approval.requested", f"Approval requested: {approval.action}", user.user_id, {"approval_id": approval.id, "rationale": payload.rationale})
    await hub.publish(incident_id, "approval.requested", {"id": approval.id, "action": approval.action})
    return approval


@app.post("/api/incidents/{incident_id}/approvals/{approval_id}", response_model=ApprovalRead)
async def decide_approval(incident_id: str, approval_id: str, payload: ApprovalDecision, db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("commander", "approver", "admin"))):
    fetch_incident(db, incident_id)
    approval = db.get(ApprovalRequest, approval_id)
    if not approval or approval.incident_id != incident_id:
        raise HTTPException(404, "Approval request not found")
    if payload.status not in {ApprovalStatus.approved, ApprovalStatus.rejected}:
        raise HTTPException(422, "Decision must be approved or rejected")
    if approval.status != ApprovalStatus.pending:
        raise HTTPException(409, "Approval has already been decided")
    approval.status, approval.decided_by = payload.status, user.user_id
    db.commit()
    db.refresh(approval)
    add_timeline_event(db, incident_id, f"approval.{payload.status.value}", f"{payload.status.value.title()} by {user.user_id}: {approval.action}", user.user_id, {"approval_id": approval.id})
    await hub.publish(incident_id, "approval.decided", {"id": approval.id, "status": approval.status.value})
    return approval


@app.post("/api/incidents/{incident_id}/participants", response_model=ParticipantRead, status_code=201)
async def add_participant(incident_id: str, payload: ParticipantCreate, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin", "voice_agent"))):
    fetch_incident(db, incident_id)
    participant = Participant(incident_id=incident_id, **payload.model_dump())
    db.add(participant)
    db.commit()
    db.refresh(participant)
    event = add_timeline_event(db, incident_id, "participant.joined", f"{participant.display_name} joined as {participant.role}", participant.id, {"agora_uid": participant.agora_uid})
    await hub.publish(incident_id, "participant.joined", {"id": participant.id, "display_name": participant.display_name, "role": participant.role})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return participant


@app.get("/api/incidents/{incident_id}/participants", response_model=list[ParticipantRead])
def list_participants(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(Participant).where(Participant.incident_id == incident_id).order_by(Participant.joined_at)))


@app.post("/api/incidents/{incident_id}/voice/rtc-token", response_model=RtcTokenRead)
def issue_voice_rtc_token(incident_id: str, payload: RtcTokenRequest, db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    fetch_incident(db, incident_id)
    if not voice_service.configured():
        raise HTTPException(503, "Agora credentials are not configured. Set AGORA_APP_ID and AGORA_APP_CERTIFICATE.")
    channel = payload.channel or f"orbit_{incident_id.replace('-', '')[:16]}_{uuid4().hex[:8]}"
    uid = 10_000 + (zlib.crc32(f"{incident_id}:{user.user_id}".encode()) % 2_000_000_000)
    expires_in_seconds = expires_in_minutes(60)
    try:
        token = generate_rtc_token(settings.agora_app_id, settings.agora_app_certificate, channel, uid, expiry_seconds=expires_in_seconds)
    except ValueError as exc:
        raise HTTPException(500, str(exc)) from exc
    return RtcTokenRead(app_id=settings.agora_app_id, channel=channel, uid=uid, token=token, expires_in_seconds=expires_in_seconds)


@app.post("/api/incidents/{incident_id}/voice/sessions", response_model=VoiceSessionRead, status_code=201)
async def start_voice_session(incident_id: str, payload: VoiceSessionCreate, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    fetch_incident(db, incident_id)
    if not voice_service.configured():
        raise HTTPException(503, "Agora credentials are not configured. Set AGORA_APP_ID and AGORA_APP_CERTIFICATE.")
    session = VoiceSession(incident_id=incident_id, channel=payload.channel, agent_uid=settings.agora_agent_uid, language=payload.language)
    db.add(session)
    db.commit()
    db.refresh(session)
    try:
        started = await voice_service.start(session.id, session.channel, payload.remote_uids, session.language)
        session.agora_agent_session_id = started.session_id
        session.status = VoiceSessionStatus.active
        db.commit()
        db.refresh(session)
    except Exception as exc:
        session.status = VoiceSessionStatus.failed
        db.commit()
        raise HTTPException(502, f"Agora agent failed to start: {exc}") from exc
    event = add_timeline_event(db, incident_id, "voice.started", f"ORBIT joined Agora channel {session.channel}", session.agent_uid, {"voice_session_id": session.id})
    await hub.publish(incident_id, "voice.started", {"id": session.id, "channel": session.channel, "status": session.status.value})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return session


@app.get("/api/incidents/{incident_id}/voice/sessions", response_model=list[VoiceSessionRead])
def list_voice_sessions(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(VoiceSession).where(VoiceSession.incident_id == incident_id).order_by(VoiceSession.started_at.desc())))


@app.post("/api/incidents/{incident_id}/voice/sessions/{session_id}/stop", response_model=VoiceSessionRead)
async def stop_voice_session(incident_id: str, session_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    fetch_incident(db, incident_id)
    session = db.get(VoiceSession, session_id)
    if not session or session.incident_id != incident_id:
        raise HTTPException(404, "Voice session not found")
    await voice_service.stop(session.id)
    session.status = VoiceSessionStatus.stopped
    session.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    add_timeline_event(db, incident_id, "voice.stopped", f"ORBIT left Agora channel {session.channel}", session.agent_uid, {"voice_session_id": session.id})
    await hub.publish(incident_id, "voice.stopped", {"id": session.id, "status": session.status.value})
    return session


@app.post("/api/incidents/{incident_id}/transcripts", response_model=TranscriptRead, status_code=201)
async def ingest_transcript(incident_id: str, payload: TranscriptCreate, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin", "voice_agent"))):
    fetch_incident(db, incident_id)
    if payload.participant_id and not db.get(Participant, payload.participant_id):
        raise HTTPException(404, "Participant not found")
    transcript = TranscriptTurn(incident_id=incident_id, **payload.model_dump())
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
    if payload.is_final:
        extraction = classify_turn(payload.text)
        evidence = EvidenceItem(incident_id=incident_id, claim=extraction.claim, classification=extraction.classification, confidence=extraction.confidence, source=f"{payload.speaker_name} ({payload.speaker_role})")
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        existing_claims = list(db.scalars(select(EvidenceItem.claim).where(EvidenceItem.incident_id == incident_id, EvidenceItem.id != evidence.id)))
        created_findings = []
        for candidate in detect_findings(existing_claims, evidence.claim):
            finding = IntelligenceFinding(incident_id=incident_id, finding_type=candidate.finding_type, title=candidate.title, description=candidate.description, severity=candidate.severity, related_evidence_ids=[evidence.id])
            db.add(finding)
            created_findings.append(finding)
        action_data = extract_action(payload.text) if extraction.classification == EvidenceClassification.action else None
        if action_data:
            owner, task = action_data
            db.add(ActionItem(incident_id=incident_id, owner_id=owner, task=task))
        db.commit()
        event = add_timeline_event(db, incident_id, "transcript.classified", f"{extraction.classification.value}: {extraction.claim}", payload.participant_id, {"transcript_id": transcript.id, "evidence_id": evidence.id, "confidence": extraction.confidence})
        await hub.publish(incident_id, "evidence.created", {"id": evidence.id, "claim": evidence.claim, "classification": evidence.classification.value, "confidence": evidence.confidence})
        for finding in created_findings:
            db.refresh(finding)
            await hub.publish(incident_id, "finding.created", {"id": finding.id, "type": finding.finding_type.value, "title": finding.title, "severity": finding.severity})
        await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    await hub.publish(incident_id, "transcript.created", {"id": transcript.id, "speaker_name": transcript.speaker_name, "speaker_role": transcript.speaker_role, "text": transcript.text, "is_final": transcript.is_final})
    return transcript


@app.get("/api/incidents/{incident_id}/transcripts", response_model=list[TranscriptRead])
def list_transcripts(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(TranscriptTurn).where(TranscriptTurn.incident_id == incident_id).order_by(TranscriptTurn.created_at)))


@app.get("/api/incidents/{incident_id}/findings", response_model=list[FindingRead])
def list_findings(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(IntelligenceFinding).where(IntelligenceFinding.incident_id == incident_id).order_by(IntelligenceFinding.created_at.desc())))


@app.post("/api/incidents/{incident_id}/voice/sessions/{session_id}/briefings")
async def speak_briefing(incident_id: str, session_id: str, payload: SpokenBriefingRequest, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    fetch_incident(db, incident_id)
    session = db.get(VoiceSession, session_id)
    if not session or session.incident_id != incident_id or session.status != VoiceSessionStatus.active:
        raise HTTPException(409, "An active voice session is required")
    await voice_service.say(session.id, payload.message)
    event = add_timeline_event(db, incident_id, "briefing.spoken", payload.message, session.agent_uid, {"voice_session_id": session.id})
    await hub.publish(incident_id, "briefing.spoken", {"message": payload.message, "timeline_event_id": event.id})
    return {"status": "spoken", "message": payload.message}


@app.post("/api/incidents/{incident_id}/briefings/generate")
def generate_briefing(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    fetch_incident(db, incident_id)
    evidence = list(db.scalars(select(EvidenceItem).where(EvidenceItem.incident_id == incident_id).order_by(EvidenceItem.created_at.desc())))
    facts = [item.claim for item in evidence if item.classification == EvidenceClassification.confirmed_fact]
    hypotheses = [item.claim for item in evidence if item.classification == EvidenceClassification.hypothesis]
    actions = list(db.scalars(select(ActionItem).where(ActionItem.incident_id == incident_id, ActionItem.status != ActionStatus.complete)))
    findings = list(db.scalars(select(IntelligenceFinding).where(IntelligenceFinding.incident_id == incident_id, IntelligenceFinding.status == "open")))
    message = build_status_briefing(facts, hypotheses, [f"{item.owner_id}: {item.task}" for item in actions], [item.description for item in findings])
    return {"message": message, "root_cause_confirmed": False}


@app.get("/api/integrations/status", response_model=list[IntegrationStatus])
def integration_status(_: CurrentUser = Depends(current_user)):
    return [
        IntegrationStatus(provider=provider, configured=connector.configured, supported_operations=connector.supported_operations)
        for provider, connector in integration_registry.items()
    ]


@app.post("/api/incidents/{incident_id}/tools/prepare", response_model=ToolExecutionRead, status_code=201)
async def prepare_tool_execution(
    incident_id: str,
    payload: ToolExecutionPrepare,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    fetch_incident(db, incident_id)
    connector = integration_registry[payload.provider]
    if payload.operation not in connector.supported_operations:
        raise HTTPException(422, f"Unsupported operation for {payload.provider.value}")
    existing = db.scalar(select(ToolExecution).where(ToolExecution.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.incident_id != incident_id:
            raise HTTPException(409, "Idempotency key is already used by another incident")
        return existing

    try:
        request_payload = sanitized_payload(payload.provider, payload.operation, payload.payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    risk_level = effective_risk(payload.provider, payload.operation, payload.risk_level)
    approval = None
    needs_approval = risk_level in {RiskLevel.high, RiskLevel.critical}
    if needs_approval:
        approval = ApprovalRequest(
            incident_id=incident_id,
            action=f"{payload.provider.value}.{payload.operation}",
            rationale=payload.rationale,
        )
        db.add(approval)
        db.flush()
    execution = ToolExecution(
        incident_id=incident_id,
        provider=payload.provider,
        operation=payload.operation,
        risk_level=risk_level,
        status=ToolExecutionStatus.awaiting_approval if needs_approval else ToolExecutionStatus.prepared,
        requested_by=user.user_id,
        idempotency_key=payload.idempotency_key,
        request_payload=request_payload,
        approval_id=approval.id if approval else None,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    event = add_timeline_event(
        db, incident_id, "tool.prepared",
        f"Prepared {execution.provider.value}.{execution.operation} ({execution.risk_level.value} risk)",
        user.user_id,
        {"tool_execution_id": execution.id, "approval_id": execution.approval_id},
    )
    await hub.publish(incident_id, "tool.prepared", {"id": execution.id, "provider": execution.provider.value, "operation": execution.operation, "status": execution.status.value})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return execution


@app.get("/api/incidents/{incident_id}/tools", response_model=list[ToolExecutionRead])
def list_tool_executions(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(ToolExecution).where(ToolExecution.incident_id == incident_id).order_by(ToolExecution.created_at.desc())))


@app.post("/api/incidents/{incident_id}/tools/{execution_id}/execute", response_model=ToolExecutionRead)
async def execute_tool(
    incident_id: str,
    execution_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    fetch_incident(db, incident_id)
    execution = db.scalar(select(ToolExecution).where(ToolExecution.id == execution_id).with_for_update())
    if not execution or execution.incident_id != incident_id:
        raise HTTPException(404, "Tool execution not found")
    if execution.status == ToolExecutionStatus.succeeded:
        return execution
    if execution.status in {ToolExecutionStatus.executing, ToolExecutionStatus.rejected}:
        raise HTTPException(409, f"Tool execution is {execution.status.value}")
    if execution.approval_id:
        approval = db.get(ApprovalRequest, execution.approval_id)
        if not approval or approval.status == ApprovalStatus.pending:
            raise HTTPException(409, "Human approval is required before execution")
        if approval.status == ApprovalStatus.rejected:
            execution.status = ToolExecutionStatus.rejected
            db.commit()
            raise HTTPException(409, "Human approval was rejected")

    connector = integration_registry[execution.provider]
    if not connector.configured:
        raise HTTPException(503, f"{execution.provider.value} integration is not configured")
    execution.status = ToolExecutionStatus.executing
    db.commit()
    try:
        result = await connector.execute(execution.operation, execution.request_payload)
        execution.status = ToolExecutionStatus.succeeded
        execution.external_id = result.external_id
        execution.response_payload = result.data
        execution.error_message = None
        event_type = "tool.succeeded"
        summary = f"Executed {execution.provider.value}.{execution.operation}"
    except Exception as exc:
        logger.exception("Tool execution failed: provider=%s operation=%s execution_id=%s", execution.provider.value, execution.operation, execution.id)
        execution.status = ToolExecutionStatus.failed
        execution.error_message = str(exc)[:2000]
        execution.response_payload = {}
        event_type = "tool.failed"
        summary = f"Failed {execution.provider.value}.{execution.operation}"
    execution.executed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(execution)
    TOOL_CALLS.labels(execution.provider.value, execution.operation, execution.status.value).inc()
    event = add_timeline_event(db, incident_id, event_type, summary, user.user_id, {"tool_execution_id": execution.id, "external_id": execution.external_id})
    await hub.publish(incident_id, event_type, {"id": execution.id, "status": execution.status.value, "external_id": execution.external_id})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    if execution.status == ToolExecutionStatus.failed:
        raise HTTPException(502, f"Integration execution failed; audit id: {execution.id}")
    return execution


@app.post("/api/incidents/{incident_id}/artifacts", response_model=EvidenceArtifactRead, status_code=201)
async def add_artifact(
    incident_id: str,
    payload: EvidenceArtifactCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    fetch_incident(db, incident_id)
    existing = db.scalar(select(EvidenceArtifact).where(EvidenceArtifact.incident_id == incident_id, EvidenceArtifact.content_sha256 == payload.content_sha256.lower()))
    if existing:
        return existing
    artifact = EvidenceArtifact(incident_id=incident_id, captured_by=user.user_id, **payload.model_dump(exclude={"content_sha256"}), content_sha256=payload.content_sha256.lower())
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    event = add_timeline_event(db, incident_id, "artifact.created", f"Evidence artifact added: {artifact.title}", user.user_id, {"artifact_id": artifact.id, "type": artifact.artifact_type.value, "sha256": artifact.content_sha256})
    await hub.publish(incident_id, "artifact.created", {"id": artifact.id, "title": artifact.title, "type": artifact.artifact_type.value})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return artifact


@app.get("/api/incidents/{incident_id}/artifacts", response_model=list[EvidenceArtifactRead])
def list_artifacts(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(EvidenceArtifact).where(EvidenceArtifact.incident_id == incident_id).order_by(EvidenceArtifact.created_at.desc())))


@app.get("/api/incidents/{incident_id}/knowledge/nodes", response_model=list[KnowledgeNodeRead])
def list_knowledge_nodes(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(KnowledgeNode).where(KnowledgeNode.incident_id == incident_id).order_by(KnowledgeNode.created_at)))


@app.get("/api/incidents/{incident_id}/knowledge/edges", response_model=list[KnowledgeEdgeRead])
def list_knowledge_edges(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(KnowledgeEdge).where(KnowledgeEdge.incident_id == incident_id).order_by(KnowledgeEdge.created_at)))


@app.get("/api/incidents/{incident_id}/unknowns", response_model=list[UnknownRead])
def list_unknowns(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(UnknownItem).where(UnknownItem.incident_id == incident_id).order_by(UnknownItem.created_at)))


@app.get("/api/incidents/{incident_id}/analyses", response_model=list[AnalysisRead])
def list_analyses(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(AnalysisResult).where(AnalysisResult.incident_id == incident_id).order_by(AnalysisResult.created_at.desc())))


@app.get("/api/incidents/{incident_id}/agent-runs", response_model=list[AgentRunRead])
def list_agent_runs(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(AgentRun).where(AgentRun.incident_id == incident_id).order_by(AgentRun.started_at.desc())))


@app.post("/api/incidents/{incident_id}/investigation/run", response_model=InvestigationReport)
async def investigate(
    incident_id: str,
    payload: InvestigationRunRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    incident = fetch_incident(db, incident_id)
    try:
        async with coordination.lock(f"investigation:{incident_id}", ttl_seconds=600):
            report = await run_investigation(db, incident, payload.model_dump(mode="json"))
    except CoordinationBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    except CoordinationUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception:
        INVESTIGATION_RUNS.labels("failed").inc()
        db.rollback()
        logger.exception("Agentic investigation failed", extra={"incident_id": incident_id})
        raise
    INVESTIGATION_RUNS.labels("succeeded").inc()
    event = add_timeline_event(db, incident_id, "investigation.completed", f"Agentic investigation completed with {report['unknowns_open']} open unknowns.", user.user_id, {"agent_run_ids": report["agent_run_ids"], "analysis_ids": [item.id for item in report["analyses"]]})
    await hub.publish(incident_id, "investigation.completed", {"unknowns_open": report["unknowns_open"], "graph_nodes_created": report["graph_nodes_created"], "graph_edges_created": report["graph_edges_created"], "root_cause_confirmed": False})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return report


@app.post("/api/incidents/{incident_id}/predictions/run", response_model=PredictionRunRead, status_code=201)
async def create_prediction(
    incident_id: str,
    payload: PredictionRunRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    incident = fetch_incident(db, incident_id)
    try:
        async with coordination.lock(f"prediction:{incident_id}", ttl_seconds=180):
            record = run_prediction(db, incident, payload.model_dump(mode="json"), user.user_id)
    except CoordinationBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    event = add_timeline_event(db, incident_id, "prediction.completed", f"{record.horizon_minutes}-minute advisory forecast generated.", user.user_id, {"prediction_run_id": record.id, "risk_band": record.forecast.get("risk_band"), "root_cause_confirmed": False})
    await hub.publish(incident_id, "prediction.completed", {"id": record.id, "horizon_minutes": record.horizon_minutes, "risk_band": record.forecast.get("risk_band"), "advisory_only": True})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return record


@app.get("/api/incidents/{incident_id}/predictions", response_model=list[PredictionRunRead])
def list_predictions(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(PredictionRun).where(PredictionRun.incident_id == incident_id).order_by(PredictionRun.created_at.desc())))


@app.post("/api/incidents/{incident_id}/simulations/run", response_model=SimulationRunRead, status_code=201)
async def create_simulation(
    incident_id: str,
    payload: SimulationRunRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    incident = fetch_incident(db, incident_id)
    try:
        record = run_simulation(db, incident, payload.model_dump(mode="json"), user.user_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    event = add_timeline_event(db, incident_id, "simulation.completed", f"Counterfactual simulation completed: {record.name}.", user.user_id, {"simulation_run_id": record.id, "prediction_run_id": record.prediction_run_id, "advisory_only": True})
    await hub.publish(incident_id, "simulation.completed", {"id": record.id, "name": record.name, "risk_reduction": record.result.get("risk_reduction"), "advisory_only": True})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return record


@app.get("/api/incidents/{incident_id}/simulations", response_model=list[SimulationRunRead])
def list_simulations(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(SimulationRun).where(SimulationRun.incident_id == incident_id).order_by(SimulationRun.created_at.desc())))


@app.post("/api/incidents/{incident_id}/telemetry", response_model=TelemetryIngestResult, status_code=202)
async def ingest_telemetry(
    incident_id: str,
    payload: TelemetryBatchCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    incident = fetch_incident(db, incident_id)
    result = ingest(db, incident, payload.model_dump(mode="python"), user.user_id)
    TELEMETRY_INGESTED.labels(payload.source).inc(result["accepted"])
    for warning in result["early_warnings"]:
        EARLY_WARNINGS.labels(warning["service"], warning["metric"]).inc()
    event = add_timeline_event(db, incident_id, "telemetry.ingested", f"Ingested {result['accepted']} telemetry observations; {len(result['early_warnings'])} early warnings active.", user.user_id, {"source": payload.source, "accepted": result["accepted"], "duplicates": result["duplicates"], "prediction_run_id": result["prediction_run_id"]})
    await hub.publish(incident_id, "telemetry.updated", {"accepted": result["accepted"], "early_warnings": result["early_warnings"], "prediction_run_id": result["prediction_run_id"]})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return result


@app.get("/api/incidents/{incident_id}/telemetry")
def list_telemetry(incident_id: str, limit: int = Query(default=500, ge=1, le=5000), db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    rows = list(db.scalars(select(TelemetryObservation).where(TelemetryObservation.incident_id == incident_id).order_by(TelemetryObservation.observed_at.desc()).limit(limit)))
    return [{"id": item.id, "metric": item.metric, "service": item.service, "region": item.region, "observed_at": item.observed_at, "value": item.value, "baseline": item.baseline, "threshold": item.threshold, "higher_is_worse": item.higher_is_worse, "source": item.source, "labels": item.labels} for item in rows]


@app.post("/api/incidents/{incident_id}/predictions/{prediction_id}/evaluate", response_model=ForecastEvaluationRead)
async def evaluate_forecast(
    incident_id: str,
    prediction_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    incident = fetch_incident(db, incident_id)
    prediction = db.get(PredictionRun, prediction_id)
    if not prediction or prediction.incident_id != incident_id:
        raise HTTPException(404, "Prediction run not found")
    try:
        record = evaluate(db, incident, prediction, user.user_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    FORECAST_EVALUATIONS.labels(record.calibration.get("quality", "unknown"), record.drift.get("status", "unknown")).inc()
    event = add_timeline_event(db, incident_id, "prediction.evaluated", f"Forecast evaluated: Brier {record.brier_score}, drift {record.drift.get('status', 'unknown')}.", user.user_id, {"prediction_run_id": prediction_id, "evaluation_id": record.id, "brier_score": record.brier_score})
    await hub.publish(incident_id, "prediction.evaluated", {"id": record.id, "prediction_run_id": prediction_id, "brier_score": record.brier_score, "drift": record.drift})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return record


@app.get("/api/incidents/{incident_id}/forecast-evaluations", response_model=list[ForecastEvaluationRead])
def list_forecast_evaluations(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(ForecastEvaluation).where(ForecastEvaluation.incident_id == incident_id).order_by(ForecastEvaluation.evaluated_at.desc())))


@app.get("/api/incidents/{incident_id}/calibration", response_model=CalibrationRead)
def forecast_calibration(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return calibration(db, incident_id)


@app.get("/api/production-learning/status", response_model=ProductionLearningRead)
def production_learning_status(db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    return learning_status(db)


@app.get("/api/incidents/{incident_id}/production-learning", response_model=ProductionLearningRead)
def incident_production_learning(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return learning_status(db, incident_id)


@app.post("/api/production-learning/run", status_code=202)
async def trigger_production_learning(
    payload: LearningCycleRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    if payload.incident_id:
        fetch_incident(db, payload.incident_id)
    try:
        async with coordination.lock(f"production-learning:{payload.incident_id or 'global'}", ttl_seconds=300):
            result = await run_learning_cycle(payload.incident_id, payload.collect_telemetry, payload.evaluate_mature_forecasts, user.user_id)
    except CoordinationBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    LEARNING_CYCLES.labels("partial" if result["collection"]["errors"] else "completed").inc()
    if payload.incident_id:
        event = add_timeline_event(db, payload.incident_id, "production_learning.completed", f"Production learning cycle completed: {result['maturity_evaluation']['evaluated']} forecasts evaluated.", user.user_id, {"run_id": result["run_id"], "collection": result["collection"], "alert_quality": result["alert_quality"]})
        await hub.publish(payload.incident_id, "production_learning.completed", result)
        await hub.publish(payload.incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return result


@app.post("/api/incidents/{incident_id}/certifications", response_model=CertificationRunRead, status_code=201)
async def start_certification(
    incident_id: str,
    payload: CertificationStartRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    fetch_incident(db, incident_id)
    run = CertificationRun(incident_id=incident_id, environment=payload.environment, notes=payload.notes, started_by=user.user_id)
    db.add(run)
    db.commit()
    db.refresh(run)
    evaluate_run(db, run)
    event = add_timeline_event(db, incident_id, "certification.started", f"{payload.environment.title()} certification started; current status is {run.status}.", user.user_id, {"certification_run_id": run.id, "promotion_allowed": run.promotion_gates.get("promotion_allowed", False)})
    await hub.publish(incident_id, "certification.updated", {"id": run.id, "status": run.status, "promotion_gates": run.promotion_gates})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return run


@app.get("/api/incidents/{incident_id}/certifications", response_model=list[CertificationRunRead])
def list_certifications(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(CertificationRun).where(CertificationRun.incident_id == incident_id).order_by(CertificationRun.started_at.desc())))


@app.post("/api/certifications/{run_id}/measurements", response_model=CertificationRunRead)
async def record_certification_measurement(
    run_id: str,
    payload: CertificationMeasurementCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    run = db.get(CertificationRun, run_id)
    if not run:
        raise HTTPException(404, "Certification run not found")
    if run.status == "certified":
        raise HTTPException(409, "Certified runs are immutable")
    measurement = CertificationMeasurement(certification_run_id=run.id, recorded_by=user.user_id, **payload.model_dump())
    db.add(measurement)
    db.commit()
    evaluate_run(db, run)
    await hub.publish(run.incident_id, "certification.updated", {"id": run.id, "status": run.status, "metric": payload.metric, "promotion_gates": run.promotion_gates})
    return run


@app.post("/api/certifications/{run_id}/guardrail-audit", response_model=CertificationRunRead)
async def record_guardrail_audit(run_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    run = db.get(CertificationRun, run_id)
    if not run:
        raise HTTPException(404, "Certification run not found")
    if run.status == "certified":
        raise HTTPException(409, "Certified runs are immutable")
    critical = list(db.scalars(select(ToolExecution).where(ToolExecution.incident_id == run.incident_id, ToolExecution.status == ToolExecutionStatus.succeeded, ToolExecution.risk_level.in_([RiskLevel.high, RiskLevel.critical]))))
    unsafe = sum(1 for item in critical if not item.approval_id or not (approval := db.get(ApprovalRequest, item.approval_id)) or approval.status != ApprovalStatus.approved)
    evidence = f"Server-side guardrail audit at {datetime.now(timezone.utc).isoformat()}; {len(critical)} successful high/critical executions reviewed."
    db.add_all([
        CertificationMeasurement(certification_run_id=run.id, metric="root_cause_guardrail_violations", value=0, unit="count", source="ORBIT server guardrail audit", evidence_reference="Root-cause confirmation remains human-only by system contract; no autonomous confirmation path is enabled."),
        CertificationMeasurement(certification_run_id=run.id, metric="unapproved_critical_actions", value=unsafe, unit="count", source="ORBIT server guardrail audit", evidence_reference=evidence),
    ])
    db.commit()
    evaluate_run(db, run)
    await hub.publish(run.incident_id, "certification.updated", {"id": run.id, "status": run.status, "metric": "guardrail_audit", "promotion_gates": run.promotion_gates})
    return run


@app.post("/api/certifications/{run_id}/evaluate", response_model=CertificationRunRead)
async def reevaluate_certification(run_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("commander", "operator", "admin"))):
    run = db.get(CertificationRun, run_id)
    if not run:
        raise HTTPException(404, "Certification run not found")
    if run.status == "certified":
        return run
    evaluate_run(db, run)
    await hub.publish(run.incident_id, "certification.updated", {"id": run.id, "status": run.status, "promotion_gates": run.promotion_gates})
    return run


@app.post("/api/certifications/{run_id}/certify", response_model=CertificationRunRead)
async def certify_release(run_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(require_roles("commander", "admin"))):
    run = db.get(CertificationRun, run_id)
    if not run:
        raise HTTPException(404, "Certification run not found")
    evaluate_run(db, run)
    if not run.promotion_gates.get("promotion_allowed"):
        raise HTTPException(409, "Promotion gates are not satisfied")
    run.status = "certified"
    run.certified_by = user.user_id
    run.certified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    event = add_timeline_event(db, run.incident_id, "certification.approved", f"Staging release certified by {user.user_id}.", user.user_id, {"certification_run_id": run.id, "human_confirmed": True})
    await hub.publish(run.incident_id, "certification.certified", {"id": run.id, "certified_by": user.user_id})
    await hub.publish(run.incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return run


@app.get("/api/certifications/{run_id}/evidence-pack", response_model=CertificationEvidencePackRead)
def certification_evidence_pack(run_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    run = db.get(CertificationRun, run_id)
    if not run:
        raise HTTPException(404, "Certification run not found")
    return evidence_pack(db, run)


@app.post("/api/runbooks", response_model=RunbookRead, status_code=201)
def create_runbook(payload: RunbookCreate, db: Session = Depends(get_db), _: CurrentUser = Depends(require_roles("commander", "admin"))):
    runbook = Runbook(**payload.model_dump())
    db.add(runbook)
    db.commit()
    db.refresh(runbook)
    return runbook


@app.get("/api/runbooks", response_model=list[RunbookRead])
def list_runbooks(service: str | None = None, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    query = select(Runbook).where(Runbook.active.is_(True))
    if service:
        query = query.where(Runbook.service == service)
    return list(db.scalars(query.order_by(Runbook.service, Runbook.title)))


@app.put("/api/incidents/{incident_id}/memory", status_code=200)
def index_incident_memory(
    incident_id: str,
    payload: MemoryIndexRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "admin")),
):
    incident = fetch_incident(db, incident_id)
    if payload.root_cause_status == "confirmed_by_human" and not payload.root_cause:
        raise HTTPException(422, "A human-confirmed root cause requires a root-cause statement")
    evidence_claims = list(db.scalars(select(EvidenceItem.claim).where(EvidenceItem.incident_id == incident_id)))
    searchable = " ".join([payload.summary, incident.title, incident.service, *payload.symptoms, *evidence_claims, payload.resolution or ""])
    memory = db.scalar(select(IncidentMemory).where(IncidentMemory.incident_id == incident_id))
    values = {
        "summary": payload.summary,
        "searchable_text": searchable,
        "services": [incident.service],
        "symptoms": payload.symptoms,
        "resolution": payload.resolution,
        "root_cause_status": payload.root_cause_status,
        "root_cause": payload.root_cause,
        "unresolved_risks": payload.unresolved_risks,
        "embedding": text_embedding(searchable),
    }
    if memory:
        for key, value in values.items():
            setattr(memory, key, value)
    else:
        memory = IncidentMemory(incident_id=incident_id, **values)
        db.add(memory)
    db.commit()
    db.refresh(memory)
    add_timeline_event(db, incident_id, "memory.indexed", "Incident memory indexed for future retrieval.", user.user_id, {"memory_id": memory.id, "root_cause_status": memory.root_cause_status})
    return {"id": memory.id, "incident_id": incident_id, "root_cause_status": memory.root_cause_status}


@app.get("/api/incidents/{incident_id}/similar", response_model=list[SimilarIncidentRead])
def similar_incidents(incident_id: str, limit: int = 5, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    incident = fetch_incident(db, incident_id)
    claims = list(db.scalars(select(EvidenceItem.claim).where(EvidenceItem.incident_id == incident_id)))
    query_vector = text_embedding(" ".join([incident.title, incident.service, *claims]))
    nearest = nearest_memories(db, query_vector, incident_id, limit)
    return [{"incident_id": item.incident_id, "similarity": score, "summary": item.summary, "resolution": item.resolution, "root_cause_status": item.root_cause_status} for item, score in nearest]


@app.post("/api/incidents/{incident_id}/briefings", response_model=BriefingRead, status_code=201)
async def generate_briefing(
    incident_id: str,
    payload: BriefingGenerateRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    incident = fetch_incident(db, incident_id)
    message, references = build_audience_briefing(db, incident, payload.audience)
    session = None
    if payload.speak:
        if not payload.voice_session_id:
            raise HTTPException(422, "voice_session_id is required when speak is true")
        session = db.get(VoiceSession, payload.voice_session_id)
        if not session or session.incident_id != incident_id or session.status != VoiceSessionStatus.active:
            raise HTTPException(409, "The selected Agora voice session is not active")
        try:
            await voice_service.say(session.id, message)
        except Exception as exc:
            raise HTTPException(502, f"Agora could not deliver the briefing: {exc}") from exc
    briefing = BriefingRecord(incident_id=incident_id, audience=payload.audience, message=message, source_references=references, spoken=payload.speak, voice_session_id=session.id if session else None, created_by=user.user_id)
    db.add(briefing)
    db.commit()
    db.refresh(briefing)
    BRIEFINGS.labels(payload.audience.value, str(payload.speak).lower()).inc()
    event = add_timeline_event(db, incident_id, "briefing.spoken" if payload.speak else "briefing.generated", f"{payload.audience.value.title()} briefing {'spoken' if payload.speak else 'generated'}.", user.user_id, {"briefing_id": briefing.id, "audience": payload.audience.value, "voice_session_id": briefing.voice_session_id})
    await hub.publish(incident_id, "briefing.created", {"id": briefing.id, "audience": payload.audience.value, "spoken": briefing.spoken})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return briefing


@app.get("/api/incidents/{incident_id}/briefings", response_model=list[BriefingRead])
def list_briefings(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(BriefingRecord).where(BriefingRecord.incident_id == incident_id).order_by(BriefingRecord.created_at.desc())))


@app.post("/api/incidents/{incident_id}/recovery/checks", response_model=RecoveryCheckRead, status_code=201)
async def create_recovery_check(
    incident_id: str,
    payload: RecoveryCheckCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    fetch_incident(db, incident_id)
    existing = db.scalar(select(RecoveryCheck).where(RecoveryCheck.incident_id == incident_id, RecoveryCheck.criterion == payload.criterion))
    if existing:
        raise HTTPException(409, "This recovery criterion already exists")
    if payload.status == RecoveryCheckStatus.passed and not payload.evidence_ids:
        raise HTTPException(422, "A passed recovery check requires supporting evidence")
    validate_evidence_references(db, incident_id, payload.evidence_ids)
    check = RecoveryCheck(incident_id=incident_id, checked_by=user.user_id if payload.status != RecoveryCheckStatus.pending else None, **payload.model_dump())
    db.add(check)
    db.commit()
    db.refresh(check)
    event = add_timeline_event(db, incident_id, "recovery.check_created", f"Recovery criterion {check.status.value}: {check.criterion}", user.user_id, {"recovery_check_id": check.id, "evidence_ids": check.evidence_ids})
    await hub.publish(incident_id, "recovery.check", {"id": check.id, "criterion": check.criterion, "status": check.status.value})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return check


@app.patch("/api/incidents/{incident_id}/recovery/checks/{check_id}", response_model=RecoveryCheckRead)
async def update_recovery_check(
    incident_id: str,
    check_id: str,
    payload: RecoveryCheckUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    fetch_incident(db, incident_id)
    check = db.get(RecoveryCheck, check_id)
    if not check or check.incident_id != incident_id:
        raise HTTPException(404, "Recovery check not found")
    if payload.status == RecoveryCheckStatus.passed and not payload.evidence_ids:
        raise HTTPException(422, "A passed recovery check requires supporting evidence")
    validate_evidence_references(db, incident_id, payload.evidence_ids)
    check.status = payload.status
    check.observation = payload.observation
    check.evidence_ids = payload.evidence_ids
    check.checked_by = user.user_id
    db.commit()
    db.refresh(check)
    event = add_timeline_event(db, incident_id, "recovery.check_updated", f"Recovery criterion {check.status.value}: {check.criterion}", user.user_id, {"recovery_check_id": check.id, "evidence_ids": check.evidence_ids})
    await hub.publish(incident_id, "recovery.check", {"id": check.id, "criterion": check.criterion, "status": check.status.value})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return check


@app.get("/api/incidents/{incident_id}/recovery/checks", response_model=list[RecoveryCheckRead])
def list_recovery_checks(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(RecoveryCheck).where(RecoveryCheck.incident_id == incident_id).order_by(RecoveryCheck.created_at)))


@app.get("/api/incidents/{incident_id}/recovery/readiness", response_model=RecoveryReadinessRead)
def get_recovery_readiness(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    incident = fetch_incident(db, incident_id)
    return incident_snapshot(db, incident)["recovery"]


@app.post("/api/incidents/{incident_id}/resolve", response_model=IncidentRead)
async def resolve_incident(
    incident_id: str,
    payload: ResolveIncidentRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "admin")),
):
    try:
        async with coordination.lock(f"resolution:{incident_id}", ttl_seconds=120):
            incident = fetch_incident(db, incident_id)
            if incident.status == IncidentStatus.resolved:
                raise HTTPException(409, "Incident is already resolved")
            readiness = incident_snapshot(db, incident)["recovery"]
            if not payload.confirm_recovery:
                raise HTTPException(422, "Explicit human recovery confirmation is required")
            if not readiness["ready"]:
                raise HTTPException(409, {"message": "Recovery criteria are not satisfied", "blockers": readiness["blockers"]})
            incident.status = IncidentStatus.resolved
            db.commit()
            db.refresh(incident)
    except CoordinationBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    except CoordinationUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    event = add_timeline_event(db, incident_id, "incident.resolved", f"Recovery confirmed by {user.user_id}: {payload.resolution_note}", user.user_id, {"human_confirmed": True, "resolution_note": payload.resolution_note})
    content = build_report(db, incident)
    content["resolution_note"] = payload.resolution_note
    postmortem_content = dict(content)
    postmortem_content["review_prompts"] = ["What accelerated detection?", "Which handoffs introduced delay?", "Which controls or runbooks should change?", "What follow-up owners and deadlines are required?"]
    reports = [
        IncidentReport(incident_id=incident_id, report_type=IncidentReportType.final_summary, title=f"Final incident summary — {incident.title}", content=content, generated_by="orbit"),
        IncidentReport(incident_id=incident_id, report_type=IncidentReportType.postmortem, title=f"Postmortem draft — {incident.title}", content=postmortem_content, generated_by="orbit"),
    ]
    db.add_all(reports)
    memory = db.scalar(select(IncidentMemory).where(IncidentMemory.incident_id == incident_id))
    searchable = " ".join([incident.title, incident.service, payload.resolution_note, *content["confirmed_facts"]])
    if memory:
        memory.summary = f"{incident.title}: {payload.resolution_note}"
        memory.searchable_text = searchable
        memory.resolution = payload.resolution_note
        memory.unresolved_risks = content["unresolved_risks"]
        memory.embedding = text_embedding(searchable)
    else:
        memory = IncidentMemory(incident_id=incident_id, summary=f"{incident.title}: {payload.resolution_note}", searchable_text=searchable, services=[incident.service], symptoms=content["confirmed_facts"], resolution=payload.resolution_note, unresolved_risks=content["unresolved_risks"], embedding=text_embedding(searchable))
        db.add(memory)
    db.commit()
    RECOVERIES.inc()
    REPORTS.labels(IncidentReportType.final_summary.value, IncidentReportStatus.draft.value).inc()
    REPORTS.labels(IncidentReportType.postmortem.value, IncidentReportStatus.draft.value).inc()
    await hub.publish(incident_id, "incident.resolved", {"id": incident.id, "confirmed_by": user.user_id, "report_ids": [item.id for item in reports]})
    await hub.publish(incident_id, "timeline.created", {"id": event.id, "summary": event.summary})
    return incident


@app.get("/api/incidents/{incident_id}/decision-audit")
def get_decision_audit(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    incident = fetch_incident(db, incident_id)
    return decision_audit(db, incident)


@app.get("/api/incidents/{incident_id}/decision-audit/export")
def export_decision_audit(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    incident = fetch_incident(db, incident_id)
    document = {"exported_at": datetime.now(timezone.utc), "incident": {"id": incident.id, "title": incident.title, "service": incident.service, "severity": incident.severity, "status": incident.status.value}, "audit": decision_audit(db, incident)}
    return JSONResponse(content=jsonable_encoder(document), headers={"Content-Disposition": f'attachment; filename="orbit-audit-{incident.id}.json"'})


@app.get("/api/incidents/{incident_id}/replay", response_model=list[ReplayEventRead])
def get_incident_replay(incident_id: str, limit: int = 1000, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    bounded_limit = min(max(limit, 1), 5000)
    rows = list(db.scalars(select(TimelineEvent).where(TimelineEvent.incident_id == incident_id).order_by(TimelineEvent.created_at).limit(bounded_limit)))
    events = [{"id": item.id, "event_type": item.event_type, "summary": item.summary, "actor_id": item.actor_id, "payload": item.payload, "created_at": item.created_at} for item in rows]
    return replay_events(events)


@app.get("/api/incidents/{incident_id}/analytics")
def get_incident_analytics(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    incident = fetch_incident(db, incident_id)
    return incident_snapshot(db, incident)["analytics"]


@app.post("/api/incidents/{incident_id}/reports", response_model=IncidentReportRead, status_code=201)
def generate_incident_report(
    incident_id: str,
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "operator", "admin")),
):
    incident = fetch_incident(db, incident_id)
    content = build_report(db, incident)
    if payload.report_type == IncidentReportType.postmortem:
        content["review_prompts"] = ["What accelerated detection?", "Which handoffs introduced delay?", "Which controls or runbooks should change?", "What follow-up owners and deadlines are required?"]
    label = "Final incident summary" if payload.report_type == IncidentReportType.final_summary else "Postmortem draft"
    report = IncidentReport(incident_id=incident_id, report_type=payload.report_type, title=f"{label} — {incident.title}", content=content, generated_by=user.user_id)
    db.add(report)
    db.commit()
    db.refresh(report)
    REPORTS.labels(report.report_type.value, report.status.value).inc()
    return report


@app.get("/api/incidents/{incident_id}/reports", response_model=list[IncidentReportRead])
def list_incident_reports(incident_id: str, db: Session = Depends(get_db), _: CurrentUser = Depends(current_user)):
    fetch_incident(db, incident_id)
    return list(db.scalars(select(IncidentReport).where(IncidentReport.incident_id == incident_id).order_by(IncidentReport.created_at.desc())))


@app.post("/api/incidents/{incident_id}/reports/{report_id}/finalize", response_model=IncidentReportRead)
def finalize_incident_report(
    incident_id: str,
    report_id: str,
    payload: ReportFinalizeRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("commander", "admin")),
):
    fetch_incident(db, incident_id)
    report = db.get(IncidentReport, report_id)
    if not report or report.incident_id != incident_id:
        raise HTTPException(404, "Incident report not found")
    if not payload.confirm:
        raise HTTPException(422, "Explicit human confirmation is required to finalize a report")
    if report.status == IncidentReportStatus.final:
        raise HTTPException(409, "Incident report is already final")
    report.status = IncidentReportStatus.final
    report.finalized_by = user.user_id
    db.commit()
    db.refresh(report)
    REPORTS.labels(report.report_type.value, report.status.value).inc()
    add_timeline_event(db, incident_id, "report.finalized", f"{report.report_type.value} finalized by {user.user_id}.", user.user_id, {"report_id": report.id})
    return report


@app.post("/api/admin/retention/run")
def run_retention(
    payload: RetentionRunRequest,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_roles("admin")),
):
    return apply_retention(db, settings.retention_days, payload.confirm)


@app.post("/api/admin/jobs", status_code=202)
async def enqueue_admin_job(
    payload: AdminJobRequest,
    user: CurrentUser = Depends(require_roles("admin")),
):
    job_payload = dict(payload.payload)
    if payload.kind == "retention_cleanup":
        job_payload.setdefault("retention_days", settings.retention_days)
        job_payload.setdefault("confirm", False)
    try:
        job = await job_queue.enqueue(payload.kind, job_payload, user.user_id)
    except Exception as exc:
        raise HTTPException(503, "Job queue is unavailable") from exc
    return {"id": job.id, "kind": job.kind, "status": "queued"}


@app.get("/api/admin/jobs/dead-letter")
async def list_dead_letter_jobs(
    limit: int = 50,
    _: CurrentUser = Depends(require_roles("admin")),
):
    try:
        client = await job_queue.redis()
        rows = await client.xrevrange("orbit:jobs:dead-letter", count=min(max(limit, 1), 200))
    except Exception as exc:
        raise HTTPException(503, "Job queue is unavailable") from exc
    return [{"stream_id": stream_id, **fields} for stream_id, fields in rows]


@app.get("/api/operations/reliability")
async def delivery_reliability(
    _: CurrentUser = Depends(require_roles("commander", "admin")),
):
    """Safe queue health summary; job payloads and errors remain admin-only."""
    try:
        client = await job_queue.redis()
        dead_letter_count, retry_count, queued_count = await asyncio.gather(
            client.xlen("orbit:jobs:dead-letter"),
            client.zcard("orbit:jobs:retry"),
            client.xlen("orbit:jobs"),
        )
    except Exception as exc:
        raise HTTPException(503, "Job queue is unavailable") from exc
    return {
        "status": "attention" if dead_letter_count else "healthy",
        "dead_letter_count": dead_letter_count,
        "retry_scheduled_count": retry_count,
        "queued_count": queued_count,
    }


@app.websocket("/ws/incidents/{incident_id}")
async def incident_updates(websocket: WebSocket, incident_id: str, token: str = Query(...), db: Session = Depends(get_db)):
    try:
        decode_access_token(token)
    except HTTPException as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed") from exc
    if not db.get(Incident, incident_id):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Incident not found")
    await hub.connect(incident_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(incident_id, websocket)
