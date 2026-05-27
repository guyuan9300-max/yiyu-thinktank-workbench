from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
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
    GrowthAbilityTrendPointRecord,
    GrowthAbilityTrendRecord,
    GrowthBusinessCoverageItemRecord,
    GrowthBusinessCoverageRecord,
    GrowthCommitmentCumulativePointRecord,
    GrowthCommitmentItemRecord,
    GrowthCommitmentSummaryRecord,
    GrowthCommitmentTrendPointRecord,
    GrowthDailyActivityRecord,
    GrowthDailyActivityResponse,
    GrowthImpactCurvePointRecord,
    GrowthImpactRecord,
    GrowthLearningPickRecord,
    GrowthLearningRecord,
    GrowthPeerComparisonRecord,
    GrowthReviewDayPointRecord,
    GrowthReviewStreakRecord,
    GrowthReviewWeekPointRecord,
    GrowthSocialFeedbackRecord,
    GrowthWorkTypeRecord,
    GrowthWorkTypeSliceRecord,
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

# N1: role_tier → 能力维度集合 + 标签覆盖
# CEO 看到的 6 维不同：战略判断/对外影响/组织建设/危机决策/远见洞察/资源调配
# 后端 ability_key 内部还是用通用 6 维 (exec/collab/analyze/insight/risk/write)，
# 通过 ROLE_ABILITY_LABEL_OVERRIDE 在返回前对 label 重命名，前端无感切换
ROLE_ABILITY_LABEL_OVERRIDE: dict[str, dict[str, str]] = {
    "ceo": {
        "exec": "资源调配",
        "collab": "组织建设",
        "analyze": "战略判断",
        "insight": "远见洞察",
        "risk": "危机决策",
        "write": "对外影响",
    },
    "leader": {
        "exec": "团队推进",
        "collab": "跨组协调",
        "analyze": "项目研判",
        "insight": "需求洞察",
        "risk": "风险把控",
        "write": "总结输出",
    },
}


def _resolve_operator_row(db: Database, user_id: str):
    """系统里有多套 id 体系（operators.id 跟 xp_ledger.user_id 经常错位）。
    先按 id 查，再按 USER_NAME_ALIASES 配置的名字反查。"""
    try:
        row = db.fetchone("SELECT id, name, role, role_tier FROM operators WHERE id = ?", (user_id,))
        if row and (row["role"] or row["role_tier"]):
            return row
    except Exception:
        pass
    for alias in USER_NAME_ALIASES.get(user_id, ()):
        try:
            row = db.fetchone(
                "SELECT id, name, role, role_tier FROM operators WHERE name = ?", (alias,)
            )
            if row:
                return row
        except Exception:
            continue
    return None


def _resolve_user_role_tier(db: Database, user_id: str) -> str:
    row = _resolve_operator_row(db, user_id)
    if row and row["role_tier"]:
        return str(row["role_tier"])
    return "member"


def _apply_role_label_override(
    ability_scores: list[GrowthAbilityScoreRecord],
    role_tier: str,
) -> list[GrowthAbilityScoreRecord]:
    overrides = ROLE_ABILITY_LABEL_OVERRIDE.get(role_tier)
    if not overrides:
        return ability_scores
    return [
        ab.model_copy(update={"label": overrides.get(ab.abilityKey, ab.label)})
        for ab in ability_scores
    ]

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

ABILITY_STAGE_SCORE_RULES = [
    {"label": "见习", "minScore": 0},
    {"label": "上手", "minScore": 20},
    {"label": "稳态", "minScore": 40},
    {"label": "独立", "minScore": 60},
    {"label": "带动", "minScore": 80},
]

ABILITY_SCORE_HALF_SATURATION_XP = 300  # K4 调参：96→300，让能力分拉开区分度（XP=300 时 50 分；XP=900 时 75 分）

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
    score = _current_score(total_xp)
    stage = ABILITY_STAGE_SCORE_RULES[0]["label"]
    next_stage = ABILITY_STAGE_SCORE_RULES[-1]["label"]
    for index, rule in enumerate(ABILITY_STAGE_SCORE_RULES):
        if score >= int(rule["minScore"]):
            stage = str(rule["label"])
            next_stage = str(ABILITY_STAGE_SCORE_RULES[min(index + 1, len(ABILITY_STAGE_SCORE_RULES) - 1)]["label"])
    return stage, next_stage


def _current_score(total_xp: int) -> int:
    if total_xp <= 0:
        return 8
    # Use a saturating curve instead of a hard linear cap so mature abilities do not all
    # collapse to 100 once cumulative XP crosses an early milestone.
    normalized = (total_xp / (total_xp + ABILITY_SCORE_HALF_SATURATION_XP)) * 100
    return max(8, min(100, int(round(normalized))))


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


# ════════════════════════════════════════════════════════════════════════════
# K 系列改造 · 真实数据源驱动的能力分（替代 ledger 关键词扫描）
# ════════════════════════════════════════════════════════════════════════════
# 旧逻辑：xp_ledger 写入靠 _infer_general_hits 关键词扫描，且大量徽章解锁自动
# 送 XP 装填了能力分（exec 100% 来自 badge_unlock 等失真现象）。
#
# 新逻辑：直接从原始表按"入口 → 能力"配置矩阵聚合。该矩阵由用户产品视角确认：
# 「周复盘是分析主力 / 任务完成是执行主力 / 被复用是写作主力 / 承诺履约是执行 /
#   风险信号是风险 / 徽章自送 XP 排除」。
#
# 数据源限制：
#   - meetings 表无 owner_user_id ⇒ B4 暂时跳过（待数据中心补字段）
#   - commitments.committer 是名字字符串 ⇒ 用别名映射反查 user_id

# user_id → 该用户可能在系统里出现的别名（commitments.committer 这类字段用）
# 后续应该读 operators 表 + 用户自定义别名表
USER_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "user_guyuan": ("顾源源", "顾老师", "本机用户"),
}


def _resolve_user_aliases(db: Database, user_id: str) -> tuple[str, ...]:
    """获取该 user 的所有可能名字（用于按名字反查 commitments 等表）。"""
    aliases = set(USER_NAME_ALIASES.get(user_id, ()))
    try:
        row = db.fetchone("SELECT name FROM operators WHERE id = ?", (user_id,))
        if row and row["name"]:
            aliases.add(str(row["name"]))
    except Exception:
        pass
    return tuple(aliases) if aliases else (user_id,)


# 每个事件类型的 base XP（事件本身的"重量"）
# 用户写作 base 高（高质量原创），任务/操作 base 低（量大易刷分）
# K4 调参：原值全部减半，让 21 条手册不会单一来源就把分数顶到 85
SOURCE_BASE_XP: dict[str, float] = {
    "weekly_review_summary": 4.0,
    "weekly_review_task_note": 2.0,
    "handbook_entry": 3.0,
    "task_done": 0.5,
    "task_created": 0.2,
    "meeting_owned": 2.5,
    "handbook_reused": 4.0,
    "exp_wall_liked": 1.0,
    "exp_wall_saved": 2.5,
    "commitment_fulfilled": 3.0,
    "risk_signal_owned": 2.5,
    "document_owned": 1.0,
    "memory_owned_client": 0.5,
}


# 入口 × 能力维度 权重矩阵（K1：来自用户产品视角确认的参考答案）
# 缺省 = 0（不算）；3.0 = ✅✅ 主力；1.5 = ✅ 次要；0.5 = 🟡 弱信号
ABILITY_WEIGHTS_BY_SOURCE: dict[str, dict[str, float]] = {
    # ── A 类：用户原创写作 ──
    "weekly_review_summary": {
        "exec": 1.5, "collab": 1.5, "analyze": 3.0,
        "insight": 1.5, "risk": 1.5, "write": 1.5,
    },
    "weekly_review_task_note": {
        "exec": 3.0, "collab": 0.5, "analyze": 1.5,
        "insight": 0.5, "risk": 1.5, "write": 1.5,
    },
    "handbook_entry": {
        "exec": 0.5, "collab": 0.5, "analyze": 3.0,
        "insight": 3.0, "risk": 1.5, "write": 3.0,
    },
    # ── B 类：真实做事 ──
    "task_done": {
        "exec": 3.0, "risk": 0.5,
    },
    "task_created": {
        "exec": 1.5,
    },
    "meeting_owned": {
        "collab": 3.0,
    },
    # ── D 类：被组织看见 ──
    "handbook_reused": {
        "write": 3.0,
    },
    "exp_wall_liked": {
        "write": 3.0,
    },
    "exp_wall_saved": {
        "write": 3.0,
    },
    # ── E 类：数据中心 P0/P1 信号 ──
    "commitment_fulfilled": {
        "exec": 3.0,
    },
    "risk_signal_owned": {
        "risk": 3.0,
    },
    # ── F 类：用户上传/挂载（弱信号）──
    "document_owned": {
        "write": 0.5,
    },
    "memory_owned_client": {
        "insight": 0.5,
    },
}


@dataclass
class _SourceContribution:
    """一个"入口"对该用户能力分的贡献明细，用于 evidence 文本拼装。"""

    source_kind: str  # 即 SOURCE_BASE_XP / ABILITY_WEIGHTS_BY_SOURCE 的 key
    count: int  # 这一类事件的件数
    base_xp_per_unit: float
    total_base_xp: float  # = count × base_xp_per_unit
    sample_title: str = ""  # 最新一条的标题（给 evidence 用）


def _count_source_events(db: Database, user_id: str) -> dict[str, _SourceContribution]:
    """从所有原始表统计该用户每类事件的件数 + 抽样标题。"""

    contributions: dict[str, _SourceContribution] = {}
    aliases = _resolve_user_aliases(db, user_id)

    def _add(kind: str, count: int, sample_title: str = "") -> None:
        if count <= 0:
            return
        base = SOURCE_BASE_XP.get(kind, 0.0)
        contributions[kind] = _SourceContribution(
            source_kind=kind,
            count=count,
            base_xp_per_unit=base,
            total_base_xp=count * base,
            sample_title=sample_title,
        )

    # A1 · 周复盘 summary（取非空且长度 ≥ 30 字的）
    try:
        rows = db.fetchall(
            """
            SELECT id, week_label, length(summary) AS slen
            FROM weekly_reviews
            WHERE user_id = ? AND length(summary) >= 30
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        if rows:
            _add("weekly_review_summary", len(rows), f"{rows[0]['week_label']} 周复盘")
    except Exception:
        pass

    # A2 · 复盘任务项 note + structured_note
    try:
        rows = db.fetchall(
            """
            SELECT id, week_label, length(note) AS nlen
            FROM weekly_review_task_entries
            WHERE user_id = ?
              AND (length(note) >= 20 OR length(structured_note_json) >= 50)
            ORDER BY reviewed_at DESC
            """,
            (user_id,),
        )
        if rows:
            _add("weekly_review_task_note", len(rows), f"{rows[0]['week_label']} 任务复盘")
    except Exception:
        pass

    # A4 · 手册条目（作者 = user）
    try:
        rows = db.fetchall(
            """
            SELECT title, created_at
            FROM handbook_entries
            WHERE author_user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        if rows:
            _add("handbook_entry", len(rows), str(rows[0]["title"])[:50])
    except Exception:
        pass

    # B1 · 任务完成（status=done）
    try:
        rows = db.fetchall(
            """
            SELECT title, updated_at
            FROM tasks
            WHERE owner_id = ? AND status = 'done'
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )
        if rows:
            _add("task_done", len(rows), str(rows[0]["title"])[:50])
    except Exception:
        pass

    # B2 · 任务创建（不过滤 status，只计数量）
    try:
        row = db.fetchone(
            "SELECT COUNT(*) AS cnt FROM tasks WHERE creator_id = ?",
            (user_id,),
        )
        if row:
            _add("task_created", int(row["cnt"] or 0))
    except Exception:
        pass

    # B4 · 会议主持 —— 跳过（meetings 表无 owner 字段）

    # D1 · 手册被复用（按用户名下手册的累计 reuse_count）
    try:
        row = db.fetchone(
            """
            SELECT COALESCE(SUM(reuse_count), 0) AS total
            FROM handbook_entries
            WHERE author_user_id = ?
            """,
            (user_id,),
        )
        if row:
            _add("handbook_reused", int(row["total"] or 0))
    except Exception:
        pass

    # D2/D3 · 经验墙被点赞 / 收藏
    try:
        row = db.fetchone(
            """
            SELECT
              COALESCE(SUM(like_count), 0) AS likes,
              COALESCE(SUM(save_count), 0) AS saves
            FROM exp_wall_quotes
            WHERE author_user_id = ? AND status = 'active'
            """,
            (user_id,),
        )
        if row:
            _add("exp_wall_liked", int(row["likes"] or 0))
            _add("exp_wall_saved", int(row["saves"] or 0))
    except Exception:
        pass

    # E1 · 承诺履约（按 committer 名字别名匹配）
    if aliases:
        try:
            placeholders = ",".join("?" * len(aliases))
            rows = db.fetchall(
                f"""
                SELECT id, content, fulfilled_at
                FROM commitments
                WHERE committer IN ({placeholders}) AND status = 'fulfilled'
                ORDER BY fulfilled_at DESC
                """,
                aliases,
            )
            if rows:
                _add("commitment_fulfilled", len(rows), str(rows[0]["content"])[:50])
        except Exception:
            pass

    # E2 · 风险信号（用户接触过的客户的风险，去重）
    try:
        rows = db.fetchall(
            """
            SELECT DISTINCT r.id, r.title, r.severity
            FROM risk_signals r
            WHERE r.status = 'active'
              AND r.client_id IN (
                SELECT DISTINCT client_id FROM v2_documents WHERE owner_user_id = ?
                UNION
                SELECT DISTINCT client_id FROM tasks WHERE owner_id = ? AND client_id IS NOT NULL
              )
            ORDER BY r.captured_at DESC
            """,
            (user_id, user_id),
        )
        if rows:
            _add("risk_signal_owned", len(rows), str(rows[0]["title"])[:50])
    except Exception:
        pass

    # F1 · 用户原创文档（v2_documents 过滤掉任务壳）
    try:
        row = db.fetchone(
            """
            SELECT COUNT(*) AS cnt FROM v2_documents
            WHERE owner_user_id = ?
              AND kind NOT IN ('task_doc', 'event_line_update_doc', 'review_entry_doc')
              AND visible_category NOT IN ('任务资料', '待处理', '归档')
            """,
            (user_id,),
        )
        if row:
            _add("document_owned", int(row["cnt"] or 0))
    except Exception:
        pass

    # F3 · 客户范围的记忆（弱信号，仅 client scope + 高置信度）
    try:
        row = db.fetchone(
            """
            SELECT COUNT(*) AS cnt FROM memory_facts
            WHERE owner_user_id = ? AND scope_type = 'client' AND confidence >= 0.5
            """,
            (user_id,),
        )
        if row:
            _add("memory_owned_client", int(row["cnt"] or 0))
    except Exception:
        pass

    return contributions


def _compute_ability_totals_from_sources(
    contributions: dict[str, _SourceContribution],
) -> dict[str, int]:
    """按配置矩阵把"事件类型 × base_xp"折算到每个能力维度。"""
    totals: dict[str, float] = defaultdict(float)
    for kind, contrib in contributions.items():
        weights = ABILITY_WEIGHTS_BY_SOURCE.get(kind, {})
        for ability_key, weight in weights.items():
            totals[ability_key] += contrib.total_base_xp * weight
    return {k: int(round(v)) for k, v in totals.items()}


def _pick_real_source_evidence_text(
    contributions: dict[str, _SourceContribution],
    ability_key: str,
    *,
    fallback: str,
) -> str:
    """根据该 ability 收到的最大几个来源拼一句话 evidence。"""
    contribs_for_ability: list[tuple[str, _SourceContribution, float]] = []
    for kind, contrib in contributions.items():
        w = ABILITY_WEIGHTS_BY_SOURCE.get(kind, {}).get(ability_key, 0)
        if w > 0 and contrib.count > 0:
            contribs_for_ability.append((kind, contrib, w * contrib.total_base_xp))
    if not contribs_for_ability:
        return fallback
    contribs_for_ability.sort(key=lambda x: -x[2])

    label_map: dict[str, str] = {
        "weekly_review_summary": "周复盘",
        "weekly_review_task_note": "任务复盘",
        "handbook_entry": "手册条目",
        "task_done": "完成任务",
        "task_created": "创建任务",
        "handbook_reused": "手册被复用",
        "exp_wall_liked": "金句被赞",
        "exp_wall_saved": "金句被收藏",
        "commitment_fulfilled": "承诺已履约",
        "risk_signal_owned": "接触客户的风险信号",
        "document_owned": "上传/产出文档",
        "memory_owned_client": "客户相关记忆",
    }
    parts: list[str] = []
    for kind, contrib, _ in contribs_for_ability[:3]:
        label = label_map.get(kind, kind)
        if contrib.sample_title:
            parts.append(f"{label} {contrib.count} 条 · 最新「{contrib.sample_title}」")
        else:
            parts.append(f"{label} {contrib.count} 条")
    return " · ".join(parts)


# ════════════════════════════════════════════════════════════════════════════
# 数据中心客观证据增强（G1+G2 P0 改造）
# ════════════════════════════════════════════════════════════════════════════
# 现有 ledger 完全基于 ABILITY_KEYWORDS 关键词匹配累计 XP。本模块直接读
# 数据中心已有的真实标注：exp_wall_quote.category、memory_facts.owner_user_id、
# v2_documents.owner_user_id。这些是"被组织真实认可 / 真实留下的产出"，
# 比关键词扫描可靠得多。
#
# 等数据中心后续提供 work_evidence_annotations / role_profile_snapshot 等
# 更精准的标注表后，这里替换数据源即可，外层 build_growth_overview 不动。

# 经验墙 6 类目 → 6 能力维度
EXP_WALL_CATEGORY_TO_ABILITY: dict[str, str] = {
    "项目推进": "exec",
    "团队协作": "collab",
    "判断决策": "analyze",
    "客户沟通": "insight",
    "风险识别": "risk",
    "方法论": "write",
}

# 经验墙金句 contribution_score → XP 折算系数
EXP_WALL_SCORE_TO_XP_RATIO = 0.5

# memory_facts.scope_type → ability（贡献了客户/项目/部门记忆 = 对应能力的实证）
MEMORY_SCOPE_TO_ABILITY: dict[str, str] = {
    "client": "insight",
    "project": "analyze",
    "department": "collab",
}

# 临时锚点：组内样本不足时的 fallback baseline（待数据中心提供 role_anchor 后删除）
_BASELINE_FALLBACK_SCORE = 50
_BASELINE_MIN_SAMPLE = 3


@dataclass
class _ObjectiveEvidence:
    """单条客观证据（来源于数据中心已有的真实标注）。"""

    ability_key: str
    source_type: str  # exp_wall_quote / memory_fact / document
    title: str
    detail: str
    weight: float  # 折算的 XP 加权值
    occurred_at: str


def _fetch_exp_wall_evidence(db: Database, user_id: str) -> list[_ObjectiveEvidence]:
    try:
        rows = db.fetchall(
            """
            SELECT id, quote_text, category, contribution_score, like_count, save_count, created_at
            FROM exp_wall_quotes
            WHERE author_user_id = ? AND status = 'active'
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
    except Exception:
        return []
    items: list[_ObjectiveEvidence] = []
    for row in rows:
        category = str(row["category"] or "").strip()
        ability_key = EXP_WALL_CATEGORY_TO_ABILITY.get(category)
        if not ability_key:
            continue
        contribution = float(row["contribution_score"] or 0)
        like_count = int(row["like_count"] or 0)
        save_count = int(row["save_count"] or 0)
        items.append(
            _ObjectiveEvidence(
                ability_key=ability_key,
                source_type="exp_wall_quote",
                title=str(row["quote_text"] or "")[:60],
                detail=f"被组织墙收录 · ♥{like_count} ⭐{save_count}",
                weight=contribution * EXP_WALL_SCORE_TO_XP_RATIO,
                occurred_at=str(row["created_at"] or ""),
            )
        )
    return items


def _fetch_memory_evidence(db: Database, user_id: str, *, limit: int = 30) -> list[_ObjectiveEvidence]:
    try:
        rows = db.fetchall(
            """
            SELECT id, scope_type, scope_id, fact_key, fact_value, source_type, confidence, updated_at
            FROM memory_facts
            WHERE owner_user_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
    except Exception:
        return []
    items: list[_ObjectiveEvidence] = []
    for row in rows:
        scope_type = str(row["scope_type"] or "")
        ability_key = MEMORY_SCOPE_TO_ABILITY.get(scope_type)
        if not ability_key:
            continue
        confidence = float(row["confidence"] or 0)
        if confidence < 0.4:
            continue
        items.append(
            _ObjectiveEvidence(
                ability_key=ability_key,
                source_type="memory_fact",
                title=str(row["fact_key"] or "")[:60],
                detail=str(row["fact_value"] or "")[:80],
                weight=4.0 * confidence,
                occurred_at=str(row["updated_at"] or ""),
            )
        )
    return items


def _fetch_document_evidence(db: Database, user_id: str, *, limit: int = 20) -> list[_ObjectiveEvidence]:
    try:
        rows = db.fetchall(
            """
            SELECT id, file_name, kind, visible_category, updated_at
            FROM v2_documents
            WHERE owner_user_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
    except Exception:
        return []
    items: list[_ObjectiveEvidence] = []
    for row in rows:
        category = str(row["visible_category"] or "")
        file_name = str(row["file_name"] or "")
        merged = f"{category} {file_name}"
        if "客户" in merged or "客户分析" in merged:
            ability_key = "insight"
        elif "风险" in merged:
            ability_key = "risk"
        elif "方法" in merged or "模板" in merged or "手册" in merged:
            ability_key = "write"
        elif "复盘" in merged or "总结" in merged or "分析" in merged:
            ability_key = "analyze"
        elif "会议" in merged or "纪要" in merged:
            ability_key = "collab"
        else:
            ability_key = "write"
        items.append(
            _ObjectiveEvidence(
                ability_key=ability_key,
                source_type="document",
                title=file_name[:60],
                detail=category,
                weight=2.0,
                occurred_at=str(row["updated_at"] or ""),
            )
        )
    return items


def _collect_objective_evidence(db: Database, user_id: str) -> list[_ObjectiveEvidence]:
    """汇总该用户在数据中心留下的全部客观证据，按时间倒序。"""
    bucket: list[_ObjectiveEvidence] = []
    bucket.extend(_fetch_exp_wall_evidence(db, user_id))
    bucket.extend(_fetch_memory_evidence(db, user_id))
    bucket.extend(_fetch_document_evidence(db, user_id))
    bucket.sort(key=lambda x: x.occurred_at, reverse=True)
    return bucket


def _objective_xp_by_ability(evidence: list[_ObjectiveEvidence]) -> dict[str, int]:
    bucket: dict[str, float] = defaultdict(float)
    for item in evidence:
        bucket[item.ability_key] += item.weight
    return {k: int(round(v)) for k, v in bucket.items()}


def _objective_count_by_ability(evidence: list[_ObjectiveEvidence]) -> dict[str, int]:
    bucket: dict[str, int] = defaultdict(int)
    for item in evidence:
        bucket[item.ability_key] += 1
    return dict(bucket)


def _pick_objective_evidence_text(
    evidence: list[_ObjectiveEvidence],
    ability_key: str,
    *,
    fallback: str,
) -> str:
    """把该 ability 的所有客观证据聚合成一句"人话"。

    H2 改造：
    - 不暴露技术 ID（旧逻辑直接打印 memory.fact_key 形如
      "data_center_ingest:task:task_638f00d491"）
    - 不暴露 memory.fact_value 内容（按 [[project-yiyu-exp-wall-rules]] 第 1 条，
      客户/项目相关的敏感判断不展示）
    - 按强弱排序：被组织看见的金句 > 真实文档产出 > 记忆沉淀计数
    """
    matches = [e for e in evidence if e.ability_key == ability_key]
    if not matches:
        return fallback

    quotes = [e for e in matches if e.source_type == "exp_wall_quote"]
    docs = [e for e in matches if e.source_type == "document"]
    memories = [e for e in matches if e.source_type == "memory_fact"]

    parts: list[str] = []
    if quotes:
        head = quotes[0]
        if len(quotes) > 1:
            parts.append(f"组织墙金句 {len(quotes)} 条 · 最新「{head.title}」")
        else:
            parts.append(f"组织墙金句：「{head.title}」")
    if docs:
        head = docs[0]
        if len(docs) > 1:
            parts.append(f"近期产出 {len(docs)} 份 · 最新《{head.title}》")
        else:
            parts.append(f"近期产出：《{head.title}》")
    if memories:
        parts.append(f"沉淀相关记忆 {len(memories)} 条")

    return " · ".join(parts) if parts else fallback


def _current_week_label() -> str:
    """ISO 周标签，如 '2026-W20'。每周一切换。"""
    today = datetime.now()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _persist_weekly_snapshot(
    db: Database,
    user_id: str,
    ability_scores: list[GrowthAbilityScoreRecord],
) -> None:
    """L1：把当周末的 6 能力分数快照写入 growth_ability_weekly_snapshot。

    懒触发：build_growth_overview 调用时检测；UNIQUE(user_id, week_label, ability_key)
    保证一周内重复 build 只覆盖不重复增长（用 INSERT OR REPLACE）。
    """
    if not ability_scores:
        return
    week_label = _current_week_label()
    now = _now_iso()
    try:
        for ab in ability_scores:
            db.execute(
                """
                INSERT OR REPLACE INTO growth_ability_weekly_snapshot(
                    id, user_id, week_label, ability_key,
                    current_score, total_xp, snapshot_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"snap_{user_id}_{week_label}_{ab.abilityKey}",
                    user_id,
                    week_label,
                    ab.abilityKey,
                    int(ab.currentScore),
                    int(ab.totalXp),
                    now,
                ),
            )
    except Exception:
        # 表可能未建（旧库），静默跳过
        pass


def _build_ability_trends(
    db: Database,
    user_id: str,
    ability_scores: list[GrowthAbilityScoreRecord],
    profile_map: dict[str, GrowthAbilityProfileRecord],
    *,
    weeks: int = 8,
) -> list[GrowthAbilityTrendRecord]:
    """L1：拉最近 N 周快照，组装 6 能力趋势。"""
    try:
        rows = db.fetchall(
            """
            SELECT ability_key, week_label, current_score, total_xp
            FROM growth_ability_weekly_snapshot
            WHERE user_id = ?
            ORDER BY week_label ASC
            """,
            (user_id,),
        )
    except Exception:
        rows = []

    by_ability: dict[str, list[GrowthAbilityTrendPointRecord]] = defaultdict(list)
    for row in rows:
        key = str(row["ability_key"])
        by_ability[key].append(
            GrowthAbilityTrendPointRecord(
                weekLabel=str(row["week_label"]),
                score=int(row["current_score"] or 0),
                totalXp=int(row["total_xp"] or 0),
            )
        )

    trends: list[GrowthAbilityTrendRecord] = []
    for ab in ability_scores:
        points = by_ability.get(ab.abilityKey, [])[-weeks:]
        score_delta = 0
        direction = "flat"
        if len(points) >= 2:
            score_delta = points[-1].score - points[-2].score
            if score_delta > 0:
                direction = "up"
            elif score_delta < 0:
                direction = "down"
        trends.append(
            GrowthAbilityTrendRecord(
                abilityKey=ab.abilityKey,
                label=ab.label,
                points=points,
                scoreDelta=score_delta,
                direction=direction,
            )
        )
    return trends


def _build_commitment_summary(db: Database, user_id: str) -> GrowthCommitmentSummaryRecord:
    """M2：承诺履约率 + 4 周趋势 + 即将到期的承诺列表。"""
    summary = GrowthCommitmentSummaryRecord()
    aliases = _resolve_user_aliases(db, user_id)
    if not aliases:
        return summary

    placeholders = ",".join("?" * len(aliases))
    today = datetime.now()
    cutoff_30 = (today - timedelta(days=30)).isoformat(timespec="seconds")

    try:
        rows = db.fetchall(
            f"""
            SELECT id, content, recipient, deadline, status, fulfilled_at
            FROM commitments
            WHERE committer IN ({placeholders}) AND created_at >= ?
            """,
            tuple(list(aliases) + [cutoff_30]),
        )
    except Exception:
        rows = []

    summary.totalCount = len(rows)
    for row in rows:
        st = str(row["status"] or "")
        if st == "fulfilled":
            summary.fulfilledCount += 1
        elif st == "pending":
            summary.pendingCount += 1
        deadline = row["deadline"]
        if deadline and st != "fulfilled":
            try:
                dd = datetime.fromisoformat(str(deadline)[:10])
                if dd < today:
                    summary.overdueCount += 1
            except Exception:
                pass
    summary.rate = round(summary.fulfilledCount / max(1, summary.totalCount), 3)

    # 4 周趋势
    try:
        trend_rows = db.fetchall(
            f"""
            SELECT id, status, created_at, fulfilled_at, deadline
            FROM commitments
            WHERE committer IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT 200
            """,
            aliases,
        )
    except Exception:
        trend_rows = []

    for weeks_back in range(3, -1, -1):
        week_end = today - timedelta(days=weeks_back * 7)
        week_start = week_end - timedelta(days=7)
        week_label = f"{week_end.isocalendar()[0]}-W{week_end.isocalendar()[1]:02d}"
        total = 0
        fulfilled = 0
        for r in trend_rows:
            ca = str(r["created_at"] or "")[:10]
            if not ca:
                continue
            try:
                created = datetime.fromisoformat(ca)
            except Exception:
                continue
            if week_start <= created < week_end:
                total += 1
                if str(r["status"] or "") == "fulfilled":
                    fulfilled += 1
        rate = round(fulfilled / max(1, total), 3) if total else 0.0
        summary.trend.append(
            GrowthCommitmentTrendPointRecord(
                weekLabel=week_label,
                totalCount=total,
                fulfilledCount=fulfilled,
                rate=rate,
            )
        )

    # 即将到期 / 已超期的 pending 承诺（保留写入，前端不再渲染——属于任务系统的事）
    try:
        upcoming_rows = db.fetchall(
            f"""
            SELECT id, content, recipient, deadline, status
            FROM commitments
            WHERE committer IN ({placeholders}) AND status='pending'
            ORDER BY COALESCE(deadline, '9999-12-31') ASC
            LIMIT 5
            """,
            aliases,
        )
        for r in upcoming_rows:
            deadline = str(r["deadline"] or "")
            days_overdue = 0
            if deadline:
                try:
                    dd = datetime.fromisoformat(deadline[:10])
                    days_overdue = (today.date() - dd.date()).days
                except Exception:
                    pass
            summary.upcomingPending.append(
                GrowthCommitmentItemRecord(
                    id=str(r["id"]),
                    content=str(r["content"] or ""),
                    recipient=str(r["recipient"] or ""),
                    deadline=deadline or None,
                    status=str(r["status"] or ""),
                    daysOverdue=days_overdue,
                )
            )
    except Exception:
        pass

    # ── 正向指标计算 ────────────────────────────────────────
    # 取本月 + 上月的全部承诺记录（按 deadline 排序），用于 streak + 累计曲线
    try:
        all_rows = db.fetchall(
            f"""
            SELECT id, status, deadline, fulfilled_at
            FROM commitments
            WHERE committer IN ({placeholders})
              AND deadline IS NOT NULL AND deadline != ''
            ORDER BY deadline ASC
            """,
            aliases,
        )
    except Exception:
        all_rows = []

    # streak: 沿 deadline 时间轴扫描，遇到 missed 就重置
    def _is_missed(row) -> bool:
        st = str(row["status"] or "")
        deadline = str(row["deadline"] or "")[:10]
        fulfilled = str(row["fulfilled_at"] or "")[:10] if row["fulfilled_at"] else ""
        if not deadline:
            return False
        try:
            dl = datetime.fromisoformat(deadline)
        except Exception:
            return False
        # 已 fulfilled 但晚于 deadline → missed
        if st == "fulfilled" and fulfilled:
            try:
                fa = datetime.fromisoformat(fulfilled)
                if fa.date() > dl.date():
                    return True
            except Exception:
                pass
            return False
        # 仍 pending 且 deadline 已过 → missed
        if st != "fulfilled" and dl.date() < today.date():
            return True
        return False

    # 最长 streak（天数）
    longest = 0
    cur = 0
    prev_date: datetime | None = None
    for r in all_rows:
        if _is_missed(r):
            cur = 0
            prev_date = None
            continue
        try:
            dl = datetime.fromisoformat(str(r["deadline"])[:10])
        except Exception:
            continue
        if prev_date is None:
            cur = 1
        else:
            cur += max(1, (dl.date() - prev_date.date()).days)
        prev_date = dl
        longest = max(longest, cur)
    summary.longestStreakDays = longest

    # 当前 streak：从今天往回数到最近一次 missed
    last_missed_date: datetime | None = None
    for r in all_rows:
        if _is_missed(r):
            try:
                dl = datetime.fromisoformat(str(r["deadline"])[:10])
                if last_missed_date is None or dl > last_missed_date:
                    last_missed_date = dl
            except Exception:
                continue
    if last_missed_date is None:
        # 从来没 missed → streak = 第一个 commitment 到今天的天数
        if all_rows:
            try:
                first_dl = datetime.fromisoformat(str(all_rows[0]["deadline"])[:10])
                summary.currentStreakDays = max(0, (today.date() - first_dl.date()).days)
            except Exception:
                summary.currentStreakDays = 0
    else:
        summary.currentStreakDays = max(0, (today.date() - last_missed_date.date()).days)

    # 月度兑现件数 + 环比
    cutoff_60 = (today - timedelta(days=60)).isoformat(timespec="seconds")
    try:
        month_rows = db.fetchall(
            f"""
            SELECT fulfilled_at
            FROM commitments
            WHERE committer IN ({placeholders})
              AND status='fulfilled' AND fulfilled_at >= ?
            """,
            tuple(list(aliases) + [cutoff_60]),
        )
    except Exception:
        month_rows = []
    monthly_n = 0
    last_monthly_n = 0
    cutoff_30_dt = today - timedelta(days=30)
    for r in month_rows:
        fa = str(r["fulfilled_at"] or "")[:10]
        if not fa:
            continue
        try:
            dt = datetime.fromisoformat(fa)
        except Exception:
            continue
        if dt >= cutoff_30_dt:
            monthly_n += 1
        else:
            last_monthly_n += 1
    summary.monthlyFulfilledCount = monthly_n
    summary.lastMonthFulfilledCount = last_monthly_n
    if last_monthly_n > 0:
        summary.growthPercent = int(round((monthly_n - last_monthly_n) / last_monthly_n * 100))
    elif monthly_n > 0:
        summary.growthPercent = 100  # 从 0 起步

    # 双线累计曲线：4 个点，每个点 = 月初到该周末的「累计件数」
    # weekIndex 0 = 月第 1 周末（前 7 天累计）；weekIndex 3 = 月第 4 周末（全月累计）
    month_start_current = today - timedelta(days=28)
    month_start_previous = today - timedelta(days=56)
    curve_points: list[GrowthCommitmentCumulativePointRecord] = []
    for week_idx in range(4):
        days_into_month = (week_idx + 1) * 7
        cur_end = month_start_current + timedelta(days=days_into_month)
        prev_end = month_start_previous + timedelta(days=days_into_month)
        cur_cumu = 0
        prev_cumu = 0
        for r in month_rows:
            fa = str(r["fulfilled_at"] or "")[:10]
            if not fa:
                continue
            try:
                dt = datetime.fromisoformat(fa)
            except Exception:
                continue
            if month_start_current <= dt <= cur_end:
                cur_cumu += 1
            if month_start_previous <= dt <= prev_end:
                prev_cumu += 1
        curve_points.append(GrowthCommitmentCumulativePointRecord(
            weekIndex=week_idx,
            weekLabel=f"W{week_idx + 1}",
            currentCumulative=cur_cumu,
            previousCumulative=prev_cumu,
        ))
    summary.cumulativeCurve = curve_points

    return summary


def _build_business_coverage(db: Database, user_id: str) -> GrowthBusinessCoverageRecord:
    """M1：业务覆盖热力图 = 按客户聚合的任务/文档/字典积累。"""
    record = GrowthBusinessCoverageRecord()
    try:
        rows = db.fetchall(
            """
            SELECT c.id AS client_id, c.name AS client_name,
                (SELECT COUNT(*) FROM tasks WHERE owner_id=? AND client_id=c.id) AS task_cnt,
                (SELECT COUNT(*) FROM v2_documents WHERE owner_user_id=? AND client_id=c.id
                     AND kind NOT IN ('task_doc','event_line_update_doc','review_entry_doc')) AS doc_cnt,
                (SELECT COUNT(*) FROM client_glossary WHERE client_id=c.id) AS term_cnt
            FROM clients c
            WHERE c.id IN (
                SELECT DISTINCT client_id FROM tasks WHERE owner_id=? AND client_id IS NOT NULL
                UNION
                SELECT DISTINCT client_id FROM v2_documents WHERE owner_user_id=? AND client_id IS NOT NULL
            )
            """,
            (user_id, user_id, user_id, user_id),
        )
    except Exception:
        rows = []

    for row in rows:
        task_cnt = int(row["task_cnt"] or 0)
        doc_cnt = int(row["doc_cnt"] or 0)
        term_cnt = int(row["term_cnt"] or 0)
        if task_cnt + doc_cnt + term_cnt == 0:
            continue
        score = task_cnt * 1 + doc_cnt * 3 + term_cnt * 0.2
        record.items.append(
            GrowthBusinessCoverageItemRecord(
                label=str(row["client_name"] or "未命名客户"),
                taskCount=task_cnt,
                documentCount=doc_cnt,
                glossaryTermCount=term_cnt,
                score=int(round(score)),
            )
        )
    record.items.sort(key=lambda x: -x.score)
    record.coveredClients = len(record.items)
    record.coveredProjects = sum(x.glossaryTermCount for x in record.items)
    return record


def _build_review_streak(db: Database, user_id: str) -> GrowthReviewStreakRecord:
    """M3：复盘 streaks。"""
    streak = GrowthReviewStreakRecord()
    try:
        rows = db.fetchall(
            """
            SELECT DISTINCT week_label FROM weekly_reviews
            WHERE user_id = ? AND week_label LIKE '____-W%'
            ORDER BY week_label DESC
            """,
            (user_id,),
        )
    except Exception:
        return streak

    week_labels = [str(r["week_label"]) for r in rows if r["week_label"]]
    if not week_labels:
        return streak

    streak.totalReviewWeeks = len(week_labels)
    streak.lastReviewedWeekLabel = week_labels[0]

    def _parse_week(label: str) -> tuple[int, int] | None:
        try:
            y, w = label.split("-W")
            return int(y), int(w)
        except Exception:
            return None

    parsed = sorted(filter(None, (_parse_week(x) for x in week_labels)), reverse=True)
    if not parsed:
        return streak

    # 计算 max streak
    max_s = 1
    cur = 1
    for i in range(1, len(parsed)):
        y0, w0 = parsed[i - 1]
        y1, w1 = parsed[i]
        is_prev = (y0 == y1 and w0 == w1 + 1) or (y0 == y1 + 1 and w0 == 1 and w1 >= 52)
        if is_prev:
            cur += 1
            max_s = max(max_s, cur)
        else:
            cur = 1
    streak.maxStreakWeeks = max_s

    # 当前 streak：从最新一周往回数连续
    today = datetime.now()
    cur_year, cur_week, _ = today.isocalendar()
    cur_streak = 0
    py, pw = cur_year, cur_week
    parsed_set = set(parsed)
    while (py, pw) in parsed_set:
        cur_streak += 1
        pw -= 1
        if pw < 1:
            py -= 1
            pw = 52
    streak.currentStreakWeeks = cur_streak

    # ── 件数 + 字数维度（聚合 weekly_review_task_entries）──
    cutoff_60 = (today - timedelta(days=60)).isoformat(timespec="seconds")
    try:
        # weekly_review_task_entries.user_id 字段在生产 db 里大多为空，
        # 必须通过 review_id join 到 weekly_reviews 拿 user_id
        entry_rows = db.fetchall(
            """
            SELECT t.reviewed_at, t.week_label,
                   length(COALESCE(t.note, '')) AS nlen,
                   length(COALESCE(t.structured_note_json, '')) AS slen
            FROM weekly_review_task_entries t
            JOIN weekly_reviews r ON r.id = t.review_id
            WHERE r.user_id = ? AND t.reviewed_at >= ?
            """,
            (user_id, cutoff_60),
        )
    except Exception:
        entry_rows = []

    cutoff_30_dt = today - timedelta(days=30)
    monthly_entry = 0
    last_monthly_entry = 0
    monthly_chars = 0
    last_monthly_chars = 0
    week_buckets: dict[str, dict[str, int]] = {}
    for r in entry_rows:
        ra = str(r["reviewed_at"] or "")[:10]
        if not ra:
            continue
        try:
            dt = datetime.fromisoformat(ra)
        except Exception:
            continue
        chars = int(r["nlen"] or 0) + int(r["slen"] or 0)
        wl = str(r["week_label"] or "")
        if dt >= cutoff_30_dt:
            monthly_entry += 1
            monthly_chars += chars
            if wl:
                bucket = week_buckets.setdefault(wl, {"entries": 0, "chars": 0})
                bucket["entries"] += 1
                bucket["chars"] += chars
        else:
            last_monthly_entry += 1
            last_monthly_chars += chars

    streak.monthlyEntryCount = monthly_entry
    streak.lastMonthEntryCount = last_monthly_entry
    streak.monthlyCharCount = monthly_chars
    streak.lastMonthCharCount = last_monthly_chars
    if last_monthly_entry > 0:
        streak.entryGrowthPercent = int(round((monthly_entry - last_monthly_entry) / last_monthly_entry * 100))
    elif monthly_entry > 0:
        streak.entryGrowthPercent = 100
    if last_monthly_chars > 0:
        streak.charGrowthPercent = int(round((monthly_chars - last_monthly_chars) / last_monthly_chars * 100))
    elif monthly_chars > 0:
        streak.charGrowthPercent = 100

    # 4 周趋势（保留兼容）
    sorted_weeks = sorted(week_buckets.keys(), reverse=True)[:4]
    sorted_weeks.reverse()
    for wl in sorted_weeks:
        b = week_buckets[wl]
        streak.weeklyTrend.append(
            GrowthReviewWeekPointRecord(
                weekLabel=wl,
                entryCount=int(b["entries"]),
                charCount=int(b["chars"]),
            )
        )

    # 30 天日聚合（新曲线图用）
    day_buckets: dict[str, dict[str, int]] = {}
    for r in entry_rows:
        ra = str(r["reviewed_at"] or "")[:10]
        if not ra:
            continue
        try:
            dt = datetime.fromisoformat(ra)
        except Exception:
            continue
        if dt < cutoff_30_dt:
            continue
        chars = int(r["nlen"] or 0) + int(r["slen"] or 0)
        bucket = day_buckets.setdefault(ra, {"entries": 0, "chars": 0})
        bucket["entries"] += 1
        bucket["chars"] += chars
    # 填充近 30 天（包括 0 值）
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        b = day_buckets.get(d, {"entries": 0, "chars": 0})
        streak.dailyTrend.append(
            GrowthReviewDayPointRecord(
                date=d,
                entryCount=int(b["entries"]),
                charCount=int(b["chars"]),
            )
        )

    return streak


def _build_work_type_distribution(db: Database, user_id: str) -> GrowthWorkTypeRecord:
    """M4：tasks.business_category 分布。

    没分到细分类目的任务统一显示「主要业务」（战略咨询公司的核心业务，
    不是分类失败）。历史的 '专项推进' / '未分类' 都合并到这个桶。
    """
    record = GrowthWorkTypeRecord()
    try:
        rows = db.fetchall(
            """
            SELECT COALESCE(NULLIF(business_category, ''), '主要业务') AS cat, COUNT(*) AS cnt
            FROM tasks WHERE owner_id = ?
            GROUP BY COALESCE(NULLIF(business_category, ''), '主要业务')
            ORDER BY cnt DESC
            """,
            (user_id,),
        )
    except Exception:
        rows = []
    total = 0
    unlabeled = 0
    bucket: dict[str, int] = {}
    for row in rows:
        cnt = int(row["cnt"] or 0)
        label = str(row["cat"])
        # 历史 fallback 值统一归到 '主要业务'
        if label in ("专项推进", "未分类", "待标注"):
            label = "主要业务"
        total += cnt
        bucket[label] = bucket.get(label, 0) + cnt
    for label, cnt in sorted(bucket.items(), key=lambda x: -x[1]):
        record.slices.append(GrowthWorkTypeSliceRecord(label=label, count=cnt))
    record.totalTasks = total
    record.unlabeledTasks = unlabeled  # 保留字段但不再有"噪音"语义
    return record


def _build_impact_curve(db: Database, user_id: str) -> GrowthImpactRecord:
    """M6：12 个月累计影响力曲线（reuses + likes + saves）。"""
    record = GrowthImpactRecord()
    today = datetime.now()
    # 用 month_label like '2026-05' 累计该月之前所有 reuse/like/save
    try:
        handbook_events = db.fetchall(
            """
            SELECT COALESCE(last_reused_at, created_at) AS d, reuse_count, created_at
            FROM handbook_entries
            WHERE author_user_id = ? AND reuse_count > 0
            """,
            (user_id,),
        )
    except Exception:
        handbook_events = []
    try:
        wall_events = db.fetchall(
            """
            SELECT created_at, like_count, save_count
            FROM exp_wall_quotes
            WHERE author_user_id = ? AND status = 'active'
            """,
            (user_id,),
        )
    except Exception:
        wall_events = []

    cumu_r = 0
    cumu_l = 0
    cumu_s = 0
    points: list[GrowthImpactCurvePointRecord] = []
    for months_back in range(11, -1, -1):
        # 该月末
        target = today - timedelta(days=months_back * 30)
        month_label = target.strftime("%Y-%m")
        # 该月累积
        for e in handbook_events:
            d = str(e["last_reused_at"] if "last_reused_at" in e.keys() and e["last_reused_at"] else e["created_at"] or "")[:7]
            if d and d == month_label:
                cumu_r += int(e["reuse_count"] or 0)
        for e in wall_events:
            d = str(e["created_at"] or "")[:7]
            if d and d == month_label:
                cumu_l += int(e["like_count"] or 0)
                cumu_s += int(e["save_count"] or 0)
        points.append(
            GrowthImpactCurvePointRecord(
                monthLabel=month_label,
                cumulativeReuses=cumu_r,
                cumulativeLikes=cumu_l,
                cumulativeSaves=cumu_s,
            )
        )
    record.points = points
    record.totalReuses = cumu_r
    record.totalLikes = cumu_l
    record.totalSaves = cumu_s
    return record


def _build_internal_learning_picks(
    db: Database,
    user_id: str,
    ability_scores: list[GrowthAbilityScoreRecord],
    profile_map: dict[str, GrowthAbilityProfileRecord],
) -> GrowthLearningRecord:
    """L3：基于最弱 2 个能力维度推同事 handbook + 经验墙金句。"""
    record = GrowthLearningRecord()
    if not ability_scores:
        return record

    sorted_abilities = sorted(ability_scores, key=lambda x: x.currentScore)[:2]
    weakest_keys = [a.abilityKey for a in sorted_abilities]
    record.weakestAbilities = weakest_keys

    # exp_wall category → ability 反查
    inv_cat = {v: k for k, v in EXP_WALL_CATEGORY_TO_ABILITY.items()}

    seen_handbook_ids: set[str] = set()
    for weak in sorted_abilities:
        # handbook：① 优先严格匹配 ability_keys ② fallback 按高复用通用推荐
        candidate_rows: list = []
        try:
            strict = db.fetchall(
                """
                SELECT id, title, summary, author_user_name, reuse_count, ability_keys_json
                FROM handbook_entries
                WHERE COALESCE(author_user_id, '') != ?
                  AND ability_keys_json LIKE ?
                ORDER BY reuse_count DESC, created_at DESC
                LIMIT 2
                """,
                (user_id, f'%"{weak.abilityKey}"%'),
            )
            candidate_rows.extend(strict)
        except Exception:
            pass
        if not candidate_rows:
            try:
                broad = db.fetchall(
                    """
                    SELECT id, title, summary, author_user_name, reuse_count, ability_keys_json
                    FROM handbook_entries
                    WHERE COALESCE(author_user_id, '') != ?
                    ORDER BY reuse_count DESC, created_at DESC
                    LIMIT 2
                    """,
                    (user_id,),
                )
                candidate_rows.extend(broad)
            except Exception:
                pass

        for row in candidate_rows:
            hid = str(row["id"])
            if hid in seen_handbook_ids:
                continue
            seen_handbook_ids.add(hid)
            record.internalPicks.append(
                GrowthLearningPickRecord(
                    source="handbook",
                    sourceId=hid,
                    title=str(row["title"] or "")[:80],
                    detail=str(row["summary"] or "")[:120],
                    authorName=str(row["author_user_name"] or "同事"),
                    matchedAbility=weak.abilityKey,
                    matchedAbilityLabel=weak.label,
                    reusedCount=int(row["reuse_count"] or 0),
                )
            )

        # exp_wall：同 category，作者非自己
        wall_cat = inv_cat.get(weak.abilityKey)
        if wall_cat:
            try:
                ew_rows = db.fetchall(
                    """
                    SELECT id, quote_text, like_count, save_count, author_user_id
                    FROM exp_wall_quotes
                    WHERE author_user_id != ? AND status='active' AND category = ?
                    ORDER BY hot_score DESC
                    LIMIT 1
                    """,
                    (user_id, wall_cat),
                )
                for row in ew_rows:
                    record.internalPicks.append(
                        GrowthLearningPickRecord(
                            source="exp_wall",
                            sourceId=str(row["id"]),
                            title=str(row["quote_text"] or "")[:80],
                            authorName="",
                            matchedAbility=weak.abilityKey,
                            matchedAbilityLabel=weak.label,
                            likedCount=int(row["like_count"] or 0),
                            savedCount=int(row["save_count"] or 0),
                        )
                    )
            except Exception:
                pass

    # L4 + L5：外部前瞻（GitHub + Exa）—— 降级实现，无 key 时空返回 + 提示
    keywords: list[str] = []
    if weakest_keys and profile_map:
        for k in weakest_keys[:1]:
            label = profile_map.get(k).label if profile_map.get(k) else k
            keywords.append(label)
    # 加 1 个用户高积累的业务方向（从 client_glossary 找最热的 term）
    try:
        top_terms = db.fetchall(
            """
            SELECT g.term
            FROM client_glossary g
            JOIN clients c ON c.id = g.client_id
            WHERE g.client_id IN (
                SELECT DISTINCT client_id FROM tasks WHERE owner_id=? AND client_id IS NOT NULL
            ) AND g.category IN ('业务术语', '项目')
            ORDER BY length(g.aliases_json) DESC
            LIMIT 2
            """,
            (user_id,),
        )
        keywords.extend(str(r["term"]) for r in top_terms if r["term"])
    except Exception:
        pass

    try:
        from app.services.external_learning import fetch_github_picks, fetch_exa_picks
        gh_picks, gh_enabled, gh_hint = fetch_github_picks(user_id, keywords, limit=3)
        record.githubPicks = gh_picks
        ex_picks, ex_enabled, ex_hint = fetch_exa_picks(user_id, keywords, limit=3)
        record.frontierPicks = ex_picks
        record.externalEnabled = bool(gh_enabled or ex_enabled)
        if not gh_enabled and not ex_enabled:
            record.externalConfigHint = f"GitHub: {gh_hint} · Exa: {ex_hint}"
        elif not gh_enabled:
            record.externalConfigHint = f"GitHub: {gh_hint}"
        elif not ex_enabled:
            record.externalConfigHint = f"Exa: {ex_hint}"
    except Exception as exc:
        record.externalEnabled = False
        record.externalConfigHint = f"外部推荐初始化失败：{type(exc).__name__}"

    return record


def _build_peer_comparison(
    db: Database,
    user_id: str,
    ability_scores: list[GrowthAbilityScoreRecord],
) -> GrowthPeerComparisonRecord:
    """成长速度：在整个机构内的 XP 排名（不按岗位过滤）。

    单人岗位（CEO、唯一负责人）按同岗位比毫无意义；
    改成跟整个机构所有有 ledger 数据的成员比，反映"机构内成长速度"。
    """
    record = GrowthPeerComparisonRecord()
    record.roleLabel = "机构成长榜"
    try:
        # 整个机构所有曾有 ledger 数据的 user_id（即"真实活跃成员"）
        peers = db.fetchall(
            """
            SELECT DISTINCT user_id FROM xp_ledger
            WHERE reversed_at IS NULL AND COALESCE(user_id, '') != ''
            """
        )
        peer_ids = [str(p["user_id"]) for p in peers]
        if user_id not in peer_ids:
            peer_ids.append(user_id)
        record.peerCount = len(peer_ids)
        if record.peerCount < 2:
            # 机构里只有自己一人有数据时
            record.rank = 1
            record.yourTotalXp = sum(int(a.totalXp) for a in ability_scores)
            record.peerMedianXp = record.yourTotalXp
            record.peerTopXp = record.yourTotalXp
            for ab in ability_scores:
                record.perAbilityRank[ab.abilityKey] = 1
            return record

        # 取所有 peer 的总 XP（基于新算法重算每个 peer 较慢，简化用 ledger 取近似值）
        rows = db.fetchall(
            f"""
            SELECT user_id, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
            FROM xp_ledger
            WHERE user_id IN ({",".join("?" * len(peer_ids))}) AND reversed_at IS NULL
            GROUP BY user_id
            """,
            tuple(peer_ids),
        )
        peer_xp = {str(r["user_id"]): int(r["xp"] or 0) for r in rows}
        for pid in peer_ids:
            peer_xp.setdefault(pid, 0)

        # 自己用新算法的总 XP（更准）
        my_total = sum(int(a.totalXp) for a in ability_scores)
        peer_xp[user_id] = max(my_total, peer_xp.get(user_id, 0))
        sorted_xp = sorted(peer_xp.values(), reverse=True)
        record.yourTotalXp = peer_xp[user_id]
        record.peerTopXp = sorted_xp[0]
        mid = len(sorted_xp) // 2
        record.peerMedianXp = sorted_xp[mid]
        record.rank = sorted_xp.index(peer_xp[user_id]) + 1

        # 各能力维度排名
        for ab in ability_scores:
            try:
                per_rows = db.fetchall(
                    f"""
                    SELECT user_id, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
                    FROM xp_ledger
                    WHERE user_id IN ({",".join("?" * len(peer_ids))})
                      AND ability_key = ? AND reversed_at IS NULL
                    GROUP BY user_id
                    """,
                    tuple(peer_ids + [ab.abilityKey]),
                )
                per_xp = {str(r["user_id"]): int(r["xp"] or 0) for r in per_rows}
                for pid in peer_ids:
                    per_xp.setdefault(pid, 0)
                per_xp[user_id] = max(int(ab.totalXp), per_xp.get(user_id, 0))
                sorted_per = sorted(per_xp.values(), reverse=True)
                record.perAbilityRank[ab.abilityKey] = sorted_per.index(per_xp[user_id]) + 1
            except Exception:
                pass
    except Exception:
        pass

    return record


def _build_daily_activity(
    db: Database,
    user_id: str,
    *,
    days: int = 84,
) -> GrowthDailyActivityResponse:
    """L2：聚合最近 N 天工作产出强度，输出 react-activity-calendar 格式。

    强度公式：task_done×2 + handbook_entry×5 + weekly_review×8 + commitment_fulfilled×3
    染色等级（level 0-4）：
        0 = 没动
        1 = 1-4 分（轻微）
        2 = 5-9 分（一般）
        3 = 10-14 分（活跃）
        4 = 15+ 分（爆发）
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    aliases = _resolve_user_aliases(db, user_id)
    daily: dict[str, int] = defaultdict(int)

    def _collect(query: str, params: tuple, weight: int) -> None:
        try:
            rows = db.fetchall(query, params)
            for row in rows:
                d = str(row["d"] or "")[:10]
                if d and d >= cutoff:
                    daily[d] += weight
        except Exception:
            pass

    _collect(
        "SELECT updated_at AS d FROM tasks WHERE owner_id=? AND status='done' AND updated_at >= ?",
        (user_id, cutoff),
        2,
    )
    _collect(
        "SELECT created_at AS d FROM handbook_entries WHERE author_user_id=? AND created_at >= ?",
        (user_id, cutoff),
        5,
    )
    _collect(
        "SELECT created_at AS d FROM weekly_reviews WHERE user_id=? AND created_at >= ?",
        (user_id, cutoff),
        8,
    )
    if aliases:
        placeholders = ",".join("?" * len(aliases))
        _collect(
            f"SELECT fulfilled_at AS d FROM commitments WHERE committer IN ({placeholders}) AND status='fulfilled' AND fulfilled_at >= ?",
            tuple(list(aliases) + [cutoff]),
            3,
        )

    def _level(count: int) -> int:
        if count <= 0:
            return 0
        if count < 5:
            return 1
        if count < 10:
            return 2
        if count < 15:
            return 3
        return 4

    today = datetime.now().date()
    items: list[GrowthDailyActivityRecord] = []
    max_streak = 0
    cur_streak = 0
    active_days = 0
    for i in range(days, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        c = daily.get(d, 0)
        if c > 0:
            active_days += 1
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 0
        items.append(GrowthDailyActivityRecord(date=d, count=c, level=_level(c)))

    return GrowthDailyActivityResponse(
        days=items,
        totalDays=len(items),
        activeDays=active_days,
        maxStreak=max_streak,
    )


def _get_or_build_ability_trends_lazy(
    db: Database,
    user_id: str,
    ability_scores: list[GrowthAbilityScoreRecord],
    profile_map: dict[str, GrowthAbilityProfileRecord],
) -> list[GrowthAbilityTrendRecord]:
    """L1：每次 build_overview 时懒触发当周快照 + 拉最近 8 周趋势。"""
    _persist_weekly_snapshot(db, user_id, ability_scores)
    return _build_ability_trends(db, user_id, ability_scores, profile_map, weeks=8)


def _build_social_feedback(db: Database, user_id: str) -> GrowthSocialFeedbackRecord:
    """H4：让用户看见"努力被看见"——聚合近 30 天的被复用 / 点赞 / 收藏。

    数据源：
    - handbook_entries（author_user_id）的 reuse_count / last_reused_at
    - exp_wall_quotes（author_user_id）的 like_count / save_count

    所有指标都不依赖数据中心新表，只读现有字段；任何一张表缺失都 silent 跳过。
    """
    cutoff = (datetime.now() - timedelta(days=30)).isoformat(timespec="seconds")
    feedback = GrowthSocialFeedbackRecord()

    try:
        row = db.fetchone(
            """
            SELECT
                COALESCE(SUM(reuse_count), 0) AS total_reuse,
                COALESCE(SUM(CASE WHEN reuse_count > 0 THEN 1 ELSE 0 END), 0) AS reused_entries
            FROM handbook_entries
            WHERE author_user_id = ?
              AND (last_reused_at IS NULL OR last_reused_at >= ?)
            """,
            (user_id, cutoff),
        )
        if row:
            feedback.handbookReuseCount = int(row["total_reuse"] or 0)
            feedback.handbookEntriesReused = int(row["reused_entries"] or 0)
    except Exception:
        pass

    try:
        row = db.fetchone(
            """
            SELECT
                COUNT(*) AS quote_count,
                COALESCE(SUM(like_count), 0) AS total_like,
                COALESCE(SUM(save_count), 0) AS total_save
            FROM exp_wall_quotes
            WHERE author_user_id = ? AND status = 'active' AND created_at >= ?
            """,
            (user_id, cutoff),
        )
        if row:
            feedback.expWallQuoteCount = int(row["quote_count"] or 0)
            feedback.expWallLikeCount = int(row["total_like"] or 0)
            feedback.expWallSaveCount = int(row["total_save"] or 0)
    except Exception:
        pass

    return feedback


def _organization_baseline_score(db: Database, ability_key: str) -> int:
    """全组织该 ability 的中位数（临时锚点）。

    后续数据中心提供 role_profile_snapshot 后，这里改成读 role_anchor.p50_score。
    """
    rows = db.fetchall(
        """
        SELECT user_id, SUM(COALESCE(NULLIF(total_xp, 0), delta)) AS xp
        FROM xp_ledger
        WHERE ability_key = ? AND reversed_at IS NULL
        GROUP BY user_id
        """,
        (ability_key,),
    )
    scores = sorted(_current_score(int(row["xp"] or 0)) for row in rows)
    if len(scores) < _BASELINE_MIN_SAMPLE:
        return _BASELINE_FALLBACK_SCORE
    return scores[len(scores) // 2]


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
    if _task_is_personal_only(task):
        return
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
        dedupe_key=f"meeting-publish:{user_id}:{meeting.id}",
        created_at=timestamp,
    )
    reset_signal_growth_outputs(db, signal_id)
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
        dedupe_key=f"{source_type}:{user_id}:{source_id}",
        created_at=timestamp,
    )
    reset_signal_growth_outputs(db, signal_id)
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
    # 真5/27 阶段 1 · mark pending → 真后台 worker 真push 云端
    try:
        from app.services.growth_sync import mark_signal_pending
        mark_signal_pending(db, signal_id)
    except Exception as _exc:
        import logging
        logging.getLogger(__name__).warning("mark signal pending failed: %s", _exc)
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
    # 真5/27 阶段 1 · mark evidence pending → 后台 worker push 云端
    try:
        from app.services.growth_sync import mark_evidence_pending
        mark_evidence_pending(db, evidence_id)
    except Exception as _exc:
        import logging
        logging.getLogger(__name__).warning("mark evidence pending failed: %s", _exc)
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
    event_id = _new_id("gve")
    db.execute(
        """
        INSERT INTO growth_validation_events(
            id, user_id, evidence_id, event_type, actor_id, actor_name, source_type, source_id, detail_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
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
    # 真5/27 阶段 1 · mark validation event pending → 后台 worker push 云端
    try:
        from app.services.growth_sync import mark_validation_event_pending
        mark_validation_event_pending(db, event_id)
    except Exception as _exc:
        import logging
        logging.getLogger(__name__).warning("mark validation event pending failed: %s", _exc)
    return True


def reset_review_growth(db: Database, review_id: str) -> None:
    evidence_rows = db.fetchall("SELECT id FROM growth_evidence_records WHERE review_id = ?", (review_id,))
    if evidence_rows:
        db.executemany("DELETE FROM xp_ledger WHERE evidence_id = ?", [(str(row["id"]),) for row in evidence_rows])
        db.executemany("DELETE FROM growth_validation_events WHERE evidence_id = ?", [(str(row["id"]),) for row in evidence_rows])
    db.execute("DELETE FROM growth_evidence_records WHERE review_id = ?", (review_id,))
    db.execute("DELETE FROM growth_signal_events WHERE review_id = ?", (review_id,))


def reset_signal_growth_outputs(db: Database, signal_id: str) -> None:
    evidence_rows = db.fetchall("SELECT id FROM growth_evidence_records WHERE signal_id = ?", (signal_id,))
    if evidence_rows:
        evidence_ids = [(str(row["id"]),) for row in evidence_rows]
        db.executemany("DELETE FROM xp_ledger WHERE evidence_id = ?", evidence_ids)
        db.executemany("DELETE FROM growth_validation_events WHERE evidence_id = ?", evidence_ids)
    db.execute("DELETE FROM growth_evidence_records WHERE signal_id = ?", (signal_id,))


def _task_is_personal_only(task: TaskRecord) -> bool:
    return task.scopeMode == "PERSONAL_ONLY" or any(tag.scope == "self" for tag in task.tags)


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
        if entry.contentDomain != "work":
            continue
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


def _build_source_coverage(
    db: Database,
    user_id: str,
    *,
    objective_evidence: list[_ObjectiveEvidence] | None = None,
) -> GrowthSourceCoverageRecord:
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

    # G3：把数据中心客观证据来源数也算进 coverage
    for item in objective_evidence or []:
        if item.source_type == "exp_wall_quote":
            coverage.expWallSignals += 1
        elif item.source_type == "memory_fact":
            coverage.memorySignals += 1
        elif item.source_type == "document":
            coverage.documentSignals += 1

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
    *,
    db: Database | None = None,
    objective_evidence: list[_ObjectiveEvidence] | None = None,
) -> list[GrowthAbilityGapRecord]:
    """识别成长机会。

    G2 改造：
    - requiredScore 不再硬编码（72/62/70/64/66/74），改为读组织 baseline
      （`_organization_baseline_score`）。等数据中心提供 role_anchor 后，
      可以把 baseline 函数换成读 `role_profile_snapshot`。
    - 优先输出"该 ability 完全没有客观证据"的成长机会；这部分判断基于
      `objective_evidence`（exp_wall + memory + documents），比单看 ledger
      关键词扫描更可靠。
    """
    score_map = {item.abilityKey: item for item in ability_scores}
    candidates: dict[str, GrowthAbilityGapRecord] = {}
    objective_evidence = objective_evidence or []
    objective_count = _objective_count_by_ability(objective_evidence)

    # baseline 计算缓存（避免对每个 push_candidate 重复查 SQL）
    baseline_cache: dict[str, int] = {}

    def baseline_for(ability_key: str) -> int:
        if ability_key not in baseline_cache:
            baseline_cache[ability_key] = (
                _organization_baseline_score(db, ability_key) if db is not None else _BASELINE_FALLBACK_SCORE
            )
        return baseline_cache[ability_key]

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

    # ── 主通路：基于客观证据缺失反推成长机会 ───────────────────
    # 一个 ability 如果在 exp_wall / memory / documents 里近期没有任何
    # 真实产出对象，就是最值得提示的成长机会，比"差几分"更有说服力。
    for ability_key in ABILITY_ORDER:
        current = score_map.get(ability_key)
        if not current:
            continue
        if objective_count.get(ability_key, 0) == 0:
            push_candidate(
                ability_key,
                required_score=baseline_for(ability_key),
                reason="近期没有这方面的真实产出对象（金句/记忆/文档），可以挑一次相关任务做深一点。",
                source_label="数据中心客观证据",
                source_type="objective_evidence_missing",
                source_id=f"missing:{ability_key}",
            )

    # ── 辅助通路：基于 recommendations / captures / highlights 补 reason ──
    for recommendation in recommendations:
        push_candidate(
            recommendation.abilityKey,
            required_score=baseline_for(recommendation.abilityKey),
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
                required_score=baseline_for(ability_key),
                reason=reason,
                source_label=source_label or "",
                source_type=source_type,
                source_id=source_id,
            )

    def push_highlights(
        highlights: list[GrowthProjectHighlightRecord],
        *,
        default_type: str,
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
                    required_score=baseline_for(ability_key),
                    reason=reason,
                    source_label=source_label,
                    source_type=source_type,
                    source_id=source_id,
                )

    push_highlights(project_highlights, default_type="client", reason_prefix="当前项目正在持续消耗这项能力：")
    push_highlights(event_line_highlights, default_type="event_line", reason_prefix="当前事件线正在持续要求这项能力：")
    push_highlights(strategic_highlights, default_type="strategic_focus", reason_prefix="当前战略线明确要求继续补强这项能力：")

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
    # K3：能力分主算法切换到真实数据源（ledger 仅做时间线展示用）
    # 旧 ledger 严重失真：3/6 能力 100% 来自徽章解锁自动送 XP。新算法直接读
    # weekly_reviews / handbook / tasks / commitments / risk_signals 等原始
    # 表，按 ABILITY_WEIGHTS_BY_SOURCE 配置矩阵折算。
    source_contributions = _count_source_events(db, user_id)
    totals = _compute_ability_totals_from_sources(source_contributions)
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

    # K3：旧 G1 客观证据加权保留为弱叠加（避免双计——新算法已经把
    # document/memory 纳入 source_contributions），仅 exp_wall_quote
    # 这种"被组织看见"的强信号继续用 G1 路径补强。
    objective_evidence = _collect_objective_evidence(db, user_id)

    ability_scores: list[GrowthAbilityScoreRecord] = []
    total_xp = 0
    weekly_xp = 0
    for ability_key in ABILITY_ORDER:
        total = totals.get(ability_key, 0)
        total_xp += total
        week_delta = weekly.get(ability_key, 0)
        weekly_xp += week_delta
        stage, next_stage = _ability_stage(total)
        # evidence 优先用新算法（真实数据源拼一句话），其次回退到 G1 客观证据，
        # 最后才回退到 ledger 关键词 reason。
        ledger_fallback = next(
            (item.reason for item in recent_entries if item.abilityKey == ability_key and item.reason.strip()),
            "",
        )
        objective_text = _pick_objective_evidence_text(
            objective_evidence, ability_key, fallback=ledger_fallback,
        )
        recent_evidence = _pick_real_source_evidence_text(
            source_contributions, ability_key, fallback=objective_text,
        )
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

    # N1-N3: 按 role_tier 替换能力标签（label）；abilityKey 保持不变
    role_tier = _resolve_user_role_tier(db, user_id)
    ability_scores = _apply_role_label_override(ability_scores, role_tier)

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
        sourceCoverage=_build_source_coverage(db, user_id, objective_evidence=objective_evidence),
        socialFeedback=_build_social_feedback(db, user_id),
        abilityTrends=_get_or_build_ability_trends_lazy(db, user_id, ability_scores, profile_map),
        dailyActivity=_build_daily_activity(db, user_id, days=84),
        commitmentSummary=_build_commitment_summary(db, user_id),
        businessCoverage=_build_business_coverage(db, user_id),
        reviewStreak=_build_review_streak(db, user_id),
        workTypeDistribution=_build_work_type_distribution(db, user_id),
        impactCurve=_build_impact_curve(db, user_id),
        learning=_build_internal_learning_picks(db, user_id, ability_scores, profile_map),
        peerComparison=_build_peer_comparison(db, user_id, ability_scores),
        projectGrowthHighlights=project_highlights,
        eventLineGrowthHighlights=event_line_highlights,
        strategicAlignmentHighlights=strategic_highlights,
        pendingCaptures=pending_captures,
        currentFocusActions=_build_focus_actions(recommendations),
        abilityGaps=_build_ability_gaps(
            ability_scores,
            recommendations,
            pending_captures,
            project_highlights,
            event_line_highlights,
            strategic_highlights,
            db=db,
            objective_evidence=objective_evidence,
        ),
        updatedAt=_now_iso(),
    )
