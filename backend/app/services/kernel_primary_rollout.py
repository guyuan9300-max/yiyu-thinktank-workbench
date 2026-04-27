from __future__ import annotations

from datetime import datetime

from app.db import Database, from_json, to_json
from app.models import (
    KernelPrimaryRolloutRunRecord,
    RetrievalModelSettingsPayload,
)
from app.services.knowledge_v2 import new_id
from app.services.retrieval_model_settings import save_retrieval_model_settings
from app.services.workspace_answer_value_diagnostics import (
    build_workspace_answer_value_diagnostics,
    build_workspace_answer_value_summary,
)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_kernel_primary_rollout_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS kernel_primary_rollout_runs (
            id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            client_ids_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'planned',
            metrics_before_json TEXT NOT NULL DEFAULT '{}',
            metrics_after_json TEXT NOT NULL DEFAULT '{}',
            verdict TEXT,
            recommended_action TEXT,
            note TEXT NOT NULL DEFAULT '',
            rollback_reason TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kernel_primary_rollout_runs_stage_status
        ON kernel_primary_rollout_runs(stage, status, updated_at DESC)
        """
    )


def _safe_ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(float(num) / float(den), 4)


def _compute_p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, int(round((len(sorted_values) - 1) * 0.95))))
    return round(float(sorted_values[index]), 2)


def collect_kernel_primary_rollout_metrics(
    db: Database,
    *,
    client_ids: list[str],
    since: str | None = None,
) -> dict[str, object]:
    normalized_client_ids = [str(item).strip() for item in client_ids if str(item).strip()]
    if not normalized_client_ids:
        return {
            "totalMessages": 0,
            "kernelPrimaryUsedCount": 0,
            "kernelPrimaryFallbackUsedCount": 0,
            "kernelPrimaryFallbackRate": 0.0,
            "answerQualityFailRate": 0.0,
            "officialBoundaryViolation": 0,
            "candidateBoundaryViolation": 0,
            "p95LatencyMs": 0.0,
            "llmTimeoutRate": 0.0,
            "fallbackRate": 0.0,
        }

    placeholders = ", ".join("?" for _ in normalized_client_ids)
    params: list[object] = [*normalized_client_ids]
    where_since = ""
    if since:
        where_since = "AND m.created_at >= ?"
        params.append(since)
    rows = db.fetchall(
        f"""
        SELECT m.failure_reason, m.timing_json, m.retrieval_summary_json
        FROM chat_messages m
        JOIN chat_threads t ON t.id = m.thread_id
        WHERE t.client_id IN ({placeholders})
          AND m.role = 'assistant'
          AND m.status = 'success'
          {where_since}
        ORDER BY m.created_at DESC
        LIMIT 1200
        """,
        tuple(params),
    )

    total_messages = len(rows)
    kernel_primary_used_count = 0
    kernel_primary_fallback_count = 0
    answer_quality_fail_count = 0
    official_boundary_violation = 0
    candidate_boundary_violation = 0
    timeout_count = 0
    fallback_count = 0
    latency_values: list[float] = []

    for row in rows:
        failure_reason = str(row["failure_reason"] or "").lower()
        if "timeout" in failure_reason:
            timeout_count += 1
        if "fallback" in failure_reason:
            fallback_count += 1

        timing = from_json(str(row["timing_json"] or "{}"), {})
        if isinstance(timing, dict):
            total_ms = float(timing.get("totalMs") or 0.0)
            if total_ms > 0:
                latency_values.append(total_ms)

        retrieval_summary = from_json(str(row["retrieval_summary_json"] or "{}"), {})
        if not isinstance(retrieval_summary, dict):
            continue
        if bool(retrieval_summary.get("kernelPrimaryUsed")):
            kernel_primary_used_count += 1
        if bool(retrieval_summary.get("kernelPrimaryFallbackUsed")):
            kernel_primary_fallback_count += 1
        answer_quality = retrieval_summary.get("answerQuality")
        if isinstance(answer_quality, dict):
            grade = str(answer_quality.get("grade") or "").strip().lower()
            if grade == "fail":
                answer_quality_fail_count += 1
            if bool(answer_quality.get("officialBoundaryViolation")):
                official_boundary_violation += 1
            if bool(answer_quality.get("candidateAsOfficialRisk")):
                candidate_boundary_violation += 1

    kernel_used_den = max(kernel_primary_used_count, 1)
    return {
        "totalMessages": total_messages,
        "kernelPrimaryUsedCount": kernel_primary_used_count,
        "kernelPrimaryFallbackUsedCount": kernel_primary_fallback_count,
        "kernelPrimaryFallbackRate": _safe_ratio(kernel_primary_fallback_count, kernel_used_den),
        "answerQualityFailRate": _safe_ratio(answer_quality_fail_count, kernel_used_den),
        "officialBoundaryViolation": official_boundary_violation,
        "candidateBoundaryViolation": candidate_boundary_violation,
        "p95LatencyMs": _compute_p95(latency_values),
        "llmTimeoutRate": _safe_ratio(timeout_count, max(total_messages, 1)),
        "fallbackRate": _safe_ratio(fallback_count, max(total_messages, 1)),
    }


def _collect_workspace_value_metrics(
    db: Database,
    *,
    client_ids: list[str],
    since: str | None = None,
) -> dict[str, object]:
    normalized_client_ids = [str(item).strip() for item in client_ids if str(item).strip()]
    if not normalized_client_ids:
        return {
            "workspaceRetryBannerRate": 0.0,
            "workspaceUsableAnswerRate": 0.0,
            "workspaceReadyOrUsableRate": 0.0,
            "workspaceNeedsRetryRate": 0.0,
            "workspaceKernelPrimaryUsedRate": 0.0,
            "humanReviewCount": 0,
            "estimatedTimeSavedRate": 0.0,
            "answerTooTemplateLikeRate": 0.0,
            "proposalCreatedFromAnswerCount": 0,
            "executionTicketCreatedFromAnswerCount": 0,
            "workspaceTopFallbackReasons": [],
            "metricErrors": [],
        }
    total_messages = 0
    retry_banner_weighted = 0.0
    usable_weighted = 0.0
    ready_or_usable_weighted = 0.0
    needs_retry_weighted = 0.0
    kernel_primary_weighted = 0.0
    template_like_weighted = 0.0
    fallback_reason_counts: dict[str, int] = {}
    human_review_count = 0
    estimated_time_saved_weighted = 0.0
    proposal_created_count = 0
    execution_created_count = 0
    metric_errors: list[str] = []
    for client_id in normalized_client_ids:
        diagnostics = build_workspace_answer_value_diagnostics(
            db,
            client_id=client_id,
            recent_messages=120,
            since=since,
        )
        summary = build_workspace_answer_value_summary(
            db,
            client_id=client_id,
        )
        recent = int(diagnostics.get("recentMessages") or 0)
        if recent <= 0:
            recent = max(int(summary.reviewCount or 0), 0)
        if recent > 0:
            total_messages += recent
            retry_banner_weighted += float(diagnostics.get("retryBannerWouldShowRate") or 0.0) * recent
            usable_weighted += float(diagnostics.get("usableAnswerRate") or 0.0) * recent
            ready_or_usable_weighted += float(diagnostics.get("readyOrUsableRate") or 0.0) * recent
            needs_retry_weighted += float(diagnostics.get("needsRetryRate") or 0.0) * recent
            kernel_primary_weighted += float(diagnostics.get("kernelPrimaryUsedRate") or 0.0) * recent
            template_like_weighted += float(diagnostics.get("answerTooTemplateLikeRate") or 0.0) * recent
            top_failure_reasons = diagnostics.get("topFailureReasons")
            if isinstance(top_failure_reasons, list):
                for item in top_failure_reasons:
                    if not isinstance(item, dict):
                        continue
                    key = str(item.get("key") or "").strip()
                    if not key:
                        continue
                    fallback_reason_counts[key] = fallback_reason_counts.get(key, 0) + int(item.get("count") or 0)
        human_review_count += int(summary.reviewCount or 0)
        estimated_time_saved_weighted += float(summary.estimatedTimeSavedRate or 0.0) * max(int(summary.reviewCount or 0), 1)
        proposal_created_count += int(summary.proposalCreatedFromAnswerCount or 0)
        execution_created_count += int(summary.executionTicketCreatedFromAnswerCount or 0)
        for item in diagnostics.get("metricErrors") or []:
            text = str(item).strip()
            if text and text not in metric_errors:
                metric_errors.append(text)
        for item in summary.metricErrors or []:
            text = str(item).strip()
            if text and text not in metric_errors:
                metric_errors.append(text)

    if total_messages <= 0:
        return {
            "workspaceRetryBannerRate": 0.0,
            "workspaceUsableAnswerRate": 0.0,
            "workspaceReadyOrUsableRate": 0.0,
            "workspaceNeedsRetryRate": 0.0,
            "workspaceKernelPrimaryUsedRate": 0.0,
            "humanReviewCount": human_review_count,
            "estimatedTimeSavedRate": 0.0,
            "answerTooTemplateLikeRate": 0.0,
            "proposalCreatedFromAnswerCount": proposal_created_count,
            "executionTicketCreatedFromAnswerCount": execution_created_count,
            "workspaceTopFallbackReasons": [],
            "metricErrors": metric_errors,
        }
    top_fallback_reasons = sorted(
        fallback_reason_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[:5]
    return {
        "workspaceRetryBannerRate": round(retry_banner_weighted / total_messages, 4),
        "workspaceUsableAnswerRate": round(usable_weighted / total_messages, 4),
        "workspaceReadyOrUsableRate": round(ready_or_usable_weighted / total_messages, 4),
        "workspaceNeedsRetryRate": round(needs_retry_weighted / total_messages, 4),
        "workspaceKernelPrimaryUsedRate": round(kernel_primary_weighted / total_messages, 4),
        "humanReviewCount": human_review_count,
        "estimatedTimeSavedRate": round(estimated_time_saved_weighted / max(human_review_count, 1), 4),
        "answerTooTemplateLikeRate": round(template_like_weighted / total_messages, 4),
        "proposalCreatedFromAnswerCount": proposal_created_count,
        "executionTicketCreatedFromAnswerCount": execution_created_count,
        "workspaceTopFallbackReasons": [
            {"key": key, "count": count}
            for key, count in top_fallback_reasons
        ],
        "metricErrors": metric_errors,
    }


def _row_to_rollout_record(row) -> KernelPrimaryRolloutRunRecord:
    client_ids_raw = from_json(str(row["client_ids_json"] or "[]"), [])
    metrics_before_raw = from_json(str(row["metrics_before_json"] or "{}"), {})
    metrics_after_raw = from_json(str(row["metrics_after_json"] or "{}"), {})
    return KernelPrimaryRolloutRunRecord(
        id=str(row["id"]),
        stage=str(row["stage"]),  # type: ignore[arg-type]
        clientIds=[str(item) for item in client_ids_raw if str(item).strip()] if isinstance(client_ids_raw, list) else [],
        status=str(row["status"]),  # type: ignore[arg-type]
        metricsBefore=metrics_before_raw if isinstance(metrics_before_raw, dict) else {},
        metricsAfter=metrics_after_raw if isinstance(metrics_after_raw, dict) else {},
        verdict=str(row["verdict"]) if row["verdict"] else None,  # type: ignore[arg-type]
        recommendedAction=str(row["recommended_action"]) if row["recommended_action"] else None,  # type: ignore[arg-type]
        note=str(row["note"] or ""),
        rollbackReason=str(row["rollback_reason"]) if row["rollback_reason"] else None,
        startedAt=str(row["started_at"]) if row["started_at"] else None,
        completedAt=str(row["completed_at"]) if row["completed_at"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def list_kernel_primary_rollout_runs(
    db: Database,
    *,
    limit: int = 40,
) -> list[KernelPrimaryRolloutRunRecord]:
    ensure_kernel_primary_rollout_schema(db)
    rows = db.fetchall(
        """
        SELECT *
        FROM kernel_primary_rollout_runs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (max(int(limit), 1),),
    )
    return [_row_to_rollout_record(row) for row in rows]


def get_kernel_primary_rollout_run(
    db: Database,
    *,
    run_id: str,
) -> KernelPrimaryRolloutRunRecord:
    ensure_kernel_primary_rollout_schema(db)
    row = db.fetchone("SELECT * FROM kernel_primary_rollout_runs WHERE id = ?", (run_id,))
    if not row:
        raise KeyError("kernel_primary_rollout_run_not_found")
    return _row_to_rollout_record(row)


def start_kernel_primary_rollout(
    db: Database,
    *,
    stage: str,
    client_ids: list[str],
    note: str = "",
) -> KernelPrimaryRolloutRunRecord:
    ensure_kernel_primary_rollout_schema(db)
    normalized_ids = [str(item).strip() for item in client_ids if str(item).strip()]
    if not normalized_ids:
        raise ValueError("kernel_primary_rollout_client_ids_required")

    metrics_before = collect_kernel_primary_rollout_metrics(
        db,
        client_ids=normalized_ids,
        since=None,
    )
    timestamp = _now_iso()
    run_id = new_id("kproll")
    db.execute(
        """
        INSERT INTO kernel_primary_rollout_runs(
            id, stage, client_ids_json, status,
            metrics_before_json, metrics_after_json, verdict, recommended_action,
            note, rollback_reason, started_at, completed_at, created_at, updated_at
        )
        VALUES(?, ?, ?, 'running', ?, '{}', NULL, NULL, ?, NULL, ?, NULL, ?, ?)
        """,
        (
            run_id,
            stage,
            to_json(normalized_ids),
            to_json(metrics_before),
            (note or "").strip(),
            timestamp,
            timestamp,
            timestamp,
        ),
    )

    # Rollout starts by enabling workspace primary and updating retrieval gate settings.
    db.set_setting("workspace_chat_data_center_primary", "1")
    save_retrieval_model_settings(
        db,
        RetrievalModelSettingsPayload(
            chatKernelPrimaryEnabled=True,
            chatKernelPrimaryClientAllowlist=normalized_ids,
        ),
    )
    # save_retrieval_model_settings merges payload with existing settings.

    return get_kernel_primary_rollout_run(db, run_id=run_id)


def complete_kernel_primary_rollout(
    db: Database,
    *,
    run_id: str,
) -> KernelPrimaryRolloutRunRecord:
    run = get_kernel_primary_rollout_run(db, run_id=run_id)
    if run.status not in {"running", "planned"}:
        raise ValueError("kernel_primary_rollout_run_not_active")

    metrics_after = collect_kernel_primary_rollout_metrics(
        db,
        client_ids=run.clientIds,
        since=run.startedAt,
    )
    workspace_value_metrics = _collect_workspace_value_metrics(
        db,
        client_ids=run.clientIds,
        since=run.startedAt,
    )
    metrics_after.update(workspace_value_metrics)
    metrics_before = run.metricsBefore if isinstance(run.metricsBefore, dict) else {}
    before_p95 = float(metrics_before.get("p95LatencyMs") or 0.0)
    after_p95 = float(metrics_after.get("p95LatencyMs") or 0.0)
    fallback_rate = float(metrics_after.get("kernelPrimaryFallbackRate") or 0.0)
    answer_quality_fail_rate = float(metrics_after.get("answerQualityFailRate") or 0.0)
    official_boundary_violation = int(metrics_after.get("officialBoundaryViolation") or 0)
    candidate_boundary_violation = int(metrics_after.get("candidateBoundaryViolation") or 0)
    workspace_retry_banner_rate = float(metrics_after.get("workspaceRetryBannerRate") or 0.0)
    workspace_ready_or_usable_rate = float(metrics_after.get("workspaceReadyOrUsableRate") or 0.0)
    workspace_needs_retry_rate = float(metrics_after.get("workspaceNeedsRetryRate") or 0.0)
    workspace_kernel_primary_used_rate = float(metrics_after.get("workspaceKernelPrimaryUsedRate") or 0.0)
    human_review_count = int(metrics_after.get("humanReviewCount") or 0)

    verdict = "pass"
    recommended_action = "keep"
    if (
        fallback_rate > 0.2
        or workspace_retry_banner_rate > 0.2
        or (workspace_ready_or_usable_rate < 0.75 and workspace_needs_retry_rate > 0.10)
        or answer_quality_fail_rate > 0.1
        or official_boundary_violation > 0
        or candidate_boundary_violation > 0
        or (before_p95 > 0 and after_p95 > before_p95 * 1.5)
    ):
        verdict = "fail"
        recommended_action = "rollback"
    elif (
        fallback_rate > 0.15
        or workspace_retry_banner_rate > 0.10
        or workspace_ready_or_usable_rate < 0.75
        or workspace_kernel_primary_used_rate < 0.80
        or human_review_count < 10
        or answer_quality_fail_rate > 0.05
        or (before_p95 > 0 and after_p95 > before_p95 * 1.3)
    ):
        verdict = "watch"
        recommended_action = "keep"

    completed_at = _now_iso()
    status = "completed" if verdict in {"pass", "watch"} else "failed"
    db.execute(
        """
        UPDATE kernel_primary_rollout_runs
        SET status = ?,
            metrics_after_json = ?,
            verdict = ?,
            recommended_action = ?,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            to_json(metrics_after),
            verdict,
            recommended_action,
            completed_at,
            completed_at,
            run.id,
        ),
    )
    return get_kernel_primary_rollout_run(db, run_id=run.id)


def rollback_kernel_primary_rollout(
    db: Database,
    *,
    run_id: str,
    reason: str = "",
) -> KernelPrimaryRolloutRunRecord:
    run = get_kernel_primary_rollout_run(db, run_id=run_id)

    # Disable both workspace and retrieval kernel-primary gate.
    db.set_setting("workspace_chat_data_center_primary", "0")
    save_retrieval_model_settings(
        db,
        RetrievalModelSettingsPayload(
            chatKernelPrimaryEnabled=False,
            chatKernelPrimaryClientAllowlist=[],
        ),
    )
    timestamp = _now_iso()
    db.execute(
        """
        UPDATE kernel_primary_rollout_runs
        SET status = 'rolled_back',
            rollback_reason = ?,
            completed_at = COALESCE(completed_at, ?),
            updated_at = ?
        WHERE id = ?
        """,
        (
            (reason or "").strip(),
            timestamp,
            timestamp,
            run.id,
        ),
    )
    return get_kernel_primary_rollout_run(db, run_id=run.id)
