from datetime import datetime
from pydantic import BaseModel, Field
from .models import (ActionStatus, AgentName, AnalysisKind, ApprovalStatus, ArtifactType,
                     BriefingAudience, EvidenceClassification, FindingType, GraphNodeType,
                     GraphRelation, IncidentReportStatus, IncidentReportType, IncidentStatus,
                     IntegrationProvider, RecoveryCheckStatus, RiskLevel, ToolExecutionStatus,
                     VoiceSessionStatus)


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    service: str
    severity: str = Field(pattern="^SEV[1-4]$")
    commander_id: str
    customer_impact: str | None = None
    affected_regions: list[str] = Field(default_factory=list)
    recovery_criteria: str | None = None


class IncidentRead(IncidentCreate):
    id: str
    status: IncidentStatus
    created_at: datetime
    model_config = {"from_attributes": True}


class TemplateIncidentCreate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    affected_regions: list[str] = Field(default_factory=list)


class GrafanaAlertWebhook(BaseModel):
    status: str = ""
    alerts: list[dict] = Field(default_factory=list)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)


class EvidenceCreate(BaseModel):
    claim: str = Field(min_length=3)
    classification: EvidenceClassification
    confidence: int = Field(ge=0, le=100)
    source: str


class EvidenceRead(EvidenceCreate):
    id: str
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ActionCreate(BaseModel):
    task: str = Field(min_length=3)
    owner_id: str
    due_at: datetime | None = None


class ActionRead(ActionCreate):
    id: str
    status: ActionStatus
    escalation_level: int
    last_escalated_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ActionUpdate(BaseModel):
    status: ActionStatus | None = None
    owner_id: str | None = Field(default=None, min_length=1, max_length=120)
    due_at: datetime | None = None


class EscalationRunRequest(BaseModel):
    thresholds_minutes: list[int] = Field(default_factory=lambda: [1, 15, 30], min_length=1, max_length=6)


class EscalationResult(BaseModel):
    evaluated: int
    escalated_action_ids: list[str]


class ApprovalCreate(BaseModel):
    action: str = Field(min_length=3)
    rationale: str = Field(min_length=3)


class ApprovalDecision(BaseModel):
    status: ApprovalStatus
    decided_by: str | None = None


class ApprovalRead(ApprovalCreate):
    id: str
    status: ApprovalStatus
    decided_by: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class TimelineRead(BaseModel):
    id: str
    incident_id: str
    event_type: str
    summary: str
    actor_id: str | None
    payload: dict
    created_at: datetime
    model_config = {"from_attributes": True}


class ParticipantCreate(BaseModel):
    agora_uid: str
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=2, max_length=80)
    language: str = "en-US"


class ParticipantRead(ParticipantCreate):
    id: str
    joined_at: datetime
    model_config = {"from_attributes": True}


class VoiceSessionCreate(BaseModel):
    channel: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    remote_uids: list[str] = Field(default_factory=list)
    language: str = "en-US"


class RtcTokenRequest(BaseModel):
    channel: str | None = Field(default=None, min_length=3, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")


class RtcTokenRead(BaseModel):
    app_id: str
    channel: str
    uid: int
    token: str
    expires_in_seconds: int


class VoiceSessionRead(BaseModel):
    id: str
    incident_id: str
    channel: str
    agora_agent_session_id: str | None
    agent_uid: str
    language: str
    status: VoiceSessionStatus
    started_at: datetime
    stopped_at: datetime | None
    model_config = {"from_attributes": True}


class TranscriptCreate(BaseModel):
    voice_session_id: str | None = None
    participant_id: str | None = None
    speaker_name: str
    speaker_role: str
    text: str = Field(min_length=1)
    language: str = "en-US"
    is_final: bool = True


class TranscriptRead(TranscriptCreate):
    id: str
    incident_id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class FindingRead(BaseModel):
    id: str
    incident_id: str
    finding_type: FindingType
    title: str
    description: str
    severity: str
    status: str
    related_evidence_ids: list[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class SpokenBriefingRequest(BaseModel):
    message: str = Field(min_length=3, max_length=1200)


class ToolExecutionPrepare(BaseModel):
    provider: IntegrationProvider
    operation: str = Field(min_length=2, max_length=80)
    risk_level: RiskLevel = RiskLevel.medium
    payload: dict
    rationale: str = Field(min_length=3, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=160)


class ToolExecutionRead(BaseModel):
    id: str
    incident_id: str
    provider: IntegrationProvider
    operation: str
    risk_level: RiskLevel
    status: ToolExecutionStatus
    requested_by: str
    idempotency_key: str
    request_payload: dict
    response_payload: dict
    approval_id: str | None
    external_id: str | None
    error_message: str | None
    created_at: datetime
    executed_at: datetime | None
    model_config = {"from_attributes": True}


class IntegrationStatus(BaseModel):
    provider: IntegrationProvider
    configured: bool
    supported_operations: list[str]


class CommandCenterRead(BaseModel):
    incident: dict
    evidence: list[dict]
    actions: list[dict]
    unknowns: list[dict]
    checks: list[dict]
    timeline: list[dict]
    decisions: list[dict]
    approvals: list[dict]
    tools: list[dict]
    recovery: dict
    analytics: dict
    live_room: dict
    intelligence: dict
    communications: dict
    reports: list[dict]
    prediction_engine: dict
    telemetry_engine: dict
    learning_engine: dict
    certification_engine: dict
    guardrails: dict
    sync: dict
    integrations: list[IntegrationStatus]
    agora_configured: bool


class EvidenceArtifactCreate(BaseModel):
    artifact_type: ArtifactType
    title: str = Field(min_length=3, max_length=200)
    mime_type: str = Field(min_length=3, max_length=120)
    storage_uri: str | None = None
    extracted_text: str | None = Field(default=None, max_length=200_000)
    content_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    source_name: str = Field(min_length=2, max_length=200)
    source_uri: str | None = None
    observed_at: datetime | None = None
    artifact_metadata: dict = Field(default_factory=dict)


class EvidenceArtifactRead(EvidenceArtifactCreate):
    id: str
    incident_id: str
    captured_by: str
    analysis_status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class KnowledgeNodeRead(BaseModel):
    id: str
    incident_id: str
    node_type: GraphNodeType
    label: str
    normalized_key: str
    properties: dict
    confidence: int
    source_evidence_ids: list[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class KnowledgeEdgeRead(BaseModel):
    id: str
    incident_id: str
    source_node_id: str
    target_node_id: str
    relation: GraphRelation
    confidence: int
    rationale: str
    evidence_ids: list[str]
    created_by_agent: AgentName
    created_at: datetime
    model_config = {"from_attributes": True}


class UnknownRead(BaseModel):
    id: str
    incident_id: str
    question: str
    normalized_key: str
    category: str
    priority: str
    status: str
    resolution_evidence_id: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class MetricObservation(BaseModel):
    name: str
    current: float
    baseline: float
    standard_deviation: float = Field(gt=0)
    service: str
    region: str | None = None
    observed_at: datetime | None = None


class InvestigationRunRequest(BaseModel):
    metrics: list[MetricObservation] = Field(default_factory=list, max_length=200)
    dependency_map: dict[str, list[str]] = Field(default_factory=dict)
    affected_services: list[str] = Field(default_factory=list)
    failure_rate_percent: float | None = Field(default=None, ge=0, le=100)
    estimated_customers_affected: int | None = Field(default=None, ge=0)
    critical_service: bool = False


class AnalysisRead(BaseModel):
    id: str
    incident_id: str
    kind: AnalysisKind
    summary: str
    confidence: int
    result: dict
    input_references: list[str]
    limitations: list[str]
    created_by_agent: AgentName
    created_at: datetime
    model_config = {"from_attributes": True}


class AgentRunRead(BaseModel):
    id: str
    incident_id: str
    agent_name: AgentName
    status: str
    input_references: list[str]
    output_references: list[str]
    latency_ms: float | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class InvestigationReport(BaseModel):
    agent_run_ids: list[str]
    graph_nodes_created: int
    graph_edges_created: int
    unknowns_open: int
    analyses: list[AnalysisRead]
    root_cause_confirmed: bool = False
    guardrail: str


class ForecastObservation(BaseModel):
    metric: str = Field(min_length=2, max_length=120)
    service: str = Field(min_length=2, max_length=120)
    region: str | None = Field(default=None, max_length=80)
    minute: float
    value: float
    baseline: float
    threshold: float
    higher_is_worse: bool = True


class GeoRegionInput(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    traffic_share: float = Field(ge=0, le=1)
    customers: int = Field(default=0, ge=0)
    services: list[str] = Field(default_factory=list)


class PredictionRunRequest(BaseModel):
    horizon_minutes: int = Field(default=30, ge=5, le=240)
    observations: list[ForecastObservation] = Field(default_factory=list, max_length=5000)
    dependency_map: dict[str, list[str]] = Field(default_factory=dict)
    regions: list[GeoRegionInput] = Field(default_factory=list, max_length=250)
    historical_incident_ids: list[str] = Field(default_factory=list, max_length=100)


class PredictionRunRead(BaseModel):
    id: str
    incident_id: str
    horizon_minutes: int
    model_version: str
    status: str
    input_snapshot: dict
    forecast: dict
    graphs: dict
    geospatial: dict
    provenance: list[str]
    limitations: list[str]
    created_by: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SimulationRunRequest(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    prediction_run_id: str | None = None
    iterations: int = Field(default=500, ge=100, le=5000)
    intervention: dict = Field(default_factory=dict)
    assumptions: dict = Field(default_factory=dict)


class SimulationRunRead(BaseModel):
    id: str
    incident_id: str
    prediction_run_id: str | None
    name: str
    iterations: int
    scenario: dict
    result: dict
    created_by: str
    created_at: datetime
    model_config = {"from_attributes": True}


class TelemetryPointCreate(BaseModel):
    metric: str = Field(min_length=2, max_length=120)
    service: str = Field(min_length=2, max_length=120)
    region: str | None = Field(default=None, max_length=80)
    observed_at: datetime
    value: float
    baseline: float
    threshold: float
    higher_is_worse: bool = True
    source_event_id: str = Field(min_length=1, max_length=200)
    labels: dict = Field(default_factory=dict)


class TelemetryBatchCreate(BaseModel):
    source: str = Field(min_length=2, max_length=120)
    observations: list[TelemetryPointCreate] = Field(min_length=1, max_length=5000)
    auto_forecast: bool = True
    forecast_horizon_minutes: int = Field(default=30, ge=5, le=240)
    dependency_map: dict[str, list[str]] = Field(default_factory=dict)
    region_catalog: list[GeoRegionInput] = Field(default_factory=list, max_length=250)


class TelemetryIngestResult(BaseModel):
    accepted: int
    duplicates: int
    early_warnings: list[dict]
    prediction_run_id: str | None = None


class ForecastEvaluationRead(BaseModel):
    id: str
    incident_id: str
    prediction_run_id: str
    outcome: dict
    calibration: dict
    drift: dict
    brier_score: float
    mean_absolute_error: float
    lead_time_minutes: float | None
    evaluated_by: str
    evaluated_at: datetime
    model_config = {"from_attributes": True}


class CalibrationRead(BaseModel):
    evaluation_count: int
    mean_brier_score: float
    mean_absolute_error: float
    mean_lead_time_minutes: float | None
    reliability_buckets: list[dict]
    drift_status: str


class ProductionLearningRead(BaseModel):
    evaluation_count: int
    alert_quality: dict
    collector: dict
    recent_runs: list[dict]
    learned_prior: dict | None = None


class LearningCycleRequest(BaseModel):
    incident_id: str | None = None
    collect_telemetry: bool = True
    evaluate_mature_forecasts: bool = True


class CertificationStartRequest(BaseModel):
    environment: str = Field(default="staging", pattern=r"^(staging|preproduction)$")
    notes: list[str] = Field(default_factory=list, max_length=20)


class CertificationMeasurementCreate(BaseModel):
    metric: str = Field(pattern=r"^(voice_join_latency_ms|transcript_to_state_ms|spoken_summary_latency_ms|websocket_delivery_ms|api_p95_latency_ms|http_error_rate_percent|root_cause_guardrail_violations|unapproved_critical_actions|backup_restore_pass|failure_recovery_pass)$")
    value: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=30)
    source: str = Field(min_length=2, max_length=120)
    evidence_reference: str | None = Field(default=None, max_length=1000)


class CertificationRunRead(BaseModel):
    id: str
    incident_id: str
    environment: str
    status: str
    checklist: dict
    performance: dict
    promotion_gates: dict
    notes: list[str]
    started_by: str
    certified_by: str | None
    started_at: datetime
    evaluated_at: datetime | None
    certified_at: datetime | None
    model_config = {"from_attributes": True}


class CertificationEvidencePackRead(BaseModel):
    certification_run_id: str
    incident_id: str
    environment: str
    status: str
    promotion_allowed: bool
    human_approval_required: bool
    blocked_gates: list[dict]
    measurements: list[dict]
    manual_next_steps: list[str]


class RunbookCreate(BaseModel):
    service: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    content: str = Field(min_length=10)
    tags: list[str] = Field(default_factory=list)
    source_uri: str | None = None
    version: str = "1.0"


class RunbookRead(RunbookCreate):
    id: str
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class MemoryIndexRequest(BaseModel):
    summary: str = Field(min_length=10)
    symptoms: list[str] = Field(default_factory=list)
    resolution: str | None = None
    root_cause_status: str = Field(default="unconfirmed", pattern=r"^(unconfirmed|confirmed_by_human)$")
    root_cause: str | None = None
    unresolved_risks: list[str] = Field(default_factory=list)


class SimilarIncidentRead(BaseModel):
    incident_id: str
    similarity: float
    summary: str
    resolution: str | None
    root_cause_status: str


class BriefingGenerateRequest(BaseModel):
    audience: BriefingAudience
    speak: bool = False
    voice_session_id: str | None = None


class BriefingRead(BaseModel):
    id: str
    incident_id: str
    audience: BriefingAudience
    message: str
    source_references: list[str]
    spoken: bool
    voice_session_id: str | None
    created_by: str
    created_at: datetime
    model_config = {"from_attributes": True}


class RecoveryCheckCreate(BaseModel):
    criterion: str = Field(min_length=3, max_length=500)
    status: RecoveryCheckStatus = RecoveryCheckStatus.pending
    observation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    automated: bool = False


class RecoveryCheckUpdate(BaseModel):
    status: RecoveryCheckStatus
    observation: str = Field(min_length=3)
    evidence_ids: list[str] = Field(default_factory=list)


class RecoveryCheckRead(BaseModel):
    id: str
    incident_id: str
    criterion: str
    status: RecoveryCheckStatus
    observation: str | None
    evidence_ids: list[str]
    checked_by: str | None
    automated: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class RecoveryReadinessRead(BaseModel):
    ready: bool
    checks_total: int
    checks_passed: int
    blockers: list[str]
    requires_human_confirmation: bool


class ResolveIncidentRequest(BaseModel):
    confirm_recovery: bool
    resolution_note: str = Field(min_length=10)


class ReportGenerateRequest(BaseModel):
    report_type: IncidentReportType


class ReportFinalizeRequest(BaseModel):
    confirm: bool


class IncidentReportRead(BaseModel):
    id: str
    incident_id: str
    report_type: IncidentReportType
    status: IncidentReportStatus
    title: str
    content: dict
    generated_by: str
    finalized_by: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ReplayEventRead(BaseModel):
    sequence: int
    offset_seconds: float
    id: str
    event_type: str
    summary: str
    actor_id: str | None
    payload: dict
    created_at: datetime


class RetentionRunRequest(BaseModel):
    confirm: bool = False


class AdminJobRequest(BaseModel):
    kind: str = Field(pattern=r"^(retention_cleanup)$")
    payload: dict = Field(default_factory=dict)
