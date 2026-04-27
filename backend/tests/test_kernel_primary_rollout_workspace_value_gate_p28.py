from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json
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
            'intro': 'kernel rollout gate p28',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def _insert_message(client: TestClient, *, client_id: str, message_id: str, status: str):
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()
    thread_id = f'thread_rollout_p28_{client_id}'
    if not db.fetchone('SELECT id FROM chat_threads WHERE id = ?', (thread_id,)):
        db.execute(
            'INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)',
            (thread_id, client_id, 'rollout p28', now, now),
        )
    should_retry = status == 'needs_retry'
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json, status, created_at
        )
        VALUES(?, ?, 'assistant', ?, '{}', 'AI · test', 1, 'doubao',
               'grounded_answer', 'sufficient', NULL, '{"totalMs":320}', ?, '[]', 'success', ?)
        """,
        (
            message_id,
            thread_id,
            'rollout message',
            to_json(
                {
                    'kernelPrimaryUsed': True,
                    'kernelPrimaryFallbackUsed': False,
                    'answerQuality': {'grade': 'pass', 'officialBoundaryViolation': False, 'candidateAsOfficialRisk': False},
                    'workspaceAnswerFinalization': {
                        'content': '回答',
                        'answerMode': 'grounded_answer',
                        'userVisibleQualityStatus': status,
                        'shouldShowRetryBanner': should_retry,
                        'qualityGrade': 'pass' if not should_retry else 'warn',
                        'internalGenerationStatus': 'quality_passed',
                        'notes': [],
                    },
                    'factSlots': {'businessModules': ['资源支持'], 'strategyDirections': [], 'timeBoundary': '当前'},
                    'answerPresentation': {
                        'sections': [
                            {'title': '直接回答', 'content': '回答'},
                            {'title': '关键依据', 'items': ['证据A']},
                            {'title': '下一步建议', 'items': ['动作A']},
                        ],
                    },
                }
            ),
            now,
        ),
    )


def test_kernel_primary_rollout_workspace_value_gate_p28(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, 'rollout-value-gate-p28')

    started = client.post(
        '/api/v1/data-center/kernel-primary-rollout/start',
        json={'stage': 'stage_1_client', 'clientIds': [client_id], 'note': 'p28 test'},
    )
    assert started.status_code == 200, started.text
    run_id = started.json()['id']

    for index in range(1, 6):
        _insert_message(client, client_id=client_id, message_id=f'msg_retry_{index}', status='needs_retry')
    for index in range(1, 4):
        _insert_message(client, client_id=client_id, message_id=f'msg_ready_{index}', status='ready')

    completed = client.post(f'/api/v1/data-center/kernel-primary-rollout/{run_id}/complete')
    assert completed.status_code == 200, completed.text
    payload = completed.json()
    metrics_after = payload.get('metricsAfter') or {}

    assert 'workspaceReadyOrUsableRate' in metrics_after
    assert 'workspaceNeedsRetryRate' in metrics_after
    assert payload.get('verdict') == 'fail'
    assert payload.get('recommendedAction') == 'rollback'
