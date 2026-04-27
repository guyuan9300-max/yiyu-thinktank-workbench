from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.eval_data_center_realistic_p22 import _strict_gate, run_eval


def test_realistic_fixture_has_required_coverage():
    fixtures = Path(__file__).resolve().parents[0] / "fixtures" / "data_center_realistic_eval_cases.json"
    payload = json.loads(fixtures.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) >= 60

    business_slot = sum(1 for item in payload if item.get("mustHaveBusinessSlots"))
    strategy_slot = sum(1 for item in payload if item.get("mustHaveStrategySlots"))
    official_cases = sum(1 for item in payload if item.get("expectedIntent") == "official_judgment_registry")
    meeting_followup = sum(1 for item in payload if item.get("mustGenerateFollowup"))

    assert business_slot >= 10
    assert strategy_slot >= 10
    assert official_cases >= 10
    assert meeting_followup >= 10


def test_realistic_eval_report_meets_release_gate():
    fixtures = Path(__file__).resolve().parents[0] / "fixtures" / "data_center_realistic_eval_cases.json"
    report = run_eval(fixtures=fixtures, mode="baseline")

    assert report["caseCount"] >= 60
    assert "factSlotHitRate" in report
    assert "officialBoundaryPass" in report
    assert "meetingFollowupPassRate" in report
    assert "failureCount" in report
    assert "failures" in report

    ok, reasons = _strict_gate(report)
    assert ok, reasons


def test_strict_gate_rejects_bad_metrics():
    ok, reasons = _strict_gate(
        {
            "factSlotHitRate": 0.5,
            "officialBoundaryPass": False,
            "meetingFollowupPassRate": 0.2,
            "failureCount": 2,
        }
    )
    assert ok is False
    assert "factSlotHitRate < 0.75" in reasons
    assert "officialBoundaryPass != true" in reasons
    assert "meetingFollowupPassRate < 0.75" in reasons
    assert "failureCount > 0" in reasons
