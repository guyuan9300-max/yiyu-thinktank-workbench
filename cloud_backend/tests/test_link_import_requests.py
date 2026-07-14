from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_link_import_data"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
os.environ["YIYU_CLOUD_QINGHUA_PASSWORD"] = "Simulate123!"
os.environ["YIYU_CLOUD_JIANING_PASSWORD"] = "Simulate123!"
os.environ["YIYU_CLOUD_YISHUO_PASSWORD"] = "Simulate123!"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import DEFAULT_ORG_ID, create_app, now_iso  # noqa: E402

BILI_URL = "https://www.bilibili.com/video/BV1xx411c7mD"


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
        shutil.rmtree(TEST_DATA_DIR)


def auth_headers(client: TestClient, email: str = "admin@yiyu-system.com", password: str = "Admin123!") -> dict[str, str]:
    timestamp = now_iso()
    client.app.state.app_state.db.executemany(
        """
        INSERT OR IGNORE INTO clients(id, organization_id, name, alias, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        [
            ("client_demo", DEFAULT_ORG_ID, "本组织", "本组织", timestamp, timestamp),
            ("client_org", DEFAULT_ORG_ID, "本组织", "本组织", timestamp, timestamp),
        ],
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_create_list_and_idempotent_resubmit():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)

    created = client.post(
        "/api/v1/link-import-requests",
        json={"url": BILI_URL, "sourceHint": "bilibili", "clientId": "client_demo", "clientName": "本组织"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    record = created.json()
    assert record["status"] == "pending"
    assert record["url"] == BILI_URL
    assert record["clientId"] == "client_demo"

    # 同链接重复提交(还在排队) → 幂等返回同一条
    duplicated = client.post(
        "/api/v1/link-import-requests",
        json={"url": BILI_URL},
        headers=headers,
    )
    assert duplicated.status_code == 200
    assert duplicated.json()["id"] == record["id"]

    listed = client.get("/api/v1/link-import-requests?status=pending", headers=headers)
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == record["id"]


@pytest.mark.parametrize(
    "source_url",
    [
        "javascript:alert(1)",
        "http://www.bilibili.com/video/BV1xx411c7mD",
        "https://evil.example/?next=https://www.bilibili.com/video/BV1xx411c7mD",
        "https://www.bilibili.com.evil.example/video/BV1xx411c7mD",
        "https://www.bilibili.com@127.0.0.1/private",
        "https://127.0.0.1/private",
        "https://mp.weixin.qq.com/not-an-article",
    ],
)
def test_rejects_unsafe_or_unsupported_url(source_url: str):
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/link-import-requests",
        json={"url": source_url},
        headers=headers,
    )
    assert response.status_code == 422


def test_status_writeback_lifecycle():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)

    record = client.post(
        "/api/v1/link-import-requests",
        json={"url": BILI_URL},
        headers=headers,
    ).json()

    # 桌面认领: processing + localRunId + 解析出的归属客户回写(原请求未带客户)
    claimed = client.post(
        f"/api/v1/link-import-requests/{record['id']}/status",
        json={"status": "processing", "localRunId": "run_123", "clientId": "client_org", "clientName": "本组织"},
        headers=headers,
    )
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "processing"
    assert claimed.json()["localRunId"] == "run_123"
    assert claimed.json()["clientId"] == "client_org"
    assert claimed.json()["clientName"] == "本组织"

    # 桌面完成回写: completed + 文档信息; localRunId 不传也要保留(COALESCE)
    completed = client.post(
        f"/api/v1/link-import-requests/{record['id']}/status",
        json={"status": "completed", "localDocumentId": "doc_456", "localDocumentPath": "资料库/x.md"},
        headers=headers,
    )
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "completed"
    assert body["localDocumentId"] == "doc_456"
    assert body["localRunId"] == "run_123"
    assert body["completedAt"]

    # 完成后同链接可再次提交(不再幂等拦截)
    again = client.post("/api/v1/link-import-requests", json={"url": BILI_URL}, headers=headers)
    assert again.status_code == 200
    assert again.json()["id"] != record["id"]


def test_failed_writeback_records_error():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    record = client.post("/api/v1/link-import-requests", json={"url": BILI_URL}, headers=headers).json()
    failed = client.post(
        f"/api/v1/link-import-requests/{record['id']}/status",
        json={"status": "failed", "errorMessage": "yt-dlp 下载失败"},
        headers=headers,
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert failed.json()["errorMessage"] == "yt-dlp 下载失败"
    assert failed.json()["completedAt"] is None


def test_unknown_request_404():
    app = create_app()
    client = TestClient(app)
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/link-import-requests/link_import_nonexistent/status",
        json={"status": "processing"},
        headers=headers,
    )
    assert response.status_code == 404
