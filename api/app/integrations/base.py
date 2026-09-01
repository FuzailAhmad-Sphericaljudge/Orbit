from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ToolResult:
    external_id: str | None = None
    data: dict = field(default_factory=dict)


class Connector(Protocol):
    @property
    def configured(self) -> bool: ...

    @property
    def supported_operations(self) -> list[str]: ...

    async def execute(self, operation: str, payload: dict) -> ToolResult: ...
