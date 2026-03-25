import json
from pathlib import Path

from app.db import Database
from app.models import (
    DecisionItem,
    HandbookEntryRecord,
    MeetingDetail,
    StrategicChecklistItemRecord,
    StrategicCockpitSnapshotRecord,
    StrategicEvidencePreviewRecord,
    StrategicHeadlineRecord,
    StrategicJudgmentRecord,
    StrategicLineRecord,
    StrategicMeetingPackDraftRecord,
    StrategicPermissionRecord,
    StrategicReadinessRecord,
    TaskAttachmentRecord,
    TaskProjectContextRecord,
    TaskRecord,
    TaskTagRecord,
    WeeklyReviewRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.growth_engine import (
    build_growth_overview,
    ingest_handbook_codification,
    ingest_meeting_growth_candidate,
    ingest_review_growth,
    ingest_strategic_growth_candidate,
    ingest_task_growth_candidate,
    list_learning_recommendations,
    mark_handbook_entry_reused,
    update_pending_capture_state,
)


def make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def make_review() -> WeeklyReviewRecord:
    return WeeklyReviewRecord(
        id="review_1",
        userId="op_1",
        userName="测试用户",
        weekLabel="2026-W11",
        workFreeNote="",
        personalGrowthNote="",
        personalPrivateNote="",
        submittedAt="2026-03-16T10:00:00",
        createdAt="2026-03-16T10:00:00",
        updatedAt="2026-03-16T10:00:00",
    )


def seed_client_and_event_line(db: Database) -> None:
    db.execute(
        "INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("client_1", "日慈基金会", "日慈", "philanthropy", "client", "公益客户", "active", "2026-03-10T09:00:00", "2026-03-10T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, business_category, stage, summary, intent, current_blocker, recent_decision, next_step,
            evidence_count, owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, 'project_line', 'active', ?, ?, ?, ?, ?, ?, ?, 2, ?, ?, ?, ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            "eline_1",
            "日慈战略陪伴主线",
            "strategic_accompaniment",
            "内部对齐",
            "围绕年度重点形成季度推进闭环",
            "帮助基金会完成战略陪伴闭环",
            "跨部门信息口径还未统一",
            "先对齐今年核心议题",
            "补会前材料",
            "op_1",
            "测试用户",
            "client_1",
            "日慈基金会",
            "2026-03-10T09:00:00",
            "2026-03-10T09:00:00",
        ),
    )


def make_context_task() -> TaskRecord:
    return TaskRecord(
        id="task_ctx_1",
        title="日慈基金会季度对齐会筹备",
        desc="需要围绕年度重点补齐会前材料和关键议题。",
        status="doing",
        priority="high",
        listId="list_1",
        listName="默认清单",
        listColor="#5B7BFE",
        ddl="2026-03-20",
        dueDate="2026-03-20",
        clientId="client_1",
        clientName="日慈基金会",
        eventLineId="eline_1",
        eventLineName="日慈战略陪伴主线",
        ownerId="op_1",
        ownerName="测试用户",
        sourceType="manual",
        businessCategory="strategic_accompaniment",
        currentBlocker="会议材料还不完整",
        nextAction="补齐会前材料并确认负责人",
        recentDecision="先围绕核心议题收口再拉会",
        evidenceCount=2,
        tags=[],
        attachments=[
            TaskAttachmentRecord(
                id="attach_1",
                taskId="task_ctx_1",
                clientId="client_1",
                eventLineId="eline_1",
                title="日慈季度重点草稿",
                path="/tmp/mock.md",
                kind="markdown",
                source="local",
                sizeBytes=32,
                createdAt="2026-03-16T09:00:00",
            )
        ],
        collaborators=[],
        collaborationSummary={},
        projectContext=TaskProjectContextRecord(
            clientId="client_1",
            clientName="日慈基金会",
            stage="内部对齐",
            projectModuleId="module_1",
            projectModuleName="战略陪伴",
            projectFlowId="flow_1",
            projectFlowName="战略陪伴会前推进",
            backgroundSummary="当前项目需要先对齐今年重点议题",
            goalSummary="形成季度对齐会结论",
            riskSummary="会议目标容易发散",
            currentFocus="聚焦本季度关键议题",
            currentBlocker="材料未齐",
            nextAction="补齐会前材料",
            recentProgress="已形成初步议题",
            infoCompleteness="medium",
            sourceEvidence=["季度议题草稿"],
        ),
        memoryHints=["先确认负责人和时间点"],
        createdAt="2026-03-16T09:00:00",
        updatedAt="2026-03-16T09:30:00",
    )


def make_task_entry(
    *,
    note: str = "",
    progress: str = "",
    success_experience: str = "",
    success_reason: str = "",
    blocker_reason: str = "",
    support_needed: str = "",
    status: str = "done",
) -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id="review_item_1",
        reviewId="review_1",
        taskId="task_1",
        weekLabel="2026-W11",
        contentDomain="work",
        note=note,
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(
            progress=progress,
            successExperience=success_experience,
            successReason=success_reason,
            blockerReason=blocker_reason,
            supportNeeded=support_needed,
            completionStatus="done_on_time" if status == "done" else "in_progress",
        ),
        reviewedAt="2026-03-16T10:00:00",
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(
            title="跨组会议闭环",
            status=status,  # type: ignore[arg-type]
            dueDate=None,
            createdAt="2026-03-10T09:00:00",
            ownerId="op_1",
            ownerName="测试用户",
            tags=[TaskTagRecord(id="tag_1", name="会议", color="#5B7BFE", scope="org", updatedAt="2026-03-10T09:00:00")],
            listName="默认清单",
            listColor="#5B7BFE",
        ),
    )


def test_done_task_without_reflection_does_not_gain_xp(tmp_path: Path):
    db = make_db(tmp_path)
    review = make_review()
    entry = make_task_entry(status="done")

    ingest_review_growth(db, user_id="op_1", user_name="测试用户", review=review, task_entries=[entry], created_at="2026-03-16T10:00:00")

    rows = db.fetchall("SELECT * FROM xp_ledger")
    assert rows == []


def test_task_candidate_creates_pending_capture_without_direct_xp(tmp_path: Path):
    db = make_db(tmp_path)
    seed_client_and_event_line(db)
    task = make_context_task()

    ingest_task_growth_candidate(db, user_id="op_1", user_name="测试用户", task=task, created_at="2026-03-16T09:30:00")

    signal_rows = db.fetchall("SELECT source_type, source_id, task_id FROM growth_signal_events ORDER BY created_at DESC")
    assert signal_rows
    assert str(signal_rows[0]["source_type"]) == "task_context_candidate"
    assert str(signal_rows[0]["source_id"]) == task.id

    xp_rows = db.fetchall("SELECT * FROM xp_ledger")
    assert xp_rows == []

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert overview.pendingCaptures
    assert any(item.sourceId == task.id and item.eventLineId == "eline_1" for item in overview.pendingCaptures)
    assert any(
        any(link.objectType == "project_module" and link.objectId == "module_1" for link in item.linkedContexts)
        and any(link.objectType == "project_flow" and link.objectId == "flow_1" for link in item.linkedContexts)
        for item in overview.pendingCaptures
    )


def test_pending_capture_state_removes_item_from_open_queue(tmp_path: Path):
    db = make_db(tmp_path)
    seed_client_and_event_line(db)
    task = make_context_task()

    ingest_task_growth_candidate(db, user_id="op_1", user_name="测试用户", task=task, created_at="2026-03-16T09:30:00")

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert overview.pendingCaptures
    capture = overview.pendingCaptures[0]

    updated = update_pending_capture_state(
        db,
        user_id="op_1",
        capture_id=capture.id,
        status="dismissed",
        reason="这条候选信号先不进入本周成长队列",
        created_at="2026-03-16T09:45:00",
    )

    assert updated is not None
    assert updated.status == "dismissed"
    assert updated.stateReason == "这条候选信号先不进入本周成长队列"

    refreshed = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert all(item.id != capture.id for item in refreshed.pendingCaptures)

    state_row = db.fetchone("SELECT status, reason FROM growth_capture_states WHERE signal_id = ?", (capture.id,))
    assert state_row is not None
    assert str(state_row["status"]) == "dismissed"
    assert str(state_row["reason"]) == "这条候选信号先不进入本周成长队列"


def test_review_ingestion_is_idempotent_and_records_reflection_xp(tmp_path: Path):
    db = make_db(tmp_path)
    review = make_review()
    entry = make_task_entry(
        note="因为跨组会议容易只停在纪要，所以这次强制写了负责人和时间点，推进闭环明显更顺。",
        progress="本周完成了跨组会议收口，并把行动项同步进任务系统。",
        success_experience="会议必须写清负责人、时间点和依赖项，否则无法闭环。",
        success_reason="因为多人协作里如果边界不清，后续推进就会返工。",
        blocker_reason="前期也暴露过依赖不明确的风险。",
        support_needed="需要设计组更早确认接口边界。",
    )

    ingest_review_growth(db, user_id="op_1", user_name="测试用户", review=review, task_entries=[entry], created_at="2026-03-16T10:00:00")
    first_rows = db.fetchall("SELECT ability_key, xp_type, delta, base_xp, premium_rate, premium_xp, total_xp FROM xp_ledger ORDER BY id ASC")
    assert first_rows
    assert any(str(row["ability_key"]) == "exec" for row in first_rows)
    assert any(str(row["ability_key"]) == "collab" for row in first_rows)
    assert any(int(row["premium_xp"] or 0) > 0 for row in first_rows)
    assert all(int(row["total_xp"] or 0) == int(row["delta"] or 0) for row in first_rows)
    assert all(int(row["total_xp"] or 0) >= int(row["base_xp"] or 0) for row in first_rows)

    ingest_review_growth(db, user_id="op_1", user_name="测试用户", review=review, task_entries=[entry], created_at="2026-03-16T10:05:00")
    second_rows = db.fetchall("SELECT ability_key, xp_type, delta, base_xp, premium_rate, premium_xp, total_xp FROM xp_ledger ORDER BY id ASC")
    assert len(second_rows) == len(first_rows)
    assert sorted((row["ability_key"], row["xp_type"], row["delta"], row["base_xp"], row["premium_xp"], row["total_xp"]) for row in second_rows) == sorted(
        (row["ability_key"], row["xp_type"], row["delta"], row["base_xp"], row["premium_xp"], row["total_xp"]) for row in first_rows
    )

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert overview.weeklyXp > 0
    assert overview.weeklyBaseXp > 0
    assert overview.weeklyPremiumXp > 0
    assert overview.rank.key
    assert overview.rank.fullLabel
    assert 0 <= overview.rank.progress <= 1


def test_handbook_codification_updates_write_ability_and_generates_recommendations(tmp_path: Path):
    db = make_db(tmp_path)
    entry = HandbookEntryRecord(
        id="handbook_1",
        title="会后行动项清单模板",
        summary="把会议结论沉淀成负责人、时间点、依赖项和跟进方式，后续可以复用到跨组协作里。",
        tags=["会议", "模板", "复用"],
        sourceType="meeting",
        clientId=None,
        createdAt="2026-03-16T12:00:00",
    )

    ingest_handbook_codification(db, user_id="op_1", user_name="测试用户", entry=entry, created_at="2026-03-16T12:00:00")

    ledger_rows = db.fetchall("SELECT ability_key, xp_type, premium_rate, validation_state FROM xp_ledger ORDER BY id ASC")
    assert any(str(row["ability_key"]) == "write" and str(row["xp_type"]) == "codification" for row in ledger_rows)
    assert any(float(row["premium_rate"] or 0) >= 0.2 for row in ledger_rows)
    assert all(str(row["validation_state"] or "") in {"candidate", "observed", "validated", "institutionalized"} for row in ledger_rows)

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert any(item.abilityKey == "write" and item.totalXp > 0 for item in overview.abilities)
    assert overview.weeklyBaseXp == 0
    assert overview.weeklyPremiumXp == 0
    assert overview.rank.name

    recommendations = list_learning_recommendations(db, "op_1")
    assert recommendations
    assert all(item.status == "active" for item in recommendations)


def test_meeting_candidate_generates_contextual_growth_entries(tmp_path: Path):
    db = make_db(tmp_path)
    seed_client_and_event_line(db)
    meeting = MeetingDetail(
        id="meeting_1",
        clientId="client_1",
        title="日慈基金会季度复盘会",
        stage="published",
        scheduledAt="2026-03-16T14:00:00",
        updatedAt="2026-03-16T16:00:00",
        transcriptText="这次会议先统一目标，再明确负责人和时间点。",
        notes="需要把关键结论转成行动项并挂回任务系统。",
        agendaItems=[],
        decisions=[DecisionItem(id="decision_1", summary="先围绕两个核心议题收口，再继续推进")],
        actionItems=[],
        risks=[],
        ambiguities=[],
    )

    ingest_meeting_growth_candidate(
        db,
        user_id="op_1",
        user_name="测试用户",
        client_id="client_1",
        meeting=meeting,
        event_line_ids=["eline_1"],
        created_at="2026-03-16T16:00:00",
    )

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W12")
    assert overview.weeklyXp > 0
    assert any(entry.meetingId == "meeting_1" and entry.clientId == "client_1" and entry.eventLineId == "eline_1" for entry in overview.recentEntries)
    assert any(item.label == "日慈基金会" for item in overview.projectGrowthHighlights)


def test_strategic_candidate_records_alignment_context(tmp_path: Path):
    db = make_db(tmp_path)
    snapshot = StrategicCockpitSnapshotRecord(
        clientId="client_1",
        clientName="日慈基金会",
        clientTagline="公益战略陪伴",
        stageLabel="战略判断",
        permission=StrategicPermissionRecord(canEdit=True, isCeo=False, leaderUserId="op_1"),
        readiness=StrategicReadinessRecord(status="ready", score=82, summary="核心材料已齐"),
        headline=StrategicHeadlineRecord(
            weekSummary=StrategicJudgmentRecord(value="本周先统一季度重点"),
            mainContradiction=StrategicJudgmentRecord(value="当前最大矛盾是跨部门信息没有对齐"),
            coreBreakthrough=StrategicJudgmentRecord(value="先锁定季度战略陪伴闭环"),
            focusItems=["季度重点", "跨部门协作"],
            focusStatus="confirmed",
            freshness="high",
        ),
        health=[],
        strategicLines=[
            StrategicLineRecord(
                id="sl_quarter_focus",
                title="季度战略陪伴闭环",
                summary="本季度先把战略陪伴闭环跑通，再决定是否扩展范围。",
                module="战略陪伴",
                flow="周判断",
                stage="战略判断",
                blocker="跨部门口径还没有统一",
                decision="先锁定季度战略陪伴闭环",
                nextStep="确认季度重点并分负责人",
                momentum="稳住",
                evidence=["季度重点草稿"],
            )
        ],
        twoWeekChanges=[],
        pendingDecisions=[StrategicChecklistItemRecord(title="确认季度重点", detail="先和核心负责人对齐", source="ceo", priority="high")],
        pendingMaterials=[],
        meetingPackDraft=StrategicMeetingPackDraftRecord(title="战略周会包", agenda=["确认季度重点", "收口协作边界"], groups=[]),
        evidencePreview=StrategicEvidencePreviewRecord(summary="已有季度重点草稿"),
        assetCandidates=[],
    )

    ingest_strategic_growth_candidate(
        db,
        user_id="op_1",
        user_name="测试用户",
        snapshot=snapshot,
        source_type="strategic_confirm",
        source_id="strategy_1",
        created_at="2026-03-16T18:00:00",
    )

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W12")
    assert any(entry.sourceType == "strategic_confirm" and entry.strategicLink for entry in overview.recentEntries)
    assert any(item.type == "strategic" for item in overview.strategicAlignmentHighlights)
    assert any(
        link.objectType == "strategic_focus"
        and link.objectId == "client_1:sl_quarter_focus"
        and link.label == "季度战略陪伴闭环"
        for entry in overview.recentEntries
        for link in entry.linkedContexts
    )


def test_handbook_reuse_creates_weekly_reuse_xp_and_dedupes_by_week(tmp_path: Path):
    db = make_db(tmp_path)
    entry = HandbookEntryRecord(
        id="handbook_1",
        title="会后行动项清单模板",
        summary="把会议结论沉淀成负责人、时间点、依赖项和跟进方式，后续可以复用到跨组协作里。",
        tags=["会议", "模板", "复用"],
        sourceType="meeting",
        clientId=None,
        createdAt="2026-03-16T12:00:00",
    )

    ingest_handbook_codification(db, user_id="op_1", user_name="测试用户", entry=entry, created_at="2026-03-16T12:00:00")

    response = mark_handbook_entry_reused(
        db,
        user_id="op_1",
        user_name="测试用户",
        entry=entry,
        week_label="2026-W11",
        source_type="handbook_manual_reuse",
        source_id="2026-W11",
        note="设计组继续沿用这张方法卡",
        created_at="2026-03-16T13:00:00",
    )

    assert response.duplicate is False
    assert response.gainedXp > 0
    assert response.createdEntries > 0
    assert response.validationState in {"validated", "institutionalized"}

    weekly_rows = db.fetchall(
        "SELECT xp_type, week_label, premium_rate, validation_state FROM xp_ledger WHERE week_label = ? ORDER BY id ASC",
        ("2026-W11",),
    )
    assert any(str(row["xp_type"]) == "reuse" for row in weekly_rows)
    assert all(float(row["premium_rate"] or 0) >= 0.4 for row in weekly_rows)
    assert all(str(row["validation_state"] or "") in {"validated", "institutionalized"} for row in weekly_rows)

    validation_rows = db.fetchall("SELECT event_type, source_type, source_id FROM growth_validation_events ORDER BY id ASC")
    assert validation_rows
    assert all(str(row["event_type"]) == "handbook_reused" for row in validation_rows)

    duplicate = mark_handbook_entry_reused(
        db,
        user_id="op_1",
        user_name="测试用户",
        entry=entry,
        week_label="2026-W11",
        source_type="handbook_manual_reuse",
        source_id="2026-W11",
        note="设计组继续沿用这张方法卡",
        created_at="2026-03-16T13:05:00",
    )
    assert duplicate.duplicate is True
    assert duplicate.gainedXp == 0

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert overview.weeklyXp > 0
    assert overview.weeklyBaseXp > 0
    assert overview.weeklyPremiumXp > 0
    assert overview.rank.nextName is not None or overview.rank.key == "legend"


def test_handbook_reuse_records_hard_context_evidence(tmp_path: Path):
    db = make_db(tmp_path)
    entry = HandbookEntryRecord(
        id="handbook_ctx_1",
        title="会前边界澄清模板",
        summary="在跨部门会议前先澄清交付边界、负责人和预期结论，减少推诿返工。",
        tags=["会议", "模板", "边界"],
        sourceType="meeting",
        clientId="client_1",
        clientName="日慈基金会",
        eventLineId="eline_1",
        eventLineName="日慈战略陪伴主线",
        projectStage="内部对齐",
        sourceObjectType="meeting",
        sourceObjectId="meeting_1",
        sourceTitle="日慈基金会季度复盘会",
        contextSummary="这条模板主要用于跨部门会前对齐和会后责任收口。",
        createdAt="2026-03-16T12:00:00",
    )

    ingest_handbook_codification(db, user_id="op_1", user_name="测试用户", entry=entry, created_at="2026-03-16T12:00:00")

    response = mark_handbook_entry_reused(
        db,
        user_id="op_1",
        user_name="测试用户",
        entry=entry,
        week_label="2026-W11",
        source_type="task",
        source_id="task_ctx_1",
        source_label="日慈基金会季度对齐会筹备",
        context_summary="这次复用发生在会前准备阶段，直接用于收口跨组协作边界。",
        linked_contexts=[
            {
                "objectType": "task",
                "objectId": "task_ctx_1",
                "label": "日慈基金会季度对齐会筹备",
                "subtitle": "内部对齐",
                "tab": "tasks",
                "statusLabel": "进行中",
            },
            {
                "objectType": "event_line",
                "objectId": "eline_1",
                "label": "日慈战略陪伴主线",
                "subtitle": "战略陪伴",
                "tab": "tasks",
                "statusLabel": "active",
            },
        ],
        note="在当前任务里继续沿用这套边界澄清模板",
        created_at="2026-03-16T13:00:00",
    )

    assert response.duplicate is False
    validation_row = db.fetchone(
        "SELECT detail_json FROM growth_validation_events WHERE source_type = ? AND source_id = ? ORDER BY created_at DESC LIMIT 1",
        ("task", "task_ctx_1"),
    )
    assert validation_row is not None
    detail = json.loads(str(validation_row["detail_json"]))
    assert detail["sourceLabel"] == "日慈基金会季度对齐会筹备"
    assert detail["contextSummary"] == "这次复用发生在会前准备阶段，直接用于收口跨组协作边界。"
    assert any(link["objectType"] == "task" and link["objectId"] == "task_ctx_1" for link in detail["linkedContexts"])

    signal_row = db.fetchone(
        "SELECT context_json FROM growth_signal_events WHERE source_type = ? AND source_id = ? ORDER BY created_at DESC LIMIT 1",
        ("handbook_reuse", "handbook_ctx_1:task_ctx_1"),
    )
    assert signal_row is not None
    signal_context = json.loads(str(signal_row["context_json"]))
    assert signal_context["sourceObjectType"] == "meeting"
    assert signal_context["sourceTitle"] == "日慈基金会季度复盘会"
    assert signal_context["sourceLabel"] == "日慈基金会季度对齐会筹备"
    assert any(link["objectType"] == "event_line" and link["objectId"] == "eline_1" for link in signal_context["linkedContexts"])
