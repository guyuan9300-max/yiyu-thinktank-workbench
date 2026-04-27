from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.eval_customer_workspace_answer_value_p27 import run_eval


def test_eval_customer_workspace_answer_value_p27(tmp_path: Path):
    output_dir = tmp_path / "output"
    payload = run_eval(strict=True, output_dir=output_dir)
    assert int(payload.get("caseCount") or 0) >= 30
    assert float(payload.get("usableAnswerRate") or 0.0) >= 0.75
    assert float(payload.get("retryBannerRate") or 0.0) <= 0.10
    assert float(payload.get("groundedAnswerPassRate") or 0.0) >= 0.80
    assert float(payload.get("businessStrategySlotHitRate") or 0.0) >= 0.75
    assert payload.get("officialBoundaryPass") is True
    assert payload.get("candidateBoundaryPass") is True
    assert int(payload.get("failureCount") or 0) == 0
    assert (output_dir / "P2.7-customer-workspace-value-eval.json").exists()
    assert (output_dir / "P2.7-customer-workspace-value-eval.md").exists()
