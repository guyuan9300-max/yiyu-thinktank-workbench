from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db import Database, from_json
from app.models import ExperienceStoryDraftRecord


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _json_list(value: Any) -> list[str]:
    parsed = from_json(value, []) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _json_dict(value: Any) -> dict[str, object]:
    parsed = from_json(value, {}) if isinstance(value, str) else value
    return parsed if isinstance(parsed, dict) else {}


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    try:
        value = row[key]
    except Exception:
        return default
    return default if value is None else value


def build_experience_story_draft_record(db: Database, row: Any) -> ExperienceStoryDraftRecord:
    client_id = _row_value(row, "client_id")
    client_name = _row_value(row, "client_name")
    if client_id and not client_name:
        client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
        if client_row:
            client_name = client_row["name"]
    return ExperienceStoryDraftRecord(
        id=str(_row_value(row, "id", "")),
        title=str(_row_value(row, "title", "")),
        story=str(_row_value(row, "story", "")),
        status=str(_row_value(row, "status", "candidate")),
        sourceType=str(_row_value(row, "source_type", "")),
        sourceId=str(_row_value(row, "source_id", "")),
        sourceTitle=str(_row_value(row, "source_title", "")),
        clientId=str(client_id) if client_id else None,
        clientName=str(client_name) if client_name else None,
        eventLineId=str(_row_value(row, "event_line_id")) if _row_value(row, "event_line_id") else None,
        eventLineName=str(_row_value(row, "event_line_name")) if _row_value(row, "event_line_name") else None,
        taskId=str(_row_value(row, "task_id")) if _row_value(row, "task_id") else None,
        meetingId=str(_row_value(row, "meeting_id")) if _row_value(row, "meeting_id") else None,
        handbookEntryId=str(_row_value(row, "handbook_entry_id")) if _row_value(row, "handbook_entry_id") else None,
        evidenceRefs=_json_list(_row_value(row, "evidence_refs_json", "[]")),
        materialPack=_json_dict(_row_value(row, "material_pack_json", "{}")),
        growthValue=str(_row_value(row, "growth_value", "")),
        organizationValue=str(_row_value(row, "organization_value", "")),
        qualityScore=_json_dict(_row_value(row, "quality_score_json", "{}")),
        factRiskNote=str(_row_value(row, "fact_risk_note", "")),
        generationModel=str(_row_value(row, "generation_model", "")),
        generationPromptVersion=str(_row_value(row, "generation_prompt_version", "")),
        createdAt=str(_row_value(row, "created_at", _now_iso())),
        updatedAt=str(_row_value(row, "updated_at", _now_iso())),
        approvedAt=str(_row_value(row, "approved_at")) if _row_value(row, "approved_at") else None,
        approvedBy=str(_row_value(row, "approved_by")) if _row_value(row, "approved_by") else None,
    )


def list_experience_story_drafts(
    db: Database,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[ExperienceStoryDraftRecord]:
    where = ""
    params: list[object] = []
    if status:
        where = "WHERE status = ?"
        params.append(status)
    params.append(max(1, min(int(limit or 100), 200)))
    try:
        rows = db.fetchall(
            f"SELECT * FROM experience_story_drafts {where} ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        )
    except Exception:
        return []
    return [build_experience_story_draft_record(db, row) for row in rows]


def generate_experience_story_drafts(
    db: Database,
    ai_service: object | None,
    *,
    limit: int = 5,
) -> tuple[list[ExperienceStoryDraftRecord], int]:
    # The full story generator is intentionally kept behind a compatibility shell here.
    # It prevents app startup from failing while preserving existing drafts and actions.
    return (list_experience_story_drafts(db, status="candidate", limit=limit), 0)


def reject_experience_story_draft(db: Database, *, draft_id: str) -> ExperienceStoryDraftRecord | None:
    row = db.fetchone("SELECT * FROM experience_story_drafts WHERE id = ?", (draft_id,))
    if not row:
        return None
    updated_at = _now_iso()
    db.execute(
        "UPDATE experience_story_drafts SET status = 'rejected', updated_at = ? WHERE id = ?",
        (updated_at, draft_id),
    )
    updated = db.fetchone("SELECT * FROM experience_story_drafts WHERE id = ?", (draft_id,))
    return build_experience_story_draft_record(db, updated) if updated else None


def regenerate_experience_story_draft(
    db: Database,
    ai_service: object | None,
    *,
    draft_id: str,
) -> ExperienceStoryDraftRecord | None:
    row = db.fetchone("SELECT * FROM experience_story_drafts WHERE id = ?", (draft_id,))
    if not row:
        return None
    updated_at = _now_iso()
    db.execute(
        "UPDATE experience_story_drafts SET status = 'candidate', updated_at = ? WHERE id = ?",
        (updated_at, draft_id),
    )
    updated = db.fetchone("SELECT * FROM experience_story_drafts WHERE id = ?", (draft_id,))
    return build_experience_story_draft_record(db, updated) if updated else None
