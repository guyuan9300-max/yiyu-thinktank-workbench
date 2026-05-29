"""v2.2 Phase 2 F2.4 + 5 件事 · IngestPipeline 测试

服务: V2.2_NORTH_STAR.md
- N1 功能顺畅: IngestPipeline 替代散落 4 路径 ingest, 不破坏现有功能
- N2 数据中心理解信息源: 4 路径 normalizer + 渠道驱动 content_role + 信息商
- N3 接入预留: 写入顺手写 ai_episode_log + event_log

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_ingest_pipeline.py -v

测试覆盖:
1. 4 路径 normalizer 默认元数据正确 (路径 1-4)
2. 渠道驱动 content_role 兜底判断
3. 管理员甲"信息商" 洞察: conflict vs supersedes vs complement 判断
4. IngestPipeline 主流程: 写 atomic_facts + event_log + ai_episode_log
5. 重复信息不写 (none + 值相同)
6. supersedes 时旧事实标 superseded_by_id, 新事实标 update_relation='supersedes'
7. ai_improvement_suggestions 表占位 (Phase 2 起步 schema)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.services.ingest_pipeline import (  # noqa: E402
    IngestMetadata,
    IngestPipeline,
    IngestRequest,
    SOURCE_TYPE_BASE_CONFIDENCE,
    SOURCE_TYPE_TO_DEFAULT_ROLE,
    base_confidence_for_source,
    default_role_for_source,
    detect_update_relation,
    log_ai_episode,
    log_event,
    metadata_for_internet_crawler,
    metadata_for_mobile_ai_chat,
    metadata_for_task_review,
    metadata_for_workbench_file,
)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    # 建一个客户依赖
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at)
           VALUES('c_test','测试客户','test','项目','项目','','active','#5B7BFE',?,?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.commit()
    return db


# ════════════════════════════════════════════════════════════════
# 1. 渠道驱动 content_role 兜底 (管理员甲 5/22 规则)
# ════════════════════════════════════════════════════════════════


def test_source_type_to_default_role_complete():
    """所有定义的 SourceType 都有 default_role 映射"""
    expected_sources = {
        "client_official_doc", "client_internal_doc", "client_verbal_meeting",
        "collaboration_task", "collaboration_review",
        "user_observation", "user_verbal_fact",
        "internet_official", "internet_media", "internet_ugc", "internet_ai_inferred",
        "llm_extracted", "system_derived", "ai_agent_authored",
    }
    assert set(SOURCE_TYPE_TO_DEFAULT_ROLE.keys()) == expected_sources
    assert set(SOURCE_TYPE_BASE_CONFIDENCE.keys()) == expected_sources


def test_default_role_contracts_are_fact():
    """管理员甲原话: '已经签署的文件合同, 它就是事实'"""
    assert default_role_for_source("client_official_doc") == "fact"


def test_default_role_meeting_minute_is_decision():
    """管理员甲原话: '会议纪要确定的事情, 他可能就是决策'"""
    assert default_role_for_source("client_internal_doc") == "decision"


def test_default_role_review_is_lesson():
    """管理员甲原话: '主观的人的复盘 ... 是经验性的'"""
    assert default_role_for_source("collaboration_review") == "lesson"


def test_default_role_internet_ugc_is_speculation():
    """公众号 / 微博 → 不可信 → speculation"""
    assert default_role_for_source("internet_ugc") == "speculation"


def test_base_confidence_authoritative_high(self_=None):
    """已签合同 0.95, 政府公示 0.85"""
    assert base_confidence_for_source("client_official_doc") == 0.95
    assert base_confidence_for_source("internet_official") == 0.85


def test_base_confidence_ugc_low():
    """公众号 / AI 推断 / 极低置信度"""
    assert base_confidence_for_source("internet_ugc") == 0.30
    assert base_confidence_for_source("internet_ai_inferred") == 0.20


def test_default_role_unknown_source_fallback_fact():
    """未知 source_type 兜底 'fact' (保守)"""
    assert default_role_for_source("unknown_xyz") == "fact"
    assert base_confidence_for_source("unknown_xyz") == 0.50


# ════════════════════════════════════════════════════════════════
# 2. 4 路径 normalizer 默认元数据
# ════════════════════════════════════════════════════════════════


def test_workbench_file_contract_metadata():
    """路径 1 合同 → source_type=client_official_doc + content_role=fact + 高置信度"""
    md = metadata_for_workbench_file(
        file_doc_type="contract",
        actor_id="user_example_user",
        time_anchor="2026-05-22",
    )
    assert md.source_type == "client_official_doc"
    assert md.content_role == "fact"
    assert md.actor_type == "human"
    assert md.actor_id == "user_example_user"
    assert md.confidence_score == 0.95


def test_workbench_file_article_metadata():
    """路径 1 文章 → source_type=client_internal_doc + content_role=decision (默认值会被 LLM 二次精化)"""
    md = metadata_for_workbench_file(
        file_doc_type="article",
        actor_id="user_example_user",
    )
    assert md.source_type == "client_internal_doc"


def test_task_review_metadata_user_confirmed():
    """路径 2 用户主动写 task → 直接 user_confirmed"""
    md = metadata_for_task_review(sub_kind="task", actor_id="u1")
    assert md.verification_status == "user_confirmed"
    assert md.confidence_score == 0.90
    assert md.content_role == "plan"


def test_internet_crawler_ugc_metadata_low_confidence():
    """路径 3 公众号 → 极低置信度 + speculation"""
    md = metadata_for_internet_crawler(crawler_kind="ugc", crawler_run_id="crawl_001")
    assert md.source_type == "internet_ugc"
    assert md.content_role == "speculation"
    assert md.confidence_score == 0.30
    assert md.actor_type == "system"


def test_mobile_ai_chat_subjective_observation():
    """路径 4 用户主观判断 → user_observation + unverified"""
    md = metadata_for_mobile_ai_chat(
        user_id="user_example_user",
        is_user_subjective=True,
    )
    assert md.source_type == "user_observation"
    assert md.content_role == "observation"
    assert md.verification_status == "unverified"


def test_mobile_ai_chat_verbal_fact_confirmed():
    """路径 4 用户口述客户事实 → user_verbal_fact + user_confirmed"""
    md = metadata_for_mobile_ai_chat(
        user_id="user_example_user",
        speaker_person_id="person_zhangzhen",
        is_user_subjective=False,
    )
    assert md.source_type == "user_verbal_fact"
    assert md.speaker_person_id == "person_zhangzhen"
    assert md.verification_status == "user_confirmed"


# ════════════════════════════════════════════════════════════════
# 3. ★ 信息商 (管理员甲 5/22 洞察)
# ════════════════════════════════════════════════════════════════


def test_no_prior_fact_is_none():
    """没有同主题已有事实 → relation='none'"""
    v = detect_update_relation(
        new_value="800 万",
        existing_facts=[],
        new_source_type="client_verbal_meeting",
    )
    assert v.relation == "none"


def test_duplicate_value_is_none_no_write():
    """新值跟已有值完全一样 → relation='none' (不重复写)"""
    existing = [{"id": "f_old", "value_text": "800 万"}]
    v = detect_update_relation(
        new_value="800 万",
        existing_facts=existing,
        new_source_type="client_verbal_meeting",
    )
    assert v.relation == "none"
    assert "duplicate" in v.reasoning


def test_supersede_keyword_重签_detected():
    """管理员甲场景: '合同金额 300 万要改成 800 万重签' → supersedes"""
    existing = [{"id": "f_contract_old", "value_text": "300 万", "validity_status": "current"}]
    v = detect_update_relation(
        new_value="应该是 800 万, 这个合同金额有问题要重签",
        existing_facts=existing,
        new_source_type="user_verbal_fact",
    )
    assert v.relation == "supersedes"
    assert v.target_fact_id == "f_contract_old"
    assert "update keyword" in v.reasoning


def test_supersede_keyword_改为_detected():
    """另一种更新表达: '改为'"""
    existing = [{"id": "f_old", "value_text": "中型", "validity_status": "current"}]
    v = detect_update_relation(
        new_value="改为大型客户",
        existing_facts=existing,
        new_source_type="user_verbal_fact",
    )
    assert v.relation == "supersedes"


def test_conflict_without_update_semantic():
    """值不同 + 没有更新关键词 → conflict (进澄清队列)"""
    existing = [{"id": "f_old", "value_text": "100 万"}]
    v = detect_update_relation(
        new_value="200 万",
        existing_facts=existing,
        new_source_type="user_verbal_fact",
    )
    assert v.relation == "conflict"


# ════════════════════════════════════════════════════════════════
# 4. IngestPipeline 端到端: atomic_facts + event_log + ai_episode_log 同步写
# ════════════════════════════════════════════════════════════════


def test_ingest_creates_atomic_fact_and_event_log(db: Database):
    """端到端: 写一条事实, atomic_facts + event_log 都有记录"""
    pipeline = IngestPipeline(db)
    md = metadata_for_workbench_file(
        file_doc_type="contract",
        actor_id="user_example_user",
        time_anchor="2026-05-22",
    )
    req = IngestRequest(
        path="workbench_file",
        client_id="c_test",
        subject_text="A组织",
        attribute="合同金额",
        value_text="800 万",
        metadata=md,
        source_v2_document_id="doc_001",
    )
    result = pipeline.ingest(req)
    assert result.written is True
    assert result.update_relation == "none"
    assert result.fact_id.startswith("af_")

    # atomic_facts 表有记录
    row = db.fetchone("SELECT * FROM atomic_facts WHERE id = ?", (result.fact_id,))
    assert row is not None
    assert row["source_type"] == "client_official_doc"
    assert row["content_role"] == "fact"
    assert row["actor_type"] == "human"
    assert row["update_relation"] == "none"
    assert row["validity_status"] == "current"

    # event_log 有记录
    rows = db.fetchall(
        "SELECT * FROM event_log WHERE entity_id = ? ORDER BY occurred_at",
        (result.fact_id,),
    )
    assert len(rows) == 1
    assert rows[0]["event_type"] == "client.fact_created"


def test_ingest_writes_ai_episode_log_when_session_given(db: Database):
    """如果带 ai_session_id, 顺手写 ai_episode_log (管理员甲 5/22 决策: v2.2 阶段就写)"""
    pipeline = IngestPipeline(db)
    md = metadata_for_workbench_file(
        file_doc_type="meeting_minute",
        actor_id="user_example_user",
    )
    req = IngestRequest(
        path="workbench_file",
        client_id="c_test",
        subject_text="负责人甲",
        attribute="角色",
        value_text="法人代表",
        metadata=md,
        ai_session_id="ai_sess_2026_05_22_001",
        source_v2_document_id="doc_meeting_519",
    )
    result = pipeline.ingest(req)
    assert result.written is True
    # ai_episode_log 有记录
    row = db.fetchone(
        "SELECT * FROM ai_episode_log WHERE ai_session_id = 'ai_sess_2026_05_22_001'"
    )
    assert row is not None
    assert row["action_type"] == "extracted_fact"
    assert row["outcome"] == "pending"


def test_ingest_skips_duplicate_value(db: Database):
    """重复信息不写 (relation='none' + 值相同) — 节省存储 + 信噪比"""
    pipeline = IngestPipeline(db)
    md = metadata_for_workbench_file(file_doc_type="contract", actor_id="u1")
    req1 = IngestRequest(
        path="workbench_file", client_id="c_test",
        subject_text="A组织", attribute="法人", value_text="负责人甲",
        metadata=md,
    )
    r1 = pipeline.ingest(req1)
    assert r1.written is True
    # 同样的事实再写一次
    r2 = pipeline.ingest(req1)
    assert r2.written is False
    # atomic_facts 只有一条
    rows = db.fetchall("SELECT * FROM atomic_facts WHERE client_id = 'c_test' AND attribute = '法人'")
    assert len(rows) == 1


def test_ingest_supersedes_old_fact_with_update_keyword(db: Database):
    """★ 管理员甲场景核心: 用户说'改成 800 万要重签' → 旧事实 superseded, 新事实 current"""
    pipeline = IngestPipeline(db)
    # 先写一个旧合同金额
    md_old = metadata_for_workbench_file(file_doc_type="contract", actor_id="u1")
    req_old = IngestRequest(
        path="workbench_file", client_id="c_test",
        subject_text="A组织", attribute="合同金额", value_text="300 万",
        metadata=md_old,
    )
    r_old = pipeline.ingest(req_old)
    assert r_old.written is True

    # 用户在手机 AI 聊天里说要重签
    md_new = metadata_for_mobile_ai_chat(user_id="user_example_user", is_user_subjective=False)
    req_new = IngestRequest(
        path="mobile_ai_chat", client_id="c_test",
        subject_text="A组织", attribute="合同金额",
        value_text="应该是 800 万, 合同金额写错了要重签",
        metadata=md_new,
    )
    r_new = pipeline.ingest(req_new)
    assert r_new.written is True
    assert r_new.update_relation == "supersedes"
    assert r_new.superseded_target_id == r_old.fact_id

    # 旧事实: validity_status='superseded', superseded_by_id 指向新
    old_row = db.fetchone("SELECT * FROM atomic_facts WHERE id = ?", (r_old.fact_id,))
    assert old_row["validity_status"] == "superseded"
    assert old_row["superseded_by_id"] == r_new.fact_id

    # 新事实: update_relation='supersedes', current
    new_row = db.fetchone("SELECT * FROM atomic_facts WHERE id = ?", (r_new.fact_id,))
    assert new_row["validity_status"] == "current"
    assert new_row["update_relation"] == "supersedes"

    # event_log 有 client.fact_superseded
    rows = db.fetchall(
        "SELECT * FROM event_log WHERE entity_id = ?", (r_new.fact_id,)
    )
    assert rows[0]["event_type"] == "client.fact_superseded"


def test_ingest_conflict_when_no_update_semantic(db: Database):
    """两个不同值但没有更新语义 → conflict (进澄清队列)"""
    pipeline = IngestPipeline(db)
    md1 = metadata_for_workbench_file(file_doc_type="contract", actor_id="u1")
    pipeline.ingest(IngestRequest(
        path="workbench_file", client_id="c_test",
        subject_text="A组织", attribute="员工数", value_text="50 人",
        metadata=md1,
    ))
    md2 = metadata_for_internet_crawler(crawler_kind="ugc", crawler_run_id="crawl_001")
    r2 = pipeline.ingest(IngestRequest(
        path="internet_crawler", client_id="c_test",
        subject_text="A组织", attribute="员工数", value_text="120 人",
        metadata=md2,
    ))
    assert r2.written is True
    assert r2.update_relation == "conflict"
    new_row = db.fetchone("SELECT * FROM atomic_facts WHERE id = ?", (r2.fact_id,))
    assert new_row["update_relation"] == "conflict"


# ════════════════════════════════════════════════════════════════
# 5. log_ai_episode + log_event 独立封装
# ════════════════════════════════════════════════════════════════


def test_log_ai_episode_writes_record(db: Database):
    """log_ai_episode 单独可用, 不一定走 IngestPipeline"""
    log_ai_episode(
        db,
        ai_session_id="ai_sess_test",
        action_type="requested_human_help",
        action_summary="我无法分辨负责人甲接的是法人还是理事长, 请补充",
        user_id="user_example_user",
        client_id="c_test",
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM ai_episode_log WHERE ai_session_id = 'ai_sess_test'"
    )
    assert row is not None
    assert row["action_type"] == "requested_human_help"  # 管理员甲洞察 4: AI 反向给人类提请求


def test_log_event_writes_record(db: Database):
    """log_event 单独可用"""
    log_event(
        db,
        event_type="ai.action_taken",
        entity_type="task",
        entity_id="task_xyz",
        actor_type="ai_agent",
        actor_id="ai_session_001",
        client_id="c_test",
        payload={"action": "create_task", "title": "拟合同初稿"},
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM event_log WHERE entity_id = 'task_xyz'"
    )
    assert row is not None
    assert row["actor_type"] == "ai_agent"
    payload = json.loads(row["payload_json"])
    assert payload["title"] == "拟合同初稿"


# ════════════════════════════════════════════════════════════════
# 6. ai_improvement_suggestions schema (Phase 2 起步)
# ════════════════════════════════════════════════════════════════


def test_ai_improvement_suggestions_table_exists(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_improvement_suggestions'"
    )
    assert len(rows) == 1


def test_ai_improvement_suggestions_can_insert(db: Database):
    """AI 提流程改进建议: '系统缺服务类合同标签'"""
    db.conn.execute(
        """
        INSERT INTO ai_improvement_suggestions (
            ai_session_id, suggestion_category,
            suggestion_title, suggestion_body,
            observed_pain_count, suggested_at, last_observed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ai_sess_001",
            "add_tag",
            "增加'服务类合同'标签",
            "我最近 3 次拟合同都遇到分不清服务类 vs 销售类的问题, 建议系统加这个标签",
            3,
            "2026-05-22T11:00:00",
            "2026-05-22T13:00:00",
        ),
    )
    db.conn.commit()
    row = db.fetchone(
        "SELECT * FROM ai_improvement_suggestions WHERE suggestion_title LIKE '%服务类%'"
    )
    assert row is not None
    assert row["observed_pain_count"] == 3
    assert row["review_status"] == "pending"  # 默认值


# ════════════════════════════════════════════════════════════════
# 7. atomic_facts.update_relation 字段
# ════════════════════════════════════════════════════════════════


def test_atomic_facts_has_update_relation_column(db: Database):
    """v2.2 Phase 2 起步: update_relation 字段就位"""
    rows = db.fetchall("PRAGMA table_info(atomic_facts)")
    cols = {r["name"]: r for r in rows}
    assert "update_relation" in cols
    assert cols["update_relation"]["dflt_value"] == "'none'"


def test_atomic_facts_update_relation_index_present(db: Database):
    """update_relation 索引就位 (查 conflict/superseded 队列用)"""
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND name='idx_atomic_facts_update_relation'"
    )
    assert len(rows) == 1
