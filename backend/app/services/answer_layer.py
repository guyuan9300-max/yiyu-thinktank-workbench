from __future__ import annotations

import re
from typing import Iterable

from app.models import (
    AiStructuredResponse,
    AnswerPlanRecord,
    AnswerPolicyRecord,
    BusinessProfileSlotsRecord,
    EvidenceItem,
    PageContextPackRecord,
    QuestionFocusFrameRecord,
    RouteDecisionRecord,
    StrategyProfileSlotsRecord,
)

_BUSINESS_TOKENS = ("核心业务", "主营业务", "业务是什么", "业务模式", "主要服务", "服务对象", "核心产品", "产品服务")
_STRATEGY_TOKENS = ("最新战略", "战略是什么", "战略方向", "2026战略", "未来战略", "战略重点", "发展方向")

_BUSINESS_MODULE_PATTERNS: dict[str, tuple[str, ...]] = {
    "资源支持": ("资源支持", "资金支持", "资助", "资源对接", "资源链接"),
    "项目服务": ("项目服务", "公益服务", "项目执行", "服务交付", "项目支持"),
    "平台协作": ("平台", "生态", "协作", "伙伴", "网络", "枢纽"),
    "能力建设": ("培训", "能力建设", "赋能", "课程", "工作坊"),
    "心理健康": ("心理", "心理健康", "心理服务", "儿童心理"),
    "教育支持": ("教育", "学校", "教师", "学生", "儿童"),
    "传播倡导": ("传播", "倡导", "品牌", "公众", "影响力"),
}
_SERVICE_OBJECT_PATTERNS: dict[str, tuple[str, ...]] = {
    "公益组织": ("公益组织", "社会组织", "机构"),
    "基金会": ("基金会", "资助方"),
    "学校与教师": ("学校", "教师"),
    "儿童与家庭": ("儿童", "家庭", "青少年"),
}
_PRODUCT_PROGRAM_PATTERNS: dict[str, tuple[str, ...]] = {
    "心理支持服务": ("心理服务", "心理健康", "心理课程"),
    "培训课程": ("培训", "课程", "工作坊"),
    "协作平台": ("平台", "协作网络", "生态平台"),
    "项目方案": ("项目方案", "项目服务", "服务项目"),
}
_DELIVERY_MODEL_PATTERNS: dict[str, tuple[str, ...]] = {
    "培训赋能交付": ("培训", "赋能", "课程"),
    "项目制交付": ("项目执行", "项目服务", "项目支持"),
    "平台协同交付": ("平台", "协作", "网络"),
    "联合伙伴交付": ("合作伙伴", "伙伴协作", "联合执行"),
}
_STRATEGY_DIRECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "能力建设": ("能力建设", "赋能", "培训", "专业化"),
    "生态协作": ("生态", "协作", "伙伴", "联盟", "网络"),
    "数字化": ("数字化", "平台化", "系统", "数据"),
    "筹资与资源": ("筹款", "资源", "资助", "基金", "募资"),
    "品牌传播": ("传播", "品牌", "影响力", "公众"),
    "服务深化": ("服务深化", "项目深化", "服务升级", "交付"),
}

_INTRODUCTORY_INTENTS = {"intro_profile", "project_intro"}
_ACTION_ORIENTED_INTENTS = {"status_progress", "next_actions", "task_next_action", "meeting_summary", "task_context"}


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _resolve_intro_display_name(prompt: str) -> str:
    text = str(prompt or "").strip()
    for pattern in (
        r"(?:介绍|了解一下|说说|帮我介绍)\s*([^\n，。；：:]{2,24}(?:基金会|机构|组织))",
        r"([^\n，。；：:]{2,24}(?:基金会|机构|组织))",
    ):
        match = re.search(pattern, text)
        if match:
            candidate = re.sub(r"\s+", "", match.group(1)).strip("“”\"' ")
            if candidate:
                return candidate
    return ""


def _build_intro_profile_seed(prompt: str, evidence_highlights: list[EvidenceItem]) -> str:
    display_name = _resolve_intro_display_name(prompt) or "该机构"
    corpus = " ".join(f"{item.title or ''} {item.excerpt or ''}" for item in evidence_highlights[:6])

    if any(token in corpus for token in ("儿童青少年", "青少年")) and any(token in corpus for token in ("心理健康", "心理教育")):
        if "基金会" in display_name:
            lead = f"{display_name}是一家以儿童青少年心理健康与心理教育为核心议题的公益基金会。"
        else:
            lead = f"从当前资料看，{display_name}主要围绕儿童青少年心理健康与心理教育议题持续展开工作。"
    elif any(token in corpus for token in ("心理健康", "心理教育", "教师赋能", "心灵魔法学院")):
        lead = f"从当前资料看，{display_name}主要围绕心理健康教育、关系支持与教师赋能持续展开工作。"
    else:
        lead = f"从当前资料看，{display_name}是一家持续围绕教育支持与项目协同展开工作的机构。"

    if any(token in corpus for token in ("关系支持系统", "关系支持之网", "学校、家庭", "学校,家庭", "教师与社区", "普惠")):
        return lead.rstrip("。") + " 它更像是在做一套把学校、家庭、教师与社区连接起来的关系支持系统。"
    if any(token in corpus for token in ("可被复制", "可持续运行", "标准化", "课程资料", "配套培训")):
        return lead.rstrip("。") + " 它试图把心理支持做成可复制、可持续运行的教育支持能力，而不是一次性活动。"
    return lead


def _extract_time_boundary(text: str) -> str:
    cleaned = _clean_text(text)
    year_match = re.search(r"(20\d{2})", cleaned)
    if year_match:
        return f"当前证据时间边界主要落在 {year_match.group(1)} 年。"
    if any(token in cleaned for token in ("年度", "今年", "当前", "最新", "未来")):
        return "当前证据以“当前/年度阶段”信息为主。"
    return ""


def _collect_match_labels(
    *,
    text: str,
    patterns: dict[str, tuple[str, ...]],
    max_items: int,
) -> list[str]:
    labels: list[str] = []
    for label, tokens in patterns.items():
        if any(token in text for token in tokens):
            labels.append(label)
        if len(labels) >= max_items:
            break
    return labels


def _resolve_intent(prompt: str, route_decision: RouteDecisionRecord, page_context: PageContextPackRecord) -> str:
    normalized = re.sub(r"\s+", "", str(prompt or "").lower())
    if (
        route_decision.intent == "official_judgment_registry"
        or page_context.intent == "official_judgment_registry"
        or _contains_any(normalized, ("正式判断", "已批准", "系统里", "系统内", "official"))
    ):
        return "official_judgment_registry"
    return "general"


def is_introductory_answer_intent(intent: str | None) -> bool:
    return str(intent or "").strip() in _INTRODUCTORY_INTENTS


def should_include_answer_boundary(intent: str | None) -> bool:
    normalized = str(intent or "").strip()
    if not normalized:
        return True
    return not is_introductory_answer_intent(normalized)


def should_include_answer_next_actions(intent: str | None) -> bool:
    normalized = str(intent or "").strip()
    if not normalized:
        return True
    return normalized in _ACTION_ORIENTED_INTENTS


def should_include_operational_context_points(intent: str | None) -> bool:
    normalized = str(intent or "").strip()
    if not normalized:
        return True
    return normalized in _ACTION_ORIENTED_INTENTS


def should_include_answer_action_cards(intent: str | None) -> bool:
    return should_include_answer_next_actions(intent)


def should_fallback_to_candidate_judgments(
    *,
    intent: str | None,
    question_focus_frame: QuestionFocusFrameRecord | dict[str, object] | None = None,
) -> bool:
    if isinstance(question_focus_frame, QuestionFocusFrameRecord):
        focus_goal = str(question_focus_frame.goal or "").strip()
        focus_facet = str(question_focus_frame.subjectFacet or "").strip()
    elif isinstance(question_focus_frame, dict):
        focus_goal = str(question_focus_frame.get("goal") or "").strip()
        focus_facet = str(question_focus_frame.get("subjectFacet") or "").strip()
    else:
        focus_goal = ""
        focus_facet = ""

    if focus_goal in {"define", "explain", "evidence"} and focus_facet in {"identity", "project", "method", "strategy"}:
        return False
    normalized = str(intent or "").strip()
    return normalized not in _INTRODUCTORY_INTENTS


def extract_business_profile_slots(evidence: list[EvidenceItem]) -> BusinessProfileSlotsRecord:
    modules: list[str] = []
    service_objects: list[str] = []
    products: list[str] = []
    delivery: list[str] = []
    refs: list[str] = []

    for item in evidence[:18]:
        merged = _clean_text(f"{item.title} {item.sectionLabel or ''} {item.excerpt}")
        modules.extend(_collect_match_labels(text=merged, patterns=_BUSINESS_MODULE_PATTERNS, max_items=7))
        service_objects.extend(_collect_match_labels(text=merged, patterns=_SERVICE_OBJECT_PATTERNS, max_items=4))
        products.extend(_collect_match_labels(text=merged, patterns=_PRODUCT_PROGRAM_PATTERNS, max_items=5))
        delivery.extend(_collect_match_labels(text=merged, patterns=_DELIVERY_MODEL_PATTERNS, max_items=4))
        if item.title:
            refs.append(item.title)
        elif item.path:
            refs.append(item.path)

    unknowns: list[str] = []
    if not modules:
        unknowns.append("当前资料不足以稳定归纳核心业务板块。")
    if not service_objects:
        unknowns.append("服务对象与边界信息仍不完整。")

    return BusinessProfileSlotsRecord(
        businessModules=list(dict.fromkeys([item for item in modules if item]))[:4],
        serviceObjects=list(dict.fromkeys([item for item in service_objects if item]))[:3],
        productsOrPrograms=list(dict.fromkeys([item for item in products if item]))[:4],
        deliveryModel=list(dict.fromkeys([item for item in delivery if item]))[:3],
        evidenceRefs=list(dict.fromkeys([item for item in refs if item]))[:6],
        unknowns=unknowns[:3],
    )


def extract_strategy_profile_slots(evidence: list[EvidenceItem]) -> StrategyProfileSlotsRecord:
    directions: list[str] = []
    actions: list[str] = []
    risks: list[str] = []
    refs: list[str] = []
    boundary = ""

    for item in evidence[:18]:
        merged = _clean_text(f"{item.title} {item.sectionLabel or ''} {item.excerpt}")
        directions.extend(_collect_match_labels(text=merged, patterns=_STRATEGY_DIRECTION_PATTERNS, max_items=6))
        if any(token in merged for token in ("行动", "计划", "推进", "里程碑", "执行", "安排", "重点任务")):
            actions.append(merged[:80])
        if any(token in merged for token in ("风险", "卡点", "挑战", "不确定", "待确认", "缺口")):
            risks.append(merged[:80])
        if not boundary:
            boundary = _extract_time_boundary(merged)
        if item.title:
            refs.append(item.title)
        elif item.path:
            refs.append(item.path)

    unknowns: list[str] = []
    if not directions:
        unknowns.append("战略方向证据仍偏弱，需要补充会议纪要或战略材料。")
    if not boundary:
        unknowns.append("当前资料未给出明确时间边界。")
        boundary = "当前资料未给出明确时间边界。"

    return StrategyProfileSlotsRecord(
        strategicDirections=list(dict.fromkeys([item for item in directions if item]))[:4],
        keyActions=list(dict.fromkeys([item for item in actions if item]))[:4],
        timeBoundary=boundary,
        risks=list(dict.fromkeys([item for item in risks if item]))[:3],
        evidenceRefs=list(dict.fromkeys([item for item in refs if item]))[:6],
        unknowns=unknowns[:3],
    )


def build_answer_plan(
    *,
    prompt: str,
    page_context: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
    answer_policy: AnswerPolicyRecord,
) -> AnswerPlanRecord:
    intent = _resolve_intent(prompt, route_decision, page_context)
    allow_candidate = answer_policy.answerLevel in {"candidate", "evidence_based", "fallback"}
    answer_shape = "insufficient" if answer_policy.answerLevel == "insufficient" else "open_answer"
    # P2.14 FREEZE(answer-shaping-answer-plan-bounds): 主回答链当前虽然已经切到 open_answer，
    # 但 maxEvidenceItems / maxAnswerChars 仍然是旧回答塑形半层留下的读取边界。
    # 先冻结为待拆层，不再继续围绕 intent 增加新的预算分支。
    max_evidence_items = 24
    max_answer_chars = 12000
    if intent == "official_judgment_registry":
        max_evidence_items = 10
        max_answer_chars = 4200

    return AnswerPlanRecord(
        intent=intent,
        answerShape=answer_shape,  # type: ignore[arg-type]
        requiredSections=[],
        mustStartWithDirectAnswer=True,
        mustCiteEvidence=True,
        mustDiscloseBoundary=False,
        allowCandidateJudgment=allow_candidate,
        maxEvidenceItems=max_evidence_items,
        maxAnswerChars=max_answer_chars,
        routeReason=route_decision.routeReason or answer_policy.reason,
    )


def build_answer_material(
    *,
    prompt: str,
    page_context: PageContextPackRecord,
    route_decision: RouteDecisionRecord,
    retrieval_evidence: list[EvidenceItem],
    answer_plan: AnswerPlanRecord,
    question_focus_frame: QuestionFocusFrameRecord | dict[str, object] | None = None,
) -> "AnswerMaterialRecord":
    del route_decision
    from app.models import AnswerMaterialRecord

    # P2.14 FREEZE(answer-shaping-answer-material-cut): 主回答材料当前仍然从 retrieval_evidence 前 N 条切片，
    # 这是旧塑形层对“模型能看到多少资料”的直接裁剪。先冻结，不在这层继续长新 summary/feed 规则。
    evidence_highlights = retrieval_evidence[: max(1, answer_plan.maxEvidenceItems)]

    key_facts: list[str] = []
    if answer_plan.intent == "official_judgment_registry":
        for item in page_context.officialJudgments[:3]:
            summary = _clean_text(str(item.get("summary") or item.get("topic") or ""))
            if summary:
                key_facts.append(summary)
        if not key_facts and should_fallback_to_candidate_judgments(
            intent=answer_plan.intent,
            question_focus_frame=question_focus_frame,
        ):
            for item in page_context.candidateJudgments[:3]:
                summary = _clean_text(str(item.get("summary") or item.get("topic") or ""))
                if summary:
                    key_facts.append(summary)
    if not key_facts:
        for item in evidence_highlights[:4]:
            excerpt = _clean_text(item.excerpt)
            if excerpt:
                key_facts.append(excerpt)

    structured_points: list[str] = []
    next_actions: list[str] = []
    boundary_notes: list[str] = []

    source_labels: list[str] = []
    for item in evidence_highlights:
        if item.title:
            source_labels.append(item.title)
        elif item.path:
            source_labels.append(item.path)
    source_labels = list(dict.fromkeys([_clean_text(item) for item in source_labels if _clean_text(item)]))

    business_profile: BusinessProfileSlotsRecord | None = None
    strategy_profile: StrategyProfileSlotsRecord | None = None
    if answer_plan.intent == "official_judgment_registry":
        approved_items: list[str] = []
        for item in page_context.officialJudgments[:3]:
            summary = _clean_text(str(item.get("summary") or item.get("topic") or item.get("statement") or ""))
            if summary:
                approved_items.append(summary)
        if approved_items:
            seed = "请优先回答系统内已批准正式判断，并把候选内容与正式内容分开。"
        else:
            seed = "当前系统内没有已批准正式判断，请如实说明并避免把候选材料写成正式事实。"
    else:
        # P2.14 FREEZE(answer-shaping-direct-seed): 主回答 directAnswerSeed 保持极简开放版。
        # 不允许恢复 intent 级软引导、固定结构、边界块或编号模板。
        seed = "请直接回答用户问题，可以自由组织结构和长度；只基于资料判断，不要编造，也不要暴露系统过程。"

    return AnswerMaterialRecord(
        directAnswerSeed=seed,
        keyFacts=list(dict.fromkeys(key_facts))[:8],
        structuredPoints=list(dict.fromkeys(structured_points))[:8],
        evidenceHighlights=evidence_highlights,
        stateHighlights=list(dict.fromkeys([*key_facts[:3], *structured_points[:3]]))[:6],
        boundaryNotes=list(dict.fromkeys([_clean_text(item) for item in boundary_notes if _clean_text(item)]))[:6],
        missingContext=list(dict.fromkeys(page_context.missingContext[:6])),
        nextActions=list(dict.fromkeys(next_actions))[:6],
        sourceLabels=source_labels[:8],
        businessProfile=business_profile,
        strategyProfile=strategy_profile,
    )


def build_grounded_answer_context(
    *,
    answer_plan: AnswerPlanRecord,
    answer_material: "AnswerMaterialRecord",
    prompt: str = "",
) -> str:
    # P2.14 FREEZE(answer-shaping-grounded-context): grounded context 当前只保留用户问题与 evidence lines。
    # 不允许重新喂回 keyFacts / previewSummary / workTrace / stateAnswerSections / answerPresentation 等二次总结对象。
    evidence_lines = [
        f"- {item.title or '证据'}：{_clean_text(item.excerpt)}"
        for item in answer_material.evidenceHighlights[: answer_plan.maxEvidenceItems]
        if _clean_text(item.excerpt)
    ]
    blocks = [
        f"【用户问题】\n{prompt or '（未提供）'}",
        "【回答原则】\n- 直接回答用户问题\n- 可以自由组织结构和长度\n- 只基于资料判断，不要编造\n- 不要暴露系统过程或检索过程",
        "【原始文档资料包】\n" + "\n".join(evidence_lines or ["- 当前无可引用资料摘录。"]),
    ]
    return "\n".join(blocks)


def build_local_answer_fallback(
    *,
    prompt: str,
    answer_plan: AnswerPlanRecord,
    answer_material: "AnswerMaterialRecord",
    failure_detail: str | None = None,
) -> AiStructuredResponse:
    evidence_lines = [
        f"{item.title or '资料'}：{_clean_text(item.excerpt)}"
        for item in answer_material.evidenceHighlights[:6]
        if _clean_text(item.excerpt)
    ]
    fact_lines = [item for item in answer_material.keyFacts[:4] if _clean_text(item)]
    answer_hint = answer_material.directAnswerSeed or "请基于当前材料先给出保守但直接的回答。"
    detail_lines = [*fact_lines, *evidence_lines[:3]]
    if detail_lines:
        content = (
            f"{answer_hint}\n\n"
            + "当前能直接支撑回答的资料包括："
            + "；".join(detail_lines)
            + "。"
        )
    else:
        content = f"{answer_hint}\n\n当前能直接调用的资料仍然有限，请围绕已确认信息保守回答。"
    analysis = "；".join(answer_material.keyFacts[:4]) or "当前事实覆盖有限。"
    if failure_detail:
        analysis = f"{analysis}（模型失败：{failure_detail}）"

    return AiStructuredResponse(
        content=content,
        judgment=f"intent={answer_plan.intent}，按开放式本地回退生成。",
        analysis=analysis,
        actions="可继续围绕当前对象追问更具体的问题。",
        timeline=f"问题：{prompt}",
    )
