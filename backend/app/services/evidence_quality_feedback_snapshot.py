from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from app.db import Database, from_json, to_json
from app.models import EvidenceQualityFeedbackSnapshotRecord
from app.services.knowledge_v2 import new_id


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _window_start_iso(days: int) -> str:
    return (datetime.now() - timedelta(days=max(int(days), 1))).replace(microsecond=0).isoformat()


def ensure_evidence_quality_feedback_snapshot_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_quality_feedback_snapshots (
            id TEXT PRIMARY KEY,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            label_counts_json TEXT NOT NULL DEFAULT '{}',
            useful_examples_json TEXT NOT NULL DEFAULT '[]',
            noise_examples_json TEXT NOT NULL DEFAULT '[]',
            needs_review_examples_json TEXT NOT NULL DEFAULT '[]',
            recommended_rules_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_evidence_quality_feedback_snapshots_created
        ON evidence_quality_feedback_snapshots(created_at DESC)
        """
    )


def _row_to_snapshot_record(row) -> EvidenceQualityFeedbackSnapshotRecord:
    label_counts_raw = from_json(str(row["label_counts_json"] or "{}"), {})
    useful_examples_raw = from_json(str(row["useful_examples_json"] or "[]"), [])
    noise_examples_raw = from_json(str(row["noise_examples_json"] or "[]"), [])
    needs_review_examples_raw = from_json(str(row["needs_review_examples_json"] or "[]"), [])
    recommended_rules_raw = from_json(str(row["recommended_rules_json"] or "[]"), [])
    return EvidenceQualityFeedbackSnapshotRecord(
        id=str(row["id"]),
        windowStart=str(row["window_start"]),
        windowEnd=str(row["window_end"]),
        labelCounts={
            str(key): int(value or 0)
            for key, value in (label_counts_raw.items() if isinstance(label_counts_raw, dict) else [])
        },
        usefulExamples=[item for item in useful_examples_raw if isinstance(item, dict)],
        noiseExamples=[item for item in noise_examples_raw if isinstance(item, dict)],
        needsReviewExamples=[item for item in needs_review_examples_raw if isinstance(item, dict)],
        recommendedRules=[str(item) for item in recommended_rules_raw if str(item).strip()],
        createdAt=str(row["created_at"]),
    )


def create_evidence_quality_feedback_snapshot(
    db: Database,
    *,
    days: int = 7,
) -> EvidenceQualityFeedbackSnapshotRecord:
    ensure_evidence_quality_feedback_snapshot_schema(db)
    window_days = max(int(days), 1)
    window_start = _window_start_iso(window_days)
    window_end = _now_iso()

    rows = db.fetchall(
        """
        SELECT *
        FROM evidence_quality_annotations
        WHERE updated_at >= ?
        ORDER BY updated_at DESC
        LIMIT 2000
        """,
        (window_start,),
    )

    label_counts: Counter[str] = Counter()
    useful_examples: list[dict[str, object]] = []
    noise_examples: list[dict[str, object]] = []
    needs_review_examples: list[dict[str, object]] = []
    noise_reason_counter: Counter[str] = Counter()

    for row in rows:
        label = str(row["human_label"] or "unlabeled").strip() or "unlabeled"
        label_counts[label] += 1
        noise_reasons = from_json(str(row["noise_reasons_json"] or "[]"), [])
        if isinstance(noise_reasons, list):
            for reason in noise_reasons:
                normalized = str(reason or "").strip().lower()
                if normalized:
                    noise_reason_counter[normalized] += 1
        sample = {
            "annotationId": str(row["id"]),
            "sourceType": str(row["source_type"]),
            "sourceId": str(row["source_id"]),
            "documentId": str(row["document_id"]) if row["document_id"] else None,
            "path": str(row["path"]) if row["path"] else None,
            "excerptHash": str(row["excerpt_hash"]),
            "humanNote": str(row["human_note"] or ""),
            "updatedAt": str(row["updated_at"]),
        }
        if label == "useful" and len(useful_examples) < 5:
            useful_examples.append(sample)
        elif label == "noise" and len(noise_examples) < 5:
            noise_examples.append(sample)
        elif label == "needs_review" and len(needs_review_examples) < 5:
            needs_review_examples.append(sample)

    recommended_rules: list[str] = []
    if label_counts.get("noise", 0) > label_counts.get("useful", 0):
        recommended_rules.append("noise 标注数量高于 useful，建议检查证据降权规则是否足够严格。")
    if noise_reason_counter:
        top_reason, top_count = noise_reason_counter.most_common(1)[0]
        recommended_rules.append(f"噪声原因 Top1 为 `{top_reason}`（{top_count} 次），建议优先针对该类证据优化。")
    if label_counts.get("needs_review", 0) > 0:
        recommended_rules.append("存在 needs_review 标注，建议运营在下个周期完成人工复核并更新标签。")
    if not recommended_rules:
        recommended_rules.append("当前反馈样本较稳定，建议继续沉淀人工标注样本。")

    snapshot_id = new_id("eqsnap")
    db.execute(
        """
        INSERT INTO evidence_quality_feedback_snapshots(
            id, window_start, window_end, label_counts_json,
            useful_examples_json, noise_examples_json, needs_review_examples_json,
            recommended_rules_json, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            window_start,
            window_end,
            to_json(dict(label_counts)),
            to_json(useful_examples),
            to_json(noise_examples),
            to_json(needs_review_examples),
            to_json(recommended_rules),
            _now_iso(),
        ),
    )
    row = db.fetchone("SELECT * FROM evidence_quality_feedback_snapshots WHERE id = ?", (snapshot_id,))
    assert row is not None
    return _row_to_snapshot_record(row)


def list_evidence_quality_feedback_snapshots(
    db: Database,
    *,
    limit: int = 30,
) -> list[EvidenceQualityFeedbackSnapshotRecord]:
    ensure_evidence_quality_feedback_snapshot_schema(db)
    rows = db.fetchall(
        """
        SELECT *
        FROM evidence_quality_feedback_snapshots
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (max(int(limit), 1),),
    )
    return [_row_to_snapshot_record(row) for row in rows]
