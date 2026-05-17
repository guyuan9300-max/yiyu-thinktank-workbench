"""战略陪伴 / 事实澄清面板 · 上下文聚合.

返回一个客户的'澄清面板'所需的全部背景:
  - eventLines: 项目骨架 + 每条主线的基本字段
  - timeline: 事件时间线 (从 event_line_activities 合并)
  - peopleCandidates: 关键人物候选 (从 actor_name + memory_facts 提取, 粗糙版)
  - commitments: 承诺链 (从 action_items)
  - clarificationNeeds: AI 主动列的待澄清项 (从 event_line_memory_snapshots.clarification_needs_json)
  - profile: 客户战略画像 (从 client_strategic_profiles + clients.domain)

设计原则:
- 每个字段都对应真实表/字段, 不编造
- 当前数据不足时返回空数组/字符串, 前端用占位符
- 不调 LLM, 纯 SQL 聚合
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from typing import Any


__all__ = ["compute_clarification_context"]


_TEST_QUOTE_FRAGMENTS = (
    "已进入项目资料层",
    "已作为任务附件进入项目资料库",
    "smoke", "test_", "offline upload", "progress test",
    "测试附件", "这是烟测附件内容",
    "with_client_test", "no_client_test", "prog_test", "final_test",
)


def compute_clarification_context(
    db: sqlite3.Connection,
    client_id: str,
) -> dict[str, Any]:
    """聚合澄清面板所需数据."""

    profile = _load_client_profile(db, client_id)
    event_lines = _load_event_lines(db, client_id)
    eline_ids = [el["id"] for el in event_lines]

    timeline = _load_timeline(db, eline_ids)
    people = _load_people_candidates(db, client_id, eline_ids)
    commitments = _load_commitments(db, client_id)
    clarification_needs = _load_clarification_needs(db, eline_ids)

    return {
        "clientId": client_id,
        "profile": profile,
        "eventLines": event_lines,
        "timeline": timeline,
        "peopleCandidates": people,
        "commitments": commitments,
        "clarificationNeeds": clarification_needs,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _load_client_profile(db: sqlite3.Connection, client_id: str) -> dict[str, Any]:
    """客户基本档案 + 战略画像."""
    client_row = db.execute(
        "SELECT id, name, alias, domain, type, intro, stage, color FROM clients WHERE id = ?",
        (client_id,),
    ).fetchone()
    if client_row is None:
        return {}

    profile_row = db.execute(
        """
        SELECT industry, scale, influence, current_needs, pain_points,
               strategic_value_to_yiyu, decision_chain, updated_at
        FROM client_strategic_profiles
        WHERE client_id = ?
        """,
        (client_id,),
    ).fetchone()

    coop_row = db.execute(
        """
        SELECT cooperation_type, relationship_health, key_stakeholders_json,
               milestones, started_at
        FROM cooperation_relationships
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (client_id,),
    ).fetchone()

    return {
        "name": client_row["name"],
        "alias": client_row["alias"],
        "domain": client_row["domain"],
        "type": client_row["type"],
        "intro": client_row["intro"] or "",
        "stage": client_row["stage"],
        "color": client_row["color"] or "#5B7BFE",
        "industry": (profile_row["industry"] if profile_row else "") or "",
        "scale": (profile_row["scale"] if profile_row else "") or "",
        "influence": (profile_row["influence"] if profile_row else "") or "",
        "currentNeeds": (profile_row["current_needs"] if profile_row else "") or "",
        "painPoints": (profile_row["pain_points"] if profile_row else "") or "",
        "strategicValueToYiyu": (profile_row["strategic_value_to_yiyu"] if profile_row else "") or "",
        "decisionChain": (profile_row["decision_chain"] if profile_row else "") or "",
        "cooperationType": (coop_row["cooperation_type"] if coop_row else "") or "",
        "relationshipHealth": (coop_row["relationship_health"] if coop_row else "") or "",
        "milestones": (coop_row["milestones"] if coop_row else "") or "",
        "cooperationStartedAt": (coop_row["started_at"] if coop_row else "") or "",
    }


def _load_event_lines(db: sqlite3.Connection, client_id: str) -> list[dict[str, Any]]:
    """该客户的所有业务主线 (event_lines)."""
    rows = db.execute(
        """
        SELECT id, name, kind, status, stage, summary, intent, next_step,
               current_blocker, recent_decision, business_category,
               owner_id, owner_name, evidence_count, created_at, updated_at, closed_at
        FROM event_lines
        WHERE primary_client_id = ?
        ORDER BY updated_at DESC
        """,
        (client_id,),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        name = (row["name"] or "").strip()
        # 跳过 name 是 id 的脏数据
        is_dirty_name = name.startswith("eline_") and len(name) > 8

        out.append({
            "id": row["id"],
            "name": name if not is_dirty_name else "(未命名主线)",
            "kind": row["kind"] or "",
            "status": row["status"] or "",
            "stage": row["stage"] or "",
            "summary": row["summary"] or "",
            "intent": row["intent"] or "",
            "nextStep": row["next_step"] or "",
            "currentBlocker": row["current_blocker"] or "",
            "recentDecision": row["recent_decision"] or "",
            "businessCategory": row["business_category"] or "",
            "ownerId": row["owner_id"] or "",
            "ownerName": row["owner_name"] or "",
            "evidenceCount": int(row["evidence_count"] or 0),
            "createdAt": row["created_at"] or "",
            "updatedAt": row["updated_at"] or "",
            "closedAt": row["closed_at"] or "",
            "isDirtyName": is_dirty_name,
        })
    return out


def _load_timeline(
    db: sqlite3.Connection,
    event_line_ids: list[str],
    limit: int = 40,
) -> list[dict[str, Any]]:
    """合并该客户所有主线的事件时间线."""
    if not event_line_ids:
        return []
    placeholders = ",".join(["?"] * len(event_line_ids))
    rows = db.execute(
        f"""
        SELECT a.id, a.event_line_id, a.source_type, a.source_id, a.happened_at,
               a.actor_id, a.actor_name, a.title, a.summary, a.is_key,
               el.name AS event_line_name
        FROM event_line_activities a
        LEFT JOIN event_lines el ON el.id = a.event_line_id
        WHERE a.event_line_id IN ({placeholders})
        ORDER BY a.happened_at DESC
        LIMIT ?
        """,
        (*event_line_ids, limit),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        title = (row["title"] or "").strip()
        # 过滤测试附件
        if any(frag.lower() in title.lower() for frag in _TEST_QUOTE_FRAGMENTS):
            continue
        if title.endswith(".jpeg") or title.endswith(".png"):
            # 简化: 直接图片附件标题, 也跳过
            continue
        out.append({
            "id": row["id"],
            "eventLineId": row["event_line_id"],
            "eventLineName": row["event_line_name"] or "",
            "happenedAt": row["happened_at"] or "",
            "sourceType": row["source_type"] or "",
            "actorName": row["actor_name"] or "",
            "title": title,
            "summary": (row["summary"] or "")[:200],
            "isKey": bool(int(row["is_key"] or 0)),
        })
    return out


def _load_people_candidates(
    db: sqlite3.Connection,
    client_id: str,
    event_line_ids: list[str],
) -> list[dict[str, Any]]:
    """关键人物候选 (粗糙版 - 等 Phase 1 花名册建好后升级).

    来源:
      1. event_lines.owner_name + event_line_activities.actor_name
      2. memory_facts 里 scope_id=client_id 的人名提取 (启发式)
      3. judgment_versions.summary 里的人名 (启发式)

    返回每个 name 的出现次数 + 来源类型。
    """
    counter: Counter[str] = Counter()
    sources: dict[str, set[str]] = {}

    # 1. event_lines owners
    rows = db.execute(
        """
        SELECT DISTINCT owner_name FROM event_lines
        WHERE primary_client_id = ? AND owner_name IS NOT NULL AND owner_name != ''
        """,
        (client_id,),
    ).fetchall()
    for r in rows:
        name = (r["owner_name"] or "").strip()
        if name and name != "本机用户":
            counter[name] += 3  # 主线 owner 权重高
            sources.setdefault(name, set()).add("event_line_owner")

    # 2. event_line_activities actors
    if event_line_ids:
        placeholders = ",".join(["?"] * len(event_line_ids))
        rows = db.execute(
            f"""
            SELECT actor_name, COUNT(*) AS cnt FROM event_line_activities
            WHERE event_line_id IN ({placeholders})
              AND actor_name IS NOT NULL AND actor_name != ''
            GROUP BY actor_name
            """,
            tuple(event_line_ids),
        ).fetchall()
        for r in rows:
            name = (r["actor_name"] or "").strip()
            if name and name != "本机用户":
                counter[name] += int(r["cnt"] or 0)
                sources.setdefault(name, set()).add("activity_actor")

    # 3. tasks owners
    rows = db.execute(
        """
        SELECT DISTINCT owner_name FROM tasks
        WHERE client_id = ? AND owner_name IS NOT NULL AND owner_name != ''
        """,
        (client_id,),
    ).fetchall()
    for r in rows:
        name = (r["owner_name"] or "").strip()
        if name and name not in ("本机用户", "迁移占位"):
            counter[name] += 1
            sources.setdefault(name, set()).add("task_owner")

    # 4. action_items owners
    rows = db.execute(
        """
        SELECT DISTINCT ai.owner_name FROM action_items ai
        JOIN meetings m ON m.id = ai.meeting_id
        WHERE m.client_id = ? AND ai.owner_name IS NOT NULL AND ai.owner_name != ''
        """,
        (client_id,),
    ).fetchall()
    for r in rows:
        name = (r["owner_name"] or "").strip()
        if name:
            counter[name] += 2
            sources.setdefault(name, set()).add("action_item_owner")

    # 排序: 出现次数降序
    out: list[dict[str, Any]] = []
    for name, count in counter.most_common(20):
        out.append({
            "name": name,
            "mentionCount": count,
            "sources": sorted(sources.get(name, set())),
        })
    return out


def _load_commitments(
    db: sqlite3.Connection,
    client_id: str,
) -> list[dict[str, Any]]:
    """承诺链 - 当前只能从 action_items 拉 (数据稀少)."""
    rows = db.execute(
        """
        SELECT ai.id, ai.title, ai.owner_name, ai.due_date, ai.confidence,
               ai.publish_status, ai.created_at,
               m.id AS meeting_id, m.title AS meeting_title, m.scheduled_at
        FROM action_items ai
        JOIN meetings m ON m.id = ai.meeting_id
        WHERE m.client_id = ?
        ORDER BY ai.due_date ASC, ai.created_at DESC
        """,
        (client_id,),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": r["id"],
            "title": (r["title"] or "").strip(),
            "ownerName": r["owner_name"] or "",
            "dueDate": r["due_date"] or "",
            "confidence": float(r["confidence"] or 0.0),
            "publishStatus": r["publish_status"] or "",
            "meetingId": r["meeting_id"] or "",
            "meetingTitle": r["meeting_title"] or "",
            "meetingScheduledAt": r["scheduled_at"] or "",
            "createdAt": r["created_at"] or "",
        })
    return out


def _load_clarification_needs(
    db: sqlite3.Connection,
    event_line_ids: list[str],
) -> list[dict[str, Any]]:
    """AI 自检列的待澄清字段 (event_line_memory_snapshots.clarification_needs_json).

    当前数据里这个字段记的是'哪些字段没填' (current_blocker / recent_decision 等),
    不是业务级问题. Phase 2/3 会被'澄清问题生成引擎'升级为针对性业务问题.
    """
    if not event_line_ids:
        return []
    placeholders = ",".join(["?"] * len(event_line_ids))
    rows = db.execute(
        f"""
        SELECT event_line_id, line_name, clarification_needs_json,
               prediction_readiness, confidence, updated_at
        FROM event_line_memory_snapshots
        WHERE event_line_id IN ({placeholders})
        """,
        tuple(event_line_ids),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        needs_raw = r["clarification_needs_json"] or "[]"
        try:
            needs = json.loads(needs_raw)
        except json.JSONDecodeError:
            needs = []
        if not isinstance(needs, list) or not needs:
            continue
        out.append({
            "eventLineId": r["event_line_id"],
            "eventLineName": r["line_name"] or "",
            "missingFields": [str(n) for n in needs if n],
            "predictionReadiness": float(r["prediction_readiness"] or 0.0),
            "confidence": float(r["confidence"] or 0.0),
            "updatedAt": r["updated_at"] or "",
        })
    return out
