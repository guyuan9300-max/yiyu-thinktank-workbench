from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_ops_panel_p25_contract():
    repo_root = Path(__file__).resolve().parents[2]
    panel_path = repo_root / "src" / "renderer" / "components" / "data_center" / "DataCenterOpsPanel.tsx"
    api_path = repo_root / "src" / "renderer" / "lib" / "api.ts"

    assert panel_path.exists()
    assert api_path.exists()

    panel_text = panel_path.read_text(encoding="utf-8")
    api_text = api_path.read_text(encoding="utf-8")

    assert "Kernel Rollout Runs" in panel_text
    assert "Execution Retry Metrics" in panel_text
    assert "Evidence Quality Snapshots" in panel_text
    assert "Rollback Drill" in panel_text

    assert "startKernelPrimaryRollout(" in api_text
    assert "completeKernelPrimaryRollout(" in api_text
    assert "rollbackKernelPrimaryRollout(" in api_text
    assert "getExecutionRetryMetrics(" in api_text
    assert "createEvidenceQualitySnapshot(" in api_text
    assert "listEvidenceQualitySnapshots(" in api_text
    assert "runDataCenterRollbackDrill(" in api_text
