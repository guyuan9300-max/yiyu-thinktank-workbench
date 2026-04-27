from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from app.db import Database, from_json, to_json
from app.models import (
    WorkspaceAnswerQualityFailureRecord,
    WorkspaceAnswerQualityFailureResolvePayloadRecord,
    WorkspaceAnswerValueDiagnosticsRecord,
    WorkspaceAnswerValueReviewPayloadRecord,
    WorkspaceAnswerValueReviewRecord,
    WorkspaceAnswerValueSummaryRecord,
    WorkspaceAnswerValueTopItemRecord,
    WorkspaceValueValidationQuestionRecord,
    WorkspaceValueValidationSessionCompleteQuestionPayloadRecord,
    WorkspaceValueValidationSessionCreatePayloadRecord,
    WorkspaceValueValidationSessionRecord,
    WorkspaceValueValidationSessionSummaryRecord,
)
from app.services.knowledge_v2 import new_id


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _safe_ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(float(num) / float(den), 4)


def _is_timeout(reason: str | None) -> bool:
    text = str(reason or "").lower()
    return any(token in text for token in ("timeout", "timed out", "read timeout", "超时"))


def _legacy_retry_banner_rule(
    *,
    answer_mode: str,
    fallback_reason: str | None,
    fallback_presentation_mode: str | None,
) -> bool:
    return (
        (
            answer_mode == "grounded_fallback"
            and str(fallback_reason or "").strip() != "state_only"
            and str(fallback_presentation_mode or "").strip() != "state_cards_only"
        )
        or answer_mode == "low_confidence_answer"
    )


def _extract_workspace_finalization(summary: dict[str, object]) -> dict[str, object] | None:
    payload = summary.get("workspaceAnswerFinalization")
    if isinstance(payload, dict):
        return payload
    return None


def _top_items(counter: Counter[str], *, limit: int = 5) -> list[WorkspaceAnswerValueTopItemRecord]:
    return [
        WorkspaceAnswerValueTopItemRecord(key=key, count=int(count))
        for key, count in counter.most_common(max(int(limit), 1))
        if str(key).strip()
    ]


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _answer_too_short(content: str) -> bool:
    compact = " ".join(str(content or "").split())
    return bool(compact) and len(compact) < 60


def _answer_too_template_like(
    *,
    content: str,
    retrieval_summary: dict[str, object],
) -> bool:
    compact = " ".join(str(content or "").split())
    if not compact:
        return False
    generic_markers = [
        "基于当前资料",
        "当前资料有限",
        "建议补齐证据",
        "先给出可确认结论",
        "建议补充资料",
    ]
    generic_hits = sum(1 for marker in generic_markers if marker in compact)
    if generic_hits <= 0:
        return False
    fact_slots = retrieval_summary.get("factSlots")
    has_fact_slots = False
    if isinstance(fact_slots, dict):
        has_fact_slots = bool(
            fact_slots.get("businessModules")
            or fact_slots.get("strategyDirections")
            or _safe_text(fact_slots.get("timeBoundary"))
        )
    answer_presentation = retrieval_summary.get("answerPresentation")
    has_evidence_titles = False
    if isinstance(answer_presentation, dict):
        sections = answer_presentation.get("sections")
        if isinstance(sections, list):
            for section in sections:
                if not isinstance(section, dict):
                    continue
                items = section.get("items")
                if isinstance(items, list) and any(_safe_text(item) for item in items):
                    has_evidence_titles = True
                    break
    return generic_hits >= 1 and not has_fact_slots and not has_evidence_titles


def build_workspace_answer_value_diagnostics(
    db: Database,
    *,
    client_id: str,
    recent_messages: int = 50,
    since: str | None = None,
) -> dict[str, Any]:
    params: list[object] = [client_id]
    where_since = ""
    if since:
        where_since = "AND m.created_at >= ?"
        params.append(since)
    params.append(max(int(recent_messages), 1))
    rows = db.fetchall(
        f"""
        SELECT m.*
        FROM chat_messages m
        JOIN chat_threads t ON t.id = m.thread_id
        WHERE t.client_id = ? AND m.role = 'assistant' AND m.status = 'success'
          {where_since}
        ORDER BY m.created_at DESC
        LIMIT ?
        """,
        tuple(params),
    )

    total = len(rows)
    answer_mode_distribution: Counter[str] = Counter()
    fallback_reason_distribution: Counter[str] = Counter()
    fallback_presentation_mode_distribution: Counter[str] = Counter()
    failure_reason_distribution: Counter[str] = Counter()

    retry_banner_count = 0
    low_confidence_count = 0
    grounded_fallback_count = 0
    grounded_answer_count = 0
    usable_answer_count = 0
    ready_or_usable_count = 0
    needs_retry_count = 0
    degraded_count = 0
    kernel_primary_used_count = 0
    kernel_primary_fallback_used_count = 0
    llm_timeout_count = 0
    answer_quality_pass_count = 0
    answer_quality_fail_count = 0
    official_boundary_violation_count = 0
    candidate_boundary_violation_count = 0
    selected_evidence_total = 0
    selected_evidence_count_samples = 0
    evidence_supported_count = 0
    business_slot_answer_count = 0
    strategy_slot_answer_count = 0
    answer_too_short_count = 0
    answer_too_template_like_count = 0

    for row in rows:
        answer_mode = str(row["answer_mode"] or "").strip() or "unknown"
        answer_mode_distribution[answer_mode] += 1
        if answer_mode == "grounded_fallback":
            grounded_fallback_count += 1
        if answer_mode == "low_confidence_answer":
            low_confidence_count += 1
        if answer_mode == "grounded_answer":
            grounded_answer_count += 1
        content = _safe_text(row["content"])

        failure_reason = str(row["failure_reason"] or "").strip()
        if failure_reason:
            failure_reason_distribution[failure_reason] += 1

        retrieval_summary = from_json(str(row["retrieval_summary_json"] or "{}"), {})
        if not isinstance(retrieval_summary, dict):
            retrieval_summary = {}

        fallback_reason = str(retrieval_summary.get("fallbackReason") or "").strip()
        fallback_mode = str(retrieval_summary.get("fallbackPresentationMode") or "").strip()
        if fallback_reason:
            fallback_reason_distribution[fallback_reason] += 1
        if fallback_mode:
            fallback_presentation_mode_distribution[fallback_mode] += 1

        finalization = _extract_workspace_finalization(retrieval_summary)
        if isinstance(finalization, dict):
            should_show_retry_banner = bool(finalization.get("shouldShowRetryBanner"))
            user_visible_status = str(finalization.get("userVisibleQualityStatus") or "").strip()
        else:
            should_show_retry_banner = _legacy_retry_banner_rule(
                answer_mode=answer_mode,
                fallback_reason=fallback_reason,
                fallback_presentation_mode=fallback_mode,
            )
            user_visible_status = "needs_retry" if should_show_retry_banner else ("ready" if answer_mode == "grounded_answer" else "degraded")

        if should_show_retry_banner:
            retry_banner_count += 1

        if user_visible_status in {"ready", "usable_with_boundary"}:
            usable_answer_count += 1
            ready_or_usable_count += 1
        elif user_visible_status == "needs_retry":
            needs_retry_count += 1
        else:
            degraded_count += 1

        if bool(retrieval_summary.get("kernelPrimaryUsed")):
            kernel_primary_used_count += 1
        if bool(retrieval_summary.get("kernelPrimaryFallbackUsed")):
            kernel_primary_fallback_used_count += 1

        generation_failure_detail = str(retrieval_summary.get("generationFailureDetail") or "").strip()
        if _is_timeout(failure_reason) or _is_timeout(generation_failure_detail):
            llm_timeout_count += 1

        answer_quality = retrieval_summary.get("answerQuality")
        if isinstance(answer_quality, dict):
            grade = str(answer_quality.get("grade") or "").strip().lower()
            if grade == "pass":
                answer_quality_pass_count += 1
            elif grade == "fail":
                answer_quality_fail_count += 1
            if bool(answer_quality.get("officialBoundaryViolation")):
                official_boundary_violation_count += 1
            if bool(answer_quality.get("candidateAsOfficialRisk")):
                candidate_boundary_violation_count += 1

        selected_evidence_count = int(
            retrieval_summary.get("kernelSelectedEvidenceCount")
            or retrieval_summary.get("selectedEvidenceCount")
            or 0
        )
        if selected_evidence_count > 0:
            evidence_supported_count += 1
        if selected_evidence_count > 0:
            selected_evidence_total += selected_evidence_count
            selected_evidence_count_samples += 1

        fact_slots = retrieval_summary.get("factSlots")
        if isinstance(fact_slots, dict):
            business_modules = fact_slots.get("businessModules")
            strategy_directions = fact_slots.get("strategyDirections")
            if isinstance(business_modules, list) and any(_safe_text(item) for item in business_modules):
                business_slot_answer_count += 1
            if isinstance(strategy_directions, list) and any(_safe_text(item) for item in strategy_directions):
                strategy_slot_answer_count += 1

        if _answer_too_short(content):
            answer_too_short_count += 1
        if _answer_too_template_like(content=content, retrieval_summary=retrieval_summary):
            answer_too_template_like_count += 1

    total_safe = max(total, 1)
    top_failure_reasons = _top_items(failure_reason_distribution, limit=5)
    recommended_fixes: list[str] = []
    _, _, metric_errors = _count_answer_action_artifacts(db, client_id=client_id)
    retry_banner_rate = _safe_ratio(retry_banner_count, total_safe)
    kernel_primary_used_rate = _safe_ratio(kernel_primary_used_count, total_safe)
    llm_timeout_rate = _safe_ratio(llm_timeout_count, total_safe)
    grounded_answer_pass_rate = _safe_ratio(answer_quality_pass_count, total_safe)

    if retry_banner_rate > 0.2:
        recommended_fixes.append("客户工作台大量回答进入 fallback 提示，应优先检查 LLM timeout、Kernel Primary allowlist、answer quality finalizer。")
    if kernel_primary_used_rate == 0:
        recommended_fixes.append("当前客户没有进入 Kernel Primary，请检查 workspace_chat_data_center_primary / chatKernelPrimaryEnabled / allowlist。")
    if llm_timeout_rate > 0.2:
        recommended_fixes.append("LLM 超时较高，应优先采用 answer-first：先返回 Kernel 高质量答案，再异步扩写。")
    if official_boundary_violation_count > 0:
        recommended_fixes.append("检测到 official boundary 违规，需立即排查 official_judgment_registry 的回答边界。")
    if not recommended_fixes:
        recommended_fixes.append("当前客户工作台回答质量趋势稳定，可继续灰度观察。")

    diagnostics = WorkspaceAnswerValueDiagnosticsRecord(
        clientId=client_id,
        recentMessages=total,
        answerModeDistribution=dict(answer_mode_distribution),
        fallbackReasonDistribution=dict(fallback_reason_distribution),
        fallbackPresentationModeDistribution=dict(fallback_presentation_mode_distribution),
        retryBannerWouldShowCount=retry_banner_count,
        retryBannerWouldShowRate=retry_banner_rate,
        lowConfidenceCount=low_confidence_count,
        groundedFallbackCount=grounded_fallback_count,
        groundedAnswerCount=grounded_answer_count,
        usableAnswerCount=usable_answer_count,
        usableAnswerRate=_safe_ratio(usable_answer_count, total_safe),
        readyOrUsableCount=ready_or_usable_count,
        readyOrUsableRate=_safe_ratio(ready_or_usable_count, total_safe),
        needsRetryCount=needs_retry_count,
        needsRetryRate=_safe_ratio(needs_retry_count, total_safe),
        degradedCount=degraded_count,
        degradedRate=_safe_ratio(degraded_count, total_safe),
        kernelPrimaryUsedCount=kernel_primary_used_count,
        kernelPrimaryFallbackUsedCount=kernel_primary_fallback_used_count,
        kernelPrimaryUsedRate=kernel_primary_used_rate,
        llmTimeoutCount=llm_timeout_count,
        llmTimeoutRate=llm_timeout_rate,
        answerQualityPassCount=answer_quality_pass_count,
        answerQualityFailCount=answer_quality_fail_count,
        groundedAnswerPassRate=grounded_answer_pass_rate,
        officialBoundaryViolationCount=official_boundary_violation_count,
        candidateBoundaryViolationCount=candidate_boundary_violation_count,
        avgSelectedEvidenceCount=round(selected_evidence_total / selected_evidence_count_samples, 2)
        if selected_evidence_count_samples > 0
        else 0.0,
        evidenceSupportedCount=evidence_supported_count,
        evidenceSupportedRate=_safe_ratio(evidence_supported_count, total_safe),
        businessSlotAnswerCount=business_slot_answer_count,
        businessSlotAnswerRate=_safe_ratio(business_slot_answer_count, total_safe),
        strategySlotAnswerCount=strategy_slot_answer_count,
        strategySlotAnswerRate=_safe_ratio(strategy_slot_answer_count, total_safe),
        answerTooShortCount=answer_too_short_count,
        answerTooShortRate=_safe_ratio(answer_too_short_count, total_safe),
        answerTooTemplateLikeCount=answer_too_template_like_count,
        answerTooTemplateLikeRate=_safe_ratio(answer_too_template_like_count, total_safe),
        topFailureReasons=top_failure_reasons,
        recommendedFixes=recommended_fixes[:8],
        metricErrors=metric_errors,
    )
    return diagnostics.model_dump(mode="json")


def ensure_workspace_answer_value_review_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_answer_value_reviews (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            prompt TEXT NOT NULL,
            answer_mode TEXT NOT NULL,
            user_visible_quality_status TEXT NOT NULL,
            should_show_retry_banner INTEGER NOT NULL DEFAULT 0,
            usable_answer INTEGER,
            reviewer_note TEXT NOT NULL DEFAULT '',
            manual_baseline_minutes REAL,
            data_center_review_minutes REAL,
            saved_minutes REAL,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workspace_answer_value_reviews_client
        ON workspace_answer_value_reviews(client_id, created_at DESC)
        """
    )


def ensure_workspace_value_validation_session_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_value_validation_sessions (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            question_set_json TEXT NOT NULL DEFAULT '[]',
            completed_question_ids_json TEXT NOT NULL DEFAULT '[]',
            summary_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workspace_value_validation_sessions_client
        ON workspace_value_validation_sessions(client_id, updated_at DESC)
        """
    )


def ensure_workspace_answer_quality_failure_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_answer_quality_failures (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            message_id TEXT,
            prompt TEXT NOT NULL,
            failure_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'medium',
            details_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workspace_answer_quality_failures_client
        ON workspace_answer_quality_failures(client_id, status, updated_at DESC)
        """
    )


def _default_workspace_value_validation_questions() -> list[WorkspaceValueValidationQuestionRecord]:
    prompts = [
        "这个客户是谁？",
        "核心业务是什么？",
        "最新战略是什么？",
        "当前合作推进到哪了？",
        "现在最大的风险是什么？",
        "下一步建议先做什么？",
        "系统内有哪些已批准正式判断？",
        "这个判断有什么证据？",
        "最近会议留下了哪些行动项？",
        "还有哪些资料缺口？",
    ]
    return [
        WorkspaceValueValidationQuestionRecord(id=f"wvq_{index:02d}", prompt=prompt)
        for index, prompt in enumerate(prompts, start=1)
    ]


def _count_answer_action_artifacts(db: Database, *, client_id: str) -> tuple[int, int, list[str]]:
    proposal_message_ids: set[str] = set()
    execution_message_ids: set[str] = set()
    metric_errors: list[str] = []
    proposal_id_to_message_id: dict[str, str] = {}
    try:
        draft_rows = db.fetchall(
            """
            SELECT payload_json
            FROM data_center_proposal_drafts
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT 400
            """,
            (client_id,),
        )
    except Exception as exc:
        draft_rows = []
        metric_errors.append(f"proposal_drafts_query_failed: {exc}")
    for row in draft_rows:
        payload = from_json(str(row["payload_json"] or "{}"), {})
        message_id = str(payload.get("workspaceAnswerMessageId") or "").strip() if isinstance(payload, dict) else ""
        if message_id:
            proposal_message_ids.add(message_id)
    try:
        proposal_rows = db.fetchall(
            """
            SELECT id, payload_json
            FROM proposal_records
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT 400
            """,
            (client_id,),
        )
    except Exception as exc:
        proposal_rows = []
        metric_errors.append(f"proposal_records_query_failed: {exc}")
    for row in proposal_rows:
        payload = from_json(str(row["payload_json"] or "{}"), {})
        message_id = str(payload.get("workspaceAnswerMessageId") or "").strip() if isinstance(payload, dict) else ""
        proposal_id = str(row["id"] or "").strip()
        if message_id:
            proposal_message_ids.add(message_id)
            if proposal_id:
                proposal_id_to_message_id[proposal_id] = message_id
    if proposal_id_to_message_id:
        try:
            placeholders = ", ".join("?" for _ in proposal_id_to_message_id)
            ticket_rows = db.fetchall(
                f"""
                SELECT DISTINCT proposal_id
                FROM execution_tickets
                WHERE proposal_id IN ({placeholders})
                """,
                tuple(proposal_id_to_message_id.keys()),
            )
        except Exception as exc:
            ticket_rows = []
            metric_errors.append(f"execution_tickets_query_failed: {exc}")
        for row in ticket_rows:
            proposal_id = str(row["proposal_id"] or "").strip()
            message_id = proposal_id_to_message_id.get(proposal_id)
            if message_id:
                execution_message_ids.add(message_id)
    return len(proposal_message_ids), len(execution_message_ids), metric_errors


def _row_to_workspace_answer_quality_failure(row) -> WorkspaceAnswerQualityFailureRecord:
    failure_type_raw = str(row["failure_type"] or "").strip()
    if failure_type_raw not in {
        "retry_banner",
        "too_template_like",
        "no_evidence",
        "no_direct_answer",
        "boundary_violation",
        "kernel_not_used",
        "answer_too_short",
        "user_marked_not_usable",
    }:
        failure_type_raw = "user_marked_not_usable"
    severity_raw = str(row["severity"] or "").strip()
    if severity_raw not in {"low", "medium", "high"}:
        severity_raw = "medium"
    status_raw = str(row["status"] or "").strip()
    if status_raw not in {"open", "resolved"}:
        status_raw = "open"
    details = from_json(str(row["details_json"] or "{}"), {})
    if not isinstance(details, dict):
        details = {}
    return WorkspaceAnswerQualityFailureRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        messageId=str(row["message_id"]) if row["message_id"] else None,
        prompt=str(row["prompt"] or ""),
        failureType=failure_type_raw,  # type: ignore[arg-type]
        severity=severity_raw,  # type: ignore[arg-type]
        details=details,
        status=status_raw,  # type: ignore[arg-type]
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def record_workspace_answer_quality_failure(
    db: Database,
    *,
    client_id: str,
    message_id: str | None,
    prompt: str,
    failure_type: str,
    severity: str = "medium",
    details: dict[str, object] | None = None,
) -> WorkspaceAnswerQualityFailureRecord:
    ensure_workspace_answer_quality_failure_schema(db)
    normalized_message_id = str(message_id or "").strip() or None
    normalized_failure_type = str(failure_type or "").strip() or "user_marked_not_usable"
    timestamp = _now_iso()
    existing = None
    if normalized_message_id:
        existing = db.fetchone(
            """
            SELECT *
            FROM workspace_answer_quality_failures
            WHERE client_id = ? AND message_id = ? AND failure_type = ? AND status = 'open'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (client_id, normalized_message_id, normalized_failure_type),
        )
    failure_id = str(existing["id"]) if existing else new_id("wavf")
    payload = details or {}
    if existing:
        db.execute(
            """
            UPDATE workspace_answer_quality_failures
            SET prompt = ?, severity = ?, details_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (prompt, severity, to_json(payload), timestamp, failure_id),
        )
    else:
        db.execute(
            """
            INSERT INTO workspace_answer_quality_failures(
                id, client_id, message_id, prompt, failure_type, severity,
                details_json, status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                failure_id,
                client_id,
                normalized_message_id,
                prompt,
                normalized_failure_type,
                severity,
                to_json(payload),
                timestamp,
                timestamp,
            ),
        )
    row = db.fetchone("SELECT * FROM workspace_answer_quality_failures WHERE id = ?", (failure_id,))
    assert row is not None
    return _row_to_workspace_answer_quality_failure(row)


def list_workspace_answer_quality_failures(
    db: Database,
    *,
    client_id: str | None = None,
    limit: int = 80,
) -> list[WorkspaceAnswerQualityFailureRecord]:
    ensure_workspace_answer_quality_failure_schema(db)
    params: list[object] = []
    where = ""
    if str(client_id or "").strip():
        where = "WHERE client_id = ?"
        params.append(str(client_id).strip())
    params.append(max(int(limit), 1))
    rows = db.fetchall(
        f"""
        SELECT *
        FROM workspace_answer_quality_failures
        {where}
        ORDER BY status ASC, updated_at DESC
        LIMIT ?
        """,
        tuple(params),
    )
    return [_row_to_workspace_answer_quality_failure(row) for row in rows]


def resolve_workspace_answer_quality_failure(
    db: Database,
    *,
    failure_id: str,
    payload: WorkspaceAnswerQualityFailureResolvePayloadRecord | None = None,
) -> WorkspaceAnswerQualityFailureRecord:
    ensure_workspace_answer_quality_failure_schema(db)
    row = db.fetchone("SELECT * FROM workspace_answer_quality_failures WHERE id = ?", (failure_id,))
    if not row:
        raise KeyError("workspace_answer_quality_failure_not_found")
    details = from_json(str(row["details_json"] or "{}"), {})
    if not isinstance(details, dict):
        details = {}
    note = str((payload.note if payload else "") or "").strip()
    if note:
        details["resolutionNote"] = note
    timestamp = _now_iso()
    db.execute(
        """
        UPDATE workspace_answer_quality_failures
        SET status = 'resolved', details_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (to_json(details), timestamp, failure_id),
    )
    updated = db.fetchone("SELECT * FROM workspace_answer_quality_failures WHERE id = ?", (failure_id,))
    assert updated is not None
    return _row_to_workspace_answer_quality_failure(updated)


def _compute_session_summary(
    *,
    session_id: str,
    client_id: str,
    entries: dict[str, dict[str, object]],
    total_questions: int,
) -> WorkspaceValueValidationSessionSummaryRecord:
    completed = len(entries)
    if completed <= 0:
        return WorkspaceValueValidationSessionSummaryRecord(sessionId=session_id, clientId=client_id, verdict="hold")
    usable = 0
    retry_banner = 0
    positive_saved = 0
    saved_samples = 0
    proposal_count = 0
    execution_count = 0
    for item in entries.values():
        if bool(item.get("usableAnswer")):
            usable += 1
        if bool(item.get("retryBannerShown")):
            retry_banner += 1
        manual = item.get("manualBaselineMinutes")
        review = item.get("dataCenterReviewMinutes")
        if manual is not None and review is not None:
            saved_samples += 1
            if float(manual) > float(review):
                positive_saved += 1
        if bool(item.get("proposalCreated")):
            proposal_count += 1
        if bool(item.get("executionTicketCreated")):
            execution_count += 1
    estimated_saved_rate = _safe_ratio(positive_saved, saved_samples) if saved_samples > 0 else 0.0
    usable_rate = _safe_ratio(usable, completed)
    retry_rate = _safe_ratio(retry_banner, completed)
    verdict = "pass" if completed >= total_questions and usable_rate >= 0.75 and retry_rate <= 0.10 else "hold"
    if retry_rate > 0.20:
        verdict = "fail"
    return WorkspaceValueValidationSessionSummaryRecord(
        sessionId=session_id,
        clientId=client_id,
        completed=completed,
        usableAnswerRate=usable_rate,
        estimatedTimeSavedRate=estimated_saved_rate,
        retryBannerRate=retry_rate,
        proposalCreatedCount=proposal_count,
        executionTicketCreatedCount=execution_count,
        verdict=verdict,  # type: ignore[arg-type]
    )


def _row_to_workspace_value_validation_session(row) -> WorkspaceValueValidationSessionRecord:
    question_set_raw = from_json(str(row["question_set_json"] or "[]"), [])
    question_set = [
        WorkspaceValueValidationQuestionRecord(
            id=str(item.get("id") or ""),
            prompt=str(item.get("prompt") or ""),
        )
        for item in question_set_raw
        if isinstance(item, dict) and str(item.get("id") or "").strip() and str(item.get("prompt") or "").strip()
    ]
    completed_question_ids_raw = from_json(str(row["completed_question_ids_json"] or "[]"), [])
    summary_raw = from_json(str(row["summary_json"] or "{}"), {})
    if not isinstance(summary_raw, dict):
        summary_raw = {}
    summary_payload = {
        key: value
        for key, value in summary_raw.items()
        if key not in {"entries", "sessionId", "clientId"}
    }
    summary = WorkspaceValueValidationSessionSummaryRecord(
        sessionId=str(row["id"]),
        clientId=str(row["client_id"]),
        **summary_payload,
    )
    return WorkspaceValueValidationSessionRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        status=str(row["status"] or "running"),  # type: ignore[arg-type]
        questionSet=question_set,
        completedQuestionIds=[str(item) for item in completed_question_ids_raw if str(item).strip()] if isinstance(completed_question_ids_raw, list) else [],
        summary=summary,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def create_workspace_value_validation_session(
    db: Database,
    *,
    payload: WorkspaceValueValidationSessionCreatePayloadRecord,
) -> WorkspaceValueValidationSessionRecord:
    ensure_workspace_value_validation_session_schema(db)
    timestamp = _now_iso()
    session_id = new_id("wvs")
    questions = _default_workspace_value_validation_questions()
    summary = WorkspaceValueValidationSessionSummaryRecord(sessionId=session_id, clientId=payload.clientId, verdict="hold")
    db.execute(
        """
        INSERT INTO workspace_value_validation_sessions(
            id, client_id, status, question_set_json, completed_question_ids_json, summary_json, created_at, updated_at
        )
        VALUES(?, ?, 'running', ?, '[]', ?, ?, ?)
        """,
        (
            session_id,
            payload.clientId,
            to_json([item.model_dump(mode="json") for item in questions]),
            to_json(summary.model_dump(mode="json")),
            timestamp,
            timestamp,
        ),
    )
    row = db.fetchone("SELECT * FROM workspace_value_validation_sessions WHERE id = ?", (session_id,))
    assert row is not None
    return _row_to_workspace_value_validation_session(row)


def list_workspace_value_validation_sessions(
    db: Database,
    *,
    client_id: str | None = None,
    limit: int = 20,
) -> list[WorkspaceValueValidationSessionRecord]:
    ensure_workspace_value_validation_session_schema(db)
    params: list[object] = []
    where = ""
    if str(client_id or "").strip():
        where = "WHERE client_id = ?"
        params.append(str(client_id).strip())
    params.append(max(int(limit), 1))
    rows = db.fetchall(
        f"""
        SELECT *
        FROM workspace_value_validation_sessions
        {where}
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        tuple(params),
    )
    return [_row_to_workspace_value_validation_session(row) for row in rows]


def get_workspace_value_validation_session(
    db: Database,
    *,
    session_id: str,
) -> WorkspaceValueValidationSessionRecord:
    ensure_workspace_value_validation_session_schema(db)
    row = db.fetchone("SELECT * FROM workspace_value_validation_sessions WHERE id = ?", (session_id,))
    if not row:
        raise KeyError("workspace_value_validation_session_not_found")
    return _row_to_workspace_value_validation_session(row)


def complete_workspace_value_validation_question(
    db: Database,
    *,
    session_id: str,
    payload: WorkspaceValueValidationSessionCompleteQuestionPayloadRecord,
) -> WorkspaceValueValidationSessionRecord:
    ensure_workspace_value_validation_session_schema(db)
    row = db.fetchone("SELECT * FROM workspace_value_validation_sessions WHERE id = ?", (session_id,))
    if not row:
        raise KeyError("workspace_value_validation_session_not_found")
    question_set_raw = from_json(str(row["question_set_json"] or "[]"), [])
    question_ids = [
        str(item.get("id") or "")
        for item in question_set_raw
        if isinstance(item, dict)
    ]
    if payload.questionId not in question_ids:
        raise ValueError("workspace_value_validation_question_not_found")
    summary_raw = from_json(str(row["summary_json"] or "{}"), {})
    if not isinstance(summary_raw, dict):
        summary_raw = {}
    entries = summary_raw.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    if not payload.reviewId or not payload.messageId:
        raise ValueError("review_message_question_mismatch")
    review_row = db.fetchone(
        """
        SELECT *
        FROM workspace_answer_value_reviews
        WHERE id = ? AND client_id = ?
        LIMIT 1
        """,
        (payload.reviewId, str(row["client_id"])),
    )
    if not review_row:
        raise ValueError("review_message_question_mismatch")
    review = _row_to_workspace_answer_value_review(review_row)
    if review.messageId != payload.messageId:
        raise ValueError("review_message_question_mismatch")
    for existing_question_id, existing_entry in entries.items():
        if existing_question_id == payload.questionId or not isinstance(existing_entry, dict):
            continue
        if str(existing_entry.get("reviewId") or "").strip() == payload.reviewId:
            raise ValueError("review_message_question_mismatch")
    entries[payload.questionId] = {
        "reviewId": payload.reviewId,
        "messageId": review.messageId,
        "usableAnswer": review.usableAnswer,
        "retryBannerShown": review.shouldShowRetryBanner,
        "manualBaselineMinutes": review.manualBaselineMinutes,
        "dataCenterReviewMinutes": review.dataCenterReviewMinutes,
        "proposalCreated": payload.proposalCreated,
        "executionTicketCreated": payload.executionTicketCreated,
        "reviewerNote": review.reviewerNote or payload.reviewerNote,
        "updatedAt": _now_iso(),
    }
    completed_ids = [item for item in question_ids if item in entries]
    session_summary = _compute_session_summary(
        session_id=str(row["id"]),
        client_id=str(row["client_id"]),
        entries=entries,
        total_questions=len(question_ids),
    )
    summary_payload = session_summary.model_dump(mode="json")
    summary_payload["entries"] = entries
    timestamp = _now_iso()
    db.execute(
        """
        UPDATE workspace_value_validation_sessions
        SET completed_question_ids_json = ?, summary_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            to_json(completed_ids),
            to_json(summary_payload),
            timestamp,
            session_id,
        ),
    )
    updated = db.fetchone("SELECT * FROM workspace_value_validation_sessions WHERE id = ?", (session_id,))
    assert updated is not None
    return _row_to_workspace_value_validation_session(updated)


def finish_workspace_value_validation_session(
    db: Database,
    *,
    session_id: str,
) -> WorkspaceValueValidationSessionRecord:
    ensure_workspace_value_validation_session_schema(db)
    row = db.fetchone("SELECT * FROM workspace_value_validation_sessions WHERE id = ?", (session_id,))
    if not row:
        raise KeyError("workspace_value_validation_session_not_found")
    summary_raw = from_json(str(row["summary_json"] or "{}"), {})
    if not isinstance(summary_raw, dict):
        summary_raw = {}
    verdict = str(summary_raw.get("verdict") or "hold")
    status = "completed" if verdict == "pass" else "failed" if verdict == "fail" else "completed"
    timestamp = _now_iso()
    db.execute(
        """
        UPDATE workspace_value_validation_sessions
        SET status = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, timestamp, session_id),
    )
    updated = db.fetchone("SELECT * FROM workspace_value_validation_sessions WHERE id = ?", (session_id,))
    assert updated is not None
    return _row_to_workspace_value_validation_session(updated)


def _row_to_workspace_answer_value_review(row) -> WorkspaceAnswerValueReviewRecord:
    status_raw = str(row["user_visible_quality_status"] or "").strip()
    status = status_raw if status_raw in {"ready", "usable_with_boundary", "degraded", "needs_retry"} else "degraded"
    usable_answer_raw = row["usable_answer"]
    usable_answer = None if usable_answer_raw is None else bool(int(usable_answer_raw))
    return WorkspaceAnswerValueReviewRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        messageId=str(row["message_id"]),
        prompt=str(row["prompt"] or ""),
        answerMode=str(row["answer_mode"] or ""),
        userVisibleQualityStatus=status,  # type: ignore[arg-type]
        shouldShowRetryBanner=bool(int(row["should_show_retry_banner"] or 0)),
        usableAnswer=usable_answer,
        reviewerNote=str(row["reviewer_note"] or ""),
        manualBaselineMinutes=float(row["manual_baseline_minutes"]) if row["manual_baseline_minutes"] is not None else None,
        dataCenterReviewMinutes=float(row["data_center_review_minutes"]) if row["data_center_review_minutes"] is not None else None,
        savedMinutes=float(row["saved_minutes"]) if row["saved_minutes"] is not None else None,
        createdAt=str(row["created_at"]),
    )


def create_workspace_answer_value_review(
    db: Database,
    *,
    payload: WorkspaceAnswerValueReviewPayloadRecord,
) -> WorkspaceAnswerValueReviewRecord:
    ensure_workspace_answer_value_review_schema(db)
    ensure_workspace_answer_quality_failure_schema(db)
    created_at = _now_iso()
    saved_minutes: float | None = None
    if payload.manualBaselineMinutes is not None and payload.dataCenterReviewMinutes is not None:
        saved_minutes = round(float(payload.manualBaselineMinutes) - float(payload.dataCenterReviewMinutes), 4)
    existing_rows = db.fetchall(
        """
        SELECT id
        FROM workspace_answer_value_reviews
        WHERE client_id = ? AND message_id = ?
        ORDER BY created_at DESC
        """,
        (payload.clientId, payload.messageId),
    )
    review_id = str(existing_rows[0]["id"]) if existing_rows else new_id("wavr")
    if len(existing_rows) > 1:
        for stale_row in existing_rows[1:]:
            db.execute("DELETE FROM workspace_answer_value_reviews WHERE id = ?", (str(stale_row["id"]),))
    if existing_rows:
        db.execute(
            """
            UPDATE workspace_answer_value_reviews
            SET prompt = ?, answer_mode = ?, user_visible_quality_status = ?,
                should_show_retry_banner = ?, usable_answer = ?, reviewer_note = ?,
                manual_baseline_minutes = ?, data_center_review_minutes = ?,
                saved_minutes = ?, created_at = ?
            WHERE id = ?
            """,
            (
                payload.prompt,
                payload.answerMode,
                payload.userVisibleQualityStatus,
                1 if payload.shouldShowRetryBanner else 0,
                None if payload.usableAnswer is None else (1 if payload.usableAnswer else 0),
                payload.reviewerNote,
                payload.manualBaselineMinutes,
                payload.dataCenterReviewMinutes,
                saved_minutes,
                created_at,
                review_id,
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO workspace_answer_value_reviews(
                id, client_id, message_id, prompt, answer_mode, user_visible_quality_status,
                should_show_retry_banner, usable_answer, reviewer_note, manual_baseline_minutes,
                data_center_review_minutes, saved_minutes, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                payload.clientId,
                payload.messageId,
                payload.prompt,
                payload.answerMode,
                payload.userVisibleQualityStatus,
                1 if payload.shouldShowRetryBanner else 0,
                None if payload.usableAnswer is None else (1 if payload.usableAnswer else 0),
                payload.reviewerNote,
                payload.manualBaselineMinutes,
                payload.dataCenterReviewMinutes,
                saved_minutes,
                created_at,
            ),
        )
    row = db.fetchone("SELECT * FROM workspace_answer_value_reviews WHERE id = ?", (review_id,))
    assert row is not None
    review = _row_to_workspace_answer_value_review(row)
    if payload.shouldShowRetryBanner:
        record_workspace_answer_quality_failure(
            db,
            client_id=payload.clientId,
            message_id=payload.messageId,
            prompt=payload.prompt,
            failure_type="retry_banner",
            severity="medium",
            details={
                "answerMode": payload.answerMode,
                "userVisibleQualityStatus": payload.userVisibleQualityStatus,
            },
        )
    if payload.usableAnswer is False:
        record_workspace_answer_quality_failure(
            db,
            client_id=payload.clientId,
            message_id=payload.messageId,
            prompt=payload.prompt,
            failure_type="user_marked_not_usable",
            severity="high",
            details={
                "answerMode": payload.answerMode,
                "userVisibleQualityStatus": payload.userVisibleQualityStatus,
                "reviewerNote": payload.reviewerNote,
            },
        )
    return review


def list_workspace_answer_value_reviews(
    db: Database,
    *,
    client_id: str | None = None,
    limit: int = 120,
) -> list[WorkspaceAnswerValueReviewRecord]:
    ensure_workspace_answer_value_review_schema(db)
    params: list[object] = []
    where = ""
    if str(client_id or "").strip():
        where = "WHERE client_id = ?"
        params.append(str(client_id).strip())
    params.append(max(int(limit), 1))
    rows = db.fetchall(
        f"""
        SELECT *
        FROM workspace_answer_value_reviews
        {where}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        tuple(params),
    )
    return [_row_to_workspace_answer_value_review(row) for row in rows]


def build_workspace_answer_value_summary(
    db: Database,
    *,
    client_id: str,
) -> WorkspaceAnswerValueSummaryRecord:
    ensure_workspace_answer_value_review_schema(db)
    proposal_created_count, execution_created_count, metric_errors = _count_answer_action_artifacts(db, client_id=client_id)
    rows = db.fetchall(
        """
        SELECT *
        FROM workspace_answer_value_reviews
        WHERE client_id = ?
        ORDER BY created_at DESC
        LIMIT 2000
        """,
        (client_id,),
    )
    review_count = len(rows)
    if review_count == 0:
        return WorkspaceAnswerValueSummaryRecord(
            clientId=client_id,
            proposalCreatedFromAnswerCount=proposal_created_count,
            executionTicketCreatedFromAnswerCount=execution_created_count,
            metricErrors=metric_errors,
        )

    usable_count = 0
    positive_review_count = 0
    negative_review_count = 0
    retry_banner_count = 0
    manual_values: list[float] = []
    review_values: list[float] = []
    saved_values: list[float] = []
    last_reviewed_at: str | None = None

    for row in rows:
        if row["usable_answer"] is not None and int(row["usable_answer"] or 0) == 1:
            usable_count += 1
            positive_review_count += 1
        elif row["usable_answer"] is not None:
            negative_review_count += 1
        if int(row["should_show_retry_banner"] or 0) == 1:
            retry_banner_count += 1
        if row["manual_baseline_minutes"] is not None:
            manual_values.append(float(row["manual_baseline_minutes"]))
        if row["data_center_review_minutes"] is not None:
            review_values.append(float(row["data_center_review_minutes"]))
        if row["saved_minutes"] is not None:
            saved_values.append(float(row["saved_minutes"]))
        if last_reviewed_at is None and row["created_at"]:
            last_reviewed_at = str(row["created_at"])

    avg_manual = round(sum(manual_values) / len(manual_values), 2) if manual_values else 0.0
    avg_review = round(sum(review_values) / len(review_values), 2) if review_values else 0.0
    estimated_saved_rate = 0.0
    if avg_manual > 0:
        estimated_saved_rate = round(max(avg_manual - avg_review, 0.0) / avg_manual, 4)
    elif saved_values:
        positives = [item for item in saved_values if item > 0]
        estimated_saved_rate = round(float(len(positives)) / float(len(saved_values)), 4)
    return WorkspaceAnswerValueSummaryRecord(
        clientId=client_id,
        reviewCount=review_count,
        usableAnswerRate=_safe_ratio(usable_count, review_count),
        retryBannerRate=_safe_ratio(retry_banner_count, review_count),
        averageManualBaselineMinutes=avg_manual,
        averageDataCenterReviewMinutes=avg_review,
        estimatedTimeSavedRate=estimated_saved_rate,
        positiveReviewCount=positive_review_count,
        negativeReviewCount=negative_review_count,
        lastReviewedAt=last_reviewed_at,
        proposalCreatedFromAnswerCount=proposal_created_count,
        executionTicketCreatedFromAnswerCount=execution_created_count,
        metricErrors=metric_errors,
    )
