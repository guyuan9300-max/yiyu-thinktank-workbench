from __future__ import annotations

import hashlib
from datetime import datetime

from app.db import Database, from_json, to_json
from app.models import (
    EvidenceItem,
    EvidenceQualityAnnotationRecord,
    EvidenceQualitySignalRecord,
)
from app.services.knowledge_v2 import new_id


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _excerpt_hash(*, title: str, excerpt: str, path: str) -> str:
    raw = f"{title.strip()}|{excerpt.strip()}|{path.strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def ensure_evidence_quality_annotation_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_quality_annotations (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            document_id TEXT,
            path TEXT,
            excerpt_hash TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            quality_score REAL NOT NULL DEFAULT 0,
            demotion_score REAL NOT NULL DEFAULT 0,
            noise_reasons_json TEXT NOT NULL DEFAULT '[]',
            authority_hint TEXT NOT NULL DEFAULT 'unknown',
            human_label TEXT,
            human_note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_type, source_id, excerpt_hash)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_evidence_quality_annotations_scope
        ON evidence_quality_annotations(source_type, source_id, created_at DESC)
        """
    )


def _row_to_record(row) -> EvidenceQualityAnnotationRecord:
    return EvidenceQualityAnnotationRecord(
        id=str(row["id"]),
        sourceType=str(row["source_type"]),
        sourceId=str(row["source_id"]),
        documentId=str(row["document_id"]) if row["document_id"] else None,
        path=str(row["path"]) if row["path"] else None,
        excerptHash=str(row["excerpt_hash"]),
        sourceKind=str(row["source_kind"]),  # type: ignore[arg-type]
        qualityScore=float(row["quality_score"] or 0.0),
        demotionScore=float(row["demotion_score"] or 0.0),
        noiseReasons=[str(item) for item in from_json(str(row["noise_reasons_json"] or "[]"), []) if str(item).strip()],
        authorityHint=str(row["authority_hint"] or "unknown"),  # type: ignore[arg-type]
        humanLabel=str(row["human_label"]) if row["human_label"] else None,  # type: ignore[arg-type]
        humanNote=str(row["human_note"] or ""),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def persist_evidence_quality_signal(
    db: Database,
    *,
    source_type: str,
    source_id: str,
    document_id: str | None,
    path: str | None,
    title: str,
    excerpt: str,
    signal: EvidenceQualitySignalRecord,
) -> EvidenceQualityAnnotationRecord:
    ensure_evidence_quality_annotation_schema(db)
    now = _now_iso()
    excerpt_hash = _excerpt_hash(title=title, excerpt=excerpt, path=path or "")
    existing = db.fetchone(
        """
        SELECT * FROM evidence_quality_annotations
        WHERE source_type = ? AND source_id = ? AND excerpt_hash = ?
        LIMIT 1
        """,
        (source_type, source_id, excerpt_hash),
    )
    if existing:
        db.execute(
            """
            UPDATE evidence_quality_annotations
            SET source_kind = ?,
                quality_score = ?,
                demotion_score = ?,
                noise_reasons_json = ?,
                authority_hint = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                signal.sourceKind,
                float(signal.qualityScore or 0.0),
                float(signal.demotionScore or 0.0),
                to_json(signal.noiseReasons),
                signal.authorityHint,
                now,
                str(existing["id"]),
            ),
        )
        row = db.fetchone("SELECT * FROM evidence_quality_annotations WHERE id = ?", (str(existing["id"]),))
        assert row is not None
        return _row_to_record(row)

    annotation_id = new_id("eqa")
    db.execute(
        """
        INSERT INTO evidence_quality_annotations(
            id, source_type, source_id, document_id, path, excerpt_hash, source_kind,
            quality_score, demotion_score, noise_reasons_json, authority_hint,
            human_label, human_note, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '', ?, ?)
        """,
        (
            annotation_id,
            source_type,
            source_id,
            document_id,
            path,
            excerpt_hash,
            signal.sourceKind,
            float(signal.qualityScore or 0.0),
            float(signal.demotionScore or 0.0),
            to_json(signal.noiseReasons),
            signal.authorityHint,
            now,
            now,
        ),
    )
    row = db.fetchone("SELECT * FROM evidence_quality_annotations WHERE id = ?", (annotation_id,))
    assert row is not None
    return _row_to_record(row)


def persist_evidence_quality_annotations_for_items(
    db: Database,
    *,
    source_type: str,
    source_id: str,
    items: list[tuple[EvidenceItem, EvidenceQualitySignalRecord]],
) -> list[EvidenceQualityAnnotationRecord]:
    records: list[EvidenceQualityAnnotationRecord] = []
    for item, signal in items:
        records.append(
            persist_evidence_quality_signal(
                db,
                source_type=source_type,
                source_id=source_id,
                document_id=item.documentId,
                path=item.path,
                title=item.title,
                excerpt=item.excerpt,
                signal=signal,
            )
        )
    return records


def list_evidence_quality_annotations(
    db: Database,
    *,
    source_type: str | None = None,
    source_id: str | None = None,
    label: str | None = None,
    limit: int = 120,
) -> list[EvidenceQualityAnnotationRecord]:
    ensure_evidence_quality_annotation_schema(db)
    clauses: list[str] = []
    params: list[object] = []
    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    if source_id:
        clauses.append("source_id = ?")
        params.append(source_id)
    if label:
        clauses.append("human_label = ?")
        params.append(label)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.fetchall(
        f"SELECT * FROM evidence_quality_annotations {where_clause} ORDER BY updated_at DESC, created_at DESC LIMIT ?",
        (*params, int(limit)),
    )
    return [_row_to_record(row) for row in rows]


def update_evidence_quality_human_label(
    db: Database,
    *,
    annotation_id: str,
    label: str,
    note: str = "",
) -> EvidenceQualityAnnotationRecord:
    ensure_evidence_quality_annotation_schema(db)
    row = db.fetchone("SELECT * FROM evidence_quality_annotations WHERE id = ?", (annotation_id,))
    if not row:
        raise KeyError("annotation_not_found")
    now = _now_iso()
    db.execute(
        """
        UPDATE evidence_quality_annotations
        SET human_label = ?,
            human_note = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (label, (note or "").strip(), now, annotation_id),
    )
    updated = db.fetchone("SELECT * FROM evidence_quality_annotations WHERE id = ?", (annotation_id,))
    assert updated is not None
    return _row_to_record(updated)
