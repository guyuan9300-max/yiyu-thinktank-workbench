from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import app.main as app_main

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    os.environ["YIYU_FEEDBACK_CENTRAL_BASE_URL"] = ""
    app = create_app(tmp_path / "data")
    return TestClient(app)


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"
        self.text = ""

    def json(self):
        return self._payload


def test_local_feedback_queues_without_cloud_and_redacts_logs(tmp_path: Path):
    client = make_client(tmp_path)
    client.post(
        "/api/v1/system/client-error",
        json={
            "level": "error",
            "message": "login failed for 13800138000 api_key=abcdef1234567890 Bearer eyJabc.def.ghi sk-12345678901234567890 volc_12345678901234567890",
            "route": "#/settings",
        },
    )

    res = client.post(
        "/api/v1/software-feedback",
        data={
            "category": "bug",
            "severity": "high",
            "title": "检查更新没有结果",
            "description": "点了以后一直转圈",
            "appVersion": "0.24.0",
            "platform": "darwin/arm64",
            "pageRoute": "settings/about/feedback",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["queued"] is True
    record = body["record"]
    assert record["queued"] is True
    assert record["title"] == "检查更新没有结果"

    listed = client.get("/api/v1/software-feedback")
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) == 1
    log_excerpt = items[0]["logExcerpt"]
    assert "13800138000" not in log_excerpt
    assert "abcdef1234567890" not in log_excerpt
    assert "sk-12345678901234567890" not in log_excerpt
    assert "volc_12345678901234567890" not in log_excerpt
    assert "<PHONE>" in log_excerpt
    assert "<TOKEN>" in log_excerpt


def test_local_feedback_queues_screenshot_and_rejects_bad_file(tmp_path: Path):
    client = make_client(tmp_path)

    ok = client.post(
        "/api/v1/software-feedback",
        data={
            "category": "suggestion",
            "severity": "low",
            "title": "希望增加批量导出",
        },
        files={"screenshot": ("feedback.png", BytesIO(b"png bytes"), "image/png")},
    )
    assert ok.status_code == 200, ok.text
    record = ok.json()["record"]
    assert record["queued"] is True
    assert record["screenshotPath"]

    bad = client.post(
        "/api/v1/software-feedback",
        data={
            "category": "bug",
            "severity": "medium",
            "title": "错误截图类型",
        },
        files={"screenshot": ("feedback.txt", BytesIO(b"text"), "text/plain")},
    )
    assert bad.status_code == 415


def test_local_feedback_reaches_central_without_org_cloud(tmp_path: Path, monkeypatch):
    os.environ["YIYU_FEEDBACK_CENTRAL_BASE_URL"] = "https://central.example.test"

    def fake_post(url, **kwargs):
        assert url == "https://central.example.test/api/v1/feedback"
        payload = kwargs["json"]
        headers = kwargs["headers"]
        assert payload["feedbackClientId"].startswith("fbc_")
        assert "feedbackClientToken" not in payload
        assert headers["X-Yiyu-Feedback-Client-Id"] == payload["feedbackClientId"]
        assert headers["X-Yiyu-Feedback-Client-Token"].startswith("fbt_")
        assert payload["localFeedbackId"].startswith("lfb_")
        assert payload["orgCode"] == "org_demo"
        assert payload["organizationId"] == "org_demo"
        assert payload["organizationName"] == "演示组织"
        return FakeResponse({"id": "central_fb_1", **payload})

    monkeypatch.setattr(app_main.httpx, "post", fake_post)
    client = TestClient(create_app(tmp_path / "data-central"))
    client.app.state.app_state.db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "user_demo",
                "organizationId": "org_demo",
                "organizationName": "演示组织",
                "email": "demo@example.com",
                "fullName": "演示成员",
                "primaryRole": "employee",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )

    res = client.post(
        "/api/v1/software-feedback",
        data={
            "category": "bug",
            "severity": "medium",
            "title": "未加入组织也能提交",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["queued"] is False
    assert body["record"]["id"] == "central_fb_1"
