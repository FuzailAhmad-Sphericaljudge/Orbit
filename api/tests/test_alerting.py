import unittest

from app.alerting import alert_key, service_from_labels, severity_from_labels


class AlertingTests(unittest.TestCase):
    def test_fingerprint_is_preferred_as_the_stable_key(self):
        self.assertEqual(alert_key({"fingerprint": "abc123"}, {"job": "orbit_api"}), "abc123")

    def test_label_fingerprint_is_stable_when_label_order_changes(self):
        self.assertEqual(alert_key({}, {"job": "orbit_api", "severity": "critical"}), alert_key({}, {"severity": "critical", "job": "orbit_api"}))

    def test_job_label_maps_to_the_orbit_service_name(self):
        self.assertEqual(service_from_labels({"job": "orbit_api"}), "orbit-api")

    def test_service_and_severity_labels_are_preserved(self):
        self.assertEqual(service_from_labels({"service": "payments-api", "job": "ignored"}), "payments-api")
        self.assertEqual(severity_from_labels({"severity": "critical"}), "SEV1")


if __name__ == "__main__":
    unittest.main()
