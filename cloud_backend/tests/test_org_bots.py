"""云端机器人同事(org_bots)注册表 + directory 带出 + holder_bot_id 持久化 单测。

覆盖 Design A 的云端半:
- POST /api/v1/org/bots 创建 → 仅此一次返回 tokenPlain;hasToken=True;handle/actorId 自动派生
- GET /api/v1/org/bots 列出
- GET /api/v1/employees/directory 把 bot 以 isBot=True 一并带出(桌面+手机同一接口可见)
- PATCH 改 status=disabled → directory 不再带出(只带 active)
- token_hash 与桌面 bot_members._hash_bot_token 算法一致(同步过去后桌面能校验)
- org-model role.holderBotId 往返持久化(岗位归属上云,退役本地 sidecar)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_data_bots"
os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD"] = "Admin123!"
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def _reset_dir() -> None:
    if TEST_DATA_DIR.exists():
        for child in TEST_DATA_DIR.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    else:
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


def setup_function():
    os.environ["YIYU_CLOUD_DATA_DIR"] = str(TEST_DATA_DIR)
    _reset_dir()


def teardown_function():
    _reset_dir()


def _admin_headers(client: TestClient):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


def test_create_list_and_directory_includes_bot():
    app = create_app()
    client = TestClient(app)
    h = _admin_headers(client)

    # 创建
    resp = client.post("/api/v1/org/bots", headers=h, json={"displayName": "庆华", "description": "首席咨询助理"})
    assert resp.status_code == 200, resp.text
    bot = resp.json()
    assert bot["displayName"] == "庆华"
    assert bot["handle"]  # 自动派生
    assert bot["actorId"].startswith("bot_")
    assert bot["hasToken"] is True
    assert bot["tokenPlain"]  # 仅此一次明文
    assert len(bot["capabilities"]) == 6  # 默认 6 项能力

    # 列表
    resp = client.get("/api/v1/org/bots", headers=h)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    assert items[0]["actorId"] == bot["actorId"]
    assert items[0]["tokenPlain"] is None  # 列表不返明文

    # directory 带出 bot(isBot=True)
    resp = client.get("/api/v1/employees/directory", headers=h)
    assert resp.status_code == 200, resp.text
    directory = resp.json()
    bots_in_dir = [m for m in directory if m.get("isBot")]
    assert len(bots_in_dir) == 1
    assert bots_in_dir[0]["fullName"] == "庆华"
    assert bots_in_dir[0]["actorId"] == bot["actorId"]
    # 人类成员仍在(admin)且 isBot=False
    humans = [m for m in directory if not m.get("isBot")]
    assert any(m["fullName"] for m in humans)


def test_token_hash_matches_desktop_algorithm():
    """云端存的 token_hash 必须能被桌面同算法校验(hmac_sha256(salt, token))。"""
    app = create_app()
    client = TestClient(app)
    h = _admin_headers(client)
    resp = client.post("/api/v1/org/bots", headers=h, json={"displayName": "校验bot"})
    assert resp.status_code == 200, resp.text
    bot = resp.json()
    token_plain = bot["tokenPlain"]

    # 从 DB 取出 hash+salt,用桌面算法复算,必须一致
    db = app.state.app_state.db
    row = db.fetchone("SELECT token_hash, token_salt FROM org_bots WHERE id = ?", (bot["id"],))
    expected = hmac.new(row["token_salt"].encode(), token_plain.encode(), hashlib.sha256).hexdigest()
    assert hmac.compare_digest(expected, row["token_hash"])


def test_disable_bot_removed_from_directory():
    app = create_app()
    client = TestClient(app)
    h = _admin_headers(client)
    bot = client.post("/api/v1/org/bots", headers=h, json={"displayName": "临时bot"}).json()

    # 停用
    resp = client.patch(f"/api/v1/org/bots/{bot['id']}", headers=h, json={"status": "disabled"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "disabled"

    # directory 不再带出(只带 active)
    directory = client.get("/api/v1/employees/directory", headers=h).json()
    assert not [m for m in directory if m.get("isBot")]
    # /org/bots 不带 status 过滤仍能看到(管理用)
    allbots = client.get("/api/v1/org/bots", headers=h).json()
    assert len(allbots) == 1


def test_duplicate_handle_rejected():
    app = create_app()
    client = TestClient(app)
    h = _admin_headers(client)
    r1 = client.post("/api/v1/org/bots", headers=h, json={"displayName": "重名", "handle": "dup"})
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/v1/org/bots", headers=h, json={"displayName": "重名2", "handle": "dup"})
    assert r2.status_code == 409


def test_rotate_token_returns_new_plain():
    app = create_app()
    client = TestClient(app)
    h = _admin_headers(client)
    bot = client.post("/api/v1/org/bots", headers=h, json={"displayName": "轮换bot"}).json()
    old_prefix = bot["tokenPrefix"]
    resp = client.patch(f"/api/v1/org/bots/{bot['id']}", headers=h, json={"rotateToken": True})
    assert resp.status_code == 200, resp.text
    rotated = resp.json()
    assert rotated["tokenPlain"]
    assert rotated["tokenPrefix"] != old_prefix or rotated["tokenPlain"][:8] == rotated["tokenPrefix"]


def test_role_holder_bot_id_roundtrips_in_org_model():
    """org-model 里某岗位 holderBotId 应能存云端并取回(退役本地 sidecar)。"""
    app = create_app()
    client = TestClient(app)
    h = _admin_headers(client)
    bot = client.post("/api/v1/org/bots", headers=h, json={"displayName": "持岗bot"}).json()

    profile = client.get("/api/v1/settings/org-model/profile", headers=h).json()
    profile["roles"] = [
        {
            "id": "role_test_holder",
            "departmentId": None,
            "name": "测试岗位",
            "level": "employee",
            "holderBotId": bot["id"],
            "updatedAt": "2026-06-07T00:00:00+00:00",
        }
    ]
    save = client.post("/api/v1/settings/org-model/profile", headers=h, json=profile)
    assert save.status_code == 200, save.text

    after = client.get("/api/v1/settings/org-model/profile", headers=h).json()
    role = next((r for r in after["roles"] if r["id"] == "role_test_holder"), None)
    assert role is not None
    assert role["holderBotId"] == bot["id"]
