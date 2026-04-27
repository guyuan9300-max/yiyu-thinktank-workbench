from __future__ import annotations

from pathlib import Path


def test_frontend_proposal_inbox_contract_p22():
    repo_root = Path(__file__).resolve().parents[2]
    app_text = (repo_root / "src" / "renderer" / "App.tsx").read_text(encoding="utf-8")
    panel_path = repo_root / "src" / "renderer" / "components" / "settings" / "DataCenterProposalInboxPanel.tsx"
    api_text = (repo_root / "src" / "renderer" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert panel_path.exists()
    panel_text = panel_path.read_text(encoding="utf-8")

    assert "DataCenterProposalInboxPanel" in app_text
    assert "getDataCenterProposalDrafts" in panel_text
    assert "markDataCenterProposalDraftReviewed" in panel_text
    assert "rejectDataCenterProposalDraft" in panel_text
    assert "promoteDataCenterProposalDraft" in panel_text

    assert "getDataCenterProposalDrafts(" in api_text
    assert "promoteDataCenterProposalDraft(" in api_text
