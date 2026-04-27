from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.check_customer_workspace_value_runtime_alignment_p29 import build_alignment_report  # noqa: E402


def test_customer_workspace_runtime_alignment_p29(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]

    renderer_dir = tmp_path / 'dist' / 'renderer' / 'assets'
    renderer_dir.mkdir(parents=True, exist_ok=True)
    (renderer_dir / 'index.js').write_text(
        '\n'.join(
            [
                'workspaceAnswerFinalization',
                'workspaceAnswerExperience',
                'shouldShowRetryBanner',
                'usable_with_boundary',
                'needs_retry',
            ]
        ),
        encoding='utf-8',
    )

    report = build_alignment_report(
        repo_root,
        renderer_assets_dir=renderer_dir,
        installed_app_root=tmp_path / 'missing-installed.app',
        local_probe=lambda: {
            'answerMode': 'grounded_answer',
            'hasWorkspaceAnswerFinalization': True,
            'hasWorkspaceAnswerExperience': True,
            'shouldShowRetryBanner': False,
            'userVisibleQualityStatus': 'ready',
            'experienceStatus': 'ready',
            'experienceDirectAnswer': '客户核心业务是资源支持与项目服务。',
            'pass': True,
        },
    )

    assert report['verdict'] == 'pass'
    assert report['runtimeValueAlignmentPass'] is True
