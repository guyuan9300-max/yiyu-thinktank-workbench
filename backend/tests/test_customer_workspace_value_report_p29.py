from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.generate_customer_workspace_release_report_p27 import build_release_report, write_release_report  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def test_customer_workspace_value_report_p29_writes_new_artifacts_and_holds_without_reviews(tmp_path: Path):
    output_dir = tmp_path / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / 'P2.7-baseline.json', {'generatedAt': '2026-04-21T10:00:00'})
    _write_json(
        output_dir / 'P2.7-customer-workspace-value-eval.json',
        {
            'usableAnswerRate': 0.9,
            'readyOrUsableRate': 0.9,
            'retryBannerRate': 0.0,
            'needsRetryRate': 0.0,
            'groundedAnswerPassRate': 0.9,
            'businessStrategySlotHitRate': 0.9,
            'kernelPrimaryUsedRate': 0.9,
            'answerTooTemplateLikeRate': 0.0,
            'evidenceSupportedRate': 0.9,
            'officialBoundaryPass': True,
            'candidateBoundaryPass': True,
            'failureCount': 0,
        },
    )
    _write_json(output_dir / 'P2.7-workspace-answer-value-summary.json', {'reviewCount': 0})
    _write_json(output_dir / 'P2.9-runtime-value-alignment-report.json', {'verdict': 'pass'})
    _write_json(output_dir / 'P2.6-operational-eval.json', {'failureCount': 0, 'releaseReportVerdict': 'pass'})
    _write_json(output_dir / 'P2.6-eval-p22-strict.json', {'officialBoundaryPass': True, 'candidateBoundaryPass': True, 'failureCount': 0})
    _write_json(
        output_dir / 'P2.6-eval-p23-strict.json',
        {
            'proposalApprovalPassRate': 1.0,
            'executionTicketPassRate': 1.0,
            'executionRetryPassRate': 1.0,
            'meetingFollowupExecutionPassRate': 1.0,
            'kernelChatPrimaryPassRate': 1.0,
            'evidenceQualityFeedbackPassRate': 1.0,
            'externalEvidenceReviewPassRate': 1.0,
            'opsPanelContractPass': True,
            'officialBoundaryPass': True,
            'candidateBoundaryPass': True,
            'noAutoExecutionViolation': True,
            'kernelPrimaryGateEmptyAllowlistPass': True,
            'failureCount': 0,
        },
    )

    payload = build_release_report(output_dir)
    assert payload['verdict'] == 'hold'
    assert 'missing workspace answer human review' in payload['blockingIssues']

    artifacts = write_release_report(payload, output_dir)
    assert Path(artifacts['p29JsonPath']).exists()
    assert Path(artifacts['p29MarkdownPath']).exists()


def test_customer_workspace_value_report_p29_fails_on_boundary_violation(tmp_path: Path):
    output_dir = tmp_path / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / 'P2.7-baseline.json', {'generatedAt': '2026-04-21T10:00:00'})
    _write_json(
        output_dir / 'P2.7-customer-workspace-value-eval.json',
        {
            'usableAnswerRate': 0.9,
            'readyOrUsableRate': 0.9,
            'retryBannerRate': 0.0,
            'needsRetryRate': 0.0,
            'groundedAnswerPassRate': 0.9,
            'businessStrategySlotHitRate': 0.9,
            'kernelPrimaryUsedRate': 0.9,
            'answerTooTemplateLikeRate': 0.0,
            'evidenceSupportedRate': 0.9,
            'officialBoundaryPass': False,
            'candidateBoundaryPass': True,
            'failureCount': 1,
        },
    )
    _write_json(
        output_dir / 'P2.7-workspace-answer-value-summary.json',
        {
            'reviewCount': 12,
            'averageManualBaselineMinutes': 20,
            'averageDataCenterReviewMinutes': 8,
            'estimatedTimeSavedRate': 0.6,
        },
    )
    _write_json(output_dir / 'P2.9-runtime-value-alignment-report.json', {'verdict': 'pass'})
    _write_json(output_dir / 'P2.6-operational-eval.json', {'failureCount': 0, 'releaseReportVerdict': 'pass'})
    _write_json(output_dir / 'P2.6-eval-p22-strict.json', {'officialBoundaryPass': True, 'candidateBoundaryPass': True, 'failureCount': 0})
    _write_json(
        output_dir / 'P2.6-eval-p23-strict.json',
        {
            'proposalApprovalPassRate': 1.0,
            'executionTicketPassRate': 1.0,
            'executionRetryPassRate': 1.0,
            'meetingFollowupExecutionPassRate': 1.0,
            'kernelChatPrimaryPassRate': 1.0,
            'evidenceQualityFeedbackPassRate': 1.0,
            'externalEvidenceReviewPassRate': 1.0,
            'opsPanelContractPass': True,
            'officialBoundaryPass': True,
            'candidateBoundaryPass': True,
            'noAutoExecutionViolation': True,
            'kernelPrimaryGateEmptyAllowlistPass': True,
            'failureCount': 0,
        },
    )

    payload = build_release_report(output_dir)
    assert payload['verdict'] == 'fail'
