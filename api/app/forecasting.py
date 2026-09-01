import math
import random
from collections import defaultdict, deque


FORECAST_GUARDRAIL = "Forecasts are advisory probability estimates, not confirmed facts or independent root-cause determinations."


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _linear_fit(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    if len(points) < 2:
        return 0.0, points[-1][1] if points else 0.0, 0.0
    xs, ys = zip(*sorted(points))
    x_mean, y_mean = sum(xs) / len(xs), sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator if denominator else 0.0
    intercept = y_mean - slope * x_mean
    residual = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - y_mean) ** 2 for y in ys)
    fit = 1.0 - residual / total if total else 0.5
    return slope, intercept, _clamp(fit, 0, 1)


def _metric_forecast(rows: list[dict], horizon: int) -> dict:
    points = [(float(row["minute"]), float(row["value"])) for row in rows]
    slope, intercept, fit = _linear_fit(points)
    latest_minute = max((point[0] for point in points), default=0)
    latest = sorted(points)[-1][1] if points else 0
    predicted = slope * (latest_minute + horizon) + intercept
    sample = rows[-1]
    baseline = float(sample["baseline"])
    threshold = float(sample["threshold"])
    higher_is_worse = bool(sample.get("higher_is_worse", True))
    span = max(abs(threshold - baseline), abs(baseline) * .05, 1e-6)
    deterioration = (predicted - baseline) / span if higher_is_worse else (baseline - predicted) / span
    probability = _clamp(50 + deterioration * 28 + min(len(rows), 12) * 1.4)
    crossing = None
    if abs(slope) > 1e-9:
        candidate = (threshold - intercept) / slope
        direction_valid = (higher_is_worse and slope > 0) or (not higher_is_worse and slope < 0)
        if direction_valid and candidate >= latest_minute:
            crossing = round(candidate - latest_minute, 1)
    confidence = round(_clamp(25 + min(len(rows), 20) * 2.7 + fit * 25), 1)
    chart = [{"minute": round(x, 2), "actual": y} for x, y in sorted(points)]
    chart.extend({"minute": round(latest_minute + step, 2), "predicted": round(slope * (latest_minute + step) + intercept, 4)} for step in range(5, horizon + 1, 5))
    return {"metric": sample["metric"], "service": sample["service"], "region": sample.get("region"), "latest": latest, "predicted": round(predicted, 4), "slope_per_minute": round(slope, 6), "threshold": threshold, "threshold_eta_minutes": crossing, "breach_probability": round(probability, 1), "confidence": confidence, "series": chart}


def _propagate(initial: dict[str, float], dependencies: dict[str, list[str]]) -> dict[str, float]:
    risks = dict(initial)
    queue = deque((service, risk, 0) for service, risk in initial.items())
    visited: set[tuple[str, str]] = set()
    while queue:
        service, risk, depth = queue.popleft()
        if depth >= 5:
            continue
        for downstream in dependencies.get(service, []):
            if (service, downstream) in visited:
                continue
            visited.add((service, downstream))
            propagated = risk * (0.72 ** (depth + 1))
            if propagated > risks.get(downstream, 0):
                risks[downstream] = propagated
                queue.append((downstream, propagated, depth + 1))
    return {key: round(_clamp(value), 1) for key, value in risks.items()}


def build_prediction(observations: list[dict], dependency_map: dict[str, list[str]], regions: list[dict], horizon_minutes: int, historical_prior: dict | None = None) -> dict:
    grouped: dict[tuple[str, str, str | None], list[dict]] = defaultdict(list)
    for row in observations:
        grouped[(row["metric"], row["service"], row.get("region"))].append(row)
    metric_forecasts = [_metric_forecast(sorted(rows, key=lambda item: item["minute"]), horizon_minutes) for rows in grouped.values()]
    direct: dict[str, float] = defaultdict(float)
    for item in metric_forecasts:
        direct[item["service"]] = max(direct[item["service"]], item["breach_probability"])
    service_risks = _propagate(dict(direct), dependency_map)
    service_graph = {
        "nodes": [{"id": service, "label": service, "risk": risk, "kind": "service"} for service, risk in sorted(service_risks.items())],
        "edges": [{"source": source, "target": target, "relation": "may_propagate_to", "confidence": round(min(95, service_risks.get(source, 0) * .8), 1)} for source, targets in dependency_map.items() for target in targets],
    }
    region_items = []
    for region in regions:
        local = [item["breach_probability"] for item in metric_forecasts if item.get("region") == region["code"]]
        service = [service_risks.get(name, 0) for name in region.get("services", [])]
        technical_risk = max(local + service + [0])
        exposure = technical_risk * (0.55 + region["traffic_share"] * .45)
        region_items.append({**region, "technical_risk": round(technical_risk, 1), "exposure_score": round(_clamp(exposure), 1), "estimated_customers_at_risk": round(region["customers"] * technical_risk / 100)})
    geo_edges = [{"source": item["service"], "target": item["region"], "relation": "observed_in"} for item in metric_forecasts if item.get("region")]
    live_probability = max(service_risks.values(), default=0)
    prior_probability = float((historical_prior or {}).get("probability", live_probability))
    prior_weight = min(.25, max(0, float((historical_prior or {}).get("confidence", 0)) / 400))
    probability = live_probability * (1 - prior_weight) + prior_probability * prior_weight
    return {
        "horizon_minutes": horizon_minutes,
        "incident_escalation_probability": round(probability, 1),
        "live_signal_probability": round(live_probability, 1),
        "historical_prior": historical_prior or {"probability": round(live_probability, 1), "confidence": 0, "incidents": []},
        "risk_band": "critical" if probability >= 80 else "high" if probability >= 60 else "elevated" if probability >= 35 else "low",
        "metric_forecasts": metric_forecasts,
        "service_risks": service_risks,
        "graphs": {"metric_trends": [item["series"] for item in metric_forecasts], "service_dependency": service_graph, "geo_relationships": geo_edges},
        "geospatial": {"regions": sorted(region_items, key=lambda item: item["exposure_score"], reverse=True), "customers_at_risk": sum(item["estimated_customers_at_risk"] for item in region_items)},
        "guardrail": FORECAST_GUARDRAIL,
    }


def simulate(prediction: dict, intervention: dict, assumptions: dict, iterations: int, seed: str) -> dict:
    rng = random.Random(seed)
    baseline = float(prediction.get("incident_escalation_probability", 0))
    effectiveness = _clamp(float(intervention.get("effectiveness_percent", 25)), 0, 95) / 100
    delay = max(0.0, float(intervention.get("implementation_delay_minutes", 5)))
    failure_chance = _clamp(float(intervention.get("failure_probability_percent", 10)), 0, 100) / 100
    volatility = max(1.0, float(assumptions.get("risk_volatility", 8)))
    outcomes = []
    for _ in range(iterations):
        failed = rng.random() < failure_chance
        realized_effect = 0 if failed else effectiveness * rng.uniform(.65, 1.15)
        delay_penalty = min(20, delay * rng.uniform(.15, .45))
        outcomes.append(_clamp(baseline * (1 - realized_effect) + delay_penalty + rng.gauss(0, volatility)))
    outcomes.sort()
    percentile = lambda q: round(outcomes[min(len(outcomes) - 1, int(q * (len(outcomes) - 1)))], 1)
    mean = round(sum(outcomes) / len(outcomes), 1)
    return {"baseline_risk": baseline, "simulated_risk": mean, "risk_reduction": round(baseline - mean, 1), "p10": percentile(.1), "p50": percentile(.5), "p90": percentile(.9), "probability_below_critical": round(sum(value < 80 for value in outcomes) / len(outcomes) * 100, 1), "distribution": [{"risk": bucket, "count": sum(bucket <= value < bucket + 10 for value in outcomes)} for bucket in range(0, 100, 10)], "advisory_only": True, "guardrail": FORECAST_GUARDRAIL}
