from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def test_refresh_token_rotates_and_restores_session(tmp_path, monkeypatch):
    data_dir = tmp_path / "cloud-data"
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Qinghua123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Jianing123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Yishuo123!")

    app = create_app()
    client = TestClient(app)

    login = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert login.status_code == 200, login.text
    login_payload = login.json()
    first_access = login_payload["accessToken"]
    first_refresh = login_payload["refreshToken"]
    assert first_refresh

    refreshed = client.post("/api/v1/auth/refresh", json={"refreshToken": first_refresh})
    assert refreshed.status_code == 200, refreshed.text
    refreshed_payload = refreshed.json()
    second_access = refreshed_payload["accessToken"]
    second_refresh = refreshed_payload["refreshToken"]

    assert second_access
    assert second_refresh
    assert second_refresh != first_refresh

    stale_refresh = client.post("/api/v1/auth/refresh", json={"refreshToken": first_refresh})
    assert stale_refresh.status_code == 401, stale_refresh.text

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {second_access}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "admin@yiyu-system.com"
