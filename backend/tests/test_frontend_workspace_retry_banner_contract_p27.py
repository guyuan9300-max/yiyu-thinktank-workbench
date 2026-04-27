from __future__ import annotations

from pathlib import Path


def test_frontend_workspace_retry_banner_contract_p27():
    repo_root = Path(__file__).resolve().parents[2]
    app_path = repo_root / "src" / "renderer" / "App.tsx"
    assert app_path.exists()
    content = app_path.read_text(encoding="utf-8")

    assert "workspaceAnswerFinalization" in content
    assert "shouldShowRetryBanner" in content
    assert "userVisibleQualityStatus" in content
    # 新逻辑不应仅靠 answerMode=grounded_fallback 直接决定重试条
    assert "msg.answerMode === 'grounded_fallback' && (" not in content
