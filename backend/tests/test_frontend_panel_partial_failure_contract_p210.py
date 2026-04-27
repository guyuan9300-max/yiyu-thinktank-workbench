from __future__ import annotations

from pathlib import Path


def test_frontend_panel_partial_failure_contract_p210():
    repo_root = Path(__file__).resolve().parents[2]
    ops_path = repo_root / 'src' / 'renderer' / 'components' / 'data_center' / 'DataCenterOpsPanel.tsx'
    value_path = repo_root / 'src' / 'renderer' / 'components' / 'data_center' / 'WorkspaceAnswerValuePanel.tsx'
    ops_content = ops_path.read_text(encoding='utf-8')
    value_content = value_path.read_text(encoding='utf-8')

    assert 'Promise.allSettled' in ops_content
    assert 'Promise.allSettled' in value_content
    assert 'Promise.all([' not in ops_content
    assert 'Promise.all([' not in value_content
    assert 'setProposalsError' in ops_content
    assert 'setSectionErrors' in value_content

