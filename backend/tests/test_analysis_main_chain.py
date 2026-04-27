from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.db import Database
from app.main import create_app
from app.models import AiStructuredResponse, AnalysisJobCreatePayload, JudgmentVersionRecord
from app.services.analysis_center import (
    _list_evidence_ids_by_scope,
    claim_next_analysis_job,
    create_analysis_job,
    get_analysis_job,
    resolve_best_judgment,
)


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "主链收口测试客户") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "用于主链 contract 测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def wait_for_knowledge_ready(client: TestClient, client_id: str, *, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/knowledge/status")
        assert response.status_code == 200, response.text
        payload = response.json()
        last_payload = payload
        if payload["pendingJobs"] == 0 and payload["runningJobs"] == 0 and payload["lastJobStatus"] not in {"queued", "running"}:
            return payload
        time.sleep(0.1)
    return last_payload


def wait_for_analysis_job_terminal(client: TestClient, job_id: str, *, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/analysis/jobs/{job_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        last_payload = payload
        if payload["status"] not in {"queued", "running"}:
            return payload
        time.sleep(0.1)
    return last_payload


def test_database_failed_write_rolls_back_before_next_transaction(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute("CREATE TABLE db_rollback_guard(id TEXT PRIMARY KEY, value TEXT NOT NULL)")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO db_rollback_guard(id, value) VALUES(?, ?)",
            ("broken", None),
        )

    inserted = db.run_in_transaction(
        lambda conn: conn.execute(
            "INSERT INTO db_rollback_guard(id, value) VALUES(?, ?)",
            ("ok", "ready"),
        ).rowcount
    )
    assert inserted == 1
    assert db.scalar("SELECT COUNT(1) AS count FROM db_rollback_guard") == 1


def test_workspace_tolerates_legacy_partial_chat_message_status(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="聊天兼容测试客户")
    created_at = "2026-04-18T09:00:00"
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO chat_threads(id, client_id, title, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        ("thread_partial_status", client_id, "旧消息线程", created_at, created_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, status, llm_invoked, provider_used, answer_mode,
            evidence_status, failure_reason, timing_json, retrieval_summary_json, structured_data_json,
            evidence_json, created_at
        ) VALUES(?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, '{}', '{}', NULL, '[]', ?)
        """,
        ("msg_user_partial_status", "thread_partial_status", "user", "最近有什么变化？", "success", created_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, status, llm_invoked, provider_used, answer_mode,
            evidence_status, failure_reason, timing_json, retrieval_summary_json, structured_data_json,
            evidence_json, created_at
        ) VALUES(?, ?, ?, ?, ?, 1, 'analysis-center', 'grounded_fallback', 'partial', NULL, '{}', '{}', NULL, '[]', ?)
        """,
        (
            "msg_assistant_partial_status",
            "thread_partial_status",
            "assistant",
            "正式成文阶段没有完整完成，但当前先保留一版可读结果。",
            "partial",
            created_at,
        ),
    )

    response = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert response.status_code == 200, response.text
    messages = response.json()["recentMessages"]
    assistant_message = next(item for item in messages if item["id"] == "msg_assistant_partial_status")
    assert assistant_message["status"] == "success"
    client.__exit__(None, None, None)


def insert_judgment(
    client: TestClient,
    *,
    judgment_id: str,
    client_id: str,
    target_type: str,
    target_id: str,
    topic: str,
    summary: str,
    authority_level: str,
    status: str,
    created_at: str,
    updated_at: str,
    context_pack_id: str | None = None,
    invalidated_by: str | None = None,
    stale_reason: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence,
            created_at, updated_at, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by
        )
        VALUES(?, ?, ?, ?, ?, 1, ?, ?, '[]', ?, 'medium', 'medium', ?, ?, 'analysis', ?, 'reviewed', NULL, '', ?, ?)
        """,
        (
            judgment_id,
            client_id,
            target_type,
            target_id,
            topic,
            status,
            summary,
            context_pack_id,
            created_at,
            updated_at,
            authority_level,
            stale_reason,
            invalidated_by,
        ),
    )


def insert_evidence_card(
    client: TestClient,
    *,
    evidence_id: str,
    client_id: str,
    source_id: str,
    source_ref: str,
    source_ref_hash: str,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO evidence_cards(
            id, client_id, scope_type, scope_id, origin_type, authority_level, quality_tier,
            source_type, source_id, source_ref, quote, normalized_claim, evidence_type, polarity,
            tags_json, topic_keys_json, confidence, time_anchor, document_id, event_line_id, task_id,
            meeting_id, module_id, flow_id, review_state, fingerprint, normalized_claim_hash,
            source_ref_hash, evidence_fingerprint, normalizer_version, created_at, updated_at
        )
        VALUES(
            ?, ?, 'client', ?, 'analysis', 'candidate', 'normalized',
            'document_card', ?, ?, '同一条证据', '同一条证据', 'finding', 'neutral',
            '[]', '[]', 0.7, NULL, NULL, NULL, NULL,
            NULL, NULL, NULL, 'awaiting_review', ?, 'claim_hash_shared',
            ?, 'fingerprint_shared', 'analysis-center-v0.3.3', '2026-04-15T08:00:00', '2026-04-15T08:00:00'
        )
        """,
        (
            evidence_id,
            client_id,
            client_id,
            source_id,
            source_ref,
            f"row::{evidence_id}",
            source_ref_hash,
        ),
    )


def insert_dna_delta(
    client: TestClient,
    *,
    delta_id: str,
    client_id: str,
    status: str,
    created_at: str,
    context_pack_id: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO dna_deltas(
            id, client_id, dimension, previous_version, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by, proposed_change, summary,
            evidence_ids_json, confidence, status, context_pack_id, created_at, updated_at
        )
        VALUES(
            ?, ?, 'organization_context', NULL, 'analysis', 'candidate', 'normalized',
            NULL, 'snapshot_sla', NULL, NULL, '补齐项目底稿', '用于 SLA 统计',
            '[]', 'medium', ?, ?, ?, ?
        )
        """,
        (delta_id, client_id, status, context_pack_id, created_at, created_at),
    )


def insert_conflict_group(
    client: TestClient,
    *,
    conflict_id: str,
    client_id: str,
    status: str,
    created_at: str,
    context_pack_id: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO conflict_groups(
            id, client_id, scope_type, scope_id, origin_type, authority_level, quality_tier,
            conflict_type, title, summary, evidence_ids_json, unresolved_question_ids_json,
            resolution_status, severity, context_pack_id, created_at, updated_at
        )
        VALUES(
            ?, ?, 'client', ?, 'analysis', 'candidate', 'normalized',
            'evidence_mismatch', '证据冲突', '用于 SLA 统计', '[]', '[]',
            ?, 'medium', ?, ?, ?
        )
        """,
        (conflict_id, client_id, client_id, status, context_pack_id, created_at, created_at),
    )


def insert_analysis_job(
    client: TestClient,
    *,
    job_id: str,
    client_id: str,
    feature_flags: dict[str, bool],
    created_at: str,
    status: str = "completed",
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO analysis_jobs(
            id, job_type, client_id, scope_type, scope_id, status, priority, trigger_type,
            intent_profile, question, source_snapshot, source_snapshot_hash, dedupe_key,
            feature_flags_json, progress, attempt_count, created_at, updated_at
        )
        VALUES(
            ?, 'strategy_pack', ?, 'client', ?, ?, 'normal', 'manual',
            'client_overview', 'test analysis job', '', '', ?, ?, 1.0, 0, ?, ?
        )
        """,
        (
            job_id,
            client_id,
            client_id,
            status,
            f"dedupe::{job_id}",
            json.dumps(feature_flags, ensure_ascii=False),
            created_at,
            created_at,
        ),
    )


def insert_context_pack(
    client: TestClient,
    *,
    context_pack_id: str,
    client_id: str,
    job_id: str | None,
    created_at: str,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO context_packs(
            id, client_id, job_id, target_type, target_id, created_at, updated_at
        )
        VALUES(?, ?, ?, 'client', ?, ?, ?)
        """,
        (context_pack_id, client_id, job_id, client_id, created_at, created_at),
    )


def insert_approval_record(
    client: TestClient,
    *,
    approval_id: str,
    client_id: str,
    target_type: str,
    target_id: str,
    created_at: str,
    decided_at: str,
    decision: str = "approved",
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO approval_records(
            id, object_type, object_id, client_id, status, note, actor_id, actor_name,
            created_at, approval_target_type, approval_target_id, policy_type, decision,
            comment, decided_by, decided_at, metadata_json
        )
        VALUES(
            ?, ?, ?, ?, ?, '', 'reviewer_demo', 'Reviewer Demo',
            ?, ?, ?, 'analysis_review', ?, '', 'reviewer_demo', ?, '{}'
        )
        """,
        (
            approval_id,
            target_type,
            target_id,
            client_id,
            decision,
            created_at,
            target_type,
            target_id,
            decision,
            decided_at,
        ),
    )


def insert_runtime_run_log(
    client: TestClient,
    *,
    run_id: str,
    client_id: str,
    intent_profile: str,
    selected_object_id: str,
    source_snapshot_hash: str = "snapshot_same",
    summary: str = "resolver metrics seed",
    detail: dict[str, object] | None = None,
    created_at: str = "2026-04-15T09:00:00",
) -> None:
    if detail is None:
        detail = {
            "intentProfile": intent_profile,
            "sourceSnapshotHash": source_snapshot_hash,
            "resolutionTrace": {
                "selectedCandidate": {
                    "objectId": selected_object_id,
                    "scopeType": "client",
                    "scopeId": client_id,
                    "originType": "analysis",
                    "authorityLevel": "candidate",
                    "qualityTier": "normalized",
                },
                "requestedScope": {"scopeType": "client", "scopeId": client_id},
                "resolvedScope": {"scopeType": "client", "scopeId": client_id},
                "writebackScope": {"scopeType": "client", "scopeId": client_id},
                "fallbackUsed": False,
                "consideredCandidates": [],
            },
        }
    client.app.state.app_state.db.execute(
        """
        INSERT INTO runtime_run_logs(
            id, client_id, job_id, provider, model, lane, cache_hit, degraded, document_count, evidence_count,
            conflict_count, context_time_range, prompt_version, schema_version, summary, detail_json, created_at
        )
        VALUES(?, ?, NULL, 'analysis-center', 'analysis-center-v0.3.3', 'cloud_final', 0, 0, 0, 0, 0, NULL, 'analysis-center-v0.3.3', 'analysis-center-v0.3.3', ?, ?, ?)
        """,
        (run_id, client_id, summary, json.dumps(detail, ensure_ascii=False), created_at),
    )


def test_workspace_bundle_returns_client_baseline_plus_overlay(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="客户总览 bundle 测试")

    module_response = client.post(
        f"/api/v1/clients/{client_id}/project-modules",
        json={
            "name": "筹资模块",
            "alias": "",
            "goal": "稳定筹资主线",
            "description": "负责筹资节奏和材料沉淀。",
            "ownerName": "庆华",
            "deliverables": [],
            "keywords": [],
        },
    )
    assert module_response.status_code == 200, module_response.text
    module_id = module_response.json()["id"]

    insert_judgment(
        client,
        judgment_id="judgment_client_baseline",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="客户总体判断",
        summary="这是客户级 approved baseline。",
        authority_level="approved",
        status="approved",
        created_at="2026-04-15T08:00:00",
        updated_at="2026-04-15T08:00:00",
    )
    insert_judgment(
        client,
        judgment_id="judgment_module_overlay",
        client_id=client_id,
        target_type="module",
        target_id=module_id,
        topic="模块变化",
        summary="这是模块级 candidate overlay。",
        authority_level="candidate",
        status="awaiting_review",
        created_at="2026-04-15T08:10:00",
        updated_at="2026-04-15T08:10:00",
    )

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()

    assert payload["judgmentBundle"]["baselineJudgment"]["id"] == "judgment_client_baseline"
    assert [item["id"] for item in payload["judgmentBundle"]["overlayDeltas"]] == ["judgment_module_overlay"]
    assert payload["latestResolutionTrace"]["selectedCandidate"]["objectId"] == "judgment_client_baseline"
    assert payload["latestResolutionTrace"]["writebackScope"] == {"scopeType": "client", "scopeId": client_id}


def test_resolver_trace_uses_fixed_rejected_reason_enums_and_never_upgrades_writeback_scope(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="resolver trace 枚举测试")
    module_id = "module_scope_1"

    insert_judgment(
        client,
        judgment_id="judgment_client_selected",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="经营主判断",
        summary="客户级正式判断。",
        authority_level="approved",
        status="approved",
        created_at="2026-04-15T08:00:00",
        updated_at="2026-04-15T08:00:00",
    )
    insert_judgment(
        client,
        judgment_id="judgment_client_stale",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="经营主判断",
        summary="旧判断已过期。",
        authority_level="candidate",
        status="awaiting_review",
        created_at="2026-04-14T08:00:00",
        updated_at="2026-04-14T08:00:00",
        invalidated_by="judgment_client_selected",
        stale_reason="superseded_by_newer_judgment",
    )
    insert_judgment(
        client,
        judgment_id="judgment_module_candidate",
        client_id=client_id,
        target_type="module",
        target_id=module_id,
        topic="经营主判断",
        summary="模块级候选判断。",
        authority_level="candidate",
        status="awaiting_review",
        created_at="2026-04-15T08:05:00",
        updated_at="2026-04-15T08:05:00",
    )

    selected, trace = resolve_best_judgment(
        client.app.state.app_state.db,
        client_id=client_id,
        requested_scope_type="event_line",
        requested_scope_id="event_line_1",
        intent_profile="task_ai",
        related_refs={"module": [module_id]},
        topic="经营主判断",
        minimum_authority="fallback",
        include_fallback=True,
    )

    assert selected is not None
    assert selected.id == "judgment_module_candidate"
    assert trace.writebackScope is not None
    assert trace.writebackScope.model_dump(mode="json") == {"scopeType": "event_line", "scopeId": "event_line_1"}
    reasons = {item.rejectedReason for item in trace.consideredCandidates if item.rejectedReason}
    assert reasons <= {
        "authority_too_low",
        "scope_less_relevant",
        "stale",
        "superseded",
        "insufficient_evidence",
        "not_approved_for_official_use",
    }
    assert "superseded" in reasons


def test_evidence_storage_rows_and_cluster_dedupe_keys_are_separate(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="evidence 去重测试")

    insert_evidence_card(
        client,
        evidence_id="evidence_source_a",
        client_id=client_id,
        source_id="doc_a",
        source_ref="来源 A",
        source_ref_hash="source_ref_hash_a",
    )
    insert_evidence_card(
        client,
        evidence_id="evidence_source_b",
        client_id=client_id,
        source_id="doc_b",
        source_ref="来源 B",
        source_ref_hash="source_ref_hash_b",
    )

    raw_ids = _list_evidence_ids_by_scope(client.app.state.app_state.db, client_id, "client", client_id)
    deduped_ids = _list_evidence_ids_by_scope(
        client.app.state.app_state.db,
        client_id,
        "client",
        client_id,
        dedupe_by_cluster_key=True,
    )

    assert len(raw_ids) == 2
    assert set(raw_ids) == {"evidence_source_a", "evidence_source_b"}
    assert len(deduped_ids) == 1
    assert deduped_ids[0] in raw_ids


def test_analysis_worker_prioritizes_interactive_and_throttles_consecutive_backfill(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="worker 节流测试")
    db = client.app.state.app_state.db

    create_analysis_job(
        db,
        AnalysisJobCreatePayload(
            jobType="strategy_pack",
            clientId=client_id,
            scopeType="client",
            scopeId=client_id,
            priority="low",
            triggerType="backfill",
            question="backfill 1",
            intentProfile="client_overview",
        ),
    )
    create_analysis_job(
        db,
        AnalysisJobCreatePayload(
            jobType="strategy_pack",
            clientId=client_id,
            scopeType="client",
            scopeId=client_id,
            priority="high",
            triggerType="manual",
            question="interactive first",
            intentProfile="task_ai",
        ),
    )

    first_job = claim_next_analysis_job(db, "worker-test")
    assert first_job is not None
    assert first_job.triggerType == "manual"
    db.execute("UPDATE analysis_jobs SET status = 'completed' WHERE id = ?", (first_job.id,))

    for index in range(2, 5):
        create_analysis_job(
            db,
            AnalysisJobCreatePayload(
                jobType="strategy_pack",
                clientId=client_id,
                scopeType="client",
                scopeId=client_id,
                priority="low",
                triggerType="backfill",
                question=f"backfill {index}",
                intentProfile="dna_summary" if index == 2 else "strategic_cockpit",
            ),
            source_snapshot={"seed": index, "clientId": client_id},
        )

    second_job = claim_next_analysis_job(db, "worker-test")
    assert second_job is not None
    assert second_job.triggerType == "backfill"
    db.execute("UPDATE analysis_jobs SET status = 'completed' WHERE id = ?", (second_job.id,))

    third_job = claim_next_analysis_job(db, "worker-test")
    assert third_job is not None
    assert third_job.triggerType == "backfill"
    db.execute("UPDATE analysis_jobs SET status = 'completed' WHERE id = ?", (third_job.id,))

    throttled = claim_next_analysis_job(db, "worker-test")
    assert throttled is None

    fourth_job = claim_next_analysis_job(db, "worker-test")
    assert fourth_job is not None
    assert fourth_job.triggerType == "backfill"


def test_cockpit_keeps_official_layer_empty_and_surfaces_review_signals(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="cockpit 官方层测试")

    insert_judgment(
        client,
        judgment_id="judgment_client_candidate",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="候选判断",
        summary="这还是候选，不应进入官方层。",
        authority_level="candidate",
        status="awaiting_review",
        created_at="2026-04-10T08:00:00",
        updated_at="2026-04-10T08:00:00",
    )

    response = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["officialLayerStatus"] == "empty"
    assert payload["officialEmptyReason"] == "当前暂无已批准判断"
    assert payload["officialLayer"]["officialBaseline"] is None
    assert payload["radarLayer"]["candidateJudgments"][0]["id"] == "judgment_client_candidate"
    assert payload["radarLayer"]["reviewSignals"][0]["level"] in {"warning", "overdue"}
    assert payload["headline"]["weekSummary"]["value"] == "当前暂无已批准判断"


def test_analysis_migration_metrics_break_down_intent_profiles(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="迁移指标 intentProfile 测试")

    insert_runtime_run_log(
        client,
        run_id="run_task_ai",
        client_id=client_id,
        intent_profile="task_ai",
        selected_object_id="judgment_task_ai",
    )
    insert_runtime_run_log(
        client,
        run_id="run_dna_summary",
        client_id=client_id,
        intent_profile="dna_summary",
        selected_object_id="judgment_dna_summary",
    )

    response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert "task_ai" in payload["pageBreakdown"]
    assert "dna_summary" in payload["pageBreakdown"]
    assert payload["pageBreakdown"]["task_ai"]["totalRuns"] == 1


def test_analysis_migration_metrics_group_mismatches_by_source_snapshot_hash(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="迁移指标 snapshot 分组测试")

    insert_runtime_run_log(
        client,
        run_id="run_snapshot_a",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_snapshot_a",
        source_snapshot_hash="snapshot_a",
    )
    insert_runtime_run_log(
        client,
        run_id="run_snapshot_b",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_snapshot_b",
        source_snapshot_hash="snapshot_b",
    )

    response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["resolverMismatchRate"] == 0.0
    assert payload["pageBreakdown"]["client_overview"]["resolverMismatchRate"] == 0.0


def test_analysis_migration_metrics_include_candidate_sla_counts(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="迁移指标 SLA 计数测试")
    now = datetime.now().replace(microsecond=0)

    insert_judgment(
        client,
        judgment_id="judgment_warning_only",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="warning_only",
        summary="超过 24h 但未超过 72h。",
        authority_level="candidate",
        status="awaiting_review",
        created_at=(now - timedelta(hours=30)).isoformat(),
        updated_at=(now - timedelta(hours=30)).isoformat(),
    )
    insert_dna_delta(
        client,
        delta_id="dna_overdue",
        client_id=client_id,
        status="awaiting_revision",
        created_at=(now - timedelta(hours=80)).isoformat(),
    )
    insert_conflict_group(
        client,
        conflict_id="conflict_new_24h",
        client_id=client_id,
        status="awaiting_review",
        created_at=(now - timedelta(hours=2)).isoformat(),
    )

    response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["approvalBacklog"] == 3
    assert payload["candidateReviewWarningCount"] == 2
    assert payload["candidateReviewOverdueCount"] == 1
    assert payload["newCandidateUnreviewed24h"] == 1


def test_analysis_migration_metrics_exclude_canary_without_excluding_real_or_legacy_samples(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="迁移指标 canary 排除测试")
    now = datetime.now().replace(microsecond=0)

    real_job_at = (now - timedelta(hours=90)).isoformat()
    insert_analysis_job(
        client,
        job_id="job_real_metrics",
        client_id=client_id,
        feature_flags={},
        created_at=real_job_at,
    )
    insert_context_pack(
        client,
        context_pack_id="ctx_real_metrics",
        client_id=client_id,
        job_id="job_real_metrics",
        created_at=real_job_at,
    )

    canary_job_at = (now - timedelta(hours=96)).isoformat()
    insert_analysis_job(
        client,
        job_id="job_canary_metrics",
        client_id=client_id,
        feature_flags={"main-chain-canary": True},
        created_at=canary_job_at,
    )
    insert_context_pack(
        client,
        context_pack_id="ctx_canary_metrics",
        client_id=client_id,
        job_id="job_canary_metrics",
        created_at=canary_job_at,
    )

    insert_judgment(
        client,
        judgment_id="judgment_real_warning",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="real_warning",
        summary="真实样本，超过 24h。",
        authority_level="candidate",
        status="awaiting_review",
        context_pack_id="ctx_real_metrics",
        created_at=(now - timedelta(hours=30)).isoformat(),
        updated_at=(now - timedelta(hours=30)).isoformat(),
    )
    insert_dna_delta(
        client,
        delta_id="dna_real_overdue",
        client_id=client_id,
        status="awaiting_revision",
        context_pack_id="ctx_real_metrics",
        created_at=(now - timedelta(hours=80)).isoformat(),
    )
    insert_conflict_group(
        client,
        conflict_id="conflict_real_new",
        client_id=client_id,
        status="awaiting_review",
        context_pack_id="ctx_real_metrics",
        created_at=(now - timedelta(hours=2)).isoformat(),
    )
    insert_judgment(
        client,
        judgment_id="judgment_legacy_warning",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="legacy_warning",
        summary="legacy 真实样本，没有 context_pack_id。",
        authority_level="candidate",
        status="awaiting_review",
        created_at=(now - timedelta(hours=50)).isoformat(),
        updated_at=(now - timedelta(hours=50)).isoformat(),
    )

    insert_judgment(
        client,
        judgment_id="judgment_real_approved",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="real_approved",
        summary="真实已审批样本。",
        authority_level="approved",
        status="approved",
        context_pack_id="ctx_real_metrics",
        created_at=(now - timedelta(hours=6)).isoformat(),
        updated_at=now.isoformat(),
    )
    insert_approval_record(
        client,
        approval_id="approval_real_metrics",
        client_id=client_id,
        target_type="judgment_version",
        target_id="judgment_real_approved",
        created_at=now.isoformat(),
        decided_at=now.isoformat(),
    )

    insert_judgment(
        client,
        judgment_id="judgment_canary_warning",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="canary_warning",
        summary="canary 样本，不应计入。",
        authority_level="candidate",
        status="awaiting_review",
        context_pack_id="ctx_canary_metrics",
        created_at=(now - timedelta(hours=90)).isoformat(),
        updated_at=(now - timedelta(hours=90)).isoformat(),
    )
    insert_dna_delta(
        client,
        delta_id="dna_canary_overdue",
        client_id=client_id,
        status="awaiting_revision",
        context_pack_id="ctx_canary_metrics",
        created_at=(now - timedelta(hours=90)).isoformat(),
    )
    insert_conflict_group(
        client,
        conflict_id="conflict_canary_warning",
        client_id=client_id,
        status="awaiting_review",
        context_pack_id="ctx_canary_metrics",
        created_at=(now - timedelta(hours=90)).isoformat(),
    )
    insert_judgment(
        client,
        judgment_id="judgment_canary_approved",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="canary_approved",
        summary="canary 已审批样本，不应影响 lag。",
        authority_level="approved",
        status="approved",
        context_pack_id="ctx_canary_metrics",
        created_at=(now - timedelta(hours=40)).isoformat(),
        updated_at=now.isoformat(),
    )
    insert_approval_record(
        client,
        approval_id="approval_canary_metrics",
        client_id=client_id,
        target_type="judgment_version",
        target_id="judgment_canary_approved",
        created_at=now.isoformat(),
        decided_at=now.isoformat(),
    )

    response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["approvalBacklog"] == 4
    assert payload["approvalLagHoursMedian"] == 6.0
    assert payload["candidateReviewWarningCount"] == 3
    assert payload["candidateReviewOverdueCount"] == 1
    assert payload["newCandidateUnreviewed24h"] == 1


def test_main_chain_backfill_dry_run_returns_candidates_without_queueing_jobs(tmp_path: Path):
    client = make_client(tmp_path)
    client_ids = [
        create_test_client_record(client, name="主链 backfill dry-run 客户 A"),
        create_test_client_record(client, name="主链 backfill dry-run 客户 B"),
    ]

    response = client.post(
        "/api/v1/analysis/backfill-main-chain",
        json={
            "clientIds": client_ids,
            "dryRun": True,
            "batchSize": 2,
            "maxJobs": 4,
            "pauseRequested": False,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["dryRun"] is True
    assert payload["queuedJobs"] == 0
    assert payload["paused"] is False
    assert len(payload["candidates"]) == 2
    assert {item["clientId"] for item in payload["candidates"]}.issubset(set(client_ids))
    assert all(item["triggerType"] == "backfill" for item in payload["candidates"])
    assert client.app.state.app_state.db.scalar("SELECT COUNT(1) AS count FROM analysis_jobs") == 0


def test_latest_judgments_shadow_power_off_keeps_main_chain_contract(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="latestJudgments 影子断电测试")

    insert_judgment(
        client,
        judgment_id="judgment_shadow_off",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="客户总体判断",
        summary="bundle 仍应可读。",
        authority_level="approved",
        status="approved",
        created_at="2026-04-15T08:00:00",
        updated_at="2026-04-15T08:00:00",
    )

    update_settings = client.post(
        "/api/v1/settings/main-chain-stability",
        json={"latestJudgmentsShadowOff": True},
    )
    assert update_settings.status_code == 200, update_settings.text
    assert update_settings.json()["latestJudgmentsShadowOff"] is True

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()

    assert payload["judgmentBundle"]["baselineJudgment"]["id"] == "judgment_shadow_off"
    assert payload["latestResolutionTrace"]["selectedCandidate"]["objectId"] == "judgment_shadow_off"
    assert payload["latestJudgments"] == []


def test_main_chain_stability_settings_accept_fixed_canary_observation_fields(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/v1/settings/main-chain-stability",
        json={
            "latestJudgmentsShadowOff": True,
            "lastCanaryObservation": {
                "timeRange": "2026-04-15 / Wave 1",
                "clientCount": 2,
                "enqueuedJobs": 2,
                "completedJobs": 2,
                "failedJobs": 0,
                "newObjectHitRateBefore": 0.6,
                "newObjectHitRateAfter": 0.8,
                "fallbackRateBefore": 0.3,
                "fallbackRateAfter": 0.1,
                "resolverMismatchRateBefore": 0.2,
                "resolverMismatchRateAfter": 0.0,
                "approvalBacklog": 1,
                "approvalLagHoursMedian": 8.5,
                "claimCounts": {"backfill": 2},
                "lockContention": {"backfill": 0},
                "backfillThrottle": {"backfill": 1},
                "impactedRealtimeTasks": False,
                "latestJudgmentsShadowOff": True,
                "verdict": "pass",
                "conclusion": "Wave 1 通过。",
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["latestJudgmentsShadowOff"] is True
    assert payload["lastCanaryObservation"]["newObjectHitRateBefore"] == 0.6
    assert payload["lastCanaryObservation"]["newObjectHitRateAfter"] == 0.8
    assert payload["lastCanaryObservation"]["latestJudgmentsShadowOff"] is True
    assert payload["lastCanaryObservation"]["verdict"] == "pass"


def test_main_chain_projection_is_idempotent_for_same_source_snapshot(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="主链幂等性测试")
    source = tmp_path / "analysis-idempotent-source"
    source.mkdir()
    (source / "项目总览.md").write_text(
        "# 项目总览\n"
        "该客户当前围绕公益机构战略陪伴、会议复盘与知识底盘建设推进统一上下文。\n"
        "本轮目标是把已有材料沉淀为稳定 judgment bundle，而不是重复膨胀对象。\n",
        encoding="utf-8",
    )

    def stable_generate_structured(prompt: str, system_instruction: str, context_summary: str) -> AiStructuredResponse:
        return AiStructuredResponse(
            content="## 1. 当前重点\n统一客户上下文。\n\n## 2. 推进建议\n围绕主问题形成稳定 judgment。",
            judgment="当前重点是把已有资料沉淀成统一上下文，并形成稳定的客户级判断。",
            analysis="仍缺阶段目标\n仍缺更多案例",
            actions="项目总览.md",
            timeline="补齐案例后再继续迭代。",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_structured", stable_generate_structured)

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "folder", "paths": [str(source)]},
    )
    assert imported.status_code == 200, imported.text
    status = wait_for_knowledge_ready(client, client_id)
    assert status["lastJobStatus"] == "completed"

    def run_analysis_job() -> dict:
        job_response = client.post(
            "/api/v1/analysis/jobs",
            json={
                "jobType": "strategy_pack",
                "clientId": client_id,
                "scopeType": "client",
                "scopeId": client_id,
                "priority": "normal",
                "triggerType": "manual",
                "question": "主链幂等性 gate",
                "sourceScope": {},
                "featureFlags": {},
                "intentProfile": "client_overview",
            },
        )
        assert job_response.status_code == 200, job_response.text
        payload = wait_for_analysis_job_terminal(client, job_response.json()["id"])
        assert payload["status"] == "completed", payload
        workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
        assert workspace.status_code == 200, workspace.text
        return workspace.json()

    first_workspace = run_analysis_job()
    second_workspace = run_analysis_job()
    metrics_response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert metrics_response.status_code == 200, metrics_response.text
    metrics_payload = metrics_response.json()

    for count_key in ("evidenceCardCount", "themeClusterCount", "conflictGroupCount", "openQuestionCount"):
        assert first_workspace["analysisCenter"][count_key] == second_workspace["analysisCenter"][count_key]
    assert first_workspace["judgmentBundle"]["baselineJudgment"]["id"] == second_workspace["judgmentBundle"]["baselineJudgment"]["id"]
    assert first_workspace["latestResolutionTrace"]["selectedCandidate"]["objectId"] == second_workspace["latestResolutionTrace"]["selectedCandidate"]["objectId"]
    assert metrics_payload["resolverMismatchRate"] == 0.0
    assert metrics_payload["pageBreakdown"]["client_overview"]["resolverMismatchRate"] == 0.0


def test_workspace_state_projection_handles_runtime_run_log_variants(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="运行日志兼容测试")

    insert_runtime_run_log(
        client,
        run_id="runlog_variant_new",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_variant_new",
        summary="客户状态分析已完成",
        detail={
            "intentProfile": "client_overview",
            "latestRunSummary": "本周重点已经从资料整理切到 judgment 收口。",
            "outputSummary": "outputSummary 不应覆盖 latestRunSummary。",
        },
    )
    insert_runtime_run_log(
        client,
        run_id="runlog_variant_old",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_variant_old",
        summary="旧版运行摘要仍应兼容",
        detail={"phase": "completed"},
        created_at="2026-04-15T09:10:00",
    )
    insert_runtime_run_log(
        client,
        run_id="runlog_variant_minimal",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_variant_minimal",
        summary="",
        detail={},
        created_at="2026-04-15T09:20:00",
    )

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()

    projection = payload["stateProjection"]
    run_log_items = [item for item in projection["progressItems"] if item["sourceType"] == "run_log"]
    assert any("本周重点已经从资料整理切到 judgment 收口" in item["summary"] for item in run_log_items)
    assert any(item["summary"] == "旧版运行摘要仍应兼容" for item in run_log_items)
    assert all(item["sourceId"] != "runlog_variant_minimal" for item in run_log_items)
    assert projection["boundaryNotes"]


def test_workspace_state_projection_does_not_fallback_to_latest_judgments_when_bundle_missing(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="compat judgment 回流测试")
    insert_judgment(
        client,
        judgment_id="judgment_bundle_only",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="bundle 正式判断",
        summary="正式判断只能来自 judgment bundle。",
        authority_level="approved",
        status="approved",
        created_at="2026-04-15T10:00:00",
        updated_at="2026-04-15T10:00:00",
    )

    real_get_bundle = app_main.get_client_analysis_bundle
    compat_judgment = JudgmentVersionRecord(
        id="judgment_compat_only",
        clientId=client_id,
        targetType="client",
        targetId=client_id,
        topic="compat judgment",
        status="approved",
        originType="analysis",
        authorityLevel="approved",
        qualityTier="reviewed",
        summary="这条 compat judgment 不能回流进正式判断。",
        createdAt="2026-04-15T10:05:00",
        updatedAt="2026-04-15T10:05:00",
    )

    def fake_get_bundle(db, workspace_seed):
        bundle = real_get_bundle(db, workspace_seed)
        bundle.judgment_bundle = None
        bundle.latest_judgments = [compat_judgment]
        return bundle

    monkeypatch.setattr(app_main, "get_client_analysis_bundle", fake_get_bundle)

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()

    assert payload["latestJudgments"][0]["id"] == "judgment_compat_only"
    judgment_items = [item for item in payload["stateProjection"]["changeItems"] if item["sourceType"] == "judgment"]
    assert judgment_items == []
    assert any("当前还没有足够稳定的正式判断" in note for note in payload["stateProjection"]["boundaryNotes"])


def test_event_line_evidence_count_defaults_to_zero_and_accepts_null_patch(tmp_path: Path):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "证据计数默认值测试",
            "kind": "custom",
            "status": "active",
            "visibilityScope": "project_public",
            "businessCategory": "增长",
            "stage": "推进中",
            "summary": "验证 evidence_count 兜底",
            "evidenceCount": None,
            "participantIds": [],
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["evidenceCount"] == 0

    updated = client.patch(
        f"/api/v1/event-lines/{payload['id']}",
        json={"evidenceCount": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["evidenceCount"] == 0


def test_analysis_job_projection_handles_event_line_tasks_and_legacy_structured_summary(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="阶段 A 运行验证客户")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "主链接管验证事件线",
            "kind": "project_line",
            "status": "active",
            "summary": "用于验证 analysis_center 主链执行。",
            "intent": "检查事件线 judgment 与 legacy analysis run 兼容。",
            "nextStep": "重跑 client_overview job。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "主链接管验证任务",
            "desc": "验证事件线 judgment 同步不会因为裸变量报错。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text

    db = client.app.state.app_state.db
    created_at = "2026-04-15T15:00:00"
    db.execute(
        """
        INSERT INTO chat_threads(id, client_id, title, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        ("thread_main_chain", client_id, "主链接管验证线程", created_at, created_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, status, llm_invoked, provider_used, answer_mode,
            evidence_status, failure_reason, timing_json, retrieval_summary_json, structured_data_json,
            evidence_json, created_at
        ) VALUES(?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, '{}', '{}', NULL, '[]', ?)
        """,
        ("msg_user_main_chain", "thread_main_chain", "user", "介绍当前客户情况", "success", created_at),
    )
    structured_summary = AiStructuredResponse(
        content="这是历史分析输出。",
        judgment="需要继续跟进事件线动作。",
        analysis="当前判断仍需补齐客户级正式确认。",
        actions="先完成一轮 client_overview 判断。",
        timeline="本周内完成。",
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, status, llm_invoked, provider_used, answer_mode,
            evidence_status, failure_reason, timing_json, retrieval_summary_json, structured_data_json,
            evidence_json, created_at
        ) VALUES(?, ?, ?, ?, ?, 1, 'analysis-center', 'grounded_answer', 'sufficient', NULL, '{}', '{}', ?, '[]', ?)
        """,
        (
            "msg_assistant_main_chain",
            "thread_main_chain",
            "assistant",
            "这是历史分析输出。",
            "success",
            json.dumps(structured_summary.model_dump(), ensure_ascii=False),
            created_at,
        ),
    )
    db.execute(
        """
        INSERT INTO client_analysis_runs(
            id, client_id, thread_id, user_message_id, assistant_message_id, question,
            status, phase, progress, progress_floor, progress_ceiling, stage_label, elapsed_ms,
            evidence_summary_json, long_answer, structured_summary_json, long_answer_status,
            summary_status, answer_mode, llm_invoked, provider_used, failure_reason, timing_json,
            created_at, updated_at
        ) VALUES(
            ?, ?, ?, ?, ?, ?, 'completed', 'completed', 100, 0, 100, '已完成', 1200,
            '{"masterHitCount": 1, "surrogateHitCount": 0, "evidenceList": []}',
            '这是历史分析输出。',
            ?, 'ready', 'ready', 'grounded_answer', 1, 'analysis-center', NULL, '{"totalMs": 1200}',
            ?, ?
        )
        """,
        (
            "legacy_run_main_chain",
            client_id,
            "thread_main_chain",
            "msg_user_main_chain",
            "msg_assistant_main_chain",
            "介绍当前客户情况",
            json.dumps(structured_summary.model_dump(), ensure_ascii=False),
            created_at,
            created_at,
        ),
    )

    payload = AnalysisJobCreatePayload(
        jobType="strategy_pack",
        clientId=client_id,
        scopeType="client",
        scopeId=client_id,
        priority="normal",
        triggerType="manual",
        question="main-chain regression",
        intentProfile="client_overview",
    )
    job = create_analysis_job(
        db,
        payload,
        source_snapshot={
            "clientId": client_id,
            "scopeType": "client",
            "scopeId": client_id,
            "question": "main-chain regression",
        },
    )

    terminal = wait_for_analysis_job_terminal(client, job.id)
    assert terminal["status"] == "completed"

    persisted = get_analysis_job(db, job.id)
    assert persisted is not None
    assert persisted.status == "completed"
    assert persisted.lastError is None

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    assert workspace_payload["judgmentBundle"]["baselineJudgment"]["id"]
    assert workspace_payload["latestResolutionTrace"]["selectedCandidate"]["objectId"]


def test_projection_helper_is_not_imported_by_main_chain_routes():
    app_root = Path(app_main.__file__).resolve().parent
    hits = []
    for path in app_root.rglob("*.py"):
        if "refresh_client_analysis_projection(" not in path.read_text(encoding="utf-8"):
            continue
        hits.append(path.name)
    assert hits == ["analysis_center.py"]


def test_main_chain_consumers_do_not_use_latest_judgments_as_formal_source():
    repo_root = Path(app_main.__file__).resolve().parents[2]
    allowed_hits = {
        "backend/app/main.py": {"latestJudgments="},
        "backend/app/models.py": {"latestJudgments:"},
        "src/shared/types.ts": {"latestJudgments:"},
        "src/renderer/App.tsx": {
            "latestJudgmentsShadowOff",
            "latestJudgments 兼容输出",
            "影子断电 latestJudgments",
            "恢复 latestJudgments",
            "已关闭 latestJudgments 兼容输出",
            "已恢复 latestJudgments 兼容输出",
            "切换 latestJudgments 影子断电失败",
        },
    }
    pattern = re.compile(r"\blatestJudgments\b")
    disallowed_hits: list[str] = []
    for base in (repo_root / "backend" / "app", repo_root / "src"):
        for path in base.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx"}:
                continue
            relative = str(path.relative_to(repo_root))
            text = path.read_text(encoding="utf-8")
            if not pattern.search(text):
                continue
            allowed_markers = allowed_hits.get(relative, set())
            filtered_lines = [
                line.strip()
                for line in text.splitlines()
                if pattern.search(line) and not any(marker in line for marker in allowed_markers)
            ]
            if filtered_lines:
                disallowed_hits.append(f"{relative}: {' | '.join(filtered_lines[:3])}")
    assert disallowed_hits == []
