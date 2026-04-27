from __future__ import annotations

from pathlib import Path


def test_frontend_no_legacy_retry_banner_p28():
    repo_root = Path(__file__).resolve().parents[2]
    app_path = repo_root / 'src' / 'renderer' / 'App.tsx'
    content = app_path.read_text(encoding='utf-8')

    assert 'workspaceAnswerFinalization?.shouldShowRetryBanner' in content
    assert 'legacyFallbackNotice = !workspaceAnswerFinalization' in content
    assert '本轮没有形成可靠答案，建议重试或补充资料。' in content
    assert '已基于客户资料生成可用回答；部分判断仍保留资料边界或待确认事项。' in content
    assert '完整长文扩写未完成' not in content
