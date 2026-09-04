import type { CommandCenterSnapshot, Incident } from "./types";

const now = "2026-09-04T10:00:00.000Z";

export const staticDemoIncident: Incident = {
  id: "submission-demo-incident",
  title: "Payment API latency investigation",
  service: "payments-api",
  severity: "SEV2",
  status: "monitoring",
  commander_id: "demo-commander",
  customer_impact: "Elevated checkout latency observed in India West.",
  affected_regions: ["india-west"],
  recovery_criteria: "Latency remains below the alert threshold for 30 minutes.",
  created_at: now,
};

export const staticDemoSnapshot: CommandCenterSnapshot = {
  incident: staticDemoIncident,
  evidence: [
    { id: "ev-001", claim: "Checkout latency rose above the operating baseline.", classification: "confirmed_fact", confidence: 96, source: "Prometheus query snapshot", created_at: now },
    { id: "ev-002", claim: "A cache saturation pattern may be contributing to the rise.", classification: "hypothesis", confidence: 71, source: "Investigation agent", created_at: now },
    { id: "ev-003", claim: "Traffic is being observed before any remediation is approved.", classification: "decision", confidence: 100, source: "Incident commander", created_at: now },
  ],
  actions: [
    { id: "act-001", task: "Validate cache capacity", owner_id: "platform-operator", status: "in_progress", escalation_level: 1, overdue: false },
    { id: "act-002", task: "Prepare customer communication", owner_id: "communications", status: "ready", escalation_level: 0, overdue: false },
  ],
  unknowns: [{ id: "unk-001", question: "Is cache pressure regional or global?", priority: "high", status: "open" }],
  checks: [
    { id: "chk-001", criterion: "API p95 is below 300 ms", status: "passed", observation: "Latest observed p95: 193 ms", evidence_ids: ["ev-001"] },
    { id: "chk-002", criterion: "Error rate is below 1%", status: "passed", observation: "Latest observed error rate: 0%", evidence_ids: ["ev-001"] },
  ],
  timeline: [
    { id: "tl-001", event_type: "alert", summary: "Latency alert received from monitoring", payload: {}, created_at: "2026-09-04T09:42:00.000Z" },
    { id: "tl-002", event_type: "evidence", summary: "Baseline and current metrics recorded", actor_id: "demo-commander", payload: {}, created_at: "2026-09-04T09:46:00.000Z" },
    { id: "tl-003", event_type: "decision", summary: "Human review retained before remediation", actor_id: "demo-commander", payload: {}, created_at: now },
  ],
  decisions: [],
  approvals: [{ id: "apr-001", action: "Traffic shift", status: "not_requested", created_at: now }],
  tools: [
    { id: "tool-001", provider: "monitoring", operation: "query_snapshot", status: "succeeded", external_id: "demo-query-001" },
    { id: "tool-002", provider: "slack", operation: "post_message", status: "succeeded", external_id: "demo-message-001" },
    { id: "tool-003", provider: "jira", operation: "create_issue", status: "succeeded", external_id: "ORBIT-42" },
  ],
  recovery: { ready: true, checks_total: 2, checks_passed: 2, blockers: [], requires_human_confirmation: true },
  analytics: { incident_age_minutes: 18, evidence_count: 3, action_count: 2 },
  live_room: {
    participants: [
      { id: "part-001", agora_uid: "1001", display_name: "Kavya", role: "investigator", language: "en-US", joined_at: now },
      { id: "part-002", agora_uid: "1002", display_name: "Lakshya", role: "communications", language: "en-US", joined_at: now },
      { id: "part-003", agora_uid: "1003", display_name: "Aarav", role: "operator", language: "en-US", joined_at: now },
    ],
    voice_sessions: [], active: false,
    recent_transcripts: [{ id: "tr-001", speaker_name: "Kavya", speaker_role: "investigator", text: "Metrics are stabilizing; root cause remains unconfirmed.", language: "en-US", created_at: now }],
  },
  intelligence: {
    findings: [{ id: "find-001", type: "correlation", title: "Latency coincides with cache pressure", description: "The correlation is advisory and requires human verification.", severity: "medium", status: "open", related_evidence_ids: ["ev-001", "ev-002"] }],
    artifacts: [{ id: "art-001", type: "metric_snapshot", title: "Payment API metrics", source_name: "Prometheus", analysis_status: "complete" }],
    knowledge_graph: { nodes: 12, edges: 18, contradiction_edges: 1 },
    analyses: [{ id: "an-001", kind: "blast_radius", summary: "India West has the highest current exposure.", confidence: 82, limitations: ["Sample data shown for submission"] }],
    agent_runs: [{ id: "run-001", agent: "investigation", status: "succeeded", latency_ms: 162 }],
  },
  communications: { briefings: [{ id: "brief-001", audience: "operations", message: "Payment API latency is improving; monitoring continues under human command.", source_references: ["ev-001"], spoken: false, created_at: now }] },
  reports: [{ id: "report-001", type: "incident_summary", status: "draft", title: "Incident summary draft", created_at: now, updated_at: now }],
  prediction_engine: { latest: { id: "pred-001", horizon_minutes: 30, forecast: { incident_escalation_probability: 18, risk_band: "low", metric_forecasts: [{ metric: "api_p95_ms", service: "payments-api", predicted: 193, breach_probability: 12, threshold_eta_minutes: null, confidence: 84 }] }, graphs: {}, geospatial: { regions: [{ code: "IN-W", exposure_score: 22, estimated_customers_at_risk: 420 }] }, limitations: ["Advisory prediction only"], created_at: now }, history_count: 4, simulations: [{ id: "sim-001", name: "Shift traffic to healthy region", iterations: 500, result: { baseline_risk: 28, simulated_risk: 14, risk_reduction: 14 }, created_at: now }], advisory_only: true },
  telemetry_engine: { observation_count: 24, recent: [], early_warnings: [{ metric: "api_p95_ms", service: "payments-api", region: "india-west", score: 22, velocity_per_minute: -0.3, threshold_progress: 64, threshold_eta_minutes: null, reason: "Returning toward baseline" }], evaluations: [{ id: "eval-001", prediction_run_id: "pred-001", brier_score: 0.12, mean_absolute_error: 0.8, lead_time_minutes: 12, quality: "good", drift: "stable", evaluated_at: now }], calibration: { evaluation_count: 8, mean_brier_score: 0.14, mean_absolute_error: 0.9, mean_lead_time_minutes: 11, reliability_buckets: [{ bucket: "20", forecast_probability: 20, observed_frequency: 18, count: 8 }], drift_status: "stable" }, automatic_forecasting: false },
  learning_engine: { evaluation_count: 8, alert_quality: { sample_count: 12, current: { precision: 0.88, recall: 0.81, false_positive_rate: 0.12, false_negative_rate: 0.19, threshold: 70 }, recommended_threshold: 72, policy: "human-reviewed", minimum_samples: 10 }, collector: { enabled: false, configured: true, interval_seconds: 60, query_count: 2 }, recent_runs: [], learned_prior: null },
  certification_engine: { id: "cert-001", environment: "staging", status: "passed", checklist: { integrations: { passed: true, required: "Successful staging calls", evidence: {} }, human_authority: { passed: true, required: "High-impact actions require approval", evidence: {} } }, performance: { api_p95_latency_ms: { passed: true, measured: 121, sample_count: 1, minimum_samples: 1 }, websocket_delivery_ms: { passed: true, measured: 75.8, sample_count: 5, minimum_samples: 5 } }, promotion_gates: { promotion_allowed: false, groups: { submission_demo: true }, configuration: {} }, certified_by: "demo-commander" },
  guardrails: { root_cause_status: "unconfirmed", may_claim_root_cause: false, human_confirmation_required_for_critical_actions: true, pending_approvals: 0, open_conflicts: 1, open_unknowns: 1 },
  sync: { generated_at: now, latest_event_at: now, timeline_event_count: 3 },
  integrations: [
    { provider: "slack", configured: true, supported_operations: ["post_message"] },
    { provider: "jira", configured: true, supported_operations: ["create_issue"] },
    { provider: "pagerduty", configured: true, supported_operations: ["create_incident", "resolve_incident"] },
    { provider: "monitoring", configured: true, supported_operations: ["query_snapshot", "query_range"] },
  ],
  agora_configured: true,
};
