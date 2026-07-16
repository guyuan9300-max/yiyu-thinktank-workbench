from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app, should_preserve_pending_event_line_archive


def _make_client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(tmp_path / "data"))
    client.__enter__()
    return client


def _seed_cloud_event_line(client: TestClient, *, status: str = "active") -> str:
    response = client.post("/api/v1/event-lines", json={"name": "离线归档保护测试"})
    assert response.status_code == 200, response.text
    event_line_id = str(response.json()["id"])
    state = client.app.state.app_state
    state.db.execute(
        """
        UPDATE event_lines
        SET organization_id = 'org_archive_test',
            cloud_id = 'cloud_archive_test',
            status = ?,
            sync_status = 'synced',
            pending_sync_action = ''
        WHERE id = ?
        """,
        (status, event_line_id),
    )
    return event_line_id


def test_offline_close_records_pending_cloud_archive(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    try:
        event_line_id = _seed_cloud_event_line(client)

        response = client.post(f"/api/v1/event-lines/{event_line_id}/close")

        assert response.status_code == 200, response.text
        row = client.app.state.app_state.db.fetchone(
            "SELECT status, sync_status, pending_sync_action FROM event_lines WHERE id = ?",
            (event_line_id,),
        )
        assert row is not None
        assert row["status"] == "archived"
        assert row["sync_status"] == "pending"
        assert row["pending_sync_action"] == "archive"
    finally:
        client.__exit__(None, None, None)


def test_offline_reopen_replaces_stale_archive_action(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    try:
        event_line_id = _seed_cloud_event_line(client, status="archived")
        client.app.state.app_state.db.execute(
            "UPDATE event_lines SET sync_status = 'pending', pending_sync_action = 'archive' WHERE id = ?",
            (event_line_id,),
        )

        response = client.post(f"/api/v1/event-lines/{event_line_id}/reopen")

        assert response.status_code == 200, response.text
        row = client.app.state.app_state.db.fetchone(
            "SELECT status, sync_status, pending_sync_action FROM event_lines WHERE id = ?",
            (event_line_id,),
        )
        assert row is not None
        assert row["status"] == "active"
        assert row["sync_status"] == "pending"
        assert row["pending_sync_action"] == "update"
    finally:
        client.__exit__(None, None, None)


def test_cloud_pull_cannot_overwrite_pending_local_archive() -> None:
    assert should_preserve_pending_event_line_archive(
        local_status="archived",
        local_sync_status="pending",
        local_pending_action="archive",
        incoming_status="active",
    )
    assert not should_preserve_pending_event_line_archive(
        local_status="archived",
        local_sync_status="pending",
        local_pending_action="archive",
        incoming_status="archived",
    )
    assert not should_preserve_pending_event_line_archive(
        local_status="active",
        local_sync_status="pending",
        local_pending_action="archive",
        incoming_status="active",
    )
