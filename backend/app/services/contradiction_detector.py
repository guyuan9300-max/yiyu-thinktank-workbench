"""矛盾检测 + 事实存储（迭代 6）。

当一条新事实写入 atomic_facts 时：
1. 查同 client + 同 (subject, attribute) 的既有 active 事实
2. 如果新值 value_normalized 与既有值不同 → 触发矛盾告警
3. 写入 fact_contradictions 表，severity 按值差异判定

review_status:
- pending：新检测的，待用户审阅
- dismissed：用户已忽略
- resolved：用户已确认正确版本（通常意味着把对方设为 superseded）
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from app.services.fact_extractor import AtomicFact

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _judge_severity(value_a: str, value_b: str, attribute: str) -> str:
    """简单的 severity 判定：金额/预算类的差异更严重。"""
    if attribute in {"预算", "预算额", "金额", "营收", "成本", "工资", "薪资"}:
        return "high"
    if attribute in {"计划时间", "上线时间", "截止时间", "完成时间"}:
        return "high"
    if attribute in {"位置", "总部", "负责人"}:
        return "medium"
    return "medium"


def insert_fact(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    fact: AtomicFact,
    subject_entity_id: str | None = None,
    source_v2_chunk_id: str | None = None,
    source_v2_document_id: str | None = None,
    now: str | None = None,
) -> str:
    """插入一条原子事实，返回 fact id。"""
    timestamp = now or _now_iso()
    fact_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO atomic_facts (
            id, client_id, subject_entity_id, subject_text, attribute,
            value_text, value_normalized, confidence,
            source_v2_chunk_id, source_v2_document_id, evidence_text,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """,
        (
            fact_id,
            client_id,
            subject_entity_id,
            fact.subject_text,
            fact.attribute,
            fact.value_text,
            fact.value_normalized,
            fact.confidence,
            source_v2_chunk_id,
            source_v2_document_id,
            fact.evidence_text,
            timestamp,
            timestamp,
        ),
    )
    return fact_id


def find_contradictions_for_fact(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    fact: AtomicFact,
    exclude_fact_id: str | None = None,
) -> list[dict[str, object]]:
    """找与给定事实（同 subject+attribute、value 不同）冲突的既有事实。"""
    rows = conn.execute(
        """
        SELECT id, value_text, value_normalized, confidence, source_v2_chunk_id,
               source_v2_document_id, evidence_text, created_at
        FROM atomic_facts
        WHERE client_id = ?
          AND status = 'active'
          AND subject_text = ?
          AND attribute = ?
          AND value_normalized != ?
          AND id != ?
        """,
        (
            client_id,
            fact.subject_text,
            fact.attribute,
            fact.value_normalized,
            exclude_fact_id or "",
        ),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_contradiction(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    fact_a_id: str,
    fact_b_id: str,
    contradiction_type: str = "value_diff",
    severity: str = "medium",
    now: str | None = None,
) -> str | None:
    """插入一条矛盾记录。UNIQUE 索引保证同对 (a, b) 不重复。

    返回 contradiction id；如果是重复直接返回 None。
    """
    timestamp = now or _now_iso()
    cid = str(uuid.uuid4())
    try:
        conn.execute(
            """
            INSERT INTO fact_contradictions (
                id, client_id, fact_a_id, fact_b_id, contradiction_type,
                severity, review_status, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (cid, client_id, fact_a_id, fact_b_id, contradiction_type, severity, timestamp),
        )
        return cid
    except sqlite3.IntegrityError:
        # UNIQUE 冲突 → 已存在
        return None


def detect_and_record_for_fact(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    new_fact_id: str,
    fact: AtomicFact,
    now: str | None = None,
) -> list[str]:
    """对一条新插入的事实，检测矛盾并写入 fact_contradictions。

    返回新创建的 contradiction id 列表。
    """
    conflicting = find_contradictions_for_fact(
        conn,
        client_id=client_id,
        fact=fact,
        exclude_fact_id=new_fact_id,
    )
    created: list[str] = []
    for other in conflicting:
        severity = _judge_severity(
            fact.value_normalized,
            str(other["value_normalized"]),
            fact.attribute,
        )
        cid = insert_contradiction(
            conn,
            client_id=client_id,
            fact_a_id=new_fact_id,
            fact_b_id=str(other["id"]),
            contradiction_type="value_diff",
            severity=severity,
            now=now,
        )
        if cid:
            created.append(cid)
    return created


def persist_chunk_facts(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    v2_document_id: str,
    v2_chunk_id: str,
    facts: list[AtomicFact],
    now: str | None = None,
) -> tuple[int, int]:
    """一站式：把一个 chunk 抽出的事实落库 + 检测矛盾。

    Returns:
        (facts_inserted, contradictions_detected)
    """
    timestamp = now or _now_iso()
    inserted = 0
    contradictions = 0
    for fact in facts:
        try:
            fact_id = insert_fact(
                conn,
                client_id=client_id,
                fact=fact,
                source_v2_chunk_id=v2_chunk_id,
                source_v2_document_id=v2_document_id,
                now=timestamp,
            )
            inserted += 1
            new_contras = detect_and_record_for_fact(
                conn,
                client_id=client_id,
                new_fact_id=fact_id,
                fact=fact,
                now=timestamp,
            )
            contradictions += len(new_contras)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "persist atomic fact failed (client=%s, subject=%s, attr=%s): %s",
                client_id,
                fact.subject_text,
                fact.attribute,
                exc,
            )
    return inserted, contradictions


def list_contradictions(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    review_status: str = "pending",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, object]], int]:
    """查询客户的矛盾列表（默认 pending）。

    JOIN v2_documents + documents 拿出每条事实来源的**文件名、原路径、
    导入时间**——前端用这些渲染"哪两份文件冲突了"。
    """
    count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM fact_contradictions "
        "WHERE client_id = ? AND review_status = ?",
        (client_id, review_status),
    ).fetchone()
    total = int(count_row["n"] or 0) if count_row else 0

    rows = conn.execute(
        """
        SELECT fc.id, fc.contradiction_type, fc.severity, fc.review_status,
               fc.detected_at, fc.resolution_note,
               fa.subject_text AS subject_text, fa.attribute AS attribute,
               fa.value_text AS value_a, fa.evidence_text AS evidence_a,
               fa.created_at AS fact_a_at,
               fb.value_text AS value_b, fb.evidence_text AS evidence_b,
               fb.created_at AS fact_b_at,
               fc.fact_a_id, fc.fact_b_id,
               -- 来源文件 A
               vda.file_name AS doc_a_file_name,
               vda.id AS doc_a_v2_id,
               da.title AS doc_a_title,
               da.path AS doc_a_path,
               da.original_source_path AS doc_a_original_path,
               da.created_at AS doc_a_imported_at,
               -- 来源文件 B
               vdb.file_name AS doc_b_file_name,
               vdb.id AS doc_b_v2_id,
               db.title AS doc_b_title,
               db.path AS doc_b_path,
               db.original_source_path AS doc_b_original_path,
               db.created_at AS doc_b_imported_at
        FROM fact_contradictions fc
        JOIN atomic_facts fa ON fa.id = fc.fact_a_id
        JOIN atomic_facts fb ON fb.id = fc.fact_b_id
        LEFT JOIN v2_documents vda ON vda.id = fa.source_v2_document_id
        LEFT JOIN documents da ON da.id = vda.document_id
        LEFT JOIN v2_documents vdb ON vdb.id = fb.source_v2_document_id
        LEFT JOIN documents db ON db.id = vdb.document_id
        WHERE fc.client_id = ? AND fc.review_status = ?
        ORDER BY fc.detected_at DESC
        LIMIT ? OFFSET ?
        """,
        (client_id, review_status, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows], total


def update_review_status(
    conn: sqlite3.Connection,
    *,
    contradiction_id: str,
    review_status: str,
    accepted_fact_id: str | None = None,
    resolution_note: str | None = None,
    reviewed_by: str | None = None,
) -> None:
    """用户审阅一条矛盾。

    - review_status='resolved' + accepted_fact_id：采纳某一份事实，另一份
      自动归档（atomic_facts.status='superseded'），未来 RAG 不再用旧值
    - review_status='dismissed'：视为误报或暂时忽略，不改 facts 状态
    """
    timestamp = _now_iso()
    if review_status == "resolved" and accepted_fact_id:
        # 找到这条矛盾涉及的两条事实
        row = conn.execute(
            "SELECT fact_a_id, fact_b_id FROM fact_contradictions WHERE id = ?",
            (contradiction_id,),
        ).fetchone()
        if row:
            fact_a_id = str(row["fact_a_id"])
            fact_b_id = str(row["fact_b_id"])
            # 验证 accepted_fact_id 是这两个之一
            if accepted_fact_id in {fact_a_id, fact_b_id}:
                losing_id = fact_b_id if accepted_fact_id == fact_a_id else fact_a_id
                # 失败方归档
                conn.execute(
                    "UPDATE atomic_facts SET status = 'superseded', updated_at = ? WHERE id = ?",
                    (timestamp, losing_id),
                )
                # 胜出方保证 active
                conn.execute(
                    "UPDATE atomic_facts SET status = 'active', updated_at = ? WHERE id = ?",
                    (timestamp, accepted_fact_id),
                )
    conn.execute(
        """
        UPDATE fact_contradictions
        SET review_status = ?, resolution_note = ?, reviewed_at = ?, reviewed_by = ?
        WHERE id = ?
        """,
        (review_status, resolution_note, timestamp, reviewed_by, contradiction_id),
    )


__all__ = [
    "detect_and_record_for_fact",
    "find_contradictions_for_fact",
    "insert_contradiction",
    "insert_fact",
    "list_contradictions",
    "persist_chunk_facts",
    "update_review_status",
]
