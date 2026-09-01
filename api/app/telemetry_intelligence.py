from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def early_warnings(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str | None], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["metric"], row["service"], row.get("region"))].append(row)
    warnings = []
    for (metric, service, region), points in grouped.items():
        points.sort(key=lambda item: _aware(item["observed_at"]))
        if len(points) < 2:
            continue
        latest, previous = points[-1], points[-2]
        minutes = max((_aware(latest["observed_at"]) - _aware(previous["observed_at"])).total_seconds() / 60, 1 / 60)
        velocity = (latest["value"] - previous["value"]) / minutes
        span = max(abs(latest["threshold"] - latest["baseline"]), abs(latest["baseline"]) * .05, 1e-6)
        progress = (latest["value"] - latest["baseline"]) / span if latest["higher_is_worse"] else (latest["baseline"] - latest["value"]) / span
        worsening_velocity = velocity if latest["higher_is_worse"] else -velocity
        eta = None
        if worsening_velocity > 0:
            distance = latest["threshold"] - latest["value"] if latest["higher_is_worse"] else latest["value"] - latest["threshold"]
            eta = max(0, distance / worsening_velocity)
        if progress >= .65 or (eta is not None and eta <= 30):
            score = min(100, max(0, progress * 70 + (30 - min(30, eta or 30))))
            warnings.append({"metric": metric, "service": service, "region": region, "score": round(score, 1), "velocity_per_minute": round(velocity, 5), "threshold_progress": round(progress * 100, 1), "threshold_eta_minutes": round(eta, 1) if eta is not None else None, "reason": "metric is approaching its operational threshold"})
    return sorted(warnings, key=lambda item: item["score"], reverse=True)


def forecast_rows(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    start = min(_aware(row["observed_at"]) for row in rows)
    return [{"metric": row["metric"], "service": row["service"], "region": row.get("region"), "minute": round((_aware(row["observed_at"]) - start).total_seconds() / 60, 3), "value": row["value"], "baseline": row["baseline"], "threshold": row["threshold"], "higher_is_worse": row["higher_is_worse"]} for row in rows]


def evaluate_prediction(prediction: dict, telemetry: list[dict], created_at: datetime) -> dict:
    forecasts = prediction.get("metric_forecasts", [])
    grouped: dict[tuple[str, str, str | None], list[dict]] = defaultdict(list)
    for row in telemetry:
        grouped[(row["metric"], row["service"], row.get("region"))].append(row)
    outcomes, brier_values, errors, lead_times = [], [], [], []
    for item in forecasts:
        points = sorted(grouped.get((item["metric"], item["service"], item.get("region")), []), key=lambda row: _aware(row["observed_at"]))
        if not points:
            continue
        threshold, higher = item["threshold"], points[-1]["higher_is_worse"]
        breached_points = [point for point in points if (point["value"] >= threshold if higher else point["value"] <= threshold)]
        actual = 1 if breached_points else 0
        probability = item["breach_probability"] / 100
        brier_values.append((probability - actual) ** 2)
        errors.append(abs(item["predicted"] - points[-1]["value"]))
        if breached_points:
            lead_times.append((_aware(breached_points[0]["observed_at"]) - _aware(created_at)).total_seconds() / 60)
        outcomes.append({"metric": item["metric"], "service": item["service"], "region": item.get("region"), "predicted_probability": item["breach_probability"], "actual_breach": bool(actual), "predicted_value": item["predicted"], "actual_value": points[-1]["value"]})
    drift = detect_drift(telemetry)
    return {"outcomes": outcomes, "brier_score": round(mean(brier_values), 4) if brier_values else 1.0, "mean_absolute_error": round(mean(errors), 4) if errors else 0.0, "lead_time_minutes": round(mean(lead_times), 2) if lead_times else None, "drift": drift}


def detect_drift(rows: list[dict]) -> dict:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["metric"], row["service"])].append(row)
    signals = []
    for (metric, service), points in grouped.items():
        points.sort(key=lambda item: _aware(item["observed_at"]))
        if len(points) < 4:
            continue
        midpoint = len(points) // 2
        earlier, current = points[:midpoint], points[midpoint:]
        baseline_span = max(abs(points[-1]["threshold"] - points[-1]["baseline"]), 1e-6)
        shift = abs(mean(point["value"] for point in current) - mean(point["value"] for point in earlier)) / baseline_span
        signals.append({"metric": metric, "service": service, "normalized_shift": round(shift, 4), "status": "drift" if shift >= .5 else "watch" if shift >= .25 else "stable"})
    status = "drift" if any(item["status"] == "drift" for item in signals) else "watch" if any(item["status"] == "watch" for item in signals) else "stable"
    return {"status": status, "signals": signals}


def calibration_summary(evaluations: list[dict]) -> dict:
    buckets = {index: {"predicted": [], "actual": []} for index in range(0, 100, 10)}
    for evaluation in evaluations:
        for outcome in evaluation.get("outcomes", []):
            key = min(90, int(outcome["predicted_probability"] // 10) * 10)
            buckets[key]["predicted"].append(outcome["predicted_probability"])
            buckets[key]["actual"].append(100 if outcome["actual_breach"] else 0)
    reliability = [{"bucket": f"{key}-{key + 10}", "forecast_probability": round(mean(value["predicted"]), 1), "observed_frequency": round(mean(value["actual"]), 1), "count": len(value["actual"])} for key, value in buckets.items() if value["actual"]]
    return reliability
