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


def test_local_mode_is_available_without_cloud_login(tmp_path: Path):
    client = make_client(tmp_path)

    auth_me = client.get("/api/v1/auth/me")
    assert auth_me.status_code == 200, auth_me.text
    payload = auth_me.json()
    assert payload["authenticated"] is False
    assert payload["sessionMode"] == "local"
    assert payload["user"] is None
    assert payload["requiresLocalIdentitySetup"] is True
    assert payload["localIdentityStatus"] == "needs_setup"

    overview = client.get("/api/v1/account/overview")
    assert overview.status_code == 200, overview.text
    overview_payload = overview.json()
    assert overview_payload["sessionMode"] == "local"
    assert overview_payload["cloudConnected"] is False
    assert overview_payload["cloudConfig"]["mode"] == "disabled"
    assert overview_payload["user"] is None
