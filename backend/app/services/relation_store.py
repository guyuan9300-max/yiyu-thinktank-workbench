"""关系三元组存储层（迭代 5）。

封装 relationship_triples 表的读写。

实体映射策略：
- 入库前先把 subject_text / object_text 在 entities 表里 lookup
- 命中 → 写 entity_id；未命中 → 保留 object_text（subject 必须有 entity_id，
  否则跳过该条三元组——subject 没法挂在自由文本上）
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from app.services.relation_extractor import ExtractedRelation

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_entity_id(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    name: str,
) -> str | None:
    """按 client + normalized_name 查实体 id。找不到返回 None。"""
    row = conn.execute(
        "SELECT id FROM entities "
        "WHERE client_id = ? AND status = 'active' AND normalized_name = ? "
        "LIMIT 1",
        (client_id, name),
    ).fetchone()
    if row:
        return str(row["id"])
    # 兜底：按 display_name 查
    row = conn.execute(
        "SELECT id FROM entities "
        "WHERE client_id = ? AND status = 'active' AND display_name = ? "
        "LIMIT 1",
        (client_id, name),
    ).fetchone()
    return str(row["id"]) if row else None


def insert_triple(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    subject_entity_id: str,
    predicate: str,
    object_entity_id: str | None,
    object_text: str,
    confidence: float,
    source_v2_chunk_id: str | None,
    source_v2_document_id: str | None,
    evidence_text: str,
    now: str | None = None,
) -> str:
    """插入一条三元组。重复键不抛错——业务上允许同 subject/predicate/object
    多次出现（每次都是新证据）。"""
    timestamp = now or _now_iso()
    triple_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO relationship_triples (
            id, client_id, subject_entity_id, predicate, object_entity_id,
            object_text, confidence, source_v2_chunk_id, source_v2_document_id,
            evidence_text, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            triple_id,
            client_id,
            subject_entity_id,
            predicate,
            object_entity_id,
            object_text,
            confidence,
            source_v2_chunk_id,
            source_v2_document_id,
            evidence_text,
            timestamp,
            timestamp,
        ),
    )
    return triple_id


def persist_chunk_relations(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    v2_document_id: str,
    v2_chunk_id: str,
    extracted: list[ExtractedRelation],
    now: str | None = None,
) -> int:
    """一站式：把一个 chunk 抽出的三元组落库。返回成功插入数。

    subject 必须能在 entities 表里找到 → 找不到的三元组跳过。
    object 找不到 → object_entity_id=None，但保留 object_text。
    """
    timestamp = now or _now_iso()
    inserted = 0
    for rel in extracted:
        subject_id = _find_entity_id(conn, client_id=client_id, name=rel.subject_text)
        if not subject_id:
            # subject 未匹配实体——跳过（没有合适的挂载点）
            continue
        object_id = _find_entity_id(conn, client_id=client_id, name=rel.object_text)
        try:
            insert_triple(
                conn,
                client_id=client_id,
                subject_entity_id=subject_id,
                predicate=rel.predicate,
                object_entity_id=object_id,
                object_text=rel.object_text,
                confidence=rel.confidence,
                source_v2_chunk_id=v2_chunk_id,
                source_v2_document_id=v2_document_id,
                evidence_text=rel.evidence_text,
                now=timestamp,
            )
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "insert relation triple failed (client=%s, predicate=%s): %s",
                client_id,
                rel.predicate,
                exc,
            )
    return inserted


def list_triples(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    subject_entity_id: str | None = None,
    object_entity_id: str | None = None,
    predicate: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, object]], int]:
    """按 client + 可选 subject / object / predicate 查三元组。"""
    where = ["client_id = ?"]
    params: list[object] = [client_id]
    if subject_entity_id:
        where.append("subject_entity_id = ?")
        params.append(subject_entity_id)
    if object_entity_id:
        where.append("object_entity_id = ?")
        params.append(object_entity_id)
    if predicate:
        where.append("predicate = ?")
        params.append(predicate)
    where_clause = " AND ".join(where)

    count_row = conn.execute(
        f"SELECT COUNT(*) AS n FROM relationship_triples WHERE {where_clause}",
        tuple(params),
    ).fetchone()
    total = int(count_row["n"] or 0) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT rt.id, rt.client_id, rt.subject_entity_id, rt.predicate,
               rt.object_entity_id, rt.object_text, rt.confidence,
               rt.source_v2_chunk_id, rt.source_v2_document_id,
               rt.evidence_text, rt.created_at,
               es.display_name AS subject_display_name,
               eo.display_name AS object_display_name
        FROM relationship_triples rt
        LEFT JOIN entities es ON es.id = rt.subject_entity_id
        LEFT JOIN entities eo ON eo.id = rt.object_entity_id
        WHERE {where_clause}
        ORDER BY rt.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": str(r["id"]),
            "clientId": str(r["client_id"]),
            "subjectEntityId": str(r["subject_entity_id"]),
            "subjectDisplayName": str(r["subject_display_name"] or ""),
            "predicate": str(r["predicate"]),
            "objectEntityId": str(r["object_entity_id"] or "") or None,
            "objectDisplayName": str(r["object_display_name"] or "") or None,
            "objectText": str(r["object_text"] or ""),
            "confidence": float(r["confidence"] or 0.0),
            "sourceV2ChunkId": str(r["source_v2_chunk_id"] or "") or None,
            "sourceV2DocumentId": str(r["source_v2_document_id"] or "") or None,
            "evidenceText": str(r["evidence_text"] or ""),
            "createdAt": str(r["created_at"] or ""),
        })
    return out, total


__all__ = [
    "insert_triple",
    "list_triples",
    "persist_chunk_relations",
]
