import unittest

from app.integrations.jira import build_create_issue
from app.integrations.pagerduty import build_create_incident, build_resolve_incident
from app.integrations.slack import build_post_message
from app.models import IntegrationProvider, RiskLevel
from app.tool_policy import effective_risk, sanitized_payload


class IntegrationPayloadTests(unittest.TestCase):
    def test_slack_payload_uses_default_channel(self):
        self.assertEqual(build_post_message({"text": "SEV1 update"}, "C123"), {"channel": "C123", "text": "SEV1 update"})

    def test_slack_payload_requires_text(self):
        with self.assertRaises(ValueError):
            build_post_message({}, "C123")

    def test_jira_payload_uses_adf_description(self):
        body = build_create_issue({"summary": "Verify payment recovery", "description": "Check success rate for 15 minutes."}, "OPS", "Task")
        self.assertEqual(body["fields"]["project"]["key"], "OPS")
        self.assertEqual(body["fields"]["description"]["type"], "doc")
        self.assertEqual(body["fields"]["description"]["version"], 1)

    def test_pagerduty_payload_has_service_reference(self):
        body = build_create_incident({"title": "Payment outage", "details": "Elevated checkout failures"}, "P123")
        self.assertEqual(body["incident"]["type"], "incident")
        self.assertEqual(body["incident"]["service"], {"id": "P123", "type": "service_reference"})
        self.assertEqual(body["incident"]["urgency"], "high")

    def test_pagerduty_risk_cannot_be_downgraded(self):
        self.assertEqual(effective_risk(IntegrationProvider.pagerduty, "create_incident", RiskLevel.low), RiskLevel.high)

    def test_pagerduty_resolution_is_high_risk_and_sanitized(self):
        self.assertEqual(build_resolve_incident(), {"incident": {"type": "incident", "status": "resolved"}})
        self.assertEqual(effective_risk(IntegrationProvider.pagerduty, "resolve_incident", RiskLevel.low), RiskLevel.high)
        self.assertEqual(sanitized_payload(IntegrationProvider.pagerduty, "resolve_incident", {"incident_id": "P123"}), {"incident_id": "P123"})

    def test_unknown_fields_are_rejected_before_persistence(self):
        with self.assertRaises(ValueError):
            sanitized_payload(IntegrationProvider.slack, "post_message", {"text": "Update", "bot_token": "must-not-be-stored"})


if __name__ == "__main__":
    unittest.main()
