"""R1 · 报告 prompt 上下文构建器。

从事件线、客户档案、组织笔记本快照、事件线最新快照中，
摘要化出 LLM A（报告主理人）需要看的素材，渲染成 markdown
prompt 块。控制长度（默认最近 ≤30 条 entries）。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from app.db import Database


def _row_value(row: sqlite3.Row | None, key: str, default: Any = "") -> Any:
    """sqlite3.Row 不支持 .get()，包一层。"""
    if row is None:
        return default
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return default if value is None else value


def _safe_json_list(raw: Any) -> list[Any]:
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if isinstance(parsed, list):
        return parsed
    return []


def _modules_to_strings(items: list[Any]) -> tuple[str, ...]:
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or "").strip()
            if name:
                out.append(name)
    return tuple(out)


def _people_to_dicts(items: list[Any]) -> tuple[dict[str, str], ...]:
    out: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            role = str(item.get("role") or item.get("title") or "").strip()
            out.append({"name": name, "role": role})
    return tuple(out)


def _strings_or_titles(items: list[Any]) -> tuple[str, ...]:
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
        elif isinstance(item, dict):
            text = str(
                item.get("text")
                or item.get("title")
                or item.get("content")
                or ""
            ).strip()
            if text:
                out.append(text)
    return tuple(out)


@dataclass(frozen=True)
class ReportPromptContext:
    """LLM A 输入的摘要化上下文。

    所有字段已 trim / cap，可以直接走 render_for_prompt() 拼到 prompt。
    immutable（frozen=True），便于在测试中比较与 hash。
    """

    client_id: str
    client_name: str
    client_intro: str
    client_stage: str

    event_line_id: str
    event_line_name: str
    event_line_kind: str
    event_line_business_category: str
    event_line_stage: str
    event_line_summary: str
    event_line_intent: str
    event_line_current_blocker: str
    event_line_recent_decision: str
    event_line_next_step: str
    event_line_owner_name: str

    period_start: str
    period_end: str
    intent_hint: str
    audience_hint: str
    tone_hint: str

    entries: tuple[dict[str, Any], ...]
    entries_truncated: bool
    total_activities: int

    org_intro: str
    org_collaboration_relationship: str
    org_current_stage: str
    org_business_modules: tuple[str, ...]
    org_key_people: tuple[dict[str, str], ...]
    org_current_challenges: tuple[str, ...]
    org_collaboration_goals: tuple[str, ...]

    snapshot_current_stage: str
    snapshot_current_work: str
    snapshot_current_blocker: str
    snapshot_recent_decision: str
    snapshot_next_step: str

    def render_for_prompt(self) -> str:
        lines: list[str] = []

        lines.append("# 客户信息")
        lines.append(f"- 客户名称：{self.client_name or '未命名客户'}")
        if self.client_intro:
            lines.append(f"- 简介：{self.client_intro}")
        if self.client_stage:
            lines.append(f"- 客户阶段：{self.client_stage}")
        lines.append("")

        lines.append("# 报告期间与意图")
        period = self._format_period()
        if period:
            lines.append(f"- 期间起止：{period}")
        if self.intent_hint:
            lines.append(f"- 人类指定的报告意图：{self.intent_hint}")
        if self.audience_hint:
            lines.append(f"- 目标读者（建议）：{self.audience_hint}")
        if self.tone_hint:
            lines.append(f"- 期望基调（建议）：{self.tone_hint}")
        lines.append("")

        if self.event_line_id:
            lines.append("# 事件线")
            lines.append(f"- 名称：{self.event_line_name or '未命名事件线'}")
            if self.event_line_kind:
                lines.append(f"- 类型：{self.event_line_kind}")
            if self.event_line_business_category:
                lines.append(f"- 业务类别：{self.event_line_business_category}")
            if self.event_line_stage:
                lines.append(f"- 当前阶段：{self.event_line_stage}")
            if self.event_line_summary:
                lines.append(f"- 摘要：{self.event_line_summary}")
            if self.event_line_intent:
                lines.append(f"- 立项意图：{self.event_line_intent}")
            if self.event_line_current_blocker:
                lines.append(f"- 当前阻塞：{self.event_line_current_blocker}")
            if self.event_line_recent_decision:
                lines.append(f"- 最近决策：{self.event_line_recent_decision}")
            if self.event_line_next_step:
                lines.append(f"- 下一步：{self.event_line_next_step}")
            if self.event_line_owner_name:
                lines.append(f"- 负责人：{self.event_line_owner_name}")
            lines.append("")

        if self._has_org_content():
            lines.append("# 客户组织档案")
            if self.org_intro:
                lines.append(f"- 简介：{self.org_intro}")
            if self.org_collaboration_relationship:
                lines.append(f"- 合作关系：{self.org_collaboration_relationship}")
            if self.org_current_stage:
                lines.append(f"- 当前阶段：{self.org_current_stage}")
            if self.org_business_modules:
                lines.append(
                    "- 主要业务模块：" + "、".join(self.org_business_modules)
                )
            if self.org_key_people:
                people = [
                    f"{p['name']}（{p['role']}）" if p.get("role") else p["name"]
                    for p in self.org_key_people
                    if p.get("name")
                ]
                if people:
                    lines.append("- 关键人物：" + "、".join(people))
            if self.org_current_challenges:
                lines.append(
                    "- 当前挑战：" + "；".join(self.org_current_challenges)
                )
            if self.org_collaboration_goals:
                lines.append(
                    "- 协作目标：" + "；".join(self.org_collaboration_goals)
                )
            lines.append("")

        if self._has_snapshot_content():
            lines.append("# 事件线最新快照（记忆中枢生成）")
            if self.snapshot_current_stage:
                lines.append(f"- 当前阶段：{self.snapshot_current_stage}")
            if self.snapshot_current_work:
                lines.append(f"- 当前工作：{self.snapshot_current_work}")
            if self.snapshot_current_blocker:
                lines.append(f"- 当前阻塞：{self.snapshot_current_blocker}")
            if self.snapshot_recent_decision:
                lines.append(f"- 最近决策：{self.snapshot_recent_decision}")
            if self.snapshot_next_step:
                lines.append(f"- 下一步：{self.snapshot_next_step}")
            lines.append("")

        if self.entries:
            shown_n = len(self.entries)
            if self.entries_truncated and self.total_activities > shown_n:
                note = (
                    f"（按时间升序，原始 {self.total_activities} 条，"
                    f"仅保留最近 {shown_n} 条）"
                )
            else:
                note = "（按时间升序）"
            lines.append(f"# 时间线条目 · {shown_n} 条 {note}")
            for idx, entry in enumerate(self.entries, start=1):
                marker = " ⭐" if entry.get("is_key") else ""
                actor = str(entry.get("actor_name") or "").strip()
                actor_str = f" · {actor}" if actor else ""
                title = (
                    str(entry.get("title") or "").strip() or "未命名活动"
                )
                summary = str(entry.get("summary") or "").strip()
                summary_str = f" — {summary}" if summary else ""
                source = str(entry.get("source_type") or "").strip()
                source_str = f" [{source}]" if source else ""
                lines.append(
                    f"{idx}. {entry.get('happened_at', '')}"
                    f"{actor_str}{source_str}{marker}：{title}{summary_str}"
                )
            lines.append("")
        else:
            lines.append("# 时间线条目")
            lines.append("- （本期间无活动记录）")
            lines.append("")

        return "\n".join(lines).strip()

    def _format_period(self) -> str:
        if self.period_start and self.period_end:
            return f"{self.period_start} ~ {self.period_end}"
        if self.period_start:
            return f"自 {self.period_start} 起"
        if self.period_end:
            return f"截至 {self.period_end}"
        return ""

    def _has_org_content(self) -> bool:
        return any(
            [
                self.org_intro,
                self.org_collaboration_relationship,
                self.org_current_stage,
                self.org_business_modules,
                self.org_key_people,
                self.org_current_challenges,
                self.org_collaboration_goals,
            ]
        )

    def _has_snapshot_content(self) -> bool:
        return any(
            [
                self.snapshot_current_stage,
                self.snapshot_current_work,
                self.snapshot_current_blocker,
                self.snapshot_recent_decision,
                self.snapshot_next_step,
            ]
        )


def build_report_prompt_context(
    db: Database,
    *,
    client_id: str,
    event_line_id: str | None = None,
    period_start: str = "",
    period_end: str = "",
    intent_hint: str = "",
    audience_hint: str = "",
    tone_hint: str = "",
    max_entries: int = 30,
    activity_summary_chars: int = 240,
) -> ReportPromptContext:
    """从 DB 拉数据 → 摘要化 → 渲染为 LLM A 的 prompt 块。

    period_start / period_end 形如 'YYYY-MM-DD' 或 '' (空表示不过滤)。
    若 event_line_id 给出，则按事件线过滤；否则只用客户档案。
    """
    if not client_id:
        raise ValueError("client_id 是必填")

    client_row = db.fetchone(
        "SELECT * FROM clients WHERE id = ?", (client_id,)
    )
    if client_row is None:
        raise ValueError(f"客户不存在: {client_id}")

    event_line_row: sqlite3.Row | None = None
    if event_line_id:
        event_line_row = db.fetchone(
            "SELECT * FROM event_lines WHERE id = ?", (event_line_id,)
        )
        if event_line_row is None:
            raise ValueError(f"事件线不存在: {event_line_id}")

    entries: list[dict[str, Any]] = []
    entries_truncated = False
    total_activities = 0
    if event_line_id:
        sql_params: tuple[Any, ...] = (event_line_id,)
        where_extra = ""
        if period_start:
            where_extra += " AND happened_at >= ?"
            sql_params = sql_params + (period_start,)
        if period_end:
            where_extra += " AND happened_at <= ?"
            sql_params = sql_params + (period_end,)

        count_row = db.fetchone(
            "SELECT COUNT(1) AS n FROM event_line_activities "
            f"WHERE event_line_id = ?{where_extra}",
            sql_params,
        )
        total_activities = int(_row_value(count_row, "n", 0) or 0)

        rows = db.fetchall(
            "SELECT id, happened_at, actor_name, source_type, title, "
            "summary, is_key "
            "FROM event_line_activities "
            f"WHERE event_line_id = ?{where_extra} "
            "ORDER BY happened_at ASC",
            sql_params,
        )

        if len(rows) > max_entries:
            rows = rows[-max_entries:]
            entries_truncated = True

        for row in rows:
            summary_raw = str(_row_value(row, "summary", "") or "")
            summary = summary_raw[:activity_summary_chars]
            if len(summary_raw) > activity_summary_chars:
                summary += "…"
            entries.append(
                {
                    "id": str(_row_value(row, "id", "")),
                    "happened_at": str(_row_value(row, "happened_at", "")),
                    "actor_name": str(_row_value(row, "actor_name", "") or ""),
                    "source_type": str(_row_value(row, "source_type", "") or ""),
                    "title": str(_row_value(row, "title", "") or ""),
                    "summary": summary,
                    "is_key": bool(_row_value(row, "is_key", 0)),
                }
            )

    org_row = db.fetchone(
        "SELECT * FROM organization_notebook_snapshots WHERE client_id = ?",
        (client_id,),
    )

    snapshot_row: sqlite3.Row | None = None
    if event_line_id:
        snapshot_row = db.fetchone(
            "SELECT * FROM event_line_memory_snapshots "
            "WHERE event_line_id = ?",
            (event_line_id,),
        )

    return ReportPromptContext(
        client_id=str(_row_value(client_row, "id", "")),
        client_name=str(_row_value(client_row, "name", "") or ""),
        client_intro=str(_row_value(client_row, "intro", "") or ""),
        client_stage=str(_row_value(client_row, "stage", "") or ""),
        event_line_id=(
            str(_row_value(event_line_row, "id", "")) if event_line_row else ""
        ),
        event_line_name=str(_row_value(event_line_row, "name", "") or ""),
        event_line_kind=str(_row_value(event_line_row, "kind", "") or ""),
        event_line_business_category=str(
            _row_value(event_line_row, "business_category", "") or ""
        ),
        event_line_stage=str(_row_value(event_line_row, "stage", "") or ""),
        event_line_summary=str(_row_value(event_line_row, "summary", "") or ""),
        event_line_intent=str(_row_value(event_line_row, "intent", "") or ""),
        event_line_current_blocker=str(
            _row_value(event_line_row, "current_blocker", "") or ""
        ),
        event_line_recent_decision=str(
            _row_value(event_line_row, "recent_decision", "") or ""
        ),
        event_line_next_step=str(
            _row_value(event_line_row, "next_step", "") or ""
        ),
        event_line_owner_name=str(
            _row_value(event_line_row, "owner_name", "") or ""
        ),
        period_start=period_start,
        period_end=period_end,
        intent_hint=intent_hint,
        audience_hint=audience_hint,
        tone_hint=tone_hint,
        entries=tuple(entries),
        entries_truncated=entries_truncated,
        total_activities=total_activities,
        org_intro=str(_row_value(org_row, "organization_intro", "") or ""),
        org_collaboration_relationship=str(
            _row_value(org_row, "collaboration_relationship", "") or ""
        ),
        org_current_stage=str(
            _row_value(org_row, "current_stage", "") or ""
        ),
        org_business_modules=_modules_to_strings(
            _safe_json_list(_row_value(org_row, "business_modules_json", "[]"))
        ),
        org_key_people=_people_to_dicts(
            _safe_json_list(_row_value(org_row, "key_people_json", "[]"))
        ),
        org_current_challenges=_strings_or_titles(
            _safe_json_list(
                _row_value(org_row, "current_challenges_json", "[]")
            )
        ),
        org_collaboration_goals=_strings_or_titles(
            _safe_json_list(
                _row_value(org_row, "collaboration_goals_json", "[]")
            )
        ),
        snapshot_current_stage=str(
            _row_value(snapshot_row, "current_stage", "") or ""
        ),
        snapshot_current_work=str(
            _row_value(snapshot_row, "current_work", "") or ""
        ),
        snapshot_current_blocker=str(
            _row_value(snapshot_row, "current_blocker", "") or ""
        ),
        snapshot_recent_decision=str(
            _row_value(snapshot_row, "recent_decision", "") or ""
        ),
        snapshot_next_step=str(
            _row_value(snapshot_row, "next_step", "") or ""
        ),
    )
