from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import DataCenterShadowRunRecord, DataCenterShadowSummaryRecord


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_data_center_shadow_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS data_center_shadow_runs (
            id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            page TEXT NOT NULL,
            mode TEXT NOT NULL,
            prompt TEXT NOT NULL,
            baseline_json TEXT NOT NULL DEFAULT '{}',
            candidate_json TEXT NOT NULL DEFAULT '{}',
            route_decision_json TEXT NOT NULL DEFAULT '{}',
            retrieval_trace_json TEXT NOT NULL DEFAULT '{}',
            answer_plan_json TEXT NOT NULL DEFAULT '{}',
            answer_quality_json TEXT NOT NULL DEFAULT '{}',
            action_suggestion_json TEXT NOT NULL DEFAULT '[]',
            overlap_rate REAL NOT NULL DEFAULT 0,
            candidate_failed INTEGER NOT NULL DEFAULT 0,
            failure_reason TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def create_data_center_shadow_run(
    db: Database,
    *,
    scope_type: str,
    scope_id: str,
    page: str,
    mode: str,
    prompt: str,
    baseline: dict[str, object],
    candidate: dict[str, object],
    route_decision: dict[str, object],
    retrieval_trace: dict[str, object],
    answer_plan: dict[str, object],
    answer_quality: dict[str, object],
    action_suggestion: list[dict[str, object]],
    overlap_rate: float,
    candidate_failed: bool,
    failure_reason: str | None = None,
) -> DataCenterShadowRunRecord:
    ensure_data_center_shadow_schema(db)
    run_id = f"dcshadow_{uuid4().hex[:10]}"
    created_at = _now_iso()
    db.execute(
        """
        INSERT INTO data_center_shadow_runs(
            id, scope_type, scope_id, page, mode, prompt,
            baseline_json, candidate_json, route_decision_json, retrieval_trace_json,
            answer_plan_json, answer_quality_json, action_suggestion_json,
            overlap_rate, candidate_failed, failure_reason, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            scope_type,
            scope_id,
            page,
            mode,
            prompt,
            to_json(baseline),
            to_json(candidate),
            to_json(route_decision),
            to_json(retrieval_trace),
            to_json(answer_plan),
            to_json(answer_quality),
            to_json(action_suggestion),
            float(overlap_rate),
            1 if candidate_failed else 0,
            failure_reason,
            created_at,
        ),
    )
    return DataCenterShadowRunRecord(
        id=run_id,
        scopeType=scope_type,
        scopeId=scope_id,
        page=page,
        mode=mode,
        prompt=prompt,
        baseline=baseline,
        candidate=candidate,
        routeDecision=route_decision,
        retrievalTrace=retrieval_trace,
        answerPlan=answer_plan,
        answerQuality=answer_quality,
        actionSuggestion=action_suggestion,
        overlapRate=float(overlap_rate),
        candidateFailed=bool(candidate_failed),
        failureReason=failure_reason,
        createdAt=created_at,
    )


def list_data_center_shadow_runs(
    db: Database,
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
    limit: int = 100,
) -> list[DataCenterShadowRunRecord]:
    ensure_data_center_shadow_schema(db)
    where: list[str] = []
    params: list[object] = []
    if scope_type:
        where.append("scope_type = ?")
        params.append(scope_type)
    if scope_id:
        where.append("scope_id = ?")
        params.append(scope_id)
    sql = "SELECT * FROM data_center_shadow_runs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))

    rows = db.fetchall(sql, tuple(params))
    records: list[DataCenterShadowRunRecord] = []
    for row in rows:
        records.append(
            DataCenterShadowRunRecord(
                id=str(row["id"]),
                scopeType=str(row["scope_type"]),
                scopeId=str(row["scope_id"]),
                page=str(row["page"]),
                mode=str(row["mode"]),
                prompt=str(row["prompt"]),
                baseline=from_json(str(row["baseline_json"] or "{}"), {}),
                candidate=from_json(str(row["candidate_json"] or "{}"), {}),
                routeDecision=from_json(str(row["route_decision_json"] or "{}"), {}),
                retrievalTrace=from_json(str(row["retrieval_trace_json"] or "{}"), {}),
                answerPlan=from_json(str(row["answer_plan_json"] or "{}"), {}),
                answerQuality=from_json(str(row["answer_quality_json"] or "{}"), {}),
                actionSuggestion=from_json(str(row["action_suggestion_json"] or "[]"), []),
                overlapRate=float(row["overlap_rate"] or 0.0),
                candidateFailed=bool(row["candidate_failed"]),
                failureReason=str(row["failure_reason"]) if row["failure_reason"] else None,
                createdAt=str(row["created_at"]),
            )
        )
    return records


def get_data_center_shadow_summary(
    db: Database,
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> DataCenterShadowSummaryRecord:
    runs = list_data_center_shadow_runs(db, scope_type=scope_type, scope_id=scope_id, limit=500)
    total = len(runs)
    if total == 0:
        return DataCenterShadowSummaryRecord()

    quality_pass = 0
    direct_answer_pass = 0
    evidence_list_only_fail = 0
    candidate_better = 0
    candidate_better_by_grade = 0
    grade_delta_total = 0.0
    independent_chain_pass = 0
    overlap_sum = 0.0
    failures = 0

    def _grade_score(value: str) -> int:
        lowered = str(value or "").strip().lower()
        if lowered == "pass":
            return 2
        if lowered == "warn":
            return 1
        return 0

    for run in runs:
        quality = run.answerQuality if isinstance(run.answerQuality, dict) else {}
        if str(quality.get("grade") or "") == "pass":
            quality_pass += 1
        if bool(quality.get("hasDirectAnswer")):
            direct_answer_pass += 1
        if bool(quality.get("evidenceListOnly")):
            evidence_list_only_fail += 1
        baseline = run.baseline if isinstance(run.baseline, dict) else {}
        candidate = run.candidate if isinstance(run.candidate, dict) else {}
        baseline_grade = str((baseline.get("answerQuality") or {}).get("grade") or "") if isinstance(baseline.get("answerQuality"), dict) else ""
        candidate_grade = str((candidate.get("answerQuality") or {}).get("grade") or "") if isinstance(candidate.get("answerQuality"), dict) else ""
        if baseline_grade and candidate_grade and baseline_grade != "pass" and candidate_grade == "pass":
            candidate_better += 1
        if baseline_grade and candidate_grade and _grade_score(candidate_grade) > _grade_score(baseline_grade):
            candidate_better_by_grade += 1
        if baseline_grade and candidate_grade:
            grade_delta_total += float(_grade_score(candidate_grade) - _grade_score(baseline_grade))

        if (
            isinstance(baseline.get("answerQuality"), dict)
            and isinstance(candidate.get("answerQuality"), dict)
            and isinstance(baseline.get("answerPlan"), dict)
            and isinstance(candidate.get("answerPlan"), dict)
            and isinstance(baseline.get("routeDecision"), dict)
            and isinstance(candidate.get("routeDecision"), dict)
        ):
            independent_chain_pass += 1
        if run.failureReason or run.candidateFailed:
            failures += 1
        overlap_sum += float(run.overlapRate or 0.0)

    return DataCenterShadowSummaryRecord(
        total=total,
        answerQualityPassRate=round(quality_pass / total, 4),
        directAnswerPassRate=round(direct_answer_pass / total, 4),
        evidenceListOnlyFailRate=round(evidence_list_only_fail / total, 4),
        candidateBetterRate=round(candidate_better / total, 4),
        candidateBetterByGradeRate=round(candidate_better_by_grade / total, 4),
        gradeDeltaAvg=round(grade_delta_total / total, 4),
        independentChainPassRate=round(independent_chain_pass / total, 4),
        overlapRateAvg=round(overlap_sum / total, 4),
        failures=failures,
    )
