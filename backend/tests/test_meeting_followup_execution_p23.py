from __future__ import annotations

import sys
from datetime import datetime
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


def create_client_record(client: TestClient, name: str = "meeting-followup-exec-p23") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "meeting followup execute p23",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_meeting_followup_execution_creates_tasks_without_judgment_override(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db
    now = datetime.now().replace(microsecond=0).isoformat()

    db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence, created_at, updated_at
        ) VALUES(?, ?, 'client', ?, ?, 1, 'draft', ?, '[]', NULL, 'medium', 'medium', ?, ?)
        """,
        ("jv_p23_meeting", client_id, client_id, "会议后判断待复核", "候选判断：待复核", now, now),
    )
    approved_before = int(db.scalar("SELECT COUNT(1) AS count FROM judgment_versions WHERE status = 'approved'") or 0)

    db.execute(
        """
        INSERT INTO proposal_records(
            id, client_id, kind, status, risk_level, title, summary, rationale,
            target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            created_by, decided_by, decided_at, rejected_reason, execution_ticket_id, created_at, updated_at
        )
        VALUES(?, ?, 'meeting_followup', 'approved', 'medium', ?, ?, ?, ?, '[]', '[]', ?, 'tester', NULL, NULL, NULL, NULL, ?, ?)
        """,
        (
            "proposal_meeting_followup_exec",
            client_id,
            "会后跟进：确认资源清单",
            "根据会议行动项执行会后跟进。",
            "需人工跟进并记录进度。",
            to_json([{"targetType": "client", "targetId": client_id, "label": "client"}]),
            to_json(
                {
                    "meetingId": "meeting_demo",
                    "actionItems": [
                        {"id": "act_a", "title": "确认资源清单", "summary": "本周内完成资源清单确认"},
                        {"id": "act_b", "title": "对齐负责人", "summary": "明确负责人和截止时间"},
                    ],
                }
            ),
            now,
            now,
        ),
    )

    create_ticket = client.post(
        "/api/v1/proposals/proposal_meeting_followup_exec/execution-ticket",
        json={"requestedBy": "tester"},
    )
    assert create_ticket.status_code == 200, create_ticket.text
    ticket = create_ticket.json().get("executionTicket") or {}
    assert ticket.get("status") == "pending"

    execute = client.post(
        f"/api/v1/execution-tickets/{ticket['id']}/execute",
        json={"requestedBy": "tester"},
    )
    assert execute.status_code == 200, execute.text
    payload = execute.json()
    executed_ticket = payload.get("executionTicket") or {}
    assert executed_ticket.get("status") == "executed"
    created_task_ids = (executed_ticket.get("result") or {}).get("createdTaskIds") or []
    assert len(created_task_ids) >= 1
    assert payload["proposal"]["status"] == "executed"

    created_task_count = int(
        db.scalar(
            """
            SELECT COUNT(1) AS count
            FROM tasks
            WHERE source_type = 'data_center_meeting_followup' AND source_id = 'proposal_meeting_followup_exec'
            """
        )
        or 0
    )
    assert created_task_count >= 1

    approved_after = int(db.scalar("SELECT COUNT(1) AS count FROM judgment_versions WHERE status = 'approved'") or 0)
    assert approved_after == approved_before

