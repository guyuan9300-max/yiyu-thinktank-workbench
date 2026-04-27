from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / 'data')
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = 'workspace-action-card-p29') -> str:
    response = client.post(
        '/api/v1/clients',
        json={
            'name': name,
            'alias': name,
            'domain': '公益',
            'type': '战略陪伴',
            'intro': 'workspace action card p29',
            'stage': '推进中',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()['id']


def _seed_message(client: TestClient, *, client_id: str, message_id: str, action_cards: list[dict[str, object]]):
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()
    thread_id = f'thread_{client_id}'
    if not db.fetchone('SELECT id FROM chat_threads WHERE id = ?', (thread_id,)):
        db.execute(
            'INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, ?, ?, ?)',
            (thread_id, client_id, 'workspace action card thread', now, now),
        )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, llm_invoked, provider_used,
            answer_mode, evidence_status, failure_reason, timing_json, retrieval_summary_json, evidence_json, status, created_at
        )
        VALUES(?, ?, 'assistant', ?, '{}', 'AI · test', 1, 'doubao',
               'grounded_answer', 'sufficient', NULL, '{"totalMs":120}', ?, '[]', 'success', ?)
        """,
        (
            message_id,
            thread_id,
            '回答',
            to_json(
                {
                    'workspaceAnswerExperience': {
                        'status': 'ready',
                        'headline': '已形成可用回答',
                        'directAnswer': '回答',
                        'actionCards': action_cards,
                    }
                }
            ),
            now,
        ),
    )


def test_workspace_answer_action_cards_p29_create_proposal_and_task(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    _seed_message(
        client,
        client_id=client_id,
        message_id='msg_action_1',
        action_cards=[
            {'actionType': 'create_proposal', 'title': '生成提案', 'summary': '基于当前回答生成提案', 'riskLevel': 'low'},
            {'actionType': 'create_task', 'title': '创建任务', 'summary': '把下一步落为任务', 'riskLevel': 'low'},
            {'actionType': 'request_evidence', 'title': '请求补证据', 'summary': '补齐关键材料', 'riskLevel': 'low'},
        ],
    )

    proposal = client.post('/api/v1/workspace-answer-action-cards/msg_action_1/create-proposal')
    assert proposal.status_code == 200, proposal.text
    proposal_payload = proposal.json()
    assert proposal_payload['draftId']
    assert proposal_payload['autoApproved'] is False
    assert proposal_payload['autoExecuted'] is False

    evidence = client.post('/api/v1/workspace-answer-action-cards/msg_action_1/request-evidence')
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()['draftId']
    assert evidence.json()['autoExecuted'] is False

    task = client.post('/api/v1/workspace-answer-action-cards/msg_action_1/create-task')
    assert task.status_code == 200, task.text
    task_payload = task.json()
    assert task_payload['taskId']
    db = client.app.state.app_state.db
    row = db.fetchone('SELECT source_type, source_id FROM tasks WHERE id = ?', (task_payload['taskId'],))
    assert row is not None
    assert row['source_type'] == 'workspace_answer_action'
    assert row['source_id'] == 'msg_action_1'
