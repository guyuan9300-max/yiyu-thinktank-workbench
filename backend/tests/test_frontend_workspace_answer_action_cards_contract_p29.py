from __future__ import annotations

from pathlib import Path


def test_frontend_workspace_answer_action_cards_contract_p29():
    repo_root = Path(__file__).resolve().parents[2]
    app_path = repo_root / 'src' / 'renderer' / 'App.tsx'
    api_path = repo_root / 'src' / 'renderer' / 'lib' / 'api.ts'
    app_content = app_path.read_text(encoding='utf-8')
    api_content = api_path.read_text(encoding='utf-8')

    assert 'createWorkspaceAnswerActionProposal' in app_content
    assert 'createWorkspaceAnswerActionTask' in app_content
    assert 'createWorkspaceAnswerActionEvidenceRequest' in app_content
    assert '/api/v1/workspace-answer-action-cards/' in api_content
