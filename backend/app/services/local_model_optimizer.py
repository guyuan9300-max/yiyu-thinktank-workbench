from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from threading import Event
from typing import Any
from uuid import uuid4

from app.db import Database, to_json


SETTINGS_KEY = "settings.local_model_optimization"
TASK_TYPE_DOCUMENT_CARD = "document_card_generation"
TASK_TYPE_PATH_OPTIMIZATION = "document_path_optimization"
TASK_TYPES = {TASK_TYPE_DOCUMENT_CARD, TASK_TYPE_PATH_OPTIMIZATION}
DEFAULT_PROFILE_ID = "local_text_deep"
PROMPT_VERSION = "local-data-optimizer-v1"

DEFAULT_SETTINGS: dict[str, object] = {
    "enabled": False,
    "modelProfileId": DEFAULT_PROFILE_ID,
    "modelName": "",
    "dailyWindows": [{"start": "22:00", "end": "08:00"}],
    "concurrency": 1,
    "paused": False,
    "autoEnqueueDocumentCards": True,
    "autoEnqueuePathOptimization": True,
    "updatedAt": None,
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _safe_json(value: object, default: object) -> object:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return default
        return parsed if parsed is not None else default
    return value


def _list_of_strings(value: object, *, limit: int = 12) -> list[str]:
    raw = _safe_json(value, [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _clamp_float(value: object, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_hhmm(value: object) -> int | None:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _format_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _normalize_window(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    start = _parse_hhmm(value.get("start"))
    end = _parse_hhmm(value.get("end"))
    if start is None or end is None:
        return None
    return {"start": _format_hhmm(start), "end": _format_hhmm(end)}


def normalize_local_model_optimization_settings(value: object | None) -> dict[str, object]:
    raw = _safe_json(value, {})
    if not isinstance(raw, dict):
        raw = {}
    settings = dict(DEFAULT_SETTINGS)
    settings.update(raw)
    windows = [_normalize_window(item) for item in _safe_json(settings.get("dailyWindows"), []) if isinstance(item, dict)]
    settings["dailyWindows"] = [item for item in windows if item] or list(DEFAULT_SETTINGS["dailyWindows"])  # type: ignore[arg-type]
    try:
        concurrency = int(settings.get("concurrency") or 1)
    except (TypeError, ValueError):
        concurrency = 1
    settings["concurrency"] = max(1, min(8, concurrency))
    settings["enabled"] = bool(settings.get("enabled"))
    settings["paused"] = bool(settings.get("paused"))
    settings["autoEnqueueDocumentCards"] = bool(settings.get("autoEnqueueDocumentCards", True))
    settings["autoEnqueuePathOptimization"] = bool(settings.get("autoEnqueuePathOptimization", True))
    settings["modelProfileId"] = str(settings.get("modelProfileId") or DEFAULT_PROFILE_ID).strip() or DEFAULT_PROFILE_ID
    settings["modelName"] = str(settings.get("modelName") or "").strip()
    return settings


def get_local_model_optimization_settings(db: Database) -> dict[str, object]:
    return normalize_local_model_optimization_settings(db.get_setting(SETTINGS_KEY, "{}"))


def save_local_model_optimization_settings(db: Database, payload: object) -> dict[str, object]:
    settings = normalize_local_model_optimization_settings(payload)
    settings["updatedAt"] = _now_iso()
    db.set_setting(SETTINGS_KEY, to_json(settings))
    return settings


def is_within_run_window(settings: object | None, now: datetime | None = None) -> bool:
    normalized = normalize_local_model_optimization_settings(settings)
    current = now or datetime.now()
    current_minutes = current.hour * 60 + current.minute
    for window in normalized.get("dailyWindows", []):
        if not isinstance(window, dict):
            continue
        start = _parse_hhmm(window.get("start"))
        end = _parse_hhmm(window.get("end"))
        if start is None or end is None:
            continue
        if start == end:
            return True
        if start < end and start <= current_minutes < end:
            return True
        if start > end and (current_minutes >= start or current_minutes < end):
            return True
    return False


def next_window_label(settings: object | None, now: datetime | None = None) -> str:
    normalized = normalize_local_model_optimization_settings(settings)
    windows = normalized.get("dailyWindows", [])
    labels = [
        f"{str(item.get('start') or '').strip()}-{str(item.get('end') or '').strip()}"
        for item in windows
        if isinstance(item, dict) and item.get("start") and item.get("end")
    ]
    if not labels:
        return ""
    prefix = "当前窗口 " if is_within_run_window(normalized, now) else "下次窗口 "
    return prefix + "；".join(labels[:2])


def _count_tasks(db: Database, status: str, client_id: str | None = None) -> int:
    if client_id:
        return int(db.scalar("SELECT COUNT(1) AS count FROM local_model_tasks WHERE client_id = ? AND status = ?", (client_id, status)))
    return int(db.scalar("SELECT COUNT(1) AS count FROM local_model_tasks WHERE status = ?", (status,)))


def get_local_model_optimization_stats(db: Database, client_id: str | None = None) -> dict[str, object]:
    settings = get_local_model_optimization_settings(db)
    client_filter = "WHERE kd.client_id = ?" if client_id else ""
    params: tuple[object, ...] = (client_id,) if client_id else ()
    pending_cards = int(
        db.scalar(
            f"""
            SELECT COUNT(1) AS count
            FROM knowledge_documents kd
            LEFT JOIN document_cards dc ON dc.knowledge_document_id = kd.id
            {client_filter}
            {"AND" if client_filter else "WHERE"} dc.id IS NULL
            """,
            params,
        )
    )
    pending_paths = int(
        db.scalar(
            f"""
            SELECT COUNT(1) AS count
            FROM knowledge_documents kd
            LEFT JOIN document_path_optimizations dpo ON dpo.knowledge_document_id = kd.id
            {client_filter}
            {"AND" if client_filter else "WHERE"} dpo.id IS NULL
            """,
            params,
        )
    )
    path_params: tuple[object, ...] = (client_id,) if client_id else ()
    path_where = "WHERE client_id = ?" if client_id else ""
    applied_paths = int(
        db.scalar(
            f"""
            SELECT COUNT(1) AS count
            FROM document_path_optimizations
            {path_where}
            {"AND" if path_where else "WHERE"} apply_status = 'applied'
            """,
            path_params,
        )
    )
    pending_confirmations = int(
        db.scalar(
            f"""
            SELECT COUNT(1) AS count
            FROM document_path_optimizations
            {path_where}
            {"AND" if path_where else "WHERE"} apply_status = 'pending_confirmation'
            """,
            path_params,
        )
    )
    task_where = "WHERE client_id = ?" if client_id else ""
    task_params: tuple[object, ...] = (client_id,) if client_id else ()
    queue_total = int(db.scalar(f"SELECT COUNT(1) AS count FROM local_model_tasks {task_where}", task_params))
    last_completed = db.fetchone(
        f"""
        SELECT completed_at
        FROM local_model_tasks
        {task_where}
        {"AND" if task_where else "WHERE"} status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
        """,
        task_params,
    )
    last_error = db.fetchone(
        f"""
        SELECT last_error
        FROM local_model_tasks
        {task_where}
        {"AND" if task_where else "WHERE"} status = 'failed' AND COALESCE(last_error, '') <> ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        task_params,
    )
    return {
        "enabled": bool(settings.get("enabled")),
        "paused": bool(settings.get("paused")),
        "inWindow": is_within_run_window(settings),
        "nextWindowLabel": next_window_label(settings),
        "modelProfileId": str(settings.get("modelProfileId") or DEFAULT_PROFILE_ID),
        "modelName": str(settings.get("modelName") or ""),
        "concurrency": int(settings.get("concurrency") or 1),
        "queueTotal": queue_total,
        "queuedTasks": _count_tasks(db, "queued", client_id),
        "runningTasks": _count_tasks(db, "running", client_id),
        "completedTasks": _count_tasks(db, "completed", client_id),
        "failedTasks": _count_tasks(db, "failed", client_id),
        "pendingDocumentCards": pending_cards,
        "pendingPathOptimizations": pending_paths,
        "appliedPathOptimizations": applied_paths,
        "pendingPathConfirmations": pending_confirmations,
        "lastCompletedAt": str(last_completed["completed_at"]) if last_completed else None,
        "lastError": str(last_error["last_error"]) if last_error else None,
    }


def _document_rows_for_enqueue(
    db: Database,
    *,
    client_id: str | None,
    document_ids: list[str] | None,
) -> list[dict[str, object]]:
    filters: list[str] = []
    params: list[object] = []
    if client_id:
        filters.append("kd.client_id = ?")
        params.append(client_id)
    clean_ids = [str(item).strip() for item in (document_ids or []) if str(item).strip()]
    if clean_ids:
        placeholders = ",".join("?" for _ in clean_ids)
        filters.append(f"(kd.id IN ({placeholders}) OR kd.document_id IN ({placeholders}))")
        params.extend(clean_ids)
        params.extend(clean_ids)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = db.fetchall(
        f"""
        SELECT
            kd.id AS knowledge_document_id,
            kd.client_id AS client_id,
            kd.document_id AS document_id,
            kd.original_path AS original_path,
            kd.binary_hash AS binary_hash,
            kd.normalized_hash AS normalized_hash,
            COALESCE(v.raw_hash, '') AS raw_hash
        FROM knowledge_documents kd
        LEFT JOIN knowledge_document_versions v
            ON v.knowledge_document_id = kd.id
           AND v.version_no = (
               SELECT MAX(version_no)
               FROM knowledge_document_versions
               WHERE knowledge_document_id = kd.id
           )
        {where_clause}
        ORDER BY kd.created_at ASC
        """,
        tuple(params),
    )
    return [dict(row) for row in rows]


def _input_hash(task_type: str, row: dict[str, object]) -> str:
    basis = "|".join(
        [
            task_type,
            str(row.get("knowledge_document_id") or ""),
            str(row.get("raw_hash") or ""),
            str(row.get("normalized_hash") or ""),
            str(row.get("binary_hash") or ""),
            str(row.get("original_path") or ""),
        ]
    )
    return _sha256(basis)


def enqueue_local_model_optimization_tasks(
    db: Database,
    *,
    client_id: str | None = None,
    document_ids: list[str] | None = None,
    task_types: list[str] | None = None,
    model_profile_id: str = DEFAULT_PROFILE_ID,
    model_name: str = "",
    priority: int = 100,
) -> dict[str, object]:
    clean_task_types = [item for item in (task_types or [TASK_TYPE_DOCUMENT_CARD, TASK_TYPE_PATH_OPTIMIZATION]) if item in TASK_TYPES]
    if not clean_task_types:
        clean_task_types = [TASK_TYPE_DOCUMENT_CARD, TASK_TYPE_PATH_OPTIMIZATION]
    rows = _document_rows_for_enqueue(db, client_id=client_id, document_ids=document_ids)
    created = 0
    attempted = 0
    now = _now_iso()
    clean_profile = str(model_profile_id or DEFAULT_PROFILE_ID).strip() or DEFAULT_PROFILE_ID
    clean_model = str(model_name or "").strip()
    for row in rows:
        for task_type in clean_task_types:
            attempted += 1
            task_id = _new_id("lmt")
            input_hash = _input_hash(task_type, row)
            db.execute(
                """
                INSERT OR IGNORE INTO local_model_tasks(
                    id, task_type, client_id, knowledge_document_id, model_profile_id, model_name,
                    status, priority, attempts, max_attempts, input_hash, result_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, 0, 3, ?, '{}', ?, ?)
                """,
                (
                    task_id,
                    task_type,
                    str(row.get("client_id") or ""),
                    str(row.get("knowledge_document_id") or ""),
                    clean_profile,
                    clean_model,
                    int(priority),
                    input_hash,
                    now,
                    now,
                ),
            )
            inserted = db.fetchone("SELECT id FROM local_model_tasks WHERE id = ?", (task_id,))
            if inserted:
                created += 1
    return {"created": created, "attempted": attempted, "documents": len(rows), "taskTypes": clean_task_types}


def retry_failed_local_model_optimization_tasks(
    db: Database,
    *,
    client_id: str | None = None,
    task_ids: list[str] | None = None,
) -> int:
    clean_ids = [str(item).strip() for item in (task_ids or []) if str(item).strip()]

    def _update(conn) -> int:
        params: list[object] = [_now_iso()]
        filters = ["status = 'failed'"]
        if client_id:
            filters.append("client_id = ?")
            params.append(client_id)
        if clean_ids:
            placeholders = ",".join("?" for _ in clean_ids)
            filters.append(f"id IN ({placeholders})")
            params.extend(clean_ids)
        cursor = conn.execute(
            f"""
            UPDATE local_model_tasks
            SET status = 'queued',
                attempts = 0,
                last_error = NULL,
                locked_by = NULL,
                locked_at = NULL,
                started_at = NULL,
                completed_at = NULL,
                updated_at = ?
            WHERE {' AND '.join(filters)}
            """,
            tuple(params),
        )
        return int(cursor.rowcount or 0)

    return int(db.run_in_transaction(_update))


def requeue_interrupted_local_model_tasks(db: Database) -> int:
    def _update(conn) -> int:
        now = _now_iso()
        cursor = conn.execute(
            """
            UPDATE local_model_tasks
            SET status = 'queued',
                locked_by = NULL,
                locked_at = NULL,
                started_at = NULL,
                updated_at = ?
            WHERE status = 'running'
            """,
            (now,),
        )
        return int(cursor.rowcount or 0)

    return int(db.run_in_transaction(_update))


def _claim_next_task(db: Database, worker_id: str) -> dict[str, object] | None:
    def _claim(conn) -> dict[str, object] | None:
        row = conn.execute(
            """
            SELECT *
            FROM local_model_tasks
            WHERE status = 'queued'
            ORDER BY priority ASC, created_at ASC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        now = _now_iso()
        conn.execute(
            """
            UPDATE local_model_tasks
            SET status = 'running',
                attempts = attempts + 1,
                locked_by = ?,
                locked_at = ?,
                started_at = COALESCE(started_at, ?),
                updated_at = ?,
                last_error = NULL
            WHERE id = ? AND status = 'queued'
            """,
            (worker_id, now, now, now, row["id"]),
        )
        updated = conn.execute("SELECT * FROM local_model_tasks WHERE id = ?", (row["id"],)).fetchone()
        return dict(updated) if updated is not None else None

    return db.run_in_transaction(_claim)


def _load_document_context(db: Database, knowledge_document_id: str) -> dict[str, object]:
    row = db.fetchone(
        """
        SELECT
            kd.id AS knowledge_document_id,
            kd.client_id AS client_id,
            kd.document_id AS document_id,
            kd.original_path AS knowledge_original_path,
            kd.current_human_path AS current_human_path,
            kd.primary_category AS primary_category,
            kd.secondary_category AS secondary_category,
            kd.binary_hash AS binary_hash,
            kd.normalized_hash AS normalized_hash,
            c.name AS client_name,
            d.title AS document_title,
            d.path AS document_path,
            d.original_source_path AS original_source_path,
            d.excerpt AS legacy_excerpt,
            vd.file_name AS file_name,
            vd.preview_text AS preview_text,
            vd.managed_path AS managed_path,
            vd.visible_category AS visible_category,
            vd.secondary_category AS v2_secondary_category,
            vd.doc_index_text AS doc_index_text,
            vd.markdown_content AS markdown_content,
            kv.raw_text AS raw_text,
            kv.raw_hash AS raw_hash
        FROM knowledge_documents kd
        JOIN clients c ON c.id = kd.client_id
        LEFT JOIN documents d ON d.id = kd.document_id
        LEFT JOIN v2_documents vd ON vd.document_id = kd.document_id
        LEFT JOIN knowledge_document_versions kv
            ON kv.knowledge_document_id = kd.id
           AND kv.version_no = (
               SELECT MAX(version_no)
               FROM knowledge_document_versions
               WHERE knowledge_document_id = kd.id
           )
        WHERE kd.id = ?
        """,
        (knowledge_document_id,),
    )
    if row is None:
        raise RuntimeError("待优化文件不存在。")
    return dict(row)


def _build_context_text(context: dict[str, object]) -> str:
    body_text = str(context.get("raw_text") or context.get("markdown_content") or "")
    pieces = [
        f"客户/项目：{context.get('client_name') or ''}",
        f"文件名：{context.get('document_title') or context.get('file_name') or ''}",
        f"原始路径：{context.get('document_path') or context.get('knowledge_original_path') or ''}",
        f"现有分类：{context.get('visible_category') or context.get('primary_category') or ''} / {context.get('v2_secondary_category') or context.get('secondary_category') or ''}",
        f"现有摘要：{context.get('legacy_excerpt') or context.get('preview_text') or ''}",
        f"索引文本：{context.get('doc_index_text') or ''}",
        f"正文片段：{body_text[:6000]}",
    ]
    return "\n".join(item for item in pieces if item.strip())


def _card_prompt(context: dict[str, object]) -> str:
    return (
        "/no_think\n"
        "请基于以下数据中心文件资料，生成一个供检索、问答、报告生成共用的文件名片。"
        "不要复述校对类任务说明，要解释文件在项目中的用途、服务对象、项目语境和可回答的问题。"
        "只返回一个合法 JSON 对象，不要输出 Markdown、解释、前后缀或代码块。"
        "字段必须包括：title, purpose, audience, project_context, key_topics, "
        "good_questions, keywords, summary, risk_notes。"
        "数组字段必须使用 JSON 数组，缺少依据时使用空字符串或空数组。\n\n"
        f"{_build_context_text(context)}"
    )


def _path_prompt(context: dict[str, object]) -> str:
    return (
        "/no_think\n"
        "请基于以下数据中心文件资料，生成非破坏性的虚拟归类建议。"
        "不要移动、重命名或要求改动真实文件路径；只给系统内部读取使用。"
        "只返回一个合法 JSON 对象，不要输出 Markdown、解释、前后缀或代码块。"
        "字段必须包括：virtual_path, classification_tags, recommended_owner, "
        "recommended_project, confidence, reason, evidence。"
        "classification_tags 和 evidence 必须是 JSON 数组，confidence 必须是 0 到 1 的数字。"
        "如果无法判断，把 confidence 设为 0.4，并给出 pending_confirmation 级别的谨慎理由。"
        "输出格式示例："
        "{\"virtual_path\":\"日慈基金会/项目与业务/项目报告\",\"classification_tags\":[\"项目报告\"],"
        "\"recommended_owner\":\"日慈基金会\",\"recommended_project\":\"\",\"confidence\":0.68,"
        "\"reason\":\"依据文件标题和正文片段给出虚拟归类，不改变真实路径。\","
        "\"evidence\":[\"文件标题\",\"正文片段\"]}\n\n"
        f"{_build_context_text(context)}"
    )


def _process_document_card_task(db: Database, ai_service: Any, task: dict[str, object]) -> dict[str, object]:
    knowledge_document_id = str(task.get("knowledge_document_id") or "").strip()
    context = _load_document_context(db, knowledge_document_id)
    prompt = _card_prompt(context)
    payload = ai_service.generate_local_model_json(
        profile_key=str(task.get("model_profile_id") or DEFAULT_PROFILE_ID),
        model_name=str(task.get("model_name") or ""),
        system_prompt="你是数据中心后台优化引擎，负责生成可复用的文件理解资产。只输出 JSON。",
        user_prompt=prompt,
        timeout_seconds=900,
        max_tokens=1800,
    )
    now = _now_iso()
    title = str(payload.get("title") or context.get("document_title") or context.get("file_name") or "未命名文件").strip()
    summary = str(payload.get("summary") or "").strip()
    one_line = summary[:80] or str(payload.get("purpose") or "").strip()[:80] or title
    input_hash = str(task.get("input_hash") or "")
    generated_model = str(task.get("model_name") or task.get("model_profile_id") or "")
    db.execute(
        """
        INSERT INTO document_cards(
            id, knowledge_document_id, title, one_line_summary, summary_200,
            purpose, audience, project_context, key_topics_json, good_questions_json,
            keywords_json, tags_json, entities_json, risk_notes, generated_model,
            input_hash, prompt_version, date_range_label, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        ON CONFLICT(knowledge_document_id) DO UPDATE SET
            title = excluded.title,
            one_line_summary = excluded.one_line_summary,
            summary_200 = excluded.summary_200,
            purpose = excluded.purpose,
            audience = excluded.audience,
            project_context = excluded.project_context,
            key_topics_json = excluded.key_topics_json,
            good_questions_json = excluded.good_questions_json,
            keywords_json = excluded.keywords_json,
            tags_json = excluded.tags_json,
            entities_json = excluded.entities_json,
            risk_notes = excluded.risk_notes,
            generated_model = excluded.generated_model,
            input_hash = excluded.input_hash,
            prompt_version = excluded.prompt_version,
            updated_at = excluded.updated_at
        """,
        (
            _new_id("dc"),
            knowledge_document_id,
            title,
            one_line,
            summary[:200],
            str(payload.get("purpose") or "").strip(),
            str(payload.get("audience") or "").strip(),
            str(payload.get("project_context") or "").strip(),
            to_json(_list_of_strings(payload.get("key_topics"))),
            to_json(_list_of_strings(payload.get("good_questions"))),
            to_json(_list_of_strings(payload.get("keywords"))),
            to_json(_list_of_strings(payload.get("key_topics"))),
            to_json([]),
            str(payload.get("risk_notes") or "").strip(),
            generated_model,
            input_hash,
            PROMPT_VERSION,
            now,
            now,
        ),
    )
    return {
        "knowledgeDocumentId": knowledge_document_id,
        "title": title,
        "summary": summary[:200],
        "keywords": _list_of_strings(payload.get("keywords")),
    }


def _process_path_optimization_task(db: Database, ai_service: Any, task: dict[str, object]) -> dict[str, object]:
    knowledge_document_id = str(task.get("knowledge_document_id") or "").strip()
    context = _load_document_context(db, knowledge_document_id)
    prompt = _path_prompt(context)
    payload = ai_service.generate_local_model_json(
        profile_key=str(task.get("model_profile_id") or DEFAULT_PROFILE_ID),
        model_name=str(task.get("model_name") or ""),
        system_prompt="你是数据中心后台优化引擎，负责生成非破坏性的虚拟路径和分类标签。只输出 JSON。",
        user_prompt=prompt,
        timeout_seconds=900,
        max_tokens=1200,
    )
    confidence = _clamp_float(payload.get("confidence"))
    virtual_path = str(payload.get("virtual_path") or "").strip()
    apply_status = "applied" if confidence >= 0.72 and virtual_path else "pending_confirmation"
    now = _now_iso()
    input_hash = str(task.get("input_hash") or "")
    generated_model = str(task.get("model_name") or task.get("model_profile_id") or "")
    db.execute(
        """
        INSERT INTO document_path_optimizations(
            id, knowledge_document_id, client_id, virtual_path, classification_tags_json,
            recommended_owner, recommended_project, confidence, reason, evidence_json,
            apply_status, generated_model, input_hash, prompt_version, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(knowledge_document_id) DO UPDATE SET
            client_id = excluded.client_id,
            virtual_path = excluded.virtual_path,
            classification_tags_json = excluded.classification_tags_json,
            recommended_owner = excluded.recommended_owner,
            recommended_project = excluded.recommended_project,
            confidence = excluded.confidence,
            reason = excluded.reason,
            evidence_json = excluded.evidence_json,
            apply_status = excluded.apply_status,
            generated_model = excluded.generated_model,
            input_hash = excluded.input_hash,
            prompt_version = excluded.prompt_version,
            updated_at = excluded.updated_at
        """,
        (
            _new_id("dpo"),
            knowledge_document_id,
            str(context.get("client_id") or ""),
            virtual_path,
            to_json(_list_of_strings(payload.get("classification_tags"))),
            str(payload.get("recommended_owner") or "").strip(),
            str(payload.get("recommended_project") or "").strip(),
            confidence,
            str(payload.get("reason") or "").strip(),
            to_json(_list_of_strings(payload.get("evidence"))),
            apply_status,
            generated_model,
            input_hash,
            PROMPT_VERSION,
            now,
            now,
        ),
    )
    return {
        "knowledgeDocumentId": knowledge_document_id,
        "virtualPath": virtual_path,
        "classificationTags": _list_of_strings(payload.get("classification_tags")),
        "applyStatus": apply_status,
    }


def _mark_task_completed(db: Database, task_id: str, result: dict[str, object]) -> None:
    now = _now_iso()
    result_json = to_json(result)
    db.execute(
        """
        UPDATE local_model_tasks
        SET status = 'completed',
            output_hash = ?,
            result_json = ?,
            locked_by = NULL,
            locked_at = NULL,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (_sha256(result_json), result_json, now, now, task_id),
    )


def _mark_task_failed(db: Database, task: dict[str, object], error: Exception) -> None:
    attempts = int(task.get("attempts") or 0)
    max_attempts = int(task.get("max_attempts") or 3)
    final_status = "failed" if attempts >= max_attempts else "queued"
    now = _now_iso()
    db.execute(
        """
        UPDATE local_model_tasks
        SET status = ?,
            last_error = ?,
            locked_by = NULL,
            locked_at = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (final_status, str(error), now, str(task.get("id") or "")),
    )


def run_due_local_model_tasks(
    db: Database,
    ai_service: Any,
    *,
    settings: object | None = None,
    worker_id: str | None = None,
    batch_size: int | None = None,
    force: bool = False,
) -> dict[str, object]:
    normalized = normalize_local_model_optimization_settings(settings if settings is not None else get_local_model_optimization_settings(db))
    if not force:
        if not bool(normalized.get("enabled")):
            return {"processed": 0, "failed": 0, "skipped": 0, "status": "disabled"}
        if bool(normalized.get("paused")):
            return {"processed": 0, "failed": 0, "skipped": 0, "status": "paused"}
        if not is_within_run_window(normalized):
            return {"processed": 0, "failed": 0, "skipped": 0, "status": "outside_window"}
    limit = max(1, int(batch_size or normalized.get("concurrency") or 1))
    resolved_worker = worker_id or f"local_optimizer_{uuid4().hex[:8]}"
    processed = 0
    failed = 0
    skipped = 0
    for _ in range(limit):
        task = _claim_next_task(db, resolved_worker)
        if task is None:
            break
        try:
            task_type = str(task.get("task_type") or "")
            if task_type == TASK_TYPE_DOCUMENT_CARD:
                result = _process_document_card_task(db, ai_service, task)
            elif task_type == TASK_TYPE_PATH_OPTIMIZATION:
                result = _process_path_optimization_task(db, ai_service, task)
            else:
                skipped += 1
                raise RuntimeError(f"不支持的本地优化任务类型：{task_type}")
            _mark_task_completed(db, str(task.get("id") or ""), result)
            processed += 1
        except Exception as error:
            failed += 1
            _mark_task_failed(db, task, error)
        if not force and not is_within_run_window(normalized):
            break
    return {"processed": processed, "failed": failed, "skipped": skipped, "status": "completed"}


def local_model_optimizer_worker_loop(
    db: Database,
    ai_service: Any,
    stop_event: Event,
    *,
    poll_seconds: float = 60.0,
) -> None:
    try:
        requeue_interrupted_local_model_tasks(db)
    except Exception:
        pass
    while not stop_event.is_set():
        try:
            run_due_local_model_tasks(db, ai_service)
        except Exception:
            pass
        stop_event.wait(max(5.0, float(poll_seconds)))
