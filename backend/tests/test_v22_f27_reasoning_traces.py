"""v2.2 F2.7 (N3 A3) · ReasoningTraceStore 测试

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_f27_reasoning_traces.py -v

测试覆盖:
- schema 完整性
- start → complete 完整流程
- fail / revert
- 列表查询 (按 entity / 按 session / 失败列表)
- duration 计算
- N3 关键场景: AI 抽错事实后用户撤销可追溯
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.services.reasoning_trace_store import (  # noqa: E402
    ReasoningTraceStore,
    get_reasoning_trace_store,
)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


@pytest.fixture
def store(db: Database) -> ReasoningTraceStore:
    return ReasoningTraceStore(db)


# ════════════════════════════════════════════════════════════════
# Schema
# ════════════════════════════════════════════════════════════════


def test_reasoning_traces_table_exists(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='reasoning_traces'"
    )
    assert len(rows) == 1


def test_reasoning_traces_columns_complete(db: Database):
    rows = db.fetchall("PRAGMA table_info(reasoning_traces)")
    col_names = {r["name"] for r in rows}
    required = {
        "id", "ai_session_id", "output_entity_type", "output_entity_id",
        "input_doc_ids_json", "input_chunk_ids_json", "input_fact_ids_json",
        "prompt_summary", "prompt_log_id", "model_name", "model_version",
        "reasoning_steps_json", "output_summary",
        "confidence", "triggered_update_relation",
        "started_at", "completed_at", "duration_ms",
        "status", "error_message",
    }
    missing = required - col_names
    assert not missing, f"missing: {missing}"


def test_reasoning_traces_indexes(db: Database):
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='reasoning_traces'"
    )
    idx_names = {r["name"] for r in rows if not r["name"].startswith("sqlite_")}
    assert "idx_reasoning_traces_session" in idx_names
    assert "idx_reasoning_traces_output_entity" in idx_names
    assert "idx_reasoning_traces_status" in idx_names


# ════════════════════════════════════════════════════════════════
# start / complete 完整流程
# ════════════════════════════════════════════════════════════════


def test_start_returns_trace_id(store: ReasoningTraceStore):
    trace_id = store.start(
        ai_session_id="ai_sess_001",
        output_entity_type="atomic_fact",
        prompt_summary="抽取负责人甲角色",
        model_name="doubao-seed",
    )
    assert trace_id.startswith("rt_")
    assert len(trace_id) == 15  # 'rt_' + 12 hex


def test_start_creates_pending_trace(store: ReasoningTraceStore, db: Database):
    trace_id = store.start(
        ai_session_id="ai_sess_001",
        output_entity_type="atomic_fact",
        input_doc_ids=["doc_519"],
        input_chunk_ids=["chunk_3", "chunk_5"],
        prompt_summary="LLM extract 负责人甲接任法人代表",
        model_name="doubao-seed",
        model_version="2.0",
    )
    db.conn.commit()
    trace = store.get(trace_id)
    assert trace is not None
    assert trace.status == "pending"
    assert trace.ai_session_id == "ai_sess_001"
    assert trace.input_doc_ids == ["doc_519"]
    assert trace.input_chunk_ids == ["chunk_3", "chunk_5"]
    assert trace.model_name == "doubao-seed"
    assert trace.output_entity_id is None  # 还没回填
    assert trace.completed_at is None


def test_complete_fills_output_and_reasoning(store: ReasoningTraceStore, db: Database):
    """完整流程: start → complete → 推理链 + 输出 entity id 都回填"""
    trace_id = store.start(
        ai_session_id="ai_sess_001",
        output_entity_type="atomic_fact",
        prompt_summary="抽负责人甲角色",
    )
    store.complete(
        trace_id,
        output_entity_id="af_abc123",
        reasoning_steps=[
            "段落 3 说'负责人甲接任法人代表'",
            "段落 5 确认'5/19 决议生效'",
            "结论: 负责人甲.角色 = 法人代表",
        ],
        output_summary="负责人甲接任A组织法人代表",
        confidence=0.92,
        triggered_update_relation="supersedes",
    )
    db.conn.commit()
    trace = store.get(trace_id)
    assert trace.status == "completed"
    assert trace.output_entity_id == "af_abc123"
    assert len(trace.reasoning_steps) == 3
    assert trace.reasoning_steps[0].startswith("段落 3")
    assert trace.output_summary == "负责人甲接任A组织法人代表"
    assert trace.confidence == 0.92
    assert trace.triggered_update_relation == "supersedes"
    assert trace.completed_at is not None


def test_complete_calculates_duration_ms(store: ReasoningTraceStore, db: Database):
    """duration_ms 自动计算 (从 start 到 complete)"""
    trace_id = store.start(
        ai_session_id="s1", output_entity_type="atomic_fact",
    )
    time.sleep(0.05)  # 50ms
    store.complete(
        trace_id, output_entity_id="x", reasoning_steps=[],
        output_summary="", confidence=0.5,
    )
    db.conn.commit()
    trace = store.get(trace_id)
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 40  # 容忍计时精度


def test_fail_records_error(store: ReasoningTraceStore, db: Database):
    """LLM timeout / parse error → fail() 记录错误"""
    trace_id = store.start(
        ai_session_id="s1", output_entity_type="atomic_fact",
    )
    store.fail(trace_id, error_message="LLM API timeout after 30s")
    db.conn.commit()
    trace = store.get(trace_id)
    assert trace.status == "failed"
    assert "timeout" in trace.error_message
    assert trace.duration_ms is not None  # 失败也记 duration


def test_revert_changes_status(store: ReasoningTraceStore, db: Database):
    """用户撤销 AI 推理 (爱马仕保修)"""
    trace_id = store.start(
        ai_session_id="s1", output_entity_type="atomic_fact",
    )
    store.complete(
        trace_id, output_entity_id="af_wrong", reasoning_steps=[],
        output_summary="", confidence=0.5,
    )
    store.revert(trace_id)
    db.conn.commit()
    trace = store.get(trace_id)
    assert trace.status == "reverted"


# ════════════════════════════════════════════════════════════════
# 查询场景: 用户 UI 上看"AI 怎么推出来的"
# ════════════════════════════════════════════════════════════════


def test_list_for_entity_returns_chain(store: ReasoningTraceStore, db: Database):
    """点击一条 atomic_fact 看它的所有推理痕迹 (可能 N 次, 每次更新都留 trace)"""
    # 同一条 fact af_xyz 有 2 次推理 (一次创建, 一次更新)
    t1 = store.start(ai_session_id="s1", output_entity_type="atomic_fact")
    store.complete(t1, output_entity_id="af_xyz", reasoning_steps=["初次抽取"],
                   output_summary="A组织员工 50 人", confidence=0.7)
    t2 = store.start(ai_session_id="s2", output_entity_type="atomic_fact")
    store.complete(t2, output_entity_id="af_xyz", reasoning_steps=["更新数据"],
                   output_summary="A组织员工 60 人", confidence=0.85,
                   triggered_update_relation="supersedes")
    db.conn.commit()
    traces = store.list_for_entity("atomic_fact", "af_xyz")
    assert len(traces) == 2


def test_list_session_recent_returns_what_ai_did(store: ReasoningTraceStore, db: Database):
    """看一个 AI session 最近做了什么 (类似 git log)"""
    for i in range(5):
        t = store.start(ai_session_id="ai_sess_morning", output_entity_type="atomic_fact")
        store.complete(t, output_entity_id=f"af_{i}", reasoning_steps=[f"step {i}"],
                       output_summary=f"fact {i}", confidence=0.7)
    db.conn.commit()
    traces = store.list_session_recent("ai_sess_morning", limit=3)
    assert len(traces) == 3


def test_list_failed_recent_for_diagnosis(store: ReasoningTraceStore, db: Database):
    """诊断 AI 最近失败的, 看是不是 prompt 有问题"""
    # 3 成功 + 2 失败
    for i in range(3):
        t = store.start(ai_session_id="s1", output_entity_type="atomic_fact")
        store.complete(t, output_entity_id=f"af_{i}", reasoning_steps=[],
                       output_summary="", confidence=0.5)
    for i in range(2):
        t = store.start(ai_session_id="s2", output_entity_type="atomic_fact")
        store.fail(t, error_message=f"timeout {i}")
    db.conn.commit()
    failed = store.list_failed_recent(limit=10)
    assert len(failed) == 2
    assert all(t.status == "failed" for t in failed)


# ════════════════════════════════════════════════════════════════
# N3 关键场景: AI 抽错 → 撤销可追溯
# ════════════════════════════════════════════════════════════════


def test_end_to_end_ai_error_then_user_revert(store: ReasoningTraceStore, db: Database):
    """场景: AI 抽 '负责人甲接任理事长' 但实际是法人代表, 用户改了之后能追溯到 AI 错在哪"""
    # AI 推理
    trace_id = store.start(
        ai_session_id="ai_sess_001",
        output_entity_type="atomic_fact",
        input_doc_ids=["doc_519"],
        input_chunk_ids=["chunk_3"],
        prompt_summary="从 5/19 会议纪要抽人物角色变化",
        model_name="doubao-seed",
    )
    # AI 跑出错误结论
    store.complete(
        trace_id,
        output_entity_id="af_wrong",
        reasoning_steps=[
            "段落 3 包含'负责人甲'和'理事长'",
            "但段落 3 实际说'负责人甲接任法人代表',  AI 误读了上下文",  # 错误推理被记录
            "结论: 负责人甲.角色 = 理事长",
        ],
        output_summary="负责人甲接任理事长 (错误)",
        confidence=0.65,
    )
    db.conn.commit()

    # 用户发现错了, 撤销
    store.revert(trace_id)
    db.conn.commit()

    # 验证: 用户能查到 AI 当时的推理过程
    trace = store.get(trace_id)
    assert trace.status == "reverted"
    assert "误读了上下文" in trace.reasoning_steps[1]
    # AI 自检学习: 这条 trace 是 "AI 错误" 训练样本, 留给 3.0 ai_learned_rules 用


# ════════════════════════════════════════════════════════════════
# factory
# ════════════════════════════════════════════════════════════════


def test_get_reasoning_trace_store_factory(db: Database):
    store = get_reasoning_trace_store(db)
    assert isinstance(store, ReasoningTraceStore)
