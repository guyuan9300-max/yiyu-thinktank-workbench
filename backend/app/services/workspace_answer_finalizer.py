from __future__ import annotations

from typing import Literal

from app.models import DataCenterKernelResultRecord, WorkspaceAnswerFinalizationRecord


def _safe_grade(answer_quality: dict[str, object] | None) -> str:
    grade = str((answer_quality or {}).get("grade") or "").strip().lower()
    if grade in {"pass", "warn", "fail"}:
        return grade
    return "warn"


def _safe_bool(payload: dict[str, object] | None, key: str) -> bool:
    return bool((payload or {}).get(key))


def _safe_evidence_status(value: str | None) -> Literal["sufficient", "partial", "none"]:
    status = str(value or "").strip().lower()
    if status in {"sufficient", "partial", "none"}:
        return status  # type: ignore[return-value]
    return "none"


def finalize_workspace_answer(
    *,
    content: str,
    answer_mode: str,
    failure_reason: str | None,
    fallback_presentation_mode: str | None,
    kernel_result: DataCenterKernelResultRecord | None,
    answer_quality: dict[str, object] | None,
    selected_evidence_count: int,
    llm_error: str | None = None,
) -> WorkspaceAnswerFinalizationRecord:
    del kernel_result

    text = str(content or "").strip()
    mode = str(answer_mode or "grounded_fallback").strip() or "grounded_fallback"
    failure = str(failure_reason or "").strip() or None
    fallback_mode = str(fallback_presentation_mode or "").strip() or None
    if fallback_mode not in {"state_cards_only", "compact_user_answer", "full_answer"}:
        fallback_mode = None

    quality_grade = _safe_grade(answer_quality)
    has_direct_answer = _safe_bool(answer_quality, "hasDirectAnswer")
    evidence_list_only = _safe_bool(answer_quality, "evidenceListOnly")
    official_boundary_violation = _safe_bool(answer_quality, "officialBoundaryViolation")
    candidate_boundary_violation = _safe_bool(answer_quality, "candidateAsOfficialRisk")
    missing_raw_evidence = _safe_bool(answer_quality, "missingRawEvidenceForIntent")

    notes: list[str] = []
    has_content = bool(text)
    selected_evidence_ok = int(selected_evidence_count or 0) >= 1
    selected_evidence_ready = selected_evidence_ok or not missing_raw_evidence
    boundary_safe = not official_boundary_violation and not candidate_boundary_violation

    if mode == "system_failure":
        notes.append("system_failure_preserved")
        return WorkspaceAnswerFinalizationRecord(
            content=text,
            answerMode="system_failure",
            failureReason=failure or "llm_generation_failed",
            fallbackPresentationMode=fallback_mode or "compact_user_answer",
            userVisibleQualityStatus="needs_retry",
            shouldShowRetryBanner=True,
            qualityGrade="fail" if quality_grade == "fail" else "warn",
            internalGenerationStatus="system_failure",
            notes=notes,
        )

    if failure == "llm_partial_preserved_after_retry":
        notes.append("partial_generation_preserved")
        return WorkspaceAnswerFinalizationRecord(
            content=text,
            answerMode="grounded_fallback",
            failureReason=failure,
            fallbackPresentationMode=fallback_mode or "full_answer",
            userVisibleQualityStatus="needs_retry",
            shouldShowRetryBanner=True,
            qualityGrade="warn" if quality_grade != "fail" else "fail",
            internalGenerationStatus="partial_generation_preserved",
            notes=notes,
        )

    if (
        has_content
        and quality_grade == "pass"
        and has_direct_answer
        and not evidence_list_only
        and boundary_safe
        and selected_evidence_ready
    ):
        notes.append("quality_pass_promoted_to_grounded_answer")
        internal_status = "llm_failed_but_kernel_answer_passed" if str(llm_error or "").strip() else "quality_passed"
        return WorkspaceAnswerFinalizationRecord(
            content=text,
            answerMode="grounded_answer",
            failureReason=None,
            fallbackPresentationMode="full_answer",
            userVisibleQualityStatus="ready",
            shouldShowRetryBanner=False,
            qualityGrade="pass",
            internalGenerationStatus=internal_status,
            notes=notes,
        )

    if (
        has_content
        and quality_grade == "warn"
        and has_direct_answer
        and boundary_safe
    ):
        notes.append("quality_warn_promoted_to_grounded_answer")
        return WorkspaceAnswerFinalizationRecord(
            content=text,
            answerMode="grounded_answer",
            failureReason=None,
            fallbackPresentationMode="full_answer",
            userVisibleQualityStatus="usable_with_boundary",
            shouldShowRetryBanner=False,
            qualityGrade="warn",
            internalGenerationStatus="quality_warned_but_usable",
            notes=notes,
        )

    hard_retry_required = (
        not has_content
        or quality_grade == "fail"
        or official_boundary_violation
        or candidate_boundary_violation
        or evidence_list_only
        or (not selected_evidence_ok and missing_raw_evidence)
    )

    if hard_retry_required:
        if mode == "system_failure":
            final_mode = "system_failure"
        elif mode in {"grounded_fallback", "low_confidence_answer", "system_failure"}:
            final_mode = "grounded_fallback"
        elif mode in {"grounded_answer", "general_answer"}:
            final_mode = "grounded_fallback"
        else:
            final_mode = "grounded_fallback"
        if not has_content:
            notes.append("empty_content")
        if quality_grade == "fail":
            notes.append("quality_fail")
        if official_boundary_violation:
            notes.append("official_boundary_violation")
        if candidate_boundary_violation:
            notes.append("candidate_boundary_violation")
        if evidence_list_only:
            notes.append("evidence_list_only")
        if not selected_evidence_ok and missing_raw_evidence:
            notes.append("selected_evidence_missing")
        return WorkspaceAnswerFinalizationRecord(
            content=text,
            answerMode=final_mode,  # type: ignore[arg-type]
            failureReason=failure or "needs_retry",
            fallbackPresentationMode=fallback_mode or "compact_user_answer",
            userVisibleQualityStatus="needs_retry",
            shouldShowRetryBanner=True,
            qualityGrade="fail" if quality_grade == "fail" else "warn",
            internalGenerationStatus="quality_not_ready",
            notes=notes,
        )

    notes.append("degraded_but_no_hard_retry")
    return WorkspaceAnswerFinalizationRecord(
        content=text,
        answerMode="grounded_answer",
        failureReason=None,
        fallbackPresentationMode="full_answer",
        userVisibleQualityStatus="degraded",
        shouldShowRetryBanner=False,
        qualityGrade="warn" if quality_grade != "pass" else "pass",
        internalGenerationStatus="degraded_output",
        notes=notes,
    )


def normalize_workspace_evidence_status(
    *,
    initial_status: str | None,
    finalization: WorkspaceAnswerFinalizationRecord,
    answer_quality: dict[str, object] | None,
    selected_evidence_count: int,
) -> Literal["sufficient", "partial", "none"]:
    normalized = _safe_evidence_status(initial_status)
    if finalization.answerMode != "grounded_answer" or finalization.shouldShowRetryBanner:
        return normalized

    selected_evidence_ok = max(int(selected_evidence_count or 0), 0) >= 1
    missing_raw_evidence = _safe_bool(answer_quality, "missingRawEvidenceForIntent")
    if selected_evidence_ok and not missing_raw_evidence:
        return "sufficient"
    if selected_evidence_ok and normalized == "none":
        return "partial"
    return normalized
