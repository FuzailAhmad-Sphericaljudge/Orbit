import unittest

from app.investigation import (analyze_artifact_text, contradiction_pairs, correlate_anomalies,
                               cosine_similarity, derive_unknowns, estimate_blast_radius,
                               predict_severity, text_embedding)


class InvestigationTests(unittest.TestCase):
    def test_embedding_is_deterministic(self):
        first = text_embedding("payment gateway timeout")
        second = text_embedding("payment gateway timeout")
        self.assertEqual(first, second)
        self.assertAlmostEqual(cosine_similarity(first, second), 1.0)

    def test_contradiction_pair_preserves_both_sources(self):
        pairs = contradiction_pairs([
            {"id": "a", "claim": "Payment gateway latency is high"},
            {"id": "b", "claim": "Payment gateway latency is normal"},
        ])
        self.assertEqual(pairs[0]["left_id"], "a")
        self.assertEqual(pairs[0]["right_id"], "b")

    def test_unknown_engine_requests_recovery_criteria(self):
        unknowns = derive_unknowns(["Payments are failing"], None, [], None)
        self.assertTrue(any(item.normalized_key == "recovery-criteria" for item in unknowns))

    def test_anomaly_correlation_uses_baseline_deviation(self):
        result = correlate_anomalies([{"name": "error_rate", "current": 12, "baseline": 2, "standard_deviation": 2, "service": "payments", "region": "us-east"}])
        self.assertEqual(result["anomaly_count"], 1)
        self.assertEqual(result["anomalies"][0]["z_score"], 5.0)

    def test_blast_radius_follows_dependencies(self):
        result = estimate_blast_radius(["payments"], {"payments": ["checkout"], "checkout": ["orders"]}, ["us-east"])
        self.assertEqual(result["potentially_affected"], ["checkout", "orders"])

    def test_severity_is_advisory(self):
        result = predict_severity(75, 200_000, 3, True)
        self.assertEqual(result["suggested_severity"], "SEV1")
        self.assertTrue(result["advisory_only"])

    def test_artifact_without_text_requests_processor(self):
        result = analyze_artifact_text("screenshot", None)
        self.assertEqual(result["status"], "needs_processor")


if __name__ == "__main__":
    unittest.main()
