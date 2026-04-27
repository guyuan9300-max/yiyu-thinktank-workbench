from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database, from_json
from app.services.data_center_ingest import ingest_user_input, mark_ingested_source_inactive
from app.services.data_center_schema import ensure_data_center_schema
from app.services.data_center_sync import build_data_center_sync_preview


NOW = "2026-04-24T10:00:00"


def _insert_client(db: Database, client_id: str = "client_sync") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, '益语平台', '益语平台', '公益科技', '客户', '公益组织数字化平台', '推进中', ?, ?)
        """,
        (client_id, NOW, NOW),
    )


def _work_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sourceType": "task",
        "sourceId": "task_sync",
        "title": "益语平台开源页修改",
        "bodyText": "本周完成开源页第二版修改，首屏从技术说明转向业务负责人能理解的价值表达。",
        "organizationId": "org_sync",
        "departmentId": "dept_product",
        "departmentIds": ["dept_product"],
        "ownerUserId": "user_owner",
        "sourceEntityType": "task",
        "sourceEntityId": "task_sync",
        "clientId": "client_sync",
        "eventLineId": "eline_sync",
        "taskId": "task_sync",
        "contentDomain": "work",
        "visibilityScope": "project_public",
        "metadata": {"source": "unit-test"},
    }
    payload.update(overrides)
    return payload


def _count(db: Database, query: str, params: tuple = ()) -> int:
    row = db.fetchone(query, params)
    return int(row["cnt"] if row else 0)


def _payload(row: object) -> dict[str, object]:
    return from_json(str(row["payload_json"]), {})  # type: ignore[index]


def test_ready_ingest_queues_sync_outbox_once(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)

    first = ingest_user_input(db, tmp_path / "data", _work_payload())
    second = ingest_user_input(db, tmp_path / "data", _work_payload())

    assert first["status"] == "ready"
    assert second["status"] == "ready"
    assert first["contentHash"] == second["contentHash"]
    assert _count(db, "SELECT COUNT(*) AS cnt FROM data_center_sync_outbox") == 1
    row = db.fetchone("SELECT * FROM data_center_sync_outbox LIMIT 1")
    assert row is not None
    payload = _payload(row)
    assert payload["sourceType"] == "task"
    assert payload["documentId"] == first["documentId"]
    assert payload["departmentIds"] == ["dept_product"]
    assert "开源页第二版修改" in str(payload["summary"])
    assert "path" not in str(payload).lower()


def test_private_ingest_not_queued_and_preview_reports_private(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)

    result = ingest_user_input(
        db,
        tmp_path / "data",
        _work_payload(
            sourceType="task_note",
            sourceId="note_private",
            sourceEntityType="task_note",
            sourceEntityId="note_private",
            contentDomain="personal",
            visibilityScope="self",
            title="个人复盘",
            bodyText="这是一条只给自己看的个人记录。",
        ),
    )

    assert result["status"] == "private_stored"
    preview = build_data_center_sync_preview(db)
    assert _count(db, "SELECT COUNT(*) AS cnt FROM data_center_sync_outbox") == 0
    assert preview["privateCount"] == 1
    assert preview["privateItems"][0]["reason"] == "ingest_status:private_stored"


def test_missing_permission_metadata_is_diagnostic_only(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)

    result = ingest_user_input(
        db,
        tmp_path / "data",
        _work_payload(
            sourceId="task_missing_meta",
            sourceEntityId="task_missing_meta",
            taskId="task_missing_meta",
            departmentId="",
            departmentIds=[],
            ownerUserId="",
        ),
    )

    assert result["status"] == "ready"
    assert _count(db, "SELECT COUNT(*) AS cnt FROM data_center_sync_outbox") == 0
    preview = build_data_center_sync_preview(db)
    assert preview["missingMetaCount"] == 1
    assert preview["missingMetaItems"][0]["reason"] == "missing_department_scope"


def test_weekly_review_entry_doc_can_become_sync_item(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)

    result = ingest_user_input(
        db,
        tmp_path / "data",
        _work_payload(
            sourceType="weekly_review_entry",
            sourceId="entry_sync",
            sourceEntityType="weekly_review_entry",
            sourceEntityId="entry_sync",
            taskId="task_sync",
            weekLabel="2026-W17",
            title="益语平台开源页复盘",
            bodyText="开源页已经完成第二版，下一步需要确认发布版本边界和负责人。",
        ),
    )

    assert result["status"] == "ready"
    row = db.fetchone("SELECT payload_json FROM data_center_sync_outbox WHERE source_type = 'weekly_review_entry'")
    assert row is not None
    payload = _payload(row)
    assert payload["sourceType"] == "weekly_review_entry"
    assert payload["weekLabel"] == "2026-W17"
    assert payload["document"]["canonicalKind"] == "review_entry_doc"
    assert "发布版本边界" in str(payload["summary"])


def test_attachment_sync_item_only_contains_reference_and_summary(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    db.execute(
        """
        INSERT INTO documents(
            id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at,
            organization_id, department_id, department_ids_json, owner_user_id, source_entity_type, source_entity_id,
            visibility_scope, content_domain, lifecycle_status
        ) VALUES(
            'doc_attachment', 'client_sync', NULL, '开源页说明.md', '/tmp/open-page.md', 'md', 'task_attachment',
            '说明平台价值表达和发布边界', '[]', ?,
            '', '', '[]', '', '', '', 'project_public', 'work', 'active'
        )
        """,
        (NOW,),
    )

    result = ingest_user_input(
        db,
        tmp_path / "data",
        _work_payload(
            sourceType="task_attachment",
            sourceId="att_sync",
            sourceEntityType="task_attachment",
            sourceEntityId="att_sync",
            title="开源页说明.md",
            bodyText="",
            documentId="doc_attachment",
        ),
    )

    assert result["status"] == "ready"
    row = db.fetchone("SELECT payload_json FROM data_center_sync_outbox WHERE source_type = 'task_attachment'")
    assert row is not None
    payload = _payload(row)
    assert payload["sourceType"] == "task_attachment"
    assert payload["documentId"] == "doc_attachment"
    assert "说明平台价值表达" in str(payload["summary"])
    payload_text = str(payload)
    assert "/tmp/open-page.md" not in payload_text
    assert "markdownContent" not in payload_text


def test_lifecycle_change_queues_tombstone_item(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    assert ingest_user_input(db, tmp_path / "data", _work_payload())["status"] == "ready"

    mark_ingested_source_inactive(db, source_type="task", source_id="task_sync", lifecycle_status="deleted")

    row = db.fetchone("SELECT lifecycle_status, payload_json FROM data_center_sync_outbox WHERE source_type = 'task'")
    assert row is not None
    assert row["lifecycle_status"] == "deleted"
    payload = _payload(row)
    assert payload["itemKind"] == "data_center_lifecycle"
    assert payload["syncAction"] == "tombstone"
    assert payload["lifecycleStatus"] == "deleted"


def test_schema_status_includes_sync_outbox(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")

    status = ensure_data_center_schema(db)

    assert "data_center_sync_outbox" in status["ensuredTables"]
