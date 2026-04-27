from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.eval_data_center_p23 import run_eval


def test_data_center_p23_eval_report_shape():
    fixtures = Path(__file__).resolve().parents[0] / "fixtures" / "data_center_p23_eval_cases.json"
    report = run_eval(fixtures=fixtures, mode="baseline")

    assert report["caseCount"] >= 1
    assert "proposalApprovalPassRate" in report
    assert "executionTicketPassRate" in report
    assert "executionRetryPassRate" in report
    assert "meetingFollowupExecutionPassRate" in report
    assert "kernelChatPrimaryPassRate" in report
    assert "evidenceQualityFeedbackPassRate" in report
    assert "externalEvidenceReviewPassRate" in report
    assert "opsPanelContractPass" in report
    assert isinstance(report.get("officialBoundaryPass"), bool)
    assert isinstance(report.get("candidateBoundaryPass"), bool)
    assert isinstance(report.get("noAutoExecutionViolation"), bool)
    assert isinstance(report.get("kernelPrimaryGateEmptyAllowlistPass"), bool)
    assert isinstance(report.get("failures"), list)
