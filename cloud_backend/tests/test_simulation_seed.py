from __future__ import annotations

import os
import shutil
import sys
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_simulation_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
os.environ["YIYU_CLOUD_QINGHUA_PASSWORD"] = "Simulate123!"
os.environ["YIYU_CLOUD_JIANING_PASSWORD"] = "Simulate123!"
os.environ["YIYU_CLOUD_YISHUO_PASSWORD"] = "Simulate123!"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, create_app  # noqa: E402
from app.simulation_seed import seed_simulated_review_org  # noqa: E402


def setup_function():
    os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_seed_simulated_review_org_populates_week_and_visibility():
    app = create_app()
    client = TestClient(app)
    db = app.state.app_state.db

    seeded = seed_simulated_review_org(db, organization_id=DEFAULT_ORG_ID, base_date=date(2026, 3, 15))
    reseeded = seed_simulated_review_org(db, organization_id=DEFAULT_ORG_ID, base_date=date(2026, 3, 15))

    assert seeded["weekLabel"] == "2026-W11"
    assert reseeded["weekLabel"] == "2026-W11"
    assert seeded["employeeCount"] == 20
    assert seeded["departmentCount"] == 4
    assert db.scalar("SELECT COUNT(1) AS count FROM tasks WHERE source_type = 'simulation_seed'") == 420
    assert db.scalar("SELECT COUNT(1) AS count FROM weekly_review_entries WHERE week_label = ?", ("2026-W11",)) == 20
    assert db.scalar("SELECT COUNT(1) AS count FROM weekly_review_task_entries WHERE week_label = ?", ("2026-W11",)) == 420
    assert db.scalar(
        "SELECT COUNT(1) AS count FROM weekly_review_task_entries WHERE week_label = ? AND TRIM(COALESCE(structured_note_json, '')) != ''",
        ("2026-W11",),
    ) == 420

    per_day_counts = db.fetchall(
        """
        SELECT owner_id, due_date, COUNT(1) AS item_count
        FROM tasks
        WHERE source_type = 'simulation_seed'
        GROUP BY owner_id, due_date
        ORDER BY owner_id, due_date
        """
    )
    assert len(per_day_counts) == 140
    assert all(int(row["item_count"]) == 3 for row in per_day_counts)

    qinghua_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "member-a@example.org", "Simulate123!"),
    )
    assert qinghua_dashboard.status_code == 200, qinghua_dashboard.text
    qinghua_payload = qinghua_dashboard.json()
    assert qinghua_payload["currentReview"] is not None
    assert qinghua_payload["workItems"][0]["structuredNote"]["completionStatus"] in {"done_on_time", "done_late", "in_progress", "not_done"}
    assert qinghua_payload["teamReport"] is not None
    assert "84 条任务复盘" in qinghua_payload["teamReport"]["summary"]

    jiale_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "member-d@example.org", "Simulate123!"),
    )
    assert jiale_dashboard.status_code == 200, jiale_dashboard.text
    assert "84 条任务复盘" in jiale_dashboard.json()["teamReport"]["summary"]

    dazhou_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "member-e@example.org", "Simulate123!"),
    )
    assert dazhou_dashboard.status_code == 200, dazhou_dashboard.text
    assert "84 条任务复盘" in dazhou_dashboard.json()["teamReport"]["summary"]

    jianing_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "member-b@example.org", "Simulate123!"),
    )
    assert jianing_dashboard.status_code == 200, jianing_dashboard.text
    assert "84 条任务复盘" in jianing_dashboard.json()["teamReport"]["summary"]

    admin_dashboard = client.get(
        "/api/v1/reviews/dashboard",
        headers=auth_headers(client, "admin@example.org", "Admin123!"),
    )
    assert admin_dashboard.status_code == 200, admin_dashboard.text
    admin_payload = admin_dashboard.json()
    assert admin_payload["orgReport"] is not None
    assert "420 条工作任务复盘" in admin_payload["orgReport"]["summary"]
