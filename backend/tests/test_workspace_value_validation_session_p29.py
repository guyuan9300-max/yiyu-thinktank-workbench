from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / 'data')
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = 'workspace-value-session-p29') -> str:
    response = client.post(
        '/api/v1/clients',
        json={
            'name': name,
            'alias': name,
            'domain': '公益',
            'type': '战略陪伴',
            'intro': 'workspace value session p29',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def test_workspace_value_validation_session_p29_lifecycle(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    created = client.post('/api/v1/workspace-value-validation-sessions', json={'clientId': client_id})
    assert created.status_code == 200, created.text
    session = created.json()
    assert session['status'] == 'running'
    assert len(session['questionSet']) == 10

    review = client.post(
        '/api/v1/workspace-answer-value-reviews',
        json={
            'clientId': client_id,
            'messageId': 'msg_1',
            'prompt': '这个客户是谁？',
            'answerMode': 'grounded_answer',
            'userVisibleQualityStatus': 'ready',
            'shouldShowRetryBanner': False,
            'usableAnswer': True,
            'manualBaselineMinutes': 20,
            'dataCenterReviewMinutes': 8,
            'reviewerNote': '可直接使用',
        },
    )
    assert review.status_code == 200, review.text
    review_payload = review.json()

    next_question = session['questionSet'][0]
    completed = client.post(
        f"/api/v1/workspace-value-validation-sessions/{session['id']}/complete-question",
        json={
            'questionId': next_question['id'],
            'reviewId': review_payload['id'],
            'messageId': 'msg_1',
            'usableAnswer': True,
            'retryBannerShown': False,
            'manualBaselineMinutes': 20,
            'dataCenterReviewMinutes': 8,
            'reviewerNote': '可直接使用',
        },
    )
    assert completed.status_code == 200, completed.text
    completed_payload = completed.json()
    assert next_question['id'] in completed_payload['completedQuestionIds']
    assert completed_payload['summary']['completed'] == 1
    assert completed_payload['summary']['usableAnswerRate'] == 1.0
    assert completed_payload['summary']['estimatedTimeSavedRate'] > 0

    finished = client.post(f"/api/v1/workspace-value-validation-sessions/{session['id']}/finish")
    assert finished.status_code == 200, finished.text
    assert finished.json()['status'] == 'completed'
