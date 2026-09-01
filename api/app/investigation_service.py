from sqlalchemy import select
from sqlalchemy.orm import Session

from .agents import RecordedAgentRun
from .investigation import (contradiction_pairs, correlate_anomalies, derive_unknowns, estimate_blast_radius,
                            graph_candidates, predict_severity, rank_runbooks, text_embedding)
from .memory_search import nearest_memories
from .models import (AgentName, AnalysisKind, AnalysisResult, EvidenceArtifact, EvidenceItem,
                     GraphNodeType, GraphRelation, Incident, IncidentMemory, KnowledgeEdge,
                     KnowledgeNode, Runbook, UnknownItem)
from .multimodal import multimodal_analyzer


ROOT_CAUSE_GUARDRAIL = "ORBIT organizes and ranks evidence; root cause remains unconfirmed until a human incident commander explicitly confirms it."


def _node(db: Session, incident_id: str, node_type: GraphNodeType, label: str, key: str, confidence: int, evidence_ids: list[str]) -> tuple[KnowledgeNode, bool]:
    existing = db.scalar(select(KnowledgeNode).where(KnowledgeNode.incident_id == incident_id, KnowledgeNode.normalized_key == key))
    if existing:
        existing.confidence = max(existing.confidence, confidence)
        existing.source_evidence_ids = sorted(set(existing.source_evidence_ids + evidence_ids))
        return existing, False
    item = KnowledgeNode(incident_id=incident_id, node_type=node_type, label=label, normalized_key=key, confidence=confidence, source_evidence_ids=evidence_ids)
    db.add(item)
    db.flush()
    return item, True


def _analysis(db: Session, incident_id: str, kind: AnalysisKind, summary: str, confidence: int, result: dict, inputs: list[str], limitations: list[str]) -> AnalysisResult:
    item = AnalysisResult(incident_id=incident_id, kind=kind, summary=summary, confidence=confidence, result=result, input_references=inputs, limitations=limitations)
    db.add(item)
    db.flush()
    return item


async def run_investigation(db: Session, incident: Incident, request: dict) -> dict:
    evidence = list(db.scalars(select(EvidenceItem).where(EvidenceItem.incident_id == incident.id).order_by(EvidenceItem.created_at)))
    artifacts = list(db.scalars(select(EvidenceArtifact).where(EvidenceArtifact.incident_id == incident.id).order_by(EvidenceArtifact.created_at)))
    evidence_refs = [item.id for item in evidence]
    agent_run_ids, analyses = [], []

    evidence_run = RecordedAgentRun(db, incident.id, AgentName.evidence, evidence_refs)
    nodes_created = edges_created = 0
    evidence_nodes: dict[str, KnowledgeNode] = {}
    for item in evidence:
        candidates = graph_candidates(item.claim, item.classification.value)
        root_candidate = candidates[0]
        root, created = _node(db, incident.id, root_candidate.node_type, root_candidate.label, f"evidence:{item.id}", item.confidence, [item.id])
        evidence_nodes[item.id] = root
        nodes_created += int(created)
        for candidate in candidates[1:]:
            entity, created = _node(db, incident.id, candidate.node_type, candidate.label, candidate.normalized_key, candidate.confidence, [item.id])
            nodes_created += int(created)
            exists = db.scalar(select(KnowledgeEdge).where(KnowledgeEdge.incident_id == incident.id, KnowledgeEdge.source_node_id == entity.id, KnowledgeEdge.target_node_id == root.id, KnowledgeEdge.relation == GraphRelation.derived_from))
            if not exists:
                db.add(KnowledgeEdge(incident_id=incident.id, source_node_id=entity.id, target_node_id=root.id, relation=GraphRelation.derived_from, confidence=min(item.confidence, candidate.confidence), rationale="Entity or incident-state node was extracted from this evidence item.", evidence_ids=[item.id], created_by_agent=AgentName.evidence))
                edges_created += 1
    evidence_record = evidence_run.complete([node.id for node in evidence_nodes.values()])
    agent_run_ids.append(evidence_record.id)

    conflict_run = RecordedAgentRun(db, incident.id, AgentName.conflict, evidence_refs)
    pairs = contradiction_pairs([{"id": item.id, "claim": item.claim} for item in evidence])
    for pair in pairs:
        left, right = evidence_nodes[pair["left_id"]], evidence_nodes[pair["right_id"]]
        exists = db.scalar(select(KnowledgeEdge).where(KnowledgeEdge.incident_id == incident.id, KnowledgeEdge.source_node_id == left.id, KnowledgeEdge.target_node_id == right.id, KnowledgeEdge.relation == GraphRelation.contradicts))
        if not exists:
            edge = KnowledgeEdge(incident_id=incident.id, source_node_id=left.id, target_node_id=right.id, relation=GraphRelation.contradicts, confidence=pair["confidence"], rationale=f"Shared terms with opposite polarity: {', '.join(pair['shared_terms'])}", evidence_ids=[pair["left_id"], pair["right_id"]], created_by_agent=AgentName.conflict)
            db.add(edge)
            edges_created += 1
    unknown_ids = []
    for candidate in derive_unknowns([item.claim for item in evidence], incident.customer_impact, incident.affected_regions, incident.recovery_criteria):
        existing = db.scalar(select(UnknownItem).where(UnknownItem.incident_id == incident.id, UnknownItem.normalized_key == candidate.normalized_key))
        if not existing:
            existing = UnknownItem(incident_id=incident.id, question=candidate.question, normalized_key=candidate.normalized_key, category=candidate.category, priority=candidate.priority)
            db.add(existing)
            db.flush()
        unknown_ids.append(existing.id)
    conflict_record = conflict_run.complete(unknown_ids)
    agent_run_ids.append(conflict_record.id)

    investigation_run = RecordedAgentRun(db, incident.id, AgentName.investigation, evidence_refs + [item.id for item in artifacts])
    metrics = request.get("metrics", [])
    anomaly = correlate_anomalies(metrics)
    analyses.append(_analysis(db, incident.id, AnalysisKind.anomaly_correlation, f"Detected {anomaly['anomaly_count']} statistically notable metric deviations.", 82 if metrics else 25, anomaly, [item.get("name", "metric") for item in metrics], ["Correlation does not establish causation", "Accuracy depends on representative baselines"]))

    affected_services = request.get("affected_services") or [incident.service]
    blast = estimate_blast_radius(affected_services, request.get("dependency_map", {}), incident.affected_regions)
    analyses.append(_analysis(db, incident.id, AnalysisKind.blast_radius, f"Potential impact spans {len(blast['directly_affected']) + len(blast['potentially_affected'])} services.", 70 if request.get("dependency_map") else 38, blast, affected_services, ["Dependency map may be incomplete", "Potential impact is not confirmed impact"]))

    severity = predict_severity(request.get("failure_rate_percent"), request.get("estimated_customers_affected"), len(incident.affected_regions), request.get("critical_service", False))
    analyses.append(_analysis(db, incident.id, AnalysisKind.severity_prediction, f"Advisory severity suggestion: {severity['suggested_severity']}.", severity["confidence"], severity, evidence_refs, ["The incident commander owns the final severity decision"]))

    runbooks = list(db.scalars(select(Runbook).where(Runbook.active.is_(True))))
    query = " ".join([incident.title, incident.service] + [item.claim for item in evidence[-20:]])
    recommendations = rank_runbooks(query, [{"id": item.id, "service": item.service, "title": item.title, "description": item.description, "tags": item.tags, "source_uri": item.source_uri} for item in runbooks])
    analyses.append(_analysis(db, incident.id, AnalysisKind.runbook_recommendation, f"Ranked {len(recommendations)} relevant runbooks.", 72 if recommendations else 20, {"recommendations": recommendations}, [item.id for item in runbooks], ["A human must review a runbook before any consequential step is executed"]))

    query_embedding = text_embedding(query)
    nearest = nearest_memories(db, query_embedding, incident.id, 5)
    similar = [{"incident_id": item.incident_id, "similarity": score, "summary": item.summary, "resolution": item.resolution, "root_cause_status": item.root_cause_status} for item, score in nearest]
    analyses.append(_analysis(db, incident.id, AnalysisKind.similar_incident, f"Retrieved {len(similar)} similar historical incidents.", 68 if similar else 15, {"incidents": similar}, [item.id for item, _ in nearest], ["Similarity is contextual evidence, not proof of the same root cause"]))

    for artifact in artifacts:
        result = await multimodal_analyzer.analyze(artifact)
        artifact.analysis_status = result["status"]
        analyses.append(_analysis(db, incident.id, AnalysisKind.multimodal_evidence, f"Analyzed {artifact.artifact_type.value}: {artifact.title}.", 65 if result["status"] == "analyzed" else 15, result, [artifact.id], result["limitations"]))

    investigation_record = investigation_run.complete([item.id for item in analyses])
    agent_run_ids.append(investigation_record.id)
    commander_run = RecordedAgentRun(db, incident.id, AgentName.commander, [item.id for item in analyses])
    commander_record = commander_run.complete(unknown_ids + [item.id for item in analyses])
    agent_run_ids.append(commander_record.id)
    db.commit()
    for item in analyses:
        db.refresh(item)
    return {"agent_run_ids": agent_run_ids, "graph_nodes_created": nodes_created, "graph_edges_created": edges_created, "unknowns_open": len(unknown_ids), "analyses": analyses, "root_cause_confirmed": False, "guardrail": ROOT_CAUSE_GUARDRAIL}
