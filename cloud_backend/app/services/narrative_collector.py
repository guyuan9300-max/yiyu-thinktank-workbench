"""收集 client 相关 facts, 喂给 narrative_generator 拼 prompt.

铁律 (来自 DNA submodule:strategic_clarification_panel.decision):
  "你设计所有区块儿的时候, 必须去想它是真实数据作为支撑的, 不能乱编"
→ collector 只 SELECT 真实数据, 不造假; 拿不到就空着, generator 会标 dataLayerGap.

收集源 (全部来自 cloud db):
  - clients (姓名/别名/类型)
  - cloud_client_workspace_snapshots (含 strategic_profile / cooperation 等)
  - event_lines (主线列表 WHERE primary_client_id = X)
  - event_line_activities (主线流水)
  - tasks (主线相关 task)
  - client_narrative_clarifications (这次的 pending 澄清)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.db import Database


def _safe_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class EventLineFact:
    id: str
    name: str
    kind: str
    status: str
    stage: str
    summary: str
    intent: str
    current_blocker: str
    recent_decision: str
    next_step: str
    evidence_count: int
    owner_id: str | None
    updated_at: str


@dataclass(frozen=True)
class EventLineActivityFact:
    id: str
    event_line_id: str
    event_line_name: str
    source_type: str
    source_id: str
    happened_at: str
    actor_id: str | None
    title: str
    summary: str


@dataclass(frozen=True)
class TaskFact:
    id: str
    title: str
    description: str
    priority: str
    progress_status: str
    deadline_at: str | None
    owner_id: str | None
    next_action: str
    current_blocker: str
    recent_decision: str
    completion_note: str
    updated_at: str


@dataclass(frozen=True)
class ClarificationFact:
    id: str
    dimension: str
    question: str
    answer: str
    answered_by_display_name: str
    answered_at: str


@dataclass(frozen=True)
class ExternalPersonFact:
    """关键人物花名册的一行 — 已结构化, 不再从原始文本里抽。"""

    id: str
    name: str
    role_title: str
    affiliation: str
    relationship_type: str
    one_liner: str
    notes: str


@dataclass(frozen=True)
class ClientContext:
    client_id: str
    client_name: str
    client_alias: str
    client_type: str

    strategic_profile: dict[str, Any] = field(default_factory=dict)
    cooperation_payload: dict[str, Any] = field(default_factory=dict)
    understanding_payload: dict[str, Any] = field(default_factory=dict)

    # 加工层 Phase 1: 结构化的项目档案 (4 字段) + 关键人物花名册
    structured_profile: dict[str, Any] = field(default_factory=dict)
    external_persons: list[ExternalPersonFact] = field(default_factory=list)

    event_lines: list[EventLineFact] = field(default_factory=list)
    activities: list[EventLineActivityFact] = field(default_factory=list)
    tasks: list[TaskFact] = field(default_factory=list)
    pending_clarifications: list[ClarificationFact] = field(default_factory=list)
    applied_clarifications: list[ClarificationFact] = field(default_factory=list)

    def is_thin(self) -> bool:
        """没东西可讲的诚实判断."""
        return (
            not self.event_lines
            and not self.activities
            and not self.tasks
            and not self.strategic_profile
            and not self.structured_profile
            and not self.external_persons
        )


_WORKSPACE_INTERESTING_KEYS = (
    "strategicProfile",
    "strategic_profile",
    "cooperation",
    "cooperationRelationship",
    "cooperation_relationship",
    "knowledgeStatus",
    "keyStakeholders",
)


def _merge_workspace_payload(rows: list[Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """同一个 client 可能有多条 workspace_snapshot (按 source_id 区分), 合并取最新。"""
    profile: dict[str, Any] = {}
    coop: dict[str, Any] = {}
    for row in rows:
        payload = _safe_json(row["payload_json"]) or {}
        if not isinstance(payload, dict):
            continue
        for key in _WORKSPACE_INTERESTING_KEYS:
            val = payload.get(key)
            if not val:
                continue
            if "cooperation" in key.lower():
                if isinstance(val, dict):
                    coop = {**coop, **val}
            else:
                if isinstance(val, dict):
                    profile = {**profile, **val}
    return profile, coop


def collect_client_context(
    db: Database,
    organization_id: str,
    client_id: str,
    *,
    event_line_limit: int = 12,
    activity_limit: int = 30,
    task_limit: int = 20,
    clarification_limit: int = 20,
) -> ClientContext:
    client_row = db.fetchone(
        "SELECT * FROM clients WHERE id = ? AND organization_id = ?",
        (client_id, organization_id),
    )
    if not client_row:
        raise ValueError(f"client not found: {client_id}")

    workspace_rows = db.fetchall(
        """
        SELECT payload_json, updated_at, source_id
        FROM cloud_client_workspace_snapshots
        WHERE organization_id = ? AND client_id = ?
        ORDER BY updated_at DESC
        LIMIT 5
        """,
        (organization_id, client_id),
    )
    profile, coop = _merge_workspace_payload(workspace_rows)

    # 加工层 Phase 1 · 项目档案 (cloud_client_strategic_profiles)
    structured_profile: dict[str, Any] = {}
    try:
        sp_row = db.fetchone(
            """
            SELECT project_type, project_goal, success_metric, current_phase,
                   cooperation_start_date, cooperation_end_date, notes,
                   updated_by_display_name, updated_at
            FROM cloud_client_strategic_profiles
            WHERE organization_id = ? AND client_id = ?
            """,
            (organization_id, client_id),
        )
        if sp_row:
            structured_profile = {
                "project_type": str(sp_row["project_type"] or ""),
                "project_goal": str(sp_row["project_goal"] or ""),
                "success_metric": str(sp_row["success_metric"] or ""),
                "current_phase": str(sp_row["current_phase"] or ""),
                "cooperation_start_date": str(sp_row["cooperation_start_date"] or ""),
                "cooperation_end_date": str(sp_row["cooperation_end_date"] or ""),
                "notes": str(sp_row["notes"] or ""),
                "updated_by": str(sp_row["updated_by_display_name"] or ""),
                "updated_at": str(sp_row["updated_at"] or ""),
            }
            # 全部 4 个核心字段都是空字符串则视为未填
            if not any(
                structured_profile[k]
                for k in ("project_type", "project_goal", "success_metric", "current_phase")
            ):
                structured_profile = {}
    except Exception:
        structured_profile = {}

    # 加工层 Phase 1 · 关键人物花名册 (cloud_external_persons)
    external_persons_list: list[ExternalPersonFact] = []
    try:
        person_rows = db.fetchall(
            """
            SELECT id, name, role_title, affiliation, relationship_type, one_liner, notes
            FROM cloud_external_persons
            WHERE organization_id = ? AND client_id = ?
            ORDER BY sort_order ASC, created_at ASC
            """,
            (organization_id, client_id),
        )
        for r in person_rows:
            external_persons_list.append(
                ExternalPersonFact(
                    id=str(r["id"]),
                    name=str(r["name"] or ""),
                    role_title=str(r["role_title"] or ""),
                    affiliation=str(r["affiliation"] or ""),
                    relationship_type=str(r["relationship_type"] or ""),
                    one_liner=str(r["one_liner"] or ""),
                    notes=str(r["notes"] or ""),
                )
            )
    except Exception:
        external_persons_list = []

    understanding_row = db.fetchone(
        """
        SELECT payload_json
        FROM cloud_client_understanding_snapshots
        WHERE organization_id = ? AND client_id = ?
        ORDER BY updated_at DESC LIMIT 1
        """,
        (organization_id, client_id),
    )
    understanding_payload = (
        _safe_json(understanding_row["payload_json"]) if understanding_row else {}
    ) or {}
    if not isinstance(understanding_payload, dict):
        understanding_payload = {}

    el_rows = db.fetchall(
        """
        SELECT * FROM event_lines
        WHERE organization_id = ? AND primary_client_id = ?
        ORDER BY updated_at DESC LIMIT ?
        """,
        (organization_id, client_id, event_line_limit),
    )
    event_lines = [
        EventLineFact(
            id=str(r["id"]),
            name=str(r["name"] or ""),
            kind=str(r["kind"] or ""),
            status=str(r["status"] or ""),
            stage=str(r["stage"] or ""),
            summary=str(r["summary"] or ""),
            intent=str(r["intent"] or ""),
            current_blocker=str(r["current_blocker"] or ""),
            recent_decision=str(r["recent_decision"] or ""),
            next_step=str(r["next_step"] or ""),
            evidence_count=int(r["evidence_count"] or 0),
            owner_id=str(r["owner_id"]) if r["owner_id"] else None,
            updated_at=str(r["updated_at"] or ""),
        )
        for r in el_rows
    ]

    activities: list[EventLineActivityFact] = []
    if event_lines:
        el_id_list = [e.id for e in event_lines]
        placeholders = ",".join("?" * len(el_id_list))
        el_name_by_id = {e.id: e.name for e in event_lines}
        act_rows = db.fetchall(
            f"""
            SELECT * FROM event_line_activities
            WHERE event_line_id IN ({placeholders})
            ORDER BY happened_at DESC LIMIT ?
            """,
            (*el_id_list, activity_limit),
        )
        activities = [
            EventLineActivityFact(
                id=str(r["id"]),
                event_line_id=str(r["event_line_id"]),
                event_line_name=el_name_by_id.get(str(r["event_line_id"]), ""),
                source_type=str(r["source_type"] or ""),
                source_id=str(r["source_id"] or ""),
                happened_at=str(r["happened_at"] or ""),
                actor_id=str(r["actor_id"]) if r["actor_id"] else None,
                title=str(r["title"] or ""),
                summary=str(r["summary"] or ""),
            )
            for r in act_rows
        ]

    task_rows = db.fetchall(
        """
        SELECT t.* FROM tasks t
        WHERE t.organization_id = ?
          AND (
            EXISTS (SELECT 1 FROM event_lines e
                    WHERE e.primary_client_id = ? AND t.source_id = e.id)
            OR EXISTS (SELECT 1 FROM event_line_activities a
                       WHERE a.source_type = 'task' AND a.source_id = t.id
                       AND a.event_line_id IN (SELECT id FROM event_lines WHERE primary_client_id = ?))
          )
        ORDER BY t.updated_at DESC LIMIT ?
        """,
        (organization_id, client_id, client_id, task_limit),
    )
    tasks = [
        TaskFact(
            id=str(r["id"]),
            title=str(r["title"] or ""),
            description=str(r["description"] or ""),
            priority=str(r["priority"] or ""),
            progress_status=str(r["progress_status"] or ""),
            deadline_at=(str(r["deadline_at"]) if r["deadline_at"] else None),
            owner_id=str(r["owner_id"]) if r["owner_id"] else None,
            next_action=str(r["next_action"] or ""),
            current_blocker=str(r["current_blocker"] or ""),
            recent_decision=str(r["recent_decision"] or ""),
            completion_note=str(r["completion_note"] or ""),
            updated_at=str(r["updated_at"] or ""),
        )
        for r in task_rows
    ]

    clar_rows = db.fetchall(
        """
        SELECT id, dimension, question, answer, answered_by_display_name, answered_at, status
        FROM client_narrative_clarifications
        WHERE organization_id = ? AND client_id = ?
        ORDER BY answered_at DESC LIMIT ?
        """,
        (organization_id, client_id, clarification_limit),
    )
    pending: list[ClarificationFact] = []
    applied: list[ClarificationFact] = []
    for r in clar_rows:
        fact = ClarificationFact(
            id=str(r["id"]),
            dimension=str(r["dimension"]),
            question=str(r["question"] or ""),
            answer=str(r["answer"] or ""),
            answered_by_display_name=str(r["answered_by_display_name"] or ""),
            answered_at=str(r["answered_at"] or ""),
        )
        if str(r["status"]) == "pending":
            pending.append(fact)
        elif str(r["status"]) == "applied":
            applied.append(fact)

    return ClientContext(
        client_id=str(client_row["id"]),
        client_name=str(client_row["name"] or ""),
        client_alias=str(client_row["alias"] or ""),
        client_type=str(client_row["type"] or ""),
        strategic_profile=profile,
        cooperation_payload=coop,
        understanding_payload=understanding_payload,
        structured_profile=structured_profile,
        external_persons=external_persons_list,
        event_lines=event_lines,
        activities=activities,
        tasks=tasks,
        pending_clarifications=pending,
        applied_clarifications=applied,
    )
