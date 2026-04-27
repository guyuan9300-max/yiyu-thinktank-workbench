from __future__ import annotations

from pathlib import Path


def test_frontend_data_center_ops_panel_contract_p23():
    repo_root = Path(__file__).resolve().parents[2]
    app_text = (repo_root / "src" / "renderer" / "App.tsx").read_text(encoding="utf-8")
    panel_path = repo_root / "src" / "renderer" / "components" / "data_center" / "DataCenterOpsPanel.tsx"
    api_text = (repo_root / "src" / "renderer" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert panel_path.exists()
    panel_text = panel_path.read_text(encoding="utf-8")

    assert "DataCenterOpsPanel" in app_text
    assert "approveProposal" in panel_text
    assert "rejectProposal" in panel_text
    assert "createProposalExecutionTicket" in panel_text
    assert "executeExecutionTicket" in panel_text
    assert "确认执行" in panel_text

    assert "getProposalExecutionPreview(" in api_text
    assert "createProposalExecutionTicket(" in api_text
    assert "getExecutionTickets(" in api_text
    assert "executeExecutionTicket(" in api_text

