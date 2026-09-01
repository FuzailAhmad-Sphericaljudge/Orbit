import httpx

from .base import ToolResult


class PagerDutyConnector:
    supported_operations = ["create_incident", "resolve_incident"]

    def __init__(self, token: str, from_email: str, service_id: str, timeout: float):
        self.token, self.from_email, self.service_id, self.timeout = token, from_email, service_id, timeout

    @property
    def configured(self) -> bool:
        return bool(self.token and self.from_email and self.service_id)

    async def execute(self, operation: str, payload: dict) -> ToolResult:
        if operation == "create_incident":
            return await self._create(payload)
        if operation == "resolve_incident":
            return await self._resolve(payload)
        raise ValueError(f"Unsupported PagerDuty operation: {operation}")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token token={self.token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
            "From": self.from_email,
        }

    async def _create(self, payload: dict) -> ToolResult:
        body = build_create_incident(payload, self.service_id)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.pagerduty.com/incidents",
                headers=self._headers(),
                json=body,
            )
            response.raise_for_status()
            data = response.json().get("incident", {})
        return ToolResult(external_id=data.get("id"), data={"id": data.get("id"), "incident_number": data.get("incident_number"), "html_url": data.get("html_url")})

    async def _resolve(self, payload: dict) -> ToolResult:
        incident_id = str(payload.get("incident_id", "")).strip()
        if not incident_id:
            raise ValueError("PagerDuty incident_id is required")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(
                f"https://api.pagerduty.com/incidents/{incident_id}",
                headers=self._headers(),
                json=build_resolve_incident(),
            )
            response.raise_for_status()
            data = response.json().get("incident", {})
        return ToolResult(external_id=data.get("id"), data={"id": data.get("id"), "status": data.get("status"), "html_url": data.get("html_url")})


def build_create_incident(payload: dict, service_id: str) -> dict:
    title = str(payload.get("title", "")).strip()
    if not title:
        raise ValueError("PagerDuty incident title is required")
    details = str(payload.get("details", "")).strip()
    return {"incident": {
        "type": "incident",
        "title": title,
        "service": {"id": payload.get("service_id") or service_id, "type": "service_reference"},
        "urgency": payload.get("urgency", "high"),
        "body": {"type": "incident_body", "details": details or title},
    }}


def build_resolve_incident() -> dict:
    return {"incident": {"type": "incident", "status": "resolved"}}
