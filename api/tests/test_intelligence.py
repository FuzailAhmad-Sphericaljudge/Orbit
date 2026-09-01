import unittest
from app.intelligence import build_status_briefing, classify_turn, detect_findings, extract_action
from app.models import EvidenceClassification, FindingType


class IntelligenceTests(unittest.TestCase):
    def test_hypothesis_is_not_promoted_to_fact(self):
        result = classify_turn("I think the database connection pool may be exhausted")
        self.assertEqual(result.classification, EvidenceClassification.hypothesis)
        self.assertLess(result.confidence, 80)

    def test_action_owner_is_extracted(self):
        result = extract_action("Fuzail, inspect the payment gateway logs.")
        self.assertEqual(result, ("Fuzail", "inspect the payment gateway logs"))

    def test_conflicting_metric_statement_is_flagged(self):
        findings = detect_findings(["Database saturation is high"], "Database saturation is normal")
        self.assertTrue(any(item.finding_type == FindingType.contradiction for item in findings))

    def test_briefing_preserves_root_cause_guardrail(self):
        briefing = build_status_briefing(["Payment failures are confirmed"], ["Gateway latency may be elevated"], ["Fuzail: inspect logs"], [])
        self.assertIn("No root cause is confirmed", briefing)


if __name__ == "__main__":
    unittest.main()
