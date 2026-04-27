from __future__ import annotations

from pathlib import Path


def test_workspace_data_center_readiness_panel_p29_contract():
    repo_root = Path(__file__).resolve().parents[2]
    panel_path = repo_root / 'src' / 'renderer' / 'components' / 'data_center' / 'WorkspaceAnswerValuePanel.tsx'
    readiness_panel_path = repo_root / 'src' / 'renderer' / 'components' / 'settings' / 'DataCenterReadinessPanel.tsx'
    api_path = repo_root / 'src' / 'renderer' / 'lib' / 'api.ts'

    panel_content = panel_path.read_text(encoding='utf-8')
    readiness_content = readiness_panel_path.read_text(encoding='utf-8')
    api_content = api_path.read_text(encoding='utf-8')

    assert '数据中心准备度摘要' in panel_content
    assert '文档总数' in panel_content
    assert '解析失败' in panel_content
    assert 'vector:' in panel_content
    assert 'getWorkspaceDataCenterReadiness' in panel_content
    assert '/workspace/data-center-readiness' in api_content
    assert '推荐修复动作' in readiness_content
