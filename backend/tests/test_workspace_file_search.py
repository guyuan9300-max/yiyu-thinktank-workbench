from __future__ import annotations

from types import SimpleNamespace
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.models import AiStructuredResponse
from app.services.workspace_file_search import build_file_search_user_summary


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "workspace-file-search") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "workspace file search regression",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def enable_dc_primary(client: TestClient) -> None:
    db = client.app.state.app_state.db
    db.set_setting("workspace_chat_data_center_primary", "1")
    db.set_setting("workspace_chat_use_legacy_fallback", "0")


def wait_for_knowledge_ready(client: TestClient, client_id: str, *, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    payload: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/knowledge/status")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["pendingJobs"] == 0 and payload["runningJobs"] == 0 and payload["lastJobStatus"] not in {"queued", "running"}:
            return payload
        time.sleep(0.1)
    assert payload is not None
    return payload


def test_build_file_search_user_summary_uses_selected_hits():
    summary = build_file_search_user_summary(
        SimpleNamespace(
            hits=[
                SimpleNamespace(
                    title="候选资料",
                    excerpt="这是普通命中片段",
                    sourceType="document",
                    path="/tmp/a.md",
                    sectionLabel="正文",
                    score=0.5,
                ),
            ],
            selectedHits=[
                SimpleNamespace(
                    title="上次会议纪要",
                    excerpt="这里提到了行动项和下一步安排。",
                    sourceType="document",
                    path="/tmp/meeting.md",
                    sectionLabel="行动项",
                    score=0.9,
                ),
            ],
        )
    )
    assert "我找到了这些可能相关的资料" in summary
    assert "上次会议纪要" in summary
    assert "行动项" in summary
    assert "打开原文" in summary or "点击文件卡片打开原文" in summary


def test_workspace_file_search_hit_exposes_annotation_fields_and_reads_back_human_label(tmp_path: Path):
    client = make_client(tmp_path)
    enable_dc_primary(client)
    client_id = create_client_record(client, "workspace-file-search-annotations")

    file_path = tmp_path / "xinsheng-plan.md"
    file_path.write_text(
        "# 心盛计划资料\n心盛计划聚焦青年社群与品牌协同，本资料用于文件查找和原文定位测试。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200, imported.text
    wait_for_knowledge_ready(client, client_id)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "帮我找一下心盛计划原文"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}
    search_result = retrieval_summary.get("searchResult") or {}
    hits = search_result.get("selectedHits") or search_result.get("hits") or []
    assert retrieval_summary.get("workspaceWorkflow") == "file_search"
    assert hits

    first_hit = hits[0]
    annotation_id = first_hit.get("annotationId")
    assert annotation_id
    assert first_hit.get("humanLabel") in {None, "useful", "noise", "needs_review"}

    label_response = client.post(
        f"/api/v1/data-center/evidence-quality/{annotation_id}/label",
        json={"label": "useful"},
    )
    assert label_response.status_code == 200, label_response.text

    second_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "帮我找一下心盛计划原文"},
    )
    assert second_response.status_code == 200, second_response.text
    second_payload = second_response.json()
    second_search_result = (second_payload.get("retrievalSummary") or {}).get("searchResult") or {}
    second_hits = second_search_result.get("selectedHits") or second_search_result.get("hits") or []
    assert second_hits
    matching_hit = next((item for item in second_hits if item.get("annotationId") == annotation_id), None)
    assert matching_hit is not None
    assert matching_hit.get("humanLabel") == "useful"


def test_workspace_chat_business_question_with_baohan_does_not_route_to_file_search(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    enable_dc_primary(client)
    client_id = create_client_record(client, "workspace-route-tighten")

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

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个项目包含哪些核心模块"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get("retrievalSummary") or {}

    assert retrieval_summary.get("workspaceWorkflow") == "synthesis"
    assert retrieval_summary.get("generationMode") == "long_synthesis"
    assert called is True
