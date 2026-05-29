from app.models import (
    EventLineJudgmentRecord,
    OrgDepartmentPlanItemRecord,
    OrgDepartmentPlanRecord,
    OrgDepartmentRecord,
    OrgEmployeeBindingRecord,
    OrgFocusItemRecord,
    OrgModelProfileRecord,
    OrgProfileRecord,
    OrgRoleTemplateRecord,
    OrganizationDnaModuleRecord,
    TaskOrgContextRecord,
    TaskProjectContextRecord,
    TaskTagRecord,
    WeeklyReviewEventLineContextRecord,
    ReviewDashboardCardTargetRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.review_analysis import build_hierarchy_report_from_analysis, build_weekly_review_analysis


def build_item(
    task_id: str,
    title: str,
    status: str,
    note: str,
    list_name: str = "Q3 营销",
    structured_note: WeeklyReviewTaskStructuredNoteRecord | None = None,
    *,
    org_context: TaskOrgContextRecord | None = None,
    project_context: TaskProjectContextRecord | None = None,
    event_line_id: str | None = None,
    event_line_name: str | None = None,
    event_line_context: WeeklyReviewEventLineContextRecord | None = None,
) -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id=f"review_{task_id}",
        reviewId="review_demo",
        taskId=task_id,
        weekLabel="2026-W11",
        contentDomain="work",
        note=note,
        structuredNote=structured_note or WeeklyReviewTaskStructuredNoteRecord(),
        reviewedAt="2026-03-15T12:00:00",
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(
            title=title,
            status=status,  # type: ignore[arg-type]
            dueDate="2026-03-14",
            createdAt="2026-03-14T10:00:00",
            tags=[TaskTagRecord(id="tag_1", name="情报跟进", color="#5B7BFE", scope="org", updatedAt="2026-03-14T10:00:00")],
            listName=list_name,
            listColor="#5B7BFE",
            orgContext=org_context,
            projectContext=project_context,
            eventLineId=event_line_id,
            eventLineName=event_line_name,
            eventLineContext=event_line_context,
        ),
    )


def build_org_module(module_key: str, title: str, summary: str) -> OrganizationDnaModuleRecord:
    return OrganizationDnaModuleRecord(
        moduleKey=module_key,  # type: ignore[arg-type]
        title=title,
        markdownContent="",
        normalizedText=summary,
        summary=summary,
        fileName=None,
        contentHash=None,
        updatedAt="2026-03-01T00:00:00",
        updatedBy="tester",
        hasDocument=True,
    )


def build_org_model_profile() -> OrgModelProfileRecord:
    return OrgModelProfileRecord(
        organization=OrgProfileRecord(
            organizationId="org_yiyu_default",
            name="示例工作台",
            annualGoal="做深战略判断与交付闭环",
            quarterlyFocus=["推进关键客户交付", "沉淀标准件"],
            leaderUserId="user_ceo",
            managementUserIds=["user_ceo"],
            updatedAt="2026-03-20T10:00:00",
        ),
        departments=[
            OrgDepartmentRecord(
                id="dept_consult_strategy",
                name="咨询策略部",
                color="#5B7BFE",
                leaderUserId="user_ceo",
                mission="推进关键客户战略判断",
                quarterlyFocus=["推进关键客户交付"],
                collaborationDepartmentIds=[],
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        roles=[
            OrgRoleTemplateRecord(
                id="role_consultant",
                departmentId="dept_consult_strategy",
                name="咨询顾问",
                level="employee",
                isManager=False,
                goal="推进关键客户方案",
                responsibilities=["方案推进"],
                shouldAvoid=[],
                taskEditScope="self",
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        bindings=[
            OrgEmployeeBindingRecord(
                userId="user_demo",
                departmentId="dept_consult_strategy",
                primaryRoleId="role_consultant",
                isManager=False,
                currentFocus="推进关键客户交付",
                taskEditScope="self",
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        reportingLines=[],
        taskControlRules=[],
        roleProcessTemplates=[],
        focusItems=[
            OrgFocusItemRecord(
                id="focus_q2_delivery",
                periodKey="2026-Q2",
                title="推进关键客户交付",
                statement="围绕标杆客户推进应用交付并沉淀案例。",
                ownerUserId="user_ceo",
                priority="high",
                status="active",
                evidenceKeywords=["交付", "标杆客户"],
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        departmentPlans=[
            OrgDepartmentPlanRecord(
                id="plan_consult_w12",
                departmentId="dept_consult_strategy",
                weekLabel="2026-W11",
                ownerUserId="user_ceo",
                summary="本周重点推进黄河基金会应用交付方案。",
                majorRisks=[],
                dependencies=[],
                status="active",
                items=[
                    OrgDepartmentPlanItemRecord(
                        id="plan_item_hh_delivery",
                        focusItemId="focus_q2_delivery",
                        title="推进黄河基金会应用交付方案",
                        statement="把方案推进到可审阅版本。",
                        ownerUserId="user_demo",
                        status="active",
                        expectedOutput="可审阅方案",
                        sortOrder=0,
                        updatedAt="2026-03-20T10:00:00",
                    )
                ],
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        updatedAt="2026-03-20T10:00:00",
    )


def test_build_weekly_review_analysis_prefers_user_notes_and_dna():
    items = [
        build_item(
            "task_1",
            "推进客户方案验证",
            "done",
            "这周完成了客户验证，反馈比预期更顺，说明方案路径比较清楚。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(progress="完成客户验证", successReason="方案路径较清楚"),
        ),
        build_item(
            "task_2",
            "梳理跨组协作节奏",
            "doing",
            "目前卡在接口对齐和责任边界不清，推进有阻力，需要协同支持。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(blockerReason="接口对齐不清", supportNeeded="需要协同支持"),
        ),
    ]
    modules = [
        build_org_module("business_intro", "业务介绍", "本月重点是把咨询方案验证做深，优先推进高反馈、低决策成本的项目。"),
        build_org_module("team_intro", "团队介绍", "团队当前的关键任务是收敛协作接口，降低跨组沟通损耗。"),
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, modules)

    assert analysis.scope == "work"
    assert analysis.emphasis == "analysis"
    assert analysis.metricCards
    assert analysis.metricCards[0].key == "timely_completion"
    assert analysis.evidenceWeights[0].sourceType == "user_note"
    assert analysis.evidenceWeights[0].weight == "high"
    assert "业务介绍" in analysis.dnaModuleTitles
    assert analysis.hypothesisHighlights
    assert any(item.title == "可能的成功原因" for item in analysis.hypothesisHighlights)
    assert any(item.title == "可能的阻碍原因" for item in analysis.hypothesisHighlights)
    assert any("假设" in analysis.caution for _ in [0])
    assert any("协作接口" in item.statement or "协作" in item.statement for item in analysis.hypothesisHighlights)


def test_build_hierarchy_report_from_analysis_uses_weighted_summary():
    items = [build_item("task_1", "推进客户方案验证", "done", "方案路径清楚，反馈较好。")]
    modules = [build_org_module("organization_intro", "组织介绍", "组织主线是沉淀可复用的方法资产。")]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, modules)
    report = build_hierarchy_report_from_analysis(analysis, week_label="2026-W11")

    assert report.logicMode == "weighted_hypothesis_v1"
    assert report.weekLabel == "2026-W11"
    assert report.headline == analysis.headline
    assert report.summaryMetrics
    assert report.publishState == "local_preview"
    assert report.sourcePolicy["user_note"] == "high"
    assert "eventLineSummaryCount" in report.sourcePolicy
    assert report.focusAreas
    assert "｜" in report.focusAreas[0]


def test_build_hierarchy_report_from_analysis_prefers_event_line_judgments():
    items = [build_item("task_1", "推进A组织系统演示", "doing", "这周主要是把系统演示推进成会后合作判断。")]
    analysis = build_weekly_review_analysis("work", "2026-W11", items, [])
    analysis = analysis.model_copy(
        update={
            "eventLineJudgments": [
                EventLineJudgmentRecord(
                    eventLineId="eline_demo",
                    title="A组织系统演示推进线",
                    viewerRole="admin",
                    judgmentVersion="event_line_judgment_v1",
                    bundleFingerprint="bundle_demo_fp",
                    coverageScore=84,
                    confidenceScore=78,
                    safeOutputMode="full_judgment",
                    publishState="publish_ready",
                    whatHappened="本周这条线实际在推进：给负责人甲看系统并收集会后合作判断。",
                    whyItMatters="这条线直接决定A组织是否把系统演示看成合作入口，而不只是普通交流。",
                    coreBlocker="真正阻碍不是资料数量，而是会后动作和合作判断还没有被钉住。",
                    blockerType="decision",
                    evidenceSummary="已关联 1 条任务、1 次会谈、2 份附件。",
                    managerImplication="管理层现在最该盯的是这次会谈能否收成明确判断，而不是继续停在交流层。",
                    nextWeekFocus="把会谈反馈压成明确的合作判断和下一步动作。",
                    minimumAction="本周内确认负责人甲的反馈、下一次对齐时间和要补的关键证据。",
                    riskIfIgnored="如果继续放着不管，这条线会停在关系交流层，管理层也看不清是否值得继续加码。",
                    opportunityIfAmplified="如果现在收成结论，这条线就能成为后续合作推进的样板。",
                    target=ReviewDashboardCardTargetRecord(targetType="event_line", targetId="eline_demo", targetLabel="A组织系统演示推进线"),
                )
            ]
        }
    )

    report = build_hierarchy_report_from_analysis(analysis, week_label="2026-W11")

    assert report.judgmentVersion == "event_line_judgment_v1"
    assert report.bundleFingerprint
    assert report.coverageScore is not None and report.coverageScore >= 0
    assert report.confidenceScore is not None and report.confidenceScore >= 0
    assert report.safeOutputMode == "full_judgment"
    assert report.publishState == "publish_ready"
    assert "给负责人甲看系统" in report.summary
    assert any("真正阻碍不是资料数量" in signal for signal in report.supportSignals)
    assert any("本周内确认负责人甲的反馈" in action for action in report.suggestedActions)
    assert any("A组织系统演示推进线" in area for area in report.focusAreas)
    assert report.sourcePolicy["judgmentVersion"] == "event_line_judgment_v1"
    assert report.sourcePolicy["publishReadyCount"] == 1


def test_build_weekly_review_analysis_detects_overload_signal():
    items = [
        build_item(
            "task_3",
            "推进客户交付排期",
            "doing",
            "",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="这周主要不是方向错，而是手上的交付任务已经过载。",
                lightweightTag="工作过度饱和",
            ),
        )
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [])

    assert any(item.title == "可能存在容量过载" for item in analysis.hypothesisHighlights)
    assert any("工作过度饱和" in item for item in analysis.confirmedFacts)


def test_build_weekly_review_analysis_uses_team_plan_and_quarter_background():
    items = [
        build_item(
            "task_4",
            "推进黄河基金会应用交付方案",
            "done",
            "本周把黄河基金会应用交付方案推进到可审阅版本。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="方案已经推进到可审阅版本，客户反馈更聚焦。",
                completionStatus="done_on_time",
            ),
        )
    ]
    modules = [
        build_org_module("team_intro", "咨询策略部 部门计划背景", "月度 DNA：做深重点客户方案验证。本周重点计划：推进黄河基金会应用交付方案。"),
        build_org_module("organization_intro", "组织介绍", "2026 Q2 重点目标：推进应用交付、沉淀标杆客户案例、强化跨部门作战。"),
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, modules)

    assert len(analysis.metricCards) == 4


def test_build_weekly_review_analysis_admin_prefers_event_line_and_strategy_context():
    items = [
        build_item(
            "task_admin_1",
            "推进黄河基金会合作方案初稿",
            "doing",
            "本周先把黄河基金会合作方案推进到可内部讨论版本。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                progress="黄河基金会合作方案进入内部讨论阶段。",
                nextAction="补齐方案分工后与黄河基金会确认下一轮沟通。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="黄河基金会当前围绕合作方案做前期业务判断。",
                goalSummary="把合作方案推进到可确认范围。",
                riskSummary="当前风险是方案分工和下一轮沟通安排还没完全收束。",
                currentFocus="当前主要在推进：黄河基金会合作方案初稿。",
                currentBlocker="当前阻塞：方案分工和下一轮沟通安排还没完全收束。",
                nextAction="下一步动作：补齐方案分工后与黄河基金会确认下一轮沟通。",
                recentProgress="最近进展：黄河基金会合作方案进入内部讨论阶段。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_hh",
            event_line_name="黄河基金会合作推进",
        ),
        build_item(
            "task_admin_2",
            "补齐黄河基金会下一轮沟通提纲",
            "doing",
            "沟通提纲还没完全补齐。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                blockerReason="下一轮沟通提纲还没完全收束。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="黄河基金会当前围绕合作方案做前期业务判断。",
                goalSummary="把合作方案推进到可确认范围。",
                riskSummary="当前风险是方案分工和下一轮沟通安排还没完全收束。",
                currentFocus="当前主要在推进：黄河基金会合作方案初稿。",
                currentBlocker="当前阻塞：方案分工和下一轮沟通安排还没完全收束。",
                nextAction="下一步动作：补齐方案分工后与黄河基金会确认下一轮沟通。",
                recentProgress="最近进展：黄河基金会合作方案进入内部讨论阶段。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_hh",
            event_line_name="黄河基金会合作推进",
        ),
    ]
    modules = [
        build_org_module("organization_intro", "组织介绍", "2026 Q2 重点目标：推进关键客户交付与业务扩展。"),
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, modules, viewer_role="admin")

    assert any(card.label == "事件线成线率" for card in analysis.metricCards)
    assert not any(card.label == "个人-部门对齐率" for card in analysis.metricCards)
    assert any("黄河基金会" in item.statement for item in analysis.hypothesisHighlights)
    assert any("业务扩展" in item.statement for item in analysis.hypothesisHighlights)
    assert any("当前最具体的推进事项" in item.statement for item in analysis.hypothesisHighlights)
    assert any("下一步动作" in item.statement or "接下来应优先推进" in item.statement for item in analysis.hypothesisHighlights)
    assert "个人-部门对齐" not in analysis.caution
    assert any(card.key == "department_alignment" and card.valueText != "待补录" for card in analysis.metricCards)
    assert any(card.key == "strategy_alignment" and card.valueText != "待补录" for card in analysis.metricCards)
    assert any(weight.sourceType == "project_context" and weight.weight == "medium" for weight in analysis.evidenceWeights)
    assert any("季度重点" in fact for fact in analysis.confirmedFacts)
    assert len(analysis.eventLineSummaries) == 1
    assert analysis.eventLineSummaries[0].title == "黄河基金会合作推进"
    assert analysis.eventLineSummaries[0].projectName == "黄河基金会"
    assert analysis.eventLineSummaries[0].predictionReadiness in {"conservative_forecast", "strong_forecast"}
    assert analysis.eventLineCompleteness[0].score >= 65
    assert any(card.title == "黄河基金会合作推进" for card in analysis.riskCards)
    assert any(card.title == "黄河基金会合作推进" for card in analysis.opportunityCards)


def test_build_weekly_review_analysis_detects_event_line_continuity():
    items = [
        build_item(
            "task_event_1",
            "推进云南连心第一轮沟通",
            "doing",
            "本周先完成第一轮沟通和问题收集。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="这周先把外部需求和内部判断对齐。",
                completionStatus="in_progress",
            ),
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
        build_item(
            "task_event_2",
            "整理云南连心后续推进方案",
            "doing",
            "下一步要把沟通结果收束成后续方案。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="还需要继续推进下周安排。",
                completionStatus="in_progress",
            ),
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [])

    assert any("事件线" in fact for fact in analysis.confirmedFacts)
    assert any(item.title == "与事件线连续推进的关系判断" for item in analysis.hypothesisHighlights)
    assert any("事件线" in focus for focus in analysis.nextWeekFocus)
    assert len(analysis.eventLineSummaries) == 1
    assert analysis.eventLineSummaries[0].title == "云南连心"
    assert analysis.eventLineCompleteness[0].status in {"summary_ready", "forecast_ready", "high_confidence"}
    assert any(slot.label == "下一步动作" for slot in analysis.eventLineCompleteness[0].slots)


def test_build_weekly_review_analysis_reads_structured_plan_and_project_context():
    org_profile = build_org_model_profile()
    items = [
        build_item(
            "task_5",
            "推进黄河基金会应用交付方案",
            "doing",
            "本周继续推进黄河基金会交付方案，并结合近期会议判断风险。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="方案推进到可审阅版本，但要继续盯会议里暴露的交付风险。",
                completionStatus="in_progress",
            ),
            org_context=TaskOrgContextRecord(
                departmentId="dept_consult_strategy",
                roleTemplateId="role_consultant",
                focusItemId="focus_q2_delivery",
                departmentPlanItemId="plan_item_hh_delivery",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="方案推进",
                backgroundSummary="围绕基金会应用交付推进方案落地。",
                goalSummary="把应用交付方案推进到可审阅版本。",
                riskSummary="近期会议提示交付节奏和资料补齐仍有风险。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台来源", "项目目标", "近期会议决策"],
            ),
        )
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [], org_model_profile=org_profile)

    assert any(weight.sourceType == "focus_plan" and weight.weight == "medium" for weight in analysis.evidenceWeights)
    assert any(weight.sourceType == "project_context" and weight.weight == "medium" for weight in analysis.evidenceWeights)
    assert any("挂接项目背景" in fact for fact in analysis.confirmedFacts)
    assert any("正式录入的部门计划和机构重点" in fact or "挂接部门计划项" in fact for fact in analysis.confirmedFacts)
    assert any(item.title == "与项目阶段的关系判断" for item in analysis.hypothesisHighlights)
    assert any(item.title == "与正式计划对象的关系判断" for item in analysis.hypothesisHighlights)


def test_build_weekly_review_analysis_prefers_event_line_context_for_admin_story():
    items = [
        build_item(
            "task_event_ctx_1",
            "推进黄河基金会合作方案确认",
            "doing",
            "这周继续推进合作方案。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="先把合作范围和下轮确认节奏拉齐。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="方案推进",
                backgroundSummary="围绕基金会合作方案推进。",
                goalSummary="把方案推进到可确认版本。",
                riskSummary="需要继续补资料。",
                currentFocus="项目共享焦点：继续推进合作方案。",
                currentBlocker="项目共享阻塞：资料还不完整。",
                nextAction="项目共享下一步：继续补资料。",
                recentProgress="项目共享进展：内部已经开始讨论。",
                infoCompleteness="medium",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_hh_case",
            event_line_name="黄河基金会合作推进",
            event_line_context=WeeklyReviewEventLineContextRecord(
                id="eline_hh_case",
                name="黄河基金会合作推进",
                stage="方案确认",
                summary="围绕黄河基金会合作范围与合作方式确认的一条业务扩展线。",
                intent="当前核心是收束合作范围，并明确下一轮确认的关键人和时间点。",
                currentBlocker="关键阻塞是合作边界和确认节奏还没有被双方说死。",
                recentDecision="最近已决定先用收束版方案推进下一轮确认，不再继续扩写。",
                nextStep="下一步先把收束版方案发出，并锁定黄河基金会下一轮确认会议。",
                primaryClientId="client_hh",
                primaryClientName="黄河基金会",
            ),
        )
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [], viewer_role="admin")

    assert len(analysis.eventLineSummaries) == 1
    summary_card = analysis.eventLineSummaries[0]
    assert "合作范围与合作方式确认" in summary_card.whatThisLineIs
    assert "收束合作范围" in summary_card.whatHappenedThisWeek
    assert "合作边界和确认节奏" in summary_card.mainBlocker
    assert "锁定黄河基金会下一轮确认会议" in summary_card.nextCriticalMove
    assert any(
        "合作范围与合作方式确认" in item.statement or "收束合作范围" in item.statement
        for item in analysis.hypothesisHighlights
    )


def test_build_weekly_review_analysis_event_line_intelligence_varies_by_role():
    items = [
        build_item(
            "task_role_1",
            "推进黄河基金会合作边界确认",
            "doing",
            "这周继续推进合作边界和下一轮沟通。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="先把合作边界和关键人确认下来。",
                nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="围绕黄河基金会合作可能性做判断。",
                goalSummary="确认合作边界和下一轮沟通。",
                riskSummary="合作边界和关键确认节点还没有收束。",
                currentFocus="当前主要在推进：合作边界和下一轮沟通确认。",
                currentBlocker="合作边界和关键确认节点还没有收束。",
                nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
                recentProgress="最近进展：双方已经开始围绕合作边界进行确认。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_role_hh",
            event_line_name="黄河基金会合作确认",
        )
    ]

    admin_analysis = build_weekly_review_analysis("work", "2026-W11", items, [], viewer_role="admin")
    employee_analysis = build_weekly_review_analysis("work", "2026-W11", items, [], viewer_role="employee")

    assert admin_analysis.riskCards
    assert employee_analysis.riskCards
    assert "管理层看不清该不该继续加码" in admin_analysis.riskCards[0].statement
    assert "反复确认和来回推进" in employee_analysis.riskCards[0].statement
    assert admin_analysis.opportunityCards
    assert "业务机会" in admin_analysis.opportunityCards[0].upside


def test_build_weekly_review_analysis_event_line_intelligence_varies_by_category():
    items = [
        build_item(
            "task_prod_1",
            "沉淀示例团队问答判断模板",
            "doing",
            "这周继续把判断模板固化成可复用结构。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="先把样本、结构和输出标准收束。",
                nextAction="补齐关键样本并固化输出结构。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_yiyu",
                clientName="示例工作台",
                stage="模板沉淀",
                projectModuleName="判断模板库",
                backgroundSummary="围绕判断模板做产品化沉淀。",
                goalSummary="把模板推进到可复用状态。",
                riskSummary="结构还没钉死，样本也不够稳定。",
                currentFocus="当前主要在推进：判断模板的结构和输出标准。",
                currentBlocker="结构还没钉死，样本也不够稳定。",
                nextAction="补齐关键样本并固化输出结构。",
                recentProgress="最近进展：已经形成第一版模板骨架。",
                infoCompleteness="high",
                sourceEvidence=["项目资料"],
            ),
            event_line_id="eline_prod_1",
            event_line_name="判断模板沉淀",
        )
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [], viewer_role="admin")

    assert analysis.eventLineSummaries
    assert "产品化线" in analysis.eventLineSummaries[0].whatThisLineIs
    assert analysis.opportunityCards
    assert "模板、标准件或 AI 可复用判断组件" in analysis.opportunityCards[0].upside


def test_build_weekly_review_analysis_department_lead_uses_department_view():
    org_profile = build_org_model_profile()
    items = [
        build_item(
            "task_dept_lead_1",
            "推进黄河基金会合作边界确认",
            "doing",
            "这周继续推进合作边界和下一轮沟通。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="先把合作边界和关键人确认下来。",
                nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
                completionStatus="in_progress",
            ),
            org_context=TaskOrgContextRecord(
                departmentId="dept_consult_strategy",
                roleTemplateId="role_consultant",
                focusItemId="focus_q2_delivery",
                departmentPlanItemId="plan_item_hh_delivery",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="围绕黄河基金会合作可能性做判断。",
                goalSummary="确认合作边界和下一轮沟通。",
                riskSummary="合作边界和关键确认节点还没有收束。",
                currentFocus="当前主要在推进：合作边界和下一轮沟通确认。",
                currentBlocker="合作边界和关键确认节点还没有收束。",
                nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
                recentProgress="最近进展：双方已经开始围绕合作边界进行确认。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_dept_hh",
            event_line_name="黄河基金会合作确认",
            event_line_context=WeeklyReviewEventLineContextRecord(
                id="eline_dept_hh",
                name="黄河基金会合作确认",
                stage="方案确认",
                summary="围绕黄河基金会合作边界和确认节奏推进的一条业务扩展线。",
                intent="把合作边界和确认节奏收束到部门可以持续跟进的状态。",
                currentBlocker="合作边界和关键确认节点还没有收束。",
                recentDecision="最近明确先用收束版方案推进下一轮确认。",
                nextStep="下一步锁定下一轮沟通时间并把合作边界确认清楚。",
                primaryClientId="client_hh",
                primaryClientName="黄河基金会",
            ),
        )
    ]

    analysis = build_weekly_review_analysis(
        "work",
        "2026-W11",
        items,
        [],
        org_model_profile=org_profile,
        viewer_role="department_lead",
    )

    assert any(card.label == "部门任务-部门计划对齐率" for card in analysis.metricCards)
    assert any(card.label == "部门任务-机构方向对齐率" for card in analysis.metricCards)
    assert "部门计划解释本周推进" in analysis.caution
    assert any(item.title == "部门计划与机构方向提示" for item in analysis.hypothesisHighlights)
    assert analysis.riskCards
    assert "部门带宽" in analysis.riskCards[0].statement or "部门推进" in analysis.riskCards[0].statement
    assert analysis.opportunityCards
    assert "部门里同类事项" in analysis.opportunityCards[0].upside
