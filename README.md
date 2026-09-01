# ORBIT Incident Engine

ORBIT (Operational Response & Briefing Intelligence Team) is a production-oriented real-time incident command platform. The current foundation implements the persistent Incident Digital Twin, live event stream, Agora voice-agent lifecycle, transcript intelligence, task tracking, decision approvals, safe external-tool execution, and command-center shell.

## Repository layout

- `api/` - FastAPI service, PostgreSQL persistence, WebSocket event stream.
- `web/` - React command-center shell.
- `docs/` - product contract, delivered-phase records, and production roadmap.
- `submission/` - the final EchoSphere PDF and PowerPoint kept with the project.
- `docker-compose.yml` - local PostgreSQL, API, and web development stack.

## Phase 1 capabilities

- Persistent incidents with severity, status, commander, and customer impact.
- Immutable timeline events for every state change.
- Evidence items with source, classification, and confidence.
- Action ownership, due dates, escalation level, and follow-up status.
- Human approval records for high-risk decisions.
- Incident-scoped WebSocket updates at `/ws/incidents/{incident_id}`.

## Phase 2 capabilities

- Participant identity, Agora UID, role, and language records.
- Server-side Agora Conversational AI agent start, speak, and stop lifecycle.
- Final transcript ingestion with speaker and role provenance.
- Fact, hypothesis, decision, and action classification with confidence.
- Missing-information and contradiction findings.
- Owner extraction for directly assigned actions.
- Guarded status-briefing generation and spoken delivery.

See `docs/PHASE_2_VOICE_AND_INTELLIGENCE.md` for the full flow.

## Phase 3 capabilities

- Slack message, Jira issue, PagerDuty incident, and monitoring snapshot connectors.
- Idempotent tool-execution records with complete request and outcome audit history.
- Automatic human-approval gates for high and critical risk actions.
- Role-based authorization for operators, commanders, approvers, and administrators.
- JSON logs, request correlation IDs, Prometheus metrics, timeline records, and WebSocket events.

See `docs/PHASE_3_INTEGRATIONS_SECURITY_OBSERVABILITY.md` for configuration, permissions, and execution flow.

## Phase 4 capabilities

- Persisted Evidence Knowledge Graph and contradiction graph with source IDs and confidence.
- Multi-agent run records for Commander, Listener, Evidence, Conflict, Timeline, Action, Investigation, and Integration responsibilities.
- Deduplicated What We Still Don't Know queue.
- PostgreSQL/pgvector incident memory and similar-incident retrieval with a SQLite fallback.
- Runbook ranking, anomaly correlation, blast-radius estimation, and advisory severity prediction.
- Checksum-addressed log, screenshot, chart, metric, and document evidence with optional controlled multimodal analysis.

See `docs/PHASE_4_EVIDENCE_AND_INVESTIGATION.md` for the data model, safety rules, and API flow.

Agent responsibilities are discoverable at `GET /api/agents`, and each investigation's auditable execution trail is available at `GET /api/incidents/{incident_id}/agent-runs`.

## Phase 5 capabilities

- Deadline-based action aging, deduplicated escalation levels, reassignment, and completion tracking.
- Engineering, support, executive, and commander briefings with source references and optional Agora speech.
- Evidence-backed recovery checks and explicit commander-only incident resolution.
- Decision audit, ordered incident replay, and operational analytics data contracts.
- Automatic final-summary and postmortem drafts with unresolved risks and guarded root-cause status.
- Automatic historical-memory indexing after confirmed recovery.

See `docs/PHASE_5_COMMANDER_OPERATIONS.md` for the complete workflow and API surface.

## Phase 6 capabilities

- Alembic migrations with production auto-schema creation disabled.
- Redis distributed locks, cross-replica events, rate limiting, background jobs, retries, and dead-letter handling.
- Authenticated WebSockets plus local JWT or OIDC/JWKS verification.
- Mounted secret files, authenticated field encryption, retention dry-runs, and confirmed redaction.
- Health/readiness probes, production containers, CI schema checks, load tests, backup/restore scripts, Prometheus rules, and SLOs.

See `docs/PHASE_6_PRODUCTION_HARDENING.md` for deployment and operating procedures.

The backend identifies itself as version `0.6.0`.

## Run locally

1. Copy `api/.env.example` to `api/.env` and set secrets.
2. Start PostgreSQL and Redis: `docker compose up -d db redis`.
3. Apply the schema: `cd api && alembic upgrade head`.
4. Start the API: `uv run uvicorn app.main:app --reload`.
5. Start the worker in another terminal: `cd api && uv run python -m app.worker`.
6. Start the command center: `cd web && npm install && npm run dev`.

Production deployment uses `deploy/docker-compose.production.yml`, mounted secrets, and automatic migration execution before API startup.

## Database backups

Create a Docker database backup and keep the latest 14 days:

```powershell
.\scripts\backup-docker.ps1
```

Install a Windows daily task (default 02:30) for the same backup policy:

```powershell
.\scripts\install-backup-schedule.ps1
```

The task removes only `backups/orbit-*.dump` files older than the retention period. Verify every backup policy with a non-production restore drill.

## Delivery reliability

Commanders can see safe background-delivery health at `GET /api/operations/reliability`. It reports queue, scheduled-retry, and dead-letter counts only; job payloads and error details remain restricted to administrators.

The complete build sequence is in `docs/PROJECT_PHASES.md`.
