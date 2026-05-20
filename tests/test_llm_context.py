"""W2-B 验证 · LLM Context 三件套(composer / logger / inspector)

跑法:
    backend/.venv/bin/python3 -m pytest tests/test_llm_context.py -v

设计:
- compose narrative intent → 验证 prompt 装配出 client + events + tasks
- log_prompt 写入 → inspector 能查回来
- compose 失败(client 不存在 / frozen)→ 返回 stub,不崩
- token 估算 + truncated 标记
- log 失败不阻塞主流程
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Database  # noqa: E402
from app.llm_context import (  # noqa: E402
    LLMContext,
    PromptLogEntry,
    ContextComposer,
    ContextInspector,
    PromptLogger,
    compose_context,
    log_prompt,
    inspect_recent_prompts,
)


# ── Fixtures ──


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.conn.execute("PRAGMA foreign_keys=OFF")
    return db


@pytest.fixture
def db_with_client(db: Database) -> Database:
    """seed 1 active client + 1 event + 2 tasks"""
    now = "2026-05-20T10:00:00"
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at, frozen_at)
           VALUES('client_a', '客户A', '阿', '项目', '项目', '介绍', '推进中', '#5B7BFE',
                  ?, ?, NULL)""",
        (now, now),
    )
    db.conn.execute(
        """INSERT INTO event_lines(id, name, kind, status, primary_client_id, stage,
                                   summary, next_step, created_at, updated_at)
           VALUES('el_1', '签约推进', 'custom', 'active', 'client_a',
                  '商务谈判', '本周已完成合同初稿', '下周客户确认',
                  ?, ?)""",
        (now, now),
    )
    # task_lists
    db.conn.execute(
        """INSERT INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope)
           VALUES('list_default', '', 'def', '#5B7BFE', 0, 1, 'org')"""
    )
    db.conn.executemany(
        """INSERT INTO tasks(id, title, description, status, priority, list_id,
                             owner_name, ddl, source_type, tags_json,
                             created_at, updated_at, client_id)
           VALUES(?, ?, '', 'todo', 'high', 'list_default', '', '2026-05-25',
                  'manual', '[]', ?, ?, 'client_a')""",
        [
            ("t_1", "整理材料", now, now),
            ("t_2", "对接客户", now, now),
        ],
    )
    db.conn.commit()
    return db


@pytest.fixture
def db_with_frozen_client(db: Database) -> Database:
    now = "2026-05-20T10:00:00"
    db.conn.execute(
        """INSERT INTO clients(id, name, alias, domain, type, intro, stage, color,
                               created_at, updated_at, frozen_at)
           VALUES('client_frozen', 'Frozen客户', '', '项目', '项目', '', '已冻结',
                  '#999', ?, ?, '2026-05-19')""",
        (now, now),
    )
    db.conn.commit()
    return db


# ── schema 验证 ──


@pytest.mark.integration
def test_prompt_log_table_created(db: Database):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prompt_log'"
    ).fetchall()
    assert len(rows) == 1


@pytest.mark.integration
def test_prompt_log_indexes_exist(db: Database):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_prompt_log_%'"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert "idx_prompt_log_intent_created" in names
    assert "idx_prompt_log_client_created" in names
    assert "idx_prompt_log_user_created" in names


# ── ContextComposer ──


@pytest.mark.integration
def test_compose_narrative_returns_llm_context(db_with_client: Database):
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    assert isinstance(ctx, LLMContext)
    assert ctx.intent == "narrative"
    assert ctx.client_id == "client_a"
    assert "客户A" in ctx.prompt_text
    assert "client_header" in ctx.sections_included


@pytest.mark.integration
def test_compose_narrative_includes_active_events(db_with_client: Database):
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    assert "签约推进" in ctx.prompt_text
    assert "active_events" in ctx.sections_included


@pytest.mark.integration
def test_compose_narrative_includes_pending_tasks(db_with_client: Database):
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    assert "整理材料" in ctx.prompt_text
    assert "pending_tasks" in ctx.sections_included


@pytest.mark.integration
def test_compose_narrative_excludes_frozen_client(db_with_frozen_client: Database):
    """frozen client 不应能装出 narrative(走 v_active_clients 守卫)"""
    ctx = compose_context(db_with_frozen_client, intent="narrative", client_id="client_frozen")
    assert ctx.sections_included == ()  # 空,因为 v_active_clients 排除了
    assert ctx.prompt_text == ""


@pytest.mark.integration
def test_compose_narrative_without_client_id_returns_stub(db: Database):
    ctx = compose_context(db, intent="narrative", client_id=None)
    assert ctx.sections_included == ()


@pytest.mark.integration
def test_compose_unimplemented_intent_returns_stub(db: Database):
    ctx = compose_context(db, intent="qa", client_id="client_a")
    assert ctx.intent == "qa"
    assert ctx.sections_included == ()


@pytest.mark.integration
def test_compose_truncates_when_token_estimate_exceeds(db_with_client: Database):
    """max_tokens 极小时应触发 truncated"""
    ctx = compose_context(
        db_with_client, intent="narrative", client_id="client_a", max_tokens=10,
    )
    assert ctx.truncated is True
    # 装载列表里 pending_tasks 应被裁掉
    assert "pending_tasks" not in ctx.sections_included


@pytest.mark.integration
def test_compose_token_estimate_is_positive(db_with_client: Database):
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    assert ctx.token_estimate > 0


# ── PromptLogger ──


@pytest.mark.integration
def test_log_prompt_writes_row(db_with_client: Database):
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    log_id = log_prompt(
        db_with_client,
        context=ctx,
        output_text="生成的叙事内容",
        duration_ms=1234.5,
        tokens_used=512,
        model_id="qwen3-vl:32b",
    )
    assert log_id is not None and log_id.startswith("plog_")
    row = db_with_client.fetchone("SELECT * FROM prompt_log WHERE id = ?", (log_id,))
    assert row["intent"] == "narrative"
    assert row["client_id"] == "client_a"
    assert row["output_text"] == "生成的叙事内容"
    assert row["model_id"] == "qwen3-vl:32b"
    assert row["error"] == ""


@pytest.mark.integration
def test_log_prompt_records_failure(db_with_client: Database):
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    log_id = log_prompt(
        db_with_client, context=ctx, output_text="",
        error="rate limit exceeded", duration_ms=200,
    )
    row = db_with_client.fetchone("SELECT * FROM prompt_log WHERE id = ?", (log_id,))
    assert "rate limit" in row["error"]


@pytest.mark.integration
def test_log_prompt_does_not_raise_on_db_failure(db_with_client: Database):
    """db 出错时 log 静默失败,不阻塞主流程"""
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    db_with_client.conn.close()  # 故意关闭 connection
    # 应该返回 None,不抛
    result = log_prompt(db_with_client, context=ctx, output_text="x")
    assert result is None


@pytest.mark.integration
def test_logger_update_score(db_with_client: Database):
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    log_id = log_prompt(db_with_client, context=ctx, output_text="out")
    logger = PromptLogger(db_with_client)
    assert logger.update_score(log_id, score=0.8, note="不错") is True
    row = db_with_client.fetchone("SELECT score, score_note FROM prompt_log WHERE id = ?", (log_id,))
    assert row["score"] == 0.8
    assert row["score_note"] == "不错"


# ── ContextInspector ──


@pytest.mark.integration
def test_inspector_last_n(db_with_client: Database):
    """写入 3 条 → last_n(2) 返回最近 2 条"""
    for i in range(3):
        ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
        log_prompt(db_with_client, context=ctx, output_text=f"out_{i}", duration_ms=float(i))
    insp = ContextInspector(db_with_client)
    recent = insp.last_n(2)
    assert len(recent) == 2
    assert all(isinstance(e, PromptLogEntry) for e in recent)


@pytest.mark.integration
def test_inspector_for_client(db_with_client: Database):
    ctx_a = compose_context(db_with_client, intent="narrative", client_id="client_a")
    log_prompt(db_with_client, context=ctx_a, output_text="a")

    # 另一个 client(不存在,装不出 narrative,但用 test_intent 装空 prompt)
    ctx_b = compose_context(db_with_client, intent="test_intent", client_id="client_b")
    log_prompt(db_with_client, context=ctx_b, output_text="b")

    insp = ContextInspector(db_with_client)
    a_logs = insp.for_client("client_a")
    assert len(a_logs) == 1 and a_logs[0].output_text == "a"
    b_logs = insp.for_client("client_b")
    assert len(b_logs) == 1 and b_logs[0].output_text == "b"


@pytest.mark.integration
def test_inspector_by_intent(db_with_client: Database):
    ctx1 = compose_context(db_with_client, intent="narrative", client_id="client_a")
    log_prompt(db_with_client, context=ctx1, output_text="n1")
    ctx2 = compose_context(db_with_client, intent="test_intent", client_id="client_a")
    log_prompt(db_with_client, context=ctx2, output_text="t1")
    insp = ContextInspector(db_with_client)
    assert len(insp.by_intent("narrative")) == 1
    assert len(insp.by_intent("test_intent")) == 1


@pytest.mark.integration
def test_inspector_recent_failures(db_with_client: Database):
    ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
    log_prompt(db_with_client, context=ctx, output_text="ok")
    log_prompt(db_with_client, context=ctx, output_text="", error="boom!")
    insp = ContextInspector(db_with_client)
    failures = insp.recent_failures()
    assert len(failures) == 1
    assert "boom" in failures[0].error


@pytest.mark.integration
def test_inspector_stats_by_intent(db_with_client: Database):
    for _ in range(3):
        ctx = compose_context(db_with_client, intent="narrative", client_id="client_a")
        log_prompt(db_with_client, context=ctx, output_text="x", duration_ms=100, tokens_used=50)
    insp = ContextInspector(db_with_client)
    stats = insp.stats_by_intent()
    assert len(stats) == 1
    assert stats[0]["intent"] == "narrative"
    assert stats[0]["total"] == 3
    assert stats[0]["avg_ms"] == 100.0
    assert stats[0]["avg_tokens"] == 50.0


@pytest.mark.integration
def test_inspector_last_for_client_with_intent(db_with_client: Database):
    ctx_n = compose_context(db_with_client, intent="narrative", client_id="client_a")
    log_prompt(db_with_client, context=ctx_n, output_text="narrative_out")
    ctx_t = compose_context(db_with_client, intent="test_intent", client_id="client_a")
    log_prompt(db_with_client, context=ctx_t, output_text="test_out")
    insp = ContextInspector(db_with_client)
    entry = insp.last_for_client("client_a", intent="narrative")
    assert entry is not None and entry.output_text == "narrative_out"


@pytest.mark.unit
def test_llm_context_dataclass_frozen():
    from dataclasses import FrozenInstanceError
    ctx = LLMContext(
        intent="test_intent", client_id=None, user_id=None,
        system_text="", prompt_text="", sections_included=(),
        token_estimate=0, truncated=False, composed_at="2026-05-20",
    )
    with pytest.raises(FrozenInstanceError):
        ctx.intent = "qa"  # type: ignore[misc]
