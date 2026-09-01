import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import VECTOR
from .database import Base
from .encrypted import EncryptedText


class IncidentStatus(str, enum.Enum):
    declared = "declared"
    investigating = "investigating"
    mitigating = "mitigating"
    monitoring = "monitoring"
    resolved = "resolved"


class EvidenceClassification(str, enum.Enum):
    confirmed_fact = "confirmed_fact"
    hypothesis = "hypothesis"
    decision = "decision"
    action = "action"


class ActionStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    complete = "complete"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class VoiceSessionStatus(str, enum.Enum):
    starting = "starting"
    active = "active"
    stopped = "stopped"
    failed = "failed"


class FindingType(str, enum.Enum):
    contradiction = "contradiction"
    missing_information = "missing_information"


class IntegrationProvider(str, enum.Enum):
    slack = "slack"
    jira = "jira"
    pagerduty = "pagerduty"
    monitoring = "monitoring"


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ToolExecutionStatus(str, enum.Enum):
    prepared = "prepared"
    awaiting_approval = "awaiting_approval"
    executing = "executing"
    succeeded = "succeeded"
    failed = "failed"
    rejected = "rejected"


class ArtifactType(str, enum.Enum):
    log = "log"
    screenshot = "screenshot"
    chart = "chart"
    metric = "metric"
    document = "document"


class GraphNodeType(str, enum.Enum):
    evidence = "evidence"
    service = "service"
    component = "component"
    region = "region"
    symptom = "symptom"
    hypothesis = "hypothesis"
    decision = "decision"
    action = "action"


class GraphRelation(str, enum.Enum):
    supports = "supports"
    contradicts = "contradicts"
    affects = "affects"
    observed_in = "observed_in"
    derived_from = "derived_from"
    related_to = "related_to"


class AnalysisKind(str, enum.Enum):
    anomaly_correlation = "anomaly_correlation"
    blast_radius = "blast_radius"
    severity_prediction = "severity_prediction"
    similar_incident = "similar_incident"
    runbook_recommendation = "runbook_recommendation"
    multimodal_evidence = "multimodal_evidence"


class AgentName(str, enum.Enum):
    commander = "commander"
    listener = "listener"
    evidence = "evidence"
    conflict = "conflict"
    timeline = "timeline"
    action = "action"
    investigation = "investigation"
    integration = "integration"


class BriefingAudience(str, enum.Enum):
    commander = "commander"
    engineering = "engineering"
    support = "support"
    executive = "executive"


class RecoveryCheckStatus(str, enum.Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"


class IncidentReportType(str, enum.Enum):
    final_summary = "final_summary"
    postmortem = "postmortem"


class IncidentReportStatus(str, enum.Enum):
    draft = "draft"
    final = "final"


def id_column() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = id_column()
    title: Mapped[str] = mapped_column(String(200))
    service: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus), default=IncidentStatus.declared)
    commander_id: Mapped[str] = mapped_column(String(120))
    customer_impact: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    affected_regions: Mapped[list] = mapped_column(JSON, default=list)
    recovery_criteria: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    claim: Mapped[str] = mapped_column(EncryptedText())
    classification: Mapped[EvidenceClassification] = mapped_column(Enum(EvidenceClassification))
    confidence: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActionItem(Base):
    __tablename__ = "action_items"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    task: Mapped[str] = mapped_column(EncryptedText())
    owner_id: Mapped[str] = mapped_column(String(120))
    status: Mapped[ActionStatus] = mapped_column(Enum(ActionStatus), default=ActionStatus.open)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    action: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.pending)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    agora_uid: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(20), default="en-US")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VoiceSession(Base):
    __tablename__ = "voice_sessions"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    channel: Mapped[str] = mapped_column(String(120), unique=True)
    agora_agent_session_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    agent_uid: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(20), default="en-US")
    status: Mapped[VoiceSessionStatus] = mapped_column(Enum(VoiceSessionStatus), default=VoiceSessionStatus.starting)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    voice_session_id: Mapped[str | None] = mapped_column(ForeignKey("voice_sessions.id"), nullable=True, index=True)
    participant_id: Mapped[str | None] = mapped_column(ForeignKey("participants.id"), nullable=True)
    speaker_name: Mapped[str] = mapped_column(String(120))
    speaker_role: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(EncryptedText())
    language: Mapped[str] = mapped_column(String(20), default="en-US")
    is_final: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntelligenceFinding(Base):
    __tablename__ = "intelligence_findings"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    finding_type: Mapped[FindingType] = mapped_column(Enum(FindingType))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open")
    related_evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    provider: Mapped[IntegrationProvider] = mapped_column(Enum(IntegrationProvider))
    operation: Mapped[str] = mapped_column(String(80))
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    status: Mapped[ToolExecutionStatus] = mapped_column(Enum(ToolExecutionStatus), default=ToolExecutionStatus.prepared)
    requested_by: Mapped[str] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("approval_requests.id"), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvidenceArtifact(Base):
    __tablename__ = "evidence_artifacts"
    __table_args__ = (UniqueConstraint("incident_id", "content_sha256", name="uq_artifact_incident_checksum"),)
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    artifact_type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType))
    title: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(120))
    storage_uri: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_name: Mapped[str] = mapped_column(String(200))
    source_uri: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    captured_by: Mapped[str] = mapped_column(String(120))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    artifact_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"
    __table_args__ = (UniqueConstraint("incident_id", "normalized_key", name="uq_knowledge_node_incident_key"),)
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    node_type: Mapped[GraphNodeType] = mapped_column(Enum(GraphNodeType))
    label: Mapped[str] = mapped_column(String(240))
    normalized_key: Mapped[str] = mapped_column(String(260), index=True)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[int] = mapped_column(Integer, default=50)
    source_evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"
    __table_args__ = (UniqueConstraint("incident_id", "source_node_id", "target_node_id", "relation", name="uq_knowledge_edge_relation"),)
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"), index=True)
    target_node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"), index=True)
    relation: Mapped[GraphRelation] = mapped_column(Enum(GraphRelation))
    confidence: Mapped[int] = mapped_column(Integer, default=50)
    rationale: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_by_agent: Mapped[AgentName] = mapped_column(Enum(AgentName), default=AgentName.evidence)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UnknownItem(Base):
    __tablename__ = "unknown_items"
    __table_args__ = (UniqueConstraint("incident_id", "normalized_key", name="uq_unknown_incident_key"),)
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    normalized_key: Mapped[str] = mapped_column(String(260), index=True)
    category: Mapped[str] = mapped_column(String(80))
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open")
    resolution_evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_items.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Runbook(Base):
    __tablename__ = "runbooks"
    id: Mapped[str] = id_column()
    service: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(40), default="1.0")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IncidentMemory(Base):
    __tablename__ = "incident_memories"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text)
    searchable_text: Mapped[str] = mapped_column(Text)
    services: Mapped[list] = mapped_column(JSON, default=list)
    symptoms: Mapped[list] = mapped_column(JSON, default=list)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_status: Mapped[str] = mapped_column(String(30), default="unconfirmed")
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    unresolved_risks: Mapped[list] = mapped_column(JSON, default=list)
    embedding: Mapped[list] = mapped_column(JSON().with_variant(VECTOR(96), "postgresql"), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    kind: Mapped[AnalysisKind] = mapped_column(Enum(AnalysisKind))
    summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    input_references: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    created_by_agent: Mapped[AgentName] = mapped_column(Enum(AgentName), default=AgentName.investigation)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    agent_name: Mapped[AgentName] = mapped_column(Enum(AgentName))
    status: Mapped[str] = mapped_column(String(30), default="running")
    input_references: Mapped[list] = mapped_column(JSON, default=list)
    output_references: Mapped[list] = mapped_column(JSON, default=list)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BriefingRecord(Base):
    __tablename__ = "briefing_records"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    audience: Mapped[BriefingAudience] = mapped_column(Enum(BriefingAudience))
    message: Mapped[str] = mapped_column(Text)
    source_references: Mapped[list] = mapped_column(JSON, default=list)
    spoken: Mapped[bool] = mapped_column(Boolean, default=False)
    voice_session_id: Mapped[str | None] = mapped_column(ForeignKey("voice_sessions.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecoveryCheck(Base):
    __tablename__ = "recovery_checks"
    __table_args__ = (UniqueConstraint("incident_id", "criterion", name="uq_recovery_check_incident_criterion"),)
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    criterion: Mapped[str] = mapped_column(String(500))
    status: Mapped[RecoveryCheckStatus] = mapped_column(Enum(RecoveryCheckStatus), default=RecoveryCheckStatus.pending)
    observation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    checked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    automated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IncidentReport(Base):
    __tablename__ = "incident_reports"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    report_type: Mapped[IncidentReportType] = mapped_column(Enum(IncidentReportType))
    status: Mapped[IncidentReportStatus] = mapped_column(Enum(IncidentReportStatus), default=IncidentReportStatus.draft)
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_by: Mapped[str] = mapped_column(String(120), default="orbit")
    finalized_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PredictionRun(Base):
    __tablename__ = "prediction_runs"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    horizon_minutes: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(40), default="orbit-forecast-v1")
    status: Mapped[str] = mapped_column(String(30), default="completed")
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    forecast: Mapped[dict] = mapped_column(JSON, default=dict)
    graphs: Mapped[dict] = mapped_column(JSON, default=dict)
    geospatial: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    prediction_run_id: Mapped[str | None] = mapped_column(ForeignKey("prediction_runs.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    iterations: Mapped[int] = mapped_column(Integer, default=500)
    scenario: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TelemetryObservation(Base):
    __tablename__ = "telemetry_observations"
    __table_args__ = (UniqueConstraint("incident_id", "source", "source_event_id", name="uq_telemetry_incident_source_event"),)
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    metric: Mapped[str] = mapped_column(String(120), index=True)
    service: Mapped[str] = mapped_column(String(120), index=True)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[float] = mapped_column(Float)
    baseline: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    higher_is_worse: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(120))
    source_event_id: Mapped[str] = mapped_column(String(200))
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ForecastEvaluation(Base):
    __tablename__ = "forecast_evaluations"
    __table_args__ = (UniqueConstraint("prediction_run_id", name="uq_forecast_evaluation_prediction"),)
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    prediction_run_id: Mapped[str] = mapped_column(ForeignKey("prediction_runs.id"), index=True)
    outcome: Mapped[dict] = mapped_column(JSON, default=dict)
    calibration: Mapped[dict] = mapped_column(JSON, default=dict)
    drift: Mapped[dict] = mapped_column(JSON, default=dict)
    brier_score: Mapped[float] = mapped_column(Float)
    mean_absolute_error: Mapped[float] = mapped_column(Float)
    lead_time_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluated_by: Mapped[str] = mapped_column(String(120))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductionLearningRun(Base):
    __tablename__ = "production_learning_runs"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), nullable=True, index=True)
    run_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="completed")
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="orbit-scheduler")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CertificationRun(Base):
    __tablename__ = "certification_runs"
    id: Mapped[str] = id_column()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    environment: Mapped[str] = mapped_column(String(40), default="staging")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    performance: Mapped[dict] = mapped_column(JSON, default=dict)
    promotion_gates: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[list] = mapped_column(JSON, default=list)
    started_by: Mapped[str] = mapped_column(String(120))
    certified_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CertificationMeasurement(Base):
    __tablename__ = "certification_measurements"
    id: Mapped[str] = id_column()
    certification_run_id: Mapped[str] = mapped_column(ForeignKey("certification_runs.id"), index=True)
    metric: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(120))
    evidence_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(120))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
