# Phase 5 — Commander Operations, Recovery, and Learning

Phase 5 closes the incident-response loop. ORBIT now follows owned work, prepares audience-specific updates, verifies recovery against evidence, reconstructs incident history, measures response performance, and produces durable final reports. Human authority remains mandatory for resolution, report finalization, critical actions, severity, and root-cause confirmation.

## Action aging and escalation

- Actions support status, owner, deadline, completion time, escalation level, and last-escalated time.
- The escalation engine evaluates overdue work against configurable positive-minute thresholds.
- It raises each action only to the required level, avoiding repeated duplicate escalations.
- Every escalation is written to the timeline, broadcast over WebSockets, and counted in Prometheus.
- Operators can reassign, reschedule, block, reopen, or complete actions through the update API.

## Role-specific briefings

ORBIT produces separate briefings for:

- **Engineering:** confirmed signals, explicitly unconfirmed hypotheses, and technical actions.
- **Support:** verified customer impact and facts safe to communicate externally.
- **Executives:** business impact, work/unknown counts, and recovery readiness.
- **Incident command:** facts, decisions, owners, unknowns, and control status.

Each briefing stores source references and its creator. A briefing can be spoken in an active Agora Conversational AI session. Every audience receives the root-cause guardrail.

## Evidence-backed recovery

- An incident's initial recovery criteria automatically become a pending recovery check.
- Passed checks require evidence or artifact IDs belonging to that incident.
- Readiness remains false while criteria fail or remain pending, actions are incomplete, or high-priority unknowns remain open.
- Readiness is advisory; resolving the incident requires an explicit request by a commander or administrator.
- Resolution records the human identity and note in the timeline.

## Decision audit, replay, and analytics

- The decision audit joins classified decisions, human approval outcomes, and external tool executions.
- Replay emits ordered timeline events with stable sequence numbers and offsets from incident declaration.
- Analytics include elapsed time, evidence classification mix, average confidence, action completion and overdue counts, open unknowns, decisions, approvals, and timeline volume.
- All data contracts are UI-neutral so the command-center theme can be applied later without changing the engine.

## Final summary, postmortem, and memory

Resolution automatically creates two draft reports: a final incident summary and a postmortem. They contain impact, confirmed facts, hypotheses, decisions, actions, full timeline, recovery verification, analytics, unresolved risks, and guarded root-cause state. The postmortem adds structured learning prompts without inventing lessons.

Reports remain drafts until a commander or administrator explicitly finalizes them. Resolution also indexes the incident in historical memory for similar-incident retrieval while preserving any existing human-confirmed root cause.

## Main APIs

- `PATCH /api/incidents/{id}/actions/{action_id}`
- `POST /api/incidents/{id}/actions/escalate`
- `POST/GET /api/incidents/{id}/briefings`
- `POST/GET /api/incidents/{id}/recovery/checks`
- `PATCH /api/incidents/{id}/recovery/checks/{check_id}`
- `GET /api/incidents/{id}/recovery/readiness`
- `POST /api/incidents/{id}/resolve`
- `GET /api/incidents/{id}/decision-audit`
- `GET /api/incidents/{id}/replay`
- `GET /api/incidents/{id}/analytics`
- `POST/GET /api/incidents/{id}/reports`
- `POST /api/incidents/{id}/reports/{report_id}/finalize`

## Payment-outage acceptance behavior

For the payment outage, ORBIT escalates overdue payment-owner actions; prepares engineering, support, executive, and commander briefings; speaks an approved briefing into the Agora room; requires evidence that payment success rate, latency, and queue health meet recovery criteria; refuses resolution while blockers remain; records the commander's recovery confirmation; creates the final summary and postmortem drafts; preserves remaining risks; and indexes the resolved incident for future retrieval without inventing a root cause.
