"""事件线主线还原 (Timeline Narrative) — 让 AI 把碎片素材重组成因果故事。

跟 client_narrative 不同, 这里聚焦在单条事件线: 输入 event_line + activities + tasks +
attachments parsed_preview + 关联到这条线的 atomic_facts / memory_facts, 输出:
  - headline: 一句话当事件线的概括
  - opening: 起源段, 这事是怎么开始的
  - nodes: 3-5 个关键转折点 (每个含 time / title / narrative / linkedRefs)
  - closing: 今天在哪里 / 下一个决策点

LLM 失败时返回 stub 兜底, 不阻塞用户。
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import httpx

SYSTEM_PROMPT = """你是事件线主线还原专家。任务: 给定一条事件线的全部碎片素材
(事件线本体 + 活动流水 + 任务 + 附件摘要 + 相关事实), 重组成一篇 5 分钟能读完的"传记"。

【硬要求】所有输出文字必须是简体中文 (headline / opening / closing / 每个节点的 title 和 narrative)。
不要出现任何英文段落 — 哪怕原素材是英文也要翻译成中文。

【内容要求】
1. 抓 3-5 个**关键转折点** (key turning points): 决定了事件线方向的重要节点。
2. 不要罗列所有活动/任务 — 那些去"按任务查看"看就行。
3. 用具体内容写每个节点的 title/narrative, 不要模板话术。
4. 节点之间有时间和因果, 不是孤立卡片。
5. opening 写"这事是怎么开始的", closing 写"今天在哪里, 下一个决策点"。
6. 用第三人称写, 严肃克制, 不煽情。
7. 如果素材不足某个节点, 宁愿少写也不要编造。
8. 避免提"用户 guyuan 创建"这种技术语言, 用业务语言, 比如"益语团队启动了…"。

严格输出 JSON, schema 见用户消息。"""


@dataclass
class NarrativeNodeOutput:
    id: str
    time: str
    title: str
    narrative: str
    confidence: str
    linkedTaskIds: list[str]
    linkedActivityIds: list[str]
    linkedAttachmentIds: list[str]


@dataclass
class TimelineNarrativeOutput:
    eventLineId: str
    rev: int
    headline: str
    opening: str
    closing: str
    nodes: list[NarrativeNodeOutput]
    overallConfidence: float
    generator: str
    modelName: str
    updatedAt: str
    triggeredByDisplayName: str = ""


def _strip_to_json(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


def _collect_context(db, organization_id: str, event_line_id: str) -> dict[str, Any]:
    """收集这条事件线的所有素材。"""
    el = db.fetchone(
        "SELECT * FROM event_lines WHERE id=? AND organization_id=?",
        (event_line_id, organization_id),
    )
    if not el:
        raise ValueError(f"event_line not found: {event_line_id}")

    # event_line_activities 云端没有 actor_name / is_key 字段
    activities = db.fetchall(
        """
        SELECT id, source_type, source_id, happened_at, actor_id, title, summary
        FROM event_line_activities
        WHERE event_line_id=?
        ORDER BY happened_at ASC
        LIMIT 60
        """,
        (event_line_id,),
    )
    # 云端 tasks 表没有 owner_name 字段, 用 owner_id 替代
    tasks = db.fetchall(
        """
        SELECT id, title, description, progress_status, due_date, owner_id,
               current_blocker, next_action, recent_decision
        FROM tasks
        WHERE event_line_id=? AND organization_id=?
        ORDER BY created_at ASC
        LIMIT 30
        """,
        (event_line_id, organization_id),
    )
    attachments = db.fetchall(
        """
        SELECT id, task_id, title, summary, kind, mime_type, created_at
        FROM task_attachments
        WHERE event_line_id=? AND organization_id=?
        UNION ALL
        SELECT id, '' AS task_id, title, summary, kind, mime_type, created_at
        FROM event_line_attachments
        WHERE event_line_id=? AND organization_id=?
        ORDER BY created_at ASC
        """,
        (event_line_id, organization_id, event_line_id, organization_id),
    )

    return {
        "event_line": dict(el),
        "activities": [dict(r) for r in activities],
        "tasks": [dict(r) for r in tasks],
        "attachments": [dict(r) for r in attachments],
    }


def _build_user_prompt(ctx: dict[str, Any]) -> str:
    el = ctx["event_line"]
    parts: list[str] = []
    parts.append(f"# 事件线本体")
    parts.append(
        f"- name: {el.get('name')}\n"
        f"- kind: {el.get('kind')}\n"
        f"- status: {el.get('status')}\n"
        f"- stage: {el.get('stage')}\n"
        f"- summary: {el.get('summary')}\n"
        f"- intent: {el.get('intent')}\n"
        f"- next_step: {el.get('next_step')}\n"
        f"- current_blocker: {el.get('current_blocker')}\n"
        f"- recent_decision: {el.get('recent_decision')}\n"
        f"- primary_client_name: {el.get('primary_client_name')}\n"
        f"- created_at: {el.get('created_at')}\n"
    )

    parts.append(f"\n# 任务 (共 {len(ctx['tasks'])} 条, 按创建时间排)")
    for t in ctx["tasks"][:30]:
        parts.append(
            f"- [task:{t['id']}] {t['title']} | status={t['progress_status']} | "
            f"due={t.get('due_date') or '-'} | owner_id={t.get('owner_id') or '-'}"
        )
        d = (t.get("description") or "").strip()
        if d:
            parts.append(f"    desc: {d[:200]}")
        for fld in ("current_blocker", "next_action", "recent_decision"):
            v = (t.get(fld) or "").strip()
            if v:
                parts.append(f"    {fld}: {v[:150]}")

    parts.append(f"\n# 活动流水 (共 {len(ctx['activities'])} 条, 按时间排)")
    for a in ctx["activities"][:60]:
        title = (a.get("title") or "").strip()
        summary = (a.get("summary") or "").strip()
        actor = a.get("actor_id") or "-"
        parts.append(f"- [act:{a['id']}] {a['happened_at']} | actor={actor} | {title}")
        if summary and summary != title:
            parts.append(f"    {summary[:200]}")

    parts.append(f"\n# 附件 (共 {len(ctx['attachments'])} 条)")
    for att in ctx["attachments"][:40]:
        title = att.get("title") or ""
        summary = (att.get("summary") or "").strip()
        parts.append(f"- [att:{att['id']}] {title}")
        if summary:
            parts.append(f"    parsed: {summary[:400]}")

    parts.append(
        "\n# 输出 schema (严格 JSON, 不要多余文字)\n"
        + json.dumps(
            {
                "headline": "一句话描述这条事件线 (不超过 40 字)",
                "opening": "起源段, 这事是怎么开始的 (2-3 句)",
                "closing": "今天在哪里, 下一个决策点是什么 (2-3 句)",
                "overallConfidence": "0.0-1.0 浮点",
                "nodes": [
                    {
                        "time": "ISO 时间, 必填",
                        "title": "一句话标题, 抓住这个转折点的本质",
                        "narrative": "1-3 句话: 发生了什么 → 因此后续怎么走",
                        "confidence": "high|medium|low",
                        "linkedTaskIds": ["相关任务 id"],
                        "linkedActivityIds": ["相关活动 id"],
                        "linkedAttachmentIds": ["相关附件 id"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return "\n".join(parts)


def _chat_completions_endpoint(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if not normalized:
        raise RuntimeError("organization AI base URL is missing")
    return normalized if normalized.endswith("/chat/completions") else f"{normalized}/chat/completions"


def _call_llm(
    user_prompt: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    if not api_key or not model:
        raise RuntimeError("organization AI configuration is incomplete")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "top_p": 0.9,
        "max_tokens": 4000,
        "stream": False,
        "enable_thinking": False,
    }
    timeout = httpx.Timeout(timeout=None, connect=10.0, read=180.0, write=20.0, pool=10.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            _chat_completions_endpoint(base_url),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return json.loads(_strip_to_json(text))


def _stub_output(event_line_id: str, reason: str) -> TimelineNarrativeOutput:
    return TimelineNarrativeOutput(
        eventLineId=event_line_id,
        rev=1,
        headline=f"⏳ 主线叙事暂未生成 — {reason}",
        opening="",
        closing="",
        nodes=[],
        overallConfidence=0.0,
        generator="stub",
        modelName="",
        updatedAt=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def regenerate_timeline_narrative(
    db,
    organization_id: str,
    event_line_id: str,
    *,
    triggered_by_user_id: str | None,
    triggered_by_display_name: str,
    trigger: str = "manual",
    ai_api_key: str | None = None,
    ai_base_url: str = "",
    ai_model: str = "",
) -> TimelineNarrativeOutput:
    ctx = _collect_context(db, organization_id, event_line_id)

    if not ai_api_key or not ai_base_url or not ai_model:
        out = _stub_output(event_line_id, "当前组织 AI 配置未提供")
        _write_version(db, organization_id, out, triggered_by_user_id, triggered_by_display_name, trigger)
        return out

    user_prompt = _build_user_prompt(ctx)
    try:
        parsed = _call_llm(
            user_prompt,
            api_key=ai_api_key,
            base_url=ai_base_url,
            model=ai_model,
        )
    except Exception as exc:
        out = _stub_output(event_line_id, f"LLM 调用失败: {type(exc).__name__}: {exc}")
        _write_version(db, organization_id, out, triggered_by_user_id, triggered_by_display_name, trigger)
        return out

    if not isinstance(parsed, dict):
        out = _stub_output(event_line_id, "LLM 返回格式不合法")
        _write_version(db, organization_id, out, triggered_by_user_id, triggered_by_display_name, trigger)
        return out

    nodes_raw = parsed.get("nodes") or []
    nodes: list[NarrativeNodeOutput] = []
    for idx, n in enumerate(nodes_raw):
        if not isinstance(n, dict):
            continue
        nodes.append(
            NarrativeNodeOutput(
                id=f"narrative-{event_line_id}-{idx + 1}",
                time=str(n.get("time") or ""),
                title=str(n.get("title") or "").strip()[:200],
                narrative=str(n.get("narrative") or "").strip()[:800],
                confidence=str(n.get("confidence") or "medium"),
                linkedTaskIds=[str(x) for x in (n.get("linkedTaskIds") or []) if x],
                linkedActivityIds=[str(x) for x in (n.get("linkedActivityIds") or []) if x],
                linkedAttachmentIds=[str(x) for x in (n.get("linkedAttachmentIds") or []) if x],
            )
        )

    try:
        confidence = float(parsed.get("overallConfidence") or 0.5)
    except (TypeError, ValueError):
        confidence = 0.5

    output = TimelineNarrativeOutput(
        eventLineId=event_line_id,
        rev=1,
        headline=str(parsed.get("headline") or "").strip()[:200],
        opening=str(parsed.get("opening") or "").strip()[:600],
        closing=str(parsed.get("closing") or "").strip()[:600],
        nodes=nodes,
        overallConfidence=confidence,
        generator="ai_doubao",
        modelName=ai_model,
        updatedAt=time.strftime("%Y-%m-%dT%H:%M:%S"),
        triggeredByDisplayName=triggered_by_display_name or "",
    )
    _write_version(db, organization_id, output, triggered_by_user_id, triggered_by_display_name, trigger)
    return output


def _write_version(
    db,
    organization_id: str,
    output: TimelineNarrativeOutput,
    triggered_by_user_id: str | None,
    triggered_by_display_name: str,
    trigger: str,
) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    # bump is_latest=0 for old versions
    db.execute(
        "UPDATE cloud_event_line_timeline_narratives SET is_latest=0 WHERE event_line_id=? AND organization_id=?",
        (output.eventLineId, organization_id),
    )
    # compute next rev
    row = db.fetchone(
        "SELECT MAX(rev) AS max_rev FROM cloud_event_line_timeline_narratives WHERE event_line_id=? AND organization_id=?",
        (output.eventLineId, organization_id),
    )
    next_rev = int((row["max_rev"] or 0) if row else 0) + 1
    output.rev = next_rev

    db.execute(
        """
        INSERT INTO cloud_event_line_timeline_narratives
        (id, organization_id, event_line_id, rev, headline, opening, closing,
         nodes_json, overall_confidence, generator, model_name,
         triggered_by_user_id, triggered_by_display_name, trigger, is_latest,
         created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
        """,
        (
            f"eln_{uuid.uuid4().hex[:12]}",
            organization_id,
            output.eventLineId,
            next_rev,
            output.headline,
            output.opening,
            output.closing,
            json.dumps([asdict(n) for n in output.nodes], ensure_ascii=False),
            output.overallConfidence,
            output.generator,
            output.modelName,
            triggered_by_user_id,
            triggered_by_display_name or "",
            trigger,
            now,
            now,
        ),
    )


def get_latest_narrative(db, organization_id: str, event_line_id: str) -> TimelineNarrativeOutput | None:
    row = db.fetchone(
        """
        SELECT * FROM cloud_event_line_timeline_narratives
        WHERE event_line_id=? AND organization_id=? AND is_latest=1
        LIMIT 1
        """,
        (event_line_id, organization_id),
    )
    if not row:
        return None
    try:
        nodes_raw = json.loads(row["nodes_json"] or "[]")
    except Exception:
        nodes_raw = []
    nodes = [
        NarrativeNodeOutput(
            id=str(n.get("id") or ""),
            time=str(n.get("time") or ""),
            title=str(n.get("title") or ""),
            narrative=str(n.get("narrative") or ""),
            confidence=str(n.get("confidence") or "medium"),
            linkedTaskIds=list(n.get("linkedTaskIds") or []),
            linkedActivityIds=list(n.get("linkedActivityIds") or []),
            linkedAttachmentIds=list(n.get("linkedAttachmentIds") or []),
        )
        for n in nodes_raw
        if isinstance(n, dict)
    ]
    return TimelineNarrativeOutput(
        eventLineId=str(row["event_line_id"]),
        rev=int(row["rev"]),
        headline=str(row["headline"] or ""),
        opening=str(row["opening"] or ""),
        closing=str(row["closing"] or ""),
        nodes=nodes,
        overallConfidence=float(row["overall_confidence"] or 0.0),
        generator=str(row["generator"] or ""),
        modelName=str(row["model_name"] or ""),
        updatedAt=str(row["updated_at"] or ""),
        triggeredByDisplayName=str(row["triggered_by_display_name"] or ""),
    )
