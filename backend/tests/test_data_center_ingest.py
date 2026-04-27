from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database, to_json
from app.services.data_center_ingest import (
    ingest_event_line_by_id,
    ingest_meeting_by_id,
    ingest_task_attachment_by_id,
    ingest_task_by_id,
    ingest_task_note_by_id,
    ingest_weekly_review_by_id,
    mark_ingested_source_inactive,
)
from app.services.knowledge_v2 import retrieve_knowledge_bundle


NOW = "2026-04-24T10:00:00"


def _insert_client(db: Database, client_id: str = "client_ingest") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, '益语平台', '益语平台', '公益科技', '客户', '公益组织数字化平台', '推进中', ?, ?)
        """,
        (client_id, NOW, NOW),
    )


def _insert_task_list(db: Database) -> None:
    db.execute(
        """
        INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope)
        VALUES('list_ingest', '', '本周任务', '#5B7BFE', 0, 1, 'org')
        """
    )


def _insert_event_line(
    db: Database,
    event_line_id: str = "eline_ingest",
    client_id: str = "client_ingest",
    *,
    visibility_scope: str = "project_public",
) -> None:
    db.execute(
        """
        INSERT INTO event_lines(
            organization_id,
            id, name, stage, summary, intent, current_blocker, recent_decision, next_step,
            owner_id, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            visibility_scope, participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, '益语平台建设', '交付校准', '开源页和平台表达正在调整', '面向业务负责人说清价值',
            '转化表达还需校准', '先改开源页面', '确认版本发布边界', 'user_owner',
            ?, '益语平台', 'dept_ingest', '产品部', ?, '[]', ?, ?)
        """,
        ("org_ingest", event_line_id, client_id, visibility_scope, NOW, NOW),
    )


def _insert_task(
    db: Database,
    task_id: str = "task_ingest",
    *,
    title: str = "益语平台开源页面修改",
    client_id: str = "client_ingest",
    event_line_id: str = "eline_ingest",
    scope_mode: str = "COLLAB_SHARED",
) -> None:
    db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, status, priority, list_id, creator_id, owner_id, owner_name,
            progress_status, ddl, due_date, duration_minutes, scope_mode, client_id, event_line_id,
            current_blocker, next_action, recent_decision, source_type, source_id,
            tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, 'org_ingest', ?, '把平台首屏从技术说明改成业务价值表达', 'done', 'normal', 'list_ingest',
            'user_creator', 'user_owner', '高原', 'done', '4月24日', '2026-04-24', 60, ?, ?, ?,
            '目标用户表达需要再校准', '确认发布版本边界', '开源页第二版已完成', 'manual', NULL,
            '[]', '[]', ?, ?)
        """,
        (task_id, title, scope_mode, client_id, event_line_id, NOW, NOW),
    )


def _count(db: Database, query: str, params: tuple = ()) -> int:
    row = db.fetchone(query, params)
    return int(row["cnt"] if row else 0)


def test_task_ingest_is_idempotent_and_writes_docs_and_facts(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db)
    _insert_task(db)
    db.execute(
        """
        INSERT INTO task_notes(id, task_id, note, created_at, updated_at)
        VALUES('note_ingest', 'task_ingest', '首屏需要突出业务负责人能理解的价值。', ?, ?)
        """,
        (NOW, NOW),
    )

    first = ingest_task_by_id(db, tmp_path / "data", "task_ingest")
    second = ingest_task_by_id(db, tmp_path / "data", "task_ingest")

    assert first is not None
    assert second is not None
    assert first["contentHash"] == second["contentHash"]
    assert _count(
        db,
        "SELECT COUNT(*) AS cnt FROM data_center_ingest_events WHERE source_type = 'task' AND source_id = 'task_ingest'",
    ) == 1
    assert db.fetchone(
        "SELECT id FROM v2_documents WHERE canonical_kind = 'task_doc' AND origin_type = 'task' AND origin_id = 'task_ingest'"
    )
    task_doc = db.fetchone(
        "SELECT markdown_content FROM v2_documents WHERE canonical_kind = 'task_doc' AND origin_id = 'task_ingest'"
    )
    assert task_doc is not None
    assert "首屏需要突出业务负责人能理解的价值" in str(task_doc["markdown_content"])
    scopes = {
        str(row["scope_type"])
        for row in db.fetchall(
            "SELECT scope_type FROM memory_facts WHERE source_type = 'task' AND source_id LIKE 'task_ingest:%'"
        )
    }
    assert {"task", "client", "event_line"}.issubset(scopes)


def test_private_task_note_stays_out_of_client_documents(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db)
    _insert_task(db, task_id="task_private", title="个人成长记录", scope_mode="PERSONAL_ONLY")
    db.execute(
        """
        INSERT INTO task_notes(id, task_id, note, created_at, updated_at)
        VALUES('note_private', 'task_private', '这是一条只给自己看的个人复盘。', ?, ?)
        """,
        (NOW, NOW),
    )

    result = ingest_task_note_by_id(db, tmp_path / "data", "task_private")

    assert result is not None
    assert result["status"] == "private_stored"
    assert _count(
        db,
        """
        SELECT COUNT(*) AS cnt
        FROM v2_documents
        WHERE canonical_kind = 'task_note_doc' AND origin_id = 'task_private'
        """,
    ) == 0
    scopes = {
        str(row["scope_type"])
        for row in db.fetchall(
            "SELECT scope_type FROM memory_facts WHERE source_type = 'task_note' AND source_id LIKE 'task_private:%'"
        )
    }
    assert "person" in scopes
    assert "client" not in scopes
    assert "event_line" not in scopes


def test_task_attachment_binds_existing_document_without_creating_attachment_doc(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db)
    _insert_task(db)
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_existing', 'client_ingest', NULL, '开源页说明.md', '/tmp/open.md', 'md', 'task_attachment',
            '说明平台价值表达和发布边界', '[]', ?)
        """,
        (NOW,),
    )
    db.execute(
        """
        INSERT INTO task_attachments(id, task_id, client_id, event_line_id, document_id, title, path, kind, source, size_bytes, created_at)
        VALUES('att_existing', 'task_ingest', 'client_ingest', 'eline_ingest', 'doc_existing',
            '开源页说明.md', '/tmp/open.md', 'md', 'upload', 128, ?)
        """,
        (NOW,),
    )

    result = ingest_task_attachment_by_id(db, tmp_path / "data", "att_existing")

    assert result is not None
    assert result["documentId"] == "doc_existing"
    row = db.fetchone(
        """
        SELECT document_id, status
        FROM data_center_ingest_events
        WHERE source_type = 'task_attachment' AND source_id = 'att_existing'
        """
    )
    assert row is not None
    assert row["document_id"] == "doc_existing"
    assert row["status"] == "ready"
    assert _count(
        db,
        """
        SELECT COUNT(*) AS cnt
        FROM v2_documents
        WHERE origin_type = 'task_attachment' AND origin_id = 'att_existing'
        """,
    ) == 0


def test_meeting_review_and_event_line_ingest_cover_user_inputs(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db)
    _insert_task(db)
    db.execute(
        """
        INSERT INTO meetings(id, client_id, title, stage, scheduled_at, transcript_text, notes, created_at, updated_at)
        VALUES('meeting_ingest', 'client_ingest', '益语平台周会', 'extracted', '2026-04-24T09:00:00',
            '讨论开源页表达和发布范围', '确认先面向业务负责人重写首屏', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute(
        "INSERT INTO decisions(id, meeting_id, summary, created_at) VALUES('dec_ingest', 'meeting_ingest', '先确认发布版本边界', ?)",
        (NOW,),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, work_progress, work_direction, personal_private_note, created_at, updated_at)
        VALUES('review_ingest', '2026-W17', '本周完成开源页调整', '平台表达进入校准阶段',
            '下周确认发布边界', '个人压力记录', ?, ?)
        """,
        (NOW, NOW),
    )
    snapshot = {
        "title": "益语平台开源页面修改",
        "status": "done",
        "clientId": "client_ingest",
        "eventLineId": "eline_ingest",
    }
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json,
            reviewed_at, task_snapshot_json, created_at, updated_at
        ) VALUES('entry_ingest', 'review_ingest', 'task_ingest', '2026-W17', 'work',
            '完成开源页修改，需要确认发布标准。', ?, ?, ?, ?, ?)
        """,
        (to_json({"nextAction": "确认发布版本边界"}), NOW, to_json(snapshot), NOW, NOW),
    )

    assert ingest_meeting_by_id(db, tmp_path / "data", "meeting_ingest") is not None
    assert ingest_weekly_review_by_id(db, tmp_path / "data", "review_ingest") is not None
    assert ingest_event_line_by_id(db, tmp_path / "data", "eline_ingest") is not None

    source_types = {
        str(row["source_type"])
        for row in db.fetchall("SELECT source_type FROM data_center_ingest_events")
    }
    assert {"meeting", "weekly_review", "weekly_review_entry", "event_line_manual_update"}.issubset(source_types)
    assert db.fetchone(
        "SELECT id FROM v2_documents WHERE canonical_kind = 'meeting_doc' AND origin_id = 'meeting_ingest'"
    )
    assert db.fetchone(
        "SELECT id FROM v2_documents WHERE canonical_kind = 'review_entry_doc' AND source_entity_id = 'entry_ingest' AND lifecycle_status = 'active'"
    )
    private_row = db.fetchone(
        """
        SELECT status
        FROM data_center_ingest_events
        WHERE source_type = 'weekly_review' AND source_id = 'review_ingest:personal_private'
        """
    )
    assert private_row is not None
    assert private_row["status"] == "private_stored"


def test_ingest_writes_permission_and_source_metadata(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db)
    _insert_task(db)

    result = ingest_task_by_id(db, tmp_path / "data", "task_ingest")

    assert result is not None
    doc = db.fetchone(
        """
        SELECT organization_id, department_id, owner_user_id, source_entity_type, source_entity_id,
               visibility_scope, content_domain, lifecycle_status
        FROM v2_documents
        WHERE canonical_kind = 'task_doc' AND origin_type = 'task' AND origin_id = 'task_ingest'
        """
    )
    assert doc is not None
    assert doc["organization_id"] == "org_ingest"
    assert doc["department_id"] == "dept_ingest"
    assert doc["owner_user_id"] == "user_owner"
    assert doc["source_entity_type"] == "task"
    assert doc["source_entity_id"] == "task_ingest"
    assert doc["visibility_scope"] == "project_public"
    assert doc["content_domain"] == "work"
    assert doc["lifecycle_status"] == "active"
    fact = db.fetchone(
        """
        SELECT department_id, source_entity_type, source_entity_id, lifecycle_status
        FROM memory_facts
        WHERE source_type = 'task' AND scope_type = 'task' AND scope_id = 'task_ingest'
        LIMIT 1
        """
    )
    assert fact is not None
    assert fact["department_id"] == "dept_ingest"
    assert fact["source_entity_id"] == "task_ingest"


def test_private_event_line_update_does_not_create_client_document_or_fact(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_event_line(db, visibility_scope="self")

    result = ingest_event_line_by_id(db, tmp_path / "data", "eline_ingest")

    assert result is not None
    assert result["status"] == "private_stored"
    assert _count(
        db,
        """
        SELECT COUNT(*) AS cnt
        FROM v2_documents
        WHERE canonical_kind = 'event_line_update_doc' AND source_entity_id = 'eline_ingest'
        """,
    ) == 0
    assert _count(
        db,
        """
        SELECT COUNT(*) AS cnt
        FROM memory_facts
        WHERE source_type = 'event_line_manual_update' AND scope_type = 'client'
        """,
    ) == 0


def test_private_task_attachment_marks_bound_document_unsearchable(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db)
    _insert_task(db, task_id="task_private_attachment", title="个人附件", scope_mode="PERSONAL_ONLY")
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_private_attachment', 'client_ingest', NULL, '个人记录.md', '/tmp/private.md', 'md', 'task_attachment',
            '个人记录', '[]', ?)
        """,
        (NOW,),
    )
    db.execute(
        """
        INSERT INTO task_attachments(id, task_id, client_id, event_line_id, document_id, title, path, kind, source, size_bytes, created_at)
        VALUES('att_private', 'task_private_attachment', 'client_ingest', 'eline_ingest', 'doc_private_attachment',
            '个人记录.md', '/tmp/private.md', 'md', 'upload', 128, ?)
        """,
        (NOW,),
    )

    result = ingest_task_attachment_by_id(db, tmp_path / "data", "att_private")

    assert result is not None
    doc = db.fetchone(
        """
        SELECT visibility_scope, content_domain, source_entity_type, source_entity_id, is_searchable
        FROM documents
        WHERE id = 'doc_private_attachment'
        """
    )
    assert doc is not None
    assert doc["visibility_scope"] == "self"
    assert doc["content_domain"] == "personal"
    assert doc["source_entity_type"] == "task_attachment"
    assert doc["source_entity_id"] == "att_private"
    assert int(doc["is_searchable"]) == 0


def test_inactive_task_document_is_excluded_from_retrieval(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db)
    _insert_task(db)
    assert ingest_task_by_id(db, tmp_path / "data", "task_ingest") is not None

    before = retrieve_knowledge_bundle(db, tmp_path / "data", "client_ingest", "业务负责人价值表达")
    assert before.citations

    mark_ingested_source_inactive(db, source_type="task", source_id="task_ingest", lifecycle_status="deleted")

    doc = db.fetchone(
        "SELECT lifecycle_status, is_searchable FROM v2_documents WHERE canonical_kind = 'task_doc' AND origin_id = 'task_ingest'"
    )
    assert doc is not None
    assert doc["lifecycle_status"] == "deleted"
    assert int(doc["is_searchable"]) == 0
    after = retrieve_knowledge_bundle(db, tmp_path / "data", "client_ingest", "业务负责人价值表达")
    assert not after.citations


def test_weekly_review_entry_edit_supersedes_previous_doc(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db)
    _insert_task(db)
    db.execute(
        """
        INSERT INTO weekly_reviews(id, organization_id, user_id, week_label, summary, work_progress, work_direction, created_at, updated_at)
        VALUES('review_versioned', 'org_ingest', 'user_owner', '2026-W17', '本周复盘', '', '', ?, ?)
        """,
        (NOW, NOW),
    )
    snapshot = {
        "title": "益语平台开源页面修改",
        "clientId": "client_ingest",
        "eventLineId": "eline_ingest",
        "departmentId": "dept_ingest",
        "ownerId": "user_owner",
    }
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, organization_id, review_id, task_id, user_id, week_label, content_domain, note,
            structured_note_json, reviewed_at, task_snapshot_json, created_at, updated_at
        ) VALUES('entry_versioned', 'org_ingest', 'review_versioned', 'task_ingest', 'user_owner', '2026-W17',
            'work', '第一版复盘', '{}', ?, ?, ?, ?)
        """,
        (NOW, to_json(snapshot), NOW, NOW),
    )

    assert ingest_weekly_review_by_id(db, tmp_path / "data", "review_versioned") is not None
    first_doc = db.fetchone(
        "SELECT id FROM v2_documents WHERE canonical_kind = 'review_entry_doc' AND source_entity_id = 'entry_versioned' AND lifecycle_status = 'active'"
    )
    assert first_doc is not None

    db.execute(
        """
        UPDATE weekly_review_task_entries
        SET note = '第二版复盘，补充了发布边界。', updated_at = '2026-04-24T11:00:00'
        WHERE id = 'entry_versioned'
        """
    )
    assert ingest_weekly_review_by_id(db, tmp_path / "data", "review_versioned") is not None

    rows = db.fetchall(
        """
        SELECT id, lifecycle_status
        FROM v2_documents
        WHERE canonical_kind = 'review_entry_doc' AND source_entity_id = 'entry_versioned'
        ORDER BY updated_at ASC
        """
    )
    statuses = [str(row["lifecycle_status"]) for row in rows]
    assert statuses.count("superseded") == 1
    assert statuses.count("active") == 1
