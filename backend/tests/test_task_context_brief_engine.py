from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.main import create_app
from app.services.task_context_brief_engine import (
    apply_task_context_brief_quality_gate,
    build_task_context_brief_material_pack,
    generate_task_context_brief_snapshot,
    should_generate_context_brief,
)


NOW = "2026-05-03T10:00:00"


class FakeBriefAi:
    def __init__(self) -> None:
        self.material_packs: list[dict[str, object]] = []

    def get_health(self):
        return SimpleNamespace(provider="fake", model="fake-brief-model")

    def generate_task_context_brief(self, *, material_pack: dict[str, object]) -> dict[str, object]:
        self.material_packs.append(material_pack)
        return {
            "shouldDisplay": True,
            "brief": "这次不是单纯改报告结构，而是在把评审、尽调、案例和资助判断重新组织成一条可读主线。继续推进时最容易漏掉工具分工和报告边界，需先确认哪些内容由佳维排版，哪些判断必须回到工作坊材料里找证据。",
            "usedProjectSignals": ["工作坊评审", "尽调材料", "报告结构", "工具分工"],
            "materialBoundary": "基于同客户任务链和数据中心片段生成。",
            "qualityFlags": [],
        }


def _db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def _seed_project_brief_materials(db: Database) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_yunnan', '云南儿童资助研究', '云南儿童资助研究', '公益', '研究项目', '云南儿童服务机构工作坊与报告。', '推进中', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute("INSERT INTO task_lists(id, name, color, sort_order, is_default) VALUES('list_default', '默认', '#5B7BFE', 0, 1)")
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, stage, summary, intent, current_blocker, recent_decision,
            next_step, evidence_count, primary_client_id, primary_client_name, created_at, updated_at
        )
        VALUES('eline_yunnan', '云南儿童资助研究', 'project_line', 'active', '报告收束',
               '围绕云南儿童服务机构工作坊、评审和报告结构持续推进。',
               '把工作坊材料沉淀成资助判断报告。', '', '', '', 4,
               'client_yunnan', '云南儿童资助研究', ?, ?)
        """,
        (NOW, NOW),
    )
    tasks = [
        (
            "task_workshop",
            "云南儿童工作坊",
            "组织工作坊，围绕报名机构材料进行初步筛选和共创。",
            "eline_yunnan",
            "2026-04-10",
            "工作坊需要支撑后续资助决策。",
        ),
        (
            "task_ppt",
            "调整云南PPT的结构",
            "报告和PPT进入收束阶段，不能无休止迭代完善。",
            "eline_yunnan",
            "2026-04-20",
            "PPT要和报告主线保持一致。",
        ),
        (
            "task_report",
            "重新梳理云南报告结构",
            "和乐乐核对报告结构和内容需要修改的地方。要重新把结构梳理清楚。codex 自动报告排版交给佳维研究，不以CC作为主力工具。",
            "eline_yunnan",
            "2026-04-21",
            "和乐乐核对报告结构和内容需要修改的地方。",
        ),
        (
            "task_chapter_six",
            "云南儿童报告第六章",
            "补齐云南地区儿童公益议题与项目布局研究中的机制判断。",
            None,
            "2026-04-27",
            "第六章需要解释项目布局变化。",
        ),
        (
            "task_chapter_seven",
            "云南儿童报告第七章",
            "把机构案例和评审结论合并成资助建议。",
            None,
            "2026-04-27",
            "第七章需要回到机构案例。",
        ),
    ]
    for task_id, title, desc, event_line_id, due_date, decision in tasks:
        db.execute(
            """
            INSERT INTO tasks(
                id, title, description, status, priority, list_id, creator_id, owner_name,
                progress_status, ddl, due_date, duration_minutes, scope_mode, client_id, event_line_id,
                current_blocker, next_action, recent_decision, evidence_count, source_type,
                source_id, tags_json, tag_ids_json, created_at, updated_at
            )
            VALUES(?, ?, ?, 'done', 'normal', 'list_default', 'user_1', '管理员甲',
                   'done', '', ?, 60, 'COLLAB_SHARED', 'client_yunnan', ?,
                   '', '继续收束报告结构', ?, 2, 'manual',
                   NULL, '[]', '[]', ?, ?)
            """,
            (task_id, title, desc, due_date, event_line_id, decision, NOW, NOW),
        )
    db.execute(
        """
        INSERT INTO event_line_activities(id, event_line_id, source_type, source_id, happened_at, title, summary, created_at)
        VALUES('ela_report', 'eline_yunnan', 'attachment', 'att_ppt', '2026-04-19T09:00:00',
               '上传附件：士平云南ppt（待修改）.pptx', '士平云南ppt待修改，报告和PPT结构需要一起收束。', ?)
        """,
        (NOW,),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, operator_id, user_id, summary, created_at, updated_at)
        VALUES('review_yunnan', '2026-W17', 'user_1', 'user_1', '云南报告结构复盘', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, user_id, week_label, content_domain, note, structured_note_json,
            reviewed_at, task_snapshot_json, created_at, updated_at
        )
        VALUES('entry_report', 'review_yunnan', 'task_report', 'user_1', '2026-W17', 'work',
               '报告结构不能只是章节拼接，要把评审、尽调、案例和资助判断组织成一条可读主线。',
               '{}', ?, '{}', ?, ?)
        """,
        (NOW, NOW, NOW),
    )
    docs = [
        (
            "v2doc_score",
            "云南儿童服务机构工作坊—报名机构评分报告.docx",
            [
                ("评审方法", "本次工作坊报名机构共20家，评分方式为AI辅助评审，重点看机构服务基础、案例质量和项目承接能力。"),
                ("报告用途", "评分报告不是简单排名，而是为后续资助决策提供可解释依据。"),
            ],
        ),
        (
            "v2doc_due",
            "云南儿童服务机构工作坊—报名机构综合评估报告（含尽调）.docx",
            [
                ("尽调结论", "综合评估报告补充了机构尽调信息，需要和案例材料一起支撑报告判断。"),
            ],
        ),
        (
            "v2doc_noise",
            "士平云南ppt（待修改）.pptx",
            [
                ("字体信息", "WPS 文字 On-screen Show PowerPoint 演示文稿 Arial Wingdings 微软雅黑 Office Theme"),
            ],
        ),
    ]
    for doc_id, file_name, chunks in docs:
        document_id = doc_id.replace("v2doc_", "doc_")
        db.execute(
            """
            INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
            VALUES(?, 'client_yunnan', NULL, ?, '/tmp/source', 'docx', 'file', '', '[]', ?)
            """,
            (document_id, file_name, NOW),
        )
        db.execute(
            """
            INSERT INTO v2_documents(
                id, client_id, document_id, original_path, managed_path, file_name, kind,
                preview_text, doc_index_text, markdown_content, content_hash, imported_at, updated_at
            )
            VALUES(?, 'client_yunnan', ?, '/tmp/source', '/tmp/managed', ?, 'docx',
                   '', '', '', ?, ?, ?)
            """,
            (doc_id, document_id, file_name, doc_id, NOW, NOW),
        )
        section_id = f"{doc_id}_section"
        db.execute(
            """
            INSERT INTO v2_sections(id, v2_document_id, section_index, title, content, searchable_text, char_count, created_at)
            VALUES(?, ?, 0, ?, '', ?, 0, ?)
            """,
            (section_id, doc_id, file_name, file_name, NOW),
        )
        for index, (section, content) in enumerate(chunks):
            db.execute(
                """
                INSERT INTO v2_chunks(id, v2_document_id, v2_section_id, chunk_index, section_label, content, searchable_text, char_count, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f"{doc_id}_chunk_{index}", doc_id, section_id, index, section, content, f"{file_name} {section} {content}", len(content), NOW),
            )


def _seed_thin_materials(db: Database) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_platform', '示例工作台', '示例工作台', '软件', '内部', '', '推进中', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute("INSERT INTO task_lists(id, name, color, sort_order, is_default) VALUES('list_default', '默认', '#5B7BFE', 0, 1)")
    db.execute(
        """
        INSERT INTO event_lines(id, name, kind, status, primary_client_id, primary_client_name, created_at, updated_at)
        VALUES('eline_platform', '示例工作台平台', 'project_line', 'active', 'client_platform', '示例工作台', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, creator_id, owner_name,
            progress_status, ddl, due_date, duration_minutes, scope_mode, client_id, event_line_id,
            current_blocker, next_action, recent_decision, evidence_count, source_type,
            source_id, tags_json, tag_ids_json, created_at, updated_at
        )
        VALUES('task_phone', '手机系统全测', '', 'todo', 'high', 'list_default', 'user_1', '管理员甲',
               'todo', '', '2026-05-03', 60, 'COLLAB_SHARED', 'client_platform', 'eline_platform',
               '', '根据最近会议形成明确后续安排。', '最近进展：示例团队战略咨询技术应用规划 2026年3月11日',
               0, 'manual', NULL, '[]', '[]', ?, ?)
        """,
        (NOW, NOW),
    )


def test_material_pack_uses_same_client_tasks_and_data_center_chunks(tmp_path: Path):
    db = _db(tmp_path)
    _seed_project_brief_materials(db)

    pack = build_task_context_brief_material_pack(db, "task_report")

    assert pack["coverage"]["eventLineTaskCount"] == 3
    assert pack["coverage"]["sameClientTaskCount"] >= 5
    assert pack["coverage"]["documentChunkCount"] >= 3
    assert any(item["title"] == "云南儿童报告第六章" for item in pack["sameClientTasks"])
    chunk_text = json.dumps(pack["dataCenterDocumentChunks"], ensure_ascii=False)
    assert "20家" in chunk_text
    assert "资助决策" in chunk_text
    assert "WPS 文字" not in chunk_text


def test_thin_material_pack_does_not_generate_context_brief(tmp_path: Path):
    db = _db(tmp_path)
    _seed_thin_materials(db)

    pack = build_task_context_brief_material_pack(db, "task_phone")
    readiness = should_generate_context_brief(pack)

    assert readiness["shouldGenerate"] is False
    assert "insufficient_project_context" in readiness["qualityFlags"]


def test_generate_context_brief_uses_cache_and_never_creates_proposal(tmp_path: Path):
    db = _db(tmp_path)
    _seed_project_brief_materials(db)
    fake_ai = FakeBriefAi()

    first = generate_task_context_brief_snapshot(db, fake_ai, "task_report")
    second = generate_task_context_brief_snapshot(db, fake_ai, "task_report")

    assert first["shouldDisplay"] is True
    assert second["brief"] == first["brief"]
    assert len(fake_ai.material_packs) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM task_context_brief_snapshots")) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM proposal_records")) == 0

    db.execute(
        """
        INSERT INTO v2_chunks(id, v2_document_id, v2_section_id, chunk_index, section_label, content, searchable_text, char_count, created_at)
        VALUES('v2doc_score_chunk_extra', 'v2doc_score', 'v2doc_score_section', 9, '新增结构提醒',
               '新增材料指出报告主线必须把工作坊观察、尽调结果和机构案例合并呈现。',
               '云南 报告 工作坊 尽调 机构案例', 33, ?)
        """,
        (NOW,),
    )
    refreshed = generate_task_context_brief_snapshot(db, fake_ai, "task_report")

    assert refreshed["materialPackHash"] != first["materialPackHash"]
    assert len(fake_ai.material_packs) == 2


def test_context_brief_quality_gate_hides_field_restatement():
    gated = apply_task_context_brief_quality_gate(
        {
            "shouldDisplay": True,
            "brief": "本任务为云南儿童报告结构调整，截止时间2026年4月21日，过往已有4项记录。",
            "usedProjectSignals": [],
            "materialBoundary": "",
            "qualityFlags": [],
        }
    )

    assert gated["shouldDisplay"] is False
    assert "template_field_restatement" in gated["qualityFlags"]
    assert "missing_next_step_reminder" in gated["qualityFlags"]


def test_context_brief_batch_api_returns_cached_brief_without_proposal(tmp_path: Path):
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    db = client.app.state.app_state.db
    _seed_project_brief_materials(db)
    fake_ai = FakeBriefAi()
    client.app.state.app_state.ai = fake_ai

    response = client.post("/api/v1/tasks/context-briefs/batch", json={"taskIds": ["task_report"]})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["briefs"][0]["taskId"] == "task_report"
    assert payload["briefs"][0]["shouldDisplay"] is True
    assert "任务前情" not in payload["briefs"][0]["brief"]
    assert len(fake_ai.material_packs) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM proposal_records")) == 0
    client.__exit__(None, None, None)
