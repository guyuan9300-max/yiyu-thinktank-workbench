from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.artifact_utils import stamp_artifact


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _collect_db_stats(db_path: Path) -> dict[str, object]:
    stats: dict[str, object] = {
        "dbAvailable": False,
        "rolloutRuns": [],
        "executionRetryMetrics": {},
        "evidenceQualitySnapshots": [],
    }
    if not db_path.exists():
        return stats

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    stats["dbAvailable"] = True
    try:
        rollout_rows = conn.execute(
            """
            SELECT id, stage, status, verdict, recommended_action, created_at, updated_at
            FROM kernel_primary_rollout_runs
            ORDER BY created_at DESC
            LIMIT 20
            """
        ).fetchall()
        stats["rolloutRuns"] = [
            {
                "id": str(row["id"]),
                "stage": str(row["stage"]),
                "status": str(row["status"]),
                "verdict": str(row["verdict"]) if row["verdict"] else None,
                "recommendedAction": str(row["recommended_action"]) if row["recommended_action"] else None,
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in rollout_rows
        ]
    except sqlite3.Error:
        stats["rolloutRuns"] = []

    try:
        row = conn.execute(
            """
            SELECT
              COUNT(1) AS total_tickets,
              SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_tickets,
              SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END) AS retried_tickets,
              SUM(CASE WHEN status = 'failed' AND retry_count >= max_retries THEN 1 ELSE 0 END) AS retry_exhausted_tickets
            FROM execution_tickets
            """
        ).fetchone()
        stats["executionRetryMetrics"] = {
            "totalTickets": int(row["total_tickets"] or 0),
            "failedTickets": int(row["failed_tickets"] or 0),
            "retriedTickets": int(row["retried_tickets"] or 0),
            "retryExhaustedTickets": int(row["retry_exhausted_tickets"] or 0),
        }
    except sqlite3.Error:
        stats["executionRetryMetrics"] = {}

    try:
        snapshot_rows = conn.execute(
            """
            SELECT id, window_start, window_end, created_at
            FROM evidence_quality_feedback_snapshots
            ORDER BY created_at DESC
            LIMIT 20
            """
        ).fetchall()
        stats["evidenceQualitySnapshots"] = [
            {
                "id": str(row["id"]),
                "windowStart": str(row["window_start"]),
                "windowEnd": str(row["window_end"]),
                "createdAt": str(row["created_at"]),
            }
            for row in snapshot_rows
        ]
    except sqlite3.Error:
        stats["evidenceQualitySnapshots"] = []

    conn.close()
    return stats


def _strict_eval_from_full_report(full_report: dict[str, object] | None, key: str) -> dict[str, object] | None:
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


def _render_markdown(payload: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Data Center RC2 Operational Release Report (P2.6)")
    lines.append("")
    lines.append(f"- generatedAt: `{payload.get('generatedAt')}`")
    lines.append(f"- verdict: `{payload.get('verdict')}`")
    lines.append("")

    lines.append("## Required Artifacts")
    required = payload.get("requiredArtifacts") if isinstance(payload.get("requiredArtifacts"), dict) else {}
    for key, value in required.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")

    lines.append("## Blocking Issues")
    blocking = payload.get("blockingIssues") if isinstance(payload.get("blockingIssues"), list) else []
    if not blocking:
        lines.append("- (none)")
    else:
        for item in blocking:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("## Rollout Snapshot")
    db_stats = payload.get("dbStats") if isinstance(payload.get("dbStats"), dict) else {}
    rollout_runs = db_stats.get("rolloutRuns") if isinstance(db_stats.get("rolloutRuns"), list) else []
    lines.append(f"- rolloutRuns: `{len(rollout_runs)}`")
    if rollout_runs:
        latest = rollout_runs[0]
        if isinstance(latest, dict):
            lines.append(
                f"- latest: `{latest.get('stage')}/{latest.get('status')}/verdict={latest.get('verdict')}`"
            )
    lines.append("")

    lines.append("## Retry / Snapshot")
    retry_metrics = db_stats.get("executionRetryMetrics") if isinstance(db_stats.get("executionRetryMetrics"), dict) else {}
    lines.append(f"- executionRetryMetrics: `{json.dumps(retry_metrics, ensure_ascii=False)}`")
    snapshots = db_stats.get("evidenceQualitySnapshots") if isinstance(db_stats.get("evidenceQualitySnapshots"), list) else []
    lines.append(f"- evidenceQualitySnapshots: `{len(snapshots)}`")
    lines.append("")

    lines.append("## Eval")
    lines.append(f"- p22StrictPass: `{payload.get('p22StrictPass')}`")
    lines.append(f"- p23StrictPass: `{payload.get('p23StrictPass')}`")
    return "\n".join(lines)


def main() -> int:
    script_path = Path(__file__).resolve()
    backend_root = script_path.parents[1]
    output_dir = backend_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = output_dir / "P2.4-baseline.json"
    full_report_path = output_dir / "P2.5-full-regression-report.json"
    rollout_report_path = output_dir / "P2.6-kernel-primary-rollout-report.json"
    rollback_report_path = output_dir / "P2.6-rollback-drill-report.json"
    snapshot_report_path = output_dir / "P2.6-evidence-quality-snapshot-report.json"
    p22_strict_path = output_dir / "P2.6-eval-p22-strict.json"
    p23_strict_path = output_dir / "P2.6-eval-p23-strict.json"
    operational_eval_path = output_dir / "P2.6-operational-eval.json"
    workspace_value_report_path = output_dir / "P2.9-customer-workspace-value-report.json"
    runtime_alignment_report_path = output_dir / "P2.9-runtime-value-alignment-report.json"

    default_data_dir = Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR")
        or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench")
    )
    db_path = default_data_dir / "app.db"

    baseline_payload = _read_json(baseline_path)
    full_report_payload = _read_json(full_report_path)
    rollout_payload = _read_json(rollout_report_path)
    rollback_payload = _read_json(rollback_report_path)
    snapshot_payload = _read_json(snapshot_report_path)
    p22_payload = _read_json(p22_strict_path)
    p23_payload = _read_json(p23_strict_path)
    operational_eval_payload = _read_json(operational_eval_path)
    workspace_value_payload = _read_json(workspace_value_report_path)
    runtime_alignment_payload = _read_json(runtime_alignment_report_path)

    if p22_payload is None:
        p22_payload = _strict_eval_from_full_report(full_report_payload, "eval_data_center_realistic_p22_strict")
    if p23_payload is None:
        p23_payload = _strict_eval_from_full_report(full_report_payload, "eval_data_center_p23_strict")

    db_stats = _collect_db_stats(db_path)
    rollout_runs = db_stats.get("rolloutRuns") if isinstance(db_stats.get("rolloutRuns"), list) else []
    retry_metrics = db_stats.get("executionRetryMetrics") if isinstance(db_stats.get("executionRetryMetrics"), dict) else {}
    snapshots = db_stats.get("evidenceQualitySnapshots") if isinstance(db_stats.get("evidenceQualitySnapshots"), list) else []

    required_artifacts = {
        "fullRegression": bool(full_report_payload and str(full_report_payload.get("verdict") or "") == "pass"),
        "p22Strict": _p22_strict_pass(p22_payload),
        "p23Strict": _p23_strict_pass(p23_payload),
        "rolloutReport": bool(rollout_payload and isinstance(rollout_payload.get("stageSummary"), list)),
        "rollbackDrill": bool(rollback_payload and str(rollback_payload.get("verdict") or "") == "pass"),
        "evidenceSnapshot": bool(snapshot_payload and snapshot_payload.get("snapshotExists") is True),
        "executionRetryMetrics": bool(isinstance(retry_metrics, dict)),
        "customerWorkspaceValueReport": bool(workspace_value_payload),
        "operationalEval": bool(operational_eval_payload and int(operational_eval_payload.get("failureCount") or 0) == 0),
        "runtimeAlignment": bool(runtime_alignment_payload and str(runtime_alignment_payload.get("verdict") or "") == "pass"),
    }

    blocking_issues: list[str] = []
    if not required_artifacts["fullRegression"]:
        blocking_issues.append("full regression report missing or verdict != pass")
    if not required_artifacts["p22Strict"]:
        blocking_issues.append("p22 strict result missing or not pass")
    if not required_artifacts["p23Strict"]:
        blocking_issues.append("p23 strict result missing or not pass")
    if not required_artifacts["rolloutReport"]:
        blocking_issues.append("rollout report missing")
    if not rollout_runs:
        blocking_issues.append("rolloutRuns = 0")
    if not required_artifacts["rollbackDrill"]:
        blocking_issues.append("rollback drill report missing or verdict != pass")
    if not required_artifacts["evidenceSnapshot"]:
        blocking_issues.append("evidence quality snapshot report missing or no snapshot")
    if not required_artifacts["executionRetryMetrics"]:
        blocking_issues.append("execution retry metrics unavailable")
    if not snapshots:
        blocking_issues.append("evidenceQualitySnapshots = 0")
    if not required_artifacts["operationalEval"]:
        blocking_issues.append("operational eval missing or not pass")
    if not required_artifacts["runtimeAlignment"]:
        blocking_issues.append("runtime alignment missing or not pass")
    if workspace_value_payload and str(workspace_value_payload.get("verdict") or "hold") != "pass":
        blocking_issues.append("customer workspace value report not pass")

    verdict = "pass" if not blocking_issues else "hold"

    payload = stamp_artifact(
        {
        "generatedAt": _now_iso(),
        "baseline": baseline_payload,
        "dbPath": str(db_path),
        "dbStats": db_stats,
        "p22StrictPass": required_artifacts["p22Strict"],
        "p23StrictPass": required_artifacts["p23Strict"],
        "requiredArtifacts": required_artifacts,
        "blockingIssues": blocking_issues,
        "executionRetryMetrics": retry_metrics,
        "rolloutRuns": rollout_runs,
        "evidenceQualitySnapshots": snapshots,
        "operationalEval": operational_eval_payload or {},
        "runtimeAlignment": runtime_alignment_payload or {},
        "customerWorkspaceValueReport": workspace_value_payload or {},
        "verdict": verdict,
        },
        "p26_rc2_operational_release_report",
    )

    md_path = output_dir / "P2.6-RC2-operational-release-report.md"
    json_path = output_dir / "P2.6-RC2-operational-release-report.json"
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Keep P2.5 path for compatibility.
    legacy_md_path = output_dir / "P2.5-RC2-release-report.md"
    legacy_md_path.write_text(_render_markdown(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "reportMarkdown": str(md_path),
                "reportJson": str(json_path),
                "verdict": verdict,
                "blockingIssues": blocking_issues,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
