from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.eval_data_center_answer_p1 import run_eval


def test_eval_data_center_answer_p1_outputs_metrics():
    fixtures = Path(__file__).resolve().parents[0] / "fixtures" / "data_center_answer_eval_cases.json"
    report = run_eval(fixtures=fixtures, mode="baseline", client_id="eval_client")
    assert report["caseCount"] >= 4
    assert "intentAccuracy" in report
    assert "routeAccuracy" in report
    assert "directAnswerPassRate" in report
