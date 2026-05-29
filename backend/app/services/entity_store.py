"""实体存储层（迭代 2）。

封装 entities / entity_mentions 两张表的读写。所有写操作幂等——同
(client_id, entity_type, normalized_name) 二次 upsert 只增 mention_count
不创建新行。
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.entity_extractor import ExtractedEntity

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EntityRow:
    """从 entities 表 SELECT 出的一行（只读视图）。"""

    id: str
    client_id: str
    entity_type: str
    normalized_name: str
    display_name: str
    aliases: list[str]
    attributes: dict[str, object]
    mention_count: int
    confidence: float
    first_seen_at: str
    last_seen_at: str
    status: str
    created_at: str
    updated_at: str


def _row_to_entity(row: sqlite3.Row) -> EntityRow:
    return EntityRow(
        id=str(row["id"]),
        client_id=str(row["client_id"]),
        entity_type=str(row["entity_type"]),
        normalized_name=str(row["normalized_name"]),
        display_name=str(row["display_name"]),
        aliases=json.loads(row["aliases_json"] or "[]"),
        attributes=json.loads(row["attributes_json"] or "{}"),
        mention_count=int(row["mention_count"] or 0),
        confidence=float(row["confidence"] or 0.0),
        first_seen_at=str(row["first_seen_at"] or ""),
        last_seen_at=str(row["last_seen_at"] or ""),
        status=str(row["status"] or "active"),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


def upsert_entity(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    entity: ExtractedEntity,
    now: str | None = None,
) -> str:
    """插入或更新实体，返回 entity id。

    重复键 (client_id, entity_type, normalized_name)：
    - mention_count += 1
    - last_seen_at = now
    - confidence 用滚动平均（保守起见）
    - aliases 若 display_name 不在 aliases 中则追加
    """
    timestamp = now or _now_iso()
    cur = conn.execute(
        "SELECT id, aliases_json, mention_count, confidence "
        "FROM entities "
        "WHERE client_id = ? AND entity_type = ? AND normalized_name = ?",
        (client_id, entity.entity_type, entity.normalized_name),
    )
    existing = cur.fetchone()

    if existing is None:
        entity_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO entities (id, client_id, entity_type, normalized_name, "
            "display_name, aliases_json, attributes_json, mention_count, confidence, "
            "first_seen_at, last_seen_at, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'active', ?, ?)",
            (
                entity_id,
                client_id,
                entity.entity_type,
                entity.normalized_name,
                entity.display_name,
                json.dumps([entity.display_name], ensure_ascii=False),
                json.dumps(entity.attributes, ensure_ascii=False),
                entity.confidence,
                timestamp,
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        return entity_id

    entity_id = str(existing["id"])
    current_aliases = json.loads(existing["aliases_json"] or "[]")
    if entity.display_name not in current_aliases:
        current_aliases.append(entity.display_name)
    current_count = int(existing["mention_count"] or 0)
    current_conf = float(existing["confidence"] or 0.0)
    new_count = current_count + 1
    rolling_conf = (current_conf * current_count + entity.confidence) / new_count
    conn.execute(
        "UPDATE entities "
        "SET mention_count = ?, confidence = ?, aliases_json = ?, "
        "    last_seen_at = ?, updated_at = ? "
        "WHERE id = ?",
        (
            new_count,
            rolling_conf,
            json.dumps(current_aliases, ensure_ascii=False),
            timestamp,
            timestamp,
            entity_id,
        ),
    )
    return entity_id


def insert_mention(
    conn: sqlite3.Connection,
    *,
    entity_id: str,
    v2_document_id: str,
    v2_chunk_id: str | None,
    entity: ExtractedEntity,
    now: str | None = None,
) -> str:
    """记录一次实体提及。"""
    mention_id = str(uuid.uuid4())
    timestamp = now or _now_iso()
    conn.execute(
        "INSERT INTO entity_mentions (id, entity_id, v2_document_id, v2_chunk_id, "
        "mention_text, position_start, position_end, confidence, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            mention_id,
            entity_id,
            v2_document_id,
            v2_chunk_id,
            entity.text,
            entity.position_start,
            entity.position_end,
            entity.confidence,
            timestamp,
        ),
    )
    return mention_id


def update_chunk_entity_ids(
    conn: sqlite3.Connection,
    chunk_id: str,
    entity_ids: list[str],
) -> None:
    """把 chunk 关联的 entity_ids 写到 v2_chunks.entity_ids_json。"""
    conn.execute(
        "UPDATE v2_chunks SET entity_ids_json = ? WHERE id = ?",
        (json.dumps(entity_ids, ensure_ascii=False), chunk_id),
    )


def persist_chunk_entities(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    v2_document_id: str,
    v2_chunk_id: str,
    extracted: list[ExtractedEntity],
    now: str | None = None,
) -> list[str]:
    """一站式：把一个 chunk 抽出的所有实体落库 + 更新 v2_chunks.entity_ids_json。

    返回该 chunk 关联的 entity_ids 列表。失败时部分写入也无妨——upsert
    是幂等的，下次 backfill 会修补。
    """
    entity_ids: list[str] = []
    for entity in extracted:
        try:
            entity_id = upsert_entity(
                conn,
                client_id=client_id,
                entity=entity,
                now=now,
            )
            insert_mention(
                conn,
                entity_id=entity_id,
                v2_document_id=v2_document_id,
                v2_chunk_id=v2_chunk_id,
                entity=entity,
                now=now,
            )
            if entity_id not in entity_ids:
                entity_ids.append(entity_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "persist entity failed (client=%s, type=%s, name=%s): %s",
                client_id,
                entity.entity_type,
                entity.normalized_name,
                exc,
            )
    if entity_ids:
        update_chunk_entity_ids(conn, v2_chunk_id, entity_ids)
    return entity_ids


def list_entities(
    conn: sqlite3.Connection,
    *,
    client_id: str,
    entity_type: str | None = None,
    name_query: str | None = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[EntityRow], int]:
    """分页查询实体。

    Returns:
        (entities, total_count)
    """
    where = ["client_id = ?", "status = ?"]
    params: list[object] = [client_id, status]
    if entity_type:
        where.append("entity_type = ?")
        params.append(entity_type)
    if name_query:
        where.append("(normalized_name LIKE ? OR display_name LIKE ?)")
        wildcard = f"%{name_query}%"
        params.append(wildcard)
        params.append(wildcard)
    where_clause = " AND ".join(where)

    count_row = conn.execute(
        f"SELECT COUNT(*) AS n FROM entities WHERE {where_clause}",
        tuple(params),
    ).fetchone()
    total = int(count_row["n"] or 0) if count_row else 0

    rows = conn.execute(
        f"SELECT * FROM entities WHERE {where_clause} "
        "ORDER BY last_seen_at DESC, mention_count DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [_row_to_entity(r) for r in rows], total


__all__ = [
    "EntityRow",
    "insert_mention",
    "list_entities",
    "persist_chunk_entities",
    "update_chunk_entity_ids",
    "upsert_entity",
]
