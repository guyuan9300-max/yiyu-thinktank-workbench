"""v2.2 F2.8 (N3 A6) · IdempotencyStore — 防 AI retry 时重复创建

服务: V2.2_NORTH_STAR.md
- N3 接入预留: 3.0 AI agent 会频繁 retry, 没有幂等保护会污染数据库 (重复任务/重复事实)
- 设计参考: Stripe API Idempotency-Key 规范

用法 (endpoint 按需接入):

    @app.post("/api/v1/tasks")
    async def create_task(payload: TaskPayload, request: Request):
        store = IdempotencyStore(state.db)
        # 检查 Idempotency-Key
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            cached = store.find(idempotency_key, "POST", "/api/v1/tasks", payload_dict)
            if cached:
                return JSONResponse(
                    status_code=cached.response_status,
                    content=json.loads(cached.response_body),
                )
            # 记录开始处理
            store.start(idempotency_key, "POST", "/api/v1/tasks", payload_dict,
                        actor_type="human", actor_id=user_id)
        # ... 正常处理逻辑
        result = create_task_internal(...)
        # 记录完成
        if idempotency_key:
            store.complete(idempotency_key, "POST", "/api/v1/tasks",
                           status=200, response_body=result.dict())
        return result

为什么不做全局 middleware (v2.2 阶段):
- streaming response (chat 接口) 跟 idempotency 缓存冲突
- 不是所有 endpoint 需要幂等 (GET 天然幂等)
- middleware 全局拦截要读 request.body, 跟 FastAPI 的请求 body 消费机制冲突
- 渐进改造让 endpoint 自己决定何时幂等 (创建型 endpoint 必接, 更新型可选)
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


# 24 小时窗口 (Stripe 标准)
DEFAULT_TTL_HOURS = 24


class _DbLike(Protocol):
    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]: ...
    def execute(self, query: str, params: tuple = ()) -> None: ...


@dataclass(frozen=True)
class CachedResponse:
    """命中的幂等缓存"""
    idempotency_key: str
    request_method: str
    request_path: str
    response_status: int
    response_body: str            # JSON 字符串
    actor_type: str
    actor_id: str
    created_at: str
    expires_at: str
    status: str                   # in_progress / completed / failed


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expires_at(ttl_hours: int = DEFAULT_TTL_HOURS) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()


def _hash_body(payload: dict[str, Any] | str | bytes | None) -> str:
    """规范化请求体 + sha256, 用于检测同 key 但不同 body 的攻击"""
    if payload is None:
        return ""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        # 字典: 用稳定 json 序列化 (sort_keys 保证同样内容生成同 hash)
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class IdempotencyKeyMismatchError(Exception):
    """同 idempotency_key 但 body 不同 — 客户端 bug 或被攻击, 必须拒绝"""

    def __init__(self, key: str, method: str, path: str):
        super().__init__(
            f"Idempotency-Key '{key}' was previously used with a different request body "
            f"for {method} {path}. Refusing to replay."
        )


class IdempotencyStore:
    """跟 Stripe Idempotency-Key 兼容的 store。

    流程 (endpoint 视角):
    1. 客户端发请求带 Idempotency-Key header
    2. find() → 命中且 status=completed → 直接返回缓存
    3. find() → 命中且 status=in_progress → 返回 409 让客户端等
    4. find() → 不命中 → start() 标记开始处理 → 正常业务 → complete() 写结果
    """

    def __init__(self, db: _DbLike):
        self._db = db

    def find(
        self,
        idempotency_key: str,
        method: str,
        path: str,
        payload: dict[str, Any] | str | bytes | None = None,
    ) -> CachedResponse | None:
        """查找缓存。如果同 key 但 body 不同 → 抛 IdempotencyKeyMismatchError。

        返回 None: 表示这是首次请求, 调用方应该 start() + 正常处理 + complete()
        """
        if not idempotency_key:
            return None
        row = self._db.fetchone(
            """
            SELECT idempotency_key, request_method, request_path, request_body_hash,
                   response_status, response_body, actor_type, actor_id,
                   created_at, expires_at, status
            FROM idempotency_keys
            WHERE idempotency_key = ? AND request_method = ? AND request_path = ?
            """,
            (idempotency_key, method, path),
        )
        if not row:
            return None

        # 检查过期
        if str(row["expires_at"]) < _now_iso():
            # 过期 → 当作不存在 (cleanup 之后会清掉)
            return None

        # 检查 body hash 一致性
        if payload is not None:
            new_hash = _hash_body(payload)
            old_hash = str(row["request_body_hash"] or "")
            if old_hash and new_hash != old_hash:
                raise IdempotencyKeyMismatchError(idempotency_key, method, path)

        return CachedResponse(
            idempotency_key=str(row["idempotency_key"]),
            request_method=str(row["request_method"]),
            request_path=str(row["request_path"]),
            response_status=int(row["response_status"]),
            response_body=str(row["response_body"] or ""),
            actor_type=str(row["actor_type"]),
            actor_id=str(row["actor_id"]),
            created_at=str(row["created_at"]),
            expires_at=str(row["expires_at"]),
            status=str(row["status"]),
        )

    def start(
        self,
        idempotency_key: str,
        method: str,
        path: str,
        payload: dict[str, Any] | str | bytes | None = None,
        *,
        actor_type: str = "human",
        actor_id: str = "",
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> None:
        """标记一次幂等请求开始处理。如果 key 已存在 (UNIQUE), 抛错。"""
        body_hash = _hash_body(payload)
        self._db.execute(
            """
            INSERT INTO idempotency_keys (
                idempotency_key, request_method, request_path,
                request_body_hash,
                response_status, response_body,
                actor_type, actor_id,
                created_at, expires_at, status
            ) VALUES (?, ?, ?, ?, 0, '', ?, ?, ?, ?, 'in_progress')
            """,
            (
                idempotency_key, method, path, body_hash,
                actor_type, actor_id,
                _now_iso(), _expires_at(ttl_hours),
            ),
        )

    def complete(
        self,
        idempotency_key: str,
        method: str,
        path: str,
        *,
        status: int,
        response_body: dict[str, Any] | str,
    ) -> None:
        """标记成功, 缓存 response body 供后续 retry 复用。"""
        if isinstance(response_body, dict):
            body_str = json.dumps(response_body, ensure_ascii=False)
        else:
            body_str = response_body
        self._db.execute(
            """
            UPDATE idempotency_keys
            SET response_status = ?, response_body = ?, status = 'completed'
            WHERE idempotency_key = ? AND request_method = ? AND request_path = ?
            """,
            (status, body_str, idempotency_key, method, path),
        )

    def mark_failed(
        self,
        idempotency_key: str,
        method: str,
        path: str,
    ) -> None:
        """标记失败 — 后续 retry 应该当作新请求, 不复用这条 (3.0 AI agent retry 容错)"""
        self._db.execute(
            """
            UPDATE idempotency_keys
            SET status = 'failed'
            WHERE idempotency_key = ? AND request_method = ? AND request_path = ?
            """,
            (idempotency_key, method, path),
        )

    def cleanup_expired(self) -> int:
        """清理过期记录 (定期跑, 不影响业务)。返回清理条数。

        N3 设计选择: failed 状态的也清掉 (失败不缓存, retry 当新请求)
        """
        row = self._db.fetchone(
            "SELECT COUNT(*) AS n FROM idempotency_keys WHERE expires_at < ?",
            (_now_iso(),),
        )
        n = int(row["n"]) if row else 0
        self._db.execute(
            "DELETE FROM idempotency_keys WHERE expires_at < ?",
            (_now_iso(),),
        )
        return n


def get_idempotency_store(db: _DbLike) -> IdempotencyStore:
    return IdempotencyStore(db)
