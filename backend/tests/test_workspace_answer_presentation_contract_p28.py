from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / 'data')
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        '/api/v1/clients',
        json={
            'name': name,
            'alias': name,
            'domain': '公益',
            'type': '战略陪伴',
            'intro': 'workspace answer presentation p28',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def test_workspace_answer_presentation_contract_p28(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client.app.state.app_state.db.set_setting('workspace_chat_data_center_primary', '1')
    client.app.state.app_state.db.set_setting('workspace_chat_use_legacy_fallback', '0')
    client_id = create_client_record(client, 'workspace-answer-presentation-p28')

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        'generate_chat_response',
        lambda *_args, **_kwargs: AiStructuredResponse(
            content='客户当前核心业务聚焦资源支持与项目执行，下一步建议先确认负责人和资料缺口。',
            judgment='ok',
            analysis='ok',
            actions='ok',
            timeline='ok',
        ),
    )
    monkeypatch.setattr(
        app_main,
        'validate_answer_quality',
        lambda **_kwargs: {
            'hasDirectAnswer': True,
            'evidenceListOnly': False,
            'evidenceQuoteOnly': False,
            'leakedInternalMarkers': [],
            'candidateAsOfficialRisk': False,
            'officialBoundaryViolation': False,
            'missingRawEvidenceForIntent': False,
            'offTopicRisk': False,
            'factSlotHit': True,
            'factSlotMissingReason': None,
            'grade': 'pass',
            'reason': 'unit-test',
        },
    )

    response = client.post(f'/api/v1/clients/{client_id}/workspace/chat', json={'prompt': '核心业务和下一步建议是什么？'})
    assert response.status_code == 200, response.text
    payload = response.json()
    retrieval_summary = payload.get('retrievalSummary') or {}
    presentation = retrieval_summary.get('answerPresentation') or {}
    sections = presentation.get('sections') or []

    assert isinstance(sections, list)
    titles = {section.get('title') for section in sections if isinstance(section, dict)}
    assert '直接回答' in titles
    assert len({'关键依据', '边界与待确认', '下一步建议'} & titles) >= 2
