"""
叙事分析引擎 — 五层上下文驱动的周复盘深度理解

分析调用顺序：
1. 组织 DNA（益语是谁、靠什么服务客户）
2. 客户背景（客户是谁、行业位置、需求痛点）
3. 合作关系（为什么接触、对双方意味着什么）
4. 事件线时间记忆（跨周历史轨迹）
5. 当前任务快照（作为整条线上的一个节点）

输出优先级：
- 这是什么事 → 为什么重要 → 推进到哪 → 还缺什么理解
- 信息足够时才升级为：风险、时间闸门、最小动作、管理建议
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db import Database
    from app.services.ai import AiService

from app.models import (
    ClientStrategicProfileRecord,
    CooperationRelationshipRecord,
    EventLineWeeklySnapshotRecord,
    NarrativeAnalysisRecord,
    OrganizationDnaModuleRecord,
    WeeklyReviewTaskEntryRecord,
)

logger = logging.getLogger(__name__)


@dataclass
class WeeklyLineCard:
    line_name: str
    score: float
    what_happened: str
    why_it_matters: str
    progress_now: str
    next_gap_or_need: str


SOFTWARE_LINE_KEYWORDS = (
    "codex",
    "attachment",
    "附件",
    "保存",
    "上传",
    "debug",
    "排查",
    "可见性",
    "链路",
    "联调",
    "任务可见",
)
INTEL_LINE_KEYWORDS = (
    "心理健康",
    "心理友好",
    "数字监管",
    "垃圾代码",
    "开源社区",
    "ai ",
    "ai垃圾代码",
    "情报",
    "议题",
)
COLLAB_LINE_KEYWORDS = (
    "合作",
    "协作",
    "见面",
    "沟通",
    "交流",
    "吃饭",
    "对话",
)

NARRATIVE_SYSTEM_INSTRUCTION = """\
你是益语智库的周复盘分析助手。益语智库是一家咨询公司，核心业务是与客户的合作关系。

你的任务是为一条事件线生成深度叙事分析。你会收到五层上下文信息，请按以下优先级输出：

**必须回答（即使信息不完整也要尽力回答）：**
1. 这是什么事（whatThisIs）— 用一段话说清楚这条事件线在做什么
2. 为什么重要（whyImportant）— 结合客户背景和合作关系，解释这件事对益语和客户分别意味着什么
3. 现在推进到哪（currentProgress）— 结合事件线历史轨迹，说明当前处于什么阶段，相比之前有什么进展
4. 还缺什么理解（missingUnderstanding）— 系统目前对这条线还不够了解的地方，需要补充什么信息

**仅在信息充分时回答（否则留空）：**
5. 风险提示（riskNote）
6. 时间闸门（timeGate）
7. 最小动作（minimumAction）
8. 管理建议（managementAdvice）

重要原则：
- 不要从任务出发去猜背景，而是从背景、关系和时间线出发去理解任务
- 不要生成泛泛的建议，每一句话都要有具体的上下文支撑
- 如果某一层上下文缺失，明确说"系统尚未看到…的信息"，不要编造
- 用中文输出，语言简练有力
"""

NARRATIVE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "whatThisIs": {"type": "string", "description": "这是什么事"},
        "whyImportant": {"type": "string", "description": "为什么重要"},
        "currentProgress": {"type": "string", "description": "现在推进到哪"},
        "missingUnderstanding": {"type": "string", "description": "还缺什么理解"},
        "riskNote": {"type": "string", "description": "风险提示，信息不足时留空"},
        "timeGate": {"type": "string", "description": "时间闸门，信息不足时留空"},
        "minimumAction": {"type": "string", "description": "最小动作，信息不足时留空"},
        "managementAdvice": {"type": "string", "description": "管理建议，信息不足时留空"},
        "confidenceLevel": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["whatThisIs", "whyImportant", "currentProgress", "missingUnderstanding", "confidenceLevel"],
}

WEEKLY_OVERVIEW_SYSTEM_INSTRUCTION = """\
你是益语智库的周复盘写作助手。

你的任务不是罗列任务，而是把一周发生的事情收成一段可以指导管理的“本周概况总结”。

写作要求：
1. 先说这一周整体是什么性质的一周，例如在打底、铺线、收束、突破，而不是一上来罗列任务。
2. 必须优先利用这些背景：益语组织 DNA、客户背景、合作关系、事件线叙事。
3. 不要把技术排查写成琐碎 debug，要指出它对后续判断和交付意味着什么。
4. 不要泛泛而谈“持续推进”“值得关注”，要写清楚为什么重要。
5. 输出语言要像成熟助理给管理层写的周概况，简洁、深入、一针见血。

输出字段：
- overview: 1 到 2 段完整中文总结
- focusLines: 2 到 4 条本周主线
- nextFocus: 1 到 3 条下周重点
"""

WEEKLY_OVERVIEW_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {"type": "string"},
        "focusLines": {"type": "array", "items": {"type": "string"}},
        "nextFocus": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["overview", "focusLines", "nextFocus"],
}


def _week_start_iso(week_label: str) -> str:
    """Convert a week label like '2026-W13' to the Monday ISO date string."""
    from datetime import datetime, timedelta
    try:
        year, week = week_label.split("-W")
        jan4 = datetime(int(year), 1, 4)
        start_of_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
        monday = start_of_w1 + timedelta(weeks=int(week) - 1)
        return monday.strftime("%Y-%m-%d")
    except Exception:
        return "2000-01-01"


def _assemble_context_prompt(
    *,
    org_dna_modules: list[OrganizationDnaModuleRecord],
    client_profile: ClientStrategicProfileRecord | None,
    cooperation: CooperationRelationshipRecord | None,
    weekly_history: list[EventLineWeeklySnapshotRecord],
    event_line_name: str,
    event_line_stage: str,
    event_line_summary: str,
    event_line_intent: str,
    event_line_blocker: str,
    current_tasks: list[WeeklyReviewTaskEntryRecord],
    week_label: str,
    recent_activities: list[dict] | None = None,
) -> tuple[str, list[str]]:
    """组装五层上下文 prompt，返回 (prompt_text, layers_used)。"""
    sections: list[str] = []
    layers_used: list[str] = []

    # 第一层：组织 DNA
    if org_dna_modules:
        dna_text = "\n".join(
            f"- {m.title}: {m.summary or m.normalizedText[:200]}"
            for m in org_dna_modules[:4]
            if m.summary or m.normalizedText
        )
        if dna_text:
            sections.append(f"【第一层：益语智库组织 DNA】\n{dna_text}")
            layers_used.append("organization_dna")

    # 第二层：客户背景
    if client_profile and (client_profile.industry or client_profile.scale or client_profile.currentNeeds):
        parts = []
        if client_profile.industry:
            parts.append(f"行业：{client_profile.industry}")
        if client_profile.scale:
            parts.append(f"规模：{client_profile.scale}")
        if client_profile.influence:
            parts.append(f"影响力：{client_profile.influence}")
        if client_profile.currentNeeds:
            parts.append(f"当前需求：{client_profile.currentNeeds}")
        if client_profile.painPoints:
            parts.append(f"痛点：{client_profile.painPoints}")
        if client_profile.strategicValueToYiyu:
            parts.append(f"对益语的战略价值：{client_profile.strategicValueToYiyu}")
        if client_profile.decisionChain:
            parts.append(f"决策链：{client_profile.decisionChain}")
        sections.append(f"【第二层：客户背景】\n" + "\n".join(f"- {p}" for p in parts))
        layers_used.append("client_profile")

    # 第三层：合作关系
    if cooperation and (cooperation.whyConnected or cooperation.meaningToYiyu):
        parts = []
        if cooperation.whyConnected:
            parts.append(f"为什么接触：{cooperation.whyConnected}")
        if cooperation.meaningToYiyu:
            parts.append(f"对益语意味着：{cooperation.meaningToYiyu}")
        if cooperation.meaningToClient:
            parts.append(f"对客户意味着：{cooperation.meaningToClient}")
        parts.append(f"合作类型：{cooperation.cooperationType}")
        parts.append(f"关系健康度：{cooperation.relationshipHealth}")
        if cooperation.milestones:
            parts.append(f"里程碑：{cooperation.milestones}")
        if cooperation.keyStakeholders:
            stakeholder_text = "、".join(f"{s.name}({s.role})" for s in cooperation.keyStakeholders[:5])
            parts.append(f"关键干系人：{stakeholder_text}")
        sections.append(f"【第三层：益语与客户的合作关系】\n" + "\n".join(f"- {p}" for p in parts))
        layers_used.append("cooperation_relationship")

    # 第四层：事件线跨周历史
    if weekly_history:
        history_lines = []
        for snap in weekly_history[:8]:
            line = f"- {snap.weekLabel}：阶段={snap.stageAtThatTime or '未标记'}，任务{snap.taskCount}条/完成{snap.completedCount}条"
            if snap.keyDecisions:
                line += f"，决定：{'；'.join(snap.keyDecisions[:2])}"
            if snap.blockersThen:
                line += f"，卡点：{'；'.join(snap.blockersThen[:2])}"
            if snap.progressDelta:
                line += f"，进展：{snap.progressDelta}"
            history_lines.append(line)
        sections.append(f"【第四层：事件线历史轨迹（近{len(weekly_history)}周）】\n" + "\n".join(history_lines))
        layers_used.append("event_line_history")

    # 第五层：当前周任务
    task_lines = []
    for item in current_tasks[:10]:
        snap = item.taskSnapshot
        status = getattr(snap, "status", "未知")
        title = getattr(snap, "title", "")
        note = item.note.strip() if item.note else ""
        line = f"- [{status}] {title}"
        if note:
            line += f" — 复盘说明：{note[:100]}"
        task_lines.append(line)
    event_info = f"事件线：{event_line_name}"
    if event_line_stage:
        event_info += f"（阶段：{event_line_stage}）"
    if event_line_summary:
        event_info += f"\n概要：{event_line_summary}"
    if event_line_intent:
        event_info += f"\n意图：{event_line_intent}"
    if event_line_blocker:
        event_info += f"\n当前阻碍：{event_line_blocker}"

    # 事件线本周活动记录（任务状态变更、会议发布、支持请求处理、手动备注）
    activity_text = ""
    if recent_activities:
        activity_lines = []
        for act in recent_activities[:8]:
            act_title = act.get("title", "")
            act_summary = act.get("summary", "")
            act_time = str(act.get("happened_at", ""))[:16].replace("T", " ")
            act_type = act.get("source_type", "")
            activity_lines.append(f"- [{act_type}] {act_title}（{act_time}）：{act_summary[:120]}")
        if activity_lines:
            activity_text = "\n\n本周事件线活动记录：\n" + "\n".join(activity_lines)
            layers_used.append("event_line_activities")

    sections.append(
        f"【第五层：{week_label} 当前任务（共{len(current_tasks)}条）】\n{event_info}\n"
        + ("\n".join(task_lines) if task_lines else "本周暂无任务记录。")
        + activity_text
    )
    layers_used.append("current_tasks")

    prompt = "\n\n".join(sections)
    return prompt, layers_used


def build_narrative_analyses(
    *,
    ai: AiService,
    db: Database,
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
    org_dna_modules: list[OrganizationDnaModuleRecord],
) -> list[NarrativeAnalysisRecord]:
    """为本周涉及的每条事件线生成叙事分析。"""
    from collections import defaultdict

    # 按事件线分组
    groups: dict[str, list[WeeklyReviewTaskEntryRecord]] = defaultdict(list)
    for item in items:
        el_id = getattr(item.taskSnapshot, "eventLineId", None) or ""
        if el_id:
            groups[el_id].append(item)

    if not groups:
        return []

    results: list[NarrativeAnalysisRecord] = []

    for el_id, line_items in groups.items():
        try:
            # 读取事件线基本信息
            el_row = db.fetchone("SELECT * FROM event_lines WHERE id = ?", (el_id,))
            if not el_row:
                continue
            el_name = str(el_row["name"] or "")
            client_id = str(el_row["primary_client_id"] or "")
            client_name = str(el_row["primary_client_name"] or "")

            # 读取客户战略画像
            client_profile: ClientStrategicProfileRecord | None = None
            if client_id:
                profile_row = db.fetchone("SELECT * FROM client_strategic_profiles WHERE client_id = ?", (client_id,))
                if profile_row:
                    client_profile = ClientStrategicProfileRecord(
                        clientId=str(profile_row["client_id"]),
                        industry=str(profile_row["industry"] or ""),
                        scale=str(profile_row["scale"] or ""),
                        influence=str(profile_row["influence"] or ""),
                        currentNeeds=str(profile_row["current_needs"] or ""),
                        painPoints=str(profile_row["pain_points"] or ""),
                        strategicValueToYiyu=str(profile_row["strategic_value_to_yiyu"] or ""),
                        decisionChain=str(profile_row["decision_chain"] or ""),
                        updatedAt=str(profile_row["updated_at"] or ""),
                    )

            # 读取合作关系
            cooperation: CooperationRelationshipRecord | None = None
            if client_id:
                coop_row = db.fetchone("SELECT * FROM cooperation_relationships WHERE client_id = ?", (client_id,))
                if coop_row:
                    cooperation = CooperationRelationshipRecord(
                        id=str(coop_row["id"]),
                        clientId=str(coop_row["client_id"]),
                        clientName=str(coop_row["client_name"] or ""),
                        whyConnected=str(coop_row["why_connected"] or ""),
                        meaningToYiyu=str(coop_row["meaning_to_yiyu"] or ""),
                        meaningToClient=str(coop_row["meaning_to_client"] or ""),
                        cooperationType=str(coop_row["cooperation_type"] or "exploring"),
                        relationshipHealth=str(coop_row["relationship_health"] or "steady"),
                        keyStakeholders=json.loads(str(coop_row["key_stakeholders_json"] or "[]")),
                        milestones=str(coop_row["milestones"] or ""),
                        startedAt=str(coop_row["started_at"] or ""),
                        updatedAt=str(coop_row["updated_at"] or ""),
                    )

            # 读取事件线跨周历史
            history_rows = db.fetchall(
                "SELECT * FROM event_line_weekly_snapshots WHERE event_line_id = ? ORDER BY week_label DESC LIMIT 13",
                (el_id,),
            )
            weekly_history = [
                EventLineWeeklySnapshotRecord(
                    id=str(r["id"]),
                    eventLineId=str(r["event_line_id"]),
                    eventLineName=str(r["event_line_name"] or ""),
                    weekLabel=str(r["week_label"]),
                    stageAtThatTime=str(r["stage_at_that_time"] or ""),
                    keyDecisions=json.loads(str(r["key_decisions_json"] or "[]")),
                    turningPoints=json.loads(str(r["turning_points_json"] or "[]")),
                    blockersThen=json.loads(str(r["blockers_then_json"] or "[]")),
                    progressDelta=str(r["progress_delta"] or ""),
                    taskCount=int(r["task_count"] or 0),
                    completedCount=int(r["completed_count"] or 0),
                    createdAt=str(r["created_at"] or ""),
                )
                for r in history_rows
            ]

            # 读取事件线本周活动记录
            activity_rows = db.fetchall(
                """
                SELECT source_type, title, summary, happened_at
                FROM event_line_activities
                WHERE event_line_id = ? AND happened_at >= ?
                ORDER BY happened_at DESC
                LIMIT 10
                """,
                (el_id, _week_start_iso(week_label)),
            )
            recent_activities = [dict(r) for r in activity_rows] if activity_rows else []

            # 组装 prompt
            prompt, layers_used = _assemble_context_prompt(
                org_dna_modules=org_dna_modules,
                client_profile=client_profile,
                cooperation=cooperation,
                weekly_history=weekly_history,
                event_line_name=el_name,
                event_line_stage=str(el_row["stage"] or ""),
                event_line_summary=str(el_row["summary"] or ""),
                event_line_intent=str(el_row["intent"] or ""),
                event_line_blocker=str(el_row["current_blocker"] or ""),
                current_tasks=line_items,
                week_label=week_label,
                recent_activities=recent_activities,
            )

            # 调用 LLM
            try:
                raw = ai._qwen_generate(
                    prompt=prompt,
                    system_instruction=NARRATIVE_SYSTEM_INSTRUCTION,
                    response_schema=NARRATIVE_RESPONSE_SCHEMA,
                    timeout_seconds=45.0,
                    max_tokens=1500,
                    temperature=0.3,
                )
            except Exception:
                # fallback: 如果 qwen 不可用，尝试 gemini
                try:
                    raw = ai._gemini_generate(
                        prompt=(
                            "请严格返回一个 JSON 对象，不要使用 Markdown。\n"
                            f"{json.dumps(NARRATIVE_RESPONSE_SCHEMA, ensure_ascii=False)}\n\n"
                            f"{prompt}"
                        ),
                        system_instruction=NARRATIVE_SYSTEM_INSTRUCTION,
                        response_schema=None,
                    )
                    if isinstance(raw, str):
                        raw = json.loads(raw)
                except Exception:
                    raw = None

            if not raw or not isinstance(raw, dict):
                # 无法调用 LLM，生成保守的规则兜底
                results.append(NarrativeAnalysisRecord(
                    eventLineId=el_id,
                    eventLineName=el_name,
                    clientId=client_id or None,
                    clientName=client_name or None,
                    whatThisIs=f"事件线「{el_name}」本周共涉及 {len(line_items)} 条任务。",
                    whyImportant="系统当前无法调用 AI 服务，暂时只能展示基本事实。",
                    currentProgress=f"阶段：{el_row['stage'] or '未标记'}",
                    missingUnderstanding="AI 分析服务暂不可用，建议检查 AI 配置后重新生成。",
                    contextLayersUsed=layers_used,
                    confidenceLevel="low",
                ))
                continue

            results.append(NarrativeAnalysisRecord(
                eventLineId=el_id,
                eventLineName=el_name,
                clientId=client_id or None,
                clientName=client_name or None,
                whatThisIs=str(raw.get("whatThisIs", "")),
                whyImportant=str(raw.get("whyImportant", "")),
                currentProgress=str(raw.get("currentProgress", "")),
                missingUnderstanding=str(raw.get("missingUnderstanding", "")),
                riskNote=str(raw.get("riskNote", "")) or None,
                timeGate=str(raw.get("timeGate", "")) or None,
                minimumAction=str(raw.get("minimumAction", "")) or None,
                managementAdvice=str(raw.get("managementAdvice", "")) or None,
                contextLayersUsed=layers_used,
                confidenceLevel=str(raw.get("confidenceLevel", "low")),
            ))

        except Exception as exc:
            logger.warning("Narrative analysis failed for event line %s: %s", el_id, exc)
            continue

    return results


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _dedupe_lines(values: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _organization_background_preview(org_dna_modules: list[OrganizationDnaModuleRecord]) -> str:
    lines: list[str] = []
    for module in org_dna_modules:
        if module.moduleKey not in {"organization_intro", "business_intro"}:
            continue
        text = _clean_text(module.summary or module.normalizedText[:220])
        if text:
            lines.append(f"- {module.title}: {text}")
        if len(lines) >= 3:
            break
    return "\n".join(lines)


def _weekly_overview_task_lines(items: list[WeeklyReviewTaskEntryRecord]) -> str:
    lines: list[str] = []
    for item in items[:12]:
        snap = item.taskSnapshot
        parts = [snap.title]
        if snap.clientName:
            parts.append(f"客户={snap.clientName}")
        if snap.eventLineName:
            parts.append(f"事件线={snap.eventLineName}")
        desc = _clean_text(getattr(snap, "desc", "") or "")
        note = _clean_text(getattr(snap, "note", "") or item.note or "")
        if desc:
            parts.append(f"说明={desc[:100]}")
        elif note:
            parts.append(f"备注={note[:100]}")
        lines.append("- " + "；".join(parts))
    return "\n".join(lines)


def _narrative_summary_lines(narratives: list[NarrativeAnalysisRecord]) -> str:
    lines: list[str] = []
    for narrative in narratives[:6]:
        parts = [
            f"{narrative.eventLineName or narrative.eventLineId}",
            f"这是什么事：{_clean_text(narrative.whatThisIs)}" if narrative.whatThisIs else "",
            f"为什么重要：{_clean_text(narrative.whyImportant)}" if narrative.whyImportant else "",
            f"推进到哪：{_clean_text(narrative.currentProgress)}" if narrative.currentProgress else "",
            f"还缺什么理解：{_clean_text(narrative.missingUnderstanding)}" if narrative.missingUnderstanding else "",
        ]
        lines.append("- " + "；".join(part for part in parts if part))
    return "\n".join(lines)


def _client_background_map(org_dna_modules: list[OrganizationDnaModuleRecord]) -> dict[str, str]:
    backgrounds: dict[str, str] = {}
    for module in org_dna_modules:
        title = _clean_text(module.title)
        text = _clean_text(module.summary or module.normalizedText[:220])
        if not title or not text:
            continue
        if title.endswith("业务背景"):
            client_name = title[: -len("业务背景")].strip()
            if client_name:
                backgrounds[client_name] = text
    return backgrounds


def _task_text(item: WeeklyReviewTaskEntryRecord) -> str:
    snap = item.taskSnapshot
    return _clean_text(
        " ".join(
            part
            for part in [
                snap.title,
                snap.clientName or "",
                snap.eventLineName or "",
                getattr(snap, "desc", "") or "",
                getattr(snap, "note", "") or item.note or "",
            ]
            if str(part or "").strip()
        )
    )


def _infer_line_bucket(item: WeeklyReviewTaskEntryRecord) -> tuple[str, str]:
    snap = item.taskSnapshot
    text = _task_text(item).lower()
    client_name = _clean_text(snap.clientName or "")
    event_line_name = _clean_text(snap.eventLineName or "")
    event_line_id = _clean_text(snap.eventLineId or "")
    if event_line_id or event_line_name:
        base_name = event_line_name or snap.title
        if client_name and client_name not in base_name:
            return (f"event_line::{event_line_id or base_name}", f"{client_name} · {base_name}")
        return (f"event_line::{event_line_id or base_name}", base_name)
    if client_name:
        return (f"client::{client_name}", f"{client_name} 推进线")
    if any(keyword in text for keyword in SOFTWARE_LINE_KEYWORDS):
        return ("semantic::software", "软件底层修复与验证线")
    if any(keyword in text for keyword in INTEL_LINE_KEYWORDS):
        return ("semantic::intel", "情报沉淀与产品化线")
    if any(keyword in text for keyword in COLLAB_LINE_KEYWORDS):
        return ("semantic::collab", "行业连接与协作探索线")
    return (f"task::{snap.title}", snap.title)


def _line_progress_from_items(items: list[WeeklyReviewTaskEntryRecord], narrative: NarrativeAnalysisRecord | None) -> str:
    if narrative and _clean_text(narrative.currentProgress):
        return _clean_text(narrative.currentProgress)
    statuses = [str(item.taskSnapshot.status or "").strip().lower() for item in items]
    completed_count = sum(1 for status in statuses if status == "done")
    if completed_count == len(items) and items:
        return "这条线本周已经有明确推进，但还处在把结果进一步收束成正式输出的阶段。"
    if completed_count > 0:
        return "这条线已经从泛推进进入更具体的说明、校准或方案收束阶段。"
    return "这条线仍处在推进中的早中段，已经有动作，但还没有完全收束成明确结果。"


def _line_gap_from_items(items: list[WeeklyReviewTaskEntryRecord], narrative: NarrativeAnalysisRecord | None) -> str:
    if narrative and _clean_text(narrative.missingUnderstanding):
        return _clean_text(narrative.missingUnderstanding)
    next_actions: list[str] = []
    blockers: list[str] = []
    for item in items:
        structured = getattr(item, "structuredNote", None)
        for value in [
            getattr(structured, "nextAction", "") if structured else "",
            getattr(item.taskSnapshot, "nextAction", "") or "",
        ]:
            cleaned = _clean_text(value)
            if cleaned and cleaned not in next_actions:
                next_actions.append(cleaned)
        for value in [
            getattr(structured, "blockerReason", "") if structured else "",
            getattr(item.taskSnapshot, "currentBlocker", "") or "",
        ]:
            cleaned = _clean_text(value)
            if cleaned and cleaned not in blockers:
                blockers.append(cleaned)
    if next_actions:
        return f"接下来最缺的是把这条线收成明确动作：{next_actions[0]}"
    if blockers:
        return f"接下来最缺的是把当前卡点讲清楚并收束：{blockers[0]}"
    return "接下来最缺的不是新增动作，而是把已有推进收成更清楚的边界、产出和后续安排。"


def _line_score(items: list[WeeklyReviewTaskEntryRecord], line_name: str, why_it_matters: str) -> float:
    text = _clean_text(" ".join([line_name, why_it_matters, *(_task_text(item) for item in items)])).lower()
    strategic_leverage = 0.45
    if "cffc" in text or "枢纽" in text or "基金会网络" in text:
        strategic_leverage = 0.95
    elif "软件" in line_name or "底层" in line_name or "codex" in text:
        strategic_leverage = 0.86
    elif "日慈" in text or "为爱黔行" in text:
        strategic_leverage = 0.78
    elif "情报" in line_name or "心理友好" in text or "开源社区" in text:
        strategic_leverage = 0.74
    progress_evidence = min(1.0, len(items) / 3.0)
    output_clarity = 0.45
    if any(_clean_text(getattr(item.taskSnapshot, "nextAction", "") or "") for item in items):
        output_clarity += 0.2
    if any(_clean_text(item.note) for item in items):
        output_clarity += 0.15
    if any(_clean_text(getattr(item.taskSnapshot, "recentDecision", "") or "") for item in items):
        output_clarity += 0.2
    productization_potential = 0.35
    if "软件" in line_name or "情报" in line_name or "开源" in text or "心理友好" in text:
        productization_potential = 0.9
    evidence_strength = min(
        1.0,
        sum(
            max(1, int(getattr(item.taskSnapshot, "evidenceCount", 0) or 0))
            for item in items
        )
        / 8.0,
    )
    score = (
        0.35 * strategic_leverage
        + 0.25 * progress_evidence
        + 0.20 * min(output_clarity, 1.0)
        + 0.10 * productization_potential
        + 0.10 * evidence_strength
    )
    return round(score, 3)


def _build_weekly_line_cards(
    items: list[WeeklyReviewTaskEntryRecord],
    org_dna_modules: list[OrganizationDnaModuleRecord],
    narratives: list[NarrativeAnalysisRecord],
) -> list[WeeklyLineCard]:
    if not items:
        return []
    grouped_items: dict[str, dict[str, object]] = {}
    narrative_by_line: dict[str, NarrativeAnalysisRecord] = {}
    for narrative in narratives:
        if narrative.eventLineId:
            narrative_by_line[f"event_line::{narrative.eventLineId}"] = narrative
        if narrative.eventLineName:
            narrative_by_line.setdefault(f"event_line::{narrative.eventLineName}", narrative)
    client_backgrounds = _client_background_map(org_dna_modules)
    for item in items:
        bucket_key, line_name = _infer_line_bucket(item)
        bucket = grouped_items.setdefault(bucket_key, {"line_name": line_name, "items": []})
        bucket["items"].append(item)  # type: ignore[index]

    line_cards: list[WeeklyLineCard] = []
    for bucket_key, bucket in grouped_items.items():
        line_name = str(bucket["line_name"])
        bucket_items = list(bucket["items"])  # type: ignore[arg-type]
        primary_item = bucket_items[0]
        narrative = narrative_by_line.get(bucket_key)
        if narrative is None and primary_item.taskSnapshot.eventLineName:
            narrative = narrative_by_line.get(f"event_line::{primary_item.taskSnapshot.eventLineName}")
        task_titles = "、".join(item.taskSnapshot.title for item in bucket_items[:3])
        client_name = _clean_text(primary_item.taskSnapshot.clientName or "")
        client_bg = client_backgrounds.get(client_name, "")

        if narrative and _clean_text(narrative.whatThisIs):
            what_happened = _clean_text(narrative.whatThisIs)
        elif line_name == "软件底层修复与验证线":
            what_happened = f"这周围绕 {task_titles} 等事项，集中排查并修复了附件保存、上传写入和任务可见性等底层链路问题。"
        elif line_name == "情报沉淀与产品化线":
            what_happened = f"这周把 {task_titles} 这类外部信号收进系统，开始从资讯吸收转向咨询议题和产品切口沉淀。"
        else:
            what_happened = f"这周围绕 {task_titles} 等事项持续推进，已经不只是零散接触，而是在形成一条更清楚的业务推进线。"

        if narrative and _clean_text(narrative.whyImportant):
            why_it_matters = _clean_text(narrative.whyImportant)
        elif client_bg:
            why_it_matters = client_bg
        elif "cffc" in _clean_text(line_name).lower():
            why_it_matters = "这条线的重要性不只是一次普通合作，而是通过公益行业关键枢纽去打开更大基金会网络的入口。"
        elif line_name == "软件底层修复与验证线":
            why_it_matters = "这条线表面上像在 debug，实际上是在给益语的数字化工作台补地基；地基不稳，后续判断、交付和客户体验都站不住。"
        elif line_name == "情报沉淀与产品化线":
            why_it_matters = "这条线的意义不在资讯本身，而在于把外部变化转成益语后续的咨询议题、产品方向和客户对话素材。"
        else:
            why_it_matters = "这条线的重要性在于，它直接关系到益语能否把当前的关系推进成更清楚的合作、诊断或交付。"

        progress_now = _line_progress_from_items(bucket_items, narrative)
        next_gap_or_need = _line_gap_from_items(bucket_items, narrative)
        line_cards.append(
            WeeklyLineCard(
                line_name=line_name,
                score=_line_score(bucket_items, line_name, why_it_matters),
                what_happened=what_happened,
                why_it_matters=why_it_matters,
                progress_now=progress_now,
                next_gap_or_need=next_gap_or_need,
            )
        )

    line_cards.sort(key=lambda item: (-item.score, item.line_name))
    return line_cards[:5]


def _weekly_line_card_lines(line_cards: list[WeeklyLineCard]) -> str:
    lines: list[str] = []
    for card in line_cards:
        lines.append(
            "\n".join(
                [
                    f"- {card.line_name}（score={card.score}）",
                    f"  这周发生了什么：{card.what_happened}",
                    f"  为什么重要：{card.why_it_matters}",
                    f"  现在推进到哪：{card.progress_now}",
                    f"  还缺什么理解：{card.next_gap_or_need}",
                ]
            )
        )
    return "\n".join(lines)


def build_weekly_overview_draft(
    *,
    ai: AiService,
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
    org_dna_modules: list[OrganizationDnaModuleRecord],
    narratives: list[NarrativeAnalysisRecord],
    fallback_overview: str,
    fallback_focus_lines: list[str],
    fallback_next_focus: list[str],
) -> tuple[str, list[str], list[str]]:
    fallback_focus = _dedupe_lines(fallback_focus_lines, limit=4)
    fallback_next = _dedupe_lines(fallback_next_focus, limit=3)
    fallback_summary = _clean_text(fallback_overview)
    line_cards = _build_weekly_line_cards(items, org_dna_modules, narratives)
    health = ai.get_health()
    if health.provider == "mock" or not health.ready:
        return fallback_summary, fallback_focus, fallback_next

    prompt = "\n\n".join(
        part
        for part in [
            f"【周标签】\n{week_label}",
            f"【规则兜底草稿】\n{fallback_summary}",
            f"【规则识别的主线】\n" + "\n".join(f"- {line}" for line in fallback_focus) if fallback_focus else "",
            f"【主线理解卡】\n{_weekly_line_card_lines(line_cards)}" if line_cards else "",
            f"【组织背景】\n{_organization_background_preview(org_dna_modules)}",
            f"【事件线叙事】\n{_narrative_summary_lines(narratives)}" if narratives else "",
            f"【本周任务与线索】\n{_weekly_overview_task_lines(items)}",
        ]
        if part
    )

    try:
        if health.provider == "qwen":
            raw = ai._qwen_generate(
                prompt=prompt,
                system_instruction=WEEKLY_OVERVIEW_SYSTEM_INSTRUCTION,
                response_schema=WEEKLY_OVERVIEW_RESPONSE_SCHEMA,
                timeout_seconds=45.0,
                max_tokens=1800,
                temperature=0.35,
                top_p=0.9,
                enable_thinking=False,
            )
        else:
            raw = ai._gemini_generate(
                prompt=prompt,
                system_instruction=WEEKLY_OVERVIEW_SYSTEM_INSTRUCTION,
                response_schema=WEEKLY_OVERVIEW_RESPONSE_SCHEMA,
            )
        if not isinstance(raw, dict):
            return fallback_summary, fallback_focus, fallback_next
        overview = _clean_text(str(raw.get("overview") or ""))
        focus_lines = _dedupe_lines([str(item) for item in raw.get("focusLines") or []], limit=4)
        next_focus = _dedupe_lines([str(item) for item in raw.get("nextFocus") or []], limit=3)
        if not ai._has_sufficient_cjk(overview) or len(overview) < 80:
            return fallback_summary, fallback_focus, fallback_next
        if not focus_lines:
            focus_lines = fallback_focus
        if not next_focus:
            next_focus = fallback_next
        return overview, focus_lines, next_focus
    except Exception as exc:
        logger.warning("Weekly overview generation failed: %s", exc)
        return fallback_summary, fallback_focus, fallback_next
