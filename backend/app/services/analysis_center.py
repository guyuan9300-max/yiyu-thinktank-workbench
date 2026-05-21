from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app.db import Database, from_json, to_json
from app.models import (
    AnalysisAuthorityLevel,
    AnalysisBackfillMainChainJobRecord,
    AnalysisBackfillMainChainPayload,
    AnalysisBackfillMainChainResultRecord,
    AnalysisCenterSummaryRecord,
    AnalysisIntentProfile,
    AnalysisJobCreatePayload,
    AnalysisJobRecord,
    AnalysisJobStageRunRecord,
    AnalysisLane,
    AnalysisMigrationMetricsRecord,
    AnalysisOriginType,
    AnalysisQualityTier,
    AnalysisRejectedReason,
    AnalysisReviewState,
    AnalysisScopeType,
    AnalysisStaleReason,
    ApprovalDecisionPayload,
    ApprovalStateRecord,
    ApprovalRecordRecord,
    ClientAnalysisRunRecord,
    ClientDnaModuleRecord,
    ClientWorkspaceResponse,
    ConflictGroupRecord,
    ContextPackRecord,
    DnaDeltaCreatePayload,
    DnaDeltaRecord,
    DocumentCardRecord,
    EventLineMemorySnapshot,
    JudgmentBundleRecord,
    JudgmentConfirmPayload,
    JudgmentVersionRecord,
    MemoryStatus,
    OpenQuestionRecord,
    OrganizationNotebookSnapshot,
    ProjectFlowRecord,
    ProjectModuleRecord,
    RuntimeRunLogRecord,
    ResolutionCandidateRecord,
    ResolutionScopeRecord,
    ResolutionTraceRecord,
    TaskRecord,
    ThemeClusterRecord,
)


@dataclass
class AnalysisCenterProjectionBundle:
    summary: AnalysisCenterSummaryRecord
    latest_context_pack: ContextPackRecord | None
    judgment_bundle: JudgmentBundleRecord | None
    latest_resolution_trace: ResolutionTraceRecord | None
    latest_judgments: list[JudgmentVersionRecord]
    latest_topics: list[ThemeClusterRecord]
    latest_conflicts: list[ConflictGroupRecord]
    latest_open_questions: list[OpenQuestionRecord]
    latest_run_logs: list[RuntimeRunLogRecord]


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "::".join(part.strip() for part in parts if part is not None)
    return f"{prefix}_{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"


def _model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _parse_json_list(value: str | None) -> list[str]:
    data = from_json(value, [])
    return [str(item) for item in data] if isinstance(data, list) else []


def _parse_json_dict(value: str | None) -> dict[str, Any]:
    data = from_json(value, {})
    return data if isinstance(data, dict) else {}


def _first_non_empty(*values: str | None, fallback: str = "") -> str:
    for value in values:
        text = (value or "").strip()
        if text:
            return text
    return fallback


_ATTACHMENT_INGEST_BOILERPLATE_MARKERS = (
    "已作为任务附件进入项目资料库",
    "可用于后续检索、问答与事件线证据引用",
    "任务附件已进入项目资料库",
)


def looks_like_attachment_ingest_boilerplate(value: str | None) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return False
    if any(marker in text for marker in _ATTACHMENT_INGEST_BOILERPLATE_MARKERS):
        return True
    lowered = text.lower()
    file_name_like = re.match(r"^[^\s]+\.(?:jpg|jpeg|png|gif|pdf|doc|docx|ppt|pptx|xls|xlsx|txt|md)\b", lowered)
    return bool(file_name_like and ("项目资料库" in text or "后续检索" in text or "问答" in text))


def _first_non_empty_non_boilerplate(*values: str | None, fallback: str = "") -> str:
    for value in values:
        text = (value or "").strip()
        if text and not looks_like_attachment_ingest_boilerplate(text):
            return text
    return fallback


def _truncate(value: str | None, limit: int = 160) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 1]}…"


def _unique(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        text = (raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


_MAIN_CHAIN_CANARY_FEATURE_FLAG = "main-chain-canary"


_AUTHORITY_RANK: dict[AnalysisAuthorityLevel, int] = {
    "fallback": 0,
    "candidate": 1,
    "approved": 2,
}

_STALE_REASON_MAP: dict[str, AnalysisStaleReason] = {
    "new_document": "source_snapshot_changed",
    "scope_changed": "scope_no_longer_primary",
    "manual_override": "manual_invalidation",
    "superseded_by_newer_record": "superseded_by_newer_judgment",
    "source_snapshot_changed": "source_snapshot_changed",
    "approval_revoked": "approval_revoked",
    "scope_no_longer_primary": "scope_no_longer_primary",
    "insufficient_evidence": "insufficient_evidence",
    "manual_invalidation": "manual_invalidation",
    "superseded_by_newer_judgment": "superseded_by_newer_judgment",
}

_INTENT_SCOPE_ORDER: dict[AnalysisIntentProfile, tuple[AnalysisScopeType, ...]] = {
    "task_ai": ("event_line", "flow", "module", "client"),
    "weekly_review": ("event_line", "flow", "module", "client"),
    "meeting_enhance": ("event_line", "flow", "module", "client"),
    "client_overview": ("client", "module", "flow", "event_line"),
    "dna_summary": ("client", "module", "flow", "event_line"),
    "strategic_cockpit": ("client", "event_line", "module", "flow"),
}

_SCOPE_GRANULARITY: dict[AnalysisScopeType, int] = {
    "task": 0,
    "meeting": 1,
    "event_line": 2,
    "flow": 3,
    "module": 4,
    "client": 5,
}

_CANDIDATE_REVIEW_WARNING_AFTER_HOURS = 24
_CANDIDATE_REVIEW_OVERDUE_AFTER_HOURS = 72
_ANALYSIS_BACKFILL_CONSECUTIVE_LIMIT = 2
_ANALYSIS_WORKER_BUCKETS = ("interactive", "system", "backfill", "unknown")


def _hash_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _normalize_stale_reason(value: str | None) -> AnalysisStaleReason | None:
    text = (value or "").strip()
    if not text:
        return None
    return _STALE_REASON_MAP.get(text, "manual_invalidation")


def _parse_dt(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _serialize_snapshot(value: Any) -> str:
    if isinstance(value, str):
        return value
    return to_json(value)


def _build_snapshot_hash(value: Any) -> str:
    return _hash_text(_serialize_snapshot(value))


def _build_canary_exclusion_scope(db: Database) -> dict[str, set[str]]:
    canary_job_ids: set[str] = set()
    for row in db.fetchall("SELECT id, feature_flags_json FROM analysis_jobs"):
        feature_flags = _parse_json_dict(row["feature_flags_json"])
        if bool(feature_flags.get(_MAIN_CHAIN_CANARY_FEATURE_FLAG)):
            canary_job_ids.add(str(row["id"]))
    if not canary_job_ids:
        return {
            "judgment_versions": set(),
            "dna_deltas": set(),
            "conflict_groups": set(),
        }

    placeholders = ",".join("?" for _ in canary_job_ids)
    context_pack_ids = {
        str(row["id"])
        for row in db.fetchall(
            f"SELECT id FROM context_packs WHERE job_id IN ({placeholders})",
            tuple(canary_job_ids),
        )
    }
    if not context_pack_ids:
        return {
            "judgment_versions": set(),
            "dna_deltas": set(),
            "conflict_groups": set(),
        }

    context_placeholders = ",".join("?" for _ in context_pack_ids)

    def list_ids(table_name: str) -> set[str]:
        return {
            str(row["id"])
            for row in db.fetchall(
                f"SELECT id FROM {table_name} WHERE context_pack_id IN ({context_placeholders})",
                tuple(context_pack_ids),
            )
        }

    return {
        "judgment_versions": list_ids("judgment_versions"),
        "dna_deltas": list_ids("dna_deltas"),
        "conflict_groups": list_ids("conflict_groups"),
    }


def _validate_truth_boundary(
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> None:
    if origin_type == "human_override" and authority_level == "fallback":
        raise ValueError("human_override 不能保持 fallback 权威级别")
    if authority_level == "approved" and quality_tier != "reviewed":
        raise ValueError("approved 对象必须是 reviewed")
    if origin_type == "projection" and authority_level == "approved":
        raise ValueError("projection 不能直接成为 approved")


def _derive_child_authority(*parents: AnalysisAuthorityLevel | None) -> AnalysisAuthorityLevel:
    ordered = [parent for parent in parents if parent]
    if any(parent == "fallback" for parent in ordered):
        return "fallback"
    if any(parent == "candidate" for parent in ordered):
        return "candidate"
    return "approved"


def _truth_fields(
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> dict[str, str]:
    _validate_truth_boundary(
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
    )
    return {
        "origin_type": origin_type,
        "authority_level": authority_level,
        "quality_tier": quality_tier,
    }


def _compute_scope_snapshot_hash(
    workspace: ClientWorkspaceResponse,
    *,
    scope_type: AnalysisScopeType,
    scope_id: str,
) -> str:
    payload: dict[str, Any] = {
        "clientId": workspace.client.id,
        "scopeType": scope_type,
        "scopeId": scope_id,
        "documents": [(item.id, item.updatedAt) for item in workspace.documentCards[:40]],
        "meetings": [(item.id, item.updatedAt, item.stage) for item in workspace.meetings[:24]],
        "tasks": [
            (
                item.id,
                item.updatedAt,
                item.status,
                item.eventLineId,
                item.projectModuleId,
                item.projectFlowId,
            )
            for item in workspace.relatedTasks[:80]
            if scope_type == "client"
            or (scope_type == "event_line" and item.eventLineId == scope_id)
            or (scope_type == "module" and item.projectModuleId == scope_id)
            or (scope_type == "flow" and item.projectFlowId == scope_id)
        ],
        "dnaModules": [(item.moduleKey, item.updatedAt, item.hasDocument) for item in workspace.dnaModules],
    }
    return _build_snapshot_hash(payload)


def _mark_previous_record_stale(
    db: Database,
    table_name: str,
    previous_id: str | None,
    *,
    invalidated_by: str,
    stale_reason: str,
    now: str,
) -> None:
    if not previous_id:
        return
    normalized_reason = _normalize_stale_reason(stale_reason)
    db.execute(
        f"""
        UPDATE {table_name}
        SET invalidated_by = ?, stale_reason = ?, updated_at = ?
        WHERE id = ? AND COALESCE(invalidated_by, '') = ''
        """,
        (invalidated_by, normalized_reason, now, previous_id),
    )


class DerivedSyncSerializer:
    @staticmethod
    def serialize_context_pack(
        context_pack: ContextPackRecord,
        themes: list[ThemeClusterRecord],
        conflicts: list[ConflictGroupRecord],
        open_questions: list[OpenQuestionRecord],
    ) -> dict[str, Any]:
        return {
            "contextPackId": context_pack.id,
            "targetType": context_pack.targetType,
            "targetId": context_pack.targetId,
            "originType": context_pack.originType,
            "authorityLevel": context_pack.authorityLevel,
            "qualityTier": context_pack.qualityTier,
            "sourceSnapshotHash": context_pack.sourceSnapshotHash,
            "promptVersion": context_pack.promptVersion,
            "evidenceCount": context_pack.evidenceCount,
            "themeTitles": [item.title for item in themes[:6]],
            "conflictTitles": [item.title for item in conflicts[:4]],
            "openQuestions": [item.question for item in open_questions[:6]],
            "themeRefs": [item.id for item in themes[:6]],
            "conflictRefs": [item.id for item in conflicts[:4]],
            "questionRefs": [item.id for item in open_questions[:6]],
            "updatedAt": context_pack.updatedAt,
        }


def _upsert(db: Database, table: str, payload: dict[str, Any], conflict_columns: tuple[str, ...] = ("id",)) -> None:
    columns = list(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column not in conflict_columns)
    sql = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT({", ".join(conflict_columns)}) DO UPDATE SET {updates}
    """
    db.execute(sql, tuple(payload[column] for column in columns))


def _upsert_stage_run(db: Database, stage: AnalysisJobStageRunRecord) -> None:
    _upsert(
        db,
        "job_stage_runs",
        {
            "id": stage.id,
            "job_id": stage.jobId,
            "stage_name": stage.stageName,
            "status": stage.status,
            "provider": stage.provider,
            "model_name": stage.modelName,
            "lane": stage.lane,
            "cache_key": stage.cacheKey,
            "cache_hit": int(stage.cacheHit),
            "degraded": int(stage.degraded),
            "evidence_count": stage.evidenceCount,
            "topic_count": stage.topicCount,
            "conflict_count": stage.conflictCount,
            "context_time_range": stage.contextTimeRange,
            "metrics_json": to_json(stage.metrics),
            "detail": stage.detail,
            "correlation_id": stage.correlationId,
            "started_at": stage.startedAt,
            "finished_at": stage.finishedAt,
            "created_at": stage.createdAt,
            "updated_at": stage.updatedAt,
        },
    )


def _upsert_analysis_job(db: Database, job: AnalysisJobRecord) -> None:
    _upsert(
        db,
        "analysis_jobs",
        {
            "id": job.id,
            "job_type": job.jobType,
            "client_id": job.clientId,
            "scope_type": job.scopeType,
            "scope_id": job.scopeId,
            "status": job.status,
            "priority": job.priority,
            "trigger_type": job.triggerType,
            "intent_profile": job.intentProfile,
            "question": job.question,
            "source_snapshot": job.sourceSnapshot,
            "source_snapshot_hash": job.sourceSnapshotHash,
            "dedupe_key": job.dedupeKey,
            "feature_flags_json": to_json(job.featureFlags),
            "progress": job.progress,
            "stage_label": job.stageLabel,
            "run_log_id": job.runLogId,
            "error": job.error,
            "locked_by": job.lockedBy,
            "locked_at": job.lockedAt,
            "lock_expires_at": job.lockExpiresAt,
            "attempt_count": job.attemptCount,
            "last_error": job.lastError,
            "created_at": job.createdAt,
            "updated_at": job.updatedAt,
            "started_at": job.startedAt,
            "finished_at": job.finishedAt,
        },
    )


def _upsert_runtime_run_log(db: Database, record: RuntimeRunLogRecord) -> None:
    _upsert(
        db,
        "runtime_run_logs",
        {
            "id": record.id,
            "client_id": record.clientId,
            "job_id": record.jobId,
            "analysis_job_id": record.analysisJobId,
            "stage_run_id": record.stageRunId,
            "context_pack_id": record.contextPackId,
            "judgment_version_id": record.judgmentVersionId,
            "correlation_id": record.correlationId,
            "provider": record.provider,
            "model": record.model,
            "lane": record.lane,
            "cache_hit": int(record.cacheHit),
            "degraded": int(record.degraded),
            "document_count": record.documentCount,
            "evidence_count": record.evidenceCount,
            "conflict_count": record.conflictCount,
            "context_time_range": record.contextTimeRange,
            "prompt_version": record.promptVersion,
            "schema_version": record.schemaVersion,
            "summary": record.summary,
            "detail_json": to_json(record.detail),
            "created_at": record.createdAt,
        },
    )


def _upsert_doc_skeleton(db: Database, record: dict[str, Any]) -> None:
    _upsert(
        db,
        "doc_skeletons",
        {
            "id": record["id"],
            "client_id": record["client_id"],
            "document_id": record["document_id"],
            "title": record["title"],
            "outline_json": to_json(record["outline"]),
            "entities_json": to_json(record["entities"]),
            "time_range": record["time_range"],
            "parser_version": record["parser_version"],
            "source_snapshot": record["source_snapshot"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        },
    )


def _upsert_evidence_card(db: Database, record: dict[str, Any]) -> None:
    _validate_truth_boundary(
        origin_type=record["origin_type"],
        authority_level=record["authority_level"],
        quality_tier=record["quality_tier"],
    )
    _upsert(
        db,
        "evidence_cards",
        {
            "id": record["id"],
            "client_id": record["client_id"],
            "scope_type": record["scope_type"],
            "scope_id": record["scope_id"],
            "origin_type": record["origin_type"],
            "authority_level": record["authority_level"],
            "quality_tier": record["quality_tier"],
            "source_type": record["source_type"],
            "source_id": record["source_id"],
            "source_ref": record["source_ref"],
            "quote": record["quote"],
            "normalized_claim": record["normalized_claim"],
            "evidence_type": record["evidence_type"],
            "polarity": record["polarity"],
            "tags_json": to_json(record["tags"]),
            "topic_keys_json": to_json(record["topic_keys"]),
            "confidence": record["confidence"],
            "time_anchor": record["time_anchor"],
            "document_id": record["document_id"],
            "event_line_id": record["event_line_id"],
            "task_id": record["task_id"],
            "meeting_id": record["meeting_id"],
            "module_id": record["module_id"],
            "flow_id": record["flow_id"],
            "review_state": record["review_state"],
            "fingerprint": record["fingerprint"],
            "normalized_claim_hash": record["normalized_claim_hash"],
            "source_ref_hash": record["source_ref_hash"],
            "evidence_fingerprint": record["evidence_fingerprint"],
            "normalizer_version": record["normalizer_version"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        },
    )


def _upsert_theme_cluster(db: Database, record: ThemeClusterRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "theme_clusters",
        {
            "id": record.id,
            "client_id": record.clientId,
            "scope_type": record.scopeType,
            "scope_id": record.scopeId,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "theme_key": record.themeKey,
            "title": record.title,
            "support_ids_json": to_json(record.supportIds),
            "oppose_ids_json": to_json(record.opposeIds),
            "gap_summary": record.gapSummary,
            "latest_change_summary": record.latestChangeSummary,
            "evidence_count": record.evidenceCount,
            "version": record.version,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
        conflict_columns=("client_id", "scope_type", "scope_id", "theme_key"),
    )


def _upsert_conflict_group(db: Database, record: ConflictGroupRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "conflict_groups",
        {
            "id": record.id,
            "client_id": record.clientId,
            "scope_type": record.scopeType,
            "scope_id": record.scopeId,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "conflict_type": record.conflictType,
            "title": record.title,
            "summary": record.summary,
            "evidence_ids_json": to_json(record.evidenceIds),
            "unresolved_question_ids_json": to_json(record.unresolvedQuestionIds),
            "resolution_status": record.resolutionStatus,
            "severity": record.severity,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_open_question(db: Database, record: OpenQuestionRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "open_questions",
        {
            "id": record.id,
            "client_id": record.clientId,
            "scope_type": record.scopeType,
            "scope_id": record.scopeId,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "theme_key": record.themeKey,
            "question": record.question,
            "reason": record.reason,
            "blocker_level": record.blockerLevel,
            "status": record.status,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_context_pack(db: Database, record: ContextPackRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "context_packs",
        {
            "id": record.id,
            "client_id": record.clientId,
            "job_id": record.jobId,
            "target_type": record.targetType,
            "target_id": record.targetId,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "supersedes_id": record.supersedesId,
            "source_snapshot_hash": record.sourceSnapshotHash,
            "stale_reason": _normalize_stale_reason(record.staleReason),
            "invalidated_by": record.invalidatedBy,
            "prompt_version": record.promptVersion,
            "source_count": record.sourceCount,
            "evidence_count": record.evidenceCount,
            "payload_json": to_json(record.payload),
            "stale_at": record.staleAt,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_dna_delta(db: Database, record: DnaDeltaRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "dna_deltas",
        {
            "id": record.id,
            "client_id": record.clientId,
            "dimension": record.dimension,
            "previous_version": record.previousVersion,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "supersedes_id": record.supersedesId,
            "source_snapshot_hash": record.sourceSnapshotHash,
            "stale_reason": _normalize_stale_reason(record.staleReason),
            "invalidated_by": record.invalidatedBy,
            "proposed_change": record.proposedChange,
            "summary": record.summary,
            "evidence_ids_json": to_json(record.evidenceIds),
            "confidence": record.confidence,
            "status": record.status,
            "context_pack_id": record.contextPackId,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_judgment_version(db: Database, record: JudgmentVersionRecord) -> None:
    _validate_truth_boundary(
        origin_type=record.originType,
        authority_level=record.authorityLevel,
        quality_tier=record.qualityTier,
    )
    _upsert(
        db,
        "judgment_versions",
        {
            "id": record.id,
            "client_id": record.clientId,
            "target_type": record.targetType,
            "target_id": record.targetId,
            "topic": record.topic,
            "version": record.version,
            "status": record.status,
            "origin_type": record.originType,
            "authority_level": record.authorityLevel,
            "quality_tier": record.qualityTier,
            "supersedes_id": record.supersedesId,
            "source_snapshot_hash": record.sourceSnapshotHash,
            "stale_reason": _normalize_stale_reason(record.staleReason),
            "invalidated_by": record.invalidatedBy,
            "summary": record.summary,
            "evidence_ids_json": to_json(record.evidenceIds),
            "context_pack_id": record.contextPackId,
            "risk_level": record.riskLevel,
            "confidence": record.confidence,
            "created_at": record.createdAt,
            "updated_at": record.updatedAt,
        },
    )


def _upsert_sync_memory_record(
    db: Database,
    *,
    client_id: str,
    scope_type: AnalysisScopeType,
    scope_id: str,
    payload: dict[str, Any],
    source_fingerprint: str,
    synced_at: str | None,
    now: str,
) -> None:
    record_id = _stable_id("syncmem", client_id, scope_type, scope_id)
    _upsert(
        db,
        "sync_memory_records",
        {
            "id": record_id,
            "client_id": client_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "sync_mode": "derived_only",
            "payload_json": to_json(payload),
            "source_fingerprint": source_fingerprint,
            "synced_at": synced_at,
            "created_at": now,
            "updated_at": now,
        },
    )


def _build_analysis_job_record(row: Any) -> AnalysisJobRecord:
    return AnalysisJobRecord(
        id=str(row["id"]),
        jobType=str(row["job_type"]),
        clientId=str(row["client_id"]),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        status=str(row["status"]),
        priority=str(row["priority"]),
        triggerType=str(row["trigger_type"]),
        intentProfile=str(row["intent_profile"] or "client_overview"),
        question=str(row["question"] or ""),
        sourceSnapshot=str(row["source_snapshot"] or ""),
        sourceSnapshotHash=str(row["source_snapshot_hash"] or ""),
        dedupeKey=str(row["dedupe_key"] or ""),
        featureFlags=_parse_json_dict(row["feature_flags_json"]),
        progress=float(row["progress"] or 0.0),
        stageLabel=str(row["stage_label"]) if row["stage_label"] else None,
        runLogId=str(row["run_log_id"]) if row["run_log_id"] else None,
        error=str(row["error"]) if row["error"] else None,
        lockedBy=str(row["locked_by"]) if row["locked_by"] else None,
        lockedAt=str(row["locked_at"]) if row["locked_at"] else None,
        lockExpiresAt=str(row["lock_expires_at"]) if row["lock_expires_at"] else None,
        attemptCount=int(row["attempt_count"] or 0),
        lastError=str(row["last_error"]) if row["last_error"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        startedAt=str(row["started_at"]) if row["started_at"] else None,
        finishedAt=str(row["finished_at"]) if row["finished_at"] else None,
    )


def _build_stage_run_record(row: Any) -> AnalysisJobStageRunRecord:
    return AnalysisJobStageRunRecord(
        id=str(row["id"]),
        jobId=str(row["job_id"]),
        stageName=str(row["stage_name"]),
        status=str(row["status"]),
        provider=str(row["provider"]) if row["provider"] else None,
        modelName=str(row["model_name"]) if row["model_name"] else None,
        lane=str(row["lane"]),
        cacheKey=str(row["cache_key"]) if row["cache_key"] else None,
        cacheHit=bool(row["cache_hit"]),
        degraded=bool(row["degraded"]),
        evidenceCount=int(row["evidence_count"] or 0),
        topicCount=int(row["topic_count"] or 0),
        conflictCount=int(row["conflict_count"] or 0),
        contextTimeRange=str(row["context_time_range"]) if row["context_time_range"] else None,
        metrics=_parse_json_dict(row["metrics_json"]),
        detail=str(row["detail"]) if row["detail"] else None,
        correlationId=str(row["correlation_id"]) if row["correlation_id"] else None,
        startedAt=str(row["started_at"]) if row["started_at"] else None,
        finishedAt=str(row["finished_at"]) if row["finished_at"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_runtime_run_log_record(row: Any) -> RuntimeRunLogRecord:
    return RuntimeRunLogRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        jobId=str(row["job_id"]) if row["job_id"] else None,
        analysisJobId=str(row["analysis_job_id"]) if row["analysis_job_id"] else None,
        stageRunId=str(row["stage_run_id"]) if row["stage_run_id"] else None,
        contextPackId=str(row["context_pack_id"]) if row["context_pack_id"] else None,
        judgmentVersionId=str(row["judgment_version_id"]) if row["judgment_version_id"] else None,
        correlationId=str(row["correlation_id"]) if row["correlation_id"] else None,
        provider=str(row["provider"]) if row["provider"] else None,
        model=str(row["model"]) if row["model"] else None,
        lane=str(row["lane"]),
        cacheHit=bool(row["cache_hit"]),
        degraded=bool(row["degraded"]),
        documentCount=int(row["document_count"] or 0),
        evidenceCount=int(row["evidence_count"] or 0),
        conflictCount=int(row["conflict_count"] or 0),
        contextTimeRange=str(row["context_time_range"]) if row["context_time_range"] else None,
        promptVersion=str(row["prompt_version"]) if row["prompt_version"] else None,
        schemaVersion=str(row["schema_version"]) if row["schema_version"] else None,
        summary=str(row["summary"] or ""),
        detail=_parse_json_dict(row["detail_json"]),
        createdAt=str(row["created_at"]),
    )


def _build_theme_cluster_record(row: Any) -> ThemeClusterRecord:
    return ThemeClusterRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        themeKey=str(row["theme_key"]),
        title=str(row["title"]),
        supportIds=_parse_json_list(row["support_ids_json"]),
        opposeIds=_parse_json_list(row["oppose_ids_json"]),
        gapSummary=str(row["gap_summary"] or ""),
        latestChangeSummary=str(row["latest_change_summary"] or ""),
        evidenceCount=int(row["evidence_count"] or 0),
        version=int(row["version"] or 1),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_conflict_group_record(row: Any) -> ConflictGroupRecord:
    return ConflictGroupRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        conflictType=str(row["conflict_type"]),
        title=str(row["title"]),
        summary=str(row["summary"]),
        evidenceIds=_parse_json_list(row["evidence_ids_json"]),
        unresolvedQuestionIds=_parse_json_list(row["unresolved_question_ids_json"]),
        resolutionStatus=str(row["resolution_status"]),
        severity=str(row["severity"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_open_question_record(row: Any) -> OpenQuestionRecord:
    return OpenQuestionRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        scopeType=str(row["scope_type"]),
        scopeId=str(row["scope_id"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        themeKey=str(row["theme_key"]),
        question=str(row["question"]),
        reason=str(row["reason"] or ""),
        blockerLevel=str(row["blocker_level"]),
        status=str(row["status"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_context_pack_record(row: Any) -> ContextPackRecord:
    return ContextPackRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        jobId=str(row["job_id"]) if row["job_id"] else None,
        targetType=str(row["target_type"]),
        targetId=str(row["target_id"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        supersedesId=str(row["supersedes_id"]) if row["supersedes_id"] else None,
        sourceSnapshotHash=str(row["source_snapshot_hash"] or ""),
        staleReason=_normalize_stale_reason(str(row["stale_reason"]) if row["stale_reason"] else None),
        invalidatedBy=str(row["invalidated_by"]) if row["invalidated_by"] else None,
        promptVersion=str(row["prompt_version"]),
        sourceCount=int(row["source_count"] or 0),
        evidenceCount=int(row["evidence_count"] or 0),
        payload=_parse_json_dict(row["payload_json"]),
        staleAt=str(row["stale_at"]) if row["stale_at"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _build_dna_delta_record(row: Any) -> DnaDeltaRecord:
    return DnaDeltaRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        dimension=str(row["dimension"]),
        previousVersion=str(row["previous_version"]) if row["previous_version"] else None,
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        supersedesId=str(row["supersedes_id"]) if row["supersedes_id"] else None,
        sourceSnapshotHash=str(row["source_snapshot_hash"] or ""),
        staleReason=_normalize_stale_reason(str(row["stale_reason"]) if row["stale_reason"] else None),
        invalidatedBy=str(row["invalidated_by"]) if row["invalidated_by"] else None,
        proposedChange=str(row["proposed_change"]),
        summary=str(row["summary"] or ""),
        evidenceIds=_parse_json_list(row["evidence_ids_json"]),
        confidence=str(row["confidence"]),
        status=str(row["status"]),
        contextPackId=str(row["context_pack_id"]) if row["context_pack_id"] else None,
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


_LEGACY_TARGET_TYPE_MAP = {
    "workspace_answer": "client",
}
_VALID_TARGET_TYPES = {"client", "event_line", "meeting", "task", "module", "flow"}

_LEGACY_REVIEW_STATE_MAP = {
    "confirmed": "approved",
    "pending": "draft",
    "discarded": "rejected",
}
_VALID_REVIEW_STATES = {"draft", "awaiting_review", "awaiting_revision", "approved", "rejected", "superseded"}


def _normalize_judgment_target_type(value: Any) -> str:
    text = str(value or "").strip()
    if text in _VALID_TARGET_TYPES:
        return text
    mapped = _LEGACY_TARGET_TYPE_MAP.get(text)
    return mapped or "client"


def _normalize_judgment_review_state(value: Any) -> str:
    text = str(value or "").strip()
    if text in _VALID_REVIEW_STATES:
        return text
    mapped = _LEGACY_REVIEW_STATE_MAP.get(text)
    return mapped or "draft"


def _build_judgment_version_record(row: Any) -> JudgmentVersionRecord:
    return JudgmentVersionRecord(
        id=str(row["id"]),
        clientId=str(row["client_id"]),
        targetType=_normalize_judgment_target_type(row["target_type"]),
        targetId=str(row["target_id"]),
        topic=str(row["topic"]),
        version=int(row["version"] or 1),
        status=_normalize_judgment_review_state(row["status"]),
        originType=str(row["origin_type"] or "projection"),
        authorityLevel=str(row["authority_level"] or "fallback"),
        qualityTier=str(row["quality_tier"] or "legacy"),
        supersedesId=str(row["supersedes_id"]) if row["supersedes_id"] else None,
        sourceSnapshotHash=str(row["source_snapshot_hash"] or ""),
        staleReason=_normalize_stale_reason(str(row["stale_reason"]) if row["stale_reason"] else None),
        invalidatedBy=str(row["invalidated_by"]) if row["invalidated_by"] else None,
        summary=str(row["summary"]),
        evidenceIds=_parse_json_list(row["evidence_ids_json"]),
        contextPackId=str(row["context_pack_id"]) if row["context_pack_id"] else None,
        riskLevel=str(row["risk_level"]),
        confidence=str(row["confidence"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def list_analysis_jobs(db: Database, client_id: str, limit: int = 12) -> list[AnalysisJobRecord]:
    return [
        _build_analysis_job_record(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_jobs WHERE client_id = ? ORDER BY updated_at DESC LIMIT ?",
            (client_id, limit),
        )
    ]


def get_analysis_job(db: Database, job_id: str) -> AnalysisJobRecord | None:
    row = db.fetchone("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,))
    return _build_analysis_job_record(row) if row else None


def list_analysis_job_stages(db: Database, job_id: str) -> list[AnalysisJobStageRunRecord]:
    return [
        _build_stage_run_record(row)
        for row in db.fetchall(
            "SELECT * FROM job_stage_runs WHERE job_id = ? ORDER BY created_at ASC",
            (job_id,),
        )
    ]


def get_runtime_run_log(db: Database, run_id: str) -> RuntimeRunLogRecord | None:
    row = db.fetchone("SELECT * FROM runtime_run_logs WHERE id = ?", (run_id,))
    return _build_runtime_run_log_record(row) if row else None


def list_runtime_run_logs(db: Database, client_id: str, limit: int = 8) -> list[RuntimeRunLogRecord]:
    return [
        _build_runtime_run_log_record(row)
        for row in db.fetchall(
            "SELECT * FROM runtime_run_logs WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
            (client_id, limit),
        )
    ]


def list_theme_clusters(
    db: Database,
    client_id: str,
    limit: int = 12,
    scope_type: AnalysisScopeType | None = None,
    scope_id: str | None = None,
) -> list[ThemeClusterRecord]:
    clauses = ["client_id = ?"]
    params: list[Any] = [client_id]
    if scope_type:
        clauses.append("scope_type = ?")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = ?")
        params.append(scope_id)
    params.append(limit)
    query = f"SELECT * FROM theme_clusters WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?"
    return [_build_theme_cluster_record(row) for row in db.fetchall(query, tuple(params))]


def list_conflict_groups(
    db: Database,
    client_id: str,
    limit: int = 12,
    scope_type: AnalysisScopeType | None = None,
    scope_id: str | None = None,
) -> list[ConflictGroupRecord]:
    clauses = ["client_id = ?"]
    params: list[Any] = [client_id]
    if scope_type:
        clauses.append("scope_type = ?")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = ?")
        params.append(scope_id)
    params.append(limit)
    query = f"SELECT * FROM conflict_groups WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?"
    return [_build_conflict_group_record(row) for row in db.fetchall(query, tuple(params))]


def list_open_questions(
    db: Database,
    client_id: str,
    limit: int = 12,
    scope_type: AnalysisScopeType | None = None,
    scope_id: str | None = None,
) -> list[OpenQuestionRecord]:
    clauses = ["client_id = ?"]
    params: list[Any] = [client_id]
    if scope_type:
        clauses.append("scope_type = ?")
        params.append(scope_type)
    if scope_id:
        clauses.append("scope_id = ?")
        params.append(scope_id)
    params.append(limit)
    query = f"SELECT * FROM open_questions WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?"
    return [_build_open_question_record(row) for row in db.fetchall(query, tuple(params))]


def list_judgment_versions(
    db: Database,
    client_id: str,
    limit: int = 12,
    target_type: AnalysisScopeType | None = None,
    target_id: str | None = None,
    minimum_authority: AnalysisAuthorityLevel = "fallback",
    include_fallback: bool = True,
) -> list[JudgmentVersionRecord]:
    clauses = ["client_id = ?"]
    params: list[Any] = [client_id]
    if target_type:
        clauses.append("target_type = ?")
        params.append(target_type)
    if target_id:
        clauses.append("target_id = ?")
        params.append(target_id)
    authority_clause = """
        CASE authority_level
            WHEN 'approved' THEN 2
            WHEN 'candidate' THEN 1
            ELSE 0
        END
    """
    clauses.append(f"{authority_clause} >= ?")
    params.append(_AUTHORITY_RANK[minimum_authority])
    if not include_fallback:
        clauses.append("authority_level != 'fallback'")
    params.append(limit)
    query = f"""
        SELECT *
        FROM judgment_versions
        WHERE {' AND '.join(clauses)}
        ORDER BY
            CASE WHEN COALESCE(invalidated_by, '') = '' THEN 0 ELSE 1 END ASC,
            {authority_clause} DESC,
            updated_at DESC
        LIMIT ?
    """
    return [_build_judgment_version_record(row) for row in db.fetchall(query, tuple(params))]


def list_dna_deltas(db: Database, client_id: str, limit: int = 12) -> list[DnaDeltaRecord]:
    return [
        _build_dna_delta_record(row)
        for row in db.fetchall(
            "SELECT * FROM dna_deltas WHERE client_id = ? ORDER BY updated_at DESC LIMIT ?",
            (client_id, limit),
        )
    ]


def resolve_analysis_scope(
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    *,
    intent_profile: AnalysisIntentProfile,
    related_refs: dict[str, list[str]] | None = None,
    client_id: str,
) -> list[tuple[AnalysisScopeType, str]]:
    refs = related_refs or {}
    order = _INTENT_SCOPE_ORDER[intent_profile]
    requested_by_type: dict[AnalysisScopeType, list[str]] = {
        requested_scope_type: [requested_scope_id],
        "client": [client_id],
        "event_line": refs.get("event_line", []),
        "flow": refs.get("flow", []),
        "module": refs.get("module", []),
        "meeting": refs.get("meeting", []),
        "task": refs.get("task", []),
    }
    if requested_scope_id not in requested_by_type.get(requested_scope_type, []):
        requested_by_type.setdefault(requested_scope_type, []).insert(0, requested_scope_id)

    seen: set[tuple[AnalysisScopeType, str]] = set()
    resolved: list[tuple[AnalysisScopeType, str]] = []
    for scope_type in order:
        for scope_id in requested_by_type.get(scope_type, []):
            key = (scope_type, scope_id)
            if not scope_id or key in seen:
                continue
            seen.add(key)
            resolved.append(key)
    fallback_client = ("client", client_id)
    if fallback_client not in seen:
        resolved.append(fallback_client)
    return resolved


def _scope_ref(scope_type: AnalysisScopeType, scope_id: str) -> ResolutionScopeRecord:
    return ResolutionScopeRecord(scopeType=scope_type, scopeId=scope_id)


def _ensure_writeback_scope(
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    *,
    writeback_scope_type: AnalysisScopeType | None = None,
    writeback_scope_id: str | None = None,
    allow_scope_upgrade: bool = False,
) -> ResolutionScopeRecord:
    resolved_scope_type = writeback_scope_type or requested_scope_type
    resolved_scope_id = writeback_scope_id or requested_scope_id
    requested_rank = _SCOPE_GRANULARITY.get(requested_scope_type, 0)
    writeback_rank = _SCOPE_GRANULARITY.get(resolved_scope_type, 0)
    if not allow_scope_upgrade and writeback_rank > requested_rank:
        raise ValueError("writeback scope cannot automatically broaden beyond requested scope")
    return _scope_ref(resolved_scope_type, resolved_scope_id)


def _resolve_rejected_reason(
    judgment: JudgmentVersionRecord,
    *,
    topic: str | None,
    minimum_authority: AnalysisAuthorityLevel,
    include_fallback: bool,
    already_selected: bool,
) -> AnalysisRejectedReason | None:
    if topic and judgment.topic != topic:
        return "scope_less_relevant"
    if judgment.staleReason == "superseded_by_newer_judgment":
        return "superseded"
    if judgment.invalidatedBy or judgment.staleReason:
        return "stale"
    if judgment.status in {"awaiting_revision", "rejected"}:
        return "insufficient_evidence"
    if _AUTHORITY_RANK[judgment.authorityLevel] < _AUTHORITY_RANK[minimum_authority]:
        return "authority_too_low"
    if not include_fallback and judgment.authorityLevel != "approved":
        return "not_approved_for_official_use"
    if already_selected:
        return "scope_less_relevant"
    return None


def _candidate_from_judgment(
    judgment: JudgmentVersionRecord,
    *,
    rejected_reason: AnalysisRejectedReason | None = None,
) -> ResolutionCandidateRecord:
    return ResolutionCandidateRecord(
        objectId=judgment.id,
        topic=judgment.topic,
        scopeType=judgment.targetType,
        scopeId=judgment.targetId,
        originType=judgment.originType,
        authorityLevel=judgment.authorityLevel,
        qualityTier=judgment.qualityTier,
        staleReason=judgment.staleReason,
        status=judgment.status,
        rejectedReason=rejected_reason,
    )


def resolve_current_approval_state(
    db: Database,
    target_type: str,
    target_id: str,
) -> ApprovalStateRecord:
    row = db.fetchone(
        """
        SELECT *
        FROM approval_records
        WHERE approval_target_type = ? AND approval_target_id = ?
        ORDER BY COALESCE(decided_at, created_at) DESC, created_at DESC
        LIMIT 1
        """,
        (target_type, target_id),
    )
    if not row:
        return ApprovalStateRecord(targetType=target_type, targetId=target_id)
    approval = _build_approval_record(row)
    current_status: AnalysisReviewState | None = {
        "approved": "approved",
        "rejected": "rejected",
        "returned_for_revision": "awaiting_revision",
    }.get(approval.decision)
    return ApprovalStateRecord(
        targetType=target_type,
        targetId=target_id,
        currentDecision=approval.decision,
        currentStatus=current_status,
        lastApproval=approval,
    )


def resolve_best_judgment(
    db: Database,
    *,
    client_id: str,
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    intent_profile: AnalysisIntentProfile,
    related_refs: dict[str, list[str]] | None = None,
    topic: str | None = None,
    minimum_authority: AnalysisAuthorityLevel = "fallback",
    include_fallback: bool = True,
    restrict_to_requested_scope: bool = False,
) -> tuple[JudgmentVersionRecord | None, ResolutionTraceRecord]:
    candidates = (
        [(requested_scope_type, requested_scope_id)]
        if restrict_to_requested_scope
        else resolve_analysis_scope(
            requested_scope_type,
            requested_scope_id,
            intent_profile=intent_profile,
            related_refs=related_refs,
            client_id=client_id,
        )
    )
    considered: list[ResolutionCandidateRecord] = []
    selected: JudgmentVersionRecord | None = None
    resolved_scope: ResolutionScopeRecord | None = None
    for scope_type, scope_id in candidates:
        items = list_judgment_versions(
            db,
            client_id,
            limit=8,
            target_type=scope_type,
            target_id=scope_id,
            minimum_authority="fallback",
            include_fallback=True,
        )
        if not items:
            considered.append(
                ResolutionCandidateRecord(
                    scopeType=scope_type,
                    scopeId=scope_id,
                    rejectedReason="insufficient_evidence",
                )
            )
            continue
        for item in items:
            rejected_reason = _resolve_rejected_reason(
                item,
                topic=topic,
                minimum_authority=minimum_authority,
                include_fallback=include_fallback,
                already_selected=selected is not None,
            )
            if rejected_reason is None:
                selected = item
                resolved_scope = _scope_ref(scope_type, scope_id)
                considered.append(_candidate_from_judgment(item))
            else:
                considered.append(_candidate_from_judgment(item, rejected_reason=rejected_reason))
    fallback_reason: str | None = None
    if selected is None:
        fallback_reason = "no_judgment_found"
    elif selected.authorityLevel == "fallback":
        fallback_reason = "resolved_to_fallback_authority"
    return selected, ResolutionTraceRecord(
        selectedCandidate=_candidate_from_judgment(selected) if selected else None,
        consideredCandidates=considered,
        requestedScope=_scope_ref(requested_scope_type, requested_scope_id),
        resolvedScope=resolved_scope,
        writebackScope=_ensure_writeback_scope(requested_scope_type, requested_scope_id),
        fallbackUsed=selected is None or selected.authorityLevel == "fallback",
        fallbackReason=fallback_reason,
    )


def resolve_judgment_bundle(
    db: Database,
    *,
    client_id: str,
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    intent_profile: AnalysisIntentProfile,
    related_refs: dict[str, list[str]] | None = None,
    topic: str | None = None,
) -> JudgmentBundleRecord:
    baseline, trace = resolve_best_judgment(
        db,
        client_id=client_id,
        requested_scope_type=requested_scope_type,
        requested_scope_id=requested_scope_id,
        intent_profile=intent_profile,
        related_refs=None,
        topic=topic,
        minimum_authority="fallback",
        include_fallback=True,
        restrict_to_requested_scope=True,
    )
    overlays: list[JudgmentVersionRecord] = []
    seen_ids: set[str] = {baseline.id} if baseline else set()
    for scope_type, scope_id in resolve_analysis_scope(
        requested_scope_type,
        requested_scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
        client_id=client_id,
    ):
        if scope_type == "client":
            continue
        for item in list_judgment_versions(
            db,
            client_id,
            limit=4,
            target_type=scope_type,
            target_id=scope_id,
            minimum_authority="candidate",
            include_fallback=False,
        ):
            if topic and item.topic != topic:
                continue
            if item.id in seen_ids:
                continue
            seen_ids.add(item.id)
            overlays.append(item)
    overlays.sort(
        key=lambda item: (
            _AUTHORITY_RANK[item.authorityLevel],
            0 if item.targetType == "event_line" else 1,
            item.updatedAt,
        ),
        reverse=True,
    )
    return JudgmentBundleRecord(
        baselineJudgment=baseline,
        overlayDeltas=overlays[:8],
        resolutionTrace=trace,
    )


def resolve_context_pack(
    db: Database,
    *,
    client_id: str,
    requested_scope_type: AnalysisScopeType,
    requested_scope_id: str,
    intent_profile: AnalysisIntentProfile,
    related_refs: dict[str, list[str]] | None = None,
    minimum_authority: AnalysisAuthorityLevel = "fallback",
    include_fallback: bool = True,
) -> tuple[ContextPackRecord | None, dict[str, Any]]:
    candidates = resolve_analysis_scope(
        requested_scope_type,
        requested_scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
        client_id=client_id,
    )
    for scope_type, scope_id in candidates:
        rows = db.fetchall(
            """
            SELECT *
            FROM context_packs
            WHERE client_id = ? AND target_type = ? AND target_id = ?
            ORDER BY
                CASE WHEN COALESCE(invalidated_by, '') = '' THEN 0 ELSE 1 END ASC,
                CASE authority_level WHEN 'approved' THEN 2 WHEN 'candidate' THEN 1 ELSE 0 END DESC,
                updated_at DESC
            LIMIT 8
            """,
            (client_id, scope_type, scope_id),
        )
        packs = [_build_context_pack_record(row) for row in rows]
        packs = [
            item for item in packs
            if _AUTHORITY_RANK[item.authorityLevel] >= _AUTHORITY_RANK[minimum_authority]
            and (include_fallback or item.authorityLevel != "fallback")
        ]
        if not packs:
            continue
        chosen = packs[0]
        return chosen, {
            "objectId": chosen.id,
            "scopeType": scope_type,
            "scopeId": scope_id,
            "originType": chosen.originType,
            "authorityLevel": chosen.authorityLevel,
            "qualityTier": chosen.qualityTier,
            "fallbackUsed": chosen.authorityLevel == "fallback",
            "requestedScopeType": requested_scope_type,
            "requestedScopeId": requested_scope_id,
            "intentProfile": intent_profile,
            "reason": "resolved_by_priority_chain",
        }
    return None, {
        "scopeType": requested_scope_type,
        "scopeId": requested_scope_id,
        "requestedScopeType": requested_scope_type,
        "requestedScopeId": requested_scope_id,
        "intentProfile": intent_profile,
        "fallbackUsed": True,
        "reason": "no_context_pack_found",
    }


def _build_related_refs(workspace: ClientWorkspaceResponse) -> dict[str, list[str]]:
    return {
        "event_line": _unique([item.eventLineId for item in workspace.relatedTasks if item.eventLineId]),
        "flow": [item.id for item in workspace.projectFlows[:12]],
        "module": [item.id for item in workspace.projectModules[:12]],
        "meeting": [item.id for item in workspace.meetings[:12]],
        "task": [item.id for item in workspace.relatedTasks[:24]],
    }


def _build_analysis_center_summary(db: Database, client_id: str) -> AnalysisCenterSummaryRecord:
    # P1-3 性能: 把原来 8 个独立 COUNT 合并成 1 个 UNION ALL, 250MB db 时减少 7-8x 扫表
    # 每个 SELECT 返回 (key, count) 形式, Python 里 dict 化用.
    count_rows = db.fetchall(
        """
        SELECT 'evidence' AS k, COUNT(*) AS n FROM evidence_cards WHERE client_id = ?
        UNION ALL
        SELECT 'theme', COUNT(*) FROM theme_clusters WHERE client_id = ?
        UNION ALL
        SELECT 'conflict', COUNT(*) FROM conflict_groups WHERE client_id = ?
        UNION ALL
        SELECT 'open_q', COUNT(*) FROM open_questions WHERE client_id = ?
        UNION ALL
        SELECT 'judg_draft', COUNT(*) FROM judgment_versions
          WHERE client_id = ? AND status IN ('draft','awaiting_review','awaiting_revision')
        UNION ALL
        SELECT 'judg_approved', COUNT(*) FROM judgment_versions
          WHERE client_id = ? AND status = 'approved'
        UNION ALL
        SELECT 'analysis_job', COUNT(*) FROM analysis_jobs WHERE client_id = ?
        """,
        (client_id,) * 7,
    )
    counts = {row["k"]: int(row["n"] or 0) for row in count_rows}

    # latest_* 仍单查 (各表 ORDER BY DESC LIMIT 1 走索引, 单次很快, 没必要合并)
    latest_job = db.fetchone(
        "SELECT status, stage_label FROM analysis_jobs WHERE client_id = ? ORDER BY updated_at DESC LIMIT 1",
        (client_id,),
    )
    latest_context_pack = db.fetchone(
        "SELECT updated_at FROM context_packs WHERE client_id = ? ORDER BY updated_at DESC LIMIT 1",
        (client_id,),
    )
    latest_run_log = db.fetchone(
        "SELECT id, summary FROM runtime_run_logs WHERE client_id = ? ORDER BY created_at DESC LIMIT 1",
        (client_id,),
    )
    return AnalysisCenterSummaryRecord(
        clientId=client_id,
        evidenceCardCount=counts.get("evidence", 0),
        themeClusterCount=counts.get("theme", 0),
        conflictGroupCount=counts.get("conflict", 0),
        openQuestionCount=counts.get("open_q", 0),
        draftJudgmentCount=counts.get("judg_draft", 0),
        approvedJudgmentCount=counts.get("judg_approved", 0),
        analysisJobCount=counts.get("analysis_job", 0),
        latestJobStatus=str(latest_job["status"]) if latest_job and latest_job["status"] else None,
        latestJobLabel=str(latest_job["stage_label"]) if latest_job and latest_job["stage_label"] else None,
        latestContextPackUpdatedAt=str(latest_context_pack["updated_at"]) if latest_context_pack else None,
        latestRunLogId=str(latest_run_log["id"]) if latest_run_log and latest_run_log["id"] else None,
        latestRunSummary=str(latest_run_log["summary"]) if latest_run_log and latest_run_log["summary"] else None,
    )


def _pick_topic_keys(card: DocumentCardRecord) -> list[str]:
    return _unique(
        [
            card.primaryCategory,
            card.secondaryCategory,
            *card.keywords[:3],
            *card.tags[:2],
        ]
    )[:4]


def _sync_doc_skeletons(db: Database, workspace: ClientWorkspaceResponse, now: str) -> None:
    for card in workspace.documentCards:
        outline = _unique(
            [
                card.primaryCategory,
                card.secondaryCategory,
                *card.coreQuestions[:3],
                *card.distinctFindings[:2],
            ]
        )[:6]
        entities = _unique(card.entities + card.keywords)[:8]
        record_id = _stable_id("docskeleton", workspace.client.id, card.documentId)
        _upsert_doc_skeleton(
            db,
            {
                "id": record_id,
                "client_id": workspace.client.id,
                "document_id": card.documentId,
                "title": card.title,
                "outline": outline,
                "entities": entities,
                "time_range": card.dateRange,
                "parser_version": "analysis-center-v1",
                "source_snapshot": to_json(
                    {
                        "docId": card.docId,
                        "documentRole": card.documentRole,
                        "summary": card.shortSummary,
                        "queryHints": card.queryHints[:4],
                    }
                ),
                "created_at": now,
                "updated_at": now,
            },
        )


def _event_line_groups(tasks: list[TaskRecord]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not task.eventLineId:
            continue
        group = groups.setdefault(
            task.eventLineId,
            {
                "id": task.eventLineId,
                "name": task.eventLineName or task.title,
                "tasks": [],
            },
        )
        group["tasks"].append(task)
        if task.eventLineName:
            group["name"] = task.eventLineName
    return groups


def _sync_evidence_cards(
    db: Database,
    workspace: ClientWorkspaceResponse,
    notebook_summary: OrganizationNotebookSnapshot | None,
    memory_status: MemoryStatus | None,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> list[str]:
    evidence_ids: list[str] = []

    def create_card(
        *,
        scope_type: AnalysisScopeType,
        scope_id: str,
        source_type: str,
        source_id: str,
        source_ref: str,
        quote: str,
        normalized_claim: str,
        evidence_type: str,
        tags: list[str] | None = None,
        topic_keys: list[str] | None = None,
        confidence: float = 0.55,
        time_anchor: str | None = None,
        document_id: str | None = None,
        event_line_id: str | None = None,
        task_id: str | None = None,
        meeting_id: str | None = None,
        module_id: str | None = None,
        flow_id: str | None = None,
        review_state: AnalysisReviewState = "draft",
    ) -> None:
        clean_quote = _truncate(quote, 320)
        clean_claim = _truncate(normalized_claim, 240)
        if not clean_quote or not clean_claim:
            return
        normalized_claim_hash = _hash_text(clean_claim.lower())
        source_ref_hash = _hash_text((source_ref or "").strip().lower())
        evidence_fingerprint = hashlib.sha1(
            "::".join(
                [
                    normalized_claim_hash,
                    evidence_type,
                    "neutral",
                    time_anchor or "",
                    scope_type,
                    scope_id,
                    source_ref_hash,
                ]
            ).encode("utf-8")
        ).hexdigest()
        fingerprint = hashlib.sha1(
            "::".join(
                [
                    workspace.client.id,
                    scope_type,
                    scope_id,
                    source_type,
                    source_id,
                    clean_claim,
                    evidence_fingerprint,
                ]
            ).encode("utf-8")
        ).hexdigest()
        record_id = _stable_id("evidence", workspace.client.id, scope_type, scope_id, source_type, source_id, clean_claim[:80])
        _upsert_evidence_card(
            db,
            {
                "id": record_id,
                "client_id": workspace.client.id,
                "scope_type": scope_type,
                "scope_id": scope_id,
                **_truth_fields(
                    origin_type=origin_type,
                    authority_level=authority_level,
                    quality_tier=quality_tier,
                ),
                "source_type": source_type,
                "source_id": source_id,
                "source_ref": source_ref,
                "quote": clean_quote,
                "normalized_claim": clean_claim,
                "evidence_type": evidence_type,
                "polarity": "neutral",
                "tags": _unique(tags or [])[:8],
                "topic_keys": _unique(topic_keys or [])[:6],
                "confidence": confidence,
                "time_anchor": time_anchor,
                "document_id": document_id,
                "event_line_id": event_line_id,
                "task_id": task_id,
                "meeting_id": meeting_id,
                "module_id": module_id,
                "flow_id": flow_id,
                "review_state": review_state,
                "fingerprint": fingerprint,
                "normalized_claim_hash": normalized_claim_hash,
                "source_ref_hash": source_ref_hash,
                "evidence_fingerprint": evidence_fingerprint,
                "normalizer_version": "analysis-center-v0.3.3",
                "created_at": now,
                "updated_at": now,
            },
        )
        evidence_ids.append(record_id)

    for card in workspace.documentCards[:24]:
        claim = _first_non_empty(
            card.shortSummary,
            card.summary,
            card.retrievalSummary,
            fallback=card.title,
        )
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="document_card",
            source_id=card.id,
            source_ref=card.title,
            quote=claim,
            normalized_claim=claim,
            evidence_type="document_summary",
            tags=card.tags + [card.documentRole],
            topic_keys=_pick_topic_keys(card),
            confidence=max(card.classificationConfidence, 0.45),
            time_anchor=card.dateRange,
            document_id=card.documentId,
            review_state="awaiting_review" if card.needsReview else "draft",
        )
        for finding in card.distinctFindings[:2]:
            create_card(
                scope_type="client",
                scope_id=workspace.client.id,
                source_type="document_finding",
                source_id=f"{card.id}:{finding[:36]}",
                source_ref=card.title,
                quote=finding,
                normalized_claim=finding,
                evidence_type="finding",
                tags=card.tags,
                topic_keys=_pick_topic_keys(card),
                confidence=max(card.classificationConfidence, 0.52),
                time_anchor=card.dateRange,
                document_id=card.documentId,
            )

    for module in workspace.dnaModules:
        if not module.hasDocument:
            continue
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="dna_module",
            source_id=module.moduleKey,
            source_ref=module.title,
            quote=_first_non_empty(module.summary, module.normalizedText, fallback=module.title),
            normalized_claim=_first_non_empty(module.summary, fallback=f"{module.title} 已接入"),
            evidence_type="dna_module",
            tags=[module.moduleKey, "dna"],
            topic_keys=[module.moduleKey, module.title],
            confidence=0.72,
            time_anchor=module.updatedAt,
        )

    for goal in workspace.goals[:4]:
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="goal",
            source_id=goal.id,
            source_ref=goal.title,
            quote=goal.title,
            normalized_claim=f"{goal.title} 当前进度 {goal.progress}%，负责人 {goal.ownerName}",
            evidence_type="goal_anchor",
            tags=["goal", goal.quarter],
            topic_keys=["goal", goal.title],
            confidence=0.7,
            time_anchor=goal.quarter,
        )

    for meeting in workspace.meetings[:4]:
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="meeting",
            source_id=meeting.id,
            source_ref=meeting.title,
            quote=f"{meeting.title} 当前处于 {meeting.stage} 阶段",
            normalized_claim=f"会议 {meeting.title} 已沉淀到 {meeting.stage} 阶段",
            evidence_type="meeting_signal",
            tags=["meeting", meeting.stage],
            topic_keys=["meeting", meeting.title],
            confidence=0.62,
            time_anchor=meeting.updatedAt,
            meeting_id=meeting.id,
        )

    for task in workspace.relatedTasks[:40]:
        scope_type: AnalysisScopeType = "event_line" if task.eventLineId else "client"
        scope_id = task.eventLineId or workspace.client.id
        task_claim = _first_non_empty(
            task.projectContext.currentBlocker if task.projectContext else None,
            task.projectContext.recentProgress if task.projectContext else None,
            task.desc,
            fallback=task.title,
        )
        create_card(
            scope_type=scope_type,
            scope_id=scope_id,
            source_type="task",
            source_id=task.id,
            source_ref=task.title,
            quote=task_claim,
            normalized_claim=f"{task.title}：{task.status}，负责人 {task.ownerName}",
            evidence_type="task_signal",
            tags=[
                task.status,
                task.priority,
                task.projectModuleName or "",
                task.projectFlowName or "",
            ],
            topic_keys=_unique(
                [
                    task.eventLineName,
                    task.projectModuleName,
                    task.projectFlowName,
                    task.clientName,
                ]
            )[:4],
            confidence=max(task.backgroundReadiness.score, 0.35) if task.backgroundReadiness else 0.35,
            time_anchor=task.updatedAt,
            event_line_id=task.eventLineId,
            task_id=task.id,
            module_id=task.projectModuleId,
            flow_id=task.projectFlowId,
            review_state="awaiting_review" if task.backgroundReadiness and task.backgroundReadiness.level == "low" else "draft",
        )

    for module in workspace.projectModules:
        create_card(
            scope_type="module",
            scope_id=module.id,
            source_type="project_module",
            source_id=module.id,
            source_ref=module.name,
            quote=_first_non_empty(module.goal, module.description, fallback=module.name),
            normalized_claim=f"模块 {module.name} 目标：{_first_non_empty(module.goal, module.description, fallback='待补')}",
            evidence_type="module_definition",
            tags=["module", module.ownerName or ""],
            topic_keys=[module.name, "module"],
            confidence=0.66,
            time_anchor=module.updatedAt,
            module_id=module.id,
        )

    for flow in workspace.projectFlows:
        create_card(
            scope_type="flow",
            scope_id=flow.id,
            source_type="project_flow",
            source_id=flow.id,
            source_ref=flow.name,
            quote=_first_non_empty(flow.description, flow.scenario, fallback=flow.name),
            normalized_claim=f"流程 {flow.name} 适用于 {flow.scenario or '待补'}",
            evidence_type="flow_definition",
            tags=["flow", flow.moduleName or ""],
            topic_keys=[flow.name, flow.moduleName or "", "flow"],
            confidence=0.64,
            time_anchor=flow.updatedAt,
            module_id=flow.moduleId,
            flow_id=flow.id,
        )

    if notebook_summary:
        for fact in notebook_summary.recentFacts[:3]:
            create_card(
                scope_type="client",
                scope_id=workspace.client.id,
                source_type="organization_notebook",
                source_id=notebook_summary.id,
                source_ref="organization_notebook",
                quote=fact,
                normalized_claim=fact,
                evidence_type="notebook_fact",
                tags=["notebook"],
                topic_keys=notebook_summary.businessModules[:3] or [workspace.client.name],
                confidence=max(notebook_summary.confidence, 0.55),
                time_anchor=notebook_summary.updatedAt,
            )

    if memory_status and memory_status.lowEvidenceJudgments:
        create_card(
            scope_type="client",
            scope_id=workspace.client.id,
            source_type="memory_status",
            source_id=workspace.client.id,
            source_ref="memory_status",
            quote=f"当前仍有 {memory_status.lowEvidenceJudgments} 条低证据判断待补强。",
            normalized_claim="当前客户判断层还有低证据区域，需要进一步补材料或补会议。",
            evidence_type="memory_gap",
            tags=["memory", "low_evidence"],
            topic_keys=["memory_gap"],
            confidence=0.7,
            time_anchor=memory_status.updatedAt,
            review_state="awaiting_review",
        )

    return evidence_ids


def _evidence_cluster_key(row: Any) -> tuple[str, str]:
    return (
        str(row["evidence_fingerprint"] or row["fingerprint"] or row["id"]),
        str(row["normalizer_version"] or ""),
    )


def _list_evidence_ids_by_scope(
    db: Database,
    client_id: str,
    scope_type: AnalysisScopeType,
    scope_id: str,
    *,
    dedupe_by_cluster_key: bool = False,
) -> list[str]:
    rows = db.fetchall(
        """
        SELECT id, evidence_fingerprint, fingerprint, normalizer_version
        FROM evidence_cards
        WHERE client_id = ? AND scope_type = ? AND scope_id = ?
        ORDER BY updated_at DESC
        """,
        (client_id, scope_type, scope_id),
    )
    if not dedupe_by_cluster_key:
        return [str(row["id"]) for row in rows]
    deduped_ids: list[str] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = _evidence_cluster_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped_ids.append(str(row["id"]))
    return deduped_ids


def _sync_theme_clusters(
    db: Database,
    workspace: ClientWorkspaceResponse,
    notebook_summary: OrganizationNotebookSnapshot | None,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> list[ThemeClusterRecord]:
    records: list[ThemeClusterRecord] = []
    client_scope_ids = _list_evidence_ids_by_scope(
        db,
        workspace.client.id,
        "client",
        workspace.client.id,
        dedupe_by_cluster_key=True,
    )

    for module in workspace.dnaModules:
        if not module.hasDocument:
            continue
        evidence_ids = [
            evidence_id
            for evidence_id in client_scope_ids
            if module.moduleKey in evidence_id or module.title[:12] in evidence_id
        ][:4]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "client", workspace.client.id, module.moduleKey),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=module.moduleKey,
                title=module.title,
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="；".join(module.missingInfo[:3]),
                latestChangeSummary=_first_non_empty(module.summary, fallback=f"{module.title} 已接入项目公共上下文"),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    for module in workspace.projectModules:
        evidence_ids = _list_evidence_ids_by_scope(
            db,
            workspace.client.id,
            "module",
            module.id,
            dedupe_by_cluster_key=True,
        )[:6]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "module", module.id, module.name),
                clientId=workspace.client.id,
                scopeType="module",
                scopeId=module.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=module.name,
                title=module.name,
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="" if module.description or module.goal else "当前模块还没有明确目标和说明。",
                latestChangeSummary=_first_non_empty(module.goal, module.description, fallback="模块已建立，但目标仍待补充。"),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    for flow in workspace.projectFlows:
        evidence_ids = _list_evidence_ids_by_scope(
            db,
            workspace.client.id,
            "flow",
            flow.id,
            dedupe_by_cluster_key=True,
        )[:6]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "flow", flow.id, flow.name),
                clientId=workspace.client.id,
                scopeType="flow",
                scopeId=flow.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=flow.name,
                title=flow.name,
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="" if flow.description or flow.steps else "当前流程还没有足够细的说明。",
                latestChangeSummary=_first_non_empty(flow.description, flow.scenario, fallback="流程已建立，但应用场景仍待补齐。"),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    for event_line_id, group in _event_line_groups(workspace.relatedTasks).items():
        tasks: list[TaskRecord] = sorted(group["tasks"], key=lambda item: item.updatedAt, reverse=True)
        task_titles = [task.title for task in tasks[:2]]
        evidence_ids = _list_evidence_ids_by_scope(
            db,
            workspace.client.id,
            "event_line",
            event_line_id,
            dedupe_by_cluster_key=True,
        )[:8]
        missing_parts = [
            "缺当前阻塞" if not any((task.currentBlocker or (task.projectContext.currentBlocker if task.projectContext else "")) for task in tasks) else "",
            "缺下一步" if not any((task.nextAction or (task.projectContext.nextAction if task.projectContext else "")) for task in tasks) else "",
        ]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "event_line", event_line_id, group["name"]),
                clientId=workspace.client.id,
                scopeType="event_line",
                scopeId=event_line_id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=group["name"],
                title=group["name"],
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="；".join(_unique(missing_parts)),
                latestChangeSummary=_first_non_empty(*task_titles, fallback="事件线已建立，但最近推进记录仍偏少。"),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    if notebook_summary and notebook_summary.businessModules:
        evidence_ids = client_scope_ids[:6]
        records.append(
            ThemeClusterRecord(
                id=_stable_id("theme", workspace.client.id, "client", workspace.client.id, "organization_notebook"),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey="organization_notebook",
                title="组织与合作理解",
                supportIds=evidence_ids,
                opposeIds=[],
                gapSummary="；".join(notebook_summary.informationGaps[:3]),
                latestChangeSummary=_first_non_empty(
                    notebook_summary.currentStage,
                    notebook_summary.collaborationRelationship,
                    fallback="组织级协作关系已进入统一认知层。",
                ),
                evidenceCount=len(evidence_ids),
                version=1,
                createdAt=now,
                updatedAt=now,
            )
        )

    for record in records:
        _upsert_theme_cluster(db, record)
    return records


def _build_event_line_question(
    task_group: list[TaskRecord],
    event_line_id: str,
    event_line_name: str,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> list[OpenQuestionRecord]:
    questions: list[OpenQuestionRecord] = []
    if not any((task.desc or "").strip() for task in task_group):
        questions.append(
            OpenQuestionRecord(
                id=_stable_id("openq", event_line_id, "desc"),
                clientId=task_group[0].clientId or "",
                scopeType="event_line",
                scopeId=event_line_id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=event_line_name,
                question=f"{event_line_name} 还缺少完整背景描述，这条线到底在推进什么？",
                reason="事件线下的任务标题存在，但缺少连续背景。",
                blockerLevel="medium",
                status="awaiting_review",
                createdAt=now,
                updatedAt=now,
            )
        )
    if not any((task.nextAction or (task.projectContext.nextAction if task.projectContext else "")) for task in task_group):
        questions.append(
            OpenQuestionRecord(
                id=_stable_id("openq", event_line_id, "next"),
                clientId=task_group[0].clientId or "",
                scopeType="event_line",
                scopeId=event_line_id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey=event_line_name,
                question=f"{event_line_name} 的下一步动作还没有被结构化记录。",
                reason="任务有推进，但未形成统一下一步。",
                blockerLevel="high",
                status="awaiting_review",
                createdAt=now,
                updatedAt=now,
            )
        )
    return questions


def _sync_open_questions_and_conflicts(
    db: Database,
    workspace: ClientWorkspaceResponse,
    notebook_summary: OrganizationNotebookSnapshot | None,
    memory_status: MemoryStatus | None,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
) -> tuple[list[OpenQuestionRecord], list[ConflictGroupRecord]]:
    questions: list[OpenQuestionRecord] = []
    conflicts: list[ConflictGroupRecord] = []

    for gap in (notebook_summary.informationGaps[:4] if notebook_summary else []):
        questions.append(
            OpenQuestionRecord(
                id=_stable_id("openq", workspace.client.id, "client", gap),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey="client_notebook",
                question=gap,
                reason="当前客户背景资料里还缺少这部分信息。",
                blockerLevel="medium",
                status="awaiting_review",
                createdAt=now,
                updatedAt=now,
            )
        )

    if memory_status and memory_status.lowEvidenceJudgments:
        questions.append(
            OpenQuestionRecord(
                id=_stable_id("openq", workspace.client.id, "client", "low_evidence"),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                themeKey="evidence_gap",
                question="当前有哪些客户判断仍然建立在低证据基础上？",
                reason=f"系统识别到 {memory_status.lowEvidenceJudgments} 条低证据判断。",
                blockerLevel="high",
                status="awaiting_review",
                createdAt=now,
                updatedAt=now,
            )
        )

    if memory_status and memory_status.pendingClarifications:
        conflicts.append(
            ConflictGroupRecord(
                id=_stable_id("conflict", workspace.client.id, "clarification"),
                clientId=workspace.client.id,
                scopeType="client",
                scopeId=workspace.client.id,
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                conflictType="pending_clarification",
                title="客户主判断仍受待澄清问题影响",
                summary=f"当前还有 {memory_status.pendingClarifications} 个待澄清问题，不能直接把现有结论抬成正式判断。",
                evidenceIds=[],
                unresolvedQuestionIds=[],
                resolutionStatus="awaiting_review",
                severity="high",
                createdAt=now,
                updatedAt=now,
            )
        )

    event_line_groups = _event_line_groups(workspace.relatedTasks)
    for event_line_id, group in event_line_groups.items():
        task_group: list[TaskRecord] = sorted(group["tasks"], key=lambda item: item.updatedAt, reverse=True)
        questions.extend(
            _build_event_line_question(
                task_group,
                event_line_id,
                group["name"],
                now,
                origin_type=origin_type,
                authority_level=authority_level,
                quality_tier=quality_tier,
            )
        )
        blocked_titles = [
            _first_non_empty(task.currentBlocker, task.projectContext.currentBlocker if task.projectContext else None)
            for task in task_group
        ]
        blockers = _unique(blocked_titles)
        if blockers:
            conflicts.append(
                ConflictGroupRecord(
                    id=_stable_id("conflict", workspace.client.id, event_line_id, "blocker"),
                    clientId=workspace.client.id,
                    scopeType="event_line",
                    scopeId=event_line_id,
                    originType=origin_type,
                    authorityLevel=authority_level,
                    qualityTier=quality_tier,
                    conflictType="blocker_cluster",
                    title=f"{group['name']} 当前卡点",
                    summary="；".join(blockers[:3]),
                    evidenceIds=_list_evidence_ids_by_scope(
                        db,
                        workspace.client.id,
                        "event_line",
                        event_line_id,
                        dedupe_by_cluster_key=True,
                    )[:4],
                    unresolvedQuestionIds=[item.id for item in questions if item.scopeType == "event_line" and item.scopeId == event_line_id][:3],
                    resolutionStatus="awaiting_review",
                    severity="high" if len(blockers) > 1 else "medium",
                    createdAt=now,
                    updatedAt=now,
                )
            )

    for question in questions:
        _upsert_open_question(db, question)
    for conflict in conflicts:
        _upsert_conflict_group(db, conflict)
    return questions, conflicts


def _sync_context_pack(
    db: Database,
    workspace: ClientWorkspaceResponse,
    target_type: AnalysisScopeType,
    target_id: str,
    theme_clusters: list[ThemeClusterRecord],
    conflict_groups: list[ConflictGroupRecord],
    open_questions: list[OpenQuestionRecord],
    job_id: str | None,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
    source_snapshot_hash: str,
) -> ContextPackRecord:
    target_themes = [
        item
        for item in theme_clusters
        if (item.scopeType == target_type and item.scopeId == target_id)
        or (target_type == "client" and item.scopeType == "client" and item.scopeId == workspace.client.id)
    ]
    target_conflicts = [
        item
        for item in conflict_groups
        if (item.scopeType == target_type and item.scopeId == target_id)
        or (target_type == "client" and item.scopeType == "client" and item.scopeId == workspace.client.id)
    ]
    target_questions = [
        item
        for item in open_questions
        if (item.scopeType == target_type and item.scopeId == target_id)
        or (target_type == "client" and item.scopeType == "client" and item.scopeId == workspace.client.id)
    ]
    evidence_ids = _list_evidence_ids_by_scope(db, workspace.client.id, target_type, target_id)
    if target_type != "client":
        evidence_ids = evidence_ids + _list_evidence_ids_by_scope(db, workspace.client.id, "client", workspace.client.id)
    current_row = db.fetchone(
        """
        SELECT id
        FROM context_packs
        WHERE client_id = ? AND target_type = ? AND target_id = ? AND source_snapshot_hash = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, target_type, target_id, source_snapshot_hash),
    )
    previous_row = db.fetchone(
        """
        SELECT id
        FROM context_packs
        WHERE client_id = ? AND target_type = ? AND target_id = ? AND COALESCE(invalidated_by, '') = ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, target_type, target_id),
    )
    context_pack_id = str(current_row["id"]) if current_row else _new_id("ctx")
    context_pack = ContextPackRecord(
        id=context_pack_id,
        clientId=workspace.client.id,
        jobId=job_id,
        targetType=target_type,
        targetId=target_id,
        originType=origin_type,
        authorityLevel=authority_level,
        qualityTier=quality_tier,
        supersedesId=None if current_row else (str(previous_row["id"]) if previous_row else None),
        sourceSnapshotHash=source_snapshot_hash,
        staleReason=None,
        invalidatedBy=None,
        promptVersion="analysis-center-v1",
        sourceCount=len(workspace.documentCards) + len(workspace.meetings) + len(workspace.relatedTasks),
        evidenceCount=len(_unique(evidence_ids)),
        payload={
            "client": {
                "id": workspace.client.id,
                "name": workspace.client.name,
                "stage": workspace.client.stage,
                "intro": workspace.client.intro,
            },
            "scope": {"type": target_type, "id": target_id},
            "goals": [goal.title for goal in workspace.goals[:4]],
            "dnaModules": [
                {
                    "key": module.moduleKey,
                    "title": module.title,
                    "summary": module.summary,
                    "missingInfo": module.missingInfo[:3],
                }
                for module in workspace.dnaModules
                if module.hasDocument
            ],
            "projectModules": [
                {
                    "id": module.id,
                    "name": module.name,
                    "goal": module.goal,
                    "ownerName": module.ownerName,
                }
                for module in workspace.projectModules[:6]
            ],
            "projectFlows": [
                {
                    "id": flow.id,
                    "name": flow.name,
                    "moduleName": flow.moduleName,
                    "scenario": flow.scenario,
                    "riskPoints": flow.riskPoints[:3],
                }
                for flow in workspace.projectFlows[:6]
            ],
            "themes": [_model_dump(item) for item in target_themes[:8]],
            "conflicts": [_model_dump(item) for item in target_conflicts[:6]],
            "openQuestions": [_model_dump(item) for item in target_questions[:8]],
            "latestMeetings": [
                {
                    "id": meeting.id,
                    "title": meeting.title,
                    "stage": meeting.stage,
                    "updatedAt": meeting.updatedAt,
                }
                for meeting in workspace.meetings[:5]
            ],
            "relatedTasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "ownerName": task.ownerName,
                    "eventLineId": task.eventLineId,
                    "eventLineName": task.eventLineName,
                    "moduleName": task.projectModuleName,
                    "flowName": task.projectFlowName,
                }
                for task in workspace.relatedTasks[:12]
                if target_type == "client"
                or (target_type == "event_line" and task.eventLineId == target_id)
                or (target_type == "module" and task.projectModuleId == target_id)
                or (target_type == "flow" and task.projectFlowId == target_id)
            ],
        },
        staleAt=None,
        createdAt=now,
        updatedAt=now,
    )
    _upsert_context_pack(db, context_pack)
    if not current_row:
        _mark_previous_record_stale(
            db,
            "context_packs",
            str(previous_row["id"]) if previous_row else None,
            invalidated_by=context_pack.id,
            stale_reason="scope_changed" if target_type != "client" else "new_document",
            now=now,
        )
    _upsert_sync_memory_record(
        db,
        client_id=workspace.client.id,
        scope_type=target_type,
        scope_id=target_id,
        payload=DerivedSyncSerializer.serialize_context_pack(
            context_pack,
            target_themes,
            target_conflicts,
            target_questions,
        ),
        source_fingerprint=_stable_id("memfp", context_pack.id, str(context_pack.evidenceCount)),
        synced_at=now,
        now=now,
    )
    return context_pack


def _sync_dna_delta(
    db: Database,
    workspace: ClientWorkspaceResponse,
    notebook_summary: OrganizationNotebookSnapshot | None,
    memory_status: MemoryStatus | None,
    context_pack: ContextPackRecord,
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
    source_snapshot_hash: str,
) -> DnaDeltaRecord | None:
    missing_modules = [module.title for module in workspace.dnaModules if not module.hasDocument]
    gaps = list(notebook_summary.informationGaps[:2] if notebook_summary else [])
    if not missing_modules and not gaps and not (memory_status and memory_status.lowEvidenceJudgments):
        return None
    summary_parts = []
    if missing_modules:
        summary_parts.append(f"待补模块：{'、'.join(missing_modules[:3])}")
    if gaps:
        summary_parts.append(f"信息缺口：{'；'.join(gaps[:2])}")
    if memory_status and memory_status.lowEvidenceJudgments:
        summary_parts.append(f"低证据判断 {memory_status.lowEvidenceJudgments} 条")
    current_row = db.fetchone(
        """
        SELECT id, previous_version
        FROM dna_deltas
        WHERE client_id = ? AND dimension = ? AND source_snapshot_hash = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, "organization_context", source_snapshot_hash),
    )
    previous_row = db.fetchone(
        """
        SELECT id
        FROM dna_deltas
        WHERE client_id = ? AND dimension = ? AND COALESCE(invalidated_by, '') = ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, "organization_context"),
    )
    record = DnaDeltaRecord(
        id=str(current_row["id"]) if current_row else _new_id("dnadelta"),
        clientId=workspace.client.id,
        dimension="organization_context",
        previousVersion=None,
        originType=origin_type,
        authorityLevel=authority_level,
        qualityTier=quality_tier,
        supersedesId=None if current_row else (str(previous_row["id"]) if previous_row else None),
        sourceSnapshotHash=source_snapshot_hash,
        staleReason=None,
        invalidatedBy=None,
        proposedChange="需要先补齐项目底稿和低证据信号，再把客户判断升格为正式 DNA。",
        summary="；".join(summary_parts),
        evidenceIds=_list_evidence_ids_by_scope(db, workspace.client.id, "client", workspace.client.id)[:6],
        confidence="medium" if missing_modules or gaps else "low",
        status="awaiting_review",
        contextPackId=context_pack.id,
        createdAt=now,
        updatedAt=now,
    )
    _upsert_dna_delta(db, record)
    if not current_row:
        _mark_previous_record_stale(
            db,
            "dna_deltas",
            str(previous_row["id"]) if previous_row else None,
            invalidated_by=record.id,
            stale_reason="new_document",
            now=now,
        )
    return record


def _sync_judgment_versions(
    db: Database,
    workspace: ClientWorkspaceResponse,
    context_pack: ContextPackRecord,
    conflict_groups: list[ConflictGroupRecord],
    now: str,
    *,
    origin_type: AnalysisOriginType,
    authority_level: AnalysisAuthorityLevel,
    quality_tier: AnalysisQualityTier,
    source_snapshot_hash: str,
) -> list[JudgmentVersionRecord]:
    records: list[JudgmentVersionRecord] = []
    client_conflicts = [
        item for item in conflict_groups if item.scopeType == "client" and item.scopeId == workspace.client.id
    ]
    client_evidence = _list_evidence_ids_by_scope(db, workspace.client.id, "client", workspace.client.id)[:8]
    client_summary = _first_non_empty_non_boilerplate(
        workspace.goals[0].title if workspace.goals else None,
        workspace.documentCards[0].shortSummary if workspace.documentCards else None,
        workspace.client.intro,
        fallback=f"{workspace.client.name} 当前还处于资料与判断收束阶段。",
    )
    current_client_row = db.fetchone(
        """
        SELECT id, version
        FROM judgment_versions
        WHERE client_id = ? AND target_type = 'client' AND target_id = ? AND topic = ? AND source_snapshot_hash = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, workspace.client.id, "client_overview", source_snapshot_hash),
    )
    previous_client_row = db.fetchone(
        """
        SELECT id, version
        FROM judgment_versions
        WHERE client_id = ? AND target_type = 'client' AND target_id = ? AND topic = ? AND COALESCE(invalidated_by, '') = ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (workspace.client.id, workspace.client.id, "client_overview"),
    )
    client_record = JudgmentVersionRecord(
            id=str(current_client_row["id"]) if current_client_row else _new_id("judgment"),
            clientId=workspace.client.id,
            targetType="client",
            targetId=workspace.client.id,
            topic="client_overview",
            version=int(current_client_row["version"] or 1) if current_client_row else int(previous_client_row["version"] or 0) + 1 if previous_client_row else 1,
            status="awaiting_review",
            originType=origin_type,
            authorityLevel=authority_level,
            qualityTier=quality_tier,
            supersedesId=None if current_client_row else (str(previous_client_row["id"]) if previous_client_row else None),
            sourceSnapshotHash=source_snapshot_hash,
            staleReason=None,
            invalidatedBy=None,
            summary=client_summary,
            evidenceIds=client_evidence,
            contextPackId=context_pack.id,
            riskLevel="high" if client_conflicts else "medium",
            confidence="medium" if len(client_evidence) >= 3 else "low",
            createdAt=now,
            updatedAt=now,
        )
    records.append(client_record)

    for event_line_id, group in _event_line_groups(workspace.relatedTasks).items():
        tasks: list[TaskRecord] = sorted(group["tasks"], key=lambda item: item.updatedAt, reverse=True)
        blockers = _unique(
            [
                item
                for task in tasks
                for item in (
                    task.currentBlocker,
                    task.projectContext.currentBlocker if task.projectContext else None,
                    task.nextAction,
                )
            ]
        )
        summary = _first_non_empty(
            tasks[0].desc if tasks else None,
            tasks[0].projectContext.recentProgress if tasks and tasks[0].projectContext else None,
            tasks[0].title if tasks else None,
            fallback=f"{group['name']} 当前还缺少稳定的事件线判断。",
        )
        current_row = db.fetchone(
            """
            SELECT id, version
            FROM judgment_versions
            WHERE client_id = ? AND target_type = 'event_line' AND target_id = ? AND topic = ? AND source_snapshot_hash = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (workspace.client.id, event_line_id, group["name"], source_snapshot_hash),
        )
        previous_row = db.fetchone(
            """
            SELECT id, version
            FROM judgment_versions
            WHERE client_id = ? AND target_type = 'event_line' AND target_id = ? AND topic = ? AND COALESCE(invalidated_by, '') = ''
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (workspace.client.id, event_line_id, group["name"]),
        )
        records.append(
            JudgmentVersionRecord(
                id=str(current_row["id"]) if current_row else _new_id("judgment"),
                clientId=workspace.client.id,
                targetType="event_line",
                targetId=event_line_id,
                topic=group["name"],
                version=int(current_row["version"] or 1) if current_row else int(previous_row["version"] or 0) + 1 if previous_row else 1,
                status="awaiting_review" if blockers else "draft",
                originType=origin_type,
                authorityLevel=authority_level,
                qualityTier=quality_tier,
                supersedesId=None if current_row else (str(previous_row["id"]) if previous_row else None),
                sourceSnapshotHash=source_snapshot_hash,
                staleReason=None,
                invalidatedBy=None,
                summary=summary,
                evidenceIds=_list_evidence_ids_by_scope(db, workspace.client.id, "event_line", event_line_id)[:8],
                contextPackId=context_pack.id,
                riskLevel="high" if blockers else "medium",
                confidence="medium" if len(tasks) >= 2 else "low",
                createdAt=now,
                updatedAt=now,
            )
    )

    for record in records:
        _upsert_judgment_version(db, record)
        if not record.supersedesId:
            continue
        _mark_previous_record_stale(
            db,
            "judgment_versions",
            record.supersedesId,
            invalidated_by=record.id,
            stale_reason="new_document" if record.targetType == "client" else "scope_changed",
            now=now,
        )
    return records


def _sync_runtime_logs_from_legacy_runs(db: Database, workspace: ClientWorkspaceResponse) -> list[RuntimeRunLogRecord]:
    records: list[RuntimeRunLogRecord] = []
    for run in workspace.analysisRuns[:8]:
        legacy_summary = _first_non_empty(
            run.structuredSummary.content if run.structuredSummary else None,
            run.structuredSummary.judgment if run.structuredSummary else None,
            run.structuredSummary.analysis if run.structuredSummary else None,
            run.question,
            fallback="历史分析运行",
        )
        record = RuntimeRunLogRecord(
            id=_stable_id("runlog", workspace.client.id, "legacy", run.id),
            clientId=workspace.client.id,
            jobId=None,
            provider=run.providerUsed,
            model=None,
            lane="cloud_final",
            cacheHit=False,
            degraded=run.answerMode in {"grounded_fallback", "system_failure"} or run.longAnswerStatus == "fallback",
            documentCount=run.evidenceSummary.masterHitCount + run.evidenceSummary.surrogateHitCount,
            evidenceCount=len(run.evidenceSummary.evidenceList),
            conflictCount=0,
            contextTimeRange=None,
            promptVersion="legacy-analysis-run",
            schemaVersion="legacy-analysis-run",
            summary=legacy_summary,
            detail={
                "phase": run.phase,
                "status": run.status,
                "llmInvoked": run.llmInvoked,
                "timing": run.timing,
                "latestRunSummary": legacy_summary,
            },
            createdAt=run.updatedAt,
        )
        _upsert_runtime_run_log(db, record)
        records.append(record)
    return records


def refresh_client_analysis_projection(
    db: Database,
    workspace: ClientWorkspaceResponse,
    *,
    notebook_summary: OrganizationNotebookSnapshot | None = None,
    memory_status: MemoryStatus | None = None,
    target_type: AnalysisScopeType = "client",
    target_id: str | None = None,
    job_id: str | None = None,
    origin_type: AnalysisOriginType = "projection",
    authority_level: AnalysisAuthorityLevel = "fallback",
    quality_tier: AnalysisQualityTier = "normalized",
) -> AnalysisCenterProjectionBundle:
    now = _now_iso()
    scope_id = target_id or workspace.client.id
    source_snapshot_hash = _compute_scope_snapshot_hash(workspace, scope_type=target_type, scope_id=scope_id)
    _sync_doc_skeletons(db, workspace, now)
    _sync_evidence_cards(
        db,
        workspace,
        notebook_summary,
        memory_status,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
    )
    theme_clusters = _sync_theme_clusters(
        db,
        workspace,
        notebook_summary,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
    )
    open_questions, conflict_groups = _sync_open_questions_and_conflicts(
        db,
        workspace,
        notebook_summary,
        memory_status,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
    )
    context_pack = _sync_context_pack(
        db,
        workspace,
        target_type=target_type,
        target_id=scope_id,
        theme_clusters=theme_clusters,
        conflict_groups=conflict_groups,
        open_questions=open_questions,
        job_id=job_id,
        now=now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
        source_snapshot_hash=source_snapshot_hash,
    )
    for conflict in conflict_groups:
        db.execute(
            "UPDATE conflict_groups SET context_pack_id = ? WHERE id = ?",
            (context_pack.id, conflict.id),
        )
    _sync_dna_delta(
        db,
        workspace,
        notebook_summary,
        memory_status,
        context_pack,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
        source_snapshot_hash=source_snapshot_hash,
    )
    judgments = _sync_judgment_versions(
        db,
        workspace,
        context_pack,
        conflict_groups,
        now,
        origin_type=origin_type,
        authority_level=authority_level,
        quality_tier=quality_tier,
        source_snapshot_hash=source_snapshot_hash,
    )
    run_logs = _sync_runtime_logs_from_legacy_runs(db, workspace)
    summary = _build_analysis_center_summary(db, workspace.client.id)
    return AnalysisCenterProjectionBundle(
        summary=summary,
        latest_context_pack=context_pack,
        judgment_bundle=None,
        latest_resolution_trace=None,
        latest_judgments=judgments[:6],
        latest_topics=theme_clusters[:8],
        latest_conflicts=conflict_groups[:6],
        latest_open_questions=open_questions[:8],
        latest_run_logs=run_logs[:6] or list_runtime_run_logs(db, workspace.client.id, limit=6),
    )


def get_client_analysis_bundle(
    db: Database,
    workspace: ClientWorkspaceResponse,
    *,
    requested_scope_type: AnalysisScopeType = "client",
    requested_scope_id: str | None = None,
    intent_profile: AnalysisIntentProfile = "client_overview",
) -> AnalysisCenterProjectionBundle:
    scope_id = requested_scope_id or workspace.client.id
    related_refs = _build_related_refs(workspace)
    latest_context_pack, _ = resolve_context_pack(
        db,
        client_id=workspace.client.id,
        requested_scope_type=requested_scope_type,
        requested_scope_id=scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
        include_fallback=True,
    )
    latest_judgment, _ = resolve_best_judgment(
        db,
        client_id=workspace.client.id,
        requested_scope_type=requested_scope_type,
        requested_scope_id=scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
        include_fallback=True,
    )
    judgments = list_judgment_versions(db, workspace.client.id, limit=6)
    if latest_judgment and latest_judgment.id not in {item.id for item in judgments}:
        judgments = [latest_judgment, *judgments][:6]
    judgment_bundle = resolve_judgment_bundle(
        db,
        client_id=workspace.client.id,
        requested_scope_type=requested_scope_type,
        requested_scope_id=scope_id,
        intent_profile=intent_profile,
        related_refs=related_refs,
    )
    return AnalysisCenterProjectionBundle(
        summary=_build_analysis_center_summary(db, workspace.client.id),
        latest_context_pack=latest_context_pack,
        judgment_bundle=judgment_bundle,
        latest_resolution_trace=judgment_bundle.resolutionTrace,
        latest_judgments=judgments[:6],
        latest_topics=list_theme_clusters(db, workspace.client.id, limit=8),
        latest_conflicts=list_conflict_groups(db, workspace.client.id, limit=6),
        latest_open_questions=list_open_questions(db, workspace.client.id, limit=8),
        latest_run_logs=list_runtime_run_logs(db, workspace.client.id, limit=6),
    )


def create_analysis_job(
    db: Database,
    payload: AnalysisJobCreatePayload,
    *,
    source_snapshot: dict[str, Any] | None = None,
) -> AnalysisJobRecord:
    scope_type = payload.scopeType or "client"
    now = _now_iso()
    snapshot_payload = source_snapshot or {
        "question": payload.question,
        "sourceScope": payload.sourceScope,
        "featureFlags": payload.featureFlags,
    }
    source_snapshot_hash = _build_snapshot_hash(snapshot_payload)
    dedupe_key = _stable_id(
        "analysisdedupe",
        payload.jobType,
        payload.clientId,
        scope_type,
        payload.scopeId,
        payload.triggerType,
        payload.intentProfile,
        source_snapshot_hash,
    )
    existing_row = db.fetchone(
        """
        SELECT *
        FROM analysis_jobs
        WHERE dedupe_key = ? AND status IN ('queued', 'running')
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (dedupe_key,),
    )
    if existing_row:
        return _build_analysis_job_record(existing_row)

    job_id = _new_id("analysisjob")
    job = AnalysisJobRecord(
        id=job_id,
        jobType=payload.jobType,
        clientId=payload.clientId,
        scopeType=scope_type,
        scopeId=payload.scopeId,
        status="queued",
        priority=payload.priority,
        triggerType=payload.triggerType,
        intentProfile=payload.intentProfile,
        question=payload.question,
        sourceSnapshot=_serialize_snapshot(snapshot_payload),
        sourceSnapshotHash=source_snapshot_hash,
        dedupeKey=dedupe_key,
        featureFlags=payload.featureFlags,
        progress=0.0,
        stageLabel="已进入分析队列",
        runLogId=None,
        error=None,
        lockedBy=None,
        lockedAt=None,
        lockExpiresAt=None,
        attemptCount=0,
        lastError=None,
        createdAt=now,
        updatedAt=now,
        startedAt=None,
        finishedAt=None,
    )
    _upsert_analysis_job(db, job)
    queued_stage = AnalysisJobStageRunRecord(
        id=_stable_id("analysisstage", job.id, "queued"),
        jobId=job.id,
        stageName="queued",
        status="queued",
        provider=None,
        modelName=None,
        lane="cloud_final",
        cacheKey=None,
        cacheHit=False,
        degraded=False,
        evidenceCount=0,
        topicCount=0,
        conflictCount=0,
        contextTimeRange=None,
        metrics={},
        detail="等待进入分析中心",
        correlationId=None,
        startedAt=None,
        finishedAt=None,
        createdAt=now,
        updatedAt=now,
    )
    _upsert_stage_run(db, queued_stage)
    return job


def _read_setting(db: Database, key: str, default: str = "") -> str:
    row = db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
    return str(row["value"]) if row and row["value"] is not None else default


def _write_setting(db: Database, key: str, value: str) -> None:
    _upsert(db, "settings", {"key": key, "value": value}, conflict_columns=("key",))


def _increment_json_counter_setting(db: Database, key: str, bucket: str) -> None:
    normalized_bucket = bucket if bucket in _ANALYSIS_WORKER_BUCKETS else "unknown"
    payload = _parse_json_dict(_read_setting(db, key, "{}"))
    payload[normalized_bucket] = int(payload.get(normalized_bucket, 0) or 0) + 1
    payload["updatedAt"] = _now_iso()
    _write_setting(db, key, to_json(payload))


def _worker_backfill_streak_key(worker_id: str) -> str:
    return f"analysis.worker.backfill_streak.{worker_id}"


def _get_worker_backfill_streak(db: Database, worker_id: str) -> int:
    try:
        return int(_read_setting(db, _worker_backfill_streak_key(worker_id), "0") or 0)
    except ValueError:
        return 0


def _set_worker_backfill_streak(db: Database, worker_id: str, streak: int) -> None:
    _write_setting(db, _worker_backfill_streak_key(worker_id), str(max(streak, 0)))


def _record_analysis_job_bucket_claim(db: Database, bucket: str) -> None:
    _increment_json_counter_setting(db, "analysis.worker.claim_counts", bucket)


def _record_analysis_job_lock_contention(db: Database, bucket: str) -> None:
    _increment_json_counter_setting(db, "analysis.worker.lock_contention", bucket)


def renew_analysis_job_lock(
    db: Database,
    job_id: str,
    worker_id: str,
    *,
    ttl_minutes: int = 10,
) -> None:
    now = _now_iso()
    lock_expires_at = (datetime.now() + timedelta(minutes=ttl_minutes)).replace(microsecond=0).isoformat()
    db.execute(
        """
        UPDATE analysis_jobs
        SET locked_at = ?,
            lock_expires_at = ?,
            updated_at = ?
        WHERE id = ? AND status = 'running' AND COALESCE(locked_by, '') = ?
        """,
        (now, lock_expires_at, now, job_id, worker_id),
    )


def get_candidate_review_sla_summary(db: Database, *, client_id: str | None = None) -> dict[str, int]:
    exclude_ids = _build_canary_exclusion_scope(db)
    recent_cutoff = (datetime.now() - timedelta(hours=24)).replace(microsecond=0).isoformat()
    warning_cutoff = (datetime.now() - timedelta(hours=_CANDIDATE_REVIEW_WARNING_AFTER_HOURS)).replace(microsecond=0).isoformat()
    overdue_cutoff = (datetime.now() - timedelta(hours=_CANDIDATE_REVIEW_OVERDUE_AFTER_HOURS)).replace(microsecond=0).isoformat()
    new_unreviewed_24h_count = 0
    warning_count = 0
    overdue_count = 0
    for table_name, status_column in (
        ("judgment_versions", "status"),
        ("dna_deltas", "status"),
        ("conflict_groups", "resolution_status"),
    ):
        rows = db.fetchall(
            f"""
            SELECT id, created_at
            FROM {table_name}
            WHERE {status_column} IN ('awaiting_review', 'awaiting_revision')
            {" AND client_id = ?" if client_id else ""}
            """,
            tuple([client_id] if client_id else []),
        )
        excluded_for_table = exclude_ids.get(table_name, set())
        for row in rows:
            row_id = str(row["id"] or "")
            if row_id in excluded_for_table:
                continue
            created_at = _parse_dt(str(row["created_at"] or ""))
            if created_at is None:
                continue
            created_iso = created_at.replace(microsecond=0).isoformat()
            if created_iso >= recent_cutoff:
                new_unreviewed_24h_count += 1
            if created_iso <= warning_cutoff:
                warning_count += 1
            if created_iso <= overdue_cutoff:
                overdue_count += 1
    return {
        "warningAfterHours": _CANDIDATE_REVIEW_WARNING_AFTER_HOURS,
        "overdueAfterHours": _CANDIDATE_REVIEW_OVERDUE_AFTER_HOURS,
        "newUnreviewed24hCount": new_unreviewed_24h_count,
        "warningCount": warning_count,
        "overdueCount": overdue_count,
    }


def is_analysis_backfill_paused(db: Database) -> bool:
    return _read_setting(db, "analysis.backfill.paused", "0") == "1"


def set_analysis_backfill_paused(db: Database, paused: bool) -> bool:
    _write_setting(db, "analysis.backfill.paused", "1" if paused else "0")
    return paused


def queue_main_chain_backfill(
    db: Database,
    payload: AnalysisBackfillMainChainPayload,
) -> AnalysisBackfillMainChainResultRecord:
    paused = set_analysis_backfill_paused(db, payload.pauseRequested) if payload.pauseRequested else is_analysis_backfill_paused(db)
    # 没指定 clientIds 时遍历所有客户,但跳过冷冻项目 — 它们不参与自动 backfill 分析
    client_ids = payload.clientIds or [str(row["id"]) for row in db.fetchall("SELECT id FROM clients WHERE frozen_at IS NULL ORDER BY updated_at DESC")]
    max_jobs = max(1, min(payload.maxJobs, 500))
    batch_size = max(1, min(payload.batchSize, max_jobs))
    candidates: list[AnalysisBackfillMainChainJobRecord] = []
    for client_id in client_ids:
        for intent_profile in ("client_overview", "dna_summary", "strategic_cockpit"):
            if len(candidates) >= max_jobs:
                break
            candidates.append(
                AnalysisBackfillMainChainJobRecord(
                    clientId=client_id,
                    scopeType="client",
                    scopeId=client_id,
                    jobType="strategy_pack",
                    triggerType="backfill",
                    intentProfile=intent_profile,
                )
            )
        if len(candidates) >= max_jobs:
            break
    if payload.dryRun:
        return AnalysisBackfillMainChainResultRecord(
            dryRun=True,
            pauseRequested=payload.pauseRequested,
            paused=paused,
            scannedClients=len(client_ids),
            queuedJobs=0,
            skippedJobs=0,
            candidates=candidates[:batch_size],
        )
    queued_jobs = 0
    skipped_jobs = 0
    for candidate in candidates[:batch_size]:
        existing_active = db.fetchone(
            """
            SELECT id
            FROM analysis_jobs
            WHERE client_id = ? AND scope_type = ? AND scope_id = ? AND trigger_type = ? AND intent_profile = ?
              AND status IN ('queued', 'running')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (
                candidate.clientId,
                candidate.scopeType,
                candidate.scopeId,
                candidate.triggerType,
                candidate.intentProfile,
            ),
        )
        if existing_active:
            skipped_jobs += 1
            continue
        create_analysis_job(
            db,
            AnalysisJobCreatePayload(
                jobType=candidate.jobType,
                clientId=candidate.clientId,
                scopeType=candidate.scopeType,
                scopeId=candidate.scopeId,
                priority="low",
                triggerType=candidate.triggerType,
                question="主链 backfill",
                intentProfile=candidate.intentProfile,
            ),
            source_snapshot={
                "clientId": candidate.clientId,
                "scopeType": candidate.scopeType,
                "scopeId": candidate.scopeId,
                "triggerType": candidate.triggerType,
                "intentProfile": candidate.intentProfile,
            },
        )
        queued_jobs += 1
    return AnalysisBackfillMainChainResultRecord(
        dryRun=False,
        pauseRequested=payload.pauseRequested,
        paused=paused,
        scannedClients=len(client_ids),
        queuedJobs=queued_jobs,
        skippedJobs=skipped_jobs,
        candidates=candidates[:batch_size],
    )


def recover_stale_analysis_jobs(db: Database) -> None:
    now = _now_iso()
    db.execute(
        """
        UPDATE analysis_jobs
        SET status = 'queued',
            stage_label = '检测到中断，已重新入队',
            locked_by = NULL,
            locked_at = NULL,
            lock_expires_at = NULL,
            updated_at = ?
        WHERE status IN ('running', 'preparing', 'extracting', 'clustering', 'comparing', 'drafting')
        """,
        (now,),
    )


def claim_next_analysis_job(db: Database, worker_id: str) -> AnalysisJobRecord | None:
    now = _now_iso()
    lock_expires_at = (datetime.now() + timedelta(minutes=10)).replace(microsecond=0).isoformat()
    backfill_paused = is_analysis_backfill_paused(db)
    backfill_streak = _get_worker_backfill_streak(db, worker_id)

    bucket_queries = {
        "interactive": (
            """
            SELECT *
            FROM analysis_jobs
            WHERE status = 'queued'
              AND (lock_expires_at IS NULL OR lock_expires_at = '' OR lock_expires_at <= ?)
              AND COALESCE(trigger_type, 'manual') != 'backfill'
              AND (
                priority = 'high'
                OR COALESCE(trigger_type, 'manual') = 'manual'
                OR intent_profile IN ('task_ai', 'meeting_enhance')
              )
            ORDER BY
              CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END ASC,
              created_at ASC
            LIMIT 1
            """,
            (now,),
        ),
        "system": (
            """
            SELECT *
            FROM analysis_jobs
            WHERE status = 'queued'
              AND (lock_expires_at IS NULL OR lock_expires_at = '' OR lock_expires_at <= ?)
              AND COALESCE(trigger_type, 'manual') != 'backfill'
              AND NOT (
                priority = 'high'
                OR COALESCE(trigger_type, 'manual') = 'manual'
                OR intent_profile IN ('task_ai', 'meeting_enhance')
              )
            ORDER BY
              CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END ASC,
              created_at ASC
            LIMIT 1
            """,
            (now,),
        ),
        "backfill": (
            """
            SELECT *
            FROM analysis_jobs
            WHERE status = 'queued'
              AND (lock_expires_at IS NULL OR lock_expires_at = '' OR lock_expires_at <= ?)
              AND COALESCE(trigger_type, 'manual') = 'backfill'
            ORDER BY
              CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END ASC,
              created_at ASC
            LIMIT 1
            """,
            (now,),
        ),
    }

    def _claim(conn):
        bucket_order = ["interactive", "system"]
        if not backfill_paused and backfill_streak < _ANALYSIS_BACKFILL_CONSECUTIVE_LIMIT:
            bucket_order.append("backfill")
        for bucket in bucket_order:
            query, params = bucket_queries[bucket]
            row = conn.execute(query, params).fetchone()
            if not row:
                continue
            updated = conn.execute(
                """
                UPDATE analysis_jobs
                SET status = 'running',
                    stage_label = '正在执行分析任务',
                    locked_by = ?,
                    locked_at = ?,
                    lock_expires_at = ?,
                    attempt_count = COALESCE(attempt_count, 0) + 1,
                    updated_at = ?,
                    started_at = COALESCE(started_at, ?)
                WHERE id = ?
                  AND status = 'queued'
                  AND (lock_expires_at IS NULL OR lock_expires_at = '' OR lock_expires_at <= ?)
                """,
                (worker_id, now, lock_expires_at, now, now, str(row["id"]), now),
            )
            if updated.rowcount != 1:
                return {"jobId": None, "bucket": bucket, "contention": True}
            return {"jobId": str(row["id"]), "bucket": bucket, "contention": False}
        return {"jobId": None, "bucket": "backfill", "contention": False}

    claim_result = db.run_in_transaction(_claim)
    claimed_job_id = str(claim_result.get("jobId") or "")
    claimed_bucket = str(claim_result.get("bucket") or "unknown")
    if claim_result.get("contention"):
        _record_analysis_job_lock_contention(db, claimed_bucket)
    if not claimed_job_id:
        if not backfill_paused and backfill_streak >= _ANALYSIS_BACKFILL_CONSECUTIVE_LIMIT:
            _increment_json_counter_setting(db, "analysis.worker.backfill_throttle", "backfill")
            _set_worker_backfill_streak(db, worker_id, 0)
        return None
    _record_analysis_job_bucket_claim(db, claimed_bucket)
    if claimed_bucket == "backfill":
        _set_worker_backfill_streak(db, worker_id, backfill_streak + 1)
    else:
        _set_worker_backfill_streak(db, worker_id, 0)
    return get_analysis_job(db, claimed_job_id)


def fail_analysis_job(
    db: Database,
    job_id: str,
    *,
    stage_name: str,
    error: str,
    correlation_id: str | None = None,
) -> AnalysisJobRecord | None:
    job = get_analysis_job(db, job_id)
    if job is None:
        return None
    now_dt = datetime.now().replace(microsecond=0)
    now = now_dt.isoformat()
    retry_schedule = [30, 120, 600]
    should_retry = job.attemptCount <= len(retry_schedule)
    retry_delay = retry_schedule[job.attemptCount - 1] if should_retry and job.attemptCount > 0 else None
    retry_at = (now_dt + timedelta(seconds=retry_delay)).isoformat() if retry_delay is not None else None
    _upsert_stage_run(
        db,
        AnalysisJobStageRunRecord(
            id=_stable_id("analysisstage", job.id, stage_name, str(job.attemptCount), "failed"),
            jobId=job.id,
            stageName=stage_name,
            status="failed",
            provider="analysis-center",
            modelName="analysis-center-v0.3.2",
            lane="cloud_final",
            cacheKey=None,
            cacheHit=False,
            degraded=False,
            evidenceCount=0,
            topicCount=0,
            conflictCount=0,
            contextTimeRange=None,
            metrics={"attempt": job.attemptCount},
            detail=_truncate(error, 280),
            correlationId=correlation_id,
            startedAt=job.startedAt,
            finishedAt=now,
            createdAt=now,
            updatedAt=now,
        ),
    )
    failed_or_queued = AnalysisJobRecord(
        **{
            **_model_dump(job),
            "status": "queued" if should_retry else "failed",
            "progress": max(float(job.progress or 0.0), 1.0),
            "stageLabel": f"执行失败，{retry_delay}s 后重试" if should_retry and retry_delay is not None else "执行失败",
            "error": error if not should_retry else None,
            "lastError": error,
            "lockedBy": None,
            "lockedAt": None,
            "lockExpiresAt": retry_at if should_retry else None,
            "updatedAt": now,
            "finishedAt": None if should_retry else now,
        }
    )
    _upsert_analysis_job(db, failed_or_queued)
    return failed_or_queued


def execute_analysis_job_projection(
    db: Database,
    job: AnalysisJobRecord,
    workspace: ClientWorkspaceResponse,
    *,
    notebook_summary: OrganizationNotebookSnapshot | None = None,
    memory_status: MemoryStatus | None = None,
    lane: AnalysisLane = "cloud_final",
) -> AnalysisJobRecord:
    started_at = _now_iso()
    correlation_id = _stable_id("analysiscorr", job.id, str(job.attemptCount or 0), started_at)
    running_stage = AnalysisJobStageRunRecord(
        id=_stable_id("analysisstage", job.id, "analysis_pipeline", str(job.attemptCount or 0)),
        jobId=job.id,
        stageName="analysis_pipeline",
        status="running",
        provider="analysis-center",
        modelName="analysis-center-v0.3.2",
        lane=lane,
        cacheKey=job.sourceSnapshotHash or None,
        cacheHit=False,
        degraded=False,
        evidenceCount=0,
        topicCount=0,
        conflictCount=0,
        contextTimeRange=None,
        metrics={"attempt": job.attemptCount},
        detail="正在执行证据提取、主题归并和判断生成",
        correlationId=correlation_id,
        startedAt=started_at,
        finishedAt=None,
        createdAt=started_at,
        updatedAt=started_at,
    )
    _upsert_stage_run(db, running_stage)
    started_summary = f"{job.scopeType} 级分析任务已启动"
    run_log = RuntimeRunLogRecord(
        id=_stable_id("runlog", workspace.client.id, "analysis_job", job.id, str(job.attemptCount or 0)),
        clientId=workspace.client.id,
        jobId=job.id,
        analysisJobId=job.id,
        stageRunId=running_stage.id,
        contextPackId=None,
        judgmentVersionId=None,
        correlationId=correlation_id,
        provider="analysis-center",
        model="analysis-center-v0.3.2",
        lane=lane,
        cacheHit=False,
        degraded=False,
        documentCount=len(workspace.documentCards),
        evidenceCount=0,
        conflictCount=0,
        contextTimeRange=None,
        promptVersion="analysis-center-v0.3",
        schemaVersion="analysis-center-v0.3",
        summary=started_summary,
        detail={
            "jobType": job.jobType,
            "scopeId": job.scopeId,
            "scopeType": job.scopeType,
            "question": job.question,
            "intentProfile": job.intentProfile,
            "sourceSnapshotHash": job.sourceSnapshotHash,
            "latestRunSummary": started_summary,
        },
        createdAt=started_at,
    )
    _upsert_runtime_run_log(db, run_log)

    running_job = AnalysisJobRecord(
        **{
            **_model_dump(job),
            "status": "running",
            "progress": 18.0,
            "stageLabel": "正在生成证据与主题对象",
            "runLogId": run_log.id,
            "updatedAt": started_at,
            "startedAt": started_at,
        }
    )
    _upsert_analysis_job(db, running_job)
    if running_job.lockedBy:
        renew_analysis_job_lock(db, running_job.id, running_job.lockedBy)

    bundle = refresh_client_analysis_projection(
        db,
        workspace,
        notebook_summary=notebook_summary,
        memory_status=memory_status,
        target_type=job.scopeType,
        target_id=job.scopeId,
        job_id=job.id,
        origin_type="analysis",
        authority_level="candidate",
        quality_tier="normalized",
    )
    if running_job.lockedBy:
        renew_analysis_job_lock(db, running_job.id, running_job.lockedBy)
    best_judgment, resolution_trace = resolve_best_judgment(
        db,
        client_id=workspace.client.id,
        requested_scope_type=job.scopeType,
        requested_scope_id=job.scopeId,
        intent_profile=job.intentProfile,
        related_refs=_build_related_refs(workspace),
        include_fallback=True,
    )

    finished_at = _now_iso()
    _upsert_stage_run(
        db,
        AnalysisJobStageRunRecord(
            id=_stable_id("analysisstage", job.id, "analysis_pipeline", str(job.attemptCount or 0), "completed"),
            jobId=job.id,
            stageName="analysis_pipeline",
            status="completed",
            provider="analysis-center",
            modelName="analysis-center-v0.3.2",
            lane=lane,
            cacheKey=job.sourceSnapshotHash or None,
            cacheHit=False,
            degraded=False,
            evidenceCount=bundle.summary.evidenceCardCount,
            topicCount=bundle.summary.themeClusterCount,
            conflictCount=bundle.summary.conflictGroupCount,
            contextTimeRange=bundle.latest_context_pack.updatedAt if bundle.latest_context_pack else None,
            metrics={
                "evidenceCount": bundle.summary.evidenceCardCount,
                "topicCount": bundle.summary.themeClusterCount,
                "conflictCount": bundle.summary.conflictGroupCount,
                "draftJudgmentCount": bundle.summary.draftJudgmentCount,
            },
            detail="主链投影完成，已生成 context pack 与 judgment draft",
            correlationId=correlation_id,
            startedAt=started_at,
            finishedAt=finished_at,
            createdAt=finished_at,
            updatedAt=finished_at,
        ),
    )

    finished_summary = f"{job.scopeType} 级分析投影已完成"
    _upsert_runtime_run_log(
        db,
        RuntimeRunLogRecord(
            id=run_log.id,
            clientId=run_log.clientId,
            jobId=run_log.jobId,
            analysisJobId=job.id,
            stageRunId=running_stage.id,
            contextPackId=bundle.latest_context_pack.id if bundle.latest_context_pack else None,
            judgmentVersionId=best_judgment.id if best_judgment else None,
            correlationId=correlation_id,
            provider=run_log.provider,
            model=run_log.model,
            lane=run_log.lane,
            cacheHit=False,
            degraded=False,
            documentCount=len(workspace.documentCards),
            evidenceCount=bundle.summary.evidenceCardCount,
            conflictCount=bundle.summary.conflictGroupCount,
            contextTimeRange=bundle.latest_context_pack.updatedAt if bundle.latest_context_pack else None,
            promptVersion=run_log.promptVersion,
            schemaVersion=run_log.schemaVersion,
            summary=finished_summary,
            detail={
                "latestContextPackId": bundle.latest_context_pack.id if bundle.latest_context_pack else None,
                "latestJudgmentId": best_judgment.id if best_judgment else None,
                "draftJudgmentCount": bundle.summary.draftJudgmentCount,
                "latestRunSummary": bundle.summary.latestRunSummary or finished_summary,
                "intentProfile": job.intentProfile,
                "sourceSnapshotHash": job.sourceSnapshotHash,
                "resolutionTrace": resolution_trace.model_dump(mode="json"),
            },
            createdAt=run_log.createdAt,
        ),
    )

    completed_job = AnalysisJobRecord(
        **{
            **_model_dump(job),
            "status": "completed",
            "progress": 100.0,
            "stageLabel": "已生成 judgment draft，等待人工确认",
            "runLogId": run_log.id,
            "error": None,
            "lastError": None,
            "lockedBy": None,
            "lockedAt": None,
            "lockExpiresAt": None,
            "updatedAt": finished_at,
            "startedAt": started_at,
            "finishedAt": finished_at,
        }
    )
    _upsert_analysis_job(db, completed_job)
    return completed_job


def create_dna_delta(db: Database, payload: DnaDeltaCreatePayload) -> DnaDeltaRecord:
    now = _now_iso()
    source_snapshot_hash = _build_snapshot_hash(
        {
            "clientId": payload.clientId,
            "dimension": payload.dimension,
            "proposedChange": payload.proposedChange,
            "summary": payload.summary,
            "evidenceIds": payload.evidenceIds,
            "contextPackId": payload.contextPackId,
        }
    )
    current_row = db.fetchone(
        """
        SELECT id
        FROM dna_deltas
        WHERE client_id = ? AND dimension = ? AND COALESCE(invalidated_by, '') = ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (payload.clientId, payload.dimension),
    )
    record = DnaDeltaRecord(
        id=_new_id("dnadelta"),
        clientId=payload.clientId,
        dimension=payload.dimension,
        previousVersion=None,
        originType="human_override",
        authorityLevel="candidate",
        qualityTier="reviewed",
        supersedesId=str(current_row["id"]) if current_row else None,
        sourceSnapshotHash=source_snapshot_hash,
        staleReason=None,
        invalidatedBy=None,
        proposedChange=payload.proposedChange,
        summary=payload.summary,
        evidenceIds=payload.evidenceIds,
        confidence=payload.confidence,
        status="awaiting_review",
        contextPackId=payload.contextPackId,
        createdAt=now,
        updatedAt=now,
    )
    _upsert_dna_delta(db, record)
    _mark_previous_record_stale(
        db,
        "dna_deltas",
        str(current_row["id"]) if current_row else None,
        invalidated_by=record.id,
        stale_reason="manual_override",
        now=now,
    )
    return record


def _build_approval_record(row: Any) -> ApprovalRecordRecord:
    return ApprovalRecordRecord(
        id=str(row["id"]),
        approvalTargetType=str(row["approval_target_type"] or row["object_type"]),
        approvalTargetId=str(row["approval_target_id"] or row["object_id"]),
        clientId=str(row["client_id"]),
        policyType=str(row["policy_type"] or "analysis_review"),
        decision=str(row["decision"] or row["status"]),
        comment=str(row["comment"] or row["note"] or ""),
        decidedBy=str(row["decided_by"] or row["actor_name"] or ""),
        decidedAt=str(row["decided_at"] or row["created_at"]),
        metadata=_parse_json_dict(row["metadata_json"]),
    )


def decide_approval(
    db: Database,
    payload: ApprovalDecisionPayload,
    *,
    actor_id: str = "",
    actor_name: str = "",
) -> ApprovalRecordRecord:
    now = _now_iso()
    target_table = {
        "judgment_version": ("judgment_versions", _build_judgment_version_record, _upsert_judgment_version, "status"),
        "dna_delta": ("dna_deltas", _build_dna_delta_record, _upsert_dna_delta, "status"),
        "conflict_group": ("conflict_groups", _build_conflict_group_record, _upsert_conflict_group, "resolutionStatus"),
    }.get(payload.targetType)
    if target_table is None:
        raise ValueError("不支持的审批目标类型")
    table_name, row_builder, upsert_fn, status_field = target_table
    row = db.fetchone(f"SELECT * FROM {table_name} WHERE id = ?", (payload.targetId,))
    if not row:
        raise ValueError("审批目标不存在")
    record = row_builder(row)
    next_state: AnalysisReviewState = {
        "approved": "approved",
        "rejected": "rejected",
        "returned_for_revision": "awaiting_revision",
    }[payload.decision]
    updates = {
        **_model_dump(record),
        status_field: next_state,
        "updatedAt": now,
    }
    if hasattr(record, "authorityLevel"):
        updates["authorityLevel"] = "approved" if payload.decision == "approved" else record.authorityLevel
    if hasattr(record, "qualityTier") and payload.decision == "approved":
        updates["qualityTier"] = "reviewed"
    updated_record = type(record)(**updates)
    upsert_fn(db, updated_record)
    approval_id = _new_id("approval")
    _upsert(
        db,
        "approval_records",
        {
            "id": approval_id,
            "object_type": payload.targetType,
            "object_id": payload.targetId,
            "client_id": getattr(record, "clientId", ""),
            "status": payload.decision,
            "note": payload.comment,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "created_at": now,
            "approval_target_type": payload.targetType,
            "approval_target_id": payload.targetId,
            "policy_type": payload.policyType,
            "decision": payload.decision,
            "comment": payload.comment,
            "decided_by": actor_name or actor_id,
            "decided_at": now,
            "metadata_json": to_json(payload.metadata),
        },
    )
    approval_row = db.fetchone("SELECT * FROM approval_records WHERE id = ?", (approval_id,))
    if not approval_row:
        raise ValueError("审批记录写入失败")
    return _build_approval_record(approval_row)


def confirm_judgment(db: Database, payload: JudgmentConfirmPayload, *, actor_id: str = "", actor_name: str = "") -> JudgmentVersionRecord:
    decide_approval(
        db,
        ApprovalDecisionPayload(
            targetType="judgment_version",
            targetId=payload.judgmentId,
            decision=payload.action,
            comment=payload.note,
        ),
        actor_id=actor_id,
        actor_name=actor_name,
    )
    row = db.fetchone("SELECT * FROM judgment_versions WHERE id = ?", (payload.judgmentId,))
    if not row:
        raise ValueError("目标 judgment 不存在")
    return _build_judgment_version_record(row)


def get_analysis_migration_metrics(db: Database, *, window_days: int = 7) -> AnalysisMigrationMetricsRecord:
    cutoff = (datetime.now() - timedelta(days=window_days)).replace(microsecond=0).isoformat()
    rows = db.fetchall(
        "SELECT * FROM runtime_run_logs WHERE created_at >= ? ORDER BY created_at DESC",
        (cutoff,),
    )
    page_bucket_map = {
        "task_ai": "task_ai",
        "weekly_review": "weekly_review",
        "meeting_enhance": "meeting_enhance",
        "client_overview": "client_overview",
        "dna_summary": "dna_summary",
        "strategic_cockpit": "strategic_cockpit",
    }
    page_counts: dict[str, dict[str, float | int]] = {}
    resolver_groups: dict[tuple[str, str, str, str, str], set[str]] = {}
    total = 0
    new_object_hits = 0
    fallback_hits = 0
    for row in rows:
        detail = _parse_json_dict(row["detail_json"])
        trace = detail.get("resolutionTrace") if isinstance(detail.get("resolutionTrace"), dict) else {}
        selected = trace.get("selectedCandidate") if isinstance(trace.get("selectedCandidate"), dict) else {}
        requested_scope = trace.get("requestedScope") if isinstance(trace.get("requestedScope"), dict) else {}
        intent_profile = str(detail.get("intentProfile") or "client_overview")
        page_key = page_bucket_map.get(intent_profile, intent_profile)
        page_counts.setdefault(page_key, {"total": 0, "newHits": 0, "fallbackHits": 0, "mismatchGroups": 0})
        page_counts[page_key]["total"] = int(page_counts[page_key]["total"]) + 1
        total += 1
        fallback_used = bool(trace.get("fallbackUsed"))
        origin_type = str(selected.get("originType") or trace.get("originType") or "")
        if fallback_used:
            fallback_hits += 1
            page_counts[page_key]["fallbackHits"] = int(page_counts[page_key]["fallbackHits"]) + 1
        elif origin_type and origin_type != "projection":
            new_object_hits += 1
            page_counts[page_key]["newHits"] = int(page_counts[page_key]["newHits"]) + 1
        selected_object_id = str(
            selected.get("objectId")
            or trace.get("objectId")
            or detail.get("judgmentVersionId")
            or ""
        )
        requested_scope_type = str(
            requested_scope.get("scopeType")
            or trace.get("requestedScopeType")
            or "client"
        )
        requested_scope_id = str(
            requested_scope.get("scopeId")
            or trace.get("requestedScopeId")
            or row["client_id"]
            or ""
        )
        source_snapshot_hash = str(detail.get("sourceSnapshotHash") or "")
        if selected_object_id:
            resolver_groups.setdefault(
                (str(row["client_id"]), requested_scope_type, requested_scope_id, intent_profile, source_snapshot_hash),
                set(),
            ).add(selected_object_id)

    canary_exclusion_ids = _build_canary_exclusion_scope(db)
    target_type_to_table = {
        "judgment_version": "judgment_versions",
        "dna_delta": "dna_deltas",
        "conflict_group": "conflict_groups",
    }

    approval_rows = db.fetchall(
        """
        SELECT approval_target_type, approval_target_id, decision, decided_at
        FROM approval_records
        WHERE decided_at >= ?
        ORDER BY decided_at DESC
        """,
        (cutoff,),
    )
    approval_lags: list[float] = []
    for row in approval_rows:
        target_type = str(row["approval_target_type"] or "")
        target_id = str(row["approval_target_id"] or "")
        decided_at = _parse_dt(str(row["decided_at"] or ""))
        if not target_type or not target_id or decided_at is None:
            continue
        table_name = target_type_to_table.get(target_type)
        if not table_name:
            continue
        if target_id in canary_exclusion_ids.get(table_name, set()):
            continue
        target_row = db.fetchone(f"SELECT created_at FROM {table_name} WHERE id = ?", (target_id,))
        created_at = _parse_dt(str(target_row["created_at"] or "")) if target_row else None
        if created_at is None:
            continue
        approval_lags.append(max((decided_at - created_at).total_seconds() / 3600.0, 0.0))
    approval_lags.sort()
    median_approval_lag = approval_lags[len(approval_lags) // 2] if approval_lags else 0.0
    approval_backlog_queries = (
        (
            "judgment_versions",
            "status",
        ),
        (
            "dna_deltas",
            "status",
        ),
        (
            "conflict_groups",
            "resolution_status",
        ),
    )
    approval_backlog = 0
    for table_name, status_column in approval_backlog_queries:
        rows = db.fetchall(
            f"""
            SELECT id
            FROM {table_name}
            WHERE {status_column} IN ('awaiting_review', 'awaiting_revision')
            """
        )
        excluded_for_table = canary_exclusion_ids.get(table_name, set())
        approval_backlog += sum(1 for row in rows if str(row["id"] or "") not in excluded_for_table)
    candidate_review_sla = get_candidate_review_sla_summary(db)

    candidate_total = db.scalar(
        "SELECT COUNT(*) AS count FROM judgment_versions WHERE authority_level = 'candidate' AND created_at >= ?",
        (cutoff,),
    )
    approved_total = db.scalar(
        "SELECT COUNT(*) AS count FROM judgment_versions WHERE authority_level = 'approved' AND updated_at >= ?",
        (cutoff,),
    )
    stale_approved_count = db.scalar(
        "SELECT COUNT(*) AS count FROM judgment_versions WHERE authority_level = 'approved' AND COALESCE(invalidated_by, '') != ''",
    )
    mismatch_count_by_page: dict[str, int] = defaultdict(int)
    for (_, _, _, intent_profile, _), selected_ids in resolver_groups.items():
        if len(selected_ids) > 1:
            mismatch_count_by_page[page_bucket_map.get(intent_profile, intent_profile)] += 1
    resolver_mismatch_groups = sum(1 for selected_ids in resolver_groups.values() if len(selected_ids) > 1)
    resolver_mismatch_rate = (resolver_mismatch_groups / len(resolver_groups)) if resolver_groups else 0.0
    page_breakdown: dict[str, dict[str, float | int]] = {}
    for page_key, bucket in page_counts.items():
        bucket_total = int(bucket["total"])
        mismatch_groups = mismatch_count_by_page.get(page_key, 0)
        page_breakdown[page_key] = {
            "newObjectHitRate": round((int(bucket["newHits"]) / bucket_total) if bucket_total else 0.0, 4),
            "fallbackRate": round((int(bucket["fallbackHits"]) / bucket_total) if bucket_total else 0.0, 4),
            "resolverMismatchRate": round((mismatch_groups / bucket_total) if bucket_total else 0.0, 4),
            "totalRuns": bucket_total,
        }
    return AnalysisMigrationMetricsRecord(
        windowDays=window_days,
        newObjectHitRate=round((new_object_hits / total) if total else 0.0, 4),
        fallbackRate=round((fallback_hits / total) if total else 0.0, 4),
        approvalBacklog=approval_backlog,
        approvalLagHoursMedian=round(median_approval_lag, 2),
        candidateReviewWarningCount=int(candidate_review_sla["warningCount"]),
        candidateReviewOverdueCount=int(candidate_review_sla["overdueCount"]),
        newCandidateUnreviewed24h=int(candidate_review_sla["newUnreviewed24hCount"]),
        candidateToApprovedConversionRate=round((approved_total / candidate_total) if candidate_total else 0.0, 4),
        staleApprovedJudgmentCount=stale_approved_count,
        resolverMismatchRate=round(resolver_mismatch_rate, 4),
        pageBreakdown=page_breakdown,
    )
