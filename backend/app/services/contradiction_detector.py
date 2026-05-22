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
    """插入或返回已有原子事实，返回 fact id。

    Dedup 键：(client_id, subject_text, attribute, value_normalized, status='active')
    同一个事实从多个 chunk 提及不应当产生 N 条重复 fact——否则矛盾检测
    会对每对组合都触发，产生 N×N 个冗余告警。

    V2.3 阶段 2 M-D2.1 接通 (顾源源 5/22 钦定):
      · 旧路径保持工作 (向后兼容)
      · 新加: 自动 register_source 拿 source_id + 写 atomic_facts.source_registry_id
      · 失败时跳过 (旧路径正常)
    """
    timestamp = now or _now_iso()
    # 先查是否已存在相同的 active fact
    existing = conn.execute(
        """
        SELECT id FROM atomic_facts
        WHERE client_id = ?
          AND subject_text = ?
          AND attribute = ?
          AND value_normalized = ?
          AND status = 'active'
        LIMIT 1
        """,
        (client_id, fact.subject_text, fact.attribute, fact.value_normalized),
    ).fetchone()
    if existing:
        # 已存在 → 更新 updated_at（保留最近一次见到的时间）+ 返回旧 id
        conn.execute(
            "UPDATE atomic_facts SET updated_at = ? WHERE id = ?",
            (timestamp, str(existing["id"])),
        )
        return str(existing["id"])

    fact_id = str(uuid.uuid4())

    # ★ V2.3 阶段 2 M-D2.1 接 source_registry (向后兼容: 失败跳过, 主 INSERT 仍跑)
    source_registry_id: str | None = None
    try:
        # 用 _SqliteAdapter 把 sqlite3.Connection 包装成 _DbLike 接口
        from app.services.source_registry_store import register_source, ensure_schema
        from app.services.atomic_fact_confidence_history import (
            ensure_schema as ensure_ch,
            record_confidence_change,
        )

        class _SqliteAdapter:
            def __init__(self, c): self._c = c
            def execute(self, sql, params=()): return self._c.execute(sql, params)
            def fetchone(self, sql, params=()): return self._c.execute(sql, params).fetchone()
            def fetchall(self, sql, params=()): return self._c.execute(sql, params).fetchall()

        adapter = _SqliteAdapter(conn)
        ensure_schema(adapter)
        ensure_ch(adapter)
        # atomic_facts 加列 (idempotent)
        try:
            conn.execute("ALTER TABLE atomic_facts ADD COLUMN source_registry_id TEXT")
        except Exception:
            pass

        source_registry_id = register_source(
            adapter,
            source_type="llm_extracted",
            source_channel="document_llm_extractor",  # contradiction_detector 通常被 fact_extractor 调
            source_owner="contradiction_detector",
            client_id=client_id,
            content=f"{fact.subject_text}|{fact.attribute}|{fact.value_text}",
            source_role="ai_derived",
            raw_reference=source_v2_document_id or source_v2_chunk_id,
            strict_4_required=False,  # contradiction_detector 兼容旧调用
        )
    except Exception as exc:
        logger.warning("contradiction_detector V2.3 register_source 失败: %s", exc)

    conn.execute(
        """
        INSERT INTO atomic_facts (
            id, client_id, subject_entity_id, subject_text, attribute,
            value_text, value_normalized, confidence,
            source_v2_chunk_id, source_v2_document_id, evidence_text,
            status, created_at, updated_at, source_registry_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
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
            source_registry_id,  # V2.3 阶段 2 M-D2.1
        ),
    )

    # V2.3 阶段 2 M-D2.1 · 写 confidence_history initial_extract
    if source_registry_id:
        try:
            adapter = _SqliteAdapter(conn)
            record_confidence_change(
                adapter, fact_id=fact_id, new_confidence=fact.confidence,
                trigger_event="initial_extract",
                evidence_link=source_registry_id,
                actor_id="contradiction_detector",
                reasoning_note=f"insert_fact via contradiction_detector",
            )
        except Exception as exc:
            logger.warning("contradiction_detector confidence_history 失败: %s", exc)

    return fact_id


def find_contradictions_for_fact(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    fact: AtomicFact,
    exclude_fact_id: str | None = None,
    exclude_v2_document_id: str | None = None,
) -> list[dict[str, object]]:
    """找与给定事实（同 subject+attribute、value 不同）冲突的既有事实。

    P1: exclude_v2_document_id — 同文档内的"冲突"通常是 regex 在同句子不同
    截断版本，不是真矛盾，自动排除。
    """
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
          AND (? = '' OR COALESCE(source_v2_document_id, '') != ?)
        """,
        (
            client_id,
            fact.subject_text,
            fact.attribute,
            fact.value_normalized,
            exclude_fact_id or "",
            exclude_v2_document_id or "",
            exclude_v2_document_id or "",
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
    source_v2_document_id: str | None = None,
) -> list[str]:
    """对一条新插入的事实，检测矛盾并写入 fact_contradictions。

    返回新创建的 contradiction id 列表。
    """
    from app.services.text_normalizer import is_noise_difference
    from app.services.glossary_conflict_alert import check_fact_against_glossary

    # Codex 方案 A · 强提示: 新事实 vs 字典 verified 立刻报警 (不等用户事后发现)
    try:
        check_fact_against_glossary(
            conn,
            client_id=client_id,
            new_fact_id=new_fact_id,
            subject_text=fact.subject_text,
            attribute=fact.attribute,
            value_text=fact.value_text,
        )
    except Exception as exc:  # noqa: BLE001
        # 报警失败不阻塞主流程
        import logging
        logging.getLogger(__name__).warning(
            "[glossary-drift] check failed for fact=%s: %s", new_fact_id, exc
        )

    conflicting = find_contradictions_for_fact(
        conn,
        client_id=client_id,
        fact=fact,
        exclude_fact_id=new_fact_id,
        exclude_v2_document_id=source_v2_document_id,
    )
    created: list[str] = []
    for other in conflicting:
        # Codex 实测发现的 OCR 噪声过滤: ^A / 繁简 / 标点差异不算真冲突
        # 例: "明天的青年" vs "明天的青年\"" 只是引号差异 / "广州" vs "⼴州" 是 OCR 字宽差异
        other_value = str(other.get("value_text") or other.get("value_normalized") or "")
        if is_noise_difference(fact.value_text, other_value):
            continue
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
                source_v2_document_id=v2_document_id,  # P1: 同文档自冲突自动排除
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
