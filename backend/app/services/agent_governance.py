"""[A] V2.5 R2-A · Agent Run Log + Approval Queue · 治理层

顾源源 5/23 钦定 (优先级 2):
> 从"AI 自动分析"走向"AI 操作软件"的安全底座.
> 必须有 Agent Run Log 100%, Approval Queue, Idempotency-Key.
> AI 不直接写权威 DB, 危险动作进 Approval Queue, 用户拍板才执行.

设计:
  · agent_run_log    — 每次 agent 调用一条, 含 run_id / actor_type / tool / input / output / status
  · approval_queue   — 危险动作 (任务发布 / 权威值变更 / 客户字典写入) 排队等用户审批
  · idempotency_key  — 同 key 重复跑不重复创建, 让 agent 安全 retry

actor_type:
  · internal_ai    — 益语内置驱动
  · external_agent — Codex/Claude/Cursor 等外置 Agent
  · user           — 用户直接操作
  · system         — 后台定时任务

approval_required_actions:
  · task.publish              — 任务发布 (不只是 draft)
  · authoritative_value.write — 权威值变更
  · client_glossary.update    — 客户字典写入
  · external_message.send     — 给客户发材料
  · permission.change         — 权限变更
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


ActorType = Literal["internal_ai", "external_agent", "user", "system"]
ApprovalAction = Literal[
    "task.publish", "authoritative_value.write",
    "client_glossary.update", "external_message.send", "permission.change",
]
ApprovalStatus = Literal["pending", "approved", "rejected", "auto_approved", "withdrawn"]


# ─── schema ensure ──────────────────────────────────


def ensure_governance_schema(db: _DbLike) -> None:
    """V2.5 R2-A: 建 agent_run_log + approval_queue + idempotency_keys 表."""
    schemas = [
        """CREATE TABLE IF NOT EXISTS agent_run_log (
            id TEXT PRIMARY KEY,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            client_id TEXT,
            tool_name TEXT NOT NULL,
            tool_version TEXT DEFAULT 'v1',
            input_json TEXT NOT NULL DEFAULT '{}',
            output_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'success',
            error_message TEXT,
            idempotency_key TEXT,
            duration_ms INTEGER,
            triggered_at TEXT NOT NULL,
            session_id TEXT
        )""",
        """CREATE INDEX IF NOT EXISTS idx_agent_run_log_client
           ON agent_run_log(client_id, triggered_at DESC)""",
        """CREATE INDEX IF NOT EXISTS idx_agent_run_log_idem
           ON agent_run_log(idempotency_key)""",
        """CREATE TABLE IF NOT EXISTS approval_queue (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            action_type TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            target_resource TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            decided_at TEXT,
            decided_by TEXT,
            decision_note TEXT,
            agent_run_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_approval_queue_client_status
           ON approval_queue(client_id, status, created_at DESC)""",
        """CREATE TABLE IF NOT EXISTS idempotency_keys_v25 (
            key TEXT PRIMARY KEY,
            agent_run_id TEXT,
            outcome_json TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT
        )""",
    ]
    for sql in schemas:
        try:
            db.execute(sql)
        except Exception as exc:
            logger.warning("ensure_governance_schema sql failed: %s", exc)


# ─── Agent Run Log ──────────────────────────────────


@dataclass(frozen=True)
class AgentRunRecord:
    run_id: str
    actor_type: ActorType
    actor_id: str
    client_id: str | None
    tool_name: str
    input_payload: dict = field(default_factory=dict)
    idempotency_key: str | None = None
    session_id: str | None = None


def log_agent_run_start(
    db: _DbLike, *,
    actor_type: ActorType, actor_id: str,
    tool_name: str, client_id: str | None = None,
    input_payload: dict | None = None,
    idempotency_key: str | None = None,
    session_id: str | None = None,
) -> str:
    """记录 agent 调用开始, 返回 run_id."""
    ensure_governance_schema(db)
    # idempotency 检查
    if idempotency_key:
        existing = db.fetchone(
            "SELECT id FROM agent_run_log WHERE idempotency_key = ? LIMIT 1",
            (idempotency_key,),
        )
        if existing:
            return dict(existing)["id"]

    run_id = f"run_{uuid.uuid4().hex[:24]}"
    now = _now_iso()
    db.execute(
        """INSERT INTO agent_run_log (
            id, actor_type, actor_id, client_id, tool_name, tool_version,
            input_json, output_json, status, idempotency_key, triggered_at, session_id
        ) VALUES (?, ?, ?, ?, ?, 'v1', ?, '{}', 'running', ?, ?, ?)""",
        (run_id, actor_type, actor_id, client_id, tool_name,
         json.dumps(input_payload or {}, ensure_ascii=False),
         idempotency_key, now, session_id),
    )
    return run_id


def log_agent_run_complete(
    db: _DbLike, run_id: str, *,
    output_payload: dict | None = None,
    status: str = "success",
    error_message: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """记录 agent 调用完成."""
    db.execute(
        """UPDATE agent_run_log
           SET output_json = ?, status = ?, error_message = ?, duration_ms = ?
           WHERE id = ?""",
        (json.dumps(output_payload or {}, ensure_ascii=False),
         status, error_message, duration_ms, run_id),
    )


def list_recent_agent_runs(
    db: _DbLike, *, client_id: str | None = None,
    actor_type: ActorType | None = None, limit: int = 50,
) -> list[dict]:
    """拉最近 agent 运行日志."""
    where = []
    params: list[Any] = []
    if client_id:
        where.append("client_id = ?")
        params.append(client_id)
    if actor_type:
        where.append("actor_type = ?")
        params.append(actor_type)
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.fetchall(
        f"SELECT * FROM agent_run_log {wsql} ORDER BY triggered_at DESC LIMIT ?",
        tuple(params + [limit]),
    )
    return [dict(r) for r in rows]


# ─── Approval Queue ──────────────────────────────────


@dataclass(frozen=True)
class ApprovalRequest:
    action_type: ApprovalAction
    actor_type: ActorType
    actor_id: str
    payload: dict
    reason: str
    client_id: str | None = None
    target_resource: str | None = None
    agent_run_id: str | None = None


def enqueue_approval(db: _DbLike, req: ApprovalRequest) -> str:
    """将危险动作入审批队列, 返回 approval_id."""
    ensure_governance_schema(db)
    aid = f"appr_{uuid.uuid4().hex[:24]}"
    now = _now_iso()
    db.execute(
        """INSERT INTO approval_queue (
            id, client_id, action_type, actor_type, actor_id,
            target_resource, payload_json, reason, status,
            agent_run_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
        (aid, req.client_id, req.action_type, req.actor_type, req.actor_id,
         req.target_resource,
         json.dumps(req.payload, ensure_ascii=False),
         req.reason, req.agent_run_id, now, now),
    )
    return aid


def list_pending_approvals(
    db: _DbLike, *, client_id: str | None = None, limit: int = 50,
) -> list[dict]:
    """拉 pending 审批."""
    ensure_governance_schema(db)
    where = ["status = 'pending'"]
    params: list[Any] = []
    if client_id:
        where.append("client_id = ?")
        params.append(client_id)
    rows = db.fetchall(
        f"SELECT * FROM approval_queue WHERE {' AND '.join(where)} "
        f"ORDER BY created_at DESC LIMIT ?",
        tuple(params + [limit]),
    )
    return [dict(r) for r in rows]


def decide_approval(
    db: _DbLike, approval_id: str, *,
    decision: Literal["approved", "rejected"],
    decided_by: str, decision_note: str = "",
) -> bool:
    """用户裁决审批. 返回是否成功."""
    try:
        db.execute(
            """UPDATE approval_queue
               SET status = ?, decided_at = ?, decided_by = ?,
                   decision_note = ?, updated_at = ?
               WHERE id = ? AND status = 'pending'""",
            (decision, _now_iso(), decided_by, decision_note, _now_iso(), approval_id),
        )
        return True
    except Exception as exc:
        logger.warning("decide_approval failed: %s", exc)
        return False


# ─── Idempotency ─────────────────────────────────────


def check_idempotency(db: _DbLike, key: str) -> dict | None:
    """检查 idempotency_key 是否已用过, 返回上次 outcome."""
    ensure_governance_schema(db)
    row = db.fetchone(
        "SELECT * FROM idempotency_keys_v25 WHERE key = ?", (key,),
    )
    if not row:
        return None
    d = dict(row)
    try:
        d["outcome"] = json.loads(d.get("outcome_json") or "{}")
    except Exception:
        d["outcome"] = {}
    return d


def record_idempotency(
    db: _DbLike, key: str, *, run_id: str, outcome: dict,
) -> None:
    """记录 idempotency 完成结果."""
    ensure_governance_schema(db)
    try:
        db.execute(
            """INSERT INTO idempotency_keys_v25 (key, agent_run_id, outcome_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (key, run_id, json.dumps(outcome, ensure_ascii=False), _now_iso()),
        )
    except Exception:
        # 已存在 → 忽略
        pass


# ─── 统计/验收用 ────────────────────────────────────


def get_governance_stats(db: _DbLike, client_id: str | None = None) -> dict:
    """治理层统计 (R2 硬门槛验收用)."""
    ensure_governance_schema(db)
    where = ""
    params: tuple = ()
    if client_id:
        where = "WHERE client_id = ?"
        params = (client_id,)
    total_runs = db.fetchone(
        f"SELECT COUNT(*) AS c FROM agent_run_log {where}", params,
    )
    by_actor = db.fetchall(
        f"SELECT actor_type, COUNT(*) AS c FROM agent_run_log {where} "
        f"GROUP BY actor_type", params,
    )
    pending_approvals = db.fetchone(
        f"SELECT COUNT(*) AS c FROM approval_queue "
        f"{'WHERE client_id = ? AND ' if client_id else 'WHERE '} status = 'pending'",
        params,
    )
    return {
        "total_runs": dict(total_runs)["c"] if total_runs else 0,
        "by_actor_type": {dict(r)["actor_type"]: dict(r)["c"] for r in by_actor},
        "pending_approvals": dict(pending_approvals)["c"] if pending_approvals else 0,
    }
