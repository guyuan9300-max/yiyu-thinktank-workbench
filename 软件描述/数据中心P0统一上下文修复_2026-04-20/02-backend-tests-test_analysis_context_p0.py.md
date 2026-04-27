# 源码文件：`backend/tests/test_analysis_context_p0.py`

- 导出时间：2026-04-20
- 说明：以下为当前工作区中的完整文件内容。

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse, AnswerPolicyRecord, ContextQualityRecord, PageContextPackRecord
from app.services.ai import AiInvocationError
from app.services.analysis_context import build_answer_material
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "P0 上下文测试客户") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "用于 P0 page-context 测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def default_task_list_id(client: TestClient) -> str:
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["lists"][0]["id"]


def create_task(
    client: TestClient,
    *,
    title: str,
    desc: str = "",
    client_id: str | None = None,
    event_line_id: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "title": title,
        "desc": desc,
        "priority": "high",
        "listId": default_task_list_id(client),
    }
    if client_id:
        payload["clientId"] = client_id
    if event_line_id:
        payload["eventLineId"] = event_line_id
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_judgment(
    client: TestClient,
    *,
    judgment_id: str,
    client_id: str,
    status: str,
    authority_level: str,
    summary: str,
    evidence_ids: list[str] | None = None,
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
            ?, ?, 'client', ?, 'P0 judgment', 1, ?, ?, ?, NULL, 'medium', 'medium',
            '2026-04-18T10:00:00', '2026-04-18T10:00:00', 'analysis', ?,
            ?, NULL, 'snapshot_p0', NULL, NULL
        )
        """,
        (
            judgment_id,
            client_id,
            client_id,
            status,
            summary,
            json.dumps(evidence_ids or [], ensure_ascii=False),
            authority_level,
            "reviewed" if status == "approved" else "normalized",
        ),
    )


def insert_evidence_card(
    client: TestClient,
    *,
    evidence_id: str,
    client_id: str,
    normalized_claim: str,
    source_id: str = "src_p0",
    source_ref: str = "P0 证据",
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO evidence_cards(
            id, client_id, scope_type, scope_id, source_type, source_id, source_ref, quote, normalized_claim,
            evidence_type, polarity, tags_json, topic_keys_json, confidence, time_anchor, review_state,
            fingerprint, normalized_claim_hash, source_ref_hash, evidence_fingerprint, normalizer_version,
            created_at, updated_at
        )
        VALUES(
            ?, ?, 'client', ?, 'analysis_note', ?, ?, ?, ?,
            'finding', 'neutral', '[]', '[]', 0.78, '2026-04-18T09:00:00', 'awaiting_review',
            ?, ?, ?, ?, 'analysis-center-v0.3.3',
            '2026-04-18T09:00:00', '2026-04-18T09:00:00'
        )
        """,
        (
            evidence_id,
            client_id,
            client_id,
            source_id,
            source_ref,
            normalized_claim,
            normalized_claim,
            f"fp::{evidence_id}",
            f"claim::{evidence_id}",
            f"src::{evidence_id}",
            f"evfp::{evidence_id}",
        ),
    )


def insert_open_question(client: TestClient, *, question_id: str, client_id: str, question: str) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO open_questions(
            id, client_id, scope_type, scope_id, theme_key, question, reason, blocker_level, status, created_at, updated_at
        )
        VALUES(?, ?, 'client', ?, 'p0_theme', ?, '待确认', 'medium', 'draft', '2026-04-18T10:10:00', '2026-04-18T10:10:00')
        """,
        (question_id, client_id, client_id, question),
    )


def build_retrieval_bundle(excerpts: list[str]) -> RetrievalBundle:
    citations = [
        CitationMatch(
            knowledge_document_id=f"kd_{index}",
            chunk_id=f"chunk_{index}",
            title=f"P0资料{index}",
            excerpt=excerpt,
            score=0.9 - index * 0.04,
            coverage=0.82,
            section_label="正文",
            source_stage="raw_chunk",
            drillthrough_used=True,
            matched_terms=["介绍", "资料"],
            path=f"/tmp/p0_{index}.md",
        )
        for index, excerpt in enumerate(excerpts, start=1)
    ]
    return RetrievalBundle(
        citations=citations,
        coverage=0.82,
        retrieval_summary={
            "docHitCount": len(citations),
            "rawChunkHitCount": len(citations),
            "masterHitCount": len(citations),
            "surrogateHitCount": len(citations),
        },
        context_text="",
        matched_terms=["介绍", "资料"],
        failure_reason=None,
    )


def test_client_page_context_returns_core_objects(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="P0 page-context 客户")

    insert_evidence_card(
        client,
        evidence_id="evidence_p0_core",
        client_id=client_id,
        normalized_claim="当前推进已经进入关键协同阶段。",
    )
    insert_judgment(
        client,
        judgment_id="judgment_p0_approved",
        client_id=client_id,
        status="approved",
        authority_level="approved",
        summary="已批准正式判断：当前推进进入协同阶段。",
        evidence_ids=["evidence_p0_core"],
    )
    insert_judgment(
        client,
        judgment_id="judgment_p0_candidate",
        client_id=client_id,
        status="awaiting_review",
        authority_level="candidate",
        summary="候选判断：仍需补齐会议证据。",
        evidence_ids=["evidence_p0_core"],
    )
    insert_open_question(
        client,
        question_id="oq_p0_1",
        client_id=client_id,
        question="关键责任人是否已经确认？",
    )
    create_task(client, title="P0 关联任务", desc="用于 page-context 验证", client_id=client_id)

    response = client.get(
        f"/api/v1/clients/{client_id}/page-context",
        params={"page": "workspace_chat", "prompt": "这个客户现在推进到哪了？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["clientId"] == client_id
    assert payload["officialJudgments"]
    assert payload["candidateJudgments"]
    assert payload["evidenceCards"]
    assert payload["relatedTasks"]
    assert payload["quality"]["contextQuality"] in {"usable", "strong"}
    assert payload["answerPolicy"]["canAnswer"] is True


def test_workspace_chat_state_insufficient_triggers_raw_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="P0 raw fallback 客户")

    retrieval_bundle = build_retrieval_bundle(
        [
            "该客户是公益协同机构，当前重点是把项目推进路径收束成可执行动作。",
            "会议纪要显示当前卡点在负责人和时间线确认。",
        ]
    )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: retrieval_bundle)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="基于原始资料，这个客户当前的核心定位与推进状态已经可以给出简版回答。",
            judgment="当前可先给 evidence-based 回答。",
            analysis="状态对象不足时已回到原文证据。",
            actions="继续补齐负责人与时间线。",
            timeline="本周完成关键确认。",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "请介绍一下这个客户"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["retrievalSummary"]["answerLevel"] == "evidence_based"
    assert payload["retrievalSummary"]["rawFallbackTriggered"] is True
    assert payload["evidence"]
    assert "当前暂无已批准判断所以无法回答" not in payload["content"]


def test_workspace_chat_official_query_stays_registry_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="P0 registry-only 客户")
    insert_judgment(
        client,
        judgment_id="judgment_registry_only_p0",
        client_id=client_id,
        status="approved",
        authority_level="approved",
        summary="系统内已批准正式判断：推进以任务协同为主。",
    )

    monkeypatch.setattr(
        app_main,
        "retrieve_knowledge_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("registry-only query should not call retrieval")),
    )
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_workspace_state_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="当前优先展示已批准正式判断。",
            judgment="这是 registry-only 查询。",
            analysis="无需触发原文下钻。",
            actions="如需依据可继续追问证据。",
            timeline="当前可直接返回。",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "系统里已批准的正式判断有哪些？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["judgmentQueryMode"] == "registry_only"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["retrievalSummary"]["rawFallbackTriggered"] is False
    assert payload["retrievalSummary"]["answerLevel"] == "official"
    assert payload["evidence"] == []


def test_workspace_chat_candidate_boundary_disclosed_when_no_approved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="P0 candidate 边界客户")

    insert_evidence_card(
        client,
        evidence_id="evidence_candidate_p0",
        client_id=client_id,
        normalized_claim="当前只有候选判断，尚未完成审批。",
        source_id="candidate_only",
        source_ref="候选判断证据",
    )
    insert_judgment(
        client,
        judgment_id="judgment_candidate_only_p0",
        client_id=client_id,
        status="awaiting_review",
        authority_level="candidate",
        summary="候选判断：当前推进路径需要更多证据确认。",
        evidence_ids=["evidence_candidate_p0"],
    )

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="当前可以先整理一版判断和下一步动作。",
            judgment="候选层可用。",
            analysis="需要继续补证据。",
            actions="补齐会议纪要和任务证据。",
            timeline="补齐后进入审批。",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在有哪些正式判断？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["retrievalSummary"]["answerLevel"] == "candidate"
    assert payload["retrievalSummary"]["mustDiscloseCandidateBoundary"] is True
    assert payload["retrievalSummary"]["candidateBoundaryDisclosed"] is True
    assert "还没有已批准的正式判断" in payload["content"]
    assert "候选判断" in payload["content"]
    assert payload["stateAnswerSections"]["candidate"]
    assert payload["stateAnswerSections"]["official"] == []


def test_task_page_context_minimum_available_without_client_or_event_line(tmp_path: Path):
    client = make_client(tmp_path)
    task_id = create_task(
        client,
        title="P0 最小任务上下文",
        desc="只有标题和描述，也要返回可用上下文。",
    )

    response = client.get(f"/api/v1/tasks/{task_id}/page-context")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["relatedTasks"]
    assert payload["relatedTasks"][0]["id"] == task_id
    assert payload["quality"]["contextQuality"] in {"weak", "usable"}
    assert payload["answerPolicy"]["canAnswer"] is True
    missing_text = "\n".join(payload["missingContext"])
    assert "client" in missing_text.lower()
    assert "event line" in missing_text.lower()
    assert payload["contextPack"]["understanding"]["whatIsThis"]
    assert payload["contextPack"]["understanding"].get("_pending") is None


def test_task_page_context_enhanced_with_client_and_event_line(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="P0 任务增强客户")

    event_line_response = client.post(
        "/api/v1/event-lines",
        json={
            "name": "P0 任务推进线",
            "kind": "project_line",
            "status": "active",
            "summary": "用于任务 page-context 增强测试",
            "nextStep": "先补齐会前判断",
            "currentBlocker": "负责人未确认",
            "recentDecision": "先收口再推进",
            "primaryClientId": client_id,
        },
    )
    assert event_line_response.status_code == 200, event_line_response.text
    event_line_id = event_line_response.json()["id"]

    task_id = create_task(
        client,
        title="P0 增强任务",
        desc="关联客户和事件线后应返回更强上下文。",
        client_id=client_id,
        event_line_id=event_line_id,
    )

    insert_judgment(
        client,
        judgment_id="judgment_task_enhanced_official",
        client_id=client_id,
        status="approved",
        authority_level="approved",
        summary="正式判断：当前主线是先完成会前判断与责任分配。",
    )

    response = client.get(
        f"/api/v1/tasks/{task_id}/page-context",
        params={"prompt": "这条任务下一步应该做什么？", "page": "task_ai"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["officialJudgments"]
    assert payload["stateProjection"]["taskHasClient"] is True
    assert payload["stateProjection"]["taskHasEventLine"] is True
    assert payload["quality"]["contextQuality"] in {"usable", "strong"}
    assert payload["answerPolicy"]["answerLevel"] != "insufficient"


def test_build_answer_material_filters_process_leak_markers():
    pack = PageContextPackRecord(
        page="workspace_chat",
        scopeType="client",
        scopeId="client_x",
        clientId="client_x",
        intent="status_progress",
        officialJudgments=[{"summary": "analysis-first 正式判断 [本周动作]"}],
        candidateJudgments=[{"summary": "候选判断包含 [缺失信息]"}],
        overlayJudgments=[],
        evidenceCards=[{"normalized_claim": "state_first_hit_rate 不应泄漏"}],
        rawEvidence=[{"title": "资料A", "excerpt": "candidate_leakage_count 是内部指标"}],
        openQuestions=[],
        conflicts=[],
        themeClusters=[],
        relatedTasks=[],
        relatedMeetings=[],
        relatedDocuments=[],
        notebookSummary=None,
        memoryFacts=[],
        contextPack=None,
        judgmentBundle=None,
        resolutionTrace=None,
        stateProjection=None,
        missingContext=[],
        boundaryNotes=[],
        sourceSummary={},
        answerPolicy=AnswerPolicyRecord(canAnswer=True, answerLevel="candidate", mustDiscloseCandidateBoundary=True),
        retrievalPlan={},
        quality=ContextQualityRecord(contextQuality="usable", canUseAnalysisFirst=True),
    )

    material = build_answer_material(pack)
    lowered = material.lower()
    assert "analysis-first" not in lowered
    assert "[本周动作]" not in material
    assert "[缺失信息]" not in material
    assert "state_first_hit_rate" not in lowered
    assert "candidate_leakage_count" not in lowered


def test_workspace_chat_ai_failure_still_returns_readable_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="P0 AI 失败兜底客户")
    insert_judgment(
        client,
        judgment_id="judgment_ai_failure_official",
        client_id=client_id,
        status="approved",
        authority_level="approved",
        summary="正式判断：当前可先按状态池给出下一步。",
    )
    create_task(client, title="P0 AI 失败任务", desc="用于 state-only fallback 验证", client_id=client_id)

    monkeypatch.setattr(
        app_main,
        "retrieve_knowledge_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("state-first query should not run retrieval here")),
    )
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_workspace_state_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AiInvocationError("qwen", "mock timeout")),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "接下来最重要的事情是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["content"]
    assert "traceback" not in payload["content"].lower()
    assert payload["stateAnswerSections"]["actions"]
    assert payload["fallbackPresentationMode"] in {"state_cards_only", "compact_user_answer", "full_answer"}

```
