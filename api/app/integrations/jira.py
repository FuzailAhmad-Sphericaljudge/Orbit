import httpx

from .base import ToolResult


class JiraConnector:
    supported_operations = ["create_issue"]

    def __init__(self, base_url: str, email: str, token: str, project_key: str, issue_type: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.email, self.token, self.project_key = email, token, project_key
        self.issue_type, self.timeout = issue_type, timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.email and self.token and self.project_key)

    async def execute(self, operation: str, payload: dict) -> ToolResult:
        if operation != "create_issue":
            raise ValueError(f"Unsupported Jira operation: {operation}")
        body = build_create_issue(payload, self.project_key, self.issue_type)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/rest/api/3/issue",
                auth=(self.email, self.token),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=body,
            )
            response.raise_for_status()
            data = response.json()
        return ToolResult(external_id=data.get("key") or data.get("id"), data={"id": data.get("id"), "key": data.get("key"), "self": data.get("self")})


def build_create_issue(payload: dict, project_key: str, issue_type: str) -> dict:
    summary = str(payload.get("summary", "")).strip()
    if not summary:
        raise ValueError("Jira issue summary is required")
    description = str(payload.get("description", "")).strip()
    return {"fields": {
        "project": {"key": payload.get("project_key") or project_key},
        "summary": summary,
        "issuetype": {"name": payload.get("issue_type") or issue_type},
        "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description or summary}]}]},
    }}
