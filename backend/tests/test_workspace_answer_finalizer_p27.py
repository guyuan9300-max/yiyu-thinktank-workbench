from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.workspace_answer_finalizer import finalize_workspace_answer


def _quality(**overrides):
    payload = {
        "grade": "pass",
        "hasDirectAnswer": True,
        "evidenceListOnly": False,
        "officialBoundaryViolation": False,
        "candidateAsOfficialRisk": False,
        "missingRawEvidenceForIntent": False,
    }
    payload.update(overrides)
    return payload


def test_finalize_workspace_answer_timeout_but_quality_pass_promotes_grounded_answer():
    result = finalize_workspace_answer(
        content="基于现有资料，核心业务聚焦资源支持与项目服务。",
        answer_mode="grounded_fallback",
        failure_reason="llm_timeout",
        fallback_presentation_mode="compact_user_answer",
        kernel_result=None,
        answer_quality=_quality(grade="pass"),
        selected_evidence_count=0,
        llm_error="read timeout",
    )
    assert result.answerMode == "grounded_answer"
    assert result.shouldShowRetryBanner is False
    assert result.userVisibleQualityStatus == "ready"
    assert result.internalGenerationStatus == "llm_failed_but_kernel_answer_passed"


def test_finalize_workspace_answer_warn_promotes_usable_with_boundary():
    result = finalize_workspace_answer(
        content="当前资料显示战略方向包括能力建设与生态协作，但时间边界仍待确认。",
        answer_mode="grounded_fallback",
        failure_reason="partial_materials",
        fallback_presentation_mode="compact_user_answer",
        kernel_result=None,
        answer_quality=_quality(grade="warn"),
        selected_evidence_count=2,
        llm_error=None,
    )
    assert result.answerMode == "grounded_answer"
    assert result.userVisibleQualityStatus == "usable_with_boundary"
    assert result.shouldShowRetryBanner is False


def test_finalize_workspace_answer_fail_keeps_retry_banner():
    result = finalize_workspace_answer(
        content="这是一段仅文件列表式的输出。",
        answer_mode="grounded_fallback",
        failure_reason="partial_materials",
        fallback_presentation_mode="compact_user_answer",
        kernel_result=None,
        answer_quality=_quality(grade="fail", evidenceListOnly=True),
        selected_evidence_count=0,
        llm_error=None,
    )
    assert result.answerMode == "grounded_fallback"
    assert result.userVisibleQualityStatus == "needs_retry"
    assert result.shouldShowRetryBanner is True


def test_finalize_workspace_answer_official_boundary_violation_keeps_retry_banner():
    result = finalize_workspace_answer(
        content="已批准正式判断如下：候选结论A。",
        answer_mode="grounded_answer",
        failure_reason=None,
        fallback_presentation_mode="full_answer",
        kernel_result=None,
        answer_quality=_quality(grade="fail", officialBoundaryViolation=True),
        selected_evidence_count=3,
        llm_error=None,
    )
    assert result.userVisibleQualityStatus == "needs_retry"
    assert result.shouldShowRetryBanner is True


def test_finalize_workspace_answer_system_failure_preserved():
    result = finalize_workspace_answer(
        content="模型调用失败，请重试。",
        answer_mode="system_failure",
        failure_reason="llm_generation_failed",
        fallback_presentation_mode="compact_user_answer",
        kernel_result=None,
        answer_quality=None,
        selected_evidence_count=0,
        llm_error="timeout",
    )
    assert result.answerMode == "system_failure"
    assert result.shouldShowRetryBanner is True
