import httpx

from .base import ToolResult


class MonitoringConnector:
    supported_operations = ["query_snapshot", "query_range"]

    def __init__(self, webhook_url: str, token: str, timeout: float):
        self.webhook_url, self.token, self.timeout = webhook_url, token, timeout

    @property
    def configured(self) -> bool:
        return bool(self.webhook_url)

    async def execute(self, operation: str, payload: dict) -> ToolResult:
        if operation not in self.supported_operations:
            raise ValueError(f"Unsupported monitoring operation: {operation}")
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.webhook_url, headers=headers, json={"operation": operation, "payload": payload})
            response.raise_for_status()
            data = response.json()
        return ToolResult(external_id=str(data.get("snapshot_id")) if data.get("snapshot_id") else None, data=data)
