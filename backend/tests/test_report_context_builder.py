"""R1 · report_context_builder 单测。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.db import Database
from app.services.report_context_builder import (
    ReportPromptContext,
    build_report_prompt_context,
)


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _seed_client(db: Database, *, client_id: str = "client-1") -> str:
    now = _now_iso()
    db.execute(
        "INSERT INTO clients (id, name, alias, domain, type, intro, stage, "
        "color, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            client_id,
            "上海A组织",
            "A组织",
            "公益",
            "ngo",
            "致力于青少年心理健康与社会情感学习",
            "深度合作",
            "#5B7BFE",
            now,
            now,
        ),
    )
    return client_id


def _seed_event_line(
    db: Database,
    *,
    event_line_id: str = "el-1",
    client_id: str = "client-1",
    name: str = "A组织战略陪伴 Q1",
) -> str:
    now = _now_iso()
    db.execute(
        """
        INSERT INTO event_lines (
            id, organization_id, name, kind, status, business_category,
            stage, summary, intent, current_blocker, recent_decision,
            next_step, owner_name, primary_client_id, primary_client_name,
            participant_ids_json, created_at, updated_at
        ) VALUES (?, '', ?, 'strategic_partnership', 'active', '战略陪伴',
                  '执行中', '战略陪伴季度复盘', '帮助A组织梳理 Q1 关键成果',
                  '组织内部对齐尚需推进', 'CEO 决定 Q2 加大投入',
                  '完成 Q1 报告', '管理员甲', ?, 'A组织', '[]', ?, ?)
        """,
        (event_line_id, name, client_id, now, now),
    )
    return event_line_id


def _seed_activity(
    db: Database,
    *,
    activity_id: str,
    event_line_id: str,
    happened_at: str,
    title: str,
    summary: str = "",
    actor: str = "张三",
    source: str = "meeting",
    is_key: bool = False,
) -> None:
    db.execute(
        """
        INSERT INTO event_line_activities (
            id, event_line_id, source_type, source_id, happened_at,
            actor_name, title, summary, metadata_json, is_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
        """,
        (
            activity_id,
            event_line_id,
            source,
            f"src-{activity_id}",
            happened_at,
            actor,
            title,
            summary,
            1 if is_key else 0,
            happened_at,
        ),
    )


def _make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return _make_db(tmp_path)


@pytest.mark.unit
def test_basic_context_with_event_line(db: Database) -> None:
    _seed_client(db)
    _seed_event_line(db)
    _seed_activity(
        db,
        activity_id="a1",
        event_line_id="el-1",
        happened_at="2026-01-10T09:00:00Z",
        title="启动会",
        summary="确定 Q1 三大主题",
        is_key=True,
    )
    _seed_activity(
        db,
        activity_id="a2",
        event_line_id="el-1",
        happened_at="2026-02-15T14:00:00Z",
        title="中期检视",
        summary="进度过半",
    )

    ctx = build_report_prompt_context(
        db,
        client_id="client-1",
        event_line_id="el-1",
        period_start="2026-01-01",
        period_end="2026-03-31",
        intent_hint="给客户的季度报告",
    )

    assert isinstance(ctx, ReportPromptContext)
    assert ctx.client_id == "client-1"
    assert ctx.client_name == "上海A组织"
    assert ctx.event_line_name == "A组织战略陪伴 Q1"
    assert ctx.event_line_business_category == "战略陪伴"
    assert ctx.event_line_current_blocker == "组织内部对齐尚需推进"
    assert len(ctx.entries) == 2
    assert ctx.entries[0]["title"] == "启动会"
    assert ctx.entries[0]["is_key"] is True
    assert ctx.entries[1]["title"] == "中期检视"
    assert ctx.entries_truncated is False
    assert ctx.total_activities == 2
    assert ctx.intent_hint == "给客户的季度报告"


@pytest.mark.unit
def test_render_for_prompt_contains_key_sections(db: Database) -> None:
    _seed_client(db)
    _seed_event_line(db)
    _seed_activity(
        db,
        activity_id="a1",
        event_line_id="el-1",
        happened_at="2026-01-10T09:00:00Z",
        title="启动会",
    )

    ctx = build_report_prompt_context(
        db,
        client_id="client-1",
        event_line_id="el-1",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )
    rendered = ctx.render_for_prompt()

    assert "# 客户信息" in rendered
    assert "上海A组织" in rendered
    assert "# 报告期间与意图" in rendered
    assert "2026-01-01 ~ 2026-03-31" in rendered
    assert "# 事件线" in rendered
    assert "A组织战略陪伴 Q1" in rendered
    assert "# 时间线条目" in rendered
    assert "启动会" in rendered


@pytest.mark.unit
def test_no_event_line(db: Database) -> None:
    _seed_client(db)
    ctx = build_report_prompt_context(db, client_id="client-1")
    assert ctx.event_line_id == ""
    assert ctx.entries == ()
    assert ctx.total_activities == 0
    rendered = ctx.render_for_prompt()
    assert "# 事件线" not in rendered
    assert "（本期间无活动记录）" in rendered


@pytest.mark.unit
def test_missing_client_raises(db: Database) -> None:
    with pytest.raises(ValueError, match="客户不存在"):
        build_report_prompt_context(db, client_id="nonexistent")


@pytest.mark.unit
def test_missing_event_line_raises(db: Database) -> None:
    _seed_client(db)
    with pytest.raises(ValueError, match="事件线不存在"):
        build_report_prompt_context(
            db, client_id="client-1", event_line_id="nope"
        )


@pytest.mark.unit
def test_empty_client_id_raises(db: Database) -> None:
    with pytest.raises(ValueError, match="client_id"):
        build_report_prompt_context(db, client_id="")


@pytest.mark.unit
def test_entries_truncated(db: Database) -> None:
    _seed_client(db)
    _seed_event_line(db)
    base = datetime(2026, 1, 1)
    for i in range(50):
        when = base + timedelta(days=i)
        _seed_activity(
            db,
            activity_id=f"a{i:02d}",
            event_line_id="el-1",
            happened_at=when.isoformat(timespec="seconds") + "Z",
            title=f"活动 {i}",
        )

    ctx = build_report_prompt_context(
        db, client_id="client-1", event_line_id="el-1", max_entries=10
    )

    assert ctx.total_activities == 50
    assert len(ctx.entries) == 10
    assert ctx.entries_truncated is True
    # 应该保留最近 10 条（即 idx 40-49）
    assert ctx.entries[0]["title"] == "活动 40"
    assert ctx.entries[-1]["title"] == "活动 49"


@pytest.mark.unit
def test_period_filter(db: Database) -> None:
    _seed_client(db)
    _seed_event_line(db)
    _seed_activity(
        db,
        activity_id="a1",
        event_line_id="el-1",
        happened_at="2025-12-15T09:00:00Z",
        title="期前事件",
    )
    _seed_activity(
        db,
        activity_id="a2",
        event_line_id="el-1",
        happened_at="2026-02-10T09:00:00Z",
        title="期内事件",
    )
    _seed_activity(
        db,
        activity_id="a3",
        event_line_id="el-1",
        happened_at="2026-04-01T09:00:00Z",
        title="期后事件",
    )

    ctx = build_report_prompt_context(
        db,
        client_id="client-1",
        event_line_id="el-1",
        period_start="2026-01-01",
        period_end="2026-03-31",
    )

    assert ctx.total_activities == 1
    assert len(ctx.entries) == 1
    assert ctx.entries[0]["title"] == "期内事件"


@pytest.mark.unit
def test_long_summary_truncated(db: Database) -> None:
    _seed_client(db)
    _seed_event_line(db)
    long_text = "细节" * 200  # 400 字符
    _seed_activity(
        db,
        activity_id="a1",
        event_line_id="el-1",
        happened_at="2026-01-10T09:00:00Z",
        title="周会",
        summary=long_text,
    )

    ctx = build_report_prompt_context(
        db,
        client_id="client-1",
        event_line_id="el-1",
        activity_summary_chars=20,
    )

    summary = ctx.entries[0]["summary"]
    assert len(summary) == 21  # 20 + "…"
    assert summary.endswith("…")


@pytest.mark.unit
def test_org_notebook_parsed(db: Database) -> None:
    _seed_client(db)
    now = _now_iso()
    db.execute(
        """
        INSERT INTO organization_notebook_snapshots (
            id, client_id, organization_intro, collaboration_relationship,
            current_stage, business_modules_json, key_people_json,
            current_challenges_json, collaboration_goals_json,
            confidence, created_at, updated_at
        ) VALUES (?, 'client-1', '关注青少年心理', '战略陪伴', '稳步推进',
                  ?, ?, ?, ?, 0.8, ?, ?)
        """,
        (
            "snap-1",
            json.dumps(["心理课程", "社会情感学习", {"name": "公益运营"}]),
            json.dumps(
                [
                    {"name": "李四", "role": "CEO"},
                    {"name": "王五", "title": "项目主管"},
                ]
            ),
            json.dumps(["资金紧张", {"text": "城市覆盖有限"}]),
            json.dumps([{"title": "扩大影响力"}, "完善评估体系"]),
            now,
            now,
        ),
    )

    ctx = build_report_prompt_context(db, client_id="client-1")
    assert "心理课程" in ctx.org_business_modules
    assert "社会情感学习" in ctx.org_business_modules
    assert "公益运营" in ctx.org_business_modules
    assert len(ctx.org_key_people) == 2
    assert ctx.org_key_people[0] == {"name": "李四", "role": "CEO"}
    assert "资金紧张" in ctx.org_current_challenges
    assert "城市覆盖有限" in ctx.org_current_challenges
    assert "扩大影响力" in ctx.org_collaboration_goals
    assert "完善评估体系" in ctx.org_collaboration_goals
