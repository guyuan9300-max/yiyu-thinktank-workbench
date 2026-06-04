"""FactExtractRunner — 深读 worker 的"事实抽取"阶段(meeting-spine ② 基石)。

把已入库的 v2_document 交给 DocumentLLMExtractor 抽 atomic_facts。因为走的是
IngestPipeline.ingest, 所以:
  - Phase0 的 speaker 解析钩子(speaker_person_id → speaker_entity_id)在此通电;
  - Phase1③ 的客户名册注入(extract prompt)在此通电。
产出 atomic_facts 后, IngestPipeline 末尾的 _v25_maybe_derive 自动派生
commitments / event_line_activities → /next-steps reconcile → 优化下一步, 整链闭合。

task.payload_json: {"source_v2_document_id": "...", "source_client_id": "..."}
成功 return result dict(写入 local_model_tasks.result_json);失败抛异常, 外层
local_model_optimizer 负责 mark_failed + 按 attempts/max_attempts 重试。
幂等: 由入队层 UNIQUE(task_type, knowledge_document_id, input_hash) 保证。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.db import Database

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_payload(task: dict[str, object]) -> dict[str, Any]:
    raw = task.get("payload_json") or "{}"
    try:
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        payload = {}
    return payload if isinstance(payload, dict) else {}


def process(db: Database, ai_service: Any, task: dict[str, object]) -> dict[str, object]:
    """供 local_model_optimizer worker dispatch 调用。

    成功返回 result_json dict;失败抛异常(外层 mark_failed + 重试计数)。
    """
    payload = _parse_payload(task)
    v2_document_id = str(
        payload.get("source_v2_document_id") or task.get("knowledge_document_id") or ""
    ).strip()
    client_id = str(payload.get("source_client_id") or task.get("client_id") or "").strip()
    if not v2_document_id:
        raise RuntimeError("fact_extract_runner: payload 缺 source_v2_document_id")

    # 延迟 import 避免循环依赖(document_llm_extractor → ingest_pipeline 链较重)
    from app.services.document_llm_extractor import DocumentLLMExtractor

    extractor = DocumentLLMExtractor(db, ai_service)
    ai_session_id = f"deepread_fact_{uuid4().hex[:10]}"
    result = extractor.extract_from_document(
        v2_document_id=v2_document_id,
        ai_session_id=ai_session_id,
        actor_id="deep_read_worker",
        client_id_override=client_id or None,
    )

    return {
        "v2DocumentId": v2_document_id,
        "clientId": client_id,
        "factsWritten": result.facts_written,
        "factsSkippedDuplicate": result.facts_skipped_duplicate,
        "factsSkippedGeneral": result.facts_skipped_general,
        "factsFailed": result.facts_failed,
        "updateRelations": result.update_relations,
        "layerCoverage": result.layer_coverage,
        "extractionSummary": result.extraction_summary,
        "errors": result.errors[:5],
        "ranAt": _now_iso(),
    }


__all__ = ["process"]
