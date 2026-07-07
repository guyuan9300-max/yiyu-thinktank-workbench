from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import Database, to_json
from app.main import create_app
from app.services.badge_engine import build_badge_board


def make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def seed_client(db: Database) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_1', '测试客户', '测试', 'example.com', 'B2B', '测试客户', 'active', '2026-03-01T09:00:00', '2026-03-01T09:00:00')
        """
    )


def seed_task_list(db: Database) -> None:
    db.execute(
        """
        INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at)
        VALUES('list_1', '默认清单', '#5B7BFE', 0, 1, NULL)
        """
    )


def test_closed_loop_meeting_badge_unlocks_and_awards_xp(tmp_path: Path):
    db = make_db(tmp_path)
    seed_client(db)
    seed_task_list(db)

    for index in range(3):
        meeting_id = f"meeting_{index}"
        date = f"2026-03-1{index + 1}T10:00:00"
        db.execute(
            """
            INSERT INTO meetings(id, client_id, title, stage, scheduled_at, transcript_text, notes, created_at, updated_at)
            VALUES(?, 'client_1', ?, 'published', ?, '', '跨组对齐', ?, ?)
            """,
            (meeting_id, f"第{index + 1}次闭环会议", date, date, date),
        )
        db.execute(
            """
            INSERT INTO decisions(id, meeting_id, summary, created_at)
            VALUES(?, ?, '会议已有明确结论', ?)
            """,
            (f"decision_{index}", meeting_id, date),
        )
        db.execute(
            """
            INSERT INTO action_items(id, meeting_id, title, owner_name, due_date, confidence, publish_status, created_at)
            VALUES(?, ?, '跟进行动项', '测试用户', '2026-03-20', 0.9, 'published', ?)
            """,
            (f"action_{index}", meeting_id, date),
        )
        db.execute(
            """
            INSERT INTO tasks(id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at)
            VALUES(?, '会议行动项', '', 'done', 'normal', 'list_1', '测试用户', '2026-03-20T18:00:00', 'meeting', ?, '[]', '[]', ?, ?)
            """,
            (f"task_{index}", meeting_id, date, date),
        )

    board = build_badge_board(db, user_id="op_1", user_name="测试用户", auto_sync=True)
    badge = next(item for category in board.categories for item in category.badges if item.id == "post_meeting_closer")

    assert badge.state in {"lit", "mastered"}
    assert badge.unlockedAt is not None
    assert badge.progressValue >= badge.progressTarget
    assert badge.evidence

    unlock_rows = db.fetchall("SELECT badge_id, xp FROM badge_unlock_records ORDER BY unlocked_at DESC")
    assert any(str(row["badge_id"]) == "post_meeting_closer" and int(row["xp"]) == 15 for row in unlock_rows)

    ledger_rows = db.fetchall(
        """
        SELECT l.total_xp, s.source_type, s.source_id
        FROM xp_ledger l
        INNER JOIN growth_evidence_records e ON e.id = l.evidence_id
        INNER JOIN growth_signal_events s ON s.id = e.signal_id
        WHERE s.source_type = 'badge_unlock'
        """
    )
    assert any(str(row["source_id"]) == "post_meeting_closer" and int(row["total_xp"]) == 15 for row in ledger_rows)


def test_quick_response_badge_reports_progress_and_next_action(tmp_path: Path):
    db = make_db(tmp_path)
    seed_task_list(db)

    for index in range(3):
        task_id = f"task_{index}"
        created_dt = datetime.now() - timedelta(days=3 - index, hours=1)
        confirm_dt = created_dt + timedelta(hours=1)
        created_at = created_dt.isoformat(timespec="seconds")
        confirm_at = confirm_dt.isoformat(timespec="seconds")
        db.execute(
            """
            INSERT INTO tasks(id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at)
            VALUES(?, ?, '', 'todo', 'normal', 'list_1', '测试用户', '2026-03-20T18:00:00', 'manual', NULL, '[]', '[]', ?, ?)
            """,
            (task_id, f"待响应事项{index + 1}", created_at, confirm_at),
        )
        db.execute(
            """
            INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
            VALUES(?, '测试用户', 'task.create', 'task', ?, ?, ?)
            """,
            (f"log_create_{index}", task_id, to_json({"title": f"待响应事项{index + 1}"}), created_at),
        )
        db.execute(
            """
            INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
            VALUES(?, '测试用户', 'task.confirm', 'task', ?, ?, ?)
            """,
            (f"log_confirm_{index}", task_id, to_json({"title": f"待响应事项{index + 1}"}), confirm_at),
        )

    board = build_badge_board(db, user_id="op_1", user_name="测试用户", auto_sync=False)
    badge = next(item for category in board.categories for item in category.badges if item.id == "collab_responder")

    assert badge.state == "progress"
    assert badge.progressValue == 3
    assert badge.progressTarget == 10
    assert badge.progressPercent == 30
    assert "还差 7 次" in badge.nextActionText


def test_badge_board_only_uses_current_users_task_evidence(tmp_path: Path):
    db = make_db(tmp_path)
    seed_task_list(db)

    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, owner_id, owner_name, ddl,
            source_type, source_id, scope_mode, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(
            'task_alice', 'Alice 的任务', '这是一条不属于 Bob 的任务', 'todo', 'normal', 'list_1', 'op_alice', 'Alice', '',
            'manual', NULL, 'COLLAB_SHARED', '[]', '[]', '2026-03-16T09:00:00', '2026-03-16T09:00:00'
        )
        """
    )
    db.execute(
        """
        INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
        VALUES('log_alice_create', 'Alice', 'task.create', 'task', 'task_alice', ?, '2026-03-16T09:00:00')
        """,
        (to_json({"title": "Alice 的任务", "ownerName": "Alice"}),),
    )

    bob_board = build_badge_board(db, user_id="op_bob", user_name="Bob", auto_sync=True)
    bob_spark = next(item for category in bob_board.categories for item in category.badges if item.id == "spark_start")

    assert bob_spark.state == "locked"
    assert bob_spark.progressValue == 0
    assert all(item.title != "Alice 的任务" for item in bob_spark.evidence)
    assert db.fetchall("SELECT * FROM badge_unlock_records WHERE user_id = 'op_bob'") == []
    assert db.fetchall("SELECT * FROM xp_ledger WHERE user_id = 'op_bob'") == []

    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, owner_id, owner_name, ddl,
            source_type, source_id, scope_mode, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(
            'task_bob', 'Bob 的任务', '这是一条 Bob 自己的任务', 'todo', 'normal', 'list_1', 'op_bob', 'Bob', '',
            'manual', NULL, 'COLLAB_SHARED', '[]', '[]', '2026-03-16T10:00:00', '2026-03-16T10:00:00'
        )
        """
    )

    bob_board = build_badge_board(db, user_id="op_bob", user_name="Bob", auto_sync=True)
    bob_spark = next(item for category in bob_board.categories for item in category.badges if item.id == "spark_start")

    assert bob_spark.state in {"lit", "mastered"}
    assert bob_spark.progressValue == 1
    assert [item.title for item in bob_spark.evidence] == ["Bob 的任务"]
    assert db.fetchone("SELECT * FROM badge_unlock_records WHERE user_id = 'op_bob' AND badge_id = 'spark_start'") is not None


def test_badge_board_filters_weekly_reviews_and_activity_logs_by_actor(tmp_path: Path):
    db = make_db(tmp_path)
    seed_task_list(db)

    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, owner_id, owner_name, ddl,
            source_type, source_id, scope_mode, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(
            'task_alice', 'Alice 的周复盘任务', '这是一条 Alice 的任务', 'done', 'normal', 'list_1', 'op_alice', 'Alice', '',
            'manual', NULL, 'COLLAB_SHARED', '[]', '[]', '2026-03-16T09:00:00', '2026-03-16T09:30:00'
        )
        """
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(
            id, week_label, operator_id, user_id, summary, work_free_note, personal_growth_note, personal_private_note,
            created_at, updated_at
        ) VALUES(
            'review_alice', '2026-W11', 'op_alice', 'op_alice', 'Alice 的周复盘', '', '', '',
            '2026-03-16T10:00:00', '2026-03-16T10:00:00'
        )
        """
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(
            'entry_alice', 'review_alice', 'task_alice', '2026-W11', 'work', 'Alice 复盘了负责人、风险和下一步。',
            ?, ?, '2026-03-16T10:00:00', '2026-03-16T10:00:00', '2026-03-16T10:00:00'
        )
        """,
        (
            to_json({"successExperience": "负责人和下一步要写清楚", "nextAction": "继续推进", "blockerReason": "风险需要提前处理"}),
            to_json({"title": "Alice 的周复盘任务", "ownerId": "op_alice", "ownerName": "Alice"}),
        ),
    )
    db.execute(
        """
        INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
        VALUES('log_alice_confirm', 'Alice', 'task.confirm', 'task', 'task_alice', ?, '2026-03-16T11:00:00')
        """,
        (to_json({"title": "Alice 快速响应"}),),
    )

    bob_board = build_badge_board(db, user_id="op_bob", user_name="Bob", auto_sync=False)
    review_badge = next(item for category in bob_board.categories for item in category.badges if item.id == "feedback_coach")
    quick_badge = next(item for category in bob_board.categories for item in category.badges if item.id == "collab_responder")

    assert review_badge.progressValue == 0
    assert quick_badge.progressValue == 0
    assert all("Alice" not in item.title for item in review_badge.evidence + quick_badge.evidence)


def test_growth_badges_get_does_not_unlock_or_award_badge_xp(tmp_path: Path):
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    db = app.state.app_state.db
    operator = db.fetchone("SELECT * FROM operators ORDER BY created_at LIMIT 1")
    assert operator is not None
    operator_id = str(operator["id"])
    operator_name = str(operator["name"])
    list_row = db.fetchone("SELECT id FROM task_lists ORDER BY sort_order LIMIT 1")
    list_id = str(list_row["id"]) if list_row else "list-0"

    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, owner_id, owner_name, ddl,
            source_type, source_id, scope_mode, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(
            'task_current_user', '当前用户自己的任务', '用于验证 GET 不写入徽章积分', 'todo', 'normal', ?, ?, ?, '',
            'manual', NULL, 'COLLAB_SHARED', '[]', '[]', '2026-03-16T09:00:00', '2026-03-16T09:00:00'
        )
        """,
        (list_id, operator_id, operator_name),
    )

    before_unlocks = len(db.fetchall("SELECT id FROM badge_unlock_records"))
    before_xp = len(db.fetchall("SELECT id FROM xp_ledger"))
    response = client.get("/api/v1/growth/badges")

    assert response.status_code == 200
    assert len(db.fetchall("SELECT id FROM badge_unlock_records")) == before_unlocks
    assert len(db.fetchall("SELECT id FROM xp_ledger")) == before_xp
