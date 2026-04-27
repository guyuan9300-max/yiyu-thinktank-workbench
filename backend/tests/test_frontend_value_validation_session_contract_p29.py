from __future__ import annotations

from pathlib import Path


def test_frontend_value_validation_session_contract_p29():
    repo_root = Path(__file__).resolve().parents[2]
    panel_path = repo_root / 'src' / 'renderer' / 'components' / 'data_center' / 'WorkspaceAnswerValuePanel.tsx'
    content = panel_path.read_text(encoding='utf-8')

    assert '开始 10 问价值验证' in content
    assert '复制下一问题' in content
    assert '选择本题对应回答' in content
    assert '用选中复核完成当前题' in content
    assert '生成价值验证报告' in content
    assert 'workspace-value-validation-sessions' in (repo_root / 'src' / 'renderer' / 'lib' / 'api.ts').read_text(encoding='utf-8')
