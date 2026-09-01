import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal
from .forecasting_service import learned_prior_for_incident
from .models import (ForecastEvaluation, Incident, IncidentStatus, PredictionRun,
                     ProductionLearningRun)
from .production_learning import alert_quality, normalize_prometheus_matrix
from .telemetry_service import evaluate, ingest


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def evaluate_mature(db: Session, incident_id: str | None, now: datetime, grace_minutes: int, actor: str) -> dict:
    query = select(PredictionRun).order_by(PredictionRun.created_at)
    if incident_id:
        query = query.where(PredictionRun.incident_id == incident_id)
    predictions = list(db.scalars(query))
    evaluated_ids = set(db.scalars(select(ForecastEvaluation.prediction_run_id)))
    evaluated, waiting, unavailable = [], 0, []
    for prediction in predictions:
        if prediction.id in evaluated_ids:
            continue
        maturity = _aware(prediction.created_at) + timedelta(minutes=prediction.horizon_minutes + grace_minutes)
        if now < maturity:
            waiting += 1
            continue
        incident = db.get(Incident, prediction.incident_id)
        if not incident:
            continue
        try:
            record = evaluate(db, incident, prediction, actor)
            evaluated.append(record.id)
        except ValueError:
            unavailable.append(prediction.id)
    return {"evaluated": len(evaluated), "evaluation_ids": evaluated, "waiting_for_maturity": waiting, "missing_actuals": unavailable}


def learning_status(db: Session, incident_id: str | None = None) -> dict:
    query = select(ForecastEvaluation).order_by(ForecastEvaluation.evaluated_at)
    run_query = select(ProductionLearningRun).order_by(ProductionLearningRun.started_at.desc()).limit(20)
    if incident_id:
        query = query.where(ForecastEvaluation.incident_id == incident_id)
        run_query = run_query.where((ProductionLearningRun.incident_id == incident_id) | (ProductionLearningRun.incident_id.is_(None)))
    evaluations = list(db.scalars(query))
    runs = list(db.scalars(run_query))
    quality = alert_quality([{"outcomes": item.outcome.get("metrics", [])} for item in evaluations])
    incident = db.get(Incident, incident_id) if incident_id else None
    settings = get_settings()
    return {"evaluation_count": len(evaluations), "alert_quality": quality, "collector": {"enabled": settings.telemetry_collector_enabled, "configured": bool(settings.prometheus_base_url), "interval_seconds": settings.telemetry_collection_interval_seconds, "query_count": len(settings.telemetry_query_catalog.get("queries", []))}, "recent_runs": [{"id": item.id, "incident_id": item.incident_id, "run_type": item.run_type, "status": item.status, "result": item.result, "error_message": item.error_message, "started_at": item.started_at.isoformat() if item.started_at else None} for item in runs], "learned_prior": learned_prior_for_incident(db, incident) if incident else None}


async def _fetch_query(client: httpx.AsyncClient, base_url: str, token: str, query: dict, start: datetime, end: datetime, username: str = "") -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"} if token and not username else {}
    auth = (username, token) if username else None
    response = await client.get(f"{base_url.rstrip('/')}/api/v1/query_range", headers=headers, auth=auth, params={"query": query["query"], "start": start.timestamp(), "end": end.timestamp(), "step": query.get("step_seconds", 60)})
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") not in (None, "success"):
        raise RuntimeError(f"Prometheus query failed: {payload.get('error', 'unknown error')}")
    return normalize_prometheus_matrix(payload, query)


async def run_learning_cycle(incident_id: str | None = None, collect_telemetry: bool = True, evaluate_forecasts: bool = True, actor: str = "orbit-scheduler") -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        incident_query = select(Incident).where(Incident.status != IncidentStatus.resolved)
        if incident_id:
            incident_query = incident_query.where(Incident.id == incident_id)
        incidents = list(db.scalars(incident_query))
    collected = {"incidents": 0, "observations": 0, "duplicates": 0, "warnings": 0, "predictions": 0, "errors": []}
    catalog = settings.telemetry_query_catalog
    if collect_telemetry and settings.telemetry_collector_enabled and settings.prometheus_base_url:
        start = now - timedelta(minutes=settings.telemetry_collection_window_minutes)
        async with httpx.AsyncClient(timeout=settings.integration_timeout_seconds) as client:
            for incident in incidents:
                query_defs = [item for item in catalog.get("queries", []) if not item.get("incident_service") or item["incident_service"] == incident.service]
                batches = await asyncio.gather(*[_fetch_query(client, settings.prometheus_base_url, settings.prometheus_bearer_token, {**query, "query": query["query"].replace("{service}", incident.service), "service": query.get("service") or incident.service}, start, now, settings.prometheus_username) for query in query_defs], return_exceptions=True)
                observations = []
                for batch in batches:
                    if isinstance(batch, Exception):
                        collected["errors"].append(str(batch))
                    else:
                        observations.extend(batch)
                if observations:
                    with SessionLocal() as db:
                        current = db.get(Incident, incident.id)
                        result = ingest(db, current, {"source": "prometheus", "observations": observations, "auto_forecast": True, "forecast_horizon_minutes": int(catalog.get("forecast_horizon_minutes", 30)), "dependency_map": catalog.get("dependency_map", {}), "region_catalog": catalog.get("regions", [])}, actor)
                    collected["incidents"] += 1
                    collected["observations"] += result["accepted"]
                    collected["duplicates"] += result["duplicates"]
                    collected["warnings"] += len(result["early_warnings"])
                    collected["predictions"] += bool(result["prediction_run_id"])
    with SessionLocal() as db:
        maturity = evaluate_mature(db, incident_id, now, settings.forecast_evaluation_grace_minutes, actor) if evaluate_forecasts else {"evaluated": 0, "evaluation_ids": [], "waiting_for_maturity": 0, "missing_actuals": []}
        run = ProductionLearningRun(incident_id=incident_id, run_type="production_learning_cycle", status="completed" if not collected["errors"] else "partial", input_summary={"collect_telemetry": collect_telemetry, "evaluate_forecasts": evaluate_forecasts, "incident_count": len(incidents)}, result={"collection": collected, "maturity_evaluation": maturity}, created_by=actor, completed_at=datetime.now(timezone.utc))
        db.add(run)
        db.commit()
        db.refresh(run)
        status = learning_status(db, incident_id)
    return {"run_id": run.id, "collection": collected, "maturity_evaluation": maturity, "alert_quality": status["alert_quality"]}
