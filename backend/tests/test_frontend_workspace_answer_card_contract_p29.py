from __future__ import annotations

from pathlib import Path


def test_frontend_workspace_answer_card_contract_p29():
    repo_root = Path(__file__).resolve().parents[2]
    app_path = repo_root / 'src' / 'renderer' / 'App.tsx'
    content = app_path.read_text(encoding='utf-8')

    assert 'shouldRenderPlainWorkspaceAnswer' in content
    assert 'workspaceAnswerExperience' in content
    assert 'directAnswer' in content
    assert 'evidenceChips' in content
    assert 'boundaryNotes' in content
    assert 'actionCards' in content
    assert 'hasStructuredAnswerCard' in content
    assert "extendedAnalysisDecision.shouldRender && !hasStructuredAnswerCard" in content
    assert '!shouldRenderPlainWorkspaceAnswer && qualityPayload' in content
    assert '!shouldRenderPlainWorkspaceAnswer && shouldRenderStateSections && stateSections' in content
    assert '可用' in content
    assert '不可用' in content
    assert '记录耗时' in content
    assert '完整长文扩写未完成' not in content
