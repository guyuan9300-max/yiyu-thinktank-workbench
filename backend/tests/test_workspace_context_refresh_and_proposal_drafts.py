from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services.workspace_context_refresh import (
    ensure_workspace_context_refresh_schema,
    recover_stale_workspace_context_refresh_events,
)


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "workspace context refresh test",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_workspace_context_refresh_event_dedupes_active_requests(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "refresh-dedupe")

    payload = {
        "sourceType": "document_import",
        "sourceId": "import-1",
        "reason": "document_import_completed",
        "scopeType": "client",
        "scopeId": client_id,
        "priority": "normal",
    }
    first = client.post(f"/api/v1/clients/{client_id}/workspace/context-refresh-events", json=payload)
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["deduped"] is False
    event_id = first_body["event"]["id"]

    second = client.post(f"/api/v1/clients/{client_id}/workspace/context-refresh-events", json=payload)
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["deduped"] is True
    assert second_body["event"]["id"] == event_id

    listed = client.get(f"/api/v1/clients/{client_id}/workspace/context-refresh-events?activeOnly=1")
    assert listed.status_code == 200, listed.text
    listed_ids = [item["id"] for item in listed.json()]
    assert event_id in listed_ids


def test_workspace_proposal_draft_promote_to_task_creates_task_and_refresh_event(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-proposal-promote")

    create_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/proposal-drafts",
        json={
            "sourceType": "manual",
            "kind": "task_prep",
            "title": "推进客户共识会准备",
            "summary": "把会议目标、议程和材料责任人收口成可执行任务。",
            "rationale": "当前上下文里会议线索已齐，但执行动作未落到任务层。",
            "riskLevel": "medium",
            "targetRefs": [{"targetType": "client", "targetId": client_id, "label": "客户"}],
            "sourceRefs": ["message:test"],
            "boundaryNotes": ["需人工确认后执行"],
            "payload": {"fromTest": True},
            "scopeType": "client",
            "scopeId": client_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    draft = create_response.json()
    draft_id = draft["id"]
    assert draft_id

    promote_response = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/promote",
        json={
            "createdBy": "user",
            "note": "人工确认转任务",
            "promoteTo": "task",
            "options": {},
        },
    )
    assert promote_response.status_code == 200, promote_response.text
    promoted = promote_response.json()
    assert promoted["effectType"] == "task"
    assert promoted["taskId"]
    assert promoted.get("proposalId") in {None, ""}
    assert promoted.get("refreshEventId")

    task_board = client.get("/api/v1/tasks")
    assert task_board.status_code == 200, task_board.text
    tasks = task_board.json().get("tasks") or []
    task_row = next((item for item in tasks if item.get("id") == promoted["taskId"]), None)
    assert task_row is not None
    assert task_row.get("sourceType") == "data_center_proposal_draft"
    assert task_row.get("sourceId") == draft_id

    refresh_events = client.get(f"/api/v1/clients/{client_id}/workspace/context-refresh-events").json()
    assert any(item.get("id") == promoted.get("refreshEventId") for item in refresh_events)


def test_workspace_proposal_draft_create_persists_message_level_provenance(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-proposal-provenance")

    create_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/proposal-drafts",
        json={
            "sourceType": "action_suggestion",
            "sourceMessageId": "msg-123",
            "actionSuggestionId": "action-abc",
            "sourceMessageDraftId": "msg-draft-1",
            "sourceMessageDraftPayload": {"kind": "task_prep", "title": "临时草稿"},
            "kind": "task_prep",
            "title": "从消息级建议保存",
            "summary": "验证 sourceMessageId/sourceType/actionSuggestionId 的持久化。",
            "rationale": "provenance regression",
            "riskLevel": "low",
            "targetRefs": [{"targetType": "client", "targetId": client_id, "label": "客户"}],
            "scopeType": "client",
            "scopeId": client_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    payload = create_response.json().get("payload") or {}

    assert payload.get("workspaceSourceType") == "action_suggestion"
    assert payload.get("sourceMessageId") == "msg-123"
    assert payload.get("actionSuggestionId") == "action-abc"
    assert payload.get("sourceMessageDraftId") == "msg-draft-1"


def test_workspace_meeting_pipeline_creates_refresh_events(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-meeting-refresh")

    prepared = client.post(
        f"/api/v1/clients/{client_id}/meetings",
        json={"title": "战略周会", "scheduledAt": "2026-04-21"},
    )
    assert prepared.status_code == 200, prepared.text
    meeting_id = prepared.json()["meeting"]["id"]

    ingested = client.post(
        f"/api/v1/clients/{client_id}/meetings/{meeting_id}/ingest",
        json={"transcriptText": "会议讨论了行动项与风险。", "notes": "需要补资料。"},
    )
    assert ingested.status_code == 200, ingested.text

    extracted = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/extract")
    assert extracted.status_code == 200, extracted.text

    resolved = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/resolve")
    assert resolved.status_code == 200, resolved.text

    published = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/publish")
    assert published.status_code == 200, published.text

    refresh_events = client.get(f"/api/v1/clients/{client_id}/workspace/context-refresh-events?limit=200")
    assert refresh_events.status_code == 200, refresh_events.text
    reasons = {str(item.get("reason")) for item in refresh_events.json()}
    assert {
        "meeting_prepared",
        "meeting_ingested",
        "meeting_extracted",
        "meeting_resolved",
        "meeting_published",
    }.issubset(reasons)


def test_workspace_task_attachment_upload_creates_refresh_event(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-attachment-refresh")

    create_task_response = client.post(
        "/api/v1/tasks",
        json={
            "title": "上传资料附件",
            "desc": "测试附件刷新事件",
            "listId": "list-0",
            "scopeMode": "COLLAB_SHARED",
            "clientId": client_id,
        },
    )
    assert create_task_response.status_code == 200, create_task_response.text
    task_id = create_task_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        data={"clientId": client_id},
        files={"file": ("附件说明.txt", "这是可用于检索的附件正文", "text/plain")},
    )
    assert upload_response.status_code == 200, upload_response.text

    refresh_events = client.get(f"/api/v1/clients/{client_id}/workspace/context-refresh-events?limit=200")
    assert refresh_events.status_code == 200, refresh_events.text
    assert any(
        item.get("reason") == "task_attachment_uploaded" and item.get("scopeType") == "task"
        for item in refresh_events.json()
    )


def test_workspace_proposal_lifecycle_creates_refresh_events(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-proposal-refresh")

    draft_resp = client.post(
        f"/api/v1/clients/{client_id}/workspace/proposal-drafts",
        json={
            "sourceType": "manual",
            "kind": "task_prep",
            "title": "推进客户提案",
            "summary": "先审批，再执行。",
            "rationale": "测试 proposal 生命周期刷新事件。",
            "riskLevel": "medium",
            "targetRefs": [{"targetType": "client", "targetId": client_id, "label": "客户"}],
            "sourceRefs": ["message:lifecycle"],
            "boundaryNotes": ["人工确认后执行"],
            "payload": {"fromTest": "proposal_lifecycle"},
            "scopeType": "client",
            "scopeId": client_id,
        },
    )
    assert draft_resp.status_code == 200, draft_resp.text
    draft_id = draft_resp.json()["id"]

    promoted_resp = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/promote",
        json={"createdBy": "user", "note": "转为 proposal record", "promoteTo": "proposal"},
    )
    assert promoted_resp.status_code == 200, promoted_resp.text
    proposal_id = promoted_resp.json().get("proposalId")
    assert proposal_id

    approved_resp = client.post(
        f"/api/v1/proposals/{proposal_id}/approve",
        json={"decidedBy": "tester", "note": "审批通过"},
    )
    assert approved_resp.status_code == 200, approved_resp.text

    ticket_resp = client.post(
        f"/api/v1/proposals/{proposal_id}/execution-ticket",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert ticket_resp.status_code == 200, ticket_resp.text
    ticket_id = (ticket_resp.json().get("executionTicket") or {}).get("id")
    assert ticket_id

    execute_resp = client.post(
        f"/api/v1/execution-tickets/{ticket_id}/execute",
        json={"requestedBy": "tester", "dryRun": False},
    )
    assert execute_resp.status_code == 200, execute_resp.text

    reject_draft_resp = client.post(
        f"/api/v1/clients/{client_id}/workspace/proposal-drafts",
        json={
            "sourceType": "manual",
            "kind": "context_refresh",
            "title": "另一个待拒绝提案",
            "summary": "用于 reject 刷新事件测试。",
            "rationale": "reject 分支",
            "riskLevel": "low",
            "targetRefs": [{"targetType": "client", "targetId": client_id, "label": "客户"}],
            "sourceRefs": ["message:reject"],
            "boundaryNotes": ["人工确认后执行"],
            "payload": {"fromTest": "proposal_reject"},
            "scopeType": "client",
            "scopeId": client_id,
        },
    )
    assert reject_draft_resp.status_code == 200, reject_draft_resp.text
    reject_promoted_resp = client.post(
        f"/api/v1/data-center/proposal-drafts/{reject_draft_resp.json()['id']}/promote",
        json={"createdBy": "user", "note": "转为 proposal record", "promoteTo": "proposal"},
    )
    assert reject_promoted_resp.status_code == 200, reject_promoted_resp.text
    reject_proposal_id = reject_promoted_resp.json().get("proposalId")
    assert reject_proposal_id

    rejected_resp = client.post(
        f"/api/v1/proposals/{reject_proposal_id}/reject",
        json={"decidedBy": "tester", "note": "驳回"},
    )
    assert rejected_resp.status_code == 200, rejected_resp.text

    refresh_events = client.get(f"/api/v1/clients/{client_id}/workspace/context-refresh-events?limit=300")
    assert refresh_events.status_code == 200, refresh_events.text
    reasons = {str(item.get("reason")) for item in refresh_events.json()}
    assert "proposal_approved" in reasons
    assert "execution_ticket_created" in reasons
    assert ("execution_ticket_executed" in reasons) or ("execution_ticket_failed" in reasons)
    assert "proposal_rejected" in reasons


def test_workspace_task_lifecycle_creates_refresh_events(tmp_path: Path):
    client = make_client(tmp_path)
    client_a = create_client_record(client, "workspace-task-refresh-a")
    client_b = create_client_record(client, "workspace-task-refresh-b")

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "任务刷新链路验证",
            "desc": "测试 create/update/delete 触发 refresh event",
            "listId": "list-0",
            "scopeMode": "COLLAB_SHARED",
            "clientId": client_a,
        },
    )
    assert created.status_code == 200, created.text
    task_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "任务刷新链路验证（更新）"},
    )
    assert updated.status_code == 200, updated.text

    moved = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"clientId": client_b},
    )
    assert moved.status_code == 200, moved.text

    deleted = client.delete(f"/api/v1/tasks/{task_id}")
    assert deleted.status_code == 200, deleted.text

    events_a = client.get(f"/api/v1/clients/{client_a}/workspace/context-refresh-events?limit=200")
    events_b = client.get(f"/api/v1/clients/{client_b}/workspace/context-refresh-events?limit=200")
    assert events_a.status_code == 200, events_a.text
    assert events_b.status_code == 200, events_b.text
    reasons_a = {str(item.get("reason")) for item in events_a.json()}
    reasons_b = {str(item.get("reason")) for item in events_b.json()}

    assert "task_created" in reasons_a
    assert "task_updated" in reasons_a
    assert "task_scope_changed" in reasons_a
    assert "task_scope_changed" in reasons_b
    assert "task_deleted" in reasons_b


def test_workspace_proposal_draft_promote_to_context_refresh_has_no_task_side_effect(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-proposal-context-refresh")

    create_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/proposal-drafts",
        json={
            "sourceType": "manual",
            "kind": "context_refresh",
            "title": "刷新上下文",
            "summary": "触发上下文刷新，不落任务。",
            "rationale": "测试 context_refresh promote 边界。",
            "riskLevel": "low",
            "targetRefs": [{"targetType": "client", "targetId": client_id, "label": "客户"}],
            "scopeType": "client",
            "scopeId": client_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    draft_id = create_response.json()["id"]

    promote_response = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/promote",
        json={"createdBy": "user", "note": "仅刷新上下文", "promoteTo": "context_refresh"},
    )
    assert promote_response.status_code == 200, promote_response.text
    promoted = promote_response.json()

    assert promoted["effectType"] == "context_refresh"
    assert promoted.get("taskId") in {None, ""}
    assert promoted.get("proposalId") in {None, ""}
    assert promoted.get("refreshEventId")


def test_workspace_proposal_draft_promote_to_evidence_request_creates_task_with_source_ref(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-proposal-evidence-task")

    create_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/proposal-drafts",
        json={
            "sourceType": "manual",
            "kind": "evidence_request",
            "title": "补齐预算资料",
            "summary": "当前预算证据不足，需要补资料。",
            "rationale": "测试 evidence_request promote 到任务。",
            "riskLevel": "medium",
            "targetRefs": [{"targetType": "client", "targetId": client_id, "label": "客户"}],
            "scopeType": "client",
            "scopeId": client_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    draft_id = create_response.json()["id"]

    promote_response = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/promote",
        json={
            "createdBy": "user",
            "note": "转补资料任务",
            "promoteTo": "evidence_request",
            "options": {"dueDate": "2026-05-01"},
        },
    )
    assert promote_response.status_code == 200, promote_response.text
    promoted = promote_response.json()
    assert promoted["effectType"] == "evidence_request"
    assert promoted.get("taskId")

    task_board = client.get("/api/v1/tasks")
    assert task_board.status_code == 200, task_board.text
    tasks = task_board.json().get("tasks") or []
    task_row = next((item for item in tasks if item.get("id") == promoted["taskId"]), None)
    assert task_row is not None
    assert task_row.get("sourceType") == "data_center_evidence_request"
    assert task_row.get("sourceId") == draft_id
    assert task_row.get("businessCategory") == "补资料"


def test_workspace_proposal_draft_promote_to_meeting_prep_creates_meeting_task(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-proposal-meeting-task")

    create_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/proposal-drafts",
        json={
            "sourceType": "manual",
            "kind": "meeting_prep",
            "title": "准备周会议题",
            "summary": "整理会议目标和材料责任分配。",
            "rationale": "测试 meeting_prep promote 到任务。",
            "riskLevel": "medium",
            "targetRefs": [{"targetType": "client", "targetId": client_id, "label": "客户"}],
            "scopeType": "client",
            "scopeId": client_id,
            "payload": {"meetingId": "meeting-from-draft"},
        },
    )
    assert create_response.status_code == 200, create_response.text
    draft_id = create_response.json()["id"]

    promote_response = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/promote",
        json={
            "createdBy": "user",
            "note": "转会议准备任务",
            "promoteTo": "meeting_prep",
            "options": {"meetingId": "meeting-from-options", "dueDate": "2026-05-02"},
        },
    )
    assert promote_response.status_code == 200, promote_response.text
    promoted = promote_response.json()
    assert promoted["effectType"] == "meeting_prep"
    assert promoted.get("taskId")

    task_board = client.get("/api/v1/tasks")
    assert task_board.status_code == 200, task_board.text
    tasks = task_board.json().get("tasks") or []
    task_row = next((item for item in tasks if item.get("id") == promoted["taskId"]), None)
    assert task_row is not None
    assert task_row.get("sourceType") == "data_center_meeting_prep"
    assert task_row.get("sourceId") == draft_id
    assert task_row.get("businessCategory") == "会议准备"
    assert task_row.get("dueDate") == "2026-05-02"


def test_workspace_proposal_draft_promote_to_judgment_confirmation_does_not_auto_approve(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-proposal-judgment-confirm")

    db = client.app.state.app_state.db
    before_count = int(
        db.scalar(
            "SELECT COUNT(1) FROM judgment_versions WHERE client_id = ? AND status = 'approved'",
            (client_id,),
        )
        or 0
    )

    create_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/proposal-drafts",
        json={
            "sourceType": "manual",
            "kind": "judgment_review",
            "title": "判断复核",
            "summary": "需要人工确认 candidate judgment。",
            "rationale": "测试 judgment_confirmation promote 不自动 approved。",
            "riskLevel": "medium",
            "targetRefs": [{"targetType": "client", "targetId": client_id, "label": "客户"}],
            "scopeType": "client",
            "scopeId": client_id,
        },
    )
    assert create_response.status_code == 200, create_response.text
    draft_id = create_response.json()["id"]

    promote_response = client.post(
        f"/api/v1/data-center/proposal-drafts/{draft_id}/promote",
        json={"createdBy": "user", "note": "进入判断确认", "promoteTo": "judgment_confirmation"},
    )
    assert promote_response.status_code == 200, promote_response.text
    promoted = promote_response.json()

    assert promoted["effectType"] == "judgment_confirmation"
    assert promoted.get("taskId") in {None, ""}
    assert promoted.get("proposalId") in {None, ""}
    assert promoted.get("refreshEventId")

    after_count = int(
        db.scalar(
            "SELECT COUNT(1) FROM judgment_versions WHERE client_id = ? AND status = 'approved'",
            (client_id,),
        )
        or 0
    )
    assert after_count == before_count


def test_workspace_context_refresh_recover_stale_events(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client_record(client, "workspace-refresh-recover")
    db = client.app.state.app_state.db
    ensure_workspace_context_refresh_schema(db)
    db.execute(
        """
        INSERT INTO workspace_context_refresh_events(
            id, client_id, scope_type, scope_id, source_type, source_id,
            reason, priority, status, job_id, dedupe_key, error, created_at, updated_at
        ) VALUES(?, ?, 'client', ?, 'manual_test', NULL, 'manual_stale', 'normal', 'running', NULL, ?, NULL, ?, ?)
        """,
        (
            "wcrf_stale_running",
            client_id,
            client_id,
            f"{client_id}:client:{client_id}:manual_stale",
            "2026-04-20T00:00:00",
            "2026-04-20T00:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO workspace_context_refresh_events(
            id, client_id, scope_type, scope_id, source_type, source_id,
            reason, priority, status, job_id, dedupe_key, error, created_at, updated_at
        ) VALUES(?, ?, 'client', ?, 'manual_test', NULL, 'manual_queued_stale', 'normal', 'queued', NULL, ?, NULL, ?, ?)
        """,
        (
            "wcrf_stale_queued",
            client_id,
            client_id,
            f"{client_id}:client:{client_id}:manual_queued_stale",
            "2026-04-20T00:00:00",
            "2026-04-20T00:00:00",
        ),
    )

    result = recover_stale_workspace_context_refresh_events(
        db,
        max_age_minutes=1,
        queued_max_age_minutes=1,
    )
    assert result["runningRecoveredFailed"] >= 1
    assert result["queuedRecoveredFailed"] >= 1

    listed = client.get(f"/api/v1/clients/{client_id}/workspace/context-refresh-events?limit=200")
    assert listed.status_code == 200, listed.text
    by_id = {item["id"]: item for item in listed.json()}
    assert by_id["wcrf_stale_running"]["status"] == "failed"
    assert "stale_refresh_event" in str(by_id["wcrf_stale_running"].get("error") or "")
    assert by_id["wcrf_stale_queued"]["status"] == "failed"
