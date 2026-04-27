from __future__ import annotations

from pathlib import Path


def test_frontend_rollout_multiclient_contract_p210():
    repo_root = Path(__file__).resolve().parents[2]
    panel_path = repo_root / 'src' / 'renderer' / 'components' / 'data_center' / 'DataCenterOpsPanel.tsx'
    content = panel_path.read_text(encoding='utf-8')

    assert 'rolloutClientIdsInput' in content
    assert 'stage_3_clients 至少需要 3 个 clientId' in content
    assert 'stage_10_clients 至少需要 10 个 clientId' in content
    assert 'clientIds: rolloutClientIds' in content
    assert 'clientIds: [clientId]' not in content

