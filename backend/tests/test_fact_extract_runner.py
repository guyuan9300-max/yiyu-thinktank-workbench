"""meeting-spine ② · fact_extract_runner + 深读 worker 接线测试。

不依赖真实 LLM(monkeypatch generate_intelligence_json)。验证:
- runner 走真 DocumentLLMExtractor → 真 IngestPipeline 写 atomic_facts
- ★Phase0 speaker 解析钩子在此路径通电(speaker_entity_id 被回填)
- ★Phase1③ owner/speaker 对齐(顾源源→mirror_user internal)
- router 上传自动入队 fact_extract + 幂等
- worker 按 task_type 派发到 fact_extract_runner
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database
from app.services import intelligence_ai_runner, local_model_optimizer as lmo
from app.services.task_runners import fact_extract_runner
from app.services.task_runners.router import route_document_for_local_inference


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    db.conn.execute("DROP TABLE IF EXISTS mirror_users")
    db.conn.execute("CREATE TABLE mirror_users (id TEXT PRIMARY KEY, full_name TEXT, primary_role TEXT)")
    db.conn.execute("INSERT INTO mirror_users(id,full_name,primary_role) VALUES('u_gu','顾源源','秘书长')")
    db.conn.execute(
        "INSERT INTO clients(id,name,alias,domain,type,intro,stage,color,created_at,updated_at) "
        "VALUES('c_rici','日慈基金会','日慈','项目','项目','','active','#5B7BFE','t','t')"
    )
    db.conn.commit()
    return db


def _v2doc(db: Database, doc_id: str = "doc_rici_meeting") -> str:
    md = "会议纪要：张真说要推进心盛计划升级。\n\n顾源源承诺下周给出升级方案。"
    db.conn.execute(
        """INSERT INTO v2_documents(id, client_id, document_id, original_path, managed_path, markdown_path,
            file_name, kind, material_layer, visible_category, secondary_category,
            parse_status, content_hash, markdown_content, section_count, chunk_count,
            imported_at, updated_at, is_searchable, organization_id, owner_user_id)
           VALUES(?, 'c_rici', ?, '', '', '', '日慈5月会议纪要.docx', 'meeting', '', '', '',
                  'ready', 'h1', ?, 0,0,'t','t',1,'','')""",
        (doc_id, doc_id, md),
    )
    db.conn.commit()
    return doc_id


def _patch_llm(monkeypatch) -> None:
    """mock LLM 返回 2 条事实(含说话人 张真 / 顾源源)。"""
    payload = {
        "extracted_facts": [
            {
                "subject_text": "心盛计划", "attribute": "状态", "value_text": "推进升级",
                "content_role": "decision", "layer": "L3",
                "evidence_text": "张真说要推进心盛计划升级。",
                "time_anchor": None, "speaker_person_id": "张真", "confidence": 0.9,
                "reasoning_steps": ["纪要明确张真表态推进升级"],
            },
            {
                "subject_text": "顾源源", "attribute": "承诺", "value_text": "下周给升级方案",
                "content_role": "commitment", "layer": "L8",
                "evidence_text": "顾源源承诺下周给出升级方案。",
                "time_anchor": None, "speaker_person_id": "顾源源", "confidence": 0.88,
                "reasoning_steps": ["纪要明确顾源源承诺交付"],
            },
        ],
        "skipped_general_count": 0,
        "extraction_summary": "抽出 2 条事实",
    }
    result = MagicMock()
    result.ok = True
    result.payload = payload
    result.error = None
    monkeypatch.setattr(intelligence_ai_runner, "generate_intelligence_json", lambda *a, **kw: result)


def test_runner_missing_doc_raises(tmp_path):
    db = _db(tmp_path)
    with pytest.raises(RuntimeError):
        fact_extract_runner.process(db, MagicMock(), {"payload_json": "{}"})


def test_runner_writes_facts_and_resolves_speaker(tmp_path, monkeypatch):
    """★核心: runner 真抽取 → atomic_facts + speaker_entity_id 解析(Phase0 通电)。"""
    db = _db(tmp_path)
    doc_id = _v2doc(db)
    _patch_llm(monkeypatch)

    task = {
        "knowledge_document_id": "",
        "client_id": "c_rici",
        "payload_json": f'{{"source_v2_document_id":"{doc_id}","source_client_id":"c_rici"}}',
    }
    result = fact_extract_runner.process(db, MagicMock(), task)

    assert result["factsWritten"] == 2, result
    rows = db.conn.execute(
        "SELECT speaker_person_id, speaker_entity_id FROM atomic_facts WHERE client_id='c_rici'"
    ).fetchall()
    assert len(rows) == 2
    # Phase0 通电: 两条都有说话人 → speaker_entity_id 全部被解析(改前永远 NULL)
    assert all(r["speaker_entity_id"] for r in rows), "speaker_entity_id 应被自动解析"
    # 顾源源(益语)解析到 mirror_user internal;张真(客户方)落本地 entity(unknown)
    gu_fact = db.conn.execute(
        "SELECT speaker_entity_id FROM atomic_facts WHERE client_id='c_rici' AND speaker_person_id='顾源源'"
    ).fetchone()
    gu_ent = db.conn.execute(
        "SELECT resolved_kind, mirror_user_id FROM entities WHERE id=?", (gu_fact["speaker_entity_id"],)
    ).fetchone()
    assert gu_ent["resolved_kind"] == "internal"
    assert gu_ent["mirror_user_id"] == "u_gu"


def test_router_auto_enqueues_fact_extract_and_idempotent(tmp_path):
    db = _db(tmp_path)
    doc_id = _v2doc(db)
    first = route_document_for_local_inference(db, doc_id)
    assert first.get("factExtract") == 1, first
    # 幂等: 再调一次不重复入队
    second = route_document_for_local_inference(db, doc_id)
    assert second.get("factExtract") == 0
    cnt = db.conn.execute(
        "SELECT COUNT(*) FROM local_model_tasks WHERE task_type='fact_extract' AND client_id='c_rici'"
    ).fetchone()[0]
    assert cnt == 1


def test_worker_dispatches_fact_extract(tmp_path, monkeypatch):
    """worker run_due 按 task_type 派发到 fact_extract_runner。"""
    db = _db(tmp_path)
    doc_id = _v2doc(db)
    route_document_for_local_inference(db, doc_id)  # 入队一条 fact_extract

    called = {"n": 0}

    def _fake_process(db_, ai_, task_):
        called["n"] += 1
        return {"factsWritten": 0, "stub": True}

    monkeypatch.setattr(fact_extract_runner, "process", _fake_process)
    # 绕过夜间窗口 + 硬件门控
    monkeypatch.setattr(lmo, "is_within_run_window", lambda *a, **kw: True)
    monkeypatch.setattr(lmo, "_governor_check", lambda *a, **kw: lmo.Decision(verdict="go", reason="", retry_after_seconds=0))

    stats = lmo.run_due_local_model_tasks(db, MagicMock(), force=True, batch_size=5)
    assert called["n"] >= 1, stats
    done = db.conn.execute(
        "SELECT status FROM local_model_tasks WHERE task_type='fact_extract'"
    ).fetchone()
    assert done["status"] == "completed"
