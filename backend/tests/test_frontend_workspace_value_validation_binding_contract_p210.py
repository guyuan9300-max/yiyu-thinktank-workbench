from __future__ import annotations

from pathlib import Path


def test_frontend_workspace_value_validation_binding_contract_p210():
    repo_root = Path(__file__).resolve().parents[2]
    panel_path = repo_root / 'src' / 'renderer' / 'components' / 'data_center' / 'WorkspaceAnswerValuePanel.tsx'
    content = panel_path.read_text(encoding='utf-8')

    assert 'selectedReviewId' in content
    assert '选择本题对应回答' in content
    assert '用选中复核完成当前题' in content
    assert 'latestReview' not in content

