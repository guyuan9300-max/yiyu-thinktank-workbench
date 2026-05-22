"""[A] v2.2 F3 · NarrativeKernel 单元测试

服务: V2.1_AI_COLLABORATION.md A AI 职责区
- Mock 模式 (不调 LLM), 测 v0 deterministic 渲染逻辑
- 8 段结构完整性
- Tier A/B/C 引用规则 (R1)
- 排除 ugc / contradicted / superseded

跑法:
    cd backend && python3 -m pytest tests/test_v22_narrative_kernel.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.services.narrative_kernel import (  # noqa: E402
    NarrativeKernel,
    SECTION_KEYS,
    SECTION_TITLES,
    TIER_A_SOURCE_TYPES,
    TIER_B_SOURCE_TYPES,
    EXCLUDED_SOURCE_TYPES,
    get_narrative_kernel,
)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    # 建客户
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at)
           VALUES('c_rici','日慈基金会','日慈','项目','项目','','active','#5B7BFE',?,?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.commit()
    return db


def _insert_fact(
    db: Database,
    *,
    fact_id: str,
    client_id: str = "c_rici",
    subject: str,
    attribute: str,
    value: str,
    content_role: str = "fact",
    source_type: str = "client_internal_doc",
    confidence: float = 0.9,
    time_anchor: str | None = None,
    verification_status: str = "user_confirmed",
    validity_status: str = "current",
    evidence: str = "",
) -> None:
    now = "2026-05-22T10:00:00"
    db.conn.execute(
        """INSERT INTO atomic_facts (
            id, client_id, subject_text, attribute, value_text, value_normalized,
            confidence, status, created_at, updated_at,
            source_type, content_role, actor_type, actor_id,
            speaker_person_id, time_anchor,
            verification_status, confidence_source, validity_status,
            evidence_text
        ) VALUES (?, ?, ?, ?, ?, ?,
                  ?, 'active', ?, ?,
                  ?, ?, 'ai_agent', 'test',
                  NULL, ?, ?, 'rule', ?, ?)""",
        (fact_id, client_id, subject, attribute, value, value.lower(),
         confidence, now, now,
         source_type, content_role, time_anchor,
         verification_status, validity_status, evidence),
    )


# ════════════════════════════════════════════════════════════════
# 8 段结构完整性
# ════════════════════════════════════════════════════════════════


def test_section_keys_have_8(db: Database):
    """8 段固定: identity/people/main_lines/recent_changes/risks/our_collab/open_questions/timeline"""
    assert len(SECTION_KEYS) == 8
    expected = {"identity", "people", "main_lines", "recent_changes",
                "risks", "our_collab", "open_questions", "timeline"}
    assert set(SECTION_KEYS) == expected


def test_section_titles_complete(db: Database):
    """每段都有中文标题"""
    for sk in SECTION_KEYS:
        assert sk in SECTION_TITLES
        assert len(SECTION_TITLES[sk]) > 0


def test_generate_returns_8_sections(db: Database):
    """空数据库也应该返回 8 段 (每段提示无数据)"""
    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    assert len(narrative.story_sections) == 8
    section_keys = [s.section_key for s in narrative.story_sections]
    assert section_keys == list(SECTION_KEYS)


def test_generate_raises_on_missing_client(db: Database):
    kernel = NarrativeKernel(db)
    with pytest.raises(ValueError, match="not found"):
        kernel.generate("ghost_client")


# ════════════════════════════════════════════════════════════════
# Tier A/B/C 引用规则 (R1 顾源源 5/22)
# ════════════════════════════════════════════════════════════════


def test_tier_a_prioritizes_client_official_doc(db: Database):
    """Tier A: client_official_doc/internal_doc/verbal_meeting 优先"""
    _insert_fact(db, fact_id="f_a", subject="日慈", attribute="法人",
                 value="张真", source_type="client_official_doc",
                 content_role="fact", confidence=0.95)
    _insert_fact(db, fact_id="f_b", subject="日慈", attribute="员工数",
                 value="50人", source_type="user_observation",
                 content_role="fact", confidence=0.6)
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    identity = next(s for s in narrative.story_sections if s.section_key == "identity")
    # 应该都被 identity 段引用 (都是 role=fact)
    assert "f_a" in identity.cited_fact_ids
    # body 应该按 Tier A 优先呈现
    assert "客户已确认事实" in identity.body_markdown
    # source_count_by_tier 应该 a=1
    assert identity.source_count_by_tier["a"] == 1


def test_internet_ugc_excluded(db: Database):
    """internet_ugc 不进任何段 (排除)"""
    _insert_fact(db, fact_id="f_ugc", subject="日慈",
                 attribute="资金风险", value="可能资金链断裂",
                 source_type="internet_ugc",  # 排除!
                 content_role="risk", confidence=0.3)
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    risks = next(s for s in narrative.story_sections if s.section_key == "risks")
    # f_ugc 不应该出现
    assert "f_ugc" not in risks.cited_fact_ids


def test_internet_ai_inferred_excluded(db: Database):
    """internet_ai_inferred 也排除"""
    _insert_fact(db, fact_id="f_ai", subject="日慈",
                 attribute="预测", value="AI 推断",
                 source_type="internet_ai_inferred",
                 content_role="fact", confidence=0.2)
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    assert narrative.facts_excluded_by_tier >= 1


def test_superseded_facts_excluded(db: Database):
    """validity_status='superseded' 不进故事 (旧版本被推翻)"""
    _insert_fact(db, fact_id="f_old", subject="日慈", attribute="合同金额",
                 value="300 万", source_type="client_internal_doc",
                 validity_status="superseded", content_role="fact")
    _insert_fact(db, fact_id="f_new", subject="日慈", attribute="合同金额",
                 value="800 万", source_type="client_internal_doc",
                 validity_status="current", content_role="fact")
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    identity = next(s for s in narrative.story_sections if s.section_key == "identity")
    assert "f_new" in identity.cited_fact_ids
    assert "f_old" not in identity.cited_fact_ids


# ════════════════════════════════════════════════════════════════
# 每段按 content_role 筛选
# ════════════════════════════════════════════════════════════════


def test_people_section_includes_quote_role(db: Database):
    """people 段应该包含 quote (当事人原话)"""
    _insert_fact(db, fact_id="f_quote", subject="张真",
                 attribute="对兴盛计划判断", value="必须重塑",
                 content_role="quote",
                 source_type="client_internal_doc")
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    people = next(s for s in narrative.story_sections if s.section_key == "people")
    assert "f_quote" in people.cited_fact_ids


def test_main_lines_includes_progress_plan(db: Database):
    """main_lines 段应该包含 plan/progress/decision/fact"""
    _insert_fact(db, fact_id="f_plan", subject="兴盛计划",
                 attribute="6-7月动作", value="深度梳理",
                 content_role="plan", source_type="client_internal_doc")
    _insert_fact(db, fact_id="f_progress", subject="心盛计划",
                 attribute="本月进度", value="已启动",
                 content_role="progress", source_type="client_internal_doc")
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    main_lines = next(s for s in narrative.story_sections if s.section_key == "main_lines")
    assert "f_plan" in main_lines.cited_fact_ids
    assert "f_progress" in main_lines.cited_fact_ids


def test_risks_section_includes_risk_observation(db: Database):
    """risks 段应该包含 risk + observation"""
    _insert_fact(db, fact_id="f_risk", subject="日慈",
                 attribute="资金风险", value="审计趋严",
                 content_role="risk", source_type="client_verbal_meeting")
    _insert_fact(db, fact_id="f_obs", subject="日慈团队",
                 attribute="问题", value="关系大于事",
                 content_role="observation", source_type="user_observation")
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    risks = next(s for s in narrative.story_sections if s.section_key == "risks")
    assert "f_risk" in risks.cited_fact_ids
    assert "f_obs" in risks.cited_fact_ids


def test_our_collab_includes_commitment(db: Database):
    """our_collab 段应该包含 commitment + lesson + decision"""
    _insert_fact(db, fact_id="f_commit", subject="顾源源",
                 attribute="价值观稿任务", value="7月线下会前完成",
                 content_role="commitment", source_type="collaboration_task")
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    our_collab = next(s for s in narrative.story_sections if s.section_key == "our_collab")
    assert "f_commit" in our_collab.cited_fact_ids


def test_open_questions_low_confidence_unverified(db: Database):
    """open_questions 段: 低 confidence + unverified"""
    _insert_fact(db, fact_id="f_uncertain", subject="日慈",
                 attribute="某事", value="可能",
                 content_role="speculation",
                 verification_status="unverified",
                 confidence=0.4,
                 source_type="user_observation")
    _insert_fact(db, fact_id="f_certain", subject="日慈",
                 attribute="另一事", value="确定",
                 content_role="fact",
                 verification_status="user_confirmed",
                 confidence=0.95,
                 source_type="client_internal_doc")
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    open_q = next(s for s in narrative.story_sections if s.section_key == "open_questions")
    assert "f_uncertain" in open_q.cited_fact_ids
    assert "f_certain" not in open_q.cited_fact_ids


def test_timeline_orders_by_time_anchor(db: Database):
    """timeline 段按 time_anchor 升序"""
    _insert_fact(db, fact_id="f_late", subject="日慈",
                 attribute="x", value="x",
                 time_anchor="2026-05-19",
                 source_type="client_internal_doc")
    _insert_fact(db, fact_id="f_early", subject="日慈",
                 attribute="y", value="y",
                 time_anchor="2026-03-15",
                 source_type="client_internal_doc")
    _insert_fact(db, fact_id="f_no_anchor", subject="日慈",
                 attribute="z", value="z",
                 time_anchor=None,
                 source_type="client_internal_doc")
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    timeline = next(s for s in narrative.story_sections if s.section_key == "timeline")
    # 仅含带 time_anchor 的
    assert "f_late" in timeline.cited_fact_ids
    assert "f_early" in timeline.cited_fact_ids
    assert "f_no_anchor" not in timeline.cited_fact_ids
    # f_early 在前 (升序), f_late 在后
    early_idx = timeline.cited_fact_ids.index("f_early")
    late_idx = timeline.cited_fact_ids.index("f_late")
    assert early_idx < late_idx


# ════════════════════════════════════════════════════════════════
# ClientNarrative 元数据
# ════════════════════════════════════════════════════════════════


def test_narrative_contains_client_metadata(db: Database):
    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    assert narrative.client_id == "c_rici"
    assert narrative.client_name == "日慈基金会"
    assert narrative.generation_session_id.startswith("nk_")


def test_total_facts_consulted_counts_eligible_only(db: Database):
    """total_facts_consulted 只数 eligible (排除 ugc/contradicted/superseded)"""
    _insert_fact(db, fact_id="f1", subject="x", attribute="x", value="x",
                 source_type="client_internal_doc")
    _insert_fact(db, fact_id="f2", subject="x", attribute="x", value="x",
                 source_type="internet_ugc")  # 排除
    _insert_fact(db, fact_id="f3", subject="x", attribute="x", value="x",
                 source_type="client_internal_doc",
                 verification_status="contradicted")  # 排除
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    assert narrative.total_facts_consulted == 1  # 只 f1


def test_facts_excluded_by_tier_counted(db: Database):
    _insert_fact(db, fact_id="f_ugc1", subject="x", attribute="x", value="x",
                 source_type="internet_ugc")
    _insert_fact(db, fact_id="f_ugc2", subject="x", attribute="x", value="x",
                 source_type="internet_ai_inferred")
    db.conn.commit()

    kernel = NarrativeKernel(db)
    narrative = kernel.generate("c_rici")
    assert narrative.facts_excluded_by_tier == 2


# ════════════════════════════════════════════════════════════════
# Factory
# ════════════════════════════════════════════════════════════════


def test_factory_returns_kernel(db: Database):
    kernel = get_narrative_kernel(db, ai_service=None)
    assert isinstance(kernel, NarrativeKernel)
