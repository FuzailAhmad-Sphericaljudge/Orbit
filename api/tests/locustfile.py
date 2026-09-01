import uuid

from locust import HttpUser, between, task


class OrbitUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        self.headers = {"X-User-Id": f"load-{uuid.uuid4()}", "X-User-Role": "observer"}
        response = self.client.get("/api/incidents", headers=self.headers)
        incidents = response.json() if response.ok else []
        self.incident_id = incidents[0]["id"] if incidents else None

    @task(5)
    def health(self):
        self.client.get("/health")

    @task(3)
    def incidents(self):
        self.client.get("/api/incidents", headers=self.headers)

    @task(2)
    def readiness(self):
        self.client.get("/ready")

    @task(4)
    def command_center(self):
        if self.incident_id:
            self.client.get(f"/api/incidents/{self.incident_id}/command-center", headers=self.headers)

    @task(3)
    def telemetry_window(self):
        if self.incident_id:
            self.client.get(f"/api/incidents/{self.incident_id}/telemetry?limit=100", headers=self.headers)

    @task(2)
    def learning_status(self):
        if self.incident_id:
            self.client.get(f"/api/incidents/{self.incident_id}/production-learning", headers=self.headers)
