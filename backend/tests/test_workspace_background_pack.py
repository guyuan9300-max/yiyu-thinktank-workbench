"""P0 · 客户工作台问答的"背景包"单测。

覆盖：
- 空 workspace → 空串（不注入空块）
- 只有客户档案 → 出现客户档案块、没有其它块
- 完整背景（判断 + 会议 + 任务 + 目标 + 模块 + 矛盾 + 待澄清）→ 各 section 都出现
- 已确认判断优先于 draft 判断
- 没有 confirmed 但有 draft → 回退选 draft
- 内容超长 → 被截断到 max_chars
- relatedTasks 中已完成/已归档不进活跃任务
- meetings 按时间倒序（最近的在前）
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.workspace_data_center_adapter import build_workspace_background_pack


def _client(**kw) -> SimpleNamespace:
    defaults = dict(
        id="c1",
        name="A组织",
        alias="",
        domain="",
        type="公益组织",
        intro="儿童心理健康公益机构，深耕乡村学生心理健康支持。",
        stage="2026 年战略升级",
        color="#5B7BFE",
        folderCount=0,
        documentCount=0,
        taskCount=0,
        lastActivityAt="2026-05-10T12:00:00",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _workspace(**kw) -> SimpleNamespace:
    defaults = dict(
        client=_client(),
        folders=[],
        documents=[],
        documentCards=[],
        imports=[],
        knowledgeStatus=None,
        knowledgeJobs=[],
        recentReclassEvents=[],
        surrogateCount=0,
        memoryDocCount=0,
        memoryCards=[],
        threads=[],
        recentMessages=[],
        analysisRuns=[],
        meetings=[],
        goals=[],
        dnaModules=[],
        projectModules=[],
        projectFlows=[],
        dnaTerms=[],
        relatedTasks=[],
        notebookSummary=None,
        memoryStatus=None,
        analysisCenter=None,
        latestContextPack=None,
        judgmentBundle=None,
        latestResolutionTrace=None,
        latestJudgments=[],
        latestTopics=[],
        latestConflicts=[],
        latestOpenQuestions=[],
        latestRunLogs=[],
        stateProjection=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _judgment(topic: str, summary: str, *, status="draft", authorityLevel="fallback",
              confidence="medium", riskLevel="medium") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"j-{topic[:6]}",
        clientId="c1",
        targetType="client",
        targetId="c1",
        topic=topic,
        version=1,
        status=status,
        originType="projection",
        authorityLevel=authorityLevel,
        qualityTier="legacy",
        supersedesId=None,
        sourceSnapshotHash="",
        staleReason=None,
        invalidatedBy=None,
        summary=summary,
        evidenceIds=[],
        contextPackId=None,
        riskLevel=riskLevel,
        confidence=confidence,
        createdAt="2026-05-01T00:00:00",
        updatedAt="2026-05-01T00:00:00",
    )


def _meeting(title: str, *, stage="planning", scheduledAt="", updatedAt="2026-05-01") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"m-{title[:6]}",
        clientId="c1",
        title=title,
        stage=stage,
        scheduledAt=scheduledAt or None,
        updatedAt=updatedAt,
    )


def _task(title: str, *, status="todo", dueDate="", ownerName="") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"t-{title[:6]}",
        title=title,
        desc="",
        status=status,
        creatorId=None,
        creatorName=None,
        priority="normal",
        listId="l1",
        listName="收集箱",
        listColor="#5B7BFE",
        ddl="待确认",
        startDate=None,
        dueDate=dueDate or None,
        deadlineAt=None,
        scheduledStartAt=None,
        scheduledEndAt=None,
        completedAt=None,
        durationMinutes=60,
        scopeMode="COLLAB_SHARED",
        clientId="c1",
        clientName="A组织",
        eventLineId=None,
        eventLineName=None,
        projectModuleId=None,
        projectModuleName=None,
        projectFlowId=None,
        projectFlowName=None,
        ownerId=None,
        ownerName=ownerName,
    )


def _module(name: str, *, goal="", ownerName="") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"pm-{name[:6]}",
        clientId="c1",
        name=name,
        alias=None,
        goal=goal,
        description="",
        ownerName=ownerName or None,
        deliverables=[],
        keywords=[],
        templateTasksJson=None,
        createdAt="",
        updatedAt="",
    )


def _goal(title: str, *, quarter="2026Q2", progress=30) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"g-{title[:6]}",
        clientId="c1",
        title=title,
        quarter=quarter,
        progress=progress,
        ownerName="未指派",
    )


def _conflict(title: str, summary: str, *, severity="medium") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"cf-{title[:6]}",
        clientId="c1",
        scopeType="client",
        scopeId="c1",
        originType="projection",
        authorityLevel="fallback",
        qualityTier="legacy",
        conflictType="ambiguity",
        title=title,
        summary=summary,
        evidenceIds=[],
        unresolvedQuestionIds=[],
        resolutionStatus="draft",
        severity=severity,
        createdAt="",
        updatedAt="",
    )


def _open_question(question: str, *, blockerLevel="medium", reason="") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"oq-{question[:6]}",
        clientId="c1",
        scopeType="client",
        scopeId="c1",
        originType="projection",
        authorityLevel="fallback",
        qualityTier="legacy",
        themeKey="general",
        question=question,
        reason=reason,
        blockerLevel=blockerLevel,
        status="draft",
        createdAt="",
        updatedAt="",
    )


# ---- 测试 -----------------------------------------------------------------


class TestEmpty:
    def test_none_workspace_returns_empty(self) -> None:
        assert build_workspace_background_pack(None) == ""

    def test_workspace_without_anything_returns_at_least_client(self) -> None:
        ws = _workspace(client=_client(name="新客户", intro="", stage="", lastActivityAt=None))
        result = build_workspace_background_pack(ws)
        assert "新客户" in result
        assert "已确认核心判断" not in result
        assert "当前推进重点" not in result


class TestClientArchive:
    def test_archive_includes_all_fields(self) -> None:
        ws = _workspace(client=_client(
            name="A组织",
            alias="A组织",
            type="公益组织",
            stage="2026 战略升级",
            intro="儿童心理健康公益机构",
            lastActivityAt="2026-05-10T12:00:00",
        ))
        result = build_workspace_background_pack(ws)
        assert "A组织" in result
        assert "A组织" in result
        assert "公益组织" in result
        assert "2026 战略升级" in result
        assert "儿童心理健康公益机构" in result
        assert "2026-05-10T12:00:00" in result


class TestJudgments:
    def test_confirmed_judgments_preferred(self) -> None:
        ws = _workspace(latestJudgments=[
            _judgment("草稿判断", "这是个 draft，不应该被选中", status="draft"),
            _judgment("确认判断", "这是 confirmed 判断", status="confirmed"),
            _judgment("已批准判断", "这是 approved 的", status="approved"),
        ])
        result = build_workspace_background_pack(ws)
        assert "确认判断" in result
        assert "已批准判断" in result
        assert "草稿判断" not in result

    def test_falls_back_to_draft_when_no_confirmed(self) -> None:
        ws = _workspace(latestJudgments=[
            _judgment("仅有草稿", "这家组织当前的核心待证假设", status="draft"),
        ])
        result = build_workspace_background_pack(ws)
        assert "仅有草稿" in result

    def test_judgment_meta_appears(self) -> None:
        ws = _workspace(latestJudgments=[
            _judgment("核心判断", "summary here", status="confirmed", confidence="high", riskLevel="low"),
        ])
        result = build_workspace_background_pack(ws)
        assert "信心=high" in result
        assert "风险=low" in result


class TestActiveDrive:
    def test_active_tasks_only(self) -> None:
        ws = _workspace(relatedTasks=[
            _task("活跃任务", status="todo"),
            _task("已完成任务", status="done"),
            _task("已归档任务", status="archived"),
            _task("已完成 completed", status="completed"),
            _task("已取消", status="cancelled"),
        ])
        result = build_workspace_background_pack(ws)
        assert "活跃任务" in result
        assert "已完成任务" not in result
        assert "已归档任务" not in result
        assert "已完成 completed" not in result
        assert "已取消" not in result

    def test_meetings_sorted_by_recency(self) -> None:
        ws = _workspace(meetings=[
            _meeting("旧会议", scheduledAt="2026-01-01"),
            _meeting("最新会议", scheduledAt="2026-05-10"),
            _meeting("中间会议", scheduledAt="2026-03-15"),
        ])
        result = build_workspace_background_pack(ws, meeting_limit=3)
        idx_recent = result.find("最新会议")
        idx_middle = result.find("中间会议")
        idx_old = result.find("旧会议")
        assert idx_recent != -1 and idx_middle != -1 and idx_old != -1
        assert idx_recent < idx_middle < idx_old

    def test_project_modules_appear(self) -> None:
        ws = _workspace(projectModules=[
            _module("升级品牌", goal="完成品牌识别更新", ownerName="管理员甲"),
        ])
        result = build_workspace_background_pack(ws)
        assert "升级品牌" in result
        assert "完成品牌识别更新" in result
        assert "管理员甲" in result

    def test_goals_appear_with_progress(self) -> None:
        ws = _workspace(goals=[_goal("Q2 提升小学项目覆盖率", quarter="2026Q2", progress=45)])
        result = build_workspace_background_pack(ws)
        assert "Q2 提升小学项目覆盖率" in result
        assert "2026Q2" in result
        assert "45%" in result


class TestFlags:
    def test_conflicts_and_open_questions(self) -> None:
        ws = _workspace(
            latestConflicts=[_conflict("数据口径冲突", "财务报表与公开年报数字不一致", severity="high")],
            latestOpenQuestions=[_open_question("是否启动第二曲线？", blockerLevel="high", reason="资源不足")],
        )
        result = build_workspace_background_pack(ws)
        assert "矛盾" in result
        assert "数据口径冲突" in result
        assert "待澄清" in result
        assert "是否启动第二曲线？" in result
        assert "阻塞=high" in result


class TestTruncation:
    def test_max_chars_truncates(self) -> None:
        long_summary = "对该组织当前关键判断的详尽描述。" * 200
        ws = _workspace(latestJudgments=[
            _judgment(f"判断 {i}", long_summary, status="confirmed") for i in range(20)
        ])
        result = build_workspace_background_pack(
            ws,
            max_chars=1500,
            judgment_limit=20,  # 拉大上限，让总长度有机会超过 max_chars
        )
        assert len(result) <= 1500
        assert result.endswith("…")


class TestFullPicture:
    def test_all_sections_compose(self) -> None:
        ws = _workspace(
            client=_client(name="A组织"),
            latestJudgments=[_judgment("战略核心", "聚焦乡村心理健康", status="confirmed")],
            projectModules=[_module("品牌升级")],
            meetings=[_meeting("月度复盘", scheduledAt="2026-05-08")],
            relatedTasks=[_task("更新官网", status="in_progress", dueDate="2026-05-20")],
            goals=[_goal("Q2 增长", progress=55)],
            latestConflicts=[_conflict("数据口径", "需要核对")],
            latestOpenQuestions=[_open_question("是否上新产品线")],
        )
        result = build_workspace_background_pack(ws)
        # 四大块都在
        assert "客户背景包" in result
        assert "已确认核心判断" in result
        assert "当前推进重点" in result
        assert "矛盾" in result
        # 详细内容也在
        assert "战略核心" in result
        assert "品牌升级" in result
        assert "月度复盘" in result
        assert "更新官网" in result
        assert "Q2 增长" in result
