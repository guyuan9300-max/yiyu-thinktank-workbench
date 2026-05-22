"""F1.1 验证 · ClientRepository 完整 CRUD + 状态唯一真相

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_client_repository.py -v

覆盖:
- CRUD (create / get / update)
- 列表查询 (list_active / list_all / 占位兼容)
- 状态唯一真相 (freeze / unfreeze / archive / is_frozen / is_archived / can_write)
- 边界 (空 id / 空 alias / 不存在 / 空 name 不许创建)
- W2 占位接口向后兼容
"""
from __future__ import annotations

import sqlite3

import pytest

from app.modules.client import (
    ClientCreatePayload,
    ClientRepository,
    ClientUpdatePayload,
    get_client_repository,
)


@pytest.fixture
def db() -> sqlite3.Connection:
    """In-memory DB + 最小 clients schema + v_active_clients view"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            alias TEXT NOT NULL,
            domain TEXT NOT NULL,
            type TEXT NOT NULL,
            intro TEXT NOT NULL,
            stage TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#5B7BFE',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE VIEW v_active_clients AS
        SELECT id, name FROM clients
        WHERE stage NOT IN ('frozen', 'archived', 'lost')
        """
    )
    # [B] fixture 同步债修复: AI A commit 40264eb (F1.7 + N3 A1) 加了
    # client_stage_audit 表。ClientRepository.archive()/freeze() 内部写 audit log,
    # 测试需要该表存在。跟 backend/app/db.py CREATE TABLE 对齐。
    conn.execute(
        """
        CREATE TABLE client_stage_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            old_stage TEXT,
            new_stage TEXT NOT NULL,
            actor_type TEXT NOT NULL DEFAULT 'system',
            actor_id TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT '',
            guard_action TEXT NOT NULL DEFAULT 'applied',
            changed_at TEXT NOT NULL
        )
        """
    )
    return conn


# ── CRUD 基础 ────────────────────────────────────────────────


def test_factory_function(db: sqlite3.Connection) -> None:
    """get_client_repository 工厂函数返回正确类型"""
    repo = get_client_repository(db)
    assert isinstance(repo, ClientRepository)


def test_create_get_basic(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    created = repo.create(
        ClientCreatePayload(name="日慈基金会", alias="日慈", intro="心理健康公益")
    )
    assert created.name == "日慈基金会"
    assert created.alias == "日慈"
    assert created.intro == "心理健康公益"
    assert created.stage == "lead"  # default
    assert created.color == "#5B7BFE"  # default
    assert created.id.startswith("client_")

    fetched = repo.get_by_id(created.id)
    assert fetched == created


def test_create_alias_defaults_to_name(db: sqlite3.Connection) -> None:
    """alias 为空时默认用 name"""
    repo = ClientRepository(db)
    created = repo.create(ClientCreatePayload(name="单名客户"))
    assert created.alias == "单名客户"


def test_create_empty_name_raises(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    with pytest.raises(ValueError, match="name 不能为空"):
        repo.create(ClientCreatePayload(name=""))


def test_create_whitespace_only_name_raises(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    with pytest.raises(ValueError, match="name 不能为空"):
        repo.create(ClientCreatePayload(name="   "))


def test_get_by_alias(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    repo.create(ClientCreatePayload(name="日慈基金会", alias="日慈"))
    found = repo.get_by_alias("日慈")
    assert found is not None
    assert found.name == "日慈基金会"


def test_get_by_empty_returns_none(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    assert repo.get_by_id("") is None
    assert repo.get_by_id("nonexistent") is None
    assert repo.get_by_alias("") is None
    assert repo.get_by_alias("nonexistent") is None


# ── 列表查询 ──────────────────────────────────────────────────


def test_list_active_excludes_frozen_and_archived(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    repo.create(ClientCreatePayload(name="客户 A", stage="active"))
    repo.create(ClientCreatePayload(name="客户 B", stage="frozen"))
    repo.create(ClientCreatePayload(name="客户 C", stage="archived"))
    repo.create(ClientCreatePayload(name="客户 D", stage="lost"))
    repo.create(ClientCreatePayload(name="客户 E", stage="discovery"))

    actives = repo.list_active()
    names = {c.name for c in actives}
    assert names == {"客户 A", "客户 E"}


def test_list_all_default_excludes_archived_only(db: sqlite3.Connection) -> None:
    """list_all() 默认包含 frozen, 但排除 archived/lost"""
    repo = ClientRepository(db)
    repo.create(ClientCreatePayload(name="A", stage="active"))
    repo.create(ClientCreatePayload(name="B", stage="frozen"))
    repo.create(ClientCreatePayload(name="C", stage="archived"))

    result = repo.list_all()
    names = {c.name for c in result}
    assert names == {"A", "B"}  # frozen 留, archived 砍


def test_list_all_with_include_frozen_returns_everything(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    repo.create(ClientCreatePayload(name="A", stage="active"))
    repo.create(ClientCreatePayload(name="B", stage="frozen"))
    repo.create(ClientCreatePayload(name="C", stage="archived"))

    result = repo.list_all(include_frozen=True)
    assert len(result) == 3


# ── 写入 / 更新 ───────────────────────────────────────────────


def test_update_partial(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    created = repo.create(ClientCreatePayload(name="客户 X"))
    updated = repo.update(created.id, ClientUpdatePayload(intro="新简介"))
    assert updated.intro == "新简介"
    assert updated.name == "客户 X"  # 未改的字段保留


def test_update_updates_timestamp(db: sqlite3.Connection) -> None:
    """update 应该刷 updated_at"""
    repo = ClientRepository(db)
    created = repo.create(ClientCreatePayload(name="X"))
    original_updated = created.updated_at
    # 加 sleep 避免时间戳一致 (CI 环境 ISO 时间精度足够)
    import time

    time.sleep(0.01)
    updated = repo.update(created.id, ClientUpdatePayload(intro="改"))
    assert updated.updated_at != original_updated


def test_update_empty_patch_is_noop(db: sqlite3.Connection) -> None:
    """全 None 的 patch 不写 db, 返回 existing"""
    repo = ClientRepository(db)
    created = repo.create(ClientCreatePayload(name="X"))
    result = repo.update(created.id, ClientUpdatePayload())
    assert result == created  # 未改


def test_update_nonexistent_raises(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    with pytest.raises(ValueError, match="client not found"):
        repo.update("nonexistent", ClientUpdatePayload(name="X"))


def test_update_strips_text_fields(db: sqlite3.Connection) -> None:
    """update name 时会自动 strip"""
    repo = ClientRepository(db)
    created = repo.create(ClientCreatePayload(name="X"))
    updated = repo.update(created.id, ClientUpdatePayload(name="  带空格  "))
    assert updated.name == "带空格"


# ── 状态唯一真相 (L2 核心) ────────────────────────────────────


def test_freeze_unfreeze(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    created = repo.create(ClientCreatePayload(name="日慈"))
    assert not repo.is_frozen(created.id)
    assert repo.can_write(created.id)

    repo.freeze(created.id, reason="多账号同步冲突")
    assert repo.is_frozen(created.id)
    assert not repo.can_write(created.id)  # frozen 不可写

    repo.unfreeze(created.id)
    assert not repo.is_frozen(created.id)
    assert repo.can_write(created.id)


def test_freeze_idempotent(db: sqlite3.Connection) -> None:
    """已冻结再 freeze 不报错"""
    repo = ClientRepository(db)
    created = repo.create(ClientCreatePayload(name="X", stage="frozen"))
    result1 = repo.freeze(created.id)
    result2 = repo.freeze(created.id)
    assert result1.stage == "frozen"
    assert result2.stage == "frozen"


def test_archive(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    created = repo.create(ClientCreatePayload(name="日慈"))
    repo.archive(created.id)
    assert repo.is_archived(created.id)
    assert not repo.can_write(created.id)


def test_is_archived_includes_lost(db: sqlite3.Connection) -> None:
    """is_archived() 应包含 'lost' 状态"""
    repo = ClientRepository(db)
    a = repo.create(ClientCreatePayload(name="A", stage="archived"))
    b = repo.create(ClientCreatePayload(name="B", stage="lost"))
    c = repo.create(ClientCreatePayload(name="C", stage="active"))
    assert repo.is_archived(a.id)
    assert repo.is_archived(b.id)
    assert not repo.is_archived(c.id)


def test_can_write_combines_states(db: sqlite3.Connection) -> None:
    """can_write 综合 frozen + archived + lost 判断"""
    repo = ClientRepository(db)
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    b = repo.create(ClientCreatePayload(name="B", stage="frozen"))
    c = repo.create(ClientCreatePayload(name="C", stage="archived"))
    d = repo.create(ClientCreatePayload(name="D", stage="lost"))
    e = repo.create(ClientCreatePayload(name="E", stage="paused"))  # paused 可写

    assert repo.can_write(a.id)
    assert not repo.can_write(b.id)
    assert not repo.can_write(c.id)
    assert not repo.can_write(d.id)
    assert repo.can_write(e.id)


def test_can_write_nonexistent_returns_false(db: sqlite3.Connection) -> None:
    """不存在的 client can_write 返回 False"""
    repo = ClientRepository(db)
    assert not repo.can_write("nonexistent")


def test_freeze_nonexistent_raises(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    with pytest.raises(ValueError, match="client not found"):
        repo.freeze("nonexistent")


def test_unfreeze_nonexistent_raises(db: sqlite3.Connection) -> None:
    repo = ClientRepository(db)
    with pytest.raises(ValueError, match="client not found"):
        repo.unfreeze("nonexistent")


# ── W2 占位接口向后兼容 ───────────────────────────────────────


def test_backward_compat_w2_placeholder(db: sqlite3.Connection) -> None:
    """W2 占位的 list_active_client_ids / count_active 仍然工作"""
    repo = ClientRepository(db)
    repo.create(ClientCreatePayload(name="A", stage="active"))
    repo.create(ClientCreatePayload(name="B", stage="frozen"))
    repo.create(ClientCreatePayload(name="C", stage="archived"))

    ids = repo.list_active_client_ids()
    assert len(ids) == 1  # 只有 A
    assert repo.count_active() == 1


# ── DB adapter (raw sqlite3.Connection vs wrapper) ──────────


def test_works_with_raw_sqlite3_connection(db: sqlite3.Connection) -> None:
    """ClientRepository 既能用 Database wrapper 也能用 raw Connection"""
    repo = ClientRepository(db)  # db 是 raw sqlite3.Connection
    repo.create(ClientCreatePayload(name="X"))
    assert repo.count_active() == 1
