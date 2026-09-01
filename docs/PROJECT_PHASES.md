# ORBIT Production Build Phases

ORBIT means **Operational Response & Briefing Intelligence Team**. It is being built as a deployable incident-command platform, with the payment-system outage as the first full acceptance scenario.

## Phase 0 — Product and safety contract — complete

Lock the problem, users, success measures, evidence language, human authority boundaries, architecture principles, and acceptance criteria. ORBIT organizes evidence and explicitly avoids claiming an unconfirmed root cause.

## Phase 1 — Incident Digital Twin — complete

Build persistent incident state, evidence with source and confidence, actions and owners, approval records, continuously updated timeline, WebSocket events, and the functional command-center shell.

## Phase 2 — Agora voice and live intelligence — core complete; live credentials pending

Join a shared Agora RTC room, recognize participant identity/role/language, ingest live transcripts, classify facts/hypotheses/decisions/actions, detect initial contradictions and unknowns, create owned actions, and speak guarded status briefings.

## Phase 3 — Safe integrations, access, and observability — implemented; live accounts pending

Connect Slack, Jira, PagerDuty, and monitoring through an idempotent tool gateway. Enforce approval for critical actions, role-based permissions, audit history, request correlation, metrics, and real-time execution events.

## Phase 4 — Evidence and investigation intelligence — implemented; live processors pending

Expand the multi-agent Commander architecture across Commander, Listener, Evidence, Conflict, Timeline, Action, Investigation, and Integration agents. Build the Evidence Knowledge Graph and contradiction graph; source/provenance chains; confidence recalculation; the **What We Still Don't Know** engine; historical incident memory with RAG/vector search; similar-incident retrieval; automated runbook recommendations; anomaly correlation; blast-radius estimation; severity prediction; and multimodal log, screenshot, and chart analysis.

## Phase 5 — Commander operations and recovery — implemented; live acceptance run pending

Add action aging and escalation; role-specific briefings for engineering, support, executives, and incident command; decision audit views; recovery-criteria verification; safe resolution checks; incident replay; analytics dashboard; final incident summary with unresolved risks; and automatic postmortem generation.

## Phase 6 — Production hardening and deployment — implemented; environment deployment pending

Add Alembic migrations, Redis queues and distributed locks, retry/dead-letter handling, OIDC and authorized WebSockets, managed secrets, encryption and retention controls, rate limits, backup/restore, load/failure testing, sandbox integration tests, CI/CD, deployment, runbooks, and operational SLOs.

## Acceptance flow — payment outage

Engineers, support, and business leaders join the live room and provide incomplete or conflicting information. ORBIT separates evidence types, preserves each source, highlights contradictions and unknowns, assigns actions, queries approved systems, maintains the shared timeline, gives role-appropriate spoken updates, requires human confirmation for critical calls, verifies recovery criteria, and produces a final report without inventing the root cause.
