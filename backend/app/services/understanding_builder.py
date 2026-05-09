"""
UnderstandingSnapshotV1 构建器

basic 模式：只靠 6 项最小输入产出完整的第一层理解。
enhanced 模式：在 basic 基础上叠加事件线记忆、会议等增强项。

核心原则：
- 少资料先出结果
- 永远不返回"无法判断"
- humanBrief 是给用户看的主产物
- 旧版 4 项仍保留为依据/调试
- optionalAdvice 只在证据足够时出现
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ai import AiService

from app.models import (
    OrganizationDnaModuleRecord,
    UnderstandingOptionalAdviceRecord,
    UnderstandingSnapshotV1Record,
    UnderstandingSourceBreakdownRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
)

import json
import hashlib
import logging

logger = logging.getLogger(__name__)

UNDERSTANDING_PROMPT_VERSION = "v2-human-brief"


def build_understanding_content_hash(
    *,
    title: str,
    desc: str = "",
    status: str = "",
    client_id: str = "",
    event_line_id: str = "",
    prompt_version: str | None = None,
) -> str:
    """缓存 hash 包含 prompt 版本，避免旧理解快照被继续复用。"""
    version = prompt_version or UNDERSTANDING_PROMPT_VERSION
    content = f"{version}|{title or ''}|{desc or ''}|{status or ''}|{client_id or ''}|{event_line_id or ''}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]


def _compact_text(value: object, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _client_name(snapshot: WeeklyReviewTaskSnapshotRecord) -> str:
    pc = getattr(snapshot, "projectContext", None)
    if pc and getattr(pc, "clientName", None):
        return str(pc.clientName).strip()
    return str(getattr(snapshot, "clientName", "") or "").strip()


def _event_line_name(snapshot: WeeklyReviewTaskSnapshotRecord) -> str:
    return str(getattr(snapshot, "eventLineName", "") or "").strip()


def _combined_task_text(
    snapshot: WeeklyReviewTaskSnapshotRecord,
    *,
    note: str,
    structured_note_reflection: str = "",
) -> str:
    parts = [
        getattr(snapshot, "title", ""),
        getattr(snapshot, "desc", ""),
        note,
        structured_note_reflection,
        _event_line_name(snapshot),
    ]
    return " ".join(str(part or "") for part in parts)


def _contains_forbidden_human_brief_template(text: str) -> bool:
    compact = text.replace(" ", "")
    return (
        "这是一条" in compact
        or "状态的工作任务" in compact
        or "系统尚未看到" in compact
        or ("与客户" in compact and "相关" in compact)
        or ("这不是" in compact and "而是" in compact)
    )


def _build_human_brief_with_rules(
    *,
    snapshot: WeeklyReviewTaskSnapshotRecord,
    note: str,
    structured_note_reflection: str = "",
) -> str:
    """不依赖 LLM 的主简报。避免诊断模板，直接给人下一步。"""
    title = _compact_text(getattr(snapshot, "title", "") or "这项任务", 34)
    client_name = _compact_text(_client_name(snapshot), 18)
    event_line = _compact_text(_event_line_name(snapshot), 18)
    combined = _combined_task_text(snapshot, note=note, structured_note_reflection=structured_note_reflection)
    lower = combined.lower()

    if "ppt" in lower or "报告" in combined:
        subject = "这份 PPT" if "ppt" in lower else f"「{title}」"
        subject_joiner = " " if subject.endswith("PPT") else ""
        known_bits: list[str] = []
        if client_name:
            known_bits.append(f"服务对象指向「{client_name}」")
        if "35" in combined:
            known_bits.append("页数上限已明确")
        if "gpt" in lower or "生成" in combined:
            known_bits.append("生成方式已有方向")
        if note.strip() or getattr(snapshot, "desc", "").strip():
            known_bits.append("已有任务说明")
        known_clause = "、".join(known_bits[:3]) if known_bits else "交付方向已有雏形"
        return (
            f"{subject}{subject_joiner}需要先定清楚给谁看、看完要促成什么判断，以及最终交付标准。"
            f"当前{known_clause}，还缺报告主线、目标受众、核心结论和必须保留的材料。"
            "建议先拆出章节框架，再决定哪些内容展开、哪些放进附录。"
        )

    known_bits = []
    if client_name:
        known_bits.append(f"服务对象指向「{client_name}」")
    if event_line:
        known_bits.append(f"关联事件线「{event_line}」")
    if note.strip() or getattr(snapshot, "desc", "").strip():
        known_bits.append("已有任务说明或复盘信息")
    if getattr(snapshot, "listName", ""):
        known_bits.append(f"所在列表为「{_compact_text(getattr(snapshot, 'listName', ''), 12)}」")
    known_clause = "、".join(known_bits[:3]) if known_bits else "目前只有标题和推进状态可用"

    return (
        f"「{title}」需要先明确最终要支持的判断、交付或决策。"
        f"当前{known_clause}，还缺验收标准、关键材料和完成后的使用场景。"
        "建议先补齐目标、已有资料和最小交付物，再决定由谁推进。"
    )


def _human_brief_from_raw(
    raw: dict,
    *,
    snapshot: WeeklyReviewTaskSnapshotRecord,
    note: str,
    structured_note_reflection: str = "",
) -> str:
    brief = _compact_text(raw.get("humanBrief", ""), 260).strip()
    if not brief or _contains_forbidden_human_brief_template(brief):
        return _build_human_brief_with_rules(
            snapshot=snapshot,
            note=note,
            structured_note_reflection=structured_note_reflection,
        )
    return brief


# ── Prompt ──

BASIC_SYSTEM = """\
你是益语智库的理解助手。益语智库是一家咨询公司，核心业务是与客户的合作关系。

你的任务是理解一条任务，产出能指导人推进任务的中文简报。

主输出是 humanBrief，必须满足：
- 2-3 句，90-160 个中文字符左右
- 不分点，不加标签，不解释“系统看到了什么”
- 第一句：说明这件事真正要推动的判断、交付或决策
- 第二句：说明已有约束、已知信息和关键缺口
- 第三句：给出最小下一步

你还必须保留这 4 个依据字段（即使信息有限也要尽力回答）：
1. whatIsThis — 这是什么事（一段话）
2. whyItMatters — 为什么重要（结合益语背景和客户背景）
3. progressNow — 现在推进到哪
4. unknowns — 还缺什么理解

同时提取 knownFacts：从输入中能确认的事实，列为数组。

confidence 用 0-100 整数表示你对判断的把握程度。

重要：
- 不要编造信息
- 缺信息时直接判断缺口和最小补齐动作，不要说“系统尚未看到”
- humanBrief 禁用这些句式：这是一条...状态任务 / 与客户...相关 / 系统尚未看到 / 这不是...而是...
- humanBrief 不要生成泛泛的建议，要说当前最小下一步
- 用中文输出
"""

BASIC_SCHEMA = {
    "type": "object",
    "properties": {
        "humanBrief": {"type": "string"},
        "whatIsThis": {"type": "string"},
        "whyItMatters": {"type": "string"},
        "progressNow": {"type": "string"},
        "unknowns": {"type": "string"},
        "knownFacts": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
    },
    "required": ["humanBrief", "whatIsThis", "whyItMatters", "progressNow", "unknowns", "knownFacts", "confidence"],
}


def _source_breakdown(
    *,
    org_dna: list[OrganizationDnaModuleRecord],
    snapshot: WeeklyReviewTaskSnapshotRecord,
    note: str,
    structured_note_reflection: str,
) -> list[UnderstandingSourceBreakdownRecord]:
    """列出每项输入的可用状态。"""
    has_org_dna = bool(org_dna and any(m.summary or m.normalizedText for m in org_dna))
    has_client = bool(getattr(snapshot, "projectContext", None) and snapshot.projectContext and snapshot.projectContext.clientName)
    has_quarterly = bool(getattr(snapshot, "orgContext", None) and snapshot.orgContext and getattr(snapshot.orgContext, "focusItemId", None))
    has_title = bool(snapshot.title.strip())
    has_desc = bool(getattr(snapshot, "desc", "").strip())
    has_review = bool(note.strip() or structured_note_reflection.strip())

    return [
        UnderstandingSourceBreakdownRecord(sourceType="org_dna", available=has_org_dna, label="益语背景卡"),
        UnderstandingSourceBreakdownRecord(sourceType="client_background", available=has_client, label="客户/项目背景卡"),
        UnderstandingSourceBreakdownRecord(sourceType="quarterly_focus", available=has_quarterly, label="季度主线卡"),
        UnderstandingSourceBreakdownRecord(sourceType="task_title", available=has_title, label="任务标题"),
        UnderstandingSourceBreakdownRecord(sourceType="task_desc", available=has_desc, label="任务说明"),
        UnderstandingSourceBreakdownRecord(sourceType="review_note", available=has_review, label="任务复盘资料"),
    ]


def _coverage_from_sources(sources: list[UnderstandingSourceBreakdownRecord]) -> int:
    """根据可用输入数计算覆盖度（0-100）。"""
    total = len(sources)
    available = sum(1 for s in sources if s.available)
    return int(round(available / total * 100)) if total > 0 else 0


def _assemble_basic_prompt(
    *,
    org_dna: list[OrganizationDnaModuleRecord],
    snapshot: WeeklyReviewTaskSnapshotRecord,
    note: str,
    structured_note_reflection: str,
) -> str:
    """组装 basic 模式的 prompt — 只用最小输入。"""
    sections: list[str] = []

    # 益语背景卡
    if org_dna:
        dna_parts = []
        for m in org_dna[:4]:
            text = m.summary or (m.normalizedText[:300] if m.normalizedText else "")
            if text:
                dna_parts.append(f"- {m.title}: {text}")
        if dna_parts:
            sections.append(f"【益语智库背景】\n" + "\n".join(dna_parts))

    # 客户/项目背景卡
    pc = getattr(snapshot, "projectContext", None)
    if pc and pc.clientName:
        parts = [f"客户：{pc.clientName}"]
        if pc.backgroundSummary:
            parts.append(f"背景：{pc.backgroundSummary[:200]}")
        if pc.goalSummary:
            parts.append(f"目标：{pc.goalSummary[:200]}")
        if pc.riskSummary:
            parts.append(f"风险：{pc.riskSummary[:200]}")
        sections.append(f"【客户/项目背景】\n" + "\n".join(f"- {p}" for p in parts))

    # 季度主线（从 orgContext 提取）
    oc = getattr(snapshot, "orgContext", None)
    if oc:
        focus_parts = []
        if getattr(oc, "departmentName", None):
            focus_parts.append(f"部门：{oc.departmentName}")
        if getattr(oc, "focusItemTitle", None):
            focus_parts.append(f"机构重点：{oc.focusItemTitle}")
        if getattr(oc, "departmentPlanItemTitle", None):
            focus_parts.append(f"部门计划：{oc.departmentPlanItemTitle}")
        if focus_parts:
            sections.append(f"【组织/部门季度主线】\n" + "\n".join(f"- {p}" for p in focus_parts))

    # 任务标题 + 说明
    task_parts = [f"标题：{snapshot.title}"]
    if hasattr(snapshot, "desc") and snapshot.desc.strip():
        task_parts.append(f"说明：{snapshot.desc[:300]}")
    task_parts.append(f"状态：{snapshot.status}")
    if hasattr(snapshot, "listName") and snapshot.listName:
        task_parts.append(f"所在列表：{snapshot.listName}")
    if hasattr(snapshot, "ownerName") and snapshot.ownerName:
        task_parts.append(f"负责人：{snapshot.ownerName}")
    sections.append(f"【当前任务】\n" + "\n".join(f"- {p}" for p in task_parts))

    # 复盘资料
    review_parts = []
    if note.strip():
        review_parts.append(f"复盘说明：{note.strip()[:300]}")
    if structured_note_reflection.strip():
        review_parts.append(f"反思：{structured_note_reflection.strip()[:200]}")
    if review_parts:
        sections.append(f"【复盘资料】\n" + "\n".join(f"- {p}" for p in review_parts))

    return "\n\n".join(sections) if sections else f"任务标题：{snapshot.title}"


def _build_basic_with_rules(
    *,
    snapshot: WeeklyReviewTaskSnapshotRecord,
    note: str,
    structured_note_reflection: str = "",
    org_dna: list[OrganizationDnaModuleRecord],
    sources: list[UnderstandingSourceBreakdownRecord],
    coverage: int,
) -> UnderstandingSnapshotV1Record:
    """纯规则兜底 — 当 LLM 不可用时，仍然产出 basic 结果。"""
    client_name = _client_name(snapshot)
    client_info = f"，服务对象指向「{client_name}」" if client_name else ""

    what_is_this = f"「{snapshot.title}」是一项需要推进的工作{client_info}。"

    why_it_matters = ""
    if client_name and org_dna:
        dna_title = org_dna[0].title if org_dna else "组织方向"
        why_it_matters = f"它需要放在「{client_name}」的合作进展里判断，并结合益语智库的{dna_title}看清业务意义。"
    elif client_name:
        why_it_matters = f"它会影响「{client_name}」当前合作中的交付节奏和后续判断。"
    else:
        why_it_matters = "当前缺少客户或项目背景，只能先从任务标题、说明和推进状态判断其业务意义。"

    progress_now = f"当前状态为 {snapshot.status}。"
    if note.strip():
        progress_now += f" 一线复盘说明：{note.strip()[:100]}"

    unknowns_parts = []
    for s in sources:
        if not s.available:
            unknowns_parts.append(s.label)
    unknowns = f"还缺这些关键信息：{'、'.join(unknowns_parts)}。" if unknowns_parts else "最小输入已全部可用。"

    facts = [f"任务标题：{snapshot.title}", f"状态：{snapshot.status}"]
    if client_name:
        facts.append(f"关联客户：{client_name}")
    if note.strip():
        facts.append(f"已有复盘说明")
    human_brief = _build_human_brief_with_rules(
        snapshot=snapshot,
        note=note,
        structured_note_reflection=structured_note_reflection,
    )

    return UnderstandingSnapshotV1Record(
        taskId=getattr(snapshot, "id", "") or "",
        mode="basic",
        coverage=coverage,
        confidence=max(15, coverage // 2),
        humanBrief=human_brief,
        whatIsThis=what_is_this,
        whyItMatters=why_it_matters,
        progressNow=progress_now,
        unknowns=unknowns,
        knownFacts=facts,
        optionalAdvice=None,
        sourceBreakdown=sources,
    )


def build_understanding_basic(
    *,
    ai: "AiService | None",
    task_entry: WeeklyReviewTaskEntryRecord,
    org_dna_modules: list[OrganizationDnaModuleRecord],
) -> UnderstandingSnapshotV1Record:
    """
    basic 模式构建器 — 只靠最小输入产出第一层理解。
    永远不返回"无法判断"。
    """
    snapshot = task_entry.taskSnapshot
    note = task_entry.note or ""
    structured_note = task_entry.structuredNote
    reflection = structured_note.reflection if structured_note else ""

    sources = _source_breakdown(
        org_dna=org_dna_modules,
        snapshot=snapshot,
        note=note,
        structured_note_reflection=reflection,
    )
    coverage = _coverage_from_sources(sources)

    # 尝试 LLM
    if ai is not None:
        prompt = _assemble_basic_prompt(
            org_dna=org_dna_modules,
            snapshot=snapshot,
            note=note,
            structured_note_reflection=reflection,
        )
        try:
            raw = ai._qwen_generate(
                prompt=prompt,
                system_instruction=BASIC_SYSTEM,
                response_schema=BASIC_SCHEMA,
                timeout_seconds=30.0,
                max_tokens=1200,
                temperature=0.25,
            )
            if isinstance(raw, dict):
                return UnderstandingSnapshotV1Record(
                    taskId=getattr(snapshot, "id", "") or "",
                    mode="basic",
                    coverage=coverage,
                    confidence=min(int(raw.get("confidence", 30)), coverage),
                    humanBrief=_human_brief_from_raw(
                        raw,
                        snapshot=snapshot,
                        note=note,
                        structured_note_reflection=reflection,
                    ),
                    whatIsThis=str(raw.get("whatIsThis", "")),
                    whyItMatters=str(raw.get("whyItMatters", "")),
                    progressNow=str(raw.get("progressNow", "")),
                    unknowns=str(raw.get("unknowns", "")),
                    knownFacts=list(raw.get("knownFacts", [])),
                    optionalAdvice=None,
                    sourceBreakdown=sources,
                )
        except Exception as exc:
            logger.warning("Understanding basic LLM call failed: %s", exc)

    # 规则兜底
    return _build_basic_with_rules(
        snapshot=snapshot,
        note=note,
        structured_note_reflection=reflection,
        org_dna=org_dna_modules,
        sources=sources,
        coverage=coverage,
    )


# ── Enhanced 模式 ──

ENHANCED_SYSTEM = """\
你是益语智库的理解助手。益语智库是一家咨询公司，核心业务是与客户的合作关系。

你的任务是结合丰富的上下文深度理解一条任务，产出能指导人推进任务的中文简报。

主输出是 humanBrief，必须满足：
- 2-3 句，90-160 个中文字符左右
- 不分点，不加标签，不解释“系统看到了什么”
- 第一句：说明这件事真正要推动的判断、交付或决策
- 第二句：说明已有约束、已知信息和关键缺口
- 第三句：给出最小下一步

你还必须保留这 4 个依据字段：
1. whatIsThis — 这是什么事
2. whyItMatters — 为什么重要（必须体现合作关系层面的意义，不只是任务本身）
3. progressNow — 现在推进到哪（结合事件线历史和会议记录给出具体阶段判断）
4. unknowns — 还缺什么理解

额外地，如果证据确实充分，你可以给出 optionalAdvice：
- realBlocker — 真正的阻碍（必须具体，不能泛泛）
- timeGate — 时间闸门（过了这个时间点情况会质变）
- minimumAction — 最小动作（当前最该做的 1 件事）
- supportAsk — 需要谁提供什么支持

如果证据不够充分，optionalAdvice 的字段留空字符串或不填。

confidence 用 0-100 整数。
用中文输出。不要编造信息。
humanBrief 禁用这些句式：这是一条...状态任务 / 与客户...相关 / 系统尚未看到 / 这不是...而是...
"""

ENHANCED_SCHEMA = {
    "type": "object",
    "properties": {
        "humanBrief": {"type": "string"},
        "whatIsThis": {"type": "string"},
        "whyItMatters": {"type": "string"},
        "progressNow": {"type": "string"},
        "unknowns": {"type": "string"},
        "knownFacts": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "realBlocker": {"type": "string"},
        "timeGate": {"type": "string"},
        "minimumAction": {"type": "string"},
        "supportAsk": {"type": "string"},
    },
    "required": ["humanBrief", "whatIsThis", "whyItMatters", "progressNow", "unknowns", "knownFacts", "confidence"],
}


def _append_enhanced_sources(
    sources: list[UnderstandingSourceBreakdownRecord],
    *,
    has_event_line_memory: bool,
    has_meeting: bool,
    has_support_request: bool,
    has_knowledge: bool = False,
) -> list[UnderstandingSourceBreakdownRecord]:
    """在 basic 源列表上追加增强项。"""
    return sources + [
        UnderstandingSourceBreakdownRecord(sourceType="event_line_memory", available=has_event_line_memory, label="事件线记忆"),
        UnderstandingSourceBreakdownRecord(sourceType="meeting", available=has_meeting, label="会议记录"),
        UnderstandingSourceBreakdownRecord(sourceType="support_request", available=has_support_request, label="支持请求"),
        UnderstandingSourceBreakdownRecord(sourceType="knowledge_base", available=has_knowledge, label="客户知识库"),
    ]


def _assemble_enhanced_prompt(
    basic_prompt: str,
    *,
    event_line_name: str = "",
    event_line_summary: str = "",
    event_line_stage: str = "",
    event_line_blocker: str = "",
    event_line_history: list[dict] = (),
    meetings: list[dict] = (),
    support_requests: list[dict] = (),
    knowledge_summaries: list[dict] = (),
) -> str:
    """在 basic prompt 基础上追加增强上下文。"""
    sections = [basic_prompt]

    # 客户知识库摘要
    if knowledge_summaries:
        kb_lines = []
        for kb in list(knowledge_summaries)[:5]:
            kb_lines.append(f"- {kb.get('title', '文档')}：{kb.get('summary', '')[:200]}")
        sections.append(f"【客户知识库关键摘要】\n" + "\n".join(kb_lines))

    if event_line_name:
        el_parts = [f"事件线：{event_line_name}"]
        if event_line_stage:
            el_parts.append(f"阶段：{event_line_stage}")
        if event_line_summary:
            el_parts.append(f"概要：{event_line_summary}")
        if event_line_blocker:
            el_parts.append(f"阻碍：{event_line_blocker}")
        sections.append(f"【事件线当前状态】\n" + "\n".join(f"- {p}" for p in el_parts))

    if event_line_history:
        history_lines = []
        for snap in list(event_line_history)[:8]:
            line = f"- {snap.get('weekLabel', '?')}：阶段={snap.get('stage', '?')}，任务{snap.get('taskCount', 0)}条/完成{snap.get('completedCount', 0)}条"
            decisions = snap.get("keyDecisions", [])
            if decisions:
                line += f"，决定：{'；'.join(decisions[:2])}"
            history_lines.append(line)
        sections.append(f"【事件线历史轨迹（近{len(event_line_history)}周）】\n" + "\n".join(history_lines))

    if meetings:
        meeting_lines = []
        for m in list(meetings)[:3]:
            meeting_lines.append(f"- {m.get('title', '会议')}：{m.get('summary', '')[:150]}")
        sections.append(f"【相关会议】\n" + "\n".join(meeting_lines))

    if support_requests:
        sr_lines = []
        for sr in list(support_requests)[:3]:
            sr_lines.append(f"- [{sr.get('status', '?')}] {sr.get('title', '')}：{sr.get('summary', '')[:100]}")
        sections.append(f"【支持请求】\n" + "\n".join(sr_lines))

    return "\n\n".join(sections)


def build_understanding_enhanced(
    *,
    ai: "AiService | None",
    task_entry: WeeklyReviewTaskEntryRecord,
    org_dna_modules: list[OrganizationDnaModuleRecord],
    event_line_name: str = "",
    event_line_summary: str = "",
    event_line_stage: str = "",
    event_line_blocker: str = "",
    event_line_history: list[dict] | None = None,
    meetings: list[dict] | None = None,
    support_requests: list[dict] | None = None,
    knowledge_summaries: list[dict] | None = None,
) -> UnderstandingSnapshotV1Record:
    """
    enhanced 模式构建器。
    在 basic 基础上叠加事件线记忆、会议、知识库等增强项。
    增强项只提升精度，不覆盖 basic 主逻辑。
    证据不足时保留 basic 输出，不硬写 optionalAdvice。
    """
    snapshot = task_entry.taskSnapshot
    note = task_entry.note or ""
    structured_note = task_entry.structuredNote
    reflection = structured_note.reflection if structured_note else ""

    # basic 源
    basic_sources = _source_breakdown(
        org_dna=org_dna_modules,
        snapshot=snapshot,
        note=note,
        structured_note_reflection=reflection,
    )

    has_el = bool(event_line_name)
    has_meeting = bool(meetings)
    has_sr = bool(support_requests)
    has_kb = bool(knowledge_summaries)

    sources = _append_enhanced_sources(
        basic_sources,
        has_event_line_memory=has_el,
        has_meeting=has_meeting,
        has_support_request=has_sr,
        has_knowledge=has_kb,
    )
    coverage = _coverage_from_sources(sources)

    # 如果没有任何增强项，降级回 basic
    if not has_el and not has_meeting and not has_sr and not has_kb:
        basic = build_understanding_basic(ai=ai, task_entry=task_entry, org_dna_modules=org_dna_modules)
        basic.sourceBreakdown = sources
        basic.coverage = coverage
        return basic

    # 组装 enhanced prompt
    basic_prompt = _assemble_basic_prompt(
        org_dna=org_dna_modules,
        snapshot=snapshot,
        note=note,
        structured_note_reflection=reflection,
    )
    prompt = _assemble_enhanced_prompt(
        basic_prompt,
        event_line_name=event_line_name,
        event_line_summary=event_line_summary,
        event_line_stage=event_line_stage,
        event_line_blocker=event_line_blocker,
        event_line_history=event_line_history or [],
        meetings=meetings or [],
        support_requests=support_requests or [],
        knowledge_summaries=knowledge_summaries or [],
    )

    # 尝试 LLM
    if ai is not None:
        try:
            raw = ai._qwen_generate(
                prompt=prompt,
                system_instruction=ENHANCED_SYSTEM,
                response_schema=ENHANCED_SCHEMA,
                timeout_seconds=45.0,
                max_tokens=1800,
                temperature=0.3,
            )
            if isinstance(raw, dict):
                # optionalAdvice 只在有实质内容时才填
                advice = None
                rb = str(raw.get("realBlocker", "")).strip()
                tg = str(raw.get("timeGate", "")).strip()
                ma = str(raw.get("minimumAction", "")).strip()
                sa = str(raw.get("supportAsk", "")).strip()
                if rb or tg or ma or sa:
                    advice = UnderstandingOptionalAdviceRecord(
                        realBlocker=rb or None,
                        timeGate=tg or None,
                        minimumAction=ma or None,
                        supportAsk=sa or None,
                    )

                return UnderstandingSnapshotV1Record(
                    taskId=getattr(snapshot, "id", "") or "",
                    mode="enhanced",
                    coverage=coverage,
                    confidence=min(int(raw.get("confidence", 40)), coverage),
                    humanBrief=_human_brief_from_raw(
                        raw,
                        snapshot=snapshot,
                        note=note,
                        structured_note_reflection=reflection,
                    ),
                    whatIsThis=str(raw.get("whatIsThis", "")),
                    whyItMatters=str(raw.get("whyItMatters", "")),
                    progressNow=str(raw.get("progressNow", "")),
                    unknowns=str(raw.get("unknowns", "")),
                    knownFacts=list(raw.get("knownFacts", [])),
                    optionalAdvice=advice,
                    sourceBreakdown=sources,
                )
        except Exception as exc:
            logger.warning("Understanding enhanced LLM call failed: %s", exc)

    # LLM 不可用时，回退到 basic 结果但标记为 enhanced 源
    basic = build_understanding_basic(ai=None, task_entry=task_entry, org_dna_modules=org_dna_modules)
    basic.mode = "enhanced"
    basic.sourceBreakdown = sources
    basic.coverage = coverage
    return basic
