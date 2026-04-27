from __future__ import annotations

from pathlib import Path


def test_frontend_diagnostics_panel_contract_p22():
    repo_root = Path(__file__).resolve().parents[2]
    app_text = (repo_root / "src" / "renderer" / "App.tsx").read_text(encoding="utf-8")
    panel_path = repo_root / "src" / "renderer" / "components" / "settings" / "DataCenterDiagnosticsPanel.tsx"
    api_text = (repo_root / "src" / "renderer" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert panel_path.exists()
    panel_text = panel_path.read_text(encoding="utf-8")

    assert "DataCenterDiagnosticsPanel" in app_text
    assert "getWorkspaceChatDiagnostics" in panel_text
    assert "resetGenerationRuntimeStateV2" in panel_text
    assert "retryKnowledgeParseFailures" in panel_text
    assert "getDataCenterProposalDrafts" in panel_text
    assert "getClientVectorIndexStatus" in panel_text
    assert "getSourceIntegrity" in panel_text

    assert "getWorkspaceChatDiagnostics(clientId: string" in api_text
    assert "resetGenerationRuntimeStateV2(" in api_text
