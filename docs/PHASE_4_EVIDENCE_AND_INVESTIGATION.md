# Phase 4 — Evidence and Investigation Intelligence

Phase 4 turns ORBIT's incident state into a traceable investigation workspace. Every recommendation stores its inputs, confidence, limitations, responsible agent, and creation time. None of these analyses independently confirms root cause.

## Multi-agent Commander architecture

| Agent | Production responsibility |
|---|---|
| Commander | Coordinates specialist outputs and preserves human authority |
| Listener | Processes Agora speech with speaker, role, and language provenance |
| Evidence | Maintains evidence, sources, entities, and the knowledge graph |
| Conflict | Creates contradiction edges and the What We Still Don't Know queue |
| Timeline | Maintains the chronological incident record |
| Action | Tracks owned work and follow-up state |
| Investigation | Correlates anomalies and retrieves runbooks and incident memory |
| Integration | Prepares approval-gated external tool calls |

Every Phase 4 orchestration stores individual `agent_runs` with input/output references, completion status, latency, and errors.

## Evidence Knowledge Graph

- Nodes represent evidence, components, regions, hypotheses, decisions, and actions.
- Edges represent `derived_from`, `contradicts`, `supports`, `affects`, `observed_in`, and `related_to` relationships.
- Nodes and edges retain confidence and evidence IDs.
- Contradictions preserve both original claims rather than replacing either claim.
- Graph APIs expose the persisted model for a future interactive visualization.

## What We Still Don't Know

The Conflict Agent maintains deduplicated questions covering customer impact, geographic scope, start time, metric baselines, recovery criteria, and ways to falsify the leading hypothesis. Unknowns remain open until linked to resolution evidence.

## Historical memory and RAG

- Resolved incident summaries, symptoms, resolutions, risks, and human root-cause status can be indexed.
- PostgreSQL uses the official pgvector extension and cosine-distance operator over 96-dimensional embeddings.
- SQLite development mode uses the same deterministic embeddings with an in-process cosine fallback.
- Similar incidents are explicitly contextual evidence, never proof of an identical cause.

The included hashing embedding is an offline, deterministic baseline. A production embedding provider can replace it without changing the memory schema or retrieval contract.

## Investigation analytics

- **Anomaly correlation:** compares observations with supplied baselines and standard deviations, then groups anomalies by service and region.
- **Blast-radius estimation:** walks a supplied service-dependency graph to a bounded depth and distinguishes confirmed from potentially affected services.
- **Severity prediction:** combines failure rate, customers, regions, and service criticality into an advisory SEV suggestion. The commander owns the final decision.
- **Runbook retrieval:** ranks active runbooks using semantic similarity plus keyword overlap. Consequential steps still require human review and the Phase 3 approval gate.

## Multimodal evidence

Logs, screenshots, charts, metrics, and documents are stored as checksum-addressed evidence artifacts with source, URI, MIME type, observer, time, and metadata. When `VISION_ANALYSIS_URL` is configured, ORBIT sends the artifact reference to that controlled processor. If it is unavailable, ORBIT safely falls back to extracted-text analysis and records the limitation.

## Main APIs

- `GET /api/agents`
- `POST/GET /api/incidents/{id}/artifacts`
- `POST /api/incidents/{id}/investigation/run`
- `GET /api/incidents/{id}/knowledge/nodes`
- `GET /api/incidents/{id}/knowledge/edges`
- `GET /api/incidents/{id}/unknowns`
- `GET /api/incidents/{id}/analyses`
- `GET /api/incidents/{id}/agent-runs`
- `POST/GET /api/runbooks`
- `PUT /api/incidents/{id}/memory`
- `GET /api/incidents/{id}/similar`

Database uniqueness constraints protect artifact checksums, normalized graph nodes, graph relations, and unknown-question keys from duplicate concurrent writes. Prometheus exposes `orbit_investigation_runs_total{status=...}` for operational monitoring.

## Payment-outage acceptance behavior

The first acceptance run should ingest payment failure statements, a monitoring snapshot, and a dashboard screenshot; construct component/region/evidence nodes; retain conflicting latency claims; ask for missing impact and recovery criteria; correlate payment metrics; estimate downstream checkout/order impact; suggest severity; retrieve payment runbooks and similar incidents; and return `root_cause_confirmed: false`.
