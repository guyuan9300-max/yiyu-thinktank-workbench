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


def create_client_record(client: TestClient, name: str = 'workspace-failure-pool-p29') -> str:
    response = client.post(
        '/api/v1/clients',
        json={
            'name': name,
            'alias': name,
            'domain': '公益',
            'type': '战略陪伴',
            'intro': 'workspace quality failure pool p29',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def test_workspace_answer_quality_failure_pool_p29_records_negative_review_and_resolve(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    review = client.post(
        '/api/v1/workspace-answer-value-reviews',
        json={
            'clientId': client_id,
            'messageId': 'msg_failure_1',
            'prompt': '最新战略是什么？',
            'answerMode': 'grounded_answer',
            'userVisibleQualityStatus': 'needs_retry',
            'shouldShowRetryBanner': True,
            'usableAnswer': False,
            'reviewerNote': '回答不可用',
        },
    )
    assert review.status_code == 200, review.text

    failures = client.get(f'/api/v1/workspace-answer-quality-failures?clientId={client_id}&limit=20')
    assert failures.status_code == 200, failures.text
    rows = failures.json()
    failure_types = {row['failureType'] for row in rows}
    assert 'retry_banner' in failure_types
    assert 'user_marked_not_usable' in failure_types

    target = rows[0]
    resolved = client.post(f"/api/v1/workspace-answer-quality-failures/{target['id']}/resolve", json={'note': '已处理'})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()['status'] == 'resolved'
