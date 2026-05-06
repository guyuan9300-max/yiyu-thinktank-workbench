from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.db import Database, from_json, to_json


TASK_CONTEXT_BRIEF_PROMPT_VERSION = "task-context-brief-v1"

_GENERIC_TASK_PATTERNS = (
    "先补齐项目背景",
    "最核心的推进事项",
    "当前没有特别突出的阻塞",
    "还没有写下一步动作",
    "根据最近会议形成明确后续安排",
)
_NOISE_MARKERS = (
    "WPS 文字",
    "On-screen Show",
    "PowerPoint 演示文稿",
    "Office Theme",
    "Wingdings",
    "Arial Unicode",
    "已用的字体",
)
_DOMAIN_KEYWORDS = (
    "云南",
    "儿童",
    "报告",
    "结构",
    "工作坊",
    "评分",
    "评审",
    "尽调",
    "机构",
    "案例",
    "资助",
    "PPT",
    "章节",
    "数据",
    "乡村发展基金会",
    "乡基会",
    "品牌",
    "平台",
    "框架",
    "合同",
    "报价",
    "开源",
    "顾问",
    "共创",
    "交付",
    "边界",
)
_TEMPLATE_RESTATEMENT_PATTERNS = (
    r"本任务为",
    r"截止时间",
    r"过往已有\s*\d+\s*项",
    r"过去已(?:完成|记录).{0,8}\d+\s*项",
    r"启示[:：]",
    r"前情[:：]",
    r"后续[:：]",
)
_NEXT_STEP_HINTS = ("容易漏", "不要", "需注意", "下一步", "先", "边界", "避免", "否则", "确认", "核对")


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _compact_text(value: object, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _is_generic_text(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return any(pattern in text for pattern in _GENERIC_TASK_PATTERNS)


def _looks_like_noise(value: object) -> bool:
    text = str(value or "")
    if not text.strip():
        return True
    marker_count = sum(1 for marker in _NOISE_MARKERS if marker in text)
    if marker_count >= 2:
        return True
    cleaned = re.sub(r"[\s\d.,:：;；()（）/\\-]+", "", text)
    return len(cleaned) < 16 and len(text) > 80


def _row_dict(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _task_row_to_pack(row: dict[str, Any]) -> dict[str, object]:
    description = _compact_text(row.get("description"), 720)
    current_blocker = "" if _is_generic_text(row.get("current_blocker")) else _compact_text(row.get("current_blocker"), 320)
    next_action = "" if _is_generic_text(row.get("next_action")) else _compact_text(row.get("next_action"), 360)
    recent_decision = "" if _is_generic_text(row.get("recent_decision")) else _compact_text(row.get("recent_decision"), 520)
    return {
        "id": str(row.get("id") or ""),
        "title": str(row.get("title") or ""),
        "status": str(row.get("status") or ""),
        "dueDate": row.get("due_date"),
        "description": description,
        "currentBlocker": current_blocker,
        "nextAction": next_action,
        "recentDecision": recent_decision,
        "clientId": row.get("client_id"),
        "eventLineId": row.get("event_line_id"),
        "sourceType": str(row.get("source_type") or ""),
    }


def _split_keywords(text: str) -> list[str]:
    found: list[str] = []
    for keyword in _DOMAIN_KEYWORDS:
        if keyword in text:
            found.append(keyword)
    for item in re.split(r"[\s,，。；;:：|/\\()（）《》【】\[\]·\-]+", text):
        item = item.strip()
        if item.isdigit():
            continue
        if len(item) >= 2:
            found.append(item[:20])
    seen: set[str] = set()
    result: list[str] = []
    for item in found:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(item)
    return result[:48]


def _derive_keywords(pack_seed: dict[str, object]) -> list[str]:
    parts: list[str] = []
    for value in pack_seed.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.extend(str(v) for v in value.values() if isinstance(v, str))
        elif isinstance(value, list):
            for item in value[:12]:
                if isinstance(item, dict):
                    parts.extend(str(v) for v in item.values() if isinstance(v, str))
                elif isinstance(item, str):
                    parts.append(item)
    return _split_keywords(" ".join(parts))


def _score_chunk(row: dict[str, Any], keywords: list[str]) -> int:
    file_name = str(row.get("file_name") or "")
    section = str(row.get("section_label") or "")
    content = str(row.get("content") or "")
    haystack = f"{file_name} {section} {content}".lower()
    score = 0
    for keyword in keywords:
        key = keyword.lower()
        if not key:
            continue
        if key in file_name.lower():
            score += 7
        if key in section.lower():
            score += 4
        if key in haystack:
            score += 1
    if row.get("source_entity_type") == "task":
        score -= 2
    if str(row.get("kind") or "") == "task_doc" and any(pattern in content for pattern in _GENERIC_TASK_PATTERNS):
        score -= 4
    return score


def _select_data_center_chunks(db: Database, client_id: str, keywords: list[str]) -> list[dict[str, object]]:
    if not client_id or not keywords:
        return []
    rows = db.fetchall(
        """
        SELECT
            vd.id AS document_id,
            vd.file_name,
            vd.kind,
            vd.source_entity_type,
            vd.source_entity_id,
            c.chunk_index,
            COALESCE(c.section_label, '') AS section_label,
            c.content,
            c.char_count
        FROM v2_documents vd
        JOIN v2_chunks c ON c.v2_document_id = vd.id
        WHERE vd.client_id = ?
          AND COALESCE(vd.is_searchable, 1) = 1
          AND COALESCE(vd.lifecycle_status, 'active') = 'active'
        """,
        (client_id,),
    )
    scored: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        content = str(row.get("content") or "")
        if _looks_like_noise(content):
            continue
        score = _score_chunk(row, keywords)
        if score <= 0:
            continue
        row["_score"] = score
        scored.append(row)
    scored.sort(key=lambda item: (-int(item.get("_score") or 0), str(item.get("file_name") or ""), int(item.get("chunk_index") or 0)))

    picked: list[dict[str, object]] = []
    per_doc_count: dict[str, int] = {}
    for row in scored:
        doc_id = str(row.get("document_id") or "")
        if per_doc_count.get(doc_id, 0) >= 4:
            continue
        picked.append(
            {
                "sourceType": "v2_chunk",
                "sourceId": f"{doc_id}:{row.get('chunk_index')}",
                "fileName": str(row.get("file_name") or ""),
                "section": str(row.get("section_label") or ""),
                "content": _compact_text(row.get("content"), 560),
                "score": int(row.get("_score") or 0),
            }
        )
        per_doc_count[doc_id] = per_doc_count.get(doc_id, 0) + 1
        if len(picked) >= 18:
            break
    return picked


def _fetch_task_notes(db: Database, task_id: str) -> list[dict[str, object]]:
    rows = db.fetchall(
        "SELECT note, created_at FROM task_notes WHERE task_id = ? ORDER BY updated_at DESC LIMIT 4",
        (task_id,),
    )
    return [{"note": _compact_text(row["note"], 520), "createdAt": str(row["created_at"] or "")} for row in rows if not _looks_like_noise(row["note"])]


def _fetch_task_attachments(db: Database, task_id: str) -> list[dict[str, object]]:
    rows = db.fetchall(
        """
        SELECT id, title, kind, source, document_id, created_at
        FROM task_attachments
        WHERE task_id = ?
        ORDER BY created_at DESC
        LIMIT 8
        """,
        (task_id,),
    )
    return [
        {
            "id": str(row["id"]),
            "title": str(row["title"] or ""),
            "kind": str(row["kind"] or ""),
            "source": str(row["source"] or ""),
            "documentId": str(row["document_id"]) if row["document_id"] else None,
            "createdAt": str(row["created_at"] or ""),
        }
        for row in rows
    ]


def build_task_context_brief_material_pack(db: Database, task_id: str) -> dict[str, object]:
    task = _row_dict(db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,)))
    if not task:
        raise KeyError("task_not_found")
    event_line = _row_dict(db.fetchone("SELECT * FROM event_lines WHERE id = ?", (task.get("event_line_id"),))) if task.get("event_line_id") else None
    client_id = str(task.get("client_id") or (event_line or {}).get("primary_client_id") or "")
    client = _row_dict(db.fetchone("SELECT id, name, alias, intro, stage FROM clients WHERE id = ?", (client_id,))) if client_id else None

    event_tasks: list[dict[str, object]] = []
    if task.get("event_line_id"):
        event_task_rows = db.fetchall(
            """
            SELECT * FROM tasks
            WHERE event_line_id = ? AND status NOT IN ('inbox', 'rejected')
            ORDER BY COALESCE(due_date, updated_at, created_at), updated_at
            LIMIT 14
            """,
            (task.get("event_line_id"),),
        )
        event_tasks = [_task_row_to_pack(dict(row)) for row in event_task_rows]

    same_client_tasks: list[dict[str, object]] = []
    if client_id:
        client_task_rows = db.fetchall(
            """
            SELECT * FROM tasks
            WHERE client_id = ? AND status NOT IN ('inbox', 'rejected')
            ORDER BY COALESCE(due_date, updated_at, created_at), updated_at
            LIMIT 18
            """,
            (client_id,),
        )
        same_client_tasks = [_task_row_to_pack(dict(row)) for row in client_task_rows]

    activity_rows = []
    if task.get("event_line_id"):
        activity_rows = db.fetchall(
            """
            SELECT source_type, source_id, happened_at, title, summary, is_key
            FROM event_line_activities
            WHERE event_line_id = ?
            ORDER BY happened_at DESC, created_at DESC
            LIMIT 14
            """,
            (task.get("event_line_id"),),
        )
    event_line_activities = [
        {
            "sourceType": str(row["source_type"] or ""),
            "sourceId": str(row["source_id"] or ""),
            "happenedAt": str(row["happened_at"] or ""),
            "title": str(row["title"] or ""),
            "summary": _compact_text(row["summary"], 520),
            "isKey": bool(row["is_key"]),
        }
        for row in activity_rows
        if not _looks_like_noise(row["summary"])
    ]

    review_rows = []
    if client_id:
        review_rows = db.fetchall(
            """
            SELECT e.week_label, e.note, e.structured_note_json, e.reviewed_at, t.title AS task_title
            FROM weekly_review_task_entries e
            JOIN tasks t ON t.id = e.task_id
            WHERE t.client_id = ?
            ORDER BY e.reviewed_at DESC
            LIMIT 12
            """,
            (client_id,),
        )
    review_entries = []
    for row in review_rows:
        structured = from_json(row["structured_note_json"], {})
        structured_text = json.dumps(structured, ensure_ascii=False) if isinstance(structured, dict) and structured else ""
        note = _compact_text(row["note"] or structured_text, 620)
        if note and not _looks_like_noise(note):
            review_entries.append(
                {
                    "taskTitle": str(row["task_title"] or ""),
                    "weekLabel": str(row["week_label"] or ""),
                    "note": note,
                    "reviewedAt": str(row["reviewed_at"] or ""),
                }
            )

    seed = {
        "task": _task_row_to_pack(task),
        "client": client or {},
        "eventLine": {
            "id": str((event_line or {}).get("id") or ""),
            "name": str((event_line or {}).get("name") or ""),
            "summary": _compact_text((event_line or {}).get("summary"), 360),
            "intent": _compact_text((event_line or {}).get("intent"), 280),
            "currentBlocker": _compact_text((event_line or {}).get("current_blocker"), 220),
            "recentDecision": _compact_text((event_line or {}).get("recent_decision"), 260),
            "nextStep": _compact_text((event_line or {}).get("next_step"), 260),
        } if event_line else {},
        "sameEventLineTasks": event_tasks,
        "sameClientTasks": same_client_tasks,
        "eventLineActivities": event_line_activities,
        "reviewEntries": review_entries,
    }
    keywords = _derive_keywords(seed)
    chunks = _select_data_center_chunks(db, client_id, keywords)
    pack = {
        **seed,
        "taskNotes": _fetch_task_notes(db, task_id),
        "taskAttachments": _fetch_task_attachments(db, task_id),
        "dataCenterDocumentChunks": chunks,
        "keywords": keywords[:24],
        "coverage": {
            "eventLineTaskCount": len(event_tasks),
            "sameClientTaskCount": len(same_client_tasks),
            "activityCount": len(event_line_activities),
            "reviewEntryCount": len(review_entries),
            "documentChunkCount": len(chunks),
        },
        "promptVersion": TASK_CONTEXT_BRIEF_PROMPT_VERSION,
    }
    return pack


def material_pack_hash(material_pack: dict[str, object]) -> str:
    raw = json.dumps(material_pack, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def should_generate_context_brief(material_pack: dict[str, object]) -> dict[str, object]:
    coverage = material_pack.get("coverage") if isinstance(material_pack.get("coverage"), dict) else {}
    document_count = int(coverage.get("documentChunkCount") or 0)
    review_count = int(coverage.get("reviewEntryCount") or 0)
    event_task_count = int(coverage.get("eventLineTaskCount") or 0)
    client_task_count = int(coverage.get("sameClientTaskCount") or 0)
    activity_count = int(coverage.get("activityCount") or 0)
    current_task = material_pack.get("task") if isinstance(material_pack.get("task"), dict) else {}
    meaningful_current = any(
        str(current_task.get(key) or "").strip()
        for key in ("description", "currentBlocker", "nextAction", "recentDecision")
    )
    flags: list[str] = []
    if document_count <= 0 and review_count <= 0 and activity_count <= 0 and event_task_count <= 1 and client_task_count <= 1:
        flags.append("insufficient_project_context")
    if document_count <= 0 and review_count <= 0 and not meaningful_current:
        flags.append("thin_task_material")
    if document_count <= 0 and review_count <= 0 and activity_count <= 0 and event_task_count <= 1:
        flags.append("single_task_only")
    return {
        "shouldGenerate": not flags,
        "qualityFlags": flags,
    }


def apply_task_context_brief_quality_gate(result: dict[str, object]) -> dict[str, object]:
    brief = _compact_text(result.get("brief"), 260)
    flags = [str(item) for item in result.get("qualityFlags", []) if str(item).strip()] if isinstance(result.get("qualityFlags"), list) else []
    for pattern in _TEMPLATE_RESTATEMENT_PATTERNS:
        if re.search(pattern, brief):
            flags.append("template_field_restatement")
            break
    if len(brief) < 80 and result.get("shouldDisplay", True):
        flags.append("too_short")
    if len(brief) > 230:
        flags.append("too_long")
    if brief and not any(hint in brief for hint in _NEXT_STEP_HINTS):
        flags.append("missing_next_step_reminder")
    if not brief:
        flags.append("empty_brief")
    seen: set[str] = set()
    deduped_flags: list[str] = []
    for flag in flags:
        if flag and flag not in seen:
            seen.add(flag)
            deduped_flags.append(flag)
    blocking = {"template_field_restatement", "missing_next_step_reminder", "empty_brief", "too_short", "too_long"}
    should_display = bool(result.get("shouldDisplay", True)) and not any(flag in blocking for flag in deduped_flags)
    return {
        "shouldDisplay": should_display,
        "brief": brief if should_display else "",
        "usedProjectSignals": [str(item).strip() for item in result.get("usedProjectSignals", []) if str(item).strip()][:6]
        if isinstance(result.get("usedProjectSignals"), list)
        else [],
        "materialBoundary": _compact_text(result.get("materialBoundary"), 240),
        "qualityFlags": deduped_flags,
    }


def _snapshot_row_to_record(row) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "taskId": str(row["task_id"]),
        "clientId": str(row["client_id"]) if row["client_id"] else None,
        "eventLineId": str(row["event_line_id"]) if row["event_line_id"] else None,
        "brief": str(row["brief"] or ""),
        "shouldDisplay": bool(row["should_display"]),
        "materialPackHash": str(row["material_pack_hash"] or ""),
        "usedProjectSignals": from_json(row["used_project_signals_json"], []),
        "materialBoundary": str(row["material_boundary"] or ""),
        "qualityFlags": from_json(row["quality_flags_json"], []),
        "generationModel": str(row["generation_model"] or ""),
        "generationPromptVersion": str(row["generation_prompt_version"] or ""),
        "updatedAt": str(row["updated_at"] or ""),
    }


def _save_snapshot(
    db: Database,
    *,
    task_id: str,
    client_id: str | None,
    event_line_id: str | None,
    material_hash: str,
    result: dict[str, object],
    generation_model: str,
) -> dict[str, object]:
    now = _now_iso()
    existing = db.fetchone("SELECT id, created_at FROM task_context_brief_snapshots WHERE task_id = ? ORDER BY updated_at DESC LIMIT 1", (task_id,))
    snapshot_id = str(existing["id"]) if existing else f"tcbrief_{uuid4().hex[:12]}"
    created_at = str(existing["created_at"]) if existing else now
    db.execute(
        """
        INSERT OR REPLACE INTO task_context_brief_snapshots(
            id, task_id, client_id, event_line_id, brief, should_display, material_pack_hash,
            used_project_signals_json, material_boundary, quality_flags_json,
            generation_model, generation_prompt_version, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            task_id,
            client_id,
            event_line_id,
            str(result.get("brief") or ""),
            1 if result.get("shouldDisplay") else 0,
            material_hash,
            to_json(result.get("usedProjectSignals") if isinstance(result.get("usedProjectSignals"), list) else []),
            str(result.get("materialBoundary") or ""),
            to_json(result.get("qualityFlags") if isinstance(result.get("qualityFlags"), list) else []),
            generation_model,
            TASK_CONTEXT_BRIEF_PROMPT_VERSION,
            created_at,
            now,
        ),
    )
    row = db.fetchone("SELECT * FROM task_context_brief_snapshots WHERE id = ?", (snapshot_id,))
    return _snapshot_row_to_record(row)


def generate_task_context_brief_snapshot(
    db: Database,
    ai: object,
    task_id: str,
    *,
    force_refresh: bool = False,
) -> dict[str, object]:
    material_pack = build_task_context_brief_material_pack(db, task_id)
    task = material_pack.get("task") if isinstance(material_pack.get("task"), dict) else {}
    client_id = str(task.get("clientId") or "") or None
    event_line_id = str(task.get("eventLineId") or "") or None
    current_hash = material_pack_hash(material_pack)
    if not force_refresh:
        row = db.fetchone(
            "SELECT * FROM task_context_brief_snapshots WHERE task_id = ? AND material_pack_hash = ? ORDER BY updated_at DESC LIMIT 1",
            (task_id, current_hash),
        )
        if row:
            return _snapshot_row_to_record(row)

    readiness = should_generate_context_brief(material_pack)
    health = ai.get_health() if hasattr(ai, "get_health") else None
    generation_model = str(getattr(health, "model", "") or "")
    if not readiness.get("shouldGenerate"):
        return _save_snapshot(
            db,
            task_id=task_id,
            client_id=client_id,
            event_line_id=event_line_id,
            material_hash=current_hash,
            result={
                "shouldDisplay": False,
                "brief": "",
                "usedProjectSignals": [],
                "materialBoundary": "材料不足，未生成任务前情提要。",
                "qualityFlags": readiness.get("qualityFlags", []),
            },
            generation_model=generation_model,
        )

    try:
        generated = ai.generate_task_context_brief(material_pack=material_pack)  # type: ignore[attr-defined]
        if not isinstance(generated, dict):
            generated = {}
    except Exception:
        generated = {
            "shouldDisplay": False,
            "brief": "",
            "usedProjectSignals": [],
            "materialBoundary": "后台模型生成失败。",
            "qualityFlags": ["generation_failed"],
        }
    gated = apply_task_context_brief_quality_gate(generated)
    return _save_snapshot(
        db,
        task_id=task_id,
        client_id=client_id,
        event_line_id=event_line_id,
        material_hash=current_hash,
        result=gated,
        generation_model=generation_model,
    )
