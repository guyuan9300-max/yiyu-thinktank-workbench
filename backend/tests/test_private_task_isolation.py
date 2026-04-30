from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services.data_center_ingest import ingest_task_by_id, purge_private_task_ingest_events


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "私人任务隔离客户") -> str:
    created = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于私人任务隔离测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["id"]


def test_personal_only_task_is_visible_only_to_task_board_and_excluded_from_derivatives(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    client_id = create_test_client_record(client)
    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "不应绑定的共享事件线",
            "kind": "project_line",
            "primaryClientId": client_id,
        },
    )
    assert event_line.status_code == 200, event_line.text

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "和杨沐媛去韶关",
            "desc": "私人安排，不应进入任何组织计算。",
            "priority": "normal",
            "listId": "list-0",
            "dueDate": "2026-04-30",
            "ddl": "2026-04-30",
            "scopeMode": "PERSONAL_ONLY",
            "clientId": client_id,
            "eventLineId": event_line.json()["id"],
            "projectModuleId": "module_should_clear",
            "projectFlowId": "flow_should_clear",
            "currentBlocker": "私人信息不应进入成长分析",
            "nextAction": "只在任务模块显示",
            "evidenceCount": 3,
        },
    )
    assert created.status_code == 200, created.text
    task = created.json()
    task_id = task["id"]
    assert task["scopeMode"] == "PERSONAL_ONLY"
    assert task["clientId"] in ("", None)
    assert task["eventLineId"] in ("", None)
    assert task["projectModuleId"] in ("", None)
    assert task["projectFlowId"] in ("", None)

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    assert any(item["id"] == task_id and item["title"] == "和杨沐媛去韶关" for item in board.json()["tasks"])

    assert db.scalar("SELECT COUNT(1) FROM growth_signal_events WHERE task_id = ?", (task_id,)) == 0
    assert db.scalar("SELECT COUNT(1) FROM data_center_ingest_events WHERE task_id = ? OR source_id = ?", (task_id, task_id)) == 0

    growth = client.get("/api/v1/growth/workbench", params={"weekLabel": "2026-W18"})
    assert growth.status_code == 200, growth.text
    assert "和杨沐媛去韶关" not in json.dumps(growth.json(), ensure_ascii=False)

    reviews = client.get("/api/v1/reviews", params={"weekLabel": "2026-W18", "skipAi": "true"})
    assert reviews.status_code == 200, reviews.text
    review_payload_text = json.dumps(reviews.json(), ensure_ascii=False)
    assert "和杨沐媛去韶关" not in review_payload_text
    assert reviews.json()["personalItems"] == []

    forced_review = client.post(
        "/api/v1/reviews/weekly/draft",
        json={
            "weekLabel": "2026-W18",
            "workFreeNote": "",
            "personalGrowthNote": "",
            "personalPrivateNote": "",
            "taskEntries": [
                {
                    "taskId": task_id,
                    "contentDomain": "work",
                    "note": "强行把私人任务塞进周复盘，也必须被忽略。",
                    "structuredNote": {
                        "progress": "不应保存",
                        "successReason": "不应进入成长",
                        "blockerReason": "",
                        "supportNeeded": "",
                        "nextAction": "",
                    },
                }
            ],
        },
    )
    assert forced_review.status_code == 200, forced_review.text
    assert forced_review.json()["workItems"] == []
    assert forced_review.json()["personalItems"] == []
    assert db.scalar("SELECT COUNT(1) FROM weekly_review_task_entries WHERE task_id = ?", (task_id,)) == 0
    assert db.scalar("SELECT COUNT(1) FROM growth_signal_events WHERE task_id = ?", (task_id,)) == 0

    assert ingest_task_by_id(db, client.app.state.app_state.data_dir, task_id) is None
    assert db.scalar("SELECT COUNT(1) FROM data_center_ingest_events WHERE task_id = ? OR source_id = ?", (task_id, task_id)) == 0

    backfill = client.post("/api/v1/memory/backfill")
    assert backfill.status_code == 200, backfill.text
    assert db.scalar("SELECT COUNT(1) FROM memory_facts WHERE scope_type = 'task' AND scope_id = ?", (task_id,)) == 0
    assert db.scalar("SELECT COUNT(1) FROM memory_facts WHERE source_entity_type = 'task' AND source_entity_id = ?", (task_id,)) == 0


def test_private_task_data_center_cleanup_removes_legacy_private_stored_events(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "私人历史任务",
            "desc": "历史兼容数据",
            "priority": "normal",
            "listId": "list-0",
            "scopeMode": "PERSONAL_ONLY",
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]
    db.execute(
        """
        INSERT INTO data_center_ingest_events(
            id, source_type, source_id, title, status, task_id, content_hash, document_id,
            visibility_scope, content_domain, lifecycle_status, created_at, updated_at
        ) VALUES(?, 'task', ?, '私人历史任务', 'private_stored', ?, 'hash', NULL, 'self', 'personal', 'active', ?, ?)
        """,
        ("ingest_legacy_private", task_id, task_id, "2026-04-27T10:00:00", "2026-04-27T10:00:00"),
    )

    deleted = purge_private_task_ingest_events(db)

    assert deleted >= 1
    assert db.scalar("SELECT COUNT(1) FROM tasks WHERE id = ?", (task_id,)) == 1
    assert db.scalar("SELECT COUNT(1) FROM data_center_ingest_events WHERE task_id = ? OR source_id = ?", (task_id, task_id)) == 0
