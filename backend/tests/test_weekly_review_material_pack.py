from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database, to_json
from app.services.data_center_access import DataCenterAccessContext
from app.services.data_center_ingest import ingest_weekly_review_by_id
from app.services.knowledge_v2 import upsert_canonical_text_document
from app.services.weekly_review_material_pack import build_weekly_review_material_pack


NOW = "2026-04-24T10:00:00"
WEEK = "2026-W17"


def _insert_client(db: Database, client_id: str = "client_pack", name: str = "益语平台") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, ?, ?, '公益科技', '客户', '公益组织数字化平台', '推进中', ?, ?)
        """,
        (client_id, name, name, NOW, NOW),
    )


def _insert_task_list(db: Database) -> None:
    db.execute(
        """
        INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope)
        VALUES('list_pack', 'org_pack', '本周任务', '#5B7BFE', 0, 1, 'org')
        """
    )


def _insert_event_line(
    db: Database,
    event_line_id: str,
    *,
    client_id: str = "client_pack",
    name: str,
    department_id: str,
    owner_id: str,
    visibility_scope: str = "project_public",
) -> None:
    db.execute(
        """
        INSERT INTO event_lines(
            organization_id,
            id, name, stage, summary, intent, current_blocker, recent_decision, next_step,
            owner_id, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            visibility_scope, participant_ids_json, created_at, updated_at
        ) VALUES('org_pack', ?, ?, '推进中', '本周围绕项目材料和任务推进', '形成可交付成果',
            '', '完成阶段性调整', '确认下一版交付边界', ?, ?, '益语平台', ?, '部门',
            ?, '[]', ?, ?)
        """,
        (event_line_id, name, owner_id, client_id, department_id, visibility_scope, NOW, NOW),
    )


def _insert_task(
    db: Database,
    task_id: str,
    *,
    title: str,
    owner_id: str,
    client_id: str = "client_pack",
    event_line_id: str = "",
    due_date: str = "2026-04-24",
    status: str = "done",
    scope_mode: str = "COLLAB_SHARED",
) -> None:
    db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, status, priority, list_id, creator_id, owner_id, owner_name,
            progress_status, ddl, due_date, duration_minutes, scope_mode, client_id, event_line_id,
            current_blocker, next_action, recent_decision, source_type, source_id,
            tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, 'org_pack', ?, '本周完成关键推进，等待复盘沉淀。', ?, 'normal', 'list_pack',
            ?, ?, '成员', ?, '4月24日', ?, 60, ?, ?, ?,
            '', '确认负责人、交付物和完成时间', '已完成阶段性任务', 'manual', NULL,
            '[]', '[]', ?, ?)
        """,
        (
            task_id,
            title,
            status,
            owner_id,
            owner_id,
            "done" if status == "done" else "doing",
            due_date,
            scope_mode,
            client_id,
            event_line_id,
            NOW,
            NOW,
        ),
    )


def _insert_weekly_review(db: Database, review_id: str = "review_pack", *, user_id: str = "lead_a") -> None:
    db.execute(
        """
        INSERT INTO weekly_reviews(
            id, organization_id, user_id, week_label, summary, work_progress, work_direction,
            created_at, updated_at
        ) VALUES(?, 'org_pack', ?, ?, '本周复盘', '完成本周关键任务', '下周确认交付边界', ?, ?)
        """,
        (review_id, user_id, WEEK, NOW, NOW),
    )


def _insert_review_entry(
    db: Database,
    entry_id: str,
    *,
    review_id: str = "review_pack",
    task_id: str,
    user_id: str,
    title: str,
    department_id: str = "",
    owner_id: str,
    client_id: str = "client_pack",
    event_line_id: str = "",
    content_domain: str = "work",
    note: str,
    updated_at: str = NOW,
) -> None:
    snapshot = {
        "title": title,
        "status": "done",
        "clientId": client_id,
        "eventLineId": event_line_id,
        "departmentId": department_id,
        "ownerId": owner_id,
    }
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, organization_id, review_id, task_id, user_id, week_label, content_domain, note,
            structured_note_json, reviewed_at, task_snapshot_json, created_at, updated_at
        ) VALUES(?, 'org_pack', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            review_id,
            task_id,
            user_id,
            WEEK,
            content_domain,
            note,
            to_json({"progress": note, "nextAction": "确认下一步交付标准"}),
            updated_at,
            to_json(snapshot),
            NOW,
            updated_at,
        ),
    )


def _seed_pack_data(db: Database, data_dir: Path) -> None:
    _insert_client(db)
    _insert_task_list(db)
    _insert_event_line(db, "eline_a", name="益语平台建设", department_id="dept_a", owner_id="lead_a")
    _insert_event_line(db, "eline_b", name="云南材料交付", department_id="dept_b", owner_id="lead_b")
    _insert_event_line(db, "eline_private", name="个人记录", department_id="dept_a", owner_id="user_private", visibility_scope="self")
    _insert_task(db, "task_a", title="益语平台开源页面修改", owner_id="lead_a", event_line_id="eline_a")
    _insert_task(db, "task_b", title="云南报告结构调整", owner_id="lead_b", event_line_id="eline_b")
    _insert_task(db, "task_private", title="个人私密复盘", owner_id="user_private", event_line_id="eline_private", scope_mode="PERSONAL_ONLY")
    _insert_weekly_review(db)
    _insert_review_entry(
        db,
        "entry_a",
        task_id="task_a",
        user_id="lead_a",
        title="益语平台开源页面修改",
        department_id="dept_a",
        owner_id="lead_a",
        event_line_id="eline_a",
        note="完成开源页面修改，平台表达进入价值校准。",
    )
    _insert_review_entry(
        db,
        "entry_b",
        task_id="task_b",
        user_id="lead_b",
        title="云南报告结构调整",
        department_id="dept_b",
        owner_id="lead_b",
        event_line_id="eline_b",
        note="完成云南报告结构调整，交付材料进入最终修订。",
    )
    _insert_review_entry(
        db,
        "entry_private",
        task_id="task_private",
        user_id="user_private",
        title="个人私密复盘",
        department_id="dept_a",
        owner_id="user_private",
        event_line_id="eline_private",
        content_domain="personal",
        note="只给自己看的复盘。",
    )
    assert ingest_weekly_review_by_id(db, data_dir, "review_pack") is not None


def _build_pack(db: Database, data_dir: Path, context: DataCenterAccessContext) -> dict:
    return build_weekly_review_material_pack(
        db=db,
        data_dir=data_dir,
        access_context=context,
        week_label=WEEK,
    )


def _task_ids(pack: dict) -> set[str]:
    return {str(item.get("taskId")) for item in pack.get("tasks", [])}


def _entry_ids(pack: dict) -> set[str]:
    return {str(item.get("entryId")) for item in pack.get("reviewEntries", [])}


def test_ceo_pack_can_see_multi_department_work_without_private_content(tmp_path: Path) -> None:
    db = Database(tmp_path / "pack.db")
    data_dir = tmp_path / "data"
    _seed_pack_data(db, data_dir)

    pack = _build_pack(db, data_dir, DataCenterAccessContext(organization_id="org_pack", role="ceo"))

    assert {"task_a", "task_b"}.issubset(_task_ids(pack))
    assert "task_private" not in _task_ids(pack)
    assert {"entry_a", "entry_b"}.issubset(_entry_ids(pack))
    assert "entry_private" not in _entry_ids(pack)
    assert pack["sourceCounts"]["tasks"] == 2
    assert pack["accessMeta"]["role"] == "ceo"


def test_department_pack_only_contains_matching_department_material(tmp_path: Path) -> None:
    db = Database(tmp_path / "pack_dept.db")
    data_dir = tmp_path / "data"
    _seed_pack_data(db, data_dir)

    pack = _build_pack(
        db,
        data_dir,
        DataCenterAccessContext(
            organization_id="org_pack",
            role="department_lead",
            viewer_user_id="lead_a",
            department_ids=("dept_a",),
        ),
    )

    assert _task_ids(pack) == {"task_a"}
    assert _entry_ids(pack) == {"entry_a"}
    assert [item["eventLineId"] for item in pack["eventLines"]] == ["eline_a"]


def test_employee_pack_contains_owned_work_material(tmp_path: Path) -> None:
    db = Database(tmp_path / "pack_employee.db")
    data_dir = tmp_path / "data"
    _seed_pack_data(db, data_dir)

    pack = _build_pack(
        db,
        data_dir,
        DataCenterAccessContext(
            organization_id="org_pack",
            role="employee",
            viewer_user_id="lead_b",
        ),
    )

    assert _task_ids(pack) == {"task_b"}
    assert _entry_ids(pack) == {"entry_b"}


def test_missing_department_material_is_excluded_from_department_pack_and_reported(tmp_path: Path) -> None:
    db = Database(tmp_path / "pack_missing_dept.db")
    data_dir = tmp_path / "data"
    _seed_pack_data(db, data_dir)
    _insert_task(db, "task_missing_dept", title="没有部门归属的任务", owner_id="other_user")
    _insert_review_entry(
        db,
        "entry_missing_dept",
        task_id="task_missing_dept",
        user_id="other_user",
        title="没有部门归属的任务",
        owner_id="other_user",
        note="完成了一条缺少部门归属的记录。",
    )
    assert ingest_weekly_review_by_id(db, data_dir, "review_pack") is not None

    pack = _build_pack(
        db,
        data_dir,
        DataCenterAccessContext(
            organization_id="org_pack",
            role="department_lead",
            viewer_user_id="lead_a",
            department_ids=("dept_a",),
        ),
    )

    assert "task_missing_dept" not in _task_ids(pack)
    assert "task_missing_dept" in pack["missingMeta"]["excludedMissingDepartmentTaskIds"]


def test_attachments_return_summary_and_relationships_without_file_body(tmp_path: Path) -> None:
    db = Database(tmp_path / "pack_attachment.db")
    data_dir = tmp_path / "data"
    _seed_pack_data(db, data_dir)
    doc = upsert_canonical_text_document(
        db,
        data_dir=data_dir,
        client_id="client_pack",
        canonical_kind="raw_file",
        origin_type="task_attachment",
        origin_id="att_a",
        title="开源页修改说明.md",
        text="这份材料说明益语平台开源页从功能说明转向业务负责人能理解的价值表达。",
        visible_category="项目与业务",
        secondary_category="任务附件",
        created_at=NOW,
        updated_at=NOW,
        organization_id="org_pack",
        department_id="dept_a",
        department_ids=["dept_a"],
        owner_user_id="lead_a",
        source_entity_type="task_attachment",
        source_entity_id="att_a",
        visibility_scope="project_public",
        content_domain="work",
    )
    assert doc is not None
    db.execute(
        """
        INSERT INTO task_attachments(
            id, task_id, client_id, event_line_id, document_id, title, path, kind, source, size_bytes, created_at
        ) VALUES('att_a', 'task_a', 'client_pack', 'eline_a', ?, '开源页修改说明.md', '/tmp/open.md', 'md', 'upload', 128, ?)
        """,
        (doc["documentId"], NOW),
    )

    pack = _build_pack(
        db,
        data_dir,
        DataCenterAccessContext(
            organization_id="org_pack",
            role="department_lead",
            viewer_user_id="lead_a",
            department_ids=("dept_a",),
        ),
    )

    assert len(pack["attachments"]) == 1
    attachment = pack["attachments"][0]
    assert attachment["title"] == "开源页修改说明.md"
    assert attachment["taskId"] == "task_a"
    assert attachment["eventLineId"] == "eline_a"
    assert attachment["documentId"] == doc["documentId"]
    assert "业务负责人能理解的价值表达" in attachment["summary"]
    assert "path" not in attachment
    assert "markdownContent" not in attachment


def test_pack_fingerprint_changes_when_review_entry_changes(tmp_path: Path) -> None:
    db = Database(tmp_path / "pack_fingerprint.db")
    data_dir = tmp_path / "data"
    _seed_pack_data(db, data_dir)
    context = DataCenterAccessContext(
        organization_id="org_pack",
        role="department_lead",
        viewer_user_id="lead_a",
        department_ids=("dept_a",),
    )
    before = _build_pack(db, data_dir, context)

    db.execute(
        """
        UPDATE weekly_review_task_entries
        SET note = '第二版复盘，补充了开源页发布标准。', updated_at = '2026-04-24T11:00:00'
        WHERE id = 'entry_a'
        """
    )

    after = _build_pack(db, data_dir, context)

    assert before["packFingerprint"] != after["packFingerprint"]
