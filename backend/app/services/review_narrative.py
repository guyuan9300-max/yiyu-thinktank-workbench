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

from collections.abc import Iterable
import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.db import Database
    from app.services.ai import AiService

from app.models import (
    ClientStrategicProfileRecord,
    CooperationRelationshipRecord,
    EventLineWeeklySnapshotRecord,
    NarrativeAnalysisRecord,
    OrganizationDnaModuleRecord,
    WeeklyEventReviewCardRecord,
    WeeklyEventReviewCardsRecord,
    WeeklyMainlineCardRecord,
    WeeklyMainlineCardsRecord,
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
你是益语智库的周复盘写作助手，为管理层生成结构化的周概况。

信息权重（从高到低）：
1. 用户手写的周复盘说明（最可信的一手判断）
2. 会议纪要和附件内容（包含具体讨论细节、决策、下一步，是最有深度的信息源）
3. 事件线管理字段（卡点、决策、下一步）
4. 任务的卡点和下一步
5. 事件线叙事分析
6. 组织 DNA 背景（用于解释"为什么重要"，不要照搬）

写作规则：
1. headline: 用一句话定性这一周，必须包含一个具体事实（如"日慈教师赋能完成Q1复盘，为爱黔行创始人分歧待协调"），不要泛泛说"持续推进""取得进展"。
2. needsAttention: 只列需要管理层关注的事件线，reason 必须引用一个具体事实（人名、事件、数据），不要抽象概括。
3. onTrack: 正常推进的事件线，一句话说明本周具体完成了什么。
4. blockerSummary: 必须写具体的卡点——谁卡住了、卡在什么事上、为什么卡。如果多条线有类似卡点就对比说明。如果没有明确卡点就留空字符串，不要编造。
5. nextWeekHint: 必须是一个可执行的管理建议，包含具体的人/事/时间。例如"下周五前让高老师交品牌规划，否则日慈Q2节奏会延迟"。不要写"优先收束""聚焦存量"这种没有行动对象的空话。
6. nextWeekFocus: 每条必须包含：做什么 + 谁来做 + 什么时候要结果。

核心原则：
- 每一句话都必须有事实支撑，能从输入材料里找到出处
- 如果材料里没有足够信息支撑某个判断，就不要写，留空比编造好
- 宁可少写两条有信息量的，也不要多写五条空话

禁止：
- 不要输出覆盖率、置信度、样本量等元信息
- 不要用"值得关注""持续推进""成果收束""合作边界""明确落地方案"等抽象表述
- 不要把不同事件线的卡点抽象成一句话——每个卡点都是独立的，分开写
"""

WEEKLY_OVERVIEW_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "一句话定性本周"},
        "needsAttention": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lineName": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["lineName", "reason"],
            },
            "description": "需要管理层关注的事件线",
        },
        "onTrack": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lineName": {"type": "string"},
                    "progress": {"type": "string"},
                },
                "required": ["lineName", "progress"],
            },
            "description": "正常推进的事件线",
        },
        "blockerSummary": {"type": "array", "items": {"type": "string"}, "description": "卡点列表，每条一个具体卡点，没有就留空数组"},
        "nextWeekHint": {"type": "string", "description": "本周管理洞察"},
        "nextWeekFocus": {"type": "array", "items": {"type": "string"}, "description": "下周重点"},
    },
    "required": ["headline", "needsAttention", "onTrack", "blockerSummary", "nextWeekHint", "nextWeekFocus"],
}

WEEKLY_MAINLINE_INTERNAL_TERMS = (
    "客户DNA",
    "数据中心",
    "附件未读",
    "系统不能假装理解",
    "证据包",
    "内部诊断",
)
WEEKLY_MAINLINE_BANNED_PHRASES = (
    "继续推进",
    "推进收束",
    "沉淀为可复用记录",
    "开放风险",
    "判断是否闭环",
    "整体完成度较高",
    "明确负责人、交付物和完成时间",
    "避免只停留在任务完成状态",
)
WEEKLY_MAINLINE_ACTION_KEYWORDS = (
    "完成",
    "确认",
    "核对",
    "整理",
    "补充",
    "输出",
    "重写",
    "拆分",
    "发起",
    "对接",
    "明确",
    "导出",
    "提交",
    "安排",
    "更新",
    "定稿",
    "列出",
    "锁定",
    "校准",
    "约",
)

WEEKLY_MAINLINE_SYSTEM_INSTRUCTION = """\
你是益语智库的周复盘主线卡写作助手。你会收到本周任务、任务复盘、关联材料摘要、项目/客户背景和事件线字段。

输出目标：
1. 生成一个本周总览 summaryText。
2. 选择最多 6 条重点主线（按重要性排序，常见 3-5 条；真有更多独立主线再多放，宁可少不可凑数），每条只写两个段落：progressText（本周推进）和 nextGoalText（下一步目标）。

写作规则：
- progressText 写 2-4 句，必须说明：做了什么、推进到什么阶段、这件事对业务/交付/合作有什么意义。
- nextGoalText 写 2-3 句，必须是 action，必须说明：优先做什么、为什么现在做、产出标准是什么。
- 主线必须围绕项目状态变化写，不要只把任务标题串起来；优先写“从准备到交付”“从功能完成到表达校准”“从名单整理到落地安排”这类阶段变化。
- 如果需要用户补充资料，必须写清楚“补什么”和“补齐后能带来什么价值”。例如：补材料文字大纲后，可以判断版本是否服务资方决策、客户沟通或内部执行。
- 如果材料不足，不要假装已经理解材料内容；直接把下一步写成补齐资料、负责人、交付物和完成时间的动作。
- 不要输出资料来源、读取状态、内部诊断、模型置信度。

禁止输出：
- 客户DNA、数据中心、附件未读、系统不能假装理解、证据包、内部诊断
- 继续推进、推进收束、沉淀为可复用记录、开放风险、判断是否闭环、整体完成度较高、明确负责人、交付物和完成时间、避免只停留在任务完成状态
- 没有证据支撑的具体功能或动作，例如输入里没有“下载按钮”，就不能写“上线下载按钮”。
"""

WEEKLY_MAINLINE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summaryText": {"type": "string", "description": "本周总览，2-3句"},
        "mainlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "taskCount": {"type": "integer"},
                    "completedCount": {"type": "integer"},
                    "pendingCount": {"type": "integer"},
                    "progressText": {"type": "string"},
                    "nextGoalText": {"type": "string"},
                },
                "required": ["title", "taskCount", "completedCount", "pendingCount", "progressText", "nextGoalText"],
            },
            "description": "最多6条重点主线（按重要性排序，宁可少不凑数）",
        },
    },
    "required": ["summaryText", "mainlines"],
}

WEEKLY_EVENT_REVIEW_BANNED_PHRASES = (
    *WEEKLY_MAINLINE_BANNED_PHRASES,
    "持续推进",
    "夯实",
    "闭环",
    "打下坚实基础",
    "坚实基础",
    "统一复盘",
    "下一步动作",
    "补充资料",
    "请回答以下问题",
    "请逐条回答",
    "复盘正文",
)

WEEKLY_EVENT_REVIEW_SYSTEM_INSTRUCTION = """\
你是益语智库的事件复盘整理助手。你的任务不是代替用户写复盘，而是把候选事件复盘卡改成更自然的事项标题，并为复盘输入框生成灰色提示。

重要边界：
- 必须保留输入候选卡的 taskIds 集合；不要合并候选卡，不要拆分候选卡，不要新增或遗漏任务。
- 每张卡只输出 title、reflectionPromptText 和 confidence；不要输出复盘正文，不要输出下一步动作。
- title 要像一个真实的复盘事项，例如“云南儿童资助研究材料调整”。
- reflectionPromptText 写 2-4 句开放提醒，放在输入框 placeholder 里使用；要贴合该项目，但不强迫用户逐条回答。
- 提醒可以启发用户想：这组任务完成后项目状态有什么变化、还缺哪个判断、下周最小动作、负责人/交付物/时间点是否需要确认。
- 用“可以回想一下…”“也可以顺手想想…”这类开放口吻，不要写成表单题或汇报结论。

禁止输出：
- 客户DNA、数据中心、附件未读、系统不能假装理解、证据包、内部诊断
- 统一复盘、下一步动作、补充资料、请回答以下问题、请逐条回答
- 继续推进、持续推进、推进收束、沉淀为可复用记录、开放风险、判断是否闭环、夯实、闭环、打下坚实基础
"""

WEEKLY_EVENT_REVIEW_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "cardKind": {"type": "string", "enum": ["event_line", "task_cluster", "single_task", "needs_assignment"]},
                    "taskIds": {"type": "array", "items": {"type": "string"}},
                    "reflectionPromptText": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["id", "title", "cardKind", "taskIds", "reflectionPromptText", "confidence"],
            },
        },
    },
    "required": ["cards"],
}


def _weekly_mainline_row_value(row: Any, key: str, default: Any = "") -> Any:
    try:
        value = row[key]
    except Exception:
        return default
    return default if value is None else value


def _weekly_mainline_clean(value: Any, *, limit: int | None = None) -> str:
    text = str(value or "").replace("\u3000", " ")
    text = " ".join(text.split())
    if limit is not None and len(text) > limit:
        return f"{text[: max(0, limit - 1)]}…"
    return text


def _weekly_mainline_first_text(values: list[Any], *, min_length: int = 12, limit: int = 900) -> str:
    for value in values:
        cleaned = _weekly_mainline_clean(value, limit=limit)
        if len(cleaned) >= min_length and "提取失败" not in cleaned and "No module" not in cleaned:
            return cleaned
    return ""


def _weekly_mainline_material_suggestion(title: str, kind: str) -> str:
    lower = f"{title} {kind}".lower()
    if any(token in lower for token in ("ppt", "pptx", "keynote", "演示", "路演")):
        return (
            "建议补充这份演示材料的文字大纲或导出的 PDF；补齐后可以判断材料是否服务资方决策、"
            "客户沟通或内部执行，并把下一步改成具体修改清单。"
        )
    if any(token in lower for token in ("pdf", "报告", "方案", "说明")):
        return (
            "建议补充可复制的报告目录、摘要或关键结论；补齐后可以判断当前版本是否已经满足交付对象的阅读和决策需要。"
        )
    return (
        "建议补充这份材料的文字摘要、使用对象和期望产出；补齐后可以把复盘从任务完成状态推进到交付价值判断。"
    )


def _weekly_mainline_task_lookup_ids(db: Database, task_ids: list[str]) -> dict[str, str]:
    lookup: dict[str, str] = {task_id: task_id for task_id in task_ids}
    if not task_ids:
        return lookup
    placeholders = ",".join("?" for _ in task_ids)
    try:
        rows = db.fetchall(
            f"""
            SELECT id, cloud_id
            FROM tasks
            WHERE (id IN ({placeholders}) OR cloud_id IN ({placeholders}))
              AND COALESCE(scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
            """,
            tuple([*task_ids, *task_ids]),
        )
    except Exception:
        return lookup
    for row in rows:
        local_id = str(_weekly_mainline_row_value(row, "id", "") or "")
        cloud_id = str(_weekly_mainline_row_value(row, "cloud_id", "") or "")
        canonical = local_id if local_id in lookup else cloud_id if cloud_id in lookup else local_id
        if local_id:
            lookup[local_id] = canonical
        if cloud_id:
            lookup[cloud_id] = canonical
    return lookup


def _weekly_mainline_task_descriptions(db: Database, task_ids: list[str]) -> dict[str, str]:
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    try:
        rows = db.fetchall(
            f"""
            SELECT id, description
            FROM tasks
            WHERE id IN ({placeholders})
              AND COALESCE(scope_mode, 'COLLAB_SHARED') != 'PERSONAL_ONLY'
            """,
            tuple(task_ids),
        )
    except Exception:
        return {}
    return {
        str(_weekly_mainline_row_value(row, "id", "") or ""): _weekly_mainline_clean(
            _weekly_mainline_row_value(row, "description", ""),
            limit=240,
        )
        for row in rows
        if str(_weekly_mainline_row_value(row, "id", "") or "")
    }


def build_weekly_mainline_evidence_pack(
    *,
    db: Database,
    data_dir: Any,
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
    include_data_center: bool = True,
    access_context: Any | None = None,
) -> dict[str, Any]:
    task_ids = sorted({str(item.taskId) for item in items if str(item.taskId or "").strip()})
    task_lookup = _weekly_mainline_task_lookup_ids(db, task_ids)
    task_descriptions = _weekly_mainline_task_descriptions(db, task_ids)
    item_by_lookup_id: dict[str, WeeklyReviewTaskEntryRecord] = {}
    for item in items:
        item_by_lookup_id[str(item.taskId)] = item
    for lookup_id, canonical_id in task_lookup.items():
        item = item_by_lookup_id.get(canonical_id)
        if item is not None:
            item_by_lookup_id[lookup_id] = item

    task_records: list[dict[str, Any]] = []
    client_names: dict[str, str] = {}
    client_ids: list[str] = []
    for item in items:
        snap = item.taskSnapshot
        structured = item.structuredNote
        project = snap.projectContext
        event_context = snap.eventLineContext
        client_id = (
            snap.clientId
            or (project.clientId if project else None)
            or (event_context.primaryClientId if event_context else None)
            or ""
        )
        client_name = (
            snap.clientName
            or (project.clientName if project else None)
            or (event_context.primaryClientName if event_context else None)
            or ""
        )
        if client_id and client_id not in client_ids:
            client_ids.append(client_id)
        if client_id and client_name:
            client_names[client_id] = client_name
        task_records.append(
            {
                "taskId": item.taskId,
                "title": snap.title,
                "status": str(snap.status),
                "clientId": client_id,
                "clientName": client_name,
                "eventLineId": snap.eventLineId or (event_context.id if event_context else "") or "",
                "eventLineName": snap.eventLineName or (event_context.name if event_context else "") or "",
                "taskDescription": task_descriptions.get(item.taskId, ""),
                "reviewNote": item.note,
                "structuredNote": {
                    "reflection": structured.reflection,
                    "progress": structured.progress,
                    "successExperience": structured.successExperience,
                    "blockerReason": structured.blockerReason,
                    "failureInsight": structured.failureInsight,
                    "supportNeeded": structured.supportNeeded,
                    "nextAction": structured.nextAction,
                    "completionStatus": structured.completionStatus,
                },
                "projectContext": {
                    "backgroundSummary": project.backgroundSummary if project else "",
                    "goalSummary": project.goalSummary if project else "",
                    "riskSummary": project.riskSummary if project else "",
                    "currentFocus": project.currentFocus if project else "",
                    "currentBlocker": project.currentBlocker if project else "",
                    "nextAction": project.nextAction if project else "",
                    "recentProgress": project.recentProgress if project else "",
                },
                "eventLineContext": {
                    "summary": event_context.summary if event_context else "",
                    "intent": event_context.intent if event_context else "",
                    "currentBlocker": event_context.currentBlocker if event_context else "",
                    "recentDecision": event_context.recentDecision if event_context else "",
                    "nextStep": event_context.nextStep if event_context else "",
                    "stage": event_context.stage if event_context else "",
                },
            }
        )

    material_pack: dict[str, Any] | None = None
    if include_data_center:
        try:
            from app.services.weekly_review_material_pack import build_weekly_review_material_pack

            material_pack = build_weekly_review_material_pack(
                db=db,
                data_dir=data_dir,
                access_context=access_context,
                week_label=week_label,
                work_items=items,
                task_ids=task_ids,
            )
        except Exception as exc:
            logger.warning("Weekly review material pack build failed: %s", exc)
            material_pack = None

    if material_pack and material_pack.get("tasks"):
        material_tasks = {
            str(task.get("taskId") or ""): task
            for task in material_pack.get("tasks") or []
            if isinstance(task, dict) and str(task.get("taskId") or "")
        }
        for record in task_records:
            material_task = material_tasks.get(str(record.get("taskId") or ""))
            if not isinstance(material_task, dict):
                continue
            for key, material_key in [
                ("clientId", "clientId"),
                ("clientName", "clientName"),
                ("eventLineId", "eventLineId"),
                ("eventLineName", "eventLineName"),
                ("taskDescription", "description"),
            ]:
                if not record.get(key) and material_task.get(material_key):
                    record[key] = material_task.get(material_key)
            for key in ["currentBlocker", "nextAction", "recentDecision", "ownerName", "dueDate"]:
                if material_task.get(key):
                    record[key] = material_task.get(key)

    attachments: list[dict[str, Any]] = []
    lookup_ids = sorted(task_lookup.keys())
    if material_pack and material_pack.get("attachments"):
        for item in material_pack.get("attachments") or []:
            if not isinstance(item, dict):
                continue
            row_task_id = str(item.get("taskId") or "")
            attachments.append(
                {
                    "attachmentId": str(item.get("attachmentId") or ""),
                    "sourceTable": str(item.get("sourceTable") or ""),
                    "taskId": row_task_id,
                    "canonicalTaskId": task_lookup.get(row_task_id, row_task_id),
                    "taskTitle": str(item.get("taskTitle") or ""),
                    "clientId": str(item.get("clientId") or ""),
                    "eventLineId": str(item.get("eventLineId") or ""),
                    "documentId": str(item.get("documentId") or ""),
                    "title": _weekly_mainline_clean(item.get("title"), limit=90),
                    "kind": _weekly_mainline_clean(item.get("kind"), limit=40),
                    "createdAt": str(item.get("createdAt") or ""),
                    "documentUpdatedAt": str(item.get("documentUpdatedAt") or ""),
                    "contentHash": str(item.get("contentHash") or ""),
                    "parseStatus": str(item.get("parseStatus") or ""),
                    "readableText": _weekly_mainline_clean(item.get("summary"), limit=1200),
                    "suggestedMaterial": "" if item.get("summary") else _weekly_mainline_material_suggestion(str(item.get("title") or ""), str(item.get("kind") or "")),
                }
            )
    elif lookup_ids:
        placeholders = ",".join("?" for _ in lookup_ids)
        attachment_sql = f"""
            SELECT
                'task_attachments' AS source_table,
                a.id,
                a.task_id,
                a.client_id,
                a.event_line_id,
                a.document_id,
                a.title,
                a.path,
                a.kind,
                a.source,
                a.size_bytes,
                a.created_at,
                d.excerpt AS document_excerpt,
                vd.markdown_content AS markdown_content,
                vd.preview_text AS preview_text,
                vd.doc_index_text AS doc_index_text,
                vd.content_hash AS content_hash,
                vd.updated_at AS document_updated_at,
                vd.parse_status AS parse_status
            FROM task_attachments a
            LEFT JOIN documents d ON d.id = a.document_id
            LEFT JOIN v2_documents vd ON vd.document_id = a.document_id
            WHERE a.task_id IN ({placeholders})
            UNION ALL
            SELECT
                'task_attachments_cloud' AS source_table,
                a.id,
                a.task_id,
                a.client_id,
                a.event_line_id,
                a.document_id,
                a.title,
                a.path,
                a.kind,
                a.source,
                a.size_bytes,
                a.created_at,
                d.excerpt AS document_excerpt,
                vd.markdown_content AS markdown_content,
                vd.preview_text AS preview_text,
                vd.doc_index_text AS doc_index_text,
                vd.content_hash AS content_hash,
                vd.updated_at AS document_updated_at,
                vd.parse_status AS parse_status
            FROM task_attachments_cloud a
            LEFT JOIN documents d ON d.id = a.document_id
            LEFT JOIN v2_documents vd ON vd.document_id = a.document_id
            WHERE a.task_id IN ({placeholders})
        """
        try:
            attachment_rows = db.fetchall(attachment_sql, tuple([*lookup_ids, *lookup_ids]))
        except Exception as exc:
            logger.warning("Weekly mainline attachment evidence query failed: %s", exc)
            attachment_rows = []
        for row in attachment_rows:
            row_task_id = str(_weekly_mainline_row_value(row, "task_id", "") or "")
            item = item_by_lookup_id.get(row_task_id)
            title = _weekly_mainline_clean(_weekly_mainline_row_value(row, "title", ""))
            kind = _weekly_mainline_clean(_weekly_mainline_row_value(row, "kind", ""))
            readable_text = _weekly_mainline_first_text(
                [
                    _weekly_mainline_row_value(row, "markdown_content", ""),
                    _weekly_mainline_row_value(row, "preview_text", ""),
                    _weekly_mainline_row_value(row, "doc_index_text", ""),
                    _weekly_mainline_row_value(row, "document_excerpt", ""),
                ],
                min_length=20,
                limit=1200,
            )
            attachments.append(
                {
                    "attachmentId": str(_weekly_mainline_row_value(row, "id", "") or ""),
                    "sourceTable": str(_weekly_mainline_row_value(row, "source_table", "") or ""),
                    "taskId": row_task_id,
                    "canonicalTaskId": task_lookup.get(row_task_id, row_task_id),
                    "taskTitle": item.taskSnapshot.title if item else "",
                    "clientId": str(_weekly_mainline_row_value(row, "client_id", "") or ""),
                    "eventLineId": str(_weekly_mainline_row_value(row, "event_line_id", "") or ""),
                    "documentId": str(_weekly_mainline_row_value(row, "document_id", "") or ""),
                    "title": title,
                    "kind": kind,
                    "createdAt": str(_weekly_mainline_row_value(row, "created_at", "") or ""),
                    "documentUpdatedAt": str(_weekly_mainline_row_value(row, "document_updated_at", "") or ""),
                    "contentHash": str(_weekly_mainline_row_value(row, "content_hash", "") or ""),
                    "parseStatus": str(_weekly_mainline_row_value(row, "parse_status", "") or ""),
                    "readableText": readable_text,
                    "suggestedMaterial": "" if readable_text else _weekly_mainline_material_suggestion(title, kind),
                }
            )

    data_context: list[dict[str, Any]] = []
    if material_pack and material_pack.get("documents"):
        for item in material_pack.get("documents") or []:
            if not isinstance(item, dict):
                continue
            client_id = str(item.get("clientId") or "")
            data_context.append(
                {
                    "clientId": client_id,
                    "clientName": client_names.get(client_id, ""),
                    "title": _weekly_mainline_clean(item.get("title"), limit=90),
                    "excerpt": _weekly_mainline_clean(item.get("excerpt"), limit=800),
                    "canonicalKind": str(item.get("canonicalKind") or ""),
                    "originType": str(item.get("originType") or ""),
                    "score": item.get("score") or 0.0,
                }
            )
    elif include_data_center and client_ids:
        try:
            from app.services.knowledge_v2 import retrieve_knowledge_bundle
        except Exception:
            retrieve_knowledge_bundle = None  # type: ignore[assignment]
        if retrieve_knowledge_bundle is not None:
            query_parts = [week_label]
            query_parts.extend(record["title"] for record in task_records[:12] if record.get("title"))
            query_parts.extend(record["eventLineName"] for record in task_records[:12] if record.get("eventLineName"))
            query_parts.extend(
                str(record.get("structuredNote", {}).get("nextAction", ""))
                for record in task_records[:12]
                if record.get("structuredNote", {}).get("nextAction")
            )
            retrieval_prompt = _weekly_mainline_clean(" ".join(query_parts), limit=900)
            for client_id in client_ids[:4]:
                try:
                    bundle = retrieve_knowledge_bundle(db, data_dir, client_id, retrieval_prompt, access_context=access_context)
                except Exception as exc:
                    logger.warning("Weekly mainline data context retrieval failed for %s: %s", client_id, exc)
                    continue
                for citation in getattr(bundle, "citations", [])[:4]:
                    data_context.append(
                        {
                            "clientId": client_id,
                            "clientName": client_names.get(client_id, ""),
                            "title": _weekly_mainline_clean(getattr(citation, "title", ""), limit=90),
                            "excerpt": _weekly_mainline_clean(getattr(citation, "excerpt", ""), limit=800),
                            "canonicalKind": getattr(citation, "canonical_kind", "") or "",
                            "originType": getattr(citation, "origin_type", "") or "",
                            "score": getattr(citation, "score", 0.0) or 0.0,
                        }
                    )

    background_tasks = [
        item for item in (material_pack or {}).get("backgroundTasks", [])
        if isinstance(item, dict)
    ]
    background_review_entries = [
        item for item in (material_pack or {}).get("backgroundReviewEntries", [])
        if isinstance(item, dict)
    ]
    background_documents = [
        item for item in (material_pack or {}).get("backgroundDocuments", [])
        if isinstance(item, dict)
    ]
    background_event_lines = [
        item for item in (material_pack or {}).get("backgroundEventLines", [])
        if isinstance(item, dict)
    ]
    structured_mainline_evidence = _weekly_mainline_structured_evidence(
        tasks=task_records,
        background_tasks=background_tasks,
        background_review_entries=background_review_entries,
        background_documents=background_documents,
        background_event_lines=background_event_lines,
        attachments=attachments,
    )

    evidence_pack = {
        "weekLabel": week_label,
        "tasks": task_records,
        "backgroundTasks": background_tasks,
        "backgroundReviewEntries": background_review_entries,
        "backgroundDocuments": background_documents,
        "backgroundEventLines": background_event_lines,
        "structuredMainlineEvidence": structured_mainline_evidence,
        "attachments": attachments,
        "dataContext": data_context,
        "evidenceMeta": {
            "taskCount": len(task_records),
            "taskIdCount": len(task_ids),
            "attachmentCount": len(attachments),
            "readableAttachmentCount": len([item for item in attachments if item.get("readableText")]),
            "dataContextCount": len(data_context),
            "materialPackFingerprint": (material_pack or {}).get("packFingerprint", ""),
            "materialPackSourceCounts": (material_pack or {}).get("sourceCounts", {}),
            "materialPackMissingMeta": (material_pack or {}).get("missingMeta", {}),
        },
        "materialPack": material_pack or {},
    }
    return evidence_pack


def weekly_mainline_attachment_texts(evidence_pack: dict[str, Any], *, limit: int = 6) -> list[str]:
    texts: list[str] = []
    for attachment in evidence_pack.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        readable = _weekly_mainline_clean(attachment.get("readableText", ""), limit=1800)
        title = _weekly_mainline_clean(attachment.get("title", "") or attachment.get("taskTitle", ""), limit=80)
        if readable and len(readable) > 80:
            texts.append(f"【{title or '关联材料'}】\n{readable}")
        if len(texts) >= limit:
            break
    return texts


def weekly_mainline_evidence_fingerprint(evidence_pack: dict[str, Any]) -> str:
    source = json.dumps(evidence_pack, ensure_ascii=False, sort_keys=True, default=str)
    import hashlib

    return hashlib.sha1(source.encode("utf-8")).hexdigest()


def _weekly_mainline_group_key(task: dict[str, Any]) -> tuple[str, str]:
    event_id = _weekly_mainline_clean(task.get("eventLineId"), limit=80)
    if event_id:
        return f"event:{event_id}", _weekly_mainline_clean(task.get("eventLineName"), limit=80) or _weekly_mainline_clean(task.get("title"), limit=80)
    client_id = _weekly_mainline_clean(task.get("clientId"), limit=80)
    if client_id:
        return f"client:{client_id}", _weekly_mainline_clean(task.get("clientName"), limit=80) or _weekly_mainline_clean(task.get("title"), limit=80)
    return f"title:{_weekly_event_normalize_title(str(task.get('title') or ''))}", _weekly_mainline_clean(task.get("title"), limit=80)


def _weekly_mainline_structured_evidence(
    *,
    tasks: list[dict[str, Any]],
    background_tasks: list[dict[str, Any]],
    background_review_entries: list[dict[str, Any]],
    background_documents: list[dict[str, Any]],
    background_event_lines: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        key, title = _weekly_mainline_group_key(task)
        group = groups.setdefault(
            key,
            {
                "title": title or "本周主线",
                "currentWeekTasks": [],
                "previousProgress": [],
                "currentChange": "",
                "suspectedBlocker": [],
                "nextActionCandidates": [],
                "evidenceGaps": [],
            },
        )
        group["currentWeekTasks"].append(_weekly_mainline_clean(task.get("title"), limit=90))
        for candidate in [task.get("currentBlocker"), task.get("nextAction"), task.get("recentDecision")]:
            cleaned = _weekly_mainline_clean(candidate, limit=180)
            if cleaned and cleaned not in group["nextActionCandidates"] and ("下一步" in cleaned or _weekly_mainline_has_action(cleaned)):
                group["nextActionCandidates"].append(cleaned)
            elif cleaned and cleaned not in group["suspectedBlocker"] and ("卡" in cleaned or "阻塞" in cleaned or "风险" in cleaned):
                group["suspectedBlocker"].append(cleaned)

    for bg_task in background_tasks[:24]:
        key, _title = _weekly_mainline_group_key(bg_task)
        if key not in groups:
            continue
        progress = _weekly_mainline_clean(
            "；".join(
                part for part in [
                    bg_task.get("title"),
                    bg_task.get("recentDecision"),
                    bg_task.get("nextAction"),
                    bg_task.get("description"),
                ]
                if part
            ),
            limit=220,
        )
        if progress and progress not in groups[key]["previousProgress"]:
            groups[key]["previousProgress"].append(progress)

    review_by_task = {
        str(entry.get("taskId") or ""): entry
        for entry in background_review_entries
        if isinstance(entry, dict)
    }
    background_by_task = {
        str(task.get("taskId") or ""): _weekly_mainline_group_key(task)[0]
        for task in background_tasks
        if isinstance(task, dict)
    }
    for task_id, entry in review_by_task.items():
        key = background_by_task.get(task_id)
        if not key or key not in groups:
            continue
        note = _weekly_mainline_clean(entry.get("note") or entry.get("documentExcerpt"), limit=220)
        if note and note not in groups[key]["previousProgress"]:
            groups[key]["previousProgress"].append(note)

    for event_line in background_event_lines:
        key = f"event:{_weekly_mainline_clean(event_line.get('eventLineId'), limit=80)}"
        if key not in groups:
            continue
        for value in [event_line.get("summary"), event_line.get("recentDecision"), event_line.get("nextStep"), event_line.get("currentBlocker")]:
            cleaned = _weekly_mainline_clean(value, limit=180)
            if cleaned and cleaned not in groups[key]["previousProgress"]:
                groups[key]["previousProgress"].append(cleaned)

    for document in background_documents[:12]:
        client_id = _weekly_mainline_clean(document.get("clientId"), limit=80)
        excerpt = _weekly_mainline_clean(document.get("excerpt"), limit=220)
        if not client_id or not excerpt:
            continue
        for key, group in groups.items():
            if key == f"client:{client_id}" or any(
                isinstance(task, dict) and _weekly_mainline_clean(task.get("clientId"), limit=80) == client_id and _weekly_mainline_group_key(task)[0] == key
                for task in tasks
            ):
                if excerpt not in group["previousProgress"]:
                    group["previousProgress"].append(excerpt)

    attachment_task_ids = {str(item.get("canonicalTaskId") or item.get("taskId") or "") for item in attachments if isinstance(item, dict)}
    for key, group in groups.items():
        group_tasks = [
            task for task in tasks
            if isinstance(task, dict) and _weekly_mainline_group_key(task)[0] == key
        ]
        completed = len([task for task in group_tasks if str(task.get("status") or "") == "done"])
        pending = max(0, len(group_tasks) - completed)
        group["currentChange"] = f"本周 {len(group_tasks)} 项纳入，{completed} 项完成，{pending} 项未完成。"
        if not group["previousProgress"]:
            group["evidenceGaps"].append("缺少前序复盘或背景材料")
        if not any(str(task.get("taskId") or "") in attachment_task_ids for task in group_tasks):
            group["evidenceGaps"].append("缺少本周任务附件摘要")
        group["previousProgress"] = group["previousProgress"][:5]
        group["suspectedBlocker"] = group["suspectedBlocker"][:3]
        group["nextActionCandidates"] = group["nextActionCandidates"][:4]
        group["evidenceGaps"] = group["evidenceGaps"][:3]
    return list(groups.values())[:8]


def _weekly_event_task_text(task: dict[str, Any]) -> str:
    structured = task.get("structuredNote") if isinstance(task.get("structuredNote"), dict) else {}
    project = task.get("projectContext") if isinstance(task.get("projectContext"), dict) else {}
    event_line = task.get("eventLineContext") if isinstance(task.get("eventLineContext"), dict) else {}
    return _weekly_mainline_clean(
        " ".join(
            str(value or "")
            for value in [
                task.get("title"),
                task.get("taskDescription"),
                task.get("reviewNote"),
                task.get("clientName"),
                task.get("eventLineName"),
                structured.get("progress"),
                structured.get("nextAction"),
                project.get("backgroundSummary"),
                project.get("goalSummary"),
                event_line.get("summary"),
                event_line.get("nextStep"),
            ]
        ),
        limit=900,
    )


def _weekly_event_normalize_title(title: str) -> str:
    cleaned = _weekly_mainline_clean(title).lower()
    cleaned = re.sub(r"^\[[^\]]+\]\s*", "", cleaned)
    cleaned = re.sub(r"[（(].*?[）)]", "", cleaned)
    cleaned = re.sub(r"[\s·,，。:：;；/\\_-]+", "", cleaned)
    return cleaned


def _weekly_event_topic_group(task: dict[str, Any]) -> tuple[str, str] | None:
    """机制化 topic 分组: 用 task 已挂载的 event_line / project 字段做 key,
    任意客户都能自动分组, 不依赖任何客户名/人名/项目名硬编码。
    """
    text = _weekly_event_task_text(task)
    if any(token in text for token in ("模拟", "测试", "demo", "dummy")):
        return ("needs_assignment:测试/模拟事项", "测试/模拟事项")
    event_line_ctx = task.get("eventLineContext") if isinstance(task.get("eventLineContext"), dict) else {}
    event_line_id = str(event_line_ctx.get("id") or task.get("eventLineId") or "").strip()
    event_line_name = (
        str(event_line_ctx.get("name") or "").strip()
        or str(task.get("eventLineName") or "").strip()
    )
    if event_line_name:
        key = f"topic:event_line::{event_line_id or event_line_name}"
        return (key, event_line_name)
    project_ctx = task.get("projectContext") if isinstance(task.get("projectContext"), dict) else {}
    project_id = str(project_ctx.get("id") or "").strip()
    project_name = str(project_ctx.get("name") or "").strip()
    if project_name:
        key = f"topic:project::{project_id or project_name}"
        return (key, project_name)
    return None


def _weekly_event_task_status_counts(tasks: list[dict[str, Any]]) -> tuple[int, int]:
    completed = len([task for task in tasks if str(task.get("status") or "") == "done"])
    pending = max(0, len(tasks) - completed)
    return completed, pending


def _weekly_event_task_titles(tasks: list[dict[str, Any]]) -> list[str]:
    return [_weekly_mainline_clean(task.get("title"), limit=80) or "未命名任务" for task in tasks]


def _weekly_event_join_titles(titles: list[str], *, limit: int = 4) -> str:
    deduped: list[str] = []
    for title in titles:
        if title and title not in deduped:
            deduped.append(title)
    if len(deduped) <= limit:
        return "、".join(deduped)
    return "、".join(deduped[:limit]) + f"等 {len(deduped)} 项"


def _weekly_event_attachment_suggestions(evidence_pack: dict[str, Any], task_ids: set[str]) -> list[str]:
    suggestions: list[str] = []
    for attachment in evidence_pack.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        canonical_task_id = str(attachment.get("canonicalTaskId") or attachment.get("taskId") or "")
        if canonical_task_id not in task_ids:
            continue
        suggestion = _weekly_mainline_clean(attachment.get("suggestedMaterial"), limit=220)
        if suggestion and suggestion not in suggestions:
            suggestions.append(suggestion)
    return suggestions


def _weekly_event_first_action(tasks: list[dict[str, Any]], title: str, material_suggestions: list[str]) -> str:
    candidates: list[str] = []
    for task in tasks:
        structured = task.get("structuredNote") if isinstance(task.get("structuredNote"), dict) else {}
        project = task.get("projectContext") if isinstance(task.get("projectContext"), dict) else {}
        event_line = task.get("eventLineContext") if isinstance(task.get("eventLineContext"), dict) else {}
        candidates.extend(
            [
                structured.get("nextAction"),
                task.get("taskDescription") if "下一步" in str(task.get("taskDescription") or "") else "",
                project.get("nextAction"),
                project.get("currentFocus"),
                event_line.get("nextStep"),
            ]
        )
    for candidate in candidates:
        cleaned = _weekly_mainline_clean(candidate, limit=180)
        cleaned = re.sub(r"^下一步动作[:：]\s*", "", cleaned)
        if not cleaned:
            continue
        if any(phrase in cleaned for phrase in WEEKLY_EVENT_REVIEW_BANNED_PHRASES):
            continue
        if "先补齐项目背景" in cleaned and len(tasks) > 1:
            continue
        if _weekly_mainline_has_action(cleaned):
            return f"下一步先{cleaned.lstrip('先')}。产出标准是把负责人、交付物和完成时间说清楚。"
    if material_suggestions:
        return f"下一步先按复盘卡补齐关键资料。产出标准是让这条事件能判断下周是否继续跟、由谁跟、交付什么。"
    return f"下一步先确认“{title}”是否需要下周继续跟进，并补齐负责人、交付物和完成时间。"


def _weekly_event_material_text(tasks: list[dict[str, Any]], evidence_pack: dict[str, Any], task_ids: set[str]) -> str:
    suggestions = _weekly_event_attachment_suggestions(evidence_pack, task_ids)
    if suggestions:
        return suggestions[0]
    has_context = any(
        len(
            _weekly_mainline_clean(
                " ".join(
                    [
                        str(task.get("taskDescription") or ""),
                        str(task.get("reviewNote") or ""),
                        str((task.get("structuredNote") or {}).get("progress") if isinstance(task.get("structuredNote"), dict) else ""),
                        str((task.get("projectContext") or {}).get("backgroundSummary") if isinstance(task.get("projectContext"), dict) else ""),
                        str((task.get("eventLineContext") or {}).get("summary") if isinstance(task.get("eventLineContext"), dict) else ""),
                    ]
                )
            )
        )
        >= 30
        for task in tasks
    )
    if has_context:
        return ""
    return "建议补充这条事件的背景、负责人、交付物和完成时间；补齐后可以判断它是否需要进入下周重点跟进。"


def _weekly_event_reflection_prompt_text(
    *,
    title: str,
    card_kind: str,
    tasks: list[dict[str, Any]],
    evidence_pack: dict[str, Any],
    task_ids: set[str],
) -> str:
    task_titles = _weekly_event_task_titles(tasks)
    title_list = _weekly_event_join_titles(task_titles, limit=3)
    material_suggestions = _weekly_event_attachment_suggestions(evidence_pack, task_ids)
    combined = _weekly_mainline_clean(
        " ".join(
            [
                title,
                title_list,
                *[
                    _weekly_mainline_clean(
                        " ".join(
                            [
                                str(task.get("title") or ""),
                                str(task.get("taskDescription") or ""),
                                str(task.get("reviewNote") or ""),
                                str((task.get("structuredNote") or {}).get("progress") if isinstance(task.get("structuredNote"), dict) else ""),
                                str((task.get("structuredNote") or {}).get("nextAction") if isinstance(task.get("structuredNote"), dict) else ""),
                                str((task.get("projectContext") or {}).get("goalSummary") if isinstance(task.get("projectContext"), dict) else ""),
                                str((task.get("projectContext") or {}).get("backgroundSummary") if isinstance(task.get("projectContext"), dict) else ""),
                                str((task.get("eventLineContext") or {}).get("summary") if isinstance(task.get("eventLineContext"), dict) else ""),
                            ]
                        ),
                        limit=260,
                    )
                    for task in tasks
                ],
            ]
        ),
        limit=900,
    )
    completed, pending = _weekly_event_task_status_counts(tasks)
    pending_hint = (
        f"这组里还有 {pending} 项没完成，也可以顺手写清楚它卡在谁、卡在哪个交付物或时间点上。"
        if pending
        else ""
    )
    material_hint = (
        "如果还缺材料，可以补一份最小文字说明；补上后，这条复盘会更容易判断项目状态、责任边界和下周优先级。"
        if material_suggestions
        else ""
    )

    if card_kind == "needs_assignment":
        prompt = (
            f"可以先判断“{title_list}”是否应该进入正式复盘，还是只是测试、模拟或临时协作记录。"
            "如果要纳入，建议写清它对应哪个客户、项目或事件线，以及这条记录对真实工作有什么影响。"
        )
    elif any(keyword in combined for keyword in ["云南", "报告", "PPT", "工作坊"]):
        prompt = (
            "可以回想一下：这组材料调整之后，云南项目是更接近资方决策、机构执行，还是内部沟通。"
            "也可以写下目前最需要确认的版本边界、修改清单、负责人和交付时间。"
        )
    elif any(keyword in combined for keyword in ["合同", "报价", "签约", "交付范围"]):
        prompt = (
            f"可以回想一下：围绕“{title}”这次合同或报价确认，真正锁定的是价格、范围、责任边界，还是下一阶段启动条件。"
            "也可以写下还有哪个条款、交付物或对方确认点会影响项目进入执行。"
        )
    elif "益语" in combined or any(keyword in combined for keyword in ["开源页", "开源页面", "首屏价值", "价值表达"]):
        prompt = (
            "可以回想一下：这组任务是否让目标用户更容易理解益语平台的价值，而不只是看到功能列表。"
            "也可以写下页面表达、目标读者和转化路径里，哪一处判断还需要你亲自确认。"
        )
    elif any(keyword in combined for keyword in ["县域", "学校", "招募", "音乐课堂", "落地"]):
        prompt = (
            "可以回想一下：学校招募和县域落地计划完成后，项目准备度发生了什么变化。"
            "也可以写下名单、筛选标准、沟通节奏或现场落地条件里，哪一项最影响后续推进。"
        )
    elif card_kind == "single_task":
        prompt = (
            f"可以回想一下：“{title_list}”完成后，这件事对当前项目有什么实际变化。"
            "如果它只是一个独立任务，也可以只写最关键的一点：结果、遗留判断，或是否需要带到下周。"
        )
    else:
        prompt = (
            f"可以回想一下：这组围绕“{title}”的任务完成后，项目状态有什么变化。"
            "也可以写下还缺哪个判断、谁需要接手，以及下周最小可推进事项是什么。"
        )

    return _weekly_mainline_clean("".join([prompt, pending_hint, material_hint]), limit=420)


def _weekly_event_make_fallback_card(
    *,
    index: int,
    title: str,
    card_kind: str,
    tasks: list[dict[str, Any]],
    evidence_pack: dict[str, Any],
    confidence: str,
) -> WeeklyEventReviewCardRecord:
    task_ids = [str(task.get("taskId") or "") for task in tasks if str(task.get("taskId") or "")]
    task_id_set = set(task_ids)
    task_titles = _weekly_event_task_titles(tasks)
    reflection_prompt = _weekly_event_reflection_prompt_text(
        title=title,
        card_kind=card_kind,
        tasks=tasks,
        evidence_pack=evidence_pack,
        task_ids=task_id_set,
    )
    return WeeklyEventReviewCardRecord(
        id=f"fallback-weekly-event-{index}",
        title=title,
        cardKind=card_kind,  # type: ignore[arg-type]
        taskIds=task_ids,
        taskTitles=task_titles,
        reflectionPromptText=reflection_prompt,
        progressText="",
        nextActionText="",
        materialSuggestionText="",
        confidence=confidence,  # type: ignore[arg-type]
        generatedBy="fallback",
    )


def build_weekly_event_review_cards_fallback(
    evidence_pack: dict[str, Any],
    *,
    reason: str = "",
) -> WeeklyEventReviewCardsRecord:
    tasks = [task for task in (evidence_pack.get("tasks") or []) if isinstance(task, dict) and str(task.get("taskId") or "")]
    remaining: dict[str, dict[str, Any]] = {str(task.get("taskId")): task for task in tasks}
    raw_groups: list[tuple[str, str, str, list[dict[str, Any]], str]] = []

    event_groups: dict[str, list[dict[str, Any]]] = {}
    event_titles: dict[str, str] = {}
    for task_id, task in list(remaining.items()):
        event_line_id = _weekly_mainline_clean(task.get("eventLineId"), limit=80)
        if not event_line_id:
            continue
        key = f"event:{event_line_id}"
        event_groups.setdefault(key, []).append(task)
        event_titles[key] = _weekly_mainline_clean(task.get("eventLineName"), limit=80) or _weekly_mainline_clean(task.get("title"), limit=80)
        del remaining[task_id]
    for key, grouped_tasks in event_groups.items():
        raw_groups.append((key, event_titles.get(key) or "事件线复盘", "event_line", grouped_tasks, "high"))

    topic_groups: dict[str, list[dict[str, Any]]] = {}
    topic_titles: dict[str, str] = {}
    topic_kinds: dict[str, str] = {}
    for task_id, task in list(remaining.items()):
        topic = _weekly_event_topic_group(task)
        if topic is None:
            continue
        key, title = topic
        topic_groups.setdefault(key, []).append(task)
        topic_titles[key] = title
        topic_kinds[key] = "needs_assignment" if key.startswith("needs_assignment:") else "task_cluster"
        del remaining[task_id]
    for key, grouped_tasks in topic_groups.items():
        if len(grouped_tasks) > 1 or topic_kinds.get(key) == "needs_assignment":
            raw_groups.append((key, topic_titles.get(key) or "任务簇复盘", topic_kinds.get(key, "task_cluster"), grouped_tasks, "medium"))
        else:
            task = grouped_tasks[0]
            remaining[str(task.get("taskId"))] = task

    duplicate_groups: dict[str, list[dict[str, Any]]] = {}
    duplicate_titles: dict[str, str] = {}
    for task_id, task in list(remaining.items()):
        normalized_title = _weekly_event_normalize_title(str(task.get("title") or ""))
        if not normalized_title:
            continue
        duplicate_groups.setdefault(normalized_title, []).append(task)
        duplicate_titles[normalized_title] = _weekly_mainline_clean(task.get("title"), limit=80)
    for key, grouped_tasks in list(duplicate_groups.items()):
        if len(grouped_tasks) < 2:
            continue
        raw_groups.append((f"duplicate:{key}", duplicate_titles.get(key) or "重复任务复盘", "task_cluster", grouped_tasks, "medium"))
        for task in grouped_tasks:
            remaining.pop(str(task.get("taskId")), None)

    for task in remaining.values():
        title = _weekly_mainline_clean(task.get("title"), limit=80) or "单项复盘"
        raw_groups.append((f"single:{task.get('taskId')}", title, "single_task", [task], "low"))

    cards = [
        _weekly_event_make_fallback_card(
            index=index,
            title=title,
            card_kind=card_kind,
            tasks=grouped_tasks,
            evidence_pack=evidence_pack,
            confidence=confidence,
        )
        for index, (_key, title, card_kind, grouped_tasks, confidence) in enumerate(raw_groups, start=1)
    ]
    meta = dict(evidence_pack.get("evidenceMeta") or {})
    if reason:
        meta["failureReason"] = reason
    meta["cardCount"] = len(cards)
    return WeeklyEventReviewCardsRecord(cards=cards, generatedBy="fallback", evidenceMeta=meta)


def _weekly_event_candidate_prompt_lines(cards: list[WeeklyEventReviewCardRecord]) -> str:
    lines: list[str] = []
    for card in cards:
        lines.append(
            "\n".join(
                [
                    f"- id={card.id}",
                    f"  title={card.title}",
                    f"  cardKind={card.cardKind}",
                    f"  taskIds={json.dumps(card.taskIds, ensure_ascii=False)}",
                    f"  taskTitles={json.dumps(card.taskTitles, ensure_ascii=False)}",
                    f"  fallbackReflectionPrompt={card.reflectionPromptText}",
                ]
            )
        )
    return "\n".join(lines)


def _weekly_event_expected_task_sets(cards: list[WeeklyEventReviewCardRecord]) -> list[tuple[str, ...]]:
    return sorted(tuple(sorted(card.taskIds)) for card in cards)


def weekly_event_review_cards_cover_task_ids(
    cards: WeeklyEventReviewCardsRecord | None,
    expected_task_ids: Iterable[str],
) -> bool:
    expected_ids = {str(task_id).strip() for task_id in expected_task_ids if str(task_id).strip()}
    if not expected_ids or cards is None or not cards.cards:
        return False
    seen_ids: list[str] = []
    for card in cards.cards:
        card_ids = [str(task_id).strip() for task_id in (card.taskIds or []) if str(task_id).strip()]
        if not card_ids:
            return False
        seen_ids.extend(card_ids)
    return set(seen_ids) == expected_ids and len(seen_ids) == len(set(seen_ids))


def _coerce_weekly_event_review_cards(
    raw: Any,
    evidence_pack: dict[str, Any],
    fallback_cards: WeeklyEventReviewCardsRecord,
) -> tuple[WeeklyEventReviewCardsRecord | None, str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None, "ai_returned_non_json_string"
    if not isinstance(raw, dict):
        return None, "ai_returned_non_dict"
    raw_cards = raw.get("cards") or []
    if not isinstance(raw_cards, list) or not raw_cards:
        return None, "cards_empty"

    source_tasks = {
        str(task.get("taskId")): task
        for task in (evidence_pack.get("tasks") or [])
        if isinstance(task, dict) and str(task.get("taskId") or "")
    }
    expected_ids = set(source_tasks.keys())
    seen_ids: list[str] = []
    cards: list[WeeklyEventReviewCardRecord] = []
    combined_text_parts: list[str] = []
    for index, item in enumerate(raw_cards, start=1):
        if not isinstance(item, dict):
            continue
        task_ids = [str(task_id) for task_id in item.get("taskIds") or [] if str(task_id).strip()]
        if not task_ids:
            return None, "card_without_task_ids"
        unknown_ids = [task_id for task_id in task_ids if task_id not in expected_ids]
        if unknown_ids:
            return None, f"unknown_task_ids:{','.join(unknown_ids)}"
        seen_ids.extend(task_ids)
        title = _weekly_mainline_clean(item.get("title"), limit=90)
        card_kind = str(item.get("cardKind") or "single_task")
        if card_kind not in {"event_line", "task_cluster", "single_task", "needs_assignment"}:
            return None, f"invalid_card_kind:{card_kind}"
        if _weekly_mainline_clean(item.get("progressText"), limit=40) or _weekly_mainline_clean(item.get("nextActionText"), limit=40) or _weekly_mainline_clean(item.get("materialSuggestionText"), limit=40):
            return None, f"unexpected_draft_text:{title or index}"
        reflection_prompt = _weekly_mainline_clean(item.get("reflectionPromptText"), limit=420)
        confidence = str(item.get("confidence") or "medium")
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"
        if not title:
            return None, "card_title_empty"
        if len(reflection_prompt) < 24:
            return None, f"reflection_prompt_too_short:{title}"
        task_titles = [_weekly_mainline_clean(source_tasks[task_id].get("title"), limit=90) for task_id in task_ids]
        combined_text_parts.extend([title, reflection_prompt])
        cards.append(
            WeeklyEventReviewCardRecord(
                id=str(item.get("id") or f"ai-weekly-event-{index}"),
                title=title,
                cardKind=card_kind,  # type: ignore[arg-type]
                taskIds=task_ids,
                taskTitles=task_titles,
                reflectionPromptText=reflection_prompt,
                progressText="",
                nextActionText="",
                materialSuggestionText="",
                confidence=confidence,  # type: ignore[arg-type]
                generatedBy="ai",
            )
        )
    if not cards:
        return None, "cards_empty_after_clean"
    if set(seen_ids) != expected_ids:
        return None, "task_coverage_mismatch"
    if len(seen_ids) != len(set(seen_ids)):
        return None, "duplicate_task_ids"
    if _weekly_event_expected_task_sets(cards) != _weekly_event_expected_task_sets(fallback_cards.cards):
        return None, "task_group_boundary_changed"
    combined_text = "\n".join(combined_text_parts)
    for term in WEEKLY_MAINLINE_INTERNAL_TERMS:
        if term and term in combined_text:
            return None, f"internal_term:{term}"
    for phrase in WEEKLY_EVENT_REVIEW_BANNED_PHRASES:
        if phrase and phrase in combined_text:
            return None, f"banned_phrase:{phrase}"
    meta = dict(evidence_pack.get("evidenceMeta") or {})
    meta["validated"] = True
    meta["cardCount"] = len(cards)
    return WeeklyEventReviewCardsRecord(cards=cards, generatedBy="ai", evidenceMeta=meta), ""


def build_weekly_event_review_cards_draft(
    *,
    ai: AiService,
    week_label: str,
    evidence_pack: dict[str, Any],
) -> WeeklyEventReviewCardsRecord:
    fallback_cards = build_weekly_event_review_cards_fallback(evidence_pack)
    health = ai.get_health()
    if health.provider == "mock" or not health.ready:
        return build_weekly_event_review_cards_fallback(evidence_pack, reason="ai_not_ready")
    task_lines = _weekly_mainline_task_prompt_lines(evidence_pack)
    attachment_lines = _weekly_mainline_attachment_prompt_lines(evidence_pack)
    candidate_lines = _weekly_event_candidate_prompt_lines(fallback_cards.cards)
    prompt = "\n\n".join(
        part
        for part in [
            f"【周标签】\n{week_label}",
            f"【本周任务包】\n{task_lines}" if task_lines else "",
            attachment_lines,
            f"【候选事件复盘卡】\n{candidate_lines}" if candidate_lines else "",
            (
                "【输出要求】\n"
                "只输出 JSON。cards 必须和候选卡数量一致，且每张卡的 taskIds 必须保持不变。"
                "只可以优化 title、reflectionPromptText 和 confidence。"
                "不要输出旧的复盘正文、行动建议或材料建议字段，不要写资料来源、读取状态或内部诊断。"
            ),
        ]
        if part
    )
    try:
        raw = ai._qwen_generate(
            prompt=prompt,
            system_instruction=WEEKLY_EVENT_REVIEW_SYSTEM_INSTRUCTION,
            response_schema=WEEKLY_EVENT_REVIEW_RESPONSE_SCHEMA,
            timeout_seconds=120.0,
            max_tokens=5200,
            temperature=0.25,
            top_p=0.9,
            enable_thinking=False,
        )
        cards, reason = _coerce_weekly_event_review_cards(raw, evidence_pack, fallback_cards)
        if cards is None:
            logger.warning("Weekly event review cards validation failed: %s", reason)
            return build_weekly_event_review_cards_fallback(evidence_pack, reason=reason)
        return cards
    except Exception as exc:
        logger.warning("Weekly event review card generation failed: %s", exc)
        return build_weekly_event_review_cards_fallback(evidence_pack, reason="generation_exception")


def _weekly_mainline_task_prompt_lines(evidence_pack: dict[str, Any]) -> str:
    lines: list[str] = []
    for task in evidence_pack.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        structured = task.get("structuredNote") if isinstance(task.get("structuredNote"), dict) else {}
        project = task.get("projectContext") if isinstance(task.get("projectContext"), dict) else {}
        event_line = task.get("eventLineContext") if isinstance(task.get("eventLineContext"), dict) else {}
        parts = [
            f"标题={_weekly_mainline_clean(task.get('title'), limit=80)}",
            f"状态={_weekly_mainline_clean(task.get('status'), limit=20)}",
        ]
        if task.get("clientName") or task.get("eventLineName"):
            parts.append(
                "归属="
                + _weekly_mainline_clean(" / ".join([str(task.get("clientName") or ""), str(task.get("eventLineName") or "")]).strip(" /"), limit=80)
            )
        for label, value in [
            ("任务描述", task.get("taskDescription")),
            ("复盘说明", task.get("reviewNote")),
            ("任务卡点", task.get("currentBlocker")),
            ("任务下一步", task.get("nextAction")),
            ("任务最近决策", task.get("recentDecision")),
            ("复盘进展", structured.get("progress")),
            ("复盘反思", structured.get("reflection")),
            ("下一步", structured.get("nextAction")),
            ("项目近期进展", project.get("recentProgress")),
            ("项目目标", project.get("goalSummary")),
            ("项目背景", project.get("backgroundSummary")),
            ("事件线决策", event_line.get("recentDecision")),
            ("事件线下一步", event_line.get("nextStep")),
            ("事件线卡点", event_line.get("currentBlocker")),
        ]:
            cleaned = _weekly_mainline_clean(value, limit=140)
            if cleaned:
                parts.append(f"{label}={cleaned}")
        lines.append("- " + "；".join(parts))
    return "\n".join(lines)


def _weekly_mainline_structured_prompt_lines(evidence_pack: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in evidence_pack.get("structuredMainlineEvidence") or []:
        if not isinstance(item, dict):
            continue
        parts = [
            f"主线={_weekly_mainline_clean(item.get('title'), limit=90)}",
            f"本周任务={_weekly_mainline_clean('、'.join(item.get('currentWeekTasks') or []), limit=180)}",
            f"本周变化={_weekly_mainline_clean(item.get('currentChange'), limit=120)}",
        ]
        for label, key in [
            ("前序进展", "previousProgress"),
            ("可能卡点", "suspectedBlocker"),
            ("下一步候选", "nextActionCandidates"),
            ("证据缺口", "evidenceGaps"),
        ]:
            values = [
                _weekly_mainline_clean(value, limit=160)
                for value in (item.get(key) or [])
                if _weekly_mainline_clean(value, limit=160)
            ]
            if values:
                parts.append(f"{label}={'；'.join(values[:4])}")
        lines.append("- " + "；".join(part for part in parts if part and not part.endswith("=")))
    return "\n".join(lines)


def _weekly_mainline_background_prompt_lines(evidence_pack: dict[str, Any]) -> str:
    lines: list[str] = []
    for task in (evidence_pack.get("backgroundTasks") or [])[:18]:
        if not isinstance(task, dict):
            continue
        title = _weekly_mainline_clean(task.get("title"), limit=90)
        reason = _weekly_mainline_clean(task.get("relationReason"), limit=40)
        details = _weekly_mainline_clean(
            "；".join(
                value for value in [
                    task.get("eventLineName"),
                    task.get("clientName"),
                    task.get("recentDecision"),
                    task.get("nextAction"),
                    task.get("description"),
                ]
                if value
            ),
            limit=260,
        )
        if title:
            lines.append(f"- {title}（{reason or 'related_history'}）：{details}")
    for entry in (evidence_pack.get("backgroundReviewEntries") or [])[:8]:
        if not isinstance(entry, dict):
            continue
        note = _weekly_mainline_clean(entry.get("note") or entry.get("documentExcerpt"), limit=260)
        if note:
            lines.append(f"- 前序复盘（{_weekly_mainline_clean(entry.get('taskId'), limit=40)}）：{note}")
    return "\n".join(lines[:24])


def _weekly_mainline_attachment_prompt_lines(evidence_pack: dict[str, Any]) -> str:
    readable_lines: list[str] = []
    suggested_lines: list[str] = []
    for attachment in evidence_pack.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        title = _weekly_mainline_clean(attachment.get("title") or attachment.get("taskTitle") or "关联材料", limit=90)
        task_title = _weekly_mainline_clean(attachment.get("taskTitle"), limit=70)
        readable = _weekly_mainline_clean(attachment.get("readableText"), limit=900)
        if readable:
            readable_lines.append(f"- {title}（对应任务：{task_title or '未标注'}）：{readable}")
            continue
        suggestion = _weekly_mainline_clean(attachment.get("suggestedMaterial"), limit=220)
        if suggestion:
            suggested_lines.append(f"- {title}（对应任务：{task_title or '未标注'}）：{suggestion}")
    blocks = []
    if readable_lines:
        blocks.append("【本周任务关联材料摘要】\n" + "\n".join(readable_lines[:8]))
    if suggested_lines:
        blocks.append("【需要用户补充后会提升复盘质量的资料】\n" + "\n".join(suggested_lines[:6]))
    return "\n\n".join(blocks)


def _weekly_mainline_data_context_prompt_lines(evidence_pack: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in evidence_pack.get("dataContext") or []:
        if not isinstance(item, dict):
            continue
        title = _weekly_mainline_clean(item.get("title"), limit=90)
        excerpt = _weekly_mainline_clean(item.get("excerpt"), limit=520)
        client_name = _weekly_mainline_clean(item.get("clientName"), limit=40)
        if title and excerpt:
            prefix = f"{client_name} / {title}" if client_name else title
            lines.append(f"- {prefix}：{excerpt}")
    return "\n".join(lines[:10])


def _weekly_mainline_fallback_result(evidence_pack: dict[str, Any], reason: str) -> WeeklyMainlineCardsRecord:
    meta = dict(evidence_pack.get("evidenceMeta") or {})
    meta["failureReason"] = reason
    return WeeklyMainlineCardsRecord(
        summaryText="",
        mainlines=[],
        generatedBy="fallback",
        evidenceMeta=meta,
    )


def _weekly_mainline_has_action(text: str) -> bool:
    return any(keyword in text for keyword in WEEKLY_MAINLINE_ACTION_KEYWORDS)


def _coerce_weekly_mainline_cards(raw: Any, evidence_pack: dict[str, Any]) -> tuple[WeeklyMainlineCardsRecord | None, str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None, "ai_returned_non_json_string"
    if not isinstance(raw, dict):
        return None, "ai_returned_non_dict"
    summary_text = _weekly_mainline_clean(raw.get("summaryText"), limit=420)
    raw_lines = raw.get("mainlines") or []
    if not isinstance(raw_lines, list) or not raw_lines:
        return None, "mainlines_empty"
    if len(summary_text) < 30:
        return None, "summary_too_short"
    cards: list[WeeklyMainlineCardRecord] = []
    combined_text_parts = [summary_text]
    for index, item in enumerate(raw_lines[:3], start=1):
        if not isinstance(item, dict):
            continue
        title = _weekly_mainline_clean(item.get("title"), limit=80)
        progress_text = _weekly_mainline_clean(item.get("progressText"), limit=520)
        next_goal_text = _weekly_mainline_clean(item.get("nextGoalText"), limit=420)
        if not title:
            return None, "mainline_title_empty"
        if len(progress_text) < 24:
            return None, f"progress_too_short:{title}"
        if len(next_goal_text) < 24:
            return None, f"next_goal_too_short:{title}"
        if not _weekly_mainline_has_action(next_goal_text):
            return None, f"next_goal_has_no_action:{title}"
        combined_text_parts.extend([title, progress_text, next_goal_text])
        try:
            task_count = max(0, int(item.get("taskCount") or 0))
        except Exception:
            task_count = 0
        try:
            completed_count = max(0, int(item.get("completedCount") or 0))
        except Exception:
            completed_count = 0
        try:
            pending_count = max(0, int(item.get("pendingCount") or 0))
        except Exception:
            pending_count = 0
        if task_count <= 0:
            task_count = max(1, completed_count + pending_count)
        cards.append(
            WeeklyMainlineCardRecord(
                id=f"ai-weekly-mainline-{index}",
                title=title,
                taskCount=task_count,
                completedCount=completed_count,
                pendingCount=pending_count,
                progressText=progress_text,
                nextGoalText=next_goal_text,
            )
        )
    if not cards:
        return None, "mainlines_empty_after_clean"
    combined_text = "\n".join(combined_text_parts)
    for term in WEEKLY_MAINLINE_INTERNAL_TERMS:
        if term and term in combined_text:
            return None, f"internal_term:{term}"
    for phrase in WEEKLY_MAINLINE_BANNED_PHRASES:
        if phrase and phrase in combined_text:
            return None, f"banned_phrase:{phrase}"
    evidence_text = json.dumps(evidence_pack, ensure_ascii=False, default=str)
    if "下载按钮" in combined_text and "下载按钮" not in evidence_text:
        return None, "unsupported_download_button_claim"
    meta = dict(evidence_pack.get("evidenceMeta") or {})
    meta["validated"] = True
    return (
        WeeklyMainlineCardsRecord(
            summaryText=summary_text,
            mainlines=cards,
            generatedBy="ai",
            evidenceMeta=meta,
        ),
        "",
    )


def build_weekly_mainline_cards_draft(
    *,
    ai: AiService,
    week_label: str,
    evidence_pack: dict[str, Any],
) -> WeeklyMainlineCardsRecord:
    meta = evidence_pack.get("evidenceMeta") if isinstance(evidence_pack.get("evidenceMeta"), dict) else {}
    counts = meta.get("materialPackSourceCounts") if isinstance(meta.get("materialPackSourceCounts"), dict) else {}
    if int(counts.get("explicitTaskBoundary") or 0) > 0 and int(counts.get("tasks") or 0) == 0:
        return _weekly_mainline_fallback_result(evidence_pack, "material_pack_empty")

    health = ai.get_health()
    if health.provider == "mock" or not health.ready:
        return _weekly_mainline_fallback_result(evidence_pack, "ai_not_ready")

    structured_lines = _weekly_mainline_structured_prompt_lines(evidence_pack)
    task_lines = _weekly_mainline_task_prompt_lines(evidence_pack)
    background_lines = _weekly_mainline_background_prompt_lines(evidence_pack)
    attachment_lines = _weekly_mainline_attachment_prompt_lines(evidence_pack)
    data_context_lines = _weekly_mainline_data_context_prompt_lines(evidence_pack)
    prompt = "\n\n".join(
        part
        for part in [
            f"【周标签】\n{week_label}",
            (
                "【统计】\n"
                f"任务数：{meta.get('taskCount', 0)}；"
                f"任务关联材料数：{meta.get('attachmentCount', 0)}；"
                f"有文字摘要的材料数：{meta.get('readableAttachmentCount', 0)}"
            ),
            f"【结构化主线证据】\n{structured_lines}" if structured_lines else "",
            f"【本周任务包】\n{task_lines}" if task_lines else "",
            f"【前序背景包】\n{background_lines}" if background_lines else "",
            attachment_lines,
            f"【组织与项目背景材料】\n{data_context_lines}" if data_context_lines else "",
            (
                "【输出要求】\n"
                "只输出 JSON。不要解释。mainlines 最多 3 条。每条 progressText 2-4 句，nextGoalText 2-3 句。"
                "本周任务只用于统计，前序背景只用于解释项目从哪里来、当前卡在哪里。"
                "不要写任何资料来源、读取状态或内部诊断。"
            ),
        ]
        if part
    )
    try:
        raw = ai._qwen_generate(
            prompt=prompt,
            system_instruction=WEEKLY_MAINLINE_SYSTEM_INSTRUCTION,
            response_schema=WEEKLY_MAINLINE_RESPONSE_SCHEMA,
            timeout_seconds=120.0,
            max_tokens=3600,
            temperature=0.3,
            top_p=0.9,
            enable_thinking=False,
        )
        cards, reason = _coerce_weekly_mainline_cards(raw, evidence_pack)
        if cards is None:
            logger.warning("Weekly mainline cards validation failed: %s", reason)
            return _weekly_mainline_fallback_result(evidence_pack, reason)
        return cards
    except Exception as exc:
        logger.warning("Weekly mainline card generation failed: %s", exc)
        return _weekly_mainline_fallback_result(evidence_pack, "generation_exception")


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
        if not module.hasDocument:
            continue
        # Summary for DNA modules (keep prompt size manageable), full text for meeting minutes
        text = _clean_text(module.summary or module.normalizedText[:1500])
        if text:
            lines.append(f"- {module.title}: {text}")
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
            parts.append(f"说明={desc}")
        elif note:
            parts.append(f"备注={note}")
        # Task action fields
        blocker = _clean_text(getattr(snap, "currentBlocker", "") or "")
        next_action = _clean_text(getattr(snap, "nextAction", "") or "")
        decision = _clean_text(getattr(snap, "recentDecision", "") or "")
        if blocker:
            parts.append(f"卡点={blocker}")
        if next_action:
            parts.append(f"下一步={next_action}")
        if decision:
            parts.append(f"决策={decision}")
        # Event line context
        elc = snap.eventLineContext
        if elc:
            if elc.summary:
                parts.append(f"事件线说明={_clean_text(elc.summary)}")
            if elc.currentBlocker:
                parts.append(f"事件线卡点={_clean_text(elc.currentBlocker)}")
            if elc.recentDecision:
                parts.append(f"事件线决策={_clean_text(elc.recentDecision)}")
            if elc.nextStep:
                parts.append(f"事件线下一步={_clean_text(elc.nextStep)}")
        # Review note (user's weekly review input — highest weight)
        review_note = _clean_text(item.note or "")
        if review_note and review_note != note:
            parts.append(f"周复盘={review_note}")
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
    """机制化评分: 完全基于本周事实强度 (items 数 / 证据 / 决策 / narrative 完整度),
    不再用客户名/项目名做硬编码加权 — 任何客户上线都用同一套打分。
    """
    progress_evidence = min(1.0, len(items) / 3.0)
    output_clarity = 0.45
    if any(_clean_text(getattr(item.taskSnapshot, "nextAction", "") or "") for item in items):
        output_clarity += 0.2
    if any(_clean_text(item.note) for item in items):
        output_clarity += 0.15
    if any(_clean_text(getattr(item.taskSnapshot, "recentDecision", "") or "") for item in items):
        output_clarity += 0.2
    narrative_strength = 0.65 if _clean_text(why_it_matters) else 0.35
    evidence_strength = min(
        1.0,
        sum(
            max(1, int(getattr(item.taskSnapshot, "evidenceCount", 0) or 0))
            for item in items
        )
        / 8.0,
    )
    score = (
        0.30 * progress_evidence
        + 0.25 * min(output_clarity, 1.0)
        + 0.20 * narrative_strength
        + 0.25 * evidence_strength
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
        else:
            what_happened = f"这周围绕 {task_titles} 等事项持续推进，已经不只是零散接触，而是在形成一条更清楚的业务推进线。"

        if narrative and _clean_text(narrative.whyImportant):
            why_it_matters = _clean_text(narrative.whyImportant)
        elif client_bg:
            why_it_matters = client_bg
        else:
            why_it_matters = "这条线的重要性在于，它直接关系到我方咨询团队能否把当前的关系推进成更清楚的合作、诊断或交付。"

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
    attachment_texts: list[str] | None = None,
    local_memory_context: str = "",
) -> tuple[str, list[str], list[str]]:
    fallback_focus = _dedupe_lines(fallback_focus_lines, limit=4)
    fallback_next = _dedupe_lines(fallback_next_focus, limit=3)
    fallback_summary = _clean_text(fallback_overview)
    line_cards = _build_weekly_line_cards(items, org_dna_modules, narratives)
    health = ai.get_health()
    if health.provider == "mock" or not health.ready:
        return fallback_summary, fallback_focus, fallback_next

    # Build event line summary from task items (deduplicated)
    el_summary_lines: list[str] = []
    seen_el_ids: set[str] = set()
    for item in items:
        elc = item.taskSnapshot.eventLineContext
        if not elc or not elc.id or elc.id in seen_el_ids:
            continue
        seen_el_ids.add(elc.id)
        el_parts = [elc.name or ""]
        if elc.summary:
            el_parts.append(f"说明={_clean_text(elc.summary)}")
        if elc.currentBlocker:
            el_parts.append(f"卡点={_clean_text(elc.currentBlocker)}")
        if elc.recentDecision:
            el_parts.append(f"决策={_clean_text(elc.recentDecision)}")
        if elc.nextStep:
            el_parts.append(f"下一步={_clean_text(elc.nextStep)}")
        if elc.stage:
            el_parts.append(f"阶段={_clean_text(elc.stage)}")
        if len(el_parts) > 1:
            el_summary_lines.append("- " + "；".join(el_parts))
    event_line_fields_block = "\n".join(el_summary_lines)

    prompt = "\n\n".join(
        part
        for part in [
            f"【周标签】\n{week_label}",
            f"【规则兜底草稿】\n{fallback_summary}",
            f"【规则识别的主线】\n" + "\n".join(f"- {line}" for line in fallback_focus) if fallback_focus else "",
            f"【主线理解卡】\n{_weekly_line_card_lines(line_cards)}" if line_cards else "",
            f"【组织背景（含团队与市场）】\n{_organization_background_preview(org_dna_modules)}",
            f"【事件线管理字段】\n{event_line_fields_block}" if event_line_fields_block else "",
            f"【事件线叙事】\n{_narrative_summary_lines(narratives)}" if narratives else "",
            f"【本周任务与线索】\n{_weekly_overview_task_lines(items)}",
            f"【本地项目记忆（历史判断与上下文）】\n{local_memory_context}" if local_memory_context else "",
            f"【会议纪要与附件内容（高价值信息源）】\n" + "\n\n".join(attachment_texts[:6]) if attachment_texts else "",
        ]
        if part
    )

    # Log what data is actually in the prompt
    has_att = "会议纪要" in prompt or "附件内容" in prompt
    att_section_len = len(prompt.split("【会议纪要与附件内容")[1]) if "【会议纪要与附件内容" in prompt else 0
    logger.info("[weekly-overview] prompt_len=%d, has_attachment_section=%s, att_section_len=%d, attachment_texts_count=%d",
                len(prompt), has_att, att_section_len, len(attachment_texts or []))

    try:
        logger.info("[weekly-overview] AI provider=%s, calling _qwen_generate with new structured prompt...", ai.get_health().provider)
        raw = ai._qwen_generate(
            prompt=prompt,
            system_instruction=WEEKLY_OVERVIEW_SYSTEM_INSTRUCTION,
            response_schema=WEEKLY_OVERVIEW_RESPONSE_SCHEMA,
            timeout_seconds=120.0,
            max_tokens=4000,
            temperature=0.35,
            top_p=0.9,
            enable_thinking=False,
        )
        logger.info("[weekly-overview] AI raw response type=%s, keys=%s", type(raw).__name__, list(raw.keys()) if isinstance(raw, dict) else "N/A")
        if not isinstance(raw, dict):
            logger.warning("[weekly-overview] AI returned non-dict, falling back")
            return fallback_summary, fallback_focus, fallback_next

        headline = _clean_text(str(raw.get("headline") or ""))
        needs_attention = raw.get("needsAttention") or []
        on_track = raw.get("onTrack") or []
        raw_blockers = raw.get("blockerSummary") or []
        if isinstance(raw_blockers, str):
            raw_blockers = [raw_blockers] if raw_blockers.strip() else []
        blocker_items = [_clean_text(str(b)) for b in raw_blockers if _clean_text(str(b))]
        weekly_insight = _clean_text(str(raw.get("nextWeekHint") or ""))
        next_week_focus = [str(item) for item in (raw.get("nextWeekFocus") or [])]

        # Assemble structured output into readable overview text
        overview_parts: list[str] = []
        if headline:
            overview_parts.append(headline)
        if needs_attention:
            overview_parts.append("\n【需要关注】")
            for item in needs_attention:
                if isinstance(item, dict):
                    name = str(item.get("lineName", ""))
                    reason = str(item.get("reason", ""))
                    overview_parts.append(f"• {name}：{reason}")
        if on_track:
            overview_parts.append("\n【正常推进】")
            for item in on_track:
                if isinstance(item, dict):
                    name = str(item.get("lineName", ""))
                    progress = str(item.get("progress", ""))
                    overview_parts.append(f"• {name}：{progress}")
        if blocker_items:
            blocker_lines = "\n".join(f"{i+1}. {b}" for i, b in enumerate(blocker_items))
            overview_parts.append(f"\n【卡点汇总】\n{blocker_lines}")
        if weekly_insight:
            overview_parts.append(f"\n【下周提示】\n{weekly_insight}")

        overview = "\n".join(overview_parts)

        # Build focus_lines from needs_attention + on_track
        focus_lines: list[str] = []
        for item in needs_attention:
            if isinstance(item, dict):
                focus_lines.append(f"{item.get('lineName', '')}｜{item.get('reason', '')}")
        for item in on_track:
            if isinstance(item, dict):
                focus_lines.append(f"{item.get('lineName', '')}｜{item.get('progress', '')}")
        focus_lines = _dedupe_lines(focus_lines, limit=6)

        next_focus = _dedupe_lines(next_week_focus, limit=3)

        logger.info("[weekly-overview] assembled overview len=%d, has【=%s", len(overview), "【" in overview)
        if not ai._has_sufficient_cjk(overview) or len(overview) < 40:
            logger.warning("[weekly-overview] overview failed CJK/length check, falling back. len=%d", len(overview))
            return fallback_summary, fallback_focus, fallback_next
        if not focus_lines:
            focus_lines = fallback_focus
        if not next_focus:
            next_focus = fallback_next
        return overview, focus_lines, next_focus
    except Exception as exc:
        logger.warning("Weekly overview generation failed: %s", exc)
        return fallback_summary, fallback_focus, fallback_next
