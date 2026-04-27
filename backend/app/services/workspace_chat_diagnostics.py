from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import Database, from_json
from app.services.ai import classify_llm_error_kind
from app.services.evidence_quality import classify_evidence_quality_payload
from app.services.generation_runtime_policy import get_generation_runtime_state
from app.services.knowledge_v2 import compute_knowledge_status
from app.services.source_integrity import build_source_integrity_report


def _is_timeout(reason: str | None) -> bool:
    text = str(reason or "").lower()
    return any(token in text for token in ("timeout", "timed out", "read timeout", "超时"))


def _safe_ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(float(num) / float(den), 4)


def _bucket_status(score: float, *, warning_at: float, critical_at: float) -> str:
    if score >= critical_at:
        return "critical"
    if score >= warning_at:
        return "warning"
    return "ok"


def _classify_parse_failure(error_text: str) -> str:
    lowered = str(error_text or "").lower()
    if any(token in lowered for token in ("not found", "no such file", "不存在")):
        return "file_missing"
    if any(token in lowered for token in ("permission denied", "权限")):
        return "permission_denied"
    if any(token in lowered for token in ("unsupported", "不支持")):
        return "unsupported_format"
    if any(token in lowered for token in ("ocr", "scan", "扫描")):
        return "ocr_required"
    if any(token in lowered for token in ("empty", "为空", "无正文", "no text")):
        return "empty_text"
    if any(token in lowered for token in ("parser", "解析")):
        return "parser_exception"
    return "unknown"


def build_workspace_chat_diagnostics(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    recent_messages: int = 20,
) -> dict[str, Any]:
    rows = db.fetchall(
        """
        SELECT m.*
        FROM chat_messages m
        JOIN chat_threads t ON t.id = m.thread_id
        WHERE t.client_id = ? AND m.role = 'assistant' AND m.status = 'success'
        ORDER BY m.created_at DESC
        LIMIT ?
        """,
        (client_id, recent_messages),
    )

    total = len(rows)
    fallback_count = 0
    timeout_count = 0
    retrieval_ms_values: list[float] = []
    llm_ms_values: list[float] = []
    intent_distribution: dict[str, int] = {}
    failure_reason_distribution: dict[str, int] = {}
    compact_first_count = 0
    local_only_count = 0
    data_center_primary_count = 0
    fallback_template_used_count = 0
    partial_preserved_count = 0
    system_failure_count = 0
    llm_error_kind_distribution: dict[str, int] = {}
    kernel_total_ms_values: list[float] = []
    kernel_stage_sums: dict[str, float] = {}
    kernel_stage_counts: dict[str, int] = {}

    evidence_total = 0
    ppt_noise_count = 0
    generated_draft_count = 0
    memory_answer_count = 0
    short_excerpt_count = 0
    raw_chunk_hit_values: list[int] = []
    zero_evidence_count = 0
    low_coverage_count = 0

    approved_count = 0
    candidate_count = 0
    context_quality = "none"

    for row in rows:
        answer_mode = str(row["answer_mode"] or "")
        if answer_mode == "grounded_fallback":
            fallback_count += 1
        if answer_mode == "system_failure":
            system_failure_count += 1

        failure_reason = str(row["failure_reason"] or "")
        if failure_reason.strip():
            failure_reason_distribution[failure_reason] = failure_reason_distribution.get(failure_reason, 0) + 1
        if _is_timeout(failure_reason):
            timeout_count += 1

        timing = from_json(str(row["timing_json"] or "{}"), {})
        if isinstance(timing, dict):
            retrieval_ms = float(timing.get("retrievalMs", 0.0) or 0.0)
            llm_ms = float(timing.get("llmMs", 0.0) or 0.0)
            if retrieval_ms > 0:
                retrieval_ms_values.append(retrieval_ms)
            if llm_ms > 0:
                llm_ms_values.append(llm_ms)

        retrieval_summary = from_json(str(row["retrieval_summary_json"] or "{}"), {})
        if isinstance(retrieval_summary, dict):
            intent = str(retrieval_summary.get("answerIntent") or "general")
            intent_distribution[intent] = intent_distribution.get(intent, 0) + 1
            if bool(retrieval_summary.get("dataCenterPrimaryEnabled")):
                data_center_primary_count += 1
            if bool(retrieval_summary.get("fallbackTemplateUsed")):
                fallback_template_used_count += 1
            if bool(retrieval_summary.get("partialGenerationPreserved")):
                partial_preserved_count += 1
            generation_policy = retrieval_summary.get("generationPolicy")
            if isinstance(generation_policy, dict):
                if bool(generation_policy.get("shouldUseCompactFirst")):
                    compact_first_count += 1
                if bool(generation_policy.get("shouldUseLocalOnly")):
                    local_only_count += 1
            llm_error_kind = str(retrieval_summary.get("llmErrorKind") or "").strip()
            if not llm_error_kind and failure_reason:
                llm_error_kind = classify_llm_error_kind(
                    str(retrieval_summary.get("generationFailureDetail") or failure_reason)
                )
            if llm_error_kind:
                llm_error_kind_distribution[llm_error_kind] = llm_error_kind_distribution.get(llm_error_kind, 0) + 1
            kernel_profiling = retrieval_summary.get("kernelProfiling")
            if isinstance(kernel_profiling, dict):
                total_ms = float(kernel_profiling.get("totalMs") or 0.0)
                if total_ms > 0:
                    kernel_total_ms_values.append(total_ms)
                for stage_name, stage_value in kernel_profiling.items():
                    stage_key = str(stage_name or "").strip()
                    if not stage_key or stage_key == "totalMs":
                        continue
                    stage_ms = float(stage_value or 0.0)
                    if stage_ms <= 0:
                        continue
                    kernel_stage_sums[stage_key] = kernel_stage_sums.get(stage_key, 0.0) + stage_ms
                    kernel_stage_counts[stage_key] = kernel_stage_counts.get(stage_key, 0) + 1

            raw_chunk_hit_values.append(int(retrieval_summary.get("rawChunkHitCount") or 0))
            if int(retrieval_summary.get("selectedEvidenceCount") or 0) <= 0:
                zero_evidence_count += 1
            coverage = float(retrieval_summary.get("coverage") or 0.0)
            if 0 < coverage < 0.3:
                low_coverage_count += 1

            answer_sections = retrieval_summary.get("stateAnswerSections")
            if isinstance(answer_sections, dict):
                approved_count += len(answer_sections.get("official", []) or [])
                candidate_count += len(answer_sections.get("candidate", []) or [])

            if str(retrieval_summary.get("pageContextQuality") or "").strip():
                context_quality = str(retrieval_summary.get("pageContextQuality"))

        evidence_json = from_json(str(row["evidence_json"] or "[]"), [])
        if isinstance(evidence_json, list):
            evidence_total += len(evidence_json)
            if len(evidence_json) == 0:
                zero_evidence_count += 1
            for item in evidence_json:
                if not isinstance(item, dict):
                    continue
                quality = classify_evidence_quality_payload(item)
                if quality.sourceKind in {"ppt_visual", "ppt_master", "template_page"}:
                    ppt_noise_count += 1
                if quality.sourceKind == "generated_answer":
                    generated_draft_count += 1
                if quality.sourceKind == "memory_answer":
                    memory_answer_count += 1
                if quality.sourceKind == "short_excerpt":
                    short_excerpt_count += 1

    avg_retrieval_ms = round(sum(retrieval_ms_values) / len(retrieval_ms_values), 2) if retrieval_ms_values else 0.0
    avg_llm_ms = round(sum(llm_ms_values) / len(llm_ms_values), 2) if llm_ms_values else 0.0
    avg_raw_chunk_hits = round(sum(raw_chunk_hit_values) / len(raw_chunk_hit_values), 2) if raw_chunk_hit_values else 0.0
    kernel_p95_ms = 0.0
    kernel_slow_run_count = 0
    kernel_slowest_stage: str | None = None
    if kernel_total_ms_values:
        sorted_kernel = sorted(kernel_total_ms_values)
        p95_index = min(len(sorted_kernel) - 1, max(0, int(round((len(sorted_kernel) - 1) * 0.95))))
        kernel_p95_ms = round(float(sorted_kernel[p95_index]), 2)
        kernel_slow_run_count = sum(1 for value in kernel_total_ms_values if value >= max(1500.0, kernel_p95_ms))
    if kernel_stage_sums:
        stage_avg = {
            key: (kernel_stage_sums[key] / max(kernel_stage_counts.get(key, 1), 1))
            for key in kernel_stage_sums
        }
        kernel_slowest_stage = max(stage_avg, key=stage_avg.get)

    runtime_state = get_generation_runtime_state(
        db,
        client_id=client_id,
        answer_intent=max(intent_distribution, key=intent_distribution.get) if intent_distribution else "general",
    )
    knowledge_status = compute_knowledge_status(db, client_id, data_dir=data_dir)
    parse_failure_rows = db.fetchall(
        """
        SELECT parse_error
        FROM v2_documents
        WHERE client_id = ? AND COALESCE(parse_status, 'ready') != 'ready'
        LIMIT 300
        """,
        (client_id,),
    )
    parse_failure_buckets: dict[str, int] = {}
    for row in parse_failure_rows:
        bucket = _classify_parse_failure(str(row["parse_error"] or ""))
        parse_failure_buckets[bucket] = parse_failure_buckets.get(bucket, 0) + 1

    retry_summary_raw = db.get_setting(f"knowledge.parse_retry_summary:{client_id}") or "{}"
    retry_summary = from_json(retry_summary_raw, {})
    if not isinstance(retry_summary, dict):
        retry_summary = {}

    source_integrity_match: bool | None = None
    running_build_version: str | None = None
    expected_build_version: str | None = None
    try:
        running_root = Path(__file__).resolve().parents[1]
        workspace_root = (Path.cwd() / "backend").resolve()
        report = build_source_integrity_report(
            running_backend_root=running_root,
            expected_workspace_root=workspace_root if workspace_root.exists() else None,
            build_version=str(db.get_setting("runtime.build_version", "") or "").strip() or None,
            git_commit=str(db.get_setting("runtime.git_commit", "") or "").strip() or None,
            runtime_mode=str(db.get_setting("runtime.mode", "") or "").strip() or None,
        )
        raw_source_integrity_match = report.get("match")
        source_integrity_match = raw_source_integrity_match if isinstance(raw_source_integrity_match, bool) else None
        running_build_version = str(report.get("buildVersion") or "").strip() or None
        expected_build_version = str(report.get("workspaceBuildVersion") or "").strip() or running_build_version
    except Exception:
        source_integrity_match = None
        running_build_version = str(db.get_setting("runtime.build_version", "") or "").strip() or None
        expected_build_version = running_build_version

    total_safe = max(total, 1)
    general_ratio = round(float(intent_distribution.get("general", 0)) / float(total_safe), 4)
    business_strategy_count = int(intent_distribution.get("business_profile", 0)) + int(intent_distribution.get("strategy_profile", 0))
    business_strategy_miss_count = 0
    if business_strategy_count == 0:
        business_strategy_miss_count = max(0, int(intent_distribution.get("general", 0)))

    dominant_failure_reason = None
    if failure_reason_distribution:
        dominant_failure_reason = max(failure_reason_distribution, key=failure_reason_distribution.get)
    dominant_llm_error_kind = None
    if llm_error_kind_distribution:
        dominant_llm_error_kind = max(llm_error_kind_distribution, key=llm_error_kind_distribution.get)

    generation_timeout_score = _safe_ratio(timeout_count, total_safe)
    evidence_noise_score = _safe_ratio(ppt_noise_count + generated_draft_count, max(evidence_total, 1))
    parse_failure_score = _safe_ratio(sum(parse_failure_buckets.values()), max(int(knowledge_status.get("totalDocuments") or 1), 1))

    breakdown = {
        "generation": {
            "status": _bucket_status(generation_timeout_score, warning_at=0.2, critical_at=0.4),
            "details": {
                "timeoutCount": timeout_count,
                "fallbackCount": fallback_count,
                "compactFirstCount": compact_first_count,
                "localOnlyCount": local_only_count,
                "stableFallbackActive": bool(runtime_state.stableFallbackActive),
                "dominantFailureReason": dominant_failure_reason,
            },
        },
        "retrieval": {
            "status": _bucket_status(_safe_ratio(low_coverage_count + zero_evidence_count, total_safe), warning_at=0.2, critical_at=0.4),
            "details": {
                "avgRawChunkHitCount": avg_raw_chunk_hits,
                "zeroEvidenceCount": zero_evidence_count,
                "lowCoverageCount": low_coverage_count,
            },
        },
        "evidenceQuality": {
            "status": _bucket_status(evidence_noise_score, warning_at=0.2, critical_at=0.35),
            "details": {
                "pptNoiseRatio": _safe_ratio(ppt_noise_count, max(evidence_total, 1)),
                "generatedDraftRatio": _safe_ratio(generated_draft_count, max(evidence_total, 1)),
                "memoryAnswerRatio": _safe_ratio(memory_answer_count, max(evidence_total, 1)),
                "shortExcerptRatio": _safe_ratio(short_excerpt_count, max(evidence_total, 1)),
            },
        },
        "dataIntegrity": {
            "status": _bucket_status(parse_failure_score, warning_at=0.1, critical_at=0.25),
            "details": {
                "parseFailedDocuments": int(knowledge_status.get("parseFailedDocuments") or 0),
                "parseFailureBuckets": parse_failure_buckets,
                "approvedJudgmentCount": approved_count,
                "candidateJudgmentCount": candidate_count,
                "sourceIntegrityMatch": source_integrity_match,
                "lastParseRetryAt": retry_summary.get("lastRetryAt"),
                "lastParseRetrySucceeded": retry_summary.get("lastRetrySucceeded"),
            },
        },
        "intent": {
            "status": _bucket_status(general_ratio, warning_at=0.4, critical_at=0.7),
            "details": {
                "generalRatio": general_ratio,
                "businessStrategyMissCount": business_strategy_miss_count,
            },
        },
    }

    root_cause_summary: list[str] = []
    recommended_fixes: list[str] = []
    if generation_timeout_score >= 0.2:
        root_cause_summary.append("LLM 超时是主要问题")
        recommended_fixes.append("清理或等待 generation cooldown 后自动 probe")
    if dominant_llm_error_kind == "ssl_handshake_timeout":
        root_cause_summary.append("模型连接握手超时偏多")
        recommended_fixes.append("先做当前 provider 连通性检测，必要时切换稳定 provider")
    if evidence_noise_score >= 0.2:
        root_cause_summary.append("证据噪声偏高")
        recommended_fixes.append("检查 PPT/草稿类资料切块质量并重建索引")
    if parse_failure_buckets:
        root_cause_summary.append("存在解析失败文档")
        recommended_fixes.append("重试解析失败文档，必要时补 OCR 或手工摘要")
    if general_ratio >= 0.4:
        root_cause_summary.append("general intent 占比偏高")
        recommended_fixes.append("检查 business/strategy/introduction 意图规则")
    if source_integrity_match is False:
        root_cause_summary.insert(0, "当前运行态与工作区源码不一致")
        recommended_fixes.insert(0, "先确认桌面应用运行的是最新构建，再判断数据中心与模型效果")
    if not root_cause_summary:
        root_cause_summary.append("当前诊断未发现明显阻塞项")
        recommended_fixes.append("继续观察 shadow 与 answer quality 指标")

    return {
        "clientId": client_id,
        "recentMessages": int(total),
        "groundedFallbackRate": _safe_ratio(fallback_count, total),
        "llmTimeoutRate": _safe_ratio(timeout_count, total),
        "sourceIntegrityMatch": source_integrity_match,
        "runningBuildVersion": running_build_version,
        "expectedBuildVersion": expected_build_version,
        "dominantLlmErrorKind": dominant_llm_error_kind,
        "fallbackTemplateUsedRate": _safe_ratio(fallback_template_used_count, total),
        "dataCenterPrimaryEnabledRate": _safe_ratio(data_center_primary_count, total),
        "partialPreservedRate": _safe_ratio(partial_preserved_count, total),
        "systemFailureRate": _safe_ratio(system_failure_count, total),
        "stableFallbackActive": bool(runtime_state.stableFallbackActive),
        "stableFallbackReason": runtime_state.stableFallbackReason,
        "avgRetrievalMs": avg_retrieval_ms,
        "avgLlmMs": avg_llm_ms,
        "intentDistribution": intent_distribution,
        "materialQuality": {
            "pptNoiseRatio": _safe_ratio(ppt_noise_count, evidence_total),
            "generatedDraftRatio": _safe_ratio(generated_draft_count, evidence_total),
            "memoryAnswerRatio": _safe_ratio(memory_answer_count, evidence_total),
        },
        "dataCenterQuality": {
            "approvedJudgmentCount": approved_count,
            "candidateJudgmentCount": candidate_count,
            "parseFailedDocuments": int(knowledge_status.get("parseFailedDocuments") or 0),
            "parseFailureBuckets": parse_failure_buckets,
            "lastParseRetryAt": retry_summary.get("lastRetryAt"),
            "lastParseRetrySucceeded": retry_summary.get("lastRetrySucceeded"),
            "contextQuality": context_quality,
        },
        "breakdown": breakdown,
        "rootCauseSummary": root_cause_summary,
        "recommendedFixes": list(dict.fromkeys(recommended_fixes))[:8],
        "kernelP95Ms": kernel_p95_ms,
        "kernelSlowRunCount": int(kernel_slow_run_count),
        "kernelSlowestStage": kernel_slowest_stage,
    }
