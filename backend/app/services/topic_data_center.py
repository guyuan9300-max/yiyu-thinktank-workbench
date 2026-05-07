from __future__ import annotations

from pathlib import Path

from app.db import Database
from app.models import ExternalEvidenceLiteRecord, PageContextPackRecord, RetrievalTraceRecord
from app.services.analysis_context import compute_context_quality, decide_answer_policy, infer_page_intent
from app.services.external_evidence import list_external_evidence_cards
from app.services.query_router import route_page_query
from app.services.retrieval_model_settings import get_retrieval_model_settings, retrieval_embedding_signature


def _build_trace(pack: PageContextPackRecord) -> RetrievalTraceRecord:
    decision = pack.routeDecision
    if decision is None:
        raise ValueError("route decision required")
    settings = pack.retrievalPlan if isinstance(pack.retrievalPlan, dict) else {}
    return RetrievalTraceRecord(
        routeDecision=decision,
        embeddingProvider=str(settings.get("embeddingProvider") or "local_fastembed"),
        embeddingModel=str(settings.get("embeddingModel") or "BAAI/bge-small-zh-v1.5"),
        embeddingDimension=int(settings.get("embeddingDimension") or 256),
        embeddingSignature=str(settings.get("embeddingSignature") or "local_fastembed:BAAI/bge-small-zh-v1.5:256"),
        lexicalHitCount=len(pack.relatedDocuments),
        vectorHitCount=len(pack.rawEvidence),
        mergedHitCount=len(pack.relatedDocuments) + len(pack.rawEvidence),
        rerankHitCount=min(30, len(pack.rawEvidence)),
        rawChunkHitCount=len(pack.rawEvidence),
        fallbackUsed=bool(pack.answerPolicy.fallbackToLegacyRetrieval),
        latencyMs={},
    )


def build_topic_page_context_pack(
    db: Database,
    *,
    data_dir: Path,
    topic_id: str,
    prompt: str = "",
    include_raw_evidence: bool = False,
) -> PageContextPackRecord:
    del data_dir, include_raw_evidence
    row = db.fetchone(
        """
        SELECT c.*, r.title AS radar_title
        FROM topic_candidates c
        LEFT JOIN topic_radars r ON r.id = c.radar_id
        WHERE c.id = ?
        """,
        (topic_id,),
    )
    if row is None:
        raise ValueError("Topic candidate not found")

    intent = infer_page_intent(prompt, "topic_radar")
    settings = get_retrieval_model_settings(db)
    signature = retrieval_embedding_signature(settings)

    external = ExternalEvidenceLiteRecord(
        sourceType="topic_candidate",
        sourceId=str(row["id"]),
        title=str(row["title"]),
        summary=str(row["summary"]),
        sourceUrl=str(row["source_url"]) if row["source_url"] else None,
        publishedAt=str(row["published_at"]) if row["published_at"] else None,
        confidence=0.72 if str(row["status"] or "") in {"tracking", "promoted"} else 0.58,
        relatedClientIds=[str(row["client_id"])] if "client_id" in row.keys() and row["client_id"] else [],
    )

    card_docs = list_external_evidence_cards(
        db,
        topic_candidate_id=topic_id,
        status="accepted",
        limit=20,
    )
    if not card_docs:
        card_docs = list_external_evidence_cards(
            db,
            topic_candidate_id=topic_id,
            status="candidate",
            limit=20,
        )
    docs = [
        {
            "id": card.id,
            "title": card.title,
            "summary": card.summary,
            "excerpt": card.factExcerpt,
            "sourceType": "external_evidence_card",
            "sourceUrl": card.sourceUrl,
            "publishedAt": card.publishedAt,
            "confidence": card.confidence,
            "status": card.status,
            "verificationLabel": "已核验外部证据" if card.status == "accepted" else "未核验外部证据",
            "sourceTier": card.sourceTier,
        }
        for card in card_docs
    ]
    if not docs:
        docs = [
            {
                "id": external.sourceId,
                "title": external.title,
                "summary": external.summary,
                "sourceType": external.sourceType,
                "sourceUrl": external.sourceUrl,
                "publishedAt": external.publishedAt,
                "confidence": external.confidence,
                "verificationLabel": "未核验外部证据",
            }
        ]

    pack = PageContextPackRecord(
        page="topic_radar",
        scopeType=str(row["scope_type"] or "topic") if "scope_type" in row.keys() else "topic",
        scopeId=str(row["scope_id"] or topic_id) if "scope_id" in row.keys() else topic_id,
        clientId=str(row["client_id"]) if "client_id" in row.keys() and row["client_id"] else None,
        intent=intent.intent,
        officialJudgments=[],
        candidateJudgments=[],
        overlayJudgments=[],
        evidenceCards=docs,
        rawEvidence=docs,
        openQuestions=[],
        conflicts=[],
        themeClusters=[],
        relatedTasks=[],
        relatedMeetings=[],
        relatedDocuments=docs,
        notebookSummary=None,
        memoryFacts=[],
        contextPack={
            "topicId": str(row["id"]),
            "radarId": str(row["radar_id"]),
            "radarTitle": str(row["radar_title"] or ""),
            "title": external.title,
            "summary": external.summary,
            "source": str(row["source"] or ""),
            "status": str(row["status"] or ""),
        },
        judgmentBundle=None,
        resolutionTrace=None,
        stateProjection={
            "topicId": str(row["id"]),
            "candidateStatus": str(row["status"] or ""),
        },
        missingContext=[],
        boundaryNotes=["未核验外部证据可以作为候选线索引用，但必须保留核验提示；已标记不采用的证据不进入活跃检索。"],
        sourceSummary={"topicCandidateCount": 1},
        retrievalPlan={
            "strategy": "topic_candidate_lite",
            "embeddingProvider": settings.embeddingProvider,
            "embeddingModel": settings.embeddingModel,
            "embeddingDimension": settings.embeddingDimension,
            "embeddingSignature": signature,
        },
    )

    route = route_page_query(
        db,
        page="topic_radar",
        prompt=prompt,
        client_id=None,
        task_id=None,
        page_context=pack,
        settings=settings,
        ai_service=None,
    )
    pack.routeDecision = route
    pack.quality = compute_context_quality(pack)
    pack.answerPolicy = decide_answer_policy(pack)
    pack.retrievalTrace = _build_trace(pack)
    return pack
