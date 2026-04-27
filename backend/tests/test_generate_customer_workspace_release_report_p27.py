from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.generate_customer_workspace_release_report_p27 import build_release_report, write_release_report


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_generate_customer_workspace_release_report_p27_pass(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "P2.7-baseline.json", {"generatedAt": "2026-04-21T10:00:00"})
    _write_json(
        output_dir / "P2.7-customer-workspace-value-eval.json",
        {
            "usableAnswerRate": 0.9,
            "readyOrUsableRate": 0.9,
            "retryBannerRate": 0.05,
            "needsRetryRate": 0.05,
            "groundedAnswerPassRate": 0.9,
            "businessStrategySlotHitRate": 0.9,
            "kernelPrimaryUsedRate": 0.9,
            "answerTooTemplateLikeRate": 0.05,
            "evidenceSupportedRate": 0.9,
            "officialBoundaryPass": True,
            "candidateBoundaryPass": True,
            "failureCount": 0,
        },
    )
    _write_json(
        output_dir / "P2.7-workspace-answer-value-summary.json",
        {
            "reviewCount": 12,
            "usableAnswerRate": 0.9,
            "retryBannerRate": 0.05,
            "averageManualBaselineMinutes": 20.0,
            "averageDataCenterReviewMinutes": 8.0,
            "estimatedTimeSavedRate": 0.6,
            "positiveReviewCount": 10,
            "negativeReviewCount": 2,
            "lastReviewedAt": "2026-04-21T11:00:00",
        },
    )
    _write_json(output_dir / "P2.7-repo-package-alignment-report.json", {"verdict": "pass"})
    _write_json(
        output_dir / "P2.5-full-regression-report.json",
        {
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
        },
    )
    _write_json(
        output_dir / "P2.6-operational-eval.json",
        {
            "failureCount": 0,
            "releaseReportVerdict": "pass",
        },
    )

    payload = build_release_report(output_dir)
    assert payload["verdict"] == "pass"
    assert payload["requiredArtifacts"]["valueEval"] is True

    artifacts = write_release_report(payload, output_dir)
    assert Path(artifacts["jsonPath"]).exists()
    assert Path(artifacts["markdownPath"]).exists()


def test_generate_customer_workspace_release_report_p27_hold(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "P2.7-customer-workspace-value-eval.json", {"failureCount": 1})

    payload = build_release_report(output_dir)
    assert payload["verdict"] == "hold"
    assert payload["blockingIssues"]


def test_generate_customer_workspace_release_report_p27_reads_multijson_strict_artifact(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "P2.7-baseline.json", {"generatedAt": "2026-04-21T10:00:00"})
    _write_json(
        output_dir / "P2.7-customer-workspace-value-eval.json",
        {
            "usableAnswerRate": 0.9,
            "readyOrUsableRate": 0.9,
            "retryBannerRate": 0.05,
            "needsRetryRate": 0.05,
            "groundedAnswerPassRate": 0.9,
            "businessStrategySlotHitRate": 0.9,
            "kernelPrimaryUsedRate": 0.9,
            "answerTooTemplateLikeRate": 0.05,
            "evidenceSupportedRate": 0.9,
            "officialBoundaryPass": True,
            "candidateBoundaryPass": True,
            "failureCount": 0,
        },
    )
    _write_json(
        output_dir / "P2.7-workspace-answer-value-summary.json",
        {
            "reviewCount": 12,
            "usableAnswerRate": 0.9,
            "retryBannerRate": 0.05,
            "averageManualBaselineMinutes": 20.0,
            "averageDataCenterReviewMinutes": 8.0,
            "estimatedTimeSavedRate": 0.6,
            "positiveReviewCount": 10,
            "negativeReviewCount": 2,
            "lastReviewedAt": "2026-04-21T11:00:00",
        },
    )
    _write_json(output_dir / "P2.7-repo-package-alignment-report.json", {"verdict": "pass"})
    _write_json(
        output_dir / "P2.6-operational-eval.json",
        {
            "failureCount": 0,
            "releaseReportVerdict": "pass",
        },
    )
    _write_json(
        output_dir / "P2.6-eval-p22-strict.json",
        {
            "officialBoundaryPass": True,
            "candidateBoundaryPass": True,
            "failureCount": 0,
        },
    )
    (output_dir / "P2.6-eval-p23-strict.json").write_text(
        json.dumps(
            {
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
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
        + json.dumps({"strictGate": "passed"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    payload = build_release_report(output_dir)
    assert payload["requiredArtifacts"]["p23Strict"] is True


def test_generate_customer_workspace_release_report_p27_zero_retry_banner_is_not_blocking(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "P2.7-baseline.json", {"generatedAt": "2026-04-21T10:00:00"})
    _write_json(
        output_dir / "P2.7-customer-workspace-value-eval.json",
        {
            "usableAnswerRate": 0.95,
            "readyOrUsableRate": 0.95,
            "retryBannerRate": 0.0,
            "needsRetryRate": 0.0,
            "groundedAnswerPassRate": 0.95,
            "businessStrategySlotHitRate": 0.95,
            "kernelPrimaryUsedRate": 0.95,
            "answerTooTemplateLikeRate": 0.0,
            "evidenceSupportedRate": 0.95,
            "officialBoundaryPass": True,
            "candidateBoundaryPass": True,
            "failureCount": 0,
        },
    )
    _write_json(
        output_dir / "P2.7-workspace-answer-value-summary.json",
        {
            "reviewCount": 12,
            "usableAnswerRate": 0.95,
            "retryBannerRate": 0.0,
            "averageManualBaselineMinutes": 18.0,
            "averageDataCenterReviewMinutes": 6.0,
            "estimatedTimeSavedRate": 0.66,
            "positiveReviewCount": 11,
            "negativeReviewCount": 1,
            "lastReviewedAt": "2026-04-21T11:00:00",
        },
    )
    _write_json(output_dir / "P2.7-repo-package-alignment-report.json", {"verdict": "pass"})
    _write_json(
        output_dir / "P2.6-operational-eval.json",
        {
            "failureCount": 0,
            "releaseReportVerdict": "pass",
        },
    )
    _write_json(
        output_dir / "P2.6-eval-p22-strict.json",
        {
            "officialBoundaryPass": True,
            "candidateBoundaryPass": True,
            "failureCount": 0,
        },
    )
    _write_json(
        output_dir / "P2.6-eval-p23-strict.json",
        {
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
    )

    payload = build_release_report(output_dir)
    assert payload["verdict"] == "pass"
    assert "retry banner rate too high" not in payload["blockingIssues"]
