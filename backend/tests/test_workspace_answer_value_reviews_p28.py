from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


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
            'intro': 'workspace value review p28',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def test_workspace_answer_value_reviews_upsert_and_summary_p28(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, 'workspace-review-upsert-p28')

    first = client.post(
        '/api/v1/workspace-answer-value-reviews',
        json={
            'clientId': client_id,
            'messageId': 'msg_same',
            'prompt': '核心业务是什么？',
            'answerMode': 'grounded_answer',
            'userVisibleQualityStatus': 'ready',
            'shouldShowRetryBanner': False,
            'usableAnswer': True,
            'manualBaselineMinutes': 20,
            'dataCenterReviewMinutes': 8,
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        '/api/v1/workspace-answer-value-reviews',
        json={
            'clientId': client_id,
            'messageId': 'msg_same',
            'prompt': '核心业务是什么？',
            'answerMode': 'grounded_answer',
            'userVisibleQualityStatus': 'usable_with_boundary',
            'shouldShowRetryBanner': False,
            'usableAnswer': False,
            'reviewerNote': '需要补资料边界',
            'manualBaselineMinutes': 24,
            'dataCenterReviewMinutes': 12,
        },
    )
    assert second.status_code == 200, second.text

    listed = client.get(f'/api/v1/workspace-answer-value-reviews?clientId={client_id}&limit=10')
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len([row for row in rows if row['messageId'] == 'msg_same']) == 1

    summary = client.get(f'/api/v1/workspace-answer-value-summary?clientId={client_id}')
    assert summary.status_code == 200, summary.text
    payload = summary.json()
    assert payload['reviewCount'] == 1
    assert 'positiveReviewCount' in payload
    assert 'negativeReviewCount' in payload
    assert 'lastReviewedAt' in payload
