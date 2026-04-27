from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.freeze_customer_workspace_baseline_p27 import build_baseline, write_baseline


def test_freeze_customer_workspace_baseline_p27(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    payload = build_baseline(
        repo_root,
        eval_payload={
            "caseCount": 30,
            "usableAnswerRate": 0.9,
            "retryBannerRate": 0.05,
            "groundedAnswerPassRate": 0.9,
            "businessStrategySlotHitRate": 0.9,
            "kernelPrimaryUsedRate": 0.9,
            "officialBoundaryPass": True,
            "candidateBoundaryPass": True,
            "failureCount": 0,
        },
    )

    assert payload["repo"]["root"] == str(repo_root)
    schema_contract = payload.get("schemaContract") if isinstance(payload.get("schemaContract"), dict) else {}
    assert "workspaceAnswerFinalizationFields" in schema_contract
    assert "apiPaths" in schema_contract

    artifacts = write_baseline(payload, tmp_path / "output")
    json_path = Path(artifacts["jsonPath"])
    md_path = Path(artifacts["markdownPath"])
    assert json_path.exists()
    assert md_path.exists()

    stored = json.loads(json_path.read_text(encoding="utf-8"))
    assert stored["valueEvalBaseline"]["retryBannerRate"] == 0.05
