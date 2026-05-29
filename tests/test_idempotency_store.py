"""F2.8 验证 · IdempotencyStore (N3 A6 预留 — 防 AI retry 重复创建)

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_idempotency_store.py -v

服务:
- V2.2_NORTH_STAR.md N3 (3.0 共享办公室接入预留)
- A6: AI agent retry 不重复创建任务/事实/event_log

覆盖:
- find() 流程 (首次 / 命中 completed / 命中 in_progress / 过期)
- start() / complete() / mark_failed()
- body hash 校验 (同 key 不同 body → IdempotencyKeyMismatchError)
- cleanup_expired()
- actor_type 跟踪 (human vs ai_agent)
"""
from __future__ import annotations

import sqlite3
import time

import pytest

from app.services.idempotency_store import (
    IdempotencyKeyMismatchError,
    IdempotencyStore,
    get_idempotency_store,
)


# ── DB fixture (跟 client_repository.py 模式一致) ───────────


class _ConnAdapter:
    """sqlite3.Connection → _DbLike protocol"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def fetchone(self, query: str, params: tuple = ()):
        return self._conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()):
        return list(self._conn.execute(query, params).fetchall())

    def execute(self, query: str, params: tuple = ()) -> None:
        self._conn.execute(query, params)


@pytest.fixture
def db() -> sqlite3.Connection:
    """in-memory DB + idempotency_keys schema (跟 backend/app/db.py 3438 行一致)"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE idempotency_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT NOT NULL,
            request_method TEXT NOT NULL,
            request_path TEXT NOT NULL,
            request_body_hash TEXT NOT NULL DEFAULT '',
            response_status INTEGER NOT NULL,
            response_body TEXT NOT NULL DEFAULT '',
            actor_type TEXT NOT NULL DEFAULT 'human',
            actor_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed'
        );
        CREATE UNIQUE INDEX idx_idempotency_keys_lookup
            ON idempotency_keys(idempotency_key, request_method, request_path);
        """
    )
    return conn


@pytest.fixture
def store(db: sqlite3.Connection) -> IdempotencyStore:
    return IdempotencyStore(_ConnAdapter(db))


# ── find · 首次请求 ─────────────────────────────────────────


def test_find_returns_none_for_new_key(store: IdempotencyStore) -> None:
    """首次请求,find 返回 None (调用方应该 start + 处理 + complete)"""
    assert store.find("new-key-001", "POST", "/api/v1/tasks") is None


def test_find_returns_none_for_empty_key(store: IdempotencyStore) -> None:
    """空 key 一定 None,避免误命中"""
    assert store.find("", "POST", "/api/v1/tasks") is None


# ── start + find · 命中 ──────────────────────────────────────


def test_start_then_find_returns_in_progress(store: IdempotencyStore) -> None:
    """start 后立即 find,应该看到 in_progress (调用方应该返回 409)"""
    store.start("key-abc", "POST", "/api/v1/tasks", payload={"title": "T1"})
    cached = store.find("key-abc", "POST", "/api/v1/tasks", payload={"title": "T1"})
    assert cached is not None
    assert cached.status == "in_progress"
    assert cached.response_status == 0  # 还没完成


def test_complete_marks_status_completed(store: IdempotencyStore) -> None:
    """complete 后 find 返回 completed + response cache"""
    store.start("key-xyz", "POST", "/api/v1/tasks", payload={"title": "T1"})
    store.complete(
        "key-xyz", "POST", "/api/v1/tasks",
        status=201, response_body={"id": "task_1", "title": "T1"},
    )
    cached = store.find("key-xyz", "POST", "/api/v1/tasks", payload={"title": "T1"})
    assert cached is not None
    assert cached.status == "completed"
    assert cached.response_status == 201
    assert '"id": "task_1"' in cached.response_body


# ── body hash 校验 ──────────────────────────────────────────


def test_body_mismatch_raises(store: IdempotencyStore) -> None:
    """同 key + 同 endpoint 但 body 不同 → 拒绝 (客户端 bug 或攻击)"""
    store.start("collision-key", "POST", "/api/v1/tasks", payload={"title": "T1"})
    with pytest.raises(IdempotencyKeyMismatchError) as exc_info:
        store.find(
            "collision-key", "POST", "/api/v1/tasks",
            payload={"title": "T2"},  # 不同 body
        )
    assert "collision-key" in str(exc_info.value)
    assert "POST" in str(exc_info.value)


def test_same_body_no_mismatch(store: IdempotencyStore) -> None:
    """同 key + 同 body → 正常命中"""
    payload = {"title": "T1", "priority": "high"}
    store.start("key-same", "POST", "/api/v1/tasks", payload=payload)
    cached = store.find("key-same", "POST", "/api/v1/tasks", payload=payload)
    assert cached is not None


def test_find_without_payload_skips_hash_check(store: IdempotencyStore) -> None:
    """find 不传 payload (查询模式) → 不检 hash,直接返回"""
    store.start("key-no-check", "POST", "/api/v1/tasks", payload={"x": 1})
    cached = store.find("key-no-check", "POST", "/api/v1/tasks")  # 无 payload
    assert cached is not None


# ── 不同 method/path 隔离 ──────────────────────────────────


def test_different_method_treated_as_separate(store: IdempotencyStore) -> None:
    """同 key 但不同 method = 不同记录 (POST vs PATCH)"""
    store.start("key-shared", "POST", "/api/v1/tasks")
    assert store.find("key-shared", "PATCH", "/api/v1/tasks") is None


def test_different_path_treated_as_separate(store: IdempotencyStore) -> None:
    """同 key 但不同 path = 不同记录"""
    store.start("key-shared", "POST", "/api/v1/tasks")
    assert store.find("key-shared", "POST", "/api/v1/clients") is None


# ── 失败/重试场景 ───────────────────────────────────────────


def test_mark_failed_status(store: IdempotencyStore) -> None:
    """mark_failed 后状态变 'failed',下次 retry 当新请求"""
    store.start("key-fail", "POST", "/api/v1/tasks", payload={"x": 1})
    store.mark_failed("key-fail", "POST", "/api/v1/tasks")
    cached = store.find("key-fail", "POST", "/api/v1/tasks", payload={"x": 1})
    assert cached is not None
    assert cached.status == "failed"


# ── actor_type 跟踪 (N3 核心) ──────────────────────────────


def test_actor_type_human_default(store: IdempotencyStore) -> None:
    store.start("key-h", "POST", "/api/v1/tasks", payload={"x": 1})
    cached = store.find("key-h", "POST", "/api/v1/tasks", payload={"x": 1})
    assert cached is not None
    assert cached.actor_type == "human"
    assert cached.actor_id == ""


def test_actor_type_ai_agent_recorded(store: IdempotencyStore) -> None:
    """N3 关键场景: AI agent 写入要带 actor_type='ai_agent' + actor_id"""
    store.start(
        "key-ai", "POST", "/api/v1/tasks",
        payload={"title": "AI 起草的任务"},
        actor_type="ai_agent",
        actor_id="agent_contract_drafter",
    )
    cached = store.find(
        "key-ai", "POST", "/api/v1/tasks",
        payload={"title": "AI 起草的任务"},
    )
    assert cached is not None
    assert cached.actor_type == "ai_agent"
    assert cached.actor_id == "agent_contract_drafter"


# ── 过期清理 ────────────────────────────────────────────────


def test_expired_record_returns_none(
    store: IdempotencyStore, db: sqlite3.Connection
) -> None:
    """过期的记录 find 返回 None (即使表里还在)"""
    # 直接插一条过期记录
    db.execute(
        """
        INSERT INTO idempotency_keys
        (idempotency_key, request_method, request_path, request_body_hash,
         response_status, response_body, actor_type, actor_id,
         created_at, expires_at, status)
        VALUES (?, ?, ?, '', 200, '', 'human', '',
                '2026-01-01T00:00:00+00:00',
                '2026-01-02T00:00:00+00:00',  -- 已经过期
                'completed')
        """,
        ("key-expired", "POST", "/api/v1/tasks"),
    )
    assert store.find("key-expired", "POST", "/api/v1/tasks") is None


def test_cleanup_expired_deletes(
    store: IdempotencyStore, db: sqlite3.Connection
) -> None:
    """cleanup_expired 删过期记录,返回删除条数"""
    # 插 2 条过期 + 1 条有效
    for i, expires in enumerate([
        "2026-01-02T00:00:00+00:00",  # 过期
        "2026-01-02T00:00:00+00:00",  # 过期
        "2099-12-31T00:00:00+00:00",  # 不过期
    ]):
        db.execute(
            """
            INSERT INTO idempotency_keys
            (idempotency_key, request_method, request_path, request_body_hash,
             response_status, response_body, actor_type, actor_id,
             created_at, expires_at, status)
            VALUES (?, 'POST', '/api/v1/tasks', '', 200, '', 'human', '',
                    '2026-01-01T00:00:00+00:00', ?, 'completed')
            """,
            (f"k-{i}", expires),
        )
    deleted = store.cleanup_expired()
    assert deleted == 2
    # 剩 1 条
    row = db.execute("SELECT COUNT(*) AS n FROM idempotency_keys").fetchone()
    assert row["n"] == 1


# ── UNIQUE 约束验证 ────────────────────────────────────────


def test_start_twice_same_key_raises(store: IdempotencyStore) -> None:
    """同 key + 同 method + 同 path 第二次 start → UNIQUE 抛错"""
    store.start("key-unique", "POST", "/api/v1/tasks", payload={"x": 1})
    with pytest.raises(sqlite3.IntegrityError):
        store.start("key-unique", "POST", "/api/v1/tasks", payload={"x": 1})


# ── 工厂 ────────────────────────────────────────────────────


def test_factory(db: sqlite3.Connection) -> None:
    s = get_idempotency_store(_ConnAdapter(db))
    assert isinstance(s, IdempotencyStore)


# ── 集成: 端到端 Stripe 风格幂等流程 ──────────────────────


def test_stripe_style_full_flow(store: IdempotencyStore) -> None:
    """完整端到端: 模拟客户端 retry 网络请求

    场景: AI agent 提交建任务请求, 第一次成功但网络超时, retry 时应该拿到缓存结果
    """
    key = "ai-retry-scenario"
    method, path = "POST", "/api/v1/tasks"
    payload = {"title": "AI 起草: 跟进供应商合同", "owner_id": "user_admin_demo"}

    # 第 1 次请求
    cached = store.find(key, method, path, payload=payload)
    assert cached is None  # 首次

    store.start(key, method, path, payload=payload,
                actor_type="ai_agent", actor_id="agent_contract_drafter")

    # ...业务处理 (模拟创建任务)...
    fake_task = {"id": "task_xxx", "title": payload["title"]}
    store.complete(key, method, path, status=201, response_body=fake_task)

    # 第 2 次 retry (网络超时后)
    cached_2 = store.find(key, method, path, payload=payload)
    assert cached_2 is not None
    assert cached_2.status == "completed"
    assert cached_2.response_status == 201
    assert '"id": "task_xxx"' in cached_2.response_body
    assert cached_2.actor_type == "ai_agent"  # actor 跟踪保留

    # 第 3 次 retry (改了 body, 应该拒绝)
    with pytest.raises(IdempotencyKeyMismatchError):
        store.find(key, method, path, payload={"title": "改了的标题"})
