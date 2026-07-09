from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_task_restore_status_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"

from app.main import create_app  # noqa: E402


def setup_function():
    os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_restore_completed_task_clears_cloud_completion_state():
    app = create_app()
    client = TestClient(app)
    headers = _auth_headers(client)

    created = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "title": "恢复任务状态回归",
            "description": "",
            "priority": "normal",
            "listId": "list-0",
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    done = client.patch(f"/api/v1/tasks/{task_id}", headers=headers, json={"progressStatus": "done"})
    assert done.status_code == 200, done.text
    assert done.json()["progressStatus"] == "done"
    assert done.json()["completedAt"]

    restored = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=headers,
        json={"progressStatus": "doing", "completedAt": None},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["progressStatus"] == "doing"
    assert restored.json()["completedAt"] is None

    board = client.get("/api/v1/tasks", headers=headers)
    assert board.status_code == 200, board.text
    [task] = [item for item in board.json()["tasks"] if item["id"] == task_id]
    assert task["progressStatus"] == "doing"
    assert task["completedAt"] is None
