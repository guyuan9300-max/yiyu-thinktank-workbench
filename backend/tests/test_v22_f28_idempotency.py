"""v2.2 F2.8 (N3 A6) · IdempotencyStore 测试

服务: V2.2_NORTH_STAR.md N3 — 防 AI agent retry 重复创建

测试覆盖:
- schema 完整性 (idempotency_keys 表)
- 首次 find 不命中
- 完整流程: start → complete → 再 find 命中
- 同 key 不同 body → IdempotencyKeyMismatchError
- 过期 key 视为不存在
- failed 状态可以清理
- cleanup_expired 定时任务
- N3 actor_type='ai_agent' 支持

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_f28_idempotency.py -v
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.services.idempotency_store import (  # noqa: E402
    IdempotencyKeyMismatchError,
    IdempotencyStore,
    _hash_body,
    get_idempotency_store,
)


SCOPE_A = {
    "sandbox_id": "sbx_a",
    "organization_id": "org_a",
    "actor_type": "human",
    "actor_id": "user_a",
}


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    return db


@pytest.fixture
def store(db: Database) -> IdempotencyStore:
    return IdempotencyStore(db)


# ════════════════════════════════════════════════════════════════
# Schema 完整性
# ════════════════════════════════════════════════════════════════


def test_idempotency_keys_table_exists(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='idempotency_keys'"
    )
    assert len(rows) == 1


def test_idempotency_keys_columns_complete(db: Database):
    rows = db.fetchall("PRAGMA table_info(idempotency_keys)")
    col_names = {r["name"] for r in rows}
    required = {
        "id", "idempotency_key", "request_method", "request_path",
        "request_body_hash",
        "response_status", "response_body",
        "sandbox_id", "organization_id", "actor_type", "actor_id", "claim_token",
        "created_at", "expires_at", "status",
    }
    missing = required - col_names
    assert not missing, f"missing: {missing}"


def test_idempotency_unique_constraint(db: Database):
    """同 key + method + path 不能重复 — 这是幂等的核心保证"""
    now = datetime.now(timezone.utc).isoformat()
    later = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    db.conn.execute(
        """INSERT INTO idempotency_keys (
            idempotency_key, request_method, request_path,
            request_body_hash, response_status, response_body,
            created_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("key_001", "POST", "/api/v1/tasks", "h1", 200, "{}", now, later),
    )
    db.conn.commit()
    import sqlite3 as sq3
    with pytest.raises(sq3.IntegrityError):
        db.conn.execute(
            """INSERT INTO idempotency_keys (
                idempotency_key, request_method, request_path,
                request_body_hash, response_status, response_body,
                created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("key_001", "POST", "/api/v1/tasks", "h2", 200, "{}", now, later),
        )


def test_idempotency_same_key_diff_path_allowed(db: Database):
    """同 key 但不同 path → 允许 (不是冲突)"""
    now = datetime.now(timezone.utc).isoformat()
    later = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    db.conn.execute(
        """INSERT INTO idempotency_keys (
            idempotency_key, request_method, request_path,
            request_body_hash, response_status, response_body,
            created_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("key_002", "POST", "/api/v1/tasks", "", 200, "{}", now, later),
    )
    db.conn.execute(
        """INSERT INTO idempotency_keys (
            idempotency_key, request_method, request_path,
            request_body_hash, response_status, response_body,
            created_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("key_002", "POST", "/api/v1/facts", "", 200, "{}", now, later),
    )
    db.conn.commit()
    rows = db.fetchall(
        "SELECT * FROM idempotency_keys WHERE idempotency_key = 'key_002'"
    )
    assert len(rows) == 2


def test_same_key_is_independent_across_sandbox_org_and_actor(
    store: IdempotencyStore,
) -> None:
    payload = {"title": "same request"}
    scopes = (
        SCOPE_A,
        {**SCOPE_A, "sandbox_id": "sbx_b", "organization_id": "org_b"},
        {**SCOPE_A, "actor_id": "user_b"},
        {**SCOPE_A, "actor_type": "ai_agent"},
    )

    for index, scope in enumerate(scopes):
        assert store.find("shared-key", "POST", "/api/v1/tasks", payload, **scope) is None
        claim_token = store.start("shared-key", "POST", "/api/v1/tasks", payload, **scope)
        store.complete(
            "shared-key",
            "POST",
            "/api/v1/tasks",
            status=200,
            response_body={"id": f"task_{index}"},
            claim_token=claim_token,
            **scope,
        )

    replayed = [
        json.loads(
            store.find("shared-key", "POST", "/api/v1/tasks", payload, **scope).response_body
        )["id"]
        for scope in scopes
    ]
    assert replayed == ["task_0", "task_1", "task_2", "task_3"]


def test_old_unscoped_schema_is_migrated_without_replaying_old_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
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
    now = datetime.now(timezone.utc).isoformat()
    later = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    conn.execute(
        """
        INSERT INTO idempotency_keys(
            idempotency_key, request_method, request_path, request_body_hash,
            response_status, response_body, actor_type, actor_id,
            created_at, expires_at, status
        ) VALUES (?, 'POST', '/api/v1/tasks', '', 200, '{"id":"legacy"}',
                  'human', 'user_a', ?, ?, 'completed')
        """,
        ("legacy-key", now, later),
    )
    conn.commit()
    conn.close()

    migrated = Database(db_path)
    columns = {str(row["name"]) for row in migrated.fetchall("PRAGMA table_info(idempotency_keys)")}
    assert {"sandbox_id", "organization_id"}.issubset(columns)
    store = IdempotencyStore(migrated)
    assert store.find("legacy-key", "POST", "/api/v1/tasks", **SCOPE_A) is None
    store.start("legacy-key", "POST", "/api/v1/tasks", **SCOPE_A)
    scoped_rows = migrated.fetchall(
        "SELECT sandbox_id, organization_id, actor_id FROM idempotency_keys "
        "WHERE idempotency_key = 'legacy-key' ORDER BY id"
    )
    assert [tuple(row) for row in scoped_rows] == [
        ("", "", "user_a"),
        ("sbx_a", "org_a", "user_a"),
    ]


# ════════════════════════════════════════════════════════════════
# IdempotencyStore 基本流程
# ════════════════════════════════════════════════════════════════


def test_find_returns_none_for_new_key(store: IdempotencyStore):
    """首次请求 → 不命中"""
    result = store.find("never_seen_key", "POST", "/api/v1/tasks", **SCOPE_A)
    assert result is None


def test_empty_key_returns_none(store: IdempotencyStore):
    """空 key (客户端没传 header) → 不查"""
    result = store.find("", "POST", "/api/v1/tasks", **SCOPE_A)
    assert result is None


def test_full_lifecycle_start_then_complete(store: IdempotencyStore, db: Database):
    """完整流程: start → complete → 再 find 命中"""
    payload = {"title": "拟合同", "owner": "顾源源"}

    # 1. 首次 find 不命中
    assert store.find("k_001", "POST", "/api/v1/tasks", payload, **SCOPE_A) is None

    # 2. start: 标记开始处理
    claim_token = store.start(
        "k_001", "POST", "/api/v1/tasks", payload, **SCOPE_A
    )
    db.conn.commit()

    # 3. find 命中, status=in_progress
    cached = store.find("k_001", "POST", "/api/v1/tasks", payload, **SCOPE_A)
    assert cached is not None
    assert cached.status == "in_progress"
    assert cached.actor_type == "human"
    assert cached.actor_id == "user_a"
    assert cached.sandbox_id == "sbx_a"
    assert cached.organization_id == "org_a"

    # 4. complete: 写入结果
    store.complete("k_001", "POST", "/api/v1/tasks",
                   status=201, response_body={"id": "task_abc", "title": "拟合同"},
                   claim_token=claim_token,
                   **SCOPE_A)
    db.conn.commit()

    # 5. 再 find: status=completed + response 缓存
    cached = store.find("k_001", "POST", "/api/v1/tasks", payload, **SCOPE_A)
    assert cached.status == "completed"
    assert cached.response_status == 201
    body = json.loads(cached.response_body)
    assert body["id"] == "task_abc"


def test_body_hash_mismatch_raises(store: IdempotencyStore, db: Database):
    """★ 同 key 但 body 不同 → 抛 IdempotencyKeyMismatchError

    防御场景: 客户端 bug / 攻击, 用同 Idempotency-Key 但改了 payload
    """
    store.start("k_002", "POST", "/api/v1/tasks",
                {"title": "原标题"}, **SCOPE_A)
    db.conn.commit()
    # 用不同 body 查
    with pytest.raises(IdempotencyKeyMismatchError) as exc_info:
        store.find("k_002", "POST", "/api/v1/tasks",
                   {"title": "篡改后的标题"}, **SCOPE_A)
    assert "k_002" in str(exc_info.value)
    assert "different request body" in str(exc_info.value)


def test_same_body_hash_no_raise(store: IdempotencyStore, db: Database):
    """同 key + 同 body → 命中, 不抛"""
    payload = {"title": "拟合同"}
    store.start("k_003", "POST", "/api/v1/tasks", payload, **SCOPE_A)
    db.conn.commit()
    cached = store.find("k_003", "POST", "/api/v1/tasks", payload, **SCOPE_A)
    assert cached is not None


def test_dict_key_order_does_not_affect_hash():
    """JSON 序列化 sort_keys=True 保证 dict 顺序不影响 hash"""
    h1 = _hash_body({"a": 1, "b": 2})
    h2 = _hash_body({"b": 2, "a": 1})
    assert h1 == h2


def test_expired_key_returns_none(store: IdempotencyStore, db: Database):
    """过期 key → find 返回 None (当作不存在)"""
    # 直接 INSERT 一条已过期的
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    db.conn.execute(
        """INSERT INTO idempotency_keys (
            idempotency_key, request_method, request_path,
            request_body_hash, response_status, response_body,
            created_at, expires_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("k_expired", "POST", "/api/v1/x", "h", 200, "{}", now, past, "completed"),
    )
    db.conn.commit()
    result = store.find("k_expired", "POST", "/api/v1/x", **SCOPE_A)
    assert result is None


def test_expired_key_can_be_reused_atomically(store: IdempotencyStore, db: Database) -> None:
    store.start("k_expired_reuse", "POST", "/api/v1/x", ttl_hours=-1, **SCOPE_A)
    assert store.find("k_expired_reuse", "POST", "/api/v1/x", **SCOPE_A) is None
    store.start("k_expired_reuse", "POST", "/api/v1/x", {"retry": True}, **SCOPE_A)
    row = db.fetchone(
        "SELECT status, request_body_hash FROM idempotency_keys "
        "WHERE sandbox_id = ? AND organization_id = ? AND actor_id = ? "
        "AND idempotency_key = 'k_expired_reuse'",
        (SCOPE_A["sandbox_id"], SCOPE_A["organization_id"], SCOPE_A["actor_id"]),
    )
    assert row is not None
    assert row["status"] == "in_progress"
    assert row["request_body_hash"] == _hash_body({"retry": True})


def test_stale_claim_cannot_complete_after_expired_key_is_reused(
    store: IdempotencyStore,
) -> None:
    old_claim = store.start(
        "k_stale_claim", "POST", "/api/v1/x", {"try": 1}, ttl_hours=-1, **SCOPE_A
    )
    new_claim = store.start(
        "k_stale_claim", "POST", "/api/v1/x", {"try": 2}, **SCOPE_A
    )
    assert not store.complete(
        "k_stale_claim",
        "POST",
        "/api/v1/x",
        claim_token=old_claim,
        status=200,
        response_body={"winner": "old"},
        **SCOPE_A,
    )
    assert store.complete(
        "k_stale_claim",
        "POST",
        "/api/v1/x",
        claim_token=new_claim,
        status=200,
        response_body={"winner": "new"},
        **SCOPE_A,
    )
    cached = store.find("k_stale_claim", "POST", "/api/v1/x", {"try": 2}, **SCOPE_A)
    assert cached is not None
    assert json.loads(cached.response_body) == {"winner": "new"}


def test_mark_failed(store: IdempotencyStore, db: Database):
    """failed 状态: retry 当新请求, 不复用"""
    claim_token = store.start("k_fail", "POST", "/api/v1/x", **SCOPE_A)
    db.conn.commit()
    store.mark_failed(
        "k_fail", "POST", "/api/v1/x", claim_token=claim_token, **SCOPE_A
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT status FROM idempotency_keys WHERE idempotency_key = 'k_fail'"
    )
    assert row["status"] == "failed"


def test_failed_key_can_be_reused_immediately(store: IdempotencyStore, db: Database) -> None:
    claim_token = store.start(
        "k_failed_reuse", "POST", "/api/v1/x", {"try": 1}, **SCOPE_A
    )
    store.mark_failed(
        "k_failed_reuse",
        "POST",
        "/api/v1/x",
        claim_token=claim_token,
        **SCOPE_A,
    )
    assert store.find("k_failed_reuse", "POST", "/api/v1/x", **SCOPE_A) is None
    store.start("k_failed_reuse", "POST", "/api/v1/x", {"try": 2}, **SCOPE_A)
    cached = store.find("k_failed_reuse", "POST", "/api/v1/x", {"try": 2}, **SCOPE_A)
    assert cached is not None
    assert cached.status == "in_progress"


def test_cleanup_expired(store: IdempotencyStore, db: Database):
    """定时任务清理过期记录"""
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    # 2 条过期 + 1 条仍有效
    for i, exp in enumerate([past, past, later]):
        db.conn.execute(
            """INSERT INTO idempotency_keys (
                idempotency_key, request_method, request_path,
                request_body_hash, response_status, response_body,
                created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"k_{i}", "POST", "/x", "", 200, "{}", now, exp),
        )
    db.conn.commit()
    n = store.cleanup_expired()
    db.conn.commit()
    assert n == 2
    rows = db.fetchall("SELECT * FROM idempotency_keys")
    assert len(rows) == 1
    assert rows[0]["idempotency_key"] == "k_2"


# ════════════════════════════════════════════════════════════════
# N3 接入: AI agent retry 防重复
# ════════════════════════════════════════════════════════════════


def test_ai_agent_can_use_idempotency(store: IdempotencyStore, db: Database):
    """3.0 AI agent 拟合同 timeout retry — 用 Idempotency-Key 防重复"""
    payload = {"title": "供应商合同", "supplier": "X 公司"}

    # 第一次 AI 调用
    cached_1 = store.find("ai_retry_key_001", "POST", "/api/v1/tasks", payload, **SCOPE_A)
    assert cached_1 is None
    claim_token = store.start(
        "ai_retry_key_001",
        "POST",
        "/api/v1/tasks",
        payload,
        **{**SCOPE_A, "actor_type": "ai_agent"},
    )
    # ... 假设业务逻辑创建了 task_xyz
    store.complete("ai_retry_key_001", "POST", "/api/v1/tasks",
                   status=201, response_body={"id": "task_xyz"},
                   claim_token=claim_token,
                   **{**SCOPE_A, "actor_type": "ai_agent"})
    db.conn.commit()

    # AI 因 timeout 触发 retry — 用同一 key
    cached_2 = store.find(
        "ai_retry_key_001",
        "POST",
        "/api/v1/tasks",
        payload,
        **{**SCOPE_A, "actor_type": "ai_agent"},
    )
    assert cached_2 is not None
    assert cached_2.actor_type == "ai_agent"
    body = json.loads(cached_2.response_body)
    assert body["id"] == "task_xyz"
    # ★ 关键: AI retry 拿到了同一个 task_xyz, 没有创建新的 task


def test_get_idempotency_store_factory(db: Database):
    """factory 函数可调用"""
    store = get_idempotency_store(db)
    assert isinstance(store, IdempotencyStore)


# ════════════════════════════════════════════════════════════════
# Body hash 健壮性
# ════════════════════════════════════════════════════════════════


def test_hash_body_none_returns_empty():
    assert _hash_body(None) == ""


def test_hash_body_dict_string_bytes_all_work():
    """支持 dict/str/bytes 多种 body 形态"""
    assert len(_hash_body({"a": 1})) == 64
    assert len(_hash_body("hello")) == 64
    assert len(_hash_body(b"hello")) == 64
    # str 跟 bytes 同内容 → 同 hash
    assert _hash_body("hello") == _hash_body(b"hello")
