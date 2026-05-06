from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.data_center_access import DataCenterAccessContext
from app.services.review_narrative import build_weekly_mainline_cards_draft
from app.services.weekly_review_material_pack import build_weekly_review_material_pack


def make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def insert_client(db: Database, client_id: str = "client_1", name: str = "测试客户") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, ?, ?, '公益', '陪伴', '客户背景', '推进中', '2026-05-01T00:00:00', '2026-05-01T00:00:00')
        """,
        (client_id, name, name),
    )


def insert_event_line(db: Database, event_line_id: str = "eline_1", *, client_id: str = "client_1") -> None:
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
        VALUES(?, '', '测试事件线', 'project_line', 'active', NULL, '交付中',
            '事件线摘要', '事件线意图', '', '最近决策', '下一步动作', 0,
            'user_1', '顾源源', ?, '测试客户',
            '', '', '[]',
            '2026-05-01T00:00:00', '2026-05-01T00:00:00', 'local', NULL, '',
            '', '', '', '', 'project_public')
        """,
        (event_line_id, client_id),
    )


def insert_task(
    db: Database,
    task_id: str,
    title: str,
    *,
    due_date: str,
    client_id: str = "client_1",
    event_line_id: str = "eline_1",
    organization_id: str = "",
    scope_mode: str = "COLLAB_SHARED",
) -> None:
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
        VALUES(?, ?, ?, '任务描述', 'done', 'normal', 'list-0',
            'user_1', 'user_1', '顾源源', 'done', '', ?,
            60, ?, ?, NULL,
            '', '下一步', '最近决策', 0,
            'manual', NULL, '[]', '[]', '2026-04-01T00:00:00', '2026-05-01T00:00:00',
            '', '', '', '', ?)
        """,
        (task_id, organization_id, title, due_date, scope_mode, event_line_id, client_id),
    )


def insert_review_entry(db: Database, entry_id: str, task_id: str, *, week_label: str = "2026-W18") -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO weekly_reviews(
            id, week_label, operator_id, summary, work_free_note, personal_growth_note,
            personal_private_note, created_at, updated_at
        )
        VALUES('review_1', ?, 'user_1', '', '', '', '', '2026-05-01T00:00:00', '2026-05-01T00:00:00')
        """,
        (week_label,),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json,
            reviewed_at, task_snapshot_json, created_at, updated_at
        )
        VALUES(?, 'review_1', ?, ?, 'work', '用户写下的复盘内容', '{"nextAction":"核对交付清单"}',
            '2026-05-01T00:00:00', '{}', '2026-05-01T00:00:00', '2026-05-01T00:00:00')
        """,
        (entry_id, task_id, week_label),
    )


def insert_attachment(db: Database, attachment_id: str, task_id: str, document_id: str, title: str) -> None:
    db.execute(
        """
        INSERT INTO documents(id, client_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, 'client_1', ?, '/tmp/material.txt', 'txt', 'task_attachment', '附件摘要内容', '[]', '2026-05-01T00:00:00')
        """,
        (document_id, title),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, file_name, kind,
            parse_status, preview_text, doc_index_text, imported_at, updated_at
        )
        VALUES(?, 'client_1', ?, '/tmp/material.txt', '/tmp/material.txt', ?, 'txt',
            'parsed', '可读附件正文摘要', '', '2026-05-01T00:00:00', '2026-05-01T00:00:00')
        """,
        (f"v2_{document_id}", document_id, title),
    )
    db.execute(
        """
        INSERT INTO task_attachments(
            id, task_id, client_id, event_line_id, document_id, title, path, kind, source, size_bytes, created_at
        )
        VALUES(?, ?, 'client_1', 'eline_1', ?, ?, '/tmp/material.txt', 'txt', 'upload', 12, '2026-05-01T00:00:00')
        """,
        (attachment_id, task_id, document_id, title),
    )


def stub_retrieval(monkeypatch):
    def fake_bundle(*args, **kwargs):
        del args, kwargs
        return SimpleNamespace(
            citations=[
                SimpleNamespace(
                    title="客户背景材料",
                    excerpt="这是一条客户背景和项目目标摘要。",
                    knowledge_document_id="doc_context",
                    canonical_kind="client_context",
                    origin_type="client",
                    origin_id="client_1",
                    score=0.9,
                )
            ]
        )

    monkeypatch.setattr("app.services.weekly_review_material_pack.retrieve_knowledge_bundle", fake_bundle)


def test_material_pack_uses_explicit_work_item_task_boundary(tmp_path: Path, monkeypatch):
    db = make_db(tmp_path)
    insert_client(db)
    insert_event_line(db)
    insert_task(db, "task_in_pack", "本周页面任务", due_date="2026-04-01")
    insert_task(db, "task_same_week_but_not_in_pack", "同周但不在页面任务", due_date="2026-04-28")
    insert_review_entry(db, "entry_1", "task_in_pack")
    stub_retrieval(monkeypatch)

    pack = build_weekly_review_material_pack(
        db=db,
        data_dir=tmp_path / "data",
        access_context=DataCenterAccessContext(organization_id="local-device", viewer_user_id="user_1", role="employee"),
        week_label="2026-W18",
        work_items=[{"taskId": "task_in_pack"}],
    )

    assert [task["taskId"] for task in pack["tasks"]] == ["task_in_pack"]
    assert pack["sourceCounts"]["tasks"] == 1
    assert pack["sourceCounts"]["reviewEntries"] == 1
    assert pack["sourceCounts"]["documents"] == 1
    assert pack["accessMeta"]["localAccessRelaxed"] is True
    assert pack["materialBoundary"]["usedExplicitTaskBoundary"] is True


def test_material_pack_reads_attachments_only_for_visible_week_tasks(tmp_path: Path, monkeypatch):
    db = make_db(tmp_path)
    insert_client(db)
    insert_event_line(db)
    insert_task(db, "task_in_pack", "本周页面任务", due_date="2026-04-28")
    insert_task(db, "task_other", "不是本周页面任务", due_date="2026-04-28")
    insert_attachment(db, "att_in_pack", "task_in_pack", "doc_in_pack", "页面任务附件")
    insert_attachment(db, "att_other", "task_other", "doc_other", "不应混入附件")
    stub_retrieval(monkeypatch)

    pack = build_weekly_review_material_pack(
        db=db,
        data_dir=tmp_path / "data",
        access_context=DataCenterAccessContext(organization_id="local-device", viewer_user_id="user_1", role="employee"),
        week_label="2026-W18",
        task_ids=["task_in_pack"],
    )

    assert [attachment["attachmentId"] for attachment in pack["attachments"]] == ["att_in_pack"]
    assert pack["attachments"][0]["hasReadableSummary"] is True
    assert "可读附件正文摘要" in pack["attachments"][0]["summary"]
    assert pack["sourceCounts"]["attachments"] == 1
    assert pack["sourceCounts"]["readableAttachmentSummaries"] == 1


def test_material_pack_keeps_explicit_local_tasks_with_empty_org_in_org_view(tmp_path: Path, monkeypatch):
    db = make_db(tmp_path)
    insert_client(db)
    insert_event_line(db)
    insert_task(db, "task_local_org_empty", "士平足球方案撰写", due_date="2026-05-05", organization_id="")
    stub_retrieval(monkeypatch)

    pack = build_weekly_review_material_pack(
        db=db,
        data_dir=tmp_path / "data",
        access_context=DataCenterAccessContext(organization_id="org_yiyu_default", viewer_user_id="user_1", role="ceo"),
        week_label="2026-W19",
        task_ids=["task_local_org_empty"],
    )

    assert [task["taskId"] for task in pack["tasks"]] == ["task_local_org_empty"]
    assert pack["sourceCounts"]["tasks"] == 1
    assert pack["missingMeta"]["missingOrganizationCount"] == 1
    assert pack["accessMeta"]["localExplicitBoundaryRelaxed"] is True


def test_material_pack_does_not_relax_private_tasks_into_org_view(tmp_path: Path, monkeypatch):
    db = make_db(tmp_path)
    insert_client(db)
    insert_event_line(db)
    insert_task(
        db,
        "task_private",
        "个人私密任务",
        due_date="2026-05-05",
        organization_id="",
        scope_mode="PERSONAL_ONLY",
    )
    stub_retrieval(monkeypatch)

    pack = build_weekly_review_material_pack(
        db=db,
        data_dir=tmp_path / "data",
        access_context=DataCenterAccessContext(organization_id="org_yiyu_default", viewer_user_id="user_1", role="ceo"),
        week_label="2026-W19",
        task_ids=["task_private"],
    )

    assert pack["tasks"] == []
    assert pack["sourceCounts"]["tasks"] == 0
    assert pack["missingMeta"]["emptyMaterialPackReason"] == "all_explicit_tasks_filtered"


def test_material_pack_adds_previous_background_without_changing_current_task_count(tmp_path: Path, monkeypatch):
    db = make_db(tmp_path)
    insert_client(db)
    insert_event_line(db)
    insert_task(db, "task_current", "士平足球方案撰写", due_date="2026-05-05")
    insert_task(db, "task_previous", "云南儿童研究报告合并", due_date="2026-04-28")
    insert_review_entry(db, "entry_previous", "task_previous", week_label="2026-W18")
    stub_retrieval(monkeypatch)

    pack = build_weekly_review_material_pack(
        db=db,
        data_dir=tmp_path / "data",
        access_context=DataCenterAccessContext(organization_id="org_yiyu_default", viewer_user_id="user_1", role="ceo"),
        week_label="2026-W19",
        task_ids=["task_current"],
    )

    assert pack["sourceCounts"]["tasks"] == 1
    assert [task["taskId"] for task in pack["tasks"]] == ["task_current"]
    assert pack["sourceCounts"]["backgroundTasks"] >= 1
    assert any(task["taskId"] == "task_previous" and task["relationReason"] == "same_event_line" for task in pack["backgroundTasks"])
    assert pack["sourceCounts"]["backgroundReviewEntries"] >= 1


def test_weekly_mainline_cards_gate_empty_material_pack_before_ai_call():
    evidence_pack = {
        "weekLabel": "2026-W19",
        "tasks": [{"taskId": "task_1", "title": "测试任务", "status": "todo"}],
        "evidenceMeta": {
            "materialPackSourceCounts": {
                "explicitTaskBoundary": 1,
                "tasks": 0,
            }
        },
    }

    cards = build_weekly_mainline_cards_draft(ai=object(), week_label="2026-W19", evidence_pack=evidence_pack)  # type: ignore[arg-type]

    assert cards.generatedBy == "fallback"
    assert cards.mainlines == []
    assert cards.evidenceMeta["failureReason"] == "material_pack_empty"
