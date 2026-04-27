from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.eval_data_center_operational_p26 import run_eval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _good_full_regression_payload() -> dict[str, object]:
    return {
        "verdict": "pass",
        "eval": {
            "eval_data_center_realistic_p22_strict": {
                "officialBoundaryPass": True,
                "candidateBoundaryPass": True,
                "failureCount": 0,
            },
            "eval_data_center_p23_strict": {
                "proposalApprovalPassRate": 1.0,
                "executionTicketPassRate": 1.0,
                "executionRetryPassRate": 1.0,
                "meetingFollowupExecutionPassRate": 1.0,
                "kernelChatPrimaryPassRate": 1.0,
                "evidenceQualityFeedbackPassRate": 1.0,
                "externalEvidenceReviewPassRate": 1.0,
                "opsPanelContractPass": True,
                "officialBoundaryPass": True,
                "candidateBoundaryPass": True,
                "noAutoExecutionViolation": True,
                "kernelPrimaryGateEmptyAllowlistPass": True,
                "failureCount": 0,
            },
        },
    }


def test_eval_data_center_operational_p26_pass(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "P2.5-full-regression-report.json", _good_full_regression_payload())
    _write_json(
        output_dir / "P2.6-kernel-primary-rollout-report.json",
        {
            "stageSummary": [{"stage": "stage_1_client", "status": "completed"}],
            "globalSummary": {},
            "decision": "continue",
        },
    )
    _write_json(output_dir / "P2.6-rollback-drill-report.json", {"verdict": "pass"})
    _write_json(output_dir / "P2.6-evidence-quality-snapshot-report.json", {"snapshotExists": True})
    _write_json(
        output_dir / "P2.6-RC2-operational-release-report.json",
        {
            "verdict": "pass",
            "requiredArtifacts": {"executionRetryMetrics": True},
            "executionRetryMetrics": {"totalTickets": 0},
        },
    )

    report = run_eval(output_dir)
    assert report["failureCount"] == 0
    assert report["fullRegressionPass"] is True
    assert report["p22StrictPass"] is True
    assert report["p23StrictPass"] is True
    assert report["rolloutStarted"] is True
    assert report["rolloutCompleted"] is True
    assert report["rollbackDrillPass"] is True
    assert report["evidenceSnapshotExists"] is True
    assert report["executionRetryMetricsAvailable"] is True
    assert report["opsPanelContractPass"] is True
    assert report["releaseReportVerdict"] == "pass"


def test_eval_data_center_operational_p26_missing_artifacts(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # only place a partial report
    _write_json(output_dir / "P2.5-full-regression-report.json", {"verdict": "fail"})

    report = run_eval(output_dir)
    assert report["failureCount"] > 0
    assert report["fullRegressionPass"] is False
    assert report["releaseReportVerdict"] == "hold"
