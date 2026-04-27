from __future__ import annotations

import hashlib
import re
from datetime import datetime

from app.db import Database, from_json, to_json
from app.models import (
    ActionSuggestionRecord,
    AnswerPlanRecord,
    DataCenterProposalDraftRecord,
    DataCenterRequestRecord,
    PageContextPackRecord,
    ProposalTargetRefRecord,
    RouteDecisionRecord,
)
from app.services.knowledge_v2 import new_id
from app.services.meeting_followup import build_meeting_followup_proposal_drafts


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_data_center_proposal_draft_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS data_center_proposal_drafts (
            id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            client_id TEXT,
            page TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'proposal',
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            rationale TEXT NOT NULL,
            risk_level TEXT NOT NULL DEFAULT 'medium',
            target_refs_json TEXT NOT NULL DEFAULT '[]',
            source_refs_json TEXT NOT NULL DEFAULT '[]',
            boundary_notes_json TEXT NOT NULL DEFAULT '[]',
            payload_json TEXT NOT NULL DEFAULT '{}',
            source_prompt TEXT NOT NULL DEFAULT '',
            route_decision_json TEXT NOT NULL DEFAULT '{}',
            answer_plan_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'draft',
            dedupe_key TEXT NOT NULL,
            reviewed_at TEXT,
            rejected_at TEXT,
            rejected_reason TEXT,
            promoted_proposal_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_data_center_proposal_drafts_scope
        ON data_center_proposal_drafts(scope_type, scope_id, created_at DESC)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_data_center_proposal_drafts_dedupe
        ON data_center_proposal_drafts(dedupe_key)
        """
    )


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _source_refs_hash(source_refs: list[str]) -> str:
    normalized = sorted({str(item or "").strip() for item in source_refs if str(item or "").strip()})
    joined = "|".join(normalized)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]


def build_proposal_dedupe_key(
    *,
    scope_type: str,
    scope_id: str,
    kind: str,
    title: str,
    source_refs: list[str],
) -> str:
    normalized_title = _normalize_title(title)
    refs_hash = _source_refs_hash(source_refs)
    return f"{scope_type}:{scope_id}:{kind}:{normalized_title}:{refs_hash}"


def _row_to_draft(row) -> DataCenterProposalDraftRecord:
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
        dedupeKey=str(row["dedupe_key"]),
        sourcePrompt=str(row["source_prompt"] or ""),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        clientId=str(row["client_id"]) if row["client_id"] else None,
        page=str(row["page"]),
        mode=str(row["mode"] or "proposal"),
        reviewedAt=str(row["reviewed_at"]) if row["reviewed_at"] else None,
        rejectedAt=str(row["rejected_at"]) if row["rejected_at"] else None,
        rejectedReason=str(row["rejected_reason"]) if row["rejected_reason"] else None,
        promotedProposalId=str(row["promoted_proposal_id"]) if row["promoted_proposal_id"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _target_refs_from_scope(page_context: PageContextPackRecord) -> list[ProposalTargetRefRecord]:
    refs: list[ProposalTargetRefRecord] = []
    if page_context.clientId:
        refs.append(ProposalTargetRefRecord(targetType="client", targetId=page_context.clientId, label="客户"))
    refs.append(ProposalTargetRefRecord(targetType="task" if page_context.scopeType == "task" else "client", targetId=page_context.scopeId, label=page_context.scopeType))
    return refs


def build_data_center_proposal_drafts(
    *,
    request: DataCenterRequestRecord,
    page_context: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
    action_suggestions: list[ActionSuggestionRecord],
) -> list[DataCenterProposalDraftRecord]:
    drafts: list[DataCenterProposalDraftRecord] = []
    target_refs = _target_refs_from_scope(page_context)

    if page_context.missingContext and route_decision.intent in {
        "intro_profile",
        "business_profile",
        "strategy_profile",
        "evidence_question",
    }:
        drafts.append(
            DataCenterProposalDraftRecord(
                kind="evidence_request",
                title="补证据提案",
                summary="当前缺少关键原文证据，建议先补证据后再形成正式判断。",
                rationale="避免在证据不足时继续输出不稳定结论。",
                riskLevel="medium",
                targetRefs=target_refs,
                sourceRefs=page_context.missingContext[:6],
                boundaryNotes=page_context.boundaryNotes[:4],
                payload={"missingContext": page_context.missingContext[:10]},
                requiresApproval=True,
            )
        )

    if page_context.candidateJudgments and not page_context.officialJudgments:
        drafts.append(
            DataCenterProposalDraftRecord(
                kind="judgment_review",
                title="候选判断复核提案",
                summary="存在候选判断但缺少已批准判断，建议进入复核流程。",
                rationale="将候选判断与正式判断边界拉清，避免长期悬置。",
                riskLevel="medium",
                targetRefs=target_refs,
                sourceRefs=["candidate_judgments"],
                boundaryNotes=["候选判断不能直接当作已批准结论"],
                payload={"candidateCount": len(page_context.candidateJudgments)},
                requiresApproval=True,
            )
        )

    if page_context.quality.contextQuality in {"weak", "none"}:
        drafts.append(
            DataCenterProposalDraftRecord(
                kind="context_refresh",
                title="上下文刷新提案",
                summary="状态池覆盖不足，建议触发 context pack 刷新与回填。",
                rationale="降低弱状态下的检索/回答误差。",
                riskLevel="low",
                targetRefs=target_refs,
                sourceRefs=[f"contextQuality={page_context.quality.contextQuality}"],
                boundaryNotes=[],
                payload={"contextQuality": page_context.quality.contextQuality},
                requiresApproval=True,
            )
        )

    if route_decision.intent in {"meeting_summary"} or request.scope.scopeType == "meeting":
        drafts.append(
            DataCenterProposalDraftRecord(
                kind="meeting_prep",
                title="会议准备提案",
                summary="根据当前会议上下文生成结构化会前准备。",
                rationale="提升会议决策效率并减少会后返工。",
                riskLevel="medium",
                targetRefs=target_refs,
                sourceRefs=["meeting_context"],
                boundaryNotes=page_context.boundaryNotes[:4],
                payload={"meetingId": request.scope.meetingId or request.scope.scopeId},
                requiresApproval=True,
            )
        )
        drafts.extend(
            build_meeting_followup_proposal_drafts(
                meeting_context=page_context,
            )
        )

    for suggestion in action_suggestions[:8]:
        if suggestion.actionType == "create_proposal":
            drafts.append(
                DataCenterProposalDraftRecord(
                    kind="task_prep",
                    title=suggestion.title,
                    summary=suggestion.summary,
                    rationale=suggestion.rationale,
                    riskLevel=suggestion.riskLevel,
                    targetRefs=suggestion.targetRefs,
                    sourceRefs=suggestion.sourceRefs,
                    boundaryNotes=page_context.boundaryNotes[:4],
                    payload={"actionSuggestionId": suggestion.id, "actionType": suggestion.actionType},
                    requiresApproval=True,
                )
            )

    dedup: dict[tuple[str, str], DataCenterProposalDraftRecord] = {}
    for draft in drafts:
        key = (draft.kind, draft.title)
        if key not in dedup:
            dedup[key] = draft
    return list(dedup.values())[:12]


def persist_data_center_proposal_drafts(
    db: Database,
    *,
    request: DataCenterRequestRecord,
    route_decision: RouteDecisionRecord,
    answer_plan: AnswerPlanRecord | None,
    drafts: list[DataCenterProposalDraftRecord],
) -> tuple[list[DataCenterProposalDraftRecord], list[str], list[str]]:
    ensure_data_center_proposal_draft_schema(db)
    persisted_ids: list[str] = []
    deduped_ids: list[str] = []
    returned: list[DataCenterProposalDraftRecord] = []
    now = _now_iso()

    for draft in drafts:
        dedupe_key = build_proposal_dedupe_key(
            scope_type=request.scope.scopeType,
            scope_id=request.scope.scopeId,
            kind=draft.kind,
            title=draft.title,
            source_refs=draft.sourceRefs,
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
        if existing and str(existing["status"] or "") in {"draft", "reviewed", "promoted"}:
            deduped_ids.append(str(existing["id"]))
            returned.append(_row_to_draft(existing))
            continue

        draft_id = new_id("dcprop")
        db.execute(
            """
            INSERT INTO data_center_proposal_drafts(
                id, scope_type, scope_id, client_id, page, mode, kind, title, summary, rationale,
                risk_level, target_refs_json, source_refs_json, boundary_notes_json, payload_json,
                source_prompt, route_decision_json, answer_plan_json, status, dedupe_key,
                reviewed_at, rejected_at, rejected_reason, promoted_proposal_id, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                draft_id,
                request.scope.scopeType,
                request.scope.scopeId,
                request.scope.clientId,
                request.scope.page,
                "proposal",
                draft.kind,
                draft.title,
                draft.summary,
                draft.rationale,
                draft.riskLevel,
                to_json([item.model_dump(mode="json") for item in draft.targetRefs]),
                to_json(draft.sourceRefs),
                to_json(draft.boundaryNotes),
                to_json(draft.payload),
                request.prompt,
                to_json(route_decision.model_dump(mode="json")),
                to_json(answer_plan.model_dump(mode="json") if answer_plan else {}),
                dedupe_key,
                now,
                now,
            ),
        )
        persisted_ids.append(draft_id)
        returned.append(
            draft.model_copy(
                update={
                    "id": draft_id,
                    "status": "draft",
                    "dedupeKey": dedupe_key,
                    "sourcePrompt": request.prompt,
                    "scopeType": request.scope.scopeType,
                    "scopeId": request.scope.scopeId,
                    "clientId": request.scope.clientId,
                    "page": request.scope.page,
                    "mode": "proposal",
                    "createdAt": now,
                    "updatedAt": now,
                }
            )
        )
    return returned, persisted_ids, deduped_ids


def list_data_center_proposal_drafts(
    db: Database,
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
    client_id: str | None = None,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 60,
) -> list[DataCenterProposalDraftRecord]:
    ensure_data_center_proposal_draft_schema(db)
    where: list[str] = []
    params: list[object] = []
    if scope_type:
        where.append("scope_type = ?")
        params.append(scope_type)
    if scope_id:
        where.append("scope_id = ?")
        params.append(scope_id)
    if client_id:
        where.append("client_id = ?")
        params.append(client_id)
    if status:
        where.append("status = ?")
        params.append(status)
    if kind:
        where.append("kind = ?")
        params.append(kind)
    sql = "SELECT * FROM data_center_proposal_drafts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    rows = db.fetchall(sql, tuple(params))
    return [_row_to_draft(row) for row in rows]


def get_data_center_proposal_draft(
    db: Database,
    *,
    draft_id: str,
) -> DataCenterProposalDraftRecord | None:
    ensure_data_center_proposal_draft_schema(db)
    row = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    if not row:
        return None
    return _row_to_draft(row)


def create_data_center_proposal_draft(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    client_id: str | None,
    page: str,
    source_prompt: str,
    draft: DataCenterProposalDraftRecord,
) -> DataCenterProposalDraftRecord:
    ensure_data_center_proposal_draft_schema(db)
    now = _now_iso()
    dedupe_key = build_proposal_dedupe_key(
        scope_type=scope_type,
        scope_id=scope_id,
        kind=draft.kind,
        title=draft.title,
        source_refs=draft.sourceRefs,
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
    if existing and str(existing["status"] or "") in {"draft", "reviewed", "promoted"}:
        return _row_to_draft(existing)

    draft_id = draft.id or new_id("dcprop")
    db.execute(
        """
        INSERT INTO data_center_proposal_drafts(
            id, scope_type, scope_id, client_id, page, mode, kind, title, summary, rationale,
            risk_level, target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            source_prompt, route_decision_json, answer_plan_json, status, dedupe_key,
            reviewed_at, rejected_at, rejected_reason, promoted_proposal_id, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', '{}', ?, ?, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            draft_id,
            scope_type,
            scope_id,
            client_id,
            page,
            draft.mode or "proposal",
            draft.kind,
            draft.title,
            draft.summary,
            draft.rationale,
            draft.riskLevel,
            to_json([item.model_dump(mode="json") for item in draft.targetRefs]),
            to_json([str(item) for item in draft.sourceRefs if str(item).strip()]),
            to_json([str(item) for item in draft.boundaryNotes if str(item).strip()]),
            to_json(draft.payload),
            source_prompt,
            draft.status if draft.status in {"draft", "reviewed", "rejected", "promoted", "expired"} else "draft",
            dedupe_key,
            now,
            now,
        ),
    )
    row = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    assert row is not None
    return _row_to_draft(row)


def mark_data_center_proposal_draft_promoted(
    db: Database,
    *,
    draft_id: str,
    promoted_ref_id: str,
) -> DataCenterProposalDraftRecord:
    ensure_data_center_proposal_draft_schema(db)
    now = _now_iso()
    db.execute(
        """
        UPDATE data_center_proposal_drafts
        SET status = 'promoted',
            promoted_proposal_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (promoted_ref_id, now, draft_id),
    )
    row = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    if not row:
        raise KeyError("proposal_draft_not_found")
    return _row_to_draft(row)


def mark_data_center_proposal_draft_reviewed(
    db: Database,
    *,
    draft_id: str,
    note: str = "",
) -> DataCenterProposalDraftRecord:
    ensure_data_center_proposal_draft_schema(db)
    existing = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    if not existing:
        raise KeyError("proposal_draft_not_found")
    now = _now_iso()
    payload = from_json(str(existing["payload_json"] or "{}"), {})
    if not isinstance(payload, dict):
        payload = {}
    if note.strip():
        payload["reviewNote"] = note.strip()
    db.execute(
        """
        UPDATE data_center_proposal_drafts
        SET status = 'reviewed',
            reviewed_at = ?,
            updated_at = ?,
            payload_json = ?
        WHERE id = ?
        """,
        (now, now, to_json(payload), draft_id),
    )
    row = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    assert row is not None
    return _row_to_draft(row)


def reject_data_center_proposal_draft(
    db: Database,
    *,
    draft_id: str,
    reason: str = "",
) -> DataCenterProposalDraftRecord:
    ensure_data_center_proposal_draft_schema(db)
    existing = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    if not existing:
        raise KeyError("proposal_draft_not_found")
    now = _now_iso()
    db.execute(
        """
        UPDATE data_center_proposal_drafts
        SET status = 'rejected',
            rejected_at = ?,
            rejected_reason = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now, (reason or "人工驳回").strip(), now, draft_id),
    )
    row = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    assert row is not None
    return _row_to_draft(row)


def _map_draft_kind_to_proposal_kind(kind: str) -> str:
    if kind in {
        "task_prep",
        "meeting_prep",
        "meeting_followup",
        "evidence_request",
        "judgment_review",
        "context_refresh",
    }:
        return kind
    return "task_prep"


def promote_data_center_proposal_draft(
    db: Database,
    *,
    draft_id: str,
    created_by: str = "system",
    note: str = "",
) -> tuple[DataCenterProposalDraftRecord, str]:
    ensure_data_center_proposal_draft_schema(db)
    existing = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    if not existing:
        raise KeyError("proposal_draft_not_found")

    status = str(existing["status"] or "draft")
    if status not in {"draft", "reviewed", "promoted"}:
        raise ValueError("proposal_draft_not_promotable")

    if existing["promoted_proposal_id"]:
        proposal_id = str(existing["promoted_proposal_id"])
        row = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
        assert row is not None
        return _row_to_draft(row), proposal_id

    client_id = str(existing["client_id"] or "").strip()
    if not client_id:
        raise ValueError("proposal_draft_missing_client")

    draft_kind = str(existing["kind"] or "task_prep")
    proposal_kind = _map_draft_kind_to_proposal_kind(draft_kind)
    now = _now_iso()
    proposal_id = new_id("proposal")
    payload = from_json(str(existing["payload_json"] or "{}"), {})
    if not isinstance(payload, dict):
        payload = {}
    payload["dataCenterDraftKind"] = draft_kind
    if note.strip():
        payload["promoteNote"] = note.strip()

    db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, ?, 'pending_review', ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            proposal_id,
            client_id,
            proposal_kind,
            str(existing["risk_level"] or "medium"),
            str(existing["title"] or ""),
            str(existing["summary"] or ""),
            str(existing["rationale"] or ""),
            str(existing["target_refs_json"] or "[]"),
            str(existing["source_refs_json"] or "[]"),
            str(existing["boundary_notes_json"] or "[]"),
            to_json(payload),
            created_by.strip() or "system",
            now,
            now,
        ),
    )
    db.execute(
        """
        UPDATE data_center_proposal_drafts
        SET status = 'promoted',
            promoted_proposal_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (proposal_id, now, draft_id),
    )
    row = db.fetchone("SELECT * FROM data_center_proposal_drafts WHERE id = ?", (draft_id,))
    assert row is not None
    return _row_to_draft(row), proposal_id
