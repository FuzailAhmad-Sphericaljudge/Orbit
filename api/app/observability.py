import json
import logging
import time
import uuid

from fastapi import Request
from prometheus_client import Counter, Histogram, make_asgi_app


REQUESTS = Counter("orbit_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("orbit_http_request_duration_seconds", "HTTP request latency", ["method", "path"])
TOOL_CALLS = Counter("orbit_tool_executions_total", "External tool executions", ["provider", "operation", "status"])
INVESTIGATION_RUNS = Counter("orbit_investigation_runs_total", "Agentic investigation runs", ["status"])
ACTION_ESCALATIONS = Counter("orbit_action_escalations_total", "Action escalations", ["level"])
BRIEFINGS = Counter("orbit_briefings_total", "Generated role briefings", ["audience", "spoken"])
REPORTS = Counter("orbit_incident_reports_total", "Generated incident reports", ["type", "status"])
RECOVERIES = Counter("orbit_recoveries_total", "Human-confirmed incident recoveries")
TELEMETRY_INGESTED = Counter("orbit_telemetry_observations_total", "Telemetry observations ingested", ["source"])
EARLY_WARNINGS = Counter("orbit_early_warnings_total", "Predictive early warnings", ["service", "metric"])
FORECAST_EVALUATIONS = Counter("orbit_forecast_evaluations_total", "Forecast evaluations", ["quality", "drift"])
LEARNING_CYCLES = Counter("orbit_production_learning_cycles_total", "Production learning cycles", ["status"])


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


async def metrics_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        status = getattr(locals().get("response"), "status_code", 500)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        REQUESTS.labels(request.method, path, str(status)).inc()
        LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
        if "response" in locals():
            response.headers["x-request-id"] = request_id


metrics_app = make_asgi_app()
