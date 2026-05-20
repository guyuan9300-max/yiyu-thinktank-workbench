"""W1-7 关键里程碑 · 真实生产 cloud e2e

注意:
- 这个测试调用火山云生产 cloud_backend(http://101.126.34.232)
- 需要 ~/Library/Application Support/YiyuThinkTankWorkbench2/app.db 里有有效 cloud_access_token
- 如果没 token / 火山云宕机 → 自动 skip(不算失败)
- 验证:启动 backend → 调 sync API → 调 profile API → 返回真实组织数据
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


PROD_DB = Path.home() / "Library/Application Support/YiyuThinkTankWorkbench2/app.db"


def _read_prod_cloud_creds() -> tuple[str | None, str | None]:
    """从生产本地 db 读 cloud_api_url + cloud_access_token"""
    if not PROD_DB.exists():
        return None, None
    conn = sqlite3.connect(PROD_DB)
    conn.row_factory = sqlite3.Row
    try:
        url_row = conn.execute("SELECT value FROM settings WHERE key='cloud_api_url'").fetchone()
        token_row = conn.execute("SELECT value FROM settings WHERE key='cloud_access_token'").fetchone()
    finally:
        conn.close()
    url = url_row["value"] if url_row else None
    token = token_row["value"] if token_row else None
    return url, token


@pytest.mark.skipif(
    not PROD_DB.exists(),
    reason="no production db at ~/Library/Application Support/YiyuThinkTankWorkbench2/app.db",
)
def test_real_cloud_e2e_sync_then_profile(tmp_path: Path):
    """真实 e2e:启动 backend → seed cloud creds → 触发 sync → 调 profile"""
    url, token = _read_prod_cloud_creds()
    if not url or not token:
        pytest.skip("missing cloud_api_url or cloud_access_token in production db")

    # 启动空 backend
    from app.main import create_app
    data_dir = tmp_path / "data"
    app = create_app(data_dir)
    client = TestClient(app)
    client.__enter__()

    # seed cloud creds:写 settings 表 + 直接覆盖 state(state.cloud_api_url 是 create_app 时
    # 一次性从 settings 拉的快照,后改 settings 不生效)
    state = client.app.state.app_state  # type: ignore[attr-defined]
    state.db.conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES('cloud_api_url', ?)", (url,)
    )
    state.db.conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES('cloud_access_token', ?)", (token,)
    )
    state.db.conn.commit()
    state.cloud_api_url = url

    # 触发 sync(实际调火山云)
    sync_resp = client.post("/api/v1/local/organization/sync")
    if sync_resp.status_code in (502, 503):
        pytest.skip(f"cloud unavailable: {sync_resp.text}")
    assert sync_resp.status_code == 200, f"sync failed: {sync_resp.text}"
    sync_body = sync_resp.json()
    assert sync_body["status"] == "ok", f"sync status: {sync_body}"

    # 调 profile,验证有真实数据
    profile_resp = client.get("/api/v1/local/organization/profile")
    assert profile_resp.status_code == 200
    profile = profile_resp.json()

    assert profile["organization"] is not None
    assert profile["organization"]["id"] == "org_yiyu_default"
    assert profile["organization"]["name"] == "益语智库"

    # 部门:战略发展部 / 合作发展部 / 技术创新部 都应在
    dept_names = {d["name"] for d in profile["departments"] if d["active"]}
    assert "战略发展部" in dept_names, f"got: {dept_names}"
    assert "合作发展部" in dept_names, f"got: {dept_names}"
    assert "技术创新部" in dept_names, f"got: {dept_names}"

    # 员工:顾源源 / 乐乐 / 林佳维 都应在
    user_names = {u["fullName"] for u in profile["users"]}
    assert "顾源源" in user_names, f"got: {user_names}"
    assert "乐乐" in user_names, f"got: {user_names}"
    assert "林佳维" in user_names, f"got: {user_names}"

    # 顾源源应该是 CEO + isManager + dept=战略发展部
    guyuan = next(u for u in profile["users"] if u["fullName"] == "顾源源")
    assert guyuan["isManager"] is True
    assert "CEO" in guyuan["projectRoleLabels"]
    # departmentId 是动态的(department_gq160gdz),但应该非空
    assert guyuan["departmentId"]
    # 通过 dept id 查 dept name,验证是"战略发展部"
    dept_by_id = {d["id"]: d["name"] for d in profile["departments"]}
    assert dept_by_id[guyuan["departmentId"]] == "战略发展部"
