import hashlib
import json


def alert_key(alert: dict, labels: dict[str, str]) -> str:
    fingerprint = str(alert.get("fingerprint") or "").strip()
    if fingerprint:
        return fingerprint
    canonical = json.dumps({str(key): str(value) for key, value in sorted(labels.items())}, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def service_from_labels(labels: dict[str, str]) -> str:
    service = str(labels.get("service") or "").strip()
    if service:
        return service[:120]
    job = str(labels.get("job") or "").strip()
    if job:
        return job.replace("_", "-")[:120]
    return "unknown-service"


def severity_from_labels(labels: dict[str, str]) -> str:
    level = str(labels.get("severity") or "warning").lower()
    return {"critical": "SEV1", "high": "SEV2", "warning": "SEV3", "medium": "SEV3"}.get(level, "SEV4")
