from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import AnalysisJobCreatePayload  # noqa: E402
from app.services.ai import AiService  # noqa: E402
from app.services.analysis_center import (  # noqa: E402
    claim_next_analysis_job,
    create_analysis_job,
    fail_analysis_job,
    recover_stale_analysis_jobs,
)
from app.services.async_job_scope import (  # noqa: E402
    AsyncJobScopeError,
    backfill_async_job_sandbox_ids,
    load_persisted_job_workspace_context,
    resolve_client_workspace_context,
)
from app.services.sandbox_registry import (  # noqa: E402
    activate_sandbox,
    create_sandbox,
    ensure_sandbox_registry,
    set_sandbox_setting,
)
from app.services.smart_file_import import _bg_ingest_files  # noqa: E402
from app.services.workspace_context_refresh import (  # noqa: E402
    enqueue_workspace_context_refresh,
    ensure_workspace_context_refresh_schema,
)


def _seed_scope_fixture(db: Database) -> tuple[str, str]:
    ensure_sandbox_registry(db)
    sandbox_a = create_sandbox(
        db,
        kind="organization",
        name="组织 A",
        cloud_api_url="https://a.example.test",
    )
    sandbox_b = create_sandbox(
        db,
        kind="organization",
        name="组织 B",
        cloud_api_url="https://b.example.test",
    )
    for client_id, sandbox_id in (("client-a", sandbox_a.id), ("client-b", sandbox_b.id)):
        db.execute(
            """
            INSERT INTO clients(
                id, sandbox_id, name, alias, domain, type, intro, stage, color,
                created_at, updated_at
            )
            VALUES(?, ?, ?, ?, '公益', 'organization', '', 'active', '#5B7BFE', ?, ?)
            """,
            (client_id, sandbox_id, client_id, client_id, "2026-07-11T00:00:00", "2026-07-11T00:00:00"),
        )
    return sandbox_a.id, sandbox_b.id


def _analysis_payload(client_id: str = "client-a") -> AnalysisJobCreatePayload:
    return AnalysisJobCreatePayload(
        jobType="strategy_pack",
        clientId=client_id,
        scopeType="client",
        scopeId=client_id,
        question="同一个分析问题",
    )


def test_async_tables_have_nullable_sandbox_scope_and_scoped_indexes(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    ensure_workspace_context_refresh_schema(db)

    for table in ("knowledge_jobs", "analysis_jobs", "workspace_context_refresh_events"):
        columns = {str(row["name"]): row for row in db.fetchall(f"PRAGMA table_info({table})")}
        assert "sandbox_id" in columns
        assert int(columns["sandbox_id"]["notnull"] or 0) == 0
        indexes = {str(row["name"]) for row in db.fetchall(f"PRAGMA index_list({table})")}
        assert any("sandbox" in name for name in indexes)


def test_persisted_scope_survives_switch_and_rejects_empty_or_mismatch(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, sandbox_b = _seed_scope_fixture(db)

    assert resolve_client_workspace_context(db, "client-a").sandbox_id == sandbox_a
    activate_sandbox(db, sandbox_b)
    assert load_persisted_job_workspace_context(
        db,
        sandbox_id=sandbox_a,
        client_id="client-a",
    ).sandbox_id == sandbox_a

    with pytest.raises(AsyncJobScopeError, match="missing_sandbox_id"):
        load_persisted_job_workspace_context(db, sandbox_id=None, client_id="client-a")
    with pytest.raises(AsyncJobScopeError, match="client_sandbox_mismatch"):
        load_persisted_job_workspace_context(db, sandbox_id=sandbox_b, client_id="client-a")
    with pytest.raises(AsyncJobScopeError, match="client_not_found"):
        load_persisted_job_workspace_context(db, sandbox_id=sandbox_a, client_id="orphan-client")


def test_backfill_is_parent_derived_idempotent_and_never_guesses_or_overwrites(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, sandbox_b = _seed_scope_fixture(db)
    ensure_workspace_context_refresh_schema(db)
    now = "2026-07-11T00:00:00"
    db.execute(
        """
        INSERT INTO knowledge_jobs(
            id, client_id, job_type, status, payload_json, created_at, updated_at, sandbox_id
        ) VALUES('kj-parent', 'client-a', 'test', 'queued', '{}', ?, ?, NULL)
        """,
        (now, now),
    )
    db.execute("PRAGMA foreign_keys=OFF")
    db.execute(
        """
        INSERT INTO analysis_jobs(
            id, job_type, client_id, scope_type, scope_id, status, created_at, updated_at, sandbox_id
        ) VALUES('aj-orphan', 'client_analysis', 'missing-client', 'client', 'missing-client', 'queued', ?, ?, NULL)
        """,
        (now, now),
    )
    db.execute("PRAGMA foreign_keys=ON")
    db.execute(
        """
        INSERT INTO workspace_context_refresh_events(
            id, client_id, scope_type, scope_id, source_type, reason, dedupe_key,
            created_at, updated_at, sandbox_id
        ) VALUES('rf-mismatch', 'client-a', 'client', 'client-a', 'test', 'test', 'test', ?, ?, ?)
        """,
        (now, now, sandbox_b),
    )

    first = backfill_async_job_sandbox_ids(db)
    second = backfill_async_job_sandbox_ids(db)

    assert first["knowledge_jobs"] == 1
    assert second == {"knowledge_jobs": 0, "analysis_jobs": 0, "workspace_context_refresh_events": 0}
    assert db.fetchone("SELECT sandbox_id FROM knowledge_jobs WHERE id='kj-parent'")["sandbox_id"] == sandbox_a
    assert db.fetchone("SELECT sandbox_id FROM analysis_jobs WHERE id='aj-orphan'")["sandbox_id"] is None
    assert db.fetchone("SELECT sandbox_id FROM workspace_context_refresh_events WHERE id='rf-mismatch'")["sandbox_id"] == sandbox_b


def test_analysis_job_scope_is_persisted_and_dedupe_is_concurrency_safe(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, sandbox_b = _seed_scope_fixture(db)
    payload = _analysis_payload()

    with ThreadPoolExecutor(max_workers=6) as executor:
        jobs = list(executor.map(lambda _: create_analysis_job(db, payload), range(6)))

    assert {job.id for job in jobs} == {jobs[0].id}
    assert jobs[0].sandboxId == sandbox_a
    assert db.scalar("SELECT COUNT(1) FROM analysis_jobs WHERE status IN ('queued','running')") == 1

    db.execute("UPDATE analysis_jobs SET status='completed' WHERE id=?", (jobs[0].id,))
    db.execute("UPDATE clients SET sandbox_id=? WHERE id='client-a'", (sandbox_b,))
    moved_job = create_analysis_job(db, payload)
    assert moved_job.id != jobs[0].id
    assert moved_job.sandboxId == sandbox_b
    assert moved_job.dedupeKey != jobs[0].dedupeKey


def test_refresh_event_scope_is_persisted_and_dedupe_is_concurrency_safe(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, sandbox_b = _seed_scope_fixture(db)

    def enqueue(_: int):
        return enqueue_workspace_context_refresh(
            db,
            client_id="client-a",
            source_type="test",
            reason="same-reason",
        )

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(enqueue, range(6)))

    assert {record.id for record, _ in results} == {results[0][0].id}
    assert results[0][0].sandboxId == sandbox_a
    assert sum(1 for _record, deduped in results if not deduped) == 1

    db.execute("UPDATE workspace_context_refresh_events SET status='completed'")
    db.execute("UPDATE clients SET sandbox_id=? WHERE id='client-a'", (sandbox_b,))
    moved, deduped = enqueue(0)
    assert deduped is False
    assert moved.sandboxId == sandbox_b
    assert moved.dedupeKey != results[0][0].dedupeKey


def test_persisted_scope_rejects_archived_workspace(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, _sandbox_b = _seed_scope_fixture(db)
    db.execute("UPDATE sandboxes SET status='archived' WHERE id=?", (sandbox_a,))

    with pytest.raises(AsyncJobScopeError, match="sandbox_not_active"):
        load_persisted_job_workspace_context(db, sandbox_id=sandbox_a, client_id="client-a")


def test_analysis_restart_recovery_keeps_original_scope_after_active_switch(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, sandbox_b = _seed_scope_fixture(db)
    job = create_analysis_job(db, _analysis_payload())

    first_claim = claim_next_analysis_job(db, "worker-before-restart")
    assert first_claim is not None
    assert first_claim.id == job.id
    assert first_claim.sandboxId == sandbox_a

    activate_sandbox(db, sandbox_b)
    recover_stale_analysis_jobs(db)
    second_claim = claim_next_analysis_job(db, "worker-after-restart")

    assert second_claim is not None
    assert second_claim.id == job.id
    assert second_claim.sandboxId == sandbox_a
    assert second_claim.attemptCount == 2
    assert load_persisted_job_workspace_context(
        db,
        sandbox_id=second_claim.sandboxId,
        client_id=second_claim.clientId,
    ).sandbox_id == sandbox_a


def test_analysis_worker_rejects_status_write_after_persisted_scope_changes(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, sandbox_b = _seed_scope_fixture(db)
    job = create_analysis_job(db, _analysis_payload())
    claimed = claim_next_analysis_job(db, "worker-scope-cas")
    assert claimed is not None
    assert claimed.sandboxId == sandbox_a

    db.execute(
        "UPDATE analysis_jobs SET sandbox_id = ? WHERE id = ?",
        (sandbox_b, job.id),
    )

    with pytest.raises(AsyncJobScopeError, match="job_scope_changed"):
        fail_analysis_job(
            db,
            job.id,
            stage_name="analysis_pipeline",
            error="forced failure",
            retryable=False,
            expected_sandbox_id=sandbox_a,
        )

    row = db.fetchone("SELECT sandbox_id, status FROM analysis_jobs WHERE id = ?", (job.id,))
    assert row is not None
    assert row["sandbox_id"] == sandbox_b
    assert row["status"] == "running"


def test_ai_service_override_pins_settings_to_persisted_scope(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, sandbox_b = _seed_scope_fixture(db)
    set_sandbox_setting(db, sandbox_a, "ai_provider", "mock")
    set_sandbox_setting(db, sandbox_b, "ai_provider", "mock")
    set_sandbox_setting(db, sandbox_a, "ai_model", "model-for-a")
    set_sandbox_setting(db, sandbox_b, "ai_model", "model-for-b")
    activate_sandbox(db, sandbox_b)
    ai = AiService(db, {})

    assert ai.current_model() == "model-for-b"
    with ai.use_sandbox(sandbox_a):
        assert ai.current_model() == "model-for-a"
    assert ai.current_model() == "model-for-b"


def test_knowledge_worker_uses_persisted_scope_when_active_workspace_changed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This is the one test in the module that intentionally exercises the
    # application-managed knowledge worker.  The global test fixture disables
    # automatic daemon startup for isolation, so opt in explicitly here.
    monkeypatch.delenv("YIYU_DISABLE_STARTUP_WORKERS", raising=False)
    app = create_app(tmp_path / "data")
    db = app.state.app_state.db
    sandbox_a, sandbox_b = _seed_scope_fixture(db)
    now = "2026-07-11T00:00:00"

    activate_sandbox(db, sandbox_a)
    db.execute(
        """
        INSERT INTO knowledge_jobs(
            id, client_id, sandbox_id, job_type, status, payload_json, created_at, updated_at
        ) VALUES('kj-switch-before-worker', 'client-a', ?, 'scope_probe', 'queued', '{}', ?, ?)
        """,
        (sandbox_a, now, now),
    )
    activate_sandbox(db, sandbox_b)

    with TestClient(app):
        deadline = time.monotonic() + 5
        row = db.fetchone(
            "SELECT status, last_error, sandbox_id FROM knowledge_jobs WHERE id='kj-switch-before-worker'"
        )
        while row is not None and str(row["status"]) not in {"completed", "failed"} and time.monotonic() < deadline:
            time.sleep(0.05)
            row = db.fetchone(
                "SELECT status, last_error, sandbox_id FROM knowledge_jobs WHERE id='kj-switch-before-worker'"
            )

    assert row is not None
    assert row["status"] == "failed"
    assert row["sandbox_id"] == sandbox_a
    assert "未知任务类型" in str(row["last_error"] or "")
    assert "async_job_scope" not in str(row["last_error"] or "")


def test_smart_import_daemon_pins_ai_and_job_updates_to_persisted_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = Database(tmp_path / "app.db")
    sandbox_a, sandbox_b = _seed_scope_fixture(db)
    db.execute("UPDATE sandboxes SET organization_id='org-a' WHERE id=?", (sandbox_a,))
    db.execute("UPDATE sandboxes SET organization_id='org-b' WHERE id=?", (sandbox_b,))
    now = "2026-07-11T00:00:00"
    db.execute(
        """
        INSERT INTO knowledge_jobs(
            id, client_id, sandbox_id, job_type, status, payload_json,
            total_items, processed_items, created_at, started_at, updated_at
        ) VALUES('kj-smart-a', 'client-a', ?, 'smart_import_ingest', 'running', '{}', 1, 0, ?, ?, ?)
        """,
        (sandbox_a, now, now, now),
    )
    activate_sandbox(db, sandbox_b)

    class ScopedAi:
        bound_sandbox_id: str | None = None

        @contextmanager
        def use_sandbox(self, sandbox_id: str):
            previous = self.bound_sandbox_id
            self.bound_sandbox_id = sandbox_id
            try:
                yield
            finally:
                self.bound_sandbox_id = previous

    ai = ScopedAi()
    observed: list[tuple[str | None, str | None]] = []

    def ingest_document(*_args, ai_service=None, **_kwargs) -> None:
        observed.append((ai_service.bound_sandbox_id, _kwargs.get("organization_id")))

    monkeypatch.setattr(
        "app.services.data_center_broadcast.broadcast_data_changed",
        lambda *_args, **_kwargs: None,
    )
    _bg_ingest_files(
        db,
        ingest_document,
        ai,
        tmp_path,
        "client-a",
        sandbox_a,
        "kj-smart-a",
        [
            {
                "doc_id": "doc-a",
                "dest": str(tmp_path / "doc-a.md"),
                "title": "A",
                "kind": "md",
                "excerpt": "A",
            }
        ],
    )

    row = db.fetchone(
        "SELECT sandbox_id, status, processed_items, last_error FROM knowledge_jobs WHERE id='kj-smart-a'"
    )
    assert observed == [(sandbox_a, "org-a")]
    assert row is not None
    assert row["sandbox_id"] == sandbox_a
    assert row["status"] == "completed"
    assert row["processed_items"] == 1
    assert not row["last_error"]
    assert ai.bound_sandbox_id is None


def test_sandbox_audits_cover_all_async_job_tables() -> None:
    root = Path(__file__).resolve().parents[2]
    expected = {"knowledge_jobs", "analysis_jobs", "workspace_context_refresh_events"}
    for relative_path, variable_name in (
        ("scripts/audit_sandbox_contract.py", "DIRECT_SANDBOX_TABLES"),
        ("scripts/audit_sandbox_queries.py", "SENSITIVE_TABLES"),
    ):
        namespace: dict[str, object] = {"__file__": str(root / relative_path), "__name__": "audit_test"}
        exec(compile((root / relative_path).read_text(encoding="utf-8"), relative_path, "exec"), namespace)
        assert expected <= set(namespace[variable_name])
