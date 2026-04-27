from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse, GenerationRuntimeDecisionRecord
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "runtime-record-p22") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "runtime recording p22",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_chat_runtime_recording_with_compact_and_long_retry(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    client.app.state.app_state.db.set_setting("workspace_chat_data_center_primary", "0")

    monkeypatch.setattr(
        app_main,
        "decide_generation_runtime_policy",
        lambda *_args, **_kwargs: GenerationRuntimeDecisionRecord(
            shouldAttemptLlm=True,
            shouldUseCompactFirst=True,
            shouldUseLocalOnly=False,
            shouldQueueLongAnswerRetry=True,
            shouldProbeAfterCooldown=False,
            reason="timeout_or_fallback_burst",
            cooldownActive=False,
        ),
    )
    monkeypatch.setattr(
        app_main,
        "retrieve_knowledge_bundle",
        lambda *_args, **_kwargs: RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_runtime_1",
                    chunk_id="chunk_runtime_1",
                    title="状态材料",
                    excerpt="当前推进重点是组织协同和项目交付。",
                    score=0.91,
                    coverage=0.81,
                    section_label="正文",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["推进", "重点"],
                    path="/tmp/runtime.md",
                )
            ],
            coverage=0.81,
            retrieval_summary={"rawChunkHitCount": 1, "masterHitCount": 1, "surrogateHitCount": 0},
            context_text="",
            matched_terms=["推进", "重点"],
            failure_reason=None,
        ),
    )

    def fake_generate_chat_response(*_args, **kwargs):
        max_tokens = kwargs.get("max_tokens")
        if isinstance(max_tokens, int) and max_tokens <= 380:
            return AiStructuredResponse(
                content="短答版本：先给你核心结论。",
                judgment="compact",
                analysis="short",
                actions="next",
                timeline="now",
            )
        return AiStructuredResponse(
            content="长答补充版本：这里是完整展开。",
            judgment="full",
            analysis="long",
            actions="next",
            timeline="later",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "请介绍当前推进情况"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    thread_id = payload["threadId"]
    answer_intent = str(payload.get("retrievalSummary", {}).get("answerIntent") or "general")

    for _ in range(30):
        detail = client.get(f"/api/v1/clients/{client_id}/workspace/chat/threads/{thread_id}")
        assert detail.status_code == 200, detail.text
        messages = detail.json()["messages"]
        if any("长答补充版本" in str(item.get("content") or "") for item in messages):
            break
        time.sleep(0.1)

    provider = client.app.state.app_state.ai.current_provider()
    model = client.app.state.app_state.ai.current_model()

    runtime = client.get(
        "/api/v1/runtime/generation-state",
        params={
            "clientId": client_id,
            "answerIntent": answer_intent,
            "provider": provider,
            "model": model,
        },
    )
    assert runtime.status_code == 200, runtime.text
    runtime_body = runtime.json()
    assert runtime_body["recentTotal"] >= 2
    assert runtime_body["provider"] == provider

    db = client.app.state.app_state.db
    empty_provider_rows = int(
        db.scalar(
            """
            SELECT COUNT(1) AS count
            FROM generation_runtime_state_v2
            WHERE client_id = ? AND answer_intent = ? AND provider = '' AND model = ''
            """,
            (client_id, answer_intent),
        )
        or 0
    )
    assert empty_provider_rows == 0
