# Phase 6 — Production Hardening and Deployment

Phase 6 converts the ORBIT sprint build into a deployable service topology. It adds controlled schema changes, multi-instance coordination, durable background work, authenticated real-time connections, security and retention controls, deployment health gates, verification automation, backups, load testing, and measurable reliability targets.

## Runtime topology

- **API replicas:** FastAPI processes behind the deployment ingress.
- **Worker:** consumes durable Redis Stream jobs independently of API requests.
- **PostgreSQL + pgvector:** authoritative incident state and historical memory.
- **Redis:** distributed locks, rate-limit counters, cross-replica event transport, job stream, retry queue, and dead-letter stream.
- **Static web container:** compiled Vite application served by Nginx. No product theme was changed in this phase.
- **Prometheus:** API and incident-engine metrics with initial SLO alerts.

## Database migrations

Production disables automatic `create_all`. The API image runs `alembic upgrade head` before starting, and CI runs both the upgrade and `alembic check`. The baseline creates the pgvector extension on PostgreSQL and the full ORBIT metadata schema. Every future model change must receive a reviewed Alembic revision.

## Resilience and coordination

- Investigation and resolution use incident-scoped Redis locks with ownership-safe release.
- Development can fall back to in-process locks; production sets `REDIS_REQUIRED=true` and fails closed.
- Redis Pub/Sub distributes incident WebSocket events across API replicas.
- Redis Streams provide acknowledged background jobs, bounded retry attempts, idempotent completion keys, and a dead-letter stream.
- `/ready` checks PostgreSQL and required Redis availability; `/health` remains a lightweight liveness check.

## Authentication and access

- HTTP supports signed local JWTs and optional OIDC/JWKS validation with issuer and audience checks.
- WebSockets require a short-lived access token and reject unknown incidents before accepting.
- Existing RBAC gates remain in force for integrations, approvals, recovery, reporting, and administration.
- Trusted-host validation, bounded request sizes, per-identity rate limits, CORS allowlists, security headers, and HSTS are enabled.

## Secrets and encryption

- Sensitive runtime values can be loaded from Docker/Kubernetes-style mounted secret files.
- The production Compose example mounts database, Redis, JWT, and data-encryption secrets instead of embedding them in YAML.
- Customer impact, recovery criteria, evidence claims, actions, voice transcripts, and artifact contents/URIs use authenticated Fernet encryption before database storage when `DATA_ENCRYPTION_KEY` is configured.
- Integration payload sanitization remains active; secrets must never be included inside action payloads or logs.
- Use TLS for the public ingress and managed database/Redis connections. Encrypt persistent volumes with the deployment platform.

## Retention and recovery

- The admin retention endpoint is dry-run by default.
- Confirmed cleanup applies only to resolved incidents older than `RETENTION_DAYS`.
- Raw transcripts are deleted and artifact text/storage references are redacted; structured audit reports remain.
- Backup and restore PowerShell scripts require explicit database and file paths. Restore also requires `-ConfirmRestore`.
- Test restore operations in an isolated database before approving a production recovery procedure.

## CI and verification

The included GitHub Actions workflow starts pgvector PostgreSQL and Redis, applies migrations, checks schema drift, runs backend tests, builds the web application, and builds all deployment images.

Run focused load testing after installing Locust:

```text
locust -f api/tests/locustfile.py --host http://localhost:8000
```

The initial service objectives are:

- API availability: 99.9% monthly.
- HTTP 5xx rate: below 1% over 10 minutes.
- API p95 latency: below 500 ms over 10 minutes.
- No unacknowledged critical action execution.
- No automated root-cause confirmation.
- Recovery and finalized reports always identify the confirming human.

## Deployment sequence

1. Copy `deploy/.env.production.example` to `deploy/.env` and set public origins/hosts.
2. Create every file described in `deploy/secrets/README.md`.
3. Configure Agora and integration credentials through the deployment secret manager.
4. Start with `docker compose --env-file deploy/.env -f deploy/docker-compose.production.yml up -d --build`.
5. Verify `/health`, `/ready`, Prometheus targets, worker logs, and migration head.
6. Run the payment-outage acceptance scenario and a backup/restore drill before public use.

## Local release preflight

For a free local deployment, run the Docker stack and then execute the PowerShell preflight. It verifies Docker Compose, API liveness/readiness/metrics, the command center, and (when supplied) the live Cloudflare tunnel without printing any credentials:

```text
.\scripts\preflight.ps1 -TunnelUrl https://your-tunnel.trycloudflare.com
```

Create a portable database backup without installing PostgreSQL locally:

```text
.\scripts\backup-docker.ps1
```

## Free HTTPS preview with Cloudflare Quick Tunnel

After the local API is running, open a separate PowerShell window and run:

```text
.\scripts\start-quick-tunnel.ps1
```

Keep that window open. Cloudflare prints a temporary `https://…trycloudflare.com` URL; use
`https://…trycloudflare.com/api/alerts/grafana` as the Grafana webhook endpoint and validate it with:

```text
.\scripts\preflight.ps1 -TunnelUrl https://…trycloudflare.com
```

Quick Tunnels are free for local demonstrations and webhook testing, but their hostname changes on restart and they have no uptime guarantee. They are not a permanent production ingress. A real release needs a named Cloudflare Tunnel or another HTTPS host, a stable domain, and externally managed backups.

Live Agora, Slack, Jira, PagerDuty, monitoring, OIDC, and external multimodal validation still require the team's real credentials and endpoints; the code paths and production controls are ready for them.
