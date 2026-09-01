from .models import IntegrationProvider, RiskLevel


_RISK_ORDER = {RiskLevel.low: 0, RiskLevel.medium: 1, RiskLevel.high: 2, RiskLevel.critical: 3}
_MINIMUM_RISK = {
    (IntegrationProvider.slack, "post_message"): RiskLevel.medium,
    (IntegrationProvider.jira, "create_issue"): RiskLevel.medium,
    (IntegrationProvider.pagerduty, "create_incident"): RiskLevel.high,
    (IntegrationProvider.pagerduty, "resolve_incident"): RiskLevel.high,
    (IntegrationProvider.monitoring, "query_snapshot"): RiskLevel.low,
    (IntegrationProvider.monitoring, "query_range"): RiskLevel.low,
}
_ALLOWED_FIELDS = {
    (IntegrationProvider.slack, "post_message"): {"channel", "text"},
    (IntegrationProvider.jira, "create_issue"): {"summary", "description", "project_key", "issue_type"},
    (IntegrationProvider.pagerduty, "create_incident"): {"title", "details", "service_id", "urgency"},
    (IntegrationProvider.pagerduty, "resolve_incident"): {"incident_id"},
    (IntegrationProvider.monitoring, "query_snapshot"): {"query", "metrics", "window", "filters"},
    (IntegrationProvider.monitoring, "query_range"): {"query", "start", "end", "step", "filters"},
}


def effective_risk(provider: IntegrationProvider, operation: str, requested: RiskLevel) -> RiskLevel:
    minimum = _MINIMUM_RISK[(provider, operation)]
    return requested if _RISK_ORDER[requested] >= _RISK_ORDER[minimum] else minimum


def sanitized_payload(provider: IntegrationProvider, operation: str, payload: dict) -> dict:
    allowed = _ALLOWED_FIELDS[(provider, operation)]
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"Unsupported payload fields: {', '.join(sorted(unknown))}")
    return {key: value for key, value in payload.items() if key in allowed}
