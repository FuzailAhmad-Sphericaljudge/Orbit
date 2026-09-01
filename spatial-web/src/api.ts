import type { CommandCenterSnapshot, Incident, RecoveryCheck } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("orbit_access_token");
  if (token) return { Authorization: `Bearer ${token}` };
  const devUser = import.meta.env.VITE_DEV_USER_ID;
  if (!devUser) return {};
  return {
    "X-User-Id": devUser,
    "X-User-Role": import.meta.env.VITE_DEV_USER_ROLE ?? "observer",
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...init?.headers },
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `ORBIT API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const orbitApi = {
  listIncidents: () => request<Incident[]>("/api/incidents"),
  incidentTemplates: () => request<Array<{ id: string; name: string; service: string; severity: string }>>("/api/incident-templates"),
  createFromTemplate: (templateId: string) => request<Incident>(`/api/incident-templates/${templateId}/incidents`, { method: "POST", body: "{}" }),
  voiceToken: (incidentId: string) => request<{ app_id: string; channel: string; uid: number; token: string }>(`/api/incidents/${incidentId}/voice/rtc-token`, { method: "POST", body: "{}" }),
  startVoiceSession: (incidentId: string, payload: { channel: string; remote_uids: string[]; language: string }) => request<{ id: string }>(`/api/incidents/${incidentId}/voice/sessions`, { method: "POST", body: JSON.stringify(payload) }),
  stopVoiceSession: (incidentId: string, sessionId: string) => request<{ id: string }>(`/api/incidents/${incidentId}/voice/sessions/${sessionId}/stop`, { method: "POST" }),
  commandCenter: (incidentId: string) => request<CommandCenterSnapshot>(`/api/incidents/${incidentId}/command-center`),
  addEvidence: (incidentId: string, payload: { claim: string; classification: "fact" | "hypothesis" | "decision"; confidence: number; source: string }) => request<{ id: string }>(`/api/incidents/${incidentId}/evidence`, { method: "POST", body: JSON.stringify(payload) }),
  recoveryReadiness: (incidentId: string) => request<{ ready: boolean; checks_total: number; checks_passed: number; blockers: string[]; requires_human_confirmation: boolean }>(`/api/incidents/${incidentId}/recovery/readiness`),
  recoveryChecks: (incidentId: string) => request<RecoveryCheck[]>(`/api/incidents/${incidentId}/recovery/checks`),
  updateRecoveryCheck: (incidentId: string, checkId: string, payload: { status: "passed" | "failed"; observation: string; evidence_ids: string[] }) => request<RecoveryCheck>(`/api/incidents/${incidentId}/recovery/checks/${checkId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  resolveIncident: (incidentId: string, resolutionNote: string) => request<Incident>(`/api/incidents/${incidentId}/resolve`, { method: "POST", body: JSON.stringify({ confirm_recovery: true, resolution_note: resolutionNote }) }),
  finalizeReport: (incidentId: string, reportId: string) => request<{ id: string }>(`/api/incidents/${incidentId}/reports/${reportId}/finalize`, { method: "POST", body: JSON.stringify({ confirm: true }) }),
  decisionAuditExport: (incidentId: string) => request<unknown>(`/api/incidents/${incidentId}/decision-audit/export`),
  runPrediction: (incidentId: string, payload: Record<string, unknown>) => request<{ id: string }>(`/api/incidents/${incidentId}/predictions/run`, { method: "POST", body: JSON.stringify(payload) }),
  runSimulation: (incidentId: string, payload: Record<string, unknown>) => request<{ id: string }>(`/api/incidents/${incidentId}/simulations/run`, { method: "POST", body: JSON.stringify(payload) }),
  ingestTelemetry: (incidentId: string, payload: Record<string, unknown>) => request<{ accepted: number; duplicates: number; early_warnings: unknown[]; prediction_run_id?: string | null }>(`/api/incidents/${incidentId}/telemetry`, { method: "POST", body: JSON.stringify(payload) }),
  evaluatePrediction: (incidentId: string, predictionId: string) => request<{ id: string; brier_score: number; drift: { status?: string } }>(`/api/incidents/${incidentId}/predictions/${predictionId}/evaluate`, { method: "POST" }),
  runLearningCycle: (incidentId: string) => request<{ run_id: string; maturity_evaluation: { evaluated: number }; alert_quality: { sample_count: number } }>("/api/production-learning/run", { method: "POST", body: JSON.stringify({ incident_id: incidentId, collect_telemetry: true, evaluate_mature_forecasts: true }) }),
  startCertification: (incidentId: string) => request<{ id: string; status: string }>(`/api/incidents/${incidentId}/certifications`, { method: "POST", body: JSON.stringify({ environment: "staging", notes: ["Started from spatial command center"] }) }),
  evaluateCertification: (runId: string) => request<{ id: string; status: string }>(`/api/certifications/${runId}/evaluate`, { method: "POST" }),
};

export function incidentSocketUrl(incidentId: string): string | null {
  const token = localStorage.getItem("orbit_access_token");
  if (!token) return null;
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/ws/incidents/${incidentId}`;
  url.searchParams.set("token", token);
  return url.toString();
}
