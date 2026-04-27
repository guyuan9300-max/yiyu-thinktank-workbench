from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.db import to_json


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str = "proposal-promote-p22") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "proposal promote p22",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_data_center_proposal_draft_promote_flow(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client)
    db = client.app.state.app_state.db

    before_proposals = int(db.scalar("SELECT COUNT(1) AS count FROM proposal_records") or 0)
    before_tickets = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)

    resolve = client.post(
        "/api/v1/data-center/resolve",
        json={
            "scope": {
                "page": "workspace_chat",
                "scopeType": "client",
                "scopeId": client_id,
                "clientId": client_id,
            },
            "prompt": "当前还缺哪些关键资料？",
            "mode": "proposal",
            "includeActionSuggestions": True,
            "shadow": True,
            "persistDrafts": True,
        },
    )
    assert resolve.status_code == 200, resolve.text
    payload = resolve.json()
    draft_ids = payload.get("persistedProposalDraftIds") or payload.get("dedupedDraftIds") or []
    assert draft_ids
    draft_id = str(draft_ids[0])

    promote = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/promote",
        json={"createdBy": "tester", "note": "确认创建正式提案"},
    )
    assert promote.status_code == 200, promote.text
    promoted = promote.json()
    assert promoted["proposalId"]
    assert promoted["draft"]["status"] == "promoted"

    after_proposals = int(db.scalar("SELECT COUNT(1) AS count FROM proposal_records") or 0)
    after_tickets = int(db.scalar("SELECT COUNT(1) AS count FROM execution_tickets") or 0)
    assert after_proposals == before_proposals + 1
    assert after_tickets == before_tickets

    promote_again = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/promote",
        json={"createdBy": "tester", "note": "重复 promote"},
    )
    assert promote_again.status_code == 200
    assert promote_again.json()["proposalId"] == promoted["proposalId"]

    # rejected draft 不允许 promote。
    now = datetime.now().replace(microsecond=0).isoformat()
    rejected_id = "dcprop_rejected_case"
    db.execute(
        """
        INSERT INTO data_center_proposal_drafts(
            id, scope_type, scope_id, client_id, page, mode, kind, title, summary, rationale,
            risk_level, target_refs_json, source_refs_json, boundary_notes_json, payload_json,
            source_prompt, route_decision_json, answer_plan_json, status, dedupe_key,
            reviewed_at, rejected_at, rejected_reason, promoted_proposal_id, created_at, updated_at
        )
        VALUES(?, 'client', ?, ?, 'workspace_chat', 'proposal', 'evidence_request', '拒绝草稿', '拒绝草稿', '拒绝草稿',
               'medium', '[]', '[]', '[]', '{}', '', '{}', '{}', 'rejected', ?, NULL, ?, '人工驳回', NULL, ?, ?)
        """,
        (
            rejected_id,
            client_id,
            client_id,
            f"client:{client_id}:evidence_request:rejected:{client_id}",
            now,
            now,
            now,
        ),
    )

    rejected_promote = client.post(
        f"/api/v1/data-center/proposal-drafts/{rejected_id}/promote",
        json={"createdBy": "tester", "note": "不应允许"},
    )
    assert rejected_promote.status_code == 409
