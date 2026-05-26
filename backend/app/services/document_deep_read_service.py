"""数据中心第①层 · 文档深读地基统一服务 (M1/M2/M3 核心).

目标(见桌面 53/54-E): 让每份资料可靠完成 深读→要素提取→语义索引, 客户无关、可追踪、可重试、可自愈。
**不重造知识库**: 深读复用 knowledge_base.hydrate_missing_surrogates(建饱满 document surrogate)
+ reindex_client_vector(嵌入 Qdrant); 本服务只加"统一入口 + 状态表 + 队列/自愈"这层壳。

状态表: document_deep_read_states (db.py 已建)。
铁律: 客户无关, 无 `if client==X` 专属分支; 新增/未来文档由 enqueue + 自愈巡检自动覆盖。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.db import Database

# 总状态枚举
PENDING, RUNNING, SUCCESS, PARTIAL, FAILED, RETRY, DEAD_LETTER, SKIPPED, OUTDATED = (
    "pending", "running", "success", "partial_success", "failed",
    "retry_scheduled", "dead_letter", "skipped", "outdated",
)
STUCK_HOURS = 24
DEFAULT_MAX_RETRIES = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data_dir(db: Database) -> Path | None:
    raw = getattr(db, "db_path", None)
    return Path(raw).parent if raw else None


@dataclass
class DeepReadResult:
    document_id: str
    client_id: str
    status: str
    stages: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    surrogate_built: bool = False
    semantic_indexed: bool = False


# ---------------- 状态仓 (document_deep_read_states CRUD) ----------------

def get_state(db: Database, document_id: str, source_table: str = "v2_documents") -> dict | None:
    rows = db.fetchall(
        "SELECT * FROM document_deep_read_states WHERE document_source_table=? AND document_id=?",
        (source_table, document_id),
    )
    return dict(rows[0]) if rows else None


def enqueue_deep_read(
    db: Database, *, document_id: str, client_id: str, org_id: str = "",
    source_table: str = "v2_documents", priority: int = 1, reason: str = "",
    content_hash: str = "",
) -> str:
    """M3 原语: 把一份文档登记为待深读(幂等)。任何导入入口都只调这个, 不各写各的。"""
    existing = get_state(db, document_id, source_table)
    now = _now()
    if existing:
        # 内容变了 → 标 outdated 重排; 否则保持(不重复排队)
        if content_hash and content_hash != (existing.get("content_hash") or "") and existing.get("status") == SUCCESS:
            db.execute(
                "UPDATE document_deep_read_states SET status=?, content_hash=?, updated_at=? WHERE id=?",
                (OUTDATED, content_hash, now, existing["id"]),
            )
        return str(existing["id"])
    sid = f"ddr_{uuid.uuid4().hex[:16]}"
    db.execute(
        """INSERT INTO document_deep_read_states
           (id, org_id, client_id, document_id, document_source_table, content_hash,
            status, priority, max_retries, created_at, updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (sid, org_id, client_id, document_id, source_table, content_hash,
         PENDING, priority, DEFAULT_MAX_RETRIES, now, now),
    )
    return sid


def _set(db: Database, state_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE document_deep_read_states SET {cols} WHERE id=?", (*fields.values(), state_id))


def mark_running(db: Database, state_id: str, locked_by: str = "deep_read_worker") -> None:
    _set(db, state_id, status=RUNNING, locked_by=locked_by, locked_at=_now())


def mark_failed(db: Database, state_id: str, error: str, retry_count: int, max_retries: int) -> None:
    """失败 → 安排重试(指数退避), 超上限进 dead_letter。"""
    now = _now()
    if retry_count + 1 >= max_retries:
        _set(db, state_id, status=DEAD_LETTER, last_error=error[:500], last_error_at=now,
             retry_count=retry_count + 1, locked_by=None, locked_at=None)
    else:
        backoff_min = 2 ** retry_count  # 1,2,4...
        next_at = (datetime.now(timezone.utc) + timedelta(minutes=backoff_min)).isoformat()
        _set(db, state_id, status=RETRY, last_error=error[:500], last_error_at=now,
             retry_count=retry_count + 1, next_retry_at=next_at, locked_by=None, locked_at=None)


def reap_stuck(db: Database, stuck_hours: int = STUCK_HOURS) -> int:
    """M4 自愈: running 锁超时 → 放回 pending 等重跑。返回回收数。"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=stuck_hours)).isoformat()
    rows = db.fetchall(
        "SELECT id FROM document_deep_read_states WHERE status=? AND COALESCE(locked_at,'')<?",
        (RUNNING, cutoff),
    )
    for r in rows:
        _set(db, str(r[0]), status=PENDING, locked_by=None, locked_at=None)
    return len(rows)


def claim_next(db: Database, worker_id: str) -> dict | None:
    """M4: 取一条可处理的状态(pending / 到期 retry / outdated), 按优先级。并发安全靠 locked。"""
    now = _now()
    rows = db.fetchall(
        """SELECT * FROM document_deep_read_states
           WHERE (status IN (?,?) OR (status=? AND COALESCE(next_retry_at,'')<=?))
             AND COALESCE(locked_by,'')=''
           ORDER BY priority DESC, created_at ASC LIMIT 1""",
        (PENDING, OUTDATED, RETRY, now),
    )
    if not rows:
        return None
    st = dict(rows[0])
    mark_running(db, st["id"], worker_id)
    return st


# ---------------- 深读工作单元 (复用现有机制, 客户无关) ----------------

def deep_read_client(db: Database, *, client_id: str, ai_service: Any, force: bool = False,
                     data_dir: Path | None = None) -> dict:
    """客户级深读: 建饱满 document surrogate + 嵌入 Qdrant。复用现有 hydrate + reindex。
    ai_service 必须是真 LLM(qwen), 否则 surrogate 会退化为薄摘要(这正是历史薄索引的根因)。"""
    dd = data_dir or _data_dir(db)
    if dd is None:
        raise RuntimeError("data_dir 推导失败")
    from app.services.knowledge_base import hydrate_missing_surrogates, reindex_client_vector
    # 1) 富化: 为缺 surrogate / master_index 的文档建饱满 document surrogate (force=重读富化)
    hydrate_missing_surrogates(db, data_dir=dd, client_id=client_id, ai_service=ai_service, force_refresh=force)
    # 2) 嵌入 + 建向量索引 (M6 签名/collection 一致性在 reindex_client_vector 内保证)
    result = reindex_client_vector(db, data_dir=dd, client_id=client_id, ai_service=ai_service)
    sync_states_for_client(db, client_id=client_id)
    return result


def sync_states_for_client(db: Database, *, client_id: str) -> dict[str, int]:
    """把状态表跟"实际有没有 document surrogate"对齐(自愈/审计用)。客户无关逻辑。"""
    done = 0
    rows = db.fetchall(
        "SELECT id FROM v2_documents WHERE client_id=?", (client_id,))
    for r in rows:
        doc_id = str(r[0])
        has_doc_surr = db.fetchall(
            """SELECT 1 FROM knowledge_surrogates ks
               JOIN knowledge_documents kd ON kd.id=ks.knowledge_document_id
               WHERE ks.client_id=? AND ks.source_type='document'
                 AND kd.document_id=? LIMIT 1""",
            (client_id, doc_id),
        )
        sid = enqueue_deep_read(db, document_id=doc_id, client_id=client_id)
        if has_doc_surr:
            _set(db, sid, status=SUCCESS, surrogate_status=SUCCESS,
                 semantic_index_status=SUCCESS, last_processed_at=_now())
            done += 1
    return {"client_id": client_id, "synced": len(rows), "deep_read_done": done}


def coverage_for_client(db: Database, client_id: str) -> dict:
    """深读健康度(M7 基础): 覆盖率 + 状态分布。"""
    docs = db.fetchall("SELECT COUNT(*) FROM v2_documents WHERE client_id=?", (client_id,))[0][0]
    deep = db.fetchall(
        "SELECT COUNT(*) FROM knowledge_surrogates WHERE client_id=? AND source_type='document'",
        (client_id,))[0][0]
    return {
        "client_id": client_id, "documents": docs, "deep_read_done": deep,
        "deep_read_coverage": round(deep / docs, 3) if docs else 0.0,
        "reindex_required": bool(docs and deep == 0),
    }
