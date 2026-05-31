from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DATA_DIR = Path(__file__).resolve().parent / "test_cloud_data_rc_contract"
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


def _admin(client: TestClient) -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": "admin@yiyu-system.com", "password": "Admin123!"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}


def test_feedback_loop_submit_inbox_status_problempool():
    client = TestClient(create_app())
    h = _admin(client)

    # 客户端提交 (桌面 app 报错/提建议)
    res = client.post("/api/v1/feedback", headers=h, json={
        "kind": "bug", "severity": "impaired", "title": "战略陪伴状态闪回",
        "description": "刷新后状态回退", "orgCode": "acme", "version": "0.2.2",
        "page": "strategic_accompaniment", "os": "darwin",
    })
    assert res.status_code == 200, res.text
    fb = res.json()
    assert fb["status"] == "open"
    assert fb["submitterName"]
    fid = fb["id"]

    # admin 收件箱看到
    res = client.get("/api/v1/admin/feedback", headers=h)
    assert res.status_code == 200, res.text
    assert any(x["id"] == fid for x in res.json())

    # 建一个 release 用于"并入问题池"
    rel = client.post("/api/v1/admin/releases", headers=h, json={"version": "0.2.3", "platforms": ["mac"]}).json()

    # 状态流转 + 关联 release → 自动进问题池
    res = client.patch(f"/api/v1/admin/feedback/{fid}", headers=h, json={"status": "next_release", "linkedReleaseId": rel["id"]})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "next_release"
    assert res.json()["linkedReleaseId"] == rel["id"]


def test_release_publish_assignment_package_and_org_aware_yml():
    client = TestClient(create_app())
    h = _admin(client)

    # 草稿 → 发布
    rel = client.post("/api/v1/admin/releases", headers=h, json={
        "version": "0.3.0", "platforms": ["mac"], "mandatory": False,
        "userNotes": {"新增": ["报错入口"], "修复": ["状态闪回"]}, "internalNotes": "内部:改了 X",
    }).json()
    rid = rel["id"]
    assert rel["status"] == "draft"
    pub = client.patch(f"/api/v1/admin/releases/{rid}", headers=h, json={"status": "published"})
    assert pub.json()["status"] == "published"
    assert pub.json()["publishedAt"]
    assert pub.json()["userNotes"]["新增"] == ["报错入口"]

    # 安装包元数据
    pkg = client.post(f"/api/v1/admin/releases/{rid}/packages", headers=h, json={
        "platform": "mac", "fileName": "yiyu-workbench-0.3.0-arm64.zip",
        "sizeBytes": 12345, "sha512": "abc123", "downloadUrl": "https://tos/x.zip",
    })
    assert pkg.status_code == 200, pkg.text

    # 定向指派给 org 'acme'
    asg = client.post(f"/api/v1/admin/releases/{rid}/assignments", headers=h, json={
        "targetType": "org", "orgCode": "acme", "rolloutPct": 100,
    })
    assert asg.status_code == 200, asg.text
    assert asg.json()["targetType"] == "org"

    # org 感知更新解析 → yml 含版本 + sha512
    res = client.get("/api/v1/updates/acme/mac/latest-mac.yml")
    assert res.status_code == 200, res.text
    assert "version: 0.3.0" in res.text
    assert "abc123" in res.text

    # 暂停指派后, acme 仍有兜底? 这里无 all 指派, 兜底=最新已发布(仍 0.3.0)
    aid = asg.json()["id"]
    client.patch(f"/api/v1/admin/releases/{rid}/assignments/{aid}", headers=h, json={"status": "paused"})
    res = client.get("/api/v1/updates/acme/mac/latest-mac.yml")
    assert "version: 0.3.0" in res.text  # 兜底到最新已发布

    # 公开最新版 (官网下载页)
    res = client.get("/api/v1/releases/latest?platform=mac", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["version"] == "0.3.0"


def test_admin_endpoints_require_admin():
    client = TestClient(create_app())
    # 无 token → 401
    assert client.get("/api/v1/admin/releases").status_code == 401
    assert client.get("/api/v1/admin/feedback").status_code == 401
    assert client.get("/api/v1/admin/organizations").status_code == 401


def test_org_code_exposed_and_org_list_consistent():
    # 定向推送靠组织码:org-membership 必须暴露它, admin 组织列表必须列出同一个码
    client = TestClient(create_app())
    h = _admin(client)
    membership = client.get("/api/v1/me/org-membership", headers=h)
    assert membership.status_code == 200, membership.text
    slug = membership.json().get("organizationSlug")
    assert slug, f"组织码未暴露: {membership.json()}"

    res = client.get("/api/v1/admin/organizations", headers=h)
    assert res.status_code == 200, res.text
    orgs = res.json()
    assert orgs and orgs[0]["memberCount"] >= 1
    assert any(o["code"] == slug for o in orgs), "org-membership 的组织码与 admin 列表不一致"
