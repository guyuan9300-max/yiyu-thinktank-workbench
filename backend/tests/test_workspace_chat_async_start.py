from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.services import data_center_search
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "workspace-async") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "workspace async regression",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def enable_dc_primary(client: TestClient) -> None:
    db = client.app.state.app_state.db
    db.set_setting("workspace_chat_data_center_primary", "1")
    db.set_setting("workspace_chat_use_legacy_fallback", "0")


def wait_for_async_message(client: TestClient, client_id: str, message_id: str, *, timeout: float = 45.0) -> dict:
    deadline = time.time() + timeout
    payload: dict | None = None
    placeholder_contents = {
        "庆华正在整理背景材料，并组织分析答案……",
        "数据中心主链已就绪，正在组织回答……",
    }
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/workspace/chat/messages/{message_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        content = str(payload.get("content") or "").strip()
        if payload["status"] == "success" and content not in placeholder_contents:
            return payload
        time.sleep(0.1)
    assert payload is not None
    return payload


def wait_for_analysis_run(client: TestClient, client_id: str, run_id: str, *, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    payload: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/analysis-runs/{run_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in {"completed", "failed", "canceled"}:
            return payload
        time.sleep(0.1)
    assert payload is not None
    return payload


def duplicate_citation_bundle() -> RetrievalBundle:
    return RetrievalBundle(
        citations=[
            CitationMatch(
                knowledge_document_id="kd_async_meeting",
                chunk_id="chunk_async_meeting",
                title="会议纪要",
                excerpt="最近一次会议要求先收口战略，再推进执行计划。",
                score=0.82,
                coverage=0.5,
                section_label="会议",
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=["会议", "战略"],
                path="/tmp/meeting_async.md",
            ),
            CitationMatch(
                knowledge_document_id="kd_async_meeting",
                chunk_id="chunk_async_meeting",
                title="会议纪要",
                excerpt="最近一次会议要求先收口战略，再推进执行计划。",
                score=0.9,
                coverage=0.4,
                section_label="会议",
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=["战略", "执行"],
                path="/tmp/meeting_async.md",
            ),
        ],
        coverage=0.9,
        retrieval_summary={"rawChunkHitCount": 2},
        context_text="会议材料",
        matched_terms=["会议", "战略", "执行"],
        failure_reason=None,
    )


def intro_profile_bundle() -> RetrievalBundle:
    return RetrievalBundle(
        citations=[
            CitationMatch(
                knowledge_document_id="kd_intro_async_1",
                chunk_id="chunk_intro_async_1",
                title="日慈使命愿景价值观",
                excerpt="使命是构建普惠的关系支持系统，让孩子与青年在真实关系中获得理解、练习与支持。我们不是在拯救有问题的个体，而是在搭建一个大多数孩子都能用得上的关系保护网。",
                score=0.96,
                coverage=0.88,
                section_label="正文",
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=["关系支持系统", "关系保护网"],
                path="/tmp/rici-mission.md",
            ),
            CitationMatch(
                knowledge_document_id="kd_intro_async_2",
                chunk_id="chunk_intro_async_2",
                title="日慈战略陪伴工作坊2天结构",
                excerpt="这两天不是四段拼盘，而是一条连续叙事：我们是谁、为什么这样做、怎么把系统跑起来、每条业务线怎样更有积累。今年战略重点是把树放进系统/飞轮。",
                score=0.92,
                coverage=0.84,
                section_label="正文",
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=["飞轮", "系统"],
                path="/tmp/rici-workshop.md",
            ),
            CitationMatch(
                knowledge_document_id="kd_intro_async_3",
                chunk_id="chunk_intro_async_3",
                title="日慈工作坊数字化设计规划",
                excerpt="数字化的目标不是单纯上工具，而是让价值可被证明、让经验可被复用，并逐步沉淀流程、工具和数据价值。",
                score=0.9,
                coverage=0.82,
                section_label="正文",
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=["数字化", "经验可被复用"],
                path="/tmp/rici-digital.md",
            ),
            CitationMatch(
                knowledge_document_id="kd_intro_async_4",
                chunk_id="chunk_intro_async_4",
                title="心灵魔法学院项目介绍",
                excerpt="项目从预防视角出发，通过赋能在地教师，为其提供主题式、体验式、标准化的课程资料及配套培训，支持教师在学期内开展心理主题活动。",
                score=0.94,
                coverage=0.86,
                section_label="正文",
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=["预防视角", "标准化课程资料"],
                path="/tmp/rici-academy.md",
            ),
            CitationMatch(
                knowledge_document_id="kd_intro_async_5",
                chunk_id="chunk_intro_async_5",
                title="心盛计划项目介绍",
                excerpt="心盛计划围绕青年小组、沙龙、关怀员培养与社群运营展开，同时牵动内容协同和品牌建设，是面向青年群体的重要业务线。",
                score=0.91,
                coverage=0.83,
                section_label="正文",
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=["心盛计划", "青年群体"],
                path="/tmp/rici-youth.md",
            ),
        ],
        coverage=0.92,
        retrieval_summary={"rawChunkHitCount": 5, "masterHitCount": 5, "surrogateHitCount": 0},
        context_text="",
        matched_terms=["关系支持系统", "飞轮", "数字化", "心盛计划"],
        failure_reason=None,
    )


def test_no_stale_build_evidence_summary_call():
    backend_root = Path(__file__).resolve().parents[1]
    bad_hits: list[str] = []
    for path in (backend_root / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "build_evidence_summary(" in line and "def build_evidence_summary" not in line:
                bad_hits.append(f"{path}:{line.strip()}")
    assert not bad_hits, bad_hits


def test_workspace_chat_start_no_build_evidence_summary_name_error(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    enable_dc_primary(client)
    client_id = create_client_record(client, "async-name-error-regression")

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="这是异步路径下保留下来的回答。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        ),
    )

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "介绍一下这个客户"},
    )
    assert started.status_code == 200, started.text
    start_payload = started.json()
    message_id = start_payload["assistantMessage"]["id"]
    run_id = start_payload["analysisRun"]["id"]

    message = wait_for_async_message(client, client_id, message_id)
    run_payload = wait_for_analysis_run(client, client_id, run_id)
    retrieval_summary = message.get("retrievalSummary") or {}

    assert retrieval_summary.get("dataCenterPrimaryEnabled") is True
    assert retrieval_summary.get("kernelResultUsed") is True
    assert retrieval_summary.get("fallbackTemplateUsed") is False
    assert "build_evidence_summary" not in (message.get("failureReason") or "")
    assert "build_evidence_summary" not in json.dumps(retrieval_summary, ensure_ascii=False)
    assert run_payload["status"] == "completed"


def test_workspace_chat_start_preserves_successful_answer_on_post_finalize_error(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    enable_dc_primary(client)
    client_id = create_client_record(client, "async-post-finalize-warning")

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="成功回答正文：这是已经写入的回答。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        ),
    )

    def _raise_post_finalize(*_args, **_kwargs):
        raise RuntimeError("post finalize log failed")

    monkeypatch.setattr(app_main, "_schedule_chat_fact_extraction", _raise_post_finalize)

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "介绍一下这个客户"},
    )
    assert started.status_code == 200, started.text
    start_payload = started.json()
    message_id = start_payload["assistantMessage"]["id"]
    run_id = start_payload["analysisRun"]["id"]

    message = wait_for_async_message(client, client_id, message_id)
    run_payload = wait_for_analysis_run(client, client_id, run_id)
    retrieval_summary = message.get("retrievalSummary") or {}

    assert message["answerMode"] != "system_failure"
    assert "成功回答正文" in message["content"]
    assert retrieval_summary.get("postFinalizeWarningCount", 0) >= 1
    warnings = retrieval_summary.get("postFinalizeWarnings") or []
    assert warnings
    assert any("chat_fact_extraction" == warning.get("stage") for warning in warnings if isinstance(warning, dict))
    assert run_payload["status"] == "completed"
    assert run_payload["phase"] == "completed"


def test_workspace_chat_start_file_search_workflow_does_not_call_llm(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    enable_dc_primary(client)
    client_id = create_client_record(client, "async-file-search")

    called = False

    def _fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("LLM should not be called for file_search")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_raw_evidence_response", _fail_if_called)

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "帮我找一下上次会议纪要原文"},
    )
    assert started.status_code == 200, started.text
    start_payload = started.json()
    message_id = start_payload["assistantMessage"]["id"]

    message = wait_for_async_message(client, client_id, message_id)
    retrieval_summary = message.get("retrievalSummary") or {}

    assert retrieval_summary.get("workspaceWorkflow") == "file_search"
    assert retrieval_summary.get("generationMode") == "no_generation"
    assert called is False


def test_workspace_chat_start_business_question_with_baohan_stays_synthesis(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    enable_dc_primary(client)
    client_id = create_client_record(client, "async-route-tighten")

    called = False

    def _return_answer(*_args, **_kwargs):
        nonlocal called
        called = True
        return AiStructuredResponse(
            content="这是正常综合回答。",
            judgment="ok",
            analysis="ok",
            actions="ok",
            timeline="ok",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_raw_evidence_response", _return_answer)

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "教师赋能项目要试点的预防加干预综合服务模式，具体包含哪些面向教师和学生的落地服务内容？"},
    )
    assert started.status_code == 200, started.text
    start_payload = started.json()
    message_id = start_payload["assistantMessage"]["id"]

    message = wait_for_async_message(client, client_id, message_id)
    retrieval_summary = message.get("retrievalSummary") or {}

    assert retrieval_summary.get("workspaceWorkflow") == "synthesis"
    assert retrieval_summary.get("generationMode") == "long_synthesis"
    assert called is True


def test_workspace_chat_start_meeting_summary_handles_duplicate_bundle_citations(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    enable_dc_primary(client)
    client_id = create_client_record(client, "async-meeting-duplicate-citations")
    call_count = 0

    def fake_bundle(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return duplicate_citation_bundle()

    monkeypatch.setattr(data_center_search, "retrieve_knowledge_bundle", fake_bundle)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="最近一次会议的核心结论已经整理完成。",
            judgment="会议结论已基于原始材料整理。",
            analysis="重复 citation 已被共享内核正确合并。",
            actions="下一步推进执行计划。",
            timeline="本周内可继续跟进。",
        ),
    )

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "帮我总结最近一次会议"},
    )
    assert started.status_code == 200, started.text
    start_payload = started.json()
    message_id = start_payload["assistantMessage"]["id"]
    run_id = start_payload["analysisRun"]["id"]

    message = wait_for_async_message(client, client_id, message_id)
    run_payload = wait_for_analysis_run(client, client_id, run_id)
    retrieval_summary = message.get("retrievalSummary") or {}

    assert call_count > 0
    assert run_payload["status"] == "completed"
    assert message["answerMode"] != "system_failure"
    assert "核心结论已经整理完成" in message["content"]
    assert retrieval_summary.get("kernelResultUsed") is True
    assert retrieval_summary.get("fallbackTemplateUsed") is False


def test_workspace_chat_start_intro_timeout_does_not_use_profile_fallback(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    enable_dc_primary(client)
    client_id = create_client_record(client, "日慈基金会")

    monkeypatch.setattr(data_center_search, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: intro_profile_bundle())
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_raw_evidence_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AiInvocationError("doubao", "The read operation timed out")),
    )

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "介绍日慈基金会"},
    )
    assert started.status_code == 200, started.text
    start_payload = started.json()
    message_id = start_payload["assistantMessage"]["id"]
    run_id = start_payload["analysisRun"]["id"]

    message = wait_for_async_message(client, client_id, message_id)
    run_payload = wait_for_analysis_run(client, client_id, run_id)
    retrieval_summary = message.get("retrievalSummary") or {}
    content = message.get("content") or ""

    assert message["status"] == "success"
    assert message["answerMode"] == "system_failure"
    assert retrieval_summary.get("finalFailureStage") in {
        "raw_evidence_generation_failed",
        "primary_generation_exception",
    }
    assert retrieval_summary.get("compactRetryAttempted") is False
    assert retrieval_summary.get("llmErrorKind") in {"read_timeout", "unknown"}
    assert "2）日慈的核心方法：教育现场 + 数据与路径 + 生态协作" not in content
    assert "3）日慈的主要项目与业务板块（你可以把它理解为三条业务线）" not in content
    assert "5）日慈的优势可以用一句话总结" not in content
