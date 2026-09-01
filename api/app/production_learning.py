import hashlib
import math
from datetime import datetime, timezone


SEVERITY_RISK = {"SEV1": 92.0, "SEV2": 68.0, "SEV3": 38.0, "SEV4": 15.0}


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def alert_quality(evaluations: list[dict], threshold: float = 60.0) -> dict:
    outcomes = [outcome for evaluation in evaluations for outcome in evaluation.get("outcomes", [])]

    def confusion(candidate: float) -> dict:
        tp = fp = tn = fn = 0
        for item in outcomes:
            predicted = float(item["predicted_probability"]) >= candidate
            actual = bool(item["actual_breach"])
            tp += predicted and actual
            fp += predicted and not actual
            tn += not predicted and not actual
            fn += not predicted and actual
        precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
        f1 = round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0
        return {"threshold": candidate, "true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn, "precision": precision, "recall": recall, "f1": f1, "false_positive_rate": _ratio(fp, fp + tn), "false_negative_rate": _ratio(fn, fn + tp)}

    current = confusion(threshold)
    candidates = [confusion(value) for value in range(30, 91, 5)] if outcomes else [current]
    recommended = max(candidates, key=lambda item: (item["f1"], item["recall"], -item["false_positive_rate"]))
    return {"sample_count": len(outcomes), "current": current, "recommended_threshold": recommended["threshold"], "recommended": recommended, "policy": "review" if len(outcomes) < 20 else "eligible", "minimum_samples": 20}


def build_learned_prior(candidates: list[dict]) -> dict:
    weighted_probability = total_weight = 0.0
    sources = []
    for item in candidates:
        similarity = max(0.05, min(1.0, float(item.get("similarity", 0))))
        evaluation_count = int(item.get("evaluation_count", 0))
        reliability = max(0.1, 1.0 - float(item.get("mean_brier_score", 0.5)))
        evidence_factor = min(1.0, math.log2(evaluation_count + 1) / 3) if evaluation_count else 0.2
        weight = similarity * reliability * evidence_factor
        severity_probability = SEVERITY_RISK.get(item.get("severity"), 40.0)
        actual_probability = float(item.get("actual_breach_rate", severity_probability))
        probability = actual_probability * 0.75 + severity_probability * 0.25 if evaluation_count else severity_probability
        weighted_probability += probability * weight
        total_weight += weight
        sources.append({**item, "weight": round(weight, 4), "learned_probability": round(probability, 1)})
    return {"probability": round(weighted_probability / total_weight, 1) if total_weight else 0.0, "confidence": round(min(90, total_weight / max(1, len(candidates)) * 100), 1) if candidates else 0.0, "incidents": sources, "method": "similarity × measured reliability × evaluated outcome support"}


def normalize_prometheus_matrix(payload: dict, query: dict, source: str = "prometheus") -> list[dict]:
    rows = []
    for series in payload.get("data", {}).get("result", []):
        labels = series.get("metric", {})
        metric = query.get("metric") or labels.get("__name__") or "unnamed_metric"
        service = query.get("service") or labels.get("service") or labels.get("job") or "unknown-service"
        region = query.get("region") or labels.get("region")
        for raw in series.get("values", []):
            try:
                timestamp, value = float(raw[0]), float(raw[1])
            except (TypeError, ValueError, IndexError):
                continue
            identity = f"{source}|{query.get('query', '')}|{metric}|{service}|{region}|{timestamp}|{sorted(labels.items())}"
            rows.append({"metric": metric, "service": service, "region": region, "observed_at": datetime.fromtimestamp(timestamp, tz=timezone.utc), "value": value, "baseline": float(query["baseline"]), "threshold": float(query["threshold"]), "higher_is_worse": bool(query.get("higher_is_worse", True)), "source_event_id": hashlib.sha256(identity.encode()).hexdigest(), "labels": {key: value for key, value in labels.items() if key != "__name__"}})
    return rows
