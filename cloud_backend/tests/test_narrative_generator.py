"""narrative_collector + narrative_generator 闭环测试 (不调真 LLM).

覆盖:
  - collector: 从 cloud db 拿 client + event_lines + activities + tasks + clarifications.
  - generator: LLM 不可用时降级到 stub (拼澄清原文); 成功时解析 JSON 落库.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.models import NarrativeClarificationCreatePayload  # noqa: E402
from app.services import client_narrative as svc  # noqa: E402
from app.services import narrative_generator as gen  # noqa: E402
from app.services.narrative_collector import collect_client_context  # noqa: E402


ORG_ID = "org_test"
CLIENT_ID = "client_riciqi"
CLIENT_NAME = "日慈基金会"
USER_ID = "user_gu"
USER_NAME = "顾源源"


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "n.db")
    now = datetime.now(timezone.utc).isoformat()
    database.execute(
        "INSERT INTO organizations(id, name, slug, created_at, updated_at) VALUES (?,?,?,?,?)",
        (ORG_ID, "测试组织", "test-org", now, now),
    )
    database.execute(
        "INSERT INTO clients(id, organization_id, name, alias, type, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (CLIENT_ID, ORG_ID, CLIENT_NAME, "日慈", "client", now, now),
    )
    database.execute(
        """INSERT INTO employee_accounts
        (id, organization_id, email, full_name, password_hash, primary_role,
         account_status, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (USER_ID, ORG_ID, "gu@t.local", USER_NAME, "x", "admin", "approved", now, now),
    )
    # event_line
    database.execute(
        """INSERT INTO event_lines
        (id, organization_id, name, kind, status, stage, summary, intent,
         current_blocker, recent_decision, next_step, evidence_count, owner_id,
         primary_client_id, primary_client_name, primary_department_id,
         participant_ids_json, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "el_brand", ORG_ID, "日慈品牌改造", "project", "active", "discovery",
            "为日慈基金会做品牌升级 + 视觉系统重构",
            "客户希望在年底前完成新品牌发布", "等高老师反馈时间规划",
            "4月底确定 4 个候选方向", "5月15日前出 visual story 提纲",
            3, USER_ID, CLIENT_ID, CLIENT_NAME, None, "[]", now, now,
        ),
    )
    # activity
    database.execute(
        """INSERT INTO event_line_activities
        (id, event_line_id, source_type, source_id, happened_at, actor_id, title, summary, metadata_json)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            "act_1", "el_brand", "meeting", "doc_4_12", "2026-04-12T10:00:00Z",
            USER_ID, "日慈秘书长见面纪要",
            "张真秘书长明确支持品牌升级, 由徐总监经办", "{}",
        ),
    )
    # task
    database.execute(
        """INSERT INTO task_lists(id, organization_id, name, color)
        VALUES ('lst_default', ?, '默认列表', '#999')""",
        (ORG_ID,),
    )
    database.execute(
        """INSERT INTO tasks
        (id, organization_id, title, description, creator_id, owner_id,
         deadline_at, priority, list_id, progress_status, source_type, source_id,
         next_action, current_blocker, recent_decision, completion_note,
         tags_json, tag_ids_json, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "tsk_1", ORG_ID, "日慈|品牌改造|准备 visual story 提纲", "",
            USER_ID, USER_ID, "2026-05-15T00:00:00Z", "high",
            "lst_default", "doing", "event_line", "el_brand",
            "等张真确认方向后出提纲", "", "", "",
            "[]", "[]", now, now,
        ),
    )
    return database


# ============================================================
# Collector tests
# ============================================================


def test_collector_picks_up_event_lines_and_activities(db: Database) -> None:
    ctx = collect_client_context(db, ORG_ID, CLIENT_ID)
    assert ctx.client_name == CLIENT_NAME
    assert len(ctx.event_lines) == 1
    el = ctx.event_lines[0]
    assert el.name == "日慈品牌改造"
    assert "张真" not in el.summary  # summary 不应被乱拼
    assert "品牌升级" in el.summary
    assert len(ctx.activities) == 1
    assert ctx.activities[0].title == "日慈秘书长见面纪要"
    assert ctx.activities[0].event_line_name == "日慈品牌改造"
    assert len(ctx.tasks) == 1
    assert ctx.tasks[0].title.startswith("日慈|品牌改造")


def test_collector_returns_empty_when_no_event_lines(db: Database) -> None:
    db.execute("DELETE FROM tasks", ())
    db.execute("DELETE FROM event_line_activities", ())
    db.execute("DELETE FROM event_lines", ())
    ctx = collect_client_context(db, ORG_ID, CLIENT_ID)
    assert ctx.event_lines == []
    assert ctx.activities == []
    assert ctx.tasks == []
    assert ctx.is_thin()


def test_collector_pending_vs_applied_clarifications(db: Database) -> None:
    svc.add_clarification(
        db, ORG_ID, CLIENT_ID,
        NarrativeClarificationCreatePayload(dimension="people", answer="张真是秘书长"),
        answered_by_user_id=USER_ID,
        answered_by_display_name=USER_NAME,
    )
    ctx = collect_client_context(db, ORG_ID, CLIENT_ID)
    assert len(ctx.pending_clarifications) == 1
    assert len(ctx.applied_clarifications) == 0


# ============================================================
# Generator tests
# ============================================================


def test_generator_falls_back_to_stub_when_no_api_key(db: Database, monkeypatch) -> None:
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("VOLCENGINE_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("YIYU_QWEN_API_KEY", raising=False)
    svc.add_clarification(
        db, ORG_ID, CLIENT_ID,
        NarrativeClarificationCreatePayload(dimension="people", answer="张真是日慈秘书长"),
        answered_by_user_id=USER_ID,
        answered_by_display_name=USER_NAME,
    )
    new_rev = gen.regenerate_narrative(
        db, ORG_ID, CLIENT_ID,
        triggered_by_user_id=USER_ID,
        triggered_by_display_name=USER_NAME,
        use_llm=True,
    )
    assert new_rev == 1
    latest = svc.get_latest_narrative(db, ORG_ID, CLIENT_ID)
    assert latest is not None
    assert latest.generator == "stub_clarification_append"
    people = next(d for d in latest.dimensions if d.dimension == "people")
    assert "张真" in people.narrative
    # 没澄清过的 dim 应该是 stub_dim 内容
    cooperation = next(d for d in latest.dimensions if d.dimension == "cooperation")
    assert cooperation.confidence == "low"


def test_generator_uses_llm_response_when_ok(db: Database, monkeypatch) -> None:
    monkeypatch.setenv("ARK_API_KEY", "fake-key-for-test")
    fake_llm = {
        "essence": {
            "narrative": "日慈基金会是儿童社会情感学习领域的公益组织, 项目类型为品牌升级综合方案",
            "confidence": "high",
            "confidenceReason": "基于 event_line summary + activity 见面纪要",
            "references": [
                {"sourceType": "event_line", "sourceId": "el_brand", "label": "日慈品牌改造主线", "confidence": "high"},
                {"sourceType": "event_line_activity", "sourceId": "act_1", "label": "4/12 秘书长见面纪要", "confidence": "high"},
            ],
            "dataLayerGap": "",
            "openClarifications": [],
        },
        "people": {
            "narrative": "张真秘书长 — 决策者; 徐总监 — 经办; 高老师 (益语方) — 主导",
            "confidence": "medium",
            "confidenceReason": "无 external_persons 花名册, 仅从活动 summary 推断",
            "references": [
                {"sourceType": "event_line_activity", "sourceId": "act_1", "label": "见面纪要", "confidence": "high"},
            ],
            "dataLayerGap": "external_persons 花名册未建",
            "openClarifications": ["徐总监全名是?"],
        },
        "cooperation": {
            "narrative": "⏳ AI 暂时讲不出合作关系维度, 数据中心 cooperation_relationships 表未建",
            "confidence": "low",
            "confidenceReason": "数据中心加工层缺失",
            "references": [],
            "dataLayerGap": "cooperation_relationships 表未建",
            "openClarifications": [],
        },
        "business_intro": {
            "narrative": "日慈基金会是公益组织, 主营儿童社会情感学习",
            "confidence": "medium",
            "references": [{"sourceType": "event_line", "sourceId": "el_brand"}],
            "dataLayerGap": "",
            "openClarifications": [],
        },
        "timeline": {
            "narrative": "4/12 高老师与张真见面后确认方向...",
            "confidence": "medium",
            "references": [
                {"sourceType": "event_line_activity", "sourceId": "act_1"},
            ],
            "dataLayerGap": "",
            "openClarifications": [],
        },
        "next_steps": {
            "narrative": "益语 → 5/15 前出 visual story 提纲; 张真确认方向",
            "confidence": "medium",
            "references": [{"sourceType": "task", "sourceId": "tsk_1"}],
            "dataLayerGap": "",
            "openClarifications": [],
        },
        "overallConfidence": 0.55,
    }
    with patch.object(gen, "call_llm", return_value=fake_llm):
        new_rev = gen.regenerate_narrative(
            db, ORG_ID, CLIENT_ID,
            triggered_by_user_id=USER_ID,
            triggered_by_display_name=USER_NAME,
            force=True,
            use_llm=True,
        )
    assert new_rev == 1
    latest = svc.get_latest_narrative(db, ORG_ID, CLIENT_ID)
    assert latest is not None
    assert latest.generator == "ai_doubao"
    assert latest.overallConfidence == pytest.approx(0.55)
    essence = next(d for d in latest.dimensions if d.dimension == "essence")
    assert "日慈基金会" in essence.narrative
    assert essence.confidence == "high"
    assert len(essence.references) == 2
    assert any(r.sourceId == "el_brand" for r in essence.references)
    cooperation = next(d for d in latest.dimensions if d.dimension == "cooperation")
    assert cooperation.confidence == "low"
    assert "cooperation_relationships" in cooperation.dataLayerGap


def test_generator_llm_failure_falls_back_gracefully(db: Database, monkeypatch) -> None:
    monkeypatch.setenv("ARK_API_KEY", "fake")
    svc.add_clarification(
        db, ORG_ID, CLIENT_ID,
        NarrativeClarificationCreatePayload(dimension="essence", answer="项目是 6 个月组合方案"),
        answered_by_user_id=USER_ID,
        answered_by_display_name=USER_NAME,
    )
    with patch.object(gen, "call_llm", side_effect=RuntimeError("LLM 5xx")):
        new_rev = gen.regenerate_narrative(
            db, ORG_ID, CLIENT_ID,
            triggered_by_user_id=USER_ID,
            triggered_by_display_name=USER_NAME,
            use_llm=True,
        )
    assert new_rev == 1
    latest = svc.get_latest_narrative(db, ORG_ID, CLIENT_ID)
    assert latest is not None
    assert latest.generator == "stub_clarification_append"
    essence = next(d for d in latest.dimensions if d.dimension == "essence")
    assert "6 个月" in essence.narrative


def test_generator_validates_and_strips_invalid_refs(db: Database, monkeypatch) -> None:
    monkeypatch.setenv("ARK_API_KEY", "fake")
    fake_llm = {
        **{d: {
            "narrative": "短叙事",
            "confidence": "medium",
            "references": [
                {"sourceType": "event_line", "sourceId": "el_brand"},
                {"sourceType": "", "sourceId": "bad"},  # 应被丢弃
                {"sourceType": "task"},                  # 缺 sourceId, 应被丢弃
                "not_a_dict",
            ],
        } for d in gen.DIMENSIONS},
        "overallConfidence": 0.3,
    }
    with patch.object(gen, "call_llm", return_value=fake_llm):
        gen.regenerate_narrative(
            db, ORG_ID, CLIENT_ID,
            triggered_by_user_id=USER_ID,
            triggered_by_display_name=USER_NAME,
            force=True,
        )
    latest = svc.get_latest_narrative(db, ORG_ID, CLIENT_ID)
    assert latest is not None
    for dim in latest.dimensions:
        assert len(dim.references) == 1
        assert dim.references[0].sourceId == "el_brand"


def test_build_user_prompt_contains_real_facts(db: Database) -> None:
    ctx = collect_client_context(db, ORG_ID, CLIENT_ID)
    prompt = gen.build_user_prompt(ctx)
    assert CLIENT_NAME in prompt
    assert "日慈品牌改造" in prompt
    assert "张真" in prompt   # 来自 activity summary
    assert "el_brand" in prompt  # event_line id 可引用
    assert "act_1" in prompt    # activity id 可引用
    assert "essence" in prompt  # 维度指引
    assert "硬约束" in gen.SYSTEM_PROMPT


def test_strip_to_json_handles_markdown_wrap() -> None:
    raw = "```json\n{\n  \"a\": 1\n}\n```"
    assert json.loads(gen._strip_to_json(raw)) == {"a": 1}
    raw2 = "解释一下: { \"a\": 2 } 完毕"
    assert json.loads(gen._strip_to_json(raw2)) == {"a": 2}
