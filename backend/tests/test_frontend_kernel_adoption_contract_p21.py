from __future__ import annotations

from pathlib import Path


def test_frontend_kernel_adoption_contract():
    repo_root = Path(__file__).resolve().parents[2]
    api_text = (repo_root / "src" / "renderer" / "lib" / "api.ts").read_text(encoding="utf-8")
    app_text = (repo_root / "src" / "renderer" / "App.tsx").read_text(encoding="utf-8")

    assert "resolveDataCenterKernel(payload: DataCenterRequest)" in api_text
    assert "getTaskPageContext(" in api_text
    assert "getMeetingPageContext(" in api_text

    # Task page real usage.
    assert "getTaskPageContext(task.id" in app_text
    assert "page: 'task_detail'" in app_text
    assert "mode: 'page_context'" in app_text

    # Meeting prep usage.
    assert "page: 'meeting_detail'" in app_text
    assert "mode: 'prep'" in app_text
    assert "getMeetingPageContext(meetingId" in app_text

    # Strategic cockpit readonly usage.
    assert "page: 'strategic_cockpit'" in app_text
    assert "mode: 'diagnostic'" in app_text
    assert "mode: 'page_context'" in app_text

    # WorkTrace dev fields.
    assert "answerPlanRaw" in app_text
    assert "answerQualityRaw" in app_text
    assert "generationPolicyRaw" in app_text
