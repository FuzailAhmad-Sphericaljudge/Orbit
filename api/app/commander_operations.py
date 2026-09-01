from collections import Counter
from datetime import datetime, timezone


ROOT_CAUSE_NOTICE = "Root cause is unconfirmed unless explicitly approved by the human incident commander."


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def required_escalation_level(due_at: datetime | None, now: datetime, thresholds_minutes: list[int]) -> int:
    if not due_at:
        return 0
    overdue_minutes = (utc(now) - utc(due_at)).total_seconds() / 60
    if overdue_minutes <= 0:
        return 0
    return sum(overdue_minutes >= threshold for threshold in sorted(set(thresholds_minutes)))


def role_briefing(audience: str, incident: dict, facts: list[str], hypotheses: list[str], decisions: list[str],
                  actions: list[dict], unknowns: list[str], recovery: dict) -> str:
    impact = incident.get("customer_impact") or "Customer impact is still being quantified"
    status = f"{incident['severity']} {incident['service']} incident is {incident['status']}"
    open_actions = [f"{item['owner_id']}: {item['task']}" for item in actions if item.get("status") != "complete"]
    if audience == "engineering":
        parts = [status + ".", "Confirmed signals: " + ("; ".join(facts[:4]) or "none yet") + "."]
        if hypotheses:
            parts.append("Hypotheses to test, not confirmed causes: " + "; ".join(hypotheses[:3]) + ".")
        parts.append("Next technical actions: " + ("; ".join(open_actions[:4]) or "none open") + ".")
    elif audience == "support":
        parts = [status + ".", "Customer-facing impact: " + impact + ".", "Approved known facts: " + ("; ".join(facts[:3]) or "none yet") + "."]
        parts.append("Do not communicate hypotheses as causes.")
    elif audience == "executive":
        parts = [status + ".", "Business impact: " + impact + "."]
        parts.append(f"There are {len(open_actions)} open actions and {len(unknowns)} unresolved questions.")
        parts.append("Recovery readiness: " + ("ready for commander review" if recovery.get("ready") else "not yet verified") + ".")
    else:
        parts = [status + ".", "Impact: " + impact + ".", "Confirmed: " + ("; ".join(facts[:4]) or "none yet") + "."]
        if decisions:
            parts.append("Decisions: " + "; ".join(decisions[-3:]) + ".")
        parts.append("Open actions: " + ("; ".join(open_actions[:4]) or "none") + ".")
        parts.append("Unknowns: " + ("; ".join(unknowns[:3]) or "none") + ".")
    parts.append(ROOT_CAUSE_NOTICE)
    return " ".join(parts)


def recovery_readiness(checks: list[dict], open_actions: list[dict], unknowns: list[dict]) -> dict:
    blockers = []
    if not checks:
        blockers.append("No recovery criteria have been verified")
    blockers.extend(item["criterion"] for item in checks if item.get("status") != "passed")
    blockers.extend(f"Open high-priority question: {item['question']}" for item in unknowns if item.get("status") == "open" and item.get("priority") in {"high", "critical"})
    blocking_actions = [item for item in open_actions if item.get("status") in {"open", "in_progress", "blocked"}]
    blockers.extend(f"Incomplete action: {item['task']} ({item['owner_id']})" for item in blocking_actions)
    passed = sum(item.get("status") == "passed" for item in checks)
    return {
        "ready": not blockers,
        "checks_total": len(checks),
        "checks_passed": passed,
        "blockers": blockers,
        "requires_human_confirmation": True,
    }


def replay_events(events: list[dict]) -> list[dict]:
    if not events:
        return []
    origin = utc(events[0]["created_at"])
    return [{
        "sequence": index + 1,
        "offset_seconds": round((utc(event["created_at"]) - origin).total_seconds(), 3),
        **event,
    } for index, event in enumerate(events)]


def incident_analytics(created_at: datetime, now: datetime, evidence: list[dict], actions: list[dict],
                       unknowns: list[dict], decisions: list[dict], approvals: list[dict], timeline_count: int) -> dict:
    evidence_counts = Counter(item["classification"] for item in evidence)
    action_counts = Counter(item["status"] for item in actions)
    complete = action_counts.get("complete", 0)
    return {
        "elapsed_minutes": round((utc(now) - utc(created_at)).total_seconds() / 60, 1),
        "timeline_events": timeline_count,
        "evidence_by_classification": dict(evidence_counts),
        "confidence_average": round(sum(item["confidence"] for item in evidence) / len(evidence), 1) if evidence else 0,
        "actions": {"total": len(actions), "complete": complete, "overdue": sum(bool(item.get("overdue")) for item in actions), "by_status": dict(action_counts)},
        "action_completion_percent": round(complete * 100 / len(actions), 1) if actions else 100.0,
        "unknowns_open": sum(item.get("status") == "open" for item in unknowns),
        "decisions_recorded": len(decisions),
        "approvals": dict(Counter(item["status"] for item in approvals)),
    }


def report_content(incident: dict, timeline: list[dict], evidence: list[dict], actions: list[dict],
                   unknowns: list[dict], decisions: list[dict], recovery: dict, analytics: dict,
                   root_cause_status: str = "unconfirmed", root_cause: str | None = None) -> dict:
    unresolved_risks = [item["question"] for item in unknowns if item.get("status") == "open"]
    unresolved_risks.extend(f"Incomplete action: {item['task']}" for item in actions if item.get("status") != "complete")
    return {
        "incident": incident,
        "impact": incident.get("customer_impact") or "Not fully quantified",
        "confirmed_facts": [item["claim"] for item in evidence if item["classification"] == "confirmed_fact"],
        "hypotheses": [item["claim"] for item in evidence if item["classification"] == "hypothesis"],
        "decisions": decisions,
        "actions": actions,
        "timeline": timeline,
        "recovery_verification": recovery,
        "analytics": analytics,
        "unresolved_risks": unresolved_risks,
        "root_cause": {"status": root_cause_status, "statement": root_cause if root_cause_status == "confirmed_by_human" else None, "notice": ROOT_CAUSE_NOTICE},
        "follow_up_required": bool(unresolved_risks),
    }
