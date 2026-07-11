from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app, now_iso


def _make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "data"), raise_server_exceptions=False)


def _create_workspace(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "kind": "organization",
            "name": name,
            "cloudApiUrl": f"https://{name}.example.test",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["activeSandboxId"])


def _activate_workspace(client: TestClient, sandbox_id: str) -> None:
    response = client.post(f"/api/v1/workspaces/{sandbox_id}/activate")
    assert response.status_code == 200, response.text


def _create_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": "",
            "domain": "smart-import-sandbox-test",
            "type": "公益组织",
            "intro": "smart import sandbox test",
            "stage": "active",
            "color": "#5B7BFE",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def _create_session(client: TestClient, client_id: str | None = None) -> str:
    payload = {"title": "scope-a-secret-session"}
    if client_id:
        payload["clientId"] = client_id
    response = client.post("/api/v1/smart-import/sessions", json=payload)
    assert response.status_code == 200, response.text
    return str(response.json()["session"]["id"])


def _upload_file(client: TestClient, session_id: str, filename: str = "scope-a-secret.txt") -> dict:
    response = client.post(
        f"/api/v1/smart-import/sessions/{session_id}/files",
        files={"file": (filename, b"scope-a-secret-bytes", "text/plain")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _add_chunk(client: TestClient, session_id: str, file_ids: list[str] | None = None) -> str:
    response = client.post(
        f"/api/v1/smart-import/sessions/{session_id}/chunks",
        json={
            "rawText": "scope-a-secret-story",
            "fileIds": file_ids or [],
            "autoParse": False,
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["chunks"][-1]["id"])


def test_smart_import_direct_ids_fail_closed_after_workspace_switch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _make_client(tmp_path) as client:
        sandbox_a = _create_workspace(client, "smart-import-a")
        client_a = _create_client_record(client, "智能导入客户 A")
        session_id = _create_session(client, client_a)
        staged_file = _upload_file(client, session_id)
        file_id = str(staged_file["id"])
        chunk_id = _add_chunk(client, session_id, [file_id])

        state = client.app.state.app_state
        db = state.db
        file_path = Path(str(staged_file["storage_path"]))
        assert file_path.exists()
        before_session = dict(db.fetchone("SELECT * FROM import_story_sessions WHERE id=?", (session_id,)))
        before_file = dict(db.fetchone("SELECT * FROM import_staged_files WHERE id=?", (file_id,)))
        before_chunk = dict(db.fetchone("SELECT * FROM import_story_chunks WHERE id=?", (chunk_id,)))
        before_counts = {
            "sessions": db.scalar("SELECT COUNT(*) FROM import_story_sessions"),
            "files": db.scalar("SELECT COUNT(*) FROM import_staged_files"),
            "chunks": db.scalar("SELECT COUNT(*) FROM import_story_chunks"),
            "documents": db.scalar("SELECT COUNT(*) FROM documents"),
            "entities": db.scalar("SELECT COUNT(*) FROM entities"),
        }

        downstream_calls: list[str] = []

        def _unexpected(name: str):
            def _raise(*_args, **_kwargs):
                downstream_calls.append(name)
                raise AssertionError(f"foreign-scope downstream call: {name}")

            return _raise

        monkeypatch.setattr(state.ai, "_qwen_generate", _unexpected("ai"))
        monkeypatch.setattr(
            "app.services.smart_file_import.commit_session",
            _unexpected("commit"),
        )
        monkeypatch.setattr(
            "app.services.smart_file_import.upload_staged_file",
            _unexpected("upload"),
        )
        monkeypatch.setattr(
            "app.services.agent_governance.check_idempotency",
            _unexpected("idempotency"),
        )
        monkeypatch.setattr(
            "app.services.agent_governance.record_idempotency",
            _unexpected("idempotency-write"),
        )
        monkeypatch.setattr(
            "app.services.agent_governance.log_agent_run_start",
            _unexpected("audit"),
        )
        monkeypatch.setattr(
            "app.services.agent_governance.log_agent_run_complete",
            _unexpected("audit-complete"),
        )

        sandbox_b = _create_workspace(client, "smart-import-b")
        assert sandbox_b != sandbox_a

        requests = (
            client.get(f"/api/v1/smart-import/sessions/{session_id}"),
            client.patch(
                f"/api/v1/smart-import/sessions/{session_id}",
                json={"title": "foreign mutation"},
            ),
            client.delete(f"/api/v1/smart-import/sessions/{session_id}"),
            client.post(
                f"/api/v1/smart-import/sessions/{session_id}/files",
                files={"file": ("foreign.txt", b"foreign", "text/plain")},
            ),
            client.delete(f"/api/v1/smart-import/files/{file_id}"),
            client.patch(
                f"/api/v1/smart-import/files/{file_id}/assign",
                json={"chunkId": chunk_id},
            ),
            client.post(
                f"/api/v1/smart-import/sessions/{session_id}/chunks",
                json={"rawText": "foreign", "fileIds": [file_id], "autoParse": False},
            ),
            client.patch(
                f"/api/v1/smart-import/chunks/{chunk_id}",
                json={"rawText": "foreign", "autoParse": True},
            ),
            client.delete(f"/api/v1/smart-import/chunks/{chunk_id}"),
            client.post(f"/api/v1/smart-import/chunks/{chunk_id}/parse"),
            client.patch(
                f"/api/v1/smart-import/chunks/{chunk_id}/parsed",
                json={"parsed": {"entities": [{"name": "foreign"}]}},
            ),
            client.get(f"/api/v1/smart-import/sessions/{session_id}/preview"),
            client.post(
                f"/api/v1/smart-import/sessions/{session_id}/commit",
                headers={"Idempotency-Key": "foreign-scope-key"},
            ),
        )
        for response in requests:
            assert response.status_code == 404, (response.status_code, response.text)
            assert "scope-a-secret" not in response.text

        assert downstream_calls == []
        assert dict(db.fetchone("SELECT * FROM import_story_sessions WHERE id=?", (session_id,))) == before_session
        assert dict(db.fetchone("SELECT * FROM import_staged_files WHERE id=?", (file_id,))) == before_file
        assert dict(db.fetchone("SELECT * FROM import_story_chunks WHERE id=?", (chunk_id,))) == before_chunk
        assert file_path.exists()
        assert file_path.read_bytes() == b"scope-a-secret-bytes"
        assert before_counts == {
            "sessions": db.scalar("SELECT COUNT(*) FROM import_story_sessions"),
            "files": db.scalar("SELECT COUNT(*) FROM import_staged_files"),
            "chunks": db.scalar("SELECT COUNT(*) FROM import_story_chunks"),
            "documents": db.scalar("SELECT COUNT(*) FROM documents"),
            "entities": db.scalar("SELECT COUNT(*) FROM entities"),
        }


def test_smart_import_same_scope_routes_remain_usable(tmp_path: Path, monkeypatch) -> None:
    with _make_client(tmp_path) as client:
        sandbox_id = _create_workspace(client, "smart-import-same")
        client_id = _create_client_record(client, "智能导入同域客户")
        session_id = _create_session(client, client_id)
        state = client.app.state.app_state

        session_row = state.db.fetchone(
            "SELECT sandbox_id FROM import_story_sessions WHERE id=?",
            (session_id,),
        )
        assert session_row is not None
        assert session_row["sandbox_id"] == sandbox_id
        assert client.get(f"/api/v1/smart-import/sessions/{session_id}").status_code == 200
        assert client.patch(
            f"/api/v1/smart-import/sessions/{session_id}",
            json={"title": "same scope updated"},
        ).status_code == 200

        staged_file = _upload_file(client, session_id, "same-scope.txt")
        file_id = str(staged_file["id"])
        chunk_id = _add_chunk(client, session_id, [file_id])
        assert client.patch(
            f"/api/v1/smart-import/chunks/{chunk_id}",
            json={"rawText": "same scope updated story", "autoParse": False},
        ).status_code == 200

        parsed_payload = {
            "entities": [],
            "relationships": [],
            "events": [],
            "opinions": [],
            "files_classified": [],
            "files_suggested_to_attach": [],
            "commitments": [],
            "risk_signals": [],
            "open_questions": [],
        }
        monkeypatch.setattr(state.ai, "_qwen_generate", lambda *_args, **_kwargs: parsed_payload)
        assert client.post(f"/api/v1/smart-import/chunks/{chunk_id}/parse").status_code == 200
        assert client.patch(
            f"/api/v1/smart-import/chunks/{chunk_id}/parsed",
            json={"parsed": parsed_payload},
        ).status_code == 200
        assert client.get(f"/api/v1/smart-import/sessions/{session_id}/preview").status_code == 200
        assert client.patch(
            f"/api/v1/smart-import/files/{file_id}/assign",
            json={"chunkId": None},
        ).status_code == 200
        assert client.patch(
            f"/api/v1/smart-import/files/{file_id}/assign",
            json={"chunkId": chunk_id},
        ).status_code == 200

        disposable_file = _upload_file(client, session_id, "delete-me.txt")
        disposable_path = Path(str(disposable_file["storage_path"]))
        assert client.delete(
            f"/api/v1/smart-import/files/{disposable_file['id']}"
        ).status_code == 200
        assert not disposable_path.exists()

        disposable_chunk = _add_chunk(client, session_id)
        assert client.delete(f"/api/v1/smart-import/chunks/{disposable_chunk}").status_code == 200

        # Remove the remaining staged file so commit stays synchronous and does
        # not start a background ingestion thread in this route-level test.
        assert client.delete(f"/api/v1/smart-import/files/{file_id}").status_code == 200
        commit_response = client.post(f"/api/v1/smart-import/sessions/{session_id}/commit")
        assert commit_response.status_code == 200, commit_response.text

        discard_session = _create_session(client, client_id)
        assert client.delete(f"/api/v1/smart-import/sessions/{discard_session}").status_code == 200
        discarded = state.db.fetchone(
            "SELECT status FROM import_story_sessions WHERE id=?",
            (discard_session,),
        )
        assert discarded is not None
        assert discarded["status"] == "discarded"


def test_smart_import_commit_idempotency_is_scoped_to_authorized_session(
    tmp_path: Path,
) -> None:
    with _make_client(tmp_path) as client:
        sandbox_a = _create_workspace(client, "smart-import-idem-a")
        client_a = _create_client_record(client, "智能导入幂等客户 A")
        session_a = _create_session(client, client_a)
        headers = {"Idempotency-Key": "shared-caller-key"}

        first = client.post(
            f"/api/v1/smart-import/sessions/{session_a}/commit",
            headers=headers,
        )
        assert first.status_code == 200, first.text
        replay = client.post(
            f"/api/v1/smart-import/sessions/{session_a}/commit",
            headers=headers,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json() == first.json()

        sandbox_b = _create_workspace(client, "smart-import-idem-b")
        client_b = _create_client_record(client, "智能导入幂等客户 B")
        session_b = _create_session(client, client_b)
        second_scope = client.post(
            f"/api/v1/smart-import/sessions/{session_b}/commit",
            headers=headers,
        )
        assert second_scope.status_code == 200, second_scope.text
        assert second_scope.json()["agent_run_id"] != first.json()["agent_run_id"]

        db = client.app.state.app_state.db
        keys = {
            str(row["key"])
            for row in db.fetchall(
                "SELECT key FROM idempotency_keys_v25 WHERE key LIKE 'smart_import.commit:%'"
            )
        }
        assert keys == {
            f"smart_import.commit:{sandbox_a}:{session_a}:shared-caller-key",
            f"smart_import.commit:{sandbox_b}:{session_b}:shared-caller-key",
        }


def test_legacy_smart_import_scope_backfills_only_from_valid_parent_client(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        sandbox_id = _create_workspace(client, "smart-import-legacy")
        client_id = _create_client_record(client, "智能导入迁移客户")
        db = client.app.state.app_state.db
        timestamp = now_iso()
        db.execute(
            """
            INSERT INTO import_story_sessions(
                id, sandbox_id, client_id, project_event_line_id, narrator_user_id,
                title, status, total_chunks, total_files, created_at, updated_at
            ) VALUES('legacy_bound_session', '', ?, NULL, '', 'legacy bound',
                     'drafting', 0, 0, ?, ?)
            """,
            (client_id, timestamp, timestamp),
        )
        db.execute(
            """
            INSERT INTO import_story_sessions(
                id, sandbox_id, client_id, project_event_line_id, narrator_user_id,
                title, status, total_chunks, total_files, created_at, updated_at
            ) VALUES('legacy_unbound_session', '', NULL, NULL, '', 'legacy unbound',
                     'drafting', 0, 0, ?, ?)
            """,
            (timestamp, timestamp),
        )
        db.execute(
            """
            INSERT INTO clients(
                id, sandbox_id, name, alias, domain, type, intro, stage, color,
                created_at, updated_at
            ) VALUES('invalid-sandbox-client', 'missing-sandbox', 'invalid parent', '', '',
                     'other', '', 'lead', '#5B7BFE', ?, ?)
            """,
            (timestamp, timestamp),
        )
        db.execute(
            """
            INSERT INTO import_story_sessions(
                id, sandbox_id, client_id, project_event_line_id, narrator_user_id,
                title, status, total_chunks, total_files, created_at, updated_at
            ) VALUES('legacy_invalid_parent_session', '', 'invalid-sandbox-client', NULL, '',
                     'legacy invalid parent', 'drafting', 0, 0, ?, ?)
            """,
            (timestamp, timestamp),
        )

        # Recreate the pre-migration shape, including rows that genuinely have
        # no sandbox column yet.  The initial test database already ran current
        # bootstrap, so remove the new index before dropping the column.
        db.execute("DROP INDEX idx_import_story_sessions_sandbox")
        db.execute("ALTER TABLE import_story_sessions DROP COLUMN sandbox_id")
        assert "sandbox_id" not in {
            row["name"] for row in db.fetchall("PRAGMA table_info(import_story_sessions)")
        }

        # Re-running bootstrap models opening an existing pre-sandbox database.
        db._init_schema()
        # The migration must be safe to execute repeatedly and must not assign
        # quarantined legacy rows to whichever workspace happens to be active.
        db._init_schema()

        bound = db.fetchone(
            "SELECT sandbox_id FROM import_story_sessions WHERE id='legacy_bound_session'"
        )
        unbound = db.fetchone(
            "SELECT sandbox_id FROM import_story_sessions WHERE id='legacy_unbound_session'"
        )
        invalid_parent = db.fetchone(
            "SELECT sandbox_id FROM import_story_sessions "
            "WHERE id='legacy_invalid_parent_session'"
        )
        assert bound is not None and bound["sandbox_id"] == sandbox_id
        assert unbound is not None and unbound["sandbox_id"] == ""
        assert invalid_parent is not None and invalid_parent["sandbox_id"] == ""
        assert client.get("/api/v1/smart-import/sessions/legacy_bound_session").status_code == 200
        assert client.get("/api/v1/smart-import/sessions/legacy_unbound_session").status_code == 404
        assert (
            client.get("/api/v1/smart-import/sessions/legacy_invalid_parent_session").status_code
            == 404
        )

        other_sandbox = _create_workspace(client, "smart-import-legacy-other")
        assert other_sandbox != sandbox_id
        assert client.get("/api/v1/smart-import/sessions/legacy_bound_session").status_code == 404
