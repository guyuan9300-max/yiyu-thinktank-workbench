from app.models import (
    OrgDepartmentPlanItemRecord,
    OrgDepartmentPlanRecord,
    OrgDepartmentRecord,
    OrgEmployeeBindingRecord,
    OrgFocusItemRecord,
    OrgModelProfileRecord,
    OrgProfileRecord,
    OrgRoleProcessTemplateRecord,
    OrgRoleTemplateRecord,
    OrgTaskControlRuleRecord,
    OrganizationDnaModuleRecord,
    ReviewDepartmentConfigRecord,
    ReviewDepartmentMemberRecord,
    ReviewGovernanceSettingsRecord,
    TaskTagRecord,
    TaskOrgContextRecord,
    TaskProjectContextRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.review_analysis import build_weekly_review_analysis
from app.services.review_rollup import build_employee_review_report, build_executive_review_rollup


def build_item(
    task_id: str,
    title: str,
    owner_name: str,
    structured_note: WeeklyReviewTaskStructuredNoteRecord,
    *,
    owner_id: str | None = None,
    org_context: TaskOrgContextRecord | None = None,
    project_context: TaskProjectContextRecord | None = None,
    event_line_id: str | None = None,
    event_line_name: str | None = None,
) -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id=f"review_{task_id}",
        reviewId="review_demo",
        taskId=task_id,
        weekLabel="2026-W11",
        contentDomain="work",
        note="",
        structuredNote=structured_note,
        reviewedAt="2026-03-15T12:00:00",
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(
            title=title,
            status="doing",  # type: ignore[arg-type]
            dueDate="2026-03-14",
            createdAt="2026-03-14T10:00:00",
            ownerId=owner_id,
            ownerName=owner_name,
            tags=[TaskTagRecord(id="tag_1", name="情报跟进", color="#5B7BFE", scope="org", updatedAt="2026-03-14T10:00:00")],
            listName="Q3 营销",
            listColor="#5B7BFE",
            orgContext=org_context,
            projectContext=project_context,
            eventLineId=event_line_id,
            eventLineName=event_line_name,
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
            annualGoal="建立稳定的战略判断与交付闭环",
            quarterlyFocus=["组织模型 P0 上线", "关键客户交付推进"],
            leaderUserId="user_admin_demo",
            managementUserIds=["user_admin_demo", "user_qinghua"],
            updatedAt="2026-03-17T10:00:00",
        ),
        departments=[
            OrgDepartmentRecord(
                id="dept_customer_service",
                name="客户服务部",
                color="#14B8A6",
                leaderUserId="user_qinghua",
                mission="把客户现场阻力转成组织动作",
                quarterlyFocus=["客户推进", "交付协同"],
                collaborationDepartmentIds=["dept_consult_strategy"],
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        roles=[
            OrgRoleTemplateRecord(
                id="role_cs_lead",
                departmentId="dept_customer_service",
                name="客户服务部负责人",
                level="department_lead",
                isManager=True,
                goal="统筹客户推进与交付协同",
                responsibilities=["客户推进", "交付判断", "跨部门协同"],
                shouldAvoid=["长期承担底层技术修复", "大量文案细修"],
                taskEditScope="department",
                canApproveTasks=True,
                canReassignTasks=True,
                canChangeDeadline=True,
                updatedAt="2026-03-17T10:00:00",
            ),
            OrgRoleTemplateRecord(
                id="role_cs_member",
                departmentId="dept_customer_service",
                name="客户推进",
                level="employee",
                managerRoleId="role_cs_lead",
                goal="推进客户跟进与会后落地",
                responsibilities=["客户沟通", "资料整理", "会后推进"],
                shouldAvoid=["长期承担架构设计", "长期承担底层技术修复"],
                taskEditScope="self",
                updatedAt="2026-03-17T10:00:00",
            ),
        ],
        bindings=[
            OrgEmployeeBindingRecord(
                userId="user_qinghua",
                departmentId="dept_customer_service",
                primaryRoleId="role_cs_lead",
                isManager=True,
                currentFocus="客户推进与交付协同",
                taskEditScope="department",
                canApproveTasks=True,
                canReassignTasks=True,
                canChangeDeadline=True,
                updatedAt="2026-03-17T10:00:00",
            ),
            OrgEmployeeBindingRecord(
                userId="user_jianing",
                departmentId="dept_customer_service",
                primaryRoleId="role_cs_member",
                managerUserId="user_qinghua",
                currentFocus="客户推进",
                taskEditScope="self",
                updatedAt="2026-03-17T10:00:00",
            ),
        ],
        reportingLines=[],
        taskControlRules=[
            OrgTaskControlRuleRecord(
                id="rule_department_key",
                name="部门关键任务",
                controlLevel="department_control",
                departmentId="dept_customer_service",
                roleTemplateId="role_cs_lead",
                deadlineEditableBy="department_lead",
                ownerEditableBy="department_lead",
                requireCollabConfirmation=True,
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        roleProcessTemplates=[
            OrgRoleProcessTemplateRecord(
                id="process_cs_followup",
                roleTemplateId="role_cs_member",
                name="客户周会后推进流程",
                triggerType="weekly_followup",
                triggerCondition="客户周会结束",
                keySteps=["确认需补资料项", "更新客户工作台", "同步飞书群重点", "生成下周待确认事项"],
                collaborationStep="同步飞书群重点",
                approvalStep="生成下周待确认事项",
                outputArtifact="客户推进摘要 + 新任务清单",
                commonBlockers=["资料未补齐", "等待部门确认"],
                active=True,
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        focusItems=[
            OrgFocusItemRecord(
                id="focus_q2_delivery",
                periodKey="2026-Q2",
                title="关键客户交付推进",
                statement="围绕关键客户交付推进跨部门协同与反馈收束。",
                ownerUserId="user_qinghua",
                priority="high",
                status="active",
                evidenceKeywords=["客户推进", "交付协同"],
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        departmentPlans=[
            OrgDepartmentPlanRecord(
                id="dept_plan_cs_w11",
                departmentId="dept_customer_service",
                weekLabel="2026-W11",
                ownerUserId="user_qinghua",
                summary="本周重点推进客户交付协同与关键反馈收束。",
                majorRisks=[],
                dependencies=[],
                status="active",
                items=[
                    OrgDepartmentPlanItemRecord(
                        id="plan_item_client_followup",
                        focusItemId="focus_q2_delivery",
                        title="跟进客户推进并整理会后待办",
                        statement="把推进动作和反馈收束到单一节奏。",
                        ownerUserId="user_jianing",
                        status="active",
                        expectedOutput="会后待办清单",
                        sortOrder=0,
                        updatedAt="2026-03-17T10:00:00",
                    )
                ],
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        updatedAt="2026-03-17T10:00:00",
    )


def test_build_executive_review_rollup_returns_real_org_and_department_reports():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_consult_strategy",
                name="咨询策略部",
                monthlyDna="本月重点是把重点客户方案验证做深。",
                weeklyFocus="本周重点推进黄河基金会应用交付方案。",
                members=[ReviewDepartmentMemberRecord(id="u1", fullName="管理员甲")],
            ),
            ReviewDepartmentConfigRecord(
                id="dept_info_data",
                name="信息数据部",
                monthlyDna="本月重点是把市场变化转成业务判断。",
                members=[ReviewDepartmentMemberRecord(id="u2", fullName="一朔")],
            ),
        ],
        updatedAt="2026-03-15T12:00:00",
    )
    items = [
        build_item("task_1", "推进客户方案验证", "管理员甲", WeeklyReviewTaskStructuredNoteRecord(progress="推进验证", successReason="客户路径更清楚")),
        build_item("task_2", "整理市场信息", "一朔", WeeklyReviewTaskStructuredNoteRecord(progress="整理信息", blockerReason="判断口径还不统一")),
    ]
    modules = [build_org_module("business_intro", "业务介绍", "业务主线是做深方案验证和提高判断质量。")]

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=items,
        governance=governance,
        organization_dna_modules=modules,
    )

    assert org_report is not None
    assert org_report.sourcePolicy["realAggregation"] is True
    assert org_report.sourcePolicy["reviewedDepartments"] == 2
    assert org_report.summaryMetrics
    assert len(department_reports) == 2
    assert department_reports[0].sourcePolicy["sampleSize"] == 1
    assert department_reports[0].summaryMetrics
    assert "场景判断力的产品化" in department_reports[0].headline
    assert any("场景判断力产品化" in area for area in department_reports[0].focusAreas)
    assert any("｜" in area for area in department_reports[0].focusAreas)
    assert "月度 DNA" in department_reports[0].summary
    assert "本周重点计划" in department_reports[0].summary


def test_build_executive_review_rollup_returns_empty_org_when_no_department_matches():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_customer_service",
                name="客户服务部",
                members=[ReviewDepartmentMemberRecord(id="u3", fullName="小李")],
            )
        ],
        updatedAt="2026-03-15T12:00:00",
    )
    items = [
        build_item("task_1", "推进客户方案验证", "管理员甲", WeeklyReviewTaskStructuredNoteRecord(progress="推进验证")),
    ]

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=items,
        governance=governance,
        organization_dna_modules=[],
    )

    assert org_report is None
    assert len(department_reports) == 1
    assert department_reports[0].sourcePolicy["sampleSize"] == 0


def test_build_executive_review_rollup_counts_robot_samples_as_department_inputs():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_consult_strategy",
                name="咨询策略部",
                monthlyDna="本月重点是做深战略判断与客户方案。",
                members=[],
            )
        ],
        updatedAt="2026-03-15T12:00:00",
    )
    robot_item = WeeklyReviewTaskEntryRecord(
        id="review_agent_1",
        reviewId="agent_review_strategy",
        taskId="agent_task_strategy",
        weekLabel="2026-W11",
        contentDomain="work",
        note="",
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(
            planCommitment="推进重点客户战略判断",
            progress="本周围绕重点客户战略判断持续推进，并完成阶段收束。",
            completionStatus="done_on_time",
            departmentPlanId="agent_plan_1",
            departmentPlanAlignment="aligned",
            successReason="关键判断路径已清楚",
            successExperience="通过连续校准主线，减少了判断分歧。",
        ),
        reviewedAt="2026-03-15T12:00:00",
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(
            title="推进重点客户战略判断",
            status="done",  # type: ignore[arg-type]
            dueDate="2026-03-14",
            createdAt="2026-03-14T10:00:00",
            ownerId="agent:strategy_design",
            ownerName="成员甲",
            tags=[TaskTagRecord(id="tag_agent", name="战略设计", color="#5B7BFE", scope="org", updatedAt="2026-03-14T10:00:00")],
            listName="咨询策略部",
            listColor="#5B7BFE",
        ),
    )

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=[robot_item],
        governance=governance,
        organization_dna_modules=[],
    )

    assert org_report is not None
    assert org_report.sourcePolicy["agentSampleCount"] == 1
    assert len(department_reports) == 1
    assert department_reports[0].sourcePolicy["sampleSize"] == 1
    assert department_reports[0].sourcePolicy["agentSampleCount"] == 1
    assert "场景判断力的产品化" in department_reports[0].headline


def test_build_executive_review_rollup_uses_task_org_context_for_management_signals():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_customer_service",
                name="客户服务部",
                monthlyDna="本月重点是把客户推进阻力翻译成产品边界。",
                weeklyFocus="本周重点推进客户交付协同与关键反馈收束。",
                members=[ReviewDepartmentMemberRecord(id="user_jianing", fullName="佳乐")],
            )
        ],
        updatedAt="2026-03-17T10:00:00",
    )
    org_profile = build_org_model_profile()
    items = [
        build_item(
            "task_repair",
            "长期承担底层技术修复并补齐客户反馈",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(
                progress="本周一边修底层问题，一边处理客户反馈。",
                blockerReason="同步飞书群重点时，资料未补齐，跨部门确认链拉长。",
            ),
            owner_id="user_jianing",
            org_context=TaskOrgContextRecord(
                departmentId="dept_customer_service",
                roleTemplateId="role_cs_member",
                controlRuleId="rule_department_key",
                controlLevel="department_control",
                departmentFocusKey="客户推进",
                organizationFocusKey="关键客户交付推进",
                isCrossDepartment=True,
                approvalState="pending",
                blockedAtStep="同步飞书群重点",
                needsReview=True,
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_demo",
                clientName="示例客户",
                stage="交付推进",
                backgroundSummary="围绕关键客户交付推进组织协同。",
                goalSummary="推进关键客户交付方案。",
                riskSummary="当前风险集中在资料未补齐和确认链偏长。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台来源", "项目目标"],
            ),
        ),
        build_item(
            "task_followup",
            "跟进客户推进并整理会后待办",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(
                progress="推进客户跟进。",
                completionStatus="in_progress",
            ),
            owner_id="user_jianing",
            org_context=TaskOrgContextRecord(
                departmentId="dept_customer_service",
                roleTemplateId="role_cs_member",
                focusItemId="focus_q2_delivery",
                departmentPlanItemId="plan_item_client_followup",
                controlLevel="normal",
                departmentFocusKey="客户推进",
                organizationFocusKey="关键客户交付推进",
                isCrossDepartment=False,
                approvalState="none",
                needsReview=False,
            ),
        ),
    ]

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=items,
        governance=governance,
        organization_dna_modules=[],
        org_model_profile=org_profile,
    )

    assert org_report is not None
    assert len(department_reports) == 1
    department_report = department_reports[0]
    assert department_report.sourcePolicy["roleDriftCount"] == 1
    assert department_report.sourcePolicy["reviewChainCount"] == 1
    assert department_report.sourcePolicy["controlledTaskCount"] == 1
    assert department_report.sourcePolicy["crossDepartmentCount"] == 1
    assert department_report.sourcePolicy["workflowBlockedCount"] == 1
    assert department_report.sourcePolicy["projectContextCount"] == 1
    assert department_report.sourcePolicy["linkedFocusItemCount"] == 1
    assert department_report.sourcePolicy["linkedDepartmentPlanItemCount"] == 1
    assert any("职责边界" in area for area in department_report.focusAreas)
    assert any("流程卡点" in area for area in department_report.focusAreas)
    assert any("待复核" in signal or "汇报" in signal for signal in department_report.supportSignals)
    assert any("固定节点" in signal or "流程" in signal for signal in department_report.supportSignals)
    assert "挂接项目背景" in department_report.summary or "正式计划" in department_report.summary
    assert "职责边界" in department_report.summary or "待复核" in department_report.summary
    assert department_report.sourcePolicy["overloadCount"] == 0
    assert department_report.sourcePolicy["supportNeedCount"] == 0
    assert department_report.sourcePolicy["misalignedCount"] == 0
    assert department_report.sourcePolicy["projectRiskCount"] == 1
    assert department_report.actions
    assert any(action.actionType == "meeting" for action in department_report.actions)
    assert any(action.actionType == "one_on_one" for action in department_report.actions)
    assert any(action.actionType == "task" for action in department_report.actions)
    assert any("缩短复核与协作链" in action.title for action in department_report.actions)
    assert org_report.actions
    assert any(action.actionType == "meeting" for action in org_report.actions)


def test_build_employee_review_report_reads_org_context_signals():
    org_profile = build_org_model_profile()
    item = build_item(
        "task_personal_org",
        "长期承担底层技术修复并等待部门确认",
        "佳乐",
        WeeklyReviewTaskStructuredNoteRecord(
            reflection="这周推进了修复，但明显卡在确认链上。",
            lightweightTag="等待他人",
            completionStatus="in_progress",
        ),
        owner_id="user_jianing",
        org_context=TaskOrgContextRecord(
            departmentId="dept_customer_service",
            roleTemplateId="role_cs_member",
            controlRuleId="rule_department_key",
            controlLevel="department_control",
            isCrossDepartment=True,
            approvalState="pending",
            needsReview=True,
        ),
    )
    analysis = type("AnalysisLike", (), {})()
    analysis.scope = "work"
    analysis.emphasis = "analysis"
    analysis.headline = "本周任务推进呈现“有进展，但卡点也已开始显性化”的状态。"
    analysis.caution = "以下判断是带权重的假设性分析。"
    analysis.metricCards = []
    analysis.evidenceWeights = []
    analysis.confirmedFacts = ["当前已有 1 项写入一线复盘说明。"]
    analysis.hypothesisHighlights = []
    analysis.nextWeekFocus = ["优先补齐支持需求。"]

    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="user_jianing",
        items=[item],
        analysis=analysis,
        org_model_profile=org_profile,
    )

    assert report.logicMode == "employee_org_context_v1"
    assert report.sourcePolicy["roleDriftCount"] == 1
    assert report.sourcePolicy["reviewChainCount"] == 1
    assert report.sourcePolicy["controlledTaskCount"] == 1
    assert report.sourcePolicy["workflowBlockedCount"] == 1
    assert any("职责边界" in area for area in report.focusAreas)
    assert any("待复核" in signal for signal in report.supportSignals)
    assert report.actions
    assert any(action.actionType == "meeting" for action in report.actions)
    assert any(action.actionType == "one_on_one" for action in report.actions)


def test_build_employee_review_report_department_lead_uses_department_logic():
    org_profile = build_org_model_profile()
    item = build_item(
        "task_department_lead",
        "推进黄河基金会合作边界确认",
        "佳乐",
        WeeklyReviewTaskStructuredNoteRecord(
            reflection="先把合作边界和关键人确认下来。",
            completionStatus="in_progress",
        ),
        owner_id="user_jianing",
        org_context=TaskOrgContextRecord(
            departmentId="dept_customer_service",
            roleTemplateId="role_cs_member",
            focusItemId="focus_q2_delivery",
            departmentPlanItemId="plan_item_client_followup",
            controlLevel="department_control",
            needsReview=True,
        ),
        project_context=TaskProjectContextRecord(
            clientId="client_hh",
            clientName="黄河基金会",
            stage="业务拓展",
            backgroundSummary="围绕黄河基金会合作边界和确认节奏推进。",
            goalSummary="确认合作边界和下一轮沟通。",
            riskSummary="合作边界和关键确认节点还没有收束。",
            currentFocus="当前主要在推进：合作边界和下一轮沟通确认。",
            currentBlocker="合作边界和关键确认节点还没有收束。",
            nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
            recentProgress="最近进展：双方已经开始围绕合作边界进行确认。",
            infoCompleteness="high",
            sourceEvidence=["客户工作台"],
        ),
        event_line_id="eline_hh_followup",
        event_line_name="黄河基金会合作确认",
    )

    analysis = build_weekly_review_analysis(
        "work",
        "2026-W11",
        [item],
        [],
        org_model_profile=org_profile,
        viewer_role="department_lead",
    )
    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="dept_customer_service",
        items=[item],
        analysis=analysis,
        org_model_profile=org_profile,
        viewer_role="department_lead",
    )

    assert report.logicMode == "department_lead_eventline_context_v1"
    assert report.sourcePolicy["roleView"] == "department_lead"
    assert any("黄河基金会合作确认" in area for area in report.focusAreas)
    assert any("合作边界" in signal or "部门" in signal for signal in report.supportSignals)


def test_build_employee_review_report_creates_capacity_and_support_actions():
    org_profile = build_org_model_profile()
    item = build_item(
        "task_capacity",
        "等待资料补齐并安排客户推进",
        "佳乐",
        WeeklyReviewTaskStructuredNoteRecord(
            reflection="本周排期已经很满，还在等外部资料。",
            lightweightTag="工作过度饱和",
            supportNeeded="需要补齐项目资料后才能继续推进。",
            completionStatus="in_progress",
        ),
        owner_id="user_jianing",
        org_context=TaskOrgContextRecord(
            departmentId="dept_customer_service",
            roleTemplateId="role_cs_member",
            controlLevel="normal",
            isCrossDepartment=False,
            approvalState="none",
            needsReview=False,
        ),
        project_context=TaskProjectContextRecord(
            clientId="client_demo",
            clientName="示例客户",
            stage="交付推进",
            backgroundSummary="围绕关键客户交付推进组织协同。",
            goalSummary="推进关键客户交付方案。",
            riskSummary="资料未补齐导致推进卡住。",
            infoCompleteness="high",
            sourceEvidence=["客户工作台来源"],
        ),
    )
    analysis = type("AnalysisLike", (), {})()
    analysis.scope = "work"
    analysis.emphasis = "analysis"
    analysis.headline = "本周任务推进受到容量和资料依赖双重影响。"
    analysis.caution = "以下判断是带权重的假设性分析。"
    analysis.metricCards = []
    analysis.evidenceWeights = []
    analysis.confirmedFacts = ["当前已有 1 项写入一线复盘说明。"]
    analysis.hypothesisHighlights = []
    analysis.nextWeekFocus = ["先收束这项任务的资料依赖，再重新安排时间。"]

    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="user_jianing",
        items=[item],
        analysis=analysis,
        org_model_profile=org_profile,
    )

    assert report.sourcePolicy["overloadCount"] == 1
    assert report.sourcePolicy["supportNeedCount"] == 1
    assert report.sourcePolicy["projectRiskCount"] == 1
    assert any(action.actionType == "resource_request" for action in report.actions)
    assert any(action.actionType == "support_request" for action in report.actions)
    assert any(action.actionType == "task" for action in report.actions)


def test_build_employee_review_report_includes_event_line_signals():
    analysis = type("AnalysisLike", (), {})()
    analysis.scope = "work"
    analysis.emphasis = "analysis"
    analysis.headline = "本周事项开始围绕连续工作线推进。"
    analysis.caution = "以下判断是带权重的假设性分析。"
    analysis.metricCards = []
    analysis.evidenceWeights = []
    analysis.confirmedFacts = ["当前已有 2 项写入一线复盘说明。"]
    analysis.hypothesisHighlights = []
    analysis.nextWeekFocus = ["先收束这一条线的后续动作。"]

    items = [
        build_item(
            "task_event_1",
            "推进云南连心第一轮沟通",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(
                reflection="这周先完成第一轮沟通。",
                completionStatus="in_progress",
            ),
            owner_id="user_jianing",
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
        build_item(
            "task_event_2",
            "整理云南连心后续推进方案",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(
                reflection="还需要继续推进后续方案。",
                completionStatus="in_progress",
            ),
            owner_id="user_jianing",
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
    ]

    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="user_jianing",
        items=items,
        analysis=analysis,
    )

    assert report.sourcePolicy["eventLineCount"] == 1
    assert report.sourcePolicy["multiTaskEventLineCount"] == 1
    assert report.sourcePolicy["blockedEventLineCount"] == 1
    assert any("事件线连续推进" in area for area in report.focusAreas)
    assert "事件线" in report.summary
    assert any("事件线" in signal for signal in report.supportSignals)
    assert report.actions
    assert any(action.payload.get("primaryEventLineId") == "event_yunnan" for action in report.actions)
    assert any(action.payload.get("primaryEventLineName") == "云南连心" for action in report.actions)


def test_build_executive_review_rollup_includes_event_line_counts():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_customer_service",
                name="客户服务部",
                monthlyDna="本月重点推进关键客户沟通和交付闭环。",
                weeklyFocus="本周重点收束关键客户沟通结果。",
                members=[ReviewDepartmentMemberRecord(id="user_jianing", fullName="佳乐")],
            )
        ],
        updatedAt="2026-03-21T10:00:00",
    )
    items = [
        build_item(
            "task_org_event_1",
            "推进云南连心第一轮沟通",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(completionStatus="in_progress"),
            owner_id="user_jianing",
            org_context=TaskOrgContextRecord(departmentId="dept_customer_service"),
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
        build_item(
            "task_org_event_2",
            "整理云南连心后续推进方案",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(completionStatus="in_progress"),
            owner_id="user_jianing",
            org_context=TaskOrgContextRecord(departmentId="dept_customer_service"),
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
    ]

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=items,
        governance=governance,
        organization_dna_modules=[],
    )

    assert org_report is not None
    assert len(department_reports) == 1
    assert org_report.sourcePolicy["eventLineCount"] == 1
    assert org_report.sourcePolicy["multiTaskEventLineCount"] == 1
    assert department_reports[0].sourcePolicy["eventLineCount"] == 1
    assert "事件线" in org_report.summary
    assert any("事件线连续推进" in area for area in org_report.focusAreas)
    assert any("｜" in area for area in org_report.focusAreas)
    assert any("事件线" in signal for signal in department_reports[0].supportSignals)


def test_build_employee_review_report_admin_uses_event_line_specific_summary():
    items = [
        build_item(
            "task_admin_report_1",
            "推进黄河基金会合作方案初稿",
            "管理员甲",
            WeeklyReviewTaskStructuredNoteRecord(
                progress="黄河基金会合作方案进入内部讨论阶段。",
                nextAction="补齐方案分工后与黄河基金会确认下一轮沟通。",
                completionStatus="in_progress",
            ),
            owner_id="user_admin_demo",
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
            "task_admin_report_2",
            "补齐黄河基金会下一轮沟通提纲",
            "管理员甲",
            WeeklyReviewTaskStructuredNoteRecord(
                blockerReason="下一轮沟通提纲还没完全收束。",
                completionStatus="in_progress",
            ),
            owner_id="user_admin_demo",
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
    analysis = build_weekly_review_analysis(
        "work",
        "2026-W11",
        items,
        [build_org_module("organization_intro", "组织介绍", "2026 Q2 重点目标：推进关键客户交付与业务扩展。")],
        viewer_role="admin",
    )

    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="user_admin_demo",
        items=items,
        analysis=analysis,
        viewer_role="admin",
    )

    assert report.logicMode == "admin_eventline_context_v1"
    assert "黄河基金会" in report.summary
    assert any("黄河基金会合作推进" in area for area in report.focusAreas)
    assert any("｜" in area for area in report.focusAreas)
    assert not any(card.label == "个人-部门对齐率" for card in report.summaryMetrics)
    assert "推进事项" in report.summary or "黄河基金会合作方案初稿" in report.summary
    assert report.sourcePolicy["eventLineSummaryCount"] >= 1
    assert report.sourcePolicy["eventLineRiskCount"] >= 1
