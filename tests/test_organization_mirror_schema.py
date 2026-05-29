"""W1-1 验证 · organization 模块 mirror schema 完整性

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_organization_mirror_schema.py -v

设计:
- 用 tmp_path 跑空 db,跟生产数据无关
- 验证 4 张 mirror 表都建出来 + 索引 + readonly 触发器
- 验证 sync 写入(刷新 synced_from_cloud_at)合法
- 验证业务写入(不刷新 synced_from_cloud_at)被 trigger 拦截
- 验证可以 INSERT(只有 UPDATE 被守卫,sync UPSERT 模式 OK)
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Database  # noqa: E402
from app.modules.organization import (  # noqa: E402
    MIRROR_TABLE_NAMES,
    ORGANIZATION_SCHEMA_VERSION,
    SCHEMA_SQL,
)


@pytest.fixture
def fresh_db(tmp_path: Path) -> Database:
    """每个测试拿一个全新的空 db"""
    return Database(tmp_path / "app.db")


@pytest.mark.unit
def test_schema_version_constant_exists():
    """版本号是个 int >= 1"""
    assert isinstance(ORGANIZATION_SCHEMA_VERSION, int)
    assert ORGANIZATION_SCHEMA_VERSION >= 1


@pytest.mark.unit
def test_mirror_table_names_match_schema():
    """常量列表跟 SCHEMA_SQL 里实际 CREATE 的表对得上"""
    sql_lower = SCHEMA_SQL.lower()
    for name in MIRROR_TABLE_NAMES:
        assert f"create table if not exists {name}" in sql_lower, f"missing CREATE for {name}"


@pytest.mark.integration
def test_all_4_mirror_tables_created(fresh_db: Database):
    """空 db init 后 4 张表都存在"""
    rows = fresh_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mirror_%' ORDER BY name"
    ).fetchall()
    actual = {r["name"] for r in rows}
    expected = set(MIRROR_TABLE_NAMES)
    assert expected.issubset(actual), f"missing: {expected - actual}"


@pytest.mark.integration
def test_indexes_created(fresh_db: Database):
    """关键索引都建好"""
    rows = fresh_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_mirror_%' ORDER BY name"
    ).fetchall()
    indexes = {r["name"] for r in rows}
    expected = {
        "idx_mirror_departments_org",
        "idx_mirror_users_org",
        "idx_mirror_users_dept",
        "idx_mirror_cru_user",
        "idx_mirror_cru_client",
    }
    missing = expected - indexes
    assert not missing, f"missing indexes: {missing}"


@pytest.mark.integration
def test_readonly_triggers_created(fresh_db: Database):
    """4 张表都有 readonly 触发器"""
    rows = fresh_db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_mirror_%' ORDER BY name"
    ).fetchall()
    triggers = {r["name"] for r in rows}
    expected = {
        "trg_mirror_organizations_readonly",
        "trg_mirror_departments_readonly",
        "trg_mirror_users_readonly",
        "trg_mirror_cru_readonly",
    }
    missing = expected - triggers
    assert not missing, f"missing triggers: {missing}"


@pytest.mark.integration
def test_insert_works(fresh_db: Database):
    """sync 程序 INSERT 必须能正常工作(只有 UPDATE 受守卫)"""
    fresh_db.conn.execute(
        """
        INSERT INTO mirror_organizations(id, name, slug, cloud_updated_at, synced_from_cloud_at)
        VALUES('org_test', '测试组织', 'test', '2026-05-20T00:00:00', '2026-05-20T10:00:00')
        """
    )
    fresh_db.conn.commit()
    row = fresh_db.conn.execute(
        "SELECT name FROM mirror_organizations WHERE id='org_test'"
    ).fetchone()
    assert row["name"] == "测试组织"


@pytest.mark.integration
def test_sync_update_allowed_when_timestamp_refreshes(fresh_db: Database):
    """sync 程序 UPDATE 时 synced_from_cloud_at 刷新 → 允许"""
    fresh_db.conn.execute(
        "INSERT INTO mirror_organizations(id, name, synced_from_cloud_at) VALUES(?, ?, ?)",
        ("org_test", "v1", "2026-05-20T10:00:00"),
    )
    fresh_db.conn.commit()
    # sync 程序模式:每次写 row 都刷新 synced_from_cloud_at
    fresh_db.conn.execute(
        "UPDATE mirror_organizations SET name = ?, synced_from_cloud_at = ? WHERE id = ?",
        ("v2", "2026-05-20T11:00:00", "org_test"),
    )
    fresh_db.conn.commit()
    row = fresh_db.conn.execute(
        "SELECT name FROM mirror_organizations WHERE id='org_test'"
    ).fetchone()
    assert row["name"] == "v2"


@pytest.mark.integration
def test_business_update_blocked_when_timestamp_unchanged(fresh_db: Database):
    """业务代码手抖写入(没刷 synced_from_cloud_at)→ 被 trigger 拦截"""
    fresh_db.conn.execute(
        "INSERT INTO mirror_organizations(id, name, synced_from_cloud_at) VALUES(?, ?, ?)",
        ("org_test", "v1", "2026-05-20T10:00:00"),
    )
    fresh_db.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="cloud-mirrored"):
        fresh_db.conn.execute(
            "UPDATE mirror_organizations SET name = ? WHERE id = ?",
            ("hacked", "org_test"),
        )


@pytest.mark.integration
def test_all_4_tables_block_business_writes(fresh_db: Database):
    """4 张表全都拦截 unsync 写入"""
    samples = [
        ("mirror_organizations", "INSERT INTO mirror_organizations(id, name, synced_from_cloud_at) VALUES('o1','n','t1')"),
        ("mirror_departments",   "INSERT INTO mirror_departments(id, organization_id, name, synced_from_cloud_at) VALUES('d1','o1','n','t1')"),
        ("mirror_users",         "INSERT INTO mirror_users(id, organization_id, full_name, synced_from_cloud_at) VALUES('u1','o1','n','t1')"),
        ("mirror_client_related_users", "INSERT INTO mirror_client_related_users(client_id, user_id, synced_from_cloud_at) VALUES('c1','u1','t1')"),
    ]
    for table, insert_sql in samples:
        fresh_db.conn.execute(insert_sql)
        fresh_db.conn.commit()
        # 现在不刷 synced_from_cloud_at 改一个无关字段
        if table == "mirror_organizations":
            update_sql = "UPDATE mirror_organizations SET name='hacked' WHERE id='o1'"
        elif table == "mirror_departments":
            update_sql = "UPDATE mirror_departments SET name='hacked' WHERE id='d1'"
        elif table == "mirror_users":
            update_sql = "UPDATE mirror_users SET full_name='hacked' WHERE id='u1'"
        else:
            update_sql = "UPDATE mirror_client_related_users SET order_index=99 WHERE client_id='c1' AND user_id='u1'"
        with pytest.raises(sqlite3.IntegrityError, match="cloud-mirrored"):
            fresh_db.conn.execute(update_sql)


@pytest.mark.integration
def test_pragma_user_version_advanced(fresh_db: Database):
    """启动后 user_version 是新的 BACKEND_SCHEMA_VERSION"""
    from app.db import BACKEND_SCHEMA_VERSION
    version = fresh_db.get_schema_version()
    assert version == BACKEND_SCHEMA_VERSION


@pytest.mark.integration
def test_mirror_users_does_not_contain_sensitive_fields(fresh_db: Database):
    """敏感字段(password_hash 等)不应出现在 mirror_users"""
    columns = {r["name"] for r in fresh_db.conn.execute("PRAGMA table_info(mirror_users)").fetchall()}
    forbidden = {"password_hash", "phone_verified_at", "approved_by"}
    leaked = columns & forbidden
    assert not leaked, f"sensitive fields leaked into mirror_users: {leaked}"
