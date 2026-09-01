from sqlalchemy.orm import Session
from .models import TimelineEvent


def add_timeline_event(db: Session, incident_id: str, event_type: str, summary: str, actor_id: str | None = None, payload: dict | None = None) -> TimelineEvent:
    event = TimelineEvent(incident_id=incident_id, event_type=event_type, summary=summary, actor_id=actor_id, payload=payload or {})
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
