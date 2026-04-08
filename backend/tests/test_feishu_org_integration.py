from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_local_mode_feishu_collaboration_requires_cloud_and_org(tmp_path: Path):
    client = make_client(tmp_path)

    membership = client.get("/api/v1/me/org-membership")
    assert membership.status_code == 200, membership.text
    assert membership.json()["hasOrganization"] is False

    integration = client.get("/api/v1/org-integrations/feishu")
    assert integration.status_code == 200, integration.text
    integration_payload = integration.json()
    assert integration_payload["enabled"] is False
    assert "连接云端" in integration_payload["authorizationBlockedReason"]

    authorization = client.get("/api/v1/me/feishu-authorization")
    assert authorization.status_code == 200, authorization.text
    authorization_payload = authorization.json()
    assert authorization_payload["linked"] is False
    assert authorization_payload["readyForAuthorization"] is False
    assert "连接云端" in authorization_payload["blockedReason"]
