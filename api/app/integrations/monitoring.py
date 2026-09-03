import httpx

from .base import ToolResult


class MonitoringConnector:
    supported_operations = ["query_snapshot", "query_range"]

    def __init__(self, webhook_url: str, token: str, prometheus_base_url: str, prometheus_username: str, prometheus_bearer_token: str, timeout: float):
        self.webhook_url, self.token, self.prometheus_base_url = webhook_url, token, prometheus_base_url.rstrip("/")
        self.prometheus_username, self.prometheus_bearer_token, self.timeout = prometheus_username, prometheus_bearer_token, timeout

    @property
    def configured(self) -> bool:
        return bool(self.webhook_url or (self.prometheus_base_url and self.prometheus_username and self.prometheus_bearer_token))

    async def execute(self, operation: str, payload: dict) -> ToolResult:
        if operation not in self.supported_operations:
            raise ValueError(f"Unsupported monitoring operation: {operation}")
        if self.prometheus_base_url:
            query = payload.get("query")
            if not isinstance(query, str) or not query.strip():
                raise ValueError("A PromQL query is required")
            endpoint = f"{self.prometheus_base_url}/api/v1/{'query_range' if operation == 'query_range' else 'query'}"
            params = {key: value for key, value in payload.items() if key in {"query", "start", "end", "step"}}
            async with httpx.AsyncClient(timeout=self.timeout, auth=(self.prometheus_username, self.prometheus_bearer_token)) as client:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                data = response.json()
            if data.get("status") != "success":
                raise ValueError("Prometheus did not return a successful query result")
            return ToolResult(external_id=f"prometheus:{operation}", data={"status": data.get("status"), "data": data.get("data", {})})
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.webhook_url, headers=headers, json={"operation": operation, "payload": payload})
            response.raise_for_status()
            data = response.json()
        return ToolResult(external_id=str(data.get("snapshot_id")) if data.get("snapshot_id") else None, data=data)
