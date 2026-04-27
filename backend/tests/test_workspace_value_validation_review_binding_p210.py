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


def create_client_record(client: TestClient, name: str = 'session-binding-p210') -> str:
    response = client.post(
        '/api/v1/clients',
        json={
            'name': name,
            'alias': name,
            'domain': '公益',
            'type': '战略陪伴',
            'intro': 'session binding p210',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def _create_review(client: TestClient, client_id: str, message_id: str) -> dict[str, object]:
    response = client.post(
        '/api/v1/workspace-answer-value-reviews',
        json={
            'clientId': client_id,
            'messageId': message_id,
            'prompt': '验证问题',
            'answerMode': 'grounded_answer',
            'userVisibleQualityStatus': 'ready',
            'shouldShowRetryBanner': False,
            'usableAnswer': True,
            'manualBaselineMinutes': 18,
            'dataCenterReviewMinutes': 6,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_workspace_value_validation_review_binding_p210_rejects_mismatched_review(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    session = client.post('/api/v1/workspace-value-validation-sessions', json={'clientId': client_id}).json()
    review = _create_review(client, client_id, 'msg_review')
    question = session['questionSet'][0]

    completed = client.post(
        f"/api/v1/workspace-value-validation-sessions/{session['id']}/complete-question",
        json={
            'questionId': question['id'],
            'reviewId': review['id'],
            'messageId': 'msg_other',
        },
    )

    assert completed.status_code == 409
    assert completed.json()['detail'] == 'review_message_question_mismatch'


def test_workspace_value_validation_review_binding_p210_rejects_reusing_same_review(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, 'session-binding-reuse-p210')

    session = client.post('/api/v1/workspace-value-validation-sessions', json={'clientId': client_id}).json()
    review = _create_review(client, client_id, 'msg_review')
    first_question = session['questionSet'][0]
    second_question = session['questionSet'][1]

    first = client.post(
        f"/api/v1/workspace-value-validation-sessions/{session['id']}/complete-question",
        json={
            'questionId': first_question['id'],
            'reviewId': review['id'],
            'messageId': review['messageId'],
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/workspace-value-validation-sessions/{session['id']}/complete-question",
        json={
            'questionId': second_question['id'],
            'reviewId': review['id'],
            'messageId': review['messageId'],
        },
    )

    assert second.status_code == 409
    assert second.json()['detail'] == 'review_message_question_mismatch'

