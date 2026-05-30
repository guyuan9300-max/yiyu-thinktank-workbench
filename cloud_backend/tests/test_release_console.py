from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_data_release"
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


def test_install_checkin_upsert_and_list():
    client = TestClient(create_app())
    headers = _admin_headers(client)

    # 首次 checkin
    res = client.post("/api/v1/app/checkin", headers=headers, json={"installId": "dev-1", "platform": "darwin", "arch": "arm64", "appVersion": "0.2.2", "channel": "stable"})
    assert res.status_code == 200, res.text
    assert res.json()["appVersion"] == "0.2.2"
    first_seen = res.json()["firstSeenAt"]

    # 二次 checkin 同 installId: 升级版本, first_seen 不变(upsert)
    res = client.post("/api/v1/app/checkin", headers=headers, json={"installId": "dev-1", "platform": "darwin", "arch": "arm64", "appVersion": "0.2.3", "channel": "stable"})
    assert res.status_code == 200, res.text
    assert res.json()["appVersion"] == "0.2.3"
    assert res.json()["firstSeenAt"] == first_seen

    # admin 列表只 1 条(upsert 不新增)
    res = client.get("/api/v1/app/installs", headers=headers)
    assert res.status_code == 200, res.text
    rows = [r for r in res.json() if r["installId"] == "dev-1"]
    assert len(rows) == 1
    assert rows[0]["appVersion"] == "0.2.3"


def test_release_lifecycle_and_update_policy():
    client = TestClient(create_app())
    headers = _admin_headers(client)

    # 草稿创建
    res = client.post("/api/v1/app/releases", headers=headers, json={"version": "0.2.3", "channel": "stable", "platforms": ["darwin"], "changelogUser": "修复若干问题"})
    assert res.status_code == 200, res.text
    rel = res.json()
    assert rel["status"] == "draft"
    assert rel["publishedAt"] is None
    rid = rel["id"]

    # 未发布时 update-policy 无更新
    res = client.get("/api/v1/app/update-policy?platform=darwin&channel=stable", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["hasUpdate"] is False

    # 发布 → publishedAt 落戳
    res = client.post(f"/api/v1/app/releases/{rid}", headers=headers, json={"status": "published"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "published"
    assert res.json()["publishedAt"]

    # darwin 命中
    res = client.get("/api/v1/app/update-policy?platform=darwin&channel=stable", headers=headers)
    assert res.json()["hasUpdate"] is True
    assert res.json()["version"] == "0.2.3"

    # win32 不在 platforms → 不命中
    res = client.get("/api/v1/app/update-policy?platform=win32&channel=stable", headers=headers)
    assert res.json()["hasUpdate"] is False


def test_empty_platforms_matches_all():
    client = TestClient(create_app())
    headers = _admin_headers(client)
    res = client.post("/api/v1/app/releases", headers=headers, json={"version": "0.3.0", "channel": "stable", "platforms": []})
    rid = res.json()["id"]
    client.post(f"/api/v1/app/releases/{rid}", headers=headers, json={"status": "published"})
    res = client.get("/api/v1/app/update-policy?platform=win32&channel=stable", headers=headers)
    assert res.json()["hasUpdate"] is True  # platforms 空 = 全平台
