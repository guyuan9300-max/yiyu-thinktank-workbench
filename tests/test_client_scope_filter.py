"""F1.3 验证 · ClientScopeFilter

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_client_scope_filter.py -v
"""
from __future__ import annotations

import sqlite3

import pytest

from app.modules.client import (
    REASON_ARCHIVED,
    REASON_FROZEN,
    REASON_LOST,
    REASON_NOT_FOUND,
    ClientCreatePayload,
    ClientFactView,
    ClientRepository,
    ClientScopeFilter,
    ScopeFilterError,
    get_client_scope_filter,
)


@pytest.fixture
def db() -> sqlite3.Connection:
    """In-memory DB + clients schema + v_active_clients view"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE clients (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, alias TEXT NOT NULL,
            domain TEXT NOT NULL, type TEXT NOT NULL, intro TEXT NOT NULL,
            stage TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#5B7BFE',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
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
    return conn


@pytest.fixture
def repo(db: sqlite3.Connection) -> ClientRepository:
    return ClientRepository(db)


@pytest.fixture
def scope(repo: ClientRepository) -> ClientScopeFilter:
    return ClientScopeFilter(repo)


# ── assert_writable / is_writable ────────────────────────────


def test_assert_writable_active_passes(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    created = repo.create(ClientCreatePayload(name="日慈", stage="active"))
    # 不应抛
    scope.assert_writable(created.id)


def test_assert_writable_nonexistent_raises(scope: ClientScopeFilter) -> None:
    with pytest.raises(ScopeFilterError) as exc_info:
        scope.assert_writable("nonexistent")
    assert exc_info.value.client_id == "nonexistent"
    assert exc_info.value.reason == REASON_NOT_FOUND


def test_assert_writable_empty_id_raises(scope: ClientScopeFilter) -> None:
    with pytest.raises(ScopeFilterError) as exc_info:
        scope.assert_writable("")
    assert exc_info.value.reason == REASON_NOT_FOUND


def test_assert_writable_frozen_raises(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    created = repo.create(ClientCreatePayload(name="冻结客户", stage="frozen"))
    with pytest.raises(ScopeFilterError) as exc_info:
        scope.assert_writable(created.id)
    assert exc_info.value.client_id == created.id
    assert exc_info.value.reason == REASON_FROZEN


def test_assert_writable_archived_raises(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    created = repo.create(ClientCreatePayload(name="归档客户", stage="archived"))
    with pytest.raises(ScopeFilterError) as exc_info:
        scope.assert_writable(created.id)
    assert exc_info.value.reason == REASON_ARCHIVED


def test_assert_writable_lost_raises(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    created = repo.create(ClientCreatePayload(name="失败客户", stage="lost"))
    with pytest.raises(ScopeFilterError) as exc_info:
        scope.assert_writable(created.id)
    assert exc_info.value.reason == REASON_LOST


def test_assert_writable_paused_passes(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    """paused 客户应该允许写 (跟 active 一样, 只是暂停推进, 不冻结写入)"""
    created = repo.create(ClientCreatePayload(name="暂停客户", stage="paused"))
    scope.assert_writable(created.id)  # 不应抛


def test_assert_writable_lead_passes(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    created = repo.create(ClientCreatePayload(name="客户 A", stage="lead"))
    scope.assert_writable(created.id)


def test_assert_writable_discovery_passes(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    created = repo.create(ClientCreatePayload(name="客户 B", stage="discovery"))
    scope.assert_writable(created.id)


def test_assert_writable_custom_stage_passes(
    scope: ClientScopeFilter, repo: ClientRepository, db: sqlite3.Connection
) -> None:
    """自定义 stage (如真实日慈的 '待导入资料') 不在 frozen/archived/lost 里, 应允许写"""
    # 绕过 ClientCreatePayload 的 Literal 校验, 直接 INSERT
    db.execute(
        """
        INSERT INTO clients (id, name, alias, domain, type, intro, stage, color,
                             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "client_custom", "自定义阶段", "自定义", "", "", "",
            "待导入资料", "#5B7BFE", "2026-05-21", "2026-05-21",
        ),
    )
    scope.assert_writable("client_custom")  # 不应抛


def test_is_writable_returns_bool(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    active = repo.create(ClientCreatePayload(name="A", stage="active"))
    frozen = repo.create(ClientCreatePayload(name="B", stage="frozen"))
    assert scope.is_writable(active.id) is True
    assert scope.is_writable(frozen.id) is False
    assert scope.is_writable("nonexistent") is False


# ── scope_query ──────────────────────────────────────────────


def test_scope_query_none_returns_all_active(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    """传 None 默认返回所有活跃客户 (排除 frozen/archived/lost)"""
    repo.create(ClientCreatePayload(name="A", stage="active"))
    repo.create(ClientCreatePayload(name="B", stage="frozen"))
    repo.create(ClientCreatePayload(name="C", stage="archived"))
    repo.create(ClientCreatePayload(name="D", stage="discovery"))

    result = scope.scope_query(None)
    names = sorted([repo.get_by_id(cid).name for cid in result])  # type: ignore
    assert names == ["A", "D"]


def test_scope_query_given_ids_filters(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    b = repo.create(ClientCreatePayload(name="B", stage="frozen"))
    c = repo.create(ClientCreatePayload(name="C", stage="active"))
    result = scope.scope_query([a.id, b.id, c.id])
    assert b.id not in result
    assert set(result) == {a.id, c.id}


def test_scope_query_include_frozen(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    b = repo.create(ClientCreatePayload(name="B", stage="frozen"))
    result = scope.scope_query([a.id, b.id], include_frozen=True)
    assert set(result) == {a.id, b.id}


def test_scope_query_include_archived(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    b = repo.create(ClientCreatePayload(name="B", stage="archived"))
    c = repo.create(ClientCreatePayload(name="C", stage="lost"))
    result = scope.scope_query([a.id, b.id, c.id], include_archived=True)
    assert set(result) == {a.id, b.id, c.id}


def test_scope_query_require_writable_overrides_flags(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    """require_writable=True 时, include_frozen/archived 都被强制覆盖"""
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    b = repo.create(ClientCreatePayload(name="B", stage="frozen"))
    c = repo.create(ClientCreatePayload(name="C", stage="archived"))
    # 即使 include_frozen=True + include_archived=True, require_writable 强制覆盖
    result = scope.scope_query(
        [a.id, b.id, c.id],
        include_frozen=True, include_archived=True, require_writable=True,
    )
    assert set(result) == {a.id}


def test_scope_query_sorted_by_name(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    """返回结果按 name 排序"""
    c1 = repo.create(ClientCreatePayload(name="Charlie", stage="active"))
    c2 = repo.create(ClientCreatePayload(name="Alice", stage="active"))
    c3 = repo.create(ClientCreatePayload(name="Bob", stage="active"))
    result = scope.scope_query([c1.id, c2.id, c3.id])
    names = [repo.get_by_id(cid).name for cid in result]  # type: ignore
    assert names == ["Alice", "Bob", "Charlie"]


def test_scope_query_nonexistent_ids_dropped(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    result = scope.scope_query([a.id, "nonexistent_1", "nonexistent_2"])
    assert result == [a.id]


def test_scope_query_empty_list_returns_empty(
    scope: ClientScopeFilter,
) -> None:
    assert scope.scope_query([]) == []


# ── filter_records_by_client ─────────────────────────────────


def test_filter_records_dict_keeps_writable(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    b = repo.create(ClientCreatePayload(name="B", stage="frozen"))
    records = {a.id: "data_a", b.id: "data_b"}
    filtered = scope.filter_records_by_client(records)
    assert filtered == {a.id: "data_a"}


def test_filter_records_dict_drops_archived(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    b = repo.create(ClientCreatePayload(name="B", stage="archived"))
    c = repo.create(ClientCreatePayload(name="C", stage="lost"))
    records = {a.id: 1, b.id: 2, c.id: 3}
    filtered = scope.filter_records_by_client(records)
    assert filtered == {a.id: 1}


def test_filter_records_dict_empty_returns_empty(
    scope: ClientScopeFilter,
) -> None:
    assert scope.filter_records_by_client({}) == {}


def test_filter_records_preserves_value_type(
    scope: ClientScopeFilter, repo: ClientRepository
) -> None:
    """非字符串 value 也能 preserve"""
    a = repo.create(ClientCreatePayload(name="A", stage="active"))
    records: dict[str, list[int]] = {a.id: [1, 2, 3]}
    filtered = scope.filter_records_by_client(records)
    assert filtered == {a.id: [1, 2, 3]}


# ── 工厂 + 异常 ───────────────────────────────────────────────


def test_factory_with_db(db: sqlite3.Connection) -> None:
    scope = get_client_scope_filter(db)
    assert isinstance(scope, ClientScopeFilter)


def test_factory_with_repo(repo: ClientRepository) -> None:
    scope = get_client_scope_filter(repo)
    assert isinstance(scope, ClientScopeFilter)


def test_scope_filter_error_has_client_id_and_reason() -> None:
    err = ScopeFilterError("client_x", REASON_FROZEN)
    assert err.client_id == "client_x"
    assert err.reason == REASON_FROZEN
    assert "client_x" in str(err)
    assert "client_frozen" in str(err)


# ── 集成: 跟 F1.2 ClientFactView 配合 ───────────────────────


def test_scope_filter_with_fact_view(
    scope: ClientScopeFilter, db: sqlite3.Connection, repo: ClientRepository
) -> None:
    """F1.3 + F1.2 配合: ScopeFilter 可作为 ClientFactView 的前置守门"""
    # 加 schema 让 ClientFactView 不崩
    db.execute("""
        CREATE TABLE event_lines (
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'custom',
            status TEXT NOT NULL DEFAULT 'active',
            stage TEXT, summary TEXT, intent TEXT,
            current_blocker TEXT, recent_decision TEXT, next_step TEXT,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            owner_id TEXT, owner_name TEXT,
            primary_client_id TEXT, primary_client_name TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY, organization_id TEXT NOT NULL DEFAULT '',
            client_id TEXT, title TEXT NOT NULL, description TEXT NOT NULL,
            status TEXT NOT NULL, priority TEXT NOT NULL,
            list_id TEXT NOT NULL DEFAULT 'list-0',
            creator_id TEXT NOT NULL DEFAULT '',
            owner_id TEXT, owner_name TEXT NOT NULL DEFAULT '',
            progress_status TEXT NOT NULL DEFAULT 'todo',
            ddl TEXT NOT NULL DEFAULT '',
            deadline_at TEXT, scheduled_start_at TEXT,
            scheduled_end_at TEXT, completed_at TEXT,
            start_date TEXT, due_date TEXT,
            duration_minutes INTEGER NOT NULL DEFAULT 60,
            event_line_id TEXT, business_category TEXT,
            current_blocker TEXT, next_action TEXT, recent_decision TEXT,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            source_type TEXT NOT NULL DEFAULT '', source_id TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE commitments (
            id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
            committer TEXT NOT NULL, recipient TEXT NOT NULL,
            commitment_type TEXT NOT NULL DEFAULT 'delivery',
            content TEXT NOT NULL, deadline TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            related_term_ids_json TEXT NOT NULL DEFAULT '[]',
            source_type TEXT NOT NULL DEFAULT '',
            source_id TEXT NOT NULL DEFAULT '',
            fulfilled_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE atomic_facts (
            id TEXT PRIMARY KEY, client_id TEXT NOT NULL,
            subject_entity_id TEXT, subject_text TEXT NOT NULL,
            attribute TEXT NOT NULL, value_text TEXT NOT NULL,
            value_normalized TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0,
            source_v2_chunk_id TEXT, source_v2_document_id TEXT,
            evidence_text TEXT, status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE client_dna_documents (
            client_id TEXT NOT NULL, module_key TEXT NOT NULL,
            title TEXT NOT NULL, markdown_content TEXT NOT NULL,
            normalized_text TEXT NOT NULL, summary TEXT NOT NULL,
            file_name TEXT NOT NULL, content_hash TEXT NOT NULL,
            source_kind TEXT NOT NULL DEFAULT 'manual',
            missing_info_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
            PRIMARY KEY (client_id, module_key)
        )
    """)
    active = repo.create(ClientCreatePayload(name="活跃客户", stage="active"))
    frozen = repo.create(ClientCreatePayload(name="冻结客户", stage="frozen"))

    # 模拟 main.py 写入前的守门
    scope.assert_writable(active.id)  # 不抛
    with pytest.raises(ScopeFilterError):
        scope.assert_writable(frozen.id)

    # ClientFactView 拿到 active 的 bundle, frozen 的也可以拿(read 不受 scope 限制)
    view = ClientFactView(db, client_repo=repo)
    assert view.get_fact_bundle(active.id) is not None
    # frozen 客户的 bundle 也能拿(read 不被 scope 拦截, 只有 write 才拦)
    assert view.get_fact_bundle(frozen.id) is not None
