export type Incident = {
  id: string;
  title: string;
  service: string;
  severity: string;
  status: string;
  commander_id: string;
  customer_impact?: string | null;
  affected_regions: string[];
  recovery_criteria?: string | null;
  created_at: string;
};

export type Evidence = { id: string; claim: string; classification: string; confidence: number; source: string; created_at: string };
export type RecoveryCheck = { id: string; incident_id: string; criterion: string; status: "pending" | "passed" | "failed"; observation?: string | null; evidence_ids: string[]; checked_by?: string | null; automated: boolean; created_at: string; updated_at: string };
export type ActionItem = { id: string; task: string; owner_id: string; status: string; due_at?: string | null; escalation_level: number; overdue: boolean };
export type TimelineEvent = { id: string; event_type: string; summary: string; actor_id?: string | null; payload: Record<string, unknown>; created_at: string };
export type Participant = { id: string; agora_uid: string; display_name: string; role: string; language: string; joined_at: string };
export type Integration = { provider: string; configured: boolean; supported_operations: string[] };

export type CommandCenterSnapshot = {
  incident: Incident;
  evidence: Evidence[];
  actions: ActionItem[];
  unknowns: Array<{ id: string; question: string; priority: string; status: string }>;
  checks: Array<{ id: string; criterion: string; status: string; observation?: string | null; evidence_ids: string[] }>;
  timeline: TimelineEvent[];
  decisions: Evidence[];
  approvals: Array<{ id: string; action: string; status: string; decided_by?: string | null; created_at: string }>;
  tools: Array<{ id: string; provider: string; operation: string; status: string; approval_id?: string | null; external_id?: string | null }>;
  recovery: { ready: boolean; checks_total: number; checks_passed: number; blockers: string[]; requires_human_confirmation: boolean };
  analytics: Record<string, number | string | boolean | null>;
  live_room: {
    participants: Participant[];
    voice_sessions: Array<{ id: string; channel: string; language: string; status: string; started_at: string; stopped_at?: string | null }>;
    active: boolean;
    recent_transcripts: Array<{ id: string; speaker_name: string; speaker_role: string; text: string; language: string; created_at: string }>;
  };
  intelligence: {
    findings: Array<{ id: string; type: string; title: string; description: string; severity: string; status: string; related_evidence_ids: string[] }>;
    artifacts: Array<{ id: string; type: string; title: string; source_name: string; analysis_status: string }>;
    knowledge_graph: { nodes: number; edges: number; contradiction_edges: number };
    analyses: Array<{ id: string; kind: string; summary: string; confidence: number; limitations: string[] }>;
    agent_runs: Array<{ id: string; agent: string; status: string; latency_ms?: number | null }>;
  };
  communications: { briefings: Array<{ id: string; audience: string; message: string; source_references: string[]; spoken: boolean; created_at: string }> };
  reports: Array<{ id: string; type: string; status: string; title: string; created_at: string; updated_at: string }>;
  prediction_engine?: {
    latest: null | { id: string; horizon_minutes: number; forecast: { incident_escalation_probability?: number; risk_band?: string; metric_forecasts?: Array<{ metric: string; service: string; predicted: number; breach_probability: number; threshold_eta_minutes?: number | null; confidence: number }> }; graphs: Record<string, unknown>; geospatial: { regions?: Array<{ code: string; exposure_score: number; estimated_customers_at_risk: number }>; customers_at_risk?: number }; limitations: string[]; created_at: string };
    history_count: number;
    simulations: Array<{ id: string; name: string; iterations: number; result: { baseline_risk?: number; simulated_risk?: number; risk_reduction?: number; p90?: number }; created_at: string }>;
    advisory_only: true;
  };
  telemetry_engine?: {
    observation_count: number;
    recent: Array<{ metric: string; service: string; region?: string | null; observed_at: string; value: number; baseline: number; threshold: number; source: string }>;
    early_warnings: Array<{ metric: string; service: string; region?: string | null; score: number; velocity_per_minute: number; threshold_progress: number; threshold_eta_minutes?: number | null; reason: string }>;
    evaluations: Array<{ id: string; prediction_run_id: string; brier_score: number; mean_absolute_error: number; lead_time_minutes?: number | null; quality: string; drift: string; evaluated_at: string }>;
    calibration: { evaluation_count: number; mean_brier_score: number; mean_absolute_error: number; mean_lead_time_minutes?: number | null; reliability_buckets: Array<{ bucket: string; forecast_probability: number; observed_frequency: number; count: number }>; drift_status: string };
    automatic_forecasting: boolean;
  };
  learning_engine?: {
    evaluation_count: number;
    alert_quality: { sample_count: number; current: { precision: number; recall: number; false_positive_rate: number; false_negative_rate: number; threshold: number }; recommended_threshold: number; policy: string; minimum_samples: number };
    collector: { enabled: boolean; configured: boolean; interval_seconds: number; query_count: number };
    recent_runs: Array<{ id: string; run_type: string; status: string; started_at?: string | null }>;
    learned_prior?: null | { probability: number; confidence: number; method: string; incidents: Array<{ incident_id: string; evaluation_count: number; weight: number; learned_probability: number }> };
  };
  certification_engine?: {
    id?: string;
    environment?: string;
    status: string;
    checklist?: Record<string, { passed: boolean; required: string; evidence: Record<string, unknown> }>;
    performance?: Record<string, { passed: boolean; measured?: number | null; sample_count: number; minimum_samples: number }>;
    promotion_gates: { promotion_allowed: boolean; groups?: Record<string, boolean>; configuration?: Record<string, { passed: boolean; required: string }> };
    certified_by?: string | null;
  };
  guardrails: { root_cause_status: "unconfirmed"; may_claim_root_cause: false; human_confirmation_required_for_critical_actions: true; pending_approvals: number; open_conflicts: number; open_unknowns: number };
  sync: { generated_at: string; latest_event_at: string; timeline_event_count: number };
  integrations: Integration[];
  agora_configured: boolean;
};
