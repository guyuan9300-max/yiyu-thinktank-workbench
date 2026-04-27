from pathlib import Path

from app.db import Database
from app.services.agent_worklogs import (
    AGENT_AUTO_SOURCE_TYPE,
    build_agent_execution_task_activity,
    build_agent_execution_tasks,
    build_agent_weekly_digests,
    build_agent_weekly_plans,
    build_agent_weekly_review_items,
    build_agent_worklog_response,
    sync_agent_execution_tasks,
)


def test_build_agent_worklog_response_reads_db_and_thread_sync(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        ("log_1", "庆华", "review.create", "weekly_review", "review_1", "{}", "2026-03-15T10:00:00"),
    )
    db.execute(
        "INSERT INTO topic_radars(id, title, prompt, time_range, preferred_sources_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
        ("radar_1", "公益行业动态", "关注公益行业变化", "3_days", "[]", "2026-03-01T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO topic_candidates(
            id, radar_id, title, summary, source, source_url, published_at, capture_method, captured_by, status, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "cand_1",
            "radar_1",
            "新增行业情报",
            "一条新的行业情报",
            "公益时报",
            "https://example.com/1",
            "2026-03-15",
            "web_search",
            "大周",
            "tracking",
            "2026-03-15T11:00:00",
            "2026-03-15T11:00:00",
        ),
    )
    db.execute(
        "INSERT INTO tasks(id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("task_1", "推进战略问答整理", "", "doing", "high", "list-0", "庆华", "周五", "manual", None, "[]", "[]", "2026-03-15T09:00:00", "2026-03-15T09:30:00"),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text(
        "\n".join(
            [
                "# Thread Sync",
                "## 2026-03-15 科技发展部线程",
                "- 当前状态：已完成软件系统主线接线。",
                "- 风险点：还需要继续做真实验收。",
            ]
        ),
        encoding="utf-8",
    )

    response = build_agent_worklog_response(
        db=db,
        month_label="2026-03",
        thread_sync_path=thread_sync_path,
    )

    assert response.month == "2026-03"
    assert len(response.worklogs) == 3
    assert {item.agentName for item in response.worklogs} == {"庆华", "大周", "佳乐"}
    assert any(item.agentName == "佳乐" and "软件系统主线接线" in item.summary for item in response.worklogs)
    assert any(item.agentName == "大周" and "新增 1 条情报线索" in item.title for item in response.worklogs)
    assert any(digest.agentName == "庆华" and digest.focusItems for digest in response.weeklyDigests)
    assert any(plan.agentName == "庆华" and plan.planItems for plan in response.weeklyPlans)


def test_monthly_worklog_response_uses_full_week_digest_range(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        ("log_1", "庆华", "task.update", "task", "task_1", "{}", "2026-03-31T09:00:00"),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        ("log_2", "庆华", "review.create", "weekly_review", "review_1", "{}", "2026-04-01T10:00:00"),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    monthly_response = build_agent_worklog_response(
        db=db,
        month_label="2026-03",
        thread_sync_path=thread_sync_path,
    )
    march_digest = next((item for item in monthly_response.weeklyDigests if item.agentName == "庆华" and item.weekLabel == "2026-W14"), None)
    assert march_digest is not None
    assert march_digest.evidenceCount == 2

    weekly_digests = build_agent_weekly_digests(
        db=db,
        week_label="2026-W14",
        thread_sync_path=thread_sync_path,
    )
    assert len(weekly_digests) == 1
    assert weekly_digests[0].agentName == "庆华"
    assert weekly_digests[0].evidenceCount == 2

    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label="2026-W14",
        thread_sync_path=thread_sync_path,
    )
    assert len(weekly_plans) == 1
    assert weekly_plans[0].agentName == "庆华"
    assert weekly_plans[0].planItems
    assert "真实日志推演" in weekly_plans[0].summary


def test_weekly_plans_apply_manual_override(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        ("log_1", "庆华", "task.update", "task", "task_1", "{}", "2026-03-17T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO agent_weekly_plan_overrides(
            id, week_label, agent_key, summary, plan_items_json, updated_by, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "override_1",
            "2026-W12",
            "strategy_design",
            "CEO 手动修订后的战略周计划。",
            '[{"title":"优先校准机构级判断","rationale":"来自 CEO 调整","scheduleHint":"周二前完成","status":"doing"}]',
            "顾源源",
            "2026-03-17T10:00:00",
            "2026-03-17T10:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    qinghua_plan = next(item for item in weekly_plans if item.agentName == "庆华")
    assert qinghua_plan.summary == "CEO 手动修订后的战略周计划。"
    assert qinghua_plan.planItems[0].title == "优先校准机构级判断"
    assert qinghua_plan.planItems[0].status == "doing"
    assert qinghua_plan.sourcePolicy.get("manualOverride") is True


def test_derived_weekly_plan_status_updates_from_real_logs(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text(
        "\n".join(
            [
                "# Thread Sync",
                "## 2026-03-18 科技发展部线程",
                "- 当前状态：已完成软件系统主线接线。",
                "- 风险点：仍需继续做真实验收。",
            ]
        ),
        encoding="utf-8",
    )

    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    jiale_plan = next(item for item in weekly_plans if item.agentName == "佳乐")
    assert jiale_plan.planItems[0].status in {"done", "blocked"}
    assert jiale_plan.sourcePolicy.get("autoStatus") is True


def test_build_agent_weekly_review_items_turns_robot_work_into_review_samples(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (
            "log_1",
            "庆华",
            "task.update",
            "task",
            "task_1",
            '{"title":"完成战略判断整理"}',
            "2026-03-17T09:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    items = build_agent_weekly_review_items(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    qinghua_item = next(item for item in items if item.taskSnapshot.ownerName == "庆华")
    assert qinghua_item.taskSnapshot.ownerId == "agent:strategy_design"
    assert qinghua_item.structuredNote.departmentPlanAlignment == "aligned"
    assert qinghua_item.structuredNote.planCommitment
    assert qinghua_item.taskSnapshot.listName == "咨询策略部"


def test_sync_agent_execution_tasks_writes_robot_tasks_into_local_task_table(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (
            "log_1",
            "庆华",
            "task.update",
            "task",
            "task_1",
            '{"title":"完成战略判断整理"}',
            "2026-03-17T09:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    task_ids = sync_agent_execution_tasks(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    assert task_ids
    row = db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_ids[0],))
    assert row is not None
    assert str(row["source_type"]) == AGENT_AUTO_SOURCE_TYPE
    assert str(row["owner_name"]) == "庆华"
    note_row = db.fetchone("SELECT * FROM task_notes WHERE task_id = ?", (task_ids[0],))
    assert note_row is not None


def test_build_agent_execution_tasks_returns_formal_task_records(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (
            "log_1",
            "庆华",
            "task.update",
            "task",
            "task_1",
            '{"title":"完成战略判断整理"}',
            "2026-03-17T09:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    tasks = build_agent_execution_tasks(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    assert tasks
    assert tasks[0].sourceType == AGENT_AUTO_SOURCE_TYPE
    assert tasks[0].ownerName == "庆华"
    assert tasks[0].creatorId == "agent:strategy_design"
    assert tasks[0].tags


def test_build_agent_execution_task_activity_uses_worklogs(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (
            "log_1",
            "庆华",
            "review.create",
            "weekly_review",
            "review_1",
            '{"title":"完成战略判断整理"}',
            "2026-03-17T09:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    task_ids = sync_agent_execution_tasks(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )
    activities = build_agent_execution_task_activity(
        db=db,
        task_id=task_ids[0],
        thread_sync_path=thread_sync_path,
    )

    assert activities
    assert activities[0].taskId == task_ids[0]
    assert any(item.eventType == "agent.plan_synced" for item in activities)
