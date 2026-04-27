from pathlib import Path

from app.db import Database, to_json
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
    badge = next(item for category in board.categories for item in category.badges if item.id == "closed_loop_meeting")

    assert badge.state in {"lit", "mastered"}
    assert badge.unlockedAt is not None
    assert badge.progressValue >= badge.progressTarget
    assert badge.evidence

    unlock_rows = db.fetchall("SELECT badge_id, xp FROM badge_unlock_records ORDER BY unlocked_at DESC")
    assert any(str(row["badge_id"]) == "closed_loop_meeting" and int(row["xp"]) == 20 for row in unlock_rows)

    ledger_rows = db.fetchall(
        """
        SELECT l.total_xp, s.source_type, s.source_id
        FROM xp_ledger l
        INNER JOIN growth_evidence_records e ON e.id = l.evidence_id
        INNER JOIN growth_signal_events s ON s.id = e.signal_id
        WHERE s.source_type = 'badge_unlock'
        """
    )
    assert any(str(row["source_id"]) == "closed_loop_meeting" and int(row["total_xp"]) == 20 for row in ledger_rows)


def test_quick_response_badge_reports_progress_and_next_action(tmp_path: Path):
    db = make_db(tmp_path)
    seed_task_list(db)

    for index in range(3):
        task_id = f"task_{index}"
        created_at = f"2026-03-1{index + 1}T09:00:00"
        confirm_at = f"2026-03-1{index + 1}T10:00:00"
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
    badge = next(item for category in board.categories for item in category.badges if item.id == "quick_response")

    assert badge.state == "progress"
    assert badge.progressValue == 3
    assert badge.progressTarget == 15
    assert badge.progressPercent == 20
    assert "还差 12 次" in badge.nextActionText
