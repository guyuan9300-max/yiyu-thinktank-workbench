"""W1-6 验证 · 6 个核心 SQL Views

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_organization_views.py -v

设计:
- 空 db 启动后 6 个 view 都存在 + 能查
- 用 seed 数据验证 view 的过滤逻辑(frozen 客户被过滤;status 过滤正确)
- v_user_visible_clients 跟 mirror_client_related_users JOIN 工作正常
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Database  # noqa: E402
from app.modules.organization import VIEW_NAMES  # noqa: E402


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


@pytest.fixture
def db_with_data(db: Database) -> Database:
    """seed:2 active clients(其中 1 个有 frozen 兄弟)+ 任务 + 事件线 + knowledge"""
    # 测试期 disable FK,避免要 seed 上游表(knowledge_surrogates 等)
    db.conn.execute("PRAGMA foreign_keys=OFF")
    now = "2026-05-20T10:00:00"

    # 3 clients:client_a (active), client_b (active, related to user_guyuan), client_c (frozen)
    db.conn.executemany(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at, related_user_ids_json, frozen_at)
           VALUES(?, ?, '', '项目', '项目', '', '待导入资料', '#5B7BFE', ?, ?, ?, ?)""",
        [
            ("client_a", "客户A", now, now, "[]", None),
            ("client_b", "客户B", now, now, json.dumps(["user_guyuan"]), None),
            ("client_c", "客户C(已冻结)", now, now, "[]", "2026-05-19T00:00:00"),
        ],
    )

    # 2 event_lines:1 active 挂 client_a,1 paused 挂 client_b
    db.conn.executemany(
        """INSERT INTO event_lines(id, name, kind, status, primary_client_id, created_at, updated_at)
           VALUES(?, ?, 'custom', ?, ?, ?, ?)""",
        [
            ("el_1", "active 事件线", "active", "client_a", now, now),
            ("el_2", "paused 事件线", "paused", "client_b", now, now),
            ("el_3", "active 但孤儿", "active", None, now, now),
        ],
    )

    # tasks 需要 task_list 存在(FK)。task_lists 已由 _init_schema 建好,显式插一行
    db.conn.execute(
        """INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope)
           VALUES('list_default', '', 'default', '#5B7BFE', 0, 1, 'org')"""
    )
    db.conn.executemany(
        """INSERT INTO tasks(id, title, description, status, priority, list_id,
                             owner_name, ddl, source_type, tags_json,
                             created_at, updated_at, client_id)
           VALUES(?, ?, '', ?, 'normal', 'list_default', '', '', 'manual', '[]', ?, ?, ?)""",
        [
            ("t_1", "待办 1", "todo",  now, now, "client_a"),
            ("t_2", "进行 1", "doing", now, now, "client_a"),
            ("t_3", "完成 1", "done",  now, now, "client_a"),
            ("t_4", "待办 2", "todo",  now, now, "client_b"),
        ],
    )

    # knowledge
    db.conn.executemany(
        """INSERT INTO knowledge_master_index(id, client_id, surrogate_id, title, folder_category,
                                              document_role, retrieval_summary, searchable_text,
                                              surrogate_md_path, updated_at)
           VALUES(?, ?, ?, ?, '', '', '摘要', ?, '', ?)""",
        [
            ("k_1", "client_a", "sg_1", "可搜索 1", "有内容", now),
            ("k_2", "client_a", "sg_2", "空可搜索", "", now),  # searchable_text 为空
            ("k_3", "client_c", "sg_3", "在冻结 client", "内容", now),
        ],
    )

    # mirror 表:1 organization + 1 binding(user_guyuan 关联 client_b)
    db.conn.executemany(
        """INSERT INTO mirror_organizations(id, name, slug, synced_from_cloud_at) VALUES(?, ?, ?, ?)""",
        [("org_yiyu_default", "益语智库", "yiyu", now)],
    )
    db.conn.execute(
        """INSERT INTO mirror_client_related_users(client_id, user_id, order_index, synced_from_cloud_at)
           VALUES('client_b', 'user_guyuan', 0, ?)""",
        (now,),
    )

    db.conn.commit()
    return db


# ─────────────────────────────────────────────────────────────────────────────
# 基础:6 个 view 都存在
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_all_6_views_exist(db: Database):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()
    actual = {r["name"] for r in rows}
    expected = set(VIEW_NAMES)
    missing = expected - actual
    assert not missing, f"missing views: {missing}"


@pytest.mark.integration
def test_views_queryable_on_empty_db(db: Database):
    """空 db 跑 view 不报错"""
    for v in VIEW_NAMES:
        rows = db.conn.execute(f"SELECT * FROM {v} LIMIT 1").fetchall()
        assert isinstance(rows, list)


# ─────────────────────────────────────────────────────────────────────────────
# v_active_clients
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_v_active_clients_excludes_frozen(db_with_data: Database):
    rows = db_with_data.fetchall("SELECT id, name FROM v_active_clients ORDER BY id")
    ids = [r["id"] for r in rows]
    assert ids == ["client_a", "client_b"]
    assert "client_c" not in ids  # frozen


# ─────────────────────────────────────────────────────────────────────────────
# v_user_visible_clients
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_v_user_visible_clients_join(db_with_data: Database):
    """user_guyuan 应该能看到 client_b(被关联)+ client_a/无人关联的可由 LEFT JOIN 显示"""
    rows = db_with_data.fetchall(
        "SELECT id, viewer_user_id FROM v_user_visible_clients ORDER BY id, viewer_user_id"
    )
    # client_a (无关联) → viewer_user_id 是 NULL
    # client_b (关联了 user_guyuan) → viewer_user_id = user_guyuan
    pairs = [(r["id"], r["viewer_user_id"]) for r in rows]
    assert ("client_a", None) in pairs
    assert ("client_b", "user_guyuan") in pairs
    # client_c (frozen) 不应出现
    assert not any(p[0] == "client_c" for p in pairs)


@pytest.mark.integration
def test_v_user_visible_clients_user_filter(db_with_data: Database):
    """user filter 在 Repository 层加 WHERE"""
    rows = db_with_data.fetchall(
        """SELECT id FROM v_user_visible_clients
           WHERE viewer_user_id IS NULL OR viewer_user_id = ?
           ORDER BY id""",
        ("user_guyuan",),
    )
    ids = [r["id"] for r in rows]
    assert "client_a" in ids and "client_b" in ids
    assert "client_c" not in ids


# ─────────────────────────────────────────────────────────────────────────────
# v_client_facts
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_v_client_facts_aggregates(db_with_data: Database):
    """client_a 应该:1 active event / 2 pending tasks"""
    row = db_with_data.fetchone("SELECT * FROM v_client_facts WHERE id = 'client_a'")
    assert row["active_event_count"] == 1
    assert row["pending_tasks_count"] == 2  # todo + doing(done 不算)


@pytest.mark.integration
def test_v_client_facts_excludes_frozen(db_with_data: Database):
    """frozen client 不应出现"""
    rows = db_with_data.fetchall("SELECT id FROM v_client_facts WHERE id = 'client_c'")
    assert rows == []


# ─────────────────────────────────────────────────────────────────────────────
# v_active_event_lines
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_v_active_event_lines_filters_status(db_with_data: Database):
    rows = db_with_data.fetchall("SELECT id, status FROM v_active_event_lines ORDER BY id")
    statuses = [r["status"] for r in rows]
    assert all(s == "active" for s in statuses)


@pytest.mark.integration
def test_v_active_event_lines_orphan_allowed(db_with_data: Database):
    """primary_client_id IS NULL 的事件线(孤儿)也应出现"""
    ids = [r["id"] for r in db_with_data.fetchall("SELECT id FROM v_active_event_lines")]
    assert "el_3" in ids  # 孤儿 active 事件线
    assert "el_1" in ids  # 挂 client_a 的
    assert "el_2" not in ids  # paused
    # 注意:el_1 挂 client_a (active),所以会出现
    # 假如它挂 frozen client_c,会被排除


# ─────────────────────────────────────────────────────────────────────────────
# v_pending_tasks
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_v_pending_tasks_filters_status(db_with_data: Database):
    rows = db_with_data.fetchall("SELECT id, status FROM v_pending_tasks ORDER BY id")
    statuses = {r["status"] for r in rows}
    assert statuses == {"todo", "doing"}
    assert "done" not in statuses
    ids = [r["id"] for r in rows]
    assert set(ids) == {"t_1", "t_2", "t_4"}  # 3 个待办,1 个 done 排除


# ─────────────────────────────────────────────────────────────────────────────
# v_searchable_knowledge
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_v_searchable_knowledge_filters_empty_text(db_with_data: Database):
    """空 searchable_text 的 row 不应出现"""
    rows = db_with_data.fetchall("SELECT id FROM v_searchable_knowledge ORDER BY id")
    ids = [r["id"] for r in rows]
    assert "k_1" in ids  # 有内容
    assert "k_2" not in ids  # 空 searchable_text


@pytest.mark.integration
def test_v_searchable_knowledge_excludes_frozen_client(db_with_data: Database):
    """挂在 frozen client 的 knowledge 不应出现"""
    ids = [r["id"] for r in db_with_data.fetchall("SELECT id FROM v_searchable_knowledge")]
    assert "k_3" not in ids  # k_3 挂在 client_c(frozen)
