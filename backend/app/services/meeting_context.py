from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import Database
from app.models import PageContextPackRecord, RetrievalTraceRecord, RouteDecisionRecord
from app.services.analysis_context import (
    build_client_page_context_pack,
    compute_context_quality,
    decide_answer_policy,
    infer_page_intent,
)
from app.services.knowledge_v2 import retrieve_knowledge_bundle
from app.services.query_router import route_page_query
from app.services.retrieval_model_settings import get_retrieval_model_settings, retrieval_embedding_signature


def _rows_to_dict_list(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _build_retrieval_trace(
    *,
    context_pack: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_signature: str,
) -> RetrievalTraceRecord:
    return RetrievalTraceRecord(
        routeDecision=route_decision,
        embeddingProvider=embedding_provider,
        embeddingModel=embedding_model,
        embeddingDimension=embedding_dimension,
        embeddingSignature=embedding_signature,
        lexicalHitCount=len(context_pack.relatedDocuments),
        vectorHitCount=len(context_pack.rawEvidence),
        mergedHitCount=len(context_pack.relatedDocuments) + len(context_pack.rawEvidence),
        rerankHitCount=min(len(context_pack.rawEvidence), 30),
        rawChunkHitCount=len(context_pack.rawEvidence),
        fallbackUsed=bool(context_pack.answerPolicy.fallbackToLegacyRetrieval),
        latencyMs={},
    )


def build_meeting_page_context_pack(
    db: Database,
    *,
    data_dir: Path,
    meeting_id: str,
    prompt: str = "",
    include_raw_evidence: bool = False,
) -> PageContextPackRecord:
    meeting_row = db.fetchone(
        """
        SELECT id, client_id, title, stage, scheduled_at, transcript_text, notes, updated_at
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,),
    )
    if meeting_row is None:
        raise ValueError("Meeting not found")

    client_id = str(meeting_row["client_id"] or "").strip() or None
    intent = infer_page_intent(prompt, "meeting_detail")
    retrieval_settings = get_retrieval_model_settings(db)
    embedding_signature = retrieval_embedding_signature(retrieval_settings)

    agenda_items = _rows_to_dict_list(
        db.fetchall(
            "SELECT id, title, description, sort_order FROM agenda_items WHERE meeting_id = ? ORDER BY sort_order ASC, id ASC",
            (meeting_id,),
        )
    )
    decisions = _rows_to_dict_list(
        db.fetchall(
            "SELECT id, summary, created_at FROM decisions WHERE meeting_id = ? ORDER BY created_at DESC",
            (meeting_id,),
        )
    )
    action_items = _rows_to_dict_list(
        db.fetchall(
            "SELECT id, title, owner_name, due_date, confidence, publish_status, created_at FROM action_items WHERE meeting_id = ? ORDER BY created_at DESC",
            (meeting_id,),
        )
    )
    risks = _rows_to_dict_list(
        db.fetchall(
            "SELECT id, summary, severity, created_at FROM risks WHERE meeting_id = ? ORDER BY created_at DESC",
            (meeting_id,),
        )
    )
    ambiguities = _rows_to_dict_list(
        db.fetchall(
            "SELECT id, raw_text, candidates_json, status, created_at FROM ambiguities WHERE meeting_id = ? ORDER BY created_at DESC",
            (meeting_id,),
        )
    )

    related_tasks = _rows_to_dict_list(
        db.fetchall(
            """
            SELECT id, title, description, status, updated_at, client_id, event_line_id
            FROM tasks
            WHERE source_type = 'meeting' AND source_id = ?
            ORDER BY updated_at DESC
            LIMIT 40
            """,
            (meeting_id,),
        )
    )

    evidence_refs = _rows_to_dict_list(
        db.fetchall(
            """
            SELECT id, title, excerpt, source_type, document_id, path, created_at
            FROM evidence_refs
            WHERE meeting_id = ?
            ORDER BY created_at DESC
            LIMIT 60
            """,
            (meeting_id,),
        )
    )

    client_pack = None
    if client_id:
        client_pack = build_client_page_context_pack(
            db,
            data_dir=data_dir,
            client_id=client_id,
            prompt=prompt,
            page="meeting_detail",
            intent=intent,
            include_raw_evidence=bool(include_raw_evidence or intent.requiresRawEvidence),
            workspace=None,
        )

    raw_evidence: list[dict[str, Any]] = []
    should_pull_raw = bool(include_raw_evidence or intent.requiresRawEvidence)
    if should_pull_raw and client_id and str(prompt or "").strip():
        bundle = retrieve_knowledge_bundle(db, data_dir, client_id, prompt)
        raw_evidence = [
            {
                "title": item.title,
                "excerpt": item.excerpt,
                "path": item.path,
                "documentId": item.knowledge_document_id,
                "sectionLabel": item.section_label,
                "score": item.score,
                "sourceStage": item.source_stage,
            }
            for item in bundle.citations[:20]
        ]

    page_context = PageContextPackRecord(
        page="meeting_detail",
        scopeType="meeting",
        scopeId=meeting_id,
        clientId=client_id,
        intent=intent.intent,
        officialJudgments=list((client_pack.officialJudgments if client_pack else [])[:20]),
        candidateJudgments=list((client_pack.candidateJudgments if client_pack else [])[:20]),
        overlayJudgments=list((client_pack.overlayJudgments if client_pack else [])[:20]),
        evidenceCards=evidence_refs[:30],
        rawEvidence=raw_evidence,
        openQuestions=list((client_pack.openQuestions if client_pack else [])[:20]),
        conflicts=list((client_pack.conflicts if client_pack else [])[:20]),
        themeClusters=list((client_pack.themeClusters if client_pack else [])[:20]),
        relatedTasks=related_tasks,
        relatedMeetings=list((client_pack.relatedMeetings if client_pack else [])[:10]),
        relatedDocuments=evidence_refs[:30],
        notebookSummary=(client_pack.notebookSummary if client_pack else None),
        memoryFacts=list((client_pack.memoryFacts if client_pack else [])[:20]),
        contextPack={
            "id": str(meeting_row["id"]),
            "clientId": client_id,
            "title": str(meeting_row["title"]),
            "stage": str(meeting_row["stage"]),
            "scheduledAt": str(meeting_row["scheduled_at"]) if meeting_row["scheduled_at"] else None,
            "updatedAt": str(meeting_row["updated_at"]),
            "transcriptText": str(meeting_row["transcript_text"] or ""),
            "notes": str(meeting_row["notes"] or ""),
            "agendaItems": agenda_items,
            "decisions": decisions,
            "actionItems": action_items,
            "risks": risks,
            "ambiguities": ambiguities,
        },
        judgmentBundle=(client_pack.judgmentBundle if client_pack else None),
        resolutionTrace=(client_pack.resolutionTrace if client_pack else None),
        stateProjection={
            "meetingId": meeting_id,
            "agendaCount": len(agenda_items),
            "decisionCount": len(decisions),
            "actionCount": len(action_items),
            "riskCount": len(risks),
            "ambiguityCount": len(ambiguities),
        },
        missingContext=[],
        boundaryNotes=list((client_pack.boundaryNotes if client_pack else [])[:8]),
        sourceSummary={
            "meetingAgendaCount": len(agenda_items),
            "meetingDecisionCount": len(decisions),
            "meetingActionCount": len(action_items),
            "meetingRiskCount": len(risks),
            "meetingAmbiguityCount": len(ambiguities),
            "rawEvidenceCount": len(raw_evidence),
            "taskCount": len(related_tasks),
            "documentCount": len(evidence_refs),
        },
        retrievalPlan={
            "strategy": "meeting_evidence",
            "requestedRawEvidence": should_pull_raw,
            "routerSource": "rules",
        },
    )

    route_decision = route_page_query(
        db,
        page="meeting_detail",
        prompt=prompt,
        client_id=client_id,
        task_id=None,
        page_context=page_context,
        settings=retrieval_settings,
        ai_service=None,
    )
    page_context.routeDecision = route_decision
    page_context.quality = compute_context_quality(page_context)
    page_context.answerPolicy = decide_answer_policy(page_context)
    page_context.retrievalTrace = _build_retrieval_trace(
        context_pack=page_context,
        route_decision=route_decision,
        embedding_provider=retrieval_settings.embeddingProvider,
        embedding_model=retrieval_settings.embeddingModel,
        embedding_dimension=retrieval_settings.embeddingDimension,
        embedding_signature=embedding_signature,
    )
    return page_context
