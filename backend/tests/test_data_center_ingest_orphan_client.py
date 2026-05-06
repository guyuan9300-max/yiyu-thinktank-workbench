from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database, from_json
from app.services import data_center_ingest
from app.services.data_center_ingest import (
    SKIPPED_ORPHAN_CLIENT_STATUS,
    build_orphan_client_ingest_repair_report,
    ensure_data_center_ingest_schema,
    ingest_event_line_by_id,
    ingest_task_by_id,
)


def make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def insert_client(db: Database, client_id: str = "client_ok") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, '有效客户', '有效客户', '公益', '陪伴', '', '推进中', '2026-05-04T00:00:00', '2026-05-04T00:00:00')
        """,
        (client_id,),
    )


def insert_task(db: Database, task_id: str, *, client_id: str, event_line_id: str | None = None) -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO task_lists(id, name, color, sort_order, is_default)
        VALUES('list-0', '默认', '#5B7BFE', 0, 1)
        """
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, status, priority, list_id,
            creator_id, owner_id, owner_name, progress_status, ddl, due_date,
            duration_minutes, scope_mode, event_line_id, business_category,
            current_blocker, next_action, recent_decision, evidence_count,
            source_type, source_id, tags_json, tag_ids_json, created_at, updated_at,
            last_synced_at, last_cloud_version, pending_sync_action, last_sync_error,
            client_id
        )
        VALUES(?, '', '历史任务', '任务描述', 'done', 'normal', 'list-0',
            'user_1', 'user_1', '顾源源', 'done', '', NULL,
            60, 'COLLAB_SHARED', ?, NULL,
            '', '下一步', '', 0,
            'manual', NULL, '[]', '[]', '2026-05-04T00:00:00', '2026-05-04T00:00:00',
            '', '', '', '', ?)
        """,
        (task_id, event_line_id, client_id),
    )


def insert_event_line(db: Database, event_line_id: str, *, client_id: str) -> None:
    db.execute(
        """
        INSERT INTO event_lines(
            id, organization_id, name, kind, status, business_category, stage,
            summary, intent, current_blocker, recent_decision, next_step, evidence_count,
            owner_id, owner_name, primary_client_id, primary_client_name,
            primary_department_id, primary_department_name, participant_ids_json,
            created_at, updated_at, sync_status, cloud_id, cloud_payload_json,
            last_synced_at, last_cloud_version, pending_sync_action, last_sync_error,
            visibility_scope
        )
        VALUES(?, '', '历史事件线', 'project_line', 'active', NULL, '推进中',
            '摘要', '意图', '', '', '下一步', 0,
            'user_1', '顾源源', ?, '已删除客户',
            NULL, NULL, '[]',
            '2026-05-04T00:00:00', '2026-05-04T00:00:00', 'local', NULL, '',
            '', '', '', '', 'project_public')
        """,
        (event_line_id, client_id),
    )


def test_stale_client_task_is_soft_isolated_without_document_upsert(tmp_path: Path, monkeypatch):
    db = make_db(tmp_path)
    insert_task(db, "task_stale", client_id="client_deleted")

    def fail_upsert(*args, **kwargs):
        raise AssertionError("stale client task must not upsert documents")

    monkeypatch.setattr(data_center_ingest, "upsert_canonical_text_document", fail_upsert)

    result = ingest_task_by_id(db, tmp_path / "data", "task_stale")

    assert result is not None
    assert result["status"] == SKIPPED_ORPHAN_CLIENT_STATUS
    assert result["errorMessage"] == "stale_client_id:client_deleted"
    assert db.scalar("SELECT COUNT(1) FROM documents") == 0
    assert db.scalar("SELECT COUNT(1) FROM v2_documents") == 0
    assert db.scalar("SELECT COUNT(1) FROM memory_facts WHERE source_entity_type = 'task'") == 0
    row = db.fetchone("SELECT * FROM data_center_ingest_events WHERE source_id = ?", ("task_stale",))
    assert row is not None
    assert row["status"] == SKIPPED_ORPHAN_CLIENT_STATUS
    assert row["lifecycle_status"] == "scope_released"
    metadata = from_json(row["metadata_json"], {})
    assert metadata["staleClientId"] == "client_deleted"
    assert metadata["softIsolated"] is True


def test_valid_client_task_still_generates_searchable_document(tmp_path: Path):
    db = make_db(tmp_path)
    insert_client(db, "client_ok")
    insert_task(db, "task_valid", client_id="client_ok")

    result = ingest_task_by_id(db, tmp_path / "data", "task_valid")

    assert result is not None
    assert result["status"] == "ready"
    assert db.scalar("SELECT COUNT(1) FROM documents WHERE client_id = 'client_ok' AND is_searchable = 1") == 1
    assert db.scalar("SELECT COUNT(1) FROM v2_documents WHERE client_id = 'client_ok' AND is_searchable = 1") == 1


def test_stale_event_line_primary_client_is_soft_isolated(tmp_path: Path):
    db = make_db(tmp_path)
    insert_event_line(db, "eline_stale", client_id="client_deleted")

    result = ingest_event_line_by_id(db, tmp_path / "data", "eline_stale")

    assert result is not None
    assert result["status"] == SKIPPED_ORPHAN_CLIENT_STATUS
    assert db.scalar("SELECT COUNT(1) FROM documents") == 0
    row = db.fetchone("SELECT status, error_message FROM data_center_ingest_events WHERE source_id = ?", ("eline_stale",))
    assert row["status"] == SKIPPED_ORPHAN_CLIENT_STATUS
    assert row["error_message"] == "stale_client_id:client_deleted"


def test_repair_report_apply_converts_fk_errors_to_orphan_terminal_state(tmp_path: Path):
    db = make_db(tmp_path)
    insert_task(db, "task_stale", client_id="client_deleted")
    ensure_data_center_ingest_schema(db)
    db.execute(
        """
        INSERT INTO data_center_ingest_events(
            id, source_type, source_id, source_version, content_hash,
            source_entity_type, source_entity_id, client_id, task_id, title,
            visibility_scope, content_domain, lifecycle_status, document_id, status, error_message,
            metadata_json, created_at, updated_at
        )
        VALUES(
            'dcing_bad', 'task', 'task_stale', '', 'hash1',
            'task', 'task_stale', 'client_deleted', 'task_stale', '历史任务',
            'project_public', 'work', 'active', NULL, 'error', 'FOREIGN KEY constraint failed',
            '{}', '2026-05-04T00:00:00', '2026-05-04T00:00:00'
        )
        """
    )

    preview = build_orphan_client_ingest_repair_report(db, apply=False)
    assert preview["orphanTaskCount"] == 1
    assert preview["fkErrorIngestEventCount"] == 1
    assert preview["repairedIngestEventCount"] == 0

    applied = build_orphan_client_ingest_repair_report(db, apply=True)

    assert applied["repairedIngestEventCount"] == 1
    row = db.fetchone("SELECT * FROM data_center_ingest_events WHERE id = 'dcing_bad'")
    assert row["status"] == SKIPPED_ORPHAN_CLIENT_STATUS
    assert row["error_message"] == "stale_client_id:client_deleted"
    assert row["lifecycle_status"] == "scope_released"
    assert db.scalar("SELECT COUNT(1) FROM tasks WHERE id = 'task_stale'") == 1
