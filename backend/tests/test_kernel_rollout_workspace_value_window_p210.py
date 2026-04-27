from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.workspace_answer_value_diagnostics import build_workspace_answer_value_diagnostics  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / 'data')
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = 'rollout-window-p210') -> str:
    response = client.post(
        '/api/v1/clients',
        json={
            'name': name,
            'alias': name,
            'domain': '公益',
            'type': '战略陪伴',
            'intro': 'rollout window p210',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def _insert_message(client: TestClient, *, client_id: str, message_id: str, created_at: str, retry: bool) -> None:
    db = client.app.state.app_state.db
    thread_id = f'thread_rollout_window_{client_id}'
    if not db.fetchone('SELECT id FROM chat_threads WHERE id = ?', (thread_id,)):
        db.execute(
            'INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)',
            (thread_id, client_id, 'rollout window', created_at, created_at),
        )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json, status, created_at
        )
        VALUES(?, ?, 'assistant', ?, '{}', 'AI · test', 1, 'doubao',
               ?, 'sufficient', ?, '{"totalMs":320}', ?, '[]', 'success', ?)
        """,
        (
            message_id,
            thread_id,
            '回答',
            'grounded_fallback' if retry else 'grounded_answer',
            'llm_local_fallback_after_retry' if retry else None,
            to_json(
                {
                    'kernelPrimaryUsed': True,
                    'kernelPrimaryFallbackUsed': retry,
                    'answerQuality': {
                        'grade': 'fail' if retry else 'pass',
                        'officialBoundaryViolation': False,
                        'candidateAsOfficialRisk': False,
                    },
                    'workspaceAnswerFinalization': {
                        'content': '回答',
                        'answerMode': 'grounded_fallback' if retry else 'grounded_answer',
                        'userVisibleQualityStatus': 'needs_retry' if retry else 'ready',
                        'shouldShowRetryBanner': retry,
                        'qualityGrade': 'fail' if retry else 'pass',
                        'internalGenerationStatus': 'quality_passed',
                        'notes': [],
                    },
                    'kernelSelectedEvidenceCount': 2,
                }
            ),
            created_at,
        ),
    )


def test_kernel_rollout_workspace_value_window_p210_ignores_history_before_since(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)

    for index in range(10):
        _insert_message(
            client,
            client_id=client_id,
            message_id=f'bad_before_{index}',
            created_at='2026-04-22T08:00:00',
            retry=True,
        )
    for index in range(5):
        _insert_message(
            client,
            client_id=client_id,
            message_id=f'good_after_{index}',
            created_at='2026-04-22T10:00:00',
            retry=False,
        )

    diagnostics = build_workspace_answer_value_diagnostics(
        client.app.state.app_state.db,
        client_id=client_id,
        recent_messages=50,
        since='2026-04-22T09:00:00',
    )

    assert diagnostics['recentMessages'] == 5
    assert diagnostics['retryBannerWouldShowRate'] == 0.0
    assert diagnostics['readyOrUsableRate'] == 1.0

