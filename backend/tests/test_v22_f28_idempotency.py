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
        "actor_type", "actor_id",
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


# ════════════════════════════════════════════════════════════════
# IdempotencyStore 基本流程
# ════════════════════════════════════════════════════════════════


def test_find_returns_none_for_new_key(store: IdempotencyStore):
    """首次请求 → 不命中"""
    result = store.find("never_seen_key", "POST", "/api/v1/tasks")
    assert result is None


def test_empty_key_returns_none(store: IdempotencyStore):
    """空 key (客户端没传 header) → 不查"""
    result = store.find("", "POST", "/api/v1/tasks")
    assert result is None


def test_full_lifecycle_start_then_complete(store: IdempotencyStore, db: Database):
    """完整流程: start → complete → 再 find 命中"""
    payload = {"title": "拟合同", "owner": "管理员甲"}

    # 1. 首次 find 不命中
    assert store.find("k_001", "POST", "/api/v1/tasks", payload) is None

    # 2. start: 标记开始处理
    store.start("k_001", "POST", "/api/v1/tasks", payload,
                actor_type="human", actor_id="user_example_user")
    db.conn.commit()

    # 3. find 命中, status=in_progress
    cached = store.find("k_001", "POST", "/api/v1/tasks", payload)
    assert cached is not None
    assert cached.status == "in_progress"
    assert cached.actor_type == "human"
    assert cached.actor_id == "user_example_user"

    # 4. complete: 写入结果
    store.complete("k_001", "POST", "/api/v1/tasks",
                   status=201, response_body={"id": "task_abc", "title": "拟合同"})
    db.conn.commit()

    # 5. 再 find: status=completed + response 缓存
    cached = store.find("k_001", "POST", "/api/v1/tasks", payload)
    assert cached.status == "completed"
    assert cached.response_status == 201
    body = json.loads(cached.response_body)
    assert body["id"] == "task_abc"


def test_body_hash_mismatch_raises(store: IdempotencyStore, db: Database):
    """★ 同 key 但 body 不同 → 抛 IdempotencyKeyMismatchError

    防御场景: 客户端 bug / 攻击, 用同 Idempotency-Key 但改了 payload
    """
    store.start("k_002", "POST", "/api/v1/tasks",
                {"title": "原标题"})
    db.conn.commit()
    # 用不同 body 查
    with pytest.raises(IdempotencyKeyMismatchError) as exc_info:
        store.find("k_002", "POST", "/api/v1/tasks",
                   {"title": "篡改后的标题"})
    assert "k_002" in str(exc_info.value)
    assert "different request body" in str(exc_info.value)


def test_same_body_hash_no_raise(store: IdempotencyStore, db: Database):
    """同 key + 同 body → 命中, 不抛"""
    payload = {"title": "拟合同"}
    store.start("k_003", "POST", "/api/v1/tasks", payload)
    db.conn.commit()
    cached = store.find("k_003", "POST", "/api/v1/tasks", payload)
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
    result = store.find("k_expired", "POST", "/api/v1/x")
    assert result is None


def test_mark_failed(store: IdempotencyStore, db: Database):
    """failed 状态: retry 当新请求, 不复用"""
    store.start("k_fail", "POST", "/api/v1/x")
    db.conn.commit()
    store.mark_failed("k_fail", "POST", "/api/v1/x")
    db.conn.commit()
    row = db.fetchone(
        "SELECT status FROM idempotency_keys WHERE idempotency_key = 'k_fail'"
    )
    assert row["status"] == "failed"


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
    cached_1 = store.find("ai_retry_key_001", "POST", "/api/v1/tasks", payload)
    assert cached_1 is None
    store.start("ai_retry_key_001", "POST", "/api/v1/tasks", payload,
                actor_type="ai_agent", actor_id="ai_sess_001")
    # ... 假设业务逻辑创建了 task_xyz
    store.complete("ai_retry_key_001", "POST", "/api/v1/tasks",
                   status=201, response_body={"id": "task_xyz"})
    db.conn.commit()

    # AI 因 timeout 触发 retry — 用同一 key
    cached_2 = store.find("ai_retry_key_001", "POST", "/api/v1/tasks", payload)
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
