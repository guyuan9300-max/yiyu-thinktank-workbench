from __future__ import annotations

import hashlib
import sqlite3

from app.db import Database


def build_evidence_excerpt_hash(*, title: str, excerpt: str, path: str | None) -> str:
    raw = f"{str(title or '').strip()}|{str(excerpt or '').strip()}|{str(path or '').strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def get_human_quality_adjustment(
    db: Database | None,
    *,
    source_type: str,
    source_id: str,
    document_id: str | None,
    excerpt_hash: str,
) -> float:
    if db is None:
        return 0.0
    normalized_source_type = str(source_type or "").strip()
    normalized_source_id = str(source_id or "").strip()
    normalized_hash = str(excerpt_hash or "").strip()
    if not normalized_source_type or not normalized_source_id or not normalized_hash:
        return 0.0
    try:
        row = db.fetchone(
            """
            SELECT human_label
            FROM evidence_quality_annotations
            WHERE source_type = ?
              AND source_id = ?
              AND excerpt_hash = ?
              AND (? IS NULL OR document_id = ?)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (
                normalized_source_type,
                normalized_source_id,
                normalized_hash,
                document_id,
                document_id,
            ),
        )
    except sqlite3.OperationalError:
        # Backward compatibility: old databases may not have this table yet.
        return 0.0
    if not row:
        return 0.0
    label = str(row["human_label"] or "").strip().lower()
    if label == "useful":
        return 0.8
    if label == "noise":
        return -1.2
    if label == "needs_review":
        return -0.3
    return 0.0
