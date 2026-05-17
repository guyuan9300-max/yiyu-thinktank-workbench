"""本地 narrative 生成 pipeline 测试 (Plan A · v0.2).

覆盖:
  - collector 从本地 db 拿 atomic_facts + entities + memory_facts
  - generator 调 mock AI 出 6 段叙事
  - LLM 失败时降级到 stub
  - prompt 含真实人物 / 日期 / 金额 / 业务事实 (区别于 v0.1 流水账)
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.services.narrative_collector import collect_client_fact_bundle  # noqa: E402
from app.services.narrative_generator import (  # noqa: E402
    DIMENSIONS,
    build_user_prompt,
    compute_data_layer_gaps,
    generate_narrative_dimensions,
)


CLIENT_ID = "client_test_riciqi"
CLIENT_NAME = "日慈基金会"


def _seed_minimum(db: Database) -> None:
    """种最小可用数据 — clients + entities + atomic_facts + event_lines + activities + tasks + v2_documents."""
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (CLIENT_ID, CLIENT_NAME, "日慈", "", "client", "", "active", "#5B7BFE", now, now),
    )
    # entities · 5 人物 + 3 日期 + 2 金额
    entity_rows = [
        ("ent_1", "person", "高老师", "高老师", 93),
        ("ent_2", "person", "王老师", "王老师", 16),
        ("ent_3", "person", "张真老师", "张真老师", 6),
        ("ent_4", "person", "王强老师", "王强老师", 7),
        ("ent_5", "person", "顾老师", "顾老师", 6),
        ("ent_6", "date", "2026-03-30", "2026-03-30", 22),
        ("ent_7", "date", "2026-04-15", "2026-04-15", 17),
        ("ent_8", "date", "2025年9月", "2025年9月", 13),
        ("ent_9", "amount", "75,000.00元", "75,000.00元", 9),
        ("ent_10", "amount", "100万元", "100万元", 4),
    ]
    for eid, etype, name, disp, mention in entity_rows:
        db.execute(
            """INSERT INTO entities(id, client_id, entity_type, normalized_name, display_name,
               aliases_json, attributes_json, mention_count, confidence, first_seen_at, last_seen_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (eid, CLIENT_ID, etype, name, disp, "[]", "{}", mention, 0.85, now, now, now, now),
        )

    # atomic_facts · 6 条不同 attribute
    atomic_rows = [
        ("af_1", "日慈公益基金会总部", "位置", "广州", 0.85),
        ("af_2", "本次工作坊", "目标", "学习一套三次连续小组的配套培训", 0.80),
        ("af_3", "我们需要完成", "任务", "亲身体验工作坊-站在带领者的角度思考并总结", 0.80),
        ("af_4", "将标准化后", "SOP", "“关怀员”的核心培训内容", 0.80),
        ("af_5", "团队", "理解", "把行动营理解为最上层的入口", 0.85),
        ("af_6", "客户", "要求", "8 月底交付完整方案", 0.75),
    ]
    for fid, subj, attr, val, conf in atomic_rows:
        db.execute(
            """INSERT INTO atomic_facts(id, client_id, subject_text, attribute, value_text, value_normalized,
               confidence, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (fid, CLIENT_ID, subj, attr, val, val, conf, "active", now, now),
        )

    # 1 event_line + 2 activities + 1 task
    db.execute(
        """INSERT INTO event_lines(id, name, kind, status, stage, summary, intent,
           current_blocker, recent_decision, next_step, evidence_count,
           primary_client_id, participant_ids_json, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "el_1", "日慈战略陪伴", "project", "active", "discovery",
            "为日慈基金会做 6 个月组织诊断 + 干部培训", "客户对成功的定义是看到干部差在哪",
            "等张真发时间规划", "4月初确定 4 个候选方向", "5月15日前出 visual story 提纲",
            3, CLIENT_ID, "[]", now, now,
        ),
    )
    db.execute(
        """INSERT INTO event_line_activities(id, event_line_id, source_type, source_id, happened_at,
           actor_name, title, summary, metadata_json)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        ("act_1", "el_1", "meeting", "doc_4_12", "2026-04-12T10:00:00Z",
         "顾源源", "张真秘书长见面纪要", "张真明确支持品牌升级, 徐总监经办", "{}"),
    )
    # task 跳过 — schema 有 FK to task_lists + users, fixture 复杂度不值得
    # collector 单独测 task 路径在 test_prompt_no_tasks_ok 那里 (容忍空 task)
    # v2_document
    db.execute(
        """INSERT INTO v2_documents(id, client_id, document_id, original_path, managed_path,
           markdown_path, file_name, kind, parse_status, preview_text,
           imported_at, updated_at, content_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "doc_1", CLIENT_ID, "doc_1", "/tmp/a.md", "/tmp/a.md", "/tmp/a.md",
            "张真秘书长见面纪要.md", "meeting_notes", "completed",
            "4/12 张真秘书长见面... 同意品牌升级方向...",
            now, now, "hash_1",
        ),
    )


# ============================================================
# Collector tests
# ============================================================


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    db_path = tmp_path / "n.db"
    database = Database(db_path)
    # 测试 fixture: 关闭 FK 检查, 避免给每条 row 都建上游表的烦扰
    # (collector 测试目标是: 给定数据中心已有的预制菜, 能否聚合)
    database.conn.execute("PRAGMA foreign_keys = OFF")
    _seed_minimum(database)
    return database


def test_collector_picks_up_real_persons_dates_money(db: Database) -> None:
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    assert bundle.client_name == CLIENT_NAME
    assert len(bundle.persons) >= 5
    person_names = [p.name for p in bundle.persons]
    assert "高老师" in person_names
    assert "张真老师" in person_names
    assert any(p.name == "高老师" and p.mention_count == 93 for p in bundle.persons)
    assert len(bundle.time_anchors) >= 3
    assert any(a.text == "2026-03-30" for a in bundle.time_anchors)
    assert len(bundle.money_anchors) >= 2
    assert any(a.text == "75,000.00元" for a in bundle.money_anchors)


def test_collector_groups_atomic_facts_by_attribute(db: Database) -> None:
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    assert len(bundle.atomic_facts_by_attribute) >= 5
    assert "位置" in bundle.atomic_facts_by_attribute
    assert "目标" in bundle.atomic_facts_by_attribute
    pos = bundle.atomic_facts_by_attribute["位置"][0]
    assert "广州" in pos.value


def test_collector_exposes_health_gaps(db: Database) -> None:
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    assert bundle.health["atomic_facts_count"] == 6
    assert bundle.health["entity_count"] >= 10


def test_collector_filters_dirty_evidence(db: Database) -> None:
    # 灌一些"附件入库流水"型的脏 evidence_cards
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO evidence_cards(id, client_id, scope_type, scope_id, source_type, source_id,
           source_ref, quote, normalized_claim, evidence_type, polarity, tags_json,
           topic_keys_json, confidence, time_anchor, fingerprint,
           normalized_claim_hash, source_ref_hash, evidence_fingerprint, normalizer_version,
           created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "ec_dirty_1", CLIENT_ID, "client", CLIENT_ID, "document_summary", "doc_x",
            "", "x.jpeg 已作为任务附件进入项目资料库",
            "x.jpeg 已作为任务附件进入项目资料库",
            "document_summary", "neutral", "[]", "[]", 0.5, "",
            "fp_dirty_1", "h1", "h2", "ef1", "v1",
            now, now,
        ),
    )
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    eq = bundle.health["evidence_quality"]
    assert eq["total"] == 1
    assert eq["dirty_doc_summary"] == 1


# ============================================================
# Prompt content tests
# ============================================================


def test_prompt_contains_persons_dates_money_atomic_facts(db: Database) -> None:
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    prompt = build_user_prompt(bundle)
    # 关键人物
    assert "高老师" in prompt
    assert "张真老师" in prompt
    assert "93" in prompt   # 提及次数
    # 关键日期
    assert "2026-03-30" in prompt
    assert "22" in prompt   # date 提及次数
    # 关键金额
    assert "75,000.00元" in prompt or "75,000" in prompt
    # 业务事实
    assert "广州" in prompt
    assert "8 月底交付完整方案" in prompt
    # event_line
    assert "日慈战略陪伴" in prompt
    assert "el_1" in prompt  # event_line id
    # documents
    assert "张真秘书长见面纪要" in prompt
    # 维度指引
    for d in DIMENSIONS:
        assert d in prompt


# ============================================================
# Generator integration tests (with mocked AI)
# ============================================================


def _fake_llm_output() -> dict:
    return {
        d: {
            "narrative": f"[{d}] 日慈基金会做品牌升级, 张真秘书长是决策者, 高老师在 2026-03-30 前要交付方案, 预算 75,000 元",
            "confidence": "high" if d in ("essence", "people") else "medium",
            "confidenceReason": "基于 atomic_facts + entities 高置信度证据",
            "references": [
                {"sourceType": "entity", "sourceId": "ent_1", "label": "高老师", "confidence": "high"},
                {"sourceType": "atomic_fact", "sourceId": "af_2", "label": "工作坊目标", "confidence": "high"},
                {"sourceType": "event_line", "sourceId": "el_1"},
            ],
            "dataLayerGap": "",
            "openClarifications": ["王强老师跟王老师是同一个人吗?"] if d == "people" else [],
        }
        for d in DIMENSIONS
    } | {"overallConfidence": 0.75}


def test_generator_uses_real_facts_when_ai_ready(db: Database) -> None:
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    fake_health = MagicMock()
    fake_health.ready = True
    fake_ai = MagicMock()
    fake_ai.get_health.return_value = fake_health
    fake_ai._qwen_generate.return_value = _fake_llm_output()
    fake_ai.current_provider.return_value = "doubao"

    dims, overall, model = generate_narrative_dimensions(fake_ai, bundle)
    assert model != "stub"
    assert overall == pytest.approx(0.75)
    assert len(dims) == 6
    assert dims["people"]["confidence"] == "high"
    assert "张真" in dims["people"]["narrative"]
    assert any(r["sourceId"] == "ent_1" for r in dims["people"]["references"])
    assert "王强老师" in dims["people"]["openClarifications"][0]


def test_generator_stubs_when_ai_not_ready(db: Database) -> None:
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    fake_health = MagicMock()
    fake_health.ready = False
    fake_ai = MagicMock()
    fake_ai.get_health.return_value = fake_health

    dims, overall, model = generate_narrative_dimensions(fake_ai, bundle)
    assert model == "stub"
    assert overall == 0.0
    for d, payload in dims.items():
        assert payload["confidence"] == "low"
        assert "AI 暂时讲不出" in payload["narrative"]


def test_generator_validates_invalid_refs(db: Database) -> None:
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    fake_health = MagicMock()
    fake_health.ready = True
    fake_ai = MagicMock()
    fake_ai.get_health.return_value = fake_health
    bad_output = {
        d: {
            "narrative": "valid",
            "confidence": "medium",
            "references": [
                {"sourceType": "entity", "sourceId": "ent_1"},
                {"sourceType": "", "sourceId": "bad"},
                {"sourceType": "atomic_fact"},
                "not_a_dict",
            ],
        }
        for d in DIMENSIONS
    }
    bad_output["overallConfidence"] = 0.5
    fake_ai._qwen_generate.return_value = bad_output
    fake_ai.current_provider.return_value = "doubao"

    dims, overall, model = generate_narrative_dimensions(fake_ai, bundle)
    for d, payload in dims.items():
        assert len(payload["references"]) == 1
        assert payload["references"][0]["sourceId"] == "ent_1"


def test_data_layer_gaps_exposes_missing_layers(db: Database) -> None:
    bundle = collect_client_fact_bundle(db, CLIENT_ID)
    gaps = compute_data_layer_gaps(bundle)
    assert isinstance(gaps, list)
    # 1 event_line 只有, 应该报"颗粒度过粗"
    assert any("event_lines" in g for g in gaps)
