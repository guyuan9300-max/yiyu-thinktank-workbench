"""client_strategic_pulse 服务测试 - 战略陪伴克制版主页数据源."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.services.client_strategic_pulse import (
    _compute_urgency,
    _infer_impact,
    _is_test_quote,
    compute_strategic_pulse,
)


# --- 工具函数测试 ---


class TestIsTestQuote:
    def test_empty_quote_is_test(self) -> None:
        assert _is_test_quote("") is True
        assert _is_test_quote("   ") is True

    def test_too_short_is_test(self) -> None:
        assert _is_test_quote("abc") is True

    def test_jpeg_attachment_marker_is_test(self) -> None:
        assert _is_test_quote("xyz.jpeg 已进入项目资料层") is True
        assert _is_test_quote(
            "abc.jpeg 已作为任务附件进入项目资料库，可用于后续检索、问答与事件线证据引用。"
        ) is True

    def test_smoke_test_prefix_is_test(self) -> None:
        assert _is_test_quote("smoke test content") is True
        assert _is_test_quote("test_attachment something") is True
        assert _is_test_quote("attachment smoke content") is True

    def test_real_business_quote_not_test(self) -> None:
        assert _is_test_quote("老师乙上周从A组织离职") is False
        assert _is_test_quote("负责人甲承诺 5/1 前发更新价值观") is False


class TestComputeUrgency:
    def test_empty_due_returns_later(self) -> None:
        date_iso, days, urgency = _compute_urgency("", datetime(2026, 5, 15).date())
        assert date_iso is None
        assert days is None
        assert urgency == "later"

    def test_invalid_date_returns_later(self) -> None:
        date_iso, days, urgency = _compute_urgency("invalid", datetime(2026, 5, 15).date())
        assert urgency == "later"
        assert days is None

    def test_overdue(self) -> None:
        date_iso, days, urgency = _compute_urgency("2026-05-10", datetime(2026, 5, 15).date())
        assert date_iso == "2026-05-10"
        assert days == -5
        assert urgency == "overdue"

    def test_today(self) -> None:
        date_iso, days, urgency = _compute_urgency("2026-05-15", datetime(2026, 5, 15).date())
        assert days == 0
        assert urgency == "today"

    def test_this_week(self) -> None:
        date_iso, days, urgency = _compute_urgency("2026-05-20", datetime(2026, 5, 15).date())
        assert days == 5
        assert urgency == "this_week"

    def test_later(self) -> None:
        date_iso, days, urgency = _compute_urgency("2026-06-01", datetime(2026, 5, 15).date())
        assert urgency == "later"
        assert days == 17

    def test_with_time_component(self) -> None:
        """支持 ISO datetime 输入 (含 T)."""
        date_iso, days, urgency = _compute_urgency(
            "2026-05-24T10:00:00", datetime(2026, 5, 15).date()
        )
        assert date_iso == "2026-05-24"
        assert days == 9
        assert urgency == "later"


class TestInferImpact:
    def test_polarity_advance(self) -> None:
        assert _infer_impact("advance", "", "") == "advance"

    def test_polarity_block(self) -> None:
        assert _infer_impact("block", "", "") == "block"

    def test_block_keyword(self) -> None:
        assert _infer_impact("neutral", "老师乙离职导致项目停滞", "") == "block"
        assert _infer_impact("neutral", "", "工作卡住") == "block"

    def test_advance_keyword(self) -> None:
        assert _infer_impact("neutral", "项目签约完成", "") == "advance"

    def test_neutral_default(self) -> None:
        assert _infer_impact("neutral", "今天开会讨论", "") == "neutral"


# --- 端到端 (in-memory SQLite) ---


@pytest.fixture()
def db() -> sqlite3.Connection:
    """构造一个最小 in-memory SQLite, 含本服务需要的表."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript(
        """
        CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE evidence_cards (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            source_type TEXT,
            source_id TEXT,
            normalized_claim TEXT,
            quote TEXT,
            polarity TEXT,
            time_anchor TEXT,
            updated_at TEXT
        );

        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            title TEXT,
            status TEXT,
            kind TEXT,
            due_date TEXT,
            deadline_at TEXT,
            event_line_id TEXT
        );

        CREATE TABLE event_lines (
            id TEXT PRIMARY KEY,
            primary_client_id TEXT,
            name TEXT,
            status TEXT,
            closed_at TEXT,
            current_blocker TEXT,
            next_step TEXT,
            updated_at TEXT
        );

        CREATE TABLE event_line_activities (
            id TEXT PRIMARY KEY,
            event_line_id TEXT,
            happened_at TEXT
        );

        INSERT INTO clients(id, name) VALUES ('c1', 'A组织');
        """
    )
    conn.commit()
    return conn


def test_empty_client_returns_empty_sections(db: sqlite3.Connection) -> None:
    """无任何数据时返回空 lists, 不抛错."""
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    result = compute_strategic_pulse(db, "c1", now=now)
    assert result["clientId"] == "c1"
    assert result["weeklyEvents"] == []
    assert result["upcomingTodos"] == []
    assert result["currentBlockers"] == []


def test_test_quotes_filtered_out(db: sqlite3.Connection) -> None:
    """测试垃圾 evidence 被过滤; 真业务 evidence 保留."""
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    db.executescript(
        f"""
        INSERT INTO evidence_cards (id, client_id, source_type, normalized_claim, quote, polarity, updated_at) VALUES
            ('e1', 'c1', 'meeting', '老师乙上周从A组织离职', '老师乙上周从A组织离职', 'neutral', '2026-05-12T10:00:00'),
            ('e2', 'c1', 'task', 'smoke_att.txt 已进入项目资料层', 'smoke_att.txt 已进入项目资料层', 'neutral', '2026-05-13T10:00:00');
        """
    )
    db.commit()
    result = compute_strategic_pulse(db, "c1", now=now)
    titles = [e["title"] for e in result["weeklyEvents"]]
    assert "老师乙上周从A组织离职" in titles
    assert all("smoke" not in t.lower() for t in titles)


def test_overdue_tasks_appear_in_todos(db: sqlite3.Connection) -> None:
    """逾期 task 应在 upcomingTodos 中且 urgency=overdue."""
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    db.executescript(
        """
        INSERT INTO tasks (id, client_id, title, status, kind, due_date) VALUES
            ('t1', 'c1', '给詹瑶发价值观', 'todo', 'task', '2026-05-01'),
            ('t2', 'c1', '已完成任务', 'done', 'task', '2026-05-10');
        """
    )
    db.commit()
    result = compute_strategic_pulse(db, "c1", now=now)
    todos = result["upcomingTodos"]
    assert len(todos) == 1
    assert todos[0]["title"] == "给詹瑶发价值观"
    assert todos[0]["urgency"] == "overdue"
    assert todos[0]["daysUntilDue"] == -14


def test_stuck_event_line_appears_in_blockers(db: sqlite3.Connection) -> None:
    """30+ 天无活动的 active event_line 应出现在 currentBlockers."""
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    db.executescript(
        """
        INSERT INTO event_lines (id, primary_client_id, name, status, updated_at) VALUES
            ('el1', 'c1', '机构介绍升级', 'active', '2026-03-22T10:00:00');
        """
    )
    db.commit()
    result = compute_strategic_pulse(db, "c1", now=now)
    blockers = result["currentBlockers"]
    assert len(blockers) == 1
    assert blockers[0]["title"] == "机构介绍升级"
    assert blockers[0]["stuckDays"] >= 30


def test_dirty_eline_name_skipped(db: sqlite3.Connection) -> None:
    """name 字段是脏数据 (即 id) 时跳过."""
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    db.executescript(
        """
        INSERT INTO event_lines (id, primary_client_id, name, status, updated_at) VALUES
            ('el1', 'c1', 'eline_dirty_id', 'active', '2026-03-22T10:00:00');
        """
    )
    db.commit()
    result = compute_strategic_pulse(db, "c1", now=now)
    assert result["currentBlockers"] == []


def test_template_blocker_treated_as_no_real_reason(db: sqlite3.Connection) -> None:
    """current_blocker 是模板废话 (含'当前没有特别突出') 不视为真 blocker, 仅看停滞天数."""
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    db.executescript(
        """
        INSERT INTO event_lines (id, primary_client_id, name, status, current_blocker, updated_at) VALUES
            ('el_recent', 'c1', '最近活跃主线', 'active',
             '当前没有特别突出的阻塞，但仍需盯住推进收束。', '2026-05-10T10:00:00'),
            ('el_stuck', 'c1', '长期停滞主线', 'active',
             '当前没有特别突出的阻塞', '2026-03-01T10:00:00');
        """
    )
    db.commit()
    result = compute_strategic_pulse(db, "c1", now=now)
    blocker_titles = [b["title"] for b in result["currentBlockers"]]
    # 最近活跃的不应出现 (template blocker 不算 + 未停滞)
    assert "最近活跃主线" not in blocker_titles
    # 长期停滞的应出现 (因停滞 70+ 天)
    assert "长期停滞主线" in blocker_titles
    # reason 应该用兜底文案而不是模板废话
    stuck_blocker = next(b for b in result["currentBlockers"] if b["title"] == "长期停滞主线")
    assert "主线" in stuck_blocker["reason"] and "无活动" in stuck_blocker["reason"]


def test_todos_sorted_by_urgency(db: sqlite3.Connection) -> None:
    """todos 按紧迫度排: overdue > today > this_week > later."""
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    db.executescript(
        """
        INSERT INTO tasks (id, client_id, title, status, kind, due_date) VALUES
            ('t_later', 'c1', 'later task', 'todo', 'task', '2026-06-15'),
            ('t_today', 'c1', 'today task', 'todo', 'task', '2026-05-15'),
            ('t_overdue', 'c1', 'overdue task', 'todo', 'task', '2026-05-01'),
            ('t_thisweek', 'c1', 'this week task', 'todo', 'task', '2026-05-20');
        """
    )
    db.commit()
    result = compute_strategic_pulse(db, "c1", now=now)
    titles = [t["title"] for t in result["upcomingTodos"]]
    assert titles == ["overdue task", "today task", "this week task", "later task"]


def test_camelcase_fields(db: sqlite3.Connection) -> None:
    """response 必须用 camelCase 给前端."""
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    result = compute_strategic_pulse(db, "c1", now=now)
    # 顶层
    assert "weeklyEvents" in result
    assert "upcomingTodos" in result
    assert "currentBlockers" in result
    assert "weekStart" in result
    assert "weekEnd" in result
    assert "generatedAt" in result
    assert "clientId" in result
