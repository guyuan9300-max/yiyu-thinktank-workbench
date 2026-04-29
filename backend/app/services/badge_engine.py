from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import (
    BadgeActionLinkRecord,
    BadgeBoardOverviewRecord,
    BadgeBoardResponse,
    BadgeCategoryRecord,
    BadgeEvidenceRecord,
    BadgeProgressRecord,
    BadgeState,
    GrowthAbilityKey,
    GrowthContextLinkRecord,
)

AbilityLabel = Literal["沟通协作", "客户导向", "执行推进", "组织管理", "经营意识", "学习沉淀"]
RuleType = Literal["count", "consecutive", "ratio", "sequence", "composite"]

ABILITY_LABELS: dict[GrowthAbilityKey, str] = {
    "collab": "沟通协作",
    "insight": "客户导向",
    "exec": "执行推进",
    "write": "组织管理",
    "risk": "经营意识",
    "analyze": "学习沉淀",
}

CATEGORY_DEFINITIONS: list[dict[str, Any]] = [
    {"id": "task_progress", "label": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "color": "#E8913A", "order": 1},
    {"id": "calendar_rhythm", "label": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "color": "#4A9CC7", "order": 2},
    {"id": "meeting_notes", "label": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "color": "#5BA8C8", "order": 3},
    {"id": "customer_insight", "label": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "color": "#3F51B5", "order": 4},
    {"id": "relationship_collab", "label": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "color": "#2E7D32", "order": 5},
    {"id": "research_intel", "label": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "color": "#546E7A", "order": 6},
    {"id": "judgment_strategy", "label": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "color": "#6A1B9A", "order": 7},
    {"id": "delivery_product", "label": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "color": "#E57373", "order": 8},
    {"id": "team_management", "label": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "color": "#1A237E", "order": 9},
    {"id": "ai_digital", "label": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "color": "#263238", "order": 10},
]


@dataclass(frozen=True)
class WorkEvent:
    event_id: str
    module: str
    event_type: str
    object_type: str
    object_id: str
    occurred_at: str
    title: str
    payload: dict[str, Any]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.min


def _week_label(value: str) -> str:
    dt = _parse_dt(value)
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _period_key(value: str, unit: str) -> str:
    dt = _parse_dt(value)
    if unit == "day":
        return dt.strftime("%Y-%m-%d")
    if unit == "month":
        return dt.strftime("%Y-%m")
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _period_order(key: str, unit: str) -> int:
    if unit == "day":
        return int(key.replace("-", ""))
    if unit == "month":
        year, month = key.split("-")
        return int(year) * 12 + int(month)
    year, week = key.split("-W")
    return int(year) * 53 + int(week)


def _matches_filters(payload: dict[str, Any], filters: dict[str, Any] | None = None, required_fields: list[str] | None = None) -> bool:
    if filters:
        for key, expected in filters.items():
            actual = payload.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
    if required_fields:
        for field in required_fields:
            value = payload.get(field)
            if value in (None, "", False, 0, [], {}):
                return False
    return True


def _unique_events(events: list[WorkEvent]) -> list[WorkEvent]:
    bucket: dict[tuple[str, str], WorkEvent] = {}
    for event in sorted(events, key=lambda item: (_parse_dt(item.occurred_at), item.event_id), reverse=True):
        key = (event.object_type, event.object_id)
        bucket.setdefault(key, event)
    return list(bucket.values())


def _event_to_evidence(event: WorkEvent) -> BadgeEvidenceRecord:
    subtitle_parts = [event.module, event.event_type]
    if event.payload.get("summary"):
        subtitle_parts.insert(0, str(event.payload["summary"]))
    return BadgeEvidenceRecord(
        id=event.event_id,
        title=event.title,
        sourceType=event.event_type,
        sourceId=event.object_id,
        subtitle=" · ".join(part for part in subtitle_parts if part),
        occurredAt=event.occurred_at,
    )


def _context_tab_for_event_type(event_type: str) -> str:
    if event_type.startswith("meeting.") or event_type.startswith("client."):
        return "client_workspace"
    if event_type.startswith("analysis.") or event_type.startswith("improvement."):
        return "topics_management"
    if event_type.startswith("knowledge.") or event_type.startswith("learning."):
        return "growth_handbook"
    if event_type.startswith("finance.") or event_type.startswith("approval.") or event_type.startswith("expense."):
        return "settings"
    return "tasks"


def _context_object_type_for_event_type(event_type: str) -> str:
    if event_type.startswith("meeting.") or event_type.startswith("client."):
        return "meeting"
    if event_type.startswith("analysis.") or event_type.startswith("improvement."):
        return "analysis"
    if event_type.startswith("knowledge.") or event_type.startswith("learning."):
        return "handbook"
    if event_type.startswith("finance.") or event_type.startswith("approval.") or event_type.startswith("expense."):
        return "settings_object"
    return "task"


def _linked_contexts_from_evidences(evidences: list[BadgeEvidenceRecord]) -> list[GrowthContextLinkRecord]:
    seen: set[tuple[str, str]] = set()
    items: list[GrowthContextLinkRecord] = []
    for evidence in evidences:
        key = (evidence.sourceType, evidence.sourceId)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            GrowthContextLinkRecord(
                objectType=_context_object_type_for_event_type(evidence.sourceType),
                objectId=evidence.sourceId,
                label=evidence.title,
                subtitle=evidence.subtitle,
                tab=_context_tab_for_event_type(evidence.sourceType),
                statusLabel=evidence.sourceType,
            )
        )
    return items


def _event_type_labels_for_rule(rule: dict[str, Any]) -> list[str]:
    rule_type = str(rule.get("type") or "")
    if rule_type == "composite":
        labels: list[str] = []
        for condition in list(rule.get("conditions") or []):
            label = str(condition.get("label") or condition.get("eventType") or "").strip()
            if label:
                labels.append(label)
        return labels
    value = str(rule.get("eventType") or rule.get("numeratorEventType") or rule.get("denominatorEventType") or "").strip()
    return [value] if value else []


def _is_unconnected_event_type(value: str) -> bool:
    if value.startswith(("approval.", "expense.", "finance.")):
        return True
    return value in {
        "project.kickoff_clear",
        "learning.mentorship_completed",
    }


def _missing_signals_for_badge(rule: dict[str, Any], evidences: list[BadgeEvidenceRecord], progress_value: float, progress_target: float) -> list[str]:
    if progress_target > 0 and progress_value >= progress_target:
        return []
    expected_labels = _event_type_labels_for_rule(rule)
    if not expected_labels:
        return []
    missing: list[str] = []
    for label in expected_labels[:3]:
        if _is_unconnected_event_type(label):
            missing.append(f"{label}：当前模块未接通")
        else:
            missing.append(f"{label}：还缺真实业务信号")
    if evidences:
        missing.append("继续补齐动作、负责人、资料或闭环证据")
    return missing[:4]


def _is_method_like(text: str) -> bool:
    return any(keyword in text for keyword in ("模板", "方法", "清单", "SOP", "规范", "步骤", "复用", "流程"))


def _contains_all(text: str, keywords: list[str]) -> bool:
    return all(keyword in text for keyword in keywords)


def _collect_work_events(db: Database, *, user_name: str) -> list[WorkEvent]:
    events: list[WorkEvent] = []

    meeting_rows = db.fetchall(
        """
        SELECT
            m.*,
            (SELECT COUNT(*) FROM decisions d WHERE d.meeting_id = m.id) AS decision_count,
            (SELECT COUNT(*) FROM action_items a WHERE a.meeting_id = m.id) AS action_count,
            (SELECT COUNT(*) FROM action_items a WHERE a.meeting_id = m.id AND TRIM(a.owner_name) != '') AS owner_count,
            (SELECT COUNT(*) FROM action_items a WHERE a.meeting_id = m.id AND TRIM(a.due_date) != '') AS due_count,
            (SELECT COUNT(DISTINCT a.owner_name) FROM action_items a WHERE a.meeting_id = m.id AND TRIM(a.owner_name) != '') AS owner_distinct_count,
            (
                SELECT COUNT(*)
                FROM tasks t
                WHERE t.source_type = 'meeting'
                  AND t.source_id = m.id
                  AND COALESCE(t.scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
            ) AS linked_task_count,
            (SELECT COUNT(*) FROM risks r WHERE r.meeting_id = m.id) AS risk_count,
            (SELECT COUNT(*) FROM ambiguities am WHERE am.meeting_id = m.id AND COALESCE(am.status, '') != 'ignored') AS ambiguity_count
        FROM meetings m
        ORDER BY m.updated_at DESC
        """
    )
    for row in meeting_rows:
        occurred_at = str(row["updated_at"] or row["created_at"])
        title = str(row["title"] or "未命名会议")
        notes = str(row["notes"] or "")
        stage = str(row["stage"] or "")
        payload = {
            "stage": stage,
            "decisionCount": int(row["decision_count"] or 0),
            "actionCount": int(row["action_count"] or 0),
            "ownerCount": int(row["owner_count"] or 0),
            "dueCount": int(row["due_count"] or 0),
            "ownerDistinctCount": int(row["owner_distinct_count"] or 0),
            "linkedTaskCount": int(row["linked_task_count"] or 0),
            "riskCount": int(row["risk_count"] or 0),
            "ambiguityCount": int(row["ambiguity_count"] or 0),
            "summary": "会议沉淀",
        }
        if stage == "published":
            events.append(WorkEvent(f"meeting_published_{row['id']}", "meeting", "meeting.published", "meeting", str(row["id"]), occurred_at, title, payload))
        if stage == "published" and payload["decisionCount"] >= 1 and payload["actionCount"] >= 1 and payload["ownerCount"] >= 1 and payload["dueCount"] >= 1 and payload["linkedTaskCount"] >= 1:
            events.append(WorkEvent(f"meeting_closed_loop_{row['id']}", "meeting", "meeting.closed_loop", "meeting", str(row["id"]), occurred_at, title, payload))
        if stage == "published" and (payload["ownerDistinctCount"] >= 2 or any(keyword in f"{title} {notes}" for keyword in ("跨组", "协作", "对齐", "联动"))):
            events.append(WorkEvent(f"meeting_cross_{row['id']}", "meeting", "meeting.cross_function", "meeting", str(row["id"]), occurred_at, title, payload))
        if payload["riskCount"] >= 1:
            events.append(WorkEvent(f"meeting_risk_{row['id']}", "meeting", "project.risk_flagged", "meeting", str(row["id"]), occurred_at, title, payload))
        if payload["ambiguityCount"] >= 1:
            events.append(WorkEvent(f"meeting_clarity_{row['id']}", "meeting", "client.requirement_clarified", "meeting", str(row["id"]), occurred_at, title, payload))

    review_rows = db.fetchall(
        """
        SELECT wr.id AS review_id, wr.week_label, wr.summary, wr.work_free_note, wr.created_at, wr.updated_at,
               we.id AS entry_id, we.task_id, we.note, we.structured_note_json, we.task_snapshot_json
        FROM weekly_reviews wr
        LEFT JOIN weekly_review_task_entries we ON we.review_id = wr.id
        ORDER BY wr.updated_at DESC, we.reviewed_at DESC
        """
    )
    reviews_by_id: dict[str, dict[str, Any]] = {}
    for row in review_rows:
        review_id = str(row["review_id"])
        record = reviews_by_id.setdefault(
            review_id,
            {
                "reviewId": review_id,
                "weekLabel": str(row["week_label"] or ""),
                "summary": str(row["summary"] or row["work_free_note"] or ""),
                "updatedAt": str(row["updated_at"] or row["created_at"]),
                "entries": [],
            },
        )
        if row["entry_id"]:
            structured = from_json(row["structured_note_json"], {})
            snapshot = from_json(row["task_snapshot_json"], {})
            record["entries"].append(
                {
                    "id": str(row["entry_id"]),
                    "taskId": str(row["task_id"] or ""),
                    "note": str(row["note"] or ""),
                    "structured": structured,
                    "snapshot": snapshot,
                }
            )
    for review in reviews_by_id.values():
        if review["summary"] or review["entries"]:
            events.append(
                WorkEvent(
                    f"review_submitted_{review['reviewId']}",
                    "review",
                    "review.submitted",
                    "weekly_review",
                    review["reviewId"],
                    review["updatedAt"],
                    f"{review['weekLabel']} 周报",
                    {"weekLabel": review["weekLabel"], "summary": "周报提交"},
                )
            )
        for entry in review["entries"]:
            structured = entry["structured"]
            snapshot = entry["snapshot"] or {}
            task_title = str(snapshot.get("title") or "任务复盘")
            joined_text = " ".join(
                [
                    task_title,
                    str(entry["note"] or ""),
                    str(structured.get("reflection") or ""),
                    str(structured.get("progress") or ""),
                    str(structured.get("successExperience") or ""),
                    str(structured.get("successReason") or ""),
                    str(structured.get("failureInsight") or ""),
                    str(structured.get("blockerReason") or ""),
                    str(structured.get("supportNeeded") or ""),
                    str(structured.get("nextAction") or ""),
                ]
            )
            payload = {
                "hasConclusion": bool(structured.get("successExperience") or structured.get("successReason") or structured.get("failureInsight")),
                "hasNextAction": bool(structured.get("nextAction")),
                "hasRisk": bool(structured.get("blockerReason") or structured.get("supportNeeded") or structured.get("lightweightTag")),
                "hasAcceptanceTrace": _contains_all(joined_text, ["验收", "责任"]) and ("复测" in joined_text or "问题" in joined_text),
                "hasHandoffTrace": _contains_all(joined_text, ["背景", "风险", "下一步"]),
                "summary": "周复盘条目",
            }
            if payload["hasConclusion"] and payload["hasNextAction"]:
                events.append(
                    WorkEvent(
                        f"review_structured_{entry['id']}",
                        "review",
                        "review.structured_entry",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )
            if payload["hasConclusion"] and ("原因" in joined_text or "为什么" in joined_text or "改进" in joined_text):
                events.append(
                    WorkEvent(
                        f"review_retrospective_{entry['id']}",
                        "review",
                        "review.retrospective_completed",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )
            if payload["hasRisk"]:
                events.append(
                    WorkEvent(
                        f"review_risk_{entry['id']}",
                        "review",
                        "project.risk_flagged",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )
            if payload["hasAcceptanceTrace"]:
                events.append(
                    WorkEvent(
                        f"review_acceptance_{entry['id']}",
                        "review",
                        "project.acceptance_closed",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )
            if payload["hasHandoffTrace"]:
                events.append(
                    WorkEvent(
                        f"review_handoff_{entry['id']}",
                        "review",
                        "task.clear_handoff",
                        "weekly_review_entry",
                        entry["id"],
                        review["updatedAt"],
                        task_title,
                        payload,
                    )
                )

    handbook_rows = db.fetchall("SELECT * FROM handbook_entries ORDER BY created_at DESC")
    for row in handbook_rows:
        title = str(row["title"] or "经验沉淀")
        summary = str(row["summary"] or "")
        tags = from_json(row["tags_json"], [])
        text = " ".join([title, summary, " ".join(str(tag) for tag in tags)])
        occurred_at = str(row["created_at"])
        payload = {
            "sourceType": str(row["source_type"] or ""),
            "isMethodLike": _is_method_like(text),
            "tagCount": len(tags),
            "summary": "成长手册",
        }
        events.append(WorkEvent(f"handbook_entry_{row['id']}", "handbook", "knowledge.experience_published", "handbook_entry", str(row["id"]), occurred_at, title, payload))
        if payload["isMethodLike"]:
            events.append(WorkEvent(f"handbook_sop_{row['id']}", "handbook", "knowledge.sop_published", "handbook_entry", str(row["id"]), occurred_at, title, payload))
        if any(keyword in text for keyword in ("分享", "培训", "讲解", "课程")):
            events.append(WorkEvent(f"handbook_share_{row['id']}", "handbook", "learning.knowledge_share", "handbook_entry", str(row["id"]), occurred_at, title, payload))

    analysis_rows = db.fetchall("SELECT * FROM analysis_runs ORDER BY created_at DESC")
    for row in analysis_rows:
        title = str(row["title"] or "分析产出")
        occurred_at = str(row["created_at"])
        payload = {"status": str(row["status"] or ""), "summary": "分析工作台"}
        events.append(WorkEvent(f"analysis_dashboard_{row['id']}", "analysis", "analysis.dashboard_updated", "analysis_run", str(row["id"]), occurred_at, title, payload))
        if any(keyword in title for keyword in ("方案", "报价", "提案")):
            events.append(WorkEvent(f"analysis_proposal_{row['id']}", "analysis", "analysis.proposal_advanced", "analysis_run", str(row["id"]), occurred_at, title, payload))

    validation_rows = db.fetchall(
        """
        SELECT
            v.id,
            v.event_type,
            v.source_type,
            v.source_id,
            v.created_at,
            e.metadata_json
        FROM growth_validation_events v
        INNER JOIN growth_evidence_records e ON e.id = v.evidence_id
        ORDER BY v.created_at DESC
        """
    )
    for row in validation_rows:
        metadata = from_json(row["metadata_json"], {})
        title = str(metadata.get("sourceTitle") or "方法复用")
        payload = {"summary": "方法复用"}
        events.append(
            WorkEvent(
                f"validation_reuse_{row['id']}",
                "growth",
                "knowledge.reused",
                "growth_validation",
                str(row["id"]),
                str(row["created_at"]),
                title,
                payload,
            )
        )

    task_rows = db.fetchall(
        """
        SELECT *
        FROM tasks
        WHERE COALESCE(scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
        ORDER BY updated_at DESC
        """
    )
    for row in task_rows:
        title = str(row["title"] or "任务")
        created_at_str = str(row["created_at"] or "")
        occurred_at = str(row["updated_at"] or created_at_str)
        ddl = str(row["ddl"] or "")
        status = str(row["status"] or "")
        description = str(row["description"] or "")
        priority = str(row["priority"] or "")
        payload = {
            "status": status,
            "hasDeadline": bool(ddl),
            "sourceType": str(row["source_type"] or ""),
            "priority": priority,
            "summary": "任务推进",
        }
        # task.created — 每条任务都算一次创建事件
        events.append(WorkEvent(f"task_created_{row['id']}", "task", "task.created", "task", str(row["id"]), created_at_str or occurred_at, title, payload))
        # task.with_deadline / task.deadline_set — 有截止日的任务
        if ddl:
            events.append(WorkEvent(f"task_deadline_{row['id']}", "task", "task.with_deadline", "task", str(row["id"]), occurred_at, title, payload))
            events.append(WorkEvent(f"task_ddl_set_{row['id']}", "task", "task.deadline_set", "task", str(row["id"]), created_at_str or occurred_at, title, payload))
        if ddl and status == "done" and _parse_dt(occurred_at) <= _parse_dt(ddl):
            events.append(WorkEvent(f"task_done_on_time_{row['id']}", "task", "task.done_on_time", "task", str(row["id"]), occurred_at, title, payload))
        # task.closed_loop — 已完成的任务
        if status == "done":
            events.append(WorkEvent(f"task_closed_{row['id']}", "task", "task.closed_loop", "task", str(row["id"]), occurred_at, title, payload))
        # task.done_same_day — 当天创建当天完成
        if status == "done" and created_at_str and occurred_at:
            created_dt = _parse_dt(created_at_str)
            updated_dt = _parse_dt(occurred_at)
            if created_dt != datetime.min and updated_dt != datetime.min and created_dt.date() == updated_dt.date():
                events.append(WorkEvent(f"task_same_day_{row['id']}", "task", "task.done_same_day", "task", str(row["id"]), occurred_at, title, payload))
        # task.description_complete — 说明写得充分的任务（>30字符）
        if len(description) >= 30:
            events.append(WorkEvent(f"task_desc_ok_{row['id']}", "task", "task.description_complete", "task", str(row["id"]), created_at_str or occurred_at, title, payload))
        if str(row["source_type"] or "") == "growth_recommendation" and status == "done":
            events.append(WorkEvent(f"task_learning_done_{row['id']}", "task", "learning.path_completed", "task", str(row["id"]), occurred_at, title, payload))

    logs = db.fetchall(
        """
        SELECT id, action, entity_type, entity_id, detail_json, created_at
        FROM activity_logs
        ORDER BY created_at DESC
        """
    )
    create_times: dict[str, str] = {}
    for row in sorted(logs, key=lambda item: _parse_dt(str(item["created_at"] or ""))):
        action = str(row["action"] or "")
        entity_type = str(row["entity_type"] or "")
        entity_id = str(row["entity_id"] or "")
        detail = from_json(row["detail_json"], {})
        created_at = str(row["created_at"])
        if action == "task.create" and entity_type == "task":
            create_times[entity_id] = created_at
        if action == "task.confirm" and entity_type == "task":
            start = _parse_dt(create_times.get(entity_id))
            end = _parse_dt(created_at)
            if start != datetime.min and end != datetime.min and end - start <= timedelta(hours=24):
                events.append(
                    WorkEvent(
                        f"task_quick_confirm_{row['id']}",
                        "task",
                        "task.quick_response",
                        "task",
                        entity_id,
                        created_at,
                        str(detail.get("title") or "事项已快速响应"),
                        {"summary": "任务快速接收"},
                    )
                )
        # task.status_updated — 任务状态变更
        if action == "task.update" and entity_type == "task":
            events.append(
                WorkEvent(
                    f"task_updated_{row['id']}",
                    "task",
                    "task.status_updated",
                    "task",
                    entity_id,
                    created_at,
                    str(detail.get("title") or "任务已更新"),
                    {"summary": "任务状态更新"},
                )
            )
        # task.attachment_uploaded — 附件上传
        if action == "task.attachment.upload" and entity_type == "task":
            events.append(
                WorkEvent(
                    f"task_attach_{row['id']}",
                    "task",
                    "task.attachment_uploaded",
                    "task",
                    entity_id,
                    created_at,
                    str(detail.get("title") or "附件已上传"),
                    {"summary": "任务附件上传"},
                )
            )
        # task.deadline_adjusted — 截止日调整（task.update 中 ddl 变化）
        if action == "task.update" and entity_type == "task":
            changes = detail.get("changes") or detail
            if changes.get("ddl") or changes.get("due_date"):
                events.append(
                    WorkEvent(
                        f"task_ddl_adj_{row['id']}",
                        "task",
                        "task.deadline_adjusted",
                        "task",
                        entity_id,
                        created_at,
                        str(detail.get("title") or "截止日已调整"),
                        {"summary": "截止日调整"},
                    )
                )
        # task.assigned — 任务指派
        if action in ("task.create", "task.update") and entity_type == "task":
            owner = str(detail.get("owner_name") or detail.get("ownerName") or "")
            if owner:
                events.append(
                    WorkEvent(
                        f"task_assigned_{row['id']}",
                        "task",
                        "task.assigned",
                        "task",
                        entity_id,
                        created_at,
                        str(detail.get("title") or "任务已指派"),
                        {"summary": "任务指派", "ownerName": owner},
                    )
                )
        if action == "analysis.run" and entity_type == "analysis_run":
            events.append(
                WorkEvent(
                    f"analysis_share_{row['id']}",
                    "analysis",
                    "learning.knowledge_share",
                    "analysis_run",
                    entity_id,
                    created_at,
                    str(detail.get("title") or "分析产出"),
                    {"summary": "分析产出"},
                )
            )
        if action == "topic.promote.task" and entity_type == "topic_candidate":
            events.append(
                WorkEvent(
                    f"topic_promote_{row['id']}",
                    "topic",
                    "improvement.proposal_adopted",
                    "topic_candidate",
                    entity_id,
                    created_at,
                    "改进提案进入执行",
                    {"summary": "情报推动行动"},
                )
            )
        # AI 事件：chat.reply → ai.prompt_used + ai.assist_used
        if action == "chat.reply":
            events.append(WorkEvent(f"ai_prompt_{row['id']}", "ai", "ai.prompt_used", "chat", entity_id, created_at, str(detail.get("title") or "AI对话"), {"summary": "AI 对话"}))
            events.append(WorkEvent(f"ai_assist_{row['id']}", "ai", "ai.assist_used", "chat", entity_id, created_at, str(detail.get("title") or "AI协助"), {"summary": "AI 协助"}))
        # AI 事件：topic.candidate.insight → ai.assist_used + ai.result_reviewed
        if action == "topic.candidate.insight":
            events.append(WorkEvent(f"ai_insight_{row['id']}", "ai", "ai.assist_used", "topic_candidate", entity_id, created_at, str(detail.get("title") or "AI提炼洞察"), {"summary": "AI 提炼"}))
            events.append(WorkEvent(f"ai_reviewed_{row['id']}", "ai", "ai.result_reviewed", "topic_candidate", entity_id, created_at, str(detail.get("title") or "AI结果校对"), {"summary": "AI 校对"}))
        # 客户事件：client.update / client.dna_document.update → client.profile_enriched
        if action in ("client.update", "client.dna_document.update"):
            events.append(WorkEvent(f"client_enriched_{row['id']}", "client", "client.profile_enriched", "client", entity_id, created_at, str(detail.get("name") or "客户画像更新"), {"summary": "客户画像"}))
        # 客户事件：client.dna_document.update → client.key_person_identified
        if action == "client.dna_document.update":
            events.append(WorkEvent(f"client_key_person_{row['id']}", "client", "client.key_person_identified", "client", entity_id, created_at, str(detail.get("name") or "关键人识别"), {"summary": "关键人"}))
        # CRM事件：client.create → crm.lead_followed
        if action == "client.create":
            events.append(WorkEvent(f"crm_lead_{row['id']}", "crm", "crm.lead_followed", "client", entity_id, created_at, str(detail.get("name") or "新客户触达"), {"summary": "线索跟进"}))
        # CRM事件：client.document.create_from_text → crm.followup_completed
        if action == "client.document.create_from_text":
            events.append(WorkEvent(f"crm_followup_{row['id']}", "crm", "crm.followup_completed", "client", entity_id, created_at, str(detail.get("name") or "客户跟进"), {"summary": "客户跟进"}))
        # 模板事件：document.template_fill → task.template_used
        if action == "document.template_fill":
            events.append(WorkEvent(f"template_used_{row['id']}", "task", "task.template_used", "document", entity_id, created_at, str(detail.get("title") or "模板使用"), {"summary": "模板使用"}))

    candidate_rows = db.fetchall("SELECT * FROM topic_candidates ORDER BY updated_at DESC")
    for row in candidate_rows:
        title = str(row["title"] or "情报候选")
        occurred_at = str(row["updated_at"] or row["created_at"])
        status = str(row["status"] or "")
        payload = {"status": status, "summary": "情报候选"}
        events.append(WorkEvent(f"topic_candidate_{row['id']}", "topic", "improvement.proposal_submitted", "topic_candidate", str(row["id"]), occurred_at, title, payload))

    # 事件线活动 → crm.followup_completed + crm.opportunity_stage
    eline_rows = db.fetchall("SELECT * FROM event_line_activities ORDER BY happened_at DESC")
    for row in eline_rows:
        title = str(row["title"] or "事件线活动")
        occurred_at = str(row["happened_at"] or row["created_at"])
        eline_id = str(row["event_line_id"] or "")
        payload = {"sourceType": str(row["source_type"] or ""), "summary": "事件线推进"}
        events.append(WorkEvent(f"eline_followup_{row['id']}", "crm", "crm.followup_completed", "event_line", eline_id, occurred_at, title, payload))
        events.append(WorkEvent(f"eline_stage_{row['id']}", "crm", "crm.opportunity_stage", "event_line", eline_id, occurred_at, title, payload))

    return events


def _events_for_rule(events: list[WorkEvent], *, event_type: str, window_days: int | None = None, filters: dict[str, Any] | None = None, required_fields: list[str] | None = None) -> list[WorkEvent]:
    cutoff = datetime.now() - timedelta(days=window_days or 3650)
    matched = [
        event
        for event in events
        if event.event_type == event_type and _parse_dt(event.occurred_at) >= cutoff and _matches_filters(event.payload, filters, required_fields)
    ]
    return _unique_events(matched)


def _evaluate_count(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    matched = _events_for_rule(
        events,
        event_type=str(rule["eventType"]),
        window_days=int(rule.get("windowDays") or 3650),
        filters=rule.get("filters"),
        required_fields=rule.get("requiredFields"),
    )
    target = float(rule.get("targetCount") or 1)
    progress = float(len(matched))
    percent = 0 if target <= 0 else min(100, int(round((progress / target) * 100)))
    remaining = max(0, int(target - progress))
    next_action = f"再完成 1 次就会点亮【{rule['badgeName']}】" if remaining == 1 else f"还差 {remaining} 次：{rule['hintTemplate']}"
    return progress, target, percent, f"{int(progress)} / {int(target)}", [_event_to_evidence(item) for item in matched[:4]], next_action


def _evaluate_consecutive(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    matched = _events_for_rule(
        events,
        event_type=str(rule["eventType"]),
        window_days=int(rule.get("windowDays") or 3650),
        filters=rule.get("filters"),
        required_fields=rule.get("requiredFields"),
    )
    unit = str(rule.get("unit") or "week")
    period_keys = sorted({_period_key(event.occurred_at, unit) for event in matched}, key=lambda item: _period_order(item, unit))
    longest = 0
    current = 0
    previous_order: int | None = None
    for key in period_keys:
        order = _period_order(key, unit)
        if previous_order is None or order == previous_order + 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        previous_order = order
    target = float(rule.get("targetStreak") or 1)
    percent = 0 if target <= 0 else min(100, int(round((longest / target) * 100)))
    remaining = max(0, int(target - longest))
    next_action = f"再连续 1 个{ '周' if unit == 'week' else '周期' }就会点亮【{rule['badgeName']}】" if remaining == 1 else f"还差 {remaining} 个连续{ '周' if unit == 'week' else '周期' }：{rule['hintTemplate']}"
    return float(longest), target, percent, f"连续 {longest} / {int(target)}", [_event_to_evidence(item) for item in matched[:4]], next_action


def _evaluate_ratio(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    numerator = _events_for_rule(events, event_type=str(rule["numeratorEventType"]), window_days=int(rule.get("windowDays") or 3650))
    denominator = _events_for_rule(events, event_type=str(rule["denominatorEventType"]), window_days=int(rule.get("windowDays") or 3650))
    numerator_count = len(numerator)
    denominator_count = len(denominator)
    min_base = int(rule.get("minBaseCount") or 1)
    ratio = (numerator_count / denominator_count) if denominator_count else 0.0
    target_ratio = float(rule.get("minRatio") or 1.0)
    if denominator_count < min_base:
        percent = int(round((denominator_count / max(1, min_base)) * 100))
    else:
        percent = min(100, int(round((ratio / max(target_ratio, 0.01)) * 100)))
    next_action = f"把当前达成率提升到 {int(target_ratio * 100)}%，并至少形成 {min_base} 条有效样本。"
    return float(numerator_count), float(max(denominator_count, min_base)), percent, f"{numerator_count} / {denominator_count}，当前 {int(ratio * 100)}%", [_event_to_evidence(item) for item in (numerator or denominator)[:4]], next_action


def _evaluate_sequence(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    matched = _events_for_rule(events, event_type=str(rule["eventType"]), window_days=int(rule.get("windowDays") or 3650))
    completed_stage = str(rule.get("completedStage") or "")
    completed = [event for event in matched if str(event.payload.get("stage") or event.payload.get("status") or "") == completed_stage]
    progress = float(len(_unique_events(completed)))
    target = 1.0
    percent = 100 if progress >= target else 0
    next_action = f"继续把事项推进到【{completed_stage}】。"
    return progress, target, percent, f"{int(progress)} / 1", [_event_to_evidence(item) for item in matched[:4]], next_action


def _evaluate_composite(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    conditions = list(rule.get("conditions") or [])
    satisfied = 0
    texts: list[str] = []
    evidences: list[BadgeEvidenceRecord] = []
    next_action = str(rule.get("hintTemplate") or "")
    for condition in conditions:
        matched = _events_for_rule(
            events,
            event_type=str(condition.get("eventType") or ""),
            window_days=int(rule.get("windowDays") or 3650),
            filters=condition.get("filters"),
            required_fields=condition.get("requiredFields"),
        )
        target = int(condition.get("targetCount") or 1)
        count = len(matched)
        texts.append(f"{condition.get('label') or condition.get('eventType')}: {count}/{target}")
        evidences.extend(_event_to_evidence(item) for item in matched[:2])
        if count >= target:
            satisfied += 1
        elif not next_action:
            next_action = str(condition.get("hint") or "")
    target_total = float(len(conditions) or 1)
    percent = int(round((satisfied / target_total) * 100))
    if target_total - satisfied == 1:
        next_action = f"再补齐 1 项条件就会点亮【{rule['badgeName']}】"
    elif not next_action:
        next_action = str(rule.get("hintTemplate") or "")
    return float(satisfied), target_total, percent, " / ".join(texts), list({item.id: item for item in evidences}.values())[:4], next_action


def _evaluate_rule(rule: dict[str, Any], events: list[WorkEvent]) -> tuple[float, float, int, str, list[BadgeEvidenceRecord], str]:
    rule_type: RuleType = rule["type"]
    if rule_type == "count":
        return _evaluate_count(rule, events)
    if rule_type == "consecutive":
        return _evaluate_consecutive(rule, events)
    if rule_type == "ratio":
        return _evaluate_ratio(rule, events)
    if rule_type == "sequence":
        return _evaluate_sequence(rule, events)
    return _evaluate_composite(rule, events)


def _badge_definitions() -> list[dict[str, Any]]:
    def link(label: str, tab: str) -> dict[str, str]:
        return {"label": label, "tab": tab}

    return [
        # ── 任务推进系 (1-10) ──────────────────────────────────────────
        {"id": "spark_start", "code": "task_progress.spark_start", "name": "开工火花", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 10, "iconMotif": "spark_card", "description": "首次主动新建并推进一条任务线。", "whyItMatters": "第一次自发启动是自驱力的起点。", "systemHowText": "系统会识别用户是否主动创建并推进过至少一条任务。", "hintTemplate": "新建一条任务并推进到下一步。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 365, "eventType": "task.created", "targetCount": 1}},
        {"id": "closer_hand", "code": "task_progress.closer_hand", "name": "收口手", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 12, "iconMotif": "converge_box", "description": "把零散事项收成一条清楚的任务。", "whyItMatters": "收口能力是推进力最直接的表现。", "systemHowText": "系统会识别零散事项被合并或归纳为结构化任务。", "hintTemplate": "把散落的待办整理成一条有说明的任务。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.created", "targetCount": 5}},
        {"id": "one_shot_clear", "code": "task_progress.one_shot_clear", "name": "一次到位", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "check_list", "description": "任务说明写得清楚，减少反复追问。", "whyItMatters": "说清楚减少 80% 的沟通成本。", "systemHowText": "系统会识别任务说明字数和后续追问频率。", "hintTemplate": "创建任务时把目标、步骤和完成标准写清楚。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.description_complete", "targetCount": 5}},
        {"id": "continuous_push", "code": "task_progress.continuous_push", "name": "连续推进", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "steps_forward", "description": "连续多天让同一事项持续往前走。", "whyItMatters": "持续推进比间歇爆发更能把事做完。", "systemHowText": "系统会识别连续多天有任务状态更新。", "hintTemplate": "连续三天更新同一任务的进展。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "day", "targetStreak": 3, "windowDays": 30, "eventType": "task.status_updated"}},
        {"id": "breakdown_master", "code": "task_progress.breakdown_master", "name": "拆解高手", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "split_blocks", "description": "把大事拆成可执行的小步。", "whyItMatters": "好的拆解是执行力最直接的表现。", "systemHowText": "系统会识别父任务和可执行子项之间的结构关系。", "hintTemplate": "把大任务拆成可执行小任务，再分责任人。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "task.created", "targetCount": 5}},
        {"id": "blocker_spotter", "code": "task_progress.blocker_spotter", "name": "卡点识别", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "roadblock_light", "description": "能及时说清楚事情卡在哪里。", "whyItMatters": "说清卡点比埋头硬做更有效。", "systemHowText": "系统会识别任务或复盘中标记的卡点与阻碍。", "hintTemplate": "遇到阻碍时在任务里写清卡点原因。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "project.risk_flagged", "targetCount": 3}},
        {"id": "today_zero", "code": "task_progress.today_zero", "name": "今日清零", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "calendar_zero", "description": "当天关键事项当天收口。", "whyItMatters": "日清能力让整体节奏不拖沓。", "systemHowText": "系统会识别当天创建且当天完成的任务数。", "hintTemplate": "今天的关键事项今天收口。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 14, "eventType": "task.done_same_day", "targetCount": 5}},
        {"id": "week_target_hit", "code": "task_progress.week_target_hit", "name": "周目标命中", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 20, "iconMotif": "bullseye_arrow", "description": "一周里把最重要的事项按时推进。", "whyItMatters": "周目标命中率是执行节奏的真实度量。", "systemHowText": "系统会识别有截止日的任务中按时完成的比例。", "hintTemplate": "更新本周重点任务状态，确保按时完成。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "ratio", "windowDays": 14, "numeratorEventType": "task.done_on_time", "denominatorEventType": "task.with_deadline", "minRatio": 0.8, "minBaseCount": 3}},
        {"id": "key_task_guardian", "code": "task_progress.key_task_guardian", "name": "关键任务守护者", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 22, "iconMotif": "shield_card", "description": "把高优任务稳稳盯住不丢。", "whyItMatters": "关键任务不能掉是组织信任的基础。", "systemHowText": "系统会识别高优先级任务是否持续被跟进。", "hintTemplate": "确保高优任务每周至少更新一次进展。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 3, "windowDays": 60, "eventType": "task.status_updated"}},
        {"id": "closed_loop_exec", "code": "task_progress.closed_loop_exec", "name": "闭环执行官", "categoryId": "task_progress", "categoryLabel": "任务推进系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 25, "iconMotif": "loop_flag", "description": "从开始、推进到交付形成闭环。", "whyItMatters": "闭环是推进力最高形态。", "systemHowText": "系统会识别从创建到完成的完整任务闭环。", "hintTemplate": "完成一条从创建到交付的完整任务。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.closed_loop", "targetCount": 5}},
        # ── 日历与节奏系 (11-20) ──────────────────────────────────────────
        {"id": "time_arranger", "code": "calendar_rhythm.time_arranger", "name": "时间编排师", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 12, "iconMotif": "time_blocks", "description": "能把任务安排进合理时间段。", "whyItMatters": "时间编排是节奏感的第一步。", "systemHowText": "系统会识别任务是否设置了截止日期。", "hintTemplate": "给任务设定合理的截止时间。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 30, "eventType": "task.deadline_set", "targetCount": 10}},
        {"id": "focus_guard", "code": "calendar_rhythm.focus_guard", "name": "专注时段守门员", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "door_focus", "description": "为重要工作留出完整专注时间。", "whyItMatters": "深度工作需要不被打断的整块时间。", "systemHowText": "系统会识别是否有集中时段的任务推进记录。", "hintTemplate": "为本周最重要的事留出一段不被打断的时间。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 30, "eventType": "task.closed_loop", "targetCount": 4}},
        {"id": "early_preparer", "code": "calendar_rhythm.early_preparer", "name": "提前准备者", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "bell_early", "description": "在会议或截止前完成准备。", "whyItMatters": "提前准备让会议效率翻倍。", "systemHowText": "系统会识别会议前是否有任务或文档准备记录。", "hintTemplate": "在会议前准备好所需材料和议程。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.published", "targetCount": 5}},
        {"id": "post_meeting_closer", "code": "calendar_rhythm.post_meeting_closer", "name": "会后收口者", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "bubble_basket", "description": "会后能迅速把行动项接住。", "whyItMatters": "会后收口速度决定会议价值转化率。", "systemHowText": "系统会识别会议发布后24小时内是否有关联任务创建。", "hintTemplate": "会后当天把行动项转成任务。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.closed_loop", "targetCount": 3}},
        {"id": "rhythm_calibrator", "code": "calendar_rhythm.rhythm_calibrator", "name": "节奏校准者", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "dial_clock", "description": "发现任务与时间安排不匹配并纠正。", "whyItMatters": "及时校准比死守计划更智慧。", "systemHowText": "系统会识别截止日调整后是否仍按时完成。", "hintTemplate": "检查本周任务时间安排，调整不合理的排期。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.deadline_adjusted", "targetCount": 3}},
        {"id": "schedule_predictor", "code": "calendar_rhythm.schedule_predictor", "name": "预判排期者", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "timeline_split", "description": "提前看到时间冲突并调整。", "whyItMatters": "预判能把冲突消灭在发生之前。", "systemHowText": "系统会识别是否在截止日前提前调整过排期。", "hintTemplate": "提前检查下周日程，识别可能的冲突。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.deadline_adjusted", "targetCount": 3}},
        {"id": "morning_starter", "code": "calendar_rhythm.morning_starter", "name": "清晨启动器", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 12, "iconMotif": "sunrise_card", "description": "早上迅速进入工作状态。", "whyItMatters": "早启动决定一天的节奏感。", "systemHowText": "系统会识别每天第一次任务操作的时间。", "hintTemplate": "每天上午完成第一个任务动作。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "day", "targetStreak": 5, "windowDays": 14, "eventType": "task.status_updated"}},
        {"id": "evening_reviewer", "code": "calendar_rhythm.evening_reviewer", "name": "晚间复盘人", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 15, "iconMotif": "lamp_notebook", "description": "当天结束前会回看并补判断。", "whyItMatters": "日清复盘让经验不隔夜。", "systemHowText": "系统会识别一天结束时的复盘或状态更新行为。", "hintTemplate": "下班前回看今天的任务，补上判断和备注。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "day", "targetStreak": 3, "windowDays": 14, "eventType": "review.submitted"}},
        {"id": "conflict_resolver", "code": "calendar_rhythm.conflict_resolver", "name": "冲突化解师", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 18, "iconMotif": "parallel_lines", "description": "把会议、任务、出行等冲突排顺。", "whyItMatters": "化解冲突让并行事务不打架。", "systemHowText": "系统会识别时间冲突后的任务重新排期行为。", "hintTemplate": "遇到时间冲突时及时调整优先级和排期。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.deadline_adjusted", "targetCount": 5}},
        {"id": "week_rhythm_director", "code": "calendar_rhythm.week_rhythm_director", "name": "周节奏导演", "categoryId": "calendar_rhythm", "categoryLabel": "日历与节奏系", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["全员"], "xp": 22, "iconMotif": "week_baton", "description": "能把一周安排出起承转合。", "whyItMatters": "周节奏稳定是高效能的底层操作系统。", "systemHowText": "系统会识别连续周的任务完成率和复盘提交。", "hintTemplate": "保持连续四周稳定的工作节奏。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 4, "windowDays": 60, "eventType": "review.submitted"}},
        # ── 会议与纪要系 (21-30) ──────────────────────────────────────────
        {"id": "meeting_catcher", "code": "meeting_notes.meeting_catcher", "name": "会议捕手", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 12, "iconMotif": "hand_card", "description": "能把会里的关键内容及时接住。", "whyItMatters": "接住关键信息是会议价值的起点。", "systemHowText": "系统会识别已发布的会议纪要数量。", "hintTemplate": "会后及时发布会议纪要。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.published", "targetCount": 3}},
        {"id": "key_point_distiller", "code": "meeting_notes.key_point_distiller", "name": "要点提炼师", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "highlight_lines", "description": "能把一场会收成几条重点。", "whyItMatters": "提炼能力决定信息传递效率。", "systemHowText": "系统会识别纪要中是否有清晰的结论和决议。", "hintTemplate": "纪要里把最关键的三条重点标出来。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.published", "targetCount": 5}},
        {"id": "action_translator", "code": "meeting_notes.action_translator", "name": "行动项翻译官", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "bubble_to_list", "description": "把讨论翻译成可执行事项。", "whyItMatters": "讨论不转行动等于没开会。", "systemHowText": "系统会识别会议中的行动项是否有责任人和截止日。", "hintTemplate": "会后把讨论转成带责任人的行动项。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.closed_loop", "targetCount": 3}},
        {"id": "risk_recorder", "code": "meeting_notes.risk_recorder", "name": "风险记录员", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "flag_margin", "description": "能及时记下风险和模糊点。", "whyItMatters": "记录风险是防御性推进的起点。", "systemHowText": "系统会识别会议中标记的风险和待澄清项。", "hintTemplate": "会议中及时记录风险和模糊点。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "project.risk_flagged", "targetCount": 5}},
        {"id": "consensus_anchor", "code": "meeting_notes.consensus_anchor", "name": "共识锚定者", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "anchor_bubbles", "description": "会议中能抓住已形成的共识。", "whyItMatters": "锚定共识让后续推进有根据。", "systemHowText": "系统会识别纪要中是否明确标注了共识和决议。", "hintTemplate": "纪要里把达成的共识和决议明确写出来。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.published", "targetCount": 8}},
        {"id": "decision_tracker", "code": "meeting_notes.decision_tracker", "name": "决议追踪者", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "stamp_card", "description": "不让会里的决定落空。", "whyItMatters": "追踪决议是闭环文化的核心。", "systemHowText": "系统会识别会议决议是否在后续被关联到任务。", "hintTemplate": "检查上次会议的决议是否都已落实。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.closed_loop", "targetCount": 5}},
        {"id": "recording_organizer", "code": "meeting_notes.recording_organizer", "name": "录音整理者", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "wave_to_text", "description": "把录音快速转成可读内容。", "whyItMatters": "录音转文字让信息不再只存在记忆中。", "systemHowText": "系统会识别会议中是否有附件上传和转写记录。", "hintTemplate": "会后上传录音或整理录音要点。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.published", "targetCount": 3}},
        {"id": "one_page_noter", "code": "meeting_notes.one_page_noter", "name": "一页纪要师", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "page_sections", "description": "能把复杂会议收成一页就看懂。", "whyItMatters": "简洁的纪要传播效率最高。", "systemHowText": "系统会识别纪要结构完整度和阅读友好度。", "hintTemplate": "把下一场会的纪要控制在一页以内。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 120, "eventType": "meeting.published", "targetCount": 10}},
        {"id": "post_meeting_driver", "code": "meeting_notes.post_meeting_driver", "name": "会后推进官", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 22, "iconMotif": "table_path", "description": "会后能持续盯住推进。", "whyItMatters": "会后推进是会议价值兑现的最后一环。", "systemHowText": "系统会识别会议后的行动项是否有持续更新。", "hintTemplate": "会后持续跟进行动项直到完成。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.closed_loop", "targetCount": 8}},
        {"id": "meeting_to_task_master", "code": "meeting_notes.meeting_to_task_master", "name": "会议转任务大师", "categoryId": "meeting_notes", "categoryLabel": "会议与纪要系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 25, "iconMotif": "card_to_box", "description": "会后事项能一键进系统。", "whyItMatters": "会议到任务的转化率决定组织执行效率。", "systemHowText": "系统会识别会议中关联任务的完整度。", "hintTemplate": "会后把所有行动项转成系统任务。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.closed_loop", "targetCount": 10}},
        # ── 客户理解系 (31-40) ──────────────────────────────────────────
        {"id": "client_speed_reader", "code": "customer_insight.speed_reader", "name": "客户速读者", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 12, "iconMotif": "person_lens", "description": "能快速抓住客户是谁、在乎什么。", "whyItMatters": "快速理解客户是有效合作的前提。", "systemHowText": "系统会识别客户相关任务中是否有背景说明。", "hintTemplate": "在客户相关任务中补上客户背景描述。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 120, "eventType": "client.requirement_clarified", "targetCount": 2}},
        {"id": "background_puzzler", "code": "customer_insight.background_puzzler", "name": "背景拼图师", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 15, "iconMotif": "puzzle_outline", "description": "能把客户背景拼成整体理解。", "whyItMatters": "拼完整背景才能看到全貌。", "systemHowText": "系统会识别客户工作台中背景资料的丰富度。", "hintTemplate": "把客户的组织背景、核心诉求和关键人梳理一遍。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "client.profile_enriched", "targetCount": 3}},
        {"id": "scene_observer", "code": "customer_insight.scene_observer", "name": "场景洞察员", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 18, "iconMotif": "scene_frame", "description": "能看到客户问题发生在哪个场景。", "whyItMatters": "理解场景比只理解问题更深一层。", "systemHowText": "系统会识别复盘或纪要中是否有场景分析描述。", "hintTemplate": "在下次客户复盘中写清问题发生的具体场景。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.structured_entry", "targetCount": 3}},
        {"id": "need_translator", "code": "customer_insight.need_translator", "name": "需求翻译官", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 20, "iconMotif": "cloud_to_tag", "description": "能把模糊表达翻成真实需求。", "whyItMatters": "翻译需求是避免做错事的关键能力。", "systemHowText": "系统会识别会议中待澄清问题被消解的记录。", "hintTemplate": "把客户的模糊表达翻译成具体需求条目。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 120, "eventType": "client.requirement_clarified", "targetCount": 5}},
        {"id": "relation_thermometer", "code": "customer_insight.relation_thermometer", "name": "关系温度计", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 18, "iconMotif": "thermometer_hand", "description": "能感知合作关系冷暖变化。", "whyItMatters": "关系温度变化往往是风险的先兆。", "systemHowText": "系统会识别客户相关活动的频率变化。", "hintTemplate": "定期检查客户互动频率，留意关系温度变化。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "crm.followup_completed", "targetCount": 5}},
        {"id": "pain_point_lighter", "code": "customer_insight.pain_point_lighter", "name": "痛点照明者", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 20, "iconMotif": "spotlight_crack", "description": "能照出客户真正难受的地方。", "whyItMatters": "找到真痛点才能提供真价值。", "systemHowText": "系统会识别复盘中是否有客户痛点分析。", "hintTemplate": "在复盘中明确写出客户最核心的痛点。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "client_dna_keeper", "code": "customer_insight.dna_keeper", "name": "客户DNA守护者", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 22, "iconMotif": "helix_card", "description": "能持续维护客户画像与核心判断。", "whyItMatters": "持续维护的客户画像是团队共享资产。", "systemHowText": "系统会识别客户资料的持续更新频率。", "hintTemplate": "每月更新一次核心客户的画像和判断。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "month", "targetStreak": 3, "windowDays": 120, "eventType": "client.profile_enriched"}},
        {"id": "stage_judge", "code": "customer_insight.stage_judge", "name": "阶段判断员", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 20, "iconMotif": "milestone_steps", "description": "能看出合作到了哪个阶段。", "whyItMatters": "阶段判断决定下一步该做什么。", "systemHowText": "系统会识别商机阶段推进记录。", "hintTemplate": "更新当前客户合作的阶段判断。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "crm.opportunity_stage", "targetCount": 3}},
        {"id": "key_person_spotter", "code": "customer_insight.key_person_spotter", "name": "关键人识别者", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 22, "iconMotif": "person_highlight", "description": "能识别谁是真正关键对象。", "whyItMatters": "找对人比做对事更重要。", "systemHowText": "系统会识别客户工作台中关键人的标注记录。", "hintTemplate": "在客户工作台中标注出关键决策人。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "client.key_person_identified", "targetCount": 3}},
        {"id": "client_mirror", "code": "customer_insight.client_mirror", "name": "客户镜像师", "categoryId": "customer_insight", "categoryLabel": "客户理解系", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["全员"], "xp": 25, "iconMotif": "mirror_outline", "description": "能把客户现状映照得清楚。", "whyItMatters": "清晰映照是方案力的前提。", "systemHowText": "系统会识别客户分析报告的完整度和质量。", "hintTemplate": "输出一份完整的客户现状分析。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "analysis.proposal_advanced", "targetCount": 3}},
        # ── 关系与合作系 (41-50) ──────────────────────────────────────────
        {"id": "ice_breaker", "code": "relationship_collab.ice_breaker", "name": "首次破冰者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 12, "iconMotif": "ice_warm", "description": "让初次接触自然地开始。", "whyItMatters": "好的开始是成功的一半。", "systemHowText": "系统会识别首次客户或合作方的互动记录。", "hintTemplate": "主动完成一次新客户或新合作方的首次接触。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "crm.lead_followed", "targetCount": 3}},
        {"id": "trust_builder", "code": "relationship_collab.trust_builder", "name": "信任累积者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "stacked_stones", "description": "通过稳定互动积累信任。", "whyItMatters": "信任是长期合作的基石。", "systemHowText": "系统会识别对同一客户的持续跟进记录。", "hintTemplate": "对同一客户保持每月至少一次稳定互动。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "month", "targetStreak": 3, "windowDays": 120, "eventType": "crm.followup_completed"}},
        {"id": "no_drop_followup", "code": "relationship_collab.no_drop_followup", "name": "跟进不掉线", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "thread_nodes", "description": "跟进过程中不让合作线断掉。", "whyItMatters": "持续跟进比爆发式沟通更有效。", "systemHowText": "系统会识别客户跟进的连续性。", "hintTemplate": "确保每个活跃客户都有持续的跟进记录。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "crm.followup_completed", "targetCount": 8}},
        {"id": "boundary_clarifier", "code": "relationship_collab.boundary_clarifier", "name": "边界澄清者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 18, "iconMotif": "boundary_blocks", "description": "能把合作边界讲清楚。", "whyItMatters": "清晰边界减少后续扯皮。", "systemHowText": "系统会识别合作范围和边界的文档记录。", "hintTemplate": "在合作启动时把边界和范围写清楚。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "client.requirement_clarified", "targetCount": 3}},
        {"id": "co_creation_inviter", "code": "relationship_collab.co_creation_inviter", "name": "共创邀请者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "dual_pens", "description": "能把对方拉进共同设计。", "whyItMatters": "共创让合作从供需变成伙伴。", "systemHowText": "系统会识别跨角色协作会议或共创工作坊。", "hintTemplate": "邀请客户或合作方参与一次共创讨论。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "meeting.cross_function", "targetCount": 3}},
        {"id": "collab_closer", "code": "relationship_collab.collab_closer", "name": "合作收束者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "knot_hand", "description": "把泛意向收束成具体合作。", "whyItMatters": "收束是把机会变成现实的关键动作。", "systemHowText": "系统会识别商机从意向推进到合作的记录。", "hintTemplate": "把当前意向推进到具体合作方案。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 365, "eventType": "crm.opportunity_stage", "targetCount": 2}},
        {"id": "external_interface", "code": "relationship_collab.external_interface", "name": "外部接口人", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "connector_dual", "description": "对外沟通稳定、清楚、有承接。", "whyItMatters": "稳定的外部接口降低合作摩擦。", "systemHowText": "系统会识别外部会议和跟进的稳定频率。", "hintTemplate": "保持外部沟通的稳定节奏。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 4, "windowDays": 60, "eventType": "crm.followup_completed"}},
        {"id": "network_weaver", "code": "relationship_collab.network_weaver", "name": "网络编织者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 22, "iconMotif": "web_nodes", "description": "把零散关系编成更大的网。", "whyItMatters": "网络效应让每段关系都更有价值。", "systemHowText": "系统会识别多客户之间的跨线索联动。", "hintTemplate": "把相关客户或合作方的信息进行交叉引用。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 365, "eventType": "crm.lead_followed", "targetCount": 10}},
        {"id": "hub_connector", "code": "relationship_collab.hub_connector", "name": "枢纽连接者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 25, "iconMotif": "bridge_platforms", "description": "打通关键枢纽组织或关键人。", "whyItMatters": "枢纽连接能撬动整个网络。", "systemHowText": "系统会识别关键合作节点的建立记录。", "hintTemplate": "识别并连接一个关键枢纽组织或人。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 365, "eventType": "client.key_person_identified", "targetCount": 5}},
        {"id": "long_term_partner", "code": "relationship_collab.long_term_partner", "name": "长期伙伴建造者", "categoryId": "relationship_collab", "categoryLabel": "关系与合作系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 28, "iconMotif": "dual_rings", "description": "把合作从项目做成长期关系。", "whyItMatters": "长期伙伴是组织最稳定的增长来源。", "systemHowText": "系统会识别同一客户超过6个月的持续合作记录。", "hintTemplate": "维护一段超过半年的持续合作关系。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "month", "targetStreak": 6, "windowDays": 365, "eventType": "crm.followup_completed"}},
        # ── 研究与情报系 (51-60) ──────────────────────────────────────────
        {"id": "clue_catcher", "code": "research_intel.clue_catcher", "name": "线索捕手", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 12, "iconMotif": "net_sparkle", "description": "能从杂音里抓住有用线索。", "whyItMatters": "有效的线索是判断的原材料。", "systemHowText": "系统会识别情报候选条目的创建记录。", "hintTemplate": "记录一条从外部信息中发现的有用线索。", "actionLinks": [link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 90, "eventType": "improvement.proposal_submitted", "targetCount": 3}},
        {"id": "material_checker", "code": "research_intel.material_checker", "name": "资料清点师", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 12, "iconMotif": "folder_stack", "description": "能把资料盘清楚不遗漏。", "whyItMatters": "盘清资料是研究的起点。", "systemHowText": "系统会识别附件上传和整理的完整度。", "hintTemplate": "把项目相关资料整理上传到系统。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.attachment_uploaded", "targetCount": 5}},
        {"id": "noise_filter", "code": "research_intel.noise_filter", "name": "信息去噪者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "filter_clean", "description": "能把杂乱信息理干净。", "whyItMatters": "去噪让关键信息更容易被看到。", "systemHowText": "系统会识别复盘或分析中信息提炼的质量。", "hintTemplate": "在下次分析中把噪音信息过滤掉，只留关键点。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 120, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "evidence_tagger", "code": "research_intel.evidence_tagger", "name": "证据标注员", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "pin_evidence", "description": "能给观点找到清楚出处。", "whyItMatters": "有证据支撑的判断更可靠。", "systemHowText": "系统会识别复盘中是否有引用来源或附件支撑。", "hintTemplate": "在分析中标注证据来源。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 120, "eventType": "task.attachment_uploaded", "targetCount": 8}},
        {"id": "case_gold_panner", "code": "research_intel.case_gold_panner", "name": "案例淘金者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "pan_gold", "description": "能从案例中捞出有用模式。", "whyItMatters": "案例模式是经验的结晶。", "systemHowText": "系统会识别经验卡片的沉淀数量和质量。", "hintTemplate": "从一个成功案例中提炼出可复用的模式。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "knowledge.experience_published", "targetCount": 3}},
        {"id": "trend_sniffer", "code": "research_intel.trend_sniffer", "name": "趋势嗅探者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "radar_waves", "description": "能提前闻到外部变化。", "whyItMatters": "提前嗅到变化就是提前赢得窗口。", "systemHowText": "系统会识别情报和分析输出的频率。", "hintTemplate": "记录一条你观察到的行业趋势变化。", "actionLinks": [link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 180, "eventType": "improvement.proposal_submitted", "targetCount": 5}},
        {"id": "industry_puzzler", "code": "research_intel.industry_puzzler", "name": "行业拼图师", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 20, "iconMotif": "map_pieces", "description": "把行业现状拼成一张大图。", "whyItMatters": "行业大图是战略判断的基础。", "systemHowText": "系统会识别综合性分析报告的产出。", "hintTemplate": "输出一份行业或领域的综合分析。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "analysis.proposal_advanced", "targetCount": 2}},
        {"id": "problem_definer", "code": "research_intel.problem_definer", "name": "问题定义者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 20, "iconMotif": "question_frame", "description": "能把模糊困境说成清楚问题。", "whyItMatters": "问题定义清楚了，解法自然浮现。", "systemHowText": "系统会识别复盘或分析中问题定义的清晰度。", "hintTemplate": "把一个模糊的困境重新定义成清晰的问题。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.retrospective_completed", "targetCount": 3}},
        {"id": "source_gatekeeper", "code": "research_intel.source_gatekeeper", "name": "可靠来源守门员", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "door_source", "description": "能分辨什么能信、什么不能信。", "whyItMatters": "来源可靠性决定判断质量。", "systemHowText": "系统会识别引用和来源的标注规范度。", "hintTemplate": "在研究中标注每个关键信息的来源可靠度。", "actionLinks": [link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 180, "eventType": "knowledge.experience_published", "targetCount": 5}},
        {"id": "intel_to_task", "code": "research_intel.intel_to_task", "name": "情报转任务者", "categoryId": "research_intel", "categoryLabel": "研究与情报系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 22, "iconMotif": "news_to_task", "description": "把外部信息转成内部行动。", "whyItMatters": "情报只有转化为行动才有价值。", "systemHowText": "系统会识别改进建议进入任务执行的记录。", "hintTemplate": "把一条外部情报转化成一个具体的内部任务。", "actionLinks": [link("去话题情报", "topics_management"), link("去任务与日程", "tasks")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "情报收集", "eventType": "improvement.proposal_submitted", "targetCount": 3, "hint": "先收集 3 条情报。"}, {"label": "转化执行", "eventType": "improvement.proposal_adopted", "targetCount": 1, "hint": "至少推动 1 条情报进入执行。"}]}},
        # ── 判断与策略系 (61-70) ──────────────────────────────────────────
        {"id": "mainline_spotter", "code": "judgment_strategy.mainline_spotter", "name": "主线辨识者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 15, "iconMotif": "thick_line", "description": "能看出真正该盯的主线。", "whyItMatters": "抓主线是避免无效忙碌的关键。", "systemHowText": "系统会识别复盘中是否有清晰的主线判断。", "hintTemplate": "在周复盘中写出本周最该盯的主线。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "priority_officer", "code": "judgment_strategy.priority_officer", "name": "轻重缓急官", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 18, "iconMotif": "stone_stairs", "description": "能把先后顺序排出来。", "whyItMatters": "排对优先级比多做事更重要。", "systemHowText": "系统会识别任务优先级设置和调整记录。", "hintTemplate": "给本周任务重新排一次优先级。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.status_updated", "targetCount": 10}},
        {"id": "variable_watcher", "code": "judgment_strategy.variable_watcher", "name": "变量观察者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 18, "iconMotif": "eye_dials", "description": "能留意哪些条件在改变。", "whyItMatters": "变量感知是风险前置的基础。", "systemHowText": "系统会识别复盘或会议中对变量和变化的记录。", "hintTemplate": "在复盘中记录本周发生了哪些关键变量变化。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 90, "eventType": "review.structured_entry", "targetCount": 3}},
        {"id": "risk_predictor", "code": "judgment_strategy.risk_predictor", "name": "风险预判者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 20, "iconMotif": "warning_crack", "description": "提前看到可能出问题的地方。", "whyItMatters": "预判风险是最高效的风控手段。", "systemHowText": "系统会识别会议和复盘里标记的风险与预警。", "hintTemplate": "提前标出可能出问题的地方和应对方案。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "project.risk_flagged", "targetCount": 5}},
        {"id": "hypothesis_maker", "code": "judgment_strategy.hypothesis_maker", "name": "假设提出者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 18, "iconMotif": "bulb_question", "description": "能提出值得验证的判断假设。", "whyItMatters": "好假设加速决策质量。", "systemHowText": "系统会识别复盘中是否有假设和验证记录。", "hintTemplate": "在复盘中提出一个待验证的判断假设。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.retrospective_completed", "targetCount": 3}},
        {"id": "counter_questioner", "code": "judgment_strategy.counter_questioner", "name": "反例质询者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 20, "iconMotif": "dialog_reverse", "description": "能反问系统和自己是否想偏了。", "whyItMatters": "自我质疑是深度判断的标志。", "systemHowText": "系统会识别复盘中是否有反思和质疑记录。", "hintTemplate": "在复盘中对自己的判断提出一次反面质询。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.retrospective_completed", "targetCount": 5}},
        {"id": "direction_calibrator", "code": "judgment_strategy.direction_calibrator", "name": "方向校准者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 20, "iconMotif": "compass_correct", "description": "能及时把偏航的线拉回主线。", "whyItMatters": "及时校正比死守旧方向更重要。", "systemHowText": "系统会识别项目方向调整和校正的记录。", "hintTemplate": "发现偏离时及时校准方向并记录。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 120, "eventType": "task.deadline_adjusted", "targetCount": 5}},
        {"id": "leverage_finder", "code": "judgment_strategy.leverage_finder", "name": "杠杆点发现者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 22, "iconMotif": "lever_rock", "description": "能发现小投入大回报的位置。", "whyItMatters": "杠杆思维是策略力的核心。", "systemHowText": "系统会识别改进提案中的杠杆性建议。", "hintTemplate": "找到一个小投入大回报的改进点并记录。", "actionLinks": [link("去话题情报", "topics_management"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "improvement.proposal_submitted", "targetCount": 3}},
        {"id": "opportunity_amplifier", "code": "judgment_strategy.opportunity_amplifier", "name": "机会放大者", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 22, "iconMotif": "lens_seed", "description": "能把好机会看深一步。", "whyItMatters": "放大机会比发现机会更稀缺。", "systemHowText": "系统会识别商机深度推进和方案升级记录。", "hintTemplate": "把一个发现的机会进一步深挖和扩展。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 365, "eventType": "analysis.proposal_advanced", "targetCount": 3}},
        {"id": "strategy_translator", "code": "judgment_strategy.strategy_translator", "name": "战略翻译官", "categoryId": "judgment_strategy", "categoryLabel": "判断与策略系", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员", "管理"], "xp": 25, "iconMotif": "map_to_cards", "description": "把大方向翻成能执行的话。", "whyItMatters": "战略落地的关键是翻译成可执行动作。", "systemHowText": "系统会识别战略目标分解为具体任务的记录。", "hintTemplate": "把一个大方向分解成三个以上可执行的任务。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "task.created", "targetCount": 10}},
        # ── 交付与产品化系 (71-80) ──────────────────────────────────────────
        {"id": "one_page_planner", "code": "delivery_product.one_page_planner", "name": "一页方案师", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 15, "iconMotif": "page_structure", "description": "能把复杂事情收成一页讲清楚。", "whyItMatters": "一页方案是方案力的极致表现。", "systemHowText": "系统会识别方案型输出的产出记录。", "hintTemplate": "用一页纸把当前最重要的方案讲清楚。", "actionLinks": [link("去成长手册", "growth_handbook"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 180, "eventType": "analysis.proposal_advanced", "targetCount": 3}},
        {"id": "template_forger", "code": "delivery_product.template_forger", "name": "模板锻造者", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 18, "iconMotif": "mold_cards", "description": "把反复做的事打成模板。", "whyItMatters": "模板是效率杠杆的基础设施。", "systemHowText": "系统会识别方法型成长手册条目。", "hintTemplate": "把一个反复做的事情整理成模板。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.sop_published", "targetCount": 2}},
        {"id": "sop_seed", "code": "delivery_product.sop_seed", "name": "SOP种子手", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 18, "iconMotif": "sprout_flow", "description": "能把流程长成 SOP 雏形。", "whyItMatters": "SOP 是组织可复制性的底层资产。", "systemHowText": "系统会识别 SOP 类手册条目的发布。", "hintTemplate": "把一个流程写成 SOP 发布到系统。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.sop_published", "targetCount": 3}},
        {"id": "toolkit_assembler", "code": "delivery_product.toolkit_assembler", "name": "工具包拼装师", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 20, "iconMotif": "toolbox_docs", "description": "把零散材料组装成工具包。", "whyItMatters": "工具包让团队效率成倍提升。", "systemHowText": "系统会识别多个相关经验卡片或模板的集合。", "hintTemplate": "把相关的模板和经验整理成一个工具包。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.experience_published", "targetCount": 5}},
        {"id": "workshop_director", "code": "delivery_product.workshop_director", "name": "工作坊导演", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 20, "iconMotif": "whiteboard_spot", "description": "能把内容排成有节奏的现场。", "whyItMatters": "好的工作坊让共创效率最大化。", "systemHowText": "系统会识别跨角色会议和协作的组织记录。", "hintTemplate": "组织一次有明确产出的工作坊或研讨会。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 365, "eventType": "meeting.cross_function", "targetCount": 3}},
        {"id": "experience_to_product", "code": "delivery_product.experience_to_product", "name": "从经验到产品", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 22, "iconMotif": "footprint_box", "description": "把一次经验变成可复用产品。", "whyItMatters": "经验产品化是组织增长的加速器。", "systemHowText": "系统会识别经验卡片被后续复用的记录。", "hintTemplate": "把一次成功经验包装成可复用的产品或方法。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "经验沉淀", "eventType": "knowledge.experience_published", "targetCount": 3, "hint": "先沉淀 3 条经验。"}, {"label": "被复用", "eventType": "knowledge.reused", "targetCount": 3, "hint": "让经验被后续任务复用。"}]}},
        {"id": "reuse_designer", "code": "delivery_product.reuse_designer", "name": "复用设计者", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 22, "iconMotif": "center_copy", "description": "做出来的东西别人也能用。", "whyItMatters": "可复用是交付物的最高标准。", "systemHowText": "系统会识别知识条目的复用频次。", "hintTemplate": "改进一份已有的产出，让它更容易被复用。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.reused", "targetCount": 5}},
        {"id": "delivery_closer", "code": "delivery_product.delivery_closer", "name": "交付收束官", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 22, "iconMotif": "zip_folder", "description": "把交付物收得完整可用。", "whyItMatters": "交付收束质量决定客户体验。", "systemHowText": "系统会识别项目验收和闭环的记录。", "hintTemplate": "把当前交付物整理完整，确认可以交出去。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "project.acceptance_closed", "targetCount": 2}},
        {"id": "version_iterator", "code": "delivery_product.version_iterator", "name": "版本迭代者", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 22, "iconMotif": "version_up", "description": "能在已有基础上持续升级。", "whyItMatters": "持续迭代比从零开始更高效。", "systemHowText": "系统会识别经验卡片的更新和迭代记录。", "hintTemplate": "更新一份已有的方案或产出到新版本。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.experience_published", "targetCount": 8}},
        {"id": "standard_part_builder", "code": "delivery_product.standard_part_builder", "name": "标准件建造者", "categoryId": "delivery_product", "categoryLabel": "交付与产品化系", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员"], "xp": 25, "iconMotif": "part_slot", "description": "能把共性问题做成标准件。", "whyItMatters": "标准件是组织能力的模块化基础。", "systemHowText": "系统会识别标准化产出的发布和复用记录。", "hintTemplate": "把一个共性问题的解法做成标准件。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "SOP发布", "eventType": "knowledge.sop_published", "targetCount": 3, "hint": "先发布 3 条标准流程。"}, {"label": "被复用", "eventType": "knowledge.reused", "targetCount": 5, "hint": "让标准件真正被复用。"}]}},
        # ── 协作与管理系 (81-90) ──────────────────────────────────────────
        {"id": "collab_responder", "code": "team_management.collab_responder", "name": "协作响应者", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 12, "iconMotif": "reply_bubble", "description": "能及时回应别人的协作请求。", "whyItMatters": "快速响应降低协作摩擦。", "systemHowText": "系统会识别任务接收后的响应速度。", "hintTemplate": "收到协作请求后24小时内回应。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 30, "eventType": "task.quick_response", "targetCount": 10}},
        {"id": "support_router", "code": "team_management.support_router", "name": "支持请求分流员", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "split_arrows", "description": "能判断该向谁求助。", "whyItMatters": "找对人就是最大的效率杠杆。", "systemHowText": "系统会识别任务指派和分流的记录。", "hintTemplate": "遇到问题时找到最合适的人寻求帮助。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.assigned", "targetCount": 5}},
        {"id": "task_dispatcher", "code": "team_management.task_dispatcher", "name": "任务分配师", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "组长"], "xp": 18, "iconMotif": "card_to_people", "description": "能把事情交给更合适的人。", "whyItMatters": "合适的人做合适的事让效率翻倍。", "systemHowText": "系统会识别任务分配和指派的记录。", "hintTemplate": "把手头的任务分配给最合适的责任人。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.assigned", "targetCount": 10}},
        {"id": "role_coordinator", "code": "team_management.role_coordinator", "name": "角色协调官", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "组长"], "xp": 20, "iconMotif": "gears_people", "description": "能把角色之间的关系理顺。", "whyItMatters": "角色清晰让协作不打架。", "systemHowText": "系统会识别跨角色协作会议和任务分工的记录。", "hintTemplate": "在下次协作中明确每个人的角色和职责。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.cross_function", "targetCount": 3}},
        {"id": "overload_warner", "code": "team_management.overload_warner", "name": "过载预警者", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "组长"], "xp": 18, "iconMotif": "gauge_red", "description": "能看出谁已经太满。", "whyItMatters": "预警过载是管理者的基本职责。", "systemHowText": "系统会识别团队任务负载的均衡度。", "hintTemplate": "检查团队成员的任务量，预警可能过载的情况。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "project.risk_flagged", "targetCount": 3}},
        {"id": "approval_smoother", "code": "team_management.approval_smoother", "name": "审批减摩者", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "stamp_smooth", "description": "能减少审批和确认的摩擦。", "whyItMatters": "审批顺滑让组织速度更快。", "systemHowText": "系统会识别流程优化和审批简化的记录。", "hintTemplate": "优化一个审批流程，减少不必要的确认环节。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "improvement.proposal_submitted", "targetCount": 2}},
        {"id": "dept_bridge", "code": "team_management.dept_bridge", "name": "部门桥梁", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 22, "iconMotif": "bridge_depts", "description": "能把两个部门搭起来。", "whyItMatters": "跨部门桥梁是组织效率的关键通道。", "systemHowText": "系统会识别跨部门会议和协作的记录。", "hintTemplate": "促成一次跨部门的协作或对齐会议。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 120, "eventType": "meeting.cross_function", "targetCount": 5}},
        {"id": "feedback_coach", "code": "team_management.feedback_coach", "name": "反馈教练", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "资深员工"], "xp": 22, "iconMotif": "card_up_arrow", "description": "能给出让人用得上的反馈。", "whyItMatters": "有效反馈是团队成长的催化剂。", "systemHowText": "系统会识别复盘中是否有给同事的反馈和建议。", "hintTemplate": "在下次复盘中给一位同事写一条可操作的反馈。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "one_on_one_observer", "code": "team_management.one_on_one_observer", "name": "一对一观察者", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理"], "xp": 22, "iconMotif": "chairs_lamp", "description": "能通过一对一发现问题和成长点。", "whyItMatters": "一对一是最深度的管理工具。", "systemHowText": "系统会识别一对一会议和跟进记录。", "hintTemplate": "安排一次一对一谈话，发现团队成员的成长点。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 90, "eventType": "meeting.published", "targetCount": 3}},
        {"id": "squad_navigator", "code": "team_management.squad_navigator", "name": "小队领航员", "categoryId": "team_management", "categoryLabel": "协作与管理系", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["管理", "组长"], "xp": 28, "iconMotif": "flag_people", "description": "能带着一个小队稳步往前。", "whyItMatters": "小队领航是管理力的基础证明。", "systemHowText": "系统会识别团队任务完成率和协作闭环的稳定性。", "hintTemplate": "带领小队连续四周保持稳定的推进节奏。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 4, "windowDays": 60, "eventType": "review.submitted"}},
        # ── AI与数字化共创系 (91-100) ──────────────────────────────────────────
        {"id": "prompt_bridger", "code": "ai_digital.prompt_bridger", "name": "Prompt架桥者", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 12, "iconMotif": "bridge_bubble_gear", "description": "会把需求翻成 AI 听得懂的话。", "whyItMatters": "好的 Prompt 是 AI 协作效率的倍增器。", "systemHowText": "系统会识别 AI 功能的使用频率。", "hintTemplate": "尝试用 AI 辅助完成一项工作。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "ai.prompt_used", "targetCount": 5}},
        {"id": "ai_copilot_tester", "code": "ai_digital.copilot_tester", "name": "AI陪做试验员", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "hand_light_path", "description": "敢把 AI 拉进真实工作试跑。", "whyItMatters": "真实场景试跑是 AI 落地的起点。", "systemHowText": "系统会识别 AI 辅助功能的实际调用记录。", "hintTemplate": "在一个真实任务中使用 AI 辅助并记录效果。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 90, "eventType": "ai.assist_used", "targetCount": 10}},
        {"id": "automation_assembler", "code": "ai_digital.automation_assembler", "name": "自动化拼装师", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "modules_chain", "description": "能把几个步骤串成自动链。", "whyItMatters": "自动化让重复劳动消失。", "systemHowText": "系统会识别模板任务或批量操作的使用记录。", "hintTemplate": "用任务模板或自动化串联一个多步骤流程。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "task.template_used", "targetCount": 3}},
        {"id": "data_backfiller", "code": "ai_digital.data_backfiller", "name": "数据回填者", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "arrow_db_return", "description": "会把结果写回系统形成闭环。", "whyItMatters": "回填数据让系统记忆持续增长。", "systemHowText": "系统会识别任务完成后是否有结果回填记录。", "hintTemplate": "完成任务后把结果和关键数据回填到系统。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "task.status_updated", "targetCount": 15}},
        {"id": "human_ai_proofer", "code": "ai_digital.human_ai_proofer", "name": "人机协作校对官", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "pen_screen_correct", "description": "能判断 AI 结果哪里要改。", "whyItMatters": "校对能力是 AI 可靠落地的安全网。", "systemHowText": "系统会识别 AI 生成内容被人工修改的记录。", "hintTemplate": "校对一份 AI 生成的内容并标注需要修改的地方。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 120, "eventType": "ai.result_reviewed", "targetCount": 5}},
        {"id": "digital_flow_translator", "code": "ai_digital.digital_flow_translator", "name": "数字流程翻译官", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 20, "iconMotif": "flow_to_ui", "description": "把业务流程翻成系统逻辑。", "whyItMatters": "翻译能力是数字化落地的关键。", "systemHowText": "系统会识别 SOP 和流程文档的数字化记录。", "hintTemplate": "把一个业务流程翻译成系统可执行的步骤。", "actionLinks": [link("去成长手册", "growth_handbook"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 365, "eventType": "knowledge.sop_published", "targetCount": 2}},
        {"id": "knowledge_feeder", "code": "ai_digital.knowledge_feeder", "name": "知识库喂养者", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 18, "iconMotif": "doc_shelf_light", "description": "持续给系统喂真实资料。", "whyItMatters": "喂养质量决定系统智能水平。", "systemHowText": "系统会识别附件上传和知识条目的持续贡献。", "hintTemplate": "上传一份有价值的工作资料到系统。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 90, "eventType": "task.attachment_uploaded", "targetCount": 10}},
        {"id": "corpus_gardener", "code": "ai_digital.corpus_gardener", "name": "语料园丁", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 20, "iconMotif": "scissors_vine", "description": "会修剪、整理和维护语料。", "whyItMatters": "语料质量决定 AI 输出质量。", "systemHowText": "系统会识别知识库条目的维护和更新频率。", "hintTemplate": "清理和更新知识库中过时的内容。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "knowledge.experience_published", "targetCount": 10}},
        {"id": "local_co_creator", "code": "ai_digital.local_co_creator", "name": "本地化共创者", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 22, "iconMotif": "wrench_module", "description": "会按团队实际场景改工具。", "whyItMatters": "本地化是工具真正落地的关键。", "systemHowText": "系统会识别改进提案和本地化适配的记录。", "hintTemplate": "提出一条让工具更适合团队实际场景的改进建议。", "actionLinks": [link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 365, "eventType": "improvement.proposal_submitted", "targetCount": 3}},
        {"id": "interface_future_designer", "code": "ai_digital.interface_future_designer", "name": "界面未来设计师", "categoryId": "ai_digital", "categoryLabel": "AI与数字化共创系", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 25, "iconMotif": "window_path_stars", "description": "能把工具做成人人敢用的入口。", "whyItMatters": "好的界面让工具触达每一个人。", "systemHowText": "系统会识别改进提案被采纳并落地的记录。", "hintTemplate": "提出一条改善系统使用体验的建议并推动落地。", "actionLinks": [link("去话题情报", "topics_management"), link("去任务与日程", "tasks")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "建议提出", "eventType": "improvement.proposal_submitted", "targetCount": 3, "hint": "先提出 3 条改进建议。"}, {"label": "被采纳", "eventType": "improvement.proposal_adopted", "targetCount": 1, "hint": "至少推动 1 条建议落地。"}]}},
    ]


def _fetch_unlock_map(db: Database, user_id: str) -> dict[str, dict[str, Any]]:
    rows = db.fetchall("SELECT * FROM badge_unlock_records WHERE user_id = ?", (user_id,))
    return {str(row["badge_id"]): dict(row) for row in rows}


def _build_badge_progress(definition: dict[str, Any], events: list[WorkEvent], unlock_map: dict[str, dict[str, Any]]) -> BadgeProgressRecord:
    rule = dict(definition["rule"])
    rule["badgeName"] = definition["name"]
    rule["hintTemplate"] = definition["hintTemplate"]
    progress_value, progress_target, progress_percent, progress_text, evidences, next_action = _evaluate_rule(rule, events)
    unlocked_row = unlock_map.get(definition["id"])
    raw_ratio = (progress_value / progress_target) if progress_target else 0.0
    mastery_level = 1 if unlocked_row and raw_ratio >= 1.5 else 0
    state: BadgeState
    if unlocked_row:
        state = "mastered" if mastery_level > 0 else "lit"
    elif progress_percent <= 0:
        state = "locked"
    elif progress_percent >= 85:
        state = "ready"
    else:
        state = "progress"
    if unlocked_row:
        next_action = f"你已经连续做到这件事，系统已自动点亮【{definition['name']}】"
    linked_contexts = _linked_contexts_from_evidences(evidences)
    missing_signals = _missing_signals_for_badge(rule, evidences, progress_value, progress_target)
    return BadgeProgressRecord(
        id=str(definition["id"]),
        code=str(definition["code"]),
        name=str(definition["name"]),
        categoryId=str(definition["categoryId"]),
        categoryLabel=str(definition["categoryLabel"]),
        abilityKey=str(definition["abilityKey"]),  # type: ignore[arg-type]
        abilityLabel=str(definition["abilityLabel"]),
        roles=list(definition.get("roles") or []),
        xp=int(definition["xp"]),
        iconMotif=str(definition["iconMotif"]),
        description=str(definition["description"]),
        whyItMatters=str(definition["whyItMatters"]),
        systemHowText=str(definition["systemHowText"]),
        state=state,
        progressValue=progress_value,
        progressTarget=progress_target,
        progressPercent=progress_percent,
        progressText=progress_text,
        nextActionText=next_action,
        actionLinks=[BadgeActionLinkRecord(**item) for item in definition.get("actionLinks") or []],
        evidence=evidences,
        linkedContexts=linked_contexts,
        missingSignals=missing_signals,
        unlockedAt=str(unlocked_row["unlocked_at"]) if unlocked_row else None,
        masteryLevel=mastery_level,
        historical=bool(int(unlocked_row["historical"])) if unlocked_row and unlocked_row.get("historical") is not None else False,
    )


def _award_badge_xp(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    badge: BadgeProgressRecord,
    unlocked_at: str,
) -> None:
    dedupe_key = f"badge_unlock:{user_id}:{badge.id}"
    existing = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing:
        return
    signal_id = _new_id("gse")
    evidence_id = _new_id("gev")
    created_at = unlocked_at or _now_iso()
    reason = f"已自动点亮成长勋章【{badge.name}】"
    db.execute(
        """
        INSERT INTO growth_signal_events(
            id, user_id, user_name, source_type, source_id, review_id, task_id, week_label, raw_text, context_json, dedupe_key, created_at
        ) VALUES(?, ?, ?, 'badge_unlock', ?, NULL, NULL, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            user_id,
            user_name,
            badge.id,
            _week_label(created_at),
            reason,
            to_json({"badgeId": badge.id, "badgeName": badge.name, "categoryId": badge.categoryId}),
            dedupe_key,
            created_at,
        ),
    )
    db.execute(
        """
        INSERT INTO growth_evidence_records(
            id, signal_id, user_id, user_name, ability_key, evidence_type, level, confidence, reason, review_id, task_id, handbook_entry_id, metadata_json, contribution_tags_json, org_contribution_score, suggested_premium_rate, validation_state, ai_reason, ai_confidence, created_at
        ) VALUES(?, ?, ?, ?, ?, 'improvement', 'l3', 'high', ?, NULL, NULL, NULL, ?, '[]', 0, 0, 'validated', ?, 0, ?)
        """,
        (
            evidence_id,
            signal_id,
            user_id,
            user_name,
            badge.abilityKey,
            reason,
            to_json({"sourceTitle": badge.name}),
            reason,
            created_at,
        ),
    )
    db.execute(
        """
        INSERT INTO xp_ledger(
            id, user_id, user_name, ability_key, evidence_id, xp_type, delta, base_xp, premium_rate, premium_xp, total_xp, contribution_tags_json, validation_state, org_contribution_score, dedupe_key, week_label, created_at, reversed_at
        ) VALUES(?, ?, ?, ?, ?, 'improvement', ?, ?, 0, 0, ?, '[]', 'validated', 0, ?, ?, ?, NULL)
        """,
        (
            _new_id("xp"),
            user_id,
            user_name,
            badge.abilityKey,
            evidence_id,
            badge.xp,
            badge.xp,
            badge.xp,
            dedupe_key,
            _week_label(created_at),
            created_at,
        ),
    )


def _sync_badge_unlocks(db: Database, *, user_id: str, user_name: str, badges: list[BadgeProgressRecord]) -> None:
    unlock_map = _fetch_unlock_map(db, user_id)
    now_value = _now_iso()
    for badge in badges:
        if badge.id in unlock_map:
            continue
        if badge.progressTarget <= 0 or badge.progressValue < badge.progressTarget:
            continue
        unlocked_at = badge.evidence[0].occurredAt if badge.evidence else now_value
        historical = 1 if _parse_dt(unlocked_at) <= datetime.now() - timedelta(days=30) else 0
        db.execute(
            """
            INSERT INTO badge_unlock_records(
                id, user_id, user_name, badge_id, badge_code, badge_name, category_id, ability_key, xp, evidence_ids_json, unlocked_at, historical, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("bud"),
                user_id,
                user_name,
                badge.id,
                badge.code,
                badge.name,
                badge.categoryId,
                badge.abilityKey,
                badge.xp,
                to_json([item.id for item in badge.evidence]),
                unlocked_at,
                historical,
                now_value,
            ),
        )
        _award_badge_xp(db, user_id=user_id, user_name=user_name, badge=badge, unlocked_at=unlocked_at)


def build_badge_board(db: Database, *, user_id: str, user_name: str, auto_sync: bool = True) -> BadgeBoardResponse:
    events = _collect_work_events(db, user_name=user_name)
    unlock_map = _fetch_unlock_map(db, user_id)
    badges = [_build_badge_progress(definition, events, unlock_map) for definition in _badge_definitions()]
    if auto_sync:
        _sync_badge_unlocks(db, user_id=user_id, user_name=user_name, badges=badges)
        unlock_map = _fetch_unlock_map(db, user_id)
        badges = [_build_badge_progress(definition, events, unlock_map) for definition in _badge_definitions()]

    categories: list[BadgeCategoryRecord] = []
    for category in CATEGORY_DEFINITIONS:
        category_badges = [badge for badge in badges if badge.categoryId == category["id"]]
        categories.append(
            BadgeCategoryRecord(
                id=str(category["id"]),
                label=str(category["label"]),
                abilityKey=str(category["abilityKey"]),  # type: ignore[arg-type]
                abilityLabel=str(category["abilityLabel"]),
                litCount=sum(1 for badge in category_badges if badge.state in {"lit", "mastered"}),
                totalCount=len(category_badges),
                badges=category_badges,
            )
        )

    lit_badges = [badge for badge in badges if badge.state in {"lit", "mastered"}]
    ready_badges = [badge for badge in badges if badge.state == "ready"]
    in_progress_badges = [badge for badge in badges if badge.state in {"progress", "ready"}]
    monthly_new = sum(1 for badge in lit_badges if badge.unlockedAt and _parse_dt(badge.unlockedAt) >= datetime.now() - timedelta(days=30))
    upcoming = sorted(
        [badge for badge in badges if badge.state in {"progress", "ready"}],
        key=lambda item: (-item.progressPercent, item.name),
    )[:3]

    return BadgeBoardResponse(
        overview=BadgeBoardOverviewRecord(
            totalBadges=len(badges),
            litBadges=len(lit_badges),
            readyBadges=len(ready_badges),
            inProgressBadges=len(in_progress_badges),
            monthlyNewBadges=monthly_new,
            totalXp=sum(badge.xp for badge in lit_badges),
            upcomingBadgeIds=[badge.id for badge in upcoming],
        ),
        categories=categories,
        updatedAt=_now_iso(),
    )
