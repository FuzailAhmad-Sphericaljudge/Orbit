from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .forecasting_service import run_prediction
from .models import ForecastEvaluation, Incident, PredictionRun, TelemetryObservation
from .telemetry_intelligence import calibration_summary, early_warnings, evaluate_prediction, forecast_rows


def _read(item: TelemetryObservation) -> dict:
    return {"metric": item.metric, "service": item.service, "region": item.region, "observed_at": item.observed_at, "value": item.value, "baseline": item.baseline, "threshold": item.threshold, "higher_is_worse": item.higher_is_worse}


def ingest(db: Session, incident: Incident, payload: dict, user_id: str) -> dict:
    accepted = duplicates = 0
    for point in payload["observations"]:
        exists = db.scalar(select(TelemetryObservation.id).where(TelemetryObservation.incident_id == incident.id, TelemetryObservation.source == payload["source"], TelemetryObservation.source_event_id == point["source_event_id"]))
        if exists:
            duplicates += 1
            continue
        db.add(TelemetryObservation(incident_id=incident.id, source=payload["source"], **point))
        accepted += 1
    db.commit()
    recent = list(db.scalars(select(TelemetryObservation).where(TelemetryObservation.incident_id == incident.id).order_by(TelemetryObservation.observed_at.desc()).limit(2000)))
    rows = [_read(item) for item in reversed(recent)]
    warnings = early_warnings(rows)
    prediction_id = None
    if accepted and payload.get("auto_forecast") and len(rows) >= 6 and warnings:
        request = {"horizon_minutes": payload["forecast_horizon_minutes"], "observations": forecast_rows(rows), "dependency_map": payload.get("dependency_map", {}), "regions": payload.get("region_catalog", []), "historical_incident_ids": []}
        prediction_id = run_prediction(db, incident, request, user_id).id
    return {"accepted": accepted, "duplicates": duplicates, "early_warnings": warnings[:20], "prediction_run_id": prediction_id}


def evaluate(db: Session, incident: Incident, prediction: PredictionRun, user_id: str) -> ForecastEvaluation:
    end = prediction.created_at + timedelta(minutes=prediction.horizon_minutes)
    observations = list(db.scalars(select(TelemetryObservation).where(TelemetryObservation.incident_id == incident.id, TelemetryObservation.observed_at >= prediction.created_at, TelemetryObservation.observed_at <= end).order_by(TelemetryObservation.observed_at)))
    result = evaluate_prediction(prediction.forecast, [_read(item) for item in observations], prediction.created_at)
    if not result["outcomes"]:
        raise ValueError("Forecast has no matching actual observations in its evaluation window")
    existing = db.scalar(select(ForecastEvaluation).where(ForecastEvaluation.prediction_run_id == prediction.id))
    values = {"incident_id": incident.id, "prediction_run_id": prediction.id, "outcome": {"metrics": result["outcomes"], "observation_count": len(observations)}, "calibration": {"quality": "good" if result["brier_score"] <= .15 else "watch" if result["brier_score"] <= .3 else "poor"}, "drift": result["drift"], "brier_score": result["brier_score"], "mean_absolute_error": result["mean_absolute_error"], "lead_time_minutes": result["lead_time_minutes"], "evaluated_by": user_id, "evaluated_at": datetime.now(timezone.utc)}
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        record = existing
    else:
        record = ForecastEvaluation(**values)
        db.add(record)
    db.commit()
    db.refresh(record)
    return record


def calibration(db: Session, incident_id: str) -> dict:
    records = list(db.scalars(select(ForecastEvaluation).where(ForecastEvaluation.incident_id == incident_id).order_by(ForecastEvaluation.evaluated_at)))
    leads = [item.lead_time_minutes for item in records if item.lead_time_minutes is not None]
    drift_status = "drift" if any(item.drift.get("status") == "drift" for item in records[-5:]) else "watch" if any(item.drift.get("status") == "watch" for item in records[-5:]) else "stable"
    return {"evaluation_count": len(records), "mean_brier_score": round(sum(item.brier_score for item in records) / len(records), 4) if records else 0, "mean_absolute_error": round(sum(item.mean_absolute_error for item in records) / len(records), 4) if records else 0, "mean_lead_time_minutes": round(sum(leads) / len(leads), 2) if leads else None, "reliability_buckets": calibration_summary([{"outcomes": item.outcome.get("metrics", [])} for item in records]), "drift_status": drift_status}
