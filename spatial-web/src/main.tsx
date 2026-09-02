import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import AgoraRTC, { type IAgoraRTCClient, type IMicrophoneAudioTrack } from "agora-rtc-sdk-ng";
import { createRoot } from "react-dom/client";
import { SpatialCommandCenter, type SpatialModule } from "./SpatialCommandCenter";
import { useCommandCenter } from "./useCommandCenter";
import type { CommandCenterSnapshot, RecoveryCheck } from "./types";
import { API_BASE, orbitApi } from "./api";
import { completeLogin, hasAccessToken, logout, oidcEnabled, startLogin } from "./oidc";
import "./styles.css";
import "./responsive.css";

type DetailRow = { primary: string; secondary: string; status: string };

function StatusPage() {
  const [status, setStatus] = useState<{ status: string; updated_at: string; components: Array<{ name: string; status: string }> } | null>(null);
  useEffect(() => { fetch(`${API_BASE}/api/status`).then((response) => response.json()).then(setStatus).catch(() => setStatus({ status: "unknown", updated_at: new Date().toISOString(), components: [] })); }, []);
  const label = (value: string) => value.replaceAll("_", " ");
  return <main className="public-status"><header><b>ORBIT</b><span>PUBLIC SERVICE STATUS</span></header><section><p className={`status-dot ${status?.status ?? "unknown"}`}>{label(status?.status ?? "checking")}</p><h1>{status?.status === "operational" ? "All systems operational" : "Service disruption detected"}</h1><p>Last updated {status ? new Date(status.updated_at).toLocaleString() : "now"}</p><a className="status-command-link" href="/">OPEN COMMAND CENTER</a><div className="status-components">{status?.components.length ? status.components.map((component) => <article key={component.name}><span>{component.name}</span><b className={component.status}>{label(component.status)}</b></article>) : <article><span>ORBIT platform</span><b className="operational">operational</b></article>}</div></section></main>;
}

function rowsFor(id: string, snapshot: CommandCenterSnapshot | null): DetailRow[] {
  if (!snapshot) return [];
  if (id === "commander") return snapshot.live_room.participants.map((item) => ({ primary: item.display_name, secondary: `${item.role} / ${item.language}`, status: snapshot.live_room.active ? "in room" : "registered" }));
  if (id === "truth") return [...snapshot.evidence.map((item) => ({ primary: item.claim, secondary: `${item.source} / ${item.confidence}% confidence`, status: item.classification })), ...snapshot.unknowns.map((item) => ({ primary: item.question, secondary: `priority / ${item.priority}`, status: item.status }))];
  if (id === "timeline") return snapshot.timeline.slice().reverse().map((item) => ({ primary: item.summary, secondary: new Date(item.created_at).toLocaleTimeString(), status: item.event_type }));
  if (id === "actions") return snapshot.actions.map((item) => ({ primary: item.task, secondary: `owner / ${item.owner_id}`, status: item.overdue ? "overdue" : item.status }));
  if (id === "investigation") return [...snapshot.intelligence.findings.map((item) => ({ primary: item.title, secondary: item.description, status: item.status })), ...snapshot.intelligence.analyses.map((item) => ({ primary: item.summary, secondary: item.limitations.join(" / ") || "No limitation recorded", status: `${item.confidence}%` }))];
  if (id === "prediction") {
    const latest = snapshot.prediction_engine?.latest;
    return [
      ...(snapshot.telemetry_engine?.early_warnings ?? []).map((item) => ({ primary: `Early warning / ${item.service} / ${item.metric}`, secondary: `${item.threshold_progress}% toward threshold · ETA ${item.threshold_eta_minutes ?? "unknown"} min · velocity ${item.velocity_per_minute}/min`, status: `${item.score}%` })),
      ...(latest?.forecast.metric_forecasts ?? []).map((item) => ({ primary: `${item.service} / ${item.metric}`, secondary: `Predicted ${item.predicted} · threshold ETA ${item.threshold_eta_minutes ?? "not reached"} min · ${item.confidence}% confidence`, status: `${item.breach_probability}% risk` })),
      ...(latest?.geospatial.regions ?? []).map((item) => ({ primary: `Geospatial exposure / ${item.code}`, secondary: `${item.estimated_customers_at_risk.toLocaleString()} customers potentially exposed`, status: `${item.exposure_score}%` })),
      ...(snapshot.prediction_engine?.simulations ?? []).map((item) => ({ primary: `Simulation / ${item.name}`, secondary: `${item.iterations} runs · baseline ${item.result.baseline_risk ?? 0}% → ${item.result.simulated_risk ?? 0}%`, status: `-${item.result.risk_reduction ?? 0}%` })),
      ...(snapshot.telemetry_engine?.evaluations ?? []).map((item) => ({ primary: `Forecast evaluation / ${item.quality}`, secondary: `Brier ${item.brier_score} · MAE ${item.mean_absolute_error} · lead ${item.lead_time_minutes ?? "n/a"} min`, status: item.drift })),
      ...(snapshot.telemetry_engine?.calibration.reliability_buckets ?? []).map((item) => ({ primary: `Reliability / ${item.bucket}% bucket`, secondary: `Forecast ${item.forecast_probability}% · observed ${item.observed_frequency}% · ${item.count} samples`, status: snapshot.telemetry_engine?.calibration.drift_status ?? "stable" })),
      ...(snapshot.learning_engine ? [{ primary: "Alert quality policy", secondary: `Precision ${Math.round(snapshot.learning_engine.alert_quality.current.precision * 100)}% · recall ${Math.round(snapshot.learning_engine.alert_quality.current.recall * 100)}% · recommended threshold ${snapshot.learning_engine.alert_quality.recommended_threshold}%`, status: snapshot.learning_engine.alert_quality.policy }] : []),
      ...(snapshot.learning_engine?.learned_prior ? [{ primary: "Learned historical prior", secondary: `${snapshot.learning_engine.learned_prior.incidents.length} similar resolved incidents · ${snapshot.learning_engine.learned_prior.confidence}% confidence`, status: `${snapshot.learning_engine.learned_prior.probability}%` }] : []),
    ];
  }
  if (id === "systems") return [
    ...snapshot.integrations.map((item) => ({ primary: item.provider, secondary: item.supported_operations.join(" / ") || "Configuration pending", status: item.configured ? "connected" : "offline" })),
    ...snapshot.tools.map((item) => ({ primary: `${item.provider} / ${item.operation}`, secondary: item.external_id ?? "No external identifier", status: item.status })),
    ...Object.entries(snapshot.certification_engine?.checklist ?? {}).map(([key, item]) => ({ primary: `Certification / ${key.replaceAll("_", " ")}`, secondary: item.required, status: item.passed ? "passed" : "blocked" })),
    ...Object.entries(snapshot.certification_engine?.performance ?? {}).map(([key, item]) => ({ primary: `Performance / ${key.replaceAll("_", " ")}`, secondary: `${item.sample_count}/${item.minimum_samples} samples · measured ${item.measured ?? "pending"}`, status: item.passed ? "passed" : "blocked" })),
  ];
  if (id === "recovery") return [
    ...snapshot.checks.map((item) => ({ primary: item.criterion, secondary: item.observation ?? "Awaiting evidence-backed observation", status: item.status })),
    ...snapshot.recovery.blockers.map((blocker) => ({ primary: "Resolution blocker", secondary: blocker, status: "blocked" })),
  ];
  return [...snapshot.reports.map((item) => ({ primary: item.title, secondary: new Date(item.updated_at).toLocaleString(), status: item.status })), ...snapshot.communications.briefings.map((item) => ({ primary: item.message, secondary: `${item.audience} briefing / ${item.source_references.length} sources`, status: item.spoken ? "spoken" : "written" }))];
}

function modeFor(snapshot: CommandCenterSnapshot | null) {
  if (snapshot?.live_room.active) return "listening" as const;
  if (snapshot?.incident.severity === "SEV1" || snapshot?.guardrails.open_conflicts) return "alert" as const;
  return "idle" as const;
}

function App() {
  const { incidents, incidentId, setIncidentId, snapshot, loading, error, refresh } = useCommandCenter();
  const [activeIndex, setActiveIndex] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [labStatus, setLabStatus] = useState("");
  const [certStatus, setCertStatus] = useState("");
  const [recoveryStatus, setRecoveryStatus] = useState("");
  const [recoveryChecks, setRecoveryChecks] = useState<RecoveryCheck[]>([]);
  const [recoveryObservation, setRecoveryObservation] = useState("");
  const [recoveryEvidenceIds, setRecoveryEvidenceIds] = useState("");
  const [resolutionNote, setResolutionNote] = useState("");
  const [evidenceClaim, setEvidenceClaim] = useState("");
  const [evidenceSource, setEvidenceSource] = useState("");
  const [evidenceConfidence, setEvidenceConfidence] = useState("90");
  const [evidenceStatus, setEvidenceStatus] = useState("");
  const [reportStatus, setReportStatus] = useState("");
  const [signedIn, setSignedIn] = useState(() => hasAccessToken());
  const [authStatus, setAuthStatus] = useState("");
  const [templates, setTemplates] = useState<Array<{ id: string; name: string; service: string; severity: string }>>([]);
  const [templateId, setTemplateId] = useState("");
  const [templateStatus, setTemplateStatus] = useState("");
  const [reliability, setReliability] = useState<{ dead_letter_count: number; retry_scheduled_count: number } | null>(null);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [voiceMuted, setVoiceMuted] = useState(false);
  const voiceClient = useRef<IAgoraRTCClient | null>(null);
  const microphone = useRef<IMicrophoneAudioTrack | null>(null);
  const voiceSessionId = useRef<string | null>(null);
  const modules = useMemo<SpatialModule[]>(() => [
    { id: "commander", index: "01", title: "Voice Commander", eyebrow: "Agora live room", summary: "Participant roles, multilingual voice, transcripts, and spoken briefings remain synchronized with the incident.", metric: String(snapshot?.live_room.participants.length ?? 0).padStart(2, "0"), metricLabel: "participants", accent: "#f6c85f", accentSecondary: "#ff7a90", visual: "voice" },
    { id: "truth", index: "02", title: "Shared Truth", eyebrow: "Evidence intelligence", summary: "Confirmed facts, hypotheses, decisions, unknowns, conflicts, confidence, and provenance in one operational surface.", metric: String(snapshot?.evidence.length ?? 0).padStart(2, "0"), metricLabel: "evidence items", accent: "#58f5c7", accentSecondary: "#4bc8ff", visual: "evidence" },
    { id: "timeline", index: "03", title: "Living Timeline", eyebrow: "Real-time sequence", summary: "Voice, evidence, decisions, actions, tools, and recovery events ordered into the incident record.", metric: String(snapshot?.timeline.length ?? 0).padStart(2, "0"), metricLabel: "events", accent: "#8fd3ff", accentSecondary: "#617bff", visual: "timeline" },
    { id: "actions", index: "04", title: "Human Authority", eyebrow: "Ownership and approval", summary: "Owned work, aging, escalation, decisions, and critical-action confirmation without bypassing the commander.", metric: String(snapshot?.guardrails.pending_approvals ?? 0).padStart(2, "0"), metricLabel: "approvals", accent: "#ff8a66", accentSecondary: "#ffd45c", visual: "actions" },
    { id: "investigation", index: "05", title: "Investigation", eyebrow: "Eight-agent system", summary: "Contradiction graph, unknowns, anomaly correlation, blast radius, severity guidance, runbooks, and incident memory.", metric: String(snapshot?.intelligence.knowledge_graph.nodes ?? 0).padStart(2, "0"), metricLabel: "graph nodes", accent: "#c58cff", accentSecondary: "#ff70c5", visual: "graph" },
    { id: "prediction", index: "06", title: "Prediction Lab", eyebrow: "Live early warning", summary: "Streaming telemetry, threshold warnings, calibrated forecasts, drift detection, dependency propagation, geospatial exposure, and intervention simulation.", metric: String(snapshot?.telemetry_engine?.early_warnings.length ?? 0).padStart(2, "0"), metricLabel: "early warnings", accent: "#ffd45c", accentSecondary: "#b783ff", visual: "prediction" },
    { id: "systems", index: "07", title: "Connected Systems", eyebrow: "Tool gateway", summary: "Slack, Jira, PagerDuty, and monitoring calls pass through policy, idempotency, audit, and approval gates.", metric: String(snapshot?.integrations.filter((item) => item.configured).length ?? 0).padStart(2, "0"), metricLabel: "connected", accent: "#3ee7ff", accentSecondary: "#35f08c", visual: "systems" },
    { id: "recovery", index: "08", title: "Recovery Proof", eyebrow: "Verification gate", summary: "Evidence-backed recovery criteria, blockers, human confirmation, and guarded incident resolution.", metric: `${snapshot?.recovery.checks_passed ?? 0}/${snapshot?.recovery.checks_total ?? 0}`, metricLabel: "checks passed", accent: "#a8f75a", accentSecondary: "#50e3a4", visual: "recovery" },
    { id: "report", index: "09", title: "After Action", eyebrow: "Replay and reports", summary: "Decision audit, incident replay, operational analytics, final summary, unresolved risks, and automatic postmortem.", metric: String(snapshot?.reports.length ?? 0).padStart(2, "0"), metricLabel: "reports", accent: "#ff79b9", accentSecondary: "#ad8cff", visual: "report" },
  ], [snapshot]);
  const active = modules[activeIndex] ?? modules[0];
  const openModule = modules.find((item) => item.id === openId) ?? null;
  const detailRows = rowsFor(openId ?? "", snapshot).slice(0, 30);
  const handleActiveChange = useCallback((index: number) => setActiveIndex(index), []);
  const handleOpen = useCallback((id: string) => setOpenId(id), []);
  useEffect(() => {
    completeLogin().then((completed) => {
      if (completed) {
        setSignedIn(true);
        setAuthStatus("SIGNED IN");
        void refresh();
      }
    }).catch(() => setAuthStatus("SIGN-IN FAILED"));
  }, [refresh]);
  useEffect(() => { orbitApi.incidentTemplates().then(setTemplates).catch(() => undefined); }, [signedIn]);
  useEffect(() => { orbitApi.deliveryReliability().then(setReliability).catch(() => setReliability(null)); }, [signedIn]);
  const declareTemplate = async () => {
    if (!templateId) return;
    const selected = templates.find((template) => template.id === templateId);
    if (!selected || !window.confirm(`Declare ${selected.severity} incident from ${selected.name} template?`)) return;
    try {
      const incident = await orbitApi.createFromTemplate(templateId);
      setIncidentId(incident.id);
      setTemplateStatus("INCIDENT DECLARED");
    } catch { setTemplateStatus("TEMPLATE DECLARATION FAILED"); }
  };
  const runPaymentForecast = async () => {
    if (!incidentId) return;
    setLabStatus("FORECASTING");
    const observations = [
      ...[[0, 1.2], [5, 2.8], [10, 5.9], [15, 9.4]].map(([minute, value]) => ({ metric: "payment_error_rate", service: "payments", region: "us-east", minute, value, baseline: 1, threshold: 10, higher_is_worse: true })),
      ...[[0, 180], [5, 240], [10, 410], [15, 690]].map(([minute, value]) => ({ metric: "database_latency_ms", service: "payment-db", region: "us-east", minute, value, baseline: 180, threshold: 800, higher_is_worse: true })),
      ...[[0, 99.1], [5, 97.4], [10, 92.8], [15, 86.2]].map(([minute, value]) => ({ metric: "success_rate", service: "checkout", region: "eu-west", minute, value, baseline: 99, threshold: 85, higher_is_worse: false })),
    ];
    try {
      await orbitApi.runPrediction(incidentId, { horizon_minutes: 30, observations, dependency_map: { "payment-db": ["payments"], payments: ["checkout", "refunds"], checkout: ["orders"] }, regions: [{ code: "us-east", latitude: 37.4, longitude: -78.7, traffic_share: .58, customers: 240000, services: ["payment-db", "payments"] }, { code: "eu-west", latitude: 53.3, longitude: -6.2, traffic_share: .27, customers: 110000, services: ["checkout"] }, { code: "ap-south", latitude: 19.1, longitude: 72.9, traffic_share: .15, customers: 85000, services: ["payments"] }] });
      await refresh();
      setLabStatus("FORECAST READY");
    } catch { setLabStatus("FORECAST FAILED"); }
  };
  const runTrafficShiftSimulation = async () => {
    if (!incidentId || !snapshot?.prediction_engine?.latest) return;
    setLabStatus("SIMULATING 500 PATHS");
    try {
      await orbitApi.runSimulation(incidentId, { name: "Shift 40% traffic to healthy region", prediction_run_id: snapshot.prediction_engine.latest.id, iterations: 500, intervention: { effectiveness_percent: 42, implementation_delay_minutes: 6, failure_probability_percent: 8 }, assumptions: { risk_volatility: 7 } });
      await refresh();
      setLabStatus("SIMULATION READY");
    } catch { setLabStatus("SIMULATION FAILED"); }
  };
  const ingestLiveSignals = async () => {
    if (!incidentId) return;
    setLabStatus("INGESTING LIVE SIGNALS");
    const now = Date.now();
    const points = [
      ...[[15, 1.2], [10, 3.1], [5, 6.4], [0, 9.2]].map(([ago, value], index) => ({ metric: "payment_error_rate", service: "payments", region: "us-east", observed_at: new Date(now - ago * 60000).toISOString(), value, baseline: 1, threshold: 10, higher_is_worse: true, source_event_id: `payment-${now}-${index}`, labels: { environment: "production" } })),
      ...[[15, 180], [10, 290], [5, 510], [0, 735]].map(([ago, value], index) => ({ metric: "database_latency_ms", service: "payment-db", region: "us-east", observed_at: new Date(now - ago * 60000).toISOString(), value, baseline: 180, threshold: 800, higher_is_worse: true, source_event_id: `database-${now}-${index}`, labels: { environment: "production" } })),
    ];
    try {
      const result = await orbitApi.ingestTelemetry(incidentId, { source: "prometheus-demo-stream", observations: points, auto_forecast: true, forecast_horizon_minutes: 30, dependency_map: { "payment-db": ["payments"], payments: ["checkout", "refunds"] }, region_catalog: [{ code: "us-east", latitude: 37.4, longitude: -78.7, traffic_share: .58, customers: 240000, services: ["payment-db", "payments"] }] });
      await refresh();
      setLabStatus(`${result.accepted} SIGNALS · ${result.early_warnings.length} WARNINGS`);
    } catch { setLabStatus("INGEST FAILED"); }
  };
  const evaluateLatestForecast = async () => {
    if (!incidentId || !snapshot?.prediction_engine?.latest) return;
    setLabStatus("BACKTESTING FORECAST");
    try {
      const result = await orbitApi.evaluatePrediction(incidentId, snapshot.prediction_engine.latest.id);
      await refresh();
      setLabStatus(`BRIER ${result.brier_score} · ${result.drift.status ?? "STABLE"}`);
    } catch { setLabStatus("EVALUATION FAILED"); }
  };
  const runProductionLearning = async () => {
    if (!incidentId) return;
    setLabStatus("RUNNING LEARNING CYCLE");
    try {
      const result = await orbitApi.runLearningCycle(incidentId);
      await refresh();
      setLabStatus(`${result.maturity_evaluation.evaluated} MATURED · ${result.alert_quality.sample_count} OUTCOMES`);
    } catch { setLabStatus("LEARNING CYCLE FAILED"); }
  };
  const runCertification = async () => {
    if (!incidentId) return;
    setCertStatus("EVALUATING STAGING GATES");
    try {
      const current = snapshot?.certification_engine;
      const result = current?.id ? await orbitApi.evaluateCertification(current.id) : await orbitApi.startCertification(incidentId);
      await refresh();
      setCertStatus(`CERTIFICATION ${result.status.toUpperCase()}`);
    } catch { setCertStatus("CERTIFICATION FAILED"); }
  };
  const reviewRecovery = async () => {
    if (!incidentId) return;
    setRecoveryStatus("VERIFYING RECOVERY GATE");
    try {
      const result = await orbitApi.recoveryReadiness(incidentId);
      setRecoveryChecks(await orbitApi.recoveryChecks(incidentId));
      await refresh();
      setRecoveryStatus(result.ready ? "READY FOR HUMAN CONFIRMATION" : `${result.blockers.length} BLOCKERS REMAIN`);
    } catch { setRecoveryStatus("RECOVERY CHECK FAILED"); }
  };
  const updateRecoveryCheck = async (check: RecoveryCheck, status: "passed" | "failed") => {
    if (!incidentId || recoveryObservation.trim().length < 3) return setRecoveryStatus("ADD A VERIFIED OBSERVATION");
    const evidenceIds = recoveryEvidenceIds.split(",").map((id) => id.trim()).filter(Boolean);
    if (status === "passed" && !evidenceIds.length) return setRecoveryStatus("PASSED CHECKS REQUIRE EVIDENCE IDS");
    try {
      await orbitApi.updateRecoveryCheck(incidentId, check.id, { status, observation: recoveryObservation.trim(), evidence_ids: evidenceIds });
      setRecoveryObservation("");
      setRecoveryEvidenceIds("");
      await reviewRecovery();
    } catch { setRecoveryStatus("RECOVERY UPDATE FAILED"); }
  };
  const resolveIncident = async () => {
    if (!incidentId || resolutionNote.trim().length < 10) return setRecoveryStatus("ADD A RESOLUTION NOTE (10+ CHARACTERS)");
    try {
      await orbitApi.resolveIncident(incidentId, resolutionNote.trim());
      setResolutionNote("");
      setRecoveryStatus("INCIDENT RESOLVED / REPORTS DRAFTED");
      await refresh();
      await reviewRecovery();
    } catch { setRecoveryStatus("RESOLUTION BLOCKED BY RECOVERY GATE"); }
  };
  const addEvidence = async () => {
    if (!incidentId || evidenceClaim.trim().length < 3 || evidenceSource.trim().length < 2) return setEvidenceStatus("ADD A CLAIM AND SOURCE");
    const confidence = Number(evidenceConfidence);
    if (!Number.isInteger(confidence) || confidence < 0 || confidence > 100) return setEvidenceStatus("CONFIDENCE MUST BE 0-100");
    try {
      await orbitApi.addEvidence(incidentId, { claim: evidenceClaim.trim(), classification: "fact", confidence, source: evidenceSource.trim() });
      setEvidenceClaim("");
      setEvidenceSource("");
      setEvidenceStatus("EVIDENCE RECORDED");
      await refresh();
    } catch { setEvidenceStatus("EVIDENCE RECORDING FAILED"); }
  };
  const finalizeReport = async (reportId: string) => {
    if (!incidentId) return;
    try {
      await orbitApi.finalizeReport(incidentId, reportId);
      setReportStatus("REPORT FINALIZED");
      await refresh();
    } catch { setReportStatus("REPORT FINALIZATION FAILED"); }
  };
  const downloadAudit = async () => {
    if (!incidentId) return;
    try {
      const audit = await orbitApi.decisionAuditExport(incidentId);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([JSON.stringify(audit, null, 2)], { type: "application/json" }));
      link.download = `orbit-audit-${incidentId}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
      setReportStatus("AUDIT EXPORTED");
    } catch { setReportStatus("AUDIT EXPORT FAILED"); }
  };
  const joinVoiceRoom = async () => {
    if (!incidentId || voiceClient.current) return;
    setVoiceStatus("REQUESTING MICROPHONE");
    let joiningClient: IAgoraRTCClient | null = null;
    let joiningTrack: IMicrophoneAudioTrack | null = null;
    let phase = "TOKEN";
    try {
      const room = await orbitApi.voiceToken(incidentId);
      phase = "MICROPHONE";
      joiningClient = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
      joiningClient.on("user-published", async (user, mediaType) => {
        await joiningClient?.subscribe(user, mediaType);
        if (mediaType === "audio") {
          user.audioTrack?.play();
        }
      });
      joiningTrack = await AgoraRTC.createMicrophoneAudioTrack();
      phase = "RTC JOIN";
      await joiningClient.join(room.app_id, room.channel, room.token, room.uid);
      await joiningClient.publish([joiningTrack]);
      phase = "AGENT START";
      const session = await orbitApi.startVoiceSession(incidentId, { channel: room.channel, remote_uids: [String(room.uid)], language: "en-US" });
      voiceClient.current = joiningClient;
      microphone.current = joiningTrack;
      voiceSessionId.current = session.id;
      setVoiceMuted(false);
      setVoiceStatus("LIVE / MICROPHONE CONNECTED");
      await refresh();
    } catch (reason) {
      joiningTrack?.close();
      if (joiningClient) await joiningClient.leave().catch(() => undefined);
      const message = reason instanceof Error ? reason.message.replace(/007[A-Za-z0-9+/=]+/g, "REDACTED_TOKEN") : "Unknown voice error";
      setVoiceStatus(`${phase} FAILED / ${message.slice(0, 110)}`);
    }
  };
  const toggleVoiceMute = async () => {
    if (!microphone.current) return;
    const muted = !voiceMuted;
    await microphone.current.setMuted(muted);
    setVoiceMuted(muted);
    setVoiceStatus(muted ? "LIVE / MICROPHONE MUTED" : "LIVE / MICROPHONE CONNECTED");
  };
  const leaveVoiceRoom = async () => {
    setVoiceStatus("LEAVING VOICE ROOM");
    try {
      if (incidentId && voiceSessionId.current) await orbitApi.stopVoiceSession(incidentId, voiceSessionId.current);
    } finally {
      microphone.current?.close();
      await voiceClient.current?.leave().catch(() => undefined);
      microphone.current = null;
      voiceClient.current = null;
      voiceSessionId.current = null;
      setVoiceMuted(false);
      setVoiceStatus("VOICE ROOM STANDBY");
      await refresh();
    }
  };

  return <main className="spatial-app" style={{ "--accent": active.accent, "--accent-secondary": active.accentSecondary } as CSSProperties}>
    <SpatialCommandCenter modules={modules} mode={modeFor(snapshot)} onActiveChange={handleActiveChange} onOpen={handleOpen} />
    <header className="frame-top"><a href="#">ORBIT / SPATIAL COMMAND</a><div><select value={incidentId ?? ""} onChange={(event) => setIncidentId(event.target.value || null)}><option value="">NO INCIDENT</option>{incidents.map((item) => <option key={item.id} value={item.id}>{item.severity} / {item.title}</option>)}</select>{templates.length > 0 && <><select value={templateId} onChange={(event) => setTemplateId(event.target.value)}><option value="">DECLARE TEMPLATE</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.severity} / {template.name}</option>)}</select><button onClick={declareTemplate} disabled={!templateId}>DECLARE</button></>}<button onClick={refresh}>SYNC</button>{oidcEnabled && <button onClick={() => signedIn ? logout() : void startLogin()}>{signedIn ? "SIGN OUT" : "SIGN IN"}</button>}</div><span>{templateStatus || authStatus || (oidcEnabled ? (signedIn ? "OIDC AUTHENTICATED" : "SIGN-IN REQUIRED") : (error && !import.meta.env.PROD ? "ENGINE OFFLINE" : "ENGINE READY"))}</span></header>
    <aside className="frame-left"><span>OPERATIONAL RESPONSE</span><span>VOICE / EVIDENCE / ACTION</span></aside>
    <aside className="frame-right"><span>ROOT CAUSE</span><b>UNCONFIRMED</b><span>HUMAN AUTHORITY</span><b>PRESERVED</b><span>DELIVERY</span><b>{reliability?.dead_letter_count ? `${reliability.dead_letter_count} FAILED` : reliability ? "HEALTHY" : "CHECKING"}</b></aside>
    <div className="active-caption"><span>{active.index} / {active.eyebrow}</span><h1>{active.title}</h1><p>{active.summary}</p><button onClick={() => setOpenId(active.id)}>OPEN SURFACE</button></div>
    <div className="spatial-instructions"><span>DRAG / SCROLL / ARROW KEYS</span><div>{modules.map((item, index) => <i className={index === activeIndex ? "active" : ""} key={item.id} />)}</div><span>{loading ? "SYNCHRONIZING" : `${activeIndex + 1} OF ${modules.length}`}</span></div>

    {openModule && <section className="detail-layer" aria-modal="true" role="dialog">
      <button className="detail-close" onClick={() => setOpenId(null)} aria-label="Close surface">×</button>
      <div className="detail-title"><span>{openModule.index} / {openModule.eyebrow}</span><h2>{openModule.title}</h2><p>{openModule.summary}</p><dl><div><dt>Metric</dt><dd>{openModule.metric}</dd></div><div><dt>State</dt><dd>{snapshot?.incident.status ?? "standby"}</dd></div><div><dt>Root cause</dt><dd>unconfirmed</dd></div></dl></div>
      <div className="detail-data"><header><span>LIVE INCIDENT DATA</span><span>{detailRows.length} RECORDS</span></header>{detailRows.length ? detailRows.map((row, index) => <article key={`${row.primary}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{row.primary}</h3><p>{row.secondary}</p></div><b>{row.status.replaceAll("_", " ")}</b></article>) : <p className="detail-empty">This surface is ready. Live records will appear when an incident is declared.</p>}</div>
      {openModule.id === "prediction" && <div className="prediction-controls"><span>{labStatus || "LIVE LEARNING READY"}</span><button onClick={ingestLiveSignals} disabled={!incidentId}>INGEST SIGNALS</button><button onClick={runPaymentForecast} disabled={!incidentId}>FORECAST</button><button onClick={runTrafficShiftSimulation} disabled={!snapshot?.prediction_engine?.latest}>SIMULATE</button><button onClick={evaluateLatestForecast} disabled={!snapshot?.prediction_engine?.latest}>EVALUATE</button><button onClick={runProductionLearning} disabled={!incidentId}>LEARN</button></div>}
      {openModule.id === "truth" && <div className="prediction-controls recovery-controls"><span>{evidenceStatus || "RECORD VERIFIED EVIDENCE"}</span><input value={evidenceClaim} onChange={(event) => setEvidenceClaim(event.target.value)} placeholder="Verified claim" /><input value={evidenceSource} onChange={(event) => setEvidenceSource(event.target.value)} placeholder="Source system or person" /><input value={evidenceConfidence} onChange={(event) => setEvidenceConfidence(event.target.value)} inputMode="numeric" placeholder="Confidence 0-100" /><button onClick={addEvidence} disabled={!incidentId}>ADD EVIDENCE</button></div>}
      {openModule.id === "commander" && <div className="prediction-controls"><span>{voiceStatus || "VOICE ROOM STANDBY"}</span><button onClick={joinVoiceRoom} disabled={!incidentId || Boolean(voiceClient.current)}>JOIN VOICE ROOM</button><button onClick={toggleVoiceMute} disabled={!voiceClient.current}>{voiceMuted ? "UNMUTE" : "MUTE"}</button><button onClick={leaveVoiceRoom} disabled={!voiceClient.current}>LEAVE ROOM</button></div>}
      {openModule.id === "systems" && <div className="prediction-controls"><span>{certStatus || `PROMOTION / ${snapshot?.certification_engine?.status?.toUpperCase() ?? "NOT STARTED"}`}</span><button onClick={runCertification} disabled={!incidentId}>{snapshot?.certification_engine?.id ? "REEVALUATE GATES" : "START CERTIFICATION"}</button></div>}
      {openModule.id === "recovery" && <div className="prediction-controls recovery-controls"><span>{recoveryStatus || (snapshot?.recovery.ready ? "READY FOR HUMAN CONFIRMATION" : `${snapshot?.recovery.blockers.length ?? 0} BLOCKERS REMAIN`)}</span><button onClick={reviewRecovery} disabled={!incidentId}>RECHECK RECOVERY</button>{recoveryChecks.map((check) => <div className="recovery-check" key={check.id}><strong>{check.status.toUpperCase()} / {check.criterion}</strong>{check.status !== "passed" && <><input value={recoveryObservation} onChange={(event) => setRecoveryObservation(event.target.value)} placeholder="Verified observation" /><input value={recoveryEvidenceIds} onChange={(event) => setRecoveryEvidenceIds(event.target.value)} placeholder="Evidence ID(s), comma-separated" /><button onClick={() => updateRecoveryCheck(check, "passed")}>MARK PASSED</button><button onClick={() => updateRecoveryCheck(check, "failed")}>MARK FAILED</button></>}</div>)}{snapshot?.recovery.ready && <><input value={resolutionNote} onChange={(event) => setResolutionNote(event.target.value)} placeholder="Human resolution note (10+ characters)" /><button onClick={resolveIncident}>CONFIRM AND RESOLVE</button></>}</div>}
      {openModule.id === "report" && <div className="prediction-controls recovery-controls"><span>{reportStatus || "DRAFTS REQUIRE COMMANDER CONFIRMATION"}</span><button onClick={downloadAudit} disabled={!incidentId}>EXPORT AUDIT</button>{snapshot?.reports.filter((report) => report.status !== "final").map((report) => <button key={report.id} onClick={() => finalizeReport(report.id)}>FINALIZE {report.type.toUpperCase()}</button>)}</div>}
    </section>}
  </main>;
}

createRoot(document.getElementById("root")!).render(window.location.pathname === "/status" ? <StatusPage /> : <App />);
