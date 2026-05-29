from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


TASK_PREFIXES = (
    "task_created_",
    "task_deadline_",
    "task_ddl_set_",
    "task_done_on_time_",
    "task_closed_",
    "task_same_day_",
    "task_desc_ok_",
    "task_learning_done_",
)

ACTIVITY_PREFIXES = (
    "task_quick_confirm_",
    "task_updated_",
    "task_attach_",
    "task_ddl_adj_",
    "task_assigned_",
    "analysis_share_",
    "topic_promote_",
    "ai_prompt_",
    "ai_assist_",
    "ai_insight_",
    "ai_reviewed_",
    "client_enriched_",
    "client_key_person_",
    "crm_lead_",
    "crm_followup_",
    "template_used_",
)

REVIEW_PREFIXES = (
    "review_structured_",
    "review_retrospective_",
    "review_risk_",
    "review_acceptance_",
    "review_handoff_",
)

HANDBOOK_PREFIXES = (
    "handbook_entry_",
    "handbook_sop_",
    "handbook_share_",
)

MEETING_PREFIXES = (
    "meeting_published_",
    "meeting_closed_loop_",
    "meeting_cross_",
    "meeting_risk_",
    "meeting_clarity_",
)

EVENT_LINE_PREFIXES = (
    "eline_followup_",
    "eline_stage_",
)


def _normalize_name(value: object | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _id_matches(value: object | None, user_id: str) -> bool:
    raw = str(value or "").strip()
    return bool(raw and raw == user_id)


def _name_matches(value: object | None, user_name: str) -> bool:
    raw = _normalize_name(value)
    return bool(raw and raw == _normalize_name(user_name))


def _json_loads(value: object | None, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except Exception:
        return fallback


def _detail_matches(detail: dict[str, Any], *, user_id: str, user_name: str) -> bool:
    for key in ("ownerId", "owner_id", "creatorId", "creator_id", "actorId", "actor_id", "userId", "user_id"):
        if _id_matches(detail.get(key), user_id):
            return True
    for key in ("ownerName", "owner_name", "actorName", "actor_name", "userName", "user_name", "createdBy"):
        if _name_matches(detail.get(key), user_name):
            return True
    collaborator_ids = detail.get("collaboratorIds") or detail.get("collaborator_ids") or []
    return isinstance(collaborator_ids, list) and user_id in {str(item or "").strip() for item in collaborator_ids}


def _strip_prefix(value: str, prefixes: tuple[str, ...]) -> tuple[str | None, str]:
    for prefix in prefixes:
        if value.startswith(prefix):
            return prefix.rstrip("_"), value[len(prefix) :]
    return None, value


def _fetch_one(conn: sqlite3.Connection, query: str, params: tuple[object, ...]) -> sqlite3.Row | None:
    return conn.execute(query, params).fetchone()


def _task_belongs(conn: sqlite3.Connection, task_id: str, *, user_id: str, user_name: str) -> str:
    row = _fetch_one(conn, "SELECT id, owner_id, creator_id, owner_name FROM tasks WHERE id = ?", (task_id,))
    if row is None:
        return "missing_source"
    if _id_matches(row["owner_id"], user_id) or _id_matches(row["creator_id"], user_id) or _name_matches(row["owner_name"], user_name):
        return "ok"
    collaborator = _fetch_one(conn, "SELECT 1 FROM task_collaborators WHERE task_id = ? AND user_id = ?", (task_id, user_id))
    return "ok" if collaborator else "owner_mismatch"


def _activity_belongs(conn: sqlite3.Connection, log_id: str, *, user_id: str, user_name: str) -> str:
    row = _fetch_one(conn, "SELECT actor_name, detail_json FROM activity_logs WHERE id = ?", (log_id,))
    if row is None:
        return "missing_source"
    detail = _json_loads(row["detail_json"], {})
    if not isinstance(detail, dict):
        detail = {}
    return "ok" if _name_matches(row["actor_name"], user_name) or _detail_matches(detail, user_id=user_id, user_name=user_name) else "actor_mismatch"


def _review_belongs(conn: sqlite3.Connection, entry_id: str, *, user_id: str) -> str:
    row = _fetch_one(
        conn,
        """
        SELECT wr.operator_id, wr.user_id
        FROM weekly_review_task_entries e
        INNER JOIN weekly_reviews wr ON wr.id = e.review_id
        WHERE e.id = ?
        """,
        (entry_id,),
    )
    if row is None:
        return "missing_source"
    return "ok" if _id_matches(row["operator_id"], user_id) or _id_matches(row["user_id"], user_id) else "operator_mismatch"


def _handbook_belongs(conn: sqlite3.Connection, entry_id: str, *, user_id: str, user_name: str) -> str:
    row = _fetch_one(conn, "SELECT author_user_id, author_user_name FROM handbook_entries WHERE id = ?", (entry_id,))
    if row is None:
        return "missing_source"
    if not str(row["author_user_id"] or "").strip() and not str(row["author_user_name"] or "").strip():
        return "unknown_owner"
    return "ok" if _id_matches(row["author_user_id"], user_id) or _name_matches(row["author_user_name"], user_name) else "author_mismatch"


def _meeting_belongs(conn: sqlite3.Connection, meeting_id: str, *, user_id: str, user_name: str) -> str:
    meeting = _fetch_one(conn, "SELECT id FROM meetings WHERE id = ?", (meeting_id,))
    if meeting is None:
        return "missing_source"
    action = _fetch_one(conn, "SELECT 1 FROM action_items WHERE meeting_id = ? AND LOWER(TRIM(owner_name)) = LOWER(TRIM(?))", (meeting_id, user_name))
    if action:
        return "ok"
    linked_task = _fetch_one(
        conn,
        """
        SELECT 1
        FROM tasks t
        WHERE t.source_type = 'meeting'
          AND t.source_id = ?
          AND (
            t.owner_id = ?
            OR t.creator_id = ?
            OR LOWER(TRIM(COALESCE(t.owner_name, ''))) = LOWER(TRIM(?))
            OR EXISTS (SELECT 1 FROM task_collaborators tc WHERE tc.task_id = t.id AND tc.user_id = ?)
          )
        LIMIT 1
        """,
        (meeting_id, user_id, user_id, user_name, user_id),
    )
    return "ok" if linked_task else "participant_mismatch"


def _event_line_belongs(conn: sqlite3.Connection, activity_id: str, *, user_id: str, user_name: str) -> str:
    row = _fetch_one(conn, "SELECT actor_id, actor_name FROM event_line_activities WHERE id = ?", (activity_id,))
    if row is None:
        return "missing_source"
    return "ok" if _id_matches(row["actor_id"], user_id) or _name_matches(row["actor_name"], user_name) else "actor_mismatch"


def classify_evidence(conn: sqlite3.Connection, evidence_id: str, *, user_id: str, user_name: str) -> str:
    _kind, source_id = _strip_prefix(evidence_id, TASK_PREFIXES)
    if _kind:
        return _task_belongs(conn, source_id, user_id=user_id, user_name=user_name)
    _kind, source_id = _strip_prefix(evidence_id, ACTIVITY_PREFIXES)
    if _kind:
        return _activity_belongs(conn, source_id, user_id=user_id, user_name=user_name)
    _kind, source_id = _strip_prefix(evidence_id, REVIEW_PREFIXES)
    if _kind:
        return _review_belongs(conn, source_id, user_id=user_id)
    _kind, source_id = _strip_prefix(evidence_id, HANDBOOK_PREFIXES)
    if _kind:
        return _handbook_belongs(conn, source_id, user_id=user_id, user_name=user_name)
    _kind, source_id = _strip_prefix(evidence_id, MEETING_PREFIXES)
    if _kind:
        return _meeting_belongs(conn, source_id, user_id=user_id, user_name=user_name)
    _kind, source_id = _strip_prefix(evidence_id, EVENT_LINE_PREFIXES)
    if _kind:
        return _event_line_belongs(conn, source_id, user_id=user_id, user_name=user_name)
    if evidence_id.startswith("validation_reuse_"):
        validation_id = evidence_id.removeprefix("validation_reuse_")
        row = _fetch_one(conn, "SELECT user_id FROM growth_validation_events WHERE id = ?", (validation_id,))
        if row is None:
            return "missing_source"
        return "ok" if _id_matches(row["user_id"], user_id) else "user_mismatch"
    return "unsupported_evidence_id"


def audit(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, user_id, user_name, badge_id, badge_name, evidence_ids_json, unlocked_at
            FROM badge_unlock_records
            ORDER BY unlocked_at DESC
            """
        ).fetchall()
        suspicious: list[dict[str, Any]] = []
        checked_evidence = 0
        for row in rows:
            evidence_ids = _json_loads(row["evidence_ids_json"], [])
            if not isinstance(evidence_ids, list):
                evidence_ids = []
            for evidence_id in evidence_ids:
                checked_evidence += 1
                status = classify_evidence(conn, str(evidence_id), user_id=str(row["user_id"]), user_name=str(row["user_name"] or ""))
                if status != "ok":
                    suspicious.append(
                        {
                            "unlockId": str(row["id"]),
                            "userId": str(row["user_id"]),
                            "userName": str(row["user_name"] or ""),
                            "badgeId": str(row["badge_id"]),
                            "badgeName": str(row["badge_name"]),
                            "evidenceId": str(evidence_id),
                            "status": status,
                            "unlockedAt": str(row["unlocked_at"] or ""),
                        }
                    )
        return {
            "database": str(db_path),
            "checkedUnlocks": len(rows),
            "checkedEvidence": checked_evidence,
            "suspiciousCount": len(suspicious),
            "suspicious": suspicious,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit badge unlock evidence ownership without mutating the database.")
    parser.add_argument("db", type=Path, help="Path to app.db")
    args = parser.parse_args()
    print(json.dumps(audit(args.db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
