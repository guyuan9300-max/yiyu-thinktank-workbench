from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.generate_customer_workspace_release_report_p27 import build_release_report


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _good_p23_payload() -> dict[str, object]:
    return {
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
    }


def test_release_gate_dag_p210_customer_report_does_not_depend_on_operational_pass(tmp_path: Path):
    output_dir = tmp_path / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / 'P2.7-baseline.json', {'generatedAt': '2026-04-22T09:00:00'})
    _write_json(
        output_dir / 'P2.7-customer-workspace-value-eval.json',
        {
            'usableAnswerRate': 0.95,
            'readyOrUsableRate': 0.95,
            'retryBannerRate': 0.0,
            'needsRetryRate': 0.0,
            'groundedAnswerPassRate': 0.95,
            'businessStrategySlotHitRate': 0.95,
            'kernelPrimaryUsedRate': 0.95,
            'answerTooTemplateLikeRate': 0.0,
            'evidenceSupportedRate': 0.95,
            'officialBoundaryPass': True,
            'candidateBoundaryPass': True,
            'failureCount': 0,
        },
    )
    _write_json(
        output_dir / 'P2.7-workspace-answer-value-summary.json',
        {
            'reviewCount': 12,
            'usableAnswerRate': 0.95,
            'retryBannerRate': 0.0,
            'averageManualBaselineMinutes': 18.0,
            'averageDataCenterReviewMinutes': 6.0,
            'estimatedTimeSavedRate': 0.66,
            'positiveReviewCount': 11,
            'negativeReviewCount': 1,
        },
    )
    _write_json(output_dir / 'P2.9-runtime-value-alignment-report.json', {'verdict': 'pass'})
    _write_json(
        output_dir / 'P2.5-full-regression-report.json',
        {
            'verdict': 'pass',
            'eval': {
                'eval_data_center_realistic_p22_strict': {
                    'officialBoundaryPass': True,
                    'candidateBoundaryPass': True,
                    'failureCount': 0,
                },
                'eval_data_center_p23_strict': _good_p23_payload(),
            },
        },
    )
    _write_json(
        output_dir / 'P2.6-operational-eval.json',
        {
            'failureCount': 3,
            'rollbackDrillPass': False,
            'executionRetryMetricsAvailable': True,
            'opsPanelContractPass': False,
            'releaseReportVerdict': 'hold',
        },
    )

    payload = build_release_report(output_dir)
    assert payload['verdict'] == 'pass'
    assert payload['operationalArtifactsReady'] is False
    assert 'operational eval missing or not pass' not in payload['blockingIssues']


def test_release_gate_dag_p210_operational_eval_does_not_read_release_reports():
    repo_root = Path(__file__).resolve().parents[2]
    operational_script = (repo_root / 'backend' / 'scripts' / 'eval_data_center_operational_p26.py').read_text(encoding='utf-8')
    customer_report_script = (repo_root / 'backend' / 'scripts' / 'generate_customer_workspace_release_report_p27.py').read_text(encoding='utf-8')
    rc_report_script = (repo_root / 'backend' / 'scripts' / 'generate_data_center_rc2_release_report.py').read_text(encoding='utf-8')

    assert 'P2.6-RC2-operational-release-report.json' not in operational_script
    assert 'P2.7-customer-workspace-release-report.json' not in operational_script
    assert 'customer workspace value report not pass' not in customer_report_script
    assert 'P2.6-operational-eval.json' in rc_report_script
    assert 'P2.9-customer-workspace-value-report.json' in rc_report_script

