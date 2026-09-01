from sqlalchemy import select
from sqlalchemy.orm import Session

from .investigation import cosine_similarity
from .models import IncidentMemory


def nearest_memories(db: Session, embedding: list[float], exclude_incident_id: str, limit: int = 5) -> list[tuple[IncidentMemory, float]]:
    limit = max(1, min(limit, 20))
    if db.bind and db.bind.dialect.name == "postgresql":
        distance = IncidentMemory.embedding.op("<=>")(embedding)
        rows = db.execute(
            select(IncidentMemory, distance.label("distance"))
            .where(IncidentMemory.incident_id != exclude_incident_id)
            .order_by(distance)
            .limit(limit)
        )
        return [(memory, round(max(0.0, 1.0 - float(raw_distance)), 4)) for memory, raw_distance in rows]
    memories = list(db.scalars(select(IncidentMemory).where(IncidentMemory.incident_id != exclude_incident_id)))
    ranked = [(memory, round(max(0.0, cosine_similarity(embedding, memory.embedding)), 4)) for memory in memories]
    return sorted(ranked, key=lambda item: item[1], reverse=True)[:limit]
