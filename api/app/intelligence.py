import re
from dataclasses import dataclass
from .models import EvidenceClassification, FindingType


@dataclass(frozen=True)
class Extraction:
    classification: EvidenceClassification
    claim: str
    confidence: int


@dataclass(frozen=True)
class FindingCandidate:
    finding_type: FindingType
    title: str
    description: str
    severity: str


HYPOTHESIS_MARKERS = ("i think", "maybe", "might", "may be", "possibly", "could be", "suspect", "hypothesis")
DECISION_MARKERS = ("we decided", "decision:", "approved", "we will proceed", "rollback", "failover")
ACTION_PATTERNS = (
    re.compile(r"^(?P<owner>[A-Z][a-z]+),\s*(?P<task>.+)$"),
    re.compile(r"(?P<owner>[A-Z][a-z]+)\s+(?:will|should)\s+(?P<task>.+)", re.IGNORECASE),
)


def classify_turn(text: str) -> Extraction:
    normalized = " ".join(text.strip().split())
    lower = normalized.lower()
    if any(marker in lower for marker in HYPOTHESIS_MARKERS):
        return Extraction(EvidenceClassification.hypothesis, normalized, 72)
    if any(marker in lower for marker in DECISION_MARKERS):
        return Extraction(EvidenceClassification.decision, normalized, 86)
    if any(pattern.search(normalized) for pattern in ACTION_PATTERNS):
        return Extraction(EvidenceClassification.action, normalized, 82)
    return Extraction(EvidenceClassification.confirmed_fact, normalized, 68)


def extract_action(text: str) -> tuple[str, str] | None:
    normalized = " ".join(text.strip().split())
    for pattern in ACTION_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return match.group("owner"), match.group("task").rstrip(".")
    return None


def detect_findings(existing_claims: list[str], new_claim: str) -> list[FindingCandidate]:
    lower = new_claim.lower()
    findings: list[FindingCandidate] = []
    negation_tokens = ("normal", "not", "no ", "without", "unsupported")
    for existing in existing_claims:
        shared = set(re.findall(r"[a-z]{4,}", existing.lower())) & set(re.findall(r"[a-z]{4,}", lower))
        polarity_changed = any(token in existing.lower() for token in negation_tokens) != any(token in lower for token in negation_tokens)
        if len(shared) >= 2 and polarity_changed:
            findings.append(FindingCandidate(FindingType.contradiction, "Conflicting evidence detected", f'New statement "{new_claim}" conflicts with "{existing}".', "high"))
            break
    if "payment" in lower and not any(term in lower for term in ("region", "customer", "impact", "percent", "%")):
        findings.append(FindingCandidate(FindingType.missing_information, "Customer impact is incomplete", "Confirm affected regions, failure rate, and customer-facing symptoms.", "medium"))
    return findings


def build_status_briefing(facts: list[str], hypotheses: list[str], open_actions: list[str], findings: list[str]) -> str:
    sections = []
    if facts:
        sections.append("Confirmed: " + "; ".join(facts[:3]) + ".")
    if hypotheses:
        sections.append("Unconfirmed hypotheses: " + "; ".join(hypotheses[:2]) + ".")
    if open_actions:
        sections.append("Open actions: " + "; ".join(open_actions[:3]) + ".")
    if findings:
        sections.append("Attention needed: " + "; ".join(findings[:2]) + ".")
    sections.append("No root cause is confirmed unless the incident commander explicitly approves that conclusion.")
    return " ".join(sections)
