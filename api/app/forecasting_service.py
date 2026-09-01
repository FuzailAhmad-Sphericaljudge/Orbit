from sqlalchemy import select
from sqlalchemy.orm import Session

from .forecasting import FORECAST_GUARDRAIL, build_prediction, simulate
from .investigation import text_embedding
from .memory_search import nearest_memories
from .models import EvidenceItem, ForecastEvaluation, Incident, IncidentMemory, PredictionRun, SimulationRun
from .production_learning import build_learned_prior


def learned_prior_for_incident(db: Session, incident: Incident) -> dict:
    evidence = list(db.scalars(select(EvidenceItem).where(EvidenceItem.incident_id == incident.id)))
    query = " ".join([incident.title, incident.service, *[item.claim for item in evidence[-30:]]])
    nearest = nearest_memories(db, text_embedding(query), incident.id, 8)
    candidates = []
    for memory, similarity in nearest:
        historical_incident = db.get(Incident, memory.incident_id)
        if not historical_incident:
            continue
        evaluations = list(db.scalars(select(ForecastEvaluation).where(ForecastEvaluation.incident_id == memory.incident_id)))
        outcomes = [outcome for item in evaluations for outcome in item.outcome.get("metrics", [])]
        actual_rate = sum(bool(item.get("actual_breach")) for item in outcomes) / len(outcomes) * 100 if outcomes else None
        candidates.append({"incident_id": memory.incident_id, "similarity": round(similarity, 4), "severity": historical_incident.severity, "resolution": memory.resolution, "evaluation_count": len(evaluations), "actual_breach_rate": round(actual_rate, 1) if actual_rate is not None else None, "mean_brier_score": round(sum(item.brier_score for item in evaluations) / len(evaluations), 4) if evaluations else .5})
    for item in candidates:
        if item["actual_breach_rate"] is None:
            item.pop("actual_breach_rate")
    prior = build_learned_prior(candidates)
    prior["memory_ids"] = [memory.id for memory, _ in nearest]
    return prior


def run_prediction(db: Session, incident: Incident, request: dict, user_id: str) -> PredictionRun:
    evidence = list(db.scalars(select(EvidenceItem).where(EvidenceItem.incident_id == incident.id)))
    evidence_ids = [item.id for item in evidence]
    historical_prior = learned_prior_for_incident(db, incident)
    memory_ids = historical_prior.pop("memory_ids", [])
    result = build_prediction(request.get("observations", []), request.get("dependency_map", {}), request.get("regions", []), request["horizon_minutes"], historical_prior)
    confidence_values = [item["confidence"] for item in result["metric_forecasts"]]
    limitations = ["Forecast quality depends on representative time-series history and current service topology.", "Geographic exposure is an estimate derived from supplied traffic and customer distribution.", "Correlation and propagation likelihood do not prove root cause."]
    record = PredictionRun(incident_id=incident.id, horizon_minutes=request["horizon_minutes"], input_snapshot=request, forecast={key: value for key, value in result.items() if key not in {"graphs", "geospatial"}}, graphs=result["graphs"], geospatial=result["geospatial"], provenance=evidence_ids + memory_ids, limitations=limitations + (["Limited observations reduced forecast confidence."] if not confidence_values or sum(confidence_values) / len(confidence_values) < 55 else []), created_by=user_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def run_simulation(db: Session, incident: Incident, request: dict, user_id: str) -> SimulationRun:
    prediction = db.get(PredictionRun, request.get("prediction_run_id")) if request.get("prediction_run_id") else db.scalar(select(PredictionRun).where(PredictionRun.incident_id == incident.id).order_by(PredictionRun.created_at.desc()))
    if not prediction or prediction.incident_id != incident.id:
        raise ValueError("A prediction run for this incident is required before simulation.")
    result = simulate(prediction.forecast, request.get("intervention", {}), request.get("assumptions", {}), request["iterations"], f"{incident.id}:{request['name']}:{prediction.id}")
    record = SimulationRun(incident_id=incident.id, prediction_run_id=prediction.id, name=request["name"], iterations=request["iterations"], scenario={"intervention": request.get("intervention", {}), "assumptions": request.get("assumptions", {}), "guardrail": FORECAST_GUARDRAIL}, result=result, created_by=user_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
