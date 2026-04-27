from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.artifact_utils import stamp_artifact


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _p22_strict_pass(payload: dict[str, object] | None) -> bool:
    if not payload:
        return False
    return bool(
        bool(payload.get("officialBoundaryPass"))
        and bool(payload.get("candidateBoundaryPass"))
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


def _collect_db_stats(db_path: Path) -> dict[str, object]:
    stats: dict[str, object] = {
        "dbAvailable": False,
        "executionRetryMetricsAvailable": False,
    }
    if not db_path.exists():
        return stats

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    stats["dbAvailable"] = True
    try:
        row = conn.execute(
            """
            SELECT
              COUNT(1) AS total_tickets,
              SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END) AS retried_tickets
            FROM execution_tickets
            """
        ).fetchone()
        stats["executionRetryMetricsAvailable"] = bool(
            row is not None
            and (
                int(row["total_tickets"] or 0) >= 0
                or int(row["retried_tickets"] or 0) > 0
            )
        )
    except sqlite3.Error:
        stats["executionRetryMetricsAvailable"] = False
    finally:
        conn.close()
    return stats


def run_eval(output_dir: Path) -> dict[str, object]:
    failures: list[dict[str, object]] = []
    default_data_dir = Path(
        os.getenv("YIYU_WORKBENCH_DATA_DIR")
        or (Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench")
    )
    db_stats = _collect_db_stats(default_data_dir / "app.db")

    full_regression = _read_json(output_dir / "P2.5-full-regression-report.json")
    p22_report = _read_json(output_dir / "P2.6-eval-p22-strict.json")
    p23_report = _read_json(output_dir / "P2.6-eval-p23-strict.json")
    if p22_report is None and isinstance(full_regression, dict):
        eval_payload = full_regression.get("eval")
        if isinstance(eval_payload, dict):
            candidate = eval_payload.get("eval_data_center_realistic_p22_strict")
            if isinstance(candidate, dict):
                p22_report = candidate
    if p23_report is None and isinstance(full_regression, dict):
        eval_payload = full_regression.get("eval")
        if isinstance(eval_payload, dict):
            candidate = eval_payload.get("eval_data_center_p23_strict")
            if isinstance(candidate, dict):
                p23_report = candidate

    rollout_report = _read_json(output_dir / "P2.6-kernel-primary-rollout-report.json")
    rollback_report = _read_json(output_dir / "P2.6-rollback-drill-report.json")
    snapshot_report = _read_json(output_dir / "P2.6-evidence-quality-snapshot-report.json")

    full_regression_pass = bool(full_regression and str(full_regression.get("verdict") or "") == "pass")
    p22_strict_pass = _p22_strict_pass(p22_report)
    p23_strict_pass = _p23_strict_pass(p23_report)

    stage_summary = rollout_report.get("stageSummary") if isinstance(rollout_report, dict) else []
    if not isinstance(stage_summary, list):
        stage_summary = []
    rollout_started = bool(stage_summary)
    rollout_completed = any(str(item.get("status") or "") == "completed" for item in stage_summary if isinstance(item, dict))

    rollback_drill_pass = bool(rollback_report and str(rollback_report.get("verdict") or "") == "pass")
    evidence_snapshot_exists = bool(snapshot_report and snapshot_report.get("snapshotExists") is True)
    execution_retry_metrics_available = bool(db_stats.get("executionRetryMetricsAvailable"))

    ops_panel_contract_pass = p23_strict_pass

    checks = {
        "fullRegressionPass": full_regression_pass,
        "p22StrictPass": p22_strict_pass,
        "p23StrictPass": p23_strict_pass,
        "rolloutStarted": rollout_started,
        "rolloutCompleted": rollout_completed,
        "rollbackDrillPass": rollback_drill_pass,
        "evidenceSnapshotExists": evidence_snapshot_exists,
        "executionRetryMetricsAvailable": execution_retry_metrics_available,
        "opsPanelContractPass": ops_panel_contract_pass,
    }

    for key, passed in checks.items():
        if not passed:
            failures.append(
                {
                    "id": key,
                    "category": "operational_artifact",
                    "reason": f"{key} is false",
                    "expected": {"value": True},
                    "actual": {"value": passed},
                }
            )

    release_report_verdict = "pass" if not failures else "hold"
    return stamp_artifact(
        {
        "fullRegressionPass": full_regression_pass,
        "p22StrictPass": p22_strict_pass,
        "p23StrictPass": p23_strict_pass,
        "rolloutStarted": rollout_started,
        "rolloutCompleted": rollout_completed,
        "rollbackDrillPass": rollback_drill_pass,
        "evidenceSnapshotExists": evidence_snapshot_exists,
        "executionRetryMetricsAvailable": execution_retry_metrics_available,
        "opsPanelContractPass": ops_panel_contract_pass,
        "releaseReportVerdict": release_report_verdict,
        "dbStats": db_stats,
        "failureCount": len(failures),
        "failures": failures,
        },
        "p26_operational_eval",
    )


def _write_outputs(report: dict[str, object], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "P2.6-operational-eval.json"
    md_path = output_dir / "P2.6-operational-eval.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Data Center P2.6 Operational Eval",
        "",
        f"- generatedAt: `{report.get('generatedAt')}`",
        f"- verdict: `{report.get('releaseReportVerdict')}`",
        f"- failureCount: `{report.get('failureCount')}`",
        "",
        "## Checks",
    ]
    for key in (
        "fullRegressionPass",
        "p22StrictPass",
        "p23StrictPass",
        "rolloutStarted",
        "rolloutCompleted",
        "rollbackDrillPass",
        "evidenceSnapshotExists",
        "executionRetryMetricsAvailable",
        "opsPanelContractPass",
    ):
        lines.append(f"- {key}: `{report.get(key)}`")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"jsonPath": str(json_path), "markdownPath": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate P2.6 operational artifacts and release readiness.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "output"),
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    report = run_eval(output_dir)
    artifacts = _write_outputs(report, output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"artifacts": artifacts}, ensure_ascii=False))

    if args.strict and int(report.get("failureCount") or 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
