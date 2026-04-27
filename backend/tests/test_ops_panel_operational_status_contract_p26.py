from __future__ import annotations

from pathlib import Path


def test_ops_panel_operational_status_contract_p26():
    repo_root = Path(__file__).resolve().parents[2]
    panel_path = repo_root / "src" / "renderer" / "components" / "data_center" / "DataCenterOpsPanel.tsx"

    assert panel_path.exists()
    panel_text = panel_path.read_text(encoding="utf-8")

    assert "Data Center Operational Status" in panel_text
    assert "rollout verdict" in panel_text
    assert "retry alerts" in panel_text
    assert "latest snapshot" in panel_text
    assert "rollback drill" in panel_text
    assert "full regression verdict" in panel_text
    assert "Run full regression report" in panel_text
    assert "Generate RC2 report" in panel_text
