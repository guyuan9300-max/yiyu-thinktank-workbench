from __future__ import annotations

from pathlib import Path


def test_ops_panel_execution_retry_metrics_contract_p26():
    repo_root = Path(__file__).resolve().parents[2]
    panel_path = repo_root / "src" / "renderer" / "components" / "data_center" / "DataCenterOpsPanel.tsx"
    api_path = repo_root / "src" / "renderer" / "lib" / "api.ts"

    assert panel_path.exists()
    assert api_path.exists()

    panel_text = panel_path.read_text(encoding="utf-8")
    api_text = api_path.read_text(encoding="utf-8")

    assert "Execution Retry Metrics" in panel_text
    assert "failure reason TopN" in panel_text
    assert "failed stage TopN" in panel_text
    assert "retry success rate" in panel_text
    assert "avg retry count" in panel_text
    assert "oldest failed age(h)" in panel_text

    assert "getExecutionRetryMetrics(" in api_text
