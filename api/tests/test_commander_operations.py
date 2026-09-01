import unittest
from datetime import datetime, timedelta, timezone

from app.commander_operations import (incident_analytics, recovery_readiness, replay_events,
                                      required_escalation_level, role_briefing)


class CommanderOperationsTests(unittest.TestCase):
    def test_action_escalation_uses_overdue_thresholds(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(required_escalation_level(now - timedelta(minutes=31), now, [1, 15, 30]), 3)
        self.assertEqual(required_escalation_level(now + timedelta(minutes=5), now, [1, 15, 30]), 0)

    def test_recovery_requires_passed_checks_and_no_blockers(self):
        result = recovery_readiness([{"criterion": "error rate normal", "status": "passed"}], [], [])
        self.assertTrue(result["ready"])
        blocked = recovery_readiness([{"criterion": "latency normal", "status": "failed"}], [], [])
        self.assertFalse(blocked["ready"])

    def test_engineering_briefing_keeps_root_cause_guardrail(self):
        message = role_briefing("engineering", {"severity": "SEV1", "service": "payments", "status": "monitoring"}, [], ["database issue"], [], [], [], {"ready": False})
        self.assertIn("not confirmed causes", message)
        self.assertIn("human incident commander", message)

    def test_replay_has_stable_sequence_and_offsets(self):
        start = datetime.now(timezone.utc)
        events = replay_events([{"id": "a", "created_at": start}, {"id": "b", "created_at": start + timedelta(seconds=4)}])
        self.assertEqual(events[1]["sequence"], 2)
        self.assertEqual(events[1]["offset_seconds"], 4)

    def test_analytics_counts_completed_actions(self):
        now = datetime.now(timezone.utc)
        data = incident_analytics(now, now, [], [{"status": "complete", "overdue": False}], [], [], [], 2)
        self.assertEqual(data["action_completion_percent"], 100)


if __name__ == "__main__":
    unittest.main()
