from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import ExperienceStoryDraftRecord


PROMPT_VERSION = "experience_story_v1"
PRIMARY_SOURCE_TYPES = {
    "weekly_review_task_entry",
    "task_note",
    "meeting",
    "meeting_source",
    "task",
    "event_line_activity",
    "v2_document",
    "document",
}
EXCLUDED_PRIMARY_SOURCE_TYPES = {
    "strategic_thought_insight",
    "strategic_thought_insights",
    "handbook_entry",
    "growth_insight_quote",
    "ai_generated",
    "analysis_run",
    "digital_asset_narrative",
}
SYSTEM_DOC_PATTERN = re.compile(
    r"(v2doc_sysdoc|sysdoc|系统生成|自动生成|AI\s*生成|经验金句|smoke|冒烟|测试|test_|"
    r"对象-处境-动作-机制-证据|本次候选稿因 AI|请严格按|你将作为|YAML front matter)",
    re.IGNORECASE,
)
NOISE_PATTERN = re.compile(r"(报销|发票|收据|安装态|截图|\.jpeg|\.png|空白)", re.IGNORECASE)
SCENE_PATTERN = re.compile(r"(客户|会议|复盘|任务|项目|负责人|同事|团队|现场|沟通|材料|方案|合作|传播)")
TENSION_PATTERN = re.compile(r"(问题|卡|困难|风险|不足|缺口|但|然而|没有|不能|担心|冲突|误解|瓶颈|发散)")
ACTION_PATTERN = re.compile(r"(发现|判断|决定|调整|提出|追问|复盘|收窄|扩展|先|没有直接|选择|提醒|推动|补充|确认)")
LEARNING_PATTERN = re.compile(r"(意味着|说明|提醒|未来|因此|沉淀|复用|能力|组织|成长|市场|可能性|长期)")
LABEL_PREFIX_PATTERN = re.compile(r"^\s*(启示|经验|故事|结论|组织启示|个人启示)\s*[:：]\s*")
REPORT_STYLE_PATTERN = re.compile(r"(战略层面的关系数据沉淀|对象-处境-动作-机制-证据|补全指引|业务依据|系统工程)")


@dataclass(frozen=True)
class ExperienceStoryCandidate:
    source_type: str
    source_id: str
    source_title: str
    primary_text: str
    client_id: str | None = None
    event_line_id: str | None = None
    task_id: str | None = None
    meeting_id: str | None = None
    occurred_at: str = ""
    evidence_refs: tuple[str, ...] = ()
    context: dict[str, object] | None = None
    score: int = 0


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _safe_json(value: str | None, default: object) -> object:
    try:
        return from_json(value, default)
    except Exception:
        return default


def _trim(value: object, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _json_texts(value: object) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        item = _trim(value, 500)
        if item:
            texts.append(item)
    elif isinstance(value, dict):
        for item in value.values():
            texts.extend(_json_texts(item))
    elif isinstance(value, list):
        for item in value:
            texts.extend(_json_texts(item))
    return texts


def _is_generated_or_noise(source_type: str, title: str, *parts: object) -> bool:
    haystack = " ".join([source_type, title, *[str(part or "") for part in parts]])
    normalized_type = source_type.strip().lower()
    if normalized_type in EXCLUDED_PRIMARY_SOURCE_TYPES:
        return True
    if SYSTEM_DOC_PATTERN.search(haystack):
        return True
    if NOISE_PATTERN.search(haystack):
        return True
    return False


def _story_potential_score(text: str) -> int:
    score = 0
    length = len(text)
    if length >= 80:
        score += 16
    if length >= 160:
        score += 10
    if SCENE_PATTERN.search(text):
        score += 18
    if TENSION_PATTERN.search(text):
        score += 22
    if ACTION_PATTERN.search(text):
        score += 22
    if LEARNING_PATTERN.search(text):
        score += 18
    if REPORT_STYLE_PATTERN.search(text):
        score -= 30
    return max(0, min(100, score))


def _append_candidate(candidates: list[ExperienceStoryCandidate], candidate: ExperienceStoryCandidate) -> None:
    if candidate.source_type not in PRIMARY_SOURCE_TYPES:
        return
    if not candidate.evidence_refs:
        return
    text = _trim(candidate.primary_text, 1800)
    if len(text) < 60:
        return
    if _is_generated_or_noise(candidate.source_type, candidate.source_title, text):
        return
    score = candidate.score or _story_potential_score(text)
    if score < 45:
        return
    candidates.append(
        ExperienceStoryCandidate(
            **{
                **candidate.__dict__,
                "primary_text": text,
                "score": score,
            }
        )
    )


def _material_pack(candidate: ExperienceStoryCandidate) -> dict[str, object]:
    return {
        "source": {
            "type": candidate.source_type,
            "id": candidate.source_id,
            "title": candidate.source_title,
            "authority": "primary_real_work_material",
        },
        "primaryText": candidate.primary_text,
        "context": candidate.context or {},
        "evidenceRefs": list(candidate.evidence_refs),
        "sourcePolicy": {
            "primaryAllowed": True,
            "excludedPrimaryTypes": sorted(EXCLUDED_PRIMARY_SOURCE_TYPES),
            "supportOnly": ["client_profile", "client_dna", "event_line_summary", "evidence_card"],
        },
    }


def discover_experience_story_candidates(db: Database, limit: int = 20) -> list[ExperienceStoryCandidate]:
    candidates: list[ExperienceStoryCandidate] = []

    review_rows = db.fetchall(
        """
        SELECT
            wte.id, wte.note, wte.structured_note_json, wte.review_id, wte.task_id, wte.week_label,
            wte.updated_at, t.title AS task_title, t.description, t.current_blocker, t.next_action,
            t.recent_decision, t.event_line_id, e.name AS event_line_name, e.primary_client_id,
            e.primary_client_name, wr.summary AS review_summary, wr.work_free_note
        FROM weekly_review_task_entries wte
        INNER JOIN tasks t ON t.id = wte.task_id
        LEFT JOIN weekly_reviews wr ON wr.id = wte.review_id
        LEFT JOIN event_lines e ON e.id = t.event_line_id
        WHERE COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
          AND COALESCE(wte.content_domain, 'work') = 'work'
        ORDER BY wte.updated_at DESC
        LIMIT 80
        """
    )
    for row in review_rows:
        structured = _safe_json(row["structured_note_json"], {})
        parts = [
            row["note"],
            *_json_texts(structured),
            row["description"],
            row["current_blocker"],
            row["next_action"],
            row["recent_decision"],
        ]
        text = "。".join(part for part in (_trim(item, 500) for item in parts) if part)
        _append_candidate(
            candidates,
            ExperienceStoryCandidate(
                source_type="weekly_review_task_entry",
                source_id=str(row["id"]),
                source_title=str(row["task_title"] or "任务复盘"),
                primary_text=text,
                client_id=str(row["primary_client_id"]) if row["primary_client_id"] else None,
                event_line_id=str(row["event_line_id"]) if row["event_line_id"] else None,
                task_id=str(row["task_id"]),
                occurred_at=str(row["updated_at"] or ""),
                evidence_refs=(f"weekly_review_task_entry:{row['id']}", f"task:{row['task_id']}"),
                context={
                    "weekLabel": str(row["week_label"] or ""),
                    "reviewId": str(row["review_id"] or ""),
                    "eventLineName": str(row["event_line_name"] or ""),
                    "clientName": str(row["primary_client_name"] or ""),
                },
            ),
        )

    task_note_rows = db.fetchall(
        """
        SELECT tn.id, tn.note, tn.updated_at, t.id AS task_id, t.title, t.description,
               t.current_blocker, t.next_action, t.recent_decision, t.event_line_id,
               e.name AS event_line_name, e.primary_client_id, e.primary_client_name
        FROM task_notes tn
        INNER JOIN tasks t ON t.id = tn.task_id
        LEFT JOIN event_lines e ON e.id = t.event_line_id
        WHERE COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
          AND COALESCE(t.source_type, '') != 'agent_auto'
        ORDER BY tn.updated_at DESC
        LIMIT 60
        """
    )
    for row in task_note_rows:
        text = "。".join(
            part
            for part in (
                _trim(row["note"], 900),
                _trim(row["description"], 360),
                _trim(row["current_blocker"], 220),
                _trim(row["next_action"], 220),
                _trim(row["recent_decision"], 220),
            )
            if part
        )
        _append_candidate(
            candidates,
            ExperienceStoryCandidate(
                source_type="task_note",
                source_id=str(row["id"]),
                source_title=str(row["title"] or "任务备注"),
                primary_text=text,
                client_id=str(row["primary_client_id"]) if row["primary_client_id"] else None,
                event_line_id=str(row["event_line_id"]) if row["event_line_id"] else None,
                task_id=str(row["task_id"]),
                occurred_at=str(row["updated_at"] or ""),
                evidence_refs=(f"task_note:{row['id']}", f"task:{row['task_id']}"),
                context={"eventLineName": str(row["event_line_name"] or ""), "clientName": str(row["primary_client_name"] or "")},
            ),
        )

    meeting_rows = db.fetchall(
        """
        SELECT m.id, m.title, m.notes, m.transcript_text, m.stage, m.client_id, c.name AS client_name, m.updated_at
        FROM meetings m
        LEFT JOIN clients c ON c.id = m.client_id
        ORDER BY m.updated_at DESC
        LIMIT 60
        """
    )
    for row in meeting_rows:
        text = "。".join(part for part in (_trim(row["notes"], 900), _trim(row["transcript_text"], 900)) if part)
        _append_candidate(
            candidates,
            ExperienceStoryCandidate(
                source_type="meeting",
                source_id=str(row["id"]),
                source_title=str(row["title"] or "会议记录"),
                primary_text=text,
                client_id=str(row["client_id"]) if row["client_id"] else None,
                meeting_id=str(row["id"]),
                occurred_at=str(row["updated_at"] or ""),
                evidence_refs=(f"meeting:{row['id']}",),
                context={"stage": str(row["stage"] or ""), "clientName": str(row["client_name"] or "")},
            ),
        )

    meeting_source_rows = db.fetchall(
        """
        SELECT ms.id, ms.title, ms.content_text, ms.created_at, m.id AS meeting_id, m.title AS meeting_title,
               m.client_id, c.name AS client_name
        FROM meeting_sources ms
        INNER JOIN meetings m ON m.id = ms.meeting_id
        LEFT JOIN clients c ON c.id = m.client_id
        ORDER BY ms.created_at DESC
        LIMIT 60
        """
    )
    for row in meeting_source_rows:
        _append_candidate(
            candidates,
            ExperienceStoryCandidate(
                source_type="meeting_source",
                source_id=str(row["id"]),
                source_title=str(row["title"] or row["meeting_title"] or "会议资料"),
                primary_text=_trim(row["content_text"], 1400),
                client_id=str(row["client_id"]) if row["client_id"] else None,
                meeting_id=str(row["meeting_id"]),
                occurred_at=str(row["created_at"] or ""),
                evidence_refs=(f"meeting_source:{row['id']}", f"meeting:{row['meeting_id']}"),
                context={"meetingTitle": str(row["meeting_title"] or ""), "clientName": str(row["client_name"] or "")},
            ),
        )

    task_rows = db.fetchall(
        """
        SELECT t.id, t.title, t.description, t.current_blocker, t.next_action, t.recent_decision,
               t.updated_at, t.event_line_id, e.name AS event_line_name, e.primary_client_id, e.primary_client_name
        FROM tasks t
        LEFT JOIN event_lines e ON e.id = t.event_line_id
        WHERE COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
          AND COALESCE(t.source_type, '') IN ('manual', 'event_line', 'client', 'meeting')
        ORDER BY t.updated_at DESC
        LIMIT 80
        """
    )
    for row in task_rows:
        text = "。".join(
            part
            for part in (
                _trim(row["description"], 600),
                _trim(row["current_blocker"], 260),
                _trim(row["next_action"], 260),
                _trim(row["recent_decision"], 260),
            )
            if part
        )
        _append_candidate(
            candidates,
            ExperienceStoryCandidate(
                source_type="task",
                source_id=str(row["id"]),
                source_title=str(row["title"] or "任务"),
                primary_text=text,
                client_id=str(row["primary_client_id"]) if row["primary_client_id"] else None,
                event_line_id=str(row["event_line_id"]) if row["event_line_id"] else None,
                task_id=str(row["id"]),
                occurred_at=str(row["updated_at"] or ""),
                evidence_refs=(f"task:{row['id']}",),
                context={"eventLineName": str(row["event_line_name"] or ""), "clientName": str(row["primary_client_name"] or "")},
            ),
        )

    activity_rows = db.fetchall(
        """
        SELECT a.id, a.source_type, a.source_id, a.title, a.summary, a.happened_at, a.event_line_id,
               e.name AS event_line_name, e.primary_client_id, e.primary_client_name
        FROM event_line_activities a
        INNER JOIN event_lines e ON e.id = a.event_line_id
        ORDER BY a.happened_at DESC
        LIMIT 80
        """
    )
    for row in activity_rows:
        raw_source_type = str(row["source_type"] or "")
        if _is_generated_or_noise(raw_source_type, str(row["title"] or ""), row["summary"]):
            continue
        _append_candidate(
            candidates,
            ExperienceStoryCandidate(
                source_type="event_line_activity",
                source_id=str(row["id"]),
                source_title=str(row["title"] or "事件线活动"),
                primary_text=_trim(row["summary"], 1100),
                client_id=str(row["primary_client_id"]) if row["primary_client_id"] else None,
                event_line_id=str(row["event_line_id"]),
                occurred_at=str(row["happened_at"] or ""),
                evidence_refs=(f"event_line_activity:{row['id']}", f"event_line:{row['event_line_id']}"),
                context={
                    "eventLineName": str(row["event_line_name"] or ""),
                    "clientName": str(row["primary_client_name"] or ""),
                    "activitySourceType": raw_source_type,
                },
            ),
        )

    v2_rows = db.fetchall(
        """
        SELECT id, document_id, client_id, file_name, original_path, managed_path, material_layer,
               visible_category, secondary_category, parse_status,
               COALESCE(NULLIF(markdown_content,''), NULLIF(preview_text,''), NULLIF(doc_index_text,''), '') AS content,
               updated_at
        FROM v2_documents
        WHERE COALESCE(parse_status, '') IN ('ready', 'parsed', 'done', '')
        ORDER BY updated_at DESC
        LIMIT 80
        """
    )
    for row in v2_rows:
        content = _trim(row["content"], 1400)
        title = str(row["file_name"] or "资料文档")
        if _is_generated_or_noise("v2_document", title, row["id"], row["original_path"], row["managed_path"], content):
            continue
        _append_candidate(
            candidates,
            ExperienceStoryCandidate(
                source_type="v2_document",
                source_id=str(row["id"]),
                source_title=title,
                primary_text=content,
                client_id=str(row["client_id"]) if row["client_id"] else None,
                occurred_at=str(row["updated_at"] or ""),
                evidence_refs=(f"v2_document:{row['id']}", f"document:{row['document_id']}"),
                context={
                    "materialLayer": str(row["material_layer"] or ""),
                    "visibleCategory": str(row["visible_category"] or ""),
                    "secondaryCategory": str(row["secondary_category"] or ""),
                },
            ),
        )

    document_rows = db.fetchall(
        """
        SELECT id, client_id, title, path, source, excerpt, created_at
        FROM documents
        ORDER BY created_at DESC
        LIMIT 80
        """
    )
    for row in document_rows:
        title = str(row["title"] or "资料文档")
        excerpt = _trim(row["excerpt"], 1000)
        if _is_generated_or_noise("document", title, row["id"], row["path"], row["source"], excerpt):
            continue
        _append_candidate(
            candidates,
            ExperienceStoryCandidate(
                source_type="document",
                source_id=str(row["id"]),
                source_title=title,
                primary_text=excerpt,
                client_id=str(row["client_id"]) if row["client_id"] else None,
                occurred_at=str(row["created_at"] or ""),
                evidence_refs=(f"document:{row['id']}",),
                context={"documentSource": str(row["source"] or "")},
            ),
        )

    seen: set[tuple[str, str]] = set()
    deduped: list[ExperienceStoryCandidate] = []
    for candidate in sorted(candidates, key=lambda item: (item.score, item.occurred_at), reverse=True):
        key = (candidate.source_type, candidate.source_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


def _existing_active_draft(db: Database, candidate: ExperienceStoryCandidate) -> bool:
    row = db.fetchone(
        """
        SELECT 1
        FROM experience_story_drafts
        WHERE source_type = ? AND source_id = ? AND status != 'rejected'
        LIMIT 1
        """,
        (candidate.source_type, candidate.source_id),
    )
    return row is not None


def _model_label(ai_service: object | None) -> str:
    if ai_service is None:
        return "unavailable"
    try:
        health = ai_service.get_health()
        provider = str(getattr(health, "provider", "") or "")
        model = str(getattr(health, "model", "") or "")
        return f"{provider}/{model}".strip("/")
    except Exception:
        return "unknown"


def _strip_labels(text: str) -> str:
    current = str(text or "").strip()
    for _ in range(3):
        next_value = LABEL_PREFIX_PATTERN.sub("", current).strip()
        if next_value == current:
            break
        current = next_value
    return current


def _fallback_story(candidate: ExperienceStoryCandidate) -> dict[str, str]:
    sentences = [item.strip("。；; ") for item in re.split(r"[。；;\n]", candidate.primary_text) if item.strip()]
    first = sentences[0] if sentences else candidate.primary_text[:80]
    second = next((item for item in sentences[1:] if ACTION_PATTERN.search(item) or LEARNING_PATTERN.search(item)), "")
    story = (
        f"{candidate.source_title}里，团队先看见的不是一个孤立任务，而是一个需要被重新判断的工作场景。"
        f"{first[:70]}。"
    )
    if second:
        story += f"他们把关键动作落在了{second[:55]}。"
    story += "这段经验提醒团队，真正有价值的复盘不是还原过程，而是把选择背后的判断沉淀下来。"
    return {
        "title": f"{candidate.source_title[:18]}的复盘",
        "story": story[:260],
        "growthValue": "训练从行动中看见判断的能力。",
        "organizationValue": "把真实业务里的选择沉淀为可复用经验。",
        "factRiskNote": "当前为规则兜底生成，建议人工核对原始材料后再入墙。",
    }


def _quality_gate(result: dict[str, str], candidate: ExperienceStoryCandidate, *, fallback_used: bool) -> tuple[str, dict[str, object]]:
    story = _strip_labels(result.get("story") or "")
    issues: list[str] = []
    if fallback_used:
        issues.append("模型不可用或生成失败，使用规则兜底草稿")
    if not candidate.evidence_refs:
        issues.append("缺少证据引用")
    if len(story) < 80:
        issues.append("故事过短，可能缺少场景")
    if len(story) > 320:
        issues.append("故事过长，需要人工收束")
    if REPORT_STYLE_PATTERN.search(story):
        issues.append("仍含系统工程或报告式表达")
    if LABEL_PREFIX_PATTERN.search(result.get("story") or ""):
        issues.append("模型输出含显式标签，已自动移除")
    if not (SCENE_PATTERN.search(story) and ACTION_PATTERN.search(story)):
        issues.append("场景或行动不够明确")
    if candidate.score < 60:
        issues.append("原始素材故事潜力偏弱")
    quality = {
        "score": max(0, min(100, candidate.score - len(issues) * 8)),
        "sourcePotentialScore": candidate.score,
        "issues": issues,
        "promptVersion": PROMPT_VERSION,
        "sourceAuthority": "primary_real_work_material",
    }
    return ("candidate" if not issues else "needs_review"), quality


def _generate_result(ai_service: object | None, candidate: ExperienceStoryCandidate) -> tuple[dict[str, str], bool]:
    pack = _material_pack(candidate)
    if ai_service is not None and hasattr(ai_service, "generate_experience_story"):
        try:
            result = ai_service.generate_experience_story(material_pack=pack, context=candidate.context or {})
            if isinstance(result, dict) and str(result.get("story") or "").strip():
                return {
                    "title": str(result.get("title") or "").strip(),
                    "story": str(result.get("story") or "").strip(),
                    "growthValue": str(result.get("growthValue") or "").strip(),
                    "organizationValue": str(result.get("organizationValue") or "").strip(),
                    "factRiskNote": str(result.get("factRiskNote") or "").strip(),
                }, False
        except Exception:
            pass
    return _fallback_story(candidate), True


def generate_experience_story_drafts(
    db: Database,
    ai_service: object | None,
    *,
    limit: int = 5,
) -> tuple[list[ExperienceStoryDraftRecord], int]:
    generated: list[ExperienceStoryDraftRecord] = []
    skipped = 0
    now = _now_iso()
    for candidate in discover_experience_story_candidates(db, limit=max(limit * 4, 12)):
        if len(generated) >= limit:
            break
        if _existing_active_draft(db, candidate):
            skipped += 1
            continue
        result, fallback_used = _generate_result(ai_service, candidate)
        result["story"] = _strip_labels(result.get("story") or "")
        status, quality = _quality_gate(result, candidate, fallback_used=fallback_used)
        draft_id = _new_id("story")
        db.execute(
            """
            INSERT INTO experience_story_drafts(
                id, title, story, status, source_type, source_id, source_title, client_id, event_line_id,
                task_id, meeting_id, handbook_entry_id, evidence_refs_json, material_pack_json,
                growth_value, organization_value, quality_score_json, fact_risk_note,
                generation_model, generation_prompt_version, created_at, updated_at, approved_at, approved_by
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                draft_id,
                _trim(result.get("title") or candidate.source_title, 80),
                result.get("story") or "",
                status,
                candidate.source_type,
                candidate.source_id,
                candidate.source_title,
                candidate.client_id,
                candidate.event_line_id,
                candidate.task_id,
                candidate.meeting_id,
                to_json(list(candidate.evidence_refs)),
                to_json(_material_pack(candidate)),
                result.get("growthValue") or "",
                result.get("organizationValue") or "",
                to_json(quality),
                result.get("factRiskNote") or "",
                _model_label(ai_service),
                PROMPT_VERSION,
                now,
                now,
            ),
        )
        row = db.fetchone("SELECT * FROM experience_story_drafts WHERE id = ?", (draft_id,))
        if row is not None:
            generated.append(build_experience_story_draft_record(db, row))
    return generated, skipped


def list_experience_story_drafts(
    db: Database,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[ExperienceStoryDraftRecord]:
    params: list[object] = []
    where = ""
    if status:
        statuses = [item.strip() for item in status.split(",") if item.strip()]
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            where = f"WHERE status IN ({placeholders})"
            params.extend(statuses)
    params.append(limit)
    rows = db.fetchall(
        f"""
        SELECT *
        FROM experience_story_drafts
        {where}
        ORDER BY updated_at DESC, created_at DESC
        LIMIT ?
        """,
        tuple(params),
    )
    return [build_experience_story_draft_record(db, row) for row in rows]


def build_experience_story_draft_record(db: Database, row: Any) -> ExperienceStoryDraftRecord:
    client_name = ""
    event_line_name = ""
    if row["client_id"]:
        client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (str(row["client_id"]),))
        client_name = str(client_row["name"] or "") if client_row else ""
    if row["event_line_id"]:
        event_row = db.fetchone("SELECT name FROM event_lines WHERE id = ?", (str(row["event_line_id"]),))
        event_line_name = str(event_row["name"] or "") if event_row else ""
    return ExperienceStoryDraftRecord(
        id=str(row["id"]),
        title=str(row["title"] or ""),
        story=str(row["story"] or ""),
        status=str(row["status"] or "candidate"),  # type: ignore[arg-type]
        sourceType=str(row["source_type"] or ""),
        sourceId=str(row["source_id"] or ""),
        sourceTitle=str(row["source_title"] or ""),
        clientId=str(row["client_id"]) if row["client_id"] else None,
        clientName=client_name or None,
        eventLineId=str(row["event_line_id"]) if row["event_line_id"] else None,
        eventLineName=event_line_name or None,
        taskId=str(row["task_id"]) if row["task_id"] else None,
        meetingId=str(row["meeting_id"]) if row["meeting_id"] else None,
        handbookEntryId=str(row["handbook_entry_id"]) if row["handbook_entry_id"] else None,
        evidenceRefs=[str(item) for item in (_safe_json(row["evidence_refs_json"], []) or []) if item],
        materialPack=_safe_json(row["material_pack_json"], {}) if isinstance(_safe_json(row["material_pack_json"], {}), dict) else {},
        growthValue=str(row["growth_value"] or ""),
        organizationValue=str(row["organization_value"] or ""),
        qualityScore=_safe_json(row["quality_score_json"], {}) if isinstance(_safe_json(row["quality_score_json"], {}), dict) else {},
        factRiskNote=str(row["fact_risk_note"] or ""),
        generationModel=str(row["generation_model"] or ""),
        generationPromptVersion=str(row["generation_prompt_version"] or ""),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        approvedAt=str(row["approved_at"]) if row["approved_at"] else None,
        approvedBy=str(row["approved_by"]) if row["approved_by"] else None,
    )


def regenerate_experience_story_draft(
    db: Database,
    ai_service: object | None,
    *,
    draft_id: str,
) -> ExperienceStoryDraftRecord | None:
    row = db.fetchone("SELECT * FROM experience_story_drafts WHERE id = ?", (draft_id,))
    if row is None:
        return None
    evidence_refs = tuple(str(item) for item in (_safe_json(row["evidence_refs_json"], []) or []) if item)
    pack = _safe_json(row["material_pack_json"], {})
    primary_text = ""
    if isinstance(pack, dict):
        primary_text = _trim(pack.get("primaryText"), 1800)
    candidate = ExperienceStoryCandidate(
        source_type=str(row["source_type"] or ""),
        source_id=str(row["source_id"] or ""),
        source_title=str(row["source_title"] or ""),
        primary_text=primary_text or str(row["story"] or ""),
        client_id=str(row["client_id"]) if row["client_id"] else None,
        event_line_id=str(row["event_line_id"]) if row["event_line_id"] else None,
        task_id=str(row["task_id"]) if row["task_id"] else None,
        meeting_id=str(row["meeting_id"]) if row["meeting_id"] else None,
        evidence_refs=evidence_refs,
        context=pack.get("context") if isinstance(pack, dict) and isinstance(pack.get("context"), dict) else {},
        score=_story_potential_score(primary_text or str(row["story"] or "")),
    )
    result, fallback_used = _generate_result(ai_service, candidate)
    result["story"] = _strip_labels(result.get("story") or "")
    status, quality = _quality_gate(result, candidate, fallback_used=fallback_used)
    now = _now_iso()
    db.execute(
        """
        UPDATE experience_story_drafts
        SET title = ?, story = ?, status = ?, growth_value = ?, organization_value = ?,
            quality_score_json = ?, fact_risk_note = ?, generation_model = ?,
            generation_prompt_version = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            _trim(result.get("title") or candidate.source_title, 80),
            result.get("story") or "",
            status,
            result.get("growthValue") or "",
            result.get("organizationValue") or "",
            to_json(quality),
            result.get("factRiskNote") or "",
            _model_label(ai_service),
            PROMPT_VERSION,
            now,
            draft_id,
        ),
    )
    updated = db.fetchone("SELECT * FROM experience_story_drafts WHERE id = ?", (draft_id,))
    return build_experience_story_draft_record(db, updated) if updated is not None else None


def reject_experience_story_draft(db: Database, *, draft_id: str) -> ExperienceStoryDraftRecord | None:
    now = _now_iso()
    db.execute(
        "UPDATE experience_story_drafts SET status = 'rejected', updated_at = ? WHERE id = ?",
        (now, draft_id),
    )
    row = db.fetchone("SELECT * FROM experience_story_drafts WHERE id = ?", (draft_id,))
    return build_experience_story_draft_record(db, row) if row is not None else None
