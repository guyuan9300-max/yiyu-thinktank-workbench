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


def create_client_record(client: TestClient, name: str = "answer-quality-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "answer quality p1",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _bundle(title: str, excerpt: str) -> RetrievalBundle:
    citations = [
        CitationMatch(
            knowledge_document_id="kd_1",
            chunk_id="chunk_1",
            title=title,
            excerpt=excerpt,
            score=0.92,
            coverage=0.86,
            section_label="正文",
            source_stage="raw_chunk",
            drillthrough_used=True,
            matched_terms=["业务", "战略"],
            path="/tmp/source.md",
        )
    ]
    return RetrievalBundle(
        citations=citations,
        coverage=0.86,
        retrieval_summary={"rawChunkHitCount": 1, "masterHitCount": 1, "surrogateHitCount": 1},
        context_text="",
        matched_terms=["业务", "战略"],
        failure_reason=None,
    )


def test_business_question_answer_quality(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: _bundle("CFFC 业务介绍", "CFFC 核心业务包括平台建设与资源支持。"))
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="基于当前资料，CFFC 核心业务集中在平台建设、资源支持与行业协作三条主线。",
            judgment="该结论由原文与状态信息共同支撑。",
            analysis="已覆盖业务结构和证据边界。",
            actions="建议补齐最新季度会议佐证。",
            timeline="本周可完成复核。",
        ),
    )

    response = client.post(f"/api/v1/clients/{client_id}/workspace/chat", json={"prompt": "CFFC 核心业务是什么？"})
    assert response.status_code == 200, response.text
    payload = response.json()

    summary = payload["retrievalSummary"]
    assert summary["answerPlan"]["intent"] == "business_profile"
    assert summary["answerQuality"]["evidenceListOnly"] is False
    assert "RouteDecision" not in payload["content"]
    assert "embeddingSignature" not in payload["content"]
    assert len(payload["content"][:200].strip()) >= 20


def test_strategy_question_answer_quality(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client, name="strategy-client")

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: _bundle("日慈战略纪要", "当前资料能确认，日慈战略重点是心理健康服务与组织协同。"))
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="当前资料能确认，日慈的战略方向是以心理健康服务为核心，配合组织协同与阶段计划推进。",
            judgment="战略判断来自会议纪要与文档证据。",
            analysis="已给出边界与待确认项。",
            actions="建议确认 2026 年执行节奏与责任人。",
            timeline="下次评审前补齐。",
        ),
    )

    response = client.post(f"/api/v1/clients/{client_id}/workspace/chat", json={"prompt": "日慈的最新战略是什么？"})
    assert response.status_code == 200, response.text
    payload = response.json()
    summary = payload["retrievalSummary"]

    assert summary["answerPlan"]["intent"] == "strategy_profile"
    assert summary["routeDecision"]["shouldUseRawEvidence"] is True
    assert "当前资料能确认" in payload["content"]
    assert any(token in payload["content"] for token in ("战略", "方向", "重点"))
