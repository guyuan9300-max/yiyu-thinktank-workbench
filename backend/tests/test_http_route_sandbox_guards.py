from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as app_main  # noqa: E402
from app.main import create_app, now_iso  # noqa: E402
from app.services import understanding_builder  # noqa: E402
from app.services.narrative_collector import collect_client_fact_bundle  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "data"), raise_server_exceptions=False)


def create_workspace(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={"kind": "organization", "name": name, "cloudApiUrl": f"https://{name}.example.test"},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["activeSandboxId"])


def create_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": "",
            "domain": "sandbox-guard-test",
            "type": "公益组织",
            "intro": "HTTP direct-id sandbox guard test",
            "stage": "active",
            "color": "#5B7BFE",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def create_task_record(client: TestClient, title: str, client_id: str | None = None) -> str:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": "HTTP direct-id sandbox guard test",
            "priority": "normal",
            "listId": "",
            "clientId": client_id,
            "sourceType": "manual",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def activate_workspace(client: TestClient, sandbox_id: str) -> None:
    response = client.post(f"/api/v1/workspaces/{sandbox_id}/activate")
    assert response.status_code == 200, response.text


def _install_blocking_understanding_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[threading.Event, threading.Event, list[threading.Thread]]:
    build_started = threading.Event()
    release_build = threading.Event()
    workers: list[threading.Thread] = []
    original_build = understanding_builder.build_understanding_basic

    def blocking_build(*args, **kwargs):
        build_started.set()
        if not release_build.wait(timeout=5):
            raise AssertionError("timed out waiting to release understanding builder")
        # Keep the race deterministic and offline while still returning the real
        # UnderstandingSnapshot model consumed by the production cache writer.
        kwargs["ai"] = None
        return original_build(*args, **kwargs)

    def tracking_thread(*args, **kwargs):
        worker = threading.Thread(*args, **kwargs)
        target = kwargs.get("target")
        if getattr(target, "__name__", "") == "_precompute_task_understanding":
            workers.append(worker)
        return worker

    monkeypatch.setattr(understanding_builder, "build_understanding_basic", blocking_build)
    monkeypatch.setattr(app_main, "Thread", tracking_thread)
    return build_started, release_build, workers


@pytest.mark.parametrize("mutation", ["edit", "move"])
def test_slow_task_understanding_does_not_cache_stale_or_moved_task(
    mutation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with make_client(tmp_path) as client:
        sandbox_a = create_workspace(client, f"understanding-{mutation}-a")
        started, release, workers = _install_blocking_understanding_builder(monkeypatch)
        task_id = create_task_record(client, f"慢理解任务-{mutation}")
        assert started.wait(timeout=5), "background understanding build did not start"
        assert workers, "precompute worker was not captured"
        db = client.app.state.app_state.db

        if mutation == "edit":
            db.execute(
                "UPDATE tasks SET title = ?, updated_at = ? WHERE id = ? AND sandbox_id = ?",
                ("慢理解任务-已编辑", now_iso(), task_id, sandbox_a),
            )
        else:
            sandbox_b = create_workspace(client, "understanding-move-b")
            assert sandbox_b != sandbox_a
            db.execute(
                "UPDATE tasks SET sandbox_id = ?, updated_at = ? WHERE id = ? AND sandbox_id = ?",
                (sandbox_b, now_iso(), task_id, sandbox_a),
            )

        release.set()
        for worker in workers:
            worker.join(timeout=5)
            assert not worker.is_alive(), "understanding precompute worker did not finish"

        assert db.fetchone(
            "SELECT task_id FROM task_understanding_cache WHERE task_id = ?",
            (task_id,),
        ) is None


def test_slow_task_understanding_caches_when_scope_and_content_are_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with make_client(tmp_path) as client:
        create_workspace(client, "understanding-unchanged")
        started, release, workers = _install_blocking_understanding_builder(monkeypatch)
        task_id = create_task_record(client, "慢理解任务-内容未变")
        assert started.wait(timeout=5), "background understanding build did not start"
        assert workers, "precompute worker was not captured"

        release.set()
        for worker in workers:
            worker.join(timeout=5)
            assert not worker.is_alive(), "understanding precompute worker did not finish"

        cached = client.app.state.app_state.db.fetchone(
            "SELECT snapshot_json, task_hash FROM task_understanding_cache WHERE task_id = ?",
            (task_id,),
        )
        assert cached is not None
        assert str(cached["task_hash"])
        assert json.loads(str(cached["snapshot_json"]))["humanBrief"]


def test_task_read_routes_guard_before_cache_or_query(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        sandbox_a = create_workspace(client, "route-read-a")
        client_id = create_client_record(client, "读取域客户 A")
        task_id = create_task_record(client, "读取域任务 A", client_id)
        db = client.app.state.app_state.db
        timestamp = now_iso()
        db.execute(
            """
            INSERT INTO task_understanding_cache(task_id, snapshot_json, task_hash, created_at, updated_at)
            VALUES(?, '{"secret":"sandbox-a-understanding"}', 'scope-test', ?, ?)
            """,
            (task_id, timestamp, timestamp),
        )
        db.execute(
            """
            INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
            VALUES('activity_route_scope_a', 'A user', 'scope.secret', 'task', ?,
                   '{"secret":"sandbox-a-activity"}', ?)
            """,
            (task_id, timestamp),
        )

        preview = client.get(f"/api/v1/tasks/{task_id}/context-preview")
        assert preview.status_code == 200, preview.text

        sandbox_b = create_workspace(client, "route-read-b")
        assert sandbox_b != sandbox_a

        for suffix in ("understanding", "page-context", "context-preview", "activity"):
            response = client.get(f"/api/v1/tasks/{task_id}/{suffix}")
            assert response.status_code == 404, (suffix, response.status_code, response.text)
            assert "sandbox-a" not in response.text


def test_task_mutation_routes_fail_closed_before_any_write(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        sandbox_a = create_workspace(client, "route-write-a")
        task_id = create_task_record(client, "写入域任务 A")
        db = client.app.state.app_state.db
        before_task = db.fetchone(
            "SELECT status, progress_status, updated_at FROM tasks WHERE id = ?",
            (task_id,),
        )
        assert before_task is not None
        before_activity_count = db.scalar(
            "SELECT COUNT(*) FROM activity_logs WHERE entity_type = 'task' AND entity_id = ?",
            (task_id,),
        )

        sandbox_b = create_workspace(client, "route-write-b")
        assert sandbox_b != sandbox_a

        requests = (
            ("confirm", None),
            ("reject", {"reason": "foreign reject"}),
            ("complete-with-review", {"reviewNote": "foreign completion"}),
            ("review/approve", None),
            ("review/return", {"reason": "foreign review return"}),
            ("note", {"note": "foreign note"}),
        )
        for suffix, payload in requests:
            response = client.post(f"/api/v1/tasks/{task_id}/{suffix}", json=payload)
            assert response.status_code == 404, (suffix, response.status_code, response.text)

        after_task = db.fetchone(
            "SELECT status, progress_status, updated_at FROM tasks WHERE id = ?",
            (task_id,),
        )
        assert after_task is not None
        assert dict(after_task) == dict(before_task)
        assert db.scalar("SELECT COUNT(*) FROM task_notes WHERE task_id = ?", (task_id,)) == 0
        assert db.scalar(
            "SELECT COUNT(*) FROM activity_logs WHERE entity_type = 'task' AND entity_id = ?",
            (task_id,),
        ) == before_activity_count


def test_delete_attachment_requires_task_in_active_sandbox(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        sandbox_a = create_workspace(client, "route-attachment-a")
        client_id = create_client_record(client, "附件域客户 A")
        task_id = create_task_record(client, "附件域任务 A", client_id)
        state = client.app.state.app_state
        attachment_id = "attachment_route_scope_a"
        attachment_path = state.data_dir / "task-attachments" / task_id / "scope-secret.txt"
        attachment_path.parent.mkdir(parents=True, exist_ok=True)
        attachment_path.write_text("sandbox-a attachment secret", encoding="utf-8")
        state.db.execute(
            """
            INSERT INTO task_attachments(
                id, task_id, client_id, event_line_id, document_id, title,
                path, kind, source, size_bytes, created_at
            ) VALUES(?, ?, ?, NULL, NULL, 'A scope attachment', ?, 'txt', 'manual', ?, ?)
            """,
            (
                attachment_id,
                task_id,
                client_id,
                str(attachment_path),
                attachment_path.stat().st_size,
                now_iso(),
            ),
        )

        sandbox_b = create_workspace(client, "route-attachment-b")
        assert sandbox_b != sandbox_a
        response = client.delete(
            f"/api/v1/tasks/{task_id}/attachments/{attachment_id}",
            params={"syncKnowledge": "false"},
        )

        assert response.status_code == 404, response.text
        assert state.db.fetchone("SELECT id FROM task_attachments WHERE id = ?", (attachment_id,)) is not None
        assert attachment_path.exists()


def test_fact_bundle_and_narrative_cache_use_client_workspace_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with make_client(tmp_path) as client:
        sandbox_a = create_workspace(client, "route-client-a")
        client_a = create_client_record(client, "事实域客户 A")
        task_a = create_task_record(client, "事实域任务 A", client_a)
        db = client.app.state.app_state.db
        timestamp = now_iso()
        narrative = {
            "clientId": client_a,
            "dimensions": [{"dimension": "essence", "narrative": "sandbox-a-narrative-secret"}],
            "generatedAt": timestamp,
        }
        db.execute(
            """
            INSERT INTO client_narrative_local_mirror(
                client_id, generated_at, record_json, source, mirrored_at
            ) VALUES(?, ?, ?, 'local-only', ?)
            """,
            (client_a, timestamp, json.dumps(narrative), timestamp),
        )
        db.execute(
            """
            INSERT INTO narrative_stale_signals(client_id, marked_at, last_doc_title, reason)
            VALUES(?, ?, 'sandbox-a-document', 'sandbox-a-stale-secret')
            """,
            (client_a, timestamp),
        )

        sandbox_b = create_workspace(client, "route-client-b")
        task_b = create_task_record(client, "跨域伪关联任务 B")
        # Simulate legacy/corrupt data: a task owned by B points at A's client.
        db.execute("UPDATE tasks SET client_id = ? WHERE id = ?", (client_a, task_b))

        activate_workspace(client, sandbox_a)
        fact_response = client.get(f"/api/v1/clients/{client_a}/fact-bundle")
        assert fact_response.status_code == 200, fact_response.text
        fact_task_ids = {str(item["id"]) for item in fact_response.json()["tasks"]}
        assert task_a in fact_task_ids
        assert task_b not in fact_task_ids
        collected_bundle = collect_client_fact_bundle(
            db,
            client_a,
            sandbox_id=sandbox_a,
        )
        collected_task_ids = {item.id for item in collected_bundle.tasks}
        assert task_a in collected_task_ids
        assert task_b not in collected_task_ids
        narrative_response = client.get(f"/api/v1/clients/{client_a}/narrative")
        assert narrative_response.status_code == 200, narrative_response.text
        assert "sandbox-a-narrative-secret" in narrative_response.text
        generated_dimension = {
            "narrative": "sandbox-a-regenerated-secret",
            "confidence": "high",
            "confidenceReason": "scope test",
            "references": [],
            "dataLayerGap": "",
            "openClarifications": [],
            "structuredTodos": [],
        }
        monkeypatch.setattr(
            "app.services.narrative_generator.generate_narrative_dimensions",
            lambda *_args, **_kwargs: ({"essence": generated_dimension}, 0.9, "scope-test"),
        )
        regenerate_response = client.post(
            f"/api/v1/clients/{client_a}/narrative/regenerate",
            json={},
        )
        assert regenerate_response.status_code == 200, regenerate_response.text
        regenerated_mirror = db.fetchone(
            "SELECT record_json, source FROM client_narrative_local_mirror WHERE client_id = ?",
            (client_a,),
        )
        assert regenerated_mirror is not None
        assert regenerated_mirror["source"] == "local-only"
        assert "sandbox-a-regenerated-secret" in regenerated_mirror["record_json"]

        activate_workspace(client, sandbox_b)
        for method, suffix in (
            ("get", "fact-bundle"),
            ("get", "narrative"),
            ("get", "narrative/stale-status"),
            ("post", "narrative/stale-clear"),
        ):
            response = getattr(client, method)(f"/api/v1/clients/{client_a}/{suffix}")
            assert response.status_code == 404, (suffix, response.status_code, response.text)
            assert "sandbox-a" not in response.text
        for suffix, payload in (
            ("narrative/clarifications", {}),
            ("narrative/regenerate", {}),
        ):
            response = client.post(
                f"/api/v1/clients/{client_a}/{suffix}",
                json=payload,
            )
            assert response.status_code == 404, (suffix, response.status_code, response.text)
            assert "sandbox-a" not in response.text
        response = client.get(f"/api/v1/clients/{client_a}/narrative/clarifications")
        assert response.status_code == 404, response.text
        assert "sandbox-a" not in response.text
        assert db.fetchone(
            "SELECT client_id FROM narrative_stale_signals WHERE client_id = ?",
            (client_a,),
        ) is not None
