from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse, JudgmentVersionRecord
from app.services.ai import AiInvocationError
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "analysis-first 测试客户") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "用于 analysis-first 回归测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_approved_judgment(
    client: TestClient,
    *,
    client_id: str,
    judgment_id: str = "judgment_analysis_first_approved",
    topic: str = "客户主判断",
    summary: str = "当前主线已经从资料整理转向协同推进，正式判断较稳定。",
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence,
            created_at, updated_at, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by
        )
        VALUES(
            ?, ?, 'client', ?, ?, 1, 'approved', ?, '[]', NULL, 'medium', 'high',
            '2026-04-18T10:00:00', '2026-04-18T10:00:00', 'analysis', 'approved', 'reviewed',
            NULL, 'snapshot_analysis_first', NULL, NULL
        )
        """,
        (
            judgment_id,
            client_id,
            client_id,
            topic,
            summary,
        ),
    )


def insert_candidate_judgment(
    client: TestClient,
    *,
    client_id: str,
    judgment_id: str = "judgment_analysis_first_candidate",
    topic: str = "客户候选判断",
    summary: str = "当前更接近待确认判断，仍需继续补证据。",
    evidence_ids: list[str] | None = None,
    context_pack_id: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence,
            created_at, updated_at, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by
        )
        VALUES(
            ?, ?, 'client', ?, ?, 1, 'awaiting_review', ?, ?, ?, 'medium', 'medium',
            '2026-04-18T11:00:00', '2026-04-18T11:00:00', 'analysis', 'candidate', 'normalized',
            NULL, 'snapshot_analysis_first_candidate', NULL, NULL
        )
        """,
        (
            judgment_id,
            client_id,
            client_id,
            topic,
            summary,
            json.dumps(evidence_ids or [], ensure_ascii=False),
            context_pack_id,
        ),
    )


def create_scoped_task(client: TestClient, *, client_id: str, title: str, desc: str = "") -> str:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": desc,
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_evidence_card(
    client: TestClient,
    *,
    evidence_id: str,
    client_id: str,
    source_type: str,
    source_id: str,
    source_ref: str,
    normalized_claim: str,
    time_anchor: str = "2026-04-18T09:00:00",
    review_state: str = "awaiting_review",
    confidence: float = 0.72,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO evidence_cards(
            id, client_id, scope_type, scope_id, source_type, source_id, source_ref, quote, normalized_claim,
            confidence, time_anchor, review_state, fingerprint, normalized_claim_hash, source_ref_hash,
            evidence_fingerprint, created_at, updated_at
        )
        VALUES(?, ?, 'client', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-04-18T09:00:00', '2026-04-18T09:00:00')
        """,
        (
            evidence_id,
            client_id,
            client_id,
            source_type,
            source_id,
            source_ref,
            normalized_claim,
            normalized_claim,
            confidence,
            time_anchor,
            review_state,
            f"fingerprint::{evidence_id}",
            f"claim_hash::{evidence_id}",
            f"source_ref_hash::{evidence_id}",
            f"evidence_fingerprint::{evidence_id}",
        ),
    )


def insert_conflict_group(
    client: TestClient,
    *,
    conflict_id: str,
    client_id: str,
    title: str,
    summary: str,
    evidence_ids: list[str] | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO conflict_groups(
            id, client_id, scope_type, scope_id, conflict_type, title, summary, evidence_ids_json,
            unresolved_question_ids_json, resolution_status, severity, context_pack_id, created_at, updated_at
        )
        VALUES(?, ?, 'client', ?, 'judgment_conflict', ?, ?, ?, '[]', 'draft', 'medium', NULL, '2026-04-18T11:10:00', '2026-04-18T11:10:00')
        """,
        (
            conflict_id,
            client_id,
            client_id,
            title,
            summary,
            json.dumps(evidence_ids or [], ensure_ascii=False),
        ),
    )


def insert_client_dna_document(
    client: TestClient,
    *,
    client_id: str,
    module_key: str,
    title: str,
    summary: str,
    normalized_text: str,
    updated_at: str,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO client_dna_documents(
            client_id, module_key, title, markdown_content, normalized_text, summary, file_name, content_hash,
            source_kind, missing_info_json, updated_at, updated_by
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'manual', '[]', ?, 'pytest')
        ON CONFLICT(client_id, module_key) DO UPDATE SET
            title = excluded.title,
            markdown_content = excluded.markdown_content,
            normalized_text = excluded.normalized_text,
            summary = excluded.summary,
            file_name = excluded.file_name,
            content_hash = excluded.content_hash,
            source_kind = excluded.source_kind,
            missing_info_json = excluded.missing_info_json,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (
            client_id,
            module_key,
            title,
            normalized_text,
            normalized_text,
            summary,
            f"{module_key}.md",
            f"hash::{module_key}",
            updated_at,
        ),
    )


def insert_runtime_run_log(
    client: TestClient,
    *,
    run_id: str,
    client_id: str,
    summary: str,
    detail: dict[str, object],
    created_at: str = "2026-04-18T10:20:00",
) -> None:
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


def test_workspace_chat_prefers_state_pool_before_document_retrieval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="客户状态优先测试")
    insert_approved_judgment(client, client_id=client_id, topic="双年会推进判断", summary="双年会筹备已经进入协同推进阶段，重点在发言、行程和资料对齐。")
    create_scoped_task(
        client,
        client_id=client_id,
        title="推进双年会筹备",
        desc="本周继续确认发言、行程安排和会前资料对齐。",
    )

    captured: dict[str, str] = {}

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("analysis-first state-only query should not trigger document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        captured["context_summary"] = state_context_summary
        return AiStructuredResponse(
            content="正式判断和本周动作已经基于状态池整理完成。",
            judgment="当前正式判断较稳定，但仍需把风险与缺失信息单独陈述。",
            analysis="本周主线集中在双年会筹备推进。",
            actions="继续确认负责人、时间点和资料清单。",
            timeline="本周内完成关键对齐。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户本周在推进什么？当前有什么风险？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "state_only"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "state_first_default"
    assert payload["retrievalSummary"]["retrievalStage"] == "state_pool"
    assert payload["retrievalDecisionReason"] == "state_first_default"
    assert payload["stateConfidence"] == "high"
    assert "judgment" in payload["stateSources"]
    assert "task" in payload["stateSources"]
    assert payload["stateAnswerSections"]["official"]
    assert payload["stateAnswerSections"]["actions"]
    assert payload["stateSourceSummary"]["judgments"] >= 1
    assert payload["stateSourceSummary"]["tasks"] >= 1
    assert payload["retrievalSummary"]["state_first_hit_rate"] == 1
    assert payload["retrievalSummary"]["state_only_fallback_rate"] == 1
    assert payload["retrievalSummary"]["candidate_leakage_count"] == 0
    assert payload["evidence"] == []

    context_summary = captured["context_summary"]
    assert "客户状态池（analysis-first" in context_summary
    assert "[正式判断]" in context_summary
    assert "[本周动作]" in context_summary


def test_workspace_chat_state_only_ai_failure_still_returns_nonfatal_state_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="state-only 失败回退测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        topic="正式推进判断",
        summary="当前主线是继续收束客户状态，并把下一步动作明确到任务层。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进状态收口",
        desc="本周继续确认 blockers、recent decision 与 next step。",
    )

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("state-first query should not trigger document retrieval when state pool is enough")

    def fail_workspace_state_generation(prompt: str, state_context_summary: str, *, on_partial=None):
        raise AiInvocationError("qwen", "mock timeout during compact state generation")

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fail_workspace_state_generation)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "接下来最重要的事情是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "state_only"
    assert payload["fallbackPresentationMode"] == "state_cards_only"
    assert payload["stateAnswerSections"]["official"]
    assert payload["stateAnswerSections"]["actions"]
    assert payload["retrievalSummary"]["generationFailureDetail"] == "mock timeout during compact state generation"
    assert payload["content"]
    assert "围绕“接下来最重要的事情是什么？”" in payload["content"]
    assert "最值得继续推进的是：" in payload["content"]
    assert "一、正式判断" not in payload["content"]
    assert payload["evidence"] == []


def test_workspace_chat_registry_only_judgment_queries_stay_on_state_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="registry-only judgment 测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_registry_only",
        topic="已登记正式判断",
        summary="当前系统内已经批准的正式判断应直接来自 approved registry。",
    )

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("registry-only judgment query should not trigger document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="当前优先展示已登记的正式判断。",
            judgment="当前系统内已批准的正式判断来自 approved registry。",
            analysis="registry-only 查询不需要回钻文件。",
            actions="如需依据，请改问原文或资料支撑。",
            timeline="当前可直接返回。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "系统里已批准的正式判断有哪些？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["judgmentQueryMode"] == "registry_only"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "state_first_default"
    assert payload["failureReason"] == "state_only"
    assert payload["stateAnswerSections"]["official"]
    assert payload["evidence"] == []


def test_workspace_chat_intro_queries_force_evidence_retrieval_even_with_strong_state_pool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="介绍问题证据优先测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_intro_profile",
        topic="正式推进判断",
        summary="当前主线仍是战略陪伴与协同推进。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进战略陪伴",
        desc="本周持续收束会前资料和后续安排。",
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_intro_profile_1', ?, NULL, '日慈基金会机构介绍', '/tmp/richi-intro.md', 'md', 'file', '日慈基金会聚焦公益项目支持、行业协同与长期能力建设。', '[]', '2026-04-18T10:00:00')
        """,
        (client_id,),
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_intro_profile_1', ?, NULL, 'doc_intro_profile_1', 'kd_intro_profile_1_uid', '/tmp/richi-intro.md', '/tmp/richi-intro.md', NULL,
            '组织与战略', NULL, NULL, 0.0, NULL, 'md',
            '组织与战略', '机构介绍', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_intro_profile_1', 'normalized_intro_profile_1', '2026-04-18T10:00:00', '2026-04-18T10:00:00'
        )
        """,
        (client_id,),
    )

    calls = {"retrieval": 0, "state": 0}

    def fake_retrieval_bundle(client_id_arg: str, prompt: str):
        calls["retrieval"] += 1
        assert client_id_arg == client_id
        assert "介绍" in prompt
        return RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_intro_profile_1",
                    chunk_id="chunk_intro_profile_1",
                    title="日慈基金会机构介绍",
                    excerpt="日慈基金会聚焦公益项目支持、行业协同与长期能力建设，当前正在完善项目推进和对外沟通材料。",
                    score=0.93,
                    coverage=0.82,
                    section_label="机构介绍",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["介绍", "机构"],
                    path="/tmp/richi-intro.md",
                )
            ],
            coverage=0.82,
            retrieval_summary={
                "masterHitCount": 1,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 1,
                "preferredCategories": ["组织与战略"],
                "categoryCoverage": ["组织与战略"],
            },
            context_text="",
            matched_terms=["介绍", "机构"],
            failure_reason=None,
        )

    def fail_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        calls["state"] += 1
        raise AssertionError("intro/profile queries should not stay on the state-only path")

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        assert "原始证据包（可用于正式判断）：" in context_summary
        assert "日慈基金会机构介绍" in context_summary
        return AiStructuredResponse(
            content="日慈基金会是一家围绕公益项目支持与行业协同展开工作的机构，当前重点是把项目推进和对外沟通材料收得更清楚。",
            judgment="这是一条基于机构介绍原文整理出的基础介绍，不是单纯状态池回显。",
            analysis="介绍类问题应优先落到机构介绍和项目资料，而不是直接套状态面板。",
            actions="如需继续细化，可下钻到项目介绍、团队介绍和会议纪要。",
            timeline="补齐更多组织资料后可以扩成更完整的客户画像。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda db, data_dir, client_id_arg, prompt: fake_retrieval_bundle(client_id_arg, prompt))
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fail_workspace_state_response)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍日慈基金会"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert calls["retrieval"] == 1
    assert calls["state"] == 0
    assert payload["answerMode"] == "grounded_answer"
    assert payload["retrievalSummary"]["retrievalDeferred"] is False
    assert payload["retrievalDecisionReason"] == "intro_query_needs_evidence"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "intro_query_needs_evidence"
    assert payload["evidence"]
    assert payload["failureReason"] is None


def test_workspace_chat_routes_default_judgment_questions_to_hybrid_linked_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="hybrid judgment 默认路由测试")
    insert_evidence_card(
        client,
        evidence_id="evidence_hybrid_candidate",
        client_id=client_id,
        source_type="analysis_note",
        source_id="candidate_hybrid_judgment",
        source_ref="候选判断证据",
        normalized_claim="会议与任务信号共同表明，当前仍停留在待确认判断阶段。",
    )
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="candidate_hybrid_judgment",
        topic="客户候选判断",
        summary="当前更接近待确认判断：需要先把会议与任务信号收束，再决定是否进入正式层。",
        evidence_ids=["evidence_hybrid_candidate"],
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="收束候选判断",
        desc="下一步先核对会议纪要和任务推进，再决定是否生成 judgment proposal。",
    )

    captured: dict[str, str] = {}

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("default judgment hybrid query should prefer linked evidence instead of generic retrieval")

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        captured["context_summary"] = context_summary
        return AiStructuredResponse(
            content="当前先给出已登记判断和待确认判断。",
            judgment="当前系统内已批准的正式判断仍为空。",
            analysis="但基于状态对象和关联证据，已经可以形成待确认判断。",
            actions="继续围绕候选判断补证据。",
            timeline="补齐后再进入 proposal/approval 流程。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在有哪些正式判断？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["judgmentQueryMode"] == "hybrid"
    assert payload["answerIntent"] == "official_judgment_registry"
    assert payload["evidenceSupportMode"] == "evidence_cards"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "official_registry_requested"
    assert payload["retrievalSummary"]["retrievalStage"] == "hybrid_linked_evidence"
    assert payload["failureReason"] is None
    assert payload["stateAnswerSections"]["official"] == []
    assert payload["stateAnswerSections"]["candidate"]
    assert payload["stateAnswerSections"]["evidenceSupport"]
    assert payload["stateAnswerSections"]["unknowns"]
    assert payload["evidence"]
    assert payload["evidence"][0]["retrievalStage"] == "surrogate"
    assert "[待确认判断 / 判断草稿]" in captured["context_summary"]
    assert "[支撑证据摘要]" in captured["context_summary"]


def test_workspace_chat_hybrid_fallback_uses_state_cards_only_presentation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="hybrid judgment fallback 测试")
    insert_evidence_card(
        client,
        evidence_id="evidence_hybrid_fallback_candidate",
        client_id=client_id,
        source_type="analysis_note",
        source_id="candidate_hybrid_fallback_judgment",
        source_ref="候选判断证据",
        normalized_claim="当前还没有 approved judgment，但会议与任务已经形成待确认判断。",
    )
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="candidate_hybrid_fallback_judgment",
        topic="客户候选判断",
        summary="当前仍停留在待确认判断阶段。",
        evidence_ids=["evidence_hybrid_fallback_candidate"],
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续补判断证据",
        desc="需要再核对会议与任务上下文。",
    )

    def raise_timeout(*args, **kwargs):
        raise AiInvocationError("doubao", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_timeout)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在有哪些正式判断？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "llm_local_fallback_after_retry"
    assert payload["judgmentQueryMode"] == "hybrid"
    assert payload["fallbackPresentationMode"] == "state_cards_only"
    assert payload["stateAnswerSections"]["official"] == []
    assert payload["stateAnswerSections"]["candidate"]
    assert "analysis-first" not in payload["content"]
    assert "当前最值得抓住的原始观察包括" not in payload["content"]


def test_workspace_chat_queues_fact_extraction_after_main_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="后台记忆提取调度测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_fact_extract_schedule",
        topic="正式推进判断",
        summary="主回答已经足够可用时，记忆提取应退到后台。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进状态回答",
        desc="确保主回答不等待记忆提取。",
    )

    scheduled: dict[str, object] = {}

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="结构化状态回答已生成。",
            judgment="正式判断已经可直接返回。",
            analysis="记忆提取应改为后台执行。",
            actions="继续按状态池推进。",
            timeline="本周内完成。",
        )

    def fake_schedule(state, **kwargs):
        scheduled.update(kwargs)

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)
    monkeypatch.setattr(app_main, "_schedule_chat_fact_extraction", fake_schedule)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "接下来最重要的事情是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "state_only"
    assert scheduled["client_id"] == client_id
    assert scheduled["thread_id"] == payload["threadId"]
    assert scheduled["user_prompt"] == "接下来最重要的事情是什么？"
    assert "结构化状态回答已生成。" in str(scheduled["assistant_content"])
    assert scheduled["answer_mode"] == "grounded_fallback"


def test_workspace_chat_ignores_fact_extraction_queue_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="后台记忆提取失败隔离测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_fact_extract_nonfatal",
        topic="正式推进判断",
        summary="即使后台记忆提取调度失败，主回答也不能失败。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="保持主回答成功",
        desc="后台任务失败不应影响 state-first 回答。",
    )

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="状态回答已经可用。",
            judgment="主回答不依赖后台记忆提取。",
            analysis="调度失败也只能记录日志。",
            actions="继续围绕状态池给出主回答。",
            timeline="本周内完成。",
        )

    def fail_schedule(*args, **kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)
    monkeypatch.setattr(app_main, "_schedule_chat_fact_extraction", fail_schedule)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户最近在推进什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "state_only"
    assert payload["stateAnswerSections"]["official"]


@pytest.mark.parametrize(
    "prompt",
    [
        "现在最值得关注的事项是什么？",
        "接下来最重要的下一步是什么？",
        "目前最大的阻塞点是什么？",
    ],
)
def test_workspace_chat_routes_common_state_questions_to_state_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prompt: str):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="状态问题覆盖测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_state_question_coverage",
        topic="当前推进判断",
        summary="当前主线是先明确下一步动作，再收束待确认判断和阻塞点。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="明确下一步动作",
        desc="本周要把当前最重要的事项和最大阻塞点整理清楚。",
    )

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("common state questions should stay on the state-first path")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="结构化状态回答已经生成。",
            judgment="正式判断仍然只来自 judgment bundle。",
            analysis="最重要事项、下一步和阻塞点都应先走状态池。",
            actions="继续按状态池收束任务与判断。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": prompt},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["retrievalDecisionReason"] == "state_first_default"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["failureReason"] == "state_only"
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["evidence"] == []


def test_workspace_chat_official_section_ignores_compat_latest_judgments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="compat judgment 不得污染正式回答")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_bundle_source",
        topic="正式 bundle 判断",
        summary="正式判断来自 judgment bundle，不应被 compat judgment 覆盖。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进判断收口",
        desc="把正式判断和本周动作整理为统一状态回答。",
    )

    compat_judgment = JudgmentVersionRecord(
        id="judgment_compat_source",
        clientId=client_id,
        targetType="client",
        targetId=client_id,
        topic="compat judgment",
        status="approved",
        originType="analysis",
        authorityLevel="approved",
        qualityTier="reviewed",
        summary="这条 compat judgment 不应进入正式判断段。",
        createdAt="2026-04-18T10:30:00",
        updatedAt="2026-04-18T10:30:00",
    )
    real_get_bundle = app_main.get_client_analysis_bundle

    def fake_get_bundle(db, workspace_seed):
        bundle = real_get_bundle(db, workspace_seed)
        bundle.latest_judgments = [compat_judgment]
        return bundle

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("state-first query should not fall back to document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="正式判断仍来自 judgment bundle。",
            judgment="compat judgment 不能进入正式判断段。",
            analysis="状态回答需要保持 judgment 边界干净。",
            actions="继续按照 bundle 判断推进。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "get_client_analysis_bundle", fake_get_bundle)
    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户最近在推进什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    official_text = "\n".join(payload["stateAnswerSections"]["official"])
    assert "正式判断来自 judgment bundle" in official_text
    assert "compat judgment 不应进入正式判断段" not in official_text
    assert payload["retrievalSummary"]["candidate_leakage_count"] == 0


def test_workspace_chat_filters_attachment_ingest_boilerplate_from_candidate_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="candidate 污染过滤测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_clean_approved",
        topic="正式推进判断",
        summary="当前可以先围绕客户状态池回答推进问题。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进状态池问答",
        desc="保持正式判断与候选判断边界。",
    )

    polluted_candidate = JudgmentVersionRecord(
        id="judgment_polluted_candidate",
        clientId=client_id,
        targetType="client",
        targetId=client_id,
        topic="client_overview",
        status="awaiting_review",
        originType="analysis",
        authorityLevel="candidate",
        qualityTier="normalized",
        summary="client_overview：b1854d964465d43d.jpeg 已作为任务附件进入项目资料库，可用于后续检索、问答与事件线证据引用。",
        createdAt="2026-04-18T11:00:00",
        updatedAt="2026-04-18T11:00:00",
    )
    real_get_bundle = app_main.get_client_analysis_bundle

    def fake_get_bundle(db, workspace_seed):
        bundle = real_get_bundle(db, workspace_seed)
        if bundle.judgment_bundle:
            bundle.judgment_bundle.overlayDeltas = [*bundle.judgment_bundle.overlayDeltas, polluted_candidate]
        return bundle

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("state-first query should not fall back to document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="当前候选判断已经过滤导入噪音。",
            judgment="正式判断保持干净。",
            analysis="导入 boilerplate 不应进入 candidate judgment。",
            actions="继续围绕真实 judgment、任务和会议回答。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "get_client_analysis_bundle", fake_get_bundle)
    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "最近有什么变化？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    candidate_text = "\n".join(payload["stateAnswerSections"]["candidate"])
    assert "已作为任务附件进入项目资料库" not in candidate_text
    assert payload["retrievalSummary"]["candidate_leakage_count"] >= 1


def test_workspace_chat_keeps_run_logs_as_state_sources_without_promoting_them_to_judgment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="run log 只作最近运行摘要")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_bundle_runlog",
        topic="正式 bundle 判断",
        summary="正式判断仍然来自 judgment bundle。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进正式判断",
        desc="保持 judgment bundle 与状态回答一致。",
    )
    insert_runtime_run_log(
        client,
        run_id="runlog_state_first_source",
        client_id=client_id,
        summary="状态池刷新完成",
        detail={
            "intentProfile": "client_overview",
            "latestRunSummary": "最近运行提示：已完成状态池刷新。",
            "outputSummary": "这条 outputSummary 不应覆盖 latestRunSummary。",
        },
    )

    captured: dict[str, str] = {}

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("state-first query should not fall back to document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        captured["context_summary"] = state_context_summary
        return AiStructuredResponse(
            content="正式判断仍来自 judgment bundle，运行日志只作为最近运行摘要。",
            judgment="不要把 run log 当成正式判断。",
            analysis="状态池来源里可以出现 run_log，但正式判断只能来自 judgment bundle。",
            actions="继续推进正式判断与任务动作。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户最近在推进什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert "run_log" in payload["stateSources"]
    official_text = "\n".join(payload["stateAnswerSections"]["official"])
    assert "正式判断仍然来自 judgment bundle" in official_text
    assert "最近运行提示：已完成状态池刷新" not in official_text
    assert "最近运行提示：已完成状态池刷新" not in captured["context_summary"]


def test_workspace_chat_keeps_document_retrieval_for_drilldown_questions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="文档下钻测试")
    insert_approved_judgment(client, client_id=client_id, topic="客户推进判断", summary="当前主要围绕关系推进和双年会协同展开。")
    create_scoped_task(client, client_id=client_id, title="推进关系沟通", desc="补齐会前资料并安排下一轮沟通。")
    client.app.state.app_state.db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_state_1', ?, NULL, '双年会沟通纪要', '/tmp/meeting-note.md', 'md', 'file', '纪要里明确提到，本周重点是确认发言安排和资料准备。', '[]', '2026-04-18T10:00:00')
        """,
        (client_id,),
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_doc_state_1', ?, NULL, 'doc_state_1', 'kd_doc_state_1_uid', '/tmp/meeting-note.md', '/tmp/meeting-note.md', NULL,
            '组织与战略', NULL, NULL, 0.0, NULL, 'md',
            '组织与战略', '会议纪要', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_state_1', 'normalized_state_1', '2026-04-18T10:00:00', '2026-04-18T10:00:00'
        )
        """,
        (client_id,),
    )

    calls = {"retrieval": 0}

    def fake_retrieval_bundle(client_id_arg: str, prompt: str):
        calls["retrieval"] += 1
        assert client_id_arg == client_id
        return RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_doc_state_1",
                    chunk_id="chunk_state_1",
                    title="双年会沟通纪要",
                    excerpt="纪要里明确提到，本周重点是确认发言安排和资料准备。",
                    score=0.92,
                    coverage=0.8,
                    section_label="关键片段",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["原文", "资料"],
                    path="/tmp/meeting-note.md",
                )
            ],
            coverage=0.8,
            retrieval_summary={
                "masterHitCount": 1,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 1,
                "preferredCategories": ["组织与战略"],
                "categoryCoverage": ["组织与战略"],
            },
            context_text="",
            matched_terms=["原文", "资料"],
            failure_reason=None,
        )

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="已经结合原文片段回答。",
            judgment="当前判断有直接证据支撑。",
            analysis="原文明确提到了本周动作。",
            actions="继续沿着原文中的动作推进。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda db, data_dir, client_id_arg, prompt: fake_retrieval_bundle(client_id_arg, prompt))
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "哪份原文支持当前判断？请引用相关文件"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert calls["retrieval"] == 1
    assert payload["judgmentQueryMode"] == "evidence_based_synthesis"
    assert payload["evidenceSupportMode"] == "raw_doc_drilldown"
    assert payload["answerMode"] == "grounded_answer"
    assert payload["retrievalSummary"]["retrievalDeferred"] is False
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "document_drilldown_requested"
    assert payload["retrievalSummary"]["retrievalStage"] == "hybrid_raw_drilldown"
    assert payload["evidence"]
    assert payload["evidence"][0]["title"] == "双年会沟通纪要"


def test_workspace_chat_evidence_based_synthesis_keeps_raw_docs_in_support_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="evidence-based synthesis 边界测试")
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="candidate_conflicted_judgment",
        topic="客户候选判断",
        summary="当前候选判断认为项目已经进入执行协同阶段。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="核对判断依据",
        desc="需要把候选判断与原文纪要逐条对照。",
    )
    insert_conflict_group(
        client,
        conflict_id="conflict_candidate_vs_raw",
        client_id=client_id,
        title="候选判断与原文存在阶段冲突",
        summary="候选判断写的是执行协同阶段，但原文纪要仍显示方向提案阶段，需要核对后再决定是否保留。",
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_judgment_raw_conflict', ?, NULL, '双年会方向讨论纪要', '/tmp/conflict-meeting-note.md', 'md', 'file', '纪要明确写到：这次仍是方向提案，不是最终执行方案。', '[]', '2026-04-18T10:00:00')
        """,
        (client_id,),
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_judgment_raw_conflict', ?, NULL, 'doc_judgment_raw_conflict', 'kd_judgment_raw_conflict_uid', '/tmp/conflict-meeting-note.md', '/tmp/conflict-meeting-note.md', NULL,
            '组织与战略', NULL, NULL, 0.0, NULL, 'md',
            '组织与战略', '会议纪要', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_conflict_1', 'normalized_conflict_1', '2026-04-18T10:00:00', '2026-04-18T10:00:00'
        )
        """,
        (client_id,),
    )

    calls = {"retrieval": 0}

    def fake_retrieval_bundle(client_id_arg: str, prompt: str):
        calls["retrieval"] += 1
        assert client_id_arg == client_id
        return RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_judgment_raw_conflict",
                    chunk_id="chunk_judgment_raw_conflict",
                    title="双年会方向讨论纪要",
                    excerpt="纪要明确写到：这次仍是方向提案，不是最终执行方案。",
                    score=0.95,
                    coverage=0.82,
                    section_label="关键片段",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["资料", "原文", "判断"],
                    path="/tmp/conflict-meeting-note.md",
                )
            ],
            coverage=0.82,
            retrieval_summary={
                "masterHitCount": 1,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 1,
                "preferredCategories": ["组织与战略"],
                "categoryCoverage": ["组织与战略"],
            },
            context_text="",
            matched_terms=["资料", "原文", "判断"],
            failure_reason=None,
        )

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="已结合状态对象和原文片段回答。",
            judgment="当前系统内已批准的正式判断仍为空。",
            analysis="原文可以强化或削弱候选判断，但不能直接改写官方层。",
            actions="先核对候选判断与会议纪要，再决定是否生成 judgment proposal。",
            timeline="补齐后再进入审批。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda db, data_dir, client_id_arg, prompt: fake_retrieval_bundle(client_id_arg, prompt))
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "基于资料能形成哪些判断？请引用原文"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    candidate_text = "\n".join(payload["stateAnswerSections"]["candidate"])
    evidence_text = "\n".join(payload["stateAnswerSections"]["evidenceSupport"])
    risk_text = "\n".join(payload["stateAnswerSections"]["risks"])

    assert calls["retrieval"] == 1
    assert payload["judgmentQueryMode"] == "evidence_based_synthesis"
    assert payload["evidenceSupportMode"] == "raw_doc_drilldown"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] in {
        "document_drilldown_requested",
        "evidence_question_needs_evidence",
    }
    assert payload["retrievalSummary"]["retrievalStage"] == "hybrid_raw_drilldown"
    assert payload["stateAnswerSections"]["official"] == []
    assert "执行协同阶段" in candidate_text
    assert "方向提案" not in candidate_text
    assert "方向提案" in evidence_text
    assert "阶段冲突" in risk_text
    assert payload["evidence"][0]["title"] == "双年会方向讨论纪要"


def test_workspace_chat_marks_stale_dna_as_weak_support_in_hybrid_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="过旧 DNA 弱化测试")
    create_scoped_task(
        client,
        client_id=client_id,
        title="核对客户背景",
        desc="需要结合客户 DNA 和当前任务推进，但不能把过旧 DNA 当作强证据。",
    )
    insert_client_dna_document(
        client,
        client_id=client_id,
        module_key="organization_intro",
        title="组织介绍",
        summary="客户过去强调行业协同与长期能力建设。",
        normalized_text="客户过去强调行业协同与长期能力建设，这份 DNA 版本较早。",
        updated_at="2025-01-01T09:00:00",
    )

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("stale DNA hybrid query should still stay on linked evidence path")

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="当前回答已经保留 DNA 的弱支撑边界。",
            judgment="正式判断仍为空。",
            analysis="DNA 可以作为背景，但过旧时只能弱化引用。",
            actions="优先补最近会议或任务上下文。",
            timeline="补齐后再判断是否进入 proposal。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在怎么看这个客户？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    evidence_text = "\n".join(payload["stateAnswerSections"]["evidenceSupport"])
    assert payload["judgmentQueryMode"] == "hybrid"
    assert payload["evidenceSupportMode"] == "linked_state_evidence"
    assert "仅作弱支撑" in evidence_text


def test_task_prep_proposal_runs_through_review_and_execution_without_touching_official_layer(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="任务准备 proposal 测试")
    insert_approved_judgment(client, client_id=client_id, topic="客户主判断", summary="当前项目进入稳态推进，准备包可直接围绕正式判断组织。")
    task_id = create_scoped_task(client, client_id=client_id, title="准备周会材料", desc="汇总本周关键推进、风险和待确认问题。")

    prep_pack = client.get(f"/api/v1/tasks/{task_id}/prep-pack")
    assert prep_pack.status_code == 200, prep_pack.text
    prep_payload = prep_pack.json()
    assert prep_payload["summary"]
    assert prep_payload["boundaryNotes"]

    proposal = client.post(f"/api/v1/tasks/{task_id}/prep-pack/proposals")
    assert proposal.status_code == 200, proposal.text
    proposal_payload = proposal.json()
    assert proposal_payload["kind"] == "task_prep"
    assert proposal_payload["status"] == "pending_review"

    approved = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/approve",
        json={"comment": "可以进入执行台账"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    executed = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/execute",
        json={"comment": "执行"},
    )
    assert executed.status_code == 200, executed.text
    execution_payload = executed.json()
    assert execution_payload["proposal"]["status"] == "executed"
    assert execution_payload["executionTicket"]["status"] == "executed"
    assert execution_payload["executionTicket"]["result"]["resultType"] == "prep_artifact_ready"
    assert execution_payload["executionTicket"]["result"]["artifactRefs"]
    assert "不直接改写 official judgment" in execution_payload["executionTicket"]["result"]["summary"]

    judgment_count = client.app.state.app_state.db.scalar(
        "SELECT COUNT(1) AS count FROM judgment_versions WHERE client_id = ? AND authority_level = 'approved'",
        (client_id,),
    )
    assert int(judgment_count or 0) == 1


def test_meeting_followup_proposal_creates_execution_tasks_after_approval(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="会议 follow-up proposal 测试")

    prepared = client.post(
        f"/api/v1/clients/{client_id}/meetings",
        json={"title": "双年会筹备会", "scheduledAt": "2026-04-18T14:00:00"},
    )
    assert prepared.status_code == 200, prepared.text
    meeting_id = prepared.json()["meeting"]["id"]

    db = client.app.state.app_state.db
    db.execute(
        "INSERT INTO decisions(id, meeting_id, summary, created_at) VALUES('dec_followup_1', ?, '确认本周完成双年会发言和资料清单。', '2026-04-18T14:30:00')",
        (meeting_id,),
    )
    db.execute(
        """
        INSERT INTO action_items(id, meeting_id, title, owner_name, due_date, confidence, publish_status, created_at)
        VALUES('act_followup_1', ?, '整理双年会资料清单', '庆华', '本周', 0.9, 'draft', '2026-04-18T14:30:00')
        """,
        (meeting_id,),
    )
    db.execute(
        "INSERT INTO risks(id, meeting_id, summary, severity, created_at) VALUES('risk_followup_1', ?, '资料边界如果不收束，会影响会前统一口径。', 'medium', '2026-04-18T14:30:00')",
        (meeting_id,),
    )
    db.execute("UPDATE meetings SET stage = 'resolved', updated_at = '2026-04-18T14:35:00' WHERE id = ?", (meeting_id,))

    proposal = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/proposals/follow-up")
    assert proposal.status_code == 200, proposal.text
    proposal_payload = proposal.json()
    assert proposal_payload["kind"] == "meeting_followup"
    assert proposal_payload["status"] == "pending_review"
    assert proposal_payload["payload"]["actionItems"]
    assert proposal_payload["payload"]["payloadHash"]

    duplicate_proposal = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/proposals/follow-up")
    assert duplicate_proposal.status_code == 200, duplicate_proposal.text
    assert duplicate_proposal.json()["id"] == proposal_payload["id"]

    approved = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/approve",
        json={"comment": "执行会后跟进"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    executed = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/execute",
        json={"comment": "执行"},
    )
    assert executed.status_code == 200, executed.text
    execution_payload = executed.json()
    assert execution_payload["proposal"]["status"] == "executed"
    assert execution_payload["executionTicket"]["status"] == "executed"
    assert execution_payload["executionTicket"]["result"]["resultType"] == "followup_task_created"
    created_task_ids = execution_payload["executionTicket"]["result"]["createdTaskIds"]
    assert len(created_task_ids) == 1

    executed_again = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/execute",
        json={"comment": "重复执行"},
    )
    assert executed_again.status_code == 200, executed_again.text
    repeated_payload = executed_again.json()
    assert repeated_payload["executionTicket"]["id"] == execution_payload["executionTicket"]["id"]
    assert repeated_payload["executionTicket"]["result"]["createdTaskIds"] == created_task_ids

    created_task = db.fetchone(
        "SELECT title, source_type, source_id, client_id FROM tasks WHERE source_type = 'meeting_followup_proposal' ORDER BY created_at DESC LIMIT 1"
    )
    assert created_task is not None
    assert str(created_task["title"]) == "整理双年会资料清单"
    assert str(created_task["source_id"]) == proposal_payload["id"]
    assert str(created_task["client_id"]) == client_id
    task_count = db.scalar("SELECT COUNT(1) AS count FROM tasks WHERE source_type = 'meeting_followup_proposal' AND source_id = ?", (proposal_payload["id"],))
    assert int(task_count or 0) == 1
