from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.knowledge_v2 import materialize_workspace_native_documents, retrieve_knowledge_bundle


NOW = "2026-04-23T12:00:00"


def _insert_client(db: Database, client_id: str, name: str = "日慈基金会") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, ?, ?, '公益', '客户', '', '推进中', ?, ?)
        """,
        (client_id, name, name, NOW, NOW),
    )


def _insert_task_list(db: Database) -> None:
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order) VALUES('list_relation', '关系测试', '#5B7BFE', 0)"
    )


def _insert_task(
    db: Database,
    *,
    task_id: str,
    title: str,
    client_id: str | None = None,
    event_line_id: str | None = None,
    project_module_id: str | None = None,
    project_flow_id: str | None = None,
    due_date: str = "2026-04-30",
) -> None:
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id,
            tags_json, created_at, updated_at, client_id, event_line_id, project_module_id, project_flow_id,
            due_date, current_blocker, next_action, recent_decision, progress_status
        )
        VALUES(?, ?, '任务描述', 'todo', 'normal', 'list_relation', '张真', ?, 'manual', NULL,
            '[]', ?, ?, ?, ?, ?, ?, ?, '待进一步确认', '下一步动作', '最近决策', 'todo')
        """,
        (
            task_id,
            title,
            due_date,
            NOW,
            NOW,
            client_id,
            event_line_id,
            project_module_id,
            project_flow_id,
            due_date,
        ),
    )


def _managed_text(db: Database, *, canonical_kind: str, origin_type: str | None = None) -> str:
    query = "SELECT managed_path FROM v2_documents WHERE canonical_kind = ?"
    args: tuple[str, ...] = (canonical_kind,)
    if origin_type:
        query += " AND origin_type = ?"
        args = (canonical_kind, origin_type)
    row = db.fetchone(query + " ORDER BY updated_at DESC LIMIT 1", args)
    assert row is not None
    return Path(str(row["managed_path"])).read_text(encoding="utf-8")


def test_materialize_relation_docs_creates_event_project_and_calendar_docs(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    client_id = "client_relation"
    _insert_client(db, client_id)
    _insert_task_list(db)
    db.execute(
        """
        INSERT INTO event_lines(id, name, primary_client_id, primary_client_name, stage, current_blocker, recent_decision, next_step, participant_ids_json, created_at, updated_at)
        VALUES('eline_1', '日慈战略陪伴', ?, '日慈基金会', '推进中', '信息同步不足', '先做关系业务流', '完成下一阶段安排', '[]', ?, ?)
        """,
        (client_id, NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO project_modules(id, client_id, name, alias, goal, description, owner_name, deliverables_json, keywords_json, created_at, updated_at)
        VALUES('pm_1', ?, '心盛计划', '', '沉淀青年心理支持样板', '', '老高', '["项目方案"]', '["心理支持"]', ?, ?)
        """,
        (client_id, NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO project_flows(id, client_id, module_id, name, description, scenario, trigger_condition, steps_json, inputs_json, outputs_json, collaborators_json, risk_points_json, created_at, updated_at)
        VALUES('pf_1', ?, 'pm_1', '关怀员培养流程', '', '青年小组支持', '报名启动', '["报名", "演练", "实践"]', '[]', '["培养记录"]', '[]', '["边界不清"]', ?, ?)
        """,
        (client_id, NOW, NOW),
    )
    _insert_task(
        db,
        task_id="task_1",
        title="推进心盛计划下一阶段安排",
        client_id=client_id,
        event_line_id="eline_1",
        project_module_id="pm_1",
        project_flow_id="pf_1",
    )
    db.execute(
        """
        INSERT INTO meetings(id, client_id, title, stage, scheduled_at, transcript_text, notes, created_at, updated_at)
        VALUES('meeting_1', ?, '日慈战略沟通会', '沟通', '2026-04-24T10:00:00', '', '讨论下一阶段安排', ?, ?)
        """,
        (client_id, NOW, NOW),
    )

    counts = materialize_workspace_native_documents(db, data_dir=tmp_path / "data", client_id=client_id)

    assert counts["event_line_doc"] == 1
    assert counts["project_doc"] == 2
    assert counts["calendar_doc"] == 1
    kinds = {
        str(row["canonical_kind"])
        for row in db.fetchall("SELECT canonical_kind FROM v2_documents WHERE client_id = ?", (client_id,))
    }
    assert {"event_line_doc", "project_doc", "calendar_doc", "task_doc", "meeting_doc"}.issubset(kinds)

    event_text = _managed_text(db, canonical_kind="event_line_doc")
    assert "事件线：日慈战略陪伴" in event_text
    assert "关系置信度：strong" in event_text
    assert "推进心盛计划下一阶段安排" in event_text

    project_text = _managed_text(db, canonical_kind="project_doc", origin_type="project_module")
    assert "项目模块：心盛计划" in project_text
    assert "暂无明确项目说明" not in project_text

    calendar_text = _managed_text(db, canonical_kind="calendar_doc")
    assert "这不是完整飞书日历" in calendar_text
    assert "日慈战略沟通会" in calendar_text
    assert "推进心盛计划下一阶段安排" in calendar_text

    bundle = retrieve_knowledge_bundle(db, tmp_path / "data", client_id, "日慈战略陪伴下一阶段有哪些任务和会议")
    selected_kinds = set(bundle.retrieval_summary["selectedCanonicalKinds"])
    assert bundle.retrieval_summary["readingPassCount"] == 2
    assert selected_kinds & {"event_line_doc", "project_doc", "calendar_doc"}
    assert bundle.retrieval_summary["softwareMaterialIncluded"] is True


def test_review_doc_can_bind_by_direct_task_and_marks_strong(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    client_id = "client_review_strong"
    _insert_client(db, client_id)
    _insert_task_list(db)
    _insert_task(db, task_id="task_review", title="整理战略陪伴复盘", client_id=client_id)
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, created_at, updated_at, work_progress)
        VALUES('review_strong', '2026-W16', '本周完成关键任务回看', ?, ?, '围绕任务推进做了复盘')
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(id, review_id, task_id, week_label, content_domain, note, reviewed_at, created_at, updated_at)
        VALUES('entry_1', 'review_strong', 'task_review', '2026-W16', 'work', '任务复盘记录', ?, ?, ?)
        """,
        (NOW, NOW, NOW),
    )

    counts = materialize_workspace_native_documents(db, data_dir=tmp_path / "data", client_id=client_id)

    assert counts["review_doc"] == 1
    review_text = _managed_text(db, canonical_kind="review_doc")
    assert "关系置信度：strong" in review_text
    assert "复盘关联了当前客户的 1 条任务" in review_text
    assert "整理战略陪伴复盘" in review_text


def test_review_doc_can_bind_by_client_name_match_and_marks_weak(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.db")
    client_id = "client_review_weak"
    _insert_client(db, client_id, name="日慈基金会")
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, created_at, updated_at, work_progress, next_week_focus)
        VALUES('review_weak', '2026-W17', '', ?, ?, '本周继续推进日慈战略陪伴的资料整理。', '下周继续跟日慈确认项目节奏。')
        """,
        (NOW, NOW),
    )

    counts = materialize_workspace_native_documents(db, data_dir=tmp_path / "data", client_id=client_id)

    assert counts["review_doc"] == 1
    review_text = _managed_text(db, canonical_kind="review_doc")
    assert "关系置信度：weak" in review_text
    assert "可能相关" in review_text
    assert "复盘正文命中客户词" in review_text
    assert "本周继续推进日慈战略陪伴" in review_text
