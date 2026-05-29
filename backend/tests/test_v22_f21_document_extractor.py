"""v2.1 [A] F2.1 · DocumentLLMExtractor 单元测试

服务: V2.1_AI_COLLABORATION.md A AI 职责区
- 不依赖真实 LLM (mock ai_service), 只测 extractor 工作流逻辑
- 真实 LLM 调用留给"跑通战略执行手册.pdf" 那一步, 单独 demo

测试覆盖:
1. _map_kind_to_source_type: v2_documents.kind → 14 类 source_type 映射
2. _split_to_batches: 分批策略 (按段落边界, 12k 字阈值)
3. extract_from_document: 端到端工作流
   - 读 v2_document (markdown_content + 元数据)
   - 调 LLM (mock 返回 5 维元数据完整的 facts)
   - 走 IngestPipeline 写 atomic_facts
   - 写 reasoning_traces
   - 写 ai_episode_log
4. 失败路径:
   - v2_document 不存在 → 返回空 result
   - markdown 为空 → 返回空
   - LLM 调用失败 → 写 reasoning_trace status=failed
   - LLM 返回的 fact 缺必填字段 → facts_failed += 1
5. 信息商集成: 同一 subject+attribute 已有事实 → conflict / supersedes / complement

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_f21_document_extractor.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.services.document_llm_extractor import (  # noqa: E402
    DocumentLLMExtractor,
    _map_kind_to_source_type,
    _split_to_batches,
    get_document_llm_extractor,
)


# ════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    # 建客户 + v2_document 依赖
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at)
           VALUES('c_rici','A组织','A组织','项目','项目','','active','#5B7BFE',?,?)""",
        ("2026-05-22T10:00:00", "2026-05-22T10:00:00"),
    )
    db.conn.commit()
    return db


def _create_v2_document(
    db: Database,
    *,
    doc_id: str = "doc_test_001",
    client_id: str = "c_rici",
    file_name: str = "A组织测试.docx",
    kind: str = "docx",
    markdown_content: str = "A组织成立于 2010 年。\n\n负责人甲担任法人代表。",
) -> str:
    """建一个 v2_document 测试用"""
    now = "2026-05-22T10:00:00"
    db.conn.execute(
        """INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path,
            file_name, kind, material_layer, visible_category, secondary_category,
            parse_status, content_hash, markdown_content,
            section_count, chunk_count, imported_at, updated_at,
            is_searchable, organization_id, owner_user_id
        ) VALUES (?, ?, '', '', '', '', ?, ?, '', '', '',
                  'ready', '', ?, 0, 0, ?, ?, 1, '', '')""",
        (doc_id, client_id, file_name, kind, markdown_content, now, now),
    )
    db.conn.commit()
    return doc_id


@pytest.fixture
def mock_ai_service():
    """mock ai_service - 不调真实 LLM"""
    return MagicMock(name="mock_ai_service")


# ════════════════════════════════════════════════════════════════
# 1. _map_kind_to_source_type (渠道驱动 source_type 映射)
# ════════════════════════════════════════════════════════════════


def test_contract_filename_maps_to_official_doc():
    """合同 → client_official_doc (管理员甲 5/22 渠道驱动 fact)"""
    assert _map_kind_to_source_type("docx", "供应商合同_v3.docx") == "client_official_doc"
    assert _map_kind_to_source_type("contract", "随便.pdf") == "client_official_doc"


def test_strategy_manual_maps_to_official_doc():
    """战略手册 → client_official_doc"""
    assert _map_kind_to_source_type("pdf", "A组织战略执行手册.pdf") == "client_official_doc"
    assert _map_kind_to_source_type("docx", "annual report.docx") == "client_official_doc"


def test_meeting_minute_maps_to_internal_doc():
    """会议纪要 → client_internal_doc"""
    assert _map_kind_to_source_type("meeting", "5月19日.docx") == "client_internal_doc"
    assert _map_kind_to_source_type("docx", "纪要-周一.docx") == "client_internal_doc"


def test_review_maps_to_collaboration_review():
    """周复盘 → collaboration_review"""
    assert _map_kind_to_source_type("review", "x.docx") == "collaboration_review"
    assert _map_kind_to_source_type("docx", "周复盘-5月.docx") == "collaboration_review"


def test_task_doc_maps_to_collaboration_task():
    """task_doc → collaboration_task"""
    assert _map_kind_to_source_type("task_doc", "任务描述.docx") == "collaboration_task"


def test_wechat_maps_to_internet_ugc():
    """微信公众号 → internet_ugc (低置信度)"""
    assert _map_kind_to_source_type("wechat_excerpt", "公众号文章.docx") == "internet_ugc"
    assert _map_kind_to_source_type("docx", "微信摘录.docx") == "internet_ugc"


def test_unknown_kind_defaults_to_internal_doc():
    """未知 kind 默认 client_internal_doc (用户主动上传的资料)"""
    assert _map_kind_to_source_type("docx", "随便起的名.docx") == "client_internal_doc"
    assert _map_kind_to_source_type("pdf", "无线索文件.pdf") == "client_internal_doc"


# ════════════════════════════════════════════════════════════════
# 2. _split_to_batches (分批策略)
# ════════════════════════════════════════════════════════════════


def test_short_text_single_batch():
    """短文本不分批"""
    text = "短内容" * 100  # 300 字, 远小于 12000
    batches = _split_to_batches(text, 12000)
    assert len(batches) == 1
    assert batches[0] == text


def test_long_text_splits_into_multiple_batches():
    """超阈值分多批"""
    text = "a" * 30000
    batches = _split_to_batches(text, 12000)
    assert len(batches) >= 2
    # 总长度保持
    assert sum(len(b) for b in batches) == 30000


def test_split_prefers_paragraph_boundary():
    """优先在段落边界 (\\n\\n) 切, 不在词中间切"""
    # 8000 字 + \n\n + 8000 字 = 跨阈值, 应该在段落边界切
    text = "a" * 8000 + "\n\n" + "b" * 8000
    batches = _split_to_batches(text, 12000)
    # 第一批应该止于段落边界, 第二批从下一段开始
    assert len(batches) == 2
    # 第一批不应该包含 b
    assert "b" not in batches[0]


# ════════════════════════════════════════════════════════════════
# 3. extract_from_document 端到端 (mock LLM)
# ════════════════════════════════════════════════════════════════


def _make_llm_payload(facts: list[dict]) -> dict:
    """构造 mock LLM 返回的 payload (符合 EXTRACTION_RESPONSE_SCHEMA)"""
    return {
        "extracted_facts": facts,
        "skipped_general_count": 0,
        "extraction_summary": f"抽出 {len(facts)} 条事实",
    }


def test_extract_returns_empty_when_doc_not_found(db: Database, mock_ai_service):
    """v2_document 不存在 → 返回 errors"""
    extractor = DocumentLLMExtractor(db, mock_ai_service)
    result = extractor.extract_from_document(
        v2_document_id="ghost_doc",
        ai_session_id="ai_sess_001",
    )
    assert result.facts_written == 0
    assert "not found" in " ".join(result.errors).lower()


def test_extract_returns_empty_when_markdown_empty(db: Database, mock_ai_service):
    """markdown_content 为空 → 返回 empty"""
    _create_v2_document(db, doc_id="doc_empty", markdown_content="")
    extractor = DocumentLLMExtractor(db, mock_ai_service)
    result = extractor.extract_from_document(
        v2_document_id="doc_empty",
        ai_session_id="ai_sess_001",
    )
    assert result.facts_written == 0
    assert "empty" in " ".join(result.errors).lower()


def test_extract_writes_facts_via_ingest_pipeline(db: Database, mock_ai_service, monkeypatch):
    """端到端: mock LLM 返回 2 条事实 → IngestPipeline 写入 atomic_facts 表"""
    doc_id = _create_v2_document(
        db,
        markdown_content="A组织成立于 2010 年。\n\n负责人甲担任法人代表。",
    )
    # mock LLM 返回 2 条 facts (5 维元数据完整)
    mock_payload = _make_llm_payload([
        {
            "subject_text": "A组织",
            "attribute": "成立年份",
            "value_text": "2010 年",
            "content_role": "fact",
            "layer": "L1",
            "evidence_text": "A组织成立于 2010 年。",
            "time_anchor": "2010-01-01",
            "speaker_person_id": None,
            "confidence": 0.95,
            "reasoning_steps": [
                "段落 1 明确说'成立于 2010 年'",
                "结论: A组织.成立年份 = 2010 年",
            ],
        },
        {
            "subject_text": "负责人甲",
            "attribute": "角色",
            "value_text": "A组织法人代表",
            "content_role": "fact",
            "layer": "L2",
            "evidence_text": "负责人甲担任法人代表。",
            "time_anchor": None,
            "speaker_person_id": None,
            "confidence": 0.90,
            "reasoning_steps": ["段落 2 说负责人甲担任法人代表"],
        },
    ])

    # mock generate_intelligence_json
    from app.services import intelligence_ai_runner
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.payload = mock_payload
    mock_result.error = None
    monkeypatch.setattr(
        intelligence_ai_runner,
        "generate_intelligence_json",
        lambda *a, **kw: mock_result,
    )

    extractor = DocumentLLMExtractor(db, mock_ai_service)
    result = extractor.extract_from_document(
        v2_document_id=doc_id,
        ai_session_id="ai_sess_001",
        actor_id="user_example_user",
    )

    # 验证: facts_written = 2
    assert result.facts_written == 2
    assert result.facts_failed == 0
    # atomic_facts 表里有 2 条 — 按 attribute 查 (避免中文 ORDER BY 不确定)
    rici_row = db.fetchone(
        "SELECT * FROM atomic_facts WHERE client_id='c_rici' AND attribute='成立年份'"
    )
    zhang_row = db.fetchone(
        "SELECT * FROM atomic_facts WHERE client_id='c_rici' AND attribute='角色'"
    )
    assert rici_row is not None
    assert zhang_row is not None
    # A组织 / 成立年份 / 5 维元数据完整
    assert rici_row["subject_text"] == "A组织"
    assert rici_row["value_text"] == "2010 年"
    assert rici_row["source_type"] == "client_internal_doc"  # docx kind 映射
    assert rici_row["content_role"] == "fact"
    assert rici_row["actor_type"] == "ai_agent"  # F2.1 是 AI 抽的
    assert rici_row["actor_id"] == "ai_sess_001"
    assert rici_row["time_anchor"] == "2010-01-01"
    assert rici_row["verification_status"] == "unverified"
    assert rici_row["confidence_source"] == "llm"
    assert abs(float(rici_row["confidence"]) - 0.95) < 0.001
    # 负责人甲 / 角色 / 5 维元数据完整
    assert zhang_row["subject_text"] == "负责人甲"
    assert zhang_row["value_text"] == "A组织法人代表"


def test_extract_writes_reasoning_trace(db: Database, mock_ai_service, monkeypatch):
    """每批写一条 reasoning_trace (N3 A3)"""
    doc_id = _create_v2_document(db, markdown_content="测试内容")
    mock_payload = _make_llm_payload([{
        "subject_text": "X", "attribute": "Y", "value_text": "Z",
        "content_role": "fact", "evidence_text": "测试", "confidence": 0.5,
        "reasoning_steps": ["step 1"],
    }])
    from app.services import intelligence_ai_runner
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.payload = mock_payload
    monkeypatch.setattr(
        intelligence_ai_runner, "generate_intelligence_json",
        lambda *a, **kw: mock_result,
    )

    extractor = DocumentLLMExtractor(db, mock_ai_service)
    extractor.extract_from_document(
        v2_document_id=doc_id, ai_session_id="ai_sess_trace",
    )
    # reasoning_traces 应该有 1 条 (单批)
    rows = db.fetchall(
        "SELECT * FROM reasoning_traces WHERE ai_session_id = 'ai_sess_trace'"
    )
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    assert rows[0]["output_entity_type"] == "atomic_fact"


def test_extract_writes_ai_episode_log(db: Database, mock_ai_service, monkeypatch):
    """每条 fact 走 IngestPipeline → 写 ai_episode_log (N3 A5 dogfood)"""
    doc_id = _create_v2_document(db, markdown_content="测试")
    mock_payload = _make_llm_payload([{
        "subject_text": "X", "attribute": "Y", "value_text": "Z",
        "content_role": "fact", "evidence_text": "ev", "confidence": 0.5,
        "reasoning_steps": [],
    }])
    from app.services import intelligence_ai_runner
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.payload = mock_payload
    monkeypatch.setattr(
        intelligence_ai_runner, "generate_intelligence_json",
        lambda *a, **kw: mock_result,
    )

    extractor = DocumentLLMExtractor(db, mock_ai_service)
    extractor.extract_from_document(
        v2_document_id=doc_id, ai_session_id="ai_sess_episode",
    )
    # ai_episode_log 应该有 1 条 (extracted_fact)
    rows = db.fetchall(
        "SELECT * FROM ai_episode_log WHERE ai_session_id = 'ai_sess_episode'"
    )
    assert len(rows) >= 1
    assert any(r["action_type"] == "extracted_fact" for r in rows)


def test_extract_llm_failure_records_trace_failed(db: Database, mock_ai_service, monkeypatch):
    """LLM 调用失败 → reasoning_trace status='failed' + errors 列表"""
    doc_id = _create_v2_document(db, markdown_content="测试")
    from app.services import intelligence_ai_runner
    # mock LLM 返回失败
    mock_result = MagicMock()
    mock_result.ok = False
    mock_result.payload = None
    mock_result.error = "LLM API timeout"
    monkeypatch.setattr(
        intelligence_ai_runner, "generate_intelligence_json",
        lambda *a, **kw: mock_result,
    )

    extractor = DocumentLLMExtractor(db, mock_ai_service)
    result = extractor.extract_from_document(
        v2_document_id=doc_id, ai_session_id="ai_sess_fail",
    )
    assert result.facts_written == 0
    # reasoning_trace 应该 status='failed'
    rows = db.fetchall(
        "SELECT * FROM reasoning_traces WHERE ai_session_id = 'ai_sess_fail'"
    )
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"


def test_extract_skips_fact_missing_required_fields(db: Database, mock_ai_service, monkeypatch):
    """LLM 返回的 fact 缺 subject/attribute/value → 跳过, facts_failed += 1"""
    doc_id = _create_v2_document(db, markdown_content="测试")
    # 故意返回 1 条完整 + 1 条缺字段
    mock_payload = _make_llm_payload([
        {
            "subject_text": "完整", "attribute": "X", "value_text": "Y",
            "content_role": "fact", "evidence_text": "ev", "confidence": 0.5,
            "reasoning_steps": [],
        },
        {
            "subject_text": "", "attribute": "缺主语", "value_text": "Y",  # 空 subject
            "content_role": "fact", "evidence_text": "ev", "confidence": 0.5,
            "reasoning_steps": [],
        },
    ])
    from app.services import intelligence_ai_runner
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.payload = mock_payload
    monkeypatch.setattr(
        intelligence_ai_runner, "generate_intelligence_json",
        lambda *a, **kw: mock_result,
    )

    extractor = DocumentLLMExtractor(db, mock_ai_service)
    result = extractor.extract_from_document(
        v2_document_id=doc_id, ai_session_id="ai_sess_invalid",
    )
    assert result.facts_written == 1
    assert result.facts_failed == 1


# ════════════════════════════════════════════════════════════════
# 4. 信息商集成: 抽取触发 conflict / supersedes / complement
# ════════════════════════════════════════════════════════════════


def test_extract_triggers_supersedes_when_update_keyword(db: Database, mock_ai_service, monkeypatch):
    """已有事实 + LLM 抽出"重签/改成" 语义 → supersedes"""
    # 先建一条已有事实 (旧的合同金额)
    now = "2026-05-22T10:00:00"
    db.conn.execute(
        """INSERT INTO atomic_facts (
            id, client_id, subject_text, attribute, value_text, value_normalized,
            confidence, status, created_at, updated_at,
            source_type, content_role, actor_type, validity_status
        ) VALUES (
            'af_old', 'c_rici', 'A组织', '合同金额', '300 万', '300 万',
            0.7, 'active', ?, ?, 'client_official_doc', 'fact', 'human', 'current'
        )""",
        (now, now),
    )
    db.conn.commit()

    # LLM 抽出新事实: 含"重签"语义
    doc_id = _create_v2_document(db, markdown_content="合同金额要重签为 800 万")
    mock_payload = _make_llm_payload([{
        "subject_text": "A组织",
        "attribute": "合同金额",
        "value_text": "应该是 800 万, 合同金额写错了要重签",
        "content_role": "fact",
        "evidence_text": "合同金额要重签为 800 万",
        "confidence": 0.85,
        "reasoning_steps": ["原文说要重签 800 万"],
    }])
    from app.services import intelligence_ai_runner
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.payload = mock_payload
    monkeypatch.setattr(
        intelligence_ai_runner, "generate_intelligence_json",
        lambda *a, **kw: mock_result,
    )

    extractor = DocumentLLMExtractor(db, mock_ai_service)
    result = extractor.extract_from_document(
        v2_document_id=doc_id, ai_session_id="ai_sess_supersede",
    )
    assert result.facts_written == 1
    # update_relations 应该有 supersedes
    assert result.update_relations.get("supersedes", 0) == 1
    # 旧事实应被标 superseded
    old_row = db.fetchone("SELECT * FROM atomic_facts WHERE id = 'af_old'")
    assert old_row["validity_status"] == "superseded"


# ════════════════════════════════════════════════════════════════
# 5. layer 覆盖统计
# ════════════════════════════════════════════════════════════════


def test_extract_records_layer_coverage(db: Database, mock_ai_service, monkeypatch):
    """LLM 返回的 facts 带 layer 字段 → result.layer_coverage 统计"""
    doc_id = _create_v2_document(db, markdown_content="X")
    mock_payload = _make_llm_payload([
        {"subject_text": "A", "attribute": "X", "value_text": "1",
         "content_role": "fact", "layer": "L1",
         "evidence_text": "e", "confidence": 0.5, "reasoning_steps": []},
        {"subject_text": "B", "attribute": "X", "value_text": "2",
         "content_role": "fact", "layer": "L1",
         "evidence_text": "e", "confidence": 0.5, "reasoning_steps": []},
        {"subject_text": "C", "attribute": "X", "value_text": "3",
         "content_role": "decision", "layer": "L4",
         "evidence_text": "e", "confidence": 0.5, "reasoning_steps": []},
    ])
    from app.services import intelligence_ai_runner
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.payload = mock_payload
    monkeypatch.setattr(
        intelligence_ai_runner, "generate_intelligence_json",
        lambda *a, **kw: mock_result,
    )

    extractor = DocumentLLMExtractor(db, mock_ai_service)
    result = extractor.extract_from_document(
        v2_document_id=doc_id, ai_session_id="ai_sess_layer",
    )
    assert result.facts_written == 3
    assert result.layer_coverage.get("L1") == 2
    assert result.layer_coverage.get("L4") == 1


# ════════════════════════════════════════════════════════════════
# 6. factory
# ════════════════════════════════════════════════════════════════


def test_factory_returns_extractor_instance(db: Database, mock_ai_service):
    extractor = get_document_llm_extractor(db, mock_ai_service)
    assert isinstance(extractor, DocumentLLMExtractor)
