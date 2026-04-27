from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "shadow-chat-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "shadow chat test",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def build_retrieval_bundle() -> RetrievalBundle:
    citations = [
        CitationMatch(
            knowledge_document_id="kd_shadow_1",
            chunk_id="chunk_shadow_1",
            title="shadow 资料 1",
            excerpt="该客户当前推进到执行协调阶段，下一步需要确认负责人。",
            score=0.92,
            coverage=0.83,
            section_label="正文",
            source_stage="raw_chunk",
            drillthrough_used=True,
            matched_terms=["推进", "负责人"],
            path="/tmp/shadow_1.md",
        ),
        CitationMatch(
            knowledge_document_id="kd_shadow_2",
            chunk_id="chunk_shadow_2",
            title="shadow 资料 2",
            excerpt="最近会议纪要要求先补齐证据，再推进周计划。",
            score=0.88,
            coverage=0.83,
            section_label="会议纪要",
            source_stage="raw_chunk",
            drillthrough_used=True,
            matched_terms=["会议", "证据"],
            path="/tmp/shadow_2.md",
        ),
    ]
    return RetrievalBundle(
        citations=citations,
        coverage=0.83,
        retrieval_summary={
            "masterHitCount": 2,
            "surrogateHitCount": 2,
            "rawChunkHitCount": 2,
        },
        context_text="",
        matched_terms=["推进", "会议"],
        failure_reason=None,
    )


def test_shadow_mode_keeps_answer_and_records_shadow_run(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: build_retrieval_bundle())
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="当前推进已进入执行协调阶段，建议先确认负责人与截止时间。",
            judgment="回答来自状态池与原文证据混合路径。",
            analysis="已引用会议纪要与任务资料。",
            actions="先补齐负责人，再确认时间线。",
            timeline="本周内完成对齐。",
        ),
    )

    settings_resp = client.post(
        "/api/v1/retrieval/settings",
        json={
            "embeddingProvider": "local_fastembed",
            "embeddingModel": "BAAI/bge-small-zh-v1.5",
            "embeddingDimension": 256,
            "embeddingMode": "local",
            "routerEnabled": True,
            "routerProvider": "rules",
            "routerModel": "",
            "rerankEnabled": True,
            "rerankProvider": "rules",
            "shadowMode": True,
        },
    )
    assert settings_resp.status_code == 200, settings_resp.text

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户现在推进到哪了，上次会议说了什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert "执行协调阶段" in payload["content"]
    summary = payload["retrievalSummary"]
    assert summary["shadowMode"] is True
    assert "routeDecision" in summary
    assert "retrievalTrace" in summary
    assert "answerIntent" in summary
    assert "retrievalDecisionReason" in summary
    assert "embeddingSignature" in summary

    shadow_runs_resp = client.get("/api/v1/retrieval/shadow-runs", params={"clientId": client_id})
    assert shadow_runs_resp.status_code == 200, shadow_runs_resp.text
    runs = shadow_runs_resp.json()
    assert runs
    assert runs[0]["clientId"] == client_id
    assert "baselineSummary" in runs[0]
    assert "candidateSummary" in runs[0]
