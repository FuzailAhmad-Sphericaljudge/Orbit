import httpx

from .base import ToolResult


class SlackConnector:
    supported_operations = ["post_message"]

    def __init__(self, token: str, default_channel: str, timeout: float):
        self.token, self.default_channel, self.timeout = token, default_channel, timeout

    @property
    def configured(self) -> bool:
        return bool(self.token and self.default_channel)

    async def execute(self, operation: str, payload: dict) -> ToolResult:
        if operation != "post_message":
            raise ValueError(f"Unsupported Slack operation: {operation}")
        body = build_post_message(payload, self.default_channel)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self.token}"},
                json=body,
            )
            response.raise_for_status()
            data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack rejected the request: {data.get('error', 'unknown_error')}")
        return ToolResult(external_id=data.get("ts"), data={"channel": data.get("channel"), "timestamp": data.get("ts")})


def build_post_message(payload: dict, default_channel: str) -> dict:
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("Slack message text is required")
    return {"channel": payload.get("channel") or default_channel, "text": text}
