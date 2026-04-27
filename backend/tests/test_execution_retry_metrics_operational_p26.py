from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import to_json
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "execution-retry-metrics-p26") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "execution retry metrics p26",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_proposal(client: TestClient, *, proposal_id: str, client_id: str) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, 'task_prep', 'execution_pending', 'medium', ?, ?, ?, ?, '[]', '[]', '{}', 'tester', 'tester', ?, NULL, NULL, ?, ?)
        """,
        (
            proposal_id,
            client_id,
            f"{proposal_id} title",
            f"{proposal_id} summary",
            f"{proposal_id} rationale",
            to_json([{"targetType": "client", "targetId": client_id, "label": "client"}]),
            now,
            now,
            now,
        ),
    )


def test_execution_retry_metrics_operational_p26(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db

    now = datetime.now().replace(microsecond=0)
    old = (now - timedelta(hours=6)).isoformat()
    now_iso = now.isoformat()

    insert_proposal(client, proposal_id="proposal_retry_metrics_p26_1", client_id=client_id)
    insert_proposal(client, proposal_id="proposal_retry_metrics_p26_2", client_id=client_id)
    insert_proposal(client, proposal_id="proposal_retry_metrics_p26_3", client_id=client_id)

    db.execute(
        """
        INSERT INTO execution_tickets(
            id, proposal_id, client_id, execution_type, status, payload_json, result_json,
            idempotency_key, retry_count, max_retries, last_error, last_attempt_at,
            error_message, executed_at, created_at, updated_at
        )
        VALUES('ticket_retry_metrics_p26_1', 'proposal_retry_metrics_p26_1', ?, 'task_prep', 'failed', '{}', '{}',
               'idem_1', 3, 3, 'task_create_failed', ?, 'task_create_failed', NULL, ?, ?)
        """,
        (client_id, now_iso, old, now_iso),
    )
    db.execute(
        """
        INSERT INTO execution_tickets(
            id, proposal_id, client_id, execution_type, status, payload_json, result_json,
            idempotency_key, retry_count, max_retries, last_error, last_attempt_at,
            error_message, executed_at, created_at, updated_at
        )
        VALUES('ticket_retry_metrics_p26_2', 'proposal_retry_metrics_p26_2', ?, 'meeting_followup', 'failed', '{}', '{}',
               'idem_2', 1, 3, 'invalid_payload', ?, 'invalid_payload', NULL, ?, ?)
        """,
        (client_id, now_iso, now_iso, now_iso),
    )
    db.execute(
        """
        INSERT INTO execution_tickets(
            id, proposal_id, client_id, execution_type, status, payload_json, result_json,
            idempotency_key, retry_count, max_retries, last_error, last_attempt_at,
            error_message, executed_at, created_at, updated_at
        )
        VALUES('ticket_retry_metrics_p26_3', 'proposal_retry_metrics_p26_3', ?, 'evidence_request', 'executed', '{}', '{}',
               'idem_3', 2, 3, NULL, ?, NULL, ?, ?, ?)
        """,
        (client_id, now_iso, now_iso, now_iso, now_iso),
    )
    db.execute(
        """
        INSERT INTO execution_ticket_logs(id, ticket_id, stage, status, message, payload_json, created_at)
        VALUES('log_retry_metrics_p26_1', 'ticket_retry_metrics_p26_1', 'execute_action', 'failed', 'boom', '{}', ?)
        """,
        (now_iso,),
    )

    response = client.get(f"/api/v1/data-center/execution-retry-metrics?clientId={client_id}&days=7")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload.get("totalTickets", 0) >= 3
    assert payload.get("failedTickets", 0) >= 2
    assert payload.get("retriedTickets", 0) >= 3
    assert payload.get("retryExhaustedTickets", 0) >= 1

    # P2.6 新增运营字段
    assert float(payload.get("retrySuccessRate") or 0.0) > 0.0
    assert float(payload.get("avgRetryCount") or 0.0) >= 1.0
    assert float(payload.get("oldestFailedTicketAgeHours") or 0.0) > 0.0

    failure_reason_topn = payload.get("failureReasonTopN") or []
    assert any(item.get("key") == "task_create_failed" for item in failure_reason_topn)
    failed_stage_topn = payload.get("failedStageTopN") or []
    assert any(item.get("key") == "execute_action" for item in failed_stage_topn)
    alerts = payload.get("alerts") or []
    assert alerts
