# ORBIT Phase 0: Product Contract

## Product

**ORBIT — Operational Response & Briefing Intelligence Team** is a real-time AI Incident Commander for operational and technical incident rooms. It joins an Agora-powered voice room, organizes evidence into a continuously updated Incident Digital Twin, and keeps people aligned without claiming an unverified root cause.

## Product outcome

ORBIT is a real incident-operations product. The payment-outage flow is its first end-to-end acceptance scenario, built on persistent data, authenticated users, real-time events, and integration-ready services. By the end of the prototype round, a team can run that scenario in a live voice room and see ORBIT:

1. recognize the participants and their roles;
2. capture confirmed facts, hypotheses, decisions, and action items;
3. show evidence source and confidence;
4. flag a contradiction and a missing piece of information;
5. assign and follow up on a task;
6. speak a concise status briefing;
7. request human approval before a critical action;
8. verify recovery and produce a final summary with unresolved risks.

## Primary users

| User | Needs from ORBIT |
|---|---|
| Incident Commander | A trusted live picture, clear decisions, owners, and risk visibility. |
| Backend Engineer | Fast capture of technical facts, hypotheses, logs, and assigned investigations. |
| DevOps / SRE | Monitoring context, conflicting-evidence visibility, and safe action approval. |
| Support Lead | A concise customer-impact briefing and next update time. |
| Business Stakeholder | A non-technical status summary without unsupported root-cause claims. |

## First end-to-end acceptance scenario: payment outage

| Time | Speaker / event | ORBIT response |
|---|---|---|
| 14:31 | Backend Engineer: “Payment API failures began around 14:31.” | Creates a **confirmed fact** and timeline event with source. |
| 14:32 | Support Lead: “Customers report checkout failures in India.” | Records customer impact and opens an affected-region question. |
| 14:33 | DevOps: “The DB connection pool may be exhausted.” | Records an **unconfirmed hypothesis**, not a root cause. |
| 14:34 | Monitoring tool: DB saturation is normal. | Links evidence, flags the DB hypothesis as unsupported, and marks a contradiction. |
| 14:35 | Incident Commander: “Fuzail, inspect payment-gateway logs.” | Creates a task assigned to Fuzail and begins follow-up tracking. |
| 14:37 | ORBIT | Speaks: “Payment failures are confirmed. Database saturation is not supported by current metrics. Gateway investigation is open with Fuzail. Root cause is not confirmed.” |
| 14:40 | Engineer proposes traffic failover. | Shows an approval request before any critical execution. |
| 14:45 | Human approves; monitoring recovers. | Records the decision, verifies recovery criteria, and updates status. |
| Close | Incident Commander ends the room. | Generates final summary, decision log, actions, and unresolved risks. |

## Incident Digital Twin: minimum state

```text
Incident
  id, title, service, severity, status, createdAt, commanderId
  customerImpact, affectedRegions, recoveryCriteria

Participant
  id, name, role, roomId, speakingState

EvidenceItem
  id, type, claim, classification, confidence, source, timestamp
  status: confirmed | hypothesis | contradicted | superseded

TimelineEvent
  id, timestamp, eventType, summary, evidenceIds, actorId

ActionItem
  id, task, ownerId, status, createdAt, dueAt, escalationLevel

Decision
  id, statement, approverId, approvalStatus, rationale, timestamp

Risk / Unknown
  id, description, severity, ownerId, status, relatedEvidenceIds
```

## MVP acceptance checklist

| Requirement | Demo proof |
|---|---|
| Live team voice room | At least three people plus ORBIT in an Agora room. |
| Participant-role recognition | Visible participant list with Backend, DevOps, Support, and Commander roles. |
| Classification | Live cards for fact, hypothesis, decision, and action. |
| Ownership and follow-up | Assigned gateway-log task with owner and open status. |
| Missing/conflicting information | DB hypothesis is challenged by monitoring evidence; an unknown is shown. |
| Continuous timeline | Every voice/tool event appears in chronological order. |
| Integrations | Tool-call panel demonstrates monitoring, Jira, Slack, and PagerDuty paths. |
| Spoken summary | ORBIT delivers the 14:37 briefing in the room. |
| Human confirmation | Failover action is blocked until approval. |
| Final summary | Recovery status, decisions, open tasks, and unresolved risks are exported. |

## Production direction and sprint boundaries

The sprint delivers a production-oriented vertical slice, not a throwaway demo. Core components must have stable APIs, persistent incident records, authenticated role-based access, WebSocket reconnection handling, structured audit logs, and deployable configuration. Where external credentials are unavailable, a sandbox connector may be used, but it must implement the same tool interface as the real Jira, Slack, PagerDuty, or monitoring connector.

ORBIT can recommend and organize; humans confirm critical actions and root-cause conclusions.

## Non-negotiable engineering standards

- **API-first services:** typed contracts for incident state, evidence, tasks, decisions, and integrations.
- **Persistent state:** PostgreSQL-backed records; no browser-only incident state.
- **Real-time reliability:** WebSocket reconnect, ordered event IDs, and idempotent updates.
- **Security:** authenticated users, role-based access control, encrypted secrets, and scoped integration permissions.
- **Auditability:** immutable events for tool calls, approvals, decisions, and state transitions.
- **Observability:** structured logs, error tracking, health endpoints, and basic latency/error metrics.
- **Deployment readiness:** environment-based configuration, containerized services, migrations, and a reproducible setup guide.

## Priority sequence

**Must build:** live Agora room, Digital Twin, real-time timeline, extraction/classification, task ownership, conflict/missing-info detection, spoken briefing, approval gate, final summary.

**Should build:** monitoring evidence feed, Jira/Slack/PagerDuty tool calls, provenance/confidence, WebSocket command center, role-based access.

**Differentiators:** evidence graph, RAG + runbooks, historical-incident memory, anomaly correlation, blast radius, severity prediction, multimodal analysis, replay, analytics, and automatic postmortem.

## Mentor questions

1. Which Agora Conversational AI integration path best supports a multi-participant incident-room agent and barge-in?
2. What is the simplest production-sound architecture for streaming speech, structured events, and spoken summaries within the sprint?
3. Which integration should be demonstrated live versus transparently mocked for the strongest evaluation outcome?
4. What reliability, latency, and failure-handling details will judges expect in the prototype demo?
