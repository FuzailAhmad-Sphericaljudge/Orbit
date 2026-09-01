from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy.orm import Session

from .models import AgentName, AgentRun


@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    responsibility: str
    may_execute_external_actions: bool = False


AGENT_CATALOG = {
    AgentName.commander: AgentSpec(AgentName.commander, "Coordinates specialist outputs and preserves human authority"),
    AgentName.listener: AgentSpec(AgentName.listener, "Consumes Agora speech and preserves speaker/role provenance"),
    AgentName.evidence: AgentSpec(AgentName.evidence, "Builds evidence and provenance graph records"),
    AgentName.conflict: AgentSpec(AgentName.conflict, "Detects contradictions and missing information"),
    AgentName.timeline: AgentSpec(AgentName.timeline, "Maintains chronological incident state"),
    AgentName.action: AgentSpec(AgentName.action, "Tracks ownership, aging, and completion"),
    AgentName.investigation: AgentSpec(AgentName.investigation, "Correlates anomalies and retrieves relevant knowledge"),
    AgentName.integration: AgentSpec(AgentName.integration, "Prepares approval-gated tool calls", may_execute_external_actions=True),
}


class RecordedAgentRun:
    def __init__(self, db: Session, incident_id: str, agent_name: AgentName, inputs: list[str] | None = None):
        self.db = db
        self.started = perf_counter()
        self.record = AgentRun(incident_id=incident_id, agent_name=agent_name, input_references=inputs or [])
        db.add(self.record)
        db.flush()

    def complete(self, outputs: list[str] | None = None) -> AgentRun:
        self.record.status = "completed"
        self.record.output_references = outputs or []
        self.record.latency_ms = round((perf_counter() - self.started) * 1000, 2)
        self.record.completed_at = datetime.now(timezone.utc)
        self.db.flush()
        return self.record

    def fail(self, error: Exception) -> AgentRun:
        self.record.status = "failed"
        self.record.error_message = str(error)[:2000]
        self.record.latency_ms = round((perf_counter() - self.started) * 1000, 2)
        self.record.completed_at = datetime.now(timezone.utc)
        self.db.flush()
        return self.record
