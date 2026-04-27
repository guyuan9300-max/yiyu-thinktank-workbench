from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services import data_center_search
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "kernel-p1-client") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "kernel p1 test",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def duplicate_citation_bundle() -> RetrievalBundle:
    duplicated = CitationMatch(
        knowledge_document_id="kd_meeting",
        chunk_id="chunk_meeting",
        title="最近会议纪要",
        excerpt="最近一次会议明确了战略重点与后续动作。",
        score=0.78,
        coverage=0.55,
        section_label="会议纪要",
        source_stage="raw_chunk",
        drillthrough_used=True,
        matched_terms=["会议", "战略"],
        path="/tmp/meeting.md",
    )
    return RetrievalBundle(
        citations=[
            duplicated,
            CitationMatch(
                knowledge_document_id="kd_meeting",
                chunk_id="chunk_meeting",
                title="最近会议纪要",
                excerpt="最近一次会议明确了战略重点与后续动作。",
                score=0.91,
                coverage=0.35,
                section_label="会议纪要",
                source_stage="raw_chunk",
                drillthrough_used=True,
                matched_terms=["战略", "行动"],
                path="/tmp/meeting.md",
            ),
        ],
        coverage=0.9,
        retrieval_summary={"rawChunkHitCount": 2},
        context_text="会议材料",
        matched_terms=["会议", "战略", "行动"],
        failure_reason=None,
    )


def test_merge_citations_uses_coverage_field_for_duplicates():
    merged = data_center_search._merge_citations(duplicate_citation_bundle().citations)

    assert len(merged) == 1
    assert merged[0].score == pytest.approx(0.91)
    assert merged[0].coverage == pytest.approx(0.9)
    assert merged[0].matched_terms == ["会议", "战略", "行动"]


def test_data_center_resolve_answer_mode(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    response = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "CFFC 核心业务是什么？",
            "mode": "answer",
            "includeRawEvidence": False,
            "includeActionSuggestions": True,
            "shadow": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["scope"]["scopeId"] == client_id
    assert payload["answerPlan"] is not None
    assert payload["answerPlan"]["intent"] == "business_profile"


def test_data_center_resolve_search_mode_returns_search_result(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, name="kernel-p1-client-2")

    response = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "请检索最新材料",
            "mode": "search",
            "includeRawEvidence": False,
            "includeActionSuggestions": False,
            "shadow": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["searchResult"] is not None
    assert payload["searchResult"]["query"] == "请检索最新材料"
    assert "selectedHits" in payload["searchResult"]


def test_data_center_diagnose_endpoint(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, name="kernel-p1-client-3")

    response = client.get(
        "/api/v1/data-center/diagnose",
        params={
            "page": "workspace_chat",
            "clientId": client_id,
            "prompt": "日慈的最新战略是什么？",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["scope"]["clientId"] == client_id
    assert payload["debug"]["routeReason"]


def test_data_center_resolve_meeting_summary_handles_duplicate_bundle_citations(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client, name="kernel-p1-meeting-resolve")
    call_count = 0

    def fake_bundle(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return duplicate_citation_bundle()

    monkeypatch.setattr(data_center_search, "retrieve_knowledge_bundle", fake_bundle)

    response = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "帮我总结最近一次会议",
            "mode": "answer",
            "includeRawEvidence": False,
            "includeActionSuggestions": True,
            "shadow": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert call_count > 0
    assert payload["routeDecision"]["retrievalMode"] == "hybrid"
    assert payload["answerPlan"] is not None


def test_data_center_diagnose_meeting_summary_handles_duplicate_bundle_citations(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_client_record(client, name="kernel-p1-meeting-diagnose")
    call_count = 0

    def fake_bundle(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return duplicate_citation_bundle()

    monkeypatch.setattr(data_center_search, "retrieve_knowledge_bundle", fake_bundle)

    response = client.get(
        "/api/v1/data-center/diagnose",
        params={
            "page": "workspace_chat",
            "clientId": client_id,
            "prompt": "帮我总结最近一次会议",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert call_count > 0
    assert payload["routeDecision"]["retrievalMode"] == "hybrid"
    assert payload["debug"]["routeReason"] == "meeting_summary_rule"
