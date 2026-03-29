from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime
from typing import Literal

from app.models import (
    EventLineCompletenessRecord,
    EventLineEvidenceSlotRecord,
    EventLineJudgmentRecord,
    EventLineOpportunityCardRecord,
    EventLineRiskCardRecord,
    ReviewDashboardCardTargetRecord,
    ReviewDashboardEvidenceRefRecord,
    EventLineSummaryCardRecord,
    HierarchyReportRecord,
    OrgModelProfileRecord,
    OrganizationDnaModuleRecord,
    ReviewEvidenceWeightRecord,
    ReviewHypothesisRecord,
    ReviewMetricCardRecord,
    TrendSignalRecord,
    WeeklyReviewAnalysisRecord,
    WeeklyReviewTaskEntryRecord,
)
from app.services.knowledge_base import tokenize
from app.services.memory_foundation import sanitize_memory_background_text

ReviewViewerRole = Literal["employee", "department_lead", "admin"]

SUCCESS_KEYWORDS = ("完成", "推进", "落地", "交付", "落实", "确认", "跑通", "有效", "顺畅", "清楚", "达成")
ISSUE_KEYWORDS = ("卡住", "阻力", "困难", "问题", "风险", "不足", "不清", "延迟", "冲突", "等待", "没法", "不明确")
SUPPORT_KEYWORDS = ("需要支持", "需要帮助", "资源", "协同", "支持", "配合", "接口", "协调")
BUSINESS_KEYWORDS = ("客户", "用户", "需求", "方案", "转化", "产品", "项目", "服务", "验证", "交付")
TEAM_KEYWORDS = ("协作", "协同", "对齐", "接口", "责任", "分工", "交接", "支持", "排期", "同步", "配合")
MARKET_KEYWORDS = ("市场", "行业", "竞品", "传播", "渠道", "政策", "外部", "趋势", "流量", "品牌")
GROWTH_KEYWORDS = ("感受", "观察", "状态", "学到", "收获", "反思", "习惯", "节奏", "精力", "判断")

MODULE_LENS: dict[str, Literal["organization", "business", "team", "market"]] = {
    "organization_intro": "organization",
    "business_intro": "business",
    "team_intro": "team",
    "market_intro": "market",
}

LENS_LABEL: dict[str, str] = {
    "execution": "执行层",
    "organization": "组织视角",
    "business": "业务视角",
    "team": "团队视角",
    "market": "市场视角",
    "growth": "成长视角",
}

BUSINESS_CATEGORY_LENS: dict[str, Literal["organization", "business", "team", "market"]] = {
    "业务扩展": "business",
    "项目推进": "business",
    "产品化沉淀": "organization",
    "组织协同": "team",
    "管理机制": "organization",
    "外部合作": "market",
    "专项推进": "business",
}

LIGHTWEIGHT_TAG_ACTIONS: dict[str, str] = {
    "资料不足": "先补齐关键资料、上下文和输入，再判断这件事是否值得继续推进。",
    "等待他人": "先把外部依赖、等待对象和最晚回收时间点写清，避免任务继续悬空。",
    "方向不清": "先补目标、边界和判断标准，不要在方向模糊时继续堆动作。",
    "资源不够": "先确认缺的是人力、时间还是预算，再决定是压缩范围还是争取支持。",
    "工作过度饱和": "这更像容量过载信号，建议优先做取舍，而不是继续叠加任务。",
}

QUARTER_PATTERN = re.compile(r"(Q[1-4]|季度|本季度|季度重点|季度目标|本季)")
TEAM_PLAN_MODULE_MARKER = "部门计划背景"

COMPLETION_STATUS_LABEL: dict[str, str] = {
    "done_on_time": "按时完成",
    "done_late": "延迟完成",
    "in_progress": "仍在推进",
    "not_done": "未完成",
}

ALIGNMENT_STATUS_LABEL: dict[str, str] = {
    "aligned": "明确对齐",
    "partial": "部分对齐",
    "misaligned": "存在偏离",
    "unknown": "待补录",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _sanitize_story_text(value: object | None, *, reject_generic: bool = False, max_length: int = 140) -> str:
    return sanitize_memory_background_text(value, reject_generic=reject_generic, max_length=max_length)


def _sanitize_story_texts(
    values: list[object | None],
    *,
    reject_generic: bool = False,
    limit: int = 6,
    max_length: int = 140,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _sanitize_story_text(value, reject_generic=reject_generic, max_length=max_length)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _item_text(item: WeeklyReviewTaskEntryRecord) -> str:
    reflection = _reflection_text(item)
    tags = " ".join(tag.name for tag in item.taskSnapshot.tags)
    structured = " ".join(
        part
        for part in [
            reflection,
            item.structuredNote.lightweightTag,
            item.structuredNote.progress,
            item.structuredNote.blockerReason,
            item.structuredNote.supportNeeded,
        ]
        if part
    )
    return _clean_text(
        f"{item.taskSnapshot.title} {item.note} {structured} {item.taskSnapshot.listName} {tags}"
    ).lower()


def _item_short_label(item: WeeklyReviewTaskEntryRecord) -> str:
    return item.taskSnapshot.title.strip() or item.taskId


def _reflection_text(item: WeeklyReviewTaskEntryRecord) -> str:
    candidates = [
        item.structuredNote.reflection.strip(),
        item.structuredNote.successExperience.strip(),
        item.structuredNote.supportNeeded.strip(),
        item.structuredNote.failureInsight.strip(),
        item.structuredNote.blockerReason.strip(),
        item.structuredNote.progress.strip(),
        item.note.strip(),
    ]
    return next((item for item in candidates if item), "")


def _lightweight_tag(item: WeeklyReviewTaskEntryRecord) -> str:
    return item.structuredNote.lightweightTag.strip()


def _item_department_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = item.taskSnapshot.orgContext
    return (context.departmentId if context else "") or ""


def _item_focus_item_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = item.taskSnapshot.orgContext
    return (context.focusItemId if context else "") or ""


def _item_department_plan_item_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = item.taskSnapshot.orgContext
    return (context.departmentPlanItemId if context else "") or ""


def _item_project_context(item: WeeklyReviewTaskEntryRecord):
    return item.taskSnapshot.projectContext


def _item_event_line_context(item: WeeklyReviewTaskEntryRecord):
    return item.taskSnapshot.eventLineContext


def _item_event_line_id(item: WeeklyReviewTaskEntryRecord) -> str:
    raw = (item.taskSnapshot.eventLineId or "").strip()
    if raw.startswith("event_line::"):
        return raw.split("::", 1)[1].strip()
    return raw


def _item_event_line_name(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.eventLineName or "").strip()


def _extract_tokens(text: str) -> list[str]:
    return [token for token in tokenize(text) if token and len(token.strip()) >= 2]


def _module_preview(module: OrganizationDnaModuleRecord) -> str:
    return _clean_text(module.summary or module.normalizedText[:360])


def _module_source_text(module: OrganizationDnaModuleRecord) -> str:
    return "\n".join(part for part in [module.markdownContent, module.normalizedText, module.summary] if part).strip()


def _team_plan_modules(dna_modules: list[OrganizationDnaModuleRecord]) -> list[OrganizationDnaModuleRecord]:
    return [
        module
        for module in dna_modules
        if module.moduleKey == "team_intro" and TEAM_PLAN_MODULE_MARKER in module.title
    ]


def _extract_quarter_goal_lines(dna_modules: list[OrganizationDnaModuleRecord]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for module in dna_modules:
        if module.moduleKey != "organization_intro":
            continue
        source_text = _module_source_text(module)
        if not source_text:
            continue
        candidates = re.split(r"[\r\n]+|(?<=[。；;])", source_text)
        for raw in candidates:
            candidate = _clean_text(re.sub(r"^[\-\d\.\)\s、]+", "", raw))
            if len(candidate) < 6 or len(candidate) > 120:
                continue
            if not QUARTER_PATTERN.search(candidate):
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            lines.append(candidate.rstrip("。；;"))
    return lines[:4]


def _dedupe_texts(values: list[str], limit: int = 6) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _clean_text(value)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _truncate_overview_text(value: str, limit: int = 84) -> str:
    normalized = _clean_text(value)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip("，、；：: ") + "…"


OVERVIEW_INFRA_KEYWORDS = ("debug", "排查", "修复", "联调", "上传", "保存", "附件", "可见", "可见性", "回写", "启动", "登录", "卡死")
OVERVIEW_INTEL_KEYWORDS = ("情报", "资讯", "报告", "研究", "倡导", "引关注", "趋势", "观察")
OVERVIEW_COLLAB_KEYWORDS = ("合作", "协作", "协同", "交流", "讨论", "对接", "工作坊", "战略", "诊断", "梳理", "收束")


def _item_full_text(item: WeeklyReviewTaskEntryRecord) -> str:
    snap = item.taskSnapshot
    parts = [
        snap.title,
        getattr(snap, "desc", "") or "",
        getattr(snap, "note", "") or "",
        item.note or "",
        _reflection_text(item),
        snap.clientName or "",
        snap.eventLineName or "",
        snap.listName or "",
    ]
    return _clean_text(" ".join(part for part in parts if part)).lower()


def _client_background_hint(dna_modules: list[OrganizationDnaModuleRecord], client_name: str) -> str:
    if not client_name:
        return ""
    for module in dna_modules:
        if client_name in module.title:
            return _module_source_text(module)
    return ""


def _build_weekly_overview(
    items: list[WeeklyReviewTaskEntryRecord],
    dna_modules: list[OrganizationDnaModuleRecord],
    note_items_count: int,
) -> tuple[str, list[str], list[str]]:
    if not items:
        return ("本周暂无可复盘的事项。", [], [])

    texts = [_item_full_text(item) for item in items]
    infra_items = [item for item, text in zip(items, texts) if _contains_any(text, OVERVIEW_INFRA_KEYWORDS)]
    intel_items = [item for item, text in zip(items, texts) if _contains_any(text, OVERVIEW_INTEL_KEYWORDS)]
    collab_items = [item for item, text in zip(items, texts) if _contains_any(text, OVERVIEW_COLLAB_KEYWORDS)]
    cffc_items = [item for item, text in zip(items, texts) if "cffc" in text or "鸿鹄" in text or "洪峰" in text]

    client_names = _dedupe_texts([item.taskSnapshot.clientName or "" for item in items if item.taskSnapshot.clientName], limit=6)
    companion_clients = [name for name in client_names if any(key in name for key in ("日慈", "为爱", "向光"))]

    focus_lines: list[str] = []
    if infra_items:
        focus_lines.append("软件底层链路修稳")
    if cffc_items:
        focus_lines.append("CFFC 合作推进")
    if companion_clients:
        focus_lines.append("客户陪伴收束")
    if intel_items:
        focus_lines.append("情报沉淀与议题输入")
    if not focus_lines and collab_items:
        focus_lines.append("合作与协作线推进")

    overview_parts: list[str] = ["这周对益语来说，更像是一周在打底、铺线、蓄力。"]

    if infra_items:
        overview_parts.append(
            "本周花了不少精力在把软件底层链路修稳，围绕附件保存、上传写入、新建任务可见性等做了多轮排查，本质是在补地基。"
        )

    if cffc_items:
        background_hint = _client_background_hint(dna_modules, "CFFC")
        extra = ""
        if any(keyword in background_hint for keyword in ("枢纽", "基金会", "行业")):
            extra = "它的意义不只是一次合作，而是通过行业关键枢纽进入更大网络的机会。"
        overview_parts.append(f"围绕 CFFC 的合作讨论和说明迭代在推进。{extra}".rstrip("。"))

    if companion_clients:
        names = "、".join(companion_clients[:2])
        overview_parts.append(f"客户陪伴线开始从泛沟通往更具体的诊断或收束推进，{names} 逐步落到更清楚的项目梳理上。")

    if intel_items:
        intel_titles = _dedupe_texts([item.taskSnapshot.title for item in intel_items if item.taskSnapshot.title], limit=2)
        if intel_titles:
            overview_parts.append(f"本周有值得沉淀的情报线索：{ '；'.join(intel_titles) }，已开始接到后续咨询议题。")
        else:
            overview_parts.append("本周有几条情报线索已经开始接到后续咨询议题。")

    review_ratio = note_items_count / max(1, len(items))
    if review_ratio < 0.3:
        overview_parts.append("当前系统可读的复盘说明仍然偏少，判断深度主要停留在任务事实和备注层。")

    overview_parts.append("整体来看，这是偏打底和铺线的一周。")

    next_focus: list[str] = []
    if cffc_items:
        next_focus.append("把 CFFC 这条线继续往更明确的合作边界和方式上收。")
    if companion_clients:
        next_focus.append("把客户陪伴线推进到更清楚的诊断或项目梳理结果。")
    if review_ratio < 0.3:
        next_focus.append("把本周任务复盘补进系统，让判断不只看到动作。")
    if not next_focus and focus_lines:
        next_focus.append("围绕本周主线做收束性推进，避免同时开太多新线。")

    return " ".join(_dedupe_texts(overview_parts, limit=8)), focus_lines[:4], next_focus[:3]


def _overview_line(title: str, body: str) -> str:
    normalized_title = _clean_text(title).rstrip("：:｜")
    normalized_body = _truncate_overview_text(body)
    if not normalized_title:
        return normalized_body
    if not normalized_body or normalized_body == normalized_title:
        return normalized_title
    return f"{normalized_title}｜{normalized_body}"


def _event_line_story_target(story: dict[str, object]) -> ReviewDashboardCardTargetRecord:
    raw_key = str(story.get("id") or "")
    raw_event_line_id = str(story.get("eventLineId") or "")
    title = str(story.get("name") or "").strip()
    clients = list(story.get("clients") or [])
    category = str(story.get("category") or "").strip()
    if raw_key.startswith("event_line::") and raw_event_line_id:
        return ReviewDashboardCardTargetRecord(
            targetType="event_line",
            targetId=raw_event_line_id,
            targetLabel=title or raw_event_line_id,
            targetFilters={
                "eventLineId": raw_event_line_id,
                "businessCategory": category or None,
            },
        )
    return ReviewDashboardCardTargetRecord(
        targetType="task_view",
        targetId=raw_key or f"story::{title}",
        targetLabel=title or "相关任务",
        targetFilters={
            "groupKey": raw_key,
            "clientNames": [str(item) for item in clients if str(item).strip()],
            "businessCategories": [category] if category else [],
            "onlyWithEventLine": False,
        },
    )


def _story_evidence_refs(
    story: dict[str, object],
    *,
    include_event_line_ref: bool = True,
    limit: int = 4,
) -> list[ReviewDashboardEvidenceRefRecord]:
    refs: list[ReviewDashboardEvidenceRefRecord] = []
    raw_key = str(story.get("id") or "")
    raw_event_line_id = str(story.get("eventLineId") or "")
    title = str(story.get("name") or "").strip()
    if include_event_line_ref and raw_key.startswith("event_line::") and raw_event_line_id:
        refs.append(
            ReviewDashboardEvidenceRefRecord(
                sourceType="event_line",
                sourceId=raw_event_line_id,
                title=title or raw_event_line_id,
                summary=_truncate_overview_text(
                    _first_non_empty(
                        [str(item) for item in story.get("lineSummaries", []) if str(item).strip()]
                        + [str(item) for item in story.get("lineIntents", []) if str(item).strip()]
                    )
                    or title
                ),
            )
        )
    task_ids = [str(item) for item in story.get("taskIds", []) if str(item).strip()]
    task_titles = [str(item) for item in story.get("taskTitles", []) if str(item).strip()]
    for task_id, task_title in zip(task_ids[:limit], task_titles[:limit]):
        refs.append(
            ReviewDashboardEvidenceRefRecord(
                sourceType="task",
                sourceId=task_id,
                title=task_title,
                summary=_truncate_overview_text(task_title),
            )
        )
    return refs[:limit]


def _event_line_overview_lines(items: list[EventLineSummaryCardRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [
            _overview_line(item.title, item.whatHappenedThisWeek or item.currentState or item.whatThisLineIs)
            for item in items[:limit]
        ],
        limit=limit,
    )


def _judgment_overview_lines(items: list[EventLineJudgmentRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.whatHappened or item.whyItMatters or item.nextWeekFocus) for item in items[:limit]],
        limit=limit,
    )


def _judgment_blocker_lines(items: list[EventLineJudgmentRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.coreBlocker or item.riskIfIgnored) for item in items[:limit]],
        limit=limit,
    )


def _judgment_action_lines(items: list[EventLineJudgmentRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.minimumAction or item.nextWeekFocus) for item in items[:limit]],
        limit=limit,
    )


def _risk_overview_lines(items: list[EventLineRiskCardRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.statement) for item in items[:limit]],
        limit=limit,
    )


def _opportunity_overview_lines(items: list[EventLineOpportunityCardRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.statement) for item in items[:limit]],
        limit=limit,
    )


def _hypothesis_overview_lines(items: list[ReviewHypothesisRecord], limit: int = 4) -> list[str]:
    return _dedupe_texts(
        [_overview_line(item.title, item.statement) for item in items[:limit]],
        limit=limit,
    )


def _next_focus_overview_lines(values: list[str], limit: int = 4) -> list[str]:
    return _dedupe_texts([_overview_line("下周关注", value) for value in values[:limit]], limit=limit)


def _department_plan_reference_texts(
    org_model_profile: OrgModelProfileRecord | None,
    *,
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
) -> list[str]:
    if org_model_profile is None:
        return []
    department_ids = {_item_department_id(item) for item in items if _item_department_id(item)}
    linked_plan_item_ids = {_item_department_plan_item_id(item) for item in items if _item_department_plan_item_id(item)}
    linked_focus_ids = {_item_focus_item_id(item) for item in items if _item_focus_item_id(item)}
    texts: list[str] = []
    for plan in org_model_profile.departmentPlans:
        if plan.weekLabel != week_label:
            continue
        if department_ids and plan.departmentId and plan.departmentId not in department_ids:
            continue
        if plan.summary.strip():
            texts.append(plan.summary.strip())
        for plan_item in plan.items:
            if linked_plan_item_ids and plan_item.id not in linked_plan_item_ids and plan_item.focusItemId not in linked_focus_ids:
                continue
            texts.append(
                _clean_text(
                    " ".join(
                        part
                        for part in [
                            plan_item.title,
                            plan_item.statement,
                            plan_item.expectedOutput,
                        ]
                        if part
                    )
                )
            )
    if not texts and department_ids:
        for plan in org_model_profile.departmentPlans:
            if plan.weekLabel != week_label:
                continue
            if plan.departmentId and plan.departmentId not in department_ids:
                continue
            texts.extend(
                _clean_text(" ".join(part for part in [item.title, item.statement, item.expectedOutput] if part))
                for item in plan.items
            )
            if plan.summary.strip():
                texts.append(plan.summary.strip())
    return _dedupe_texts(texts, limit=8)


def _focus_item_reference_texts(org_model_profile: OrgModelProfileRecord | None) -> list[str]:
    if org_model_profile is None:
        return []
    texts = [
        _clean_text(" ".join(part for part in [item.title, item.statement, " ".join(item.evidenceKeywords)] if part))
        for item in org_model_profile.focusItems
        if item.status in {"draft", "active"}
    ]
    return _dedupe_texts(texts, limit=6)


def _project_context_summary(items: list[WeeklyReviewTaskEntryRecord]) -> dict[str, object]:
    contexts = [context for item in items if (context := _item_project_context(item))]
    client_names = _dedupe_texts([context.clientName for context in contexts if context.clientName], limit=4)
    stages = _dedupe_texts([context.stage or "" for context in contexts], limit=3)
    goals = _dedupe_texts([context.goalSummary for context in contexts if context.goalSummary], limit=3)
    risks = _dedupe_texts([context.riskSummary for context in contexts if context.riskSummary], limit=3)
    evidence = _dedupe_texts([evidence for context in contexts for evidence in context.sourceEvidence], limit=6)
    completeness_levels = Counter(context.infoCompleteness for context in contexts if context.infoCompleteness)
    highest_completeness = "low"
    if completeness_levels.get("high"):
        highest_completeness = "high"
    elif completeness_levels.get("medium"):
        highest_completeness = "medium"
    return {
        "count": len(contexts),
        "clients": client_names,
        "stages": stages,
        "goals": goals,
        "risks": risks,
        "evidence": evidence,
        "infoCompleteness": highest_completeness,
    }


def _event_line_summary(items: list[WeeklyReviewTaskEntryRecord]) -> dict[str, object]:
    groups: dict[str, dict[str, object]] = {}
    for item in items:
        event_line_id = _item_event_line_id(item)
        if not event_line_id:
            continue
        bucket = groups.setdefault(
            event_line_id,
            {
                "name": _item_event_line_name(item) or _item_short_label(item),
                "items": [],
            },
        )
        bucket["items"].append(item)  # type: ignore[index]

    multi_task_groups = [
        bucket
        for bucket in groups.values()
        if len(bucket["items"]) >= 2  # type: ignore[index]
    ]
    blocked_groups = []
    for bucket in groups.values():
        bucket_items: list[WeeklyReviewTaskEntryRecord] = bucket["items"]  # type: ignore[assignment]
        if any(_completion_status(item) in {"in_progress", "not_done"} for item in bucket_items):
            blocked_groups.append(bucket)
    names = _dedupe_texts([str(bucket["name"]) for bucket in groups.values()], limit=4)
    blocked_names = _dedupe_texts([str(bucket["name"]) for bucket in blocked_groups], limit=3)
    return {
        "groupCount": len(groups),
        "taskCount": sum(len(bucket["items"]) for bucket in groups.values()),  # type: ignore[index]
        "multiTaskGroupCount": len(multi_task_groups),
        "names": names,
        "blockedGroupCount": len(blocked_groups),
        "blockedNames": blocked_names,
    }


def _item_group_key(item: WeeklyReviewTaskEntryRecord) -> str:
    event_line_id = _item_event_line_id(item)
    if event_line_id:
        return f"event_line::{event_line_id}"
    project_context = _item_project_context(item)
    if project_context and (project_context.clientId or project_context.clientName):
        return f"project::{project_context.clientId or project_context.clientName}"
    return ""


def _item_group_name(item: WeeklyReviewTaskEntryRecord) -> str:
    event_line_name = _item_event_line_name(item)
    if event_line_name:
        return event_line_name
    project_context = _item_project_context(item)
    if project_context and project_context.clientName:
        return project_context.clientName
    return _item_short_label(item)


def _item_next_step_hint(item: WeeklyReviewTaskEntryRecord) -> str:
    candidates = [
        item.structuredNote.nextAction.strip(),
        item.structuredNote.supportNeeded.strip(),
        item.structuredNote.blockerReason.strip(),
        item.structuredNote.failureInsight.strip(),
        item.structuredNote.progress.strip(),
        item.note.strip(),
    ]
    return next((candidate for candidate in candidates if candidate), "")


def _recent_decision_hint(item: WeeklyReviewTaskEntryRecord) -> str:
    candidates = [
        item.structuredNote.planCommitment.strip(),
        item.structuredNote.progress.strip(),
        _reflection_text(item),
        item.note.strip(),
    ]
    decision_keywords = ("决定", "确认", "改为", "暂定", "确定", "拍板", "收束", "切到", "优先")
    return next((candidate for candidate in candidates if candidate and _contains_any(candidate, decision_keywords)), "")


def _infer_business_category(text: str) -> str:
    if _contains_any(text, ("基金会", "客户", "合作", "工作坊", "方案", "拜访", "赋能", "拓展", "bd")):
        return "业务扩展"
    if _contains_any(text, ("模板", "标准件", "系统", "产品", "自动化", "sop", "组件", "资料底盘", "沉淀")):
        return "产品化沉淀"
    if _contains_any(text, ("交付", "推进", "落地", "收束", "会后", "对接", "反馈", "执行")):
        return "项目推进"
    if _contains_any(text, ("流程", "复核", "审批", "协同", "对齐", "汇报", "支持", "确认链")):
        return "组织协同"
    if _contains_any(text, ("预算", "资源", "机制", "规则", "权限", "治理")):
        return "管理机制"
    if _contains_any(text, ("传播", "活动", "品牌", "外部", "媒体", "渠道")):
        return "外部合作"
    return "专项推进"


def _event_line_story_groups(items: list[WeeklyReviewTaskEntryRecord]) -> list[dict[str, object]]:
    groups: dict[str, dict[str, object]] = {}
    for item in items:
        group_key = _item_group_key(item)
        if not group_key:
            continue
        bucket = groups.setdefault(
            group_key,
            {
                "id": group_key,
                "eventLineId": _item_event_line_id(item) or group_key,
                "name": _item_group_name(item),
                "items": [],
                "taskTitles": [],
                "clients": [],
                "stages": [],
                "goals": [],
                "risks": [],
                "currentFocuses": [],
                "currentBlockers": [],
                "nextSteps": [],
                "recentProgresses": [],
                "owners": [],
                "moduleNames": [],
                "flowNames": [],
                "recentDecisions": [],
                "lineSummaries": [],
                "lineIntents": [],
                "lineStages": [],
                "lineBlockers": [],
                "lineNextSteps": [],
                "lineRecentDecisions": [],
            },
        )
        bucket["items"].append(item)  # type: ignore[index]
        bucket["taskTitles"].append(_item_short_label(item))  # type: ignore[index]
        if item.taskSnapshot.ownerName:
            bucket["owners"].append(item.taskSnapshot.ownerName)  # type: ignore[index]
        event_line_context = _item_event_line_context(item)
        if event_line_context:
            if event_line_context.summary:
                bucket["lineSummaries"].append(event_line_context.summary)  # type: ignore[index]
            if event_line_context.intent:
                bucket["lineIntents"].append(event_line_context.intent)  # type: ignore[index]
            if event_line_context.stage:
                bucket["lineStages"].append(event_line_context.stage)  # type: ignore[index]
            if event_line_context.currentBlocker:
                bucket["lineBlockers"].append(event_line_context.currentBlocker)  # type: ignore[index]
            if event_line_context.nextStep:
                bucket["lineNextSteps"].append(event_line_context.nextStep)  # type: ignore[index]
            if event_line_context.recentDecision:
                bucket["lineRecentDecisions"].append(event_line_context.recentDecision)  # type: ignore[index]
            if event_line_context.primaryClientName:
                bucket["clients"].append(event_line_context.primaryClientName)  # type: ignore[index]
        project_context = _item_project_context(item)
        if project_context:
            if project_context.clientName:
                bucket["clients"].append(project_context.clientName)  # type: ignore[index]
            if project_context.stage:
                bucket["stages"].append(project_context.stage)  # type: ignore[index]
            if project_context.goalSummary:
                bucket["goals"].append(project_context.goalSummary)  # type: ignore[index]
            if project_context.riskSummary:
                bucket["risks"].append(project_context.riskSummary)  # type: ignore[index]
            if getattr(project_context, "currentFocus", None):
                bucket["currentFocuses"].append(project_context.currentFocus)  # type: ignore[index]
            if getattr(project_context, "currentBlocker", None):
                bucket["currentBlockers"].append(project_context.currentBlocker)  # type: ignore[index]
            if getattr(project_context, "nextAction", None):
                bucket["nextSteps"].append(project_context.nextAction)  # type: ignore[index]
            if getattr(project_context, "recentProgress", None):
                bucket["recentProgresses"].append(project_context.recentProgress)  # type: ignore[index]
            if getattr(project_context, "projectModuleName", None):
                bucket["moduleNames"].append(project_context.projectModuleName)  # type: ignore[index]
            if getattr(project_context, "projectFlowName", None):
                bucket["flowNames"].append(project_context.projectFlowName)  # type: ignore[index]
        next_step_hint = _item_next_step_hint(item)
        if next_step_hint:
            bucket["nextSteps"].append(next_step_hint)  # type: ignore[index]
        recent_decision = _recent_decision_hint(item)
        if recent_decision:
            bucket["recentDecisions"].append(recent_decision)  # type: ignore[index]

    stories: list[dict[str, object]] = []
    for bucket in groups.values():
        bucket_items: list[WeeklyReviewTaskEntryRecord] = bucket["items"]  # type: ignore[assignment]
        task_titles = _dedupe_texts([str(item) for item in bucket["taskTitles"]], limit=4)
        clients = _sanitize_story_texts([str(item) for item in bucket["clients"]], limit=2, max_length=40)
        stages = _sanitize_story_texts([str(item) for item in bucket["stages"]], limit=2, max_length=40)
        goals = _sanitize_story_texts([str(item) for item in bucket["goals"]], reject_generic=True, limit=2)
        risks = _sanitize_story_texts([str(item) for item in bucket["risks"]], reject_generic=True, limit=2)
        current_focuses = _sanitize_story_texts([str(item) for item in bucket["currentFocuses"]], reject_generic=True, limit=2)
        current_blockers = _sanitize_story_texts([str(item) for item in bucket["currentBlockers"]], reject_generic=True, limit=2)
        next_steps = _sanitize_story_texts([str(item) for item in bucket["nextSteps"]], reject_generic=True, limit=2)
        recent_progresses = _sanitize_story_texts([str(item) for item in bucket["recentProgresses"]], reject_generic=True, limit=2)
        owners = _sanitize_story_texts([str(item) for item in bucket["owners"]], limit=3, max_length=16)
        module_names = _sanitize_story_texts([str(item) for item in bucket["moduleNames"]], limit=2, max_length=40)
        flow_names = _sanitize_story_texts([str(item) for item in bucket["flowNames"]], limit=2, max_length=40)
        recent_decisions = _sanitize_story_texts([str(item) for item in bucket["recentDecisions"]], reject_generic=True, limit=2)
        line_summaries = _sanitize_story_texts([str(item) for item in bucket["lineSummaries"]], reject_generic=True, limit=2)
        line_intents = _sanitize_story_texts([str(item) for item in bucket["lineIntents"]], reject_generic=True, limit=2)
        line_stages = _sanitize_story_texts([str(item) for item in bucket["lineStages"]], limit=2, max_length=40)
        line_blockers = _sanitize_story_texts([str(item) for item in bucket["lineBlockers"]], reject_generic=True, limit=2)
        line_next_steps = _sanitize_story_texts([str(item) for item in bucket["lineNextSteps"]], reject_generic=True, limit=2)
        line_recent_decisions = _sanitize_story_texts([str(item) for item in bucket["lineRecentDecisions"]], reject_generic=True, limit=2)
        stage_sources = line_stages + stages
        current_focus_sources = line_intents + current_focuses
        goal_sources = line_intents + line_summaries + goals + current_focuses
        blocker_sources = line_blockers + current_blockers + risks
        next_step_sources = line_next_steps + next_steps
        recent_decision_sources = line_recent_decisions + recent_decisions
        text_blob = " ".join(
            [
                str(bucket["name"]),
                " ".join(task_titles),
                " ".join(clients),
                " ".join(stage_sources),
                " ".join(module_names),
                " ".join(flow_names),
                " ".join(current_focus_sources),
                " ".join(goal_sources),
                " ".join(blocker_sources),
                " ".join(next_step_sources),
                " ".join(recent_progresses),
                " ".join(recent_decision_sources),
            ]
        ).lower()
        stories.append(
            {
                "id": str(bucket["id"]),
                "name": str(bucket["name"]),
                "taskIds": [item.taskId for item in bucket_items],
                "taskTitles": task_titles,
                "clients": clients,
                "stages": stage_sources,
                "currentFocuses": current_focus_sources,
                "currentBlockers": blocker_sources,
                "goals": goal_sources,
                "risks": risks,
                "nextSteps": next_step_sources,
                "recentProgresses": recent_progresses,
                "owners": owners,
                "moduleNames": module_names,
                "flowNames": flow_names,
                "recentDecisions": recent_decision_sources,
                "lineSummaries": line_summaries,
                "lineIntents": line_intents,
                "completedCount": sum(1 for item in bucket_items if _completion_status(item) in {"done_on_time", "done_late"}),
                "unfinishedCount": sum(1 for item in bucket_items if _completion_status(item) in {"in_progress", "not_done"}),
                "category": _infer_business_category(text_blob),
            }
        )
    stories.sort(
        key=lambda story: (
            -int(story["unfinishedCount"]),
            -len(story["taskIds"]),  # type: ignore[arg-type]
            str(story["name"]),
        )
    )
    return stories


def _slot_strength_score(value: Literal["strong", "medium", "weak", "none"]) -> float:
    if value == "strong":
        return 1.0
    if value == "medium":
        return 0.75
    if value == "weak":
        return 0.5
    return 0.0


def _event_line_completeness_status(score: int) -> Literal["insufficient", "summary_ready", "forecast_ready", "high_confidence"]:
    if score >= 85:
        return "high_confidence"
    if score >= 65:
        return "forecast_ready"
    if score >= 40:
        return "summary_ready"
    return "insufficient"


def _prediction_readiness(status: Literal["insufficient", "summary_ready", "forecast_ready", "high_confidence"]) -> Literal["not_ready", "summary_only", "conservative_forecast", "strong_forecast"]:
    if status == "high_confidence":
        return "strong_forecast"
    if status == "forecast_ready":
        return "conservative_forecast"
    if status == "summary_ready":
        return "summary_only"
    return "not_ready"


def _build_event_line_slot(
    *,
    key: Literal["stage", "goal", "blocker", "next_action", "recent_change", "owner_chain", "recent_decision", "project_link"],
    label: str,
    values: list[str],
    source_types: list[Literal["event_line", "task_fact", "project_context", "user_note", "uploaded_doc", "manual_clarification"]],
    recommended_fix: Literal["upload_docs", "clarify_now", "wait_for_more_trace"],
    fallback_summary: str,
    prefer_full_when_any: bool = False,
) -> EventLineEvidenceSlotRecord:
    cleaned = _dedupe_texts(values, limit=2)
    if cleaned:
        if prefer_full_when_any or len(cleaned) >= 2:
            coverage: Literal["full", "partial", "missing"] = "full"
            strength: Literal["strong", "medium", "weak", "none"] = "strong" if len(source_types) >= 2 or len(cleaned) >= 2 else "medium"
        else:
            coverage = "partial"
            strength = "medium" if source_types else "weak"
        summary = "；".join(cleaned)
    else:
        coverage = "missing"
        strength = "none"
        summary = fallback_summary
    return EventLineEvidenceSlotRecord(
        key=key,
        label=label,
        coverage=coverage,
        evidenceStrength=strength,
        sourceTypes=source_types,
        summary=summary,
        recommendedFix=recommended_fix,
    )


def _infer_risk_type(text: str) -> Literal["schedule_drift", "collaboration_friction", "decision_lag", "goal_drift", "workflow_breakdown", "overload"]:
    normalized = text.lower()
    if _contains_any(normalized, ("协作", "接口", "对齐", "等待他人", "跨部门", "配合")):
        return "collaboration_friction"
    if _contains_any(normalized, ("审批", "决策", "确认", "拍板", "定不下来")):
        return "decision_lag"
    if _contains_any(normalized, ("流程", "步骤", "卡点", "模板")):
        return "workflow_breakdown"
    if _contains_any(normalized, ("资源", "过载", "饱和", "人手", "容量")):
        return "overload"
    if _contains_any(normalized, ("目标", "方向", "偏", "不清")):
        return "goal_drift"
    return "schedule_drift"


BUSINESS_CATEGORY_THEME: dict[str, dict[str, str]] = {
    "业务扩展": {
        "identity": "做客户关系推进与合作收束",
        "progress": "客户判断、方案确认和下一轮沟通准备",
        "state": "关键不是再铺更多动作，而是把合作边界和关键确认节点说死",
        "fallback_blocker": "合作边界、确认节奏或下一轮沟通节点",
        "fallback_next": "先把下一轮沟通、关键人和合作边界收住",
        "upside": "把零散接触转成更清楚的业务机会，并让领导判断是否值得继续加码",
        "admin_risk_tail": "机构层会继续看不清这条线究竟是高潜机会、一般跟进，还是应该及时止损的探索。",
        "employee_risk_tail": "执行会继续陷在反复确认里，很难把推进动作收成明确进展。",
        "opportunity_type": "momentum_building",
    },
    "项目推进": {
        "identity": "做交付收口与推进节奏控制",
        "progress": "把交付动作往可审阅、可执行或可验收状态推进",
        "state": "重点不是继续加任务，而是把交付收口、确认链和接口责任压实",
        "fallback_blocker": "交付接口、资料补齐或确认链收口不够",
        "fallback_next": "先把当前交付动作压成明确收口节点",
        "upside": "把这条线从忙碌推进变成可复盘的稳定交付节奏",
        "admin_risk_tail": "这条线会继续拖慢项目节奏，并消耗管理层对关键交付的判断带宽。",
        "employee_risk_tail": "执行会继续卡在交接、补齐和来回确认上，返工会明显增加。",
        "opportunity_type": "repeatable_pattern",
    },
    "产品化沉淀": {
        "identity": "沉淀模板、标准件和系统能力",
        "progress": "把零散经验、资料和判断固化成可复用结构",
        "state": "重点不是再补更多描述，而是把可复用结构、样本边界和输出标准钉住",
        "fallback_blocker": "结构还没钉死、输入样本不稳或标准还不统一",
        "fallback_next": "先把样本、结构和输出标准收束成可复用件",
        "upside": "一旦收束，会直接变成模板、标准件或 AI 可复用判断组件",
        "admin_risk_tail": "组织会持续重复造轮子，沉淀不下来，后续 AI 也读不到稳定结构。",
        "employee_risk_tail": "这条线会一直停留在整理阶段，难以真正变成可复用资产。",
        "opportunity_type": "repeatable_pattern",
    },
    "组织协同": {
        "identity": "做责任对齐、审批确认和协同接口收束",
        "progress": "把跨人协作、确认链和责任边界逐步说清",
        "state": "重点不是继续催动作，而是先明确谁拍板、谁配合、谁负责收口",
        "fallback_blocker": "责任边界、确认链或跨人接口还没收拢",
        "fallback_next": "先明确拍板人、配合人和最晚回收时间",
        "upside": "协同一旦收束，后续同类事项会明显减少来回确认成本",
        "admin_risk_tail": "它会把局部卡点放大成管理负荷，并不断占用上级确认带宽。",
        "employee_risk_tail": "这条线会继续停留在等待和确认里，个人推进感会很弱。",
        "opportunity_type": "process_upgrade",
    },
    "管理机制": {
        "identity": "做规则、资源和管理节奏调校",
        "progress": "把优先级、资源配置和机制边界逐步调顺",
        "state": "重点不是继续堆任务，而是先把资源、规则和优先级重新排清",
        "fallback_blocker": "资源配置、规则边界或管理节奏仍然不顺",
        "fallback_next": "先明确资源、优先级和规则边界，再继续投入",
        "upside": "一旦调顺，会直接释放管理带宽，并减少后续同类摩擦",
        "admin_risk_tail": "它会把局部问题不断抬升成机构层面的管理噪音。",
        "employee_risk_tail": "这条线会持续让执行感到用力很多，但推进很慢。",
        "opportunity_type": "process_upgrade",
    },
    "外部合作": {
        "identity": "做外部伙伴、品牌或渠道连接",
        "progress": "把外部关系、合作接口和共同动作往前推进",
        "state": "重点不是继续扩圈，而是把合作接口、共同目标和下一步动作压实",
        "fallback_blocker": "合作接口、对外口径或共同动作还没收束",
        "fallback_next": "先把合作接口和下一步共同动作说清",
        "upside": "如果收束得当，会把外部连接放大成更稳定的渠道或品牌势能",
        "admin_risk_tail": "它会持续消耗外部关系信用，但还形不成真正可放大的合作资产。",
        "employee_risk_tail": "推进会一直停在外部沟通层，难以形成更实的合作结果。",
        "opportunity_type": "leverage_point",
    },
    "专项推进": {
        "identity": "推进当前核心事项",
        "progress": "把关键动作往可收束状态推进",
        "state": "重点是先把当前阶段最关键的动作和判断压实",
        "fallback_blocker": "当前阻塞还没有被稳定识别",
        "fallback_next": "先把下一步动作说清",
        "upside": "如果顺着这条线补齐背景和下一步动作，后续判断会明显更准",
        "admin_risk_tail": "这条线会继续停留在零散动作层，管理层难以判断是否值得继续投入。",
        "employee_risk_tail": "执行会继续像在忙，但很难形成清楚的推进感。",
        "opportunity_type": "momentum_building",
    },
}


def _story_theme(category: str) -> dict[str, str]:
    return BUSINESS_CATEGORY_THEME.get(category, BUSINESS_CATEGORY_THEME["专项推进"])


def _first_non_empty(values: list[str]) -> str:
    return next((value for value in values if value), "")


def _story_subject_name(story: dict[str, object]) -> str:
    clients = list(story["clients"])  # type: ignore[arg-type]
    name = str(story["name"])
    if clients:
        client = clients[0]
        if client and client in name:
            return f"{client}这条线"
    return f"{name}这条线"


def _story_kind(category: str, *, project_name: str | None) -> Literal["project_line", "issue_line", "coordination_line", "case_line", "custom"]:
    if category in {"业务扩展", "项目推进", "外部合作"} and project_name:
        return "project_line"
    if category in {"组织协同", "管理机制"}:
        return "coordination_line"
    if category == "产品化沉淀":
        return "case_line"
    if category == "专项推进" and not project_name:
        return "issue_line"
    return "custom"


def _compose_story_identity(
    category: str,
    *,
    story_name: str,
    project_name: str | None,
    module_name: str | None,
    flow_name: str | None,
    line_summary: str,
) -> str:
    theme = _story_theme(category)
    anchor = module_name or flow_name or project_name or story_name
    if line_summary:
        return line_summary
    if category == "业务扩展":
        return f"这是围绕 {anchor} 做客户关系推进与合作收束的一条业务扩展线。"
    if category == "项目推进":
        return f"这是围绕 {anchor} 做交付收口与推进节奏控制的一条项目推进线。"
    if category == "产品化沉淀":
        return f"这是围绕 {anchor} 沉淀模板、标准件和系统能力的一条产品化线。"
    if category == "组织协同":
        return f"这是围绕 {anchor} 做责任对齐、审批确认和协同接口收束的一条协同线。"
    if category == "管理机制":
        return f"这是围绕 {anchor} 做规则、资源和管理节奏调校的一条管理线。"
    if category == "外部合作":
        return f"这是围绕 {anchor} 做外部伙伴、品牌或渠道连接的一条合作线。"
    return f"这是围绕 {anchor} {theme['identity']}的一条连续推进线。"


def _compose_story_week_progress(
    category: str,
    *,
    focus: str,
    signal: str,
    task_titles: list[str],
) -> str:
    theme = _story_theme(category)
    if focus:
        return f"本周主要在推进：{focus}。"
    if signal:
        return f"本周已经出现的关键推进信号是：{signal}。"
    task_text = "、".join(task_titles[:2])
    if task_text:
        return f"本周主要围绕 {task_text} 推进 {theme['progress']}。"
    return f"本周主要在推进 {theme['progress']}。"


def _compose_story_state(
    category: str,
    *,
    stage_label: str,
    completed_count: int,
    unfinished_count: int,
) -> str:
    theme = _story_theme(category)
    parts = [f"当前更像处在「{stage_label}」阶段。"]
    if completed_count and unfinished_count:
        parts.append(f"本周已有 {completed_count} 项动作形成推进，但还有 {unfinished_count} 项没有收束。")
    elif completed_count:
        parts.append(f"本周已有 {completed_count} 项动作形成推进。")
    elif unfinished_count:
        parts.append(f"本周仍有 {unfinished_count} 项关键动作待收束。")
    parts.append(theme["state"] + "。")
    return " ".join(parts)


def _compose_story_blocker(category: str, blocker_text: str) -> str:
    theme = _story_theme(category)
    return blocker_text or f"当前最需要直面的阻力仍然更像：{theme['fallback_blocker']}。"


def _compose_story_next_move(category: str, next_move: str) -> str:
    theme = _story_theme(category)
    if next_move:
        return next_move
    return theme["fallback_next"] + "。"


def _compose_risk_statement(
    category: str,
    *,
    subject: str,
    blocker_text: str,
    viewer_role: ReviewViewerRole,
) -> str:
    theme = _story_theme(category)
    blocker = blocker_text or theme["fallback_blocker"]
    if viewer_role == "admin":
        return f"{subject} 当前卡在“{blocker}”，如果未来 1-2 周还不收束，这条{category}线会继续拖慢推进，并让管理层看不清该不该继续加码。"
    if viewer_role == "department_lead":
        return f"{subject} 当前卡在“{blocker}”，如果未来 1-2 周还不收束，这条线会继续占住部门带宽，并让负责人很难判断该先收哪一段。"
    return f"{subject} 当前卡在“{blocker}”，如果未来 1-2 周还不收束，这条线会继续停留在反复确认和来回推进里。"


def _compose_risk_if_ignored(
    category: str,
    *,
    viewer_role: ReviewViewerRole,
) -> str:
    theme = _story_theme(category)
    if viewer_role == "admin":
        return theme["admin_risk_tail"]
    if viewer_role == "department_lead":
        return "这条线会继续把局部卡点放大成部门级协同和取舍压力，负责人需要不断介入收口。"
    return theme["employee_risk_tail"]


def _compose_opportunity_statement(
    category: str,
    *,
    subject: str,
    signal: str,
    viewer_role: ReviewViewerRole,
) -> str:
    theme = _story_theme(category)
    core_signal = signal or theme["progress"]
    if viewer_role == "admin":
        return f"{subject} 已经开始形成连续推进势能，当前最值得放大的信号是：{core_signal}。"
    if viewer_role == "department_lead":
        return f"{subject} 已经开始形成部门内可放大的正向势能，当前最值得继续压实的信号是：{core_signal}。"
    return f"{subject} 已经开始形成可继续推进的顺手感，当前最值得延续的信号是：{core_signal}。"


def _compose_opportunity_upside(category: str, *, viewer_role: ReviewViewerRole) -> str:
    theme = _story_theme(category)
    if viewer_role == "admin":
        return f"如果继续顺着这条线补齐背景和下一步动作，它更容易长成 {theme['upside']}。"
    if viewer_role == "department_lead":
        return f"如果继续顺着这条线收束，部门里同类事项会更容易形成 {theme['upside']}。"
    return f"如果继续顺着这条线往前推，它更容易从零散动作变成 {theme['upside']}。"


def _compose_opportunity_amplifier(category: str, *, next_move: str, viewer_role: ReviewViewerRole) -> str:
    move = next_move or _story_theme(category)["fallback_next"]
    if viewer_role == "admin":
        return f"继续按“{move}”推进，并把这条线当前有效做法沉淀下来。"
    if viewer_role == "department_lead":
        return f"继续按“{move}”推进，并把这条线当前有效做法沉淀给部门复用。"
    return f"先按“{move}”继续推进，再把这次有效做法留成可复用经验。"


def _build_event_line_intelligence(
    items: list[WeeklyReviewTaskEntryRecord],
    *,
    viewer_role: ReviewViewerRole = "employee",
) -> tuple[list[EventLineSummaryCardRecord], list[EventLineCompletenessRecord], list[EventLineRiskCardRecord], list[EventLineOpportunityCardRecord]]:
    stories = _event_line_story_groups(items)
    summaries: list[EventLineSummaryCardRecord] = []
    completeness_records: list[EventLineCompletenessRecord] = []
    risk_cards: list[EventLineRiskCardRecord] = []
    opportunity_cards: list[EventLineOpportunityCardRecord] = []
    slot_weights = {
        "stage": 15,
        "goal": 15,
        "blocker": 15,
        "next_action": 15,
        "recent_change": 10,
        "owner_chain": 10,
        "recent_decision": 10,
        "project_link": 10,
    }

    for story in stories:
        category = str(story["category"])
        theme = _story_theme(category)
        stage_values = list(story["stages"])  # type: ignore[arg-type]
        goal_values = list(story["goals"]) + list(story["currentFocuses"])  # type: ignore[arg-type]
        blocker_values = list(story["currentBlockers"]) + list(story["risks"])  # type: ignore[arg-type]
        next_action_values = list(story["nextSteps"])  # type: ignore[arg-type]
        recent_change_values = list(story["recentProgresses"])  # type: ignore[arg-type]
        owner_values = list(story["owners"])  # type: ignore[arg-type]
        recent_decision_values = list(story["recentDecisions"])  # type: ignore[arg-type]
        project_link_values = list(story["clients"]) + list(story["moduleNames"]) + list(story["flowNames"])  # type: ignore[arg-type]
        task_title_values = list(story["taskTitles"])  # type: ignore[arg-type]
        line_summary_values = list(story.get("lineSummaries", []))  # type: ignore[arg-type]
        line_intent_values = list(story.get("lineIntents", []))  # type: ignore[arg-type]

        slots = [
            _build_event_line_slot(
                key="stage",
                label="当前阶段",
                values=stage_values,
                source_types=["project_context"] if stage_values else [],
                recommended_fix="clarify_now",
                fallback_summary="当前还没有明确写出这条线推进到哪个阶段。",
                prefer_full_when_any=True,
            ),
            _build_event_line_slot(
                key="goal",
                label="当前目标",
                values=goal_values or task_title_values[:1],
                source_types=["project_context"] if goal_values else ["task_fact"] if task_title_values else [],
                recommended_fix="upload_docs" if not goal_values else "clarify_now",
                fallback_summary="当前还看不清这条线这周最关键要达成什么。",
            ),
            _build_event_line_slot(
                key="blocker",
                label="当前阻塞",
                values=blocker_values,
                source_types=["project_context", "user_note"] if blocker_values else [],
                recommended_fix="clarify_now",
                fallback_summary="暂时还没有稳定识别到这条线最主要的阻塞。",
                prefer_full_when_any=True,
            ),
            _build_event_line_slot(
                key="next_action",
                label="下一步动作",
                values=next_action_values,
                source_types=["project_context", "user_note"] if next_action_values else [],
                recommended_fix="clarify_now",
                fallback_summary="还缺下一步最关键动作，所以很难判断这条线接下来怎么变。",
                prefer_full_when_any=True,
            ),
            _build_event_line_slot(
                key="recent_change",
                label="最近关键变化",
                values=recent_change_values or list(story["taskTitles"]),  # type: ignore[arg-type]
                source_types=["project_context"] if recent_change_values else ["task_fact"] if story["taskTitles"] else [],
                recommended_fix="wait_for_more_trace" if recent_change_values else "clarify_now",
                fallback_summary="当前还缺清楚的最近变化信号，只能看到零散动作。",
            ),
            _build_event_line_slot(
                key="owner_chain",
                label="责任关系",
                values=owner_values,
                source_types=["task_fact"] if owner_values else [],
                recommended_fix="clarify_now",
                fallback_summary="当前还不够清楚谁在主负责、谁在等待。",
                prefer_full_when_any=True,
            ),
            _build_event_line_slot(
                key="recent_decision",
                label="最近关键决策",
                values=recent_decision_values,
                source_types=["user_note"] if recent_decision_values else [],
                recommended_fix="clarify_now",
                fallback_summary="最近改变这条线走向的关键决策还不够清楚。",
            ),
            _build_event_line_slot(
                key="project_link",
                label="项目/模块/流程归属",
                values=project_link_values or [str(story["name"])],
                source_types=["project_context"] if project_link_values else ["event_line"],
                recommended_fix="upload_docs",
                fallback_summary="当前还没有把这条线稳定挂到项目、模块或流程上。",
            ),
        ]

        score = 0
        for slot in slots:
            score += round(slot_weights[slot.key] * _slot_strength_score(slot.evidenceStrength))
        status = _event_line_completeness_status(score)
        missing_slots = [slot.label for slot in slots if slot.coverage != "full"]
        strongest_slots = [
            slot.label
            for slot in sorted(slots, key=lambda item: (slot_weights[item.key] * _slot_strength_score(item.evidenceStrength)), reverse=True)
            if slot.evidenceStrength in {"strong", "medium"}
        ][:3]
        completeness = EventLineCompletenessRecord(
            eventLineId=str(story.get("eventLineId") or story["id"]),
            title=str(story["name"]),
            score=score,
            status=status,
            missingSlots=missing_slots[:4],
            strongestSlots=strongest_slots,
            slots=slots,
        )
        completeness_records.append(completeness)

        project_name = next(iter(story["clients"]), None) if story["clients"] else None  # type: ignore[arg-type]
        module_name = next(iter(story["moduleNames"]), None) if story["moduleNames"] else None  # type: ignore[arg-type]
        flow_name = next(iter(story["flowNames"]), None) if story["flowNames"] else None  # type: ignore[arg-type]
        current_blocker = _compose_story_blocker(category, blocker_values[0] if blocker_values else "")
        next_move = _compose_story_next_move(category, next_action_values[0] if next_action_values else "")
        what_this_line_is = _compose_story_identity(
            category,
            story_name=str(story["name"]),
            project_name=project_name,
            module_name=module_name,
            flow_name=flow_name,
            line_summary=line_summary_values[0] if line_summary_values else "",
        )
        what_happened = _compose_story_week_progress(
            category,
            focus=_first_non_empty(line_intent_values + list(story["currentFocuses"])),  # type: ignore[arg-type]
            signal=_first_non_empty(recent_change_values),
            task_titles=task_title_values,
        )
        stage_label = stage_values[0] if stage_values else "阶段待澄清"
        current_state = _compose_story_state(
            category,
            stage_label=stage_label,
            completed_count=int(story["completedCount"]),
            unfinished_count=int(story["unfinishedCount"]),
        )
        evidence_preview = _dedupe_texts(
            [
                *line_summary_values,
                *line_intent_values,
                *list(story["currentFocuses"]),  # type: ignore[arg-type]
                *list(story["recentProgresses"]),  # type: ignore[arg-type]
                *list(story["goals"]),  # type: ignore[arg-type]
                *list(story["recentDecisions"]),  # type: ignore[arg-type]
                *list(story["taskTitles"]),  # type: ignore[arg-type]
            ],
            limit=4,
        )
        summary_card = EventLineSummaryCardRecord(
            eventLineId=str(story.get("eventLineId") or story["id"]),
            title=str(story["name"]),
            kind=_story_kind(category, project_name=project_name),
            status="blocked" if blocker_values else "active",
            projectName=project_name,
            moduleName=module_name,
            flowName=flow_name,
            whatThisLineIs=what_this_line_is,
            whatHappenedThisWeek=what_happened,
            currentState=current_state,
            mainBlocker=current_blocker,
            nextCriticalMove=next_move,
            ownerNames=owner_values[:3],
            completenessScore=score,
            predictionReadiness=_prediction_readiness(status),
            missingSlots=missing_slots[:4],
            evidencePreview=evidence_preview,
            target=_event_line_story_target(story),
            evidenceRefs=_story_evidence_refs(story),
        )
        summaries.append(summary_card)

        if status in {"forecast_ready", "high_confidence"} and (blocker_values or int(story["unfinishedCount"]) > 0):
            risk_type = _infer_risk_type(current_blocker)
            risk_cards.append(
                EventLineRiskCardRecord(
                    eventLineId=str(story.get("eventLineId") or story["id"]),
                    title=str(story["name"]),
                    riskType=risk_type,
                    statement=_compose_risk_statement(
                        category,
                        subject=_story_subject_name(story),
                        blocker_text=current_blocker,
                        viewer_role=viewer_role,
                    ),
                    forecastWindow="1w" if blocker_values else "2w",
                    probability="high" if status == "high_confidence" else "medium",
                    impactScope="project" if project_name else "team",
                    triggerSignals=_dedupe_texts([current_blocker, *evidence_preview], limit=3),
                    whyNow=what_happened,
                    ifIgnored=_compose_risk_if_ignored(category, viewer_role=viewer_role),
                    suggestedAction=next_move,
                    ownerRole=owner_values[0] if owner_values else "该线负责人",
                    target=_event_line_story_target(story),
                    evidenceRefs=_story_evidence_refs(story),
                )
            )

        if status in {"forecast_ready", "high_confidence"} and (recent_change_values or int(story["completedCount"]) > 0):
            opportunity_cards.append(
                EventLineOpportunityCardRecord(
                    eventLineId=str(story.get("eventLineId") or story["id"]),
                    title=str(story["name"]),
                    opportunityType=theme["opportunity_type"],  # type: ignore[arg-type]
                    statement=_compose_opportunity_statement(
                        category,
                        subject=_story_subject_name(story),
                        signal=recent_change_values[0] if recent_change_values else what_happened,
                        viewer_role=viewer_role,
                    ),
                    forecastWindow="2w",
                    confidence="high" if status == "high_confidence" else "medium",
                    upside=_compose_opportunity_upside(category, viewer_role=viewer_role),
                    supportingSignals=_dedupe_texts([*recent_change_values, *goal_values, *evidence_preview], limit=3),
                    recommendedAmplifier=_compose_opportunity_amplifier(category, next_move=next_move, viewer_role=viewer_role),
                    ownerRole=owner_values[0] if owner_values else "该线负责人",
                    target=_event_line_story_target(story),
                    evidenceRefs=_story_evidence_refs(story),
                )
            )

    return summaries[:6], completeness_records[:6], risk_cards[:4], opportunity_cards[:4]


def _build_trend_signals(
    items: list[WeeklyReviewTaskEntryRecord],
    event_line_summaries: list[EventLineSummaryCardRecord],
    event_line_completeness: list[EventLineCompletenessRecord],
) -> list[TrendSignalRecord]:
    signals: list[TrendSignalRecord] = []
    review_pending_items = [item for item in items if bool(item.taskSnapshot.orgContext and item.taskSnapshot.orgContext.needsReview)]
    if len(review_pending_items) >= 2:
        signals.append(
            TrendSignalRecord(
                key="repeat_review_pending",
                title="待复核事项持续堆积",
                statement=f"本周有 {len(review_pending_items)} 条任务仍卡在复核/确认链，说明判断和执行之间的回收链还没有真正收紧。",
                signalType="repeat_review_pending",
                severity="high" if len(review_pending_items) >= 4 else "medium",
                windowLabel="本周",
                relatedEventLineId=None,
                relatedTaskIds=[item.taskId for item in review_pending_items[:5]],
                evidenceRefs=[
                    ReviewDashboardEvidenceRefRecord(
                        sourceType="task",
                        sourceId=item.taskId,
                        title=item.taskSnapshot.title,
                        summary="待复核或待确认",
                    )
                    for item in review_pending_items[:4]
                ],
                target=ReviewDashboardCardTargetRecord(
                    targetType="task_view",
                    targetId="builtin:risk",
                    targetLabel="风险视图",
                    targetFilters={"onlyRisky": True, "needsReview": True},
                ),
            )
        )

    support_need_items = [
        item
        for item in items
        if item.structuredNote.supportNeeded.strip()
        or item.structuredNote.lightweightTag.strip() in {"需要支持", "资源不够", "等待他人"}
    ]
    if len(support_need_items) >= 2:
        signals.append(
            TrendSignalRecord(
                key="repeat_support_request",
                title="支持依赖开始持续化",
                statement=f"本周至少 {len(support_need_items)} 条任务明确提到支持或外部依赖，这已经不是单点阻塞，而是协作链需要干预的信号。",
                signalType="repeat_support_request",
                severity="medium",
                windowLabel="本周",
                relatedEventLineId=None,
                relatedTaskIds=[item.taskId for item in support_need_items[:5]],
                evidenceRefs=[
                    ReviewDashboardEvidenceRefRecord(
                        sourceType="task",
                        sourceId=item.taskId,
                        title=item.taskSnapshot.title,
                        summary=_truncate_overview_text(item.structuredNote.supportNeeded or item.structuredNote.lightweightTag or item.note),
                    )
                    for item in support_need_items[:4]
                ],
                target=ReviewDashboardCardTargetRecord(
                    targetType="task_view",
                    targetId="builtin:risk",
                    targetLabel="风险视图",
                    targetFilters={"onlyRisky": True, "sourceTypes": ["support_request"]},
                ),
            )
        )

    completeness_by_id = {item.eventLineId: item for item in event_line_completeness}
    for summary in event_line_summaries:
        completeness = completeness_by_id.get(summary.eventLineId)
        if not completeness:
            continue
        if summary.status == "blocked" or completeness.status == "insufficient":
            signals.append(
                TrendSignalRecord(
                    key=f"stalled_event_line::{summary.eventLineId}",
                    title=f"{summary.title} 长时间无收束",
                    statement=f"{summary.title} 当前仍卡在“{summary.mainBlocker or '信息待补'}”，如果接下来 1-2 周不继续补证据，这条线的判断质量和推进速度都会继续下降。",
                    signalType="stalled_event_line",
                    severity="high" if summary.status == "blocked" else "medium",
                    windowLabel="未来 1-2 周",
                    relatedEventLineId=summary.eventLineId,
                    relatedTaskIds=[ref.sourceId for ref in summary.evidenceRefs or [] if ref.sourceType == "task"],
                    evidenceRefs=list(summary.evidenceRefs or []),
                    target=summary.target,
                )
            )
        if summary.predictionReadiness in {"summary_only", "not_ready"} and completeness.missingSlots:
            signals.append(
                TrendSignalRecord(
                    key=f"thin_evidence::{summary.eventLineId}",
                    title=f"{summary.title} 证据仍偏薄",
                    statement=f"{summary.title} 目前还缺 { '、'.join(completeness.missingSlots[:2]) }，如果继续直接产出判断，结论会反复回到泛化层。",
                    signalType="thin_evidence",
                    severity="medium",
                    windowLabel="本周",
                    relatedEventLineId=summary.eventLineId,
                    relatedTaskIds=[ref.sourceId for ref in summary.evidenceRefs or [] if ref.sourceType == "task"],
                    evidenceRefs=list(summary.evidenceRefs or []),
                    target=summary.target,
                )
            )
    return signals[:6]


def _reference_alignment_counts(
    items: list[WeeklyReviewTaskEntryRecord],
    reference_texts: list[str],
) -> tuple[int, int] | None:
    token_sets = [set(_extract_tokens(text.lower())) for text in reference_texts if _clean_text(text)]
    token_sets = [token_set for token_set in token_sets if token_set]
    if not token_sets:
        return None
    aligned = 0
    partial = 0
    for item in items:
        item_tokens = set(_extract_tokens(_item_text(item)))
        if not item_tokens:
            continue
        overlap = max((len(item_tokens & token_set) for token_set in token_sets), default=0)
        if overlap >= 2:
            aligned += 1
        elif overlap == 1:
            partial += 1
    return aligned, partial


def _completion_status(item: WeeklyReviewTaskEntryRecord) -> Literal["done_on_time", "done_late", "in_progress", "not_done"]:
    status = item.structuredNote.completionStatus
    if status in {"done_on_time", "done_late", "in_progress", "not_done"}:
        return status
    if item.taskSnapshot.status == "done":
        return "done_on_time"
    if item.taskSnapshot.status == "doing":
        return "in_progress"
    return "not_done"


def _alignment_status(value: str | None) -> Literal["aligned", "partial", "misaligned", "unknown"]:
    if value in {"aligned", "partial", "misaligned", "unknown"}:
        return value
    return "unknown"


def _format_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "待补录"
    rate = numerator / denominator * 100
    rounded = round(rate, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return f"{int(round(rounded))}%"
    return f"{rounded:.1f}%"


def _metric_tone(rate: float, *, good: float, okay: float) -> Literal["positive", "neutral", "warning", "risk"]:
    if rate >= good:
        return "positive"
    if rate >= okay:
        return "neutral"
    if rate > 0:
        return "warning"
    return "risk"


def _build_metric_card(
    *,
    key: Literal["timely_completion", "department_alignment", "strategy_alignment", "reflection_capture"],
    label: str,
    numerator: int,
    denominator: int,
    description: str,
    tone: Literal["positive", "neutral", "warning", "risk"],
) -> ReviewMetricCardRecord:
    rate = numerator / denominator if denominator > 0 else 0.0
    return ReviewMetricCardRecord(
        key=key,
        label=label,
        valueText=_format_rate(numerator, denominator),
        numerator=numerator,
        denominator=denominator,
        rate=round(rate, 4),
        description=description,
        tone=tone,
    )


def _build_metric_cards(
    scope: Literal["work", "personal"],
    items: list[WeeklyReviewTaskEntryRecord],
    dna_modules: list[OrganizationDnaModuleRecord],
    *,
    week_label: str,
    org_model_profile: OrgModelProfileRecord | None = None,
    viewer_role: ReviewViewerRole = "employee",
) -> list[ReviewMetricCardRecord]:
    total_count = len(items)
    completion_statuses = Counter(_completion_status(item) for item in items)
    completed_items = [item for item in items if _completion_status(item) in {"done_on_time", "done_late"}]
    unfinished_items = [item for item in items if _completion_status(item) in {"in_progress", "not_done"}]
    completed_with_experience = sum(
        1 for item in completed_items if _reflection_text(item)
    )
    unfinished_with_insight = sum(
        1 for item in unfinished_items if _reflection_text(item) or _lightweight_tag(item)
    )
    cards = [
        _build_metric_card(
            key="timely_completion",
            label="计划及时完成率",
            numerator=int(completion_statuses["done_on_time"]),
            denominator=total_count,
            description=(
                f"本周共 {total_count} 项计划，其中按时完成 {completion_statuses['done_on_time']} 项、延迟完成 {completion_statuses['done_late']} 项、"
                f"仍在推进 {completion_statuses['in_progress']} 项、未完成 {completion_statuses['not_done']} 项。"
                if total_count
                else "当前还没有可分析的计划样本。"
            ),
            tone=_metric_tone(
                (int(completion_statuses["done_on_time"]) / total_count) if total_count else 0.0,
                good=0.65,
                okay=0.4,
            ),
        ),
    ]

    if scope == "work" and viewer_role == "admin":
        story_groups = _event_line_story_groups(items)
        grouped_task_count = sum(len(group["taskIds"]) for group in story_groups)  # type: ignore[arg-type]
        cards.append(
            _build_metric_card(
                key="department_alignment",
                label="事件线成线率",
                numerator=grouped_task_count,
                denominator=total_count,
                description=(
                    f"本周共有 {grouped_task_count}/{total_count} 条任务已经能放回具体事件线或项目线里判断。"
                    if story_groups
                    else "当前还没有把事项稳定串到事件线或项目线里，机构视角看到的仍是零散动作。"
                ),
                tone=_metric_tone((grouped_task_count / total_count) if total_count else 0.0, good=0.7, okay=0.45),
            )
        )
        quarter_goal_lines = [
            *_extract_quarter_goal_lines(dna_modules),
            *_focus_item_reference_texts(org_model_profile),
        ]
        strategy_alignment = _reference_alignment_counts(items, quarter_goal_lines)
        if strategy_alignment is None:
            cards.append(
                _build_metric_card(
                    key="strategy_alignment",
                    label="任务-机构战略对齐率",
                    numerator=0,
                    denominator=0,
                    description="当前还没有足够稳定的机构重点参照，暂时无法判断这些动作是否真的在推进机构主线。",
                    tone="warning",
                )
            )
        else:
            aligned_count, partial_count = strategy_alignment
            cards.append(
                _build_metric_card(
                    key="strategy_alignment",
                    label="任务-机构战略对齐率",
                    numerator=aligned_count + partial_count,
                    denominator=total_count,
                    description=(
                        f"根据任务文本与机构季度重点的对应关系判断，当前明确支撑 {aligned_count} 项，部分支撑 {partial_count} 项。"
                        if total_count
                        else "当前还没有可分析的任务样本。"
                    ),
                    tone=_metric_tone(
                        ((aligned_count + partial_count) / total_count) if total_count else 0.0,
                        good=0.65,
                        okay=0.35,
                    ),
                )
            )
    elif scope == "work":
        team_plan_texts = [
            *_dedupe_texts([_module_preview(module) for module in _team_plan_modules(dna_modules)], limit=4),
            *_department_plan_reference_texts(org_model_profile, week_label=week_label, items=items),
        ]
        department_alignment = _reference_alignment_counts(items, team_plan_texts)
        department_alignment_label = "部门任务-部门计划对齐率" if viewer_role == "department_lead" else "个人-部门对齐率"
        department_alignment_empty_desc = (
            "当前还没有补齐部门周计划 / 月度 DNA 背景，暂时无法判断部门任务与部门重点是否一致。"
            if viewer_role == "department_lead"
            else "当前还没有补齐部门周计划 / 月度 DNA 背景，暂时无法判断个人任务与部门重点是否一致。"
        )
        if department_alignment is None:
            cards.append(
                _build_metric_card(
                    key="department_alignment",
                    label=department_alignment_label,
                    numerator=0,
                    denominator=0,
                    description=department_alignment_empty_desc,
                    tone="warning",
                )
            )
        else:
            aligned_count, partial_count = department_alignment
            department_alignment_desc = (
                f"根据任务文本与部门计划背景的对应关系判断，当前明确对齐 {aligned_count} 项，部分对齐 {partial_count} 项。"
                if total_count
                else "当前还没有可分析的任务样本。"
            )
            cards.append(
                _build_metric_card(
                    key="department_alignment",
                    label=department_alignment_label,
                    numerator=aligned_count + partial_count,
                    denominator=total_count,
                    description=department_alignment_desc,
                    tone=_metric_tone(
                        ((aligned_count + partial_count) / total_count) if total_count else 0.0,
                        good=0.7,
                        okay=0.45,
                    ),
                )
            )

        quarter_goal_lines = [
            *_extract_quarter_goal_lines(dna_modules),
            *_focus_item_reference_texts(org_model_profile),
        ]
        strategy_alignment = _reference_alignment_counts(items, quarter_goal_lines)
        if strategy_alignment is None:
            cards.append(
                _build_metric_card(
                    key="strategy_alignment",
                    label="部门任务-机构方向对齐率" if viewer_role == "department_lead" else "部门-机构对齐率",
                    numerator=0,
                    denominator=0,
                    description=(
                        "当前还没有从组织介绍或正式机构重点里识别到足够稳定的战略参照，暂时无法判断部门动作与机构主线的关系。"
                        if viewer_role == "department_lead"
                        else "当前还没有从组织介绍或正式机构重点里识别到足够稳定的战略参照，暂时无法判断本周动作与机构主线的关系。"
                    ),
                    tone="warning",
                )
            )
        else:
            aligned_count, partial_count = strategy_alignment
            cards.append(
                _build_metric_card(
                    key="strategy_alignment",
                    label="部门任务-机构方向对齐率" if viewer_role == "department_lead" else "部门-机构对齐率",
                    numerator=aligned_count + partial_count,
                    denominator=total_count,
                    description=(
                        f"根据任务文本与机构季度重点的对应关系判断，当前明确支撑 {aligned_count} 项，部分支撑 {partial_count} 项。"
                        if total_count
                        else "当前还没有可分析的任务样本。"
                    ),
                    tone=_metric_tone(
                        ((aligned_count + partial_count) / total_count) if total_count else 0.0,
                        good=0.65,
                        okay=0.35,
                    ),
                )
            )

    cards.append(
        _build_metric_card(
            key="reflection_capture",
            label="复盘沉淀率",
            numerator=completed_with_experience + unfinished_with_insight,
            denominator=total_count,
            description=(
                f"已完成事项中有 {completed_with_experience}/{len(completed_items)} 项留下了心得；未完成事项中有 {unfinished_with_insight}/{len(unfinished_items)} 项写出了思考或支持需求。"
                if total_count
                else "当前还没有可分析的复盘沉淀样本。"
            ),
            tone=_metric_tone(
                ((completed_with_experience + unfinished_with_insight) / total_count) if total_count else 0.0,
                good=0.75,
                okay=0.45,
            ),
        ),
    )
    return cards


def _select_relevant_modules(
    items: list[WeeklyReviewTaskEntryRecord],
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    limit: int = 3,
) -> list[OrganizationDnaModuleRecord]:
    usable = [module for module in organization_dna_modules if module.hasDocument and _module_preview(module)]
    if not usable:
        return []
    haystack = " ".join(_item_text(item) for item in items)
    tokens = set(_extract_tokens(haystack))
    scored: list[tuple[int, int, OrganizationDnaModuleRecord]] = []
    for module in usable:
        text = f"{module.title} {_module_preview(module)}".lower()
        overlap = sum(1 for token in tokens if token in text)
        structural_bonus = 0
        if module.moduleKey == "business_intro" and _contains_any(haystack, BUSINESS_KEYWORDS):
            structural_bonus += 2
        if module.moduleKey == "team_intro" and _contains_any(haystack, TEAM_KEYWORDS):
            structural_bonus += 2
        if module.moduleKey == "market_intro" and _contains_any(haystack, MARKET_KEYWORDS):
            structural_bonus += 2
        if module.moduleKey == "organization_intro":
            structural_bonus += 1
        scored.append((overlap + structural_bonus, 1 if module.summary.strip() else 0, module))
    scored.sort(key=lambda item: (item[0], item[1], item[2].updatedAt or ""), reverse=True)
    picked = [module for score, _, module in scored if score > 0][:limit]
    if picked:
        return picked
    return usable[:limit]


def _confidence(level_score: int) -> Literal["high", "medium", "low"]:
    if level_score >= 5:
        return "high"
    if level_score >= 3:
        return "medium"
    return "low"


def _build_evidence_weights(
    scope: Literal["work", "personal"],
    note_count: int,
    total_count: int,
    dna_modules: list[OrganizationDnaModuleRecord],
    *,
    project_context_count: int = 0,
    focus_plan_ready: bool = False,
) -> list[ReviewEvidenceWeightRecord]:
    team_plan_ready = bool(_team_plan_modules(dna_modules))
    weights = [
        ReviewEvidenceWeightRecord(
            sourceType="user_note",
            label="用户手写复盘说明",
            weight="high" if note_count else "medium",
            rationale="一线复盘说明直接来自当事人，本轮分析默认把这类信息作为最高权重依据。",
        ),
        ReviewEvidenceWeightRecord(
            sourceType="task_fact",
            label="任务客观事实",
            weight="medium",
            rationale=f"任务状态、周标签、清单归属等事实用于约束分析，当前共参考 {total_count} 项任务。",
        ),
    ]
    if scope == "work":
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="team_plan",
                label="部门周计划 / 月度 DNA",
                weight="medium" if team_plan_ready else "low",
                rationale="部门负责人填写的本周重点计划和月度 DNA 用来判断任务是否贴着部门主线推进。",
            )
        )
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="organization_dna",
                label="组织 / 业务 DNA",
                weight="medium" if dna_modules else "low",
                rationale="组织介绍和业务 DNA 用来提供方向参照，系统会自动尝试抽取季度重点，而不再要求员工手工挂接。",
            )
        )
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="focus_plan",
                label="机构重点 / 部门计划对象",
                weight="medium" if focus_plan_ready else "low",
                rationale="正式录入的机构季度重点、部门周计划和计划项，会优先作为 AI 判断当前动作与管理计划关系的结构化背景。",
            )
        )
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="project_context",
                label="项目 / 客户背景",
                weight="medium" if project_context_count else "low",
                rationale=f"任务挂接的项目背景、目标、风险和近期会议线索，用来判断当前动作是否贴着项目阶段与真实业务节奏推进；当前命中 {project_context_count} 项。",
            )
        )
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="external_context",
                label="外部补充资料",
                weight="low",
                rationale="本轮周复盘未直接接入互联网补充信息；即便后续接入，也只应作为弱证据使用。",
            )
        )
    else:
        weights.append(
            ReviewEvidenceWeightRecord(
                sourceType="organization_dna",
                label="组织 DNA 参考",
                weight="low",
                rationale="成长复盘以自我总结为主，组织 DNA 只适合作为弱参考，不应盖过个人真实感受。",
            )
        )
    return weights


def _detect_dominant_lens(items: list[WeeklyReviewTaskEntryRecord], default_lens: str) -> str:
    haystack = " ".join(_item_text(item) for item in items)
    lens_scores = Counter[str]()
    if _contains_any(haystack, BUSINESS_KEYWORDS):
        lens_scores["business"] += 2
    if _contains_any(haystack, TEAM_KEYWORDS):
        lens_scores["team"] += 2
    if _contains_any(haystack, MARKET_KEYWORDS):
        lens_scores["market"] += 2
    if _contains_any(haystack, ISSUE_KEYWORDS):
        lens_scores["organization"] += 1
    if not lens_scores:
        return default_lens
    return lens_scores.most_common(1)[0][0]


def _hypothesis_reason(
    note_count: int,
    task_count: int,
    dna_titles: list[str],
) -> str:
    dna_text = f"；补充参考 DNA：{'、'.join(dna_titles)}" if dna_titles else ""
    return f"高权重依据来自 {note_count} 条一线复盘说明；中权重依据来自 {task_count} 条任务事实{dna_text}。"


def _build_work_hypotheses(
    items: list[WeeklyReviewTaskEntryRecord],
    dna_modules: list[OrganizationDnaModuleRecord],
    *,
    week_label: str,
    org_model_profile: OrgModelProfileRecord | None = None,
) -> list[ReviewHypothesisRecord]:
    note_items = [item for item in items if _reflection_text(item) or _lightweight_tag(item)]
    progress_items = [
        item
        for item in items
        if _completion_status(item) in {"done_on_time", "done_late"}
        or _reflection_text(item)
        or _contains_any(item.note, SUCCESS_KEYWORDS)
    ]
    blocker_items = [
        item
        for item in items
        if _completion_status(item) in {"in_progress", "not_done"}
        and (
            not item.note.strip()
            or _lightweight_tag(item)
            or _reflection_text(item)
            or _contains_any(item.note, ISSUE_KEYWORDS)
        )
    ]
    dna_titles = [module.title for module in dna_modules]
    quarter_goal_lines = _extract_quarter_goal_lines(dna_modules)
    project_summary = _project_context_summary(items)
    event_line_summary = _event_line_summary(items)
    structured_plan_texts = _department_plan_reference_texts(org_model_profile, week_label=week_label, items=items)
    focus_item_texts = _focus_item_reference_texts(org_model_profile)
    hypotheses: list[ReviewHypothesisRecord] = []

    if progress_items:
        success_lens = _detect_dominant_lens(progress_items, MODULE_LENS.get(dna_modules[0].moduleKey, "business") if dna_modules else "business")
        success_examples = "、".join(_item_short_label(item) for item in progress_items[:3])
        success_statement_map = {
            "business": "初步看，本周推进较顺的事项更可能受益于目标对象和业务路径相对清晰，因此执行动作能较快转成具体产出。",
            "team": "初步看，本周推进较顺的事项更可能受益于责任分工较清楚、协作链条较短，因此过程阻力相对较小。",
            "market": "初步看，本周推进较顺的事项更可能踩中了较明确的外部窗口或需求时点，因此反馈比预期更顺。",
            "organization": "初步看，本周推进较顺的事项更可能与当前组织主线较一致，所以资源注意力更容易集中到这些事项上。",
        }
        success_confidence = _confidence(len(progress_items) + (2 if len(note_items) >= 2 else 0) + (1 if dna_titles else 0))
        hypotheses.append(
            ReviewHypothesisRecord(
                id="success_pattern",
                lens=success_lens,  # type: ignore[arg-type]
                title="可能的成功原因",
                statement=f"{success_statement_map.get(success_lens, success_statement_map['organization'])} 当前比较能说明这一点的任务包括：{success_examples}。",
                confidence=success_confidence,
                reason=_hypothesis_reason(
                    len([item for item in progress_items if item.note.strip() or _reflection_text(item)]),
                    len(progress_items),
                    dna_titles,
                ),
                relatedTaskIds=[item.taskId for item in progress_items[:4]],
                evidenceSources=["user_note", "task_fact", *(("organization_dna",) if dna_titles else ())],
                assumptionNote="这是基于任务说明与 DNA 的推断，不等同于严格因果结论。",
            )
        )

    if blocker_items:
        blocker_lens = _detect_dominant_lens(blocker_items, MODULE_LENS.get(dna_modules[0].moduleKey, "organization") if dna_modules else "organization")
        blocker_examples = "、".join(_item_short_label(item) for item in blocker_items[:3])
        blocker_statement_map = {
            "business": "初步看，本周卡点不只是执行慢，更像是前置业务判断还不够清楚，例如目标对象、方案路径或交付标准没有完全钉死。",
            "team": "初步看，本周卡点不只是单点执行问题，更像出在协作接口、责任边界或排期节奏上。",
            "market": "初步看，本周卡点里有一部分可能来自外部变化或需求反馈不足，导致内部动作难以顺畅推进。",
            "organization": "初步看，本周卡点更像是优先级、目标边界或资源注意力没有完全聚焦，因此任务推进容易反复或悬空。",
        }
        blocker_confidence = _confidence(len(blocker_items) + (2 if len([item for item in blocker_items if item.note.strip()]) >= 2 else 0) + (1 if dna_titles else 0))
        hypotheses.append(
            ReviewHypothesisRecord(
                id="blocker_pattern",
                lens=blocker_lens,  # type: ignore[arg-type]
                title="可能的阻碍原因",
                statement=f"{blocker_statement_map.get(blocker_lens, blocker_statement_map['organization'])} 当前暴露这一点较明显的任务包括：{blocker_examples}。",
                confidence=blocker_confidence,
                reason=_hypothesis_reason(
                    len([item for item in blocker_items if item.note.strip() or _reflection_text(item) or _lightweight_tag(item)]),
                    len(blocker_items),
                    dna_titles,
                ),
                relatedTaskIds=[item.taskId for item in blocker_items[:4]],
                evidenceSources=["user_note", "task_fact", *(("organization_dna",) if dna_titles else ())],
                assumptionNote="这是带权重的解释性判断，后续仍需要人工确认是否真的是机制问题而非偶发事件。",
            )
        )

    overloaded_items = [item for item in items if _lightweight_tag(item) == "工作过度饱和"]
    if overloaded_items:
        overload_examples = "、".join(_item_short_label(item) for item in overloaded_items[:3])
        hypotheses.append(
            ReviewHypothesisRecord(
                id="capacity_saturation",
                lens="team",
                title="可能存在容量过载",
                statement=f"当前有 {len(overloaded_items)} 项任务被直接标记为“工作过度饱和”，说明这周的问题不一定是判断失误，也可能是负责人容量已经顶满。较明显的任务包括：{overload_examples}。",
                confidence=_confidence(len(overloaded_items) + (1 if len(note_items) >= 2 else 0)),
                reason=f"这类判断优先依据一线轻量卡点标签，而不是系统推断；当前共命中 {len(overloaded_items)} 条。",
                relatedTaskIds=[item.taskId for item in overloaded_items[:4]],
                evidenceSources=["user_note", "task_fact"],
                assumptionNote="容量过载不等于人员能力不足，更像是任务取舍和节奏配置问题。",
            )
        )

    if int(event_line_summary["groupCount"]) > 0:
        event_line_names = "、".join(event_line_summary["names"][:3]) or "当前重点事件线"
        blocked_text = (
            f" 当前仍待继续推进的事件线包括：{'、'.join(event_line_summary['blockedNames'][:2])}。"
            if event_line_summary["blockedNames"]
            else ""
        )
        hypotheses.append(
            ReviewHypothesisRecord(
                id="event_line_continuity",
                lens="team",
                title="与事件线连续推进的关系判断",
                statement=(
                    f"从当前任务关系看，本周已有 {event_line_summary['groupCount']} 条事件线把离散任务串成持续推进的工作线，"
                    f"其中 {event_line_summary['multiTaskGroupCount']} 条事件线已经跨了多项任务。像 {event_line_names} 这类事项，更适合按同一条线统一判断，而不是拆成多条任务分别复盘。{blocked_text}"
                ).strip(),
                confidence=_confidence(int(event_line_summary["groupCount"]) + int(event_line_summary["multiTaskGroupCount"]) + (1 if note_items else 0)),
                reason=f"这条判断直接读取任务快照中的 eventLineId / eventLineName；当前命中 {event_line_summary['taskCount']} 条任务、{event_line_summary['groupCount']} 条事件线。",
                relatedTaskIds=[item.taskId for item in items if _item_event_line_id(item)][:6],
                evidenceSources=["task_fact", *(("user_note",) if note_items else ())],
                assumptionNote="事件线还处在早期搭建阶段；如果任务没有挂入事件线，系统会继续回落到单条任务判断。",
            )
        )

    if int(project_summary["count"]) > 0:
        project_clients = "、".join(project_summary["clients"][:3]) or "当前重点项目"
        project_stages = "、".join(project_summary["stages"][:2])
        project_goals = "；".join(project_summary["goals"][:2])
        project_risks = "；".join(project_summary["risks"][:2])
        stage_text = f" 当前涉及的项目阶段包括：{project_stages}。" if project_stages else ""
        goal_text = f" 这些任务更像在推进：{project_goals}。" if project_goals else ""
        risk_text = f" 但也要继续警惕：{project_risks}。" if project_risks else ""
        hypotheses.append(
            ReviewHypothesisRecord(
                id="project_context_check",
                lens="business",
                title="与项目阶段的关系判断",
                statement=(
                    f"从当前已挂接的项目背景看，本周动作主要围绕 {project_clients} 展开，"
                    f"系统已经能把任务放回项目语境里理解，而不再只看单条执行动作。{stage_text}{goal_text}{risk_text}"
                ).strip(),
                confidence=_confidence(int(project_summary["count"]) + (1 if project_summary["infoCompleteness"] == "high" else 0) + (1 if note_items else 0)),
                reason=f"当前共有 {project_summary['count']} 条任务已挂接项目背景；项目背景来自客户工作台、项目目标、流程和近期会议线索。",
                relatedTaskIds=[item.taskId for item in items if _item_project_context(item)][:4],
                evidenceSources=["task_fact", "project_context", *(("user_note",) if note_items else ())],
                assumptionNote="项目背景来自系统中已有的项目资料和任务挂接，仍需随着客户工作台和会议纪要持续补全。",
            )
        )

    if structured_plan_texts or focus_item_texts:
        linked_focus_count = len({_item_focus_item_id(item) for item in items if _item_focus_item_id(item)})
        linked_plan_item_count = len({_item_department_plan_item_id(item) for item in items if _item_department_plan_item_id(item)})
        structured_text = (
            f"当前已有 {linked_plan_item_count} 条任务直接挂到了部门计划项，{linked_focus_count} 条任务直接挂到了机构重点。"
            if linked_plan_item_count or linked_focus_count
            else "当前虽未把任务逐条挂到计划项，但系统已经能读取正式录入的部门计划和机构重点。"
        )
        focus_preview = "；".join(_dedupe_texts([*focus_item_texts[:2], *structured_plan_texts[:2]], limit=3))
        hypotheses.append(
            ReviewHypothesisRecord(
                id="structured_plan_alignment",
                lens="organization",
                title="与正式计划对象的关系判断",
                statement=(
                    f"{structured_text} 本周判断优先参考正式录入的机构重点与部门计划对象，而不只靠自由文本推断。"
                    f"{f' 当前高频计划线索包括：{focus_preview}。' if focus_preview else ''}"
                ).strip(),
                confidence=_confidence((2 if linked_focus_count or linked_plan_item_count else 1) + (1 if structured_plan_texts else 0) + (1 if focus_item_texts else 0)),
                reason="这条判断直接读取组织模型中的 focusItems、departmentPlans 和任务挂接关系，结构化程度高于普通说明文字。",
                relatedTaskIds=[item.taskId for item in items[:4]],
                evidenceSources=["task_fact", "focus_plan", *(("user_note",) if note_items else ())],
                assumptionNote="正式计划对象仍需要持续维护；如果计划项没有更新，系统判断也会偏保守。",
            )
        )

    if dna_modules:
        titles_text = "、".join(module.title for module in dna_modules)
        quarter_text = (
            f" 当前从组织介绍中识别到的季度重点包括：{'；'.join(quarter_goal_lines[:3])}。"
            if quarter_goal_lines
            else ""
        )
        if len(progress_items) >= len(blocker_items):
            alignment_statement = f"从当前任务与 DNA 的对应关系看，本周主要工作大体仍贴着组织主线在走，但尚缺明确的战略挂接标注。当前主要参考的 DNA 模块是：{titles_text}。{quarter_text}"
        else:
            alignment_statement = f"从当前任务与 DNA 的对应关系看，本周已有偏航风险，部分任务虽然在推进，但与组织主线的关系还没有被说清。当前主要参考的 DNA 模块是：{titles_text}。{quarter_text}"
        hypotheses.append(
            ReviewHypothesisRecord(
                id="alignment_check",
                lens="organization",
                title="与组织方向的关系判断",
                statement=alignment_statement,
                confidence=_confidence(2 + (1 if dna_modules else 0) + (1 if note_items else 0)),
                reason=_hypothesis_reason(len(note_items), len(items), [module.title for module in dna_modules]),
                relatedTaskIds=[item.taskId for item in items[:4]],
                evidenceSources=["task_fact", "organization_dna", *(("user_note",) if note_items else ())],
                assumptionNote="这条判断主要用于提醒是否出现方向偏差，不代表系统已经掌握全部业务背景。",
            )
        )

    return hypotheses


def _build_admin_work_hypotheses(
    items: list[WeeklyReviewTaskEntryRecord],
    dna_modules: list[OrganizationDnaModuleRecord],
    *,
    week_label: str,
    org_model_profile: OrgModelProfileRecord | None = None,
    viewer_role: Literal["department_lead", "admin"] = "admin",
) -> list[ReviewHypothesisRecord]:
    story_groups = _event_line_story_groups(items)
    if not story_groups:
        return _build_work_hypotheses(
            items,
            dna_modules,
            week_label=week_label,
            org_model_profile=org_model_profile,
        )

    hypotheses: list[ReviewHypothesisRecord] = []
    for story in story_groups[:3]:
        name = str(story["name"])
        category = str(story["category"])
        lens = BUSINESS_CATEGORY_LENS.get(category, "business")
        task_titles = "、".join(story["taskTitles"][:3])  # type: ignore[index]
        clients = "、".join(story["clients"][:2])  # type: ignore[index]
        stages = "、".join(story["stages"][:2])  # type: ignore[index]
        current_focuses = "；".join(story["currentFocuses"][:2])  # type: ignore[index]
        current_blockers = "；".join(story["currentBlockers"][:2])  # type: ignore[index]
        goals = "；".join(story["goals"][:2])  # type: ignore[index]
        risks = "；".join(story["risks"][:2])  # type: ignore[index]
        next_steps = "；".join(story["nextSteps"][:2])  # type: ignore[index]
        recent_progresses = "；".join(story["recentProgresses"][:2])  # type: ignore[index]
        line_summaries = "；".join(story.get("lineSummaries", [])[:2])  # type: ignore[index]
        line_intents = "；".join(story.get("lineIntents", [])[:2])  # type: ignore[index]
        completed_count = int(story["completedCount"])
        unfinished_count = int(story["unfinishedCount"])
        subject = f"{clients}这条线" if clients and name in clients else f"{name}这条线"
        parts = [f"{subject}当前更接近「{category}」。"]
        if line_summaries:
            parts.append(f"这条线本身要推进的是：{line_summaries}。")
        if line_intents:
            parts.append(f"当前正在收束的核心事项是：{line_intents}。")
        if current_focuses:
            parts.append(f"当前最具体的推进事项是：{current_focuses}。")
        if task_titles:
            parts.append(f"本周主要推进了：{task_titles}。")
        if completed_count and unfinished_count:
            parts.append(f"这条线本周已有 {completed_count} 项动作形成推进，但还有 {unfinished_count} 项没有收束。")
        elif completed_count:
            parts.append(f"这条线本周已有 {completed_count} 项动作形成推进。")
        elif unfinished_count:
            parts.append(f"这条线本周仍有 {unfinished_count} 项关键动作待收束。")
        if recent_progresses:
            parts.append(f"最近已经出现的推进迹象是：{recent_progresses}。")
        if stages:
            parts.append(f"当前更像处在「{stages}」阶段。")
        if goals:
            parts.append(f"就现有背景看，这条线现在真正要推进的是：{goals}。")
        if current_blockers:
            parts.append(f"当前最需要直面的阻力是：{current_blockers}。")
        elif risks:
            parts.append(f"当前最需要直面的阻力是：{risks}。")
        if next_steps:
            parts.append(f"接下来应优先推进：{next_steps}。")
        hypotheses.append(
            ReviewHypothesisRecord(
                id=f"event_line_story_{story['id']}",
                lens=lens,
                title=f"{name}｜{'部门推进判断' if viewer_role == 'department_lead' else '本周推进判断'}",
                statement=" ".join(parts).strip(),
                confidence=_confidence(len(story["taskIds"]) + completed_count + (1 if risks or next_steps else 0)),  # type: ignore[arg-type]
                reason=(
                    f"直接依据这条线下 {len(story['taskIds'])} 条任务、事件线维护摘要与项目阶段/阻塞生成，"
                    f"不再把 {name} 与其他业务线混写成泛化判断。"
                ),
                relatedTaskIds=list(story["taskIds"]),  # type: ignore[arg-type]
                evidenceSources=["task_fact", "project_context", "event_line"],
                assumptionNote=(
                    "这是按事件线和部门推进语境直接收束出的业务判断，优先帮助部门负责人做取舍。"
                    if viewer_role == "department_lead"
                    else "这是按事件线和项目语境直接收束出的业务判断，不再使用个人-部门对齐口径。"
                ),
            )
        )

    quarter_goal_lines = [
        *_extract_quarter_goal_lines(dna_modules),
        *_focus_item_reference_texts(org_model_profile),
    ]
    strategy_alignment = _reference_alignment_counts(items, quarter_goal_lines)
    if strategy_alignment is not None:
        aligned_count, partial_count = strategy_alignment
        hypotheses.append(
            ReviewHypothesisRecord(
                id="admin_strategy_alignment",
                lens="organization",
                title="部门计划与机构方向提示" if viewer_role == "department_lead" else "机构战略对齐提示",
                statement=(
                    (
                        f"站在部门负责人视角，本周共有 {aligned_count + partial_count}/{len(items)} 项任务与机构重点形成了明确或部分支撑。"
                        "接下来更需要继续判断的是：这些动作是否真的贴着部门本周重点在推进。"
                    )
                    if viewer_role == "department_lead"
                    else (
                        f"站在机构视角，本周共有 {aligned_count + partial_count}/{len(items)} 项任务与机构重点形成了明确或部分支撑。"
                        "接下来需要继续判断的是：这些动作是否真的在推关键项目，而不是只停留在局部执行层。"
                    )
                ),
                confidence=_confidence(aligned_count + partial_count + (1 if quarter_goal_lines else 0)),
                reason=(
                    "这条判断直接读取机构季度重点与正式 focusItems，并结合部门视角判断是否需要继续收束本周重点。"
                    if viewer_role == "department_lead"
                    else "这条判断直接读取机构季度重点与正式 focusItems，不再使用部门对齐度来替代 CEO 视角。"
                ),
                relatedTaskIds=[item.taskId for item in items[:4]],
                evidenceSources=["task_fact", "focus_plan"],
                assumptionNote=(
                    "部门负责人视角会优先看部门本周重点和机构方向是否一致，不再退回到员工口径。"
                    if viewer_role == "department_lead"
                    else "CEO 视角只看与机构战略和关键项目的关系，不再输出个人-部门对齐度。"
                ),
            )
        )
    return hypotheses[:4]


def _build_personal_hypotheses(items: list[WeeklyReviewTaskEntryRecord]) -> list[ReviewHypothesisRecord]:
    note_items = [item for item in items if _reflection_text(item) or _lightweight_tag(item)]
    if not items:
        return []
    completed_items = [item for item in items if _completion_status(item) in {"done_on_time", "done_late"}]
    blocker_items = [
        item
        for item in items
        if _completion_status(item) in {"in_progress", "not_done"}
        and (not item.note.strip() or _reflection_text(item) or _lightweight_tag(item) or _contains_any(item.note, ISSUE_KEYWORDS))
    ]
    hypotheses: list[ReviewHypothesisRecord] = [
        ReviewHypothesisRecord(
            id="growth_rhythm",
            lens="growth",
            title="当前更像是哪种成长状态",
            statement=(
                "从这周的私人事项看，当前更像是在做经验沉淀和节奏校准，而不是单纯追求完成数量。"
                if note_items
                else "从当前记录量看，这周更像是先顾着推进事务，还没有把自己的观察和感受写下来。"
            ),
            confidence=_confidence(len(note_items) + len(completed_items)),
            reason=f"当前共有 {len(items)} 项私人事项，其中 {len(note_items)} 项写了复盘说明，{len(completed_items)} 项已完成。",
            relatedTaskIds=[item.taskId for item in items[:4]],
            evidenceSources=["user_note", "task_fact"],
            assumptionNote="成长复盘里的判断更偏向自我观察，不应替代本人真实感受。",
        )
    ]
    if blocker_items:
        blocker_titles = "、".join(_item_short_label(item) for item in blocker_items[:3])
        hypotheses.append(
            ReviewHypothesisRecord(
                id="growth_blocker",
                lens="growth",
                title="可能拖慢个人节奏的因素",
                statement=f"这周的个人节奏里，可能存在“事情在推进，但自己的判断与整理没有同步跟上”的情况。当前较明显的事项包括：{blocker_titles}。",
                confidence=_confidence(len(blocker_items) + len([item for item in blocker_items if item.note.strip()])),
                reason=f"共有 {len(blocker_items)} 项私人事项尚未完成或尚未写清当前感受。",
                relatedTaskIds=[item.taskId for item in blocker_items[:4]],
                evidenceSources=["user_note", "task_fact"],
                assumptionNote="这是一种节奏判断，不代表这些事项本身做得不好。",
            )
        )
    return hypotheses


def _work_headline(item_count: int, completed_count: int, blocker_count: int) -> str:
    if item_count == 0:
        return "本周还没有形成可分析的组织复盘样本。"
    if completed_count and blocker_count:
        return "本周任务推进呈现“有进展，但卡点也已开始显性化”的状态。"
    if completed_count:
        return "本周任务推进总体偏顺，已经出现可以沉淀为方法的正向样本。"
    if blocker_count:
        return "本周任务推进阻力偏多，当前更需要先判断卡点类型，而不是继续堆动作。"
    return "本周任务仍处于推进中段，当前更适合先补齐过程事实，再做更强分析。"


def _personal_headline(item_count: int, note_count: int) -> str:
    if item_count == 0:
        return "本周还没有形成可分析的成长复盘样本。"
    if note_count >= max(1, item_count // 2):
        return "本周成长复盘已经开始从“记事情”转向“记判断”。"
    return "本周成长复盘仍偏简略，当前更像是个人事项清点，还不是完整的成长分析。"


def _build_next_focus(
    scope: Literal["work", "personal"],
    items: list[WeeklyReviewTaskEntryRecord],
    hypotheses: list[ReviewHypothesisRecord],
    *,
    viewer_role: ReviewViewerRole = "employee",
) -> list[str]:
    unfinished = [item for item in items if item.taskSnapshot.status != "done"]
    next_focus = [f"优先补齐「{_item_short_label(item)}」的支持需求和下一步动作。" for item in unfinished[:2]]
    event_line_summary = _event_line_summary(items)
    if scope == "work":
        if viewer_role == "admin":
            for story in _event_line_story_groups(items)[:3]:
                name = str(story["name"])
                next_steps = "；".join(story["nextSteps"][:1])  # type: ignore[index]
                if next_steps:
                    next_focus.append(f"下周围绕「{name}」先收束：{next_steps}。")
                elif int(story["unfinishedCount"]) > 0:
                    next_focus.append(f"下周先把「{name}」这条线的未收束动作和关键阻塞写清，再决定继续投入还是调整策略。")
        elif viewer_role == "department_lead":
            for story in _event_line_story_groups(items)[:3]:
                name = str(story["name"])
                next_steps = "；".join(story["nextSteps"][:1])  # type: ignore[index]
                if next_steps:
                    next_focus.append(f"下周围绕「{name}」先压实：{next_steps}。")
                elif int(story["unfinishedCount"]) > 0:
                    next_focus.append(f"下周先把「{name}」这条线的未收束动作和责任分工收清，再决定是否继续投入。")
        if int(event_line_summary["blockedGroupCount"]) > 0:
            blocked_names = "、".join(event_line_summary["blockedNames"][:2])
            next_focus.append(
                f"下周先按事件线收束 {blocked_names} 的推进节奏，把相关任务、会议和支持依赖放回同一条线里判断。"
                if blocked_names
                else "下周先按事件线收束相关事项，不要继续把同一件事拆成多条任务各自推进。"
            )
        if viewer_role == "department_lead" and any(item.lens == "team" for item in hypotheses):
            next_focus.append("下周先把部门内协作接口、负责人和拍板节点压实，避免继续靠临时协调推进。")
        if viewer_role != "admin" and viewer_role != "department_lead" and any(item.lens == "team" for item in hypotheses):
            next_focus.append("下周先收敛协作接口，避免继续把协同问题误判成个人执行问题。")
        if viewer_role != "admin" and viewer_role != "department_lead" and any(item.lens == "business" for item in hypotheses):
            next_focus.append("对业务判断仍模糊的事项，先补目标对象、交付标准和验证口径，再继续投入。")
        if viewer_role == "department_lead" and any(item.lens == "organization" for item in hypotheses):
            next_focus.append("把本周部门动作重新对照部门计划和机构重点，明确哪些必须继续推进，哪些应先降优先级。")
        if viewer_role != "admin" and viewer_role != "department_lead" and any(item.lens == "organization" for item in hypotheses):
            next_focus.append("把本周事项重新对照组织主线，明确哪些必须继续推进，哪些应降优先级。")
        if any(item.lens == "team" and item.title == "可能存在容量过载" for item in hypotheses):
            next_focus.append(LIGHTWEIGHT_TAG_ACTIONS["工作过度饱和"])
    else:
        next_focus.append("给仍在推进的私人事项补一句“我为什么要做这件事”，避免成长复盘只剩事实列表。")
    deduped: list[str] = []
    for item in next_focus:
        if item not in deduped:
            deduped.append(item)
    return deduped[:4]


def build_weekly_review_analysis(
    scope: Literal["work", "personal"],
    week_label: str,
    items: list[WeeklyReviewTaskEntryRecord],
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    *,
    org_model_profile: OrgModelProfileRecord | None = None,
    viewer_role: ReviewViewerRole = "employee",
    knowledge_summaries: list[dict] | None = None,
    meeting_summaries: list[dict] | None = None,
) -> WeeklyReviewAnalysisRecord:
    note_items = [item for item in items if item.note.strip() or _reflection_text(item) or _lightweight_tag(item)]
    dna_modules = _select_relevant_modules(items, organization_dna_modules, limit=3 if scope == "work" else 1)
    completion_statuses = Counter(_completion_status(item) for item in items)
    completed_count = int(completion_statuses["done_on_time"] + completion_statuses["done_late"])
    blocker_count = int(completion_statuses["in_progress"] + completion_statuses["not_done"])
    list_counts = Counter(item.taskSnapshot.listName for item in items)
    list_summary = "、".join(f"{name} {count} 项" for name, count in list_counts.most_common(3))
    metric_cards = _build_metric_cards(
        scope,
        items,
        dna_modules,
        week_label=week_label,
        org_model_profile=org_model_profile,
        viewer_role=viewer_role,
    )
    completed_with_experience = sum(
        1
        for item in items
        if _completion_status(item) in {"done_on_time", "done_late"}
        and _reflection_text(item)
    )
    unfinished_with_insight = sum(
        1
        for item in items
        if _completion_status(item) in {"in_progress", "not_done"}
        and (_reflection_text(item) or _lightweight_tag(item))
    )
    event_line_summary = _event_line_summary(items)
    tag_counts = Counter(_lightweight_tag(item) for item in items if _lightweight_tag(item))
    weekly_overview, weekly_focus_lines, weekly_next_focus = _build_weekly_overview(
        items,
        dna_modules,
        note_items_count=len(note_items),
    )
    confirmed_facts = [
        f"{week_label} 共纳入 {len(items)} 项{'工作任务' if scope == 'work' else '私人事项'}，其中已完成 {completed_count} 项，未完成 {len(items) - completed_count} 项。",
        (
            f"按时完成 {completion_statuses['done_on_time']} 项，延迟完成 {completion_statuses['done_late']} 项，仍在推进 {completion_statuses['in_progress']} 项，未完成 {completion_statuses['not_done']} 项。"
            if items
            else "当前还没有形成计划执行样本。"
        ),
        f"当前已有 {len(note_items)} 项写入一线复盘说明。"
        if note_items
        else "当前还没有足够多的一线复盘说明，系统只能基于任务事实做保守判断。",
        (
            f"已完成事项中有 {completed_with_experience} 项沉淀了成功经验，未完成事项中有 {unfinished_with_insight} 项写出了心得或教训。"
            if items
            else ""
        ),
    ]
    confirmed_facts = [item for item in confirmed_facts if item]
    if tag_counts:
        tag_summary = "、".join(f"{tag} {count} 项" for tag, count in tag_counts.most_common())
        confirmed_facts.append(f"本周一线补充的轻量卡点主要包括：{tag_summary}。")
    if list_summary:
        confirmed_facts.append(f"本周事项主要分布在：{list_summary}。")
    if dna_modules:
        confirmed_facts.append(f"本轮额外参考的 DNA 模块：{'、'.join(module.title for module in dna_modules)}。")
    quarter_goal_lines = _extract_quarter_goal_lines(dna_modules)
    if quarter_goal_lines:
        confirmed_facts.append(f"组织介绍中当前可识别的季度重点包括：{'；'.join(quarter_goal_lines[:3])}。")
    if int(event_line_summary["groupCount"]) > 0:
        names = "、".join(event_line_summary["names"][:3])
        confirmed_facts.append(
            f"本周已有 {event_line_summary['taskCount']} 条任务被归入 {event_line_summary['groupCount']} 条事件线，其中 {event_line_summary['multiTaskGroupCount']} 条事件线串起了多项持续推进事项。"
        )
        if names:
            confirmed_facts.append(f"当前识别到的主要事件线包括：{names}。")
    project_summary = _project_context_summary(items)
    if int(project_summary["count"]) > 0:
        client_text = "、".join(project_summary["clients"][:3]) or "已挂接项目"
        stage_text = f"，阶段包括：{'、'.join(project_summary['stages'][:2])}" if project_summary["stages"] else ""
        confirmed_facts.append(
            f"本周有 {project_summary['count']} 条任务已挂接项目背景，涉及：{client_text}{stage_text}。"
        )
        if project_summary["goals"]:
            confirmed_facts.append(f"项目目标线索主要包括：{'；'.join(project_summary['goals'][:2])}。")
        if project_summary["risks"]:
            confirmed_facts.append(f"项目当前显性风险包括：{'；'.join(project_summary['risks'][:2])}。")
    structured_plan_texts = _department_plan_reference_texts(org_model_profile, week_label=week_label, items=items)
    focus_item_texts = _focus_item_reference_texts(org_model_profile)
    linked_focus_ids = {_item_focus_item_id(item) for item in items if _item_focus_item_id(item)}
    linked_plan_item_ids = {_item_department_plan_item_id(item) for item in items if _item_department_plan_item_id(item)}
    if structured_plan_texts or focus_item_texts:
        plan_fact = (
            f"当前已识别到 {len(linked_plan_item_ids)} 条任务直接挂接部门计划项、{len(linked_focus_ids)} 条任务直接挂接机构重点。"
            if linked_plan_item_ids or linked_focus_ids
            else "当前周判断已开始读取正式录入的部门计划和机构重点，而不只靠自由文本做判断。"
        )
        confirmed_facts.append(plan_fact)
        preview = "；".join(_dedupe_texts([*focus_item_texts[:2], *structured_plan_texts[:2]], limit=3))
        if preview:
            confirmed_facts.append(f"本轮已读取的正式计划线索包括：{preview}。")
    # 知识库摘要注入
    _kb = knowledge_summaries or []
    if _kb:
        kb_titles = [item.get("title", "") for item in _kb[:3] if item.get("title")]
        if kb_titles:
            confirmed_facts.append(f"本轮已读取 {len(_kb)} 份客户知识库文档，包括：{'、'.join(kb_titles)}。")
    # 会议内容注入
    _ms = meeting_summaries or []
    if _ms:
        meeting_titles = [item.get("title", "") for item in _ms[:3] if item.get("title")]
        if meeting_titles:
            confirmed_facts.append(f"本轮已读取 {len(_ms)} 场相关会议，包括：{'、'.join(meeting_titles)}。")

    event_line_summaries, event_line_completeness, risk_cards, opportunity_cards = (
        _build_event_line_intelligence(items, viewer_role=viewer_role) if scope == "work" else ([], [], [], [])
    )
    trend_signals = (
        _build_trend_signals(items, event_line_summaries, event_line_completeness)
        if scope == "work"
        else []
    )

    hypotheses = (
        _build_admin_work_hypotheses(
            items,
            dna_modules,
            week_label=week_label,
            org_model_profile=org_model_profile,
            viewer_role=viewer_role if viewer_role in {"admin", "department_lead"} else "admin",
        )
        if scope == "work" and viewer_role in {"admin", "department_lead"}
        else _build_work_hypotheses(
            items,
            dna_modules,
            week_label=week_label,
            org_model_profile=org_model_profile,
        )
        if scope == "work"
        else _build_personal_hypotheses(items)
    )
    return WeeklyReviewAnalysisRecord(
        scope=scope,
        emphasis="analysis" if scope == "work" else "summary",
        headline=_work_headline(len(items), completed_count, blocker_count) if scope == "work" else _personal_headline(len(items), len(note_items)),
        caution=(
            "以下内容优先按事件线和项目语境解释本周推进，不再用向上汇报对齐口径替代机构视角。"
            if scope == "work" and viewer_role == "admin"
            else "以下内容优先按事件线和部门计划解释本周推进，不再退回到员工个人执行口径。"
            if scope == "work" and viewer_role == "department_lead"
            else "以下判断是带权重的假设性分析：用户手写复盘说明权重最高，任务客观事实次之，组织 DNA 只作为解释视角；不要把它直接当成确定结论。"
            if scope == "work"
            else "以下内容更偏个人总结和自我观察，不应让系统的解释压过你自己的真实感受。"
        ),
        weeklyOverview=weekly_overview if scope == "work" else "",
        weeklyFocusLines=weekly_focus_lines if scope == "work" else [],
        weeklyNextFocus=weekly_next_focus if scope == "work" else [],
        dnaModuleTitles=[module.title for module in dna_modules],
        metricCards=metric_cards,
        evidenceWeights=_build_evidence_weights(
            scope,
            len(note_items),
            len(items),
            dna_modules,
            project_context_count=int(project_summary["count"]),
            focus_plan_ready=bool(structured_plan_texts or focus_item_texts),
        ),
        confirmedFacts=confirmed_facts,
        hypothesisHighlights=hypotheses,
        nextWeekFocus=_build_next_focus(scope, items, hypotheses, viewer_role=viewer_role),
        eventLineSummaries=event_line_summaries,
        eventLineCompleteness=event_line_completeness,
        riskCards=risk_cards,
        opportunityCards=opportunity_cards,
        trendSignals=trend_signals,
    )


def build_hierarchy_report_from_analysis(
    analysis: WeeklyReviewAnalysisRecord,
    *,
    week_label: str,
    scope_type: Literal["employee", "team", "org"] = "org",
    scope_ref_id: str = "local",
) -> HierarchyReportRecord:
    summary_parts = [analysis.caution]
    event_line_summaries = list(getattr(analysis, "eventLineSummaries", []) or [])
    event_line_judgments = list(getattr(analysis, "eventLineJudgments", []) or [])
    risk_cards = list(getattr(analysis, "riskCards", []) or [])
    opportunity_cards = list(getattr(analysis, "opportunityCards", []) or [])
    hypothesis_highlights = list(getattr(analysis, "hypothesisHighlights", []) or [])
    next_week_focus = list(getattr(analysis, "nextWeekFocus", []) or [])
    evidence_weights = list(getattr(analysis, "evidenceWeights", []) or [])
    if event_line_judgments:
        summary_parts.append(event_line_judgments[0].whatHappened)
        summary_parts.append(event_line_judgments[0].whyItMatters)
    elif event_line_summaries:
        summary_parts.append(event_line_summaries[0].whatHappenedThisWeek)
        summary_parts.append(event_line_summaries[0].currentState)
    elif hypothesis_highlights:
        summary_parts.append(hypothesis_highlights[0].statement)
    support_signals = _risk_overview_lines(risk_cards, limit=3)
    if not support_signals and event_line_judgments:
        support_signals = _judgment_blocker_lines(event_line_judgments, limit=3)
    if not support_signals:
        support_signals = _hypothesis_overview_lines([item for item in hypothesis_highlights if item.title == "可能的阻碍原因"], limit=3)
    if not support_signals:
        support_signals = _hypothesis_overview_lines(hypothesis_highlights[1:3], limit=3)
    focus_areas = _judgment_overview_lines(event_line_judgments, limit=4) or _event_line_overview_lines(event_line_summaries, limit=4)
    if not focus_areas:
        focus_areas = _hypothesis_overview_lines(hypothesis_highlights[:4], limit=4)
    suggested_actions = _dedupe_texts(
        [
            *_judgment_action_lines(event_line_judgments, limit=3),
            *[_overview_line(item.title, item.suggestedAction) for item in risk_cards[:3]],
            *[_overview_line(item.title, item.recommendedAmplifier) for item in opportunity_cards[:3]],
            *_next_focus_overview_lines(next_week_focus, limit=3),
        ],
        limit=4,
    )
    anonymous_insights = _opportunity_overview_lines(opportunity_cards, limit=3) or _dedupe_texts(
        [
            *[_overview_line(item.title, item.managerImplication or item.opportunityIfAmplified) for item in event_line_judgments[:2]],
            *[_overview_line(item.title, item.currentState) for item in event_line_summaries[:2]],
            *_hypothesis_overview_lines(hypothesis_highlights[:2], limit=2),
        ],
        limit=3,
    )
    judgment_version = None
    bundle_fingerprint = None
    coverage_score = None
    confidence_score = None
    safe_output_mode = None
    publish_state: Literal["local_preview", "publish_ready", "published_by_human", "published_by_robot", "stale"] = "local_preview"
    published_at = None
    published_by = None
    invalidated_at = None
    publish_priority = {
        "local_preview": 0,
        "publish_ready": 1,
        "stale": 2,
        "published_by_robot": 3,
        "published_by_human": 4,
    }
    if event_line_judgments:
        judgment_versions = _dedupe_texts([item.judgmentVersion for item in event_line_judgments if item.judgmentVersion], limit=8)
        judgment_version = judgment_versions[0] if len(judgment_versions) == 1 else "mixed"
        fingerprints = sorted({item.bundleFingerprint for item in event_line_judgments if item.bundleFingerprint})
        if fingerprints:
            bundle_fingerprint = hashlib.sha1("|".join(fingerprints).encode("utf-8")).hexdigest()
        coverage_values = [item.coverageScore for item in event_line_judgments if item.coverageScore >= 0]
        if coverage_values:
            coverage_score = round(sum(coverage_values) / len(coverage_values))
        confidence_values = [item.confidenceScore for item in event_line_judgments if item.confidenceScore >= 0]
        if confidence_values:
            confidence_score = round(sum(confidence_values) / len(confidence_values))
        safe_modes = {item.safeOutputMode for item in event_line_judgments}
        if safe_modes == {"full_judgment"}:
            safe_output_mode = "full_judgment"
        elif "summary_only" in safe_modes or "full_judgment" in safe_modes:
            safe_output_mode = "summary_only"
        else:
            safe_output_mode = "needs_input"
        if safe_output_mode != "full_judgment":
            publish_state = "local_preview"
        else:
            states = [item.publishState for item in event_line_judgments]
            publish_state = max(states, key=lambda state: publish_priority.get(state, 0), default="local_preview")
            if scope_type == "employee" and publish_state == "publish_ready":
                publish_state = "local_preview"
        published_candidates = [item.publishedAt for item in event_line_judgments if item.publishedAt]
        published_at = max(published_candidates) if published_candidates else None
        published_by_candidates = [item.publishedBy for item in event_line_judgments if item.publishedBy]
        published_by = published_by_candidates[-1] if published_by_candidates else None
        invalidated_candidates = [item.invalidatedAt for item in event_line_judgments if item.invalidatedAt]
        invalidated_at = max(invalidated_candidates) if invalidated_candidates else None
    created_at = datetime.now().replace(microsecond=0).isoformat()
    return HierarchyReportRecord(
        id=f"review_report_{analysis.scope}_{week_label}",
        scopeType=scope_type,
        scopeRefId=scope_ref_id,
        weekLabel=week_label,
        logicMode="weighted_hypothesis_v1",
        judgmentVersion=judgment_version,
        bundleFingerprint=bundle_fingerprint,
        coverageScore=coverage_score,
        confidenceScore=confidence_score,
        safeOutputMode=safe_output_mode,
        headline=analysis.headline,
        summary=" ".join(summary_parts),
        summaryMetrics=analysis.metricCards,
        focusAreas=focus_areas,
        supportSignals=support_signals,
        suggestedActions=suggested_actions,
        anonymousInsights=anonymous_insights,
        sourcePolicy={
            **{item.sourceType: item.weight for item in evidence_weights},
            "eventLineSummaryCount": len(event_line_summaries),
            "eventLineJudgmentCount": len(event_line_judgments),
            "eventLineRiskCount": len(risk_cards),
            "eventLineOpportunityCount": len(opportunity_cards),
            "judgmentVersion": judgment_version,
            "bundleFingerprintCount": len({item.bundleFingerprint for item in event_line_judgments if item.bundleFingerprint}),
            "publishReadyCount": sum(1 for item in event_line_judgments if item.publishState == "publish_ready"),
            "coverageScore": coverage_score,
            "confidenceScore": confidence_score,
            "safeOutputMode": safe_output_mode,
        },
        actions=[],
        publishState=publish_state,
        publishedAt=published_at,
        publishedBy=published_by,
        invalidatedAt=invalidated_at,
        createdAt=created_at,
        updatedAt=created_at,
    )
