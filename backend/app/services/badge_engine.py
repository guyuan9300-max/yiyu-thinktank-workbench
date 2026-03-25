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
    {"id": "collab", "label": "协同沟通", "abilityKey": "collab", "abilityLabel": "沟通协作"},
    {"id": "customer", "label": "客户经营", "abilityKey": "insight", "abilityLabel": "客户导向"},
    {"id": "delivery", "label": "项目交付", "abilityKey": "exec", "abilityLabel": "执行推进"},
    {"id": "operations", "label": "运营管理", "abilityKey": "write", "abilityLabel": "组织管理"},
    {"id": "finance", "label": "财务风控", "abilityKey": "risk", "abilityLabel": "经营意识"},
    {"id": "learning", "label": "学习成长", "abilityKey": "analyze", "abilityLabel": "学习沉淀"},
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
    if value.startswith(("crm.", "approval.", "expense.", "finance.")):
        return True
    return value in {
        "project.kickoff_clear",
        "task.breakdown_completed",
        "crm.followup_completed",
        "crm.opportunity_stage",
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
            (SELECT COUNT(*) FROM tasks t WHERE t.source_type = 'meeting' AND t.source_id = m.id) AS linked_task_count,
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

    task_rows = db.fetchall("SELECT * FROM tasks ORDER BY updated_at DESC")
    for row in task_rows:
        title = str(row["title"] or "任务")
        occurred_at = str(row["updated_at"] or row["created_at"])
        ddl = str(row["ddl"] or "")
        status = str(row["status"] or "")
        payload = {
            "status": status,
            "hasDeadline": bool(ddl),
            "sourceType": str(row["source_type"] or ""),
            "summary": "任务推进",
        }
        if ddl:
            events.append(WorkEvent(f"task_deadline_{row['id']}", "task", "task.with_deadline", "task", str(row["id"]), occurred_at, title, payload))
        if ddl and status == "done" and _parse_dt(occurred_at) <= _parse_dt(ddl):
            events.append(WorkEvent(f"task_done_on_time_{row['id']}", "task", "task.done_on_time", "task", str(row["id"]), occurred_at, title, payload))
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

    candidate_rows = db.fetchall("SELECT * FROM topic_candidates ORDER BY updated_at DESC")
    for row in candidate_rows:
        title = str(row["title"] or "情报候选")
        occurred_at = str(row["updated_at"] or row["created_at"])
        status = str(row["status"] or "")
        payload = {"status": status, "summary": "情报候选"}
        events.append(WorkEvent(f"topic_candidate_{row['id']}", "topic", "improvement.proposal_submitted", "topic_candidate", str(row["id"]), occurred_at, title, payload))

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
        {"id": "closed_loop_meeting", "code": "collab.closed_loop_meeting", "name": "闭环会议", "categoryId": "collab", "categoryLabel": "协同沟通", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 20, "iconMotif": "meeting_ring", "description": "把会议结论落实到责任人与任务上，而不是只停留在纪要。", "whyItMatters": "闭环会议能显著减少会后失焦、返工和扯皮。", "systemHowText": "系统会识别最近30天内已发布的会议，是否同时具备结论、责任人、截止日与关联任务。", "hintTemplate": "完成一场带结论、责任人、截止日，并关联任务的会议。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 30, "eventType": "meeting.closed_loop", "targetCount": 3}},
        {"id": "conclusion_first", "code": "collab.conclusion_first", "name": "结论先行", "categoryId": "collab", "categoryLabel": "协同沟通", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员", "管理"], "xp": 15, "iconMotif": "report_arrow", "description": "汇报先给结论，再给依据和下一步。", "whyItMatters": "先结论能提升沟通效率，也让管理者更容易判断。", "systemHowText": "系统会识别周复盘条目里是否同时出现结论性总结和下一步动作。", "hintTemplate": "下一次汇报先写结论，再补依据和下一步。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 90, "eventType": "review.structured_entry", "targetCount": 5}},
        {"id": "quick_response", "code": "collab.quick_response", "name": "快速响应", "categoryId": "collab", "categoryLabel": "协同沟通", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 10, "iconMotif": "chat_bolt", "description": "收到事项后快速接收并同步状态，让协作方知道事情在推进。", "whyItMatters": "快速响应能降低沟通焦虑和等待成本。", "systemHowText": "系统会识别任务创建后24小时内是否出现确认动作。", "hintTemplate": "收到任务后24小时内先接收，并更新状态。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 14, "eventType": "task.quick_response", "targetCount": 15}},
        {"id": "same_page_collab", "code": "collab.same_page", "name": "同频协作", "categoryId": "collab", "categoryLabel": "协同沟通", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员", "管理"], "xp": 25, "iconMotif": "linked_rings", "description": "把跨角色协作拉进同一条推进链路，并形成共识。", "whyItMatters": "同频协作能让跨职能任务真正往前推，而不是各做各的。", "systemHowText": "系统会识别最近60天是否有跨协作会议或多人行动项的闭环事件。", "hintTemplate": "把协作事项拉进同一任务流，完成一次跨部门确认。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 60, "eventType": "meeting.cross_function", "targetCount": 2}},
        {"id": "clear_handoff", "code": "collab.clear_handoff", "name": "清晰交接", "categoryId": "collab", "categoryLabel": "协同沟通", "abilityKey": "collab", "abilityLabel": "沟通协作", "roles": ["全员"], "xp": 15, "iconMotif": "handoff", "description": "交接时把背景、现状、风险和下一步说清楚。", "whyItMatters": "好的交接能显著减少接手成本和遗漏。", "systemHowText": "系统会识别复盘或任务说明里是否同时出现背景、风险与下一步交接要点。", "hintTemplate": "交接前补齐背景、现状、风险和下一步。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "task.clear_handoff", "targetCount": 3}},
        {"id": "lead_fast_response", "code": "customer.lead_fast", "name": "线索快反", "categoryId": "customer", "categoryLabel": "客户经营", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["销售", "客服"], "xp": 15, "iconMotif": "radar_ping", "description": "拿到新线索后迅速完成首轮触达。", "whyItMatters": "客户侧响应速度通常会直接影响转化窗口。", "systemHowText": "系统会识别线索创建与首次跟进之间的时间差。", "hintTemplate": "拿到新线索后，当天完成第一次联系并记录结果。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 30, "eventType": "crm.lead_followed", "targetCount": 10}},
        {"id": "requirement_clarity", "code": "customer.requirement_clarity", "name": "需求澄清", "categoryId": "customer", "categoryLabel": "客户经营", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["销售", "产品", "项目"], "xp": 20, "iconMotif": "search_chat", "description": "先把目标、范围和边界问清楚，再进入方案。", "whyItMatters": "需求不清是返工和误判的常见根源。", "systemHowText": "系统会识别会议中是否出现待澄清问题并完成消解。", "hintTemplate": "先把目标、范围、优先级和时间补完整，再提交需求单。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 120, "eventType": "client.requirement_clarified", "targetCount": 5}},
        {"id": "proposal_formed", "code": "customer.proposal_formed", "name": "方案成形", "categoryId": "customer", "categoryLabel": "客户经营", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["销售", "顾问"], "xp": 25, "iconMotif": "stack_docs", "description": "把客户问题推进成结构化方案，而不是停留在想法。", "whyItMatters": "方案能力是把需求转成推进杠杆的关键一步。", "systemHowText": "系统会识别带方案语义的分析或提案产出。", "hintTemplate": "输出一份方案或报价，并推进到下一步。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去话题情报", "topics_management")], "rule": {"type": "count", "windowDays": 180, "eventType": "analysis.proposal_advanced", "targetCount": 3}},
        {"id": "steady_followup", "code": "customer.steady_followup", "name": "持续跟进", "categoryId": "customer", "categoryLabel": "客户经营", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["销售", "客户成功"], "xp": 20, "iconMotif": "path_nodes", "description": "按节奏推动客户跟进，不让事项无声中断。", "whyItMatters": "持续跟进比单次高热情更能建立客户信任。", "systemHowText": "系统会识别客户跟进计划和实际触达记录。", "hintTemplate": "按计划完成下一次客户跟进，不要让跟进超期。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 30, "eventType": "crm.followup_completed", "targetCount": 8}},
        {"id": "deal_push", "code": "customer.deal_push", "name": "成交推进", "categoryId": "customer", "categoryLabel": "客户经营", "abilityKey": "insight", "abilityLabel": "客户导向", "roles": ["销售", "负责人"], "xp": 30, "iconMotif": "handshake_seal", "description": "把商机从讨论推进到确认和成交节点。", "whyItMatters": "真正的客户经营，不是聊过，而是推进过关键节点。", "systemHowText": "系统会识别商机阶段从已报价推进到签约或成交。", "hintTemplate": "把当前商机继续推进到合同或成交节点。", "actionLinks": [link("去统一工作台", "unified_workbench")], "rule": {"type": "sequence", "windowDays": 365, "eventType": "crm.opportunity_stage", "completedStage": "signed"}},
        {"id": "project_kickoff_clear", "code": "delivery.kickoff_clear", "name": "立项清晰", "categoryId": "delivery", "categoryLabel": "项目交付", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["项目", "管理"], "xp": 20, "iconMotif": "blueprint_flag", "description": "从一开始就把目标、范围、角色和风险立住。", "whyItMatters": "立项质量决定后面大部分返工概率。", "systemHowText": "系统会识别项目立项单是否完整并审批通过。", "hintTemplate": "立项时先补齐目标、范围、角色、里程碑和风险。", "actionLinks": [link("去任务与日程", "tasks"), link("去设置", "settings")], "rule": {"type": "count", "windowDays": 365, "eventType": "project.kickoff_clear", "targetCount": 2}},
        {"id": "task_breakdown", "code": "delivery.task_breakdown", "name": "拆解到位", "categoryId": "delivery", "categoryLabel": "项目交付", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["项目", "组长"], "xp": 15, "iconMotif": "grid_blocks", "description": "把模糊大事拆成能落地的小动作。", "whyItMatters": "好的拆解，是推进能力最直接的表现。", "systemHowText": "系统会识别父任务和可执行子项之间的结构关系。", "hintTemplate": "把大任务拆成可执行小任务，再分责任人。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 180, "eventType": "task.breakdown_completed", "targetCount": 10}},
        {"id": "milestone_on_time", "code": "delivery.milestone_on_time", "name": "里程守时", "categoryId": "delivery", "categoryLabel": "项目交付", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["项目", "交付"], "xp": 25, "iconMotif": "summit_flag", "description": "关键节点能按承诺时间落地。", "whyItMatters": "稳定交付比偶发爆发更能建立组织信任。", "systemHowText": "系统会识别有截止日的任务中，已按时完成的比例是否达到阈值。", "hintTemplate": "更新里程碑状态，确保关键节点按时落地。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "ratio", "windowDays": 60, "numeratorEventType": "task.done_on_time", "denominatorEventType": "task.with_deadline", "minRatio": 0.9, "minBaseCount": 3}},
        {"id": "risk_scout", "code": "delivery.risk_scout", "name": "风险前哨", "categoryId": "delivery", "categoryLabel": "项目交付", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["项目", "交付"], "xp": 20, "iconMotif": "shield_ping", "description": "提前把会卡住的地方说出来，并给出处理方案。", "whyItMatters": "风险前移，能把救火变成预防。", "systemHowText": "系统会识别会议和复盘里提到的阻碍、风险与应对方案。", "hintTemplate": "一旦发现会延期或有障碍，先标风险，再写解决方案。", "actionLinks": [link("去任务与日程", "tasks"), link("去统一工作台", "unified_workbench")], "rule": {"type": "count", "windowDays": 60, "eventType": "project.risk_flagged", "targetCount": 3}},
        {"id": "acceptance_closed", "code": "delivery.acceptance_closed", "name": "验收闭环", "categoryId": "delivery", "categoryLabel": "项目交付", "abilityKey": "exec", "abilityLabel": "执行推进", "roles": ["实施", "QA"], "xp": 30, "iconMotif": "seal_box", "description": "验收不仅有结果，还有问题清单、责任人与复测结论。", "whyItMatters": "验收闭环决定交付质量是否真正落地。", "systemHowText": "系统会识别复盘中是否同时出现验收结果、问题、责任人和复测结论。", "hintTemplate": "验收后别只写结果，把问题、责任人和复测都补齐。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "project.acceptance_closed", "targetCount": 3}},
        {"id": "weekly_report_stable", "code": "operations.weekly_report", "name": "周报稳定", "categoryId": "operations", "categoryLabel": "运营管理", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员", "管理"], "xp": 10, "iconMotif": "calendar_lines", "description": "连续按时输出有结构的周报，而不是想起来才补。", "whyItMatters": "稳定周报是组织节奏感的基础设施。", "systemHowText": "系统会识别周报是否连续按周提交。", "hintTemplate": "按时提交周报，并把问题和下周重点写清楚。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 4, "windowDays": 120, "eventType": "review.submitted"}},
        {"id": "dashboard_refresh", "code": "operations.dashboard_refresh", "name": "看板更新", "categoryId": "operations", "categoryLabel": "运营管理", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["运营", "管理"], "xp": 20, "iconMotif": "dashboard_gauge", "description": "让团队关键指标保持持续更新，而不是偶尔补录。", "whyItMatters": "没有稳定数据节奏，管理动作就会失焦。", "systemHowText": "系统会识别分析或看板更新是否按周持续发生。", "hintTemplate": "把本周关键数据补到看板里，并保持连续更新。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去话题情报", "topics_management")], "rule": {"type": "consecutive", "unit": "week", "targetStreak": 4, "windowDays": 120, "eventType": "analysis.dashboard_updated"}},
        {"id": "sop_deposit", "code": "operations.sop_deposit", "name": "SOP沉淀", "categoryId": "operations", "categoryLabel": "运营管理", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["运营", "资深员工"], "xp": 25, "iconMotif": "manual_stack", "description": "把会用的做法写成别人也能跟着做的步骤。", "whyItMatters": "SOP 是组织可复制性的底层资产。", "systemHowText": "系统会识别方法型成长手册条目，以及它们后续是否被复用。", "hintTemplate": "把做法写成步骤化SOP，发到知识库。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "SOP发布", "eventType": "knowledge.sop_published", "targetCount": 3, "hint": "先沉淀 3 条可复用 SOP。"}, {"label": "被复用", "eventType": "knowledge.reused", "targetCount": 5, "hint": "让已经写出的 SOP 真正被后续任务复用。"}]}},
        {"id": "approval_clean", "code": "operations.approval_clean", "name": "审批规范", "categoryId": "operations", "categoryLabel": "运营管理", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员", "管理"], "xp": 15, "iconMotif": "stamp_flow", "description": "一次提交就把必要信息补齐，减少来回追问。", "whyItMatters": "规范审批减少流程摩擦，也节省支持团队时间。", "systemHowText": "系统会识别审批单的必填字段完整度和一次通过率。", "hintTemplate": "提交申请前补齐金额、用途、附件和说明。", "actionLinks": [link("去设置", "settings")], "rule": {"type": "ratio", "windowDays": 90, "numeratorEventType": "approval.request_clean", "denominatorEventType": "approval.request_submitted", "minRatio": 0.9, "minBaseCount": 20}},
        {"id": "retrospective_output", "code": "operations.retrospective_output", "name": "复盘输出", "categoryId": "operations", "categoryLabel": "运营管理", "abilityKey": "write", "abilityLabel": "组织管理", "roles": ["全员", "管理"], "xp": 20, "iconMotif": "loop_note", "description": "一件事做完后，能把结果、原因和改进讲透。", "whyItMatters": "复盘质量决定经验是否能真正积累下来。", "systemHowText": "系统会识别复盘中是否同时出现结果、原因和改进动作。", "hintTemplate": "一次事情做完后，写一份有原因和改进的复盘。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 180, "eventType": "review.retrospective_completed", "targetCount": 2}},
        {"id": "expense_clean", "code": "finance.expense_clean", "name": "报销规范", "categoryId": "finance", "categoryLabel": "财务风控", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["全员"], "xp": 10, "iconMotif": "invoice_shield", "description": "提交前把票据、科目和用途补齐，减少退回。", "whyItMatters": "基础流程的规范性，本质上是组织效率和风险控制。", "systemHowText": "系统会识别报销单提交和退回记录。", "hintTemplate": "上传票据、选对科目、写清用途后再提交。", "actionLinks": [link("去设置", "settings")], "rule": {"type": "count", "windowDays": 180, "eventType": "expense.clean_submitted", "targetCount": 5}},
        {"id": "budget_guard", "code": "finance.budget_guard", "name": "预算守门", "categoryId": "finance", "categoryLabel": "财务风控", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["管理", "财务"], "xp": 25, "iconMotif": "wallet_gate", "description": "预算不只是记账，而是对经营节奏负责。", "whyItMatters": "预算意识强，组织决策才更稳。", "systemHowText": "系统会识别预算执行偏差率及月度说明。", "hintTemplate": "月底前更新预算执行和偏差说明。", "actionLinks": [link("去设置", "settings")], "rule": {"type": "ratio", "windowDays": 45, "numeratorEventType": "finance.budget_on_track", "denominatorEventType": "finance.budget_reported", "minRatio": 0.9, "minBaseCount": 1}},
        {"id": "contract_compliance", "code": "finance.contract_compliance", "name": "合同合规", "categoryId": "finance", "categoryLabel": "财务风控", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["销售", "法务", "管理"], "xp": 20, "iconMotif": "scroll_seal", "description": "使用标准模板并走完整审批归档。", "whyItMatters": "合同合规是业务放大的安全边界。", "systemHowText": "系统会识别标准合同模板、审批、盖章和归档记录。", "hintTemplate": "用标准合同模板，走完审批和归档。", "actionLinks": [link("去设置", "settings")], "rule": {"type": "count", "windowDays": 365, "eventType": "finance.contract_compliant", "targetCount": 3}},
        {"id": "cash_collection", "code": "finance.cash_collection", "name": "回款推进", "categoryId": "finance", "categoryLabel": "财务风控", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["销售", "财务"], "xp": 30, "iconMotif": "bill_return", "description": "按计划收回该回来的钱，或者把逾期拉回正轨。", "whyItMatters": "回款推进是经营质量最直接的现实反馈。", "systemHowText": "系统会识别回款计划与实际到账节点。", "hintTemplate": "盯一次即将到期或已逾期的回款，并更新结果。", "actionLinks": [link("去设置", "settings")], "rule": {"type": "count", "windowDays": 180, "eventType": "finance.collection_completed", "targetCount": 3}},
        {"id": "procurement_traceable", "code": "finance.procurement_traceable", "name": "采购有据", "categoryId": "finance", "categoryLabel": "财务风控", "abilityKey": "risk", "abilityLabel": "经营意识", "roles": ["行政", "运营", "财务"], "xp": 20, "iconMotif": "cart_checklist", "description": "采购过程能留痕、可回看、可解释。", "whyItMatters": "采购闭环清晰，才能兼顾效率和风控。", "systemHowText": "系统会识别需求、比价、审批、验收和入库链路。", "hintTemplate": "采购前补齐比价和审批，采购后补验收和入库。", "actionLinks": [link("去设置", "settings")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "采购需求", "eventType": "finance.procurement_requested", "targetCount": 3}, {"label": "采购闭环", "eventType": "finance.procurement_closed", "targetCount": 3}]}},
        {"id": "mentor_newcomer", "code": "learning.mentor", "name": "新人带教", "categoryId": "learning", "categoryLabel": "学习成长", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["组长", "资深员工"], "xp": 30, "iconMotif": "mentor_orbit", "description": "带教不是口头提醒，而是把新人真正带上手。", "whyItMatters": "带教能力是团队复制和扩张的关键指标。", "systemHowText": "系统会识别新人学习任务完成率和带教反馈。", "hintTemplate": "带教别只口头说，建任务、跟进并提交反馈。", "actionLinks": [link("去任务与日程", "tasks")], "rule": {"type": "count", "windowDays": 365, "eventType": "learning.mentorship_completed", "targetCount": 1}},
        {"id": "knowledge_share", "code": "learning.knowledge_share", "name": "知识分享", "categoryId": "learning", "categoryLabel": "学习成长", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员", "资深员工"], "xp": 20, "iconMotif": "idea_burst", "description": "把自己学到的东西讲出来，变成团队共有资产。", "whyItMatters": "分享能把个人经验外溢成组织增益。", "systemHowText": "系统会识别分享、培训或分析输出等内部传播行为。", "hintTemplate": "准备一次分享，把内容发布并完成签到。", "actionLinks": [link("去统一工作台", "unified_workbench"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "learning.knowledge_share", "targetCount": 2}},
        {"id": "experience_deposit", "code": "learning.experience_deposit", "name": "经验沉淀", "categoryId": "learning", "categoryLabel": "学习成长", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 25, "iconMotif": "cards_spark", "description": "把一次有效做法写成经验卡片，并真的被再次用起来。", "whyItMatters": "经验沉淀的价值不在写，而在能不能被下一次用。", "systemHowText": "系统会识别成长手册条目数量和后续复用记录。", "hintTemplate": "把一次有效做法沉淀成经验卡片，写清场景和做法。", "actionLinks": [link("去成长手册", "growth_handbook")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "经验卡片", "eventType": "knowledge.experience_published", "targetCount": 5, "hint": "先写出 5 条经验卡片。"}, {"label": "被收藏或复用", "eventType": "knowledge.reused", "targetCount": 10, "hint": "让已经沉淀的经验被后续任务真正复用。"}]}},
        {"id": "learning_path", "code": "learning.path", "name": "学习通关", "categoryId": "learning", "categoryLabel": "学习成长", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员"], "xp": 15, "iconMotif": "path_flag", "description": "把建议练习真正做完，而不是只收藏。", "whyItMatters": "学习真正发生在做完之后，而不是浏览之后。", "systemHowText": "系统会识别成长练习任务是否完成。", "hintTemplate": "把当前学习路径剩余的必修节点做完。", "actionLinks": [link("去任务与日程", "tasks"), link("去成长手册", "growth_handbook")], "rule": {"type": "count", "windowDays": 365, "eventType": "learning.path_completed", "targetCount": 1}},
        {"id": "improvement_proposal", "code": "learning.improvement", "name": "改进提案", "categoryId": "learning", "categoryLabel": "学习成长", "abilityKey": "analyze", "abilityLabel": "学习沉淀", "roles": ["全员", "管理"], "xp": 30, "iconMotif": "wrench_up", "description": "不只是发现问题，还能把改进建议推进到执行。", "whyItMatters": "持续改进能力，会直接决定组织进化速度。", "systemHowText": "系统会识别情报候选、改进建议以及它们是否进入任务执行。", "hintTemplate": "提交一条能落地的改进建议，并推动它进入执行。", "actionLinks": [link("去话题情报", "topics_management"), link("去任务与日程", "tasks")], "rule": {"type": "composite", "windowDays": 365, "conditions": [{"label": "建议提出", "eventType": "improvement.proposal_submitted", "targetCount": 3, "hint": "先形成 3 条可落地建议。"}, {"label": "进入执行", "eventType": "improvement.proposal_adopted", "targetCount": 1, "hint": "至少推动 1 条建议进入任务执行。"}]}},
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
