from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database, to_json
from app.main import create_app
from app.services.experience_story_engine import (
    discover_experience_story_candidates,
    generate_experience_story_drafts,
)


NOW = "2026-04-28T10:00:00"


class FakeStoryAi:
    def __init__(self) -> None:
        self.material_packs: list[dict[str, object]] = []

    def get_health(self):
        return SimpleNamespace(provider="fake", model="fake-story-model")

    def generate_experience_story(self, *, material_pack: dict[str, object], context: dict[str, object]):
        self.material_packs.append(material_pack)
        return {
            "title": "从客户边界里看见市场机会",
            "story": "启示：团队复盘马老师沟通时发现，产品对社会企业客户也有明显价值。真正的问题不是功能不足，而是传播时把品牌边界收得太窄，导致潜在合作场景没有被看见。后来他们把复盘重点放在客户类型与市场可能性的关系上，提醒自己每次项目判断都要同时看功能价值和传播边界。",
            "growthValue": "训练个人从一次客户沟通里看见更大的业务可能。",
            "organizationValue": "把传播边界和客户类型的判断沉淀成可复用经验。",
            "factRiskNote": "基于任务复盘生成，需人工核对会议原文。",
        }


def _db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def _seed_story_materials(db: Database) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_1', '马老师项目', '马老师项目', '公益', '战略陪伴', '社会企业客户合作探索。', '推进中', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO task_lists(id, name, color, sort_order, is_default)
        VALUES('list_default', '默认', '#5B7BFE', 0, 1)
        """
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, stage, summary, intent, current_blocker, recent_decision,
            next_step, evidence_count, primary_client_id, primary_client_name, created_at, updated_at
        )
        VALUES('eline_1', '马老师客户沟通线', 'project', 'active', '客户沟通', '围绕客户需求判断产品与市场机会。',
               '识别社会企业客户的真实需求。', '传播口径过窄', '不要只看功能价值', '补充市场合作判断', 3,
               'client_1', '马老师项目', ?, ?)
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
        VALUES('task_1', '拜访马老师后复盘社会企业客户机会',
               '今天见到马老师，沟通中发现我们的产品对社会企业客户也很有用，但传播过程并没有提及这类客户。',
               'done', 'normal', 'list_default', 'user_1', '顾问甲',
               'done', '', NULL, 60, 'COLLAB_SHARED', 'client_1', 'eline_1',
               '品牌传播边界过窄', '补充社会企业客户传播口径', '项目判断不能只看功能可能性，也要看市场合作可能性',
               2, 'manual', 'client_1', '[]', '[]', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(
            id, week_label, operator_id, user_id, summary, work_free_note, created_at, updated_at
        )
        VALUES('review_1', '2026-W18', 'user_1', 'user_1', '马老师沟通复盘', '', ?, ?)
        """,
        (NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, user_id, week_label, content_domain, note, structured_note_json,
            reviewed_at, task_snapshot_json, created_at, updated_at
        )
        VALUES('entry_1', 'review_1', 'task_1', 'user_1', '2026-W18', 'work', ?, ?, ?, '{}', ?, ?)
        """,
        (
            "面对马老师这样的客户时，我们发现产品对社会企业很有价值，但过去传播时没有主动提到这类客户。这个复盘让团队意识到，项目判断不能只看功能性的可能性，还要看到市场合作和品牌边界带来的长期机会。",
            json.dumps(
                {
                    "successExperience": "客户沟通之后及时复盘，把一次需求反馈抽象成传播边界问题。",
                    "successReason": "团队没有停在会议记录，而是追问为什么社会企业客户过去没有被纳入传播对象。",
                },
                ensure_ascii=False,
            ),
            NOW,
            NOW,
            NOW,
        ),
    )
    db.execute(
        """
        INSERT INTO strategic_thought_insights(
            id, scope_type, client_id, client_name, title, insight_type, insight_text,
            future_judgment, recommended_action, evidence_summary, evidence_labels_json,
            source_refs_json, source_fingerprint, signal_score, raw_payload_json,
            is_favorite, is_deleted, generated_at, created_at, updated_at
        )
        VALUES('thought_bad', 'client', 'client_1', '马老师项目', '系统工程式摘要', 'strategic_shift',
               '日慈基金会Q1复盘发现，核心业务线教师赋能项目的设计缺口，不仅会影响同济资助项目结项节奏，还会导致后续数字化搭建缺少业务依据。对象-处境-动作-机制-证据。',
               '', '', '', '[]', '[]', 'bad', 90, '{}', 0, 0, ?, ?, ?)
        """,
        (NOW, NOW, NOW),
    )
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_sys', 'client_1', NULL, 'v2doc_sysdoc_系统生成报告.md', '/tmp/v2doc_sysdoc.md', 'md', 'system',
               '对象-处境-动作-机制-证据。系统自动生成材料，不应作为主素材。', '[]', ?)
        """,
        (NOW,),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error,
            preview_text, doc_index_text, content_hash, markdown_content, classification_confidence,
            section_count, chunk_count, imported_at, updated_at
        )
        VALUES('v2_sys', 'client_1', 'doc_sys', '/tmp/v2doc_sysdoc.md', '/tmp/v2doc_sysdoc.md', NULL,
               'v2doc_sysdoc_系统生成报告.md', 'md', 'background', '系统资料', '自动生成', 'ready', NULL,
               '对象-处境-动作-机制-证据。系统自动生成材料，不应作为主素材。', '', 'hash_sys',
               '对象-处境-动作-机制-证据。系统自动生成材料，不应作为主素材。', 0.9, 1, 1, ?, ?)
        """,
        (NOW, NOW),
    )


def test_experience_story_candidates_exclude_generated_sources(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_story_materials(db)

    candidates = discover_experience_story_candidates(db, limit=10)

    assert any(candidate.source_type == "weekly_review_task_entry" for candidate in candidates)
    assert all(candidate.source_type != "strategic_thought_insight" for candidate in candidates)
    assert all("对象-处境-动作-机制-证据" not in candidate.primary_text for candidate in candidates)


def test_generate_story_draft_keeps_handbook_empty_and_strips_labels(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_story_materials(db)
    fake_ai = FakeStoryAi()

    drafts, skipped = generate_experience_story_drafts(db, fake_ai, limit=2)

    assert skipped == 0
    assert drafts
    assert fake_ai.material_packs
    assert int(db.scalar("SELECT COUNT(1) AS count FROM handbook_entries")) == 0
    assert drafts[0].evidenceRefs
    assert not drafts[0].story.startswith("启示：")
    assert drafts[0].sourceType in {"weekly_review_task_entry", "task"}


def test_experience_story_api_approve_and_reject(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    try:
        db = client.app.state.app_state.db
        _seed_story_materials(db)
        client.app.state.app_state.ai = FakeStoryAi()

        generated = client.post("/api/v1/growth/experience-stories/generate", json={"limit": 1})
        assert generated.status_code == 200, generated.text
        payload = generated.json()
        assert payload["generatedCount"] == 1
        draft_id = payload["drafts"][0]["id"]
        assert db.scalar("SELECT COUNT(1) AS count FROM handbook_entries") == 0

        approved = client.post(f"/api/v1/growth/experience-stories/drafts/{draft_id}/approve")
        assert approved.status_code == 200, approved.text
        approved_payload = approved.json()
        assert approved_payload["draft"]["status"] == "approved"
        assert approved_payload["handbookEntry"]["sourceType"] == "experience_story"
        assert "经验故事" in approved_payload["handbookEntry"]["tags"]
        assert db.scalar("SELECT COUNT(1) AS count FROM handbook_entries") == 1

        db.execute(
            """
            INSERT INTO experience_story_drafts(
                id, title, story, status, source_type, source_id, source_title, evidence_refs_json,
                material_pack_json, quality_score_json, created_at, updated_at
            ) VALUES('story_reject', '待驳回故事', '这是一个待驳回的故事草稿，来源真实但本次不入墙。',
                     'candidate', 'task_note', 'note_1', '任务备注', ?, '{}', '{}', ?, ?)
            """,
            (to_json(["task_note:note_1"]), NOW, NOW),
        )
        rejected = client.post("/api/v1/growth/experience-stories/drafts/story_reject/reject")
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["draft"]["status"] == "rejected"
        assert db.scalar("SELECT COUNT(1) AS count FROM handbook_entries") == 1
    finally:
        client.__exit__(None, None, None)
