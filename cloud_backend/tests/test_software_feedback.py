from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_data_feedback"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def setup_function():
    os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def teardown_function():
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)


def _admin_headers(client: TestClient) -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}


def test_create_list_and_status_flow():
    client = TestClient(create_app())
    headers = _admin_headers(client)

    # create
    res = client.post(
        "/api/v1/software-feedback",
        headers=headers,
        json={
            "category": "bug",
            "severity": "high",
            "title": "战略陪伴状态显示异常",
            "description": "刷新后状态闪回",
            "appVersion": "0.2.2",
            "platform": "darwin",
            "pageRoute": "strategic_accompaniment",
            "clientId": "client_abc",
        },
    )
    assert res.status_code == 200, res.text
    rec = res.json()
    assert rec["status"] == "open"
    assert rec["category"] == "bug"
    assert rec["reporterName"]  # 反报人名已落库
    assert rec["clientId"] == "client_abc"
    fid = rec["id"]

    # list 能看到
    res = client.get("/api/v1/software-feedback", headers=headers)
    assert res.status_code == 200, res.text
    assert any(r["id"] == fid for r in res.json())

    # 流转到 in_progress: resolved_at 仍空
    res = client.post(f"/api/v1/software-feedback/{fid}/status", headers=headers, json={"status": "in_progress", "targetVersion": "0.2.3"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "in_progress"
    assert res.json()["resolvedAt"] is None
    assert res.json()["targetVersion"] == "0.2.3"

    # 流转到 resolved: resolved_at 落时间戳
    res = client.post(f"/api/v1/software-feedback/{fid}/status", headers=headers, json={"status": "resolved", "resolutionNote": "已修"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "resolved"
    assert res.json()["resolvedAt"]


def test_severity_ordering_and_filters():
    client = TestClient(create_app())
    headers = _admin_headers(client)
    for sev, title in [("low", "小建议"), ("critical", "崩溃"), ("medium", "卡顿")]:
        cat = "suggestion" if sev == "low" else ("bug" if sev == "critical" else "lag")
        res = client.post("/api/v1/software-feedback", headers=headers, json={"category": cat, "severity": sev, "title": title})
        assert res.status_code == 200, res.text

    res = client.get("/api/v1/software-feedback", headers=headers)
    sev_order = [r["severity"] for r in res.json()]
    assert sev_order[0] == "critical"  # critical 排最前

    res = client.get("/api/v1/software-feedback?category=bug", headers=headers)
    assert all(r["category"] == "bug" for r in res.json())


def test_unknown_id_404():
    client = TestClient(create_app())
    headers = _admin_headers(client)
    res = client.post("/api/v1/software-feedback/nope/status", headers=headers, json={"status": "open"})
    assert res.status_code == 404
