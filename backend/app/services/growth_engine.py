from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import (
    GrowthAbilityProfileRecord,
    GrowthAbilityScoreRecord,
    GrowthAbilityGapRecord,
    GrowthConfidence,
    GrowthContextLinkRecord,
    GrowthContributionTag,
    GrowthEvidenceLevel,
    GrowthEvidenceRecord,
    GrowthEvidenceType,
    GrowthFocusActionRecord,
    GrowthLedgerResponse,
    GrowthOverviewRecord,
    GrowthPendingCaptureRecord,
    GrowthPendingCaptureState,
    GrowthProjectHighlightRecord,
    GrowthRankRecord,
    GrowthSourceCoverageRecord,
    GrowthValidationActionResponse,
    GrowthValidationState,
    HandbookEntryRecord,
    HandbookReuseRecord,
    LearningContentItemRecord,
    LearningRecommendationRecord,
    MeetingDetail,
    StrategicCockpitSnapshotRecord,
    TaskRecord,
    WeeklyReviewRecord,
    WeeklyReviewTaskEntryRecord,
    XpLedgerEntryRecord,
)

ABILITY_ORDER = ("exec", "collab", "analyze", "insight", "risk", "write")

ABILITY_DEFAULTS = {
    "exec": {
        "label": "推进执行",
        "description": "把任务拆清楚、推动起来、按节点闭环。",
        "positive": ["主动推进", "闭环", "行动项清晰", "依赖提前处理"],
        "negative": ["长期卡住", "等别人推动", "没有下一步动作"],
    },
    "collab": {
        "label": "协作沟通",
        "description": "把多人协作中的理解、边界和行动方式说清楚。",
        "positive": ["会议闭环", "跨组对齐", "责任明确", "沟通节奏清晰"],
        "negative": ["边界不清", "返工", "理解偏差"],
    },
    "analyze": {
        "label": "分析判断",
        "description": "能解释原因、提炼规律、做出可执行判断。",
        "positive": ["原因判断", "规律提炼", "结论清楚", "能解释得失"],
        "negative": ["只报结果", "没有因果", "缺少判断"],
    },
    "insight": {
        "label": "客户洞察",
        "description": "识别客户真实顾虑、动机、限制与机会。",
        "positive": ["深层诉求", "真实顾虑", "对象理解", "使用场景"],
        "negative": ["只看表面需求", "忽略顾虑", "洞察停在表层"],
    },
    "risk": {
        "label": "风险识别",
        "description": "提前识别卡点、依赖与风险，而不是事后补救。",
        "positive": ["提前预警", "识别阻碍", "暴露依赖", "降低风险"],
        "negative": ["事后才发现", "风险未说明", "依赖不透明"],
    },
    "write": {
        "label": "写作表达",
        "description": "把经验沉淀成别人能看懂、能复用的表达。",
        "positive": ["方法卡", "模板", "话术", "可复用表达"],
        "negative": ["流水账", "表达空泛", "无法复用"],
    },
}

ABILITY_STAGE_RULES = [
    {"label": "见习", "minXp": 0},
    {"label": "上手", "minXp": 24},
    {"label": "稳态", "minXp": 54},
    {"label": "独立", "minXp": 96},
    {"label": "带动", "minXp": 150},
]

ABILITY_WEIGHTS = {
    "reflection": {"l1": 5, "l2": 10, "l3": 14},
    "codification": {"l1": 8, "l2": 12, "l3": 16},
    "reuse": {"l1": 12, "l2": 18, "l3": 24},
    "improvement": {"l1": 8, "l2": 12, "l3": 16},
}

PREMIUM_RATE_THRESHOLDS = [
    (85, 0.5),
    (70, 0.4),
    (55, 0.3),
    (40, 0.2),
]

VALIDATION_RATE_CAPS: dict[GrowthValidationState, float] = {
    "candidate": 0.2,
    "observed": 0.3,
    "validated": 0.4,
    "institutionalized": 0.5,
}

VALIDATION_STATE_ORDER: dict[GrowthValidationState, int] = {
    "candidate": 0,
    "observed": 1,
    "validated": 2,
    "institutionalized": 3,
}

RANK_DIVISIONS = ("一阶", "二阶", "三阶", "四阶", "五阶")

RANK_TIERS = [
    {"key": "t01_starter", "name": "启程见习者", "min_xp": 0, "show_division": True},
    {"key": "t02_task_apprentice", "name": "任务学徒", "min_xp": 50, "show_division": True},
    {"key": "t03_rhythm_walker", "name": "节奏行者", "min_xp": 120, "show_division": True},
    {"key": "t04_collab_branch", "name": "协作新枝", "min_xp": 210, "show_division": True},
    {"key": "t05_review_lighter", "name": "复盘点灯人", "min_xp": 320, "show_division": True},
    {"key": "t06_client_walker", "name": "客户随行者", "min_xp": 450, "show_division": True},
    {"key": "t07_thread_weaver", "name": "线索编织者", "min_xp": 600, "show_division": True},
    {"key": "t08_delivery_pusher", "name": "交付推进者", "min_xp": 780, "show_division": True},
    {"key": "t09_judgment_smith", "name": "判断工匠", "min_xp": 980, "show_division": True},
    {"key": "t10_solution_forger", "name": "方案锻造者", "min_xp": 1200, "show_division": True},
    {"key": "t11_system_builder", "name": "系统搭手", "min_xp": 1450, "show_division": True},
    {"key": "t12_dept_pivot", "name": "部门支点", "min_xp": 1730, "show_division": True},
    {"key": "t13_project_navigator", "name": "项目领航者", "min_xp": 2040, "show_division": True},
    {"key": "t14_org_pathfinder", "name": "组织通路者", "min_xp": 2380, "show_division": True},
    {"key": "t15_growth_advisor", "name": "增长参谋", "min_xp": 2750, "show_division": True},
    {"key": "t16_strategic_partner", "name": "战略合伙人", "min_xp": 3150, "show_division": True},
    {"key": "t17_framework_architect", "name": "体系构造者", "min_xp": 3600, "show_division": True},
    {"key": "t18_network_hub", "name": "网络中枢者", "min_xp": 4100, "show_division": True},
    {"key": "t19_interface_bridge", "name": "界面引桥者", "min_xp": 4650, "show_division": True},
    {"key": "t20_symbiosis_designer", "name": "共生设计师", "min_xp": 5250, "show_division": True},
]

CONTRIBUTION_TAG_CONFIG: dict[GrowthContributionTag, dict[str, object]] = {
    "knowledge_asset": {
        "keywords": ["模板", "清单", "方法", "复用", "经验", "手册", "规则", "话术", "框架"],
        "score": 18,
    },
    "critical_resolution": {
        "keywords": ["关键", "解决", "收口", "恢复", "闭环", "卡点", "问题", "阻塞"],
        "score": 18,
    },
    "collaboration_enablement": {
        "keywords": ["协作", "跨组", "对齐", "支持", "帮助", "负责人", "同步", "边界", "会议"],
        "score": 16,
    },
    "risk_alignment": {
        "keywords": ["风险", "依赖", "预警", "时间点", "责任", "边界", "阻碍", "返工"],
        "score": 15,
    },
    "mechanism_building": {
        "keywords": ["机制", "流程", "规范", "制度", "模板", "标准", "规则", "长期"],
        "score": 18,
    },
}

ABILITY_KEYWORDS = {
    "exec": ["推进", "闭环", "行动项", "排期", "拆解", "跟进", "收口", "完成", "延期", "推进完"],
    "collab": ["协作", "沟通", "对齐", "会议", "负责人", "跨组", "边界", "配合", "同步", "话术"],
    "analyze": ["分析", "判断", "原因", "本质", "结论", "规律", "假设", "洞察", "推演", "说明"],
    "insight": ["客户", "用户", "访谈", "需求", "顾虑", "诉求", "对象", "场景", "反馈", "审计客户"],
    "risk": ["风险", "阻碍", "卡点", "依赖", "预警", "问题", "延误", "退回", "不确定", "失败"],
    "write": ["写", "表达", "文档", "模板", "方法", "清单", "沉淀", "复用", "记录", "总结"],
}

DEFAULT_LEARNING_CONTENT = [
    {
        "id": "learn_exec_practice",
        "contentType": "practice_card",
        "abilityKey": "exec",
        "title": "会议闭环四要素",
        "summary": "把会议结论变成负责人、时间点、依赖项和跟进方式。",
        "body": "开会不是为了产纪要，而是为了产下一步动作。每次会议结束前，必须确认负责人、时间点、依赖项和跟进方式。",
        "practiceTask": "下次协作会结束前，用四要素生成 3 条行动项并写进任务系统。",
        "acceptanceCriteria": ["每条行动项都有负责人", "每条行动项都有时间点", "至少 1 条行动项进入任务系统"],
    },
    {
        "id": "learn_collab_correction",
        "contentType": "correction_card",
        "abilityKey": "collab",
        "title": "边界不清先补对齐话术",
        "summary": "跨组任务卡住时，先把目标、交付边界和依赖说清楚。",
        "body": "很多协作问题不是执行差，而是边界没说清。先确认目标、接口、输出格式、依赖人和时间点，再进入推进。",
        "practiceTask": "下次跨组沟通前，先写 3 句澄清话术并带着去对齐。",
        "acceptanceCriteria": ["至少写 3 句澄清问题", "会后形成清晰边界说明"],
    },
    {
        "id": "learn_analyze_method",
        "contentType": "method_card",
        "abilityKey": "analyze",
        "title": "不要只写结果，要写为什么",
        "summary": "每次复盘至少回答：发生了什么、为什么、下次怎么做。",
        "body": "分析判断的关键，不是堆信息，而是把因果链说明白。没有“为什么”的总结，很难沉淀成方法。",
        "practiceTask": "下一次复盘时，把一个结论拆成“现象 / 原因 / 建议”三段。",
        "acceptanceCriteria": ["复盘中出现 1 条明确原因判断", "复盘中出现 1 条下次建议"],
    },
    {
        "id": "learn_insight_practice",
        "contentType": "practice_card",
        "abilityKey": "insight",
        "title": "客户说“快一点”时先追问真实顾虑",
        "summary": "表层需求后面往往是协调成本、风险和不确定性。",
        "body": "客户原话不能直接当作真实需求。先问清目标、约束、担心点和当前阻力，再进入方案。",
        "practiceTask": "下一次客户沟通前，先写出 3 个追问顾虑的问题。",
        "acceptanceCriteria": ["至少准备 3 个追问问题", "复盘里写出客户真实顾虑"],
    },
    {
        "id": "learn_risk_correction",
        "contentType": "correction_card",
        "abilityKey": "risk",
        "title": "风险不要事后补，提前写在周内推进里",
        "summary": "真正有价值的风险识别，是在任务还没彻底卡死前说出来。",
        "body": "风险识别不是复盘时追认失败，而是在推进中提前把依赖、阻碍和不可控点暴露出来。",
        "practiceTask": "给一个本周任务补 1 条提前预警，并明确需要谁支持。",
        "acceptanceCriteria": ["任务备注里出现 1 条风险预警", "说明具体支持对象或依赖项"],
    },
    {
        "id": "learn_write_method",
        "contentType": "method_card",
        "abilityKey": "write",
        "title": "把经验写成可复用的方法卡",
        "summary": "好经验至少要写清结论、适用场景、成立原因和复用方式。",
        "body": "沉淀不是记流水账，而是把别人下次也能拿来用的方法写出来。要尽量做到一句标题能说清价值。",
        "practiceTask": "把本周一条复盘内容整理成一张方法卡，补上适用边界。",
        "acceptanceCriteria": ["标题能独立表达价值", "正文包含适用场景与复用方式"],
    },
]

TASK_CANDIDATE_SOURCE_TYPES = {"task_context_candidate", "task_attachment_candidate"}
MEETING_SOURCE_TYPES = {"meeting_publish"}
STRATEGIC_SOURCE_TYPES = {"strategic_confirm", "strategic_meeting_apply"}


def build_generic_learning_fallback(ability_keys: list[GrowthAbilityKey] | None = None, *, limit: int = 3) -> list[LearningContentItemRecord]:
    ordered_keys = [key for key in dict.fromkeys(ability_keys or []) if key in ABILITY_DEFAULTS]
    prioritized_items: list[dict[str, object]] = []
    if ordered_keys:
        for ability_key in ordered_keys:
            prioritized_items.extend(item for item in DEFAULT_LEARNING_CONTENT if item.get("abilityKey") == ability_key)
    prioritized_items.extend(DEFAULT_LEARNING_CONTENT)

    selected: list[LearningContentItemRecord] = []
    seen_ids: set[str] = set()
    timestamp = datetime.now().isoformat()
    for item in prioritized_items:
        item_id = str(item.get("id") or "").strip()
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        selected.append(
            LearningContentItemRecord(
                id=item_id,
                contentType=str(item.get("contentType") or "method_card"),
                abilityKey=str(item.get("abilityKey") or "exec"),
                title=str(item.get("title") or ""),
                summary=str(item.get("summary") or ""),
                body=str(item.get("body") or ""),
                practiceTask=str(item.get("practiceTask") or ""),
                acceptanceCriteria=[str(value).strip() for value in item.get("acceptanceCriteria") or [] if str(value).strip()],
                sourceKind="system_rule",
                sourceRefId=None,
                status="active",
                createdAt=timestamp,
                updatedAt=timestamp,
            )
        )
        if len(selected) >= limit:
            break
    return selected


def _as_str(value: object | None) -> str:
    return str(value).strip() if value is not None else ""


def _list_of_strings(value: object | None) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _safe_context_value(context: dict[str, object], key: str) -> str | None:
    value = context.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_context_list(context: dict[str, object], key: str) -> list[str]:
    return _list_of_strings(context.get(key))


def _json_ready_context(value: object) -> object:
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        return _json_ready_context(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _json_ready_context(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready_context(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _fact_preview_label(fact: object) -> str:
    if hasattr(fact, "factValue") and _as_str(getattr(fact, "factValue", None)):
        return _as_str(getattr(fact, "factValue", None))
    if hasattr(fact, "title") and _as_str(getattr(fact, "title", None)):
        return _as_str(getattr(fact, "title", None))
    if hasattr(fact, "factKey") and _as_str(getattr(fact, "factKey", None)):
        return _as_str(getattr(fact, "factKey", None))
    return _as_str(fact)


def _context_link_dict(
    object_type: str,
    object_id: str | None,
    label: str | None,
    *,
    subtitle: str = "",
    tab: str = "",
    status_label: str = "",
) -> dict[str, object]:
    normalized_id = _as_str(object_id)
    normalized_label = _as_str(label)
    if not normalized_id or not normalized_label:
        return {}
    return {
        "objectType": object_type,
        "objectId": normalized_id,
        "label": normalized_label,
        "subtitle": subtitle.strip(),
        "tab": tab.strip(),
        "statusLabel": status_label.strip(),
    }


def _context_links_from_context(context: dict[str, object]) -> list[GrowthContextLinkRecord]:
    raw_links = context.get("linkedContexts")
    links: list[GrowthContextLinkRecord] = []
    if isinstance(raw_links, list):
        for item in raw_links:
            if not isinstance(item, dict):
                continue
            object_id = _as_str(item.get("objectId"))
            label = _as_str(item.get("label"))
            if not object_id or not label:
                continue
            links.append(
                GrowthContextLinkRecord(
                    objectType=_as_str(item.get("objectType")) or "unknown",
                    objectId=object_id,
                    label=label,
                    subtitle=_as_str(item.get("subtitle")),
                    tab=_as_str(item.get("tab")),
                    statusLabel=_as_str(item.get("statusLabel")),
                )
            )
    strategic_link = _safe_context_value(context, "strategicLink")
    strategic_client_id = _safe_context_value(context, "clientId")
    if strategic_link and strategic_client_id and not any(link.objectType == "strategic_focus" for link in links):
        links.append(
            GrowthContextLinkRecord(
                objectType="strategic_focus",
                objectId=strategic_client_id,
                label=strategic_link,
                subtitle=_safe_context_value(context, "projectStage") or _safe_context_value(context, "clientName"),
                tab="strategic_accompaniment",
                statusLabel="战略呼应",
            )
        )
    return links


def _normalize_match_text(value: str | None) -> str:
    return re.sub(r"\s+", "", _as_str(value).lower())


def _find_best_matching_strategic_line(
    snapshot: StrategicCockpitSnapshotRecord,
    strategic_link: str | None,
) -> object | None:
    target = _normalize_match_text(strategic_link)
    if not target or not snapshot.strategicLines:
        return None
    scored: list[tuple[int, object]] = []
    for line in snapshot.strategicLines:
        texts = [
            _normalize_match_text(line.title),
            _normalize_match_text(line.summary),
            _normalize_match_text(line.decision),
            _normalize_match_text(line.nextStep),
            _normalize_match_text(line.blocker),
        ]
        score = 0
        for text in texts:
            if not text:
                continue
            if text == target:
                score = max(score, 100)
            elif target in text or text in target:
                score = max(score, 70)
            else:
                overlap = len(set(target) & set(text))
                score = max(score, overlap)
        if score > 0:
            scored.append((score, line))
    if not scored:
        return snapshot.strategicLines[0] if snapshot.strategicLines else None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _week_label_from_timestamp(timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return ""
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _lookup_client_name(db: Database, client_id: str | None) -> str | None:
    normalized_id = _as_str(client_id)
    if not normalized_id:
        return None
    row = db.fetchone("SELECT name FROM clients WHERE id = ?", (normalized_id,))
    return _as_str(row["name"]) if row and row["name"] else None


def _lookup_event_line_name(db: Database, event_line_id: str | None) -> str | None:
    normalized_id = _as_str(event_line_id)
    if not normalized_id:
        return None
    row = db.fetchone("SELECT name FROM event_lines WHERE id = ?", (normalized_id,))
    return _as_str(row["name"]) if row and row["name"] else None


def _derive_context_summary(
    *,
    client_name: str | None = None,
    event_line_name: str | None = None,
    project_stage: str | None = None,
    business_category: str | None = None,
    strategic_link: str | None = None,
    source_title: str | None = None,
    next_action: str | None = None,
) -> str:
    parts = [part for part in [client_name, event_line_name, project_stage, business_category, strategic_link, source_title] if _as_str(part)]
    summary = " / ".join(parts[:4])
    if next_action and _as_str(next_action):
        return f"{summary} · 下一步：{_as_str(next_action)}" if summary else f"下一步：{_as_str(next_action)}"
    return summary


def _build_source_route(context: dict[str, object]) -> list[str]:
    route = _safe_context_list(context, "sourceRoute")
    if route:
        return route
    items = [
        _safe_context_value(context, "sourceLabel"),
        _safe_context_value(context, "clientName"),
        _safe_context_value(context, "eventLineName"),
        _safe_context_value(context, "projectStage"),
        _safe_context_value(context, "strategicLink"),
    ]
    return [item for item in items if item]


def _build_task_signal_context(db: Database, task: TaskRecord, *, source_type: str) -> dict[str, object]:
    project_context = task.projectContext
    client_name = _as_str(task.clientName) or (project_context.clientName if project_context else "") or _as_str(_lookup_client_name(db, task.clientId))
    event_line_name = _as_str(task.eventLineName) or _as_str(_lookup_event_line_name(db, task.eventLineId))
    project_stage = project_context.stage if project_context else None
    evidence_refs = [_fact_preview_label(fact) for fact in task.linkedFactsPreview[:4] if _fact_preview_label(fact)] if task.linkedFactsPreview else []
    if task.attachments:
        evidence_refs.extend([attachment.title for attachment in task.attachments[:3] if _as_str(attachment.title)])
    evidence_refs = list(dict.fromkeys(evidence_refs))
    missing_reasons: list[str] = []
    if not task.eventLineId:
        missing_reasons.append("缺少事件线归属")
    if not (task.currentBlocker or task.nextAction or task.recentDecision):
        missing_reasons.append("缺少 blocker / 下一步 / 最近判断")
    if (task.evidenceCount or 0) <= 0 and not evidence_refs:
        missing_reasons.append("缺少附件或事实证据")
    missing_reasons.append("还没有在周复盘或成长沉淀里解释这次动作")

    linked_contexts = [
        _context_link_dict("task", task.id, task.title, subtitle=_as_str(task.status), tab="tasks", status_label=_as_str(task.priority)),
        _context_link_dict("client", task.clientId, client_name, tab="client_workspace", subtitle=project_stage or ""),
        _context_link_dict("event_line", task.eventLineId, event_line_name, tab="tasks", subtitle=_as_str(task.businessCategory)),
    ]
    if project_context and project_context.projectModuleId and project_context.projectModuleName:
        linked_contexts.append(
            _context_link_dict(
                "project_module",
                project_context.projectModuleId,
                project_context.projectModuleName,
                tab="tasks",
                subtitle=project_stage or _as_str(task.businessCategory),
            )
        )
    if project_context and project_context.projectFlowId and project_context.projectFlowName:
        linked_contexts.append(
            _context_link_dict(
                "project_flow",
                project_context.projectFlowId,
                project_context.projectFlowName,
                tab="tasks",
                subtitle=_as_str(project_context.projectModuleName),
            )
        )

    context_summary = _derive_context_summary(
        client_name=client_name,
        event_line_name=event_line_name,
        project_stage=project_stage,
        business_category=task.businessCategory,
        source_title=task.title,
        next_action=task.nextAction,
    )
    return {
        "sourceLabel": "任务候选成长",
        "taskId": task.id,
        "taskTitle": task.title,
        "taskStatus": task.status,
        "clientId": task.clientId or (project_context.clientId if project_context else None),
        "clientName": client_name,
        "eventLineId": task.eventLineId,
        "eventLineName": event_line_name,
        "projectModuleId": project_context.projectModuleId if project_context else task.projectModuleId,
        "projectModuleName": project_context.projectModuleName if project_context else task.projectModuleName,
        "projectFlowId": project_context.projectFlowId if project_context else task.projectFlowId,
        "projectFlowName": project_context.projectFlowName if project_context else task.projectFlowName,
        "projectStage": project_stage,
        "businessCategory": task.businessCategory,
        "sourceRoute": ["任务", client_name, event_line_name, project_stage],
        "currentBlocker": task.currentBlocker,
        "nextAction": task.nextAction,
        "recentDecision": task.recentDecision,
        "evidenceRefs": evidence_refs,
        "contextSummary": context_summary,
        "memoryHints": list(task.memoryHints or []),
        "backgroundReadiness": task.backgroundReadiness,
        "missingReasons": missing_reasons,
        "linkedContexts": [item for item in linked_contexts if item],
        "triggerNode": project_context.projectFlowName if project_context and project_context.projectFlowName else "任务推进",
        "sourceTypeLabel": source_type,
    }


def _build_meeting_signal_context(
    db: Database,
    *,
    client_id: str,
    meeting: MeetingDetail,
    event_line_ids: list[str] | None = None,
) -> dict[str, object]:
    client_name = _lookup_client_name(db, client_id) or ""
    event_line_names = [name for name in (_lookup_event_line_name(db, item) for item in (event_line_ids or [])) if name]
    evidence_refs = [item.summary for item in meeting.decisions[:3] if _as_str(item.summary)]
    evidence_refs.extend([item.title for item in meeting.actionItems[:3] if _as_str(item.title)])
    evidence_refs = list(dict.fromkeys(evidence_refs))
    linked_contexts = [
        _context_link_dict("meeting", meeting.id, meeting.title, subtitle=_as_str(meeting.stage), tab="client_workspace"),
        _context_link_dict("client", client_id, client_name, tab="client_workspace"),
    ]
    for event_line_id, event_line_name in zip(event_line_ids or [], event_line_names):
        linked_contexts.append(_context_link_dict("event_line", event_line_id, event_line_name, tab="tasks", subtitle="会议联动"))
    return {
        "sourceLabel": "会议发布",
        "meetingId": meeting.id,
        "meetingTitle": meeting.title,
        "clientId": client_id,
        "clientName": client_name,
        "eventLineId": event_line_ids[0] if event_line_ids else None,
        "eventLineName": event_line_names[0] if event_line_names else None,
        "projectStage": meeting.stage,
        "businessCategory": "meeting",
        "sourceRoute": ["会议", client_name, event_line_names[0] if event_line_names else "", "行动项发布"],
        "evidenceRefs": evidence_refs,
        "contextSummary": _derive_context_summary(
            client_name=client_name,
            event_line_name=event_line_names[0] if event_line_names else None,
            project_stage=_as_str(meeting.stage),
            source_title=meeting.title,
        ),
        "missingReasons": ["还没有在周复盘里解释这次会议动作的成效"],
        "linkedContexts": [item for item in linked_contexts if item],
        "triggerNode": "会议发布",
    }


def _build_strategic_signal_context(
    snapshot: StrategicCockpitSnapshotRecord,
    *,
    source_type: str,
    meeting_id: str | None = None,
) -> dict[str, object]:
    strategic_link = _as_str(snapshot.headline.coreBreakthrough.value) or _as_str(snapshot.headline.mainContradiction.value)
    focus_texts = [_as_str(item.title) for item in snapshot.pendingDecisions[:2] if _as_str(item.title)]
    matched_line = _find_best_matching_strategic_line(snapshot, strategic_link)
    linked_contexts = [
        _context_link_dict("client", snapshot.clientId, snapshot.clientName, tab="client_workspace", subtitle=snapshot.stageLabel),
    ]
    if matched_line:
        linked_contexts.append(
            _context_link_dict(
                "strategic_focus",
                f"{snapshot.clientId}:{matched_line.id}",
                matched_line.title,
                tab="strategic_accompaniment",
                subtitle=matched_line.stage or snapshot.stageLabel,
                status_label="战略呼应",
            )
        )
    if meeting_id:
        linked_contexts.append(_context_link_dict("meeting", meeting_id, "战略周会", tab="client_workspace", subtitle="战略陪伴"))
    return {
        "sourceLabel": "战略陪伴",
        "clientId": snapshot.clientId,
        "clientName": snapshot.clientName,
        "projectStage": snapshot.stageLabel,
        "businessCategory": "strategic",
        "strategicLink": strategic_link,
        "sourceRoute": ["战略陪伴", snapshot.clientName, snapshot.stageLabel, strategic_link],
        "evidenceRefs": focus_texts,
        "contextSummary": _derive_context_summary(
            client_name=snapshot.clientName,
            project_stage=snapshot.stageLabel,
            strategic_link=strategic_link,
        ),
        "missingReasons": ["还没有在任务或复盘里证明本次战略判断被实际执行"],
        "linkedContexts": [item for item in linked_contexts if item],
        "triggerNode": "战略判断确认" if source_type == "strategic_confirm" else "战略周会应用",
        "strategicLineId": matched_line.id if matched_line else None,
        "strategicLineTitle": matched_line.title if matched_line else strategic_link,
    }


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_method_like(text: str) -> bool:
    return bool(re.search(r"(模板|方法|清单|话术|框架|适用|复用|以后|下次|边界)", text))


def _contains_reasoning(text: str) -> bool:
    return bool(re.search(r"(因为|所以|导致|说明|本质|原因|判断|结论|规律|为什么)", text))


def _derive_level(text: str, *, source_type: str) -> GrowthEvidenceLevel:
    normalized = _normalize_text(text)
    if source_type == "handbook_entry" or _is_method_like(normalized):
        return "l3"
    if len(normalized) >= 40 or _contains_reasoning(normalized):
        return "l2"
    return "l1"


def _ability_stage(total_xp: int) -> tuple[str, str]:
    stage = ABILITY_STAGE_RULES[0]["label"]
    next_stage = ABILITY_STAGE_RULES[-1]["label"]
    for index, rule in enumerate(ABILITY_STAGE_RULES):
        if total_xp >= int(rule["minXp"]):
            stage = str(rule["label"])
            next_stage = str(ABILITY_STAGE_RULES[min(index + 1, len(ABILITY_STAGE_RULES) - 1)]["label"])
    return stage, next_stage


def _current_score(total_xp: int) -> int:
    return max(8, min(100, int(round((total_xp / 120) * 100))))


def _score_delta(evidence_type: GrowthEvidenceType, level: GrowthEvidenceLevel, confidence: GrowthConfidence) -> int:
    base = ABILITY_WEIGHTS[evidence_type][level]
    if confidence == "high":
        return base + 2
    if confidence == "low":
        return max(3, base - 2)
    return base


def _infer_contribution_tags(text: str, *, source_type: str, ability_key: str) -> list[GrowthContributionTag]:
    normalized = _normalize_text(text)
    matched: list[GrowthContributionTag] = []
    for tag, config in CONTRIBUTION_TAG_CONFIG.items():
        keywords = config["keywords"]
        if any(keyword in normalized for keyword in keywords):
            matched.append(tag)
    if source_type == "handbook_entry" and "knowledge_asset" not in matched:
        matched.append("knowledge_asset")
    if source_type == "handbook_entry" and _is_method_like(normalized) and "mechanism_building" not in matched:
        matched.append("mechanism_building")
    if ability_key == "collab" and "collaboration_enablement" not in matched:
        matched.append("collaboration_enablement")
    if ability_key == "risk" and "risk_alignment" not in matched:
        matched.append("risk_alignment")
    if ability_key == "write" and "knowledge_asset" not in matched:
        matched.append("knowledge_asset")
    return matched


def _max_validation_state(*states: GrowthValidationState) -> GrowthValidationState:
    return max(states, key=lambda item: VALIDATION_STATE_ORDER[item])


def _build_rank_record(total_xp: int) -> GrowthRankRecord:
    current_index = 0
    for index, tier in enumerate(RANK_TIERS):
        if total_xp >= int(tier["min_xp"]):
            current_index = index
    current_tier = RANK_TIERS[current_index]
    next_tier = RANK_TIERS[current_index + 1] if current_index + 1 < len(RANK_TIERS) else None
    current_min_xp = int(current_tier["min_xp"])
    tier_span = (int(next_tier["min_xp"]) - current_min_xp) if next_tier else 600
    progress = 1.0 if not next_tier else max(0.0, min(1.0, (total_xp - current_min_xp) / max(1, tier_span)))
    division: str | None = None
    if bool(current_tier["show_division"]):
        bucket = min(len(RANK_DIVISIONS) - 1, int(progress * len(RANK_DIVISIONS)))
        division = RANK_DIVISIONS[max(0, bucket)]
    full_label = f"{current_tier['name']}\u00b7{division}" if division else str(current_tier["name"])
    xp_to_next = max(0, int(next_tier["min_xp"]) - total_xp) if next_tier else 0
    return GrowthRankRecord(
        key=str(current_tier["key"]),
        name=str(current_tier["name"]),
        division=division,
        fullLabel=full_label,
        progress=progress,
        nextName=str(next_tier["name"]) if next_tier else None,
        xpToNext=xp_to_next,
    )


def _infer_validation_state(
    *,
    source_type: str,
    evidence_type: GrowthEvidenceType,
    level: GrowthEvidenceLevel,
    contribution_tags: list[GrowthContributionTag],
    text: str,
) -> GrowthValidationState:
    normalized = _normalize_text(text)
    if evidence_type == "reuse":
        return "institutionalized" if any(tag in contribution_tags for tag in ("knowledge_asset", "mechanism_building")) else "validated"
    if evidence_type == "improvement":
        return "validated"
    if source_type == "handbook_entry":
        return "observed"
    if level == "l3" and any(tag in contribution_tags for tag in ("knowledge_asset", "mechanism_building")):
        return "observed"
    if any(keyword in normalized for keyword in ("被复用", "标准", "统一", "大家", "团队", "跨组")):
        return "observed"
    return "candidate"


def _score_org_contribution(
    text: str,
    *,
    source_type: str,
    ability_key: str,
    evidence_type: GrowthEvidenceType,
    level: GrowthEvidenceLevel,
    confidence: GrowthConfidence,
    contribution_tags: list[GrowthContributionTag],
    validation_state: GrowthValidationState,
) -> tuple[int, float]:
    normalized = _normalize_text(text)
    leverage = 0
    if source_type == "handbook_entry":
        leverage += 8
    if any(tag in contribution_tags for tag in ("critical_resolution", "mechanism_building")):
        leverage += 10
    if any(keyword in normalized for keyword in ("团队", "组织", "跨组", "大家")):
        leverage += 7
    leverage = min(25, leverage)

    reusability = 0
    if _is_method_like(normalized):
        reusability += 8
    if any(tag in contribution_tags for tag in ("knowledge_asset", "mechanism_building")):
        reusability += 8
    if any(keyword in normalized for keyword in ("复用", "模板", "清单", "以后", "下次", "适用")):
        reusability += 6
    reusability = min(20, reusability)

    collaboration_value = 0
    if ability_key == "collab":
        collaboration_value += 5
    if any(tag == "collaboration_enablement" for tag in contribution_tags):
        collaboration_value += 8
    if any(keyword in normalized for keyword in ("支持", "帮助", "负责人", "时间点", "边界", "会议", "同步")):
        collaboration_value += 7
    collaboration_value = min(20, collaboration_value)

    risk_reduction = 0
    if ability_key == "risk":
        risk_reduction += 4
    if any(tag == "risk_alignment" for tag in contribution_tags):
        risk_reduction += 6
    if any(keyword in normalized for keyword in ("风险", "预警", "依赖", "返工", "阻碍", "卡点")):
        risk_reduction += 5
    risk_reduction = min(15, risk_reduction)

    mechanism_value = 0
    if any(tag == "mechanism_building" for tag in contribution_tags):
        mechanism_value += 6
    if source_type == "handbook_entry":
        mechanism_value += 2
    if any(keyword in normalized for keyword in ("规则", "流程", "规范", "机制", "模板")):
        mechanism_value += 4
    mechanism_value = min(10, mechanism_value)

    validation_strength = 0
    if validation_state == "observed":
        validation_strength = 4
    elif validation_state == "validated":
        validation_strength = 7
    elif validation_state == "institutionalized":
        validation_strength = 10
    if evidence_type in {"reuse", "improvement"}:
        validation_strength = max(validation_strength, 7)
    if level == "l3":
        validation_strength = min(10, validation_strength + 1)
    if confidence == "high":
        validation_strength = min(10, validation_strength + 1)

    score = min(100, leverage + reusability + collaboration_value + risk_reduction + mechanism_value + validation_strength)
    premium_rate = 0.0
    for threshold, rate in PREMIUM_RATE_THRESHOLDS:
        if score >= threshold:
            premium_rate = rate
            break
    premium_rate = min(premium_rate, VALIDATION_RATE_CAPS[validation_state])
    return score, premium_rate


def _build_profile_record(ability_key: str, timestamp: str) -> GrowthAbilityProfileRecord:
    config = ABILITY_DEFAULTS[ability_key]
    return GrowthAbilityProfileRecord(
        id=f"gap_{ability_key}",
        abilityKey=ability_key,  # type: ignore[arg-type]
        label=str(config["label"]),
        description=str(config["description"]),
        stageRules=list(ABILITY_STAGE_RULES),
        positiveSignals=list(config["positive"]),
        negativeSignals=list(config["negative"]),
        weights={"xp": ABILITY_WEIGHTS},
        createdAt=timestamp,
        updatedAt=timestamp,
    )


def ensure_growth_catalog(db: Database, timestamp: str | None = None) -> None:
    now_value = timestamp or _now_iso()
    for ability_key in ABILITY_ORDER:
        profile = _build_profile_record(ability_key, now_value)
        db.execute(
            """
            INSERT OR IGNORE INTO growth_ability_profiles(
                id, ability_key, label, description, stage_rules_json, positive_signals_json, negative_signals_json, weights_json, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.id,
                profile.abilityKey,
                profile.label,
                profile.description,
                to_json(profile.stageRules),
                to_json(profile.positiveSignals),
                to_json(profile.negativeSignals),
                to_json(profile.weights),
                profile.createdAt,
                profile.updatedAt,
            ),
        )
    for item in DEFAULT_LEARNING_CONTENT:
        db.execute(
            """
            INSERT OR IGNORE INTO learning_content_items(
                id, content_type, ability_key, title, summary, body, practice_task, acceptance_criteria_json, source_kind, source_ref_id, status, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'system_rule', NULL, 'active', ?, ?)
            """,
            (
                item["id"],
                item["contentType"],
                item["abilityKey"],
                item["title"],
                item["summary"],
                item["body"],
                item["practiceTask"],
                to_json(item["acceptanceCriteria"]),
                now_value,
                now_value,
            ),
        )


def _fetch_profile_map(db: Database) -> dict[str, GrowthAbilityProfileRecord]:
    ensure_growth_catalog(db)
    rows = db.fetchall("SELECT * FROM growth_ability_profiles ORDER BY rowid ASC")
    profile_map: dict[str, GrowthAbilityProfileRecord] = {}
    for row in rows:
        profile = GrowthAbilityProfileRecord(
            id=str(row["id"]),
            abilityKey=str(row["ability_key"]),  # type: ignore[arg-type]
            label=str(row["label"]),
            description=str(row["description"] or ""),
            stageRules=from_json(row["stage_rules_json"], []),  # type: ignore[arg-type]
            positiveSignals=from_json(row["positive_signals_json"], []),  # type: ignore[arg-type]
            negativeSignals=from_json(row["negative_signals_json"], []),  # type: ignore[arg-type]
            weights=from_json(row["weights_json"], {}),  # type: ignore[arg-type]
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )
        profile_map[str(row["ability_key"])] = profile
    return profile_map


def _keyword_hits(text: str) -> dict[str, int]:
    normalized = _normalize_text(text)
    scores = defaultdict(int)
    for ability_key, keywords in ABILITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword and keyword in normalized:
                scores[ability_key] += 1
    return scores


def _infer_general_hits(
    text: str,
    *,
    source_type: str,
    preferred: list[str] | None = None,
) -> list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    scores = _keyword_hits(normalized)
    for ability_key in preferred or []:
        scores[ability_key] += 2
    if source_type == "handbook_entry":
        scores["write"] += 3
    if _is_method_like(normalized):
        scores["write"] += 2

    ordered = sorted(scores.items(), key=lambda item: (-item[1], ABILITY_ORDER.index(item[0]) if item[0] in ABILITY_ORDER else 99))
    if not ordered and len(normalized) >= 24:
        ordered = [("analyze", 1)]

    level = _derive_level(normalized, source_type=source_type)
    results: list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]] = []
    for ability_key, score in ordered[:3]:
        if score <= 0:
            continue
        confidence: GrowthConfidence = "high" if score >= 3 else "medium" if score == 2 else "low"
        matched_keywords = [keyword for keyword in ABILITY_KEYWORDS.get(ability_key, []) if keyword in normalized][:3]
        reason = "命中了成长信号"
        if matched_keywords:
            reason = f"提到了{'、'.join(matched_keywords)}"
        results.append((ability_key, level, confidence, reason))
    return results


def infer_review_hits(entry: WeeklyReviewTaskEntryRecord) -> list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]]:
    structured = entry.structuredNote
    preferred: list[str] = []
    if structured.reflection.strip() or structured.successExperience.strip() or structured.progress.strip() or entry.taskSnapshot.status == "done":
        preferred.append("exec")
    if structured.reflection.strip() or structured.successReason.strip() or structured.failureInsight.strip():
        preferred.append("analyze")
    if structured.lightweightTag.strip() or structured.blockerReason.strip() or structured.supportNeeded.strip():
        preferred.extend(["risk", "collab"])
    joined_text = " ".join(
        [
            entry.taskSnapshot.title,
            entry.note,
            structured.reflection,
            structured.lightweightTag,
            structured.progress,
            structured.successReason,
            structured.successExperience,
            structured.blockerReason,
            structured.failureInsight,
            structured.supportNeeded,
            structured.nextAction,
            " ".join(tag.name for tag in entry.taskSnapshot.tags),
        ]
    )
    hits = _infer_general_hits(joined_text, source_type="weekly_review_task_entry", preferred=preferred)
    unique: list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]] = []
    seen: set[str] = set()
    for hit in hits:
        if hit[0] in seen:
            continue
        seen.add(hit[0])
        unique.append(hit)
    return unique


def infer_handbook_hits(entry: HandbookEntryRecord) -> list[tuple[str, GrowthEvidenceLevel, GrowthConfidence, str]]:
    text = " ".join([entry.title, entry.summary, " ".join(entry.tags), entry.sourceType])
    preferred = ["write"]
    if entry.sourceType == "meeting":
        preferred.append("collab")
    if entry.sourceType == "task":
        preferred.append("exec")
    if entry.sourceType == "analysis":
        preferred.append("analyze")
    hits = _infer_general_hits(text, source_type="handbook_entry", preferred=preferred)
    if not any(item[0] == "write" for item in hits):
        hits.insert(0, ("write", "l3", "high", "已将经验整理成正式成长手册条目"))
    return hits[:3]


def _upsert_signal(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    source_type: str,
    source_id: str,
    review_id: str | None,
    task_id: str | None,
    week_label: str,
    raw_text: str,
    context: dict[str, object],
    dedupe_key: str,
    created_at: str,
) -> str:
    existing = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing:
        signal_id = str(existing["id"])
        db.execute(
            """
            UPDATE growth_signal_events
            SET user_id = ?, user_name = ?, source_type = ?, source_id = ?, review_id = ?, task_id = ?, week_label = ?, raw_text = ?, context_json = ?, created_at = ?
            WHERE id = ?
            """,
            (
                user_id,
                user_name,
                source_type,
                source_id,
                review_id,
                task_id,
                week_label,
                raw_text,
                to_json(_json_ready_context(context)),
                created_at,
                signal_id,
            ),
        )
        return signal_id
    return _insert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type=source_type,
        source_id=source_id,
        review_id=review_id,
        task_id=task_id,
        week_label=week_label,
        raw_text=raw_text,
        context=context,
        dedupe_key=dedupe_key,
        created_at=created_at,
    )


def ingest_task_growth_candidate(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    task: TaskRecord,
    source_type: str = "task_context_candidate",
    created_at: str | None = None,
    ai_service: object | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    context = _build_task_signal_context(db, task, source_type=source_type)
    raw_text = _normalize_text(
        " ".join(
            [
                task.title,
                task.desc,
                _as_str(task.currentBlocker),
                _as_str(task.nextAction),
                _as_str(task.recentDecision),
                _as_str(context.get("contextSummary")),
                " ".join(_safe_context_list(context, "evidenceRefs")),
                " ".join(_safe_context_list(context, "memoryHints")),
            ]
        )
    )
    meaningful = bool(task.eventLineId or task.projectContext or task.clientId or task.currentBlocker or task.nextAction or task.recentDecision or (task.evidenceCount or 0) > 0 or task.attachments)
    if not meaningful or not raw_text:
        return

    # ── AI insight quote distillation ──────────────────────────
    if ai_service is not None:
        try:
            result = ai_service.distill_growth_insight_quote(
                task_title=task.title,
                task_desc=task.desc or "",
                client_name=_as_str(context.get("clientName")) or "",
                event_line_name=_as_str(context.get("eventLineName")) or "",
                blocker=_as_str(task.currentBlocker) or "",
                next_action=_as_str(task.nextAction) or "",
                recent_decision=_as_str(task.recentDecision) or "",
                context_summary=_as_str(context.get("contextSummary")) or "",
                evidence_refs=_safe_context_list(context, "evidenceRefs"),
            )
            if result.get("quote"):
                context["insightQuote"] = result["quote"]
            if result.get("sourceLabel"):
                context["insightSourceLabel"] = result["sourceLabel"]
        except Exception:
            pass  # Non-critical: fall back to raw title/summary

    _upsert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type=source_type,
        source_id=task.id,
        review_id=None,
        task_id=task.id,
        week_label=_week_label_from_timestamp(timestamp),
        raw_text=raw_text,
        context=context,
        dedupe_key=f"task-candidate:{task.id}",
        created_at=timestamp,
    )


def ingest_meeting_growth_candidate(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    client_id: str,
    meeting: MeetingDetail,
    event_line_ids: list[str] | None = None,
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    context = _build_meeting_signal_context(db, client_id=client_id, meeting=meeting, event_line_ids=event_line_ids)
    raw_text = _normalize_text(
        " ".join(
            [
                meeting.title,
                meeting.notes,
                meeting.transcriptText[:280],
                " ".join(item.summary for item in meeting.decisions[:3]),
                " ".join(item.title for item in meeting.actionItems[:3]),
                " ".join(item.summary for item in meeting.risks[:2]),
            ]
        )
    )
    if not raw_text:
        return
    signal_id = _upsert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type="meeting_publish",
        source_id=meeting.id,
        review_id=None,
        task_id=None,
        week_label=_week_label_from_timestamp(timestamp),
        raw_text=raw_text,
        context=context,
        dedupe_key=f"meeting-publish:{meeting.id}",
        created_at=timestamp,
    )
    preferred = ["collab", "risk", "exec", "write"]
    if client_id:
        preferred.append("insight")
    for ability_key, level, confidence, reason in _infer_general_hits(raw_text, source_type="meeting_publish", preferred=preferred):
        _insert_evidence_and_xp(
            db,
            user_id=user_id,
            user_name=user_name,
            signal_id=signal_id,
            ability_key=ability_key,
            evidence_type="reflection",
            level=level,
            confidence=confidence,
            reason=reason,
            review_id=None,
            task_id=None,
            handbook_entry_id=None,
            source_title=meeting.title,
            week_label=_week_label_from_timestamp(timestamp),
            source_type="meeting_publish",
            raw_text=raw_text,
            context=context,
            created_at=timestamp,
        )


def ingest_strategic_growth_candidate(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    snapshot: StrategicCockpitSnapshotRecord,
    source_type: str,
    source_id: str,
    meeting_id: str | None = None,
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    context = _build_strategic_signal_context(snapshot, source_type=source_type, meeting_id=meeting_id)
    raw_text = _normalize_text(
        " ".join(
            [
                snapshot.headline.weekSummary.value,
                snapshot.headline.mainContradiction.value,
                snapshot.headline.coreBreakthrough.value,
                snapshot.stageLabel,
                " ".join(item.title for item in snapshot.pendingDecisions[:3] if _as_str(item.title)),
                " ".join(item.title for item in snapshot.pendingMaterials[:3] if _as_str(item.title)),
                " ".join(item for item in snapshot.meetingPackDraft.agenda[:3] if _as_str(item)),
            ]
        )
    )
    if not raw_text:
        return
    signal_id = _upsert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type=source_type,
        source_id=source_id,
        review_id=None,
        task_id=None,
        week_label=_week_label_from_timestamp(timestamp),
        raw_text=raw_text,
        context=context,
        dedupe_key=f"{source_type}:{source_id}",
        created_at=timestamp,
    )
    for ability_key, level, confidence, reason in _infer_general_hits(raw_text, source_type=source_type, preferred=["analyze", "collab", "exec", "write"]):
        _insert_evidence_and_xp(
            db,
            user_id=user_id,
            user_name=user_name,
            signal_id=signal_id,
            ability_key=ability_key,
            evidence_type="reflection",
            level=level,
            confidence=confidence,
            reason=reason,
            review_id=None,
            task_id=None,
            handbook_entry_id=None,
            source_title=_as_str(snapshot.headline.coreBreakthrough.value) or _as_str(snapshot.headline.mainContradiction.value) or snapshot.clientName,
            week_label=_week_label_from_timestamp(timestamp),
            source_type=source_type,
            raw_text=raw_text,
            context=context,
            created_at=timestamp,
        )


def _insert_signal(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    source_type: str,
    source_id: str,
    review_id: str | None,
    task_id: str | None,
    week_label: str,
    raw_text: str,
    context: dict[str, object],
    dedupe_key: str,
    created_at: str,
) -> str:
    existing = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing:
        return str(existing["id"])
    signal_id = _new_id("gse")
    db.execute(
        """
        INSERT INTO growth_signal_events(
            id, user_id, user_name, source_type, source_id, review_id, task_id, week_label, raw_text, context_json, dedupe_key, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            user_id,
            user_name,
            source_type,
            source_id,
            review_id,
            task_id,
            week_label,
            raw_text,
            to_json(_json_ready_context(context)),
            dedupe_key,
            created_at,
        ),
    )
    return signal_id


def _has_prior_context_chain(
    db: Database,
    *,
    user_id: str,
    task_id: str | None,
    event_line_id: str | None,
    client_id: str | None,
    source_types: set[str] | None = None,
) -> bool:
    clauses = ["user_id = ?"]
    params: list[object] = [user_id]
    if source_types:
        placeholders = ", ".join("?" for _ in source_types)
        clauses.append(f"source_type IN ({placeholders})")
        params.extend(list(source_types))
    id_clauses: list[str] = []
    if _as_str(task_id):
        id_clauses.append("task_id = ?")
        params.append(_as_str(task_id))
    if _as_str(event_line_id):
        id_clauses.append("json_extract(context_json, '$.eventLineId') = ?")
        params.append(_as_str(event_line_id))
    if _as_str(client_id):
        id_clauses.append("json_extract(context_json, '$.clientId') = ?")
        params.append(_as_str(client_id))
    if not id_clauses:
        return False
    row = db.fetchone(
        f"SELECT 1 FROM growth_signal_events WHERE {' AND '.join(clauses)} AND ({' OR '.join(id_clauses)}) LIMIT 1",
        tuple(params),
    )
    return row is not None


def _continuity_weight(
    db: Database,
    *,
    user_id: str,
    task_id: str | None,
    context: dict[str, object],
) -> float:
    event_line_id = _safe_context_value(context, "eventLineId")
    client_id = _safe_context_value(context, "clientId")
    has_chain = _has_prior_context_chain(
        db,
        user_id=user_id,
        task_id=task_id,
        event_line_id=event_line_id,
        client_id=client_id,
        source_types=TASK_CANDIDATE_SOURCE_TYPES | MEETING_SOURCE_TYPES | STRATEGIC_SOURCE_TYPES,
    )
    return 1.15 if has_chain else 1.0


def _strategic_alignment_weight(context: dict[str, object]) -> float:
    if _safe_context_value(context, "strategicLink"):
        return 1.12
    if _safe_context_value(context, "projectStage") and "战略" in (_safe_context_value(context, "sourceLabel") or ""):
        return 1.08
    return 1.0


def _insert_evidence_and_xp(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    signal_id: str,
    ability_key: str,
    evidence_type: GrowthEvidenceType,
    level: GrowthEvidenceLevel,
    confidence: GrowthConfidence,
    reason: str,
    review_id: str | None,
    task_id: str | None,
    handbook_entry_id: str | None,
    source_title: str | None,
    week_label: str,
    source_type: str,
    raw_text: str,
    context: dict[str, object] | None = None,
    created_at: str,
) -> tuple[str, int, GrowthValidationState]:
    normalized_context = context or {}
    contribution_tags = _infer_contribution_tags(raw_text, source_type=source_type, ability_key=ability_key)
    validation_state = _infer_validation_state(
        source_type=source_type,
        evidence_type=evidence_type,
        level=level,
        contribution_tags=contribution_tags,
        text=raw_text,
    )
    continuity_weight = _continuity_weight(
        db,
        user_id=user_id,
        task_id=task_id,
        context=normalized_context,
    )
    strategic_alignment_weight = _strategic_alignment_weight(normalized_context)
    org_contribution_score, premium_rate = _score_org_contribution(
        raw_text,
        source_type=source_type,
        ability_key=ability_key,
        evidence_type=evidence_type,
        level=level,
        confidence=confidence,
        contribution_tags=contribution_tags,
        validation_state=validation_state,
    )
    evidence_id = _new_id("gev")
    db.execute(
        """
        INSERT INTO growth_evidence_records(
            id, signal_id, user_id, user_name, ability_key, evidence_type, level, confidence, reason, review_id, task_id, handbook_entry_id, metadata_json, contribution_tags_json, org_contribution_score, suggested_premium_rate, validation_state, ai_reason, ai_confidence, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            signal_id,
            user_id,
            user_name,
            ability_key,
            evidence_type,
            level,
            confidence,
            reason,
            review_id,
            task_id,
            handbook_entry_id,
            to_json(
                {
                    "sourceTitle": source_title or "",
                    "contextSummary": _safe_context_value(normalized_context, "contextSummary") or "",
                    "sourceRoute": _build_source_route(normalized_context),
                    "evidenceRefs": _safe_context_list(normalized_context, "evidenceRefs"),
                    "clientId": _safe_context_value(normalized_context, "clientId"),
                    "clientName": _safe_context_value(normalized_context, "clientName"),
                    "eventLineId": _safe_context_value(normalized_context, "eventLineId"),
                    "eventLineName": _safe_context_value(normalized_context, "eventLineName"),
                    "meetingId": _safe_context_value(normalized_context, "meetingId"),
                    "reviewId": review_id,
                    "taskId": task_id,
                    "projectStage": _safe_context_value(normalized_context, "projectStage"),
                    "businessCategory": _safe_context_value(normalized_context, "businessCategory"),
                    "strategicLink": _safe_context_value(normalized_context, "strategicLink"),
                    "linkedContexts": normalized_context.get("linkedContexts") if isinstance(normalized_context.get("linkedContexts"), list) else [],
                    "continuityWeight": continuity_weight,
                    "strategicAlignmentWeight": strategic_alignment_weight,
                }
            ),
            to_json(contribution_tags),
            org_contribution_score,
            premium_rate,
            validation_state,
            reason,
            0.0,
            created_at,
        ),
    )
    base_xp = int(round(_score_delta(evidence_type, level, confidence) * continuity_weight * strategic_alignment_weight))
    base_xp = max(1, base_xp)
    premium_xp = int(round(base_xp * premium_rate))
    total_xp = base_xp + premium_xp
    xp_dedupe_key = f"{signal_id}:{ability_key}:{evidence_type}"
    db.execute(
        """
        INSERT INTO xp_ledger(
            id, user_id, user_name, ability_key, evidence_id, xp_type, delta, base_xp, premium_rate, premium_xp, total_xp, contribution_tags_json, validation_state, org_contribution_score, dedupe_key, week_label, created_at, reversed_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            _new_id("xp"),
            user_id,
            user_name,
            ability_key,
            evidence_id,
            evidence_type,
            total_xp,
            base_xp,
            premium_rate,
            premium_xp,
            total_xp,
            to_json(contribution_tags),
            validation_state,
            org_contribution_score,
            xp_dedupe_key,
            week_label,
            created_at,
        ),
    )
    return evidence_id, total_xp, validation_state


def _record_validation_event(
    db: Database,
    *,
    user_id: str,
    evidence_id: str,
    event_type: str,
    actor_id: str,
    actor_name: str,
    source_type: str,
    source_id: str,
    detail: dict[str, object],
    created_at: str,
) -> bool:
    existing = db.fetchone(
        """
        SELECT id
        FROM growth_validation_events
        WHERE user_id = ? AND evidence_id = ? AND event_type = ? AND source_type = ? AND source_id = ?
        """,
        (user_id, evidence_id, event_type, source_type, source_id),
    )
    if existing:
        return False
    db.execute(
        """
        INSERT INTO growth_validation_events(
            id, user_id, evidence_id, event_type, actor_id, actor_name, source_type, source_id, detail_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _new_id("gve"),
            user_id,
            evidence_id,
            event_type,
            actor_id,
            actor_name,
            source_type,
            source_id,
            to_json(detail),
            created_at,
        ),
    )
    return True


def reset_review_growth(db: Database, review_id: str) -> None:
    evidence_rows = db.fetchall("SELECT id FROM growth_evidence_records WHERE review_id = ?", (review_id,))
    if evidence_rows:
        db.executemany("DELETE FROM xp_ledger WHERE evidence_id = ?", [(str(row["id"]),) for row in evidence_rows])
    db.execute("DELETE FROM growth_evidence_records WHERE review_id = ?", (review_id,))
    db.execute("DELETE FROM growth_signal_events WHERE review_id = ?", (review_id,))


def ingest_review_growth(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    review: WeeklyReviewRecord,
    task_entries: list[WeeklyReviewTaskEntryRecord],
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    reset_review_growth(db, review.id)

    for entry in task_entries:
        signal_text = _normalize_text(
            " ".join(
                [
                    entry.note,
                    entry.structuredNote.progress,
                    entry.structuredNote.successReason,
                    entry.structuredNote.successExperience,
                    entry.structuredNote.blockerReason,
                    entry.structuredNote.failureInsight,
                    entry.structuredNote.supportNeeded,
                    entry.structuredNote.nextAction,
                ]
            )
        )
        if not signal_text:
            continue
        review_context = {
            "sourceLabel": "周复盘",
            "taskId": entry.taskId,
            "taskTitle": entry.taskSnapshot.title,
            "taskStatus": entry.taskSnapshot.status,
            "contentDomain": entry.contentDomain,
            "clientId": entry.taskSnapshot.clientId,
            "clientName": entry.taskSnapshot.clientName,
            "eventLineId": entry.taskSnapshot.eventLineId,
            "eventLineName": entry.taskSnapshot.eventLineName,
            "projectModuleId": entry.taskSnapshot.projectContext.projectModuleId if entry.taskSnapshot.projectContext else None,
            "projectModuleName": entry.taskSnapshot.projectContext.projectModuleName if entry.taskSnapshot.projectContext else None,
            "projectFlowId": entry.taskSnapshot.projectContext.projectFlowId if entry.taskSnapshot.projectContext else None,
            "projectFlowName": entry.taskSnapshot.projectContext.projectFlowName if entry.taskSnapshot.projectContext else None,
            "projectStage": entry.taskSnapshot.projectContext.stage if entry.taskSnapshot.projectContext else entry.taskSnapshot.eventLineContext.stage if entry.taskSnapshot.eventLineContext else None,
            "businessCategory": entry.taskSnapshot.eventLineContext.businessCategory if entry.taskSnapshot.eventLineContext else None,
            "evidenceRefs": [_fact_preview_label(fact) for fact in entry.taskSnapshot.projectContext.sourceEvidence[:3]] if entry.taskSnapshot.projectContext else [],
            "contextSummary": _derive_context_summary(
                client_name=entry.taskSnapshot.clientName,
                event_line_name=entry.taskSnapshot.eventLineName,
                project_stage=entry.taskSnapshot.projectContext.stage if entry.taskSnapshot.projectContext else entry.taskSnapshot.eventLineContext.stage if entry.taskSnapshot.eventLineContext else None,
                business_category=entry.taskSnapshot.eventLineContext.businessCategory if entry.taskSnapshot.eventLineContext else None,
                source_title=entry.taskSnapshot.title,
                next_action=entry.structuredNote.nextAction,
            ),
            "strategicLink": "组织重点对齐" if entry.structuredNote.organizationPlanAlignment == "aligned" else "",
            "sourceRoute": [
                "周复盘",
                entry.taskSnapshot.clientName,
                entry.taskSnapshot.eventLineName,
                entry.taskSnapshot.projectContext.stage if entry.taskSnapshot.projectContext else entry.taskSnapshot.eventLineContext.stage if entry.taskSnapshot.eventLineContext else None,
            ],
            "linkedContexts": [
                item
                for item in (
                    _context_link_dict("review", review.id, review.weekLabel, tab="tasks", subtitle=entry.contentDomain),
                    _context_link_dict("task", entry.taskId, entry.taskSnapshot.title, tab="tasks", subtitle=_as_str(entry.taskSnapshot.status)),
                    _context_link_dict("client", entry.taskSnapshot.clientId, entry.taskSnapshot.clientName, tab="client_workspace"),
                    _context_link_dict("event_line", entry.taskSnapshot.eventLineId, entry.taskSnapshot.eventLineName, tab="tasks", subtitle=_as_str(entry.taskSnapshot.eventLineContext.stage) if entry.taskSnapshot.eventLineContext else ""),
                    _context_link_dict(
                        "project_module",
                        entry.taskSnapshot.projectContext.projectModuleId if entry.taskSnapshot.projectContext else None,
                        entry.taskSnapshot.projectContext.projectModuleName if entry.taskSnapshot.projectContext else None,
                        tab="tasks",
                        subtitle=entry.taskSnapshot.projectContext.stage if entry.taskSnapshot.projectContext else "",
                    ),
                    _context_link_dict(
                        "project_flow",
                        entry.taskSnapshot.projectContext.projectFlowId if entry.taskSnapshot.projectContext else None,
                        entry.taskSnapshot.projectContext.projectFlowName if entry.taskSnapshot.projectContext else None,
                        tab="tasks",
                        subtitle=entry.taskSnapshot.projectContext.projectModuleName if entry.taskSnapshot.projectContext else "",
                    ),
                )
                if item
            ],
            "triggerNode": (
                entry.taskSnapshot.projectContext.projectFlowName
                if entry.taskSnapshot.projectContext and entry.taskSnapshot.projectContext.projectFlowName
                else entry.taskSnapshot.eventLineContext.stage
                if entry.taskSnapshot.eventLineContext
                else "周复盘解释"
            ),
        }
        signal_id = _insert_signal(
            db,
            user_id=user_id,
            user_name=user_name,
            source_type="weekly_review_task_entry",
            source_id=entry.id,
            review_id=review.id,
            task_id=entry.taskId,
            week_label=review.weekLabel,
            raw_text=signal_text,
            context=review_context,
            dedupe_key=f"review:{review.id}:task:{entry.taskId}",
            created_at=timestamp,
        )
        for ability_key, level, confidence, reason in infer_review_hits(entry):
            _insert_evidence_and_xp(
                db,
                user_id=user_id,
                user_name=user_name,
                signal_id=signal_id,
                ability_key=ability_key,
                evidence_type="reflection",
                level=level,
                confidence=confidence,
                reason=reason,
                review_id=review.id,
                task_id=entry.taskId,
                handbook_entry_id=None,
                source_title=entry.taskSnapshot.title,
                week_label=review.weekLabel,
                source_type="weekly_review_task_entry",
                raw_text=signal_text,
                context=review_context,
                created_at=timestamp,
            )

    for note_key, text in (
        ("work_free_note", review.workFreeNote),
        ("personal_growth_note", review.personalGrowthNote),
    ):
        normalized = _normalize_text(text)
        if not normalized:
            continue
        signal_id = _insert_signal(
            db,
            user_id=user_id,
            user_name=user_name,
            source_type="weekly_review_note",
            source_id=f"{review.id}:{note_key}",
            review_id=review.id,
            task_id=None,
            week_label=review.weekLabel,
            raw_text=normalized,
            context={
                "sourceLabel": "周复盘补充说明",
                "noteKey": note_key,
                "contextSummary": "周复盘补充说明",
                "sourceRoute": ["周复盘", "补充说明"],
                "linkedContexts": [_context_link_dict("review", review.id, review.weekLabel, tab="tasks", subtitle="补充说明")],
                "triggerNode": "周复盘补充说明",
            },
            dedupe_key=f"review:{review.id}:{note_key}",
            created_at=timestamp,
        )
        for ability_key, level, confidence, reason in _infer_general_hits(normalized, source_type="weekly_review_note"):
            _insert_evidence_and_xp(
                db,
                user_id=user_id,
                user_name=user_name,
                signal_id=signal_id,
                ability_key=ability_key,
                evidence_type="reflection",
                level=level,
                confidence=confidence,
                reason=reason,
                review_id=review.id,
                task_id=None,
                handbook_entry_id=None,
                source_title="周复盘补充说明",
                week_label=review.weekLabel,
                source_type="weekly_review_note",
                raw_text=normalized,
                context={
                    "sourceLabel": "周复盘补充说明",
                    "contextSummary": "周复盘补充说明",
                    "sourceRoute": ["周复盘", "补充说明"],
                    "linkedContexts": [_context_link_dict("review", review.id, review.weekLabel, tab="tasks", subtitle="补充说明")],
                },
                created_at=timestamp,
            )

    rebuild_learning_recommendations(db, user_id=user_id, user_name=user_name, week_label=review.weekLabel, created_at=timestamp)


def ingest_handbook_codification(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    entry: HandbookEntryRecord,
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    dedupe_key = f"handbook:{entry.id}"
    existing = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing:
        return
    signal_id = _insert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type="handbook_entry",
        source_id=entry.id,
        review_id=None,
        task_id=None,
        week_label="",
        raw_text=_normalize_text(f"{entry.title} {entry.summary} {' '.join(entry.tags)}"),
        context={
            "sourceLabel": "成长手册沉淀",
            "sourceType": entry.sourceType,
            "sourceObjectType": entry.sourceObjectType,
            "sourceObjectId": entry.sourceObjectId,
            "sourceTitle": entry.sourceTitle or entry.title,
            "clientId": entry.clientId,
            "clientName": entry.clientName,
            "eventLineId": entry.eventLineId,
            "eventLineName": entry.eventLineName,
            "projectModuleId": entry.projectModuleId,
            "projectModuleName": entry.projectModuleName,
            "projectFlowId": entry.projectFlowId,
            "projectFlowName": entry.projectFlowName,
            "projectStage": entry.projectStage,
            "businessCategory": entry.businessCategory,
            "evidenceRefs": list(entry.evidenceRefs),
            "contextSummary": entry.contextSummary or _derive_context_summary(
                client_name=entry.clientName,
                event_line_name=entry.eventLineName,
                project_stage=entry.projectStage,
                business_category=entry.businessCategory,
                source_title=entry.title,
            ),
            "sourceRoute": ["成长手册", entry.clientName, entry.eventLineName, entry.projectStage],
            "linkedContexts": [link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else [
                item
                for item in (
                    _context_link_dict("handbook", entry.id, entry.title, tab="growth", subtitle=entry.sourceType),
                    _context_link_dict(entry.sourceObjectType or "", entry.sourceObjectId, entry.sourceTitle, tab="growth"),
                    _context_link_dict("client", entry.clientId, entry.clientName, tab="client_workspace"),
                    _context_link_dict("event_line", entry.eventLineId, entry.eventLineName, tab="tasks", subtitle=entry.projectStage or ""),
                )
                if item
            ],
            "strategicLink": entry.contextSummary if "战略" in entry.contextSummary else "",
            "triggerNode": entry.projectFlowName or entry.projectStage or "经验沉淀",
        },
        dedupe_key=dedupe_key,
        created_at=timestamp,
    )
    for ability_key, level, confidence, reason in infer_handbook_hits(entry):
        _insert_evidence_and_xp(
            db,
            user_id=user_id,
            user_name=user_name,
            signal_id=signal_id,
            ability_key=ability_key,
            evidence_type="codification",
            level=level,
            confidence=confidence,
            reason=reason,
            review_id=None,
            task_id=None,
            handbook_entry_id=entry.id,
            source_title=entry.title,
            week_label="",
            source_type="handbook_entry",
            raw_text=_normalize_text(f"{entry.title} {entry.summary} {' '.join(entry.tags)}"),
            context={
                "sourceLabel": "成长手册沉淀",
                "sourceObjectType": entry.sourceObjectType,
                "sourceObjectId": entry.sourceObjectId,
                "sourceTitle": entry.sourceTitle or entry.title,
                "clientId": entry.clientId,
                "clientName": entry.clientName,
                "eventLineId": entry.eventLineId,
                "eventLineName": entry.eventLineName,
                "projectStage": entry.projectStage,
                "businessCategory": entry.businessCategory,
                "evidenceRefs": list(entry.evidenceRefs),
                "contextSummary": entry.contextSummary,
                "sourceRoute": ["成长手册", entry.clientName, entry.eventLineName, entry.projectStage],
                "linkedContexts": [link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else [],
                "triggerNode": entry.projectFlowName or entry.projectStage or "经验沉淀",
            },
            created_at=timestamp,
        )
    rebuild_learning_recommendations(db, user_id=user_id, user_name=user_name, week_label="", created_at=timestamp)


def backfill_handbook_entries(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    entries: list[HandbookEntryRecord],
    created_at: str | None = None,
) -> None:
    for entry in entries:
        ingest_handbook_codification(db, user_id=user_id, user_name=user_name, entry=entry, created_at=created_at)


def _build_recommendation_record(db, row) -> LearningRecommendationRecord:
    content = LearningContentItemRecord(
        id=str(row["content_item_id"]),
        contentType=str(row["content_type"]),  # type: ignore[arg-type]
        abilityKey=str(row["ability_key"]),  # type: ignore[arg-type]
        title=str(row["title"]),
        summary=str(row["summary"]),
        body=str(row["body"]),
        practiceTask=str(row["practice_task"] or ""),
        acceptanceCriteria=from_json(row["acceptance_criteria_json"], []),  # type: ignore[arg-type]
        sourceKind=str(row["source_kind"] or "system_rule"),
        sourceRefId=str(row["source_ref_id"]) if row["source_ref_id"] else None,
        status=str(row["content_status"] or "active"),
        createdAt=str(row["content_created_at"]),
        updatedAt=str(row["content_updated_at"]),
    )
    profile_map = _fetch_profile_map(db)
    profile = profile_map.get(str(row["ability_key"]))
    linked_contexts = _context_links_from_context({"linkedContexts": from_json(row["linked_contexts_json"], [])})
    return LearningRecommendationRecord(
        id=str(row["id"]),
        userId=str(row["user_id"]),
        userName=str(row["user_name"] or ""),
        abilityKey=str(row["ability_key"]),  # type: ignore[arg-type]
        abilityLabel=profile.label if profile else str(row["ability_key"]),
        contentItemId=content.id,
        contentType=content.contentType,
        title=content.title,
        summary=content.summary,
        body=content.body,
        practiceTask=content.practiceTask,
        reason=str(row["reason"] or ""),
        linkedTaskId=str(row["linked_task_id"]) if row["linked_task_id"] else None,
        clientId=str(row["client_id"]) if row["client_id"] else None,
        clientName=str(row["client_name"]) if row["client_name"] else None,
        eventLineId=str(row["event_line_id"]) if row["event_line_id"] else None,
        eventLineName=str(row["event_line_name"]) if row["event_line_name"] else None,
        projectStage=str(row["project_stage"]) if row["project_stage"] else None,
        triggerNode=str(row["trigger_node"]) if row["trigger_node"] else None,
        whyNow=str(row["why_now"] or ""),
        linkedContexts=linked_contexts,
        priority=str(row["priority"] or "normal"),  # type: ignore[arg-type]
        status=str(row["status"] or "active"),  # type: ignore[arg-type]
        acceptedTaskId=str(row["accepted_task_id"]) if row["accepted_task_id"] else None,
        dismissedReason=str(row["dismissed_reason"]) if row["dismissed_reason"] else None,
        dedupeKey=str(row["dedupe_key"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def rebuild_learning_recommendations(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    week_label: str,
    created_at: str | None = None,
) -> None:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    db.execute("DELETE FROM learning_recommendations WHERE user_id = ? AND status = 'active'", (user_id,))

    totals = {str(row["ability_key"]): int(row["xp"] or 0) for row in db.fetchall(
        """
        SELECT ability_key, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
        FROM xp_ledger
        WHERE user_id = ? AND reversed_at IS NULL
        GROUP BY ability_key
        """,
        (user_id,),
    )}
    recent_evidence = db.fetchall(
        """
        SELECT
            e.ability_key,
            e.reason,
            e.created_at,
            s.source_type,
            s.source_id,
            s.task_id,
            s.context_json
        FROM growth_evidence_records
        e
        INNER JOIN growth_signal_events s ON s.id = e.signal_id
        WHERE e.user_id = ?
        ORDER BY e.created_at DESC
        LIMIT 12
        """,
        (user_id,),
    )
    blocker_keys = {
        str(row["ability_key"])
        for row in recent_evidence
        if any(token in str(row["reason"] or "") for token in ("阻碍", "支持", "边界", "返工", "风险", "卡点"))
    }

    candidates = sorted(
        ABILITY_ORDER,
        key=lambda key: (0 if key in blocker_keys else 1, totals.get(key, 0), ABILITY_ORDER.index(key)),
    )
    recent_cutoff = (datetime.fromisoformat(timestamp) - timedelta(days=14)).isoformat(timespec="seconds")
    for ability_key in candidates[:3]:
        preferred_type = "correction_card" if ability_key in blocker_keys else "practice_card"
        content_row = db.fetchone(
            """
            SELECT *
            FROM learning_content_items
            WHERE ability_key = ? AND status = 'active'
            ORDER BY CASE content_type
                WHEN ? THEN 0
                WHEN 'practice_card' THEN 1
                WHEN 'method_card' THEN 2
                ELSE 3
            END, created_at ASC
            LIMIT 1
            """,
            (ability_key, preferred_type),
        )
        if not content_row:
            continue
        dedupe_key = f"{ability_key}:{content_row['id']}"
        existing_recent = db.fetchone(
            """
            SELECT 1
            FROM learning_recommendations
            WHERE user_id = ? AND dedupe_key = ? AND status IN ('accepted', 'dismissed') AND updated_at >= ?
            LIMIT 1
            """,
            (user_id, dedupe_key, recent_cutoff),
        )
        if existing_recent:
            continue
        recent_reason_row = next((row for row in recent_evidence if str(row["ability_key"]) == ability_key), None)
        profile = ABILITY_DEFAULTS[ability_key]
        context = from_json(recent_reason_row["context_json"], {}) if recent_reason_row else {}
        reason = (
            f"最近在{profile['label']}上暴露了明显卡点：{recent_reason_row['reason']}"
            if recent_reason_row and str(recent_reason_row["reason"]).strip()
            else f"当前 {profile['label']} 的成长信号偏少，建议补一条针对性练习。"
        )
        why_now = (
            f"当前任务/事件线正处在 {_safe_context_value(context, 'projectStage') or _safe_context_value(context, 'triggerNode') or '关键推进节点'}，如果不补这一步，容易继续拖慢闭环。"
            if context
            else f"当前最容易拖后腿的是 {profile['label']}，建议趁本周任务推进时补一条动作。"
        )
        priority = "high" if ability_key in blocker_keys else "normal"
        linked_contexts = context.get("linkedContexts") if isinstance(context.get("linkedContexts"), list) else []
        db.execute(
            """
            INSERT INTO learning_recommendations(
                id, user_id, user_name, ability_key, content_item_id, trigger_source_type, trigger_source_id, reason, linked_task_id, client_id, client_name, event_line_id, event_line_name, project_stage, trigger_node, why_now, linked_contexts_json, priority, status, accepted_task_id, dismissed_reason, dedupe_key, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL, NULL, ?, ?, ?)
            """,
            (
                _new_id("rec"),
                user_id,
                user_name,
                ability_key,
                str(content_row["id"]),
                str(recent_reason_row["source_type"]) if recent_reason_row else "growth_engine",
                str(recent_reason_row["source_id"]) if recent_reason_row else ability_key,
                reason,
                str(recent_reason_row["task_id"]) if recent_reason_row and recent_reason_row["task_id"] else (_safe_context_value(context, "taskId") or None),
                _safe_context_value(context, "clientId"),
                _safe_context_value(context, "clientName"),
                _safe_context_value(context, "eventLineId"),
                _safe_context_value(context, "eventLineName"),
                _safe_context_value(context, "projectStage"),
                _safe_context_value(context, "triggerNode"),
                why_now,
                to_json(linked_contexts),
                priority,
                dedupe_key,
                timestamp,
                timestamp,
            ),
        )


def list_learning_recommendations(db: Database, user_id: str) -> list[LearningRecommendationRecord]:
    ensure_growth_catalog(db)
    rows = db.fetchall(
        """
        SELECT
            r.*,
            c.content_type,
            c.title,
            c.summary,
            c.body,
            c.practice_task,
            c.acceptance_criteria_json,
            c.source_kind,
            c.source_ref_id,
            c.status AS content_status,
            c.created_at AS content_created_at,
            c.updated_at AS content_updated_at
        FROM learning_recommendations r
        INNER JOIN learning_content_items c ON c.id = r.content_item_id
        WHERE r.user_id = ? AND r.status = 'active'
        ORDER BY CASE r.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, r.created_at DESC
        LIMIT 4
        """,
        (user_id,),
    )
    return [_build_recommendation_record(db, row) for row in rows]


def mark_recommendation_accepted(db: Database, recommendation_id: str, task_id: str, updated_at: str | None = None) -> LearningRecommendationRecord | None:
    timestamp = updated_at or _now_iso()
    row = db.fetchone("SELECT * FROM learning_recommendations WHERE id = ?", (recommendation_id,))
    if not row:
        return None
    db.execute(
        """
        UPDATE learning_recommendations
        SET status = 'accepted', accepted_task_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (task_id, timestamp, recommendation_id),
    )
    updated_row = db.fetchone(
        """
        SELECT
            r.*,
            c.content_type,
            c.title,
            c.summary,
            c.body,
            c.practice_task,
            c.acceptance_criteria_json,
            c.source_kind,
            c.source_ref_id,
            c.status AS content_status,
            c.created_at AS content_created_at,
            c.updated_at AS content_updated_at
        FROM learning_recommendations r
        INNER JOIN learning_content_items c ON c.id = r.content_item_id
        WHERE r.id = ?
        """,
        (recommendation_id,),
    )
    return _build_recommendation_record(db, updated_row) if updated_row else None


def mark_recommendation_dismissed(db: Database, recommendation_id: str, reason: str = "", updated_at: str | None = None) -> LearningRecommendationRecord | None:
    timestamp = updated_at or _now_iso()
    row = db.fetchone("SELECT * FROM learning_recommendations WHERE id = ?", (recommendation_id,))
    if not row:
        return None
    db.execute(
        """
        UPDATE learning_recommendations
        SET status = 'dismissed', dismissed_reason = ?, updated_at = ?
        WHERE id = ?
        """,
        (reason.strip(), timestamp, recommendation_id),
    )
    updated_row = db.fetchone(
        """
        SELECT
            r.*,
            c.content_type,
            c.title,
            c.summary,
            c.body,
            c.practice_task,
            c.acceptance_criteria_json,
            c.source_kind,
            c.source_ref_id,
            c.status AS content_status,
            c.created_at AS content_created_at,
            c.updated_at AS content_updated_at
        FROM learning_recommendations r
        INNER JOIN learning_content_items c ON c.id = r.content_item_id
        WHERE r.id = ?
        """,
        (recommendation_id,),
    )
    return _build_recommendation_record(db, updated_row) if updated_row else None


def mark_handbook_entry_reused(
    db: Database,
    *,
    user_id: str,
    user_name: str,
    entry: HandbookEntryRecord,
    week_label: str,
    source_type: str,
    source_id: str,
    source_label: str = "",
    context_summary: str = "",
    linked_contexts: list[dict[str, object]] | None = None,
    note: str = "",
    created_at: str | None = None,
) -> GrowthValidationActionResponse:
    ensure_growth_catalog(db, created_at)
    timestamp = created_at or _now_iso()
    normalized_source_id = _normalize_text(source_id) or week_label or timestamp[:10]
    reuse_text = _normalize_text(
        " ".join(
            part
            for part in (
                entry.title,
                entry.summary,
                " ".join(entry.tags),
                note.strip(),
                "被复用 团队继续沿用这条方法 模板 规则",
            )
            if part
        )
    )
    dedupe_key = f"handbook_reuse:{entry.id}:{source_type}:{normalized_source_id}"
    existing_signal = db.fetchone("SELECT id FROM growth_signal_events WHERE dedupe_key = ?", (dedupe_key,))
    if existing_signal:
        existing_rows = db.fetchall(
            """
            SELECT validation_state
            FROM growth_evidence_records
            WHERE signal_id = ?
            ORDER BY created_at DESC
            """,
            (str(existing_signal["id"]),),
        )
        validation_state: GrowthValidationState = "institutionalized"
        if existing_rows:
            validation_state = max(
                (str(row["validation_state"] or "candidate") for row in existing_rows),
                key=lambda item: VALIDATION_STATE_ORDER[item],  # type: ignore[index]
            )
        return GrowthValidationActionResponse(
            entryId=entry.id,
            gainedXp=0,
            createdEntries=len(existing_rows),
            validationState=validation_state,
            duplicate=True,
            sourceId=normalized_source_id,
            createdAt=timestamp,
        )

    signal_id = _insert_signal(
        db,
        user_id=user_id,
        user_name=user_name,
        source_type="handbook_reuse",
        source_id=f"{entry.id}:{normalized_source_id}",
        review_id=None,
        task_id=None,
        week_label=week_label,
        raw_text=reuse_text,
        context={
            "sourceLabel": "成长手册复用",
            "handbookEntryId": entry.id,
            "entryTitle": entry.title,
            "validationSourceType": source_type,
            "validationSourceId": normalized_source_id,
            "sourceObjectType": entry.sourceObjectType,
            "sourceObjectId": entry.sourceObjectId,
            "sourceTitle": entry.sourceTitle or entry.title,
            "clientId": entry.clientId,
            "clientName": entry.clientName,
            "eventLineId": entry.eventLineId,
            "eventLineName": entry.eventLineName,
            "projectStage": entry.projectStage,
            "businessCategory": entry.businessCategory,
            "evidenceRefs": list(entry.evidenceRefs),
            "contextSummary": context_summary.strip() or entry.contextSummary or _derive_context_summary(
                client_name=entry.clientName,
                event_line_name=entry.eventLineName,
                project_stage=entry.projectStage,
                business_category=entry.businessCategory,
                source_title=entry.title,
            ),
            "sourceRoute": ["成长手册复用", entry.clientName, entry.eventLineName, entry.projectStage],
            "linkedContexts": linked_contexts if linked_contexts is not None else ([link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else []),
            "note": note.strip(),
            "sourceLabel": source_label.strip(),
            "triggerNode": entry.projectFlowName or entry.projectStage or "方法复用",
        },
        dedupe_key=dedupe_key,
        created_at=timestamp,
    )

    gained_xp = 0
    created_entries = 0
    final_state: GrowthValidationState = "candidate"
    for ability_key, level, confidence, reason in infer_handbook_hits(entry):
        evidence_id, total_xp, validation_state = _insert_evidence_and_xp(
            db,
            user_id=user_id,
            user_name=user_name,
            signal_id=signal_id,
            ability_key=ability_key,
            evidence_type="reuse",
            level=level,
            confidence=confidence,
            reason=f"{reason}，且本周已被继续复用",
            review_id=None,
            task_id=None,
            handbook_entry_id=entry.id,
            source_title=entry.title,
            week_label=week_label,
            source_type="handbook_entry",
            raw_text=reuse_text,
            context={
                "sourceLabel": "成长手册复用",
                "handbookEntryId": entry.id,
                "sourceObjectType": entry.sourceObjectType,
                "sourceObjectId": entry.sourceObjectId,
                "sourceTitle": entry.sourceTitle or entry.title,
                "clientId": entry.clientId,
                "clientName": entry.clientName,
                "eventLineId": entry.eventLineId,
                "eventLineName": entry.eventLineName,
                "projectStage": entry.projectStage,
                "businessCategory": entry.businessCategory,
                "evidenceRefs": list(entry.evidenceRefs),
                "contextSummary": context_summary.strip() or entry.contextSummary,
                "sourceRoute": ["成长手册复用", entry.clientName, entry.eventLineName, entry.projectStage],
                "linkedContexts": linked_contexts if linked_contexts is not None else ([link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else []),
                "sourceLabel": source_label.strip(),
                "triggerNode": entry.projectFlowName or entry.projectStage or "方法复用",
            },
            created_at=timestamp,
        )
        _record_validation_event(
            db,
            user_id=user_id,
            evidence_id=evidence_id,
            event_type="handbook_reused",
            actor_id=user_id,
            actor_name=user_name,
            source_type=source_type,
            source_id=normalized_source_id,
            detail={
                "entryId": entry.id,
                "entryTitle": entry.title,
                "note": note.strip(),
                "sourceLabel": source_label.strip(),
                "contextSummary": context_summary.strip(),
                "linkedContexts": linked_contexts if linked_contexts is not None else ([link.model_dump() for link in entry.linkedContexts] if entry.linkedContexts else []),
            },
            created_at=timestamp,
        )
        gained_xp += total_xp
        created_entries += 1
        final_state = _max_validation_state(final_state, validation_state)

    db.execute(
        """
        UPDATE handbook_entries
        SET reuse_count = COALESCE(reuse_count, 0) + 1,
            last_reused_at = ?
        WHERE id = ?
        """,
        (timestamp, entry.id),
    )

    # Award reuse XP to the original author if different from the current user
    author_row = db.fetchone(
        "SELECT author_user_id, author_user_name FROM handbook_entries WHERE id = ?",
        (entry.id,),
    )
    original_author_id = str(author_row["author_user_id"] or "") if author_row else ""
    original_author_name = str(author_row["author_user_name"] or "") if author_row else ""
    if original_author_id and original_author_id != user_id:
        for ability_key, level, confidence, reason in infer_handbook_hits(entry):
            _insert_evidence_and_xp(
                db,
                user_id=original_author_id,
                user_name=original_author_name,
                signal_id=signal_id,
                ability_key=ability_key,
                evidence_type="reuse",
                level=level,
                confidence=confidence,
                reason=f"{reason}，方法卡被 {user_name} 复用",
                review_id=None,
                task_id=None,
                handbook_entry_id=entry.id,
                source_title=entry.title,
                week_label=week_label,
                source_type="handbook_entry",
                raw_text=reuse_text,
                context={
                    "sourceLabel": "方法卡被他人复用",
                    "handbookEntryId": entry.id,
                    "reusedBy": user_name,
                    "reusedByUserId": user_id,
                },
                created_at=timestamp,
            )

    rebuild_learning_recommendations(db, user_id=user_id, user_name=user_name, week_label=week_label, created_at=timestamp)
    return GrowthValidationActionResponse(
        entryId=entry.id,
        gainedXp=gained_xp,
        createdEntries=created_entries,
        validationState=final_state,
        duplicate=False,
        sourceId=normalized_source_id,
        createdAt=timestamp,
    )


def _merged_growth_context(row) -> dict[str, object]:
    signal_context = from_json(row["context_json"], {})
    metadata = from_json(row["metadata_json"], {})
    merged: dict[str, object] = {}
    if isinstance(signal_context, dict):
        merged.update(signal_context)
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key not in merged or merged[key] in (None, "", [], {}):
                merged[key] = value
    return merged


def _build_ledger_entry(profile_map: dict[str, GrowthAbilityProfileRecord], row) -> XpLedgerEntryRecord:
    context = _merged_growth_context(row)
    ability_label = profile_map.get(str(row["ability_key"])).label if profile_map.get(str(row["ability_key"])) else str(row["ability_key"])
    source_title = (
        _safe_context_value(context, "sourceTitle")
        or _safe_context_value(context, "taskTitle")
        or _safe_context_value(context, "meetingTitle")
        or _safe_context_value(context, "entryTitle")
        or _safe_context_value(context, "sourceLabel")
    )
    return XpLedgerEntryRecord(
        id=str(row["id"]),
        userId=str(row["user_id"]),
        userName=str(row["user_name"] or ""),
        abilityKey=str(row["ability_key"]),  # type: ignore[arg-type]
        abilityLabel=ability_label,
        evidenceId=str(row["evidence_id"]),
        xpType=str(row["xp_type"]),  # type: ignore[arg-type]
        delta=int(row["delta"] or row["total_xp"] or 0),
        baseXp=int(row["base_xp"] or 0),
        premiumRate=float(row["premium_rate"] or 0),
        premiumXp=int(row["premium_xp"] or 0),
        totalXp=int(row["total_xp"] or row["delta"] or 0),
        reason=str(row["reason"] or ""),
        sourceType=str(row["source_type"] or ""),
        sourceId=str(row["source_id"] or ""),
        sourceTitle=source_title or None,
        handbookEntryId=str(row["handbook_entry_id"]) if row["handbook_entry_id"] else _safe_context_value(context, "handbookEntryId"),
        taskId=str(row["task_id"]) if row["task_id"] else _safe_context_value(context, "taskId"),
        meetingId=_safe_context_value(context, "meetingId"),
        reviewId=str(row["review_id"]) if row["review_id"] else _safe_context_value(context, "reviewId"),
        clientId=_safe_context_value(context, "clientId"),
        clientName=_safe_context_value(context, "clientName"),
        eventLineId=_safe_context_value(context, "eventLineId"),
        eventLineName=_safe_context_value(context, "eventLineName"),
        businessCategory=_safe_context_value(context, "businessCategory"),
        projectStage=_safe_context_value(context, "projectStage"),
        sourceRoute=_build_source_route(context),
        evidenceRefs=_safe_context_list(context, "evidenceRefs"),
        contextSummary=_safe_context_value(context, "contextSummary") or "",
        strategicLink=_safe_context_value(context, "strategicLink"),
        linkedContexts=_context_links_from_context(context),
        contributionTags=from_json(row["contribution_tags_json"], []),  # type: ignore[arg-type]
        validationState=str(row["validation_state"] or "candidate"),  # type: ignore[arg-type]
        orgContributionScore=int(row["org_contribution_score"] or 0),
        weekLabel=str(row["week_label"] or ""),
        createdAt=str(row["created_at"]),
        reversedAt=str(row["reversed_at"]) if row["reversed_at"] else None,
    )


def _build_source_coverage(db: Database, user_id: str) -> GrowthSourceCoverageRecord:
    rows = db.fetchall(
        """
        SELECT source_type, context_json
        FROM growth_signal_events
        WHERE user_id = ?
        """,
        (user_id,),
    )
    client_ids: set[str] = set()
    event_line_ids: set[str] = set()
    coverage = GrowthSourceCoverageRecord()
    for row in rows:
        source_type = str(row["source_type"] or "")
        context = from_json(row["context_json"], {})
        if source_type in TASK_CANDIDATE_SOURCE_TYPES:
            coverage.taskSignals += 1
        elif source_type in MEETING_SOURCE_TYPES:
            coverage.meetingSignals += 1
        elif source_type in STRATEGIC_SOURCE_TYPES:
            coverage.strategicSignals += 1
        elif source_type.startswith("weekly_review"):
            coverage.reviewSignals += 1
        elif source_type.startswith("handbook"):
            coverage.handbookSignals += 1
        if isinstance(context, dict):
            client_id = _safe_context_value(context, "clientId")
            event_line_id = _safe_context_value(context, "eventLineId")
            if client_id:
                client_ids.add(client_id)
            if event_line_id:
                event_line_ids.add(event_line_id)
    coverage.clientCount = len(client_ids)
    coverage.eventLineCount = len(event_line_ids)
    return coverage


def _aggregate_growth_highlights(
    entries: list[XpLedgerEntryRecord],
    *,
    mode: str,
    limit: int = 4,
) -> list[GrowthProjectHighlightRecord]:
    buckets: dict[str, dict[str, object]] = {}
    for entry in entries:
        if mode == "client":
            bucket_id = entry.clientId or ""
            label = entry.clientName or ""
            context_link = next((link for link in entry.linkedContexts if link.objectType == "client"), None)
        elif mode == "event_line":
            bucket_id = entry.eventLineId or ""
            label = entry.eventLineName or ""
            context_link = next((link for link in entry.linkedContexts if link.objectType == "event_line"), None)
        else:
            strategic_link = entry.strategicLink or ""
            bucket_id = strategic_link
            label = strategic_link
            context_link = next((link for link in entry.linkedContexts if link.objectType in {"meeting", "client"}), None)
        if not bucket_id or not label:
            continue
        bucket = buckets.setdefault(
            bucket_id,
            {
                "id": bucket_id,
                "label": label,
                "type": mode,
                "weeklyXp": 0,
                "entryCount": 0,
                "summary": "",
                "abilityKeys": [],
                "contexts": [],
            },
        )
        bucket["weeklyXp"] = int(bucket["weeklyXp"]) + entry.totalXp
        bucket["entryCount"] = int(bucket["entryCount"]) + 1
        if entry.reason and not bucket["summary"]:
            bucket["summary"] = entry.reason
        ability_keys = set(bucket["abilityKeys"])
        ability_keys.add(entry.abilityKey)
        bucket["abilityKeys"] = list(ability_keys)
        contexts: list[GrowthContextLinkRecord] = bucket["contexts"]
        if context_link and not any(link.objectId == context_link.objectId and link.objectType == context_link.objectType for link in contexts):
            contexts.append(context_link)
    ordered = sorted(buckets.values(), key=lambda item: (-int(item["weeklyXp"]), -int(item["entryCount"]), str(item["label"])))
    return [
        GrowthProjectHighlightRecord(
            id=str(item["id"]),
            label=str(item["label"]),
            type=str(item["type"]),
            weeklyXp=int(item["weeklyXp"]),
            entryCount=int(item["entryCount"]),
            summary=str(item["summary"] or ""),
            abilityKeys=list(item["abilityKeys"]),  # type: ignore[arg-type]
            contexts=list(item["contexts"]),
        )
        for item in ordered[:limit]
    ]


def _build_pending_capture_record(row) -> GrowthPendingCaptureRecord | None:
    context = from_json(row["context_json"], {})
    if not isinstance(context, dict):
        return None
    # Prefer AI-distilled insight quote if available
    insight_quote = _safe_context_value(context, "insightQuote")
    raw_title = _safe_context_value(context, "taskTitle") or _safe_context_value(context, "sourceLabel") or str(row["source_id"])
    if not raw_title and not insight_quote:
        return None
    # If we have an AI-distilled quote, use it as title (the display text);
    # keep raw_title available via summary for source context
    if insight_quote:
        title = insight_quote
        summary = _safe_context_value(context, "insightSourceLabel") or _safe_context_value(context, "contextSummary") or ""
    else:
        title = raw_title
        summary = _safe_context_value(context, "contextSummary") or ""
    return GrowthPendingCaptureRecord(
        id=str(row["id"]),
        sourceType=str(row["source_type"]),
        sourceId=str(row["source_id"]),
        status=str(row["capture_status"] or "open"),  # type: ignore[arg-type]
        title=title,
        summary=summary,
        clientId=_safe_context_value(context, "clientId"),
        clientName=_safe_context_value(context, "clientName"),
        eventLineId=_safe_context_value(context, "eventLineId"),
        eventLineName=_safe_context_value(context, "eventLineName"),
        projectStage=_safe_context_value(context, "projectStage"),
        nextActionText=_safe_context_value(context, "nextAction") or "",
        missingReasons=_safe_context_list(context, "missingReasons"),
        abilityKeys=[ability_key for ability_key, *_ in _infer_general_hits(str(row["raw_text"] or ""), source_type=str(row["source_type"]))],  # type: ignore[list-item]
        linkedContexts=_context_links_from_context(context),
        stateReason=str(row["capture_reason"] or ""),
        promotedHandbookEntryId=str(row["promoted_handbook_entry_id"]) if row["promoted_handbook_entry_id"] else None,
        updatedAt=str(row["capture_updated_at"] or row["created_at"] or ""),
    )


def get_pending_capture(db: Database, user_id: str, capture_id: str) -> GrowthPendingCaptureRecord | None:
    row = db.fetchone(
        """
        SELECT
            s.*,
            cs.status AS capture_status,
            cs.reason AS capture_reason,
            cs.promoted_handbook_entry_id,
            cs.updated_at AS capture_updated_at
        FROM growth_signal_events s
        LEFT JOIN growth_capture_states cs
            ON cs.signal_id = s.id AND cs.user_id = s.user_id
        WHERE s.user_id = ?
          AND s.id = ?
          AND s.source_type IN ('task_context_candidate', 'task_attachment_candidate')
        """,
        (user_id, capture_id),
    )
    if not row:
        return None
    return _build_pending_capture_record(row)


def update_pending_capture_state(
    db: Database,
    *,
    user_id: str,
    capture_id: str,
    status: GrowthPendingCaptureState,
    reason: str = "",
    handbook_entry_id: str | None = None,
    created_at: str | None = None,
) -> GrowthPendingCaptureRecord | None:
    timestamp = created_at or _now_iso()
    row = db.fetchone(
        """
        SELECT id
        FROM growth_signal_events
        WHERE user_id = ?
          AND id = ?
          AND source_type IN ('task_context_candidate', 'task_attachment_candidate', 'review_insight_pending')
        """,
        (user_id, capture_id),
    )
    # Fallback: try with the cloud session user_id if operator ID didn't match
    if not row:
        row = db.fetchone(
            """
            SELECT id
            FROM growth_signal_events
            WHERE id = ?
              AND source_type IN ('task_context_candidate', 'task_attachment_candidate', 'review_insight_pending')
            """,
            (capture_id,),
        )
    if not row:
        return None
    existing = db.fetchone(
        "SELECT id, user_id FROM growth_capture_states WHERE signal_id = ?",
        (capture_id,),
    )
    normalized_reason = reason.strip()
    actual_user_id = str(existing["user_id"]) if existing else user_id
    if existing:
        db.execute(
            """
            UPDATE growth_capture_states
            SET status = ?,
                reason = ?,
                promoted_handbook_entry_id = ?,
                updated_at = ?
            WHERE signal_id = ?
            """,
            (status, normalized_reason, handbook_entry_id, timestamp, capture_id),
        )
    else:
        db.execute(
            """
            INSERT INTO growth_capture_states(
                id, user_id, signal_id, status, reason, promoted_handbook_entry_id, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (_new_id("gcs"), user_id, capture_id, status, normalized_reason, handbook_entry_id, timestamp, timestamp),
        )
    return get_pending_capture(db, user_id, capture_id)


def _list_pending_captures(db: Database, user_id: str, *, limit: int = 6) -> list[GrowthPendingCaptureRecord]:
    rows = db.fetchall(
        """
        SELECT
            s.*,
            cs.status AS capture_status,
            cs.reason AS capture_reason,
            cs.promoted_handbook_entry_id,
            cs.updated_at AS capture_updated_at
        FROM growth_signal_events s
        LEFT JOIN growth_evidence_records e ON e.signal_id = s.id
        LEFT JOIN growth_capture_states cs
            ON cs.signal_id = s.id AND cs.user_id = s.user_id
        WHERE s.user_id = ? AND e.id IS NULL AND s.source_type IN ('task_context_candidate', 'task_attachment_candidate', 'review_insight_pending')
          AND COALESCE(cs.status, 'open') = 'open'
        ORDER BY s.created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    captures: list[GrowthPendingCaptureRecord] = []
    for row in rows:
        record = _build_pending_capture_record(row)
        if record:
            captures.append(record)
    return captures


def _build_focus_actions(recommendations: list[LearningRecommendationRecord]) -> list[GrowthFocusActionRecord]:
    return [
        GrowthFocusActionRecord(
            id=item.id,
            title=item.title,
            summary=item.summary,
            whyNow=item.whyNow or item.reason,
            linkedTaskId=item.linkedTaskId,
            clientId=item.clientId,
            clientName=item.clientName,
            eventLineId=item.eventLineId,
            eventLineName=item.eventLineName,
            projectStage=item.projectStage,
            triggerNode=item.triggerNode,
            linkedContexts=item.linkedContexts,
        )
        for item in recommendations[:3]
    ]


def _build_ability_gaps(
    ability_scores: list[GrowthAbilityScoreRecord],
    recommendations: list[LearningRecommendationRecord],
    pending_captures: list[GrowthPendingCaptureRecord],
    project_highlights: list[GrowthProjectHighlightRecord],
    event_line_highlights: list[GrowthProjectHighlightRecord],
    strategic_highlights: list[GrowthProjectHighlightRecord],
) -> list[GrowthAbilityGapRecord]:
    score_map = {item.abilityKey: item for item in ability_scores}
    candidates: dict[str, GrowthAbilityGapRecord] = {}

    def push_candidate(
        ability_key: str,
        *,
        required_score: int,
        reason: str,
        source_label: str,
        source_type: str,
        source_id: str,
    ) -> None:
        current = score_map.get(ability_key)
        if not current:
            return
        gap = max(0, required_score - current.currentScore)
        if gap <= 0:
            return
        existing = candidates.get(ability_key)
        candidate = GrowthAbilityGapRecord(
            abilityKey=ability_key,  # type: ignore[arg-type]
            label=current.label,
            currentScore=current.currentScore,
            requiredScore=required_score,
            gap=gap,
            reason=reason,
            sourceLabel=source_label,
            sourceType=source_type,
            sourceId=source_id,
        )
        if existing is None or candidate.gap > existing.gap or (candidate.gap == existing.gap and candidate.requiredScore > existing.requiredScore):
            candidates[ability_key] = candidate

    for recommendation in recommendations:
        push_candidate(
            recommendation.abilityKey,
            required_score=72 if recommendation.priority == "high" else 62,
            reason=recommendation.whyNow or recommendation.reason,
            source_label=recommendation.eventLineName or recommendation.clientName or recommendation.triggerNode or recommendation.title or "",
            source_type="event_line" if recommendation.eventLineId else "client" if recommendation.clientId else "recommendation",
            source_id=recommendation.eventLineId or recommendation.clientId or recommendation.id,
        )
    for capture in pending_captures:
        source_context = next(
            (
                context
                for context in capture.linkedContexts
                if context.objectType in {"task", "event_line", "client", "project_module", "project_flow", "strategic_focus"}
            ),
            None,
        )
        source_type = source_context.objectType if source_context else "capture"
        source_id = source_context.objectId if source_context else capture.id
        source_label = source_context.label if source_context else capture.eventLineName or capture.clientName or capture.title
        reason = "；".join(capture.missingReasons[:2]) or capture.summary or capture.nextActionText or "当前这条成长候选还缺正式闭环"
        for ability_key in capture.abilityKeys[:3]:
            push_candidate(
                ability_key,
                required_score=70 if capture.eventLineId or capture.projectStage else 64,
                reason=reason,
                source_label=source_label or "",
                source_type=source_type,
                source_id=source_id,
            )

    def push_highlights(
        highlights: list[GrowthProjectHighlightRecord],
        *,
        default_type: str,
        required_score: int,
        reason_prefix: str,
    ) -> None:
        for item in highlights:
            source_context = next(
                (
                    context
                    for context in item.contexts
                    if context.objectType in {"client", "event_line", "strategic_focus", "project_module", "project_flow", "task"}
                ),
                None,
            )
            source_type = source_context.objectType if source_context else default_type
            source_id = source_context.objectId if source_context else item.id
            source_label = source_context.label if source_context else item.label
            reason = item.summary or f"{reason_prefix}{item.label}"
            for ability_key in item.abilityKeys[:3]:
                push_candidate(
                    ability_key,
                    required_score=required_score,
                    reason=reason,
                    source_label=source_label,
                    source_type=source_type,
                    source_id=source_id,
                )

    push_highlights(project_highlights, default_type="client", required_score=66, reason_prefix="当前项目正在持续消耗这项能力：")
    push_highlights(event_line_highlights, default_type="event_line", required_score=70, reason_prefix="当前事件线正在持续要求这项能力：")
    push_highlights(strategic_highlights, default_type="strategic_focus", required_score=74, reason_prefix="当前战略线明确要求继续补强这项能力：")

    return sorted(candidates.values(), key=lambda item: (-item.gap, ABILITY_ORDER.index(item.abilityKey)))[:3]


def build_growth_ledger(db: Database, user_id: str, *, ability_key: str | None = None, week_label: str | None = None) -> GrowthLedgerResponse:
    ensure_growth_catalog(db)
    profile_map = _fetch_profile_map(db)
    clauses = ["l.user_id = ?", "l.reversed_at IS NULL"]
    params: list[object] = [user_id]
    if ability_key:
        clauses.append("l.ability_key = ?")
        params.append(ability_key)
    if week_label:
        clauses.append("l.week_label = ?")
        params.append(week_label)
    rows = db.fetchall(
        f"""
        SELECT
            l.*,
            e.reason,
            e.evidence_type,
            e.metadata_json,
            e.contribution_tags_json,
            e.validation_state,
            e.org_contribution_score,
            e.review_id,
            e.task_id,
            e.handbook_entry_id,
            s.source_type,
            s.source_id,
            s.context_json
        FROM xp_ledger l
        INNER JOIN growth_evidence_records e ON e.id = l.evidence_id
        INNER JOIN growth_signal_events s ON s.id = e.signal_id
        WHERE {' AND '.join(clauses)}
        ORDER BY l.created_at DESC
        LIMIT 80
        """,
        tuple(params),
    )
    return GrowthLedgerResponse(entries=[_build_ledger_entry(profile_map, row) for row in rows])


def build_growth_overview(db: Database, user_id: str, user_name: str, *, week_label: str = "") -> GrowthOverviewRecord:
    ensure_growth_catalog(db)
    profile_map = _fetch_profile_map(db)
    totals = {
        str(row["ability_key"]): int(row["xp"] or 0)
        for row in db.fetchall(
            """
            SELECT ability_key, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
            FROM xp_ledger
            WHERE user_id = ? AND reversed_at IS NULL
            GROUP BY ability_key
            """,
            (user_id,),
        )
    }
    weekly = {
        str(row["ability_key"]): int(row["xp"] or 0)
        for row in db.fetchall(
            """
            SELECT ability_key, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
            FROM xp_ledger
            WHERE user_id = ? AND reversed_at IS NULL AND week_label = ?
            GROUP BY ability_key
            """,
            (user_id, week_label),
        )
    } if week_label else {}
    weekly_row = db.fetchone(
        """
        SELECT
            SUM(COALESCE(NULLIF(base_xp, 0), CASE WHEN COALESCE(NULLIF(total_xp, 0), delta) > 0 THEN COALESCE(NULLIF(total_xp, 0), delta) ELSE 0 END)) AS base_xp,
            SUM(COALESCE(premium_xp, 0)) AS premium_xp,
            SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS total_xp
        FROM xp_ledger
        WHERE user_id = ? AND reversed_at IS NULL AND week_label = ?
        """,
        (user_id, week_label),
    ) if week_label else None

    recent_entries = build_growth_ledger(db, user_id).entries[:6]
    weekly_entries = build_growth_ledger(db, user_id, week_label=week_label).entries if week_label else recent_entries
    recommendations = list_learning_recommendations(db, user_id)
    pending_captures = _list_pending_captures(db, user_id)

    ability_scores: list[GrowthAbilityScoreRecord] = []
    total_xp = 0
    weekly_xp = 0
    for ability_key in ABILITY_ORDER:
        total = totals.get(ability_key, 0)
        total_xp += total
        week_delta = weekly.get(ability_key, 0)
        weekly_xp += week_delta
        stage, next_stage = _ability_stage(total)
        recent_evidence = next((item.reason for item in recent_entries if item.abilityKey == ability_key and item.reason.strip()), "")
        ability_scores.append(
            GrowthAbilityScoreRecord(
                abilityKey=ability_key,  # type: ignore[arg-type]
                label=profile_map[ability_key].label,
                currentScore=_current_score(total),
                previousScore=max(0, _current_score(max(0, total - week_delta))),
                totalXp=total,
                weeklyXp=week_delta,
                stage=stage,
                nextStage=next_stage,
                evidence=recent_evidence,
            )
        )

    overall_stage, _ = _ability_stage(total_xp)
    level = max(1, total_xp // 100 + 1)
    xp_to_next = 100 - (total_xp % 100) if total_xp % 100 else 100
    rank = _build_rank_record(total_xp)
    project_highlights = _aggregate_growth_highlights(weekly_entries, mode="client")
    event_line_highlights = _aggregate_growth_highlights(weekly_entries, mode="event_line")
    strategic_highlights = _aggregate_growth_highlights(
        [entry for entry in weekly_entries if entry.strategicLink],
        mode="strategic",
        limit=3,
    )
    return GrowthOverviewRecord(
        userId=user_id,
        userName=user_name,
        totalXp=total_xp,
        weeklyXp=weekly_xp,
        weeklyBaseXp=int(weekly_row["base_xp"] or 0) if weekly_row else 0,
        weeklyPremiumXp=int(weekly_row["premium_xp"] or 0) if weekly_row else 0,
        level=level,
        stageLabel=f"{overall_stage}期",
        xpToNext=xp_to_next,
        rank=rank,
        abilities=ability_scores,
        recentEntries=recent_entries,
        recommendations=recommendations,
        sourceCoverage=_build_source_coverage(db, user_id),
        projectGrowthHighlights=project_highlights,
        eventLineGrowthHighlights=event_line_highlights,
        strategicAlignmentHighlights=strategic_highlights,
        pendingCaptures=pending_captures,
        currentFocusActions=_build_focus_actions(recommendations),
        abilityGaps=_build_ability_gaps(ability_scores, recommendations, pending_captures, project_highlights, event_line_highlights, strategic_highlights),
        updatedAt=_now_iso(),
    )
