from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from app.db import Database, from_json, to_json
from app.models import DataCenterProposalDraftRecord, ExternalEvidenceCardRecord, ProposalTargetRefRecord
from app.services.data_center_proposal import (
    build_proposal_dedupe_key,
    ensure_data_center_proposal_draft_schema,
)
from app.services.knowledge_v2 import new_id


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return str(parsed.netloc or "").lower()
    except Exception:
        return ""


def ensure_external_evidence_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS external_evidence_cards (
            id TEXT PRIMARY KEY,
            source_url TEXT NOT NULL,
            source_domain TEXT NOT NULL,
            source_tier TEXT NOT NULL DEFAULT 'unknown',
            title TEXT NOT NULL,
            published_at TEXT,
            fact_excerpt TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]',
            related_scope_type TEXT NOT NULL,
            related_scope_id TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'candidate',
            reviewed_by TEXT,
            reviewed_at TEXT,
            review_note TEXT NOT NULL DEFAULT '',
            linked_proposal_ids_json TEXT NOT NULL DEFAULT '[]',
            topic_candidate_id TEXT,
            client_id TEXT,
            project_module_id TEXT,
            data_center_ingest_event_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_external_evidence_scope
        ON external_evidence_cards(related_scope_type, related_scope_id, created_at DESC)
        """
    )
    db.ensure_column("external_evidence_cards", "reviewed_by", "TEXT")
    db.ensure_column("external_evidence_cards", "reviewed_at", "TEXT")
    db.ensure_column("external_evidence_cards", "review_note", "TEXT NOT NULL DEFAULT ''")
    db.ensure_column("external_evidence_cards", "linked_proposal_ids_json", "TEXT NOT NULL DEFAULT '[]'")
    db.ensure_column("external_evidence_cards", "topic_candidate_id", "TEXT")
    db.ensure_column("external_evidence_cards", "client_id", "TEXT")
    db.ensure_column("external_evidence_cards", "project_module_id", "TEXT")
    db.ensure_column("external_evidence_cards", "data_center_ingest_event_id", "TEXT")
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_external_evidence_topic_candidate
        ON external_evidence_cards(topic_candidate_id, created_at DESC)
        """
    )


def _row_to_record(row) -> ExternalEvidenceCardRecord:
    return ExternalEvidenceCardRecord(
        id=str(row["id"]),
        sourceUrl=str(row["source_url"]),
        sourceDomain=str(row["source_domain"]),
        sourceTier=str(row["source_tier"] or "unknown"),  # type: ignore[arg-type]
        title=str(row["title"]),
        publishedAt=str(row["published_at"]) if row["published_at"] else None,
        factExcerpt=str(row["fact_excerpt"] or ""),
        summary=str(row["summary"] or ""),
        tags=[str(item) for item in from_json(str(row["tags_json"] or "[]"), []) if str(item).strip()],
        relatedScopeType=str(row["related_scope_type"]),
        relatedScopeId=str(row["related_scope_id"]),
        confidence=float(row["confidence"] or 0.0),
        status=str(row["status"] or "candidate"),  # type: ignore[arg-type]
        reviewedBy=str(row["reviewed_by"]) if row["reviewed_by"] else None,
        reviewedAt=str(row["reviewed_at"]) if row["reviewed_at"] else None,
        reviewNote=str(row["review_note"] or ""),
        linkedProposalIds=[
            str(item).strip()
            for item in from_json(str(row["linked_proposal_ids_json"] or "[]"), [])
            if str(item).strip()
        ],
        topicCandidateId=str(row["topic_candidate_id"]) if "topic_candidate_id" in row.keys() and row["topic_candidate_id"] else None,
        clientId=str(row["client_id"]) if "client_id" in row.keys() and row["client_id"] else None,
        projectModuleId=str(row["project_module_id"]) if "project_module_id" in row.keys() and row["project_module_id"] else None,
        dataCenterIngestEventId=str(row["data_center_ingest_event_id"]) if "data_center_ingest_event_id" in row.keys() and row["data_center_ingest_event_id"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def list_external_evidence_cards(
    db: Database,
    *,
    related_scope_type: str | None = None,
    related_scope_id: str | None = None,
    topic_candidate_id: str | None = None,
    status: str | None = None,
    limit: int = 120,
) -> list[ExternalEvidenceCardRecord]:
    ensure_external_evidence_schema(db)
    where: list[str] = []
    params: list[object] = []
    if related_scope_type:
        where.append("related_scope_type = ?")
        params.append(related_scope_type)
    if related_scope_id:
        where.append("related_scope_id = ?")
        params.append(related_scope_id)
    if topic_candidate_id:
        where.append("topic_candidate_id = ?")
        params.append(topic_candidate_id)
    if status:
        where.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM external_evidence_cards"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_record(row) for row in rows]


def create_external_evidence_card_from_topic_candidate(
    db: Database,
    *,
    topic_candidate_id: str,
) -> ExternalEvidenceCardRecord:
    ensure_external_evidence_schema(db)
    topic_row = db.fetchone(
        """
        SELECT *
        FROM topic_candidates
        WHERE id = ?
        """,
        (topic_candidate_id,),
    )
    if not topic_row:
        raise KeyError("topic_candidate_not_found")

    source_url = str(topic_row["source_url"] or "").strip()
    if not source_url:
        source_url = f"topic-candidate://{topic_candidate_id}"
    source_domain = _domain(source_url)
    source_tier = "trusted_media" if source_domain else "unknown"
    scope_type = str(topic_row["scope_type"] or "").strip() if "scope_type" in topic_row.keys() else ""
    scope_id = str(topic_row["scope_id"] or "").strip() if "scope_id" in topic_row.keys() else ""
    client_id = str(topic_row["client_id"] or "").strip() if "client_id" in topic_row.keys() and topic_row["client_id"] else ""
    project_module_id = (
        str(topic_row["project_module_id"] or "").strip()
        if "project_module_id" in topic_row.keys() and topic_row["project_module_id"]
        else ""
    )
    data_center_ingest_event_id = (
        str(topic_row["data_center_ingest_event_id"] or "").strip()
        if "data_center_ingest_event_id" in topic_row.keys() and topic_row["data_center_ingest_event_id"]
        else ""
    )
    if not scope_type or not scope_id:
        scope_type = "topic"
        scope_id = topic_candidate_id

    existing = db.fetchone(
        """
        SELECT *
        FROM external_evidence_cards
        WHERE topic_candidate_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (topic_candidate_id,),
    )
    if existing:
        return _row_to_record(existing)

    card_id = new_id("evcard")
    now = _now_iso()
    summary = str(topic_row["summary"] or "")
    excerpt = summary[:220]
    db.execute(
        """
        INSERT INTO external_evidence_cards(
            id, source_url, source_domain, source_tier, title, published_at,
            fact_excerpt, summary, tags_json, related_scope_type, related_scope_id,
            confidence, status, topic_candidate_id, client_id, project_module_id,
            data_center_ingest_event_id, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?)
        """,
        (
            card_id,
            source_url,
            source_domain,
            source_tier,
            str(topic_row["title"] or ""),
            str(topic_row["published_at"]) if topic_row["published_at"] else None,
            excerpt,
            summary,
            to_json(["topic_candidate", str(topic_row["status"] or "unknown")]),
            scope_type,
            scope_id,
            0.68 if str(topic_row["status"] or "").lower() in {"tracking", "promoted"} else 0.55,
            topic_candidate_id,
            client_id or None,
            project_module_id or None,
            data_center_ingest_event_id or None,
            now,
            now,
        ),
    )
    row = db.fetchone("SELECT * FROM external_evidence_cards WHERE id = ?", (card_id,))
    assert row is not None
    return _row_to_record(row)


def accept_external_evidence_card(
    db: Database,
    *,
    card_id: str,
    reviewed_by: str = "user",
    review_note: str = "",
) -> ExternalEvidenceCardRecord:
    ensure_external_evidence_schema(db)
    row = db.fetchone("SELECT * FROM external_evidence_cards WHERE id = ?", (card_id,))
    if not row:
        raise KeyError("external_evidence_card_not_found")
    now = _now_iso()
    db.execute(
        """
        UPDATE external_evidence_cards
        SET status = 'accepted',
            reviewed_by = ?,
            reviewed_at = ?,
            review_note = ?,
            updated_at = ?
        WHERE id = ?
        """,
        ((reviewed_by or "user").strip() or "user", now, (review_note or "").strip(), now, card_id),
    )
    updated = db.fetchone("SELECT * FROM external_evidence_cards WHERE id = ?", (card_id,))
    assert updated is not None
    return _row_to_record(updated)


def reject_external_evidence_card(
    db: Database,
    *,
    card_id: str,
    reviewed_by: str = "user",
    review_note: str = "",
) -> ExternalEvidenceCardRecord:
    ensure_external_evidence_schema(db)
    row = db.fetchone("SELECT * FROM external_evidence_cards WHERE id = ?", (card_id,))
    if not row:
        raise KeyError("external_evidence_card_not_found")
    now = _now_iso()
    db.execute(
        """
        UPDATE external_evidence_cards
        SET status = 'rejected',
            reviewed_by = ?,
            reviewed_at = ?,
            review_note = ?,
            updated_at = ?
        WHERE id = ?
        """,
        ((reviewed_by or "user").strip() or "user", now, (review_note or "").strip(), now, card_id),
    )
    updated = db.fetchone("SELECT * FROM external_evidence_cards WHERE id = ?", (card_id,))
    assert updated is not None
    return _row_to_record(updated)


def _row_to_proposal_draft(row) -> DataCenterProposalDraftRecord:
    return DataCenterProposalDraftRecord(
        id=str(row["id"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        title=str(row["title"]),
        summary=str(row["summary"]),
        rationale=str(row["rationale"]),
        riskLevel=str(row["risk_level"] or "medium"),  # type: ignore[arg-type]
        targetRefs=[
            ProposalTargetRefRecord(**item)
            for item in from_json(str(row["target_refs_json"] or "[]"), [])
            if isinstance(item, dict)
        ],
        sourceRefs=[str(item) for item in from_json(str(row["source_refs_json"] or "[]"), []) if str(item).strip()],
        boundaryNotes=[str(item) for item in from_json(str(row["boundary_notes_json"] or "[]"), []) if str(item).strip()],
        payload=from_json(str(row["payload_json"] or "{}"), {}),
        requiresApproval=True,
        status=str(row["status"] or "draft"),  # type: ignore[arg-type]
        dedupeKey=str(row["dedupe_key"] or ""),
        sourcePrompt=str(row["source_prompt"] or ""),
        scopeType=str(row["scope_type"] or ""),
        scopeId=str(row["scope_id"] or ""),
        clientId=str(row["client_id"]) if row["client_id"] else None,
        page=str(row["page"] or ""),
        mode=str(row["mode"] or "proposal"),
        reviewedAt=str(row["reviewed_at"]) if row["reviewed_at"] else None,
        rejectedAt=str(row["rejected_at"]) if row["rejected_at"] else None,
        rejectedReason=str(row["rejected_reason"]) if row["rejected_reason"] else None,
        promotedProposalId=str(row["promoted_proposal_id"]) if row["promoted_proposal_id"] else None,
        createdAt=str(row["created_at"]) if row["created_at"] else None,
        updatedAt=str(row["updated_at"]) if row["updated_at"] else None,
    )


def create_proposal_draft_from_external_evidence_card(
    db: Database,
    *,
    card_id: str,
) -> DataCenterProposalDraftRecord:
    ensure_external_evidence_schema(db)
    ensure_data_center_proposal_draft_schema(db)
    row = db.fetchone("SELECT * FROM external_evidence_cards WHERE id = ?", (card_id,))
    if not row:
        raise KeyError("external_evidence_card_not_found")
    card = _row_to_record(row)
    if card.status != "accepted":
        raise ValueError("external_evidence_card_not_accepted")

    scope_type = card.relatedScopeType or "topic"
    scope_id = card.relatedScopeId or card.id
    client_id = None
    if scope_type == "client":
        client_id = scope_id
    now = _now_iso()
    source_refs = [card.id, card.sourceUrl, card.sourceDomain]
    title = f"外部证据转提案：{card.title}"
    dedupe_key = build_proposal_dedupe_key(
        scope_type=scope_type,
        scope_id=scope_id,
        kind="evidence_request",
        title=title,
        source_refs=source_refs,
    )
    existing = db.fetchone(
        """
        SELECT *
        FROM data_center_proposal_drafts
        WHERE dedupe_key = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (dedupe_key,),
    )
    if existing:
        return _row_to_proposal_draft(existing)

    draft_id = new_id("dcprop")
    payload = {
        "externalEvidenceCardId": card.id,
        "sourceUrl": card.sourceUrl,
        "sourceDomain": card.sourceDomain,
        "reviewedBy": card.reviewedBy,
        "reviewNote": card.reviewNote,
    }
    db.execute(
        """
        INSERT INTO data_center_proposal_drafts(
            id, scope_type, scope_id, client_id, page, mode, kind, title, summary, rationale,
            risk_level, target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            source_prompt, route_decision_json, answer_plan_json, status, dedupe_key,
            reviewed_at, rejected_at, rejected_reason, promoted_proposal_id, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, 'proposal', 'evidence_request', ?, ?, ?, 'medium', ?, ?, ?, ?, '', '{}', '{}', 'draft', ?, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            draft_id,
            scope_type,
            scope_id,
            client_id,
            "topic_radar" if scope_type == "topic" else "workspace_chat",
            title,
            card.summary or card.factExcerpt or card.title,
            "该外部证据已人工接受，建议转为补证据/复核提案进入审批流。",
            to_json(
                [
                    ProposalTargetRefRecord(
                        targetType="client" if scope_type == "client" else "meeting" if scope_type == "meeting" else "event_line",
                        targetId=scope_id,
                        label=scope_type,
                    ).model_dump(mode="json")
                ]
            ),
            to_json(source_refs),
            to_json(["external evidence 仍属于 candidate 层，不能直接作为 official judgment"]),
            to_json(payload),
            dedupe_key,
            now,
            now,
        ),
    )
    linked_ids = list(dict.fromkeys([*card.linkedProposalIds, draft_id]))
    db.execute(
        """
        UPDATE external_evidence_cards
        SET linked_proposal_ids_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (to_json(linked_ids), now, card.id),
    )
    created = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    assert created is not None
    return _row_to_proposal_draft(created)
