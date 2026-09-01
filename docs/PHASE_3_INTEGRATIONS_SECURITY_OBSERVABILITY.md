# Phase 3 — Safe Tool Execution, Security, and Observability

Phase 3 turns ORBIT's recommendations into controlled production actions. The AI can prepare tool calls, but it cannot silently perform critical changes.

## Integration gateway

| Provider | Operation | Required configuration |
|---|---|---|
| Slack | `post_message` | Bot token and default channel |
| Jira Cloud | `create_issue` | Site URL, user email, API token, project key |
| PagerDuty | `create_incident` | API token, valid account email, service ID |
| Monitoring | `query_snapshot` | Fixed server-side webhook URL and optional token |

Each connector uses a bounded timeout, validates its operation, keeps credentials server-side, and returns only the external identifiers needed for the audit trail.
Payloads are allow-listed per operation so credentials or unexpected fields cannot be persisted accidentally. PagerDuty incident creation is always treated as at least high risk, even if a caller requests a lower classification.

## Approval-gated execution

1. An operator prepares a call through `POST /api/incidents/{incident_id}/tools/prepare`.
2. ORBIT stores the exact provider, operation, sanitized request, requester, risk, rationale, and idempotency key.
3. `high` and `critical` requests automatically enter `awaiting_approval` and create an approval record.
4. A commander, approver, or administrator must approve the request using the approval endpoint.
5. An operator then executes the stored call. ORBIT refuses pending or rejected requests.
6. The result is recorded once, published over WebSocket, counted in metrics, and appended to the incident timeline.

Repeated calls with the same idempotency key return the original record. A successfully executed record cannot be sent again.

## Role-based access

- `observer`: read integration status and execution history.
- `operator`: prepare and execute permitted tool calls.
- `commander`: operator permissions plus human approval decisions.
- `approver`: approval decisions.
- `admin`: all Phase 3 operations.

Production requests use an HS256 bearer JWT with validated issuer and audience. Development supports explicit `X-User-ID` and `X-User-Role` headers so the flow can be tested locally. This fallback is disabled outside the development environment.

## Operational visibility

- JSON application logs.
- `x-request-id` propagation on API responses.
- Prometheus metrics at `/metrics` for request rate, latency, and tool outcomes.
- Incident-scoped WebSocket events for prepared and completed tool calls.
- Immutable incident timeline entries for preparation, approval, success, and failure.

## Local validation example

Use development identity headers without placing production credentials in requests:

```text
X-User-ID: fuzail
X-User-Role: commander
```

Set real integration secrets only in `api/.env` or a deployment secret manager. Never commit that file or paste tokens into chat.

## Next hardening phase

Before a shared production deployment, add asymmetric/OIDC authentication, Alembic migrations, encrypted secret management, connector retry queues, Redis-backed distributed locks, webhook signature verification, WebSocket authorization, and end-to-end staging tests with sandbox integration accounts.
