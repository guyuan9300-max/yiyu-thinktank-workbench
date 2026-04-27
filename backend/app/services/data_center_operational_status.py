from __future__ import annotations

import json
import os
from pathlib import Path

from app.db import Database
from app.models import DataCenterOperationalStatusRecord
from app.services.evidence_quality_feedback_snapshot import list_evidence_quality_feedback_snapshots
from app.services.execution_retry_metrics import get_execution_retry_metrics
from app.services.kernel_primary_rollout import list_kernel_primary_rollout_runs


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_output_dir() -> Path:
    override = str(os.getenv("YIYU_DATA_CENTER_OUTPUT_DIR") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "output"


def _strict_report_from_full(full_report: dict[str, object] | None, key: str) -> dict[str, object] | None:
    if not isinstance(full_report, dict):
        return None
    eval_payload = full_report.get("eval")
    if not isinstance(eval_payload, dict):
        return None
    candidate = eval_payload.get(key)
    return candidate if isinstance(candidate, dict) else None


def _p22_strict_pass(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    return bool(
        payload.get("officialBoundaryPass") is True
        and payload.get("candidateBoundaryPass") is True
        and int(payload.get("failureCount") or 0) == 0
    )


def _p23_strict_pass(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    checks = [
        float(payload.get("proposalApprovalPassRate") or 0.0) >= 0.9,
        float(payload.get("executionTicketPassRate") or 0.0) >= 0.9,
        float(payload.get("executionRetryPassRate") or 0.0) >= 0.8,
        float(payload.get("meetingFollowupExecutionPassRate") or 0.0) >= 0.8,
        float(payload.get("kernelChatPrimaryPassRate") or 0.0) >= 0.85,
        float(payload.get("evidenceQualityFeedbackPassRate") or 0.0) >= 0.75,
        float(payload.get("externalEvidenceReviewPassRate") or 0.0) >= 0.8,
        bool(payload.get("opsPanelContractPass")) is True,
        bool(payload.get("officialBoundaryPass")) is True,
        bool(payload.get("candidateBoundaryPass")) is True,
        bool(payload.get("noAutoExecutionViolation")) is True,
        bool(payload.get("kernelPrimaryGateEmptyAllowlistPass")) is True,
        int(payload.get("failureCount") or 0) == 0,
    ]
    return all(checks)


def _latest_rollout_status(db: Database) -> tuple[str, str]:
    runs = list_kernel_primary_rollout_runs(db, limit=1)
    if not runs:
        return "not_started", "hold"
    latest = runs[0]
    if latest.verdict:
        return latest.stage, latest.verdict
    if latest.status in {"failed", "rolled_back"}:
        return latest.stage, "fail"
    if latest.status in {"running", "planned"}:
        return latest.stage, "watch"
    if latest.status == "completed":
        return latest.stage, "pass"
    return latest.stage, "hold"


def build_data_center_operational_status(
    db: Database,
    *,
    client_id: str | None = None,
) -> DataCenterOperationalStatusRecord:
    output_dir = _resolve_output_dir()
    full_report = _read_json(output_dir / "P2.5-full-regression-report.json")
    p22_report = _read_json(output_dir / "P2.6-eval-p22-strict.json")
    p23_report = _read_json(output_dir / "P2.6-eval-p23-strict.json")
    if p22_report is None:
        p22_report = _strict_report_from_full(full_report, "eval_data_center_realistic_p22_strict")
    if p23_report is None:
        p23_report = _strict_report_from_full(full_report, "eval_data_center_p23_strict")

    release_report = _read_json(output_dir / "P2.6-RC2-operational-release-report.json")
    rollback_report = _read_json(output_dir / "P2.6-rollback-drill-report.json")

    full_regression_verdict = "unknown"
    if isinstance(full_report, dict):
        full_regression_verdict = str(full_report.get("verdict") or "unknown")
        if full_regression_verdict not in {"pass", "fail", "hold", "unknown"}:
            full_regression_verdict = "unknown"

    release_verdict = "unknown"
    blocking_issues: list[str] = []
    if isinstance(release_report, dict):
        release_verdict = str(release_report.get("verdict") or "unknown")
        if release_verdict not in {"pass", "fail", "hold", "unknown"}:
            release_verdict = "unknown"
        raw_issues = release_report.get("blockingIssues")
        if isinstance(raw_issues, list):
            blocking_issues = [str(item) for item in raw_issues if str(item).strip()]

    rollout_stage, rollout_latest_verdict = _latest_rollout_status(db)

    retry_metrics = get_execution_retry_metrics(db, client_id=client_id, days=7)
    retry_alerts = [item.message for item in retry_metrics.alerts]

    snapshots = list_evidence_quality_feedback_snapshots(db, limit=1)
    latest_snapshot_at = snapshots[0].createdAt if snapshots else None

    rollback_drill_pass = bool(
        isinstance(rollback_report, dict)
        and str(rollback_report.get("verdict") or "") == "pass"
    )

    return DataCenterOperationalStatusRecord(
        fullRegressionVerdict=full_regression_verdict,  # type: ignore[arg-type]
        p22StrictPass=_p22_strict_pass(p22_report),
        p23StrictPass=_p23_strict_pass(p23_report),
        rolloutStage=rollout_stage,
        rolloutLatestVerdict=rollout_latest_verdict,
        retryAlerts=retry_alerts,
        latestSnapshotAt=latest_snapshot_at,
        rollbackDrillPass=rollback_drill_pass,
        releaseReportVerdict=release_verdict,  # type: ignore[arg-type]
        blockingIssues=blocking_issues,
    )
