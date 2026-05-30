from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.models import (
    HierarchyReportRecord,
    OrgModelProfileRecord,
    OrgRoleProcessTemplateRecord,
    OrganizationDnaModuleRecord,
    ReviewActionCardRecord,
    ReviewDashboardCardTargetRecord,
    ReviewDashboardEvidenceRefRecord,
    ReviewDepartmentConfigRecord,
    ReviewGovernanceSettingsRecord,
    WeeklyReviewTaskEntryRecord,
)
from app.services.knowledge_base import tokenize
from app.services.review_analysis import build_hierarchy_report_from_analysis, build_weekly_review_analysis

DEPARTMENT_STRATEGY_PROFILES: dict[str, dict[str, object]] = {
    "咨询策略部": {
        "headline": "这周推进的不是文稿，而是“场景判断力的产品化”",
        "core": "本周真正推进的，不是几份备忘录或提纲，而是把复杂客户现场压缩成可行动判断的能力。这条能力链决定了益语后续能否把筹款、传播、项目设计等一线问题沉淀成可复用的方法。",
        "risk": "如果下周仍主要停留在提纲、初稿和零散讨论层，咨询判断就很难继续沉淀成标准件，部门会出现“看起来很忙、但难以复用”的问题。",
        "focus_areas": ["场景判断力产品化", "客户诊断链收束", "案例骨架沉淀", "标准件雏形"],
        "actions": ["把 1-2 条典型客户判断链整理成可复用模板。", "优先补齐关键项目的一线资料与判断依据。", "把本周判断沉淀成后续可直接复用的案例骨架。"],
    },
    "科技发展部": {
        "headline": "这周第一次把“顾问天天用的能力”做成了可运行骨架",
        "core": "本周最重要的进展，不是又做了一个功能点，而是开始把顾问天天会用的工作习惯收束成可运行骨架。只要这条主线成立，益语就能继续沿着“先顾问自用、再客户可用”的路径往前走。",
        "risk": "当前最大的风险不是功能不够多，而是如果界面和流程重新变复杂，团队会重新掉回“像项目管理软件而不像场景应用”的老路。",
        "focus_areas": ["顾问自用骨架", "极简任务闭环", "低迁移成本落地", "深分析后台"],
        "actions": ["优先把顾问高频动作继续做薄、做顺。", "用真实任务闭环验证功能，而不是继续堆复杂配置。", "盯住客户低学习成本和后台分析深度这两个方向不要跑偏。"],
    },
    "信息数据部": {
        "headline": "这周搭的不是报表，而是“管理信号引擎”",
        "core": "本周推进的核心，不只是导入结构、规则和统计口径，而是在为益语搭一层能把任务行为、客户资料和周复盘转成管理判断的信号引擎。没有这一层，高层仍然很难拿到值得信的趋势、预警和复盘依据。",
        "risk": "如果这条线只停留在数据整理和字段堆叠，而没有继续形成稳定的信号解释能力，部门就会停在“有数据、没判断”的半成品状态。",
        "focus_areas": ["管理信号引擎", "结构化导入规则", "预警阈值口径", "组织级判断模板"],
        "actions": ["把关键指标继续压缩成管理者真正会看的判断信号。", "先稳定完成率、延期率、支持请求率等核心口径。", "继续清理低质量数据源，避免噪音稀释判断。"],
    },
    "客户服务部": {
        "headline": "这周把市场真实阻力翻译成了产品边界",
        "core": "本周真正有价值的，不是单纯跟了多少客户，而是把客户为什么不用任务系统、为什么推进会卡住这件事逐步翻译成产品边界。只有这一层足够真实，产品和咨询两侧的动作才不会脱离客户现场。",
        "risk": "如果前线反馈继续只停留在零散抱怨，而没有被整理成可执行的产品约束和部署策略，团队就会反复在同样的问题上消耗。",
        "focus_areas": ["前线阻力翻译", "低学习成本落地", "部署顾虑消化", "客户使用闭环"],
        "actions": ["把客户最常见的部署顾虑整理成明确的处理话术。", "继续验证哪些录入动作是真正会劝退客户的。", "把前线反馈收束成产品团队可直接响应的边界清单。"],
    },
}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _department_member_names(department: ReviewDepartmentConfigRecord) -> set[str]:
    return {member.fullName.strip().lower() for member in department.members if member.fullName.strip()}


def _department_member_ids(department: ReviewDepartmentConfigRecord) -> set[str]:
    return {member.id.strip() for member in department.members if member.id.strip()}


def _item_owner_id(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.ownerId or "").strip()


def _item_owner_name(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.ownerName or "").strip()


def _item_list_name(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.listName or "").strip()


def _item_org_context(item: WeeklyReviewTaskEntryRecord):
    return item.taskSnapshot.orgContext


def _item_department_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.departmentId if context else "") or ""


def _item_role_template_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.roleTemplateId if context else "") or ""


def _item_control_level(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.controlLevel if context else "") or ""


def _item_needs_review(item: WeeklyReviewTaskEntryRecord) -> bool:
    context = _item_org_context(item)
    if not context:
        return False
    return bool(context.needsReview or context.approvalState == "pending" or (context.blockedAtStep or "").strip())


def _item_is_cross_department(item: WeeklyReviewTaskEntryRecord) -> bool:
    context = _item_org_context(item)
    return bool(context and context.isCrossDepartment)


def _item_project_context(item: WeeklyReviewTaskEntryRecord):
    return item.taskSnapshot.projectContext


def _item_event_line_id(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.eventLineId or "").strip()


def _item_event_line_name(item: WeeklyReviewTaskEntryRecord) -> str:
    return (item.taskSnapshot.eventLineName or "").strip()


def _item_focus_item_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.focusItemId if context else "") or ""


def _item_department_plan_item_id(item: WeeklyReviewTaskEntryRecord) -> str:
    context = _item_org_context(item)
    return (context.departmentPlanItemId if context else "") or ""


def _is_agent_item(item: WeeklyReviewTaskEntryRecord) -> bool:
    owner_id = _item_owner_id(item)
    return owner_id.startswith("agent:")


def _item_text(item: WeeklyReviewTaskEntryRecord) -> str:
    parts = [
        item.taskSnapshot.title,
        item.note,
        item.structuredNote.reflection,
        item.structuredNote.lightweightTag,
        item.structuredNote.progress,
        item.structuredNote.successReason,
        item.structuredNote.blockerReason,
        item.structuredNote.supportNeeded,
        item.structuredNote.nextAction,
        item.taskSnapshot.listName,
        " ".join(tag.name for tag in item.taskSnapshot.tags),
    ]
    return _clean_text(" ".join(part for part in parts if part))


def _is_completed_item(item: WeeklyReviewTaskEntryRecord) -> bool:
    status = (item.structuredNote.completionStatus or "").strip()
    if status in {"done_on_time", "done_late"}:
        return True
    return (item.taskSnapshot.status or "").strip() == "done"


def _has_blocker_signal(item: WeeklyReviewTaskEntryRecord) -> bool:
    return bool(
        item.structuredNote.lightweightTag.strip()
        or item.structuredNote.blockerReason.strip()
        or item.structuredNote.supportNeeded.strip()
    )


def _representative_titles(items: list[WeeklyReviewTaskEntryRecord], limit: int = 3) -> list[str]:
    seen: set[str] = set()
    titles: list[str] = []
    for item in items:
        normalized = _clean_text(item.taskSnapshot.title)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        titles.append(f"{normalized[:20]}…" if len(normalized) > 20 else normalized)
        if len(titles) >= limit:
            break
    return titles


def _clean_lines(values: list[str], limit: int = 3) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _clean_text(value)
        if not normalized or normalized in seen:
            continue
        if len(normalized) > 80:
            normalized = normalized[:80].rstrip("，、；： ") + "…"
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _overview_line(title: str, body: str) -> str:
    clean_title = _clean_text(title).rstrip("：:｜")
    clean_body = _clean_text(body)
    if len(clean_body) > 88:
        clean_body = clean_body[:87].rstrip("，、；：: ") + "…"
    if not clean_title:
        return clean_body
    if not clean_body or clean_body == clean_title:
        return clean_title
    return f"{clean_title}｜{clean_body}"


def _event_line_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, item.whatHappenedThisWeek or item.currentState or item.whatThisLineIs)
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _judgment_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "whatHappened", "") or getattr(item, "whyItMatters", "") or getattr(item, "nextWeekFocus", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _judgment_blocker_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "coreBlocker", "") or getattr(item, "riskIfIgnored", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _judgment_action_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "minimumAction", "") or getattr(item, "nextWeekFocus", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _risk_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines([_overview_line(item.title, item.statement) for item in (items or [])[:limit]], limit=limit)


def _opportunity_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines([_overview_line(item.title, item.statement) for item in (items or [])[:limit]], limit=limit)


def _action_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines([_overview_line("建议动作", item) for item in items[:limit]], limit=limit)


def _judgment_management_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "managerImplication", "") or getattr(item, "whyItMatters", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _judgment_focus_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, getattr(item, "whatHappened", "") or getattr(item, "nextWeekFocus", ""))
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _trend_overview_lines(items, limit: int = 4) -> list[str]:
    return _clean_lines(
        [
            _overview_line(item.title, item.statement)
            for item in (items or [])[:limit]
        ],
        limit=limit,
    )


def _event_line_rollup(items: list[WeeklyReviewTaskEntryRecord]) -> dict[str, object]:
    groups: dict[str, list[WeeklyReviewTaskEntryRecord]] = {}
    for item in items:
        event_line_id = _item_event_line_id(item)
        if not event_line_id:
            continue
        groups.setdefault(event_line_id, []).append(item)
    names = _clean_lines([_item_event_line_name(group[0]) or _item_text(group[0]) for group in groups.values()], limit=4)
    multi_task_group_count = sum(1 for group in groups.values() if len(group) >= 2)
    blocked_group_count = sum(1 for group in groups.values() if any(not _is_completed_item(item) for item in group))
    blocked_names = _clean_lines(
        [
            _item_event_line_name(group[0]) or _item_text(group[0])
            for group in groups.values()
            if any(not _is_completed_item(item) for item in group)
        ],
        limit=3,
    )
    return {
        "group_count": len(groups),
        "task_count": sum(len(group) for group in groups.values()),
        "multi_task_group_count": multi_task_group_count,
        "names": names,
        "blocked_group_count": blocked_group_count,
        "blocked_names": blocked_names,
    }


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _clean_text(text)
    normalized_phrase = _clean_text(phrase)
    if not normalized_text or not normalized_phrase:
        return False
    if normalized_phrase in normalized_text:
        return True
    phrase_tokens = {token for token in tokenize(normalized_phrase) if len(token.strip()) >= 2}
    text_tokens = {token for token in tokenize(normalized_text) if len(token.strip()) >= 2}
    return bool(phrase_tokens and text_tokens and phrase_tokens & text_tokens)


def _org_model_indexes(org_model_profile: OrgModelProfileRecord | None) -> dict[str, dict[str, object]]:
    if org_model_profile is None:
        return {
            "departments": {},
            "roles": {},
            "bindings": {},
            "rules": {},
            "reporting": {},
            "processes_by_role": {},
        }
    reporting: dict[str, list[object]] = {}
    for line in org_model_profile.reportingLines:
        reporting.setdefault(line.reportUserId, []).append(line)
    processes_by_role: dict[str, list[OrgRoleProcessTemplateRecord]] = {}
    for template in org_model_profile.roleProcessTemplates:
        if not template.active or not template.roleTemplateId:
            continue
        processes_by_role.setdefault(template.roleTemplateId, []).append(template)
    return {
        "departments": {department.id: department for department in org_model_profile.departments},
        "roles": {role.id: role for role in org_model_profile.roles},
        "bindings": {binding.userId: binding for binding in org_model_profile.bindings},
        "rules": {rule.id: rule for rule in org_model_profile.taskControlRules},
        "reporting": reporting,
        "processes_by_role": processes_by_role,
    }


def _management_signal_bundle(
    items: list[WeeklyReviewTaskEntryRecord],
    *,
    org_model_profile: OrgModelProfileRecord | None,
    department_name: str | None = None,
) -> dict[str, object]:
    indexes = _org_model_indexes(org_model_profile)
    roles_by_id = indexes["roles"]
    bindings_by_user = indexes["bindings"]
    rules_by_id = indexes["rules"]
    reporting_by_report = indexes["reporting"]
    processes_by_role = indexes["processes_by_role"]
    role_drift_hits: list[tuple[WeeklyReviewTaskEntryRecord, object, str]] = []
    review_chain_items: list[WeeklyReviewTaskEntryRecord] = []
    controlled_items: list[WeeklyReviewTaskEntryRecord] = []
    cross_department_items: list[WeeklyReviewTaskEntryRecord] = []
    manager_load_items: list[tuple[WeeklyReviewTaskEntryRecord, object]] = []
    workflow_blocked_hits: list[tuple[WeeklyReviewTaskEntryRecord, OrgRoleProcessTemplateRecord, str]] = []
    overloaded_items: list[WeeklyReviewTaskEntryRecord] = []
    support_need_items: list[WeeklyReviewTaskEntryRecord] = []
    misaligned_items: list[WeeklyReviewTaskEntryRecord] = []
    project_risk_items: list[WeeklyReviewTaskEntryRecord] = []

    for item in items:
        context = _item_org_context(item)
        owner_id = _item_owner_id(item)
        lightweight_tag = item.structuredNote.lightweightTag.strip()
        if lightweight_tag == "工作过度饱和":
            overloaded_items.append(item)
        if lightweight_tag in {"资料不足", "等待他人", "资源不够"} or item.structuredNote.supportNeeded.strip():
            support_need_items.append(item)
        if item.structuredNote.departmentPlanAlignment == "misaligned" or item.structuredNote.organizationPlanAlignment == "misaligned":
            misaligned_items.append(item)
        if _item_project_context(item) and _item_project_context(item).riskSummary.strip():
            project_risk_items.append(item)
        binding = bindings_by_user.get(owner_id)
        role = roles_by_id.get(_item_role_template_id(item) or (binding.primaryRoleId if binding else ""))
        if role and getattr(role, "shouldAvoid", None):
            matched_phrase = next(
                (
                    phrase
                    for phrase in role.shouldAvoid
                    if _contains_phrase(_item_text(item), phrase)
                ),
                None,
            )
            if matched_phrase:
                role_drift_hits.append((item, role, matched_phrase))
        if role:
            process_templates = processes_by_role.get(getattr(role, "id", ""), [])
            candidate_text = _clean_text(
                " ".join(
                    part
                    for part in [
                        _item_text(item),
                        context.blockedAtStep if context else "",
                        item.structuredNote.blockerReason,
                        item.structuredNote.supportNeeded,
                        item.structuredNote.lightweightTag,
                    ]
                    if part
                )
            )
            for template in process_templates:
                matched_phrase = next(
                    (
                        phrase
                        for phrase in [
                            *template.keySteps,
                            template.collaborationStep,
                            template.approvalStep,
                            *template.commonBlockers,
                        ]
                        if phrase and _contains_phrase(candidate_text, phrase)
                    ),
                    None,
                )
                if matched_phrase:
                    workflow_blocked_hits.append((item, template, matched_phrase))
                    break
        if context and context.controlLevel and context.controlLevel != "normal":
            controlled_items.append(item)
        if _item_needs_review(item):
            review_chain_items.append(item)
        if _item_is_cross_department(item):
            cross_department_items.append(item)
        if role and getattr(role, "level", "") in {"department_lead", "organization_lead"}:
            manager_load_items.append((item, role))
        elif owner_id and reporting_by_report.get(owner_id) and _item_needs_review(item):
            # 即使没有明确 leader 岗位，只要任务已进入复核链，也代表上级节点已介入。
            manager_load_items.append((item, role))

    blocked_steps = _clean_lines(
        [(_item_org_context(item).blockedAtStep or "") for item in review_chain_items if _item_org_context(item)],
        limit=2,
    )
    workflow_steps = _clean_lines([matched_phrase for _, _, matched_phrase in workflow_blocked_hits], limit=3)
    support_signals: list[str] = []
    focus_areas: list[str] = []
    suggested_actions: list[str] = []
    summary_lines: list[str] = []
    anonymous_insights: list[str] = []

    if role_drift_hits:
        sample_item, sample_role, sample_phrase = role_drift_hits[0]
        focus_areas.append("职责边界校准")
        support_signals.append(
            f"本周有 {len(role_drift_hits)} 条任务与岗位“不应长期承担”的事项重叠；例如「{_clean_text(sample_item.taskSnapshot.title)}」更像在承担“{sample_phrase}”。"
        )
        suggested_actions.append(
            f"复盘 {len(role_drift_hits)} 条疑似职责偏离任务，把不该长期挂在当前岗位上的执行事务重新分配。"
        )
        anonymous_insights.append(
            f"当前样本里已出现职责边界被挤压的迹象，问题不一定在人，而更可能在分工设计。"
        )
        summary_lines.append(
            f"样本中有 {len(role_drift_hits)} 条任务开始触碰岗位“不应长期承担”的事项，说明职责边界正在被执行需求挤压。"
        )

    if review_chain_items:
        focus_areas.append("汇报链与确认链")
        step_text = f" 当前显性的待确认步骤包括：{'、'.join(blocked_steps)}。" if blocked_steps else ""
        support_signals.append(
            f"本周有 {len(review_chain_items)} 条任务进入待复核或待确认状态，阻力更像出在汇报 / 审批链，而不只是执行速度。{step_text}".strip()
        )
        suggested_actions.append("把待复核任务逐条对照确认节点，缩短不必要的上报和协作确认链。")
        summary_lines.append(
            f"另有 {len(review_chain_items)} 条任务卡在复核或确认链上，当前需要优先判断卡的是哪一层汇报关系。"
        )

    if workflow_blocked_hits:
        focus_areas.append("流程卡点")
        workflow_text = f" 目前高频卡点包括：{'、'.join(workflow_steps)}。" if workflow_steps else ""
        support_signals.append(
            f"已有 {len(workflow_blocked_hits)} 条任务开始集中卡在岗位流程的固定节点，而不只是零散执行波动。{workflow_text}".strip()
        )
        suggested_actions.append("优先复盘对应岗位流程模板中的协作/审批步骤，确认是步骤设计问题还是角色缺位。")
        anonymous_insights.append("当前阻力开始聚集到固定流程节点，说明问题可能不在个体，而在流程设计。")
        summary_lines.append(
            f"同时已有 {len(workflow_blocked_hits)} 条任务暴露出岗位流程固定节点的卡点，需优先判断流程本身是否过长或协作位缺失。"
        )

    if controlled_items:
        control_levels = Counter(_item_control_level(item) for item in controlled_items if _item_control_level(item))
        control_text = "、".join(
            f"{level} {count} 条"
            for level, count in control_levels.items()
        )
        focus_areas.append("任务控制级别")
        support_signals.append(
            f"本周有 {len(controlled_items)} 条任务受到 leader / 部门 / 机构控制规则约束，其中控制级别分布为：{control_text}。"
        )
        suggested_actions.append("检查关键任务的控制级别是否设置过重，确认哪些修改权限可以下放。")
        summary_lines.append(
            f"控制规则正在真实影响推进节奏；当前共有 {len(controlled_items)} 条任务受控。"
        )

    if cross_department_items:
        focus_areas.append("跨部门协作")
        support_signals.append(
            f"本周有 {len(cross_department_items)} 条任务属于跨部门协作，{len([item for item in cross_department_items if _item_needs_review(item)])} 条同时伴随复核需求。"
        )
        suggested_actions.append("把跨部门任务明确到单一确认人，避免多人都“知道”但没人拍板。")
        summary_lines.append(
            f"跨部门任务已有 {len(cross_department_items)} 条，说明当前问题不止在单部门内部。"
        )

    if manager_load_items and len(manager_load_items) >= max(2, len(items) // 2 or 1):
        focus_areas.append("管理负荷")
        support_signals.append(
            f"{department_name or '当前范围'}有 {len(manager_load_items)} 条样本直接挂在管理岗或需上级节点介入，需警惕负责人被执行事务持续挤占。"
        )
        suggested_actions.append("把可下放的执行性事项从管理岗手里移出，保留负责人做判断、协调和拍板。")
        summary_lines.append(
            f"当前不少样本直接压在管理岗或上级复核节点上，管理负荷已经开始显性化。"
        )

    if overloaded_items:
        focus_areas.append("容量过载")
        support_signals.append(
            f"本周有 {len(overloaded_items)} 条任务直接标记为“工作过度饱和”，当前更像容量顶满，而不只是执行节奏问题。"
        )
        suggested_actions.append("先做任务取舍和容量重排，不要在已过载状态下继续叠加新任务。")
        summary_lines.append(
            f"样本里已有 {len(overloaded_items)} 条任务直接暴露出容量过载信号。"
        )

    return {
        "focus_areas": _clean_lines(focus_areas, limit=4),
        "support_signals": _clean_lines(support_signals, limit=4),
        "suggested_actions": _clean_lines(suggested_actions, limit=4),
        "summary_lines": _clean_lines(summary_lines, limit=4),
        "anonymous_insights": _clean_lines(anonymous_insights, limit=2),
        "role_drift_count": len(role_drift_hits),
        "review_chain_count": len(review_chain_items),
        "controlled_count": len(controlled_items),
        "cross_department_count": len(cross_department_items),
        "manager_load_count": len(manager_load_items),
        "workflow_blocked_count": len(workflow_blocked_hits),
        "overload_count": len(overloaded_items),
        "support_need_count": len(support_need_items),
        "misaligned_count": len(misaligned_items),
        "project_risk_count": len(project_risk_items),
        "review_chain_items": review_chain_items,
        "cross_department_items": cross_department_items,
        "workflow_blocked_hits": workflow_blocked_hits,
        "role_drift_hits": role_drift_hits,
        "overloaded_items": overloaded_items,
        "support_need_items": support_need_items,
        "misaligned_items": misaligned_items,
        "project_risk_items": project_risk_items,
    }


def _action_payload(
    *,
    summary: str,
    items: list[WeeklyReviewTaskEntryRecord],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    primary_project = next((context for context in (_item_project_context(item) for item in items) if context and context.clientId), None)
    primary_org_context = next((context for context in (_item_org_context(item) for item in items) if context and context.departmentId), None)
    primary_event_line_id = next((event_line_id for event_line_id in (_item_event_line_id(item) for item in items) if event_line_id), None)
    primary_event_line_name = next(
        (
            event_line_name
            for event_line_name in (
                _item_event_line_name(item)
                for item in items
                if _item_event_line_id(item) == (primary_event_line_id or "")
            )
            if event_line_name
        ),
        None,
    )
    payload: dict[str, object] = {
        "summary": summary,
        "relatedTaskIds": [item.taskId for item in items[:5]],
        "relatedTaskTitles": _representative_titles(items, limit=3),
        "count": len(items),
        "primaryClientId": primary_project.clientId if primary_project else None,
        "primaryClientName": primary_project.clientName if primary_project else None,
        "primaryDepartmentId": primary_org_context.departmentId if primary_org_context else None,
        "primaryEventLineId": primary_event_line_id,
        "primaryEventLineName": primary_event_line_name,
    }
    if extra:
        payload.update(extra)
    return payload


def _build_predictive_action_cards(
    *,
    week_label: str,
    scope_type: str,
    scope_ref_id: str,
    items: list[WeeklyReviewTaskEntryRecord],
    management_bundle: dict[str, object],
    suggested_actions: list[str],
) -> list[ReviewActionCardRecord]:
    created_at = _now_iso()
    cards: list[ReviewActionCardRecord] = []

    def dedupe_items(source_items: list[WeeklyReviewTaskEntryRecord]) -> list[WeeklyReviewTaskEntryRecord]:
        deduped: list[WeeklyReviewTaskEntryRecord] = []
        seen: set[str] = set()
        for item in source_items:
            if item.taskId in seen:
                continue
            seen.add(item.taskId)
            deduped.append(item)
        return deduped

    def append_card(
        key: str,
        action_type: str,
        title: str,
        summary: str,
        related_items: list[WeeklyReviewTaskEntryRecord],
        extra: dict[str, object] | None = None,
    ) -> None:
        if not related_items:
            return
        payload = _action_payload(summary=summary, items=related_items, extra=extra)
        primary_event_line_id = payload.get("primaryEventLineId")
        primary_event_line_name = payload.get("primaryEventLineName")
        evidence_refs = [
            ReviewDashboardEvidenceRefRecord(
                sourceType="task",
                sourceId=item.taskId,
                title=item.taskSnapshot.title,
                summary=item.structuredNote.progress.strip() or item.note.strip() or item.taskSnapshot.status,
            )
            for item in related_items[:4]
        ]
        cards.append(
            ReviewActionCardRecord(
                id=f"action_{scope_type}_{scope_ref_id}_{key}",
                actionType=action_type,  # type: ignore[arg-type]
                title=title,
                payload=payload,
                status="suggested",
                createdAt=created_at,
                target=ReviewDashboardCardTargetRecord(
                    targetType="event_line" if primary_event_line_id else "task_view",
                    targetId=str(primary_event_line_id or f"{scope_type}:{key}"),
                    targetLabel=str(primary_event_line_name or title),
                    targetFilters={
                        "eventLineId": primary_event_line_id,
                        "relatedTaskIds": [item.taskId for item in related_items[:5]],
                    },
                ),
                evidenceRefs=evidence_refs,
            )
        )

    review_chain_items = management_bundle.get("review_chain_items", [])
    cross_department_items = management_bundle.get("cross_department_items", [])
    workflow_blocked_hits = management_bundle.get("workflow_blocked_hits", [])
    if review_chain_items or cross_department_items or workflow_blocked_hits:
        workflow_items = [hit[0] for hit in workflow_blocked_hits[:5]]
        related_items = dedupe_items([*review_chain_items[:5], *cross_department_items[:5], *workflow_items])
        append_card(
            "sync_meeting",
            "meeting",
            "拉一次确认会，缩短复核与协作链",
            f"当前待复核 {management_bundle.get('review_chain_count', 0)} 条、跨部门 {management_bundle.get('cross_department_count', 0)} 条、流程卡点 {management_bundle.get('workflow_blocked_count', 0)} 条，建议合并成一次短会收敛确认人和最晚回收时间。",
            related_items,
            extra={
                "blockedSteps": _clean_lines(
                    [hit[2] for hit in workflow_blocked_hits[:4]]
                    + [(_item_org_context(item).blockedAtStep or "") for item in review_chain_items[:4] if _item_org_context(item)],
                    limit=4,
                )
            },
        )

    overloaded_items = management_bundle.get("overloaded_items", [])
    if overloaded_items or int(management_bundle.get("manager_load_count", 0) or 0) >= max(2, len(items) // 2 or 1):
        append_card(
            "capacity_adjust",
            "resource_request",
            "调整容量与资源配置",
            f"当前容量过载 {management_bundle.get('overload_count', 0)} 条、管理负荷 {management_bundle.get('manager_load_count', 0)} 条，建议先做取舍、顺延或争取额外支持，而不是继续叠加任务。",
            list(overloaded_items[:5]) or items[: min(3, len(items))],
        )

    role_drift_hits = management_bundle.get("role_drift_hits", [])
    if role_drift_hits:
        role_items = [hit[0] for hit in role_drift_hits[:5]]
        matched_phrases = _clean_lines([hit[2] for hit in role_drift_hits[:4]], limit=3)
        append_card(
            "role_boundary",
            "one_on_one",
            "做一次职责边界校准",
            f"当前有 {management_bundle.get('role_drift_count', 0)} 条任务开始触碰岗位不应长期承担的事项，建议和负责人做一次职责/负荷校准，避免长期偏岗。",
            role_items,
            extra={"matchedShouldAvoid": matched_phrases},
        )

    support_need_items = management_bundle.get("support_need_items", [])
    if support_need_items:
        support_tags = _clean_lines(
            [item.structuredNote.lightweightTag for item in support_need_items[:4] if item.structuredNote.lightweightTag.strip()],
            limit=3,
        )
        append_card(
            "support_request",
            "support_request",
            "把分散阻力收束成一次支持请求",
            f"当前有 {management_bundle.get('support_need_count', 0)} 条任务明确提出支持/依赖，建议统一说明缺什么、等谁、最晚什么时候回收，不要零散追问。",
            support_need_items[:5],
            extra={"supportTags": support_tags},
        )

    project_risk_items = management_bundle.get("project_risk_items", [])
    misaligned_items = management_bundle.get("misaligned_items", [])
    if project_risk_items or misaligned_items:
        related_items = dedupe_items([*project_risk_items[:5], *misaligned_items[:5]])
        append_card(
            "risk_followup",
            "task",
            "把项目风险和计划偏移转成明确动作",
            f"当前有 {management_bundle.get('project_risk_count', 0)} 条任务已挂接项目风险，另有 {management_bundle.get('misaligned_count', 0)} 条任务显式偏离计划对象，建议转成单独整改动作并明确负责人。",
            related_items,
        )

    if not cards and suggested_actions:
        cards.append(
            ReviewActionCardRecord(
                id=f"action_{scope_type}_{scope_ref_id}_default_next_step",
                actionType="task",
                title="把本周判断收束成第一优先动作",
                payload=_action_payload(
                    summary=suggested_actions[0],
                    items=items[:3],
                    extra={"count": min(len(items), 3)},
                ),
                status="suggested",
                createdAt=created_at,
                target=ReviewDashboardCardTargetRecord(
                    targetType="task_view",
                    targetId=f"{scope_type}:default_next_step",
                    targetLabel="相关任务",
                    targetFilters={"relatedTaskIds": [item.taskId for item in items[:3]]},
                ),
                evidenceRefs=[
                    ReviewDashboardEvidenceRefRecord(
                        sourceType="task",
                        sourceId=item.taskId,
                        title=item.taskSnapshot.title,
                        summary=item.structuredNote.progress.strip() or item.note.strip() or item.taskSnapshot.status,
                    )
                    for item in items[:3]
                ],
            )
        )

    return cards[:4]


def build_employee_review_report(
    *,
    week_label: str,
    scope_ref_id: str,
    items: list[WeeklyReviewTaskEntryRecord],
    analysis,
    org_model_profile: OrgModelProfileRecord | None = None,
    viewer_role: str = "employee",
) -> HierarchyReportRecord:
    base_report = build_hierarchy_report_from_analysis(
        analysis,
        week_label=week_label,
        scope_type="employee",
        scope_ref_id=scope_ref_id,
    )
    if not items:
        return base_report
    management_bundle = _management_signal_bundle(items, org_model_profile=org_model_profile)
    event_line_rollup = _event_line_rollup(items)
    if viewer_role == "admin":
        event_line_summaries = list(getattr(analysis, "eventLineSummaries", []) or [])
        event_line_judgments = list(getattr(analysis, "eventLineJudgments", []) or [])
        risk_cards = list(getattr(analysis, "riskCards", []) or [])
        opportunity_cards = list(getattr(analysis, "opportunityCards", []) or [])
        trend_cards = list(getattr(analysis, "trendSignals", []) or [])
        event_line_titles = _judgment_focus_lines(event_line_judgments, limit=4) or _event_line_overview_lines(event_line_summaries, limit=4) or _clean_lines(
            [_overview_line(item.title, item.statement) for item in analysis.hypothesisHighlights[:4]],
            limit=4,
        )
        event_line_statements = (
            [f"{item.title}：{item.whatHappened} {item.managerImplication}".strip() for item in event_line_judgments[:3]]
            or
            [f"{item.title}：{item.whatHappenedThisWeek} {item.currentState}".strip() for item in event_line_summaries[:3]]
            or [item.statement for item in analysis.hypothesisHighlights[:3]]
        )
        summary_parts = event_line_statements[:2] or [base_report.summary]
        if management_bundle["summary_lines"]:
            summary_parts.append(management_bundle["summary_lines"][0])
        focus_seed = event_line_titles + _judgment_management_lines(event_line_judgments, limit=3) + list(management_bundle["focus_areas"])
        support_seed = _trend_overview_lines(trend_cards, limit=3) + _risk_overview_lines(risk_cards, limit=3) + _judgment_blocker_lines(event_line_judgments, limit=3) + list(management_bundle["support_signals"])
        suggested_seed = (
            _judgment_action_lines(event_line_judgments, limit=3)
            +
            [_overview_line(item.title, item.suggestedAction) for item in risk_cards[:3]]
            + [_overview_line(item.title, item.recommendedAmplifier) for item in opportunity_cards[:3]]
            + list(analysis.nextWeekFocus)
            + list(management_bundle["suggested_actions"])
        )
        suggested_actions = _clean_lines(suggested_seed, limit=4)
        action_cards = _build_predictive_action_cards(
            week_label=week_label,
            scope_type="employee",
            scope_ref_id=scope_ref_id,
            items=items,
            management_bundle=management_bundle,
            suggested_actions=suggested_actions,
        )
        return base_report.model_copy(
            update={
                "summary": " ".join(summary_parts),
                "focusAreas": _clean_lines(focus_seed, limit=4),
                "supportSignals": _clean_lines(support_seed, limit=4),
                "suggestedActions": suggested_actions,
                "anonymousInsights": _clean_lines(
                    _opportunity_overview_lines(opportunity_cards, limit=3) + _judgment_management_lines(event_line_judgments, limit=3),
                    limit=3,
                ),
                "actions": action_cards,
                "logicMode": "admin_eventline_context_v1",
                "sourcePolicy": {
                    **base_report.sourcePolicy,
                    "roleDriftCount": management_bundle["role_drift_count"],
                    "reviewChainCount": management_bundle["review_chain_count"],
                    "controlledTaskCount": management_bundle["controlled_count"],
                    "crossDepartmentCount": management_bundle["cross_department_count"],
                    "managerLoadCount": management_bundle["manager_load_count"],
                    "workflowBlockedCount": management_bundle["workflow_blocked_count"],
                    "overloadCount": management_bundle["overload_count"],
                    "supportNeedCount": management_bundle["support_need_count"],
                    "misalignedCount": management_bundle["misaligned_count"],
                    "projectRiskCount": management_bundle["project_risk_count"],
                    "roleView": "admin",
                    "eventLineCount": event_line_rollup["group_count"],
                    "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                    "blockedEventLineCount": event_line_rollup["blocked_group_count"],
                },
            }
        )
    if viewer_role == "department_lead":
        event_line_summaries = list(getattr(analysis, "eventLineSummaries", []) or [])
        event_line_judgments = list(getattr(analysis, "eventLineJudgments", []) or [])
        risk_cards = list(getattr(analysis, "riskCards", []) or [])
        opportunity_cards = list(getattr(analysis, "opportunityCards", []) or [])
        trend_cards = list(getattr(analysis, "trendSignals", []) or [])
        event_line_titles = _judgment_focus_lines(event_line_judgments, limit=4) or _event_line_overview_lines(event_line_summaries, limit=4) or _clean_lines(
            [_overview_line(item.title, item.statement) for item in analysis.hypothesisHighlights[:4]],
            limit=4,
        )
        event_line_statements = (
            [f"{item.title}：{item.whatHappened} {item.managerImplication}".strip() for item in event_line_judgments[:3]]
            or
            [f"{item.title}：{item.whatHappenedThisWeek} {item.currentState}".strip() for item in event_line_summaries[:3]]
            or [item.statement for item in analysis.hypothesisHighlights[:3]]
        )
        summary_parts = event_line_statements[:2] or [base_report.summary]
        if management_bundle["summary_lines"]:
            summary_parts.append(management_bundle["summary_lines"][0])
        focus_seed = event_line_titles + _judgment_management_lines(event_line_judgments, limit=3) + list(management_bundle["focus_areas"])
        support_seed = _trend_overview_lines(trend_cards, limit=3) + _risk_overview_lines(risk_cards, limit=3) + _judgment_blocker_lines(event_line_judgments, limit=3) + list(management_bundle["support_signals"])
        suggested_seed = (
            _judgment_action_lines(event_line_judgments, limit=3)
            +
            [_overview_line(item.title, item.suggestedAction) for item in risk_cards[:3]]
            + [_overview_line(item.title, item.recommendedAmplifier) for item in opportunity_cards[:3]]
            + list(analysis.nextWeekFocus)
            + list(management_bundle["suggested_actions"])
        )
        suggested_actions = _clean_lines(suggested_seed, limit=4)
        action_cards = _build_predictive_action_cards(
            week_label=week_label,
            scope_type="employee",
            scope_ref_id=scope_ref_id,
            items=items,
            management_bundle=management_bundle,
            suggested_actions=suggested_actions,
        )
        return base_report.model_copy(
            update={
                "summary": " ".join(summary_parts),
                "focusAreas": _clean_lines(focus_seed, limit=4),
                "supportSignals": _clean_lines(support_seed, limit=4),
                "suggestedActions": suggested_actions,
                "anonymousInsights": _clean_lines(
                    _opportunity_overview_lines(opportunity_cards, limit=3) + _judgment_management_lines(event_line_judgments, limit=3),
                    limit=3,
                ),
                "actions": action_cards,
                "logicMode": "department_lead_eventline_context_v1",
                "sourcePolicy": {
                    **base_report.sourcePolicy,
                    "roleDriftCount": management_bundle["role_drift_count"],
                    "reviewChainCount": management_bundle["review_chain_count"],
                    "controlledTaskCount": management_bundle["controlled_count"],
                    "crossDepartmentCount": management_bundle["cross_department_count"],
                    "managerLoadCount": management_bundle["manager_load_count"],
                    "workflowBlockedCount": management_bundle["workflow_blocked_count"],
                    "overloadCount": management_bundle["overload_count"],
                    "supportNeedCount": management_bundle["support_need_count"],
                    "misalignedCount": management_bundle["misaligned_count"],
                    "projectRiskCount": management_bundle["project_risk_count"],
                    "roleView": "department_lead",
                    "eventLineCount": event_line_rollup["group_count"],
                    "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                    "blockedEventLineCount": event_line_rollup["blocked_group_count"],
                },
            }
        )
    summary_parts = [base_report.summary]
    if int(event_line_rollup["group_count"]) > 0:
        summary_parts.append(
            f"本周有 {event_line_rollup['task_count']} 条任务被串到 {event_line_rollup['group_count']} 条事件线里，其中 {event_line_rollup['multi_task_group_count']} 条已经跨了多项任务。"
        )
    if management_bundle["summary_lines"]:
        summary_parts.append(" ".join(management_bundle["summary_lines"]))
    focus_seed = list(base_report.focusAreas) + list(management_bundle["focus_areas"])
    trend_seed = _trend_overview_lines(list(getattr(analysis, "trendSignals", []) or []), limit=3)
    judgment_focus_seed = _judgment_focus_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=3)
    judgment_blocker_seed = _judgment_blocker_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=3)
    if int(event_line_rollup["group_count"]) > 0:
        focus_seed.insert(0, _overview_line("事件线连续推进", f"本周有 {event_line_rollup['group_count']} 条事件线被持续推进。"))
    focus_areas = _clean_lines(judgment_focus_seed + focus_seed, limit=4)
    support_seed = trend_seed + judgment_blocker_seed + list(management_bundle["support_signals"]) + list(base_report.supportSignals)
    if int(event_line_rollup["blocked_group_count"]) > 0:
        blocked_names = "、".join(event_line_rollup["blocked_names"][:2])
        support_seed.insert(
            0,
            (
                f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线处在待继续推进状态，重点包括：{blocked_names}。"
                if blocked_names
                else f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线没有收束完毕。"
            ),
        )
    support_signals = _clean_lines(support_seed, limit=4)
    suggested_seed = list(base_report.suggestedActions) + list(management_bundle["suggested_actions"])
    if int(event_line_rollup["group_count"]) > 0:
        suggested_seed.insert(0, _overview_line("事件线收束", "优先按事件线收束同一件事的相关任务，不要继续拆成多条独立事项分别推进。"))
    suggested_actions = _clean_lines(suggested_seed, limit=4)
    anonymous_insights = _clean_lines(
        list(base_report.anonymousInsights) + list(management_bundle["anonymous_insights"]),
        limit=3,
    )
    action_cards = _build_predictive_action_cards(
        week_label=week_label,
        scope_type="employee",
        scope_ref_id=scope_ref_id,
        items=items,
        management_bundle=management_bundle,
        suggested_actions=suggested_actions,
    )
    return base_report.model_copy(
        update={
            "summary": " ".join(summary_parts),
            "focusAreas": focus_areas,
            "supportSignals": support_signals,
            "suggestedActions": suggested_actions,
            "anonymousInsights": anonymous_insights,
            "actions": action_cards,
            "sourcePolicy": {
                **base_report.sourcePolicy,
                "roleDriftCount": management_bundle["role_drift_count"],
                "reviewChainCount": management_bundle["review_chain_count"],
                "controlledTaskCount": management_bundle["controlled_count"],
                "crossDepartmentCount": management_bundle["cross_department_count"],
                "managerLoadCount": management_bundle["manager_load_count"],
                "workflowBlockedCount": management_bundle["workflow_blocked_count"],
                "overloadCount": management_bundle["overload_count"],
                "supportNeedCount": management_bundle["support_need_count"],
                "misalignedCount": management_bundle["misaligned_count"],
                "projectRiskCount": management_bundle["project_risk_count"],
                "eventLineCount": event_line_rollup["group_count"],
                "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                "blockedEventLineCount": event_line_rollup["blocked_group_count"],
            },
            "logicMode": "employee_org_context_v1",
        }
    )


def _team_plan_module(department: ReviewDepartmentConfigRecord) -> OrganizationDnaModuleRecord | None:
    monthly_dna = department.monthlyDna.strip()
    weekly_focus = department.weeklyFocus.strip()
    if not monthly_dna and not weekly_focus:
        return None
    content_parts = []
    if monthly_dna:
        content_parts.append(f"月度 DNA：{monthly_dna}")
    if weekly_focus:
        content_parts.append(f"本周重点计划：{weekly_focus}")
    normalized = " ".join(content_parts)
    return OrganizationDnaModuleRecord(
        moduleKey="team_intro",  # type: ignore[arg-type]
        title=f"{department.name} 部门计划背景",
        markdownContent=normalized,
        normalizedText=normalized,
        summary=normalized,
        fileName=None,
        contentHash=None,
        updatedAt=None,
        updatedBy="review_governance",
        hasDocument=True,
    )


def _plan_alignment_summary(department: ReviewDepartmentConfigRecord, items: list[WeeklyReviewTaskEntryRecord]) -> str:
    if not items:
        return "本周还没有收集到该部门的真实复盘样本，暂时无法判断是否贴着部门计划前进。"
    monthly_dna = department.monthlyDna.strip()
    weekly_focus = department.weeklyFocus.strip()
    plan_source = " ".join(part for part in [monthly_dna, weekly_focus] if part)
    if not plan_source:
        return "该部门尚未填写月度 DNA 和本周重点计划，目前只能根据一线周复盘描述推进状态，不能严格判断是否偏离计划。"
    plan_tokens = {token for token in tokenize(plan_source) if len(token.strip()) >= 2}
    item_tokens = {token for item in items for token in tokenize(_item_text(item)) if len(token.strip()) >= 2}
    overlap = len(plan_tokens & item_tokens)
    blocker_count = sum(1 for item in items if item.structuredNote.lightweightTag.strip() or item.structuredNote.blockerReason.strip())
    if overlap >= 4 and blocker_count <= max(1, len(items) // 3):
        return "从当前任务表述看，本周动作与部门月度 DNA / 本周重点计划的对应关系较强，暂未出现明显偏航信号。"
    if overlap >= 2:
        return "从当前任务表述看，本周动作和部门计划背景仍有对应，但推进深度和节奏并不均衡，需要继续盯偏差。"
    return "从当前任务表述看，本周动作与部门计划背景的显式对应偏弱，建议人工确认是否已有主线偏航。"


def _department_report(
    week_label: str,
    department: ReviewDepartmentConfigRecord,
    items: list[WeeklyReviewTaskEntryRecord],
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    org_model_profile: OrgModelProfileRecord | None = None,
) -> HierarchyReportRecord:
    created_at = _now_iso()
    alignment_summary = _plan_alignment_summary(department, items)
    agent_sample_count = sum(1 for item in items if _is_agent_item(item))
    management_bundle = _management_signal_bundle(
        items,
        org_model_profile=org_model_profile,
        department_name=department.name,
    )
    if not items:
        return HierarchyReportRecord(
            id=f"dept_review_{department.id}_{week_label}",
            scopeType="team",
            scopeRefId=department.name,
            weekLabel=week_label,
            logicMode="real_department_rollup_v1",
            headline=f"{department.name} 本周暂无可分析的真实复盘样本。",
            summary=f"{alignment_summary} 当前只能先补齐成员归属、部门计划背景和至少 1-2 条一线周复盘说明。",
            focusAreas=["补齐部门输入", "确认成员归属", "补写部门计划背景"],
            supportSignals=["没有真实周复盘样本时，系统不能可靠判断成功原因和阻碍原因。"] if department.members else ["当前还没有给这个部门分配成员。"],
            suggestedActions=[
                "先给该部门配置成员归属。",
                "至少补一条本周推进说明和一条阻碍说明。",
                "把部门月度 DNA 和本周重点计划补齐，方便系统判断是否偏离。",
            ],
            anonymousInsights=[],
            sourcePolicy={
                "realAggregation": True,
                "sampleSize": 0,
                "memberCount": len(department.members),
                "agentSampleCount": 0,
                "monthPlanReady": bool(department.monthlyDna.strip()),
                "weeklyPlanReady": bool(department.weeklyFocus.strip()),
                "projectContextCount": 0,
                "linkedFocusItemCount": 0,
                "linkedDepartmentPlanItemCount": 0,
            },
            actions=[],
            createdAt=created_at,
            updatedAt=created_at,
        )

    modules = list(organization_dna_modules)
    team_plan_module = _team_plan_module(department)
    if team_plan_module:
        modules = [team_plan_module, *modules]
    analysis = build_weekly_review_analysis("work", week_label, items, modules, org_model_profile=org_model_profile)
    base_report = build_hierarchy_report_from_analysis(
        analysis,
        week_label=week_label,
        scope_type="team",
        scope_ref_id=department.name,
    )
    event_line_overview = _judgment_focus_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=4) or _event_line_overview_lines(list(getattr(analysis, "eventLineSummaries", []) or []), limit=4)
    risk_overview = _trend_overview_lines(list(getattr(analysis, "trendSignals", []) or []), limit=3) + _risk_overview_lines(list(getattr(analysis, "riskCards", []) or []), limit=3)
    opportunity_overview = _opportunity_overview_lines(list(getattr(analysis, "opportunityCards", []) or []), limit=4)
    project_context_count = sum(1 for item in items if _item_project_context(item))
    linked_focus_count = len({_item_focus_item_id(item) for item in items if _item_focus_item_id(item)})
    linked_plan_item_count = len({_item_department_plan_item_id(item) for item in items if _item_department_plan_item_id(item)})
    event_line_rollup = _event_line_rollup(items)
    profile = DEPARTMENT_STRATEGY_PROFILES.get(department.name)
    completed_count = sum(1 for item in items if _is_completed_item(item))
    blocker_count = sum(1 for item in items if not _is_completed_item(item) and _has_blocker_signal(item))
    titles = _representative_titles(items)
    clean_next_actions = _clean_lines(analysis.nextWeekFocus, limit=2)
    clean_hypothesis = _clean_lines([hypothesis.statement for hypothesis in analysis.hypothesisHighlights], limit=2)

    if profile:
        headline = f"{department.name}｜{profile['headline']}"
        summary_parts = [
            f"本周纳入 {len(items)} 条真实工作样本，已完成 {completed_count} 条，仍在推进 {len(items) - completed_count} 条。",
            str(profile["core"]),
        ]
        if titles:
            summary_parts.append(f"当前最能代表本周推进的任务包括：{'、'.join(titles)}。")
        summary_parts.append(
            f"目前有 {blocker_count} 条任务明确暴露出阻力或支持需求。"
            if blocker_count
            else "从当前样本看，本周主线推进相对连贯，尚未出现明显被打散的迹象。"
        )
        if int(event_line_rollup["group_count"]) > 0:
            summary_parts.append(
                f"其中 {event_line_rollup['task_count']} 条任务已被串到 {event_line_rollup['group_count']} 条事件线里，{event_line_rollup['multi_task_group_count']} 条事件线已经跨了多项任务。"
            )
        summary_parts.append(str(profile["risk"]))
        if department.monthlyDna.strip():
            summary_parts.append(f"部门月度 DNA：{department.monthlyDna.strip()}")
        if department.weeklyFocus.strip():
            summary_parts.append(f"本周重点计划：{department.weeklyFocus.strip()}")
        summary_parts.append(alignment_summary)
        summary_parts.extend([fact for fact in analysis.confirmedFacts if "挂接项目背景" in fact or "正式计划" in fact][:2])
        summary_parts.extend(management_bundle["summary_lines"])  # type: ignore[arg-type]
        profile_focus_lines = _clean_lines(
            [_overview_line(area, "、".join(titles[:2]) or str(profile["core"])) for area in profile["focus_areas"]],  # type: ignore[index]
            limit=4,
        )
        focus_seed = event_line_overview + list(management_bundle["focus_areas"]) + profile_focus_lines  # type: ignore[arg-type]
        if int(event_line_rollup["group_count"]) > 0:
            focus_seed.insert(0, _overview_line("事件线连续推进", f"当前已有 {event_line_rollup['group_count']} 条事件线把关键推进串起来。"))
        focus_areas = _clean_lines(focus_seed, limit=4)
        suggested_actions = _clean_lines(
            _action_overview_lines(list(management_bundle["suggested_actions"]) + list(profile["actions"]) + clean_next_actions, limit=4),  # type: ignore[arg-type]
            limit=4,
        )
        support_signals = _clean_lines(
            [
                *management_bundle["support_signals"],  # type: ignore[arg-type]
                *risk_overview,
                *_judgment_blocker_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=3),
                f"本周样本 {len(items)} 条，已完成 {completed_count} 条，带阻力或支持需求 {blocker_count} 条。",
                *(
                    [
                        (
                            f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线未收束，重点包括：{'、'.join(event_line_rollup['blocked_names'][:2])}。"
                            if event_line_rollup["blocked_names"]
                            else f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线未收束。"
                        )
                    ]
                    if int(event_line_rollup["blocked_group_count"]) > 0
                    else []
                ),
                *[fact for fact in analysis.confirmedFacts if "挂接项目背景" in fact or "正式计划" in fact][:2],
                str(profile["risk"]),
                *analysis.confirmedFacts[:1],
            ],
            limit=4,
        )
        anonymous_insights = _clean_lines(opportunity_overview + _judgment_management_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=3) + list(management_bundle["anonymous_insights"]), limit=3)  # type: ignore[arg-type]
    else:
        headline = f"{department.name}：{analysis.headline}"
        summary_parts = []
        if department.monthlyDna.strip():
            summary_parts.append(f"部门月度 DNA：{department.monthlyDna.strip()}")
        if department.weeklyFocus.strip():
            summary_parts.append(f"本周重点计划：{department.weeklyFocus.strip()}")
        summary_parts.append(alignment_summary)
        if int(event_line_rollup["group_count"]) > 0:
            summary_parts.append(
                f"本周已有 {event_line_rollup['group_count']} 条事件线把相关任务串成连续工作线，其中 {event_line_rollup['multi_task_group_count']} 条已经跨了多项任务。"
            )
        summary_parts.append(analysis.caution)
        summary_parts.extend(management_bundle["summary_lines"])  # type: ignore[arg-type]
        focus_areas = event_line_overview + _action_overview_lines(list(analysis.nextWeekFocus[:2]), limit=2) + list(management_bundle["focus_areas"])  # type: ignore[arg-type]
        if department.monthlyDna.strip() or department.weeklyFocus.strip():
            focus_areas.insert(0, _overview_line("部门计划背景对照", "优先检查本周动作是否贴着部门月度 DNA 和本周重点计划推进。"))
        if int(event_line_rollup["group_count"]) > 0:
            focus_areas.insert(0, _overview_line("事件线连续推进", f"当前已有 {event_line_rollup['group_count']} 条事件线把相关任务串起来。"))
        suggested_actions = _clean_lines(_action_overview_lines(list(analysis.nextWeekFocus[:3]) + list(management_bundle["suggested_actions"]), limit=4), limit=4)  # type: ignore[arg-type]
        support_signals = _clean_lines(
            list(management_bundle["support_signals"])  # type: ignore[arg-type]
            + risk_overview
            + (
            (
                [
                    (
                        f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线未收束，重点包括：{'、'.join(event_line_rollup['blocked_names'][:2])}。"
                        if event_line_rollup["blocked_names"]
                        else f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线未收束。"
                    )
                ]
                if int(event_line_rollup["blocked_group_count"]) > 0
                else []
            )
            + _judgment_blocker_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=2)
            + analysis.confirmedFacts[:2]
            + base_report.supportSignals[:2]
            ),
            limit=4,
        )  # type: ignore[arg-type]
        anonymous_insights = _clean_lines(
            opportunity_overview + _judgment_management_lines(list(getattr(analysis, "eventLineJudgments", []) or []), limit=2) + list(management_bundle["anonymous_insights"]),
            limit=3,
        )  # type: ignore[arg-type]

    action_cards = _build_predictive_action_cards(
        week_label=week_label,
        scope_type="team",
        scope_ref_id=department.id,
        items=items,
        management_bundle=management_bundle,
        suggested_actions=suggested_actions,
    )

    return base_report.model_copy(
        update={
            "headline": headline,
            "summary": " ".join(summary_parts),
            "focusAreas": focus_areas[:4],
            "supportSignals": support_signals,
            "suggestedActions": suggested_actions,
            "anonymousInsights": anonymous_insights,
            "actions": action_cards,
            "sourcePolicy": {
                **base_report.sourcePolicy,
                "realAggregation": True,
                "sampleSize": len(items),
                "memberCount": len(department.members),
                "agentSampleCount": agent_sample_count,
                "monthPlanReady": bool(department.monthlyDna.strip()),
                "weeklyPlanReady": bool(department.weeklyFocus.strip()),
                "projectContextCount": project_context_count,
                "linkedFocusItemCount": linked_focus_count,
                "linkedDepartmentPlanItemCount": linked_plan_item_count,
                "roleDriftCount": management_bundle["role_drift_count"],
                "reviewChainCount": management_bundle["review_chain_count"],
                "controlledTaskCount": management_bundle["controlled_count"],
                "crossDepartmentCount": management_bundle["cross_department_count"],
                "managerLoadCount": management_bundle["manager_load_count"],
                "workflowBlockedCount": management_bundle["workflow_blocked_count"],
                "overloadCount": management_bundle["overload_count"],
                "supportNeedCount": management_bundle["support_need_count"],
                "misalignedCount": management_bundle["misaligned_count"],
                "projectRiskCount": management_bundle["project_risk_count"],
                "eventLineCount": event_line_rollup["group_count"],
                "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                "blockedEventLineCount": event_line_rollup["blocked_group_count"],
            },
            "logicMode": "real_department_rollup_v2",
            "updatedAt": created_at,
        }
    )


def build_executive_review_rollup(
    *,
    week_label: str,
    work_items: list[WeeklyReviewTaskEntryRecord],
    governance: ReviewGovernanceSettingsRecord,
    organization_dna_modules: list[OrganizationDnaModuleRecord],
    org_model_profile: OrgModelProfileRecord | None = None,
) -> tuple[HierarchyReportRecord | None, list[HierarchyReportRecord]]:
    # LEGACY REVIEW GOVERNANCE COMPAT:
    # This still consumes the old governance-shaped object while the new
    # department/organization plan-background domain is not implemented yet.
    # Do not add new Settings-page monthly/weekly plan behavior here.
    if not governance.departments:
        return None, []

    department_reports: list[HierarchyReportRecord] = []
    assigned_task_ids: set[str] = set()
    departments_with_samples = 0
    total_agent_samples = 0

    for department in governance.departments:
        member_ids = _department_member_ids(department)
        member_names = _department_member_names(department)
        department_items = [
            item for item in work_items
            if (_item_department_id(item) and _item_department_id(item) == department.id)
            or (_item_owner_id(item) and _item_owner_id(item) in member_ids)
            or (_item_owner_name(item).lower() in member_names)
            or (_is_agent_item(item) and _item_list_name(item) == department.name)
        ]
        if department_items:
            departments_with_samples += 1
            assigned_task_ids.update(item.taskId for item in department_items)
            total_agent_samples += sum(1 for item in department_items if _is_agent_item(item))
        department_reports.append(
            _department_report(
                week_label=week_label,
                department=department,
                items=department_items,
                organization_dna_modules=organization_dna_modules,
                org_model_profile=org_model_profile,
            )
        )

    if departments_with_samples == 0:
        return None, department_reports

    created_at = _now_iso()
    org_analysis = build_weekly_review_analysis("work", week_label, work_items, organization_dna_modules, org_model_profile=org_model_profile)
    org_management_bundle = _management_signal_bundle(
        work_items,
        org_model_profile=org_model_profile,
    )
    event_line_overview = _judgment_focus_lines(list(getattr(org_analysis, "eventLineJudgments", []) or []), limit=4) or _event_line_overview_lines(list(getattr(org_analysis, "eventLineSummaries", []) or []), limit=4)
    risk_overview = _trend_overview_lines(list(getattr(org_analysis, "trendSignals", []) or []), limit=3) + _risk_overview_lines(list(getattr(org_analysis, "riskCards", []) or []), limit=3)
    opportunity_overview = _opportunity_overview_lines(list(getattr(org_analysis, "opportunityCards", []) or []), limit=4)
    org_report = build_hierarchy_report_from_analysis(
        org_analysis,
        week_label=week_label,
        scope_type="org",
        scope_ref_id="organization",
    )
    reviewed_people = {
        _item_owner_name(item)
        for item in work_items
        if _item_owner_name(item)
    }
    unassigned_count = sum(1 for item in work_items if item.taskId not in assigned_task_ids)
    project_context_count = sum(1 for item in work_items if _item_project_context(item))
    linked_focus_count = len({_item_focus_item_id(item) for item in work_items if _item_focus_item_id(item)})
    linked_plan_item_count = len({_item_department_plan_item_id(item) for item in work_items if _item_department_plan_item_id(item)})
    event_line_rollup = _event_line_rollup(work_items)
    support_signals = list(risk_overview[:2] or org_report.supportSignals[:2])
    if unassigned_count:
        support_signals.append(f"当前还有 {unassigned_count} 条工作域复盘没有匹配到部门，机构层判断仍不完整。")
    missing_plan_departments = [department.name for department in governance.departments if not department.monthlyDna.strip()]
    missing_weekly_departments = [department.name for department in governance.departments if not department.weeklyFocus.strip()]
    if missing_plan_departments:
        support_signals.append(f"这些部门尚未填写月度 DNA：{'、'.join(missing_plan_departments[:3])}。")
    if missing_weekly_departments:
        support_signals.append(f"这些部门尚未填写本周重点计划：{'、'.join(missing_weekly_departments[:3])}。")
    support_signals = list(org_management_bundle["support_signals"]) + support_signals  # type: ignore[arg-type]
    if int(event_line_rollup["blocked_group_count"]) > 0:
        blocked_names = "、".join(event_line_rollup["blocked_names"][:2])
        support_signals.insert(
            0,
            (
                f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线没有收束，重点包括：{blocked_names}。"
                if blocked_names
                else f"当前仍有 {event_line_rollup['blocked_group_count']} 条事件线没有收束。"
            ),
        )
    support_signals.extend(_judgment_blocker_lines(list(getattr(org_analysis, "eventLineJudgments", []) or []), limit=2))
    support_signals.extend([fact for fact in org_analysis.confirmedFacts if "挂接项目背景" in fact or "正式计划" in fact][:2])
    department_headlines = [report.headline for report in department_reports if int(report.sourcePolicy.get("sampleSize", 0) or 0) > 0]
    focus_counter = Counter(area for report in department_reports for area in report.focusAreas[:2])
    org_headline = (
        f"机构真实聚合已覆盖 {departments_with_samples}/{len(governance.departments)} 个部门，"
        f"本周已有 {event_line_rollup['group_count']} 条事件线把关键推进串成连续工作线。"
        if int(event_line_rollup["group_count"]) > 0
        else f"机构真实聚合已覆盖 {departments_with_samples}/{len(governance.departments)} 个部门，当前最值得 CEO 盯的是部门计划与周内动作是否继续保持一致。"
    )
    quarter_focus_summary = next((fact for fact in org_analysis.confirmedFacts if "季度重点" in fact), "")
    org_summary = (
        f"本轮机构视角基于 {len(work_items)} 条真实工作域周复盘、约 {len(reviewed_people)} 位负责人、"
        f"{departments_with_samples} 个有样本的部门生成。"
        f"{f' {quarter_focus_summary}' if quarter_focus_summary else ''} {org_analysis.caution}"
    )
    if int(event_line_rollup["group_count"]) > 0:
        org_summary = (
            f"{org_summary} 当前已有 {event_line_rollup['task_count']} 条任务被串到 {event_line_rollup['group_count']} 条事件线里，"
            f"其中 {event_line_rollup['multi_task_group_count']} 条事件线已经跨了多项任务。"
        )
    if org_management_bundle["summary_lines"]:
        org_summary = f"{org_summary} {' '.join(org_management_bundle['summary_lines'])}"
    executive_suggested_actions = _clean_lines(
        _action_overview_lines(
            list(org_management_bundle["suggested_actions"]) + org_analysis.nextWeekFocus[:2] + [
                "固定对照每个部门的月度 DNA 和本周实际推进，优先处理持续偏航的部门。",
            ],
            limit=4,
        ),
        limit=4,
    )  # type: ignore[arg-type]
    action_cards = _build_predictive_action_cards(
        week_label=week_label,
        scope_type="org",
        scope_ref_id="organization",
        items=work_items,
        management_bundle=org_management_bundle,
        suggested_actions=executive_suggested_actions,
    )
    executive_report = org_report.model_copy(
        update={
            "headline": org_headline,
            "summary": org_summary,
            "focusAreas": _clean_lines(
                (
                    (([_overview_line("事件线连续推进", f"当前已有 {event_line_rollup['group_count']} 条事件线被持续推进。")] if int(event_line_rollup["group_count"]) > 0 else []) + event_line_overview)
                    + list(org_management_bundle["focus_areas"])
                    + [name for name, _ in focus_counter.most_common(4)]
                ),
                limit=4,
            )
            or org_report.focusAreas,  # type: ignore[arg-type]
            "supportSignals": _clean_lines(support_signals, limit=4),
            "suggestedActions": executive_suggested_actions,
            "anonymousInsights": _clean_lines(opportunity_overview + _judgment_management_lines(list(getattr(org_analysis, "eventLineJudgments", []) or []), limit=3) + department_headlines[:4] + list(org_management_bundle["anonymous_insights"]), limit=4) or org_report.anonymousInsights,  # type: ignore[arg-type]
            "actions": action_cards,
            "sourcePolicy": {
                **org_report.sourcePolicy,
                "realAggregation": True,
                "sampleSize": len(work_items),
                "reviewedPeople": len(reviewed_people),
                "reviewedDepartments": departments_with_samples,
                "configuredDepartments": len(governance.departments),
                "unassignedTaskCount": unassigned_count,
                "agentSampleCount": total_agent_samples,
                "projectContextCount": project_context_count,
                "linkedFocusItemCount": linked_focus_count,
                "linkedDepartmentPlanItemCount": linked_plan_item_count,
                "roleDriftCount": org_management_bundle["role_drift_count"],
                "reviewChainCount": org_management_bundle["review_chain_count"],
                "controlledTaskCount": org_management_bundle["controlled_count"],
                "crossDepartmentCount": org_management_bundle["cross_department_count"],
                "managerLoadCount": org_management_bundle["manager_load_count"],
                "workflowBlockedCount": org_management_bundle["workflow_blocked_count"],
                "overloadCount": org_management_bundle["overload_count"],
                "supportNeedCount": org_management_bundle["support_need_count"],
                "misalignedCount": org_management_bundle["misaligned_count"],
                "projectRiskCount": org_management_bundle["project_risk_count"],
                "eventLineCount": event_line_rollup["group_count"],
                "multiTaskEventLineCount": event_line_rollup["multi_task_group_count"],
                "blockedEventLineCount": event_line_rollup["blocked_group_count"],
            },
            "logicMode": "real_executive_rollup_v1",
            "updatedAt": created_at,
        }
    )
    return executive_report, department_reports
