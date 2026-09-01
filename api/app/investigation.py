import hashlib
import math
import re
from dataclasses import dataclass

from .models import GraphNodeType


TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.-]{1,}")
REGIONS = {"us-east", "us-west", "eu-west", "eu-central", "ap-south", "ap-southeast", "global"}
COMPONENT_MARKERS = ("api", "gateway", "database", "db", "cache", "queue", "worker", "service", "cluster", "pod")


@dataclass(frozen=True)
class NodeCandidate:
    node_type: GraphNodeType
    label: str
    normalized_key: str
    confidence: int


@dataclass(frozen=True)
class UnknownCandidate:
    question: str
    normalized_key: str
    category: str
    priority: str


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:240]


def text_embedding(text: str, dimensions: int = 96) -> list[float]:
    """Deterministic local embedding for offline development and reproducible tests."""
    vector = [0.0] * dimensions
    tokens = TOKEN_PATTERN.findall(text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign * (1.0 + min(len(token), 12) / 12)
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def graph_candidates(claim: str, classification: str) -> list[NodeCandidate]:
    candidates = [NodeCandidate(GraphNodeType.evidence, claim[:240], normalize_key(claim), 100)]
    tokens = TOKEN_PATTERN.findall(claim.lower())
    for token in tokens:
        clean = token.strip(".-")
        if clean in REGIONS or re.fullmatch(r"[a-z]{2}-[a-z]+-\d", clean):
            candidates.append(NodeCandidate(GraphNodeType.region, clean, f"region:{clean}", 90))
        elif any(marker in clean for marker in COMPONENT_MARKERS) and len(clean) <= 80:
            candidates.append(NodeCandidate(GraphNodeType.component, clean, f"component:{normalize_key(clean)}", 72))
    class_map = {
        "hypothesis": GraphNodeType.hypothesis,
        "decision": GraphNodeType.decision,
        "action": GraphNodeType.action,
    }
    if classification in class_map:
        candidates.append(NodeCandidate(class_map[classification], claim[:240], f"{classification}:{normalize_key(claim)}", 85))
    unique: dict[str, NodeCandidate] = {}
    for item in candidates:
        unique[item.normalized_key] = item
    return list(unique.values())


def contradiction_pairs(evidence: list[dict]) -> list[dict]:
    negation_tokens = ("normal", "not", "no ", "without", "unsupported", "healthy", "recovered")
    pairs = []
    for index, left in enumerate(evidence):
        left_text = left["claim"].lower()
        left_terms = set(re.findall(r"[a-z]{4,}", left_text))
        for right in evidence[index + 1:]:
            right_text = right["claim"].lower()
            shared = left_terms & set(re.findall(r"[a-z]{4,}", right_text))
            polarity_changed = any(token in left_text for token in negation_tokens) != any(token in right_text for token in negation_tokens)
            if len(shared) >= 2 and polarity_changed:
                pairs.append({"left_id": left["id"], "right_id": right["id"], "shared_terms": sorted(shared)[:8], "confidence": min(92, 55 + len(shared) * 6)})
    return pairs


def derive_unknowns(
    claims: list[str], customer_impact: str | None, affected_regions: list[str], recovery_criteria: str | None
) -> list[UnknownCandidate]:
    corpus = " ".join(claims).lower()
    unknowns = []
    if not customer_impact or not any(marker in corpus for marker in ("customer", "checkout", "failure rate", "%")):
        unknowns.append(UnknownCandidate("What is the quantified customer impact and failure rate?", "customer-impact", "impact", "high"))
    if not affected_regions and not any(region in corpus for region in REGIONS):
        unknowns.append(UnknownCandidate("Which regions and customer segments are affected?", "affected-regions", "scope", "high"))
    if not any(marker in corpus for marker in ("started at", "since ", "first alert", "begin time")):
        unknowns.append(UnknownCandidate("When did the first confirmed symptom begin?", "incident-start-time", "timeline", "medium"))
    if not any(marker in corpus for marker in ("baseline", "normal is", "normally")):
        unknowns.append(UnknownCandidate("What is the normal baseline for the degraded metrics?", "metric-baseline", "observability", "medium"))
    if not recovery_criteria:
        unknowns.append(UnknownCandidate("What measurable criteria must hold before recovery is declared?", "recovery-criteria", "recovery", "high"))
    unknowns.append(UnknownCandidate("What evidence would falsify the leading hypothesis?", "hypothesis-falsification", "investigation", "medium"))
    return unknowns


def correlate_anomalies(metrics: list[dict]) -> dict:
    anomalies = []
    for metric in metrics:
        deviation = float(metric["standard_deviation"])
        z_score = (float(metric["current"]) - float(metric["baseline"])) / deviation
        if abs(z_score) >= 2:
            anomalies.append({**metric, "z_score": round(z_score, 2), "direction": "high" if z_score > 0 else "low"})
    clusters: dict[str, list[str]] = {}
    for item in anomalies:
        key = f"{item.get('service', 'unknown')}:{item.get('region') or 'all'}"
        clusters.setdefault(key, []).append(item["name"])
    return {"anomalies": anomalies, "clusters": clusters, "anomaly_count": len(anomalies)}


def estimate_blast_radius(affected_services: list[str], dependency_map: dict[str, list[str]], regions: list[str]) -> dict:
    discovered = set(affected_services)
    frontier = [(service, 0) for service in affected_services]
    depth_by_service = {service: 0 for service in affected_services}
    while frontier:
        service, depth = frontier.pop(0)
        if depth >= 4:
            continue
        for dependent in dependency_map.get(service, []):
            if dependent not in discovered:
                discovered.add(dependent)
                depth_by_service[dependent] = depth + 1
                frontier.append((dependent, depth + 1))
    score = min(100, len(discovered) * 12 + len(regions) * 8)
    return {
        "directly_affected": affected_services,
        "potentially_affected": sorted(discovered - set(affected_services)),
        "dependency_depth": depth_by_service,
        "regions": regions,
        "blast_radius_score": score,
    }


def predict_severity(failure_rate: float | None, customers: int | None, regions: int, critical_service: bool) -> dict:
    score, reasons = 0, []
    if critical_service:
        score += 35
        reasons.append("A business-critical service is affected")
    if failure_rate is not None:
        if failure_rate >= 50:
            score += 40
        elif failure_rate >= 20:
            score += 30
        elif failure_rate >= 5:
            score += 15
        reasons.append(f"Observed failure rate is {failure_rate:.1f}%")
    if customers is not None:
        score += 25 if customers >= 100_000 else 15 if customers >= 10_000 else 5 if customers > 0 else 0
        reasons.append(f"Estimated customers affected: {customers}")
    score += min(15, regions * 5)
    if regions:
        reasons.append(f"Affected region count: {regions}")
    severity = "SEV1" if score >= 75 else "SEV2" if score >= 45 else "SEV3" if score >= 20 else "SEV4"
    confidence = 85 if failure_rate is not None and customers is not None else 62
    return {"suggested_severity": severity, "score": min(100, score), "reasons": reasons, "advisory_only": True, "confidence": confidence}


def rank_runbooks(query: str, runbooks: list[dict], limit: int = 5) -> list[dict]:
    query_vector = text_embedding(query)
    query_tokens = set(TOKEN_PATTERN.findall(query.lower()))
    ranked = []
    for runbook in runbooks:
        corpus = " ".join([runbook.get("service", ""), runbook.get("title", ""), runbook.get("description", ""), " ".join(runbook.get("tags", []))])
        semantic = max(0.0, cosine_similarity(query_vector, text_embedding(corpus)))
        overlap = len(query_tokens & set(TOKEN_PATTERN.findall(corpus.lower()))) / max(1, len(query_tokens))
        score = round(0.65 * semantic + 0.35 * overlap, 4)
        ranked.append({"runbook_id": runbook["id"], "title": runbook["title"], "service": runbook["service"], "score": score, "source_uri": runbook.get("source_uri")})
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]


def analyze_artifact_text(artifact_type: str, extracted_text: str | None) -> dict:
    text = (extracted_text or "").strip()
    if not text:
        return {"status": "needs_processor", "observations": [], "limitations": ["No extracted text or vision output was provided"]}
    observations = []
    patterns = {
        "error": r"\b(error|exception|failed|timeout|5\d\d)\b",
        "latency": r"\b(latency|p95|p99|slow)\b",
        "capacity": r"\b(cpu|memory|saturation|pool|queue depth)\b",
        "recovery": r"\b(recovered|normal|healthy|success rate)\b",
    }
    for category, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            observations.append({"category": category, "match_count": len(matches)})
    return {
        "status": "analyzed",
        "artifact_type": artifact_type,
        "observations": observations,
        "limitations": ["Text-pattern analysis is advisory; inspect the original artifact before confirming conclusions"],
    }
