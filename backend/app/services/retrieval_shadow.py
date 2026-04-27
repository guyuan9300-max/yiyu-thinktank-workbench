from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import RetrievalShadowRunRecord, RetrievalShadowSummaryRecord


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_retrieval_shadow_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS retrieval_shadow_runs (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            page TEXT NOT NULL,
            prompt TEXT NOT NULL,
            baseline_summary_json TEXT NOT NULL DEFAULT '{}',
            candidate_summary_json TEXT NOT NULL DEFAULT '{}',
            overlap_rate REAL NOT NULL DEFAULT 0,
            candidate_better INTEGER NOT NULL DEFAULT 0,
            failure_reason TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def create_retrieval_shadow_run(
    db: Database,
    *,
    client_id: str,
    page: str,
    prompt: str,
    baseline_summary: dict[str, object],
    candidate_summary: dict[str, object],
    overlap_rate: float,
    candidate_better: bool,
    failure_reason: str | None = None,
) -> RetrievalShadowRunRecord:
    ensure_retrieval_shadow_schema(db)
    run_id = f"rshadow_{uuid4().hex[:10]}"
    created_at = _now_iso()
    db.execute(
        """
        INSERT INTO retrieval_shadow_runs(
            id, client_id, page, prompt, baseline_summary_json, candidate_summary_json,
            overlap_rate, candidate_better, failure_reason, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            client_id,
            page,
            prompt,
            to_json(baseline_summary),
            to_json(candidate_summary),
            float(overlap_rate),
            1 if candidate_better else 0,
            failure_reason,
            created_at,
        ),
    )
    return RetrievalShadowRunRecord(
        id=run_id,
        clientId=client_id,
        page=page,
        prompt=prompt,
        baselineSummary=baseline_summary,
        candidateSummary=candidate_summary,
        overlapRate=float(overlap_rate),
        candidateBetter=bool(candidate_better),
        failureReason=failure_reason,
        createdAt=created_at,
    )


def list_retrieval_shadow_runs(
    db: Database,
    *,
    client_id: str | None = None,
    limit: int = 60,
) -> list[RetrievalShadowRunRecord]:
    ensure_retrieval_shadow_schema(db)
    if client_id:
        rows = db.fetchall(
            """
            SELECT *
            FROM retrieval_shadow_runs
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (client_id, limit),
        )
    else:
        rows = db.fetchall(
            """
            SELECT *
            FROM retrieval_shadow_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
    records: list[RetrievalShadowRunRecord] = []
    for row in rows:
        baseline = from_json(str(row["baseline_summary_json"] or "{}"), {})
        candidate = from_json(str(row["candidate_summary_json"] or "{}"), {})
        records.append(
            RetrievalShadowRunRecord(
                id=str(row["id"]),
                clientId=str(row["client_id"]),
                page=str(row["page"]),
                prompt=str(row["prompt"]),
                baselineSummary=baseline if isinstance(baseline, dict) else {},
                candidateSummary=candidate if isinstance(candidate, dict) else {},
                overlapRate=float(row["overlap_rate"] or 0.0),
                candidateBetter=bool(row["candidate_better"]),
                failureReason=str(row["failure_reason"]) if row["failure_reason"] else None,
                createdAt=str(row["created_at"]),
            )
        )
    return records


def get_retrieval_shadow_summary(
    db: Database,
    *,
    client_id: str | None = None,
) -> RetrievalShadowSummaryRecord:
    runs = list_retrieval_shadow_runs(db, client_id=client_id, limit=500)
    total = len(runs)
    if total == 0:
        return RetrievalShadowSummaryRecord()
    better_count = sum(1 for run in runs if run.candidateBetter)
    overlap_avg = sum(float(run.overlapRate or 0.0) for run in runs) / total
    failures = sum(1 for run in runs if run.failureReason)
    latency_deltas: list[float] = []
    for run in runs:
        baseline_timing = run.baselineSummary.get("timing", {}) if isinstance(run.baselineSummary, dict) else {}
        candidate_timing = run.candidateSummary.get("timing", {}) if isinstance(run.candidateSummary, dict) else {}
        if not isinstance(baseline_timing, dict) or not isinstance(candidate_timing, dict):
            continue
        baseline_total = float(baseline_timing.get("totalMs", 0.0) or 0.0)
        candidate_total = float(candidate_timing.get("totalMs", 0.0) or 0.0)
        if baseline_total > 0 and candidate_total > 0:
            latency_deltas.append(candidate_total - baseline_total)
    latency_avg = (sum(latency_deltas) / len(latency_deltas)) if latency_deltas else 0.0
    return RetrievalShadowSummaryRecord(
        total=total,
        candidateBetterRate=round(better_count / total, 4),
        overlapRateAvg=round(overlap_avg, 4),
        latencyDeltaMsAvg=round(latency_avg, 2),
        failures=failures,
    )

