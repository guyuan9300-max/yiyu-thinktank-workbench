# 益语软件平台源码导出（第005卷）

- 导出时间: 2026-04-20 18:08:04
- 内容范围: 主仓库源码 + mobile 子仓库源码
- 说明: 每个条目为完整源码文件。

## `backend/tests/test_agent_worklogs.py`

- 编码: `utf-8`

~~~python
from pathlib import Path

from app.db import Database
from app.services.agent_worklogs import (
    AGENT_AUTO_SOURCE_TYPE,
    build_agent_execution_task_activity,
    build_agent_execution_tasks,
    build_agent_weekly_digests,
    build_agent_weekly_plans,
    build_agent_weekly_review_items,
    build_agent_worklog_response,
    sync_agent_execution_tasks,
)


def test_build_agent_worklog_response_reads_db_and_thread_sync(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        ("log_1", "庆华", "review.create", "weekly_review", "review_1", "{}", "2026-03-15T10:00:00"),
    )
    db.execute(
        "INSERT INTO topic_radars(id, title, prompt, time_range, preferred_sources_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
        ("radar_1", "公益行业动态", "关注公益行业变化", "3_days", "[]", "2026-03-01T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO topic_candidates(
            id, radar_id, title, summary, source, source_url, published_at, capture_method, captured_by, status, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "cand_1",
            "radar_1",
            "新增行业情报",
            "一条新的行业情报",
            "公益时报",
            "https://example.com/1",
            "2026-03-15",
            "web_search",
            "大周",
            "tracking",
            "2026-03-15T11:00:00",
            "2026-03-15T11:00:00",
        ),
    )
    db.execute(
        "INSERT INTO tasks(id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("task_1", "推进战略问答整理", "", "doing", "high", "list-0", "庆华", "周五", "manual", None, "[]", "[]", "2026-03-15T09:00:00", "2026-03-15T09:30:00"),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text(
        "\n".join(
            [
                "# Thread Sync",
                "## 2026-03-15 科技发展部线程",
                "- 当前状态：已完成软件系统主线接线。",
                "- 风险点：还需要继续做真实验收。",
            ]
        ),
        encoding="utf-8",
    )

    response = build_agent_worklog_response(
        db=db,
        month_label="2026-03",
        thread_sync_path=thread_sync_path,
    )

    assert response.month == "2026-03"
    assert len(response.worklogs) == 3
    assert {item.agentName for item in response.worklogs} == {"庆华", "大周", "佳乐"}
    assert any(item.agentName == "佳乐" and "软件系统主线接线" in item.summary for item in response.worklogs)
    assert any(item.agentName == "大周" and "新增 1 条情报线索" in item.title for item in response.worklogs)
    assert any(digest.agentName == "庆华" and digest.focusItems for digest in response.weeklyDigests)
    assert any(plan.agentName == "庆华" and plan.planItems for plan in response.weeklyPlans)


def test_monthly_worklog_response_uses_full_week_digest_range(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        ("log_1", "庆华", "task.update", "task", "task_1", "{}", "2026-03-31T09:00:00"),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        ("log_2", "庆华", "review.create", "weekly_review", "review_1", "{}", "2026-04-01T10:00:00"),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    monthly_response = build_agent_worklog_response(
        db=db,
        month_label="2026-03",
        thread_sync_path=thread_sync_path,
    )
    march_digest = next((item for item in monthly_response.weeklyDigests if item.agentName == "庆华" and item.weekLabel == "2026-W14"), None)
    assert march_digest is not None
    assert march_digest.evidenceCount == 2

    weekly_digests = build_agent_weekly_digests(
        db=db,
        week_label="2026-W14",
        thread_sync_path=thread_sync_path,
    )
    assert len(weekly_digests) == 1
    assert weekly_digests[0].agentName == "庆华"
    assert weekly_digests[0].evidenceCount == 2

    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label="2026-W14",
        thread_sync_path=thread_sync_path,
    )
    assert len(weekly_plans) == 1
    assert weekly_plans[0].agentName == "庆华"
    assert weekly_plans[0].planItems
    assert "真实日志推演" in weekly_plans[0].summary


def test_weekly_plans_apply_manual_override(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        ("log_1", "庆华", "task.update", "task", "task_1", "{}", "2026-03-17T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO agent_weekly_plan_overrides(
            id, week_label, agent_key, summary, plan_items_json, updated_by, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "override_1",
            "2026-W12",
            "strategy_design",
            "CEO 手动修订后的战略周计划。",
            '[{"title":"优先校准机构级判断","rationale":"来自 CEO 调整","scheduleHint":"周二前完成","status":"doing"}]',
            "顾源源",
            "2026-03-17T10:00:00",
            "2026-03-17T10:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    qinghua_plan = next(item for item in weekly_plans if item.agentName == "庆华")
    assert qinghua_plan.summary == "CEO 手动修订后的战略周计划。"
    assert qinghua_plan.planItems[0].title == "优先校准机构级判断"
    assert qinghua_plan.planItems[0].status == "doing"
    assert qinghua_plan.sourcePolicy.get("manualOverride") is True


def test_derived_weekly_plan_status_updates_from_real_logs(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text(
        "\n".join(
            [
                "# Thread Sync",
                "## 2026-03-18 科技发展部线程",
                "- 当前状态：已完成软件系统主线接线。",
                "- 风险点：仍需继续做真实验收。",
            ]
        ),
        encoding="utf-8",
    )

    weekly_plans = build_agent_weekly_plans(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    jiale_plan = next(item for item in weekly_plans if item.agentName == "佳乐")
    assert jiale_plan.planItems[0].status in {"done", "blocked"}
    assert jiale_plan.sourcePolicy.get("autoStatus") is True


def test_build_agent_weekly_review_items_turns_robot_work_into_review_samples(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (
            "log_1",
            "庆华",
            "task.update",
            "task",
            "task_1",
            '{"title":"完成战略判断整理"}',
            "2026-03-17T09:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    items = build_agent_weekly_review_items(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    qinghua_item = next(item for item in items if item.taskSnapshot.ownerName == "庆华")
    assert qinghua_item.taskSnapshot.ownerId == "agent:strategy_design"
    assert qinghua_item.structuredNote.departmentPlanAlignment == "aligned"
    assert qinghua_item.structuredNote.planCommitment
    assert qinghua_item.taskSnapshot.listName == "咨询策略部"


def test_sync_agent_execution_tasks_writes_robot_tasks_into_local_task_table(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (
            "log_1",
            "庆华",
            "task.update",
            "task",
            "task_1",
            '{"title":"完成战略判断整理"}',
            "2026-03-17T09:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    task_ids = sync_agent_execution_tasks(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    assert task_ids
    row = db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_ids[0],))
    assert row is not None
    assert str(row["source_type"]) == AGENT_AUTO_SOURCE_TYPE
    assert str(row["owner_name"]) == "庆华"
    note_row = db.fetchone("SELECT * FROM task_notes WHERE task_id = ?", (task_ids[0],))
    assert note_row is not None


def test_build_agent_execution_tasks_returns_formal_task_records(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (
            "log_1",
            "庆华",
            "task.update",
            "task",
            "task_1",
            '{"title":"完成战略判断整理"}',
            "2026-03-17T09:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    tasks = build_agent_execution_tasks(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )

    assert tasks
    assert tasks[0].sourceType == AGENT_AUTO_SOURCE_TYPE
    assert tasks[0].ownerName == "庆华"
    assert tasks[0].creatorId == "agent:strategy_design"
    assert tasks[0].tags


def test_build_agent_execution_task_activity_uses_worklogs(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute(
        "INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at) VALUES(?, ?, ?, ?, ?, NULL)",
        ("list-0", "收集箱", "#5B7BFE", 0, 1),
    )
    db.execute(
        "INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (
            "log_1",
            "庆华",
            "review.create",
            "weekly_review",
            "review_1",
            '{"title":"完成战略判断整理"}',
            "2026-03-17T09:00:00",
        ),
    )
    thread_sync_path = tmp_path / "thread-sync.md"
    thread_sync_path.write_text("# Thread Sync\n", encoding="utf-8")

    task_ids = sync_agent_execution_tasks(
        db=db,
        week_label="2026-W12",
        thread_sync_path=thread_sync_path,
    )
    activities = build_agent_execution_task_activity(
        db=db,
        task_id=task_ids[0],
        thread_sync_path=thread_sync_path,
    )

    assert activities
    assert activities[0].taskId == task_ids[0]
    assert any(item.eventType == "agent.plan_synced" for item in activities)
~~~

## `backend/tests/test_ai_template_fill.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.ai import AiHealth, AiService


def test_generate_template_field_values_batch_returns_cleaned_mapping(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(
            provider="qwen",
            model="qwen3.5-plus",
            ready=True,
            detail="ok",
            credential_source="local",
            fingerprint=None,
        ),
    )

    def fake_qwen_generate(*, prompt: str, system_instruction: str, response_schema: dict | None, **_: object):
        assert response_schema is not None
        assert "机构名称" in response_schema["properties"]
        assert "机构简介" in response_schema["properties"]
        return {
            "机构名称": "建议填写：日慈基金会",
            "机构简介": "```专注于青少年心理健康与社会情感学习。```",
        }

    monkeypatch.setattr(service, "_qwen_generate", fake_qwen_generate)

    values = service.generate_template_field_values_batch(
        template_name="模板.docx",
        client_name="日慈基金会",
        field_contexts=[
            ("机构名称", "字段一上下文"),
            ("机构简介", "字段二上下文"),
        ],
        field_types={
            "机构名称": "precise_fact",
            "机构简介": "structural_summary",
        },
    )

    assert values["机构名称"] == "日慈基金会"
    assert values["机构简介"] == "专注于青少年心理健康与社会情感学习。"


def test_exact_fact_field_stays_conservative_when_model_returns_process_hint(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )
    monkeypatch.setattr(
        service,
        "_qwen_generate",
        lambda **_: "可从登记证书或章程进一步核实统一社会信用代码。",
    )

    value = service.generate_template_field_value(
        field_label="统一社会信用代码",
        template_name="模板.docx",
        client_name="CFFC",
        context_summary="资料不足",
        field_type="precise_fact",
    )

    assert value.startswith("【待确认】")


def test_governance_field_does_not_output_process_style_hint(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )
    monkeypatch.setattr(
        service,
        "_qwen_generate",
        lambda **_: "可从制度文件、会议纪要中进一步梳理党建与业务结合方式。",
    )

    value = service.generate_template_field_value(
        field_label="党建与业务工作的结合方式",
        template_name="模板.docx",
        client_name="CFFC",
        context_summary="若干治理资料",
        field_type="governance_mechanism",
    )

    assert value.startswith("【待确认】")


def test_quantitative_field_cannot_use_vague_description_as_fact(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})

    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )
    monkeypatch.setattr(
        service,
        "_qwen_generate",
        lambda **_: "近三年开展了较多活动，覆盖面较广。",
    )

    value = service.generate_template_field_value(
        field_label="近三年代表性活动/会议数量",
        template_name="模板.docx",
        client_name="CFFC",
        context_summary="若干活动总结",
        field_type="quantitative_result",
    )

    assert value.startswith("【待确认】")


def test_generate_chat_response_extreme_context_uses_relaxed_profile(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})
    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )

    calls: list[dict[str, object]] = []

    def fake_qwen_generate(**kwargs):
        calls.append(kwargs)
        return "这是最终回答。"

    monkeypatch.setattr(service, "_qwen_generate", fake_qwen_generate)

    long_context = "\n\n".join(
        f"[原始证据 {index}]\n标题：材料{index}\n片段：{'原文片段' * 400}"
        for index in range(1, 45)
    )

    response = service.generate_chat_response("请介绍这家组织", "你是顾问。", long_context)

    assert response.content == "这是最终回答。"
    assert len(calls) == 1
    first_call = calls[0]
    assert float(first_call["timeout_seconds"]) >= 34.0
    assert int(first_call["max_tokens"]) <= 2800
    assert first_call["enable_thinking"] is False
    assert len(str(first_call["prompt"])) < len(f"用户问题：请介绍这家组织\n\n参考材料：\n{long_context}")


def test_generate_chat_response_retry_downgrades_to_fast_non_thinking(tmp_path: Path, monkeypatch):
    db = Database(tmp_path / "app.db")
    service = AiService(db, {"qwen": SimpleNamespace()})
    monkeypatch.setattr(
        service,
        "get_health",
        lambda: AiHealth(provider="qwen", model="qwen3.5-plus", ready=True, detail="ok", credential_source="local", fingerprint=None),
    )

    calls: list[dict[str, object]] = []

    def fake_qwen_generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("read timeout")
        return "兜底回答"

    monkeypatch.setattr(service, "_qwen_generate", fake_qwen_generate)

    medium_context = "\n\n".join(
        f"[原始证据 {index}]\n标题：材料{index}\n片段：{'背景信息' * 280}"
        for index in range(1, 22)
    )

    response = service.generate_chat_response("请给出完整判断", "你是顾问。", medium_context)

    assert response.content == "兜底回答"
    assert len(calls) == 2
    first_call, second_call = calls
    assert first_call["enable_thinking"] is True
    assert second_call["enable_thinking"] is False
    assert float(second_call["timeout_seconds"]) >= 18.0
    assert int(second_call["max_tokens"]) <= 1800
    assert len(str(second_call["prompt"])) < len(str(first_call["prompt"]))
~~~

## `backend/tests/test_analysis_main_chain.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.db import Database
from app.main import create_app
from app.models import AiStructuredResponse, AnalysisJobCreatePayload, JudgmentVersionRecord
from app.services.analysis_center import (
    _list_evidence_ids_by_scope,
    claim_next_analysis_job,
    create_analysis_job,
    get_analysis_job,
    resolve_best_judgment,
)


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "主链收口测试客户") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "用于主链 contract 测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def wait_for_knowledge_ready(client: TestClient, client_id: str, *, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/knowledge/status")
        assert response.status_code == 200, response.text
        payload = response.json()
        last_payload = payload
        if payload["pendingJobs"] == 0 and payload["runningJobs"] == 0 and payload["lastJobStatus"] not in {"queued", "running"}:
            return payload
        time.sleep(0.1)
    return last_payload


def wait_for_analysis_job_terminal(client: TestClient, job_id: str, *, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/analysis/jobs/{job_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        last_payload = payload
        if payload["status"] not in {"queued", "running"}:
            return payload
        time.sleep(0.1)
    return last_payload


def test_database_failed_write_rolls_back_before_next_transaction(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    db.execute("CREATE TABLE db_rollback_guard(id TEXT PRIMARY KEY, value TEXT NOT NULL)")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO db_rollback_guard(id, value) VALUES(?, ?)",
            ("broken", None),
        )

    inserted = db.run_in_transaction(
        lambda conn: conn.execute(
            "INSERT INTO db_rollback_guard(id, value) VALUES(?, ?)",
            ("ok", "ready"),
        ).rowcount
    )
    assert inserted == 1
    assert db.scalar("SELECT COUNT(1) AS count FROM db_rollback_guard") == 1


def test_workspace_tolerates_legacy_partial_chat_message_status(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="聊天兼容测试客户")
    created_at = "2026-04-18T09:00:00"
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO chat_threads(id, client_id, title, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        ("thread_partial_status", client_id, "旧消息线程", created_at, created_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, status, llm_invoked, provider_used, answer_mode,
            evidence_status, failure_reason, timing_json, retrieval_summary_json, structured_data_json,
            evidence_json, created_at
        ) VALUES(?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, '{}', '{}', NULL, '[]', ?)
        """,
        ("msg_user_partial_status", "thread_partial_status", "user", "最近有什么变化？", "success", created_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, status, llm_invoked, provider_used, answer_mode,
            evidence_status, failure_reason, timing_json, retrieval_summary_json, structured_data_json,
            evidence_json, created_at
        ) VALUES(?, ?, ?, ?, ?, 1, 'analysis-center', 'grounded_fallback', 'partial', NULL, '{}', '{}', NULL, '[]', ?)
        """,
        (
            "msg_assistant_partial_status",
            "thread_partial_status",
            "assistant",
            "正式成文阶段没有完整完成，但当前先保留一版可读结果。",
            "partial",
            created_at,
        ),
    )

    response = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert response.status_code == 200, response.text
    messages = response.json()["recentMessages"]
    assistant_message = next(item for item in messages if item["id"] == "msg_assistant_partial_status")
    assert assistant_message["status"] == "success"
    client.__exit__(None, None, None)


def insert_judgment(
    client: TestClient,
    *,
    judgment_id: str,
    client_id: str,
    target_type: str,
    target_id: str,
    topic: str,
    summary: str,
    authority_level: str,
    status: str,
    created_at: str,
    updated_at: str,
    context_pack_id: str | None = None,
    invalidated_by: str | None = None,
    stale_reason: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence,
            created_at, updated_at, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by
        )
        VALUES(?, ?, ?, ?, ?, 1, ?, ?, '[]', ?, 'medium', 'medium', ?, ?, 'analysis', ?, 'reviewed', NULL, '', ?, ?)
        """,
        (
            judgment_id,
            client_id,
            target_type,
            target_id,
            topic,
            status,
            summary,
            context_pack_id,
            created_at,
            updated_at,
            authority_level,
            stale_reason,
            invalidated_by,
        ),
    )


def insert_evidence_card(
    client: TestClient,
    *,
    evidence_id: str,
    client_id: str,
    source_id: str,
    source_ref: str,
    source_ref_hash: str,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO evidence_cards(
            id, client_id, scope_type, scope_id, origin_type, authority_level, quality_tier,
            source_type, source_id, source_ref, quote, normalized_claim, evidence_type, polarity,
            tags_json, topic_keys_json, confidence, time_anchor, document_id, event_line_id, task_id,
            meeting_id, module_id, flow_id, review_state, fingerprint, normalized_claim_hash,
            source_ref_hash, evidence_fingerprint, normalizer_version, created_at, updated_at
        )
        VALUES(
            ?, ?, 'client', ?, 'analysis', 'candidate', 'normalized',
            'document_card', ?, ?, '同一条证据', '同一条证据', 'finding', 'neutral',
            '[]', '[]', 0.7, NULL, NULL, NULL, NULL,
            NULL, NULL, NULL, 'awaiting_review', ?, 'claim_hash_shared',
            ?, 'fingerprint_shared', 'analysis-center-v0.3.3', '2026-04-15T08:00:00', '2026-04-15T08:00:00'
        )
        """,
        (
            evidence_id,
            client_id,
            client_id,
            source_id,
            source_ref,
            f"row::{evidence_id}",
            source_ref_hash,
        ),
    )


def insert_dna_delta(
    client: TestClient,
    *,
    delta_id: str,
    client_id: str,
    status: str,
    created_at: str,
    context_pack_id: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO dna_deltas(
            id, client_id, dimension, previous_version, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by, proposed_change, summary,
            evidence_ids_json, confidence, status, context_pack_id, created_at, updated_at
        )
        VALUES(
            ?, ?, 'organization_context', NULL, 'analysis', 'candidate', 'normalized',
            NULL, 'snapshot_sla', NULL, NULL, '补齐项目底稿', '用于 SLA 统计',
            '[]', 'medium', ?, ?, ?, ?
        )
        """,
        (delta_id, client_id, status, context_pack_id, created_at, created_at),
    )


def insert_conflict_group(
    client: TestClient,
    *,
    conflict_id: str,
    client_id: str,
    status: str,
    created_at: str,
    context_pack_id: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO conflict_groups(
            id, client_id, scope_type, scope_id, origin_type, authority_level, quality_tier,
            conflict_type, title, summary, evidence_ids_json, unresolved_question_ids_json,
            resolution_status, severity, context_pack_id, created_at, updated_at
        )
        VALUES(
            ?, ?, 'client', ?, 'analysis', 'candidate', 'normalized',
            'evidence_mismatch', '证据冲突', '用于 SLA 统计', '[]', '[]',
            ?, 'medium', ?, ?, ?
        )
        """,
        (conflict_id, client_id, client_id, status, context_pack_id, created_at, created_at),
    )


def insert_analysis_job(
    client: TestClient,
    *,
    job_id: str,
    client_id: str,
    feature_flags: dict[str, bool],
    created_at: str,
    status: str = "completed",
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO analysis_jobs(
            id, job_type, client_id, scope_type, scope_id, status, priority, trigger_type,
            intent_profile, question, source_snapshot, source_snapshot_hash, dedupe_key,
            feature_flags_json, progress, attempt_count, created_at, updated_at
        )
        VALUES(
            ?, 'strategy_pack', ?, 'client', ?, ?, 'normal', 'manual',
            'client_overview', 'test analysis job', '', '', ?, ?, 1.0, 0, ?, ?
        )
        """,
        (
            job_id,
            client_id,
            client_id,
            status,
            f"dedupe::{job_id}",
            json.dumps(feature_flags, ensure_ascii=False),
            created_at,
            created_at,
        ),
    )


def insert_context_pack(
    client: TestClient,
    *,
    context_pack_id: str,
    client_id: str,
    job_id: str | None,
    created_at: str,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO context_packs(
            id, client_id, job_id, target_type, target_id, created_at, updated_at
        )
        VALUES(?, ?, ?, 'client', ?, ?, ?)
        """,
        (context_pack_id, client_id, job_id, client_id, created_at, created_at),
    )


def insert_approval_record(
    client: TestClient,
    *,
    approval_id: str,
    client_id: str,
    target_type: str,
    target_id: str,
    created_at: str,
    decided_at: str,
    decision: str = "approved",
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO approval_records(
            id, object_type, object_id, client_id, status, note, actor_id, actor_name,
            created_at, approval_target_type, approval_target_id, policy_type, decision,
            comment, decided_by, decided_at, metadata_json
        )
        VALUES(
            ?, ?, ?, ?, ?, '', 'reviewer_demo', 'Reviewer Demo',
            ?, ?, ?, 'analysis_review', ?, '', 'reviewer_demo', ?, '{}'
        )
        """,
        (
            approval_id,
            target_type,
            target_id,
            client_id,
            decision,
            created_at,
            target_type,
            target_id,
            decision,
            decided_at,
        ),
    )


def insert_runtime_run_log(
    client: TestClient,
    *,
    run_id: str,
    client_id: str,
    intent_profile: str,
    selected_object_id: str,
    source_snapshot_hash: str = "snapshot_same",
    summary: str = "resolver metrics seed",
    detail: dict[str, object] | None = None,
    created_at: str = "2026-04-15T09:00:00",
) -> None:
    if detail is None:
        detail = {
            "intentProfile": intent_profile,
            "sourceSnapshotHash": source_snapshot_hash,
            "resolutionTrace": {
                "selectedCandidate": {
                    "objectId": selected_object_id,
                    "scopeType": "client",
                    "scopeId": client_id,
                    "originType": "analysis",
                    "authorityLevel": "candidate",
                    "qualityTier": "normalized",
                },
                "requestedScope": {"scopeType": "client", "scopeId": client_id},
                "resolvedScope": {"scopeType": "client", "scopeId": client_id},
                "writebackScope": {"scopeType": "client", "scopeId": client_id},
                "fallbackUsed": False,
                "consideredCandidates": [],
            },
        }
    client.app.state.app_state.db.execute(
        """
        INSERT INTO runtime_run_logs(
            id, client_id, job_id, provider, model, lane, cache_hit, degraded, document_count, evidence_count,
            conflict_count, context_time_range, prompt_version, schema_version, summary, detail_json, created_at
        )
        VALUES(?, ?, NULL, 'analysis-center', 'analysis-center-v0.3.3', 'cloud_final', 0, 0, 0, 0, 0, NULL, 'analysis-center-v0.3.3', 'analysis-center-v0.3.3', ?, ?, ?)
        """,
        (run_id, client_id, summary, json.dumps(detail, ensure_ascii=False), created_at),
    )


def test_workspace_bundle_returns_client_baseline_plus_overlay(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="客户总览 bundle 测试")

    module_response = client.post(
        f"/api/v1/clients/{client_id}/project-modules",
        json={
            "name": "筹资模块",
            "alias": "",
            "goal": "稳定筹资主线",
            "description": "负责筹资节奏和材料沉淀。",
            "ownerName": "庆华",
            "deliverables": [],
            "keywords": [],
        },
    )
    assert module_response.status_code == 200, module_response.text
    module_id = module_response.json()["id"]

    insert_judgment(
        client,
        judgment_id="judgment_client_baseline",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="客户总体判断",
        summary="这是客户级 approved baseline。",
        authority_level="approved",
        status="approved",
        created_at="2026-04-15T08:00:00",
        updated_at="2026-04-15T08:00:00",
    )
    insert_judgment(
        client,
        judgment_id="judgment_module_overlay",
        client_id=client_id,
        target_type="module",
        target_id=module_id,
        topic="模块变化",
        summary="这是模块级 candidate overlay。",
        authority_level="candidate",
        status="awaiting_review",
        created_at="2026-04-15T08:10:00",
        updated_at="2026-04-15T08:10:00",
    )

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()

    assert payload["judgmentBundle"]["baselineJudgment"]["id"] == "judgment_client_baseline"
    assert [item["id"] for item in payload["judgmentBundle"]["overlayDeltas"]] == ["judgment_module_overlay"]
    assert payload["latestResolutionTrace"]["selectedCandidate"]["objectId"] == "judgment_client_baseline"
    assert payload["latestResolutionTrace"]["writebackScope"] == {"scopeType": "client", "scopeId": client_id}


def test_resolver_trace_uses_fixed_rejected_reason_enums_and_never_upgrades_writeback_scope(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="resolver trace 枚举测试")
    module_id = "module_scope_1"

    insert_judgment(
        client,
        judgment_id="judgment_client_selected",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="经营主判断",
        summary="客户级正式判断。",
        authority_level="approved",
        status="approved",
        created_at="2026-04-15T08:00:00",
        updated_at="2026-04-15T08:00:00",
    )
    insert_judgment(
        client,
        judgment_id="judgment_client_stale",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="经营主判断",
        summary="旧判断已过期。",
        authority_level="candidate",
        status="awaiting_review",
        created_at="2026-04-14T08:00:00",
        updated_at="2026-04-14T08:00:00",
        invalidated_by="judgment_client_selected",
        stale_reason="superseded_by_newer_judgment",
    )
    insert_judgment(
        client,
        judgment_id="judgment_module_candidate",
        client_id=client_id,
        target_type="module",
        target_id=module_id,
        topic="经营主判断",
        summary="模块级候选判断。",
        authority_level="candidate",
        status="awaiting_review",
        created_at="2026-04-15T08:05:00",
        updated_at="2026-04-15T08:05:00",
    )

    selected, trace = resolve_best_judgment(
        client.app.state.app_state.db,
        client_id=client_id,
        requested_scope_type="event_line",
        requested_scope_id="event_line_1",
        intent_profile="task_ai",
        related_refs={"module": [module_id]},
        topic="经营主判断",
        minimum_authority="fallback",
        include_fallback=True,
    )

    assert selected is not None
    assert selected.id == "judgment_module_candidate"
    assert trace.writebackScope is not None
    assert trace.writebackScope.model_dump(mode="json") == {"scopeType": "event_line", "scopeId": "event_line_1"}
    reasons = {item.rejectedReason for item in trace.consideredCandidates if item.rejectedReason}
    assert reasons <= {
        "authority_too_low",
        "scope_less_relevant",
        "stale",
        "superseded",
        "insufficient_evidence",
        "not_approved_for_official_use",
    }
    assert "superseded" in reasons


def test_evidence_storage_rows_and_cluster_dedupe_keys_are_separate(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="evidence 去重测试")

    insert_evidence_card(
        client,
        evidence_id="evidence_source_a",
        client_id=client_id,
        source_id="doc_a",
        source_ref="来源 A",
        source_ref_hash="source_ref_hash_a",
    )
    insert_evidence_card(
        client,
        evidence_id="evidence_source_b",
        client_id=client_id,
        source_id="doc_b",
        source_ref="来源 B",
        source_ref_hash="source_ref_hash_b",
    )

    raw_ids = _list_evidence_ids_by_scope(client.app.state.app_state.db, client_id, "client", client_id)
    deduped_ids = _list_evidence_ids_by_scope(
        client.app.state.app_state.db,
        client_id,
        "client",
        client_id,
        dedupe_by_cluster_key=True,
    )

    assert len(raw_ids) == 2
    assert set(raw_ids) == {"evidence_source_a", "evidence_source_b"}
    assert len(deduped_ids) == 1
    assert deduped_ids[0] in raw_ids


def test_analysis_worker_prioritizes_interactive_and_throttles_consecutive_backfill(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="worker 节流测试")
    db = client.app.state.app_state.db

    create_analysis_job(
        db,
        AnalysisJobCreatePayload(
            jobType="strategy_pack",
            clientId=client_id,
            scopeType="client",
            scopeId=client_id,
            priority="low",
            triggerType="backfill",
            question="backfill 1",
            intentProfile="client_overview",
        ),
    )
    create_analysis_job(
        db,
        AnalysisJobCreatePayload(
            jobType="strategy_pack",
            clientId=client_id,
            scopeType="client",
            scopeId=client_id,
            priority="high",
            triggerType="manual",
            question="interactive first",
            intentProfile="task_ai",
        ),
    )

    first_job = claim_next_analysis_job(db, "worker-test")
    assert first_job is not None
    assert first_job.triggerType == "manual"
    db.execute("UPDATE analysis_jobs SET status = 'completed' WHERE id = ?", (first_job.id,))

    for index in range(2, 5):
        create_analysis_job(
            db,
            AnalysisJobCreatePayload(
                jobType="strategy_pack",
                clientId=client_id,
                scopeType="client",
                scopeId=client_id,
                priority="low",
                triggerType="backfill",
                question=f"backfill {index}",
                intentProfile="dna_summary" if index == 2 else "strategic_cockpit",
            ),
            source_snapshot={"seed": index, "clientId": client_id},
        )

    second_job = claim_next_analysis_job(db, "worker-test")
    assert second_job is not None
    assert second_job.triggerType == "backfill"
    db.execute("UPDATE analysis_jobs SET status = 'completed' WHERE id = ?", (second_job.id,))

    third_job = claim_next_analysis_job(db, "worker-test")
    assert third_job is not None
    assert third_job.triggerType == "backfill"
    db.execute("UPDATE analysis_jobs SET status = 'completed' WHERE id = ?", (third_job.id,))

    throttled = claim_next_analysis_job(db, "worker-test")
    assert throttled is None

    fourth_job = claim_next_analysis_job(db, "worker-test")
    assert fourth_job is not None
    assert fourth_job.triggerType == "backfill"


def test_cockpit_keeps_official_layer_empty_and_surfaces_review_signals(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="cockpit 官方层测试")

    insert_judgment(
        client,
        judgment_id="judgment_client_candidate",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="候选判断",
        summary="这还是候选，不应进入官方层。",
        authority_level="candidate",
        status="awaiting_review",
        created_at="2026-04-10T08:00:00",
        updated_at="2026-04-10T08:00:00",
    )

    response = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["officialLayerStatus"] == "empty"
    assert payload["officialEmptyReason"] == "当前暂无已批准判断"
    assert payload["officialLayer"]["officialBaseline"] is None
    assert payload["radarLayer"]["candidateJudgments"][0]["id"] == "judgment_client_candidate"
    assert payload["radarLayer"]["reviewSignals"][0]["level"] in {"warning", "overdue"}
    assert payload["headline"]["weekSummary"]["value"] == "当前暂无已批准判断"


def test_analysis_migration_metrics_break_down_intent_profiles(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="迁移指标 intentProfile 测试")

    insert_runtime_run_log(
        client,
        run_id="run_task_ai",
        client_id=client_id,
        intent_profile="task_ai",
        selected_object_id="judgment_task_ai",
    )
    insert_runtime_run_log(
        client,
        run_id="run_dna_summary",
        client_id=client_id,
        intent_profile="dna_summary",
        selected_object_id="judgment_dna_summary",
    )

    response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert "task_ai" in payload["pageBreakdown"]
    assert "dna_summary" in payload["pageBreakdown"]
    assert payload["pageBreakdown"]["task_ai"]["totalRuns"] == 1


def test_analysis_migration_metrics_group_mismatches_by_source_snapshot_hash(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="迁移指标 snapshot 分组测试")

    insert_runtime_run_log(
        client,
        run_id="run_snapshot_a",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_snapshot_a",
        source_snapshot_hash="snapshot_a",
    )
    insert_runtime_run_log(
        client,
        run_id="run_snapshot_b",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_snapshot_b",
        source_snapshot_hash="snapshot_b",
    )

    response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["resolverMismatchRate"] == 0.0
    assert payload["pageBreakdown"]["client_overview"]["resolverMismatchRate"] == 0.0


def test_analysis_migration_metrics_include_candidate_sla_counts(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="迁移指标 SLA 计数测试")
    now = datetime.now().replace(microsecond=0)

    insert_judgment(
        client,
        judgment_id="judgment_warning_only",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="warning_only",
        summary="超过 24h 但未超过 72h。",
        authority_level="candidate",
        status="awaiting_review",
        created_at=(now - timedelta(hours=30)).isoformat(),
        updated_at=(now - timedelta(hours=30)).isoformat(),
    )
    insert_dna_delta(
        client,
        delta_id="dna_overdue",
        client_id=client_id,
        status="awaiting_revision",
        created_at=(now - timedelta(hours=80)).isoformat(),
    )
    insert_conflict_group(
        client,
        conflict_id="conflict_new_24h",
        client_id=client_id,
        status="awaiting_review",
        created_at=(now - timedelta(hours=2)).isoformat(),
    )

    response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["approvalBacklog"] == 3
    assert payload["candidateReviewWarningCount"] == 2
    assert payload["candidateReviewOverdueCount"] == 1
    assert payload["newCandidateUnreviewed24h"] == 1


def test_analysis_migration_metrics_exclude_canary_without_excluding_real_or_legacy_samples(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="迁移指标 canary 排除测试")
    now = datetime.now().replace(microsecond=0)

    real_job_at = (now - timedelta(hours=90)).isoformat()
    insert_analysis_job(
        client,
        job_id="job_real_metrics",
        client_id=client_id,
        feature_flags={},
        created_at=real_job_at,
    )
    insert_context_pack(
        client,
        context_pack_id="ctx_real_metrics",
        client_id=client_id,
        job_id="job_real_metrics",
        created_at=real_job_at,
    )

    canary_job_at = (now - timedelta(hours=96)).isoformat()
    insert_analysis_job(
        client,
        job_id="job_canary_metrics",
        client_id=client_id,
        feature_flags={"main-chain-canary": True},
        created_at=canary_job_at,
    )
    insert_context_pack(
        client,
        context_pack_id="ctx_canary_metrics",
        client_id=client_id,
        job_id="job_canary_metrics",
        created_at=canary_job_at,
    )

    insert_judgment(
        client,
        judgment_id="judgment_real_warning",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="real_warning",
        summary="真实样本，超过 24h。",
        authority_level="candidate",
        status="awaiting_review",
        context_pack_id="ctx_real_metrics",
        created_at=(now - timedelta(hours=30)).isoformat(),
        updated_at=(now - timedelta(hours=30)).isoformat(),
    )
    insert_dna_delta(
        client,
        delta_id="dna_real_overdue",
        client_id=client_id,
        status="awaiting_revision",
        context_pack_id="ctx_real_metrics",
        created_at=(now - timedelta(hours=80)).isoformat(),
    )
    insert_conflict_group(
        client,
        conflict_id="conflict_real_new",
        client_id=client_id,
        status="awaiting_review",
        context_pack_id="ctx_real_metrics",
        created_at=(now - timedelta(hours=2)).isoformat(),
    )
    insert_judgment(
        client,
        judgment_id="judgment_legacy_warning",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="legacy_warning",
        summary="legacy 真实样本，没有 context_pack_id。",
        authority_level="candidate",
        status="awaiting_review",
        created_at=(now - timedelta(hours=50)).isoformat(),
        updated_at=(now - timedelta(hours=50)).isoformat(),
    )

    insert_judgment(
        client,
        judgment_id="judgment_real_approved",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="real_approved",
        summary="真实已审批样本。",
        authority_level="approved",
        status="approved",
        context_pack_id="ctx_real_metrics",
        created_at=(now - timedelta(hours=6)).isoformat(),
        updated_at=now.isoformat(),
    )
    insert_approval_record(
        client,
        approval_id="approval_real_metrics",
        client_id=client_id,
        target_type="judgment_version",
        target_id="judgment_real_approved",
        created_at=now.isoformat(),
        decided_at=now.isoformat(),
    )

    insert_judgment(
        client,
        judgment_id="judgment_canary_warning",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="canary_warning",
        summary="canary 样本，不应计入。",
        authority_level="candidate",
        status="awaiting_review",
        context_pack_id="ctx_canary_metrics",
        created_at=(now - timedelta(hours=90)).isoformat(),
        updated_at=(now - timedelta(hours=90)).isoformat(),
    )
    insert_dna_delta(
        client,
        delta_id="dna_canary_overdue",
        client_id=client_id,
        status="awaiting_revision",
        context_pack_id="ctx_canary_metrics",
        created_at=(now - timedelta(hours=90)).isoformat(),
    )
    insert_conflict_group(
        client,
        conflict_id="conflict_canary_warning",
        client_id=client_id,
        status="awaiting_review",
        context_pack_id="ctx_canary_metrics",
        created_at=(now - timedelta(hours=90)).isoformat(),
    )
    insert_judgment(
        client,
        judgment_id="judgment_canary_approved",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="canary_approved",
        summary="canary 已审批样本，不应影响 lag。",
        authority_level="approved",
        status="approved",
        context_pack_id="ctx_canary_metrics",
        created_at=(now - timedelta(hours=40)).isoformat(),
        updated_at=now.isoformat(),
    )
    insert_approval_record(
        client,
        approval_id="approval_canary_metrics",
        client_id=client_id,
        target_type="judgment_version",
        target_id="judgment_canary_approved",
        created_at=now.isoformat(),
        decided_at=now.isoformat(),
    )

    response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["approvalBacklog"] == 4
    assert payload["approvalLagHoursMedian"] == 6.0
    assert payload["candidateReviewWarningCount"] == 3
    assert payload["candidateReviewOverdueCount"] == 1
    assert payload["newCandidateUnreviewed24h"] == 1


def test_main_chain_backfill_dry_run_returns_candidates_without_queueing_jobs(tmp_path: Path):
    client = make_client(tmp_path)
    client_ids = [
        create_test_client_record(client, name="主链 backfill dry-run 客户 A"),
        create_test_client_record(client, name="主链 backfill dry-run 客户 B"),
    ]

    response = client.post(
        "/api/v1/analysis/backfill-main-chain",
        json={
            "clientIds": client_ids,
            "dryRun": True,
            "batchSize": 2,
            "maxJobs": 4,
            "pauseRequested": False,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["dryRun"] is True
    assert payload["queuedJobs"] == 0
    assert payload["paused"] is False
    assert len(payload["candidates"]) == 2
    assert {item["clientId"] for item in payload["candidates"]}.issubset(set(client_ids))
    assert all(item["triggerType"] == "backfill" for item in payload["candidates"])
    assert client.app.state.app_state.db.scalar("SELECT COUNT(1) AS count FROM analysis_jobs") == 0


def test_latest_judgments_shadow_power_off_keeps_main_chain_contract(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="latestJudgments 影子断电测试")

    insert_judgment(
        client,
        judgment_id="judgment_shadow_off",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="客户总体判断",
        summary="bundle 仍应可读。",
        authority_level="approved",
        status="approved",
        created_at="2026-04-15T08:00:00",
        updated_at="2026-04-15T08:00:00",
    )

    update_settings = client.post(
        "/api/v1/settings/main-chain-stability",
        json={"latestJudgmentsShadowOff": True},
    )
    assert update_settings.status_code == 200, update_settings.text
    assert update_settings.json()["latestJudgmentsShadowOff"] is True

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()

    assert payload["judgmentBundle"]["baselineJudgment"]["id"] == "judgment_shadow_off"
    assert payload["latestResolutionTrace"]["selectedCandidate"]["objectId"] == "judgment_shadow_off"
    assert payload["latestJudgments"] == []


def test_main_chain_stability_settings_accept_fixed_canary_observation_fields(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/v1/settings/main-chain-stability",
        json={
            "latestJudgmentsShadowOff": True,
            "lastCanaryObservation": {
                "timeRange": "2026-04-15 / Wave 1",
                "clientCount": 2,
                "enqueuedJobs": 2,
                "completedJobs": 2,
                "failedJobs": 0,
                "newObjectHitRateBefore": 0.6,
                "newObjectHitRateAfter": 0.8,
                "fallbackRateBefore": 0.3,
                "fallbackRateAfter": 0.1,
                "resolverMismatchRateBefore": 0.2,
                "resolverMismatchRateAfter": 0.0,
                "approvalBacklog": 1,
                "approvalLagHoursMedian": 8.5,
                "claimCounts": {"backfill": 2},
                "lockContention": {"backfill": 0},
                "backfillThrottle": {"backfill": 1},
                "impactedRealtimeTasks": False,
                "latestJudgmentsShadowOff": True,
                "verdict": "pass",
                "conclusion": "Wave 1 通过。",
            },
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["latestJudgmentsShadowOff"] is True
    assert payload["lastCanaryObservation"]["newObjectHitRateBefore"] == 0.6
    assert payload["lastCanaryObservation"]["newObjectHitRateAfter"] == 0.8
    assert payload["lastCanaryObservation"]["latestJudgmentsShadowOff"] is True
    assert payload["lastCanaryObservation"]["verdict"] == "pass"


def test_main_chain_projection_is_idempotent_for_same_source_snapshot(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="主链幂等性测试")
    source = tmp_path / "analysis-idempotent-source"
    source.mkdir()
    (source / "项目总览.md").write_text(
        "# 项目总览\n"
        "该客户当前围绕公益机构战略陪伴、会议复盘与知识底盘建设推进统一上下文。\n"
        "本轮目标是把已有材料沉淀为稳定 judgment bundle，而不是重复膨胀对象。\n",
        encoding="utf-8",
    )

    def stable_generate_structured(prompt: str, system_instruction: str, context_summary: str) -> AiStructuredResponse:
        return AiStructuredResponse(
            content="## 1. 当前重点\n统一客户上下文。\n\n## 2. 推进建议\n围绕主问题形成稳定 judgment。",
            judgment="当前重点是把已有资料沉淀成统一上下文，并形成稳定的客户级判断。",
            analysis="仍缺阶段目标\n仍缺更多案例",
            actions="项目总览.md",
            timeline="补齐案例后再继续迭代。",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_structured", stable_generate_structured)

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "folder", "paths": [str(source)]},
    )
    assert imported.status_code == 200, imported.text
    status = wait_for_knowledge_ready(client, client_id)
    assert status["lastJobStatus"] == "completed"

    def run_analysis_job() -> dict:
        job_response = client.post(
            "/api/v1/analysis/jobs",
            json={
                "jobType": "strategy_pack",
                "clientId": client_id,
                "scopeType": "client",
                "scopeId": client_id,
                "priority": "normal",
                "triggerType": "manual",
                "question": "主链幂等性 gate",
                "sourceScope": {},
                "featureFlags": {},
                "intentProfile": "client_overview",
            },
        )
        assert job_response.status_code == 200, job_response.text
        payload = wait_for_analysis_job_terminal(client, job_response.json()["id"])
        assert payload["status"] == "completed", payload
        workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
        assert workspace.status_code == 200, workspace.text
        return workspace.json()

    first_workspace = run_analysis_job()
    second_workspace = run_analysis_job()
    metrics_response = client.get("/api/v1/runtime/analysis-migration-metrics")
    assert metrics_response.status_code == 200, metrics_response.text
    metrics_payload = metrics_response.json()

    for count_key in ("evidenceCardCount", "themeClusterCount", "conflictGroupCount", "openQuestionCount"):
        assert first_workspace["analysisCenter"][count_key] == second_workspace["analysisCenter"][count_key]
    assert first_workspace["judgmentBundle"]["baselineJudgment"]["id"] == second_workspace["judgmentBundle"]["baselineJudgment"]["id"]
    assert first_workspace["latestResolutionTrace"]["selectedCandidate"]["objectId"] == second_workspace["latestResolutionTrace"]["selectedCandidate"]["objectId"]
    assert metrics_payload["resolverMismatchRate"] == 0.0
    assert metrics_payload["pageBreakdown"]["client_overview"]["resolverMismatchRate"] == 0.0


def test_workspace_state_projection_handles_runtime_run_log_variants(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="运行日志兼容测试")

    insert_runtime_run_log(
        client,
        run_id="runlog_variant_new",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_variant_new",
        summary="客户状态分析已完成",
        detail={
            "intentProfile": "client_overview",
            "latestRunSummary": "本周重点已经从资料整理切到 judgment 收口。",
            "outputSummary": "outputSummary 不应覆盖 latestRunSummary。",
        },
    )
    insert_runtime_run_log(
        client,
        run_id="runlog_variant_old",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_variant_old",
        summary="旧版运行摘要仍应兼容",
        detail={"phase": "completed"},
        created_at="2026-04-15T09:10:00",
    )
    insert_runtime_run_log(
        client,
        run_id="runlog_variant_minimal",
        client_id=client_id,
        intent_profile="client_overview",
        selected_object_id="judgment_variant_minimal",
        summary="",
        detail={},
        created_at="2026-04-15T09:20:00",
    )

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()

    projection = payload["stateProjection"]
    run_log_items = [item for item in projection["progressItems"] if item["sourceType"] == "run_log"]
    assert any("本周重点已经从资料整理切到 judgment 收口" in item["summary"] for item in run_log_items)
    assert any(item["summary"] == "旧版运行摘要仍应兼容" for item in run_log_items)
    assert all(item["sourceId"] != "runlog_variant_minimal" for item in run_log_items)
    assert projection["boundaryNotes"]


def test_workspace_state_projection_does_not_fallback_to_latest_judgments_when_bundle_missing(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="compat judgment 回流测试")
    insert_judgment(
        client,
        judgment_id="judgment_bundle_only",
        client_id=client_id,
        target_type="client",
        target_id=client_id,
        topic="bundle 正式判断",
        summary="正式判断只能来自 judgment bundle。",
        authority_level="approved",
        status="approved",
        created_at="2026-04-15T10:00:00",
        updated_at="2026-04-15T10:00:00",
    )

    real_get_bundle = app_main.get_client_analysis_bundle
    compat_judgment = JudgmentVersionRecord(
        id="judgment_compat_only",
        clientId=client_id,
        targetType="client",
        targetId=client_id,
        topic="compat judgment",
        status="approved",
        originType="analysis",
        authorityLevel="approved",
        qualityTier="reviewed",
        summary="这条 compat judgment 不能回流进正式判断。",
        createdAt="2026-04-15T10:05:00",
        updatedAt="2026-04-15T10:05:00",
    )

    def fake_get_bundle(db, workspace_seed):
        bundle = real_get_bundle(db, workspace_seed)
        bundle.judgment_bundle = None
        bundle.latest_judgments = [compat_judgment]
        return bundle

    monkeypatch.setattr(app_main, "get_client_analysis_bundle", fake_get_bundle)

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()

    assert payload["latestJudgments"][0]["id"] == "judgment_compat_only"
    judgment_items = [item for item in payload["stateProjection"]["changeItems"] if item["sourceType"] == "judgment"]
    assert judgment_items == []
    assert any("当前还没有足够稳定的正式判断" in note for note in payload["stateProjection"]["boundaryNotes"])


def test_event_line_evidence_count_defaults_to_zero_and_accepts_null_patch(tmp_path: Path):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "证据计数默认值测试",
            "kind": "custom",
            "status": "active",
            "visibilityScope": "project_public",
            "businessCategory": "增长",
            "stage": "推进中",
            "summary": "验证 evidence_count 兜底",
            "evidenceCount": None,
            "participantIds": [],
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["evidenceCount"] == 0

    updated = client.patch(
        f"/api/v1/event-lines/{payload['id']}",
        json={"evidenceCount": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["evidenceCount"] == 0


def test_analysis_job_projection_handles_event_line_tasks_and_legacy_structured_summary(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="阶段 A 运行验证客户")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "主链接管验证事件线",
            "kind": "project_line",
            "status": "active",
            "summary": "用于验证 analysis_center 主链执行。",
            "intent": "检查事件线 judgment 与 legacy analysis run 兼容。",
            "nextStep": "重跑 client_overview job。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "主链接管验证任务",
            "desc": "验证事件线 judgment 同步不会因为裸变量报错。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text

    db = client.app.state.app_state.db
    created_at = "2026-04-15T15:00:00"
    db.execute(
        """
        INSERT INTO chat_threads(id, client_id, title, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        ("thread_main_chain", client_id, "主链接管验证线程", created_at, created_at),
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, status, llm_invoked, provider_used, answer_mode,
            evidence_status, failure_reason, timing_json, retrieval_summary_json, structured_data_json,
            evidence_json, created_at
        ) VALUES(?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, '{}', '{}', NULL, '[]', ?)
        """,
        ("msg_user_main_chain", "thread_main_chain", "user", "介绍当前客户情况", "success", created_at),
    )
    structured_summary = AiStructuredResponse(
        content="这是历史分析输出。",
        judgment="需要继续跟进事件线动作。",
        analysis="当前判断仍需补齐客户级正式确认。",
        actions="先完成一轮 client_overview 判断。",
        timeline="本周内完成。",
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, status, llm_invoked, provider_used, answer_mode,
            evidence_status, failure_reason, timing_json, retrieval_summary_json, structured_data_json,
            evidence_json, created_at
        ) VALUES(?, ?, ?, ?, ?, 1, 'analysis-center', 'grounded_answer', 'sufficient', NULL, '{}', '{}', ?, '[]', ?)
        """,
        (
            "msg_assistant_main_chain",
            "thread_main_chain",
            "assistant",
            "这是历史分析输出。",
            "success",
            json.dumps(structured_summary.model_dump(), ensure_ascii=False),
            created_at,
        ),
    )
    db.execute(
        """
        INSERT INTO client_analysis_runs(
            id, client_id, thread_id, user_message_id, assistant_message_id, question,
            status, phase, progress, progress_floor, progress_ceiling, stage_label, elapsed_ms,
            evidence_summary_json, long_answer, structured_summary_json, long_answer_status,
            summary_status, answer_mode, llm_invoked, provider_used, failure_reason, timing_json,
            created_at, updated_at
        ) VALUES(
            ?, ?, ?, ?, ?, ?, 'completed', 'completed', 100, 0, 100, '已完成', 1200,
            '{"masterHitCount": 1, "surrogateHitCount": 0, "evidenceList": []}',
            '这是历史分析输出。',
            ?, 'ready', 'ready', 'grounded_answer', 1, 'analysis-center', NULL, '{"totalMs": 1200}',
            ?, ?
        )
        """,
        (
            "legacy_run_main_chain",
            client_id,
            "thread_main_chain",
            "msg_user_main_chain",
            "msg_assistant_main_chain",
            "介绍当前客户情况",
            json.dumps(structured_summary.model_dump(), ensure_ascii=False),
            created_at,
            created_at,
        ),
    )

    payload = AnalysisJobCreatePayload(
        jobType="strategy_pack",
        clientId=client_id,
        scopeType="client",
        scopeId=client_id,
        priority="normal",
        triggerType="manual",
        question="main-chain regression",
        intentProfile="client_overview",
    )
    job = create_analysis_job(
        db,
        payload,
        source_snapshot={
            "clientId": client_id,
            "scopeType": "client",
            "scopeId": client_id,
            "question": "main-chain regression",
        },
    )

    terminal = wait_for_analysis_job_terminal(client, job.id)
    assert terminal["status"] == "completed"

    persisted = get_analysis_job(db, job.id)
    assert persisted is not None
    assert persisted.status == "completed"
    assert persisted.lastError is None

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    assert workspace_payload["judgmentBundle"]["baselineJudgment"]["id"]
    assert workspace_payload["latestResolutionTrace"]["selectedCandidate"]["objectId"]


def test_projection_helper_is_not_imported_by_main_chain_routes():
    app_root = Path(app_main.__file__).resolve().parent
    hits = []
    for path in app_root.rglob("*.py"):
        if "refresh_client_analysis_projection(" not in path.read_text(encoding="utf-8"):
            continue
        hits.append(path.name)
    assert hits == ["analysis_center.py"]


def test_main_chain_consumers_do_not_use_latest_judgments_as_formal_source():
    repo_root = Path(app_main.__file__).resolve().parents[2]
    allowed_hits = {
        "backend/app/main.py": {"latestJudgments="},
        "backend/app/models.py": {"latestJudgments:"},
        "src/shared/types.ts": {"latestJudgments:"},
        "src/renderer/App.tsx": {
            "latestJudgmentsShadowOff",
            "latestJudgments 兼容输出",
            "影子断电 latestJudgments",
            "恢复 latestJudgments",
            "已关闭 latestJudgments 兼容输出",
            "已恢复 latestJudgments 兼容输出",
            "切换 latestJudgments 影子断电失败",
        },
    }
    pattern = re.compile(r"\blatestJudgments\b")
    disallowed_hits: list[str] = []
    for base in (repo_root / "backend" / "app", repo_root / "src"):
        for path in base.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx"}:
                continue
            relative = str(path.relative_to(repo_root))
            text = path.read_text(encoding="utf-8")
            if not pattern.search(text):
                continue
            allowed_markers = allowed_hits.get(relative, set())
            filtered_lines = [
                line.strip()
                for line in text.splitlines()
                if pattern.search(line) and not any(marker in line for marker in allowed_markers)
            ]
            if filtered_lines:
                disallowed_hits.append(f"{relative}: {' | '.join(filtered_lines[:3])}")
    assert disallowed_hits == []
~~~

## `backend/tests/test_api_smoke.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.ai import AiInvocationError
from app.services.knowledge_base import CitationMatch, RetrievalBundle
from app.services.topic_capture import TopicSearchHit


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def make_app_only(tmp_path: Path):
    return create_app(tmp_path / "data")


def wait_for_topic_insight_status(client: TestClient, candidate_id: str, *, expected: str = "ready", timeout: float = 8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = client.app.state.app_state.db.fetchone(
            "SELECT insight_status FROM topic_candidates WHERE id = ?",
            (candidate_id,),
        )
        if row is not None and row["insight_status"] == expected:
            return row
        time.sleep(0.1)
    return client.app.state.app_state.db.fetchone(
        "SELECT insight_status FROM topic_candidates WHERE id = ?",
        (candidate_id,),
    )


def create_test_client_record(client: TestClient, name: str = "知识底座测试客户") -> str:
    created = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于知识底座测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    return created.json()["id"]


def seed_session_user(
    client: TestClient,
    *,
    user_id: str = "user_emp",
    email: str = "employee@example.com",
    full_name: str = "普通员工",
    primary_role: str = "employee",
) -> dict:
    payload = {
        "id": user_id,
        "organizationId": "org_1",
        "email": email,
        "fullName": full_name,
        "primaryRole": primary_role,
        "accountStatus": "approved",
    }
    client.app.state.app_state.db.set_setting("cloud_session_user", json.dumps(payload, ensure_ascii=False))
    return payload


def seed_cloud_token(client: TestClient, token: str = "token_demo") -> None:
    client.app.state.app_state.db.set_setting("cloud_access_token", token)


def stub_cloud_auth_me(monkeypatch, user_payload: dict, *, base_url: str = "http://127.0.0.1:47830"):
    def fake_cloud_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url == f"{base_url.rstrip('/')}/api/v1/auth/me":
            return httpx.Response(200, json=user_payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)


def stub_cloud_strategic_services(
    monkeypatch,
    *,
    leader_user_id: str | None,
    base_url: str = "http://127.0.0.1:47830",
    tasks_payload: dict | None = None,
    review_dashboard_payload: dict | None = None,
):
    org_model_payload = {
        "organization": {
            "organizationId": "org_1",
            "name": "益语智库",
            "annualGoal": "",
            "annualStrategyYear": "2026",
            "annualStrategy": "",
            "quarterPlans": [],
            "quarterlyFocus": [],
            "leaderUserId": leader_user_id,
            "managementUserIds": [],
            "updatedAt": "2026-03-22T00:00:00",
        },
        "departments": [],
        "roles": [],
        "bindings": [],
        "reportingLines": [],
        "taskControlRules": [],
        "roleProcessTemplates": [],
        "focusItems": [],
        "departmentPlans": [],
        "updatedAt": "2026-03-22T00:00:00",
    }
    tasks_payload = tasks_payload or {"tasks": [], "lists": [], "tags": []}
    review_dashboard_payload = review_dashboard_payload or {}

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = f"{base_url.rstrip('/')}"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/settings/org-model/profile":
            return httpx.Response(200, json=org_model_payload)
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(200, json=tasks_payload)
        if method.upper() == "GET" and url == f"{normalized}/api/v1/employees/directory":
            return httpx.Response(200, json=[])
        if method.upper() == "GET" and url.startswith(f"{normalized}/api/v1/reviews/dashboard"):
            return httpx.Response(200, json=review_dashboard_payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)


def wait_for_knowledge_ready(client: TestClient, client_id: str, *, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/knowledge/status")
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if payload["pendingJobs"] == 0 and payload["runningJobs"] == 0 and payload["lastJobStatus"] not in {"queued", "running"}:
            return payload
        time.sleep(0.1)
    return last_payload


def wait_for_generated_dna_modules(
    client: TestClient,
    client_id: str,
    *,
    module_keys: list[str],
    timeout: float = 120.0,
) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/workspace")
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        modules = {item["moduleKey"]: item for item in payload.get("dnaModules", [])}
        if all(
            modules.get(module_key, {}).get("hasDocument") is True
            and modules.get(module_key, {}).get("sourceKind") == "generated"
            for module_key in module_keys
        ):
            return payload
        time.sleep(0.1)
    return last_payload


def wait_for_analysis_job_terminal(client: TestClient, job_id: str, *, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last_payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/analysis/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if payload["status"] not in {"queued", "running"}:
            return payload
        time.sleep(0.1)
    return last_payload


def test_health_and_structural_defaults(tmp_path: Path):
    client = make_client(tmp_path)

    health = client.get("/api/v1/system/health")
    assert health.status_code == 200
    payload = health.json()
    assert payload["appName"] == "益语智库自用平台"
    assert payload["buildVersion"]
    assert payload["startedAt"]
    assert "knowledge.vectorize-answer" in payload["featureFlags"]
    assert "knowledge.reclass-events" in payload["featureFlags"]
    assert "chat.general-answer" in payload["featureFlags"]
    assert payload["stats"]["clients"] == 0

    task_board = client.get("/api/v1/tasks")
    assert task_board.status_code == 200
    task_payload = task_board.json()
    assert len(task_payload["lists"]) >= 4
    assert isinstance(task_payload["tasks"], list)
    assert task_payload["tasks"] == []


def test_cross_site_browser_requests_are_rejected(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="跨站保护测试客户")

    rejected_read = client.get(
        "/api/v1/clients",
        headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
    )
    assert rejected_read.status_code == 403, rejected_read.text

    rejected_delete = client.delete(
        f"/api/v1/clients/{client_id}",
        headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
    )
    assert rejected_delete.status_code == 403, rejected_delete.text

    allowed_read = client.get(
        "/api/v1/clients",
        headers={"origin": "http://127.0.0.1:4173", "referer": "http://127.0.0.1:4173/app"},
    )
    assert allowed_read.status_code == 200, allowed_read.text


def test_local_browser_requests_allow_dynamic_renderer_ports(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.get(
        "/api/v1/settings/tasks",
        headers={"origin": "http://127.0.0.1:4174", "referer": "http://127.0.0.1:4174/"},
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:4174"


def test_local_browser_preflight_allows_dynamic_renderer_ports(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.options(
        "/api/v1/system/health",
        headers={
            "origin": "http://127.0.0.1:4174",
            "access-control-request-method": "GET",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:4174"


def test_template_fill_start_reuses_existing_active_run_for_same_template(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="模板填写排队测试客户")
    timestamp = "2026-03-24T09:00:00"
    template_path = "/tmp/demo-template.docx"
    existing_run_id = "tmplfill_existing"
    client.app.state.app_state.db.execute(
        """
        INSERT INTO client_template_fill_runs(
            id, client_id, template_name, template_path, status, phase, progress, stage_label, elapsed_ms,
            field_count, processed_count, filled_count, missing_count, current_field_label, evidence_titles_json, fields_json, output_path, error_message,
            created_at, updated_at
        )
        VALUES(?, ?, ?, ?, 'running', 'retrieving', 18, '正在检索资料', 1200, 65, 12, 5, 7, '机构全称', '[]', '[]', NULL, NULL, ?, ?)
        """,
        (existing_run_id, client_id, "demo-template.docx", template_path, timestamp, timestamp),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/documents/fill-template/start",
        json={"templatePath": template_path},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == existing_run_id
    assert payload["status"] == "running"


def test_event_line_clarification_fields_persist_locally(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="事件线澄清测试客户")

    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "项目推进确认线",
            "kind": "project_line",
            "primaryClientId": client_id,
        },
    )
    assert created.status_code == 200, created.text
    event_line_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "stage": "等待客户确认",
            "currentBlocker": "还在等客户最终确认方向。",
            "nextStep": "本周内补齐会后动作并同步下一轮排期。",
            "recentDecision": "先补齐资料，再推进下一轮方案沟通。",
        },
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["stage"] == "等待客户确认"
    assert payload["currentBlocker"] == "还在等客户最终确认方向。"
    assert payload["nextStep"] == "本周内补齐会后动作并同步下一轮排期。"
    assert payload["recentDecision"] == "先补齐资料，再推进下一轮方案沟通。"

    detail = client.get(f"/api/v1/event-lines/{event_line_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["eventLine"]["currentBlocker"] == "还在等客户最终确认方向。"
    assert detail.json()["eventLine"]["recentDecision"] == "先补齐资料，再推进下一轮方案沟通。"

    row = client.app.state.app_state.db.fetchone(
        "SELECT current_blocker, recent_decision FROM event_lines WHERE id = ?",
        (event_line_id,),
    )
    assert row is not None
    assert row["current_blocker"] == "还在等客户最终确认方向。"
    assert row["recent_decision"] == "先补齐资料，再推进下一轮方案沟通。"


def test_event_line_transfer_syncs_linked_task_client_ids(tmp_path: Path):
    client = make_client(tmp_path)
    target_client_id = create_test_client_record(client, name="正式签约客户")

    created_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "潜在线索推进线",
            "kind": "project_line",
        },
    )
    assert created_line.status_code == 200, created_line.text
    event_line_id = created_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "继续推进意向沟通",
            "priority": "high",
            "listId": "list-0",
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()
    assert task_payload["clientId"] is None

    updated_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "primaryClientId": target_client_id,
            "syncLinkedTaskClientIds": True,
        },
    )
    assert updated_line.status_code == 200, updated_line.text
    assert updated_line.json()["primaryClientId"] == target_client_id

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    migrated_task = next(item for item in board.json()["tasks"] if item["id"] == task_payload["id"])
    assert migrated_task["clientId"] == target_client_id
    assert migrated_task["clientName"] == "正式签约客户"

    row = client.app.state.app_state.db.fetchone(
        "SELECT client_id FROM tasks WHERE id = ?",
        (task_payload["id"],),
    )
    assert row is not None
    assert row["client_id"] == target_client_id


def test_event_line_transfer_rehomes_attachments_and_memory_locally(tmp_path: Path):
    client = make_client(tmp_path)
    source_client_name = "谈判阶段客户"
    target_client_name = "正式签约客户"
    source_client_id = create_test_client_record(client, name=source_client_name)
    target_client_id = create_test_client_record(client, name=target_client_name)

    created_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "签约推进线",
            "kind": "project_line",
            "primaryClientId": source_client_id,
        },
    )
    assert created_line.status_code == 200, created_line.text
    event_line_id = created_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "整理签约资料",
            "priority": "high",
            "listId": "list-0",
            "clientId": source_client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": source_client_id,
            "eventLineId": event_line_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "签约材料.md",
                "# 签约材料\n\n这里记录签约范围、预算和交付边界。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    from app.services.local_memory import event_line_memory_dir, write_event_line_memory

    write_event_line_memory(
        client.app.state.app_state.data_dir,
        source_client_id,
        event_line_id,
        "签约推进线",
        source_client_name,
        "## 线索记录\n\n当前已经进入签约细化阶段。",
    )
    source_memory_path = event_line_memory_dir(client.app.state.app_state.data_dir, source_client_id) / f"{event_line_id}.md"
    assert source_memory_path.exists()

    updated_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "primaryClientId": target_client_id,
            "syncLinkedTaskClientIds": True,
        },
    )
    assert updated_line.status_code == 200, updated_line.text
    assert updated_line.json()["primaryClientId"] == target_client_id

    attachment_row = client.app.state.app_state.db.fetchone(
        "SELECT client_id, path, document_id FROM task_attachments WHERE id = ?",
        (attachment["id"],),
    )
    assert attachment_row is not None
    assert attachment_row["client_id"] == target_client_id
    assert target_client_id in str(attachment_row["path"])
    assert Path(str(attachment_row["path"])).exists()
    assert not Path(str(attachment["path"])).exists()

    document_id = str(attachment_row["document_id"])
    document_row = client.app.state.app_state.db.fetchone(
        "SELECT client_id, path, original_source_path FROM documents WHERE id = ?",
        (document_id,),
    )
    assert document_row is not None
    assert document_row["client_id"] == target_client_id
    assert target_client_id in str(document_row["path"])

    knowledge_row = client.app.state.app_state.db.fetchone(
        "SELECT client_id, current_human_path FROM knowledge_documents WHERE document_id = ?",
        (document_id,),
    )
    assert knowledge_row is not None
    assert knowledge_row["client_id"] == target_client_id
    assert target_client_id in str(knowledge_row["current_human_path"])

    v2_row = client.app.state.app_state.db.fetchone(
        "SELECT client_id, managed_path FROM v2_documents WHERE document_id = ?",
        (document_id,),
    )
    assert v2_row is not None
    assert v2_row["client_id"] == target_client_id
    assert target_client_id in str(v2_row["managed_path"])

    target_memory_path = event_line_memory_dir(client.app.state.app_state.data_dir, target_client_id) / f"{event_line_id}.md"
    assert target_memory_path.exists()
    assert not source_memory_path.exists()
    target_memory_content = target_memory_path.read_text(encoding="utf-8")
    assert f"client_id: {target_client_id}" in target_memory_content
    assert f"project: {target_client_name}" in target_memory_content


def test_event_line_transfer_syncs_derived_client_scopes_locally(tmp_path: Path):
    client = make_client(tmp_path)
    source_client_name = "谈判阶段客户"
    target_client_name = "正式签约客户"
    source_client_id = create_test_client_record(client, name=source_client_name)
    target_client_id = create_test_client_record(client, name=target_client_name)

    created_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "签约推进线",
            "kind": "project_line",
            "primaryClientId": source_client_id,
        },
    )
    assert created_line.status_code == 200, created_line.text
    event_line_id = created_line.json()["id"]

    db = client.app.state.app_state.db
    timestamp = "2026-04-17T10:00:00"
    learning_content_id = "content_transfer_scope"
    handbook_id = "handbook_transfer_scope"
    recommendation_id = "rec_transfer_scope"
    evidence_id = "evidence_transfer_scope"
    theme_id = "theme_transfer_scope"
    conflict_id = "conflict_transfer_scope"
    question_id = "question_transfer_scope"
    sync_memory_id = "syncmem_transfer_scope"
    analysis_job_id = "analysis_transfer_scope"
    context_pack_id = "context_transfer_scope"
    runtime_log_id = "runlog_transfer_scope"
    judgment_id = "judgment_transfer_scope"
    dna_delta_id = "delta_transfer_scope"
    approval_context_id = "approval_context_transfer_scope"
    approval_judgment_id = "approval_judgment_transfer_scope"

    db.execute(
        """
        INSERT INTO learning_content_items(
            id, content_type, ability_key, title, summary, body, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            learning_content_id,
            "playbook",
            "client_push",
            "签约推进动作",
            "把推进动作压到客户主线里。",
            "围绕正式签约后的协同方式组织动作。",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO handbook_entries(
            id, title, summary, tags_json, source_type, client_id, event_line_id, event_line_name, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            handbook_id,
            "签约后立刻重挂客户主线",
            "把推进材料、判断和动作都切到正式客户下。",
            json.dumps(["签约", "迁移"], ensure_ascii=False),
            "manual",
            source_client_id,
            event_line_id,
            "签约推进线",
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO learning_recommendations(
            id, user_id, user_name, ability_key, content_item_id, trigger_source_type, trigger_source_id,
            reason, client_id, client_name, event_line_id, event_line_name, why_now, dedupe_key, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            recommendation_id,
            "op_1",
            "顾问甲",
            "client_push",
            learning_content_id,
            "event_line",
            event_line_id,
            "签约后需要立即重挂客户主线。",
            source_client_id,
            source_client_name,
            event_line_id,
            "签约推进线",
            "现在已经进入交付前切换阶段。",
            "dedupe:event_line_transfer_scope",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO evidence_cards(
            id, client_id, scope_type, scope_id, source_type, source_id, quote, normalized_claim,
            event_line_id, fingerprint, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            source_client_id,
            "event_line",
            event_line_id,
            "manual_note",
            event_line_id,
            "签约完成后要整体切换客户归属。",
            "签约后整体切换客户归属",
            event_line_id,
            "fingerprint:event_line_transfer_scope",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO theme_clusters(
            id, client_id, scope_type, scope_id, theme_key, title, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            theme_id,
            source_client_id,
            "event_line",
            event_line_id,
            "transfer_scope",
            "签约迁移",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO conflict_groups(
            id, client_id, scope_type, scope_id, conflict_type, title, summary, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conflict_id,
            source_client_id,
            "event_line",
            event_line_id,
            "ownership",
            "归属冲突",
            "旧客户归属和新客户归属尚未统一。",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO open_questions(
            id, client_id, scope_type, scope_id, theme_key, question, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            question_id,
            source_client_id,
            "event_line",
            event_line_id,
            "transfer_scope",
            "签约后哪些资料需要一并切换？",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO sync_memory_records(
            id, client_id, scope_type, scope_id, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            sync_memory_id,
            source_client_id,
            "event_line",
            event_line_id,
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO analysis_jobs(
            id, job_type, client_id, scope_type, scope_id, status, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_job_id,
            "event_line_scan",
            source_client_id,
            "event_line",
            event_line_id,
            "completed",
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO context_packs(
            id, client_id, job_id, target_type, target_id, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            context_pack_id,
            source_client_id,
            analysis_job_id,
            "event_line",
            event_line_id,
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO runtime_run_logs(
            id, client_id, job_id, summary, created_at
        ) VALUES(?, ?, ?, ?, ?)
        """,
        (
            runtime_log_id,
            source_client_id,
            analysis_job_id,
            "事件线迁移前分析运行",
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, summary, context_pack_id, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            judgment_id,
            source_client_id,
            "event_line",
            event_line_id,
            "ownership",
            "需要把客户归属整体切换。",
            context_pack_id,
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO dna_deltas(
            id, client_id, dimension, proposed_change, summary, context_pack_id, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dna_delta_id,
            source_client_id,
            "organization_context",
            "签约完成后切换客户主线",
            "需要统一重挂客户视图。",
            context_pack_id,
            timestamp,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO approval_records(
            id, object_type, object_id, client_id, status, created_at
        ) VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            approval_context_id,
            "context_pack",
            context_pack_id,
            source_client_id,
            "approved",
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO approval_records(
            id, object_type, object_id, client_id, status, created_at
        ) VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            approval_judgment_id,
            "judgment_version",
            judgment_id,
            source_client_id,
            "approved",
            timestamp,
        ),
    )

    updated_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "primaryClientId": target_client_id,
            "syncLinkedTaskClientIds": True,
        },
    )
    assert updated_line.status_code == 200, updated_line.text
    assert updated_line.json()["primaryClientId"] == target_client_id

    handbook_row = db.fetchone("SELECT client_id FROM handbook_entries WHERE id = ?", (handbook_id,))
    assert handbook_row is not None
    assert handbook_row["client_id"] == target_client_id

    recommendation_row = db.fetchone(
        "SELECT client_id, client_name FROM learning_recommendations WHERE id = ?",
        (recommendation_id,),
    )
    assert recommendation_row is not None
    assert recommendation_row["client_id"] == target_client_id
    assert recommendation_row["client_name"] == target_client_name

    evidence_row = db.fetchone("SELECT client_id FROM evidence_cards WHERE id = ?", (evidence_id,))
    assert evidence_row is not None
    assert evidence_row["client_id"] == target_client_id

    theme_row = db.fetchone("SELECT client_id FROM theme_clusters WHERE id = ?", (theme_id,))
    assert theme_row is not None
    assert theme_row["client_id"] == target_client_id

    conflict_row = db.fetchone("SELECT client_id FROM conflict_groups WHERE id = ?", (conflict_id,))
    assert conflict_row is not None
    assert conflict_row["client_id"] == target_client_id

    question_row = db.fetchone("SELECT client_id FROM open_questions WHERE id = ?", (question_id,))
    assert question_row is not None
    assert question_row["client_id"] == target_client_id

    sync_memory_row = db.fetchone("SELECT client_id FROM sync_memory_records WHERE id = ?", (sync_memory_id,))
    assert sync_memory_row is not None
    assert sync_memory_row["client_id"] == target_client_id

    analysis_job_row = db.fetchone("SELECT client_id FROM analysis_jobs WHERE id = ?", (analysis_job_id,))
    assert analysis_job_row is not None
    assert analysis_job_row["client_id"] == target_client_id

    context_pack_row = db.fetchone("SELECT client_id FROM context_packs WHERE id = ?", (context_pack_id,))
    assert context_pack_row is not None
    assert context_pack_row["client_id"] == target_client_id

    runtime_log_row = db.fetchone("SELECT client_id FROM runtime_run_logs WHERE id = ?", (runtime_log_id,))
    assert runtime_log_row is not None
    assert runtime_log_row["client_id"] == target_client_id

    judgment_row = db.fetchone("SELECT client_id FROM judgment_versions WHERE id = ?", (judgment_id,))
    assert judgment_row is not None
    assert judgment_row["client_id"] == target_client_id

    dna_delta_row = db.fetchone("SELECT client_id FROM dna_deltas WHERE id = ?", (dna_delta_id,))
    assert dna_delta_row is not None
    assert dna_delta_row["client_id"] == target_client_id

    approval_context_row = db.fetchone("SELECT client_id FROM approval_records WHERE id = ?", (approval_context_id,))
    assert approval_context_row is not None
    assert approval_context_row["client_id"] == target_client_id

    approval_judgment_row = db.fetchone("SELECT client_id FROM approval_records WHERE id = ?", (approval_judgment_id,))
    assert approval_judgment_row is not None
    assert approval_judgment_row["client_id"] == target_client_id


def test_event_line_clarification_draft_can_be_generated_from_conversation(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="事件线聊天整理客户")

    created = client.post(
        "/api/v1/event-lines",
        json={
            "name": "客户确认推进线",
            "kind": "project_line",
            "primaryClientId": client_id,
        },
    )
    assert created.status_code == 200, created.text
    event_line_id = created.json()["id"]

    drafted = client.post(
        f"/api/v1/event-lines/{event_line_id}/clarification-draft",
        json={
            "conversationText": (
                "今天和客户沟通后，先统一了这一轮方案口径。"
                "现在还在等客户确认最终版本，资料也没补齐。"
                "下一步是明天下午把会后动作整理好并同步给客户。"
                "刚刚决定先补资料，再推进下一轮方案沟通。"
            ),
        },
    )
    assert drafted.status_code == 200, drafted.text
    payload = drafted.json()
    assert payload["summary"]
    assert payload["stage"] in {"等待确认", "资料补齐中", "执行推进中"}
    assert "沟通" in payload["intent"] or "推进" in payload["intent"]
    assert "确认" in payload["currentBlocker"] or "资料" in payload["currentBlocker"]
    assert "同步给客户" in payload["nextStep"] or "下一步" in payload["nextStep"]
    assert "先补资料" in payload["recentDecision"] or "推进下一轮方案沟通" in payload["recentDecision"]
    assert payload["confidence"] in {"low", "medium", "high"}


def test_task_action_os_fields_persist_locally(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="任务对象层收口测试客户")

    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "业务扩展推进线",
            "kind": "project_line",
            "primaryClientId": client_id,
            "businessCategory": "业务扩展",
            "currentBlocker": "客户侧还没确认合作边界。",
            "nextStep": "整理确认项并约下一轮沟通。",
            "recentDecision": "先收口范围，再决定报价方式。",
            "evidenceCount": 2,
        },
    )
    assert event_line.status_code == 200, event_line.text
    event_line_id = event_line.json()["id"]

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "推进黄河合作确认",
            "description": "继续围绕合作范围做确认和整理。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
            "businessCategory": "业务扩展",
            "currentBlocker": "客户侧还没确认合作边界。",
            "nextAction": "把确认项发给对方并锁时间。",
            "recentDecision": "先收口范围，再决定报价方式。",
            "evidenceCount": 3,
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["businessCategory"] == "业务扩展"
    assert payload["currentBlocker"] == "客户侧还没确认合作边界。"
    assert payload["nextAction"] == "把确认项发给对方并锁时间。"
    assert payload["recentDecision"] == "先收口范围，再决定报价方式。"
    assert payload["evidenceCount"] == 3

    updated = client.patch(
        f"/api/v1/tasks/{payload['id']}",
        json={
            "businessCategory": "正式交付",
            "currentBlocker": "客户已确认合作边界，转入交付准备。",
            "nextAction": "输出首版交付清单。",
            "recentDecision": "先交付一版结构化清单。",
            "evidenceCount": 5,
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["businessCategory"] == "正式交付"
    assert updated_payload["currentBlocker"] == "客户已确认合作边界，转入交付准备。"
    assert updated_payload["nextAction"] == "输出首版交付清单。"
    assert updated_payload["recentDecision"] == "先交付一版结构化清单。"
    assert updated_payload["evidenceCount"] == 5

    row = client.app.state.app_state.db.fetchone(
        "SELECT business_category, current_blocker, next_action, recent_decision, evidence_count FROM tasks WHERE id = ?",
        (payload["id"],),
    )
    assert row is not None
    assert row["business_category"] == "正式交付"
    assert row["current_blocker"] == "客户已确认合作边界，转入交付准备。"
    assert row["next_action"] == "输出首版交付清单。"
    assert row["recent_decision"] == "先交付一版结构化清单。"
    assert row["evidence_count"] == 5


def test_personal_task_scope_mode_persists_locally_and_clears_shared_refs(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="个人任务隔离测试客户")
    event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "不该挂上的共享事件线",
            "kind": "project_line",
            "primaryClientId": client_id,
        },
    )
    assert event_line.status_code == 200, event_line.text

    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "和朋友见面",
            "description": "个人安排，不进入组织任务线。",
            "priority": "normal",
            "listId": "list-0",
            "scopeMode": "PERSONAL_ONLY",
            "clientId": client_id,
            "eventLineId": event_line.json()["id"],
            "projectModuleId": "module_should_clear",
            "projectFlowId": "flow_should_clear",
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["scopeMode"] == "PERSONAL_ONLY"
    assert payload["clientId"] in ("", None)
    assert payload["eventLineId"] in ("", None)
    assert payload["projectModuleId"] in ("", None)
    assert payload["projectFlowId"] in ("", None)

    row = client.app.state.app_state.db.fetchone(
        "SELECT scope_mode, client_id, event_line_id, project_module_id, project_flow_id FROM tasks WHERE id = ?",
        (payload["id"],),
    )
    assert row["scope_mode"] == "PERSONAL_ONLY"
    assert row["client_id"] is None
    assert row["event_line_id"] is None
    assert row["project_module_id"] is None
    assert row["project_flow_id"] is None


def test_strategic_cockpit_defaults_to_read_only_without_ceo(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略页只读客户")

    response = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["permission"]["canEdit"] is False
    assert "CEO" in payload["permission"]["notice"]
    assert payload["headline"]["coreBreakthrough"]["value"]
    assert payload["readiness"]["status"] in {"ready", "insufficient"}


def test_strategic_cockpit_ceo_confirm_persists_snapshot(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略页 CEO 客户")
    session_user = seed_session_user(client, user_id="user_ceo", full_name="CEO")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id=session_user["id"])

    confirm_response = client.post(
        f"/api/v1/clients/{client_id}/strategic-cockpit/confirm",
        json={
            "weekSummary": "本周已经把业务盘点会变成正式经营入口。",
            "mainContradiction": "业务推进动作已有，但关键判断还没有稳定压成经营语言。",
            "coreBreakthrough": "围绕客户盘点会收敛核心问题，并把下周动作挂上主线。",
            "focusItems": ["确认本周期主问题", "让周会只围绕一条主线", "补齐关键资料"],
        },
    )
    assert confirm_response.status_code == 200, confirm_response.text
    payload = confirm_response.json()
    assert payload["permission"]["canEdit"] is True
    assert payload["headline"]["weekSummary"]["status"] == "confirmed"
    assert payload["headline"]["weekSummary"]["value"] == "本周已经把业务盘点会变成正式经营入口。"
    assert payload["headline"]["mainContradiction"]["status"] == "confirmed"
    assert payload["headline"]["coreBreakthrough"]["value"] == "围绕客户盘点会收敛核心问题，并把下周动作挂上主线。"
    assert payload["headline"]["focusStatus"] == "confirmed"
    assert payload["headline"]["focusItems"][0] == "确认本周期主问题"

    row = client.app.state.app_state.db.fetchone(
        "SELECT week_summary, main_contradiction, core_breakthrough FROM strategic_cockpit_snapshots WHERE client_id = ?",
        (client_id,),
    )
    assert row is not None
    assert row["week_summary"] == "本周已经把业务盘点会变成正式经营入口。"
    assert row["main_contradiction"] == "业务推进动作已有，但关键判断还没有稳定压成经营语言。"
    assert row["core_breakthrough"] == "围绕客户盘点会收敛核心问题，并把下周动作挂上主线。"


def test_strategic_cockpit_confirm_rejects_non_ceo(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略页非 CEO 客户")
    seed_session_user(client, user_id="user_member", full_name="普通成员")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id="user_ceo")

    confirm_response = client.post(
        f"/api/v1/clients/{client_id}/strategic-cockpit/confirm",
        json={
            "weekSummary": "不应写入",
            "mainContradiction": "不应写入",
            "coreBreakthrough": "不应写入",
            "focusItems": ["不应写入"],
        },
    )
    assert confirm_response.status_code == 403, confirm_response.text


def test_strategic_cockpit_relationship_task_needs_contextual_description(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="关系推进背景测试客户")

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟敦和林红吃饭",
            "desc": "",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    first_snapshot = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert first_snapshot.status_code == 200, first_snapshot.text
    first_payload = first_snapshot.json()
    assert any("只写了动作名" in item for item in first_payload["readiness"]["gaps"])

    updated_task = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "desc": "敦和基金会的林红负责合作拓展，当前双方正在讨论联合研究，这次见面希望确认合作边界和下次方案节奏。",
        },
    )
    assert updated_task.status_code == 200, updated_task.text

    second_snapshot = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert second_snapshot.status_code == 200, second_snapshot.text
    second_payload = second_snapshot.json()
    assert not any("只写了动作名" in item for item in second_payload["readiness"]["gaps"])


def test_strategic_meeting_pack_writes_into_meeting_object(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略周会草稿客户")
    session_user = seed_session_user(client, user_id="user_ceo", full_name="CEO")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id=session_user["id"])

    response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack")
    assert response.status_code == 200, response.text
    payload = response.json()
    meeting = payload["meeting"]
    assert meeting["title"] == "战略周会草稿客户 周盘点会"
    assert "必须澄清的问题" in meeting["notes"]
    assert meeting["agendaItems"]

    source_row = client.app.state.app_state.db.fetchone(
        "SELECT title, content_text FROM meeting_sources WHERE meeting_id = ?",
        (meeting["id"],),
    )
    assert source_row is not None
    assert source_row["title"] == "战略陪伴周会清单草案"
    assert "建议议程" in source_row["content_text"]


def test_strategic_meeting_pack_apply_updates_cockpit_snapshot(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略周会回填客户")
    session_user = seed_session_user(client, user_id="user_ceo", full_name="CEO")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id=session_user["id"])

    meeting_response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack")
    assert meeting_response.status_code == 200, meeting_response.text
    meeting_id = meeting_response.json()["meeting"]["id"]

    ingest_response = client.post(
        f"/api/v1/clients/{client_id}/meetings/{meeting_id}/ingest",
        json={
            "transcriptText": "本周我们决定先把客户盘点会固定下来，并把关键阻塞收敛成一条主线。",
            "notes": "决定先把客户盘点会固定下来。庆华负责下周推进。当前还缺关键资料待补。",
        },
    )
    assert ingest_response.status_code == 200, ingest_response.text

    extract_response = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/extract")
    assert extract_response.status_code == 200, extract_response.text

    apply_response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack/{meeting_id}/apply")
    assert apply_response.status_code == 200, apply_response.text
    payload = apply_response.json()
    assert payload["headline"]["weekSummary"]["status"] == "confirmed"
    assert payload["headline"]["mainContradiction"]["status"] == "confirmed"
    assert payload["headline"]["coreBreakthrough"]["status"] == "confirmed"
    assert payload["headline"]["focusStatus"] == "confirmed"

    row = client.app.state.app_state.db.fetchone(
        "SELECT week_summary, main_contradiction, core_breakthrough FROM strategic_cockpit_snapshots WHERE client_id = ?",
        (client_id,),
    )
    assert row is not None
    assert row["week_summary"]
    assert row["main_contradiction"]
    assert row["core_breakthrough"]


def test_strategic_meeting_pack_apply_updates_event_line_memory(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略周会事件线回写客户")
    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "敦和合作推进线",
            "kind": "project_line",
            "status": "active",
            "summary": "围绕敦和合作推进持续补齐信息并确认节奏。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    session_user = seed_session_user(client, user_id="user_ceo", full_name="CEO")
    seed_cloud_token(client)
    stub_cloud_strategic_services(monkeypatch, leader_user_id=session_user["id"])

    meeting_response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack")
    assert meeting_response.status_code == 200, meeting_response.text
    meeting_id = meeting_response.json()["meeting"]["id"]

    client.app.state.app_state.db.execute(
        "INSERT INTO decisions(id, meeting_id, summary, created_at) VALUES(?, ?, ?, ?)",
        (
            app_main.new_id("decision"),
            meeting_id,
            "先确认敦和合作边界，再推进下次正式方案沟通。",
            "2026-03-22T10:00:00",
        ),
    )

    apply_response = client.post(f"/api/v1/clients/{client_id}/strategic-cockpit/meeting-pack/{meeting_id}/apply")
    assert apply_response.status_code == 200, apply_response.text

    memory_response = client.get(f"/api/v1/event-lines/{event_line_id}/memory")
    assert memory_response.status_code == 200, memory_response.text
    memory_payload = memory_response.json()
    assert "先确认敦和合作边界" in memory_payload["eventLineMemorySnapshot"]["recentDecision"]


def test_feishu_meeting_launch_and_minutes_writeback_flow(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="飞书纪要测试客户")
    sent_messages: list[dict] = []

    monkeypatch.setattr(app_main, "fetch_tenant_access_token", lambda **kwargs: ("tenant_token", {"code": 0}))

    def fake_send_text_message(**kwargs):
        sent_messages.append(kwargs)
        return {"code": 0}

    monkeypatch.setattr(app_main, "send_text_message", fake_send_text_message)

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    launch_response = client.post(
        f"/api/v1/clients/{client_id}/meetings/launch-feishu",
        json={
            "title": "日慈基金会项目推进会",
            "scheduledAt": "2026-03-18T14:00",
            "sourceTaskId": "task_demo_1",
        },
    )
    assert launch_response.status_code == 200, launch_response.text
    launch_payload = launch_response.json()
    assert launch_payload["deliveryStatus"] == "sent"
    assert launch_payload["deliveryMode"] == "configured_receiver"
    assert "纪要回写" in launch_payload["commandHint"]
    meeting_id = launch_payload["meeting"]["id"]
    assert sent_messages and meeting_id in sent_messages[0]["text"]

    event_response = client.post(
        "/api/v1/channels/feishu/events",
        json={
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_type": "user"},
                "message": {
                    "chat_id": "chat_ops_room",
                    "message_type": "text",
                    "content": json.dumps(
                        {
                            "text": (
                                f"纪要回写 {meeting_id}\n"
                                "本次会议决定先推进资料补齐。"
                                "庆华负责跟进客户反馈。"
                                "当前存在资源风险。"
                            )
                        },
                        ensure_ascii=False,
                    ),
                },
            },
        },
    )
    assert event_response.status_code == 200, event_response.text
    assert event_response.json()["ok"] is True

    meeting_detail = client.get(f"/api/v1/clients/{client_id}/meetings/{meeting_id}")
    assert meeting_detail.status_code == 200, meeting_detail.text
    meeting_payload = meeting_detail.json()
    assert meeting_payload["stage"] == "extracted"
    assert "资料补齐" in meeting_payload["notes"]
    assert len(meeting_payload["actionItems"]) >= 1
    assert len(meeting_payload["decisions"]) >= 1
    assert len(meeting_payload["risks"]) >= 1
    assert len(sent_messages) >= 2


def test_feishu_user_binding_callback_persists_current_user(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    session_user = seed_session_user(client, user_id="user_feishu", email="guyuan@klngo.org", full_name="顾源")
    seed_cloud_token(client)
    stub_cloud_auth_me(monkeypatch, session_user)

    start_response = client.post("/api/v1/settings/feishu-user-binding/start")
    assert start_response.status_code == 200, start_response.text
    start_payload = start_response.json()
    assert "open.feishu.cn" in start_payload["authorizeUrl"]
    assert start_payload["state"]
    assert start_payload["callbackUrl"].endswith("/api/v1/auth/feishu/callback")
    assert start_payload["qrReady"] is False
    assert start_payload["qrBlockedReason"]

    monkeypatch.setattr(app_main, "fetch_app_access_token", lambda **kwargs: ("app_token", {"code": 0}))
    monkeypatch.setattr(
        app_main,
        "exchange_authorization_code",
        lambda **kwargs: {
            "access_token": "user_access_token",
            "open_id": "ou_bound_user",
            "user_id": "feishu_user_1",
            "tenant_key": "tenant_1",
        },
    )
    monkeypatch.setattr(
        app_main,
        "fetch_user_info",
        lambda **kwargs: {
            "open_id": "ou_bound_user",
            "user_id": "feishu_user_1",
            "name": "顾源",
            "email": "guyuan@klngo.org",
            "tenant_key": "tenant_1",
        },
    )

    callback_response = client.get(
        "/api/v1/auth/feishu/callback",
        params={"state": start_payload["state"], "code": "authorization_code_1"},
    )
    assert callback_response.status_code == 200, callback_response.text
    assert "飞书账号绑定成功" in callback_response.text

    binding_response = client.get("/api/v1/settings/feishu-user-binding")
    assert binding_response.status_code == 200, binding_response.text
    binding_payload = binding_response.json()
    assert binding_payload["linked"] is True
    assert binding_payload["openId"] == "ou_bound_user"
    assert binding_payload["email"] == "guyuan@klngo.org"
    assert binding_payload["name"] == "顾源"


def test_feishu_user_binding_start_uses_configured_public_callback(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
            "userBindingCallbackUrl": "https://workbench.yiyu.example.com/api/v1/auth/feishu/callback",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    session_user = seed_session_user(client, user_id="user_feishu_callback", email="guyuan@klngo.org", full_name="顾源")
    seed_cloud_token(client)
    stub_cloud_auth_me(monkeypatch, session_user)

    start_response = client.post("/api/v1/settings/feishu-user-binding/start")
    assert start_response.status_code == 200, start_response.text
    payload = start_response.json()
    assert payload["callbackUrl"] == "https://workbench.yiyu.example.com/api/v1/auth/feishu/callback"
    assert payload["qrReady"] is True
    assert payload["qrBlockedReason"] is None


def test_feishu_user_binding_uses_cloud_relay_for_mobile_scan(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client.app.state.app_state.cloud_api_url = "https://cloud.yiyu.example.com"
    client.app.state.app_state.db.set_setting("cloud_access_token", "token_demo")

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    cloud_user_payload = {
        "id": "user_feishu_cloud",
        "organizationId": "org_1",
        "email": "guyuan@klngo.org",
        "fullName": "顾源",
        "primaryRole": "employee",
        "accountStatus": "approved",
    }
    seen_states: list[str] = []

    def fake_cloud_request(method: str, url: str, **kwargs):
        if url == "https://cloud.yiyu.example.com/api/v1/auth/me":
            return httpx.Response(200, json=cloud_user_payload)
        if url == "https://cloud.yiyu.example.com/api/v1/integrations/feishu/user-binding/sessions" and method.upper() == "POST":
            payload = kwargs.get("json") or {}
            seen_states.append(str(payload.get("state") or ""))
            return httpx.Response(200, json={"message": "ok"})
        if url.startswith("https://cloud.yiyu.example.com/api/v1/integrations/feishu/user-binding/sessions/") and method.upper() == "GET":
            state_token = url.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "state": state_token,
                    "status": "authorized",
                    "expiresAt": "2099-01-01T00:00:00",
                    "authorizedAt": "2099-01-01T00:00:00",
                    "code": "authorization_code_cloud",
                },
            )
        if url.startswith("https://cloud.yiyu.example.com/api/v1/integrations/feishu/user-binding/sessions/") and method.upper() == "DELETE":
            return httpx.Response(200, json={"message": "ok"})
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    start_response = client.post("/api/v1/settings/feishu-user-binding/start")
    assert start_response.status_code == 200, start_response.text
    start_payload = start_response.json()
    assert start_payload["callbackUrl"] == "https://cloud.yiyu.example.com/api/v1/integrations/feishu/user-binding/callback"
    assert start_payload["qrReady"] is True
    assert start_payload["qrBlockedReason"] is None
    assert seen_states == [start_payload["state"]]

    monkeypatch.setattr(app_main, "fetch_app_access_token", lambda **kwargs: ("app_token", {"code": 0}))
    monkeypatch.setattr(
        app_main,
        "exchange_authorization_code",
        lambda **kwargs: {
            "access_token": "user_access_token",
            "open_id": "ou_bound_user_cloud",
            "user_id": "feishu_user_cloud",
            "tenant_key": "tenant_1",
        },
    )
    monkeypatch.setattr(
        app_main,
        "fetch_user_info",
        lambda **kwargs: {
            "open_id": "ou_bound_user_cloud",
            "user_id": "feishu_user_cloud",
            "name": "顾源",
            "email": "guyuan@klngo.org",
            "tenant_key": "tenant_1",
        },
    )

    binding_response = client.get("/api/v1/settings/feishu-user-binding")
    assert binding_response.status_code == 200, binding_response.text
    binding_payload = binding_response.json()
    assert binding_payload["linked"] is True
    assert binding_payload["openId"] == "ou_bound_user_cloud"
    assert binding_payload["email"] == "guyuan@klngo.org"


def test_auth_me_keeps_cached_session_when_cloud_is_temporarily_unavailable(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    session_user = seed_session_user(
        client,
        user_id="user_cached",
        email="guyuan@klngo.org",
        full_name="顾源源",
        primary_role="admin",
    )
    seed_cloud_token(client, "token_cached")
    client.app.state.app_state.db.set_setting("cloud_refresh_token", "refresh_cached")

    def fake_cloud_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url == "http://127.0.0.1:47830/api/v1/auth/me":
            raise httpx.ConnectError("cloud unavailable", request=httpx.Request(method, url))
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["user"]["id"] == session_user["id"]
    assert payload["user"]["email"] == session_user["email"]
    assert "已保留当前设备上的登录状态" in (payload["message"] or "")


def test_feishu_meeting_launch_prefers_bound_user_over_global_receiver(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="飞书绑定优先级测试客户")
    sent_messages: list[dict] = []

    settings_response = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test_app",
            "appSecret": "cli_test_secret",
            "receiverId": "chat_ops_room",
            "receiveIdType": "chat_id",
            "botName": "会议机器人",
        },
    )
    assert settings_response.status_code == 200, settings_response.text

    session_user = seed_session_user(client, user_id="user_feishu_bound", email="guyuan@klngo.org", full_name="顾源")
    client.app.state.app_state.db.set_setting(
        f"settings.feishu_user_binding:{session_user['id']}",
        json.dumps(
            {
                "linked": True,
                "readyForAuthorization": True,
                "appId": "cli_test_app",
                "userId": session_user["id"],
                "openId": "ou_bound_priority",
                "name": "顾源",
                "email": "guyuan@klngo.org",
                "tenantKey": "tenant_1",
                "boundAt": "2026-03-18T10:00:00",
                "lastVerifiedAt": "2026-03-18T10:05:00",
            },
            ensure_ascii=False,
        ),
    )

    monkeypatch.setattr(app_main, "fetch_tenant_access_token", lambda **kwargs: ("tenant_token", {"code": 0}))

    def fake_send_text_message(**kwargs):
        sent_messages.append(kwargs)
        return {"code": 0}

    monkeypatch.setattr(app_main, "send_text_message", fake_send_text_message)

    launch_response = client.post(
        f"/api/v1/clients/{client_id}/meetings/launch-feishu",
        json={
            "title": "顾源飞书绑定会议",
            "scheduledAt": "2026-03-18T16:00",
        },
    )
    assert launch_response.status_code == 200, launch_response.text
    launch_payload = launch_response.json()
    assert launch_payload["deliveryStatus"] == "sent"
    assert launch_payload["deliveryMode"] == "bound_user"
    assert launch_payload["deliveryTarget"] == "顾源"
    assert sent_messages[0]["receive_id_type"] == "open_id"
    assert sent_messages[0]["receive_id"] == "ou_bound_priority"


def test_startup_requeues_stale_knowledge_jobs(tmp_path: Path):
    app = make_app_only(tmp_path)
    db = app.state.app_state.db
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_stale', '僵尸任务客户', '僵尸任务客户', '公益', '内部陪伴', '测试僵尸任务恢复', '推进中', '2026-03-13T00:00:00', '2026-03-13T00:00:00')
        """
    )
    db.execute(
        """
        INSERT INTO knowledge_jobs(
            id, client_id, job_type, status, payload_json, total_items, processed_items,
            last_error, created_at, started_at, finished_at, updated_at
        )
        VALUES('kjob_stale', 'client_stale', 'rebuild_client_knowledge', 'running', '{}', 1, 0, NULL, '2026-03-13T00:00:00', '2026-03-13T00:00:01', NULL, '2026-03-13T00:00:01')
        """
    )
    client = TestClient(app)
    client.__enter__()
    try:
        row = db.fetchone("SELECT status, last_error FROM knowledge_jobs WHERE id = 'kjob_stale'")
        assert row is not None
        assert row["status"] in {"queued", "running"}
        assert row["last_error"] == "worker_restart_requeued"
    finally:
        client.__exit__(None, None, None)


def test_settings_accept_qwen_provider(tmp_path: Path):
    client = make_client(tmp_path)

    updated = client.post(
        "/api/v1/settings",
        json={
            "aiProvider": "qwen",
            "aiModel": "qwen3.5-plus",
        },
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["settings"]["aiProvider"] == "qwen"
    assert payload["settings"]["aiModel"] == "qwen3.5-plus"


def test_feishu_bot_settings_can_be_saved_without_secret(tmp_path: Path, monkeypatch):
    class BrokenKeychain:
        def __init__(self, service_name: str = "", account_name: str = "default"):
            self.service_name = service_name
            self.account_name = account_name

        def get_api_key(self) -> str:
            raise RuntimeError("keychain disabled for tests")

    monkeypatch.setattr(app_main, "MacOSKeychainSecretStore", BrokenKeychain)
    client = make_client(tmp_path)

    initial = client.get("/api/v1/settings/feishu-bot")
    assert initial.status_code == 200
    assert initial.json()["hasAppSecret"] is False

    saved = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test",
            "receiveIdType": "email",
            "receiverId": "owner@example.com",
            "botName": "罗茜茜",
        },
    )
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["appId"] == "cli_test"
    assert payload["receiveIdType"] == "email"
    assert payload["receiverId"] == "owner@example.com"
    assert payload["botName"] == "罗茜茜"
    assert payload["hasAppSecret"] is False
    assert payload["ready"] is False


def test_feishu_bot_connect_and_send_test_message(tmp_path: Path, monkeypatch):
    class BrokenKeychain:
        def __init__(self, service_name: str = "", account_name: str = "default"):
            self.service_name = service_name
            self.account_name = account_name

        def get_api_key(self) -> str:
            raise RuntimeError("keychain disabled for tests")

    monkeypatch.setattr(app_main, "MacOSKeychainSecretStore", BrokenKeychain)
    client = make_client(tmp_path)

    sent: dict = {}

    def fake_fetch_tenant_access_token(*, app_id: str, app_secret: str, transport=None):
        assert app_id == "cli_test"
        assert app_secret == "secret_test"
        return "tenant_token_test", {"tenant_access_token": "tenant_token_test"}

    def fake_send_text_message(*, tenant_access_token: str, receive_id_type: str, receive_id: str, text: str, transport=None):
        sent.update(
            {
                "tenant_access_token": tenant_access_token,
                "receive_id_type": receive_id_type,
                "receive_id": receive_id,
                "text": text,
            }
        )
        return {"code": 0, "msg": "success"}

    monkeypatch.setattr(app_main, "fetch_tenant_access_token", fake_fetch_tenant_access_token)
    monkeypatch.setattr(app_main, "send_text_message", fake_send_text_message)

    connected = client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test",
            "receiveIdType": "email",
            "receiverId": "owner@example.com",
            "botName": "罗茜茜",
            "appSecret": "secret_test",
            "sendTestMessage": True,
            "testMessage": "罗茜茜测试消息",
        },
    )
    assert connected.status_code == 200
    payload = connected.json()
    assert payload["hasAppSecret"] is True
    assert payload["ready"] is True
    assert payload["lastConnectionStatus"] == "success"
    assert payload["lastTestMessageAt"]
    assert sent == {
        "tenant_access_token": "tenant_token_test",
        "receive_id_type": "email",
        "receive_id": "owner@example.com",
        "text": "罗茜茜测试消息",
    }


def test_system_admin_settings_accept_and_clear_brand_logo(tmp_path: Path):
    client = make_client(tmp_path)
    png_data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )

    saved = client.post(
        "/api/v1/settings/system-admin",
        json={"brandLogoDataUrl": png_data_url},
    )
    assert saved.status_code == 200
    assert saved.json()["brandLogoDataUrl"] == png_data_url

    fetched = client.get("/api/v1/settings/system-admin")
    assert fetched.status_code == 200
    assert fetched.json()["brandLogoDataUrl"] == png_data_url

    cleared = client.post(
        "/api/v1/settings/system-admin",
        json={"brandLogoDataUrl": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["brandLogoDataUrl"] is None


def test_system_admin_settings_reject_non_png_brand_logo(tmp_path: Path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/v1/settings/system-admin",
        json={"brandLogoDataUrl": "data:image/jpeg;base64,abcd"},
    )
    assert response.status_code == 400
    assert "只支持 PNG" in response.text


def test_feishu_events_url_verification_returns_challenge(tmp_path: Path, monkeypatch):
    class BrokenKeychain:
        def __init__(self, service_name: str = "", account_name: str = "default"):
            self.service_name = service_name
            self.account_name = account_name

        def get_api_key(self) -> str:
            raise RuntimeError("keychain disabled for tests")

    monkeypatch.setattr(app_main, "MacOSKeychainSecretStore", BrokenKeychain)
    client = make_client(tmp_path)

    response = client.post(
        "/api/v1/channels/feishu/events",
        json={"type": "url_verification", "challenge": "challenge_token_demo"},
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge_token_demo"}


def test_feishu_events_reply_to_text_message(tmp_path: Path, monkeypatch):
    class BrokenKeychain:
        def __init__(self, service_name: str = "", account_name: str = "default"):
            self.service_name = service_name
            self.account_name = account_name

        def get_api_key(self) -> str:
            raise RuntimeError("keychain disabled for tests")

    monkeypatch.setattr(app_main, "MacOSKeychainSecretStore", BrokenKeychain)
    client = make_client(tmp_path)

    client.post(
        "/api/v1/settings/feishu-bot",
        json={
            "appId": "cli_test",
            "botName": "罗茜茜",
            "appSecret": "secret_test",
        },
    )

    sent: dict = {}

    def fake_fetch_tenant_access_token(*, app_id: str, app_secret: str, transport=None):
        assert app_id == "cli_test"
        assert app_secret == "secret_test"
        return "tenant_token_test", {"tenant_access_token": "tenant_token_test"}

    def fake_send_text_message(*, tenant_access_token: str, receive_id_type: str, receive_id: str, text: str, transport=None):
        sent.update(
            {
                "tenant_access_token": tenant_access_token,
                "receive_id_type": receive_id_type,
                "receive_id": receive_id,
                "text": text,
            }
        )
        return {"code": 0, "msg": "success"}

    monkeypatch.setattr(app_main, "fetch_tenant_access_token", fake_fetch_tenant_access_token)
    monkeypatch.setattr(app_main, "send_text_message", fake_send_text_message)

    response = client.post(
        "/api/v1/channels/feishu/events",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_type": "user"},
                "message": {
                    "chat_id": "oc_chat_demo",
                    "message_type": "text",
                    "content": "{\"text\":\"你是谁？\"}",
                },
            },
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent == {
        "tenant_access_token": "tenant_token_test",
        "receive_id_type": "chat_id",
        "receive_id": "oc_chat_demo",
        "text": "我是罗茜茜。飞书入站链路刚接通，现在先支持固定回复；客户上下文问答还没接上。",
    }


def test_chat_start_returns_loading_then_poll_completes(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "问答异步测试客户")
    state = client.app.state.app_state

    def fake_bundle(client_id_arg: str, prompt: str) -> RetrievalBundle:
        assert client_id_arg == client_id
        return RetrievalBundle(
            citations=[],
            coverage=0.0,
            retrieval_summary={
                "masterHitCount": 0,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 0,
                "drillthroughUsed": False,
                "matchedTerms": [],
            },
            context_text="",
            matched_terms=[],
            failure_reason="没有命中当前资料",
        )

    def fake_general(prompt: str, note: str = "", *, subject_name: str = ""):
        return app_main.AiStructuredResponse(
            content=f"当前资料暂无相关内容，但基于通用知识可以先给出一版关于{subject_name or '当前客户'}的概览回答。",
            judgment=f"这是关于{subject_name or '当前客户'}的通用知识回答，不是客户资料结论。",
            analysis="这是一家面向公益服务的组织，通常围绕教育、救助、社区支持等方向开展工作。",
            actions="下一步建议：补充机构介绍、项目简介与对外材料。",
            timeline="补充资料后可再次生成更完整回答。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda db, data_dir, client_id_arg, prompt: fake_bundle(client_id_arg, prompt))
    monkeypatch.setattr(state.ai, "generate_general_fallback", fake_general)

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "什么是公益组织？请简要解释。"},
    )
    assert started.status_code == 200
    payload = started.json()
    assert payload["assistantMessage"]["status"] == "loading"
    message_id = payload["assistantMessage"]["id"]

    deadline = time.time() + 20.0
    final_payload = None
    while time.time() < deadline:
        polled = client.get(f"/api/v1/clients/{client_id}/workspace/chat/messages/{message_id}")
        assert polled.status_code == 200
        final_payload = polled.json()
        if final_payload["status"] == "success":
            break
        time.sleep(0.1)

    assert final_payload is not None
    assert final_payload["status"] == "success"
    assert final_payload["llmInvoked"] is True
    assert final_payload["answerMode"] == "general_answer"
    assert "问答异步测试客户" in final_payload["content"]


def test_chat_thread_detail_returns_only_selected_thread_messages(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "线程隔离测试客户")

    first_prompt = "线程一：机构定位怎么理解？"
    second_prompt = "线程二：团队状态怎么看？"

    first_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": first_prompt},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": second_prompt},
    )
    assert second_response.status_code == 200

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    workspace_payload = workspace.json()
    first_thread = next(thread for thread in workspace_payload["threads"] if thread["title"] == first_prompt[:16])
    second_thread = next(thread for thread in workspace_payload["threads"] if thread["title"] == second_prompt[:16])
    assert first_thread["id"] != second_thread["id"]

    first_thread_detail = client.get(f"/api/v1/clients/{client_id}/workspace/chat/threads/{first_thread['id']}")
    assert first_thread_detail.status_code == 200
    first_payload = first_thread_detail.json()

    assert first_payload["thread"]["id"] == first_thread["id"]
    assert {message["threadId"] for message in first_payload["messages"]} == {first_thread["id"]}
    assert [message["content"] for message in first_payload["messages"] if message["role"] == "user"] == [first_prompt]
    assert second_prompt not in [message["content"] for message in first_payload["messages"] if message["role"] == "user"]

    second_thread_detail = client.get(f"/api/v1/clients/{client_id}/workspace/chat/threads/{second_thread['id']}")
    assert second_thread_detail.status_code == 200
    second_payload = second_thread_detail.json()
    assert [message["content"] for message in second_payload["messages"] if message["role"] == "user"] == [second_prompt]


def test_demo_data_can_be_loaded_on_demand(tmp_path: Path):
    client = make_client(tmp_path)

    before = client.get("/api/v1/settings")
    assert before.status_code == 200
    assert before.json()["settings"]["demoDataLoaded"] is False

    loaded = client.post("/api/v1/settings/demo-data/load")
    assert loaded.status_code == 200
    assert loaded.json()["loaded"] is True
    assert loaded.json()["clients"] == 2

    clients = client.get("/api/v1/clients")
    assert clients.status_code == 200
    assert {item["name"] for item in clients.json()} == {"为爱黔行", "星辰科技"}

    cleared = client.post("/api/v1/settings/demo-data/clear")
    assert cleared.status_code == 200
    assert cleared.json()["loaded"] is False
    assert client.get("/api/v1/clients").json() == []


def test_client_meeting_publish_writes_task(tmp_path: Path):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/clients",
        json={
            "name": "测试客户",
            "alias": "测试",
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于 API 烟雾测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    client_id = created.json()["id"]

    meeting = client.post(f"/api/v1/clients/{client_id}/meetings", json={"title": "本周推进会"})
    assert meeting.status_code == 200
    meeting_id = meeting.json()["meeting"]["id"]

    ingest = client.post(
        f"/api/v1/clients/{client_id}/meetings/{meeting_id}/ingest",
        json={"transcriptText": "决定本周由庆华负责补齐方案，跟进捐赠人反馈。", "notes": "待确认时间点。"},
    )
    assert ingest.status_code == 200

    extract = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/extract")
    assert extract.status_code == 200
    assert len(extract.json()["meeting"]["actionItems"]) >= 1

    resolve = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/resolve")
    assert resolve.status_code == 200

    publish = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/publish")
    assert publish.status_code == 200

    tasks = client.get("/api/v1/tasks")
    task_items = tasks.json()["tasks"]
    assert any(task["sourceId"] == meeting_id for task in task_items)


def test_topics_promote_to_task(tmp_path: Path):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "测试雷达",
            "prompt": "验证候选晋升链路",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "测试候选",
            "summary": "将候选分别转为任务和成长手册。",
            "source": "测试",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]

    to_task = client.post(f"/api/v1/topics/candidates/{candidate_id}/promote-task")
    assert to_task.status_code == 200
    assert to_task.json()["sourceType"] == "topic_candidate"


def test_topics_task_plan_and_batch_promote(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "资助机会",
            "prompt": "关注公益组织可申请的资助信息。",
            "timeRange": "7_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "国际基金会开放资助申请",
            "summary": "某国际基金会面向公益组织开放资助申请，需提交申请表、机构资料，截止到2026年3月17日。",
            "source": "Grant Weekly",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    monkeypatch.setattr(
        app_main,
        "fetch_topic_source_excerpt",
        lambda url: "Grant application deadline is March 17, 2026. Prepare organization profile, proposal form and submit before deadline.",
    )

    plan = client.post(f"/api/v1/topics/candidates/{candidate_id}/task-plan")
    assert plan.status_code == 200
    plan_payload = plan.json()
    assert plan_payload["candidateId"] == candidate_id
    assert len(plan_payload["tasks"]) >= 3
    assert any(task["dueDate"] == "2026-03-17" for task in plan_payload["tasks"])

    promoted = client.post(
        f"/api/v1/topics/candidates/{candidate_id}/promote-tasks",
        json={
            "tasks": [
                {
                    "title": "撰写申请表",
                    "desc": "完成资助申请表初稿。",
                    "priority": "high",
                    "listId": "list-0",
                    "dueDate": "2026-03-16",
                    "ddl": "3月16日前",
                    "ownerName": "测试员",
                    "collaboratorIds": [],
                    "tags": ["资助申报"],
                    "note": "需先核对预算字段。",
                },
                {
                    "title": "整理组织资料",
                    "desc": "准备机构简介、案例和证明材料。",
                    "priority": "normal",
                    "listId": "list-0",
                    "dueDate": "2026-03-17",
                    "ddl": "3月17日前",
                    "ownerName": "测试员",
                    "collaboratorIds": [],
                    "tags": ["材料准备"],
                    "note": "包含近两年项目成果。",
                },
            ]
        },
    )
    assert promoted.status_code == 200
    promoted_payload = promoted.json()
    assert promoted_payload["createdCount"] == 2

    tasks = client.get("/api/v1/tasks")
    assert tasks.status_code == 200
    task_items = tasks.json()["tasks"]
    assert sum(1 for task in task_items if task["sourceId"] == candidate_id) == 2
    assert any(task["note"] == "需先核对预算字段。" for task in task_items if task["sourceId"] == candidate_id)

    topics = client.get("/api/v1/topics")
    candidate = next(item for item in topics.json()["candidates"] if item["id"] == candidate_id)
    assert candidate["status"] == "promoted"


def test_topic_candidate_insight_extracts_points_reasons_and_practical_uses(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "大模型应用",
            "prompt": "关注公益与咨询行业的大模型落地案例。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "公益组织开始用 AI 做客户研究",
            "summary": "文章介绍了公益咨询团队如何把 AI 用在客户研究、复盘和材料整理中，并提到可以沉淀内部方法。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    monkeypatch.setattr(
        app_main,
        "fetch_topic_source_excerpt",
        lambda url: "The article explains how nonprofit consulting teams use AI for client research, internal review, and knowledge management. It suggests turning the workflow into a reusable playbook and collecting tool resources for the team.",
    )

    insight = client.post(f"/api/v1/topics/candidates/{candidate_id}/insights")
    assert insight.status_code == 200
    payload = insight.json()
    assert payload["candidateId"] == candidate_id
    assert "一、" in payload["overview"]
    assert "二、" in payload["overview"]
    assert "三、" in payload["overview"]
    assert len(payload["overview"]) >= 80
    assert len(payload["keyPoints"]) >= 1
    assert len(payload["recommendationReasons"]) >= 1
    assert len(payload["practicalUses"]) >= 1
    assert len(payload["editorialNote"]) >= 80
    assert len(payload["discussionPrompts"]) >= 1


def test_topic_candidate_prefetches_insight_on_create(tmp_path: Path):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "安全观察",
            "prompt": "关注大模型落地中的安全与治理风险。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "大模型安全落地的新方案",
            "summary": "文章讨论了企业在大模型落地过程中面临的安全风险，并介绍了覆盖评估、防护和数据治理的整体方案。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]

    wait_for_topic_insight_status(client, candidate_id)
    db = client.app.state.app_state.db
    row = db.fetchone("SELECT * FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,))
    assert row is not None
    assert row["overview"]
    assert row["editorial_note"]


def test_topic_candidate_chat_uses_candidate_context(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "大模型应用",
            "prompt": "关注 AI 落地案例、团队方法和业务变化。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "OpenAI 用真实客户案例展示 AI 落地效果",
            "summary": "文章介绍了 AI 如何在真实业务场景中落地，并强调效率提升来自工作流重构，不只是工具升级。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    captured: dict[str, str] = {}

    def fake_generate_topic_candidate_chat_response(prompt: str, system_instruction: str, context_summary: str):
        captured["prompt"] = prompt
        captured["system_instruction"] = system_instruction
        captured["context_summary"] = context_summary
        return AiStructuredResponse(
            content="这条新闻真正值得继续追问的，是 AI 改变的到底是工具能力，还是咨询服务的交付结构。",
            judgment="",
            analysis="",
            actions="",
            timeline="",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_topic_candidate_chat_response", fake_generate_topic_candidate_chat_response)

    response = client.post(
        f"/api/v1/topics/candidates/{candidate_id}/chat",
        json={
            "question": "这件事对咨询团队的服务结构意味着什么？",
            "history": [
                {
                    "role": "user",
                    "content": "我已经看完了这篇新闻。",
                    "createdAt": "2026-03-16T10:00:00",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidateId"] == candidate_id
    assert payload["message"]["role"] == "assistant"
    assert "交付结构" in payload["answer"]
    assert captured["prompt"] == "这件事对咨询团队的服务结构意味着什么？"
    assert "当前情报标题：OpenAI 用真实客户案例展示 AI 落地效果" in captured["context_summary"]
    assert "候选摘要：" in captured["context_summary"]
    assert "已发生的对话：" in captured["context_summary"]
    assert "用户：我已经看完了这篇新闻。" in captured["context_summary"]


def test_topic_candidate_insight_refreshes_stale_editorial_tone(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "CodeX 开发",
            "prompt": "关注 GitHub 开源项目、AI coding agent 和真实落地案例。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "一个新的 GitHub 开源 AI coding agent 项目",
            "summary": "这个项目希望把开发过程里的重复步骤压缩掉，让普通开发者也能更快跑起来。",
            "source": "GitHub",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    client.app.state.app_state.db.execute(
        """
        UPDATE topic_candidate_insights
        SET editorial_note = ?
        WHERE candidate_id = ?
        """,
        (
            "九千星标背后不仅是工具的流行，更折射出专业能力民主化的深层趋势，意味着组织需要重新审视竞争壁垒。",
            candidate_id,
        ),
    )

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "build_topic_candidate_insight",
        lambda **kwargs: {
            "overview": "一、这篇文章主要讲什么：它介绍了一个新的 GitHub 开源项目，重点展示它如何压缩开发流程中的重复环节。\n二、文章里最值得抓住的观点：项目希望把原本重度依赖经验的步骤做薄。\n三、它对团队的实际价值：可以帮助团队更快判断这种工具有没有真实落地价值。",
            "keyPoints": [
                "这个项目想解决的是开发流程里那些重复、繁琐、门槛高的步骤。",
                "它的价值不在于概念新，而在于让普通开发者更快跑起来。",
                "如果它真能接进工作流，影响的会是交付速度和协作方式。",
            ],
            "recommendationReasons": [
                "它把“到底替用户省了哪一步”讲得更清楚了。",
                "它适合拿来判断这种开源项目是不是只有概念，还是已经有产品价值。",
            ],
            "practicalUses": [
                "从“开源项目是不是产品雏形”这个角度写一篇短评。",
                "拆解它到底替用户省了哪一步，以及这一步为什么值钱。",
            ],
            "editorialNote": "如果把这个 GitHub 项目当成一个产品来看，最重要的不是它有多少功能，而是它到底替用户省掉了哪一步麻烦。它真正值钱的地方，是把原来很重、很慢、很专业的一段流程，压缩成普通开发者也能先跑起来的一套用法。所以大周更想讲清楚的是：它到底解决了什么具体问题，能让谁少花时间，值不值得接进真实工作流。",
            "discussionPrompts": [
                "这个项目最核心是在替用户省哪一步麻烦？",
                "它带来的价值更像提效工具，还是会直接改掉一段工作流？",
            ],
        },
    )

    insight = client.post(f"/api/v1/topics/candidates/{candidate_id}/insights")
    assert insight.status_code == 200
    payload = insight.json()
    assert "替用户省掉了哪一步麻烦" in payload["editorialNote"]
    assert "专业能力民主化" not in payload["editorialNote"]
    assert "背后不仅是工具的流行" not in payload["editorialNote"]


def test_topic_candidate_insight_refreshes_generic_editorial_template(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "CodeX 开发",
            "prompt": "关注 GitHub 开源项目、AI coding agent 和真实落地案例。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "字节开源多 Agent 框架获三十四万星",
            "summary": "文章提到字节开源的多 Agent 框架在 GitHub 走红，并强调它原生适配飞书，面向企业自动化场景。",
            "source": "新浪财经",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    client.app.state.app_state.db.execute(
        """
        UPDATE topic_candidate_insights
        SET editorial_note = ?
        WHERE candidate_id = ?
        """,
        (
            "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。",
            candidate_id,
        ),
    )

    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "build_topic_candidate_insight",
        lambda **kwargs: {
            "overview": "一、这篇文章主要讲什么：它介绍了字节开源的多 Agent 框架，强调高 star 增长、飞书适配和企业自动化定位。\n二、文章里最值得抓住的观点：项目试图把多代理协作和流程编排打包成更容易接入的框架。\n三、它对团队的实际价值：适合用来判断这种高热开源项目到底有没有真实业务落地价值。",
            "keyPoints": [
                "字节开源的多 Agent 框架在 GitHub 获得超 34 万星，短时间内形成了很高热度。",
                "文章特别提到它原生适配飞书，并定位企业自动化场景。",
                "项目强调多代理协作、流程编排和现成集成能力。",
            ],
            "recommendationReasons": [
                "它把企业自动化框架到底替谁省事、能省哪一步这件事讲得更具体了。",
                "它适合帮助团队判断高热开源项目和真实落地能力之间有没有断层。",
            ],
            "practicalUses": [
                "围绕多 Agent 框架到底能不能接进企业自动化场景写一篇短评。",
                "拆解飞书适配和流程编排到底意味着什么真实使用门槛。",
            ],
            "editorialNote": "字节这套多 Agent 框架最值得看的，不是星数本身，而是它把飞书适配和企业自动化场景一起讲出来了。这样看，它想解决的不是“再做一个 Agent demo”，而是把多代理协作真正塞进企业现有流程里。如果这点讲得实，它的价值就在于帮团队少掉一大段从零拼装流程编排和集成能力的工作。",
            "discussionPrompts": [
                "飞书适配到底只是展示层集成，还是已经触到真实流程编排？",
                "34 万星代表热度，还是已经代表了可复用价值？",
            ],
        },
    )

    insight = client.post(f"/api/v1/topics/candidates/{candidate_id}/insights")
    assert insight.status_code == 200
    payload = insight.json()
    assert "飞书" in payload["editorialNote"]
    assert "企业自动化" in payload["editorialNote"]
    assert "如果把这个 GitHub 项目当成一个产品来看" not in payload["editorialNote"]


def test_topic_candidate_insight_grounds_editorial_note_to_article_facts(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "CodeX 开发",
            "prompt": "关注 GitHub 开源项目、AI coding agent 和真实落地案例。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "字节开源多 Agent 框架获三十四万星",
            "summary": "文章提到字节开源的多 Agent 框架在 GitHub 走红，并强调它原生适配飞书，面向企业自动化场景。",
            "source": "新浪财经",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    client.app.state.app_state.db.execute(
        "UPDATE topic_candidates SET source_url = ? WHERE id = ?",
        ("https://example.com/agent-framework", candidate_id),
    )
    client.app.state.app_state.db.execute(
        """
        UPDATE topic_candidate_insights
        SET editorial_note = ?
        WHERE candidate_id = ?
        """,
        (
            "如果把这个 GitHub 项目当成一个产品来看，最该先问的不是它酷不酷，而是它到底替用户省掉了哪一步麻烦。",
            candidate_id,
        ),
    )

    monkeypatch.setattr(
        app_main,
        "fetch_topic_source_excerpt",
        lambda url: "字节开源的多 Agent 框架在 GitHub 获得超 34 万星，文章特别提到它原生适配飞书，目标是企业自动化场景。原文还强调多代理协作、流程编排和现成集成能力，想减少团队从零搭框架的成本。",
    )

    insight = client.post(f"/api/v1/topics/candidates/{candidate_id}/insights")
    assert insight.status_code == 200
    payload = insight.json()
    assert "34 万星" in payload["editorialNote"] or "34万星" in payload["editorialNote"]
    assert "飞书" in payload["editorialNote"]
    assert "如果把这个 GitHub 项目当成一个产品来看" not in payload["editorialNote"]


def test_topic_candidate_can_be_deleted_with_cached_insight(tmp_path: Path):
    client = make_client(tmp_path)

    radar = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "删除测试",
            "prompt": "验证候选删除后不会残留解析缓存。",
            "timeRange": "3_days",
        },
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]

    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "待删除候选",
            "summary": "验证删除操作。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    wait_for_topic_insight_status(client, candidate_id)

    deleted = client.delete(f"/api/v1/topics/candidates/{candidate_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    db = client.app.state.app_state.db
    assert db.fetchone("SELECT * FROM topic_candidates WHERE id = ?", (candidate_id,)) is None
    assert db.fetchone("SELECT * FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,)) is None
    seen = db.fetchone(
        "SELECT * FROM topic_candidate_seen WHERE radar_id = ? AND title_source_key = ?",
        (radar_id, "待删除候选||测试来源"),
    )
    assert seen is not None
    assert seen["deleted_at"] is not None


def test_topic_radar_update_keeps_record_count_stable(tmp_path: Path):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "原始雷达",
            "prompt": "原始提示词",
            "timeRange": "3_days",
            "preferredSources": [{"url": "https://example.com/research", "label": "研究站"}],
        },
    )
    assert created.status_code == 200
    radar_id = created.json()["id"]
    assert created.json()["preferredSources"] == [{"url": "https://example.com/research", "label": "研究站"}]

    updated = client.put(
        f"/api/v1/topics/radars/{radar_id}",
        json={
            "title": "更新后的雷达",
            "prompt": "更新后的提示词",
            "timeRange": "7_days",
            "preferredSources": [{"url": "https://news.example.org", "label": "资讯站"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == radar_id
    assert updated.json()["title"] == "更新后的雷达"
    assert updated.json()["prompt"] == "更新后的提示词"
    assert updated.json()["timeRange"] == "7_days"
    assert updated.json()["preferredSources"] == [{"url": "https://news.example.org", "label": "资讯站"}]

    topics = client.get("/api/v1/topics")
    assert topics.status_code == 200
    assert len(topics.json()["radars"]) == 1
    assert topics.json()["radars"][0]["id"] == radar_id
    assert topics.json()["radars"][0]["preferredSources"] == [{"url": "https://news.example.org", "label": "资讯站"}]


def test_topic_radar_source_label_normalizes_url_and_uses_ai(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    monkeypatch.setattr(client.app.state.app_state.ai, "suggest_short_title", lambda prompt: "公益媒体")

    response = client.post(
        "/api/v1/topics/radars/source-label",
        json={"url": "chinadevelopmentbrief.org.cn/topics"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "url": "https://chinadevelopmentbrief.org.cn/topics",
        "label": "公益媒体",
    }


def test_topic_radar_assist_generates_title_and_expands_prompt(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    monkeypatch.setattr(client.app.state.app_state.ai, "suggest_short_title", lambda prompt: "资助情报")
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "suggest_topic_search_queries",
        lambda *, title, prompt, time_range: ["公益资助 申报公告", "基金会 资助项目", "社会组织 征集通知"],
    )

    assisted = client.post(
        "/api/v1/topics/radars/assist",
        json={
            "prompt": "公益资助信息",
            "timeRange": "7_days",
        },
    )
    assert assisted.status_code == 200
    payload = assisted.json()
    assert payload["title"] == "资助情报"
    assert payload["queries"] == ["公益资助 申报公告", "基金会 资助项目", "社会组织 征集通知"]
    assert "公益资助信息" in payload["prompt"]
    assert "近 7 天" in payload["prompt"]
    assert "“公益资助 申报公告”" in payload["prompt"]


def test_topic_capture_writes_real_search_results_into_candidate_pool(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "公益咨询团队",
            "prompt": "关注公益咨询团队如何用 AI 做客户研究与项目复盘。",
            "timeRange": "3_days",
            "preferredSources": [{"url": "https://chinadevelopmentbrief.org.cn/topics", "label": "公益媒体"}],
        },
    )
    assert created.status_code == 200

    def fake_fetch(*args, **kwargs):
        assert kwargs["preferred_source_urls"] == ["https://chinadevelopmentbrief.org.cn/topics"]
        return [
            TopicSearchHit(
                title="AI is changing how nonprofit consultancies run client research",
                summary="Consulting teams are using AI to support client research and project reviews.",
                source="测试来源A",
                source_url="https://example.com/a",
                published_at="2026-03-13T10:00:00+08:00",
                provider="google_news",
                query="公益咨询团队 AI 客户研究",
            ),
            TopicSearchHit(
                title="AI is changing how nonprofit consultancies run client research",
                summary="重复结果不应再次写入。",
                source="测试来源A",
                source_url="https://example.com/a",
                published_at="2026-03-13T10:00:00+08:00",
                provider="google_news",
                query="公益咨询团队 AI 客户研究",
            ),
            TopicSearchHit(
                title="咨询项目复盘开始结构化沉淀",
                summary="项目复盘流程开始沉淀成标准动作。",
                source="测试来源B",
                source_url="https://example.com/b",
                published_at="2026-03-13T12:00:00+08:00",
                provider="bing_news",
                query="公益咨询团队 项目复盘",
            ),
        ]

    monkeypatch.setattr(app_main, "fetch_topic_candidates_from_web", fake_fetch)

    capture = client.post("/api/v1/topics/capture")
    assert capture.status_code == 200
    payload = capture.json()
    assert payload["totalCreated"] == 2
    assert payload["totalSkipped"] == 1
    assert payload["runs"][0]["createdCount"] == 2
    assert payload["runs"][0]["query"] == "公益咨询团队 AI 客户研究"

    topics = client.get("/api/v1/topics")
    assert topics.status_code == 200
    candidates = topics.json()["candidates"]
    assert len(candidates) == 2
    assert candidates[0]["captureMethod"] == "web_search"
    assert candidates[0]["capturedBy"] == "大周"
    assert candidates[0]["sourceUrl"].startswith("https://example.com/")
    assert all(any("\u4e00" <= char <= "\u9fff" for char in candidate["title"]) for candidate in candidates)
    assert all(any("\u4e00" <= char <= "\u9fff" for char in candidate["summary"]) for candidate in candidates)


def test_deleted_topic_candidate_is_not_recaptured(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    created = client.post(
        "/api/v1/topics/radars",
        json={
            "title": "重复新闻测试",
            "prompt": "验证删除后的新闻不会再次抓回。",
            "timeRange": "3_days",
        },
    )
    assert created.status_code == 200

    def fake_fetch(*args, **kwargs):
        return [
            TopicSearchHit(
                title="同一条新闻",
                summary="第一次抓到后删除，再抓取时不应重新进入候选池。",
                source="测试来源",
                source_url="https://example.com/repeated-news?oc=5",
                published_at="2026-03-15T09:00:00+08:00",
                provider="google_news",
                query="重复新闻测试",
            )
        ]

    monkeypatch.setattr(app_main, "fetch_topic_candidates_from_web", fake_fetch)

    first_capture = client.post("/api/v1/topics/capture")
    assert first_capture.status_code == 200
    assert first_capture.json()["totalCreated"] == 1
    candidate_id = first_capture.json()["runs"][0]["candidates"][0]["id"]

    deleted = client.delete(f"/api/v1/topics/candidates/{candidate_id}")
    assert deleted.status_code == 200

    second_capture = client.post("/api/v1/topics/capture")
    assert second_capture.status_code == 200
    assert second_capture.json()["totalCreated"] == 0
    assert second_capture.json()["totalSkipped"] == 1

    topics = client.get("/api/v1/topics")
    assert topics.status_code == 200
    assert topics.json()["candidates"] == []


def test_legacy_scan_and_import_only_accepts_json_and_csv(tmp_path: Path):
    client = make_client(tmp_path)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    json_path = legacy_dir / "client.json"
    csv_path = legacy_dir / "records.csv"
    sqlite_path = legacy_dir / "archive.sqlite"
    json_path.write_text('{"name":"legacy"}', encoding="utf-8")
    csv_path.write_text("title,summary\nalpha,beta\n", encoding="utf-8")
    sqlite_path.write_text("not a real sqlite file", encoding="utf-8")

    scanned = client.post("/api/v1/settings/legacy-scan", json={"path": str(legacy_dir)})
    assert scanned.status_code == 200
    payload = scanned.json()
    entries = {item["path"]: item for item in payload["entries"]}
    assert entries[str(json_path)]["importable"] is True
    assert entries[str(csv_path)]["importable"] is True
    assert entries[str(sqlite_path)]["importable"] is False

    created = client.post(
        "/api/v1/clients",
        json={
            "name": "旧数据接收客户",
            "alias": "旧数据",
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "旧数据导入测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200
    client_id = created.json()["id"]

    imported = client.post(
        "/api/v1/imports",
        json={
            "clientId": client_id,
            "mode": "file",
            "paths": [str(json_path), str(csv_path)],
            "allowLegacy": True,
        },
    )
    assert imported.status_code == 200
    assert sum(item["importedCount"] for item in imported.json()) == 2

    rejected = client.post(
        "/api/v1/imports",
        json={
            "clientId": client_id,
            "mode": "file",
            "paths": [str(sqlite_path)],
            "allowLegacy": True,
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()[0]["importedCount"] == 0
    assert rejected.json()[0]["skippedCount"] == 1


def test_workspace_import_builds_document_cards_and_knowledge_status(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    root = tmp_path / "knowledge-source"
    nested = root / "项目资料"
    nested.mkdir(parents=True)
    (nested / "推进纪要.md").write_text(
        "# 项目推进纪要\n本周主要推进捐赠人沟通、预算梳理与阶段里程碑确认。\n下一步需要补齐项目执行方案与传播节奏。",
        encoding="utf-8",
    )
    (nested / "品牌传播.txt").write_text(
        "传播计划围绕品牌故事、媒体合作与活动节奏展开，需要同步公众号与社媒安排。",
        encoding="utf-8",
    )

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "folder", "paths": [str(root)]},
    )
    assert imported.status_code == 200
    assert sum(item["importedCount"] for item in imported.json()) == 2
    status = wait_for_knowledge_ready(client, client_id)
    assert status["lastJobStatus"] == "completed"

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    payload = workspace.json()
    assert [folder["label"] for folder in payload["folders"]] == ["财务与筹款", "品牌与传播", "项目与业务", "组织与战略", "其他资料", "战略陪伴"]
    assert payload["knowledgeStatus"]["totalDocuments"] == 2
    assert payload["knowledgeStatus"]["totalChunks"] >= 2
    assert payload["knowledgeStatus"]["surrogateCount"] == 2
    assert payload["knowledgeStatus"]["reclassifiedDocumentCount"] == 2
    assert payload["knowledgeStatus"]["qdrantReady"] is True
    assert payload["knowledgeStatus"]["embeddingMode"] in {"fastembed", "fastembed_available", "hash_fallback"}
    assert payload["knowledgeStatus"]["pendingJobs"] == 0
    assert payload["knowledgeStatus"]["runningJobs"] == 0
    assert any(item["jobType"] == "ingest_import" and item["status"] == "completed" for item in payload["knowledgeJobs"])
    assert len(payload["recentReclassEvents"]) >= 2
    assert len(payload["documentCards"]) == 2
    first_card = payload["documentCards"][0]
    assert first_card["docId"].startswith("dock_")
    assert first_card["chunkCount"] >= 1
    assert first_card["primaryCategory"] in {"项目与业务", "品牌与传播", "财务与筹款", "组织与战略", "其他资料"}
    assert first_card["surrogateMdPath"].endswith(".md")
    assert Path(first_card["surrogateMdPath"]).exists()
    assert Path(first_card["sourcePath"]).exists()
    assert first_card["logicalCategory"] in {"项目与业务", "品牌与传播", "财务与筹款", "组织与战略", "其他资料"}
    notebook = client.get(f"/api/v1/clients/{client_id}/notebook")
    assert notebook.status_code == 200
    notebook_facts = [item["factValue"] for item in notebook.json()["keyFacts"]]
    assert any("推进纪要" in item or "品牌传播" in item for item in notebook_facts)


def test_workspace_import_auto_generates_client_dna_candidates(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "自动候选客户")
    source = tmp_path / "auto-dna-source"
    source.mkdir()
    (source / "项目介绍.md").write_text(
        "# 项目介绍\n益语智库是一家长期服务公益机构的战略陪伴团队，当前项目聚焦任务协同、会议复盘与资料底盘建设。\n"
        "团队成员包括顾源源、庆华和罗茜茜，当前重点是把组织介绍、项目介绍和市场背景统一成系统上下文。",
        encoding="utf-8",
    )

    def fake_generate_structured(prompt: str, system_instruction: str, context_summary: str) -> AiStructuredResponse:
        if "组织介绍" in prompt:
            return AiStructuredResponse(
                content="## 1. 组织定位\n益语智库是一家面向公益机构的战略陪伴与知识底盘建设团队。\n\n## 2. 工作方式\n强调陪伴式共创、任务协同和资料沉淀。",
                judgment="益语智库聚焦公益行业的战略陪伴与知识底盘建设，强调陪伴式共创和长期沉淀。",
                analysis="仍缺组织发展历史\n仍缺核心使命的更完整表述",
                actions="项目介绍.md",
                timeline="建议继续补组织发展材料后再重扫。",
            )
        if "团队介绍" in prompt:
            return AiStructuredResponse(
                content="## 1. 团队概述\n当前团队围绕项目运营、研究和协同支持展开。\n\n## 2. 核心负责人\n顾源源负责整体推进。",
                judgment="当前团队已能看出负责人和协作框架，但角色分工还需要更细。",
                analysis="仍缺客户侧接口人\n仍缺完整角色分工",
                actions="项目介绍.md",
                timeline="建议补团队分工资料。",
            )
        if "市场背景" in prompt:
            return AiStructuredResponse(
                content="## 1. 行业概况\n公益机构正在持续提升任务协同、资料管理与项目复盘能力。",
                judgment="市场背景已有公益行业数字化协同方向的基本判断。",
                analysis="仍缺竞品或参照对象\n仍缺行业趋势数据",
                actions="项目介绍.md",
                timeline="建议补行业研究材料。",
            )
        return AiStructuredResponse(
            content="## 1. 项目概述\n当前项目聚焦任务、会议与知识底盘的一体化建设。\n\n## 2. 当前重点\n先把已有资料转成系统共享上下文。",
            judgment="该项目当前重点是把已有资料沉淀成系统可引用的统一项目上下文。",
            analysis="仍缺成功标准\n仍缺更细的服务范围",
            actions="项目介绍.md",
            timeline="建议补项目目标和服务范围后再重扫。",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_structured", fake_generate_structured)

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "folder", "paths": [str(source)]},
    )
    assert imported.status_code == 200

    status = wait_for_knowledge_ready(client, client_id)
    assert status["lastJobStatus"] == "completed"
    workspace_payload = wait_for_generated_dna_modules(
        client,
        client_id,
        module_keys=["organization_intro", "business_intro", "team_intro", "market_intro"],
    )

    modules = {item["moduleKey"]: item for item in workspace_payload["dnaModules"]}
    assert modules["organization_intro"]["hasDocument"] is True
    assert modules["organization_intro"]["sourceKind"] == "generated"
    assert "仍缺组织发展历史" in modules["organization_intro"]["missingInfo"]
    assert modules["business_intro"]["fileName"].endswith("business_intro-candidate.md")
    assert modules["team_intro"]["sourceKind"] == "generated"
    assert modules["market_intro"]["sourceKind"] == "generated"
    assert any(item["jobType"] == "generate_client_dna_candidates" for item in workspace_payload["knowledgeJobs"])


def test_main_chain_canary_closes_import_analysis_approval_and_cockpit(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "主链闭环 canary")
    source = tmp_path / "analysis-canary-source"
    source.mkdir()
    (source / "项目总览.md").write_text(
        "# 项目总览\n"
        "该客户当前正围绕公益机构战略陪伴、会议复盘与知识底盘建设推进一体化工作。\n"
        "本周期的关键目标是把分散材料沉淀为统一客户上下文，并形成可审批的经营判断。\n",
        encoding="utf-8",
    )

    def fast_generate_structured(prompt: str, system_instruction: str, context_summary: str) -> AiStructuredResponse:
        return AiStructuredResponse(
            content="## 1. 当前重点\n先把材料沉淀成统一上下文。\n\n## 2. 推进建议\n围绕主问题形成可审批判断。",
            judgment="当前重点是把已有资料沉淀成统一上下文，并形成可审批的客户级判断。",
            analysis="仍缺补充案例\n仍缺更完整的阶段指标",
            actions="项目总览.md",
            timeline="建议补更多项目资料后继续迭代。",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_structured", fast_generate_structured)

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "folder", "paths": [str(source)]},
    )
    assert imported.status_code == 200, imported.text

    status = wait_for_knowledge_ready(client, client_id)
    assert status["lastJobStatus"] == "completed"

    job_response = client.post(
        "/api/v1/analysis/jobs",
        json={
            "jobType": "strategy_pack",
            "clientId": client_id,
            "scopeType": "client",
            "scopeId": client_id,
            "priority": "normal",
            "triggerType": "manual",
            "question": "主链 canary",
            "sourceScope": {},
            "featureFlags": {},
            "intentProfile": "client_overview",
        },
    )
    assert job_response.status_code == 200, job_response.text
    job_payload = wait_for_analysis_job_terminal(client, job_response.json()["id"])
    assert job_payload["status"] == "completed", job_payload

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    baseline = workspace_payload["judgmentBundle"]["baselineJudgment"]
    assert baseline is not None
    assert baseline["authorityLevel"] == "candidate"
    assert workspace_payload["latestResolutionTrace"]["selectedCandidate"]["objectId"] == baseline["id"]
    assert workspace_payload["latestResolutionTrace"]["resolvedScope"] == {"scopeType": "client", "scopeId": client_id}
    assert workspace_payload["latestResolutionTrace"]["writebackScope"] == {"scopeType": "client", "scopeId": client_id}

    approval = client.post(
        "/api/v1/approvals/decide",
        json={
            "targetType": "judgment_version",
            "targetId": baseline["id"],
            "decision": "approved",
            "comment": "canary approve",
            "policyType": "analysis_review",
            "metadata": {"source": "main_chain_canary"},
        },
    )
    assert approval.status_code == 200, approval.text

    cockpit = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit")
    assert cockpit.status_code == 200, cockpit.text
    cockpit_payload = cockpit.json()
    assert cockpit_payload["officialLayerStatus"] == "ready"
    assert cockpit_payload["officialEmptyReason"] is None
    assert cockpit_payload["officialLayer"]["officialBaseline"]["id"] == baseline["id"]
    assert baseline["id"] not in {item["id"] for item in cockpit_payload["radarLayer"]["candidateJudgments"]}


def test_rebuild_backfills_logical_mappings_for_existing_knowledge_docs(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="历史知识回填客户")
    file_path = tmp_path / "legacy-org-intro.md"
    file_path.write_text(
        "# 机构介绍\n为爱黔行当前重点在山区儿童教育、捐赠人沟通和项目推进。",
        encoding="utf-8",
    )

    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    ready = wait_for_knowledge_ready(client, client_id)
    assert ready["surrogateCount"] == 1

    app_state = client.app.state.app_state
    app_state.db.execute(
        "DELETE FROM logical_file_mappings WHERE knowledge_document_id IN (SELECT id FROM knowledge_documents WHERE client_id = ?)",
        (client_id,),
    )
    app_state.db.execute(
        """
        UPDATE knowledge_documents
        SET current_human_path = NULL, human_folder_category = NULL, reclassified_at = NULL, reclass_reason = '', reclass_confidence = classification_confidence
        WHERE client_id = ?
        """,
        (client_id,),
    )

    rebuild = client.post(f"/api/v1/clients/{client_id}/knowledge/rebuild")
    assert rebuild.status_code == 200
    rebuild_ready = wait_for_knowledge_ready(client, client_id)
    assert rebuild_ready["reclassifiedDocumentCount"] == 1

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    payload = workspace.json()
    assert payload["recentReclassEvents"]
    assert payload["documentCards"][0]["logicalCategory"] in {"项目与业务", "品牌与传播", "财务与筹款", "组织与战略", "其他资料"}


def test_chat_uses_knowledge_citations_and_general_answer_fallback(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="问答测试客户")
    file_path = tmp_path / "donor-note.md"
    file_path.write_text(
        "# 捐赠人反馈\n捐赠人最关心预算透明度和项目里程碑，建议下周补充预算拆解并同步月度推进节奏。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    search = client.post(
        f"/api/v1/clients/{client_id}/knowledge/search",
        json={"prompt": "捐赠人反馈里提到的预算和推进节奏是什么？"},
    )
    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload["searchId"]
    assert search_payload["masterHitCount"] >= 1
    assert search_payload["surrogateHitCount"] >= 1

    grounded = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "捐赠人反馈里提到的预算和推进节奏是什么？", "searchId": search_payload["searchId"]},
    )
    assert grounded.status_code == 200
    grounded_payload = grounded.json()
    assert grounded_payload["evidence"]
    assert grounded_payload["evidence"][0]["score"] is not None
    assert grounded_payload["evidence"][0]["coverage"] >= 0.5
    assert grounded_payload["evidence"][0]["retrievalStage"] in {"surrogate", "raw_chunk", "master_index"}
    assert grounded_payload["llmInvoked"] is True
    assert grounded_payload["answerMode"] in {"grounded_answer", "grounded_fallback", "low_confidence_answer"}
    assert grounded_payload["retrievalSummary"]["searchId"] == search_payload["searchId"]
    assert grounded_payload["retrievalSummary"]["cacheHit"] is True

    general = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "公益机构新年度组织架构一般怎么调整？"},
    )
    assert general.status_code == 200
    general_payload = general.json()
    assert general_payload["llmInvoked"] is True
    assert general_payload["answerMode"] in {"general_answer", "grounded_fallback"}
    if general_payload["answerMode"] == "general_answer":
        assert general_payload["retrievalSummary"]["retrievalStage"] == "background_only"
        assert general_payload["evidence"] == []
        assert "以下内容不是基于当前客户原始资料的正式分析" in general_payload["content"]
    else:
        assert general_payload["failureReason"] in {
            "llm_local_fallback_after_retry",
            "llm_compact_fallback_after_retry",
            "partial_materials",
        }
        assert general_payload["content"]


def test_identity_role_query_requires_explicit_role_evidence(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="CFFC")
    transcript = tmp_path / "workshop.md"
    transcript.write_text(
        "# 战略工作坊实录\n顾源源在本次工作坊中主要负责提问、梳理业务逻辑和推进后续访谈，并未担任 CFFC 内部角色。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(transcript)]},
    )
    assert imported.status_code == 200
    wait_for_knowledge_ready(client, client_id)

    def should_not_run(*args, **kwargs):
        raise AssertionError("identity guard should prevent normal answer generation")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", should_not_run)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "CFFC 创始人是什么样的人，分析一下"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "identity_role_evidence_insufficient"
    assert "不足以直接确认" in payload["content"]
    assert "创始人" in payload["content"]


def test_strategy_query_prefers_cross_category_materials(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略问题检索客户")
    strategy_doc = tmp_path / "org-strategy.md"
    strategy_doc.write_text(
        "# 组织战略与治理\n当前战略重点是把项目陪伴与机构筹资联动起来，董事会更关注组织治理、年度路线图和关键风险。",
        encoding="utf-8",
    )
    brand_doc = tmp_path / "brand-note.md"
    brand_doc.write_text(
        "# 品牌传播规划\n目前品牌传播的主要任务是统一外部叙事、优化机构介绍和捐赠人沟通材料，避免战略表达与传播表达脱节。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(strategy_doc), str(brand_doc)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 2

    search = client.post(
        f"/api/v1/clients/{client_id}/knowledge/search",
        json={"prompt": "结合现有资料，概括这个机构的战略重点、传播线索和潜在风险。"},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["masterHitCount"] >= 2
    assert payload["surrogateHitCount"] >= 1
    assert "组织与战略" in payload.get("categoryCoverage", [])
    assert "品牌与传播" in payload.get("categoryCoverage", [])


def test_vectorize_answer_creates_memory_doc_and_export_answer_writes_docx(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="战略陪伴测试客户")
    file_path = tmp_path / "org-intro.md"
    file_path.write_text(
        "# 为爱黔行机构介绍\n为爱黔行聚焦山区儿童教育，当前重点在捐赠人沟通和项目里程碑梳理。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    answer = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍为爱黔行"},
    )
    assert answer.status_code == 200
    message_id = answer.json()["id"]

    vectorized = client.post(
        f"/api/v1/clients/{client_id}/knowledge/vectorize-answer",
        json={"messageId": message_id},
    )
    assert vectorized.status_code == 200
    vector_payload = vectorized.json()
    assert vector_payload["sourceType"] == "memory_answer"
    assert Path(vector_payload["surrogateMdPath"]).exists()

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["knowledgeStatus"]["memoryDocCount"] == 1

    reclass_events = client.get(f"/api/v1/clients/{client_id}/knowledge/reclass-events")
    assert reclass_events.status_code == 200

    exported = client.post(
        f"/api/v1/clients/{client_id}/knowledge/export-answer",
        json={"messageId": message_id},
    )
    assert exported.status_code == 200
    export_path = Path(exported.json()["path"])
    assert export_path.exists()
    assert export_path.suffix == ".docx"
    assert "战略陪伴" in export_path.as_posix()


def test_chat_falls_back_to_local_retrieval_summary_when_llm_generation_times_out(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="本地综述兜底客户")
    file_path = tmp_path / "org-intro.md"
    file_path.write_text(
        "# 为爱黔行机构介绍\n为爱黔行聚焦山区儿童教育，已经形成机构介绍、项目推进和捐赠人沟通三条主线。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    def raise_qwen_timeout(*args, **kwargs):
        raise AiInvocationError("qwen", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_qwen_timeout)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_general_fallback", raise_qwen_timeout)

    answer = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "为爱黔行是一家什么样的机构？请简要介绍。"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["llmInvoked"] is True
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["fallbackPresentationMode"] == "compact_user_answer"
    assert payload["failureReason"] in {
        "llm_local_fallback_after_retry",
        "llm_compact_fallback",
        "llm_compact_fallback_after_retry",
    }
    assert "为爱黔行" in payload["content"]
    assert "analysis-first" not in payload["content"]
    assert "当前最值得抓住的原始观察包括" not in payload["content"]
    assert payload["evidence"]


def test_chat_timeout_does_not_preserve_placeholder_partial_text(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="占位正文兜底客户")
    file_path = tmp_path / "org-intro.md"
    file_path.write_text(
        "# 日慈本周沟通纪要\n本周主要变化是教师赋能和繁星计划都开始从项目复盘转向定位校准，团队更关注价值判断、规模化潜力和后续支持路径。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    def raise_after_placeholder(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        if on_partial is not None:
            on_partial(
                {
                    "stageLabel": "正在直接生成长文回答",
                    "progress": 62.0,
                    "content": "千问正在基于完整材料直接生成长文回答。",
                    "structured": {
                        "content": "千问正在基于完整材料直接生成长文回答。",
                        "judgment": "",
                        "analysis": "",
                        "actions": "",
                        "timeline": "",
                    },
                }
            )
        raise AiInvocationError("qwen", "读取超时：The read operation timed out")

    def raise_compact_timeout(*args, **kwargs):
        raise AiInvocationError("qwen", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_after_placeholder)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_compact_grounded_fallback", raise_compact_timeout)

    answer = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这一周发生了什么变化？"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "llm_local_fallback_after_retry"
    assert payload["fallbackPresentationMode"] == "compact_user_answer"
    assert "千问正在基于完整材料直接生成长文回答" not in payload["content"]
    assert "当前最值得抓住的原始观察包括" not in payload["content"]
    assert "analysis-first" not in payload["content"]


def test_chat_timeout_does_not_preserve_opening_stage_placeholder_text(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="长文开场占位兜底客户")
    file_path = tmp_path / "weekly-update.md"
    file_path.write_text(
        "# 本周推进\n本周组织推进出现了人员安排变动、会议节奏变化和一个新增的跟进任务，已经足以支持本地证据型兜底回答。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    def raise_after_opening(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        if on_partial is not None:
            opening = "正在围绕核心判断、关键张力和潜在风险整合原始证据，准备输出连续长文分析。"
            on_partial(
                {
                    "stageLabel": "正在整合长文分析",
                    "progress": 58.0,
                    "content": opening,
                    "structured": {
                        "content": opening,
                        "judgment": "",
                        "analysis": "",
                        "actions": "",
                        "timeline": "",
                    },
                }
            )
        raise AiInvocationError("doubao", "读取超时：The read operation timed out")

    def raise_compact_timeout(*args, **kwargs):
        raise AiInvocationError("doubao", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_after_opening)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_compact_grounded_fallback", raise_compact_timeout)

    answer = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这一周发生了什么变化？"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "llm_local_fallback_after_retry"
    assert payload["fallbackPresentationMode"] == "compact_user_answer"
    assert "正在围绕核心判断、关键张力和潜在风险整合原始证据" not in payload["content"]
    assert "当前最值得抓住的原始观察包括" not in payload["content"]
    assert "analysis-first" not in payload["content"]


def test_chat_local_fallback_includes_workspace_state_summary(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="客户状态问答兜底客户")
    file_path = tmp_path / "weekly-state.md"
    file_path.write_text(
        "# 本周状态\n本周最重要的变化是项目推进节奏调整、会议结论待收敛，以及一个新的跟进任务已经创建。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    meeting = client.post(f"/api/v1/clients/{client_id}/meetings", json={"title": "本周推进会"})
    assert meeting.status_code == 200

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200
    list_id = board.json()["lists"][0]["id"]
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟进本周变化",
            "desc": "整理本周变化、关键风险和下一步推进点。",
            "listId": list_id,
            "clientId": client_id,
            "ownerName": "测试同学",
        },
    )
    assert task.status_code == 200

    def raise_timeout(*args, **kwargs):
        raise AiInvocationError("doubao", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_timeout)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_compact_grounded_fallback", raise_timeout)

    answer = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这周有什么变化？"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["fallbackPresentationMode"] == "state_cards_only"
    assert payload["stateAnswerSections"]["actions"]
    assert "analysis-first" not in payload["content"]
    assert "当前最值得抓住的原始观察包括" not in payload["content"]


def test_intro_fallback_filters_ppt_noise_and_keeps_client_materials_with_service_provider_mentions(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="日慈基金会")
    meeting_path = tmp_path / "teacher-note.md"
    meeting_path.write_text(
        "# 日慈基金会教师赋能会议纪要\n日慈基金会当前围绕教师赋能推进带领者培养、社群运营和数字化协作，资料中也提到益语智库支持后续协同，但主体仍是客户项目推进与阶段判断。",
        encoding="utf-8",
    )
    ppt_path = tmp_path / "slide-noise.pptx"
    ppt_path.write_text(
        "单击此处编辑母版文本样式 演示文稿标题 演示文稿副标题 作者和日期 开启日慈基金会的战略第二曲线",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(meeting_path), str(ppt_path)]},
    )
    assert imported.status_code == 200
    wait_for_knowledge_ready(client, client_id)

    def raise_timeout(*args, **kwargs):
        raise AiInvocationError("doubao", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_timeout)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_compact_grounded_fallback", raise_timeout)

    answer = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍日慈基金会"},
    )
    assert answer.status_code == 200
    payload = answer.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["fallbackPresentationMode"] == "compact_user_answer"
    assert "教师赋能" in payload["content"]
    assert "益语智库支持" in payload["content"]
    assert "单击此处编辑母版文本样式" not in payload["content"]
    assert "演示文稿标题" not in payload["content"]


def test_analysis_run_keeps_evidence_summary_when_long_answer_fails(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="异步分析兜底客户")
    file_path = tmp_path / "org-intro.md"
    file_path.write_text(
        "# 为爱黔行机构介绍\n为爱黔行聚焦山区儿童教育，已经形成机构介绍、项目推进和捐赠人沟通三条主线。",
        encoding="utf-8",
    )
    imported = client.post(
        "/api/v1/imports",
        json={"clientId": client_id, "mode": "file", "paths": [str(file_path)]},
    )
    assert imported.status_code == 200
    status = wait_for_knowledge_ready(client, client_id)
    assert status["surrogateCount"] == 1

    def raise_qwen_timeout(*args, **kwargs):
        raise AiInvocationError("qwen", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_qwen_timeout)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_compact_grounded_fallback", raise_qwen_timeout)

    started = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "为爱黔行是一家什么样的机构？请简要介绍。"},
    )
    assert started.status_code == 200
    start_payload = started.json()
    run_id = start_payload["analysisRun"]["id"]
    assert start_payload["analysisRun"]["status"] == "queued"

    deadline = time.time() + 30.0
    evidence_seen = False
    final_run: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/clients/{client_id}/analysis-runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["evidenceSummary"]["masterHitCount"] >= 1:
            evidence_seen = True
            assert payload["evidenceSummary"]["evidenceList"]
        if payload["status"] in {"completed", "failed"}:
            final_run = payload
            break
        time.sleep(0.1)

    assert evidence_seen is True
    assert final_run is not None
    assert final_run["status"] == "completed"
    assert final_run["longAnswerStatus"] == "fallback"
    assert final_run["summaryStatus"] == "fallback"
    assert final_run["failureReason"] == "llm_local_fallback_after_retry"
    assert final_run["evidenceSummary"]["summaryText"]
    assert final_run["longAnswer"]
    assert final_run["structuredSummary"]


def test_workspace_related_tasks_include_direct_client_and_event_line_tasks(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="工作台任务归集客户")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "工作台任务归集主线",
            "kind": "project_line",
            "status": "active",
            "stage": "推进中",
            "summary": "验证客户工作台是否会把直挂客户和事件线的任务聚合出来。",
            "intent": "补齐客户工作台的推进态势。",
            "nextStep": "继续推进任务归集验证。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    task_board = client.get("/api/v1/tasks")
    assert task_board.status_code == 200
    default_list_id = task_board.json()["lists"][0]["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "补齐客户工作台任务归集",
            "desc": "这条任务直接挂在客户和事件线上，不依赖 source_id。",
            "priority": "high",
            "listId": default_list_id,
            "clientId": client_id,
            "eventLineId": event_line_id,
            "dueDate": "2026-04-17",
            "ddl": "2026-04-17",
            "tagIds": [],
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    payload = workspace.json()
    related_task_ids = [item["id"] for item in payload["relatedTasks"]]
    assert task_id in related_task_ids


def test_organization_dna_upload_replace_and_settings_roundtrip(tmp_path: Path):
    client = make_client(tmp_path)

    uploaded = client.post(
        "/api/v1/settings/org-dna/organization_intro",
        json={
          "markdownContent": "# 组织介绍\n益语智库专注于公益咨询与知识沉淀。",
          "fileName": "organization-intro.md",
        },
    )
    assert uploaded.status_code == 200
    payload = uploaded.json()
    assert payload["moduleKey"] == "organization_intro"
    assert payload["hasDocument"] is True
    assert "益语智库" in payload["normalizedText"]

    replaced = client.post(
        "/api/v1/settings/org-dna/organization_intro",
        json={
          "markdownContent": "# 组织介绍\n益语智库专注于公益咨询、任务协同与知识工作台。",
          "fileName": "organization-intro-v2.md",
        },
    )
    assert replaced.status_code == 200
    replaced_payload = replaced.json()
    assert replaced_payload["fileName"] == "organization-intro-v2.md"
    assert "任务协同" in replaced_payload["normalizedText"]

    modules = client.get("/api/v1/settings/org-dna")
    assert modules.status_code == 200
    assert len(modules.json()["modules"]) == 4

    topics_settings = client.post(
        "/api/v1/settings/topics",
        json={
            "defaultTimeRange": "7_days",
            "defaultTaskOwnerMode": "empty",
            "useOrgDnaForInsight": True,
        },
    )
    assert topics_settings.status_code == 200
    assert topics_settings.json()["defaultTimeRange"] == "7_days"
    assert topics_settings.json()["defaultTaskOwnerMode"] == "empty"

    analysis_settings = client.post(
        "/api/v1/settings/analysis-workbench",
        json={
            "defaultTitlePrefix": "组织分析",
            "useOrgDna": True,
        },
    )
    assert analysis_settings.status_code == 200
    assert analysis_settings.json()["defaultTitlePrefix"] == "组织分析"


def test_client_dna_documents_are_saved_and_prioritized_in_chat_context(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "客户DNA测试客户")
    state = client.app.state.app_state

    uploaded = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n该客户是公益行业的可信基础设施与协作中枢。",
            "fileName": "client-organization-intro.md",
        },
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["hasDocument"] is True

    uploaded = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/business_intro",
        json={
            "markdownContent": "# 项目介绍\n核心项目围绕行业研究、陪伴式咨询与知识底座建设展开。",
            "fileName": "client-business-intro.md",
        },
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["hasDocument"] is True

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200
    workspace_payload = workspace.json()
    assert len(workspace_payload["dnaModules"]) == 4
    assert workspace_payload["dnaModules"][0]["clientId"] == client_id
    assert any(module["hasDocument"] for module in workspace_payload["dnaModules"])

    seed_timestamp = "2026-03-14T10:00:00"
    state.db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_seed', ?, NULL, '普通资料', '/tmp/source.md', 'md', 'file', '这里是普通知识库中的一段背景材料。', '[]', ?)
        """,
        (client_id, seed_timestamp),
    )
    state.db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_doc_seed', ?, NULL, 'doc_seed', 'kd_doc_seed_uid', '/tmp/source.md', '/tmp/source.md', NULL,
            '组织与战略', NULL, NULL, 0.0, NULL, 'md',
            '组织与战略', '机构介绍', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_seed', 'normalized_seed', ?, ?
        )
        """,
        (client_id, seed_timestamp, seed_timestamp),
    )

    captured_context: dict[str, str] = {}

    def fake_bundle(db, data_dir, client_id_arg: str, prompt: str) -> RetrievalBundle:
        assert client_id_arg == client_id
        return RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_doc_seed",
                    chunk_id="chunk_seed",
                    title="普通资料",
                    excerpt="这里是普通知识库中的一段背景材料。",
                    score=0.9,
                    coverage=0.5,
                    section_label="原文片段",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["客户"],
                    path="/tmp/source.md",
                )
            ],
            coverage=0.5,
            retrieval_summary={
                "masterHitCount": 1,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 1,
                "drillthroughUsed": True,
                "preferredCategories": ["组织与战略"],
                "categoryCoverage": ["组织与战略"],
            },
            context_text="",
            matched_terms=["客户"],
            failure_reason=None,
        )

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        captured_context["context"] = context_summary
        return app_main.AiStructuredResponse(
            content="这是基于客户 DNA 优先整理的一版回答。",
            judgment="已优先纳入客户 DNA。",
            analysis="1. 先读客户 DNA。\n2. 再结合普通资料。",
            actions="继续补充更多客户 DNA 模块。",
            timeline="可继续扩写。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fake_bundle)
    monkeypatch.setattr(state.ai, "generate_chat_response", fake_generate_chat_response)

    answered = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍这家客户"},
    )
    assert answered.status_code == 200
    answered_payload = answered.json()
    assert answered_payload["retrievalSummary"]["memoryBackgroundUsed"] is True
    assert answered_payload["retrievalSummary"]["memoryBackgroundSources"]
    context = captured_context["context"]
    assert "统一记忆背景（仅用于帮助理解组织与推进，不作为正式引证）：" in context
    assert "统一记忆使用规则=统一记忆只作为背景上下文" in context
    assert context.index("统一记忆背景（仅用于帮助理解组织与推进，不作为正式引证）：") < context.index("客户背景底稿（仅用于理解客户，不作为正式引证）：")
    assert "客户背景底稿（仅用于理解客户，不作为正式引证）：" in context
    assert "背景底稿使用规则=背景底稿只用于理解客户、修正语境和帮助组织分析，不作为正式引证或确定性事实来源。" in context
    assert "[组织介绍]" in context
    assert "可信基础设施与协作中枢" in context
    assert "[项目介绍]" in context
    assert "核心项目围绕行业研究、陪伴式咨询与知识底座建设展开" in context
    assert context.index("客户背景底稿（仅用于理解客户，不作为正式引证）：") < context.index("原始证据包（可用于正式判断）：")


def test_client_dna_documents_only_accept_markdown_extensions(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "Markdown 校验测试客户")

    rejected = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n这是一次错误扩展名测试。",
            "fileName": "organization-intro.txt",
        },
    )
    assert rejected.status_code == 400, rejected.text
    assert "只允许上传 .md 或 .markdown 文件" in rejected.text

    accepted = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n这是一次正确扩展名测试。",
            "fileName": "organization-intro.markdown",
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["hasDocument"] is True


def test_tasks_consume_project_dna_and_module_flow_context(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "项目上下文打通测试客户")

    uploads = {
        "organization_intro": "# 组织介绍\n该组织是一家长期深耕公益行业的战略陪伴机构，强调陪伴式共创与知识沉淀。",
        "business_intro": "# 项目介绍\n本项目聚焦公益机构的智能任务协同、会议复盘和项目资料底盘建设。",
        "team_intro": "# 团队介绍\n项目由顾源源总体负责，罗茜茜负责客户协同，庆华负责策略研判。",
        "market_intro": "# 市场背景\n当前公益咨询行业正在加速 AI 化，但对安全、治理和协同质量要求更高。",
    }
    for module_key, markdown in uploads.items():
        response = client.post(
            f"/api/v1/clients/{client_id}/dna-documents/{module_key}",
            json={
                "markdownContent": markdown,
                "fileName": f"{module_key}.md",
            },
        )
        assert response.status_code == 200, response.text

    created_module = client.post(
        f"/api/v1/clients/{client_id}/project-modules",
        json={
            "name": "客户协同模块",
            "goal": "统一客户接口、任务推进和会议纪要回流。",
            "description": "这个模块负责把客户接口、项目节奏和资料沉淀打成一个闭环。",
            "ownerName": "罗茜茜",
        },
    )
    assert created_module.status_code == 200, created_module.text
    module_payload = created_module.json()

    created_flow = client.post(
        f"/api/v1/clients/{client_id}/project-flows",
        json={
            "moduleId": module_payload["id"],
            "name": "客户周会复盘流程",
            "scenario": "客户周会后同步纪要、任务和风险。",
            "description": "先汇总会议纪要，再同步行动项与风险，最后回填项目资料。",
            "riskPoints": ["若纪要不完整，会导致任务上下文偏差。"],
        },
    )
    assert created_flow.status_code == 200, created_flow.text
    flow_payload = created_flow.json()

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "同步本周客户周会纪要",
            "desc": "把会议纪要、行动项和风险统一回填到项目底盘。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "projectModuleId": module_payload["id"],
            "projectFlowId": flow_payload["id"],
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()
    assert task_payload["clientId"] == client_id
    assert task_payload["projectModuleId"] == module_payload["id"]
    assert task_payload["projectModuleName"] == "客户协同模块"
    assert task_payload["projectFlowId"] == flow_payload["id"]
    assert task_payload["projectFlowName"] == "客户周会复盘流程"
    assert task_payload["projectContext"]["projectModuleId"] == module_payload["id"]
    assert task_payload["projectContext"]["projectFlowId"] == flow_payload["id"]
    assert "智能任务协同" in task_payload["projectContext"]["backgroundSummary"]
    assert "统一客户接口" in task_payload["projectContext"]["goalSummary"]
    assert "纪要不完整" in task_payload["projectContext"]["riskSummary"]
    assert "组织介绍" in task_payload["projectContext"]["sourceEvidence"]
    assert "项目介绍" in task_payload["projectContext"]["sourceEvidence"]
    assert "团队介绍" in task_payload["projectContext"]["sourceEvidence"]
    assert "市场背景介绍" in task_payload["projectContext"]["sourceEvidence"]
    assert f"任务模块：{module_payload['name']}" in task_payload["projectContext"]["sourceEvidence"]
    assert f"流程：{flow_payload['name']}" in task_payload["projectContext"]["sourceEvidence"]

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    assert any(item["id"] == module_payload["id"] for item in workspace_payload["projectModules"])
    assert any(item["id"] == flow_payload["id"] for item in workspace_payload["projectFlows"])


def test_task_attachment_is_archived_to_workspace_and_event_line(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "任务附件归档测试客户")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "黄河基金会方案推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "方案补齐",
            "summary": "持续推进基金会合作方案与资料沉淀。",
            "intent": "把合作方案、资料、会议和支持请求沉淀到一条线里。",
            "nextStep": "补齐关键材料并继续推进方案。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_payload = created_event_line.json()

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "补齐黄河基金会合作方案材料",
            "desc": "上传方案资料并沉淀到项目工作台。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_payload["id"],
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_payload["id"],
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "黄河基金会-合作方案补充.md",
                "# 黄河基金会合作方案\n\n本周补齐合作范围、背景资料与下一步动作。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    uploaded_task = upload_response.json()
    assert len(uploaded_task["attachments"]) == 1
    attachment = uploaded_task["attachments"][0]
    assert attachment["clientId"] == client_id
    assert attachment["eventLineId"] == event_line_payload["id"]
    assert attachment["documentId"]
    assert "本周补齐合作范围" in (attachment.get("summary") or "")
    assert Path(attachment["path"]).exists()

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    workspace_payload = workspace.json()
    assert any(document["id"] == attachment["documentId"] for document in workspace_payload["documents"])

    event_line_detail = client.get(f"/api/v1/event-lines/{event_line_payload['id']}")
    assert event_line_detail.status_code == 200, event_line_detail.text
    detail_payload = event_line_detail.json()
    assert any(
        item["sourceType"] == "attachment" and item["metadata"].get("documentId") == attachment["documentId"]
        for item in detail_payload["activities"]
    )

    evidence_count = client.app.state.app_state.db.scalar(
        "SELECT COUNT(1) AS count FROM evidence_refs WHERE source_type = 'task_attachment' AND document_id = ?",
        (attachment["documentId"],),
    )
    assert evidence_count == 1


def test_project_module_template_tasks_json_is_created_and_updated(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "模板模块保存测试客户")

    initial_template = json.dumps(
        {
            "tasks": [
                {
                    "id": "step_1",
                    "title": "准备需求访谈",
                    "description": "先梳理客户现状与访谈提纲。",
                    "daysAfterPrevious": 0,
                    "durationDays": 1,
                    "priority": "high",
                }
            ],
            "options": {"autoCreateEventLine": True, "aiFillEmpty": False},
        },
        ensure_ascii=False,
    )
    created = client.post(
        f"/api/v1/clients/{client_id}/project-modules",
        json={
            "name": "客户启动模板",
            "goal": "把客户启动阶段的标准动作固定下来。",
            "templateTasksJson": initial_template,
        },
    )
    assert created.status_code == 200, created.text
    created_payload = created.json()
    assert created_payload["templateTasksJson"] == initial_template

    updated_template = json.dumps(
        {
            "tasks": [
                {
                    "id": "step_1",
                    "title": "准备需求访谈",
                    "description": "先梳理客户现状与访谈提纲。",
                    "daysAfterPrevious": 0,
                    "durationDays": 1,
                    "priority": "high",
                },
                {
                    "id": "step_2",
                    "title": "输出启动纪要",
                    "description": "把关键目标、阻塞和后续动作写回项目底盘。",
                    "daysAfterPrevious": 1,
                    "durationDays": 1,
                    "priority": "normal",
                },
            ],
            "options": {"autoCreateEventLine": True, "aiFillEmpty": True},
        },
        ensure_ascii=False,
    )
    updated = client.patch(
        f"/api/v1/clients/{client_id}/project-modules/{created_payload['id']}",
        json={
            "name": "客户启动模板",
            "goal": "把客户启动阶段的标准动作固定下来。",
            "templateTasksJson": updated_template,
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["templateTasksJson"] == updated_template

    structure = client.get(f"/api/v1/clients/{client_id}/project-structure")
    assert structure.status_code == 200, structure.text
    module_payload = next(item for item in structure.json()["modules"] if item["id"] == created_payload["id"])
    assert module_payload["templateTasksJson"] == updated_template


def test_memory_foundation_phase1_builds_notebook_event_line_and_status(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "记忆底座测试客户")

    dna_response = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n\n这是一家围绕战略陪伴与知识沉淀提供服务的组织。",
            "fileName": "组织介绍.md",
        },
    )
    assert dna_response.status_code == 200, dna_response.text

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "记忆底座推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "资料补齐",
            "summary": "围绕客户资料补齐、会议结论和下一步动作持续推进。",
            "intent": "形成连续工作记忆，而不是只看单条任务。",
            "nextStep": "继续补齐材料并安排下次对齐会。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "补齐战略陪伴项目资料",
            "desc": "需要把客户背景、会议纪要和关键问题统一沉淀到事件线里。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    upload_response = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_id,
            "taskTitle": "补齐战略陪伴项目资料",
        },
        files={
            "file": (
                "战略陪伴补充资料.md",
                "# 补充资料\n\n这周先明确客户当前主要困境，再补齐下一步判断依据。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    task_payload = upload_response.json()
    assert task_payload["memoryHints"]
    assert task_payload["backgroundReadiness"]["level"] in {"medium", "high"}
    assert task_payload["linkedFactsPreview"]

    review_response = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W12",
            "taskEntries": [
                {
                    "taskId": task_id,
                    "contentDomain": "work",
                    "note": "本周已经补齐了部分背景，但还缺客户当前最真实的阻塞信息。",
                }
            ],
            "workFreeNote": "这周最明显的问题是背景证据还不够厚。",
        },
    )
    assert review_response.status_code == 200, review_response.text
    review_payload = review_response.json()
    summary_card = review_payload["workAnalysis"]["eventLineSummaries"][0]
    assert summary_card["eventLineId"] in {event_line_id, f"event_line::{event_line_id}"}
    if summary_card.get("memoryConfidence") is not None:
        assert summary_card["memoryConfidence"] > 0
    if summary_card.get("backgroundSources"):
        assert any(source in {"事件线记忆", "event_line_memory"} for source in summary_card["backgroundSources"])

    notebook_response = client.get(f"/api/v1/clients/{client_id}/notebook")
    assert notebook_response.status_code == 200, notebook_response.text
    notebook_payload = notebook_response.json()
    assert notebook_payload["organizationNotebookSnapshot"]["clientId"] == client_id
    assert notebook_payload["organizationNotebookSnapshot"]["currentStage"] == "推进中"
    assert notebook_payload["linkedEventLines"][0]["id"] == event_line_id
    assert any(item["factKey"].startswith("dna_module:organization_intro") for item in notebook_payload["keyFacts"])

    event_line_memory = client.get(f"/api/v1/event-lines/{event_line_id}/memory")
    assert event_line_memory.status_code == 200, event_line_memory.text
    memory_payload = event_line_memory.json()
    assert memory_payload["eventLineMemorySnapshot"]["eventLineId"] == event_line_id
    assert memory_payload["eventLineMemorySnapshot"]["lineName"] == "记忆底座推进线"
    assert memory_payload["eventLineMemorySnapshot"]["predictionReadiness"] > 0
    assert any("附件" in item or "任务" in item for item in memory_payload["evidenceRefs"])
    assert any("还缺客户当前最真实的阻塞信息" in item for item in memory_payload["eventLineMemorySnapshot"]["analysisSignals"])

    memory_status = client.get(f"/api/v1/clients/{client_id}/memory-status")
    assert memory_status.status_code == 200, memory_status.text
    status_payload = memory_status.json()
    assert status_payload["clientId"] == client_id
    assert status_payload["totalEventLines"] == 1
    assert status_payload["coveredEventLines"] == 1


def test_notebook_sanitizes_prompt_and_executive_summary_pollution(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "脏背景测试客户")
    db = client.app.state.app_state.db

    dna_response = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n\n这里先放一个正常组织介绍。",
            "fileName": "组织介绍.md",
        },
    )
    assert dna_response.status_code == 200, dna_response.text

    db.execute(
        """
        UPDATE client_dna_documents
        SET summary = ?, updated_at = ?
        WHERE client_id = ? AND module_key = 'organization_intro'
        """,
        (
            '{"prompt":"你将作为深度研究+写作综合体","title":"日慈基金会机构DNA"}',
            "2026-03-23T10:00:00",
            client_id,
        ),
    )
    db.execute(
        "UPDATE clients SET intro = ?, updated_at = ? WHERE id = ?",
        (
            "执行摘要：益语智库是专注于“可落地增长咨询”的战略陪伴者。",
            "2026-03-23T10:00:00",
            client_id,
        ),
    )

    notebook_response = client.get(f"/api/v1/clients/{client_id}/notebook")
    assert notebook_response.status_code == 200, notebook_response.text
    notebook = notebook_response.json()["organizationNotebookSnapshot"]
    assert '{"prompt"' not in notebook["organizationIntro"]
    assert "执行摘要" not in notebook["organizationIntro"]
    assert '{"prompt"' not in notebook["collaborationRelationship"]
    assert "执行摘要" not in notebook["collaborationRelationship"]


def test_task_memory_enrichment_matches_notebook_references(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "敦和合作客户")

    dna_response = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n\n敦和基金会当前由林红负责合作拓展，正在与益语讨论联合研究和后续方案边界。",
            "fileName": "组织介绍.md",
        },
    )
    assert dna_response.status_code == 200, dna_response.text

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟敦和林红吃饭",
            "desc": "先确认联合研究合作边界。",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    task_payload = next(item for item in board.json()["tasks"] if item["id"] == task_id)
    assert any("命中对象" in hint for hint in task_payload["memoryHints"])
    assert any("人物背景" in hint for hint in task_payload["memoryHints"])
    assert any("对象背景" in hint for hint in task_payload["memoryHints"])
    assert any("关联背景" in hint for hint in task_payload["memoryHints"])
    assert "notebook_reference_match" in task_payload["backgroundReadiness"]["backgroundSources"]
    assert "person_facts" in task_payload["backgroundReadiness"]["backgroundSources"]
    assert "task_reference_match" in task_payload["backgroundReadiness"]["backgroundSources"]
    assert any(fact["scopeType"] == "person" for fact in task_payload["linkedFactsPreview"])
    assert any(fact["factKey"].startswith("reference_match:") for fact in task_payload["linkedFactsPreview"])
    assert any("敦和基金会" in fact["factValue"] or "林红" in fact["factValue"] for fact in task_payload["linkedFactsPreview"])


def test_clarification_answer_writes_memory_facts(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "澄清写回答测试客户")

    created = client.post(
        "/api/v1/clarifications",
        json={
            "scopeType": "client",
            "scopeId": client_id,
            "slotKey": "current_goal",
            "question": "当前合作最核心的目标是什么？",
        },
    )
    assert created.status_code == 200, created.text
    clarification_id = created.json()["id"]

    answered = client.post(
        f"/api/v1/clarifications/{clarification_id}/answer",
        json={"answer": "先把组织背景补齐。再把季度重点和关键动作对齐。"},
    )
    assert answered.status_code == 200, answered.text
    answered_payload = answered.json()
    assert answered_payload["status"] == "answered"
    assert len(answered_payload["resolvedFactIds"]) >= 2

    notebook_response = client.get(f"/api/v1/clients/{client_id}/notebook")
    assert notebook_response.status_code == 200, notebook_response.text
    fact_values = [item["factValue"] for item in notebook_response.json()["keyFacts"]]
    assert any("先把组织背景补齐" in item for item in fact_values)
    assert any("季度重点和关键动作对齐" in item for item in fact_values)


def test_clarification_answer_backfills_person_scope_for_task_background(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "敦和合作客户")

    dna_response = client.post(
        f"/api/v1/clients/{client_id}/dna-documents/organization_intro",
        json={
            "markdownContent": "# 组织介绍\n\n敦和基金会当前由林红负责合作拓展，正在与益语讨论联合研究和后续方案边界。",
            "fileName": "组织介绍.md",
        },
    )
    assert dna_response.status_code == 200, dna_response.text

    clarification = client.post(
        "/api/v1/clarifications",
        json={
            "scopeType": "client",
            "scopeId": client_id,
            "slotKey": "partner_context",
            "question": "林红当前负责什么？",
        },
    )
    assert clarification.status_code == 200, clarification.text

    answered = client.post(
        f"/api/v1/clarifications/{clarification.json()['id']}/answer",
        json={"answer": "林红是敦和基金会合作拓展负责人，当前主要对接联合研究合作边界。"},
    )
    assert answered.status_code == 200, answered.text
    assert len(answered.json()["resolvedFactIds"]) >= 2

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟林红确认联合研究边界",
            "desc": "确认下一步合作方案。",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    task_payload = next(item for item in board.json()["tasks"] if item["id"] == task_id)
    assert "person_facts" in task_payload["backgroundReadiness"]["backgroundSources"]
    assert any(
        fact["scopeType"] == "person" and fact["sourceType"] == "clarification"
        for fact in task_payload["linkedFactsPreview"]
    )
    assert any(
        "合作拓展负责人" in fact["factValue"]
        for fact in task_payload["linkedFactsPreview"]
        if fact["scopeType"] == "person"
    )


def test_refresh_task_contexts_backfills_existing_tasks(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "黄河基金会")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "黄河基金会合作方案推进线",
            "kind": "project_line",
            "status": "active",
            "summary": "围绕黄河基金会合作方案持续推进。",
            "intent": "确认合作方向，补齐方案材料。",
            "nextStep": "进入方案确认并继续推进对外沟通。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_module = client.post(
        f"/api/v1/clients/{client_id}/project-modules",
        json={
            "name": "合作方案",
            "goal": "推进合作方案确认与落地。",
            "description": "围绕合作方案进行分析、补齐和确认。",
            "keywords": ["合作方案", "方案确认", "基金会合作"],
        },
    )
    assert created_module.status_code == 200, created_module.text
    module_id = created_module.json()["id"]

    created_flow = client.post(
        f"/api/v1/clients/{client_id}/project-flows",
        json={
            "moduleId": module_id,
            "name": "方案确认",
            "description": "确认当前合作方案与推进节奏。",
            "steps": ["补齐方案", "确认方向", "继续推进"],
            "riskPoints": ["方向不清", "材料不足"],
        },
    )
    assert created_flow.status_code == 200, created_flow.text
    flow_id = created_flow.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "黄河基金会合作方案推进与方案确认",
            "desc": "先补齐合作方案资料，再推进方案确认与下一轮沟通。",
            "priority": "high",
            "listId": "list-0",
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()
    assert task_payload["clientId"] is None
    assert task_payload["eventLineId"] is None
    assert task_payload["projectModuleId"] is None
    assert task_payload["projectFlowId"] is None

    refreshed = client.post("/api/v1/tasks/refresh-contexts")
    assert refreshed.status_code == 200, refreshed.text
    refreshed_payload = refreshed.json()
    assert refreshed_payload["totalTasks"] >= 1
    assert refreshed_payload["updatedTasks"] >= 1
    assert refreshed_payload["clientUpdatedTasks"] >= 1
    assert refreshed_payload["eventLineUpdatedTasks"] >= 1
    assert refreshed_payload["moduleUpdatedTasks"] >= 1
    assert refreshed_payload["flowUpdatedTasks"] >= 1
    assert refreshed_payload["failedTasks"] == 0

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    refreshed_task = next(item for item in board.json()["tasks"] if item["id"] == task_payload["id"])
    assert refreshed_task["clientId"] == client_id
    assert refreshed_task["eventLineId"] == event_line_id
    assert refreshed_task["projectModuleId"] == module_id
    assert refreshed_task["projectFlowId"] == flow_id
    assert refreshed_task["backgroundReadiness"]["level"] in {"medium", "high"}
    event_line_memory = client.get(f"/api/v1/event-lines/{event_line_id}/memory")
    assert event_line_memory.status_code == 200, event_line_memory.text
    assert event_line_memory.json()["eventLineMemorySnapshot"]["confidence"] > 0


def test_bootstrap_event_lines_creates_starter_lines_for_existing_tasks(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "黄河基金会")

    business_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给黄河基金会系统合作方案",
            "desc": "先补齐合作方案，再推进系统合作确认与下一步沟通。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert business_task.status_code == 200, business_task.text
    business_task_id = business_task.json()["id"]
    assert business_task.json()["eventLineId"] is None

    personal_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "去体检",
            "desc": "个人安排。",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert personal_task.status_code == 200, personal_task.text
    personal_task_id = personal_task.json()["id"]

    bootstrapped = client.post("/api/v1/tasks/bootstrap-event-lines")
    assert bootstrapped.status_code == 200, bootstrapped.text
    payload = bootstrapped.json()
    assert payload["createdEventLines"] >= 1
    assert payload["linkedTasks"] >= 1
    assert payload["failedTasks"] == 0

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    items = {item["id"]: item for item in board.json()["tasks"]}
    assert items[business_task_id]["eventLineId"]
    assert items[personal_task_id]["eventLineId"] is None
    assert items[business_task_id]["backgroundReadiness"]["level"] in {"medium", "high"}

    event_lines = client.get("/api/v1/event-lines")
    assert event_lines.status_code == 200, event_lines.text
    assert len(event_lines.json()) >= 1
    memory_response = client.get(f"/api/v1/event-lines/{items[business_task_id]['eventLineId']}/memory")
    assert memory_response.status_code == 200, memory_response.text
    assert memory_response.json()["eventLineMemorySnapshot"]["predictionReadiness"] > 0


def test_event_line_context_bundle_returns_memory_tasks_and_evidence(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈基金会")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "日慈系统演示推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "演示确认",
            "summary": "围绕系统演示、反馈和下一步合作判断持续推进。",
            "intent": "让关键联系人理解益语系统与合作目标的关系。",
            "nextStep": "补齐演示反馈并推进下一轮确认。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    updated_event_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "currentBlocker": "张真还没有把这次系统演示和内部协同目标正式对齐。",
            "recentDecision": "先用系统演示确认合作边界，再决定是否扩大到正式项目。",
            "nextStep": "整理会后反馈，并约下一轮确认会。",
        },
    )
    assert updated_event_line.status_code == 200, updated_event_line.text

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给日慈张真看益语系统",
            "desc": "通过现场演示让张真判断系统和当前合作目标的关系，并收集会后动作。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    clarification = client.post(
        "/api/v1/clarifications",
        json={
            "scopeType": "client",
            "scopeId": client_id,
            "slotKey": "partner_context",
            "question": "张真在日慈当前负责什么？",
        },
    )
    assert clarification.status_code == 200, clarification.text
    answered = client.post(
        f"/api/v1/clarifications/{clarification.json()['id']}/answer",
        json={"answer": "张真目前负责日慈和益语的系统演示与下一步合作判断。"},
    )
    assert answered.status_code == 200, answered.text

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "日慈系统演示反馈.md",
                "# 演示反馈\n\n张真重点关注系统与组织现有协同流程的贴合度。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    bundle_response = client.get(f"/api/v1/event-lines/{event_line_id}/context-bundle")
    assert bundle_response.status_code == 200, bundle_response.text
    payload = bundle_response.json()
    assert payload["eventLineId"] == event_line_id
    assert payload["lineName"] == "日慈系统演示推进线"
    assert payload["currentBlocker"] == "张真还没有把这次系统演示和内部协同目标正式对齐。"
    assert payload["nextStep"] == "整理会后反馈，并约下一轮确认会。"
    assert payload["taskCount"] >= 1
    assert payload["attachmentCount"] >= 1
    assert any(item["sourceId"] == task_payload["id"] for item in payload["taskFacts"])
    assert any(item["sourceId"] == attachment["id"] for item in payload["attachmentFacts"])
    assert any("张真" in item["summary"] for item in payload["clarificationFacts"])
    assert payload["evidenceRefs"]


def test_task_views_builtins_and_custom_view_roundtrip(tmp_path: Path):
    client = make_client(tmp_path)

    listed = client.get("/api/v1/task-views")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    preset_keys = {item["key"] for item in payload["presets"]}
    assert preset_keys == {"event_line", "risk", "source", "business_category"}
    built_in_kinds = {item["kind"] for item in payload["views"] if item["builtIn"]}
    assert {"event_line", "risk", "source", "business_category"} <= built_in_kinds

    created = client.post(
        "/api/v1/task-views",
        json={
            "name": "高证据事件线",
            "kind": "custom",
            "description": "优先查看高证据、已挂事件线的任务。",
            "calendarScope": "event_line",
            "shareability": "org",
            "sortBy": "evidenceCount",
            "sortDirection": "desc",
            "visibleFields": ["title", "status", "evidenceCount", "eventLine"],
            "filterSet": {
                "onlyWithEventLine": True,
                "minimumEvidenceCount": 1,
            },
        },
    )
    assert created.status_code == 200, created.text
    created_payload = created.json()
    assert created_payload["builtIn"] is False
    assert created_payload["kind"] == "custom"
    assert created_payload["sortBy"] == "evidenceCount"
    assert created_payload["filterSet"]["onlyWithEventLine"] is True
    assert created_payload["filterSet"]["minimumEvidenceCount"] == 1

    updated = client.patch(
        f"/api/v1/task-views/{created_payload['id']}",
        json={
            "name": "高证据风险线",
            "description": "聚焦高证据且存在风险的任务。",
            "calendarScope": "risk",
            "shareability": "private",
            "sortBy": "updatedAt",
            "sortDirection": "asc",
            "visibleFields": ["title", "priority", "businessCategory", "evidenceCount"],
            "filterSet": {
                "onlyWithEventLine": True,
                "onlyRisky": True,
                "minimumEvidenceCount": 2,
            },
        },
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["name"] == "高证据风险线"
    assert updated_payload["calendarScope"] == "risk"
    assert updated_payload["sortDirection"] == "asc"
    assert updated_payload["filterSet"]["onlyRisky"] is True
    assert updated_payload["filterSet"]["minimumEvidenceCount"] == 2

    relisted = client.get("/api/v1/task-views")
    assert relisted.status_code == 200, relisted.text
    relisted_payload = relisted.json()
    custom_view = next(item for item in relisted_payload["views"] if item["id"] == created_payload["id"])
    assert custom_view["name"] == "高证据风险线"
    assert custom_view["description"] == "聚焦高证据且存在风险的任务。"


def test_task_context_preview_returns_bundle_and_judgment(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "CFFC")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "CFFC系统演示推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "战略陪伴中",
            "summary": "围绕 CFFC 的系统演示、合作判断和下一步行动持续推进。",
            "intent": "判断这次会谈是否能从关系动作收成业务结论。",
            "nextStep": "整理系统演示反馈，并确认会后动作。",
            "primaryClientId": client_id,
            "businessCategory": "业务扩展",
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    updated_event_line = client.patch(
        f"/api/v1/event-lines/{event_line_id}",
        json={
            "currentBlocker": "这次会谈的目标和会后动作还没有被明确钉住。",
            "recentDecision": "先让对方理解系统与客户价值的关系，再决定是否继续扩大合作。",
            "nextStep": "把会谈结论压成一条明确判断和下一步动作。",
        },
    )
    assert updated_event_line.status_code == 200, updated_event_line.text

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "CFFC洪峰鸿鹄计划AI技术合作",
            "desc": "线下会谈，重点看数字化平台设计附件，并判断会后是否能进入下一轮合作。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "CFFC数字化平台设计.md",
                "# 平台设计\n\n本次会谈重点确认数字化平台设计是否能服务基金会客户的深度价值。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text

    preview_response = client.get(f"/api/v1/tasks/{task_payload['id']}/context-preview")
    assert preview_response.status_code == 200, preview_response.text
    payload = preview_response.json()
    assert payload["taskId"] == task_payload["id"]
    assert payload["clientId"] == client_id
    assert payload["judgmentVersion"] == "event_line_judgment_v1"
    assert payload["bundleFingerprint"]
    assert payload["coverageScore"] >= 0
    assert payload["confidenceScore"] >= 0
    assert payload["safeOutputMode"] in {"needs_input", "summary_only", "full_judgment"}
    assert payload["publishState"] in {"local_preview", "publish_ready"}
    assert payload["contextBundle"]["eventLineId"] == event_line_id
    assert payload["contextBundle"]["lineName"] == "CFFC系统演示推进线"
    assert payload["contextBundle"]["attachmentCount"] >= 1
    assert payload["judgment"]["eventLineId"] == event_line_id
    assert payload["judgment"]["judgmentVersion"] == "event_line_judgment_v1"
    assert payload["judgment"]["bundleFingerprint"]
    assert payload["judgment"]["coverageScore"] >= 0
    assert payload["judgment"]["confidenceScore"] >= 0
    assert payload["judgment"]["safeOutputMode"] in {"needs_input", "summary_only", "full_judgment"}
    assert payload["judgment"]["publishState"] in {"local_preview", "publish_ready"}
    assert "CFFC" in payload["judgment"]["whatHappened"]
    assert "会谈" in payload["judgment"]["whatHappened"] or "系统" in payload["judgment"]["whatHappened"] or "推进" in payload["judgment"]["whatHappened"]
    assert payload["judgment"]["minimumAction"]
    assert payload["summaryChips"]
    assert payload["readiness"] in {"medium", "high"}


def test_weekly_review_draft_save_skips_augmented_generation(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    task_board = client.get("/api/v1/tasks")
    assert task_board.status_code == 200
    default_list_id = task_board.json()["lists"][0]["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "教育双年会稿件准备",
            "desc": "补齐本周任务复盘草稿",
            "priority": "high",
            "listId": default_list_id,
            "dueDate": "2026-04-17",
            "ddl": "2026-04-17",
            "tagIds": [],
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]

    def fail_if_weekly_overview_runs(*args, **kwargs):
        raise AssertionError("draft save should not trigger weekly overview generation")

    monkeypatch.setattr(app_main, "build_weekly_overview_draft", fail_if_weekly_overview_runs)

    response = client.post(
        "/api/v1/reviews/weekly/draft",
        json={
            "weekLabel": "2026-W16",
            "taskEntries": [
                {
                    "taskId": task_id,
                    "contentDomain": "work",
                    "note": "本周已经补齐了关键复盘，但暂时不重跑整份周复盘。",
                    "structuredNote": {
                        "progress": "完成任务复盘初稿",
                        "successReason": "关键经验已经写清楚",
                        "blockerReason": "",
                        "supportNeeded": "",
                        "nextAction": "下周继续完善行动项",
                    },
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["currentReview"]["weekLabel"] == "2026-W16"
    assert [item["taskId"] for item in payload["workItems"]] == [task_id]
    assert payload["workAnalysis"] is not None
    assert payload["selfReport"] is None
    assert payload["executiveOrgReport"] is None
    assert payload["departmentReports"] == []
    assert payload["agentDepartmentDigests"] == []
    assert payload["agentDepartmentPlans"] == []

    saved_entry = client.app.state.app_state.db.fetchone(
        "SELECT note FROM weekly_review_task_entries WHERE task_id = ?",
        (task_id,),
    )
    assert saved_entry is not None
    assert "完成任务复盘初稿" in str(saved_entry["note"])


def test_review_dashboard_drill_target_returns_event_line_evidence(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈基金会")

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "日慈系统演示推进线",
            "kind": "project_line",
            "status": "active",
            "stage": "演示确认",
            "summary": "围绕系统演示、反馈和下一步合作判断持续推进。",
            "intent": "让关键联系人理解益语系统与合作目标的关系。",
            "nextStep": "补齐演示反馈并推进下一轮确认。",
            "primaryClientId": client_id,
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给日慈张真看益语系统",
            "desc": "演示系统并记录反馈，判断下一步合作方向。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "eventLineId": event_line_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "日慈系统演示反馈.md",
                "# 演示反馈\n\n张真重点关注系统与组织现有协同流程的贴合度。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    drill = client.get(
        "/api/v1/reviews/dashboard/drill-target",
        params={
            "targetType": "event_line",
            "targetId": event_line_id,
            "targetLabel": "日慈系统演示推进线",
        },
    )
    assert drill.status_code == 200, drill.text
    payload = drill.json()
    assert payload["target"]["targetType"] == "event_line"
    assert payload["target"]["targetId"] == event_line_id
    assert payload["eventLineDetail"]["eventLine"]["id"] == event_line_id
    assert any(item["id"] == task_payload["id"] for item in payload["tasks"])
    assert any(item["documentId"] == attachment["documentId"] for item in payload["attachments"])
    assert payload["eventLineMemory"] is not None
    assert payload["eventLineMemory"]["confidence"] >= 0


def test_review_dashboard_drill_target_supports_meeting_and_attachment_group(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈基金会")

    created_meeting = client.post(
        f"/api/v1/clients/{client_id}/meetings",
        json={"title": "日慈系统演示推进会"},
    )
    assert created_meeting.status_code == 200, created_meeting.text
    meeting_id = created_meeting.json()["meeting"]["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "跟进日慈系统演示反馈",
            "desc": "根据会议演示反馈整理下一步动作。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "sourceType": "meeting",
            "sourceId": meeting_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "日慈系统演示纪要.md",
                "# 会议纪要\n\n后续需要把系统演示与组织现有流程衔接起来。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    meeting_drill = client.get(
        "/api/v1/reviews/dashboard/drill-target",
        params={
            "targetType": "meeting",
            "targetId": meeting_id,
            "targetLabel": "日慈系统演示推进会",
        },
    )
    assert meeting_drill.status_code == 200, meeting_drill.text
    meeting_payload = meeting_drill.json()
    assert meeting_payload["meetings"][0]["id"] == meeting_id
    assert any(item["id"] == task_payload["id"] for item in meeting_payload["tasks"])
    assert any(item["id"] == attachment["id"] for item in meeting_payload["attachments"])

    attachment_drill = client.get(
        "/api/v1/reviews/dashboard/drill-target",
        params={
            "targetType": "attachment_group",
            "targetId": f"attachment_group:{attachment['id']}",
            "targetLabel": attachment["title"],
            "targetFilters": json.dumps({"attachmentIds": [attachment["id"]], "taskIds": [task_payload["id"]]}),
        },
    )
    assert attachment_drill.status_code == 200, attachment_drill.text
    attachment_payload = attachment_drill.json()
    assert any(item["id"] == attachment["id"] for item in attachment_payload["attachments"])
    assert any(item["id"] == task_payload["id"] for item in attachment_payload["tasks"])


def test_review_dashboard_drill_target_supports_support_request(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "支持请求客户")

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "协调外部支持资源",
            "desc": "这条任务需要跨部门支持。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_payload = created_task.json()

    upload_response = client.post(
        f"/api/v1/tasks/{task_payload['id']}/attachments",
        data={
            "clientId": client_id,
            "taskTitle": task_payload["title"],
        },
        files={
            "file": (
                "支持说明.md",
                "需要额外资源支持来推进当前任务。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment = upload_response.json()["attachments"][0]

    client.app.state.app_state.db.set_setting("cloud_access_token", "test-token")

    def fake_httpx_request(method: str, url: str, **kwargs):
        parsed = httpx.URL(url)
        if method == "GET" and parsed.path == "/api/v1/support-requests":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "support_req_1",
                        "taskId": task_payload["id"],
                        "requesterUserId": "user_test",
                        "targetScope": "department",
                        "targetRefId": "dept_ops",
                        "requestType": "collaboration",
                        "urgency": "high",
                        "summary": "需要跨部门协作支持",
                        "status": "open",
                        "resolutionNote": "",
                        "createdAt": "2026-03-23T10:00:00",
                        "updatedAt": "2026-03-23T10:00:00",
                    }
                ],
            )
        if method == "GET" and parsed.path == "/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "lists": [
                        {
                            "id": task_payload["listId"],
                            "name": task_payload["listName"],
                            "color": task_payload["listColor"],
                            "sortOrder": 0,
                            "isDefault": True,
                        }
                    ],
                    "tasks": [
                        {
                            "id": task_payload["id"],
                            "title": task_payload["title"],
                            "description": task_payload["desc"],
                            "progressStatus": "todo",
                            "priority": task_payload["priority"],
                            "listId": task_payload["listId"],
                            "listName": task_payload["listName"],
                            "listColor": task_payload["listColor"],
                            "ownerName": task_payload["ownerName"],
                            "sourceType": task_payload["sourceType"],
                            "sourceId": task_payload["sourceId"],
                            "clientId": task_payload["clientId"],
                            "clientName": task_payload["clientName"],
                            "durationMinutes": task_payload["durationMinutes"],
                            "createdAt": task_payload["createdAt"],
                            "updatedAt": task_payload["updatedAt"],
                            "attachments": [],
                        }
                    ],
                },
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(httpx, "request", fake_httpx_request)

    drill = client.get(
        "/api/v1/reviews/dashboard/drill-target",
        params={
            "targetType": "support_request",
            "targetId": "support_req_1",
            "targetLabel": "需要跨部门协作支持",
        },
    )
    assert drill.status_code == 200, drill.text
    payload = drill.json()
    assert payload["supportRequests"][0]["id"] == "support_req_1"
    assert any(item["id"] == task_payload["id"] for item in payload["tasks"])
    assert any(item["id"] == attachment["id"] for item in payload["attachments"])


def test_review_dashboard_surfaces_cross_week_trend_signals(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈基金会")
    operator_id = client.app.state.app_state.db.get_setting("current_operator_id", "") or "op_qh"

    created_event_line = client.post(
        "/api/v1/event-lines",
        json={
            "name": "日慈系统演示推进线",
            "kind": "project_line",
            "stage": "演示确认",
            "primaryClientId": client_id,
            "currentBlocker": "客户真实需求与系统演示范围还没对齐。",
            "nextStep": "先确认演示目标，再补齐下一轮动作。",
            "recentDecision": "先看系统，再判断是否进入深度合作。",
        },
    )
    assert created_event_line.status_code == 200, created_event_line.text
    event_line_id = created_event_line.json()["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "给日慈张真看益语系统",
            "desc": "演示系统并判断下一步合作方向。",
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
            "eventLineId": event_line_id,
            "dueDate": "2026-03-19",
            "businessCategory": "业务扩展",
            "currentBlocker": "客户真实需求与系统演示范围还没对齐。",
            "nextAction": "整理确认问题后再约下一轮演示。",
            "recentDecision": "先做系统演示，再决定合作深度。",
        },
    )
    assert created_task.status_code == 200, created_task.text
    task_id = created_task.json()["id"]
    db = client.app.state.app_state.db

    db.execute(
        """
        INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
        VALUES(?, ?, 'task.update', 'task', ?, ?, ?)
        """,
        (
            "log_due_1",
            "本地用户",
            task_id,
            json.dumps({"dueDate": "2026-03-12"}, ensure_ascii=False),
            "2026-03-05T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
        VALUES(?, ?, 'task.update', 'task', ?, ?, ?)
        """,
        (
            "log_due_2",
            "本地用户",
            task_id,
            json.dumps({"dueDate": "2026-03-19"}, ensure_ascii=False),
            "2026-03-12T10:00:00",
        ),
    )

    db.execute(
        """
        INSERT INTO weekly_reviews(
            id, week_label, operator_id, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at
        ) VALUES(?, '2026-W11', ?, '', '', '', '', ?, ?)
        """,
        ("review_prev", operator_id, "2026-03-08T09:00:00", "2026-03-08T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W11', 'work', ?, ?, ?, ?, ?, ?)
        """,
        (
            "entry_prev",
            "review_prev",
            task_id,
            "上一周已经卡在客户确认和支持依赖上。",
            json.dumps(
                {
                    "lightweightTag": "资源不够",
                    "supportNeeded": "需要客户关键人进一步确认演示目标。",
                    "blockerReason": "客户真实需求与系统演示范围还没对齐。",
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "id": task_id,
                    "title": "给日慈张真看益语系统",
                    "status": "doing",
                    "eventLineId": event_line_id,
                    "listName": "收集箱",
                    "listColor": "#EEF2FF",
                    "orgContext": {"needsReview": True},
                    "eventLineContext": {
                        "id": event_line_id,
                        "name": "日慈系统演示推进线",
                        "currentBlocker": "客户真实需求与系统演示范围还没对齐。",
                    },
                },
                ensure_ascii=False,
            ),
            "2026-03-08T09:00:00",
            "2026-03-08T09:00:00",
            "2026-03-08T09:00:00",
        ),
    )

    db.execute(
        """
        INSERT INTO weekly_reviews(
            id, week_label, operator_id, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at
        ) VALUES(?, '2026-W12', ?, '', '', '', '', ?, ?)
        """,
        ("review_current", operator_id, "2026-03-19T10:00:00", "2026-03-19T10:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W12', 'work', ?, ?, ?, ?, ?, ?)
        """,
        (
            "entry_current",
            "review_current",
            task_id,
            "这周仍然卡在确认链上，还需要客户侧继续对齐。",
            json.dumps(
                {
                    "lightweightTag": "资源不够",
                    "supportNeeded": "还需要客户关键人给出演示边界确认。",
                    "blockerReason": "客户真实需求与系统演示范围还没对齐。",
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "id": task_id,
                    "title": "给日慈张真看益语系统",
                    "status": "doing",
                    "eventLineId": event_line_id,
                    "listName": "收集箱",
                    "listColor": "#EEF2FF",
                    "orgContext": {"needsReview": True},
                    "eventLineContext": {
                        "id": event_line_id,
                        "name": "日慈系统演示推进线",
                        "currentBlocker": "客户真实需求与系统演示范围还没对齐。",
                    },
                },
                ensure_ascii=False,
            ),
            "2026-03-19T10:00:00",
            "2026-03-19T10:00:00",
            "2026-03-19T10:00:00",
        ),
    )

    review_response = client.get("/api/v1/reviews", params={"weekLabel": "2026-W12"})
    assert review_response.status_code == 200, review_response.text
    payload = review_response.json()
    trend_signals = payload["workAnalysis"]["trendSignals"]
    signal_types = {item["signalType"] for item in trend_signals}
    assert "repeat_reschedule" in signal_types
    assert "repeat_review_pending" in signal_types
    assert "repeat_support_request" in signal_types
    assert "escalating_blocker" in signal_types

    reschedule_signal = next(item for item in trend_signals if item["signalType"] == "repeat_reschedule")
    assert task_id in reschedule_signal["relatedTaskIds"]
    assert reschedule_signal["windowLabel"] == "连续 2-3 周"


def test_memory_backfill_route_upgrades_legacy_tasks_and_reviews(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "旧任务回填客户")
    db = client.app.state.app_state.db

    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, stage, summary, intent, current_blocker, recent_decision, next_step,
            owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, 'project_line', 'active', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            "eline_legacy",
            "旧事件线",
            "资料补齐",
            "围绕旧资料和旧任务继续推进。",
            "把历史任务串成稳定推进线。",
            "客户真实阻塞还没写清。",
            "先补会议纪要。",
            "先补会议纪要并回收到同一条推进线上。",
            "legacy-owner",
            client_id,
            "旧任务回填客户",
            "2026-03-01T10:00:00",
            "2026-03-01T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, client_id, event_line_id, project_module_id, project_flow_id,
            ddl, due_date, duration_minutes, owner_name, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, 'doing', 'high', 'list-0', ?, ?, NULL, NULL, '本周', NULL, 60, '旧负责人', 'manual', NULL, '[]', '[]', ?, ?)
        """,
        (
            "task_legacy",
            "整理旧项目资料",
            "把历史会议纪要和关键判断补齐到同一条推进线上。",
            client_id,
            "eline_legacy",
            "2026-03-12T10:00:00",
            "2026-03-12T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at)
        VALUES(?, '2026-W11', '', '', '', '', ?, ?)
        """,
        ("review_legacy", "2026-03-02T10:00:00", "2026-03-02T10:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W11', 'work', ?, '{}', ?, ?, ?, ?)
        """,
        (
            "entry_legacy",
            "review_legacy",
            "task_legacy",
            "这条旧任务已经暴露出客户真实阻塞仍未被说清。",
            json.dumps(
                {
                    "id": "task_legacy",
                    "title": "整理旧项目资料",
                    "status": "doing",
                    "eventLineId": "eline_legacy",
                    "clientId": client_id,
                    "listName": "收集箱",
                    "ownerName": "旧负责人",
                    "tags": [],
                }
            ),
            "2026-03-02T10:00:00",
            "2026-03-02T10:00:00",
            "2026-03-02T10:00:00",
        ),
    )

    response = client.post("/api/v1/memory/backfill")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["taskFactsBackfilled"] >= 1
    assert payload["reviewSignalsBackfilled"] >= 1
    assert payload["eventLineSnapshotsRefreshed"] >= 1
    assert payload["notebooksRefreshed"] >= 1

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    task = next(item for item in board.json()["tasks"] if item["id"] == "task_legacy")
    assert task["memoryHints"]
    assert task["backgroundReadiness"]["backgroundSources"]

    reviews = client.get("/api/v1/reviews", params={"weekLabel": "2026-W11"})
    assert reviews.status_code == 200, reviews.text
    review_summary = reviews.json()["workAnalysis"]["eventLineSummaries"][0]
    assert review_summary["eventLineId"] == "eline_legacy"
    assert review_summary["memoryConfidence"] > 0
    if review_summary.get("backgroundSources"):
        assert any(source in {"事件线记忆", "event_line_memory"} for source in review_summary["backgroundSources"])


def test_weekly_review_analysis_ignores_polluted_event_line_background(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "周判断清洗客户")
    db = client.app.state.app_state.db

    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, stage, summary, intent, current_blocker, recent_decision, next_step,
            owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, 'project_line', 'active', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            "eline_dirty_review",
            "向光奖马翔宇老师介绍数字化系统",
            "关系推进",
            "执行摘要：益语智库是专注于“可落地增长咨询”的战略陪伴者。",
            '{"prompt":"你将作为深度研究 + 机构与项目运营写作综合体"}',
            "当前没有特别突出的阻塞，但仍需盯住推进收束。",
            "执行摘要：继续推进介绍。",
            "建议先明确这一阶段的核心事项。",
            "review-owner",
            client_id,
            "周判断清洗客户",
            "2026-03-21T10:00:00",
            "2026-03-21T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, client_id, event_line_id, project_module_id, project_flow_id,
            ddl, due_date, duration_minutes, owner_name, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, 'doing', 'high', 'list-0', ?, ?, NULL, NULL, '本周', NULL, 60, '顾源源', 'manual', NULL, '[]', '[]', ?, ?)
        """,
        (
            "task_dirty_review",
            "向马翔宇老师介绍数字化系统",
            "先把系统价值讲清楚，再推进后续判断。",
            client_id,
            "eline_dirty_review",
            "2026-03-21T10:00:00",
            "2026-03-21T10:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at)
        VALUES(?, '2026-W12', '', '', '', '', ?, ?)
        """,
        ("review_dirty", "2026-03-22T10:00:00", "2026-03-22T10:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W12', 'work', ?, '{}', ?, ?, ?, ?)
        """,
        (
            "entry_dirty",
            "review_dirty",
            "task_dirty_review",
            "这周已经完成第一次介绍，但还需要继续推进下次沟通。",
            json.dumps(
                {
                    "id": "task_dirty_review",
                    "title": "向马翔宇老师介绍数字化系统",
                    "status": "doing",
                    "eventLineId": "eline_dirty_review",
                    "clientId": client_id,
                    "listName": "收集箱",
                    "eventLineContext": {
                        "id": "eline_dirty_review",
                        "name": "向光奖马翔宇老师介绍数字化系统",
                        "summary": "执行摘要：益语智库是专注于“可落地增长咨询”的战略陪伴者。",
                        "intent": '{"prompt":"你将作为深度研究 + 机构与项目运营写作综合体"}',
                        "currentBlocker": "当前没有特别突出的阻塞，但仍需盯住推进收束。",
                        "recentDecision": "最近线索：正文 益语2026一季度计划 传统战略咨询这个品类正在收缩。",
                        "nextStep": "建议先明确这一阶段的核心事项。",
                    },
                    "projectContext": {
                        "currentFocus": "执行摘要：益语智库是专注于“可落地增长咨询”的战略陪伴者。"
                    },
                },
                ensure_ascii=False,
            ),
            "2026-03-22T10:00:00",
            "2026-03-22T10:00:00",
            "2026-03-22T10:00:00",
        ),
    )

    response = client.get("/api/v1/reviews", params={"weekLabel": "2026-W12"})
    assert response.status_code == 200, response.text
    summary = next(
        item
        for item in response.json()["workAnalysis"]["eventLineSummaries"]
        if item["eventLineId"] == "eline_dirty_review"
    )
    assert '{"prompt"' not in summary["whatThisLineIs"]
    assert "执行摘要" not in summary["whatThisLineIs"]
    assert '{"prompt"' not in summary["whatHappenedThisWeek"]
    assert "执行摘要" not in summary["whatHappenedThisWeek"]
    assert "最近线索：" not in summary["whatHappenedThisWeek"]
    assert "向马翔宇老师介绍数字化系统" in summary["whatHappenedThisWeek"]


def test_reviews_route_accepts_notebook_and_event_line_memory_evidence_refs(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "周复盘证据来源客户")
    db = client.app.state.app_state.db

    db.execute(
        """
        INSERT INTO organization_notebook_snapshots(
            id, client_id, organization_intro, collaboration_relationship, current_stage,
            business_modules_json, key_people_json, key_products_json, current_challenges_json,
            collaboration_goals_json, recent_facts_json, information_gaps_json, confidence, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, '[]', ?, ?, '[]', ?, ?, '[]', 0.92, ?, ?)
        """,
        (
            "notebook_review_sources",
            client_id,
            "该机构正在推进数字化合作验证。",
            "当前与益语处于方案共创与会谈推进阶段。",
            "推进中",
            json.dumps(["张真"], ensure_ascii=False),
            json.dumps(["益语系统"], ensure_ascii=False),
            json.dumps(["本周已完成第一次系统介绍"], ensure_ascii=False),
            json.dumps(["明确系统演示后的合作判断"], ensure_ascii=False),
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, business_category, stage, summary, intent, current_blocker, recent_decision, next_step, evidence_count,
            owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, 'project_line', 'active', ?, ?, ?, ?, ?, ?, ?, 3, NULL, ?, ?, ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            "eline_review_sources",
            "日慈系统演示推进线",
            "业务扩展",
            "推进中",
            "围绕系统演示与合作判断继续推进。",
            "把系统演示收束成下一步合作动作。",
            "客户还没有明确会后判断边界。",
            "本周已经完成第一次系统演示。",
            "会后收齐关键反馈，并判断是否进入下一轮。",
            "顾源源",
            client_id,
            "周复盘证据来源客户",
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO event_line_memory_snapshots(
            id, event_line_id, line_name, current_stage, current_work, current_blocker, recent_decision, next_step,
            evidence_refs_json, clarification_needs_json, analysis_signals_json, prediction_readiness, confidence, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', '[]', 0.72, 0.88, ?, ?)
        """,
        (
            "eline_memory_review_sources",
            "eline_review_sources",
            "日慈系统演示推进线",
            "推进中",
            "本周重点是完成系统介绍并确认合作目标。",
            "客户真实需求与演示范围还需对齐。",
            "已经完成第一轮介绍，等待会后反馈。",
            "整理会后问题并形成合作判断。",
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, client_id, event_line_id, project_module_id, project_flow_id,
            ddl, due_date, duration_minutes, owner_name, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, ?, ?, 'doing', 'high', 'list-0', ?, ?, NULL, NULL, '本周', NULL, 60, '顾源源', 'meeting', 'meeting_demo_1', '[]', '[]', ?, ?)
        """,
        (
            "task_review_sources",
            "给日慈张真看益语系统",
            "这次会谈要确认系统与对方合作目标的关系，并收齐会后动作。",
            client_id,
            "eline_review_sources",
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )
    db.execute(
        """
        INSERT INTO weekly_reviews(id, week_label, summary, work_free_note, personal_growth_note, personal_private_note, created_at, updated_at)
        VALUES(?, '2026-W12', '', '', '', '', ?, ?)
        """,
        ("review_sources", "2026-03-24T09:00:00", "2026-03-24T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO weekly_review_task_entries(
            id, review_id, task_id, week_label, content_domain, note, structured_note_json, task_snapshot_json, reviewed_at, created_at, updated_at
        ) VALUES(?, ?, ?, '2026-W12', 'work', ?, '{}', ?, ?, ?, ?)
        """,
        (
            "entry_sources",
            "review_sources",
            "task_review_sources",
            "这周已完成系统介绍，仍需用会后反馈确认下一轮合作动作。",
            json.dumps(
                {
                    "id": "task_review_sources",
                    "title": "给日慈张真看益语系统",
                    "status": "doing",
                    "clientId": client_id,
                    "eventLineId": "eline_review_sources",
                    "listName": "收集箱",
                    "eventLineContext": {
                        "id": "eline_review_sources",
                        "name": "日慈系统演示推进线",
                        "currentBlocker": "客户真实需求与演示范围还需对齐。",
                    },
                },
                ensure_ascii=False,
            ),
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
            "2026-03-24T09:00:00",
        ),
    )

    response = client.get("/api/v1/reviews", params={"weekLabel": "2026-W12"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload["workAnalysis"], dict)
    assert "eventLineSummaries" in payload["workAnalysis"]


def test_cloud_task_board_builds_event_line_shadow_and_memory_hints(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_token(client)

    tasks_payload = {
        "tasks": [
            {
                "id": "cloud_task_1",
                "title": "推进飞书会议联调",
                "description": "跟进授权回调和会议按钮联通情况。",
                "status": "doing",
                "priority": "high",
                "listId": "list-1",
                "listName": "客户项目",
                "listColor": "#5B7BFE",
                "eventLineId": "eline_cloud_shadow",
                "eventLineName": "飞书会议联调",
                "ownerName": "顾源源",
                "sourceType": "manual",
                "createdAt": "2026-03-20T09:00:00",
                "updatedAt": "2026-03-22T09:30:00",
                "collaborators": [],
            }
        ],
        "lists": [
            {"id": "list-1", "name": "客户项目", "color": "#5B7BFE", "sortOrder": 1, "isDefault": False}
        ],
        "tags": [],
    }

    def fake_cloud_request(method: str, url: str, **kwargs):
        normalized = "http://127.0.0.1:47830"
        if method.upper() == "GET" and url == f"{normalized}/api/v1/tasks":
            return httpx.Response(200, json=tasks_payload)
        if method.upper() == "GET" and url == f"{normalized}/api/v1/employees/directory":
            return httpx.Response(200, json=[])
        if method.upper() == "GET" and url == f"{normalized}/api/v1/event-lines/eline_cloud_shadow":
            return httpx.Response(
                200,
                json={
                    "eventLine": {
                        "id": "eline_cloud_shadow",
                        "name": "飞书会议联调",
                        "kind": "custom",
                        "status": "active",
                        "stage": "推进中",
                        "summary": "当前集中处理飞书授权回调和会议按钮闭环。",
                        "currentBlocker": "redirect URI 仍需和应用后台配置对齐。",
                        "recentDecision": "先完成回调链，再验证会议发起。",
                        "nextStep": "逐项验证授权回调、绑定状态和会议发起。",
                        "evidenceCount": 3,
                    }
                },
            )
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_cloud_request)

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    task = board.json()["tasks"][0]
    assert task["eventLineId"] == "eline_cloud_shadow"
    assert task["backgroundReadiness"]["level"] in {"medium", "high"}
    assert "event_line_memory" in task["backgroundReadiness"]["backgroundSources"]
    assert task["memoryHints"]

    shadow_row = client.app.state.app_state.db.fetchone(
        "SELECT id, name FROM event_lines WHERE id = ?",
        ("eline_cloud_shadow",),
    )
    assert shadow_row is not None

    memory_response = client.get("/api/v1/event-lines/eline_cloud_shadow/memory")
    assert memory_response.status_code == 200, memory_response.text
    snapshot = memory_response.json()["eventLineMemorySnapshot"]
    assert snapshot is not None
    assert snapshot["confidence"] > 0


def test_employee_can_edit_business_settings_but_not_sensitive_settings(tmp_path: Path):
    client = make_client(tmp_path)
    client.app.state.app_state.db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "user_emp",
                "organizationId": "org_1",
                "email": "employee@example.com",
                "fullName": "普通员工",
                "primaryRole": "employee",
                "accountStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )

    topics_updated = client.post(
        "/api/v1/settings/topics",
        json={"defaultTimeRange": "14_days"},
    )
    assert topics_updated.status_code == 200
    assert topics_updated.json()["defaultTimeRange"] == "14_days"

    sensitive = client.post(
        "/api/v1/settings",
        json={"aiProvider": "qwen", "aiModel": "qwen3.5-plus"},
    )
    assert sensitive.status_code == 403


def test_org_dna_context_is_injected_into_topics_and_analysis(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)

    uploaded = client.post(
        "/api/v1/settings/org-dna/market_intro",
        json={
            "markdownContent": "# 市场介绍\n机构目前重点关注公益咨询市场中的 AI 落地、安全治理和筹资效率议题。",
            "fileName": "market.md",
        },
    )
    assert uploaded.status_code == 200

    radar = client.post(
        "/api/v1/topics/radars",
        json={"title": "AI 安全", "prompt": "关注大模型安全方案", "timeRange": "3_days"},
    )
    assert radar.status_code == 200
    radar_id = radar.json()["id"]
    created = client.post(
        "/api/v1/topics/candidates",
        json={
            "radarId": radar_id,
            "title": "移动云推出大模型安全方案",
            "summary": "文章介绍覆盖评估、防护和数据治理的安全方案。",
            "source": "测试来源",
        },
    )
    assert created.status_code == 200
    candidate_id = created.json()["id"]
    row = wait_for_topic_insight_status(client, candidate_id)
    assert row is not None
    assert row["insight_status"] == "ready"

    captured: dict[str, str] = {}

    def fake_insight_builder(**kwargs):
        captured["organization_context"] = kwargs.get("organization_context", "")
        return {
            "overview": "一、文章主旨。二、核心观点。三、团队价值。",
            "keyPoints": ["要点一"],
            "recommendationReasons": ["值得关注"],
            "practicalUses": ["整理案例"],
        }

    def fake_generate_structured(prompt, system_instruction, context_summary):
        captured["analysis_context"] = context_summary
        return app_main.AiStructuredResponse(
            content="分析综述",
            judgment="判断",
            analysis="分析",
            actions="动作",
            timeline="时间线",
        )

    monkeypatch.setattr(client.app.state.app_state.ai, "build_topic_candidate_insight", fake_insight_builder)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_structured", fake_generate_structured)
    monkeypatch.setattr(app_main, "fetch_topic_source_excerpt", lambda url: "source excerpt")
    client.app.state.app_state.db.execute("DELETE FROM topic_candidate_insights WHERE candidate_id = ?", (candidate_id,))
    client.app.state.app_state.db.execute("UPDATE topic_candidates SET insight_status = 'pending' WHERE id = ?", (candidate_id,))
    topics_settings = client.post(
        "/api/v1/settings/topics",
        json={"requireInsightBeforeActions": False},
    )
    assert topics_settings.status_code == 200

    refreshed = client.post(f"/api/v1/topics/candidates/{candidate_id}/task-plan")
    assert refreshed.status_code == 200
    assert "公益咨询市场中的 AI 落地" in captured.get("organization_context", "")

    analysis = client.post(
        "/api/v1/analysis-tools/runs",
        json={"templateId": "tpl_systemic", "title": "组织分析", "inputText": "请分析当前系统"},
    )
    assert analysis.status_code == 200
    assert "公益咨询市场中的 AI 落地" in captured.get("analysis_context", "")
~~~

## `backend/tests/test_auth_register_flow.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_register_restores_cloud_session_immediately(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    cloud_payload = {
        "accessToken": "cloud-access-token",
        "refreshToken": "cloud-refresh-token",
        "user": {
            "id": "user_personal_1",
            "organizationId": "org_yiyu_default",
            "email": "personal@example.com",
            "fullName": "个人用户",
            "primaryRole": "employee",
            "accountStatus": "approved",
        },
    }

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        if url.endswith("/api/v1/auth/register"):
            assert method == "POST"
            assert json == {
                "email": "personal@example.com",
                "fullName": "个人用户",
                "password": "Password123!",
                "departmentId": None,
                "jobTitle": None,
                "managerName": None,
                "currentFocus": None,
                "isDepartmentLead": False,
            }
            return httpx.Response(200, json=cloud_payload)
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "personal@example.com",
            "fullName": "个人用户",
            "password": "Password123!",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["sessionMode"] == "cloud"
    assert payload["user"]["email"] == "personal@example.com"
    assert db.get_setting("cloud_access_token", "") == "cloud-access-token"
    assert db.get_setting("cloud_refresh_token", "") == "cloud-refresh-token"
    assert json.loads(db.get_setting("cloud_session_user", ""))["email"] == "personal@example.com"
~~~

## `backend/tests/test_auth_session.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_auth_me_refreshes_expired_cloud_session(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    user_payload = {
      "id": "user_guyuan",
      "organizationId": "org_yiyu_default",
      "email": "guyuan@klngo.org",
      "fullName": "顾源源",
      "primaryRole": "admin",
      "accountStatus": "approved",
    }
    db.set_setting("cloud_access_token", "expired-access")
    db.set_setting("cloud_refresh_token", "refresh-1")
    db.set_setting("cloud_session_user", json.dumps(user_payload, ensure_ascii=False))

    def fake_request(method: str, url: str, json=None, headers=None, timeout=None):
        if url.endswith("/api/v1/auth/me"):
            authorization = (headers or {}).get("Authorization")
            if authorization == "Bearer expired-access":
                return httpx.Response(401, json={"detail": "invalid token"})
            if authorization == "Bearer fresh-access":
                return httpx.Response(200, json=user_payload)
        if url.endswith("/api/v1/auth/refresh"):
            assert method == "POST"
            assert json == {"refreshToken": "refresh-1"}
            return httpx.Response(
                200,
                json={
                    "accessToken": "fresh-access",
                    "refreshToken": "refresh-2",
                    "user": user_payload,
                },
            )
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["user"]["email"] == "guyuan@klngo.org"
    assert db.get_setting("cloud_access_token", "") == "fresh-access"
    assert db.get_setting("cloud_refresh_token", "") == "refresh-2"
~~~

## `backend/tests/test_badge_engine.py`

- 编码: `utf-8`

~~~python
from pathlib import Path

from app.db import Database, to_json
from app.services.badge_engine import build_badge_board


def make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def seed_client(db: Database) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_1', '测试客户', '测试', 'example.com', 'B2B', '测试客户', 'active', '2026-03-01T09:00:00', '2026-03-01T09:00:00')
        """
    )


def seed_task_list(db: Database) -> None:
    db.execute(
        """
        INSERT INTO task_lists(id, name, color, sort_order, is_default, archived_at)
        VALUES('list_1', '默认清单', '#5B7BFE', 0, 1, NULL)
        """
    )


def test_closed_loop_meeting_badge_unlocks_and_awards_xp(tmp_path: Path):
    db = make_db(tmp_path)
    seed_client(db)
    seed_task_list(db)

    for index in range(3):
        meeting_id = f"meeting_{index}"
        date = f"2026-03-1{index + 1}T10:00:00"
        db.execute(
            """
            INSERT INTO meetings(id, client_id, title, stage, scheduled_at, transcript_text, notes, created_at, updated_at)
            VALUES(?, 'client_1', ?, 'published', ?, '', '跨组对齐', ?, ?)
            """,
            (meeting_id, f"第{index + 1}次闭环会议", date, date, date),
        )
        db.execute(
            """
            INSERT INTO decisions(id, meeting_id, summary, created_at)
            VALUES(?, ?, '会议已有明确结论', ?)
            """,
            (f"decision_{index}", meeting_id, date),
        )
        db.execute(
            """
            INSERT INTO action_items(id, meeting_id, title, owner_name, due_date, confidence, publish_status, created_at)
            VALUES(?, ?, '跟进行动项', '测试用户', '2026-03-20', 0.9, 'published', ?)
            """,
            (f"action_{index}", meeting_id, date),
        )
        db.execute(
            """
            INSERT INTO tasks(id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at)
            VALUES(?, '会议行动项', '', 'done', 'normal', 'list_1', '测试用户', '2026-03-20T18:00:00', 'meeting', ?, '[]', '[]', ?, ?)
            """,
            (f"task_{index}", meeting_id, date, date),
        )

    board = build_badge_board(db, user_id="op_1", user_name="测试用户", auto_sync=True)
    badge = next(item for category in board.categories for item in category.badges if item.id == "closed_loop_meeting")

    assert badge.state in {"lit", "mastered"}
    assert badge.unlockedAt is not None
    assert badge.progressValue >= badge.progressTarget
    assert badge.evidence

    unlock_rows = db.fetchall("SELECT badge_id, xp FROM badge_unlock_records ORDER BY unlocked_at DESC")
    assert any(str(row["badge_id"]) == "closed_loop_meeting" and int(row["xp"]) == 20 for row in unlock_rows)

    ledger_rows = db.fetchall(
        """
        SELECT l.total_xp, s.source_type, s.source_id
        FROM xp_ledger l
        INNER JOIN growth_evidence_records e ON e.id = l.evidence_id
        INNER JOIN growth_signal_events s ON s.id = e.signal_id
        WHERE s.source_type = 'badge_unlock'
        """
    )
    assert any(str(row["source_id"]) == "closed_loop_meeting" and int(row["total_xp"]) == 20 for row in ledger_rows)


def test_quick_response_badge_reports_progress_and_next_action(tmp_path: Path):
    db = make_db(tmp_path)
    seed_task_list(db)

    for index in range(3):
        task_id = f"task_{index}"
        created_at = f"2026-03-1{index + 1}T09:00:00"
        confirm_at = f"2026-03-1{index + 1}T10:00:00"
        db.execute(
            """
            INSERT INTO tasks(id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id, tags_json, tag_ids_json, created_at, updated_at)
            VALUES(?, ?, '', 'todo', 'normal', 'list_1', '测试用户', '2026-03-20T18:00:00', 'manual', NULL, '[]', '[]', ?, ?)
            """,
            (task_id, f"待响应事项{index + 1}", created_at, confirm_at),
        )
        db.execute(
            """
            INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
            VALUES(?, '测试用户', 'task.create', 'task', ?, ?, ?)
            """,
            (f"log_create_{index}", task_id, to_json({"title": f"待响应事项{index + 1}"}), created_at),
        )
        db.execute(
            """
            INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
            VALUES(?, '测试用户', 'task.confirm', 'task', ?, ?, ?)
            """,
            (f"log_confirm_{index}", task_id, to_json({"title": f"待响应事项{index + 1}"}), confirm_at),
        )

    board = build_badge_board(db, user_id="op_1", user_name="测试用户", auto_sync=False)
    badge = next(item for category in board.categories for item in category.badges if item.id == "quick_response")

    assert badge.state == "progress"
    assert badge.progressValue == 3
    assert badge.progressTarget == 15
    assert badge.progressPercent == 20
    assert "还差 12 次" in badge.nextActionText
~~~

## `backend/tests/test_cffc_sample.py`

- 编码: `utf-8`

~~~python
"""
第 6 段：CFFC 联合样本验证 — 验证"理解优先"

用 CFFC 样本验证系统已经从"单任务浅分析"进入"长时间线理解"。

输入：
- 益语背景卡（组织介绍）
- CFFC 客户背景卡
- 季度主线（推进战略陪伴客户合作）
- 同一事件线下 3 条任务
- 1 条任务复盘
- 1 次会议结构结果
- 事件线历史 2 周

验证要求：
1. 输出不能先写风险或动作
2. 必须先稳定输出 4 个主问题
3. whyItMatters 必须体现高杠杆合作判断，不只是普通任务
4. optionalAdvice 只在证据足够时出现
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    OrganizationDnaModuleRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
    TaskProjectContextRecord,
    TaskOrgContextRecord,
)
from app.services.understanding_builder import build_understanding_basic, build_understanding_enhanced


# ── 构造 CFFC 样本 ──

YIYU_ORG_DNA = [
    OrganizationDnaModuleRecord(
        moduleKey="organization_intro",
        title="组织介绍",
        markdownContent="",
        normalizedText=(
            "益语智库是一家专注于公益行业的咨询公司，为基金会和公益组织提供战略咨询、"
            "数字化转型和研究服务。当前重点方向是通过战略陪伴模式，帮助公益组织建立"
            "长期能力，同时通过行业枢纽型客户扩大市场覆盖。"
        ),
        summary="益语智库是公益行业咨询公司，通过战略陪伴帮助公益组织建立长期能力。",
    ),
    OrganizationDnaModuleRecord(
        moduleKey="business_intro",
        title="业务介绍",
        markdownContent="",
        normalizedText="益语的核心业务包括：战略咨询、数字化转型咨询、行业研究报告、AI赋能方案。收入主要来自长期战略陪伴合同。",
        summary="核心业务：战略咨询、数字化转型、行业研究、AI赋能。",
    ),
]

CFFC_PROJECT_CONTEXT = TaskProjectContextRecord(
    clientId="client_cffc",
    clientName="CFFC（中国基金会发展论坛）",
    backgroundSummary="CFFC是公益行业的重要枢纽组织，连接300+基金会，在行业内有广泛影响力和号召力。",
    goalSummary="推进AI技术合作工作坊，探索数字化战略陪伴合作模式。",
    riskSummary="CFFC内部决策链较长，需要多层审批；双方在具体合作形式上还未完全对齐。",
    infoCompleteness="medium",
)

CFFC_ORG_CONTEXT = TaskOrgContextRecord(
    departmentId="dept_strategy",
    departmentName="战略合作部",
)

# 3 条任务
TASK_1_SNAPSHOT = WeeklyReviewTaskSnapshotRecord(
    title="和冯梅老师沟通CFFC的战略说明迭代",
    status="done",
    createdAt="2026-03-18T10:00:00Z",
    listName="战略合作",
    listColor="#5B7BFE",
    ownerName="顾源源",
    eventLineId="el_cffc_001",
    eventLineName="洪峰讨论赋能合作",
    projectContext=CFFC_PROJECT_CONTEXT,
    orgContext=CFFC_ORG_CONTEXT,
)

TASK_2_SNAPSHOT = WeeklyReviewTaskSnapshotRecord(
    title="准备CFFC AI赋能工作坊方案",
    status="doing",
    createdAt="2026-03-20T10:00:00Z",
    listName="战略合作",
    listColor="#5B7BFE",
    ownerName="顾源源",
    eventLineId="el_cffc_001",
    eventLineName="洪峰讨论赋能合作",
    projectContext=CFFC_PROJECT_CONTEXT,
    orgContext=CFFC_ORG_CONTEXT,
)

TASK_3_SNAPSHOT = WeeklyReviewTaskSnapshotRecord(
    title="向光奖马翔宇老师（数字化战略协作）",
    status="done",
    createdAt="2026-03-15T10:00:00Z",
    listName="战略合作",
    listColor="#5B7BFE",
    ownerName="顾源源",
    eventLineId="el_cffc_001",
    eventLineName="洪峰讨论赋能合作",
    projectContext=CFFC_PROJECT_CONTEXT,
    orgContext=CFFC_ORG_CONTEXT,
)

TASK_1_ENTRY = WeeklyReviewTaskEntryRecord(
    id="entry_cffc_1",
    reviewId="review_w13",
    taskId="task_cffc_1",
    weekLabel="2026-W13",
    contentDomain="work",
    note="本周和冯梅老师确认了工作坊的形式和方向，她很认可AI+公益的切入点，下周准备正式提案。",
    structuredNote=WeeklyReviewTaskStructuredNoteRecord(
        reflection="冯梅老师的反馈比预期积极，CFFC内部对AI话题很感兴趣",
        completionStatus="done_on_time",
        successExperience="通过具体案例展示打动了对方",
        nextAction="下周发送正式提案",
    ),
    taskSnapshot=TASK_1_SNAPSHOT,
)

TASK_2_ENTRY = WeeklyReviewTaskEntryRecord(
    id="entry_cffc_2",
    reviewId="review_w13",
    taskId="task_cffc_2",
    weekLabel="2026-W13",
    contentDomain="work",
    note="",
    structuredNote=WeeklyReviewTaskStructuredNoteRecord(),
    taskSnapshot=TASK_2_SNAPSHOT,
)

TASK_3_ENTRY = WeeklyReviewTaskEntryRecord(
    id="entry_cffc_3",
    reviewId="review_w13",
    taskId="task_cffc_3",
    weekLabel="2026-W13",
    contentDomain="work",
    note="",
    structuredNote=WeeklyReviewTaskStructuredNoteRecord(
        completionStatus="done_on_time",
    ),
    taskSnapshot=TASK_3_SNAPSHOT,
)

# 会议
CFFC_MEETING = {
    "title": "CFFC初次战略沟通会",
    "summary": "与冯梅老师和洪峰讨论了AI技术在公益行业的应用场景，确认了工作坊形式的合作切入点，双方同意先做一次小范围试点。",
}

# 事件线历史
CFFC_EVENT_LINE_HISTORY = [
    {"weekLabel": "2026-W12", "stage": "方向确认", "taskCount": 2, "completedCount": 1, "keyDecisions": ["确认AI工作坊作为切入形式"]},
    {"weekLabel": "2026-W11", "stage": "初步接触", "taskCount": 1, "completedCount": 1, "keyDecisions": ["冯梅老师引荐，建立联系"]},
]


class TestCFFCSample:

    def test_basic_mode_four_outputs_present(self):
        """basic 模式下 4 个主输出必须存在。"""
        result = build_understanding_basic(
            ai=None, task_entry=TASK_1_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        assert result.whatIsThis
        assert result.whyItMatters
        assert result.progressNow
        assert result.unknowns

    def test_basic_mode_mentions_cffc(self):
        """basic 模式就应该识别出 CFFC 客户。"""
        result = build_understanding_basic(
            ai=None, task_entry=TASK_1_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        assert "CFFC" in result.whatIsThis or "CFFC" in result.whyItMatters

    def test_enhanced_mode_deeper_understanding(self):
        """enhanced 模式应该比 basic 有更深的理解。"""
        basic = build_understanding_basic(
            ai=None, task_entry=TASK_1_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        enhanced = build_understanding_enhanced(
            ai=None,
            task_entry=TASK_1_ENTRY,
            org_dna_modules=YIYU_ORG_DNA,
            event_line_name="洪峰讨论赋能合作",
            event_line_stage="方案落地",
            event_line_summary="益语与CFFC探索AI赋能合作，从工作坊切入",
            event_line_history=CFFC_EVENT_LINE_HISTORY,
            meetings=[CFFC_MEETING],
        )
        assert enhanced.mode == "enhanced"
        # enhanced 应该有更多可用源（coverage 可能因分母变大而不严格更高）
        enhanced_available = sum(1 for s in enhanced.sourceBreakdown if s.available)
        basic_available = sum(1 for s in basic.sourceBreakdown if s.available)
        assert enhanced_available > basic_available

    def test_enhanced_no_premature_advice(self):
        """LLM 不可用时，enhanced 也不硬写 optionalAdvice。"""
        result = build_understanding_enhanced(
            ai=None,
            task_entry=TASK_1_ENTRY,
            org_dna_modules=YIYU_ORG_DNA,
            event_line_name="洪峰讨论赋能合作",
            event_line_history=CFFC_EVENT_LINE_HISTORY,
        )
        assert result.optionalAdvice is None

    def test_basic_never_starts_with_risk(self):
        """输出不能先写风险或动作 — whatIsThis 不应该包含'风险'或'阻碍'。"""
        result = build_understanding_basic(
            ai=None, task_entry=TASK_1_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        first_output = result.whatIsThis
        assert "风险" not in first_output
        assert "阻碍" not in first_output
        assert "建议" not in first_output

    def test_task_without_review_still_produces_result(self):
        """没有复盘资料的任务也必须产出结果。"""
        result = build_understanding_basic(
            ai=None, task_entry=TASK_2_ENTRY, org_dna_modules=YIYU_ORG_DNA,
        )
        assert result.whatIsThis
        assert result.whyItMatters
        assert "CFFC" in result.whatIsThis or "CFFC" in result.whyItMatters

    def test_source_breakdown_reflects_actual_inputs(self):
        """sourceBreakdown 应该准确反映哪些输入可用。"""
        result = build_understanding_enhanced(
            ai=None,
            task_entry=TASK_1_ENTRY,
            org_dna_modules=YIYU_ORG_DNA,
            event_line_name="洪峰讨论赋能合作",
            meetings=[CFFC_MEETING],
        )
        source_map = {s.sourceType: s.available for s in result.sourceBreakdown}
        assert source_map["org_dna"] is True
        assert source_map["client_background"] is True
        assert source_map["task_title"] is True
        assert source_map["review_note"] is True
        assert source_map["event_line_memory"] is True
        assert source_map["meeting"] is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
~~~

## `backend/tests/test_diagnosis_engines.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.diagnosis_engines import (
    BettaFishAdapter,
    DiagnosisEngineEndpoint,
    DiagnosisEngineRequest,
    MiroFishAdapter,
    collect_diagnosis_engine_health,
)


def test_request_payload_is_trimmed() -> None:
    payload = DiagnosisEngineRequest(
        scene="pr",
        audience_type="public",
        content="x" * 80,
        knowledge_refs=[{"title": "A" * 120, "summary": "B" * 400}] * 8,
        case_refs=[{"title": "Case", "summary": "C" * 400}] * 8,
    )

    normalized = payload.to_payload(max_payload_chars=20, max_context_items=2)

    assert normalized["content"].endswith("...")
    assert len(normalized["knowledge_refs"]) == 2
    assert len(normalized["case_refs"]) == 2
    assert normalized["knowledge_refs"][0]["title"].endswith("...")


def test_healthcheck_reports_disabled_endpoint() -> None:
    endpoint = DiagnosisEngineEndpoint(
        engine_key="bettafish",
        enabled=False,
        base_url="http://127.0.0.1:18101",
        analyze_path="/analyze",
        health_path="/health",
    )

    report = BettaFishAdapter(endpoint).healthcheck()

    assert report.status == "disabled"
    assert report.reachable is False


def test_bettafish_analysis_extracts_nested_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "data": {
                    "emotion": "skeptical",
                    "credibility": "medium",
                    "risk_points": ["语气过强", "证据不足"],
                    "misunderstanding_points": ["公众可能误以为机构在推责"],
                }
            },
        )

    transport = httpx.MockTransport(handler)
    endpoint = DiagnosisEngineEndpoint(
        engine_key="bettafish",
        enabled=True,
        base_url="http://engine.local",
        analyze_path="/analyze",
        health_path="/health",
    )
    adapter = BettaFishAdapter(endpoint, transport=transport)

    result = adapter.analyze(
        DiagnosisEngineRequest(scene="fundraising", audience_type="donor", content="test"),
    )

    assert result.emotion == "skeptical"
    assert result.credibility == "medium"
    assert result.risk_points == ["语气过强", "证据不足"]
    assert result.misunderstanding_points == ["公众可能误以为机构在推责"]


def test_mirofish_simulation_extracts_audiences_and_scenarios() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "result": {
                    "summary": "短回应会暂时止血，但证据不足时仍有二次发酵风险。",
                    "audiences": [
                        {"role": "媒体", "reaction": "关注时间线是否完整", "risk_level": "high"},
                    ],
                    "scenarios": [
                        {"strategy": "快速短回应", "outcome": "能暂时降温，但无法彻底止损"},
                    ],
                }
            },
        )

    transport = httpx.MockTransport(handler)
    endpoint = DiagnosisEngineEndpoint(
        engine_key="mirofish",
        enabled=True,
        base_url="http://engine.local",
        analyze_path="/simulate",
        health_path="/health",
    )
    adapter = MiroFishAdapter(endpoint, transport=transport)

    result = adapter.simulate(
        DiagnosisEngineRequest(scene="pr", audience_type="media", content="test"),
    )

    assert result.summary == "短回应会暂时止血，但证据不足时仍有二次发酵风险。"
    assert result.audiences == [{"role": "媒体", "reaction": "关注时间线是否完整", "risk_level": "high"}]
    assert result.scenarios == [{"strategy": "快速短回应", "outcome": "能暂时降温，但无法彻底止损"}]


def test_collect_health_reports_uses_current_env(monkeypatch) -> None:
    monkeypatch.setenv("YIYU_BETTAFISH_ENABLED", "false")
    monkeypatch.setenv("YIYU_MIROFISH_ENABLED", "false")

    reports = collect_diagnosis_engine_health()

    assert [item.engine_key for item in reports] == ["bettafish", "mirofish"]
    assert all(item.status == "disabled" for item in reports)
~~~

## `backend/tests/test_feishu_org_integration.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_local_mode_feishu_collaboration_requires_cloud_and_org(tmp_path: Path):
    client = make_client(tmp_path)

    membership = client.get("/api/v1/me/org-membership")
    assert membership.status_code == 200, membership.text
    assert membership.json()["hasOrganization"] is False

    integration = client.get("/api/v1/org-integrations/feishu")
    assert integration.status_code == 200, integration.text
    integration_payload = integration.json()
    assert integration_payload["enabled"] is False
    assert "连接云端" in integration_payload["lastValidationMessage"]

    delivery = client.get("/api/v1/me/feishu-delivery-profile")
    assert delivery.status_code == 200, delivery.text
    delivery_payload = delivery.json()
    assert delivery_payload["deliveryStatus"] == "missing_org"
    assert delivery_payload["readyForNotifications"] is False
    assert "连接云端" in delivery_payload["blockedReason"]
~~~

## `backend/tests/test_growth_engine.py`

- 编码: `utf-8`

~~~python
import json
from pathlib import Path

from app.db import Database
from app.models import (
    DecisionItem,
    HandbookEntryRecord,
    MeetingDetail,
    StrategicChecklistItemRecord,
    StrategicCockpitSnapshotRecord,
    StrategicEvidencePreviewRecord,
    StrategicHeadlineRecord,
    StrategicJudgmentRecord,
    StrategicLineRecord,
    StrategicMeetingPackDraftRecord,
    StrategicPermissionRecord,
    StrategicReadinessRecord,
    TaskAttachmentRecord,
    TaskProjectContextRecord,
    TaskRecord,
    TaskTagRecord,
    WeeklyReviewRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.growth_engine import (
    _ability_stage,
    _current_score,
    build_growth_overview,
    ingest_handbook_codification,
    ingest_meeting_growth_candidate,
    ingest_review_growth,
    ingest_strategic_growth_candidate,
    ingest_task_growth_candidate,
    list_learning_recommendations,
    mark_handbook_entry_reused,
    update_pending_capture_state,
)


def make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "app.db")


def make_review() -> WeeklyReviewRecord:
    return WeeklyReviewRecord(
        id="review_1",
        userId="op_1",
        userName="测试用户",
        weekLabel="2026-W11",
        workFreeNote="",
        personalGrowthNote="",
        personalPrivateNote="",
        submittedAt="2026-03-16T10:00:00",
        createdAt="2026-03-16T10:00:00",
        updatedAt="2026-03-16T10:00:00",
    )


def seed_client_and_event_line(db: Database) -> None:
    db.execute(
        "INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("client_1", "日慈基金会", "日慈", "philanthropy", "client", "公益客户", "active", "2026-03-10T09:00:00", "2026-03-10T09:00:00"),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, business_category, stage, summary, intent, current_blocker, recent_decision, next_step,
            evidence_count, owner_id, owner_name, primary_client_id, primary_client_name, primary_department_id, primary_department_name,
            participant_ids_json, created_at, updated_at
        ) VALUES(?, ?, 'project_line', 'active', ?, ?, ?, ?, ?, ?, ?, 2, ?, ?, ?, ?, NULL, NULL, '[]', ?, ?)
        """,
        (
            "eline_1",
            "日慈战略陪伴主线",
            "strategic_accompaniment",
            "内部对齐",
            "围绕年度重点形成季度推进闭环",
            "帮助基金会完成战略陪伴闭环",
            "跨部门信息口径还未统一",
            "先对齐今年核心议题",
            "补会前材料",
            "op_1",
            "测试用户",
            "client_1",
            "日慈基金会",
            "2026-03-10T09:00:00",
            "2026-03-10T09:00:00",
        ),
    )


def make_context_task() -> TaskRecord:
    return TaskRecord(
        id="task_ctx_1",
        title="日慈基金会季度对齐会筹备",
        desc="需要围绕年度重点补齐会前材料和关键议题。",
        status="doing",
        priority="high",
        listId="list_1",
        listName="默认清单",
        listColor="#5B7BFE",
        ddl="2026-03-20",
        dueDate="2026-03-20",
        clientId="client_1",
        clientName="日慈基金会",
        eventLineId="eline_1",
        eventLineName="日慈战略陪伴主线",
        ownerId="op_1",
        ownerName="测试用户",
        sourceType="manual",
        businessCategory="strategic_accompaniment",
        currentBlocker="会议材料还不完整",
        nextAction="补齐会前材料并确认负责人",
        recentDecision="先围绕核心议题收口再拉会",
        evidenceCount=2,
        tags=[],
        attachments=[
            TaskAttachmentRecord(
                id="attach_1",
                taskId="task_ctx_1",
                clientId="client_1",
                eventLineId="eline_1",
                title="日慈季度重点草稿",
                path="/tmp/mock.md",
                kind="markdown",
                source="local",
                sizeBytes=32,
                createdAt="2026-03-16T09:00:00",
            )
        ],
        collaborators=[],
        collaborationSummary={},
        projectContext=TaskProjectContextRecord(
            clientId="client_1",
            clientName="日慈基金会",
            stage="内部对齐",
            projectModuleId="module_1",
            projectModuleName="战略陪伴",
            projectFlowId="flow_1",
            projectFlowName="战略陪伴会前推进",
            backgroundSummary="当前项目需要先对齐今年重点议题",
            goalSummary="形成季度对齐会结论",
            riskSummary="会议目标容易发散",
            currentFocus="聚焦本季度关键议题",
            currentBlocker="材料未齐",
            nextAction="补齐会前材料",
            recentProgress="已形成初步议题",
            infoCompleteness="medium",
            sourceEvidence=["季度议题草稿"],
        ),
        memoryHints=["先确认负责人和时间点"],
        createdAt="2026-03-16T09:00:00",
        updatedAt="2026-03-16T09:30:00",
    )


def make_task_entry(
    *,
    note: str = "",
    progress: str = "",
    success_experience: str = "",
    success_reason: str = "",
    blocker_reason: str = "",
    support_needed: str = "",
    status: str = "done",
) -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id="review_item_1",
        reviewId="review_1",
        taskId="task_1",
        weekLabel="2026-W11",
        contentDomain="work",
        note=note,
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(
            progress=progress,
            successExperience=success_experience,
            successReason=success_reason,
            blockerReason=blocker_reason,
            supportNeeded=support_needed,
            completionStatus="done_on_time" if status == "done" else "in_progress",
        ),
        reviewedAt="2026-03-16T10:00:00",
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(
            title="跨组会议闭环",
            status=status,  # type: ignore[arg-type]
            dueDate=None,
            createdAt="2026-03-10T09:00:00",
            ownerId="op_1",
            ownerName="测试用户",
            tags=[TaskTagRecord(id="tag_1", name="会议", color="#5B7BFE", scope="org", updatedAt="2026-03-10T09:00:00")],
            listName="默认清单",
            listColor="#5B7BFE",
        ),
    )


def test_done_task_without_reflection_does_not_gain_xp(tmp_path: Path):
    db = make_db(tmp_path)
    review = make_review()
    entry = make_task_entry(status="done")

    ingest_review_growth(db, user_id="op_1", user_name="测试用户", review=review, task_entries=[entry], created_at="2026-03-16T10:00:00")

    rows = db.fetchall("SELECT * FROM xp_ledger")
    assert rows == []


def test_task_candidate_creates_pending_capture_without_direct_xp(tmp_path: Path):
    db = make_db(tmp_path)
    seed_client_and_event_line(db)
    task = make_context_task()

    ingest_task_growth_candidate(db, user_id="op_1", user_name="测试用户", task=task, created_at="2026-03-16T09:30:00")

    signal_rows = db.fetchall("SELECT source_type, source_id, task_id FROM growth_signal_events ORDER BY created_at DESC")
    assert signal_rows
    assert str(signal_rows[0]["source_type"]) == "task_context_candidate"
    assert str(signal_rows[0]["source_id"]) == task.id

    xp_rows = db.fetchall("SELECT * FROM xp_ledger")
    assert xp_rows == []

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert overview.pendingCaptures
    assert any(item.sourceId == task.id and item.eventLineId == "eline_1" for item in overview.pendingCaptures)
    assert any(
        any(link.objectType == "project_module" and link.objectId == "module_1" for link in item.linkedContexts)
        and any(link.objectType == "project_flow" and link.objectId == "flow_1" for link in item.linkedContexts)
        for item in overview.pendingCaptures
    )


def test_pending_capture_state_removes_item_from_open_queue(tmp_path: Path):
    db = make_db(tmp_path)
    seed_client_and_event_line(db)
    task = make_context_task()

    ingest_task_growth_candidate(db, user_id="op_1", user_name="测试用户", task=task, created_at="2026-03-16T09:30:00")

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert overview.pendingCaptures
    capture = overview.pendingCaptures[0]

    updated = update_pending_capture_state(
        db,
        user_id="op_1",
        capture_id=capture.id,
        status="dismissed",
        reason="这条候选信号先不进入本周成长队列",
        created_at="2026-03-16T09:45:00",
    )

    assert updated is not None
    assert updated.status == "dismissed"
    assert updated.stateReason == "这条候选信号先不进入本周成长队列"

    refreshed = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert all(item.id != capture.id for item in refreshed.pendingCaptures)

    state_row = db.fetchone("SELECT status, reason FROM growth_capture_states WHERE signal_id = ?", (capture.id,))
    assert state_row is not None
    assert str(state_row["status"]) == "dismissed"
    assert str(state_row["reason"]) == "这条候选信号先不进入本周成长队列"


def test_review_ingestion_is_idempotent_and_records_reflection_xp(tmp_path: Path):
    db = make_db(tmp_path)
    review = make_review()
    entry = make_task_entry(
        note="因为跨组会议容易只停在纪要，所以这次强制写了负责人和时间点，推进闭环明显更顺。",
        progress="本周完成了跨组会议收口，并把行动项同步进任务系统。",
        success_experience="会议必须写清负责人、时间点和依赖项，否则无法闭环。",
        success_reason="因为多人协作里如果边界不清，后续推进就会返工。",
        blocker_reason="前期也暴露过依赖不明确的风险。",
        support_needed="需要设计组更早确认接口边界。",
    )

    ingest_review_growth(db, user_id="op_1", user_name="测试用户", review=review, task_entries=[entry], created_at="2026-03-16T10:00:00")
    first_rows = db.fetchall("SELECT ability_key, xp_type, delta, base_xp, premium_rate, premium_xp, total_xp FROM xp_ledger ORDER BY id ASC")
    assert first_rows
    assert any(str(row["ability_key"]) == "exec" for row in first_rows)
    assert any(str(row["ability_key"]) == "collab" for row in first_rows)
    assert any(int(row["premium_xp"] or 0) > 0 for row in first_rows)
    assert all(int(row["total_xp"] or 0) == int(row["delta"] or 0) for row in first_rows)
    assert all(int(row["total_xp"] or 0) >= int(row["base_xp"] or 0) for row in first_rows)

    ingest_review_growth(db, user_id="op_1", user_name="测试用户", review=review, task_entries=[entry], created_at="2026-03-16T10:05:00")
    second_rows = db.fetchall("SELECT ability_key, xp_type, delta, base_xp, premium_rate, premium_xp, total_xp FROM xp_ledger ORDER BY id ASC")
    assert len(second_rows) == len(first_rows)
    assert sorted((row["ability_key"], row["xp_type"], row["delta"], row["base_xp"], row["premium_xp"], row["total_xp"]) for row in second_rows) == sorted(
        (row["ability_key"], row["xp_type"], row["delta"], row["base_xp"], row["premium_xp"], row["total_xp"]) for row in first_rows
    )

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert overview.weeklyXp > 0
    assert overview.weeklyBaseXp > 0
    assert overview.weeklyPremiumXp > 0
    assert overview.rank.key
    assert overview.rank.fullLabel
    assert 0 <= overview.rank.progress <= 1


def test_ability_scores_do_not_flatten_to_100_after_small_xp_threshold():
    score_map = {
        169: _current_score(169),
        227: _current_score(227),
        462: _current_score(462),
        539: _current_score(539),
        593: _current_score(593),
        907: _current_score(907),
    }

    assert score_map[169] == 64
    assert score_map[227] == 70
    assert score_map[462] == 83
    assert score_map[539] == 85
    assert score_map[593] == 86
    assert score_map[907] == 90
    assert score_map[169] < score_map[227] < score_map[462] < score_map[593] < score_map[907]
    assert max(score_map.values()) < 100
    assert _ability_stage(169)[0] == "独立"
    assert _ability_stage(907)[0] == "带动"


def test_handbook_codification_updates_write_ability_and_generates_recommendations(tmp_path: Path):
    db = make_db(tmp_path)
    entry = HandbookEntryRecord(
        id="handbook_1",
        title="会后行动项清单模板",
        summary="把会议结论沉淀成负责人、时间点、依赖项和跟进方式，后续可以复用到跨组协作里。",
        tags=["会议", "模板", "复用"],
        sourceType="meeting",
        clientId=None,
        createdAt="2026-03-16T12:00:00",
    )

    ingest_handbook_codification(db, user_id="op_1", user_name="测试用户", entry=entry, created_at="2026-03-16T12:00:00")

    ledger_rows = db.fetchall("SELECT ability_key, xp_type, premium_rate, validation_state FROM xp_ledger ORDER BY id ASC")
    assert any(str(row["ability_key"]) == "write" and str(row["xp_type"]) == "codification" for row in ledger_rows)
    assert any(float(row["premium_rate"] or 0) >= 0.2 for row in ledger_rows)
    assert all(str(row["validation_state"] or "") in {"candidate", "observed", "validated", "institutionalized"} for row in ledger_rows)

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert any(item.abilityKey == "write" and item.totalXp > 0 for item in overview.abilities)
    assert overview.weeklyBaseXp == 0
    assert overview.weeklyPremiumXp == 0
    assert overview.rank.name

    recommendations = list_learning_recommendations(db, "op_1")
    assert recommendations
    assert all(item.status == "active" for item in recommendations)


def test_meeting_candidate_generates_contextual_growth_entries(tmp_path: Path):
    db = make_db(tmp_path)
    seed_client_and_event_line(db)
    meeting = MeetingDetail(
        id="meeting_1",
        clientId="client_1",
        title="日慈基金会季度复盘会",
        stage="published",
        scheduledAt="2026-03-16T14:00:00",
        updatedAt="2026-03-16T16:00:00",
        transcriptText="这次会议先统一目标，再明确负责人和时间点。",
        notes="需要把关键结论转成行动项并挂回任务系统。",
        agendaItems=[],
        decisions=[DecisionItem(id="decision_1", summary="先围绕两个核心议题收口，再继续推进")],
        actionItems=[],
        risks=[],
        ambiguities=[],
    )

    ingest_meeting_growth_candidate(
        db,
        user_id="op_1",
        user_name="测试用户",
        client_id="client_1",
        meeting=meeting,
        event_line_ids=["eline_1"],
        created_at="2026-03-16T16:00:00",
    )

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W12")
    assert overview.weeklyXp > 0
    assert any(entry.meetingId == "meeting_1" and entry.clientId == "client_1" and entry.eventLineId == "eline_1" for entry in overview.recentEntries)
    assert any(item.label == "日慈基金会" for item in overview.projectGrowthHighlights)


def test_strategic_candidate_records_alignment_context(tmp_path: Path):
    db = make_db(tmp_path)
    snapshot = StrategicCockpitSnapshotRecord(
        clientId="client_1",
        clientName="日慈基金会",
        clientTagline="公益战略陪伴",
        stageLabel="战略判断",
        permission=StrategicPermissionRecord(canEdit=True, isCeo=False, leaderUserId="op_1"),
        readiness=StrategicReadinessRecord(status="ready", score=82, summary="核心材料已齐"),
        headline=StrategicHeadlineRecord(
            weekSummary=StrategicJudgmentRecord(value="本周先统一季度重点"),
            mainContradiction=StrategicJudgmentRecord(value="当前最大矛盾是跨部门信息没有对齐"),
            coreBreakthrough=StrategicJudgmentRecord(value="先锁定季度战略陪伴闭环"),
            focusItems=["季度重点", "跨部门协作"],
            focusStatus="confirmed",
            freshness="high",
        ),
        health=[],
        strategicLines=[
            StrategicLineRecord(
                id="sl_quarter_focus",
                title="季度战略陪伴闭环",
                summary="本季度先把战略陪伴闭环跑通，再决定是否扩展范围。",
                module="战略陪伴",
                flow="周判断",
                stage="战略判断",
                blocker="跨部门口径还没有统一",
                decision="先锁定季度战略陪伴闭环",
                nextStep="确认季度重点并分负责人",
                momentum="稳住",
                evidence=["季度重点草稿"],
            )
        ],
        twoWeekChanges=[],
        pendingDecisions=[StrategicChecklistItemRecord(title="确认季度重点", detail="先和核心负责人对齐", source="ceo", priority="high")],
        pendingMaterials=[],
        meetingPackDraft=StrategicMeetingPackDraftRecord(title="战略周会包", agenda=["确认季度重点", "收口协作边界"], groups=[]),
        evidencePreview=StrategicEvidencePreviewRecord(summary="已有季度重点草稿"),
        assetCandidates=[],
    )

    ingest_strategic_growth_candidate(
        db,
        user_id="op_1",
        user_name="测试用户",
        snapshot=snapshot,
        source_type="strategic_confirm",
        source_id="strategy_1",
        created_at="2026-03-16T18:00:00",
    )

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W12")
    assert any(entry.sourceType == "strategic_confirm" and entry.strategicLink for entry in overview.recentEntries)
    assert any(item.type == "strategic" for item in overview.strategicAlignmentHighlights)
    assert any(
        link.objectType == "strategic_focus"
        and link.objectId == "client_1:sl_quarter_focus"
        and link.label == "季度战略陪伴闭环"
        for entry in overview.recentEntries
        for link in entry.linkedContexts
    )


def test_handbook_reuse_creates_weekly_reuse_xp_and_dedupes_by_week(tmp_path: Path):
    db = make_db(tmp_path)
    entry = HandbookEntryRecord(
        id="handbook_1",
        title="会后行动项清单模板",
        summary="把会议结论沉淀成负责人、时间点、依赖项和跟进方式，后续可以复用到跨组协作里。",
        tags=["会议", "模板", "复用"],
        sourceType="meeting",
        clientId=None,
        createdAt="2026-03-16T12:00:00",
    )

    ingest_handbook_codification(db, user_id="op_1", user_name="测试用户", entry=entry, created_at="2026-03-16T12:00:00")

    response = mark_handbook_entry_reused(
        db,
        user_id="op_1",
        user_name="测试用户",
        entry=entry,
        week_label="2026-W11",
        source_type="handbook_manual_reuse",
        source_id="2026-W11",
        note="设计组继续沿用这张方法卡",
        created_at="2026-03-16T13:00:00",
    )

    assert response.duplicate is False
    assert response.gainedXp > 0
    assert response.createdEntries > 0
    assert response.validationState in {"validated", "institutionalized"}

    weekly_rows = db.fetchall(
        "SELECT xp_type, week_label, premium_rate, validation_state FROM xp_ledger WHERE week_label = ? ORDER BY id ASC",
        ("2026-W11",),
    )
    assert any(str(row["xp_type"]) == "reuse" for row in weekly_rows)
    assert all(float(row["premium_rate"] or 0) >= 0.4 for row in weekly_rows)
    assert all(str(row["validation_state"] or "") in {"validated", "institutionalized"} for row in weekly_rows)

    validation_rows = db.fetchall("SELECT event_type, source_type, source_id FROM growth_validation_events ORDER BY id ASC")
    assert validation_rows
    assert all(str(row["event_type"]) == "handbook_reused" for row in validation_rows)

    duplicate = mark_handbook_entry_reused(
        db,
        user_id="op_1",
        user_name="测试用户",
        entry=entry,
        week_label="2026-W11",
        source_type="handbook_manual_reuse",
        source_id="2026-W11",
        note="设计组继续沿用这张方法卡",
        created_at="2026-03-16T13:05:00",
    )
    assert duplicate.duplicate is True
    assert duplicate.gainedXp == 0

    overview = build_growth_overview(db, user_id="op_1", user_name="测试用户", week_label="2026-W11")
    assert overview.weeklyXp > 0
    assert overview.weeklyBaseXp > 0
    assert overview.weeklyPremiumXp > 0
    assert overview.rank.nextName is not None or overview.rank.key == "legend"


def test_handbook_reuse_records_hard_context_evidence(tmp_path: Path):
    db = make_db(tmp_path)
    entry = HandbookEntryRecord(
        id="handbook_ctx_1",
        title="会前边界澄清模板",
        summary="在跨部门会议前先澄清交付边界、负责人和预期结论，减少推诿返工。",
        tags=["会议", "模板", "边界"],
        sourceType="meeting",
        clientId="client_1",
        clientName="日慈基金会",
        eventLineId="eline_1",
        eventLineName="日慈战略陪伴主线",
        projectStage="内部对齐",
        sourceObjectType="meeting",
        sourceObjectId="meeting_1",
        sourceTitle="日慈基金会季度复盘会",
        contextSummary="这条模板主要用于跨部门会前对齐和会后责任收口。",
        createdAt="2026-03-16T12:00:00",
    )

    ingest_handbook_codification(db, user_id="op_1", user_name="测试用户", entry=entry, created_at="2026-03-16T12:00:00")

    response = mark_handbook_entry_reused(
        db,
        user_id="op_1",
        user_name="测试用户",
        entry=entry,
        week_label="2026-W11",
        source_type="task",
        source_id="task_ctx_1",
        source_label="日慈基金会季度对齐会筹备",
        context_summary="这次复用发生在会前准备阶段，直接用于收口跨组协作边界。",
        linked_contexts=[
            {
                "objectType": "task",
                "objectId": "task_ctx_1",
                "label": "日慈基金会季度对齐会筹备",
                "subtitle": "内部对齐",
                "tab": "tasks",
                "statusLabel": "进行中",
            },
            {
                "objectType": "event_line",
                "objectId": "eline_1",
                "label": "日慈战略陪伴主线",
                "subtitle": "战略陪伴",
                "tab": "tasks",
                "statusLabel": "active",
            },
        ],
        note="在当前任务里继续沿用这套边界澄清模板",
        created_at="2026-03-16T13:00:00",
    )

    assert response.duplicate is False
    validation_row = db.fetchone(
        "SELECT detail_json FROM growth_validation_events WHERE source_type = ? AND source_id = ? ORDER BY created_at DESC LIMIT 1",
        ("task", "task_ctx_1"),
    )
    assert validation_row is not None
    detail = json.loads(str(validation_row["detail_json"]))
    assert detail["sourceLabel"] == "日慈基金会季度对齐会筹备"
    assert detail["contextSummary"] == "这次复用发生在会前准备阶段，直接用于收口跨组协作边界。"
    assert any(link["objectType"] == "task" and link["objectId"] == "task_ctx_1" for link in detail["linkedContexts"])

    signal_row = db.fetchone(
        "SELECT context_json FROM growth_signal_events WHERE source_type = ? AND source_id = ? ORDER BY created_at DESC LIMIT 1",
        ("handbook_reuse", "handbook_ctx_1:task_ctx_1"),
    )
    assert signal_row is not None
    signal_context = json.loads(str(signal_row["context_json"]))
    assert signal_context["sourceObjectType"] == "meeting"
    assert signal_context["sourceTitle"] == "日慈基金会季度复盘会"
    assert signal_context["sourceLabel"] == "日慈基金会季度对齐会筹备"
    assert any(link["objectType"] == "event_line" and link["objectId"] == "eline_1" for link in signal_context["linkedContexts"])
~~~

## `backend/tests/test_growth_workbench.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_growth_workbench_understands_agreement_task(tmp_path: Path):
    client = make_client(tmp_path)

    created_client = client.post(
        "/api/v1/clients",
        json={
            "name": "CFFC",
            "alias": "CFFC",
            "domain": "公益合作",
            "type": "client",
            "intro": "CFFC 当前正在推进战略合作说明与协议边界确认。",
            "stage": "推进中",
        },
    )
    assert created_client.status_code == 200
    client_id = created_client.json()["id"]

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200
    default_list_id = board.json()["lists"][0]["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "下午找 CFFC 沟通战略合作协议",
            "desc": "需要和冯梅老师对齐战略合作协议的边界、待确认点和下一轮修改动作。",
            "priority": "high",
            "listId": default_list_id,
            "dueDate": "2026-03-24",
            "ddl": "2026-03-24",
            "clientId": client_id,
            "ownerName": "测试用户",
            "collaboratorIds": [],
            "tagIds": [],
            "businessCategory": "strategic_accompaniment",
            "currentBlocker": "缺上次沟通纪要和条款差异说明",
            "nextAction": "先整理本次必须确认的 3 个条款，再和冯梅老师沟通",
            "recentDecision": "本次先确认合作边界，不直接承诺资源与交付",
            "evidenceCount": 1,
        },
    )
    assert created_task.status_code == 200
    task_id = created_task.json()["id"]

    uploaded = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        files={"file": ("agreement-draft.md", b"# CFFC \xe5\x8d\x8f\xe8\xae\xae\xe8\x8d\x89\xe6\xa1\x88", "text/markdown")},
        data={"clientId": client_id, "taskTitle": "下午找 CFFC 沟通战略合作协议"},
    )
    assert uploaded.status_code == 200

    snapshot = client.get("/api/v1/growth/workbench")
    assert snapshot.status_code == 200
    payload = snapshot.json()

    matching = next((item for item in payload["tasks"] if item.get("linkedTaskId") == task_id), None)
    assert matching is not None
    assert matching["taskIntent"]["taskKind"] in {"agreement_alignment", "external_communication"}
    assert any(risk in matching["taskIntent"]["riskTypes"] for risk in ("boundary_risk", "commitment_risk", "negotiation_risk"))
    assert matching["universalSkills"]
    assert matching["universalSkills"][0]["sourceKind"] == "rule"
    assert matching["projectContextPack"]["taskNotes"] or matching["projectContextPack"]["clientSummary"]
    assert matching["projectContextPack"]["attachments"]
    action_groups = {item["phaseGroup"] for item in matching["actionPlan"]}
    assert {"before", "during", "after"}.issubset(action_groups)
~~~

## `backend/tests/test_knowledge_indexing.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.knowledge_base import (
    build_catalog_search_text,
    build_coverage_terms,
    clean_title_for_search,
    finance_chunk_score_adjustment,
    finance_document_score_adjustment,
    is_finance_query,
    is_finance_statement_query,
    load_surrogate_retrieval_text,
)


def test_clean_title_for_search_strips_import_suffix_noise():
    assert clean_title_for_search("基业长青2022年财务报告_CFFC_20260211.pdf") == "基业长青2022年财务报告"
    assert clean_title_for_search("CFFC_项目价值分析表 2_CFFC_20260211.pdf") == "CFFC 项目价值分析表"


def test_build_catalog_search_text_prefers_summary_and_body_over_placeholder_noise():
    catalog = build_catalog_search_text(
        title="CFFC文件+机构和业务简介-CFF2025年会手册_CFFC_20260211.md",
        short_summary="CFFC 的核心业务包括行业网络、数据资产和知识服务。",
        summary="这份材料系统介绍了机构定位、核心业务、行业角色与未来能力版图。",
        raw_text="CFFC正在从传统信息平台转向公益慈善行业的可信基础设施，围绕网络、数据与知识形成三层底盘，并以行业服务、研究倡导、共创交付等方式形成长期复利。",
        keywords=["CFFC", "机构介绍", "核心业务"],
        entities=["CFFC", "中国基金会发展论坛"],
        primary_category="组织与战略",
        secondary_category="战略规划",
        document_role="机构介绍",
    )
    assert "可作为后续问答与证据引用来源" not in catalog
    assert "CFFC 的核心业务包括行业网络、数据资产和知识服务" in catalog
    assert "可信基础设施" in catalog


def test_load_surrogate_retrieval_text_excludes_query_hint_sections(tmp_path: Path):
    surrogate = tmp_path / "surrogate.md"
    surrogate.write_text(
        "\n".join(
            [
                "# 示例文档",
                "",
                "- source_type: document",
                "- folder_category: 组织与战略",
                "- document_role: 机构介绍",
                "",
                "## overview_summary",
                "这是机构介绍摘要。",
                "",
                "## source_outline",
                "这里有真正的正文骨架。",
                "",
                "## query_hints",
                "- 不该进入 surrogate 检索正文",
                "",
                "## core_questions",
                "- 这也不该进入 surrogate 检索正文",
            ]
        ),
        encoding="utf-8",
    )
    retrieval_text = load_surrogate_retrieval_text(surrogate)
    assert "真正的正文骨架" in retrieval_text
    assert "不该进入 surrogate 检索正文" not in retrieval_text


def test_build_coverage_terms_keeps_finance_anchor_tokens_for_chunk_matching():
    tokens = ["财务情况如何", "财务情况", "情况如何", "财务", "情况", "如何"]
    coverage_terms = build_coverage_terms("财务情况如何？", tokens, ["财务与筹款"])
    assert coverage_terms[0] == "财务"
    assert "财务" in coverage_terms
    assert len(coverage_terms) <= 8


def test_is_finance_query_detects_statement_style_questions():
    assert is_finance_query("分析CFFC的财务状况")
    assert is_finance_query("有没有资产负债和现金流信息")
    assert not is_finance_query("介绍CFFC的团队")


def test_is_finance_statement_query_detects_actual_statement_questions():
    assert is_finance_statement_query("分析CFFC的财务状况")
    assert is_finance_statement_query("有没有资产负债和现金流信息")
    assert not is_finance_statement_query("预算规划怎么做")


def test_finance_document_score_adjustment_prefers_finance_reports_over_generic_intro_docs():
    finance_score = finance_document_score_adjustment(
        title="基业长青2023年财务报告_CFFC_20260211.pdf",
        summary="包含资产总额、负债总额、收入总额与费用总额。",
        document_role="财务资料",
        folder_category="财务与筹款",
        path="/tmp/财务与筹款/基业长青2023年财务报告_CFFC_20260211.pdf",
        statement_mode=True,
    )
    generic_score = finance_document_score_adjustment(
        title="CFFC核心业务介绍 2_CFFC_20260211.pdf",
        summary="介绍五个主要项目与平台化方向。",
        document_role="会议与访谈",
        folder_category="项目与业务",
        path="/tmp/项目与业务/CFFC核心业务介绍_2_CFFC_20260211.pdf",
        statement_mode=True,
    )
    assert finance_score > generic_score


def test_finance_chunk_score_adjustment_prefers_numeric_finance_chunks():
    finance_chunk = finance_chunk_score_adjustment(
        title="3 基业长青2023年财务报告_CFFC_20260211.pdf",
        excerpt="截止 2023 年 12 月 31 日，中心资产总额 751.44 万元，负债总额 42.62 万元，收入总额 880.51 万元。",
        section_label="第 1 页",
        path="/tmp/财务与筹款/3 基业长青2023年财务报告_CFFC_20260211.pdf",
        statement_mode=True,
    )
    generic_chunk = finance_chunk_score_adjustment(
        title="CFFC核心业务介绍 2_CFFC_20260211.pdf",
        excerpt="介绍年会、峰会、图书馆、数据平台与平台化方向。",
        section_label="概览",
        path="/tmp/项目与业务/CFFC核心业务介绍_2_CFFC_20260211.pdf",
        statement_mode=True,
    )
    assert finance_chunk > generic_chunk
~~~

## `backend/tests/test_knowledge_v2.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services import knowledge_base
from app.services.knowledge_v2 import (
    MAIN_KNOWLEDGE_STATUS_JOB_TYPES,
    backfill_workspace_import,
    compute_knowledge_status,
    detect_material_profile,
    ingest_document_knowledge,
    retrieve_knowledge_bundle,
)


def _insert_client(db: Database, client_id: str) -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            client_id,
            "检索测试客户",
            "检索测试客户",
            "公益",
            "内部陪伴",
            "用于知识分层测试",
            "推进中",
            "2026-03-15T00:00:00",
            "2026-03-15T00:00:00",
        ),
    )


def _insert_document_stub(
    db: Database,
    *,
    client_id: str,
    document_id: str,
    file_name: str,
    excerpt: str = "",
) -> None:
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, 'txt', 'import', ?, '[]', '2026-03-15T00:00:00')
        """,
        (
            document_id,
            client_id,
            file_name,
            f"/tmp/{file_name}",
            excerpt,
        ),
    )


def test_detect_material_profile_moves_derived_intro_to_background():
    layer, category, secondary, confidence = detect_material_profile(
        "CFFC核心业务介绍_精简版.pdf",
        "下面这份说明，完全基于你提供的材料。为了便于你后续直接做 PPT 或对外介绍，我用定位—交付—工作模式的结构来写。",
        "项目与业务",
        "核心资料",
        0.74,
    )
    assert layer == "background"
    assert category == "战略陪伴"
    assert secondary == "派生整理稿"
    assert confidence >= 0.86


def test_ingest_document_knowledge_moves_derived_intro_into_background_layer(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_reclass"
    _insert_client(db, client_id)
    document_id = "doc_intro"
    _insert_document_stub(
        db,
        client_id=client_id,
        document_id=document_id,
        file_name="CFFC核心业务介绍.txt",
        excerpt="派生介绍稿",
    )
    source_path = tmp_path / "CFFC核心业务介绍.txt"
    source_path.write_text(
        "下面这份说明，完全基于你提供的材料。为了便于你后续直接做 PPT 或对外介绍，我用定位—交付—工作模式的结构来写。",
        encoding="utf-8",
    )

    result = ingest_document_knowledge(
        db,
        data_dir=tmp_path / "data",
        client_id=client_id,
        import_id=None,
        document_id=document_id,
        source_path=source_path,
        original_source_path=source_path,
        title="CFFC核心业务介绍.txt",
        kind="txt",
        source="import",
        fallback_excerpt="派生介绍稿",
        created_at="2026-03-15T00:00:00",
        ai_service=None,
    )

    row = db.fetchone("SELECT material_layer, visible_category, secondary_category FROM v2_documents WHERE document_id = ?", (document_id,))
    assert row is not None
    assert str(row["material_layer"]) == "background"
    assert str(row["visible_category"]) == "战略陪伴"
    assert str(row["secondary_category"]) == "派生整理稿"
    assert result["material_layer"] == "background"


def test_backfill_workspace_import_registers_existing_workspace_files(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_backfill"
    _insert_client(db, client_id)

    workspace_root = tmp_path / "data" / "client_workspace" / client_id
    source_dir = workspace_root / "组织与战略"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "机构介绍.txt").write_text("日慈基金会专注于儿童心理健康与教师支持。", encoding="utf-8")

    summary = backfill_workspace_import(
        db,
        data_dir=tmp_path / "data",
        client_id=client_id,
        source_root=workspace_root,
    )

    assert summary["discovered"] == 1
    assert summary["imported"] == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM imports WHERE client_id = ?", (client_id,))) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM documents WHERE client_id = ?", (client_id,))) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM knowledge_documents WHERE client_id = ?", (client_id,))) == 1
    assert int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ?", (client_id,))) == 1


def test_compute_knowledge_status_only_counts_main_job_allowlist(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    client_id = "client_status_allowlist"
    _insert_client(db, client_id)

    db.execute(
        """
        INSERT INTO knowledge_jobs(
            id, client_id, job_type, payload_json, total_items, processed_items, status,
            last_error, created_at, started_at, finished_at, updated_at
        )
        VALUES
            ('job_ingest', ?, ?, '{}', 1, 0, 'running', NULL, '2026-04-15T08:00:00', '2026-04-15T08:00:01', NULL, '2026-04-15T08:00:02'),
            ('job_dna', ?, 'generate_client_dna_candidates', '{}', 1, 0, 'running', 'ignored', '2026-04-15T08:00:03', '2026-04-15T08:00:04', NULL, '2026-04-15T08:00:05')
        """,
        (client_id, MAIN_KNOWLEDGE_STATUS_JOB_TYPES[0], client_id),
    )

    status = compute_knowledge_status(db, client_id)

    assert status["runningJobs"] == 1
    assert status["pendingJobs"] == 0
    assert status["lastJobStatus"] == "running"
    assert status["lastJobError"] is None


def test_retrieve_knowledge_bundle_semantic_recall_can_append_new_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = Database(tmp_path / "app.db")
    client_id = "client_semantic_append"
    _insert_client(db, client_id)

    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_semantic_append', ?, NULL, '行动安排纪要', '/tmp/action-note.md', 'md', 'import', '后续安排包括负责人和截止时间。', '[]', '2026-03-15T00:00:00')
        """,
        (client_id,),
    )
    db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_semantic_append', ?, NULL, 'doc_semantic_append', 'doc_semantic_append_uid', '/tmp/action-note.md', '/tmp/action-note.md', '/tmp/action-note.md',
            '项目与业务', NULL, NULL, 0.0, '/tmp/action-note.md', 'md',
            '项目与业务', '会议纪要', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_semantic_append', 'normalized_semantic_append', '2026-03-15T00:00:00', '2026-03-15T00:00:00'
        )
        """,
        (client_id,),
    )
    db.execute(
        """
        INSERT INTO v2_documents(
            id, client_id, document_id, original_path, managed_path, markdown_path, file_name, kind,
            material_layer, visible_category, secondary_category, parse_status, parse_error, preview_text,
            doc_index_text, content_hash, classification_confidence, section_count, chunk_count, imported_at, updated_at
        )
        VALUES(
            'v2doc_semantic_append', ?, 'doc_semantic_append', '/tmp/action-note.md', '/tmp/action-note.md', NULL, '行动安排纪要.md', 'md',
            'evidence', '项目与业务', '会议纪要', 'ready', NULL, '记录了行动项和后续安排。',
            '记录行动项安排和负责人', 'hash_semantic_append', 1.0, 1, 1, '2026-03-15T00:00:00', '2026-03-15T00:00:00'
        )
        """,
        (client_id,),
    )
    db.execute(
        """
        INSERT INTO v2_sections(id, v2_document_id, section_index, title, content, searchable_text, char_count, created_at)
        VALUES('sec_semantic_append', 'v2doc_semantic_append', 0, '会议行动', '后续安排包括：确认负责人、同步截止时间、更新风险清单。', '后续安排包括负责人和截止时间', 28, '2026-03-15T00:00:00')
        """,
    )
    db.execute(
        """
        INSERT INTO v2_chunks(id, v2_document_id, v2_section_id, chunk_index, section_label, content, searchable_text, char_count, created_at)
        VALUES('chunk_semantic_append', 'v2doc_semantic_append', 'sec_semantic_append', 0, '关键片段', '后续安排包括：确认负责人、同步截止时间、更新风险清单。', '后续安排包括负责人和截止时间', 28, '2026-03-15T00:00:00')
        """,
    )
    db.execute(
        """
        INSERT INTO knowledge_surrogates(
            id, knowledge_document_id, client_id, source_type, title, folder_category, surrogate_md_path,
            overview_summary, retrieval_summary, document_role, core_questions_json, query_hints_json,
            distinct_findings_json, entities_json, time_markers_json, source_links_json, created_at, updated_at
        )
        VALUES(
            'srg_semantic_append', 'kd_semantic_append', ?, 'document', '行动安排纪要', '项目与业务', '/tmp/action-note-surrogate.md',
            '概览', '用于语义召回测试', '原始证据', '[]', '[]', '[]', '[]', '[]', '[]', '2026-03-15T00:00:00', '2026-03-15T00:00:00'
        )
        """,
        (client_id,),
    )
    db.execute(
        """
        INSERT INTO knowledge_master_index(
            id, client_id, surrogate_id, title, folder_category, document_role, retrieval_summary,
            searchable_text, source_path, surrogate_md_path, updated_at
        )
        VALUES(
            'midx_semantic_append', ?, 'srg_semantic_append', '行动安排纪要', '项目与业务', '原始证据', '用于语义召回测试',
            '后续安排包括负责人和截止时间', '/tmp/action-note.md', '/tmp/action-note-surrogate.md', '2026-03-15T00:00:00'
        )
        """,
        (client_id,),
    )

    monkeypatch.setattr(
        knowledge_base,
        "search_master_index_qdrant",
        lambda *_args, **_kwargs: {"midx_semantic_append": 0.92},
    )
    monkeypatch.setattr(
        knowledge_base,
        "search_raw_chunks_qdrant",
        lambda *_args, **_kwargs: {},
    )

    bundle = retrieve_knowledge_bundle(db, tmp_path / "data", client_id, "接下来要做什么？")

    assert bundle.retrieval_summary["semanticMappedCount"] >= 1
    assert bundle.retrieval_summary["semanticAddedDocCount"] >= 1
    assert bundle.retrieval_summary["docHitCount"] >= 1
    assert bundle.retrieval_summary["rawChunkHitCount"] >= 1
    assert any("semantic" in citation.matched_terms for citation in bundle.citations)
~~~

## `backend/tests/test_local_input_memory.py`

- 编码: `utf-8`

~~~python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_local_input_memory_includes_feishu_callback_fields() -> None:
    response = client.get(
        "/api/v1/local-input-memory",
        headers={"Origin": "http://127.0.0.1:4173"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["feishuIntegration"]["callbackMode"] == "cloud_relay"
    assert payload["feishuIntegration"]["customCallbackUrl"] == ""
~~~

## `backend/tests/test_local_mode.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_local_mode_is_available_without_cloud_login(tmp_path: Path):
    client = make_client(tmp_path)

    auth_me = client.get("/api/v1/auth/me")
    assert auth_me.status_code == 200, auth_me.text
    payload = auth_me.json()
    assert payload["authenticated"] is True
    assert payload["sessionMode"] == "local"
    assert payload["user"]["organizationId"] == "local-device"

    overview = client.get("/api/v1/account/overview")
    assert overview.status_code == 200, overview.text
    overview_payload = overview.json()
    assert overview_payload["sessionMode"] == "local"
    assert overview_payload["cloudConnected"] is False
    assert overview_payload["cloudConfig"]["mode"] == "disabled"
~~~

## `backend/tests/test_main_chain_canary.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.main_chain_canary import (  # noqa: E402
    ApiRequestError,
    WaveRunResult,
    compare_idempotency_windows,
    freeze_rc_baseline,
    load_observation_payload,
    recommend_wave1_clients,
    render_value_proof,
    render_value_proof_markdown,
)


def test_compare_idempotency_windows_reports_drift() -> None:
    previous = WaveRunResult(
        label="first",
        client_id="client_demo",
        shadow_off=True,
        job_id="job_first",
        job_status="completed",
        baseline_judgment_id="judgment_a",
        selected_candidate_id="judgment_a",
        analysis_center_counts={
            "evidenceCardCount": 4,
            "themeClusterCount": 2,
            "conflictGroupCount": 1,
            "openQuestionCount": 1,
        },
        hidden_dependency_issues=[],
    )
    rerun = WaveRunResult(
        label="rerun",
        client_id="client_demo",
        shadow_off=True,
        job_id="job_rerun",
        job_status="completed",
        baseline_judgment_id="judgment_b",
        selected_candidate_id="judgment_a",
        analysis_center_counts={
            "evidenceCardCount": 5,
            "themeClusterCount": 2,
            "conflictGroupCount": 1,
            "openQuestionCount": 1,
        },
        hidden_dependency_issues=[],
    )

    issues = compare_idempotency_windows(previous, rerun)

    assert issues == [
        "analysisCenter counts drifted after same-snapshot rerun",
        "baselineJudgment id changed after same-snapshot rerun",
    ]


def test_load_observation_payload_accepts_nested_script_output(tmp_path: Path) -> None:
    path = tmp_path / "wave.json"
    path.write_text(
        """
        {
          "recordedAt": "2026-04-15T18:00:00",
          "observation": {
            "timeRange": "Wave 2 / Day 0",
            "verdict": "pass",
            "conclusion": "Day 0 通过。"
          }
        }
        """,
        encoding="utf-8",
    )

    payload = load_observation_payload(str(path))

    assert payload["timeRange"] == "Wave 2 / Day 0"
    assert payload["verdict"] == "pass"


def test_render_value_proof_markdown_contains_core_sections() -> None:
    observation = {
        "timeRange": "Wave 2 / Day 3",
        "verdict": "watch",
        "conclusion": "指标稳定，继续观察。",
        "fallbackRateBefore": 0.18,
        "fallbackRateAfter": 0.1,
        "resolverMismatchRateBefore": 0.06,
        "resolverMismatchRateAfter": 0.02,
        "approvalBacklog": 2,
        "approvalLagHoursMedian": 6.5,
    }
    manual = {
        "releaseLabel": "v0.3.4 RC",
        "codeCompletionStatus": "pass",
        "runCompletionStatus": "watch",
        "installValidation": {
            "status": "pass",
            "appStarts": True,
            "backendStartedByInstalledApp": True,
            "overviewPanelVisible": True,
            "shadowOffParity": True,
            "workspaceBoundaryCorrect": True,
            "cockpitOfficialLayerToneCorrect": True,
            "overviewMetricsPopulated": True,
            "evidenceScreenshots": {
                "overview": "/tmp/overview.png",
                "workspace": "/tmp/workspace.png",
                "cockpit": "/tmp/cockpit.png",
            },
            "summary": "安装版和源码版行为一致。",
        },
        "judgmentConsistency": {
            "status": "基本稳定",
            "summary": "workspace、任务、会议和 cockpit 大体围绕同一套 judgment/context 说话。",
        },
        "metricsStory": {
            "importReadyTime": "主知识链 ready 更稳定。",
            "idempotencySummary": "重复运行没有膨胀。",
            "approvalSummary": "待确认判断没有明显堆积。",
        },
        "scenes": [
            {
                "name": "客户工作台",
                "before": "以前判断状态混在一起。",
                "after": "现在正式、待确认和提醒分开。",
                "stillNotGoodEnough": "待确认标签还不够醒目。",
                "confirmed": True,
                "evidence": {
                    "sampleId": "client_demo",
                    "screenshotPath": "/tmp/workspace.png",
                    "excerpt": "现在正式、待确认和提醒分开。",
                },
            }
        ],
        "reviewers": [
            {
                "name": "业务同事 A",
                "role": "顾问",
                "feedback": {
                    "boundaryClear": True,
                    "taskContextSharper": True,
                    "meetingCapturesUnresolved": False,
                    "cockpitAvoidsFakeConclusion": True,
                },
                "notes": "状态边界更清楚了。",
            }
        ],
        "nextDecision": {
            "continueObserve": True,
            "canEnterV04": False,
            "blockedBy": ["Wave 2 还未结束"],
        },
    }

    markdown = render_value_proof_markdown(observation=observation, manual=manual)

    assert "# v0.3.4 RC 价值证明结论" in markdown
    assert "## 安装版闭环" in markdown
    assert "## 场景对照" in markdown
    assert "主链判断口径：基本稳定" in markdown
    assert "47829 由安装版自拉起：通过" in markdown
    assert "待确认标签还不够醒目。" in markdown
    assert "客户工作台" in markdown
    assert "样本 client_demo" in markdown
    assert "业务同事 A / 顾问" in markdown
    assert "当前仍待补：Wave 2 还未结束" in markdown


def test_render_value_proof_markdown_marks_incomplete_business_feedback() -> None:
    observation = {
        "timeRange": "Wave 2 / Day 1",
        "verdict": "watch",
        "conclusion": "继续观察。",
        "fallbackRateBefore": 0.1,
        "fallbackRateAfter": 0.08,
        "resolverMismatchRateBefore": 0.02,
        "resolverMismatchRateAfter": 0.01,
        "approvalBacklog": 1,
        "approvalLagHoursMedian": 2.5,
    }
    manual = {
        "releaseLabel": "v0.3.4 RC",
        "codeCompletionStatus": "pass",
        "runCompletionStatus": "watch",
        "installValidation": {
            "status": "pass",
            "appStarts": True,
            "backendStartedByInstalledApp": True,
            "overviewPanelVisible": True,
            "shadowOffParity": True,
            "workspaceBoundaryCorrect": False,
            "cockpitOfficialLayerToneCorrect": False,
            "overviewMetricsPopulated": False,
        },
        "judgmentConsistency": {
            "status": "仍有漂移",
            "summary": "今天不同页面的说法还没有完全对齐。",
        },
        "metricsStory": {},
        "scenes": [],
        "reviewers": [],
        "nextDecision": {},
    }

    markdown = render_value_proof_markdown(observation=observation, manual=manual)

    assert "价值证明状态：尚未具备通过条件" in markdown
    assert "当前还没有业务同事反馈，因此不能判定价值证明通过。" in markdown
    assert "主链判断口径还未达到“稳定”" in markdown


def test_freeze_rc_baseline_contains_single_source_fields(monkeypatch, tmp_path: Path) -> None:
    class FakeApi:
        base_url = "http://127.0.0.1:47929"

        def get_stability_settings(self):
            return {
                "latestJudgmentsShadowOff": True,
                "backfillPaused": False,
                "workerCounters": {"claimCounts": {"backfill": 1}, "lockContention": {}, "backfillThrottle": {}},
                "updatedAt": "2026-04-15T12:00:00",
            }

        def get_metrics(self):
            return {
                "windowDays": 7,
                "newObjectHitRate": 0.82,
                "fallbackRate": 0.08,
                "approvalBacklog": 2,
                "approvalLagHoursMedian": 5.0,
                "candidateReviewWarningCount": 1,
                "candidateReviewOverdueCount": 0,
                "newCandidateUnreviewed24h": 1,
                "resolverMismatchRate": 0.01,
                "pageBreakdown": {},
            }

        def get_settings(self):
            return {
                "settings": {"dataDir": "/tmp/yiyu-data"},
                "health": {"appVersion": "0.1.0", "buildVersion": "2026.04.15", "startedAt": "2026-04-15T08:00:00"},
            }

    monkeypatch.setattr("scripts.main_chain_canary.get_git_commit_sha", lambda: "abc123")
    monkeypatch.setattr(
        "scripts.main_chain_canary.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": True, "dirtyPaths": ["src/renderer/App.tsx"]},
    )
    monkeypatch.setattr(
        "scripts.main_chain_canary.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_canary.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47929", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 43129,
            "backendCommand": "/Users/demo/Library/Application Support/YiyuThinkTankWorkbench/runtime/backend-venv/bin/python -m uvicorn app.main:app --port 47929",
        },
    )

    output = tmp_path / "rc-baseline.json"
    payload = freeze_rc_baseline(
        FakeApi(),
        fixed_gate_status="pass",
        full_smoke_summary="16 failed / 68 passed",
        a_class_count=0,
        b_class_summary=["Event-line / task context / cloud task board"],
        c_class_summary=["历史项"],
        notes="baseline note",
        output_path=str(output),
    )

    assert payload["commitSha"] == "abc123"
    assert payload["backendUrl"] == "http://127.0.0.1:47929"
    assert payload["databasePath"].endswith("/tmp/yiyu-data/app.db")
    assert payload["generatedAt"] == payload["recordedAt"]
    assert payload["dirtyWorktree"] is True
    assert payload["dirtyPaths"] == ["src/renderer/App.tsx"]
    assert payload["installedApp"]["rendererEntry"] == "main-demo.js"
    assert payload["installedRuntimeSignature"]["backendStartedByInstalledApp"] is True
    assert payload["installedRuntimeSignature"]["backendPid"] == 43129
    assert payload["fullSmoke"]["summary"] == "16 failed / 68 passed"
    assert payload["classification"]["aClassCount"] == 0
    assert output.exists()
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["generatedAt"] == payload["generatedAt"]
    assert written["dirtyPaths"] == ["src/renderer/App.tsx"]


def test_render_value_proof_writes_markdown_contract(tmp_path: Path) -> None:
    observation_path = tmp_path / "wave2-day0.json"
    observation_path.write_text(
        json.dumps(
            {
                "observation": {
                    "timeRange": "Wave 2 / Day 0",
                    "verdict": "watch",
                    "conclusion": "继续观察。",
                    "fallbackRateBefore": 0.12,
                    "fallbackRateAfter": 0.08,
                    "resolverMismatchRateBefore": 0.03,
                    "resolverMismatchRateAfter": 0.01,
                    "approvalBacklog": 1,
                    "approvalLagHoursMedian": 3.5,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manual_path = tmp_path / "manual.json"
    manual_path.write_text(
        json.dumps(
            {
                "releaseLabel": "v0.3.4 RC",
                "codeCompletionStatus": "pass",
                "runCompletionStatus": "watch",
                "installValidation": {
                    "status": "pass",
                    "appStarts": True,
                    "backendStartedByInstalledApp": True,
                    "overviewPanelVisible": True,
                    "shadowOffParity": True,
                    "workspaceBoundaryCorrect": True,
                    "cockpitOfficialLayerToneCorrect": True,
                    "overviewMetricsPopulated": True,
                    "evidenceScreenshots": {
                        "overview": "/tmp/overview.png",
                        "workspace": "/tmp/workspace.png",
                        "cockpit": "/tmp/cockpit.png",
                    },
                },
                "judgmentConsistency": {
                    "status": "稳定",
                    "summary": "四个主链页面围绕同一套 judgment/context 说话。",
                },
                "metricsStory": {},
                "scenes": [],
                "reviewers": [],
                "nextDecision": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    output = tmp_path / "value-proof.md"
    rendered = render_value_proof(
        observation_path=str(observation_path),
        manual_path=str(manual_path),
        output_path=str(output),
    )

    assert output.exists()
    assert rendered == output.read_text(encoding="utf-8")
    assert "# v0.3.4 RC 价值证明结论" in rendered
    assert "## 安装版闭环" in rendered
    assert "已排除 main-chain-canary=true 的样本" in rendered
    assert "本轮试跑产生的 canary 样本不计入日常审批积压指标。" in rendered
    assert "主链判断口径：稳定" in rendered
    assert "当前还没有业务同事反馈，因此不能判定价值证明通过。" in rendered


def test_recommend_wave2_skips_clients_with_broken_workspace() -> None:
    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_clients(self):
            return [
                {
                    "id": "client_ok",
                    "name": "可用客户",
                    "lastActivityAt": "2026-04-14T10:00:00",
                    "documentCount": 8,
                    "taskCount": 2,
                },
                {
                    "id": "client_fail",
                    "name": "坏客户",
                    "lastActivityAt": "2026-04-14T09:00:00",
                    "documentCount": 10,
                    "taskCount": 1,
                },
            ]

        def get_workspace(self, client_id: str):
            if client_id == "client_fail":
                raise ApiRequestError(500, "Internal Server Error")
            return {
                "knowledgeStatus": {
                    "pendingJobs": 0,
                    "runningJobs": 0,
                    "lastJobStatus": "completed",
                },
                "documentCards": [{"id": "doc_1"}],
                "meetings": [],
                "relatedTasks": [],
            }

    payload = recommend_wave1_clients(FakeApi(), limit=5, lookback_days=14)

    assert [item["clientId"] for item in payload["recommended"]] == ["client_ok"]
    assert payload["skippedClients"] == [
        {
            "clientId": "client_fail",
            "name": "坏客户",
            "reason": "Internal Server Error",
        }
    ]


def test_runbook_uses_baseline_placeholders_and_no_hard_coded_smoke_numbers() -> None:
    runbook_path = Path(__file__).resolve().parents[2] / "docs" / "main-chain-v0.3.4-rc-runbook.md"
    content = runbook_path.read_text(encoding="utf-8")

    assert "output/main-chain/rc-baseline.json" in content
    assert "http://127.0.0.1:47829" in content
    assert "main_chain_rc_ops.py" in content
    assert "capture-git-artifacts" in content
    assert "write-selection-note" in content
    assert "write-install-note" in content
    assert "write-phase-b-decision" in content
    assert "Day 0 前检查单" in content
    assert "已排除 `main-chain-canary=true` 样本" in content
    assert "runtime/main-chain-rc/v0.3.4" in content
    assert re.search(r"\b\d+\s+failed\s*/\s*\d+\s+passed\b", content) is None

    for match in re.finditer(r'--(?:b|c)-class-summary\s+"([^"]+)"', content):
        assert re.fullmatch(r"<[^>]+>", match.group(1)), match.group(0)
~~~

## `backend/tests/test_main_chain_rc_ops.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.main_chain_rc_contract import (  # noqa: E402
    attach_artifact_contract,
    default_rc_session,
    ensure_baseline_contract,
    write_rc_session,
)
from scripts.main_chain_rc_ops import (  # noqa: E402
    assess_day0_candidates,
    capture_git_artifacts,
    run_preflight,
    verify_db_isolation,
    write_invalidated_artifacts_note,
    write_install_evidence,
    write_install_note,
    write_observation_note,
    write_phase_b_decision,
    write_full_smoke_classification,
    write_selection_note,
)


def _baseline_payload(database_path: str) -> dict[str, Any]:
    return ensure_baseline_contract(
        {
            "generatedAt": "2026-04-16T10:00:00",
            "commitSha": "baseline-sha",
            "backendUrl": "http://127.0.0.1:47829",
            "databasePath": database_path,
            "latestJudgmentsShadowOff": True,
            "dirtyWorktree": False,
            "dirtyPaths": [],
            "installedRuntimeSignature": {
                "appBundleMTime": "2026-04-16T10:00:00",
                "rendererEntry": "main-demo.js",
                "backendStartedByInstalledApp": True,
                "backendPid": 12345,
            },
            "health": {"buildVersion": "2026.04.16-rc"},
            "mainChainStability": {"latestJudgmentsShadowOff": True},
        }
    )


def _write_baseline(path: Path, database_path: str) -> dict[str, Any]:
    baseline = _baseline_payload(database_path)
    path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    return baseline


def _write_session(runtime_dir: Path, baseline: dict[str, Any], baseline_path: Path, state: str = "baseline_frozen") -> None:
    session = default_rc_session(
        baseline_path=str(baseline_path.resolve()),
        session_id=str(baseline["sessionId"]),
    )
    session.update(
        {
            "state": state,
            "baselineHash": baseline["baselineHash"],
            "tupleHash": baseline["tupleHash"],
            "baselinePath": str(baseline_path.resolve()),
        }
    )
    write_rc_session(session, runtime_dir=runtime_dir)


def _write_page_proof(path: Path, baseline: dict[str, Any], page: str) -> None:
    payload = attach_artifact_contract(
        {
            "page": page,
            "screenshotPath": f"/tmp/{page}.png",
            "expectedTokens": ["token"],
            "observedTokens": ["token"],
            "matchedTokens": ["token"],
            "missingTokens": [],
            "decision": "pass",
            "reason": "all expected tokens observed",
            "recordedAt": "2026-04-18T12:00:00",
        },
        baseline,
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_preflight_reports_identity_mismatch(monkeypatch, tmp_path: Path) -> None:
    database_path = str((Path("/tmp/demo") / "app.db").resolve())
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, database_path)
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="baseline_frozen")

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {
                "latestJudgmentsShadowOff": True,
                "backfillPaused": False,
            }

        def get_metrics(self):
            return {
                "windowDays": 7,
                "fallbackRate": 0.0,
                "resolverMismatchRate": 0.0,
            }

        def get_settings(self):
            return {
                "settings": {"dataDir": "/tmp/demo"},
                "health": {"buildVersion": "2026.04.16-hotfix"},
            }

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "current-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": True, "dirtyPaths": ["src/renderer/App.tsx"]},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": False,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    with pytest.raises(RuntimeError, match="tupleHash"):
        run_preflight(FakeApi(), baseline_path=str(baseline_path), runtime_dir=str(runtime_dir))

    invalidated = json.loads((runtime_dir / "invalidated-artifacts.note.json").read_text(encoding="utf-8"))
    session = json.loads((runtime_dir / "rc-session.json").read_text(encoding="utf-8"))
    assert invalidated["invalidatedBaselineHash"] == baseline["baselineHash"]
    assert invalidated["invalidatedSessionId"] == baseline["sessionId"]
    assert session["state"] == "pre_baseline"


def test_verify_db_isolation_confirms_tmp_path_tests_and_live_app_db(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    tests_root = repo_root / "backend" / "tests"
    tests_root.mkdir(parents=True, exist_ok=True)
    (tests_root / "test_api_smoke.py").write_text(
        'from app.main import create_app\napp = create_app(tmp_path / "data")\n',
        encoding="utf-8",
    )
    (tests_root / "test_analysis_main_chain.py").write_text(
        'from app.main import create_app\napp = create_app(tmp_path / "data")\n',
        encoding="utf-8",
    )
    (tests_root / "test_tmp_db.py").write_text(
        'from app.db import Database\ndb = Database(tmp_path / "app.db")\n',
        encoding="utf-8",
    )
    home_dir = tmp_path / "home"
    live_db_path = home_dir / "Library" / "Application Support" / "YiyuThinkTankWorkbench" / "app.db"
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.collect_runtime_identity",
        lambda api, baseline_path=None: {"databasePath": str(live_db_path.resolve())},
    )

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

    payload = verify_db_isolation(
        FakeApi(),
        repo_root=repo_root,
        home_dir=home_dir,
        output_path=str(tmp_path / "db-isolation-check.json"),
    )

    assert payload["readyForBaselineRegeneration"] is True
    assert payload["liveDatabaseMatchesInstalledRuntime"] is True
    assert payload["temporaryDbPatternHits"] == ["backend/tests/test_tmp_db.py"]
    assert all(item["found"] is True for item in payload["requiredTestEvidence"])


def test_verify_db_isolation_blocks_when_static_evidence_is_incomplete(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    tests_root = repo_root / "backend" / "tests"
    tests_root.mkdir(parents=True, exist_ok=True)
    (tests_root / "test_api_smoke.py").write_text("app = object()\n", encoding="utf-8")
    (tests_root / "test_analysis_main_chain.py").write_text("app = object()\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.collect_runtime_identity",
        lambda api, baseline_path=None: {"databasePath": "/tmp/other/app.db"},
    )

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

    payload = verify_db_isolation(
        FakeApi(),
        repo_root=repo_root,
        home_dir=tmp_path / "home",
        output_path=str(tmp_path / "db-isolation-check.json"),
    )

    assert payload["readyForBaselineRegeneration"] is False
    assert payload["liveDatabaseMatchesInstalledRuntime"] is False
    assert any("apiSmokeUsesTmpDataDir" in item for item in payload["missingEvidence"])
    assert any('Database(tmp_path / "app.db")' in item for item in payload["missingEvidence"])


def test_assess_day0_candidates_selects_representative_clients_and_control_client() -> None:
    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def __init__(self) -> None:
            self.workspaces = {
                "client_cffc": {
                    "knowledgeStatus": {"pendingJobs": 0, "runningJobs": 0, "lastJobStatus": "completed", "totalDocuments": 8},
                    "documentCards": [{"id": "doc_1"}, {"id": "doc_2"}, {"id": "doc_3"}],
                    "meetings": [{"id": "meeting_1"}],
                    "relatedTasks": [{"id": "task_1", "eventLineId": "eline_1"}],
                },
                "client_a4d1db29a7": {
                    "knowledgeStatus": {"pendingJobs": 0, "runningJobs": 0, "lastJobStatus": "completed", "totalDocuments": 6},
                    "documentCards": [{"id": "doc_1"}, {"id": "doc_2"}, {"id": "doc_3"}],
                    "meetings": [],
                    "relatedTasks": [],
                },
                "client_53d82aa249": {
                    "knowledgeStatus": {"pendingJobs": 0, "runningJobs": 0, "lastJobStatus": "completed", "totalDocuments": 1},
                    "documentCards": [{"id": "doc_1"}],
                    "meetings": [{"id": "meeting_1"}],
                    "relatedTasks": [],
                },
                "client_284afd836e": {
                    "knowledgeStatus": {"pendingJobs": 0, "runningJobs": 0, "lastJobStatus": "completed", "totalDocuments": 4},
                    "documentCards": [{"id": "doc_1"}, {"id": "doc_2"}],
                    "meetings": [],
                    "relatedTasks": [],
                },
            }
            self.cockpits = {
                "client_cffc": {
                    "officialLayerStatus": "ready",
                    "radarLayer": {"candidateJudgments": [{"id": "judgment_1"}]},
                },
                "client_a4d1db29a7": {
                    "officialLayerStatus": "empty",
                    "radarLayer": {"candidateJudgments": [{"id": "judgment_1"}]},
                },
                "client_53d82aa249": {
                    "officialLayerStatus": "empty",
                    "radarLayer": {"candidateJudgments": []},
                },
                "client_284afd836e": {
                    "officialLayerStatus": "ready",
                    "radarLayer": {"candidateJudgments": []},
                },
            }

        def get_workspace(self, client_id: str):
            return self.workspaces[client_id]

        def get_cockpit(self, client_id: str):
            return self.cockpits[client_id]

    payload = assess_day0_candidates(
        FakeApi(),
        candidate_ids=["client_cffc", "client_a4d1db29a7", "client_53d82aa249", "client_284afd836e"],
    )

    assert payload["selectedClients"] == ["client_cffc", "client_a4d1db29a7", "client_53d82aa249"]
    assert payload["representationReady"] is True
    assert payload["controlClientId"] == "client_cffc"
    assert set(payload["representedCategories"]) == {"documents", "meetings_or_event_lines", "cockpit"}


def test_write_observation_note_writes_sidecar_with_required_fields(monkeypatch, tmp_path: Path) -> None:
    database_path = str((Path("/tmp/demo") / "app.db").resolve())
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, database_path)
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="wave2_active")
    observation_path = tmp_path / "wave2-day1.json"
    observation_path.write_text(json.dumps(attach_artifact_contract({}, baseline), ensure_ascii=False), encoding="utf-8")

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {
                "latestJudgmentsShadowOff": True,
                "backfillPaused": False,
            }

        def get_metrics(self):
            return {"windowDays": 7}

        def get_settings(self):
            return {
                "settings": {"dataDir": "/tmp/demo"},
                "health": {"buildVersion": "2026.04.16-rc"},
            }

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "baseline-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": False, "dirtyPaths": []},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    payload = write_observation_note(
        FakeApi(),
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        observation_path=str(observation_path),
        control_client_id="client_cffc",
        operator_note="今天指标正常，但安装版首屏比源码版慢一点。",
        output_path=None,
    )

    sidecar_path = tmp_path / "wave2-day1.note.json"
    assert sidecar_path.exists()
    assert payload["baselineGeneratedAt"] == "2026-04-16T10:00:00"
    assert payload["controlClientId"] == "client_cffc"
    assert payload["operatorNote"] == "今天指标正常，但安装版首屏比源码版慢一点。"
    assert payload["identityMatchesBaseline"] is True
    assert payload["installedRuntimeSignature"]["backendStartedByInstalledApp"] is True
    assert payload["baselineHash"] == baseline["baselineHash"]


def test_write_install_evidence_writes_default_phase_file(monkeypatch, tmp_path: Path) -> None:
    database_path = str((Path("/tmp/demo") / "app.db").resolve())
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, database_path)
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="baseline_frozen")
    overview_proof = tmp_path / "page-proof-overview.json"
    workspace_proof = tmp_path / "page-proof-workspace-state.json"
    cockpit_proof = tmp_path / "page-proof-cockpit.json"
    _write_page_proof(overview_proof, baseline, "overview")
    _write_page_proof(workspace_proof, baseline, "workspace-state")
    _write_page_proof(cockpit_proof, baseline, "cockpit")

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {
                "latestJudgmentsShadowOff": True,
                "backfillPaused": False,
            }

        def get_metrics(self):
            return {"windowDays": 7}

        def get_settings(self):
            return {
                "settings": {"dataDir": "/tmp/demo"},
                "health": {"buildVersion": "2026.04.16-rc"},
            }

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "baseline-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": False, "dirtyPaths": []},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    output = tmp_path / "install-step-a.json"
    payload = write_install_evidence(
        FakeApi(),
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        phase="step-a",
        status="pass",
        app_starts=True,
        backend_started_by_installed_app=True,
        overview_panel_visible=True,
        shadow_off_parity=True,
        workspace_boundary_correct=True,
        cockpit_official_layer_tone_correct=True,
        overview_metrics_populated=True,
        overview_screenshot="/tmp/overview.png",
        workspace_screenshot="/tmp/workspace.png",
        cockpit_screenshot="/tmp/cockpit.png",
        overview_page_proof=str(overview_proof),
        workspace_page_proof=str(workspace_proof),
        cockpit_page_proof=str(cockpit_proof),
        summary="安装版 Step A 已取到机器证据。",
        manual_backend_recovery_used=False,
        workaround_required=False,
        control_client_id=None,
        output_path=str(output),
    )

    assert output.exists()
    assert payload["backendStartedByInstalledApp"] is True
    assert payload["workspaceBoundaryCorrect"] is True
    assert payload["cockpitOfficialLayerToneCorrect"] is True
    assert payload["overviewMetricsPopulated"] is True
    assert payload["screenshots"]["workspace"] == "/tmp/workspace.png"
    assert payload["identityMatchesBaseline"] is True
    assert payload["pageProofs"]["workspace"] == str(workspace_proof.resolve())


def test_write_install_evidence_step_a_pass_rejects_manual_backend_recovery(monkeypatch, tmp_path: Path) -> None:
    database_path = str((Path("/tmp/demo") / "app.db").resolve())
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, database_path)
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="baseline_frozen")
    overview_proof = tmp_path / "page-proof-overview.json"
    workspace_proof = tmp_path / "page-proof-workspace-state.json"
    cockpit_proof = tmp_path / "page-proof-cockpit.json"
    _write_page_proof(overview_proof, baseline, "overview")
    _write_page_proof(workspace_proof, baseline, "workspace-state")
    _write_page_proof(cockpit_proof, baseline, "cockpit")

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {"latestJudgmentsShadowOff": True, "backfillPaused": False}

        def get_metrics(self):
            return {"windowDays": 7}

        def get_settings(self):
            return {"settings": {"dataDir": "/tmp/demo"}, "health": {"buildVersion": "2026.04.16-rc"}}

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "baseline-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": False, "dirtyPaths": []},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    with pytest.raises(RuntimeError, match="manual backend recovery or extra workaround"):
        write_install_evidence(
            FakeApi(),
            baseline_path=str(baseline_path),
            runtime_dir=str(runtime_dir),
            phase="step-a",
            status="pass",
            app_starts=True,
            backend_started_by_installed_app=True,
            overview_panel_visible=True,
            shadow_off_parity=True,
            workspace_boundary_correct=True,
            cockpit_official_layer_tone_correct=True,
            overview_metrics_populated=True,
            overview_screenshot="/tmp/overview.png",
            workspace_screenshot="/tmp/workspace.png",
            cockpit_screenshot="/tmp/cockpit.png",
            overview_page_proof=str(overview_proof),
            workspace_page_proof=str(workspace_proof),
            cockpit_page_proof=str(cockpit_proof),
            summary="安装版虽然启动，但靠人工救活 backend。",
            manual_backend_recovery_used=True,
            workaround_required=False,
            control_client_id=None,
            output_path=str(tmp_path / "install-step-a.json"),
        )


def test_capture_git_artifacts_writes_expected_files(monkeypatch, tmp_path: Path) -> None:
    outputs = {
        ("git", "-C", str(tmp_path), "rev-parse", "HEAD"): "abc123\n",
        ("git", "-C", str(tmp_path), "status", "--porcelain"): " M backend/scripts/main_chain_rc_ops.py\n",
        ("git", "-C", str(tmp_path), "diff", "--stat"): " 1 file changed, 10 insertions(+)\n",
        ("git", "-C", str(tmp_path), "diff"): "diff --git a/file b/file\n",
    }

    def fake_run_command(command, cwd=None):
        return 0, outputs[tuple(command)], ""

    monkeypatch.setattr("scripts.main_chain_rc_ops._run_command", fake_run_command)

    payload = capture_git_artifacts(runtime_dir=tmp_path / "rc", repo_root=tmp_path)

    assert Path(payload["artifacts"]["head.txt"]).read_text(encoding="utf-8") == "abc123\n"
    assert Path(payload["artifacts"]["status.porcelain.txt"]).read_text(encoding="utf-8") == " M backend/scripts/main_chain_rc_ops.py\n"
    assert Path(payload["artifacts"]["diff.stat.txt"]).read_text(encoding="utf-8") == " 1 file changed, 10 insertions(+)\n"
    assert Path(payload["artifacts"]["diff.patch"]).read_text(encoding="utf-8") == "diff --git a/file b/file\n"


def test_write_selection_note_captures_selected_and_rejected_reasons(tmp_path: Path) -> None:
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, str((Path("/tmp/demo") / "app.db").resolve()))
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="day0_ready")
    selection_path = tmp_path / "day0-selection.json"
    selection_path.write_text(
        json.dumps(
            attach_artifact_contract(
            {
                "controlClientId": "client_cffc",
                "controlClientReason": "选为 control client。",
                "readyForDay0": True,
                "representedCategories": ["documents", "cockpit"],
                "assessments": [
                    {
                        "clientId": "client_cffc",
                        "selected": True,
                        "selectionReason": "入选：健康，且补齐 cockpit 代表性",
                        "healthReason": "候选健康：workspace/cockpit 200",
                        "representationReason": "补齐 cockpit 代表性",
                    },
                    {
                        "clientId": "client_cb720fc373",
                        "selected": False,
                        "selectionReason": "淘汰：knowledgeReady=false",
                        "healthReason": "淘汰：knowledgeReady=false",
                        "representationReason": "具备 cockpit 代表性，但未通过健康门槛",
                    },
                ],
            },
            baseline,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = write_selection_note(
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        selection_path=str(selection_path),
        output_path=None,
    )

    note_path = tmp_path / "day0-selection.note.json"
    assert note_path.exists()
    assert payload["controlClientId"] == "client_cffc"
    assert payload["installedRuntimeSignature"]["backendStartedByInstalledApp"] is True
    assert payload["baselineHash"] == baseline["baselineHash"]
    assert payload["entries"] == [
        {
            "clientId": "client_cffc",
            "selected": True,
            "reason": "入选：健康，且补齐 cockpit 代表性",
            "healthReason": "候选健康：workspace/cockpit 200",
            "representationReason": "补齐 cockpit 代表性",
        },
        {
            "clientId": "client_cb720fc373",
            "selected": False,
            "reason": "淘汰：knowledgeReady=false",
            "healthReason": "淘汰：knowledgeReady=false",
            "representationReason": "具备 cockpit 代表性，但未通过健康门槛",
        },
    ]


def test_write_install_note_writes_blocker_class_sidecar(tmp_path: Path) -> None:
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, str((Path("/tmp/demo") / "app.db").resolve()))
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="wave2_active")

    payload = write_install_note(
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        phase="step-a",
        blocker_class="packaging",
        decision="fail",
        reason="安装版白屏，Overview 未显示。",
        evidence_path=None,
        output_path=str(tmp_path / "install-step-a.note.json"),
    )

    assert payload["blockerClass"] == "packaging"
    assert payload["decision"] == "fail"
    assert payload["reason"] == "安装版白屏，Overview 未显示。"
    assert payload["installedRuntimeSignature"]["backendStartedByInstalledApp"] is True
    assert payload["sessionId"] == baseline["sessionId"]


def test_write_install_note_requires_packaging_when_step_a_used_workaround(tmp_path: Path) -> None:
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, str((Path("/tmp/demo") / "app.db").resolve()))
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="wave2_active")
    evidence_path = tmp_path / "install-step-a.json"
    evidence_path.write_text(
        json.dumps(
            attach_artifact_contract(
                {
                    "phase": "step-a",
                    "backendStartedByInstalledApp": True,
                    "manualBackendRecoveryUsed": True,
                    "workaroundRequired": False,
                },
                baseline,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="decision=fail and blockerClass=packaging"):
        write_install_note(
            baseline_path=str(baseline_path),
            runtime_dir=str(runtime_dir),
            phase="step-a",
            blocker_class="main-chain",
            decision="fail",
            reason="虽然靠 workaround 跑起来了，但页面边界还不稳。",
            evidence_path=str(evidence_path),
            output_path=str(tmp_path / "install-step-a.note.json"),
        )


def test_write_invalidated_artifacts_note_captures_old_runtime_artifacts(tmp_path: Path) -> None:
    baseline_path = tmp_path / "output" / "main-chain" / "rc-baseline.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(
            {
                "generatedAt": "2026-04-15T22:42:55",
                "fixedGate": {"status": "pass"},
                "fullSmoke": {"summary": "17 failed / 68 passed"},
                "classification": {"aClassCount": 0},
                "installedRuntimeSignature": None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    runtime_dir = tmp_path / "runtime" / "main-chain-rc" / "v0.3.4"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "wave2-day0.json").write_text("{}", encoding="utf-8")
    (runtime_dir / "install-step-a.note.json").write_text("{}", encoding="utf-8")

    applications_dir = tmp_path / "Applications"
    stale_bundle = applications_dir / ".益语智库自用平台.installing-20260404-112300.app"
    stale_assets = stale_bundle / "Contents" / "Resources" / "app" / "dist" / "renderer" / "assets"
    stale_assets.mkdir(parents=True, exist_ok=True)
    (stale_assets / "main-old.js").write_text("// old renderer", encoding="utf-8")

    source_app = tmp_path / "dist" / "mac-arm64" / "益语智库自用平台.app"
    source_assets = source_app / "Contents" / "Resources" / "app" / "dist" / "renderer" / "assets"
    source_assets.mkdir(parents=True, exist_ok=True)
    (source_assets / "main-BHLIy-vt.js").write_text("// current renderer", encoding="utf-8")

    payload = write_invalidated_artifacts_note(
        runtime_dir=str(runtime_dir),
        baseline_path=str(baseline_path),
        source_app_path=str(source_app),
        applications_dir=str(applications_dir),
        output_path=None,
    )

    note_path = runtime_dir / "invalidated-artifacts.note.json"
    assert note_path.exists()
    assert payload["sourceRendererEntry"] == "main-BHLIy-vt.js"
    assert {Path(item["path"]).name for item in payload["entries"]} == {
        "rc-baseline.json",
        "wave2-day0.json",
        "install-step-a.note.json",
        ".益语智库自用平台.installing-20260404-112300.app",
    }
    for item in payload["entries"]:
        assert item["mayNotBeUsedFor"] == ["baseline", "day0", "wave2", "value-proof"]
        assert "reason" in item and item["reason"]


def test_write_full_smoke_classification_normalizes_existing_artifact(tmp_path: Path) -> None:
    source_path = tmp_path / "full-smoke-classification.source.json"
    source_path.write_text(
        json.dumps(
            {
                "pytestExitCode": 1,
                "logPath": str(tmp_path / "full-smoke.log"),
                "fullSmokeSummary": "17 failed / 68 passed",
                "failures": [
                    "tests/test_api_smoke.py::test_topics_promote_to_task",
                    "tests/test_api_smoke.py::test_topics_promote_to_task",
                ],
                "rcBlockingFailures": [],
                "inheritedFailures": [
                    {
                        "test": "tests/test_api_smoke.py::test_topics_promote_to_task",
                        "cluster": "Topics / Insight / Org DNA 注入",
                        "reason": "不落在 installed-runtime RC 边界内。",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = write_full_smoke_classification(
        source_path=str(source_path),
        log_path=None,
        pytest_exit_code=None,
        full_smoke_summary=None,
        failures=None,
        rc_blocking_failures=None,
        inherited_failures=None,
        classification_reason=None,
        output_path=str(tmp_path / "full-smoke-classification.json"),
    )

    assert payload["canRegenerateBaseline"] is True
    assert payload["failures"] == ["tests/test_api_smoke.py::test_topics_promote_to_task"]
    assert payload["classificationReason"]


def test_write_full_smoke_classification_marks_rc_blockers_from_inputs(tmp_path: Path) -> None:
    log_path = tmp_path / "full-smoke.log"
    log_path.write_text(
        "\n".join(
            [
                "FAILED tests/test_api_smoke.py::test_workspace_boundary",
                "FAILED tests/test_api_smoke.py::test_topic_candidate_chat_uses_candidate_context",
            ]
        ),
        encoding="utf-8",
    )

    payload = write_full_smoke_classification(
        source_path=None,
        log_path=str(log_path),
        pytest_exit_code=1,
        full_smoke_summary="2 failed / 10 passed",
        failures=[],
        rc_blocking_failures=["tests/test_api_smoke.py::test_workspace_boundary"],
        inherited_failures=[
            json.dumps(
                {
                    "test": "tests/test_api_smoke.py::test_topic_candidate_chat_uses_candidate_context",
                    "cluster": "Topics / Insight / Org DNA 注入",
                    "reason": "不落在 installed-runtime RC 边界内。",
                },
                ensure_ascii=False,
            )
        ],
        classification_reason="只要命中 workspace/cockpit/Step A/Day 0 边界，就算 RC blocker。",
        output_path=str(tmp_path / "full-smoke-classification.json"),
    )

    assert payload["canRegenerateBaseline"] is False
    assert payload["rcBlockingFailures"] == ["tests/test_api_smoke.py::test_workspace_boundary"]
    assert payload["failures"] == [
        "tests/test_api_smoke.py::test_workspace_boundary",
        "tests/test_api_smoke.py::test_topic_candidate_chat_uses_candidate_context",
    ]
    assert payload["classificationReason"] == "只要命中 workspace/cockpit/Step A/Day 0 边界，就算 RC blocker。"


def test_write_phase_b_decision_blocks_when_conditions_missing(monkeypatch, tmp_path: Path) -> None:
    baseline_path = tmp_path / "rc-baseline.json"
    baseline = _write_baseline(baseline_path, str((Path("/tmp/demo") / "app.db").resolve()))
    runtime_dir = tmp_path / "runtime"
    _write_session(runtime_dir, baseline, baseline_path, state="step_b_ready")
    overview_proof = tmp_path / "page-proof-overview.json"
    workspace_proof = tmp_path / "page-proof-workspace-state.json"
    cockpit_proof = tmp_path / "page-proof-cockpit.json"
    _write_page_proof(overview_proof, baseline, "overview")
    _write_page_proof(workspace_proof, baseline, "workspace-state")
    _write_page_proof(cockpit_proof, baseline, "cockpit")
    observation_path = tmp_path / "wave2-day3.json"
    observation_path.write_text(
        json.dumps(
            attach_artifact_contract(
            {
                "observation": {
                    "timeRange": "Wave 2 / Day 3",
                    "verdict": "watch",
                    "conclusion": "继续观察。",
                    }
                },
                baseline,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manual_path = tmp_path / "value-proof-manual.json"
    manual_path.write_text(
        json.dumps(
            {
                "sessionId": baseline["sessionId"],
                "baselineHash": baseline["baselineHash"],
                "tupleHash": baseline["tupleHash"],
                "runCompletionStatus": "watch",
                "installValidation": {
                    "status": "pass",
                    "appStarts": True,
                    "backendStartedByInstalledApp": True,
                    "overviewPanelVisible": True,
                    "shadowOffParity": True,
                    "workspaceBoundaryCorrect": True,
                    "cockpitOfficialLayerToneCorrect": True,
                    "overviewMetricsPopulated": True,
                    "evidenceScreenshots": {
                        "overview": "/tmp/overview.png",
                        "workspace": "/tmp/workspace.png",
                        "cockpit": "/tmp/cockpit.png",
                    },
                    "evidencePageProofs": {
                        "overview": str(overview_proof),
                        "workspace": str(workspace_proof),
                        "cockpit": str(cockpit_proof),
                    },
                },
                "judgmentConsistency": {
                    "status": "基本稳定",
                    "summary": "还没完全稳定。",
                },
                "scenes": [
                    {"name": "客户工作台", "confirmed": True, "evidence": {"pageProofPath": str(workspace_proof)}},
                    {"name": "任务 AI", "confirmed": True, "evidence": {"pageProofPath": str(workspace_proof)}},
                ],
                "reviewers": [],
                "nextDecision": {
                    "canEnterV04": False,
                    "blockedBy": ["Wave 2 还未结束"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    class FakeApi:
        base_url = "http://127.0.0.1:47829"

        def get_stability_settings(self):
            return {"latestJudgmentsShadowOff": True, "backfillPaused": False}

        def get_metrics(self):
            return {"windowDays": 7}

        def get_settings(self):
            return {"settings": {"dataDir": "/tmp/demo"}, "health": {"buildVersion": "2026.04.16-rc"}}

    monkeypatch.setattr("scripts.main_chain_rc_ops.get_git_commit_sha", lambda: "baseline-sha")
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.get_git_dirty_worktree_state",
        lambda excluded_paths=None: {"dirtyWorktree": False, "dirtyPaths": []},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_app",
        lambda path=None: {"path": "/Users/demo/Applications/益语智库自用平台.app", "exists": True, "modifiedAt": "2026-04-16T10:00:00", "rendererEntry": "main-demo.js"},
    )
    monkeypatch.setattr(
        "scripts.main_chain_rc_ops.inspect_installed_runtime_signature",
        lambda base_url="http://127.0.0.1:47829", installed_app=None: {
            "appBundleMTime": "2026-04-16T10:00:00",
            "rendererEntry": "main-demo.js",
            "backendStartedByInstalledApp": True,
            "backendPid": 12345,
            "backendCommand": "/tmp/demo/python -m uvicorn app.main:app --port 47829",
        },
    )

    payload = write_phase_b_decision(
        FakeApi(),
        baseline_path=str(baseline_path),
        runtime_dir=str(runtime_dir),
        observation_path=str(observation_path),
        manual_path=str(manual_path),
        blocker_class="none",
        output_path=str(tmp_path / "phase-b-decision.json"),
    )

    assert payload["allowEnterPhaseB"] is False
    assert payload["runCompletionStatus"] == "watch"
    assert payload["mainChainJudgmentStability"] == "unstable"
    assert payload["conditionsMet"]["installClosurePass"] is True
    assert payload["conditionsMet"]["runCompletionPass"] is False
    assert "Wave 2 还未结束" in payload["blockingReasons"]
    assert "manual nextDecision.canEnterV04=false" in payload["blockingReasons"]
~~~

## `backend/tests/test_memory_foundation_chat_fact_extract.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.memory_foundation import extract_chat_facts_to_memory


def test_extract_chat_facts_skips_grounded_fallback_answers(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    called = {"count": 0}

    def fake_generate(**kwargs):
        called["count"] += 1
        return {"facts": []}

    ai_service = SimpleNamespace(_qwen_generate=fake_generate)
    facts = extract_chat_facts_to_memory(
        db,
        ai_service,
        client_id="client_1",
        thread_id="thread_1",
        user_prompt="请继续推进这周的核心事项。",
        assistant_content="这是一段足够长的助手回答，用于验证 fallback 不会触发记忆抽取。" * 2,
        answer_mode="grounded_fallback",
    )

    assert facts == []
    assert called["count"] == 0


def test_extract_chat_facts_runs_for_grounded_answer(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    called = {"count": 0}

    def fake_generate(**kwargs):
        called["count"] += 1
        return {"facts": []}

    ai_service = SimpleNamespace(_qwen_generate=fake_generate)
    facts = extract_chat_facts_to_memory(
        db,
        ai_service,
        client_id="client_2",
        thread_id="thread_2",
        user_prompt="请总结今天的关键结论和下一步动作。",
        assistant_content="助手已经给出正式结论、下一步动作和边界条件，应该允许记忆抽取。" * 2,
        answer_mode="grounded_answer",
    )

    assert facts == []
    assert called["count"] == 1
~~~

## `backend/tests/test_platform_dna.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document as WordDocument

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.platform_dna import extract_platform_dna_text


def _write_simple_pdf(path: Path, text: str) -> None:
    objects: list[bytes] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    add_object(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add_object(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>")
    stream = f"BT\n/F1 18 Tf\n36 96 Td\n({text}) Tj\nET".encode("latin-1")
    add_object(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")
    add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("latin-1"))
        chunks.append(payload)
        chunks.append(b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("latin-1"))
    chunks.append(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    )
    path.write_bytes(b"".join(chunks))


def test_extract_platform_dna_text_reads_markdown(tmp_path: Path) -> None:
    target = tmp_path / "platform.md"
    target.write_text("# 腾讯公益\n\n核心偏好\n- 真实\n- 预算清楚\n", encoding="utf-8")

    result = extract_platform_dna_text(target)

    assert "腾讯公益" in result
    assert "预算清楚" in result


def test_extract_platform_dna_text_reads_docx(tmp_path: Path) -> None:
    target = tmp_path / "platform.docx"
    document = WordDocument()
    document.add_heading("抖音公益", level=1)
    document.add_paragraph("核心偏好")
    document.add_paragraph("更看重真实故事与具体行动。")
    document.save(target)

    result = extract_platform_dna_text(target)

    assert "抖音公益" in result
    assert "真实故事与具体行动" in result


def test_extract_platform_dna_text_reads_pdf(tmp_path: Path) -> None:
    target = tmp_path / "platform.pdf"
    _write_simple_pdf(target, "Hello PDF DNA")

    result = extract_platform_dna_text(target)

    assert "Hello PDF DNA" in result
~~~

## `backend/tests/test_review_analysis.py`

- 编码: `utf-8`

~~~python
from app.models import (
    EventLineJudgmentRecord,
    OrgDepartmentPlanItemRecord,
    OrgDepartmentPlanRecord,
    OrgDepartmentRecord,
    OrgEmployeeBindingRecord,
    OrgFocusItemRecord,
    OrgModelProfileRecord,
    OrgProfileRecord,
    OrgRoleTemplateRecord,
    OrganizationDnaModuleRecord,
    TaskOrgContextRecord,
    TaskProjectContextRecord,
    TaskTagRecord,
    WeeklyReviewEventLineContextRecord,
    ReviewDashboardCardTargetRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.review_analysis import build_hierarchy_report_from_analysis, build_weekly_review_analysis


def build_item(
    task_id: str,
    title: str,
    status: str,
    note: str,
    list_name: str = "Q3 营销",
    structured_note: WeeklyReviewTaskStructuredNoteRecord | None = None,
    *,
    org_context: TaskOrgContextRecord | None = None,
    project_context: TaskProjectContextRecord | None = None,
    event_line_id: str | None = None,
    event_line_name: str | None = None,
    event_line_context: WeeklyReviewEventLineContextRecord | None = None,
) -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id=f"review_{task_id}",
        reviewId="review_demo",
        taskId=task_id,
        weekLabel="2026-W11",
        contentDomain="work",
        note=note,
        structuredNote=structured_note or WeeklyReviewTaskStructuredNoteRecord(),
        reviewedAt="2026-03-15T12:00:00",
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(
            title=title,
            status=status,  # type: ignore[arg-type]
            dueDate="2026-03-14",
            createdAt="2026-03-14T10:00:00",
            tags=[TaskTagRecord(id="tag_1", name="情报跟进", color="#5B7BFE", scope="org", updatedAt="2026-03-14T10:00:00")],
            listName=list_name,
            listColor="#5B7BFE",
            orgContext=org_context,
            projectContext=project_context,
            eventLineId=event_line_id,
            eventLineName=event_line_name,
            eventLineContext=event_line_context,
        ),
    )


def build_org_module(module_key: str, title: str, summary: str) -> OrganizationDnaModuleRecord:
    return OrganizationDnaModuleRecord(
        moduleKey=module_key,  # type: ignore[arg-type]
        title=title,
        markdownContent="",
        normalizedText=summary,
        summary=summary,
        fileName=None,
        contentHash=None,
        updatedAt="2026-03-01T00:00:00",
        updatedBy="tester",
        hasDocument=True,
    )


def build_org_model_profile() -> OrgModelProfileRecord:
    return OrgModelProfileRecord(
        organization=OrgProfileRecord(
            organizationId="org_yiyu_default",
            name="益语智库",
            annualGoal="做深战略判断与交付闭环",
            quarterlyFocus=["推进关键客户交付", "沉淀标准件"],
            leaderUserId="user_ceo",
            managementUserIds=["user_ceo"],
            updatedAt="2026-03-20T10:00:00",
        ),
        departments=[
            OrgDepartmentRecord(
                id="dept_consult_strategy",
                name="咨询策略部",
                color="#5B7BFE",
                leaderUserId="user_ceo",
                mission="推进关键客户战略判断",
                quarterlyFocus=["推进关键客户交付"],
                collaborationDepartmentIds=[],
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        roles=[
            OrgRoleTemplateRecord(
                id="role_consultant",
                departmentId="dept_consult_strategy",
                name="咨询顾问",
                level="employee",
                isManager=False,
                goal="推进关键客户方案",
                responsibilities=["方案推进"],
                shouldAvoid=[],
                taskEditScope="self",
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        bindings=[
            OrgEmployeeBindingRecord(
                userId="user_demo",
                departmentId="dept_consult_strategy",
                primaryRoleId="role_consultant",
                isManager=False,
                currentFocus="推进关键客户交付",
                taskEditScope="self",
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        reportingLines=[],
        taskControlRules=[],
        roleProcessTemplates=[],
        focusItems=[
            OrgFocusItemRecord(
                id="focus_q2_delivery",
                periodKey="2026-Q2",
                title="推进关键客户交付",
                statement="围绕标杆客户推进应用交付并沉淀案例。",
                ownerUserId="user_ceo",
                priority="high",
                status="active",
                evidenceKeywords=["交付", "标杆客户"],
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        departmentPlans=[
            OrgDepartmentPlanRecord(
                id="plan_consult_w12",
                departmentId="dept_consult_strategy",
                weekLabel="2026-W11",
                ownerUserId="user_ceo",
                summary="本周重点推进黄河基金会应用交付方案。",
                majorRisks=[],
                dependencies=[],
                status="active",
                items=[
                    OrgDepartmentPlanItemRecord(
                        id="plan_item_hh_delivery",
                        focusItemId="focus_q2_delivery",
                        title="推进黄河基金会应用交付方案",
                        statement="把方案推进到可审阅版本。",
                        ownerUserId="user_demo",
                        status="active",
                        expectedOutput="可审阅方案",
                        sortOrder=0,
                        updatedAt="2026-03-20T10:00:00",
                    )
                ],
                updatedAt="2026-03-20T10:00:00",
            )
        ],
        updatedAt="2026-03-20T10:00:00",
    )


def test_build_weekly_review_analysis_prefers_user_notes_and_dna():
    items = [
        build_item(
            "task_1",
            "推进客户方案验证",
            "done",
            "这周完成了客户验证，反馈比预期更顺，说明方案路径比较清楚。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(progress="完成客户验证", successReason="方案路径较清楚"),
        ),
        build_item(
            "task_2",
            "梳理跨组协作节奏",
            "doing",
            "目前卡在接口对齐和责任边界不清，推进有阻力，需要协同支持。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(blockerReason="接口对齐不清", supportNeeded="需要协同支持"),
        ),
    ]
    modules = [
        build_org_module("business_intro", "业务介绍", "本月重点是把咨询方案验证做深，优先推进高反馈、低决策成本的项目。"),
        build_org_module("team_intro", "团队介绍", "团队当前的关键任务是收敛协作接口，降低跨组沟通损耗。"),
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, modules)

    assert analysis.scope == "work"
    assert analysis.emphasis == "analysis"
    assert analysis.metricCards
    assert analysis.metricCards[0].key == "timely_completion"
    assert analysis.evidenceWeights[0].sourceType == "user_note"
    assert analysis.evidenceWeights[0].weight == "high"
    assert "业务介绍" in analysis.dnaModuleTitles
    assert analysis.hypothesisHighlights
    assert any(item.title == "可能的成功原因" for item in analysis.hypothesisHighlights)
    assert any(item.title == "可能的阻碍原因" for item in analysis.hypothesisHighlights)
    assert any("假设" in analysis.caution for _ in [0])
    assert any("协作接口" in item.statement or "协作" in item.statement for item in analysis.hypothesisHighlights)


def test_build_hierarchy_report_from_analysis_uses_weighted_summary():
    items = [build_item("task_1", "推进客户方案验证", "done", "方案路径清楚，反馈较好。")]
    modules = [build_org_module("organization_intro", "组织介绍", "组织主线是沉淀可复用的方法资产。")]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, modules)
    report = build_hierarchy_report_from_analysis(analysis, week_label="2026-W11")

    assert report.logicMode == "weighted_hypothesis_v1"
    assert report.weekLabel == "2026-W11"
    assert report.headline == analysis.headline
    assert report.summaryMetrics
    assert report.publishState == "local_preview"
    assert report.sourcePolicy["user_note"] == "high"
    assert "eventLineSummaryCount" in report.sourcePolicy
    assert report.focusAreas
    assert "｜" in report.focusAreas[0]


def test_build_hierarchy_report_from_analysis_prefers_event_line_judgments():
    items = [build_item("task_1", "推进日慈系统演示", "doing", "这周主要是把系统演示推进成会后合作判断。")]
    analysis = build_weekly_review_analysis("work", "2026-W11", items, [])
    analysis = analysis.model_copy(
        update={
            "eventLineJudgments": [
                EventLineJudgmentRecord(
                    eventLineId="eline_demo",
                    title="日慈系统演示推进线",
                    viewerRole="admin",
                    judgmentVersion="event_line_judgment_v1",
                    bundleFingerprint="bundle_demo_fp",
                    coverageScore=84,
                    confidenceScore=78,
                    safeOutputMode="full_judgment",
                    publishState="publish_ready",
                    whatHappened="本周这条线实际在推进：给张真看系统并收集会后合作判断。",
                    whyItMatters="这条线直接决定日慈是否把系统演示看成合作入口，而不只是普通交流。",
                    coreBlocker="真正阻碍不是资料数量，而是会后动作和合作判断还没有被钉住。",
                    blockerType="decision",
                    evidenceSummary="已关联 1 条任务、1 次会谈、2 份附件。",
                    managerImplication="管理层现在最该盯的是这次会谈能否收成明确判断，而不是继续停在交流层。",
                    nextWeekFocus="把会谈反馈压成明确的合作判断和下一步动作。",
                    minimumAction="本周内确认张真的反馈、下一次对齐时间和要补的关键证据。",
                    riskIfIgnored="如果继续放着不管，这条线会停在关系交流层，管理层也看不清是否值得继续加码。",
                    opportunityIfAmplified="如果现在收成结论，这条线就能成为后续合作推进的样板。",
                    target=ReviewDashboardCardTargetRecord(targetType="event_line", targetId="eline_demo", targetLabel="日慈系统演示推进线"),
                )
            ]
        }
    )

    report = build_hierarchy_report_from_analysis(analysis, week_label="2026-W11")

    assert report.judgmentVersion == "event_line_judgment_v1"
    assert report.bundleFingerprint
    assert report.coverageScore is not None and report.coverageScore >= 0
    assert report.confidenceScore is not None and report.confidenceScore >= 0
    assert report.safeOutputMode == "full_judgment"
    assert report.publishState == "publish_ready"
    assert "给张真看系统" in report.summary
    assert any("真正阻碍不是资料数量" in signal for signal in report.supportSignals)
    assert any("本周内确认张真的反馈" in action for action in report.suggestedActions)
    assert any("日慈系统演示推进线" in area for area in report.focusAreas)
    assert report.sourcePolicy["judgmentVersion"] == "event_line_judgment_v1"
    assert report.sourcePolicy["publishReadyCount"] == 1


def test_build_weekly_review_analysis_detects_overload_signal():
    items = [
        build_item(
            "task_3",
            "推进客户交付排期",
            "doing",
            "",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="这周主要不是方向错，而是手上的交付任务已经过载。",
                lightweightTag="工作过度饱和",
            ),
        )
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [])

    assert any(item.title == "可能存在容量过载" for item in analysis.hypothesisHighlights)
    assert any("工作过度饱和" in item for item in analysis.confirmedFacts)


def test_build_weekly_review_analysis_uses_team_plan_and_quarter_background():
    items = [
        build_item(
            "task_4",
            "推进黄河基金会应用交付方案",
            "done",
            "本周把黄河基金会应用交付方案推进到可审阅版本。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="方案已经推进到可审阅版本，客户反馈更聚焦。",
                completionStatus="done_on_time",
            ),
        )
    ]
    modules = [
        build_org_module("team_intro", "咨询策略部 部门计划背景", "月度 DNA：做深重点客户方案验证。本周重点计划：推进黄河基金会应用交付方案。"),
        build_org_module("organization_intro", "组织介绍", "2026 Q2 重点目标：推进应用交付、沉淀标杆客户案例、强化跨部门作战。"),
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, modules)

    assert len(analysis.metricCards) == 4


def test_build_weekly_review_analysis_admin_prefers_event_line_and_strategy_context():
    items = [
        build_item(
            "task_admin_1",
            "推进黄河基金会合作方案初稿",
            "doing",
            "本周先把黄河基金会合作方案推进到可内部讨论版本。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                progress="黄河基金会合作方案进入内部讨论阶段。",
                nextAction="补齐方案分工后与黄河基金会确认下一轮沟通。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="黄河基金会当前围绕合作方案做前期业务判断。",
                goalSummary="把合作方案推进到可确认范围。",
                riskSummary="当前风险是方案分工和下一轮沟通安排还没完全收束。",
                currentFocus="当前主要在推进：黄河基金会合作方案初稿。",
                currentBlocker="当前阻塞：方案分工和下一轮沟通安排还没完全收束。",
                nextAction="下一步动作：补齐方案分工后与黄河基金会确认下一轮沟通。",
                recentProgress="最近进展：黄河基金会合作方案进入内部讨论阶段。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_hh",
            event_line_name="黄河基金会合作推进",
        ),
        build_item(
            "task_admin_2",
            "补齐黄河基金会下一轮沟通提纲",
            "doing",
            "沟通提纲还没完全补齐。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                blockerReason="下一轮沟通提纲还没完全收束。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="黄河基金会当前围绕合作方案做前期业务判断。",
                goalSummary="把合作方案推进到可确认范围。",
                riskSummary="当前风险是方案分工和下一轮沟通安排还没完全收束。",
                currentFocus="当前主要在推进：黄河基金会合作方案初稿。",
                currentBlocker="当前阻塞：方案分工和下一轮沟通安排还没完全收束。",
                nextAction="下一步动作：补齐方案分工后与黄河基金会确认下一轮沟通。",
                recentProgress="最近进展：黄河基金会合作方案进入内部讨论阶段。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_hh",
            event_line_name="黄河基金会合作推进",
        ),
    ]
    modules = [
        build_org_module("organization_intro", "组织介绍", "2026 Q2 重点目标：推进关键客户交付与业务扩展。"),
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, modules, viewer_role="admin")

    assert any(card.label == "事件线成线率" for card in analysis.metricCards)
    assert not any(card.label == "个人-部门对齐率" for card in analysis.metricCards)
    assert any("黄河基金会" in item.statement for item in analysis.hypothesisHighlights)
    assert any("业务扩展" in item.statement for item in analysis.hypothesisHighlights)
    assert any("当前最具体的推进事项" in item.statement for item in analysis.hypothesisHighlights)
    assert any("下一步动作" in item.statement or "接下来应优先推进" in item.statement for item in analysis.hypothesisHighlights)
    assert "个人-部门对齐" not in analysis.caution
    assert any(card.key == "department_alignment" and card.valueText != "待补录" for card in analysis.metricCards)
    assert any(card.key == "strategy_alignment" and card.valueText != "待补录" for card in analysis.metricCards)
    assert any(weight.sourceType == "project_context" and weight.weight == "medium" for weight in analysis.evidenceWeights)
    assert any("季度重点" in fact for fact in analysis.confirmedFacts)
    assert len(analysis.eventLineSummaries) == 1
    assert analysis.eventLineSummaries[0].title == "黄河基金会合作推进"
    assert analysis.eventLineSummaries[0].projectName == "黄河基金会"
    assert analysis.eventLineSummaries[0].predictionReadiness in {"conservative_forecast", "strong_forecast"}
    assert analysis.eventLineCompleteness[0].score >= 65
    assert any(card.title == "黄河基金会合作推进" for card in analysis.riskCards)
    assert any(card.title == "黄河基金会合作推进" for card in analysis.opportunityCards)


def test_build_weekly_review_analysis_detects_event_line_continuity():
    items = [
        build_item(
            "task_event_1",
            "推进云南连心第一轮沟通",
            "doing",
            "本周先完成第一轮沟通和问题收集。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="这周先把外部需求和内部判断对齐。",
                completionStatus="in_progress",
            ),
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
        build_item(
            "task_event_2",
            "整理云南连心后续推进方案",
            "doing",
            "下一步要把沟通结果收束成后续方案。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="还需要继续推进下周安排。",
                completionStatus="in_progress",
            ),
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [])

    assert any("事件线" in fact for fact in analysis.confirmedFacts)
    assert any(item.title == "与事件线连续推进的关系判断" for item in analysis.hypothesisHighlights)
    assert any("事件线" in focus for focus in analysis.nextWeekFocus)
    assert len(analysis.eventLineSummaries) == 1
    assert analysis.eventLineSummaries[0].title == "云南连心"
    assert analysis.eventLineCompleteness[0].status in {"summary_ready", "forecast_ready", "high_confidence"}
    assert any(slot.label == "下一步动作" for slot in analysis.eventLineCompleteness[0].slots)


def test_build_weekly_review_analysis_reads_structured_plan_and_project_context():
    org_profile = build_org_model_profile()
    items = [
        build_item(
            "task_5",
            "推进黄河基金会应用交付方案",
            "doing",
            "本周继续推进黄河基金会交付方案，并结合近期会议判断风险。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="方案推进到可审阅版本，但要继续盯会议里暴露的交付风险。",
                completionStatus="in_progress",
            ),
            org_context=TaskOrgContextRecord(
                departmentId="dept_consult_strategy",
                roleTemplateId="role_consultant",
                focusItemId="focus_q2_delivery",
                departmentPlanItemId="plan_item_hh_delivery",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="方案推进",
                backgroundSummary="围绕基金会应用交付推进方案落地。",
                goalSummary="把应用交付方案推进到可审阅版本。",
                riskSummary="近期会议提示交付节奏和资料补齐仍有风险。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台来源", "项目目标", "近期会议决策"],
            ),
        )
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [], org_model_profile=org_profile)

    assert any(weight.sourceType == "focus_plan" and weight.weight == "medium" for weight in analysis.evidenceWeights)
    assert any(weight.sourceType == "project_context" and weight.weight == "medium" for weight in analysis.evidenceWeights)
    assert any("挂接项目背景" in fact for fact in analysis.confirmedFacts)
    assert any("正式录入的部门计划和机构重点" in fact or "挂接部门计划项" in fact for fact in analysis.confirmedFacts)
    assert any(item.title == "与项目阶段的关系判断" for item in analysis.hypothesisHighlights)
    assert any(item.title == "与正式计划对象的关系判断" for item in analysis.hypothesisHighlights)


def test_build_weekly_review_analysis_prefers_event_line_context_for_admin_story():
    items = [
        build_item(
            "task_event_ctx_1",
            "推进黄河基金会合作方案确认",
            "doing",
            "这周继续推进合作方案。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="先把合作范围和下轮确认节奏拉齐。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="方案推进",
                backgroundSummary="围绕基金会合作方案推进。",
                goalSummary="把方案推进到可确认版本。",
                riskSummary="需要继续补资料。",
                currentFocus="项目共享焦点：继续推进合作方案。",
                currentBlocker="项目共享阻塞：资料还不完整。",
                nextAction="项目共享下一步：继续补资料。",
                recentProgress="项目共享进展：内部已经开始讨论。",
                infoCompleteness="medium",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_hh_case",
            event_line_name="黄河基金会合作推进",
            event_line_context=WeeklyReviewEventLineContextRecord(
                id="eline_hh_case",
                name="黄河基金会合作推进",
                stage="方案确认",
                summary="围绕黄河基金会合作范围与合作方式确认的一条业务扩展线。",
                intent="当前核心是收束合作范围，并明确下一轮确认的关键人和时间点。",
                currentBlocker="关键阻塞是合作边界和确认节奏还没有被双方说死。",
                recentDecision="最近已决定先用收束版方案推进下一轮确认，不再继续扩写。",
                nextStep="下一步先把收束版方案发出，并锁定黄河基金会下一轮确认会议。",
                primaryClientId="client_hh",
                primaryClientName="黄河基金会",
            ),
        )
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [], viewer_role="admin")

    assert len(analysis.eventLineSummaries) == 1
    summary_card = analysis.eventLineSummaries[0]
    assert "合作范围与合作方式确认" in summary_card.whatThisLineIs
    assert "收束合作范围" in summary_card.whatHappenedThisWeek
    assert "合作边界和确认节奏" in summary_card.mainBlocker
    assert "锁定黄河基金会下一轮确认会议" in summary_card.nextCriticalMove
    assert any(
        "合作范围与合作方式确认" in item.statement or "收束合作范围" in item.statement
        for item in analysis.hypothesisHighlights
    )


def test_build_weekly_review_analysis_event_line_intelligence_varies_by_role():
    items = [
        build_item(
            "task_role_1",
            "推进黄河基金会合作边界确认",
            "doing",
            "这周继续推进合作边界和下一轮沟通。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="先把合作边界和关键人确认下来。",
                nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="围绕黄河基金会合作可能性做判断。",
                goalSummary="确认合作边界和下一轮沟通。",
                riskSummary="合作边界和关键确认节点还没有收束。",
                currentFocus="当前主要在推进：合作边界和下一轮沟通确认。",
                currentBlocker="合作边界和关键确认节点还没有收束。",
                nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
                recentProgress="最近进展：双方已经开始围绕合作边界进行确认。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_role_hh",
            event_line_name="黄河基金会合作确认",
        )
    ]

    admin_analysis = build_weekly_review_analysis("work", "2026-W11", items, [], viewer_role="admin")
    employee_analysis = build_weekly_review_analysis("work", "2026-W11", items, [], viewer_role="employee")

    assert admin_analysis.riskCards
    assert employee_analysis.riskCards
    assert "管理层看不清该不该继续加码" in admin_analysis.riskCards[0].statement
    assert "反复确认和来回推进" in employee_analysis.riskCards[0].statement
    assert admin_analysis.opportunityCards
    assert "业务机会" in admin_analysis.opportunityCards[0].upside


def test_build_weekly_review_analysis_event_line_intelligence_varies_by_category():
    items = [
        build_item(
            "task_prod_1",
            "沉淀益语问答判断模板",
            "doing",
            "这周继续把判断模板固化成可复用结构。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="先把样本、结构和输出标准收束。",
                nextAction="补齐关键样本并固化输出结构。",
                completionStatus="in_progress",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_yiyu",
                clientName="益语智库",
                stage="模板沉淀",
                projectModuleName="判断模板库",
                backgroundSummary="围绕判断模板做产品化沉淀。",
                goalSummary="把模板推进到可复用状态。",
                riskSummary="结构还没钉死，样本也不够稳定。",
                currentFocus="当前主要在推进：判断模板的结构和输出标准。",
                currentBlocker="结构还没钉死，样本也不够稳定。",
                nextAction="补齐关键样本并固化输出结构。",
                recentProgress="最近进展：已经形成第一版模板骨架。",
                infoCompleteness="high",
                sourceEvidence=["项目资料"],
            ),
            event_line_id="eline_prod_1",
            event_line_name="判断模板沉淀",
        )
    ]

    analysis = build_weekly_review_analysis("work", "2026-W11", items, [], viewer_role="admin")

    assert analysis.eventLineSummaries
    assert "产品化线" in analysis.eventLineSummaries[0].whatThisLineIs
    assert analysis.opportunityCards
    assert "模板、标准件或 AI 可复用判断组件" in analysis.opportunityCards[0].upside


def test_build_weekly_review_analysis_department_lead_uses_department_view():
    org_profile = build_org_model_profile()
    items = [
        build_item(
            "task_dept_lead_1",
            "推进黄河基金会合作边界确认",
            "doing",
            "这周继续推进合作边界和下一轮沟通。",
            structured_note=WeeklyReviewTaskStructuredNoteRecord(
                reflection="先把合作边界和关键人确认下来。",
                nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
                completionStatus="in_progress",
            ),
            org_context=TaskOrgContextRecord(
                departmentId="dept_consult_strategy",
                roleTemplateId="role_consultant",
                focusItemId="focus_q2_delivery",
                departmentPlanItemId="plan_item_hh_delivery",
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="围绕黄河基金会合作可能性做判断。",
                goalSummary="确认合作边界和下一轮沟通。",
                riskSummary="合作边界和关键确认节点还没有收束。",
                currentFocus="当前主要在推进：合作边界和下一轮沟通确认。",
                currentBlocker="合作边界和关键确认节点还没有收束。",
                nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
                recentProgress="最近进展：双方已经开始围绕合作边界进行确认。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_dept_hh",
            event_line_name="黄河基金会合作确认",
            event_line_context=WeeklyReviewEventLineContextRecord(
                id="eline_dept_hh",
                name="黄河基金会合作确认",
                stage="方案确认",
                summary="围绕黄河基金会合作边界和确认节奏推进的一条业务扩展线。",
                intent="把合作边界和确认节奏收束到部门可以持续跟进的状态。",
                currentBlocker="合作边界和关键确认节点还没有收束。",
                recentDecision="最近明确先用收束版方案推进下一轮确认。",
                nextStep="下一步锁定下一轮沟通时间并把合作边界确认清楚。",
                primaryClientId="client_hh",
                primaryClientName="黄河基金会",
            ),
        )
    ]

    analysis = build_weekly_review_analysis(
        "work",
        "2026-W11",
        items,
        [],
        org_model_profile=org_profile,
        viewer_role="department_lead",
    )

    assert any(card.label == "部门任务-部门计划对齐率" for card in analysis.metricCards)
    assert any(card.label == "部门任务-机构方向对齐率" for card in analysis.metricCards)
    assert "部门计划解释本周推进" in analysis.caution
    assert any(item.title == "部门计划与机构方向提示" for item in analysis.hypothesisHighlights)
    assert analysis.riskCards
    assert "部门带宽" in analysis.riskCards[0].statement or "部门推进" in analysis.riskCards[0].statement
    assert analysis.opportunityCards
    assert "部门里同类事项" in analysis.opportunityCards[0].upside
~~~

## `backend/tests/test_review_rollup.py`

- 编码: `utf-8`

~~~python
from app.models import (
    OrgDepartmentPlanItemRecord,
    OrgDepartmentPlanRecord,
    OrgDepartmentRecord,
    OrgEmployeeBindingRecord,
    OrgFocusItemRecord,
    OrgModelProfileRecord,
    OrgProfileRecord,
    OrgRoleProcessTemplateRecord,
    OrgRoleTemplateRecord,
    OrgTaskControlRuleRecord,
    OrganizationDnaModuleRecord,
    ReviewDepartmentConfigRecord,
    ReviewDepartmentMemberRecord,
    ReviewGovernanceSettingsRecord,
    TaskTagRecord,
    TaskOrgContextRecord,
    TaskProjectContextRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.review_analysis import build_weekly_review_analysis
from app.services.review_rollup import build_employee_review_report, build_executive_review_rollup


def build_item(
    task_id: str,
    title: str,
    owner_name: str,
    structured_note: WeeklyReviewTaskStructuredNoteRecord,
    *,
    owner_id: str | None = None,
    org_context: TaskOrgContextRecord | None = None,
    project_context: TaskProjectContextRecord | None = None,
    event_line_id: str | None = None,
    event_line_name: str | None = None,
) -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id=f"review_{task_id}",
        reviewId="review_demo",
        taskId=task_id,
        weekLabel="2026-W11",
        contentDomain="work",
        note="",
        structuredNote=structured_note,
        reviewedAt="2026-03-15T12:00:00",
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(
            title=title,
            status="doing",  # type: ignore[arg-type]
            dueDate="2026-03-14",
            createdAt="2026-03-14T10:00:00",
            ownerId=owner_id,
            ownerName=owner_name,
            tags=[TaskTagRecord(id="tag_1", name="情报跟进", color="#5B7BFE", scope="org", updatedAt="2026-03-14T10:00:00")],
            listName="Q3 营销",
            listColor="#5B7BFE",
            orgContext=org_context,
            projectContext=project_context,
            eventLineId=event_line_id,
            eventLineName=event_line_name,
        ),
    )


def build_org_module(module_key: str, title: str, summary: str) -> OrganizationDnaModuleRecord:
    return OrganizationDnaModuleRecord(
        moduleKey=module_key,  # type: ignore[arg-type]
        title=title,
        markdownContent="",
        normalizedText=summary,
        summary=summary,
        fileName=None,
        contentHash=None,
        updatedAt="2026-03-01T00:00:00",
        updatedBy="tester",
        hasDocument=True,
    )


def build_org_model_profile() -> OrgModelProfileRecord:
    return OrgModelProfileRecord(
        organization=OrgProfileRecord(
            organizationId="org_yiyu_default",
            name="益语智库",
            annualGoal="建立稳定的战略判断与交付闭环",
            quarterlyFocus=["组织模型 P0 上线", "关键客户交付推进"],
            leaderUserId="user_guyuan",
            managementUserIds=["user_guyuan", "user_qinghua"],
            updatedAt="2026-03-17T10:00:00",
        ),
        departments=[
            OrgDepartmentRecord(
                id="dept_customer_service",
                name="客户服务部",
                color="#14B8A6",
                leaderUserId="user_qinghua",
                mission="把客户现场阻力转成组织动作",
                quarterlyFocus=["客户推进", "交付协同"],
                collaborationDepartmentIds=["dept_consult_strategy"],
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        roles=[
            OrgRoleTemplateRecord(
                id="role_cs_lead",
                departmentId="dept_customer_service",
                name="客户服务部负责人",
                level="department_lead",
                isManager=True,
                goal="统筹客户推进与交付协同",
                responsibilities=["客户推进", "交付判断", "跨部门协同"],
                shouldAvoid=["长期承担底层技术修复", "大量文案细修"],
                taskEditScope="department",
                canApproveTasks=True,
                canReassignTasks=True,
                canChangeDeadline=True,
                updatedAt="2026-03-17T10:00:00",
            ),
            OrgRoleTemplateRecord(
                id="role_cs_member",
                departmentId="dept_customer_service",
                name="客户推进",
                level="employee",
                managerRoleId="role_cs_lead",
                goal="推进客户跟进与会后落地",
                responsibilities=["客户沟通", "资料整理", "会后推进"],
                shouldAvoid=["长期承担架构设计", "长期承担底层技术修复"],
                taskEditScope="self",
                updatedAt="2026-03-17T10:00:00",
            ),
        ],
        bindings=[
            OrgEmployeeBindingRecord(
                userId="user_qinghua",
                departmentId="dept_customer_service",
                primaryRoleId="role_cs_lead",
                isManager=True,
                currentFocus="客户推进与交付协同",
                taskEditScope="department",
                canApproveTasks=True,
                canReassignTasks=True,
                canChangeDeadline=True,
                updatedAt="2026-03-17T10:00:00",
            ),
            OrgEmployeeBindingRecord(
                userId="user_jianing",
                departmentId="dept_customer_service",
                primaryRoleId="role_cs_member",
                managerUserId="user_qinghua",
                currentFocus="客户推进",
                taskEditScope="self",
                updatedAt="2026-03-17T10:00:00",
            ),
        ],
        reportingLines=[],
        taskControlRules=[
            OrgTaskControlRuleRecord(
                id="rule_department_key",
                name="部门关键任务",
                controlLevel="department_control",
                departmentId="dept_customer_service",
                roleTemplateId="role_cs_lead",
                deadlineEditableBy="department_lead",
                ownerEditableBy="department_lead",
                requireCollabConfirmation=True,
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        roleProcessTemplates=[
            OrgRoleProcessTemplateRecord(
                id="process_cs_followup",
                roleTemplateId="role_cs_member",
                name="客户周会后推进流程",
                triggerType="weekly_followup",
                triggerCondition="客户周会结束",
                keySteps=["确认需补资料项", "更新客户工作台", "同步飞书群重点", "生成下周待确认事项"],
                collaborationStep="同步飞书群重点",
                approvalStep="生成下周待确认事项",
                outputArtifact="客户推进摘要 + 新任务清单",
                commonBlockers=["资料未补齐", "等待部门确认"],
                active=True,
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        focusItems=[
            OrgFocusItemRecord(
                id="focus_q2_delivery",
                periodKey="2026-Q2",
                title="关键客户交付推进",
                statement="围绕关键客户交付推进跨部门协同与反馈收束。",
                ownerUserId="user_qinghua",
                priority="high",
                status="active",
                evidenceKeywords=["客户推进", "交付协同"],
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        departmentPlans=[
            OrgDepartmentPlanRecord(
                id="dept_plan_cs_w11",
                departmentId="dept_customer_service",
                weekLabel="2026-W11",
                ownerUserId="user_qinghua",
                summary="本周重点推进客户交付协同与关键反馈收束。",
                majorRisks=[],
                dependencies=[],
                status="active",
                items=[
                    OrgDepartmentPlanItemRecord(
                        id="plan_item_client_followup",
                        focusItemId="focus_q2_delivery",
                        title="跟进客户推进并整理会后待办",
                        statement="把推进动作和反馈收束到单一节奏。",
                        ownerUserId="user_jianing",
                        status="active",
                        expectedOutput="会后待办清单",
                        sortOrder=0,
                        updatedAt="2026-03-17T10:00:00",
                    )
                ],
                updatedAt="2026-03-17T10:00:00",
            )
        ],
        updatedAt="2026-03-17T10:00:00",
    )


def test_build_executive_review_rollup_returns_real_org_and_department_reports():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_consult_strategy",
                name="咨询策略部",
                monthlyDna="本月重点是把重点客户方案验证做深。",
                weeklyFocus="本周重点推进黄河基金会应用交付方案。",
                members=[ReviewDepartmentMemberRecord(id="u1", fullName="顾源源")],
            ),
            ReviewDepartmentConfigRecord(
                id="dept_info_data",
                name="信息数据部",
                monthlyDna="本月重点是把市场变化转成业务判断。",
                members=[ReviewDepartmentMemberRecord(id="u2", fullName="一朔")],
            ),
        ],
        updatedAt="2026-03-15T12:00:00",
    )
    items = [
        build_item("task_1", "推进客户方案验证", "顾源源", WeeklyReviewTaskStructuredNoteRecord(progress="推进验证", successReason="客户路径更清楚")),
        build_item("task_2", "整理市场信息", "一朔", WeeklyReviewTaskStructuredNoteRecord(progress="整理信息", blockerReason="判断口径还不统一")),
    ]
    modules = [build_org_module("business_intro", "业务介绍", "业务主线是做深方案验证和提高判断质量。")]

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=items,
        governance=governance,
        organization_dna_modules=modules,
    )

    assert org_report is not None
    assert org_report.sourcePolicy["realAggregation"] is True
    assert org_report.sourcePolicy["reviewedDepartments"] == 2
    assert org_report.summaryMetrics
    assert len(department_reports) == 2
    assert department_reports[0].sourcePolicy["sampleSize"] == 1
    assert department_reports[0].summaryMetrics
    assert "场景判断力的产品化" in department_reports[0].headline
    assert any("场景判断力产品化" in area for area in department_reports[0].focusAreas)
    assert any("｜" in area for area in department_reports[0].focusAreas)
    assert "月度 DNA" in department_reports[0].summary
    assert "本周重点计划" in department_reports[0].summary


def test_build_executive_review_rollup_returns_empty_org_when_no_department_matches():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_customer_service",
                name="客户服务部",
                members=[ReviewDepartmentMemberRecord(id="u3", fullName="小李")],
            )
        ],
        updatedAt="2026-03-15T12:00:00",
    )
    items = [
        build_item("task_1", "推进客户方案验证", "顾源源", WeeklyReviewTaskStructuredNoteRecord(progress="推进验证")),
    ]

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=items,
        governance=governance,
        organization_dna_modules=[],
    )

    assert org_report is None
    assert len(department_reports) == 1
    assert department_reports[0].sourcePolicy["sampleSize"] == 0


def test_build_executive_review_rollup_counts_robot_samples_as_department_inputs():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_consult_strategy",
                name="咨询策略部",
                monthlyDna="本月重点是做深战略判断与客户方案。",
                members=[],
            )
        ],
        updatedAt="2026-03-15T12:00:00",
    )
    robot_item = WeeklyReviewTaskEntryRecord(
        id="review_agent_1",
        reviewId="agent_review_strategy",
        taskId="agent_task_strategy",
        weekLabel="2026-W11",
        contentDomain="work",
        note="",
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(
            planCommitment="推进重点客户战略判断",
            progress="本周围绕重点客户战略判断持续推进，并完成阶段收束。",
            completionStatus="done_on_time",
            departmentPlanId="agent_plan_1",
            departmentPlanAlignment="aligned",
            successReason="关键判断路径已清楚",
            successExperience="通过连续校准主线，减少了判断分歧。",
        ),
        reviewedAt="2026-03-15T12:00:00",
        taskSnapshot=WeeklyReviewTaskSnapshotRecord(
            title="推进重点客户战略判断",
            status="done",  # type: ignore[arg-type]
            dueDate="2026-03-14",
            createdAt="2026-03-14T10:00:00",
            ownerId="agent:strategy_design",
            ownerName="庆华",
            tags=[TaskTagRecord(id="tag_agent", name="战略设计", color="#5B7BFE", scope="org", updatedAt="2026-03-14T10:00:00")],
            listName="咨询策略部",
            listColor="#5B7BFE",
        ),
    )

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=[robot_item],
        governance=governance,
        organization_dna_modules=[],
    )

    assert org_report is not None
    assert org_report.sourcePolicy["agentSampleCount"] == 1
    assert len(department_reports) == 1
    assert department_reports[0].sourcePolicy["sampleSize"] == 1
    assert department_reports[0].sourcePolicy["agentSampleCount"] == 1
    assert "场景判断力的产品化" in department_reports[0].headline


def test_build_executive_review_rollup_uses_task_org_context_for_management_signals():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_customer_service",
                name="客户服务部",
                monthlyDna="本月重点是把客户推进阻力翻译成产品边界。",
                weeklyFocus="本周重点推进客户交付协同与关键反馈收束。",
                members=[ReviewDepartmentMemberRecord(id="user_jianing", fullName="佳乐")],
            )
        ],
        updatedAt="2026-03-17T10:00:00",
    )
    org_profile = build_org_model_profile()
    items = [
        build_item(
            "task_repair",
            "长期承担底层技术修复并补齐客户反馈",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(
                progress="本周一边修底层问题，一边处理客户反馈。",
                blockerReason="同步飞书群重点时，资料未补齐，跨部门确认链拉长。",
            ),
            owner_id="user_jianing",
            org_context=TaskOrgContextRecord(
                departmentId="dept_customer_service",
                roleTemplateId="role_cs_member",
                controlRuleId="rule_department_key",
                controlLevel="department_control",
                departmentFocusKey="客户推进",
                organizationFocusKey="关键客户交付推进",
                isCrossDepartment=True,
                approvalState="pending",
                blockedAtStep="同步飞书群重点",
                needsReview=True,
            ),
            project_context=TaskProjectContextRecord(
                clientId="client_demo",
                clientName="示例客户",
                stage="交付推进",
                backgroundSummary="围绕关键客户交付推进组织协同。",
                goalSummary="推进关键客户交付方案。",
                riskSummary="当前风险集中在资料未补齐和确认链偏长。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台来源", "项目目标"],
            ),
        ),
        build_item(
            "task_followup",
            "跟进客户推进并整理会后待办",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(
                progress="推进客户跟进。",
                completionStatus="in_progress",
            ),
            owner_id="user_jianing",
            org_context=TaskOrgContextRecord(
                departmentId="dept_customer_service",
                roleTemplateId="role_cs_member",
                focusItemId="focus_q2_delivery",
                departmentPlanItemId="plan_item_client_followup",
                controlLevel="normal",
                departmentFocusKey="客户推进",
                organizationFocusKey="关键客户交付推进",
                isCrossDepartment=False,
                approvalState="none",
                needsReview=False,
            ),
        ),
    ]

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=items,
        governance=governance,
        organization_dna_modules=[],
        org_model_profile=org_profile,
    )

    assert org_report is not None
    assert len(department_reports) == 1
    department_report = department_reports[0]
    assert department_report.sourcePolicy["roleDriftCount"] == 1
    assert department_report.sourcePolicy["reviewChainCount"] == 1
    assert department_report.sourcePolicy["controlledTaskCount"] == 1
    assert department_report.sourcePolicy["crossDepartmentCount"] == 1
    assert department_report.sourcePolicy["workflowBlockedCount"] == 1
    assert department_report.sourcePolicy["projectContextCount"] == 1
    assert department_report.sourcePolicy["linkedFocusItemCount"] == 1
    assert department_report.sourcePolicy["linkedDepartmentPlanItemCount"] == 1
    assert any("职责边界" in area for area in department_report.focusAreas)
    assert any("流程卡点" in area for area in department_report.focusAreas)
    assert any("待复核" in signal or "汇报" in signal for signal in department_report.supportSignals)
    assert any("固定节点" in signal or "流程" in signal for signal in department_report.supportSignals)
    assert "挂接项目背景" in department_report.summary or "正式计划" in department_report.summary
    assert "职责边界" in department_report.summary or "待复核" in department_report.summary
    assert department_report.sourcePolicy["overloadCount"] == 0
    assert department_report.sourcePolicy["supportNeedCount"] == 0
    assert department_report.sourcePolicy["misalignedCount"] == 0
    assert department_report.sourcePolicy["projectRiskCount"] == 1
    assert department_report.actions
    assert any(action.actionType == "meeting" for action in department_report.actions)
    assert any(action.actionType == "one_on_one" for action in department_report.actions)
    assert any(action.actionType == "task" for action in department_report.actions)
    assert any("缩短复核与协作链" in action.title for action in department_report.actions)
    assert org_report.actions
    assert any(action.actionType == "meeting" for action in org_report.actions)


def test_build_employee_review_report_reads_org_context_signals():
    org_profile = build_org_model_profile()
    item = build_item(
        "task_personal_org",
        "长期承担底层技术修复并等待部门确认",
        "佳乐",
        WeeklyReviewTaskStructuredNoteRecord(
            reflection="这周推进了修复，但明显卡在确认链上。",
            lightweightTag="等待他人",
            completionStatus="in_progress",
        ),
        owner_id="user_jianing",
        org_context=TaskOrgContextRecord(
            departmentId="dept_customer_service",
            roleTemplateId="role_cs_member",
            controlRuleId="rule_department_key",
            controlLevel="department_control",
            isCrossDepartment=True,
            approvalState="pending",
            needsReview=True,
        ),
    )
    analysis = type("AnalysisLike", (), {})()
    analysis.scope = "work"
    analysis.emphasis = "analysis"
    analysis.headline = "本周任务推进呈现“有进展，但卡点也已开始显性化”的状态。"
    analysis.caution = "以下判断是带权重的假设性分析。"
    analysis.metricCards = []
    analysis.evidenceWeights = []
    analysis.confirmedFacts = ["当前已有 1 项写入一线复盘说明。"]
    analysis.hypothesisHighlights = []
    analysis.nextWeekFocus = ["优先补齐支持需求。"]

    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="user_jianing",
        items=[item],
        analysis=analysis,
        org_model_profile=org_profile,
    )

    assert report.logicMode == "employee_org_context_v1"
    assert report.sourcePolicy["roleDriftCount"] == 1
    assert report.sourcePolicy["reviewChainCount"] == 1
    assert report.sourcePolicy["controlledTaskCount"] == 1
    assert report.sourcePolicy["workflowBlockedCount"] == 1
    assert any("职责边界" in area for area in report.focusAreas)
    assert any("待复核" in signal for signal in report.supportSignals)
    assert report.actions
    assert any(action.actionType == "meeting" for action in report.actions)
    assert any(action.actionType == "one_on_one" for action in report.actions)


def test_build_employee_review_report_department_lead_uses_department_logic():
    org_profile = build_org_model_profile()
    item = build_item(
        "task_department_lead",
        "推进黄河基金会合作边界确认",
        "佳乐",
        WeeklyReviewTaskStructuredNoteRecord(
            reflection="先把合作边界和关键人确认下来。",
            completionStatus="in_progress",
        ),
        owner_id="user_jianing",
        org_context=TaskOrgContextRecord(
            departmentId="dept_customer_service",
            roleTemplateId="role_cs_member",
            focusItemId="focus_q2_delivery",
            departmentPlanItemId="plan_item_client_followup",
            controlLevel="department_control",
            needsReview=True,
        ),
        project_context=TaskProjectContextRecord(
            clientId="client_hh",
            clientName="黄河基金会",
            stage="业务拓展",
            backgroundSummary="围绕黄河基金会合作边界和确认节奏推进。",
            goalSummary="确认合作边界和下一轮沟通。",
            riskSummary="合作边界和关键确认节点还没有收束。",
            currentFocus="当前主要在推进：合作边界和下一轮沟通确认。",
            currentBlocker="合作边界和关键确认节点还没有收束。",
            nextAction="锁定下一轮沟通时间并把合作边界确认清楚。",
            recentProgress="最近进展：双方已经开始围绕合作边界进行确认。",
            infoCompleteness="high",
            sourceEvidence=["客户工作台"],
        ),
        event_line_id="eline_hh_followup",
        event_line_name="黄河基金会合作确认",
    )

    analysis = build_weekly_review_analysis(
        "work",
        "2026-W11",
        [item],
        [],
        org_model_profile=org_profile,
        viewer_role="department_lead",
    )
    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="dept_customer_service",
        items=[item],
        analysis=analysis,
        org_model_profile=org_profile,
        viewer_role="department_lead",
    )

    assert report.logicMode == "department_lead_eventline_context_v1"
    assert report.sourcePolicy["roleView"] == "department_lead"
    assert any("黄河基金会合作确认" in area for area in report.focusAreas)
    assert any("合作边界" in signal or "部门" in signal for signal in report.supportSignals)


def test_build_employee_review_report_creates_capacity_and_support_actions():
    org_profile = build_org_model_profile()
    item = build_item(
        "task_capacity",
        "等待资料补齐并安排客户推进",
        "佳乐",
        WeeklyReviewTaskStructuredNoteRecord(
            reflection="本周排期已经很满，还在等外部资料。",
            lightweightTag="工作过度饱和",
            supportNeeded="需要补齐项目资料后才能继续推进。",
            completionStatus="in_progress",
        ),
        owner_id="user_jianing",
        org_context=TaskOrgContextRecord(
            departmentId="dept_customer_service",
            roleTemplateId="role_cs_member",
            controlLevel="normal",
            isCrossDepartment=False,
            approvalState="none",
            needsReview=False,
        ),
        project_context=TaskProjectContextRecord(
            clientId="client_demo",
            clientName="示例客户",
            stage="交付推进",
            backgroundSummary="围绕关键客户交付推进组织协同。",
            goalSummary="推进关键客户交付方案。",
            riskSummary="资料未补齐导致推进卡住。",
            infoCompleteness="high",
            sourceEvidence=["客户工作台来源"],
        ),
    )
    analysis = type("AnalysisLike", (), {})()
    analysis.scope = "work"
    analysis.emphasis = "analysis"
    analysis.headline = "本周任务推进受到容量和资料依赖双重影响。"
    analysis.caution = "以下判断是带权重的假设性分析。"
    analysis.metricCards = []
    analysis.evidenceWeights = []
    analysis.confirmedFacts = ["当前已有 1 项写入一线复盘说明。"]
    analysis.hypothesisHighlights = []
    analysis.nextWeekFocus = ["先收束这项任务的资料依赖，再重新安排时间。"]

    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="user_jianing",
        items=[item],
        analysis=analysis,
        org_model_profile=org_profile,
    )

    assert report.sourcePolicy["overloadCount"] == 1
    assert report.sourcePolicy["supportNeedCount"] == 1
    assert report.sourcePolicy["projectRiskCount"] == 1
    assert any(action.actionType == "resource_request" for action in report.actions)
    assert any(action.actionType == "support_request" for action in report.actions)
    assert any(action.actionType == "task" for action in report.actions)


def test_build_employee_review_report_includes_event_line_signals():
    analysis = type("AnalysisLike", (), {})()
    analysis.scope = "work"
    analysis.emphasis = "analysis"
    analysis.headline = "本周事项开始围绕连续工作线推进。"
    analysis.caution = "以下判断是带权重的假设性分析。"
    analysis.metricCards = []
    analysis.evidenceWeights = []
    analysis.confirmedFacts = ["当前已有 2 项写入一线复盘说明。"]
    analysis.hypothesisHighlights = []
    analysis.nextWeekFocus = ["先收束这一条线的后续动作。"]

    items = [
        build_item(
            "task_event_1",
            "推进云南连心第一轮沟通",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(
                reflection="这周先完成第一轮沟通。",
                completionStatus="in_progress",
            ),
            owner_id="user_jianing",
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
        build_item(
            "task_event_2",
            "整理云南连心后续推进方案",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(
                reflection="还需要继续推进后续方案。",
                completionStatus="in_progress",
            ),
            owner_id="user_jianing",
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
    ]

    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="user_jianing",
        items=items,
        analysis=analysis,
    )

    assert report.sourcePolicy["eventLineCount"] == 1
    assert report.sourcePolicy["multiTaskEventLineCount"] == 1
    assert report.sourcePolicy["blockedEventLineCount"] == 1
    assert any("事件线连续推进" in area for area in report.focusAreas)
    assert "事件线" in report.summary
    assert any("事件线" in signal for signal in report.supportSignals)
    assert report.actions
    assert any(action.payload.get("primaryEventLineId") == "event_yunnan" for action in report.actions)
    assert any(action.payload.get("primaryEventLineName") == "云南连心" for action in report.actions)


def test_build_executive_review_rollup_includes_event_line_counts():
    governance = ReviewGovernanceSettingsRecord(
        departments=[
            ReviewDepartmentConfigRecord(
                id="dept_customer_service",
                name="客户服务部",
                monthlyDna="本月重点推进关键客户沟通和交付闭环。",
                weeklyFocus="本周重点收束关键客户沟通结果。",
                members=[ReviewDepartmentMemberRecord(id="user_jianing", fullName="佳乐")],
            )
        ],
        updatedAt="2026-03-21T10:00:00",
    )
    items = [
        build_item(
            "task_org_event_1",
            "推进云南连心第一轮沟通",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(completionStatus="in_progress"),
            owner_id="user_jianing",
            org_context=TaskOrgContextRecord(departmentId="dept_customer_service"),
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
        build_item(
            "task_org_event_2",
            "整理云南连心后续推进方案",
            "佳乐",
            WeeklyReviewTaskStructuredNoteRecord(completionStatus="in_progress"),
            owner_id="user_jianing",
            org_context=TaskOrgContextRecord(departmentId="dept_customer_service"),
            event_line_id="event_yunnan",
            event_line_name="云南连心",
        ),
    ]

    org_report, department_reports = build_executive_review_rollup(
        week_label="2026-W11",
        work_items=items,
        governance=governance,
        organization_dna_modules=[],
    )

    assert org_report is not None
    assert len(department_reports) == 1
    assert org_report.sourcePolicy["eventLineCount"] == 1
    assert org_report.sourcePolicy["multiTaskEventLineCount"] == 1
    assert department_reports[0].sourcePolicy["eventLineCount"] == 1
    assert "事件线" in org_report.summary
    assert any("事件线连续推进" in area for area in org_report.focusAreas)
    assert any("｜" in area for area in org_report.focusAreas)
    assert any("事件线" in signal for signal in department_reports[0].supportSignals)


def test_build_employee_review_report_admin_uses_event_line_specific_summary():
    items = [
        build_item(
            "task_admin_report_1",
            "推进黄河基金会合作方案初稿",
            "顾源源",
            WeeklyReviewTaskStructuredNoteRecord(
                progress="黄河基金会合作方案进入内部讨论阶段。",
                nextAction="补齐方案分工后与黄河基金会确认下一轮沟通。",
                completionStatus="in_progress",
            ),
            owner_id="user_guyuan",
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="黄河基金会当前围绕合作方案做前期业务判断。",
                goalSummary="把合作方案推进到可确认范围。",
                riskSummary="当前风险是方案分工和下一轮沟通安排还没完全收束。",
                currentFocus="当前主要在推进：黄河基金会合作方案初稿。",
                currentBlocker="当前阻塞：方案分工和下一轮沟通安排还没完全收束。",
                nextAction="下一步动作：补齐方案分工后与黄河基金会确认下一轮沟通。",
                recentProgress="最近进展：黄河基金会合作方案进入内部讨论阶段。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_hh",
            event_line_name="黄河基金会合作推进",
        ),
        build_item(
            "task_admin_report_2",
            "补齐黄河基金会下一轮沟通提纲",
            "顾源源",
            WeeklyReviewTaskStructuredNoteRecord(
                blockerReason="下一轮沟通提纲还没完全收束。",
                completionStatus="in_progress",
            ),
            owner_id="user_guyuan",
            project_context=TaskProjectContextRecord(
                clientId="client_hh",
                clientName="黄河基金会",
                stage="业务拓展",
                backgroundSummary="黄河基金会当前围绕合作方案做前期业务判断。",
                goalSummary="把合作方案推进到可确认范围。",
                riskSummary="当前风险是方案分工和下一轮沟通安排还没完全收束。",
                currentFocus="当前主要在推进：黄河基金会合作方案初稿。",
                currentBlocker="当前阻塞：方案分工和下一轮沟通安排还没完全收束。",
                nextAction="下一步动作：补齐方案分工后与黄河基金会确认下一轮沟通。",
                recentProgress="最近进展：黄河基金会合作方案进入内部讨论阶段。",
                infoCompleteness="high",
                sourceEvidence=["客户工作台"],
            ),
            event_line_id="eline_hh",
            event_line_name="黄河基金会合作推进",
        ),
    ]
    analysis = build_weekly_review_analysis(
        "work",
        "2026-W11",
        items,
        [build_org_module("organization_intro", "组织介绍", "2026 Q2 重点目标：推进关键客户交付与业务扩展。")],
        viewer_role="admin",
    )

    report = build_employee_review_report(
        week_label="2026-W11",
        scope_ref_id="user_guyuan",
        items=items,
        analysis=analysis,
        viewer_role="admin",
    )

    assert report.logicMode == "admin_eventline_context_v1"
    assert "黄河基金会" in report.summary
    assert any("黄河基金会合作推进" in area for area in report.focusAreas)
    assert any("｜" in area for area in report.focusAreas)
    assert not any(card.label == "个人-部门对齐率" for card in report.summaryMetrics)
    assert "推进事项" in report.summary or "黄河基金会合作方案初稿" in report.summary
    assert report.sourcePolicy["eventLineSummaryCount"] >= 1
    assert report.sourcePolicy["eventLineRiskCount"] >= 1
~~~

## `backend/tests/test_review_simulation.py`

- 编码: `utf-8`

~~~python
from app.models import OrganizationDnaModuleRecord
from app.services.review_simulation import build_review_simulation_bundle


def build_org_module(module_key: str, title: str, summary: str) -> OrganizationDnaModuleRecord:
    return OrganizationDnaModuleRecord(
        moduleKey=module_key,  # type: ignore[arg-type]
        title=title,
        markdownContent="",
        normalizedText=summary,
        summary=summary,
        fileName=None,
        contentHash=None,
        updatedAt="2026-03-01T00:00:00",
        updatedBy="tester",
        hasDocument=True,
    )


def test_build_review_simulation_bundle_returns_org_and_department_reports():
    modules = [
        build_org_module("organization_intro", "组织介绍", "组织当前关注跨部门协同。"),
        build_org_module("business_intro", "业务介绍", "业务当前关注把验证路径做深。"),
        build_org_module("team_intro", "团队介绍", "团队当前需要收敛接口节奏。"),
    ]

    bundle = build_review_simulation_bundle(
        week_label="2026-W11",
        organization_dna_modules=modules,
        sample_size=20,
    )

    assert bundle.label == "CEO 调参与 20 人模拟视角"
    assert bundle.sampleSize == 20
    assert bundle.orgReport is not None
    assert len(bundle.departmentReports) == 4
    assert bundle.orgReport.sourcePolicy["sampleSize"] == 20
    assert any(report.scopeRefId == "咨询策略部" for report in bundle.departmentReports)


def test_build_review_simulation_bundle_is_work_only_and_simulated():
    bundle = build_review_simulation_bundle(
        week_label="2026-W11",
        organization_dna_modules=[],
        sample_size=20,
    )

    assert bundle.orgReport is not None
    assert bundle.orgReport.sourcePolicy["simulationMode"] is True
    assert bundle.orgReport.sourcePolicy["visibility"] == "ceo_work_only"
    assert all(report.sourcePolicy["simulationMode"] is True for report in bundle.departmentReports)
    assert all(report.sourcePolicy["visibility"] == "ceo_work_only" for report in bundle.departmentReports)
~~~

## `backend/tests/test_review_visibility.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_department_lead_only_receives_own_department_summary(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    lists_response = client.get("/api/v1/tasks")
    assert lists_response.status_code == 200
    default_list_id = lists_response.json()["lists"][0]["id"]

    governance_response = client.post(
        "/api/v1/settings/review-governance",
        json={
            "departments": [
                {
                    "id": "dept_consult_strategy",
                    "name": "咨询策略部",
                    "color": "#5B7BFE",
                    "monthlyDna": "本月重点是把战略判断和客户方案打磨做深。",
                    "leaders": [{"id": "lead_1", "fullName": "部门负责人"}],
                    "members": [
                        {"id": "lead_1", "fullName": "部门负责人"},
                        {"id": "member_1", "fullName": "同事甲"},
                    ],
                },
                {
                    "id": "dept_info_data",
                    "name": "信息数据部",
                    "color": "#10B981",
                    "monthlyDna": "本月重点是把信息处理和数据口径校准下来。",
                    "leaders": [{"id": "lead_2", "fullName": "别的负责人"}],
                    "members": [{"id": "member_2", "fullName": "同事乙"}],
                },
            ]
        },
    )
    assert governance_response.status_code == 200

    db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "lead_1",
                "organizationId": "org_1",
                "email": "lead@example.com",
                "fullName": "部门负责人",
                "primaryRole": "employee",
                "accountStatus": "approved",
            }
        ),
    )

    task_one = client.post(
        "/api/v1/tasks",
        json={
            "title": "推进战略判断",
            "desc": "整理本周战略推进结论",
            "priority": "high",
            "listId": default_list_id,
            "dueDate": "2026-03-14",
            "ddl": "2026-03-14",
            "ownerId": "member_1",
            "ownerName": "同事甲",
            "collaboratorIds": ["lead_1"],
            "tagIds": [],
        },
    )
    assert task_one.status_code == 200
    task_one_id = task_one.json()["id"]

    task_two = client.post(
        "/api/v1/tasks",
        json={
            "title": "推进信息清洗",
            "desc": "整理本周信息数据侧工作",
            "priority": "normal",
            "listId": default_list_id,
            "dueDate": "2026-03-15",
            "ddl": "2026-03-15",
            "ownerId": "member_2",
            "ownerName": "同事乙",
            "collaboratorIds": [],
            "tagIds": [],
        },
    )
    assert task_two.status_code == 200
    task_two_id = task_two.json()["id"]

    review_response = client.post(
        "/api/v1/reviews/weekly",
        json={
            "weekLabel": "2026-W11",
            "taskEntries": [
                {
                    "taskId": task_one_id,
                    "contentDomain": "work",
                    "note": "本周已完成主要判断整理。",
                    "structuredNote": {
                        "progress": "完成关键判断梳理",
                        "successReason": "问题口径更清晰",
                        "blockerReason": "",
                        "supportNeeded": "",
                        "nextAction": "下周继续推进方案表达",
                    },
                },
                {
                    "taskId": task_two_id,
                    "contentDomain": "work",
                    "note": "本周在处理数据清洗。",
                    "structuredNote": {
                        "progress": "完成数据清洗第一轮",
                        "successReason": "",
                        "blockerReason": "口径还不统一",
                        "supportNeeded": "",
                        "nextAction": "补齐统一字段说明",
                    },
                },
            ],
        },
    )
    assert review_response.status_code == 200

    dashboard = client.get("/api/v1/reviews")
    assert dashboard.status_code == 200
    payload = dashboard.json()

    assert payload["executiveOrgReport"] is None
    assert payload["simulationBundle"] is None
    assert payload["agentDepartmentDigests"] == []
    assert payload["agentDepartmentPlans"] == []
    assert len(payload["departmentReports"]) == 1
    assert payload["departmentReports"][0]["scopeRefId"] == "咨询策略部"


def test_department_lead_can_view_own_agent_execution_tasks_only(tmp_path: Path):
    client = make_client(tmp_path)
    db = client.app.state.app_state.db

    governance_response = client.post(
        "/api/v1/settings/review-governance",
        json={
            "departments": [
                {
                    "id": "dept_consult_strategy",
                    "name": "咨询策略部",
                    "color": "#5B7BFE",
                    "monthlyDna": "本月重点是把战略判断做深。",
                    "leaders": [{"id": "lead_1", "fullName": "部门负责人"}],
                    "members": [{"id": "lead_1", "fullName": "部门负责人"}],
                },
                {
                    "id": "dept_tech",
                    "name": "科技发展部",
                    "color": "#F59E0B",
                    "monthlyDna": "本月重点是推进系统迭代。",
                    "leaders": [{"id": "lead_2", "fullName": "别的负责人"}],
                    "members": [{"id": "lead_2", "fullName": "别的负责人"}],
                },
            ]
        },
    )
    assert governance_response.status_code == 200

    db.set_setting(
        "cloud_session_user",
        json.dumps(
            {
                "id": "lead_1",
                "organizationId": "org_1",
                "email": "lead@example.com",
                "fullName": "部门负责人",
                "primaryRole": "employee",
                "accountStatus": "approved",
            }
        ),
    )
    db.execute(
        """
        INSERT INTO activity_logs(id, actor_name, action, entity_type, entity_id, detail_json, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "log_qinghua_1",
            "庆华",
            "task.update",
            "task",
            "task_1",
            json.dumps({"title": "推进战略判断闭环"}, ensure_ascii=False),
            "2026-03-12T10:00:00",
        ),
    )

    response = client.get("/api/v1/tasks/agent-execution?week=2026-W11")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert all(any(tag["name"] == "咨询策略部" for tag in item["tags"]) for item in payload)

    forbidden = client.get("/api/v1/tasks/agent-execution?week=2026-W11&department=科技发展部")
    assert forbidden.status_code == 403
~~~

## `backend/tests/test_strategic_learning_workbench.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def ensure_default_list_id(client: TestClient) -> str:
    board = client.get("/api/v1/tasks")
    assert board.status_code == 200
    return board.json()["lists"][0]["id"]


def create_client_record(client: TestClient, *, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益合作",
            "type": "client",
            "intro": f"{name} 项目资料",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def create_task_record(
    client: TestClient,
    *,
    list_id: str,
    title: str,
    desc: str,
    client_id: str | None = None,
    business_category: str = "strategic_accompaniment",
) -> str:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": desc,
            "priority": "normal",
            "listId": list_id,
            "dueDate": "2026-04-21",
            "ddl": "2026-04-21",
            "ownerName": "测试用户",
            "ownerId": None,
            "collaboratorIds": [],
            "tagIds": [],
            "clientId": client_id,
            "businessCategory": business_category,
            "sourceType": "manual",
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def lesson_titles(payload: dict) -> list[str]:
    return [item["title"] for item in payload["genericLessons"]]


def test_growth_workbench_default_mode_still_works(tmp_path: Path):
    client = make_client(tmp_path)
    response = client.get("/api/v1/growth/workbench")
    assert response.status_code == 200
    payload = response.json()
    assert "learningSummary" in payload
    assert "sourceMode" in payload


def test_strategic_growth_workbench_empty_returns_starter_presets(tmp_path: Path):
    client = make_client(tmp_path)
    response = client.get("/api/v1/growth/workbench?mode=strategic")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scopeMode"] == "strategic"
    assert payload["sourceMode"] == "empty"
    assert payload["learningSummary"]["generator"] == "rules"
    assert payload["genericLessons"]
    assert any("机构介绍三段式" in item["title"] for item in payload["genericLessons"])
    assert payload["reasoningTrace"]["mode"] == "rules_only"
    assert payload["reasoningTrace"]["aiContribution"] == []


def test_strategic_intro_task_matches_intro_presets(tmp_path: Path):
    client = make_client(tmp_path)
    list_id = ensure_default_list_id(client)
    strategic_client_id = create_client_record(client, name="日慈基金会")
    create_task_record(
        client,
        list_id=list_id,
        client_id=strategic_client_id,
        title="介绍日慈基金会，给出简洁清晰的项目资料",
        desc="请整理机构背景与项目重点，并形成可读的一页介绍。",
    )

    response = client.get(f"/api/v1/growth/workbench?mode=strategic&clientId={strategic_client_id}")
    assert response.status_code == 200
    payload = response.json()
    titles = lesson_titles(payload)
    assert "机构介绍三段式" in titles
    assert "项目介绍五要素" in titles or "一页简介写作卡" in titles
    assert "事实、判断、建议分离卡" in titles
    assert payload["learningSummary"]["generator"] == "rules"


def test_strategic_meeting_task_matches_meeting_presets(tmp_path: Path):
    client = make_client(tmp_path)
    list_id = ensure_default_list_id(client)
    strategic_client_id = create_client_record(client, name="为爱黔行")
    create_task_record(
        client,
        list_id=list_id,
        client_id=strategic_client_id,
        title="提炼最新会议纪要，整理下一步行动项",
        desc="把会议讨论拆成事实、决定、行动、风险，并明确下一步责任人。",
    )

    response = client.get(f"/api/v1/growth/workbench?mode=strategic&clientId={strategic_client_id}")
    assert response.status_code == 200
    payload = response.json()
    titles = lesson_titles(payload)
    assert "会议纪要四分法" in titles
    assert "下一步行动提取卡" in titles


def test_strategic_judgment_task_matches_judgment_presets(tmp_path: Path):
    client = make_client(tmp_path)
    list_id = ensure_default_list_id(client)
    strategic_client_id = create_client_record(client, name="乡基会")
    create_task_record(
        client,
        list_id=list_id,
        client_id=strategic_client_id,
        title="把待确认判断整理成正式判断草案",
        desc="补齐证据后给出正式判断，并说明边界与风险。",
    )

    response = client.get(f"/api/v1/growth/workbench?mode=strategic&clientId={strategic_client_id}")
    assert response.status_code == 200
    payload = response.json()
    titles = lesson_titles(payload)
    assert "候选判断转正式判断卡" in titles
    assert "证据够不够检查卡" in titles
    assert payload["reasoningTrace"]["mode"] == "rules_only"
    assert payload["reasoningTrace"]["aiContribution"] == []

~~~

## `backend/tests/test_strategic_thought_quality.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "测试客户",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_placeholder_event_line(client: TestClient, client_id: str, name: str = "品牌推进") -> None:
    response = client.post(
        "/api/v1/event-lines",
        json={
            "name": name,
            "primaryClientId": client_id,
        },
    )
    assert response.status_code == 200, response.text


def test_placeholder_line_not_promoted_to_draft(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "占位线客户")
    create_placeholder_event_line(client, client_id, "品牌推进")

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20")
    assert response.status_code == 200, response.text
    items = response.json()["items"]

    placeholder_line_cards = [item for item in items if "品牌推进" in str(item.get("line", ""))]
    assert not placeholder_line_cards or all(
        item.get("status") == "waiting_evidence" and item.get("confidence") is None
        for item in placeholder_line_cards
    )
    assert all(
        not (
            item.get("status") == "draft"
            and (
                "当前阻塞仍待澄清" in str(item.get("observation", ""))
                or "先补下一步动作" in str(item.get("suggestion", ""))
            )
        )
        for item in items
    )


def test_internal_topic_key_not_leaked_in_thought_text(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "内部key客户")
    now = datetime.now().replace(microsecond=0).isoformat()
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence, created_at, updated_at
        ) VALUES(?, ?, 'client', ?, ?, 1, ?, ?, '[]', NULL, 'medium', 'medium', ?, ?)
        """,
        (
            "judgment_candidate_topic_key",
            client_id,
            client_id,
            "client_overview",
            "awaiting_review",
            "client_overview：这条候选判断已经有具体业务事实与推进描述。",
            now,
            now,
        ),
    )

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20")
    assert response.status_code == 200, response.text
    payload = response.json()
    joined = "\n".join(
        f"{item.get('line', '')}\n{item.get('observation', '')}\n{item.get('suggestion', '')}"
        for item in payload.get("items", [])
    )
    assert "client_overview" not in joined
    assert any("概况判断" in str(item.get("line", "")) or "待确认判断" in str(item.get("line", "")) for item in payload.get("items", []))


def test_waiting_evidence_cards_merged_per_client(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "缺口合并客户")
    create_placeholder_event_line(client, client_id, "资料待补线")

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20")
    assert response.status_code == 200, response.text
    items = [item for item in response.json()["items"] if item.get("clientId") == client_id]
    waiting_items = [item for item in items if item.get("status") == "waiting_evidence"]
    assert len(waiting_items) <= 1


def test_weak_evidence_never_gets_high_confidence(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "弱证据客户")
    create_placeholder_event_line(client, client_id, "默认占位线")

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    weak_items = [item for item in items if item.get("evidenceLevel") in {"none", "weak"}]
    assert weak_items
    assert all(item.get("confidenceLevel") in {"none", "low"} for item in weak_items)


def test_all_clients_not_flooded_with_waiting_cards(tmp_path: Path):
    client = make_client(tmp_path)
    created_ids = [create_test_client_record(client, f"全局客户{i}") for i in range(1, 6)]
    for cid in created_ids:
        create_placeholder_event_line(client, cid, f"占位线-{cid[-4:]}")

    response = client.get("/api/v1/strategic/thoughts?limit=10")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    per_client_count: dict[str, int] = {}
    for item in items:
        client_id = item.get("clientId")
        if not client_id:
            continue
        per_client_count[client_id] = per_client_count.get(client_id, 0) + 1
    assert all(count <= 1 for count in per_client_count.values())
    assert len(items) <= 10


def test_strategic_brain_view_no_cffc_fallback_and_uses_client_id():
    target = Path(__file__).resolve().parents[2] / "src/renderer/components/strategic_accompaniment/StrategicBrainView.tsx"
    text = target.read_text(encoding="utf-8")
    assert "PROJECT_DETAILS['CFFC']" not in text
    assert "onOpenDetail(client.name)" not in text
    assert re.search(r"onClick=\{\(\) => onOpenDetail\(client\.id\)\}", text)
~~~

## `backend/tests/test_strategic_thoughts_api.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "测试客户",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _first_client_thought(payload: dict, client_id: str) -> dict:
    for item in payload.get("items", []):
        if item.get("scope") == "client" and item.get("clientId") == client_id:
            return item
    raise AssertionError(f"未找到 client={client_id} 的思考卡")


def test_strategic_thoughts_do_not_return_mock_cards(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "测试客户A")

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["usingMockData"] is False
    joined = "\n".join(
        [str(item.get("line", "")) + str(item.get("observation", "")) for item in payload.get("items", [])]
    )
    assert "CFFC" not in joined
    assert "日慈基金会" not in joined


def test_strategic_thoughts_client_filter_works(tmp_path: Path):
    client = make_client(tmp_path)
    client_a = create_test_client_record(client, "过滤客户A")
    client_b = create_test_client_record(client, "过滤客户B")

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_a}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert any(item.get("clientId") == client_a for item in payload.get("items", []))
    assert all(item.get("clientId") != client_b for item in payload.get("items", []))


def test_strategic_thoughts_insufficient_data_has_no_high_confidence_and_has_waiting_hint(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "资料不足客户")

    first = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    second = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    first_payload = first.json()
    second_payload = second.json()

    first_ids = {item["id"] for item in first_payload.get("items", [])}
    second_ids = {item["id"] for item in second_payload.get("items", [])}
    assert first_ids == second_ids

    client_items = [item for item in first_payload.get("items", []) if item.get("clientId") == client_id]
    assert client_items
    assert all(item.get("confidenceLevel") != "high" for item in client_items)
    assert any(
        item.get("status") == "waiting_evidence" or "还缺" in str(item.get("suggestion", ""))
        for item in client_items
    )


def test_strategic_thought_review_confirm_persists(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "确认持久化客户")

    before = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert before.status_code == 200, before.text
    thought = _first_client_thought(before.json(), client_id)

    confirm = client.post(
        f"/api/v1/strategic/thoughts/{thought['id']}/review",
        json={"action": "confirm", "note": "先补一轮核心资料再推进", "createJudgment": True},
    )
    assert confirm.status_code == 200, confirm.text
    confirmed_payload = confirm.json()
    assert confirmed_payload["status"] == "confirmed"
    assert confirmed_payload["review"]["note"] == "先补一轮核心资料再推进"

    after = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert after.status_code == 200, after.text
    item = next((x for x in after.json()["items"] if x["id"] == thought["id"]), None)
    assert item is not None
    assert item["status"] == "confirmed"
    assert item["review"]["note"] == "先补一轮核心资料再推进"


def test_strategic_thought_dismiss_hidden_by_default_and_visible_when_requested(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "忽略过滤客户")

    initial = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert initial.status_code == 200, initial.text
    thought = _first_client_thought(initial.json(), client_id)

    dismiss = client.post(
        f"/api/v1/strategic/thoughts/{thought['id']}/review",
        json={"action": "dismiss", "note": "先忽略"},
    )
    assert dismiss.status_code == 200, dismiss.text
    assert dismiss.json()["status"] == "dismissed"

    hidden = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert hidden.status_code == 200, hidden.text
    assert all(item["id"] != thought["id"] for item in hidden.json()["items"])

    visible = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&includeDismissed=true")
    assert visible.status_code == 200, visible.text
    restored = next((item for item in visible.json()["items"] if item["id"] == thought["id"]), None)
    assert restored is not None
    assert restored["status"] == "dismissed"
~~~

## `backend/tests/test_task_cloud_writeback.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def seed_cloud_token(client: TestClient) -> None:
    client.app.state.app_state.db.set_setting("cloud_access_token", "token_demo")


def ensure_default_list(client: TestClient) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT OR IGNORE INTO task_lists(
            id, organization_id, name, color, sort_order, is_default, scope
        ) VALUES(?, '', ?, ?, 0, 1, 'org')
        """,
        ("list-0", "收集箱", "#5B7BFE"),
    )


def seed_cloud_shadow_task(client: TestClient, *, task_id: str, cloud_id: str, status: str = "inbox") -> None:
    ensure_default_list(client)
    client.app.state.app_state.db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, status, priority, list_id, creator_id, owner_id, owner_name,
            progress_status, ddl, due_date, duration_minutes, scope_mode, source_type, source_id,
            tags_json, tag_ids_json, created_at, updated_at, sync_status, cloud_id
        ) VALUES(?, '', ?, ?, ?, 'normal', 'list-0', '', ?, ?, ?, ?, ?, 60, 'COLLAB_SHARED', 'manual', NULL, '[]', '[]', ?, ?, 'synced', ?)
        """,
        (
            task_id,
            "乡基会报表",
            "本地旧影子",
            status,
            "user_emp",
            "普通员工",
            "todo",
            "周五",
            "2026-04-17T09:00:00",
            "2026-04-17T00:00:00",
            "2026-04-17T00:00:00",
            cloud_id,
        ),
    )


def test_confirm_task_writes_back_cloud_payload_to_existing_local_shadow(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_token(client)
    seed_cloud_shadow_task(client, task_id="task_local_1", cloud_id="task_cloud_1")

    cloud_task = {
        "id": "task_cloud_1",
        "title": "乡基会报表",
        "description": "云端已确认",
        "priority": "normal",
        "listId": "list-0",
        "listName": "收集箱",
        "listColor": "#5B7BFE",
        "dueDate": "2026-04-17T09:00:00",
        "durationMinutes": 60,
        "scopeMode": "COLLAB_SHARED",
        "ownerId": "user_emp",
        "ownerName": "普通员工",
        "sourceType": "manual",
        "progressStatus": "todo",
        "viewerInboxStatus": "accepted",
        "collaborators": [
            {
                "userId": "user_emp",
                "fullName": "普通员工",
                "email": "employee@example.com",
                "orderIndex": 0,
                "isOwner": True,
                "inboxStatus": "accepted",
                "handledAt": "2026-04-17T00:05:00",
            }
        ],
        "createdAt": "2026-04-17T00:00:00",
        "updatedAt": "2026-04-17T00:05:00",
        "tags": [],
    }
    board_payload = {
        "tasks": [cloud_task],
        "lists": [
            {
                "id": "list-0",
                "name": "收集箱",
                "color": "#5B7BFE",
                "sortOrder": 0,
                "isDefault": True,
                "scope": "org",
            }
        ],
        "tags": [],
    }

    def fake_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url.endswith("/api/v1/auth/me"):
            return httpx.Response(
                200,
                json={
                    "id": "user_emp",
                    "organizationId": "org_1",
                    "email": "employee@example.com",
                    "fullName": "普通员工",
                    "primaryRole": "employee",
                    "accountStatus": "approved",
                },
            )
        if method.upper() == "POST" and url.endswith("/api/v1/tasks/task_cloud_1/collaborators/user_emp/accept"):
            return httpx.Response(200, json=cloud_task)
        if method.upper() == "GET" and url.endswith("/api/v1/tasks"):
            return httpx.Response(200, json=board_payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.post("/api/v1/tasks/task_cloud_1/confirm")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "todo"

    local_row = client.app.state.app_state.db.fetchone(
        "SELECT id, status, progress_status, description, cloud_id FROM tasks WHERE id = ?",
        ("task_local_1",),
    )
    assert local_row is not None
    assert local_row["status"] == "todo"
    assert local_row["progress_status"] == "todo"
    assert local_row["description"] == "云端已确认"
    assert local_row["cloud_id"] == "task_cloud_1"

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200, board.text
    tasks = {item["id"]: item for item in board.json()["tasks"]}
    assert tasks["task_local_1"]["status"] == "todo"


def test_task_board_pull_refreshes_existing_cloud_shadow_row(tmp_path: Path, monkeypatch):
    client = make_client(tmp_path)
    seed_cloud_token(client)
    seed_cloud_shadow_task(client, task_id="task_local_2", cloud_id="task_cloud_2")

    board_payload = {
        "tasks": [
            {
                "id": "task_cloud_2",
                "title": "乡基会报表",
                "description": "云端最新版",
                "priority": "normal",
                "listId": "list-0",
                "listName": "收集箱",
                "listColor": "#5B7BFE",
                "dueDate": "2026-04-17T09:00:00",
                "durationMinutes": 60,
                "scopeMode": "COLLAB_SHARED",
                "ownerId": "user_emp",
                "ownerName": "普通员工",
                "sourceType": "manual",
                "progressStatus": "todo",
                "viewerInboxStatus": "accepted",
                "createdAt": "2026-04-17T00:00:00",
                "updatedAt": "2026-04-17T00:10:00",
                "tags": [],
            }
        ],
        "lists": [
            {
                "id": "list-0",
                "name": "收集箱",
                "color": "#5B7BFE",
                "sortOrder": 0,
                "isDefault": True,
                "scope": "org",
            }
        ],
        "tags": [],
    }

    def fake_request(method: str, url: str, **kwargs):
        if method.upper() == "GET" and url.endswith("/api/v1/tasks"):
            return httpx.Response(200, json=board_payload)
        raise AssertionError(f"Unexpected cloud request: {method} {url}")

    monkeypatch.setattr(app_main.httpx, "request", fake_request)

    response = client.get("/api/v1/tasks")
    assert response.status_code == 200, response.text
    tasks = {item["id"]: item for item in response.json()["tasks"]}
    assert tasks["task_local_2"]["status"] == "todo"

    local_row = client.app.state.app_state.db.fetchone(
        "SELECT id, status, description, cloud_id FROM tasks WHERE id = ?",
        ("task_local_2",),
    )
    assert local_row is not None
    assert local_row["status"] == "todo"
    assert local_row["description"] == "云端最新版"
    assert local_row["cloud_id"] == "task_cloud_2"
~~~

## `backend/tests/test_template_fill.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document as WordDocument

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.template_fill import (
    apply_docx_template_values,
    build_template_follow_up_question,
    build_template_fill_retrieval_query,
    build_template_fill_web_queries,
    build_template_suggested_sources,
    derive_template_fill_public_names,
    derive_template_fill_public_domain,
    extract_template_milestone_year,
    extract_docx_attachment_checklist,
    extract_docx_template_fields,
    fetch_template_fill_web_sources,
    infer_template_field_type,
    infer_template_value_kind,
    normalize_template_public_domain,
    should_enable_template_fill_web_supplement,
)


def test_extract_docx_template_fields_detects_placeholders_and_blank_table_cells(tmp_path: Path):
    target = tmp_path / "template.docx"
    document = WordDocument()
    document.add_paragraph("机构名称：{{机构名称}}")
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "机构简介"
    table.rows[0].cells[1].text = ""
    table.rows[1].cells[0].text = "服务区域"
    table.rows[1].cells[1].text = "{{服务区域}}"
    document.save(target)

    fields = extract_docx_template_fields(target)
    labels = [item.label for item in fields]

    assert "机构名称" in labels
    assert "机构简介" in labels
    assert "服务区域" in labels


def test_apply_docx_template_values_fills_placeholders_and_table_cells(tmp_path: Path):
    source = tmp_path / "template.docx"
    target = tmp_path / "filled.docx"
    document = WordDocument()
    document.add_paragraph("机构名称：{{机构名称}}")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "机构简介"
    table.rows[0].cells[1].text = ""
    document.save(source)

    applied, missing = apply_docx_template_values(
        source,
        target,
        {
            "机构名称": "日慈基金会",
            "机构简介": "专注于青少年心理健康与社会情感学习。",
        },
    )

    assert applied >= 2
    assert missing == 0

    filled = WordDocument(target)
    assert "日慈基金会" in filled.paragraphs[0].text
    assert filled.tables[0].rows[0].cells[1].text == "专注于青少年心理健康与社会情感学习。"


def test_extract_docx_template_fields_detects_right_side_field_fill_pairs(tmp_path: Path):
    target = tmp_path / "paired-template.docx"
    document = WordDocument()
    table = document.add_table(rows=2, cols=4)
    table.rows[0].cells[0].text = "字段"
    table.rows[0].cells[1].text = "填写内容"
    table.rows[0].cells[2].text = "字段"
    table.rows[0].cells[3].text = "填写内容"
    table.rows[1].cells[0].text = "组织全称"
    table.rows[1].cells[1].text = ""
    table.rows[1].cells[2].text = "法定代表人"
    table.rows[1].cells[3].text = ""
    document.save(target)

    fields = extract_docx_template_fields(target)
    labels = [item.label for item in fields]

    assert "组织全称" in labels
    assert "法定代表人" in labels


def test_apply_docx_template_values_fills_right_side_field_fill_pairs(tmp_path: Path):
    source = tmp_path / "paired-template.docx"
    target = tmp_path / "paired-filled.docx"
    document = WordDocument()
    table = document.add_table(rows=2, cols=4)
    table.rows[0].cells[0].text = "字段"
    table.rows[0].cells[1].text = "填写内容"
    table.rows[0].cells[2].text = "字段"
    table.rows[0].cells[3].text = "填写内容"
    table.rows[1].cells[0].text = "组织全称"
    table.rows[1].cells[1].text = ""
    table.rows[1].cells[2].text = "法定代表人"
    table.rows[1].cells[3].text = ""
    document.save(source)

    applied, missing = apply_docx_template_values(
        source,
        target,
        {
            "组织全称": "北京基业长青社会组织服务中心",
            "法定代表人": "顾源源",
        },
    )

    assert applied == 2
    assert missing == 0

    filled = WordDocument(target)
    assert filled.tables[0].rows[1].cells[1].text == "北京基业长青社会组织服务中心"
    assert filled.tables[0].rows[1].cells[3].text == "顾源源"


def test_extract_docx_template_fields_detects_service_object_column(tmp_path: Path):
    target = tmp_path / "module-template.docx"
    document = WordDocument()
    table = document.add_table(rows=2, cols=4)
    table.rows[0].cells[0].text = "业务模块"
    table.rows[0].cells[1].text = "主要内容"
    table.rows[0].cells[2].text = "服务对象/覆盖对象"
    table.rows[0].cells[3].text = "可提取资料来源"
    table.rows[1].cells[0].text = "政策倡导"
    table.rows[1].cells[1].text = ""
    table.rows[1].cells[2].text = ""
    table.rows[1].cells[3].text = "新闻稿"
    document.save(target)

    labels = [item.label for item in extract_docx_template_fields(target)]

    assert "政策倡导" in labels
    assert "政策倡导（服务对象/覆盖对象）" in labels


def test_apply_docx_template_values_fills_service_object_column(tmp_path: Path):
    source = tmp_path / "module-template.docx"
    target = tmp_path / "module-filled.docx"
    document = WordDocument()
    table = document.add_table(rows=2, cols=4)
    table.rows[0].cells[0].text = "业务模块"
    table.rows[0].cells[1].text = "主要内容"
    table.rows[0].cells[2].text = "服务对象/覆盖对象"
    table.rows[0].cells[3].text = "可提取资料来源"
    table.rows[1].cells[0].text = "政策倡导"
    table.rows[1].cells[1].text = ""
    table.rows[1].cells[2].text = ""
    table.rows[1].cells[3].text = "新闻稿"
    document.save(source)

    applied, missing = apply_docx_template_values(
        source,
        target,
        {
            "政策倡导": "面向公益行业的政策倡导与法规建言。",
            "政策倡导（服务对象/覆盖对象）": "基金会、行业平台与政策参与方。",
        },
    )

    assert applied == 2
    assert missing == 0

    filled = WordDocument(target)
    assert filled.tables[0].rows[1].cells[1].text == "面向公益行业的政策倡导与法规建言。"
    assert filled.tables[0].rows[1].cells[2].text == "基金会、行业平台与政策参与方。"


def test_infer_template_field_type_covers_core_field_classes():
    assert infer_template_field_type("统一社会信用代码") == "precise_fact"
    assert infer_template_field_type("机构定位") == "structural_summary"
    assert infer_template_field_type("党建与业务工作的结合方式") == "governance_mechanism"
    assert infer_template_field_type("近三年代表性活动/会议数量") == "quantitative_result"
    assert infer_template_field_type("章程（含党建条款页）") == "attachment_material"


def test_infer_template_value_kind_marks_missing_values_conservatively():
    assert infer_template_value_kind("【待确认】当前缺少可直接填写该字段的资料。", "precise_fact") == "missing"
    assert infer_template_value_kind("2017年6月登记注册", "precise_fact") == "fact"
    assert infer_template_value_kind("围绕行业透明、公信力、治理能力建设开展工作。", "governance_mechanism") == "summary"


def test_extract_docx_attachment_checklist_reads_attachment_table(tmp_path: Path):
    target = tmp_path / "attachment-template.docx"
    document = WordDocument()
    table = document.add_table(rows=3, cols=4)
    table.rows[0].cells[0].text = "序号"
    table.rows[0].cells[1].text = "附件名称"
    table.rows[0].cells[2].text = "是否已备"
    table.rows[1].cells[0].text = "1"
    table.rows[1].cells[1].text = "机构登记证书复印件"
    table.rows[2].cells[0].text = "2"
    table.rows[2].cells[1].text = "章程（含党建条款页）"
    document.save(target)

    attachments = extract_docx_attachment_checklist(target)

    assert attachments == ["机构登记证书复印件", "章程（含党建条款页）"]


def test_missing_field_helpers_produce_follow_up_and_source_hints():
    follow_up = build_template_follow_up_question("governance_mechanism", "党组织在重大事项决策中的作用描述")
    sources = build_template_suggested_sources("governance_mechanism", "党组织在重大事项决策中的作用描述")

    assert "章程" in follow_up
    assert "会议纪要" in follow_up
    assert "章程" in sources
    assert "制度文件" in sources


def test_template_fill_web_supplement_only_enables_for_sparse_supported_fields():
    assert should_enable_template_fill_web_supplement("precise_fact", 0) is True
    assert should_enable_template_fill_web_supplement("structural_summary", 2) is True
    assert should_enable_template_fill_web_supplement("governance_mechanism", 0) is False
    assert should_enable_template_fill_web_supplement("structural_summary", 3) is False
    assert should_enable_template_fill_web_supplement("structural_summary", 3, field_label="2008年重大事件/里程碑") is True
    assert should_enable_template_fill_web_supplement("structural_summary", 4, field_label="2008年重大事件/里程碑") is False


def test_normalize_template_public_domain_extracts_host_safely():
    assert normalize_template_public_domain("https://www.cff.org.cn/about") == "cff.org.cn"
    assert normalize_template_public_domain("WWW.EXAMPLE.ORG") == "example.org"
    assert normalize_template_public_domain("invalid-host") is None


def test_extract_template_milestone_year_reads_year_from_label():
    assert extract_template_milestone_year("2008年重大事件/里程碑") == "2008"
    assert extract_template_milestone_year("2017重大事件/里程碑") == "2017"
    assert extract_template_milestone_year("机构定位") is None


def test_build_template_fill_retrieval_query_enriches_milestone_fields():
    query = build_template_fill_retrieval_query(
        client_name="CFFC",
        template_name="模板.docx",
        field_label="2008年重大事件/里程碑",
        field_type="structural_summary",
    )

    assert "2008年" in query
    assert "大事记" in query
    assert "发展历程" in query
    assert "模板.docx" not in query


def test_build_template_fill_web_queries_prioritizes_history_terms_for_milestones():
    queries = build_template_fill_web_queries(
        client_name="中国基金会发展论坛",
        field_label="2008年重大事件/里程碑",
        template_name="模板.docx",
        client_domain="cff.org.cn",
    )

    assert queries[0].startswith("中国基金会发展论坛 2008")
    assert any("大事记" in item for item in queries)


def test_derive_template_fill_public_names_prefers_chinese_org_name_from_local_titles():
    names = derive_template_fill_public_names(
        "CFFC",
        [
            "2016-2020年中国基金会发展论坛年会评估报告_CFFC_20260211.docx",
            "北京基业长青社会组织服务中心品牌使用指南（2025年过渡期版）_CFFC_20260211.docx",
        ],
    )

    assert names[0] == "CFFC"
    assert "中国基金会发展论坛" in names


def test_derive_template_fill_public_names_strips_rule_like_suffixes_from_titles():
    names = derive_template_fill_public_names(
        "CFFC",
        [
            "附件二：中国基金会发展论坛组委会运行规则-2023年度组委会第三次会议决议版_CFFC_20260211.pdf",
        ],
    )

    assert "中国基金会发展论坛" in names


def test_derive_template_fill_public_names_can_also_use_local_snippets():
    names = derive_template_fill_public_names(
        "CFFC",
        [],
        [
            "中国基金会发展论坛（英文名称 China Foundation Forum，中文简称基金会论坛，英文简称 CFF）是由多家机构共同发起的行业平台。",
        ],
    )

    assert "中国基金会发展论坛" in names
    assert "基金会论坛" in names


def test_derive_template_fill_public_names_ignores_generic_title_candidates():
    names = derive_template_fill_public_names(
        "CFFC",
        [
            "基金会实务工具包_CFFC_20260211.docx",
            "组织架构图_CFFC_20260211.docx",
            "中国基金会发展论坛2023年会项目总结报告_CFFC_20260211.docx",
        ],
    )

    assert "基金会实务工具包" not in names
    assert "组织架构图" not in names
    assert "中国基金会发展论坛" in names


def test_derive_template_fill_public_names_prefers_snippet_org_name_before_generic_titles():
    names = derive_template_fill_public_names(
        "CFFC",
        [
            "基金会实务工具包_CFFC_20260211.docx",
            "组织架构图_CFFC_20260211.docx",
        ],
        [
            "中国基金会发展论坛（英文名称 China Foundation Forum，中文简称基金会论坛，英文简称 CFF）是有志于追求机构卓越、行业发展的社会组织自愿发起的行业平台。",
        ],
    )

    assert names[:3] == ["CFFC", "中国基金会发展论坛", "基金会论坛"]


def test_derive_template_fill_public_domain_falls_back_to_domains_in_local_snippets():
    domain = derive_template_fill_public_domain(
        None,
        [
            "更多信息见 https://www.cfforum.org.cn/about",
            "备用网址 cfforum.org",
        ],
    )

    assert domain == "cfforum.org.cn"


def test_derive_template_fill_public_domain_prefers_domain_in_same_snippet_as_public_name():
    domain = derive_template_fill_public_domain(
        None,
        [
            "南都观察站更多信息见 https://nandu.org.cn/about",
            "中国基金会发展论坛（英文名称 China Foundation Forum，简称基金会论坛，CFF）秘书处邮箱：mishuchu@cfforum.org.cn",
        ],
        public_names=["中国基金会发展论坛", "基金会论坛"],
        client_name="CFFC",
    )

    assert domain == "cfforum.org.cn"


def test_derive_template_fill_public_domain_prefers_org_cn_over_email_only_org_variant():
    domain = derive_template_fill_public_domain(
        None,
        [
            "中国基金会发展论坛秘书处邮箱：mishuchu@cfforum.org",
            "中国基金会发展论坛官网：cfforum.org.cn",
        ],
        public_names=["中国基金会发展论坛", "基金会论坛"],
        client_name="CFFC",
    )

    assert domain == "cfforum.org.cn"


def test_derive_template_fill_public_domain_prefers_org_cn_when_only_org_is_email_sibling():
    domain = derive_template_fill_public_domain(
        None,
        [
            "中国基金会发展论坛秘书处邮箱：mishuchu@cfforum.org",
            "北京基业长青社会组织服务中心邮箱：mishuchu@cfforum.org.cn",
        ],
        public_names=["中国基金会发展论坛", "基金会论坛"],
        client_name="CFFC",
    )

    assert domain == "cfforum.org.cn"


def test_derive_template_fill_public_domain_ignores_generic_meeting_hosts():
    domain = derive_template_fill_public_domain(
        None,
        [
            "中国基金会发展论坛2024年度会议线上地址：https://meeting.dingtalk.com/abc",
            "中国基金会发展论坛官网：cfforum.org.cn",
        ],
        public_names=["中国基金会发展论坛", "基金会论坛"],
        client_name="CFFC",
    )

    assert domain == "cfforum.org.cn"


def test_fetch_template_fill_web_sources_prefers_official_internal_history_pages_for_milestones(monkeypatch):
    homepage_url = "https://cfforum.org.cn"
    history_url = "https://cfforum.org.cn/category/21"
    about_url = "https://cfforum.org.cn/category/20"

    html_map = {
        homepage_url: """
        <html><body>
          <a href="/category/20">关于我们</a>
          <a href="/category/21">大事记</a>
          <a href="/category/26">年度盛会</a>
        </body></html>
        """,
        history_url: "<html><body>2008年，在当时的民政部民间组织管理局指导下发起中国非公募基金会发展论坛。</body></html>",
        about_url: "<html><body>2016年转型为中国基金会发展论坛，2017年秘书处完成注册。</body></html>",
    }

    from app.services import template_fill as template_fill_module

    template_fill_module._fetch_url_html.cache_clear()
    template_fill_module._fetch_url_snippet.cache_clear()
    template_fill_module._search_duckduckgo_html.cache_clear()

    def fake_fetch_url_html(url: str) -> str:
        return html_map.get(url, "")

    monkeypatch.setattr(template_fill_module, "_fetch_url_html", fake_fetch_url_html)
    monkeypatch.setattr(template_fill_module, "_fetch_url_snippet", lambda url: template_fill_module._strip_web_html(fake_fetch_url_html(url))[:900])
    monkeypatch.setattr(template_fill_module, "_search_duckduckgo_html", lambda query: ())

    sources = fetch_template_fill_web_sources(
        client_name="中国基金会发展论坛",
        field_label="2008年重大事件/里程碑",
        template_name="模板.docx",
        client_domain="cfforum.org.cn",
        evidence_titles=["中国基金会发展论坛2023年会项目总结报告.docx"],
        evidence_snippets=["中国基金会发展论坛（简称基金会论坛）是行业平台。"],
        max_items=3,
        field_type="structural_summary",
    )

    urls = [item.url for item in sources]
    assert homepage_url in urls
    assert history_url in urls or about_url in urls
~~~

## `backend/tests/test_topic_capture.py`

- 编码: `utf-8`

~~~python
from pathlib import Path
from datetime import datetime, timedelta
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import topic_capture
from app.services.topic_capture import TopicSearchHit, _candidate_queries, _expand_topic_queries, _extract_prompt_queries, _keyword_tokens, fetch_topic_candidates_from_web
from app.services.topic_source_fetcher import PreferredSourceHit


class DummyAi:
    def suggest_topic_search_queries(self, *, title: str, prompt: str, time_range: str) -> list[str]:
        return ["第一条 近 30 天", "第二条"]

    def shortlist_topic_search_hits(self, *, title: str, prompt: str, hits: list[dict[str, str]], max_items: int = 4) -> list[dict[str, object]]:
        return [{"index": 1}]

    def localize_topic_hit(self, *, title: str, summary: str, radar_title: str, radar_prompt: str) -> dict[str, str]:
        return {"title": title, "summary": summary}


class FakeResponse:
    def __init__(self, text: str = "<rss></rss>"):
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str) -> FakeResponse:
        return FakeResponse()


def test_candidate_queries_strip_time_phrase_and_keep_fallback():
    queries = _candidate_queries(
        title="公益资助",
        prompt="公益资助线索，现金资助或服务购买",
        queries=["公益资助 现金资助 近 30 天", "公益组织 服务购买 项目案例"],
    )
    assert queries[0] == "公益资助 现金资助"
    assert "公益组织 服务购买 项目案例" in queries
    assert "公益资助" in queries


def test_extract_prompt_queries_reads_embedded_suggestions():
    prompt = '重点追踪 GitHub 爆，可优先使用 “GitHub 热门项目 3 天”、“GitHub Trending 新项目 价值分析” 这些搜索表达。'
    queries = _extract_prompt_queries(prompt)
    assert queries == ["GitHub 热门项目 3 天", "GitHub Trending 新项目 价值分析"]


def test_keyword_tokens_keep_concise_terms_and_drop_long_noise():
    tokens = _keyword_tokens(
        "CodeX 开发 我想找到更多与这个 code x 相关的经验分享的内容 "
        "可优先使用 “CodeX 开发板 开源项目”、“CodeX 半成型产品 落地经验” 这些搜索表达。"
    )
    assert "CodeX" in tokens
    assert "开发" in tokens
    assert "开发板" in tokens
    assert not any("经验分享的内容" in token for token in tokens)
    assert not any(len(token) > 12 and any("\u4e00" <= ch <= "\u9fff" for ch in token) for token in tokens)


def test_expand_topic_queries_for_technical_radar_adds_alias_clusters():
    queries = _expand_topic_queries(
        "CodeX 开发",
        "我想找到更多与这个 code x 相关的经验分享内容，最好是落地的一些开源项目和半成型产品。",
    )
    assert "OpenAI Codex 落地案例" in queries
    assert "Codex 开源项目 实战经验" in queries
    assert any("开发工作流" in item for item in queries)


def test_fetch_topic_candidates_tries_later_queries(monkeypatch):
    requested_queries: list[str] = []

    def fake_build_search_urls(*, query: str, time_range: str, preferred_source_urls=None):
        requested_queries.append(query)
        return [("google_news", f"https://example.com/{len(requested_queries)}", query)]

    def fake_parse_rss_hits(xml_text: str, *, provider: str, query: str):
        if query != "第二条":
            return []
        return [
            TopicSearchHit(
                title="第二条命中",
                summary="这是第二条查询词命中的测试内容。",
                source="测试来源",
                source_url="https://example.com/hit",
                published_at=None,
                provider=provider,
                query=query,
            )
        ]

    monkeypatch.setattr(topic_capture, "_build_search_urls", fake_build_search_urls)
    monkeypatch.setattr(topic_capture, "_parse_rss_hits", fake_parse_rss_hits)
    monkeypatch.setattr(topic_capture.httpx, "Client", lambda *args, **kwargs: FakeClient())

    hits = fetch_topic_candidates_from_web(
        DummyAi(),
        radar_title="大模型应用",
        radar_prompt="关注咨询行业的大模型应用实例。",
        time_range="3_days",
    )

    assert requested_queries[:2] == ["第一条", "第二条"]
    assert len(hits) == 1
    assert hits[0].query == "第二条"


def test_fetch_topic_candidates_filters_out_expired_hits(monkeypatch):
    recent_time = (datetime.now().astimezone() - timedelta(days=2)).replace(microsecond=0).isoformat()
    old_time = (datetime.now().astimezone() - timedelta(days=400)).replace(microsecond=0).isoformat()

    def fake_build_search_urls(*, query: str, time_range: str, preferred_source_urls=None):
        return [("google_news", "https://example.com/filter", query)]

    def fake_parse_rss_hits(xml_text: str, *, provider: str, query: str):
        return [
            TopicSearchHit(
                title="超出时间范围的旧新闻",
                summary="这条结果应该被过滤掉。",
                source="测试来源",
                source_url="https://example.com/old",
                published_at=old_time,
                provider=provider,
                query=query,
            ),
            TopicSearchHit(
                title="时间范围内的新新闻",
                summary="这条结果应该被保留下来。",
                source="测试来源",
                source_url="https://example.com/recent",
                published_at=recent_time,
                provider=provider,
                query=query,
            ),
        ]

    monkeypatch.setattr(topic_capture, "_build_search_urls", fake_build_search_urls)
    monkeypatch.setattr(topic_capture, "_parse_rss_hits", fake_parse_rss_hits)
    monkeypatch.setattr(topic_capture.httpx, "Client", lambda *args, **kwargs: FakeClient())

    hits = fetch_topic_candidates_from_web(
        DummyAi(),
        radar_title="公益资助",
        radar_prompt="关注近 30 天内的资助线索。",
        time_range="30_days",
    )

    assert len(hits) == 1
    assert hits[0].title == "时间范围内的新新闻"


def test_fetch_topic_candidates_includes_preferred_source_hits(monkeypatch):
    monkeypatch.setattr(
        topic_capture,
        "fetch_preferred_source_hits",
        lambda preferred_source_urls, max_items=8: [
            PreferredSourceHit(
                title="优先网址直抓命中",
                summary="这条结果来自配置站点的列表页。",
                source="中国发展简报",
                source_url="https://www.chinadevelopmentbrief.org.cn/abutment/detail/16463.html",
                published_at="2026-03-19T00:00:00",
                provider="preferred_source:list",
            )
        ],
    )
    monkeypatch.setattr(topic_capture, "_build_search_urls", lambda **kwargs: [])
    monkeypatch.setattr(topic_capture.httpx, "Client", lambda *args, **kwargs: FakeClient())

    hits = fetch_topic_candidates_from_web(
        DummyAi(),
        radar_title="公益资助",
        radar_prompt="关注公益资助与活动招募。",
        time_range="30_days",
        preferred_source_urls=["https://www.chinadevelopmentbrief.org.cn/abutment/index.html"],
    )

    assert len(hits) == 1
    assert hits[0].provider == "preferred_source:list"
    assert hits[0].title == "优先网址直抓命中"
~~~

## `backend/tests/test_topic_source_fetcher.py`

- 编码: `utf-8`

~~~python
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import topic_source_fetcher
from app.services.topic_source_fetcher import fetch_preferred_source_hits


class FakeResponse:
    def __init__(self, text: str, *, content_type: str = "text/html; charset=utf-8"):
        self.text = text
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str):
        response = self.responses.get(url)
        if response is None:
            raise RuntimeError(f"unexpected url: {url}")
        return response


def test_fetch_preferred_source_hits_discovers_feed(monkeypatch):
    html = """
    <html>
      <head>
        <link rel="alternate" type="application/rss+xml" href="/feed.xml" />
      </head>
    </html>
    """
    feed = """
    <rss version="2.0">
      <channel>
        <title>测试站点</title>
        <item>
          <title>第一条更新</title>
          <link>https://example.com/posts/1</link>
          <description>这是一条来自 RSS 的摘要。</description>
          <pubDate>Fri, 14 Mar 2026 05:24:25 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    responses = {
        "https://example.com/": FakeResponse(html),
        "https://example.com/feed.xml": FakeResponse(feed, content_type="application/rss+xml"),
    }
    monkeypatch.setattr(topic_source_fetcher.httpx, "Client", lambda *args, **kwargs: FakeClient(responses))

    hits = fetch_preferred_source_hits(["https://example.com/"])

    assert len(hits) == 1
    assert hits[0].provider == "preferred_source:rss"
    assert hits[0].source == "测试站点"
    assert hits[0].source_url == "https://example.com/posts/1"
    assert hits[0].published_at is not None


def test_fetch_preferred_source_hits_parses_list_page_details(monkeypatch):
    list_html = """
    <html>
      <body>
        <a href="/abutment/detail/16463.html">基金会秘书长：这里有三个好项目，CFF喊你来！</a>
        <a href="/abutment/detail/16461.html">报名 | 调查报告发布会期待您的到来</a>
      </body>
    </html>
    """
    detail_one = """
    <html>
      <head>
        <title>基金会秘书长：这里有三个好项目，CFF喊你来！</title>
        <meta name="description" content="这是一条从详情页提取的摘要。" />
      </head>
      <body>
        <div class="source">来源：<span>基金会论坛</span></div>
        <div class="time pub-flex-align"><span>2026-03-19</span></div>
      </body>
    </html>
    """
    detail_two = """
    <html>
      <head>
        <title>报名 | 调查报告发布会期待您的到来</title>
        <meta name="description" content="第二条详情摘要。" />
      </head>
      <body>
        <div class="source">来源：<span>中国发展简报</span></div>
        <div class="time pub-flex-align"><span>2026-03-13</span></div>
      </body>
    </html>
    """
    responses = {
        "https://www.chinadevelopmentbrief.org.cn/abutment/index.html": FakeResponse(list_html),
        "https://www.chinadevelopmentbrief.org.cn/abutment/detail/16463.html": FakeResponse(detail_one),
        "https://www.chinadevelopmentbrief.org.cn/abutment/detail/16461.html": FakeResponse(detail_two),
    }
    monkeypatch.setattr(topic_source_fetcher.httpx, "Client", lambda *args, **kwargs: FakeClient(responses))

    hits = fetch_preferred_source_hits(["https://www.chinadevelopmentbrief.org.cn/abutment/index.html"])

    assert len(hits) == 2
    assert all(hit.provider == "preferred_source:list" for hit in hits)
    assert hits[0].source_url == "https://www.chinadevelopmentbrief.org.cn/abutment/detail/16463.html"
    assert hits[0].summary == "这是一条从详情页提取的摘要。"
    assert hits[0].source == "基金会论坛"
    assert hits[0].published_at is not None
~~~

## `backend/tests/test_understanding_basic.py`

- 编码: `utf-8`

~~~python
"""
测试 basic 模式构建器：
- 只有最小输入时也能得到 basic 结果
- 结果中必须包含 4 个主输出
- 不会生成假精细的建议字段
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    OrganizationDnaModuleRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
    TaskProjectContextRecord,
)
from app.services.understanding_builder import build_understanding_basic


def _make_snapshot(**overrides) -> WeeklyReviewTaskSnapshotRecord:
    defaults = {
        "title": "和冯梅老师沟通CFFC的战略说明迭代",
        "status": "doing",
        "createdAt": "2026-03-20T10:00:00Z",
        "listName": "战略合作",
        "listColor": "#5B7BFE",
        "ownerName": "顾源源",
        "eventLineId": "",
        "eventLineName": "",
    }
    defaults.update(overrides)
    return WeeklyReviewTaskSnapshotRecord(**defaults)


def _make_entry(snapshot=None, note="", reflection="") -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id="entry_001",
        reviewId="review_001",
        taskId="task_001",
        weekLabel="2026-W13",
        contentDomain="work",
        note=note,
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(reflection=reflection),
        taskSnapshot=snapshot or _make_snapshot(),
    )


def _make_org_dna() -> list[OrganizationDnaModuleRecord]:
    return [
        OrganizationDnaModuleRecord(
            moduleKey="organization_intro",
            title="组织介绍",
            markdownContent="益语智库是一家专注于公益行业的咨询公司",
            normalizedText="益语智库是一家专注于公益行业的咨询公司，为基金会和公益组织提供战略咨询、数字化转型和研究服务。",
            summary="益语智库是公益行业咨询公司，提供战略咨询和数字化转型服务。",
        ),
    ]


class TestBasicModeMinimalInput:
    """只有最小输入时也能得到 basic 结果。"""

    def test_minimal_input_produces_result(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert result is not None
        assert result.mode == "basic"

    def test_four_main_outputs_always_present(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert result.whatIsThis, "whatIsThis must not be empty"
        assert result.whyItMatters, "whyItMatters must not be empty"
        assert result.progressNow, "progressNow must not be empty"
        assert result.unknowns, "unknowns must not be empty"

    def test_no_false_advice_in_basic(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert result.optionalAdvice is None, "basic mode should not produce optional advice"

    def test_with_org_dna_improves_coverage(self):
        entry = _make_entry()
        result_no_dna = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        result_with_dna = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        assert result_with_dna.coverage > result_no_dna.coverage

    def test_with_client_background(self):
        pc = TaskProjectContextRecord(
            clientId="client_cffc",
            clientName="CFFC",
            backgroundSummary="CFFC是公益行业的重要枢纽组织",
            goalSummary="推进数字化转型合作",
            riskSummary="决策链较长",
        )
        snapshot = _make_snapshot(projectContext=pc)
        entry = _make_entry(snapshot=snapshot)
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        assert "CFFC" in result.whatIsThis or "CFFC" in result.whyItMatters
        assert result.coverage >= 50

    def test_with_review_note(self):
        entry = _make_entry(note="本周和冯梅老师确认了工作坊方向，下周准备正式提案。")
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert "复盘" in result.progressNow or "冯梅" in result.progressNow or "说明" in result.progressNow

    def test_never_returns_cannot_judge(self):
        """即使输入几乎为空，也不能返回"无法判断"。"""
        snapshot = _make_snapshot(title="测试任务", desc="")
        entry = _make_entry(snapshot=snapshot)
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        assert "无法判断" not in result.whatIsThis
        assert "无法判断" not in result.whyItMatters
        assert result.whatIsThis  # 不为空

    def test_known_facts_populated(self):
        entry = _make_entry(note="已完成初步沟通")
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        assert len(result.knownFacts) >= 2

    def test_source_breakdown_complete(self):
        entry = _make_entry()
        result = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=[])
        source_types = {s.sourceType for s in result.sourceBreakdown}
        assert "org_dna" in source_types
        assert "client_background" in source_types
        assert "task_title" in source_types
        assert "review_note" in source_types


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
~~~

## `backend/tests/test_understanding_enhanced.py`

- 编码: `utf-8`

~~~python
"""
测试 enhanced 模式构建器：
- 有事件线 + 会议时，结果升级为 enhanced
- optionalAdvice 只在证据足够时才出现
- 无增强项时降级回 basic
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    OrganizationDnaModuleRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
    TaskProjectContextRecord,
)
from app.services.understanding_builder import build_understanding_enhanced, build_understanding_basic


def _make_snapshot(**overrides) -> WeeklyReviewTaskSnapshotRecord:
    defaults = {
        "title": "和冯梅老师沟通CFFC的战略说明迭代",
        "status": "doing",
        "createdAt": "2026-03-20T10:00:00Z",
        "listName": "战略合作",
        "listColor": "#5B7BFE",
        "ownerName": "顾源源",
        "projectContext": TaskProjectContextRecord(
            clientId="client_cffc",
            clientName="CFFC",
            backgroundSummary="CFFC是公益行业的重要枢纽组织，连接300+基金会",
            goalSummary="推进数字化转型合作",
            riskSummary="决策链较长",
        ),
    }
    defaults.update(overrides)
    return WeeklyReviewTaskSnapshotRecord(**defaults)


def _make_entry(snapshot=None, note="", reflection="") -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id="entry_001",
        reviewId="review_001",
        taskId="task_001",
        weekLabel="2026-W13",
        contentDomain="work",
        note=note,
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(reflection=reflection),
        taskSnapshot=snapshot or _make_snapshot(),
    )


def _make_org_dna() -> list[OrganizationDnaModuleRecord]:
    return [
        OrganizationDnaModuleRecord(
            moduleKey="organization_intro",
            title="组织介绍",
            markdownContent="",
            normalizedText="益语智库是公益行业咨询公司",
            summary="益语智库是公益行业咨询公司，提供战略咨询和数字化转型服务。",
        ),
    ]


class TestEnhancedMode:

    def test_no_enhancement_falls_back_to_basic(self):
        entry = _make_entry()
        result = build_understanding_enhanced(
            ai=None, task_entry=entry, org_dna_modules=_make_org_dna(),
        )
        # 没有增强项时应该降级
        assert result.mode in ("basic", "enhanced")
        assert result.whatIsThis
        assert result.whyItMatters

    def test_with_event_line_becomes_enhanced(self):
        entry = _make_entry(note="本周确认了工作坊形式")
        result = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="CFFC 战略合作线",
            event_line_stage="方案落地",
            event_line_summary="益语与CFFC的数字化战略合作",
        )
        assert result.mode == "enhanced"
        assert result.whatIsThis
        # enhanced 源中应该有事件线
        source_types = {s.sourceType for s in result.sourceBreakdown}
        assert "event_line_memory" in source_types

    def test_enhanced_has_more_available_sources(self):
        entry = _make_entry(note="初步沟通完成")
        basic = build_understanding_basic(ai=None, task_entry=entry, org_dna_modules=_make_org_dna())
        enhanced = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="CFFC 合作线",
            meetings=[{"title": "CFFC 初次沟通", "summary": "确认了AI合作方向"}],
        )
        basic_available = sum(1 for s in basic.sourceBreakdown if s.available)
        enhanced_available = sum(1 for s in enhanced.sourceBreakdown if s.available)
        assert enhanced_available > basic_available

    def test_no_false_advice_without_llm(self):
        """LLM 不可用时，enhanced 也不应该硬造 optionalAdvice。"""
        entry = _make_entry()
        result = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="CFFC 合作线",
        )
        assert result.optionalAdvice is None

    def test_four_main_outputs_always_present_in_enhanced(self):
        entry = _make_entry()
        result = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="CFFC 合作线",
            event_line_history=[
                {"weekLabel": "2026-W12", "stage": "方向确认", "taskCount": 2, "completedCount": 1},
            ],
        )
        assert result.whatIsThis
        assert result.whyItMatters
        assert result.progressNow
        assert result.unknowns

    def test_source_breakdown_includes_enhancement_items(self):
        entry = _make_entry()
        result = build_understanding_enhanced(
            ai=None,
            task_entry=entry,
            org_dna_modules=_make_org_dna(),
            event_line_name="线",
            meetings=[{"title": "会", "summary": "内容"}],
            support_requests=[{"title": "求", "summary": "帮助", "status": "open"}],
        )
        source_types = {s.sourceType for s in result.sourceBreakdown}
        assert "event_line_memory" in source_types
        assert "meeting" in source_types
        assert "support_request" in source_types


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
~~~

## `backend/tests/test_weekly_overview_lines.py`

- 编码: `utf-8`

~~~python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    OrganizationDnaModuleRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.review_narrative import _build_weekly_line_cards


def _make_snapshot(**overrides) -> WeeklyReviewTaskSnapshotRecord:
    defaults = {
        "title": "测试任务",
        "status": "doing",
        "createdAt": "2026-03-25T10:00:00Z",
        "listName": "任务清单",
        "listColor": "#5B7BFE",
        "ownerName": "顾源源",
        "clientName": "",
        "eventLineId": "",
        "eventLineName": "",
        "desc": "",
        "note": "",
        "evidenceCount": 0,
    }
    defaults.update(overrides)
    return WeeklyReviewTaskSnapshotRecord(**defaults)


def _make_entry(task_id: str, snapshot: WeeklyReviewTaskSnapshotRecord, note: str = "") -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id=f"entry_{task_id}",
        reviewId="review_w13",
        taskId=task_id,
        weekLabel="2026-W13",
        contentDomain="work",
        note=note,
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(),
        taskSnapshot=snapshot,
    )


def test_debug_tasks_group_into_software_line():
    items = [
        _make_entry("task_1", _make_snapshot(title="codex-attachment-save-debug", desc="排查附件保存链路")),
        _make_entry("task_2", _make_snapshot(title="CODEx新建任务可见性排查", desc="验证任务可见性问题")),
    ]
    cards = _build_weekly_line_cards(items, [], [])
    line_names = [card.line_name for card in cards]
    assert "软件底层修复与验证线" in line_names


def test_cffc_line_uses_client_background_for_importance():
    org_modules = [
        OrganizationDnaModuleRecord(
            moduleKey="organization_intro",
            title="组织介绍",
            markdownContent="",
            normalizedText="益语智库是一家咨询公司",
            summary="益语智库是一家咨询公司。",
        ),
        OrganizationDnaModuleRecord(
            moduleKey="business_intro",
            title="CFFC 业务背景",
            markdownContent="",
            normalizedText="CFFC是公益行业的重要枢纽组织，连接大量基金会，具备很强的行业影响力。",
            summary="CFFC是公益行业的重要枢纽组织，连接大量基金会，具备很强的行业影响力。",
        ),
    ]
    items = [
        _make_entry(
            "task_cffc_1",
            _make_snapshot(
                title="和冯梅老师沟通CFFC的战略说明迭代",
                clientName="CFFC",
                eventLineId="el_cffc",
                eventLineName="洪峰讨论赋能合作",
                desc="推进合作说明迭代",
            ),
        )
    ]
    cards = _build_weekly_line_cards(items, org_modules, [])
    assert cards
    cffc_card = cards[0]
    assert "CFFC" in cffc_card.line_name
    assert "枢纽" in cffc_card.why_it_matters or "基金会" in cffc_card.why_it_matters
~~~

## `backend/tests/test_workspace_analysis_first.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse, JudgmentVersionRecord
from app.services.ai import AiInvocationError
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "analysis-first 测试客户") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "用于 analysis-first 回归测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_approved_judgment(
    client: TestClient,
    *,
    client_id: str,
    judgment_id: str = "judgment_analysis_first_approved",
    topic: str = "客户主判断",
    summary: str = "当前主线已经从资料整理转向协同推进，正式判断较稳定。",
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence,
            created_at, updated_at, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by
        )
        VALUES(
            ?, ?, 'client', ?, ?, 1, 'approved', ?, '[]', NULL, 'medium', 'high',
            '2026-04-18T10:00:00', '2026-04-18T10:00:00', 'analysis', 'approved', 'reviewed',
            NULL, 'snapshot_analysis_first', NULL, NULL
        )
        """,
        (
            judgment_id,
            client_id,
            client_id,
            topic,
            summary,
        ),
    )


def insert_candidate_judgment(
    client: TestClient,
    *,
    client_id: str,
    judgment_id: str = "judgment_analysis_first_candidate",
    topic: str = "客户候选判断",
    summary: str = "当前更接近待确认判断，仍需继续补证据。",
    evidence_ids: list[str] | None = None,
    context_pack_id: str | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence,
            created_at, updated_at, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by
        )
        VALUES(
            ?, ?, 'client', ?, ?, 1, 'awaiting_review', ?, ?, ?, 'medium', 'medium',
            '2026-04-18T11:00:00', '2026-04-18T11:00:00', 'analysis', 'candidate', 'normalized',
            NULL, 'snapshot_analysis_first_candidate', NULL, NULL
        )
        """,
        (
            judgment_id,
            client_id,
            client_id,
            topic,
            summary,
            json.dumps(evidence_ids or [], ensure_ascii=False),
            context_pack_id,
        ),
    )


def create_scoped_task(client: TestClient, *, client_id: str, title: str, desc: str = "") -> str:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": desc,
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_evidence_card(
    client: TestClient,
    *,
    evidence_id: str,
    client_id: str,
    source_type: str,
    source_id: str,
    source_ref: str,
    normalized_claim: str,
    time_anchor: str = "2026-04-18T09:00:00",
    review_state: str = "awaiting_review",
    confidence: float = 0.72,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO evidence_cards(
            id, client_id, scope_type, scope_id, source_type, source_id, source_ref, quote, normalized_claim,
            confidence, time_anchor, review_state, fingerprint, normalized_claim_hash, source_ref_hash,
            evidence_fingerprint, created_at, updated_at
        )
        VALUES(?, ?, 'client', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-04-18T09:00:00', '2026-04-18T09:00:00')
        """,
        (
            evidence_id,
            client_id,
            client_id,
            source_type,
            source_id,
            source_ref,
            normalized_claim,
            normalized_claim,
            confidence,
            time_anchor,
            review_state,
            f"fingerprint::{evidence_id}",
            f"claim_hash::{evidence_id}",
            f"source_ref_hash::{evidence_id}",
            f"evidence_fingerprint::{evidence_id}",
        ),
    )


def insert_conflict_group(
    client: TestClient,
    *,
    conflict_id: str,
    client_id: str,
    title: str,
    summary: str,
    evidence_ids: list[str] | None = None,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO conflict_groups(
            id, client_id, scope_type, scope_id, conflict_type, title, summary, evidence_ids_json,
            unresolved_question_ids_json, resolution_status, severity, context_pack_id, created_at, updated_at
        )
        VALUES(?, ?, 'client', ?, 'judgment_conflict', ?, ?, ?, '[]', 'draft', 'medium', NULL, '2026-04-18T11:10:00', '2026-04-18T11:10:00')
        """,
        (
            conflict_id,
            client_id,
            client_id,
            title,
            summary,
            json.dumps(evidence_ids or [], ensure_ascii=False),
        ),
    )


def insert_client_dna_document(
    client: TestClient,
    *,
    client_id: str,
    module_key: str,
    title: str,
    summary: str,
    normalized_text: str,
    updated_at: str,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO client_dna_documents(
            client_id, module_key, title, markdown_content, normalized_text, summary, file_name, content_hash,
            source_kind, missing_info_json, updated_at, updated_by
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'manual', '[]', ?, 'pytest')
        ON CONFLICT(client_id, module_key) DO UPDATE SET
            title = excluded.title,
            markdown_content = excluded.markdown_content,
            normalized_text = excluded.normalized_text,
            summary = excluded.summary,
            file_name = excluded.file_name,
            content_hash = excluded.content_hash,
            source_kind = excluded.source_kind,
            missing_info_json = excluded.missing_info_json,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (
            client_id,
            module_key,
            title,
            normalized_text,
            normalized_text,
            summary,
            f"{module_key}.md",
            f"hash::{module_key}",
            updated_at,
        ),
    )


def insert_runtime_run_log(
    client: TestClient,
    *,
    run_id: str,
    client_id: str,
    summary: str,
    detail: dict[str, object],
    created_at: str = "2026-04-18T10:20:00",
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO runtime_run_logs(
            id, client_id, job_id, provider, model, lane, cache_hit, degraded, document_count, evidence_count,
            conflict_count, context_time_range, prompt_version, schema_version, summary, detail_json, created_at
        )
        VALUES(?, ?, NULL, 'analysis-center', 'analysis-center-v0.3.3', 'cloud_final', 0, 0, 0, 0, 0, NULL, 'analysis-center-v0.3.3', 'analysis-center-v0.3.3', ?, ?, ?)
        """,
        (run_id, client_id, summary, json.dumps(detail, ensure_ascii=False), created_at),
    )


def test_workspace_chat_prefers_state_pool_before_document_retrieval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="客户状态优先测试")
    insert_approved_judgment(client, client_id=client_id, topic="双年会推进判断", summary="双年会筹备已经进入协同推进阶段，重点在发言、行程和资料对齐。")
    create_scoped_task(
        client,
        client_id=client_id,
        title="推进双年会筹备",
        desc="本周继续确认发言、行程安排和会前资料对齐。",
    )

    captured: dict[str, str] = {}

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("analysis-first state-only query should not trigger document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        captured["context_summary"] = state_context_summary
        return AiStructuredResponse(
            content="正式判断和本周动作已经基于状态池整理完成。",
            judgment="当前正式判断较稳定，但仍需把风险与缺失信息单独陈述。",
            analysis="本周主线集中在双年会筹备推进。",
            actions="继续确认负责人、时间点和资料清单。",
            timeline="本周内完成关键对齐。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户本周在推进什么？当前有什么风险？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "state_only"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "state_first_default"
    assert payload["retrievalSummary"]["retrievalStage"] == "state_pool"
    assert payload["retrievalDecisionReason"] == "state_first_default"
    assert payload["stateConfidence"] == "high"
    assert "judgment" in payload["stateSources"]
    assert "task" in payload["stateSources"]
    assert payload["stateAnswerSections"]["official"]
    assert payload["stateAnswerSections"]["actions"]
    assert payload["stateSourceSummary"]["judgments"] >= 1
    assert payload["stateSourceSummary"]["tasks"] >= 1
    assert payload["retrievalSummary"]["state_first_hit_rate"] == 1
    assert payload["retrievalSummary"]["state_only_fallback_rate"] == 1
    assert payload["retrievalSummary"]["candidate_leakage_count"] == 0
    assert payload["evidence"] == []

    context_summary = captured["context_summary"]
    assert "客户状态池（analysis-first" in context_summary
    assert "[正式判断]" in context_summary
    assert "[本周动作]" in context_summary


def test_workspace_chat_state_only_ai_failure_still_returns_nonfatal_state_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="state-only 失败回退测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        topic="正式推进判断",
        summary="当前主线是继续收束客户状态，并把下一步动作明确到任务层。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进状态收口",
        desc="本周继续确认 blockers、recent decision 与 next step。",
    )

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("state-first query should not trigger document retrieval when state pool is enough")

    def fail_workspace_state_generation(prompt: str, state_context_summary: str, *, on_partial=None):
        raise AiInvocationError("qwen", "mock timeout during compact state generation")

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fail_workspace_state_generation)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "接下来最重要的事情是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "state_only"
    assert payload["fallbackPresentationMode"] == "state_cards_only"
    assert payload["stateAnswerSections"]["official"]
    assert payload["stateAnswerSections"]["actions"]
    assert payload["retrievalSummary"]["generationFailureDetail"] == "mock timeout during compact state generation"
    assert payload["content"]
    assert "围绕“接下来最重要的事情是什么？”" in payload["content"]
    assert "最值得继续推进的是：" in payload["content"]
    assert "一、正式判断" not in payload["content"]
    assert payload["evidence"] == []


def test_workspace_chat_registry_only_judgment_queries_stay_on_state_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="registry-only judgment 测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_registry_only",
        topic="已登记正式判断",
        summary="当前系统内已经批准的正式判断应直接来自 approved registry。",
    )

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("registry-only judgment query should not trigger document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="当前优先展示已登记的正式判断。",
            judgment="当前系统内已批准的正式判断来自 approved registry。",
            analysis="registry-only 查询不需要回钻文件。",
            actions="如需依据，请改问原文或资料支撑。",
            timeline="当前可直接返回。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "系统里已批准的正式判断有哪些？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["judgmentQueryMode"] == "registry_only"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "state_first_default"
    assert payload["failureReason"] == "state_only"
    assert payload["stateAnswerSections"]["official"]
    assert payload["evidence"] == []


def test_workspace_chat_intro_queries_force_evidence_retrieval_even_with_strong_state_pool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="介绍问题证据优先测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_intro_profile",
        topic="正式推进判断",
        summary="当前主线仍是战略陪伴与协同推进。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进战略陪伴",
        desc="本周持续收束会前资料和后续安排。",
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_intro_profile_1', ?, NULL, '日慈基金会机构介绍', '/tmp/richi-intro.md', 'md', 'file', '日慈基金会聚焦公益项目支持、行业协同与长期能力建设。', '[]', '2026-04-18T10:00:00')
        """,
        (client_id,),
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_intro_profile_1', ?, NULL, 'doc_intro_profile_1', 'kd_intro_profile_1_uid', '/tmp/richi-intro.md', '/tmp/richi-intro.md', NULL,
            '组织与战略', NULL, NULL, 0.0, NULL, 'md',
            '组织与战略', '机构介绍', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_intro_profile_1', 'normalized_intro_profile_1', '2026-04-18T10:00:00', '2026-04-18T10:00:00'
        )
        """,
        (client_id,),
    )

    calls = {"retrieval": 0, "state": 0}

    def fake_retrieval_bundle(client_id_arg: str, prompt: str):
        calls["retrieval"] += 1
        assert client_id_arg == client_id
        assert "介绍" in prompt
        return RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_intro_profile_1",
                    chunk_id="chunk_intro_profile_1",
                    title="日慈基金会机构介绍",
                    excerpt="日慈基金会聚焦公益项目支持、行业协同与长期能力建设，当前正在完善项目推进和对外沟通材料。",
                    score=0.93,
                    coverage=0.82,
                    section_label="机构介绍",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["介绍", "机构"],
                    path="/tmp/richi-intro.md",
                )
            ],
            coverage=0.82,
            retrieval_summary={
                "masterHitCount": 1,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 1,
                "preferredCategories": ["组织与战略"],
                "categoryCoverage": ["组织与战略"],
            },
            context_text="",
            matched_terms=["介绍", "机构"],
            failure_reason=None,
        )

    def fail_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        calls["state"] += 1
        raise AssertionError("intro/profile queries should not stay on the state-only path")

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        assert "原始证据包（可用于正式判断）：" in context_summary
        assert "日慈基金会机构介绍" in context_summary
        return AiStructuredResponse(
            content="日慈基金会是一家围绕公益项目支持与行业协同展开工作的机构，当前重点是把项目推进和对外沟通材料收得更清楚。",
            judgment="这是一条基于机构介绍原文整理出的基础介绍，不是单纯状态池回显。",
            analysis="介绍类问题应优先落到机构介绍和项目资料，而不是直接套状态面板。",
            actions="如需继续细化，可下钻到项目介绍、团队介绍和会议纪要。",
            timeline="补齐更多组织资料后可以扩成更完整的客户画像。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda db, data_dir, client_id_arg, prompt: fake_retrieval_bundle(client_id_arg, prompt))
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fail_workspace_state_response)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍日慈基金会"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert calls["retrieval"] == 1
    assert calls["state"] == 0
    assert payload["answerMode"] == "grounded_answer"
    assert payload["retrievalSummary"]["retrievalDeferred"] is False
    assert payload["retrievalDecisionReason"] == "intro_query_needs_evidence"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "intro_query_needs_evidence"
    assert payload["evidence"]
    assert payload["failureReason"] is None


def test_workspace_chat_routes_default_judgment_questions_to_hybrid_linked_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="hybrid judgment 默认路由测试")
    insert_evidence_card(
        client,
        evidence_id="evidence_hybrid_candidate",
        client_id=client_id,
        source_type="analysis_note",
        source_id="candidate_hybrid_judgment",
        source_ref="候选判断证据",
        normalized_claim="会议与任务信号共同表明，当前仍停留在待确认判断阶段。",
    )
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="candidate_hybrid_judgment",
        topic="客户候选判断",
        summary="当前更接近待确认判断：需要先把会议与任务信号收束，再决定是否进入正式层。",
        evidence_ids=["evidence_hybrid_candidate"],
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="收束候选判断",
        desc="下一步先核对会议纪要和任务推进，再决定是否生成 judgment proposal。",
    )

    captured: dict[str, str] = {}

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("default judgment hybrid query should prefer linked evidence instead of generic retrieval")

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        captured["context_summary"] = context_summary
        return AiStructuredResponse(
            content="当前先给出已登记判断和待确认判断。",
            judgment="当前系统内已批准的正式判断仍为空。",
            analysis="但基于状态对象和关联证据，已经可以形成待确认判断。",
            actions="继续围绕候选判断补证据。",
            timeline="补齐后再进入 proposal/approval 流程。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在有哪些正式判断？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["judgmentQueryMode"] == "hybrid"
    assert payload["answerIntent"] == "official_judgment_registry"
    assert payload["evidenceSupportMode"] == "evidence_cards"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "official_registry_requested"
    assert payload["retrievalSummary"]["retrievalStage"] == "hybrid_linked_evidence"
    assert payload["failureReason"] is None
    assert payload["stateAnswerSections"]["official"] == []
    assert payload["stateAnswerSections"]["candidate"]
    assert payload["stateAnswerSections"]["evidenceSupport"]
    assert payload["stateAnswerSections"]["unknowns"]
    assert payload["evidence"]
    assert payload["evidence"][0]["retrievalStage"] == "surrogate"
    assert "[待确认判断 / 判断草稿]" in captured["context_summary"]
    assert "[支撑证据摘要]" in captured["context_summary"]


def test_workspace_chat_hybrid_fallback_uses_state_cards_only_presentation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="hybrid judgment fallback 测试")
    insert_evidence_card(
        client,
        evidence_id="evidence_hybrid_fallback_candidate",
        client_id=client_id,
        source_type="analysis_note",
        source_id="candidate_hybrid_fallback_judgment",
        source_ref="候选判断证据",
        normalized_claim="当前还没有 approved judgment，但会议与任务已经形成待确认判断。",
    )
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="candidate_hybrid_fallback_judgment",
        topic="客户候选判断",
        summary="当前仍停留在待确认判断阶段。",
        evidence_ids=["evidence_hybrid_fallback_candidate"],
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续补判断证据",
        desc="需要再核对会议与任务上下文。",
    )

    def raise_timeout(*args, **kwargs):
        raise AiInvocationError("doubao", "读取超时：The read operation timed out")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", raise_timeout)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在有哪些正式判断？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "llm_local_fallback_after_retry"
    assert payload["judgmentQueryMode"] == "hybrid"
    assert payload["fallbackPresentationMode"] == "state_cards_only"
    assert payload["stateAnswerSections"]["official"] == []
    assert payload["stateAnswerSections"]["candidate"]
    assert "analysis-first" not in payload["content"]
    assert "当前最值得抓住的原始观察包括" not in payload["content"]


def test_workspace_chat_queues_fact_extraction_after_main_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="后台记忆提取调度测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_fact_extract_schedule",
        topic="正式推进判断",
        summary="主回答已经足够可用时，记忆提取应退到后台。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进状态回答",
        desc="确保主回答不等待记忆提取。",
    )

    scheduled: dict[str, object] = {}

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="结构化状态回答已生成。",
            judgment="正式判断已经可直接返回。",
            analysis="记忆提取应改为后台执行。",
            actions="继续按状态池推进。",
            timeline="本周内完成。",
        )

    def fake_schedule(state, **kwargs):
        scheduled.update(kwargs)

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)
    monkeypatch.setattr(app_main, "_schedule_chat_fact_extraction", fake_schedule)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "接下来最重要的事情是什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "state_only"
    assert scheduled["client_id"] == client_id
    assert scheduled["thread_id"] == payload["threadId"]
    assert scheduled["user_prompt"] == "接下来最重要的事情是什么？"
    assert "结构化状态回答已生成。" in str(scheduled["assistant_content"])
    assert scheduled["answer_mode"] == "grounded_fallback"


def test_workspace_chat_ignores_fact_extraction_queue_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="后台记忆提取失败隔离测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_fact_extract_nonfatal",
        topic="正式推进判断",
        summary="即使后台记忆提取调度失败，主回答也不能失败。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="保持主回答成功",
        desc="后台任务失败不应影响 state-first 回答。",
    )

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="状态回答已经可用。",
            judgment="主回答不依赖后台记忆提取。",
            analysis="调度失败也只能记录日志。",
            actions="继续围绕状态池给出主回答。",
            timeline="本周内完成。",
        )

    def fail_schedule(*args, **kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)
    monkeypatch.setattr(app_main, "_schedule_chat_fact_extraction", fail_schedule)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户最近在推进什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["failureReason"] == "state_only"
    assert payload["stateAnswerSections"]["official"]


@pytest.mark.parametrize(
    "prompt",
    [
        "现在最值得关注的事项是什么？",
        "接下来最重要的下一步是什么？",
        "目前最大的阻塞点是什么？",
    ],
)
def test_workspace_chat_routes_common_state_questions_to_state_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prompt: str):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="状态问题覆盖测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_state_question_coverage",
        topic="当前推进判断",
        summary="当前主线是先明确下一步动作，再收束待确认判断和阻塞点。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="明确下一步动作",
        desc="本周要把当前最重要的事项和最大阻塞点整理清楚。",
    )

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("common state questions should stay on the state-first path")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="结构化状态回答已经生成。",
            judgment="正式判断仍然只来自 judgment bundle。",
            analysis="最重要事项、下一步和阻塞点都应先走状态池。",
            actions="继续按状态池收束任务与判断。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": prompt},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["retrievalDecisionReason"] == "state_first_default"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["failureReason"] == "state_only"
    assert payload["answerMode"] == "grounded_fallback"
    assert payload["evidence"] == []


def test_workspace_chat_official_section_ignores_compat_latest_judgments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="compat judgment 不得污染正式回答")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_bundle_source",
        topic="正式 bundle 判断",
        summary="正式判断来自 judgment bundle，不应被 compat judgment 覆盖。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进判断收口",
        desc="把正式判断和本周动作整理为统一状态回答。",
    )

    compat_judgment = JudgmentVersionRecord(
        id="judgment_compat_source",
        clientId=client_id,
        targetType="client",
        targetId=client_id,
        topic="compat judgment",
        status="approved",
        originType="analysis",
        authorityLevel="approved",
        qualityTier="reviewed",
        summary="这条 compat judgment 不应进入正式判断段。",
        createdAt="2026-04-18T10:30:00",
        updatedAt="2026-04-18T10:30:00",
    )
    real_get_bundle = app_main.get_client_analysis_bundle

    def fake_get_bundle(db, workspace_seed):
        bundle = real_get_bundle(db, workspace_seed)
        bundle.latest_judgments = [compat_judgment]
        return bundle

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("state-first query should not fall back to document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="正式判断仍来自 judgment bundle。",
            judgment="compat judgment 不能进入正式判断段。",
            analysis="状态回答需要保持 judgment 边界干净。",
            actions="继续按照 bundle 判断推进。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "get_client_analysis_bundle", fake_get_bundle)
    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户最近在推进什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    official_text = "\n".join(payload["stateAnswerSections"]["official"])
    assert "正式判断来自 judgment bundle" in official_text
    assert "compat judgment 不应进入正式判断段" not in official_text
    assert payload["retrievalSummary"]["candidate_leakage_count"] == 0


def test_workspace_chat_filters_attachment_ingest_boilerplate_from_candidate_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="candidate 污染过滤测试")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_clean_approved",
        topic="正式推进判断",
        summary="当前可以先围绕客户状态池回答推进问题。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进状态池问答",
        desc="保持正式判断与候选判断边界。",
    )

    polluted_candidate = JudgmentVersionRecord(
        id="judgment_polluted_candidate",
        clientId=client_id,
        targetType="client",
        targetId=client_id,
        topic="client_overview",
        status="awaiting_review",
        originType="analysis",
        authorityLevel="candidate",
        qualityTier="normalized",
        summary="client_overview：b1854d964465d43d.jpeg 已作为任务附件进入项目资料库，可用于后续检索、问答与事件线证据引用。",
        createdAt="2026-04-18T11:00:00",
        updatedAt="2026-04-18T11:00:00",
    )
    real_get_bundle = app_main.get_client_analysis_bundle

    def fake_get_bundle(db, workspace_seed):
        bundle = real_get_bundle(db, workspace_seed)
        if bundle.judgment_bundle:
            bundle.judgment_bundle.overlayDeltas = [*bundle.judgment_bundle.overlayDeltas, polluted_candidate]
        return bundle

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("state-first query should not fall back to document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="当前候选判断已经过滤导入噪音。",
            judgment="正式判断保持干净。",
            analysis="导入 boilerplate 不应进入 candidate judgment。",
            actions="继续围绕真实 judgment、任务和会议回答。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "get_client_analysis_bundle", fake_get_bundle)
    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "最近有什么变化？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    candidate_text = "\n".join(payload["stateAnswerSections"]["candidate"])
    assert "已作为任务附件进入项目资料库" not in candidate_text
    assert payload["retrievalSummary"]["candidate_leakage_count"] >= 1


def test_workspace_chat_keeps_run_logs_as_state_sources_without_promoting_them_to_judgment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="run log 只作最近运行摘要")
    insert_approved_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_bundle_runlog",
        topic="正式 bundle 判断",
        summary="正式判断仍然来自 judgment bundle。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="继续推进正式判断",
        desc="保持 judgment bundle 与状态回答一致。",
    )
    insert_runtime_run_log(
        client,
        run_id="runlog_state_first_source",
        client_id=client_id,
        summary="状态池刷新完成",
        detail={
            "intentProfile": "client_overview",
            "latestRunSummary": "最近运行提示：已完成状态池刷新。",
            "outputSummary": "这条 outputSummary 不应覆盖 latestRunSummary。",
        },
    )

    captured: dict[str, str] = {}

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("state-first query should not fall back to document retrieval")

    def fake_generate_workspace_state_response(prompt: str, state_context_summary: str, *, on_partial=None):
        captured["context_summary"] = state_context_summary
        return AiStructuredResponse(
            content="正式判断仍来自 judgment bundle，运行日志只作为最近运行摘要。",
            judgment="不要把 run log 当成正式判断。",
            analysis="状态池来源里可以出现 run_log，但正式判断只能来自 judgment bundle。",
            actions="继续推进正式判断与任务动作。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_workspace_state_response", fake_generate_workspace_state_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "这个客户最近在推进什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert "run_log" in payload["stateSources"]
    official_text = "\n".join(payload["stateAnswerSections"]["official"])
    assert "正式判断仍然来自 judgment bundle" in official_text
    assert "最近运行提示：已完成状态池刷新" not in official_text
    assert "最近运行提示：已完成状态池刷新" not in captured["context_summary"]


def test_workspace_chat_keeps_document_retrieval_for_drilldown_questions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="文档下钻测试")
    insert_approved_judgment(client, client_id=client_id, topic="客户推进判断", summary="当前主要围绕关系推进和双年会协同展开。")
    create_scoped_task(client, client_id=client_id, title="推进关系沟通", desc="补齐会前资料并安排下一轮沟通。")
    client.app.state.app_state.db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_state_1', ?, NULL, '双年会沟通纪要', '/tmp/meeting-note.md', 'md', 'file', '纪要里明确提到，本周重点是确认发言安排和资料准备。', '[]', '2026-04-18T10:00:00')
        """,
        (client_id,),
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_doc_state_1', ?, NULL, 'doc_state_1', 'kd_doc_state_1_uid', '/tmp/meeting-note.md', '/tmp/meeting-note.md', NULL,
            '组织与战略', NULL, NULL, 0.0, NULL, 'md',
            '组织与战略', '会议纪要', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_state_1', 'normalized_state_1', '2026-04-18T10:00:00', '2026-04-18T10:00:00'
        )
        """,
        (client_id,),
    )

    calls = {"retrieval": 0}

    def fake_retrieval_bundle(client_id_arg: str, prompt: str):
        calls["retrieval"] += 1
        assert client_id_arg == client_id
        return RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_doc_state_1",
                    chunk_id="chunk_state_1",
                    title="双年会沟通纪要",
                    excerpt="纪要里明确提到，本周重点是确认发言安排和资料准备。",
                    score=0.92,
                    coverage=0.8,
                    section_label="关键片段",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["原文", "资料"],
                    path="/tmp/meeting-note.md",
                )
            ],
            coverage=0.8,
            retrieval_summary={
                "masterHitCount": 1,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 1,
                "preferredCategories": ["组织与战略"],
                "categoryCoverage": ["组织与战略"],
            },
            context_text="",
            matched_terms=["原文", "资料"],
            failure_reason=None,
        )

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="已经结合原文片段回答。",
            judgment="当前判断有直接证据支撑。",
            analysis="原文明确提到了本周动作。",
            actions="继续沿着原文中的动作推进。",
            timeline="本周内完成。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda db, data_dir, client_id_arg, prompt: fake_retrieval_bundle(client_id_arg, prompt))
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "哪份原文支持当前判断？请引用相关文件"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert calls["retrieval"] == 1
    assert payload["judgmentQueryMode"] == "evidence_based_synthesis"
    assert payload["evidenceSupportMode"] == "raw_doc_drilldown"
    assert payload["answerMode"] == "grounded_answer"
    assert payload["retrievalSummary"]["retrievalDeferred"] is False
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "document_drilldown_requested"
    assert payload["retrievalSummary"]["retrievalStage"] == "hybrid_raw_drilldown"
    assert payload["evidence"]
    assert payload["evidence"][0]["title"] == "双年会沟通纪要"


def test_workspace_chat_evidence_based_synthesis_keeps_raw_docs_in_support_layer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="evidence-based synthesis 边界测试")
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="candidate_conflicted_judgment",
        topic="客户候选判断",
        summary="当前候选判断认为项目已经进入执行协同阶段。",
    )
    create_scoped_task(
        client,
        client_id=client_id,
        title="核对判断依据",
        desc="需要把候选判断与原文纪要逐条对照。",
    )
    insert_conflict_group(
        client,
        conflict_id="conflict_candidate_vs_raw",
        client_id=client_id,
        title="候选判断与原文存在阶段冲突",
        summary="候选判断写的是执行协同阶段，但原文纪要仍显示方向提案阶段，需要核对后再决定是否保留。",
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES('doc_judgment_raw_conflict', ?, NULL, '双年会方向讨论纪要', '/tmp/conflict-meeting-note.md', 'md', 'file', '纪要明确写到：这次仍是方向提案，不是最终执行方案。', '[]', '2026-04-18T10:00:00')
        """,
        (client_id,),
    )
    client.app.state.app_state.db.execute(
        """
        INSERT INTO knowledge_documents(
            id, client_id, import_batch_id, document_id, doc_uid, original_path, import_source_path, current_human_path,
            human_folder_category, reclassified_at, reclass_reason, reclass_confidence, normalized_path, kind,
            primary_category, secondary_category, classification_confidence, needs_review, deep_read, last_hit_question,
            dedup_status, vector_status, version, binary_hash, normalized_hash, created_at, updated_at
        )
        VALUES(
            'kd_judgment_raw_conflict', ?, NULL, 'doc_judgment_raw_conflict', 'kd_judgment_raw_conflict_uid', '/tmp/conflict-meeting-note.md', '/tmp/conflict-meeting-note.md', NULL,
            '组织与战略', NULL, NULL, 0.0, NULL, 'md',
            '组织与战略', '会议纪要', 1.0, 0, 0, NULL,
            'unique', 'chunk_indexed', 1, 'binary_conflict_1', 'normalized_conflict_1', '2026-04-18T10:00:00', '2026-04-18T10:00:00'
        )
        """,
        (client_id,),
    )

    calls = {"retrieval": 0}

    def fake_retrieval_bundle(client_id_arg: str, prompt: str):
        calls["retrieval"] += 1
        assert client_id_arg == client_id
        return RetrievalBundle(
            citations=[
                CitationMatch(
                    knowledge_document_id="kd_judgment_raw_conflict",
                    chunk_id="chunk_judgment_raw_conflict",
                    title="双年会方向讨论纪要",
                    excerpt="纪要明确写到：这次仍是方向提案，不是最终执行方案。",
                    score=0.95,
                    coverage=0.82,
                    section_label="关键片段",
                    source_stage="raw_chunk",
                    drillthrough_used=True,
                    matched_terms=["资料", "原文", "判断"],
                    path="/tmp/conflict-meeting-note.md",
                )
            ],
            coverage=0.82,
            retrieval_summary={
                "masterHitCount": 1,
                "surrogateHitCount": 0,
                "rawChunkHitCount": 1,
                "preferredCategories": ["组织与战略"],
                "categoryCoverage": ["组织与战略"],
            },
            context_text="",
            matched_terms=["资料", "原文", "判断"],
            failure_reason=None,
        )

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="已结合状态对象和原文片段回答。",
            judgment="当前系统内已批准的正式判断仍为空。",
            analysis="原文可以强化或削弱候选判断，但不能直接改写官方层。",
            actions="先核对候选判断与会议纪要，再决定是否生成 judgment proposal。",
            timeline="补齐后再进入审批。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda db, data_dir, client_id_arg, prompt: fake_retrieval_bundle(client_id_arg, prompt))
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "基于资料能形成哪些判断？请引用原文"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    candidate_text = "\n".join(payload["stateAnswerSections"]["candidate"])
    evidence_text = "\n".join(payload["stateAnswerSections"]["evidenceSupport"])
    risk_text = "\n".join(payload["stateAnswerSections"]["risks"])

    assert calls["retrieval"] == 1
    assert payload["judgmentQueryMode"] == "evidence_based_synthesis"
    assert payload["evidenceSupportMode"] == "raw_doc_drilldown"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] in {
        "document_drilldown_requested",
        "evidence_question_needs_evidence",
    }
    assert payload["retrievalSummary"]["retrievalStage"] == "hybrid_raw_drilldown"
    assert payload["stateAnswerSections"]["official"] == []
    assert "执行协同阶段" in candidate_text
    assert "方向提案" not in candidate_text
    assert "方向提案" in evidence_text
    assert "阶段冲突" in risk_text
    assert payload["evidence"][0]["title"] == "双年会方向讨论纪要"


def test_workspace_chat_marks_stale_dna_as_weak_support_in_hybrid_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="过旧 DNA 弱化测试")
    create_scoped_task(
        client,
        client_id=client_id,
        title="核对客户背景",
        desc="需要结合客户 DNA 和当前任务推进，但不能把过旧 DNA 当作强证据。",
    )
    insert_client_dna_document(
        client,
        client_id=client_id,
        module_key="organization_intro",
        title="组织介绍",
        summary="客户过去强调行业协同与长期能力建设。",
        normalized_text="客户过去强调行业协同与长期能力建设，这份 DNA 版本较早。",
        updated_at="2025-01-01T09:00:00",
    )

    def fail_if_retrieval_runs(*args, **kwargs):
        raise AssertionError("stale DNA hybrid query should still stay on linked evidence path")

    def fake_generate_chat_response(prompt: str, system_instruction: str, context_summary: str, *, on_partial=None):
        return AiStructuredResponse(
            content="当前回答已经保留 DNA 的弱支撑边界。",
            judgment="正式判断仍为空。",
            analysis="DNA 可以作为背景，但过旧时只能弱化引用。",
            actions="优先补最近会议或任务上下文。",
            timeline="补齐后再判断是否进入 proposal。",
        )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", fail_if_retrieval_runs)
    monkeypatch.setattr(client.app.state.app_state.ai, "generate_chat_response", fake_generate_chat_response)

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在怎么看这个客户？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    evidence_text = "\n".join(payload["stateAnswerSections"]["evidenceSupport"])
    assert payload["judgmentQueryMode"] == "hybrid"
    assert payload["evidenceSupportMode"] == "linked_state_evidence"
    assert "仅作弱支撑" in evidence_text


def test_task_prep_proposal_runs_through_review_and_execution_without_touching_official_layer(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="任务准备 proposal 测试")
    insert_approved_judgment(client, client_id=client_id, topic="客户主判断", summary="当前项目进入稳态推进，准备包可直接围绕正式判断组织。")
    task_id = create_scoped_task(client, client_id=client_id, title="准备周会材料", desc="汇总本周关键推进、风险和待确认问题。")

    prep_pack = client.get(f"/api/v1/tasks/{task_id}/prep-pack")
    assert prep_pack.status_code == 200, prep_pack.text
    prep_payload = prep_pack.json()
    assert prep_payload["summary"]
    assert prep_payload["boundaryNotes"]

    proposal = client.post(f"/api/v1/tasks/{task_id}/prep-pack/proposals")
    assert proposal.status_code == 200, proposal.text
    proposal_payload = proposal.json()
    assert proposal_payload["kind"] == "task_prep"
    assert proposal_payload["status"] == "pending_review"

    approved = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/approve",
        json={"comment": "可以进入执行台账"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    executed = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/execute",
        json={"comment": "执行"},
    )
    assert executed.status_code == 200, executed.text
    execution_payload = executed.json()
    assert execution_payload["proposal"]["status"] == "executed"
    assert execution_payload["executionTicket"]["status"] == "executed"
    assert execution_payload["executionTicket"]["result"]["resultType"] == "prep_artifact_ready"
    assert execution_payload["executionTicket"]["result"]["artifactRefs"]
    assert "不直接改写 official judgment" in execution_payload["executionTicket"]["result"]["summary"]

    judgment_count = client.app.state.app_state.db.scalar(
        "SELECT COUNT(1) AS count FROM judgment_versions WHERE client_id = ? AND authority_level = 'approved'",
        (client_id,),
    )
    assert int(judgment_count or 0) == 1


def test_meeting_followup_proposal_creates_execution_tasks_after_approval(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="会议 follow-up proposal 测试")

    prepared = client.post(
        f"/api/v1/clients/{client_id}/meetings",
        json={"title": "双年会筹备会", "scheduledAt": "2026-04-18T14:00:00"},
    )
    assert prepared.status_code == 200, prepared.text
    meeting_id = prepared.json()["meeting"]["id"]

    db = client.app.state.app_state.db
    db.execute(
        "INSERT INTO decisions(id, meeting_id, summary, created_at) VALUES('dec_followup_1', ?, '确认本周完成双年会发言和资料清单。', '2026-04-18T14:30:00')",
        (meeting_id,),
    )
    db.execute(
        """
        INSERT INTO action_items(id, meeting_id, title, owner_name, due_date, confidence, publish_status, created_at)
        VALUES('act_followup_1', ?, '整理双年会资料清单', '庆华', '本周', 0.9, 'draft', '2026-04-18T14:30:00')
        """,
        (meeting_id,),
    )
    db.execute(
        "INSERT INTO risks(id, meeting_id, summary, severity, created_at) VALUES('risk_followup_1', ?, '资料边界如果不收束，会影响会前统一口径。', 'medium', '2026-04-18T14:30:00')",
        (meeting_id,),
    )
    db.execute("UPDATE meetings SET stage = 'resolved', updated_at = '2026-04-18T14:35:00' WHERE id = ?", (meeting_id,))

    proposal = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/proposals/follow-up")
    assert proposal.status_code == 200, proposal.text
    proposal_payload = proposal.json()
    assert proposal_payload["kind"] == "meeting_followup"
    assert proposal_payload["status"] == "pending_review"
    assert proposal_payload["payload"]["actionItems"]
    assert proposal_payload["payload"]["payloadHash"]

    duplicate_proposal = client.post(f"/api/v1/clients/{client_id}/meetings/{meeting_id}/proposals/follow-up")
    assert duplicate_proposal.status_code == 200, duplicate_proposal.text
    assert duplicate_proposal.json()["id"] == proposal_payload["id"]

    approved = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/approve",
        json={"comment": "执行会后跟进"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    executed = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/execute",
        json={"comment": "执行"},
    )
    assert executed.status_code == 200, executed.text
    execution_payload = executed.json()
    assert execution_payload["proposal"]["status"] == "executed"
    assert execution_payload["executionTicket"]["status"] == "executed"
    assert execution_payload["executionTicket"]["result"]["resultType"] == "followup_task_created"
    created_task_ids = execution_payload["executionTicket"]["result"]["createdTaskIds"]
    assert len(created_task_ids) == 1

    executed_again = client.post(
        f"/api/v1/proposals/{proposal_payload['id']}/execute",
        json={"comment": "重复执行"},
    )
    assert executed_again.status_code == 200, executed_again.text
    repeated_payload = executed_again.json()
    assert repeated_payload["executionTicket"]["id"] == execution_payload["executionTicket"]["id"]
    assert repeated_payload["executionTicket"]["result"]["createdTaskIds"] == created_task_ids

    created_task = db.fetchone(
        "SELECT title, source_type, source_id, client_id FROM tasks WHERE source_type = 'meeting_followup_proposal' ORDER BY created_at DESC LIMIT 1"
    )
    assert created_task is not None
    assert str(created_task["title"]) == "整理双年会资料清单"
    assert str(created_task["source_id"]) == proposal_payload["id"]
    assert str(created_task["client_id"]) == client_id
    task_count = db.scalar("SELECT COUNT(1) AS count FROM tasks WHERE source_type = 'meeting_followup_proposal' AND source_id = ?", (proposal_payload["id"],))
    assert int(task_count or 0) == 1
~~~

## `backend/tests/test_workspace_chat_regression.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.ai import AiInvocationError
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "问答回归客户") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "用于问答主链回归测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_scoped_task(client: TestClient, *, client_id: str, title: str, desc: str = "") -> str:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": desc,
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_candidate_judgment(
    client: TestClient,
    *,
    client_id: str,
    judgment_id: str,
    topic: str,
    summary: str,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence,
            created_at, updated_at, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by
        )
        VALUES(
            ?, ?, 'client', ?, ?, 1, 'awaiting_review', ?, '[]', NULL, 'medium', 'medium',
            '2026-04-18T11:00:00', '2026-04-18T11:00:00', 'analysis', 'candidate', 'normalized',
            NULL, 'snapshot_regression_candidate', NULL, NULL
        )
        """,
        (
            judgment_id,
            client_id,
            client_id,
            topic,
            summary,
        ),
    )


def _build_retrieval_bundle(title_prefix: str, excerpts: list[str]) -> RetrievalBundle:
    citations = [
        CitationMatch(
            knowledge_document_id=f"kd_{index}",
            chunk_id=f"chunk_{index}",
            title=f"{title_prefix}{index}",
            excerpt=excerpt,
            score=0.86 - (index * 0.03),
            coverage=0.81,
            section_label="关键片段",
            source_stage="raw_chunk",
            drillthrough_used=True,
            matched_terms=["资料", "原文"],
            path=f"/tmp/{title_prefix}{index}.md",
        )
        for index, excerpt in enumerate(excerpts, start=1)
    ]
    return RetrievalBundle(
        citations=citations,
        coverage=0.81,
        retrieval_summary={
            "docHitCount": len(citations),
            "sectionHitCount": len(citations),
            "rawChunkHitCount": len(citations),
            "masterHitCount": len(citations),
            "surrogateHitCount": len(citations),
            "preferredCategories": ["组织与战略", "项目与业务"],
            "categoryCoverage": ["组织与战略", "项目与业务"],
        },
        context_text="",
        matched_terms=["资料", "原文"],
        failure_reason=None,
    )


def test_workspace_chat_intro_timeout_still_returns_deliverable_intro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="日慈基金会")
    create_scoped_task(client, client_id=client_id, title="补齐项目介绍", desc="补齐项目介绍与会议纪要引用。")

    retrieval_bundle = _build_retrieval_bundle(
        "日慈基金会资料",
        [
            "日慈基金会聚焦教师赋能，围绕学校协同与长期能力建设开展项目。",
            "心盛计划聚焦青少年社群与心理健康支持，强调阶段性陪伴机制。",
            "繁星计划强调生态协同、传播联动与项目执行节奏。",
            "一季度沟通会议纪要明确下一阶段需要补齐负责人和里程碑。",
        ],
    )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: retrieval_bundle)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AiInvocationError("doubao", "read timeout")),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍日慈基金会，给一版简洁清晰的项目资料，并引用原文。"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["answerIntent"] in {"intro_profile", "project_intro"}
    assert payload["retrievalSummary"]["answerIntent"] in {"intro_profile", "project_intro"}
    assert payload["retrievalSummary"]["retrievalDecisionReason"] in {
        "intro_query_needs_evidence",
        "project_intro_needs_evidence",
    }
    assert "日慈基金会" in payload["content"]
    assert any(token in payload["content"] for token in ("教师赋能", "心盛计划", "繁星计划"))
    assert "当前最值得抓住的原始观察包括" not in payload["content"]
    assert "正式长回答阶段没有成功完成" not in payload["content"]
    assert len(payload["evidence"]) >= 3


def test_workspace_chat_meeting_summary_forces_evidence_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="会议证据回归客户")
    create_scoped_task(client, client_id=client_id, title="跟进会议行动项", desc="补齐负责人和截止时间。")

    retrieval_bundle = _build_retrieval_bundle(
        "一季度沟通会议纪要",
        [
            "会议重点是项目推进节奏与资源分工，明确下周完成材料对齐。",
            "会议决定先收敛范围，再进入执行协同，避免并行扩散。",
            "行动项包括：确认负责人、更新时间表、同步风险清单。",
        ],
    )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: retrieval_bundle)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="最近会议已形成阶段决定，并明确了下一步行动与风险待确认项。",
            judgment="会议类问题应以会议纪要与行动项为主来源。",
            analysis="这次回答已经命中会议与原文证据。",
            actions="继续核对负责人、截止时间和风险项。",
            timeline="本周内完成对齐。",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "提炼最新会议纪要"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerIntent"] == "meeting_summary"
    assert payload["retrievalSummary"]["answerIntent"] == "meeting_summary"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "meeting_summary_needs_evidence"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] != "state_first_default"
    assert payload["retrievalSummary"]["retrievalDeferred"] is False
    assert payload["retrievalSummary"]["rawChunkHitCount"] > 0
    assert "会议" in payload["content"]
    assert any(token in payload["content"] for token in ("决定", "行动", "风险", "待确认"))


def test_workspace_chat_next_actions_timeout_uses_three_section_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="下一步回归客户")
    create_scoped_task(client, client_id=client_id, title="确认行动负责人", desc="本周补齐负责人和截止时间。")
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_next_action_candidate",
        topic="候选判断",
        summary="当前推进节奏仍需会议与任务证据交叉确认。",
    )

    retrieval_bundle = _build_retrieval_bundle(
        "行动跟进资料",
        [
            "后续安排包括：本周确认负责人、下周同步风险和未决问题。",
            "会议行动项强调先补证据，再推进执行分工。",
            "任务记录显示仍有两项待办尚未确认截止时间。",
        ],
    )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: retrieval_bundle)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AiInvocationError("doubao", "read timeout")),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "接下来这个客户要做什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["answerIntent"] == "next_actions"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "next_actions_needs_evidence"
    assert "一、已经比较明确的行动" in payload["content"]
    assert "二、需要先补证据 / 补沟通的信息" in payload["content"]
    assert "三、系统里的候选提醒（暂不当成确定事实）" in payload["content"]
    assert any(token in payload["content"] for token in ("负责人", "风险", "待确认", "行动"))


def test_workspace_chat_official_registry_keeps_candidate_out_of_official_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="正式判断边界客户")
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_candidate_only",
        topic="候选判断",
        summary="当前只有候选判断，尚未进入 approved 层。",
    )

    monkeypatch.setattr(
        app_main,
        "retrieve_knowledge_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("official registry query should stay state-only")),
    )
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_workspace_state_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="当前暂无正式判断，候选判断需继续补证据。",
            judgment="正式层为空。",
            analysis="候选判断与正式判断边界清晰。",
            actions="继续补证据后再申请审批。",
            timeline="补齐后再推进。",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在有哪些正式判断？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerIntent"] == "official_judgment_registry"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "official_registry_requested"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["stateAnswerSections"]["official"] == []
    assert payload["stateAnswerSections"]["candidate"]
~~~

## `backend/uv.lock`

- 编码: `utf-8`

~~~text
version = 1
revision = 3
requires-python = ">=3.11"
resolution-markers = [
    "python_full_version >= '3.14'",
    "python_full_version == '3.13.*'",
    "python_full_version == '3.12.*'",
    "python_full_version < '3.12'",
]

[[package]]
name = "annotated-doc"
version = "0.0.4"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/57/ba/046ceea27344560984e26a590f90bc7f4a75b06701f653222458922b558c/annotated_doc-0.0.4.tar.gz", hash = "sha256:fbcda96e87e9c92ad167c2e53839e57503ecfda18804ea28102353485033faa4", size = 7288, upload-time = "2025-11-10T22:07:42.062Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/1e/d3/26bf1008eb3d2daa8ef4cacc7f3bfdc11818d111f7e2d0201bc6e3b49d45/annotated_doc-0.0.4-py3-none-any.whl", hash = "sha256:571ac1dc6991c450b25a9c2d84a3705e2ae7a53467b5d111c24fa8baabbed320", size = 5303, upload-time = "2025-11-10T22:07:40.673Z" },
]

[[package]]
name = "annotated-types"
version = "0.7.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/ee/67/531ea369ba64dcff5ec9c3402f9f51bf748cec26dde048a2f973a4eea7f5/annotated_types-0.7.0.tar.gz", hash = "sha256:aff07c09a53a08bc8cfccb9c85b05f1aa9a2a6f23728d790723543408344ce89", size = 16081, upload-time = "2024-05-20T21:33:25.928Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/78/b6/6307fbef88d9b5ee7421e68d78a9f162e0da4900bc5f5793f6d3d0e34fb8/annotated_types-0.7.0-py3-none-any.whl", hash = "sha256:1f02e8b43a8fbbc3f3e0d4f0f4bfc8131bcb4eebe8849b8e5c773f3a1c582a53", size = 13643, upload-time = "2024-05-20T21:33:24.1Z" },
]

[[package]]
name = "anyio"
version = "4.12.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "idna" },
    { name = "typing-extensions", marker = "python_full_version < '3.13'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/96/f0/5eb65b2bb0d09ac6776f2eb54adee6abe8228ea05b20a5ad0e4945de8aac/anyio-4.12.1.tar.gz", hash = "sha256:41cfcc3a4c85d3f05c932da7c26d0201ac36f72abd4435ba90d0464a3ffed703", size = 228685, upload-time = "2026-01-06T11:45:21.246Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/38/0e/27be9fdef66e72d64c0cdc3cc2823101b80585f8119b5c112c2e8f5f7dab/anyio-4.12.1-py3-none-any.whl", hash = "sha256:d405828884fc140aa80a3c667b8beed277f1dfedec42ba031bd6ac3db606ab6c", size = 113592, upload-time = "2026-01-06T11:45:19.497Z" },
]

[[package]]
name = "certifi"
version = "2026.2.25"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/af/2d/7bf41579a8986e348fa033a31cdd0e4121114f6bce2457e8876010b092dd/certifi-2026.2.25.tar.gz", hash = "sha256:e887ab5cee78ea814d3472169153c2d12cd43b14bd03329a39a9c6e2e80bfba7", size = 155029, upload-time = "2026-02-25T02:54:17.342Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/9a/3c/c17fb3ca2d9c3acff52e30b309f538586f9f5b9c9cf454f3845fc9af4881/certifi-2026.2.25-py3-none-any.whl", hash = "sha256:027692e4402ad994f1c42e52a4997a9763c646b73e4096e4d5d6db8af1d6f0fa", size = 153684, upload-time = "2026-02-25T02:54:15.766Z" },
]

[[package]]
name = "charset-normalizer"
version = "3.4.5"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/1d/35/02daf95b9cd686320bb622eb148792655c9412dbb9b67abb5694e5910a24/charset_normalizer-3.4.5.tar.gz", hash = "sha256:95adae7b6c42a6c5b5b559b1a99149f090a57128155daeea91732c8d970d8644", size = 134804, upload-time = "2026-03-06T06:03:19.46Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/8f/9e/bcec3b22c64ecec47d39bf5167c2613efd41898c019dccd4183f6aa5d6a7/charset_normalizer-3.4.5-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:610f72c0ee565dfb8ae1241b666119582fdbfe7c0975c175be719f940e110694", size = 279531, upload-time = "2026-03-06T06:00:52.252Z" },
    { url = "https://files.pythonhosted.org/packages/58/12/81fd25f7e7078ab5d1eedbb0fac44be4904ae3370a3bf4533c8f2d159acd/charset_normalizer-3.4.5-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:60d68e820af339df4ae8358c7a2e7596badeb61e544438e489035f9fbf3246a5", size = 188006, upload-time = "2026-03-06T06:00:53.8Z" },
    { url = "https://files.pythonhosted.org/packages/ae/6e/f2d30e8c27c1b0736a6520311982cf5286cfc7f6cac77d7bc1325e3a23f2/charset_normalizer-3.4.5-cp311-cp311-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:10b473fc8dca1c3ad8559985794815f06ca3fc71942c969129070f2c3cdf7281", size = 205085, upload-time = "2026-03-06T06:00:55.311Z" },
    { url = "https://files.pythonhosted.org/packages/d0/90/d12cefcb53b5931e2cf792a33718d7126efb116a320eaa0742c7059a95e4/charset_normalizer-3.4.5-cp311-cp311-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:d4eb8ac7469b2a5d64b5b8c04f84d8bf3ad340f4514b98523805cbf46e3b3923", size = 200545, upload-time = "2026-03-06T06:00:56.532Z" },
    { url = "https://files.pythonhosted.org/packages/03/f4/44d3b830a20e89ff82a3134912d9a1cf6084d64f3b95dcad40f74449a654/charset_normalizer-3.4.5-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:5bcb3227c3d9aaf73eaaab1db7ccd80a8995c509ee9941e2aae060ca6e4e5d81", size = 193863, upload-time = "2026-03-06T06:00:57.823Z" },
    { url = "https://files.pythonhosted.org/packages/25/4b/f212119c18a6320a9d4a730d1b4057875cdeabf21b3614f76549042ef8a8/charset_normalizer-3.4.5-cp311-cp311-manylinux_2_31_armv7l.whl", hash = "sha256:75ee9c1cce2911581a70a3c0919d8bccf5b1cbc9b0e5171400ec736b4b569497", size = 181827, upload-time = "2026-03-06T06:00:59.323Z" },
    { url = "https://files.pythonhosted.org/packages/74/00/b26158e48b425a202a92965f8069e8a63d9af1481dfa206825d7f74d2a3c/charset_normalizer-3.4.5-cp311-cp311-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:1d1401945cb77787dbd3af2446ff2d75912327c4c3a1526ab7955ecf8600687c", size = 191085, upload-time = "2026-03-06T06:01:00.546Z" },
    { url = "https://files.pythonhosted.org/packages/c4/c2/1c1737bf6fd40335fe53d28fe49afd99ee4143cc57a845e99635ce0b9b6d/charset_normalizer-3.4.5-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:0a45e504f5e1be0bd385935a8e1507c442349ca36f511a47057a71c9d1d6ea9e", size = 190688, upload-time = "2026-03-06T06:01:02.479Z" },
    { url = "https://files.pythonhosted.org/packages/5a/3d/abb5c22dc2ef493cd56522f811246a63c5427c08f3e3e50ab663de27fcf4/charset_normalizer-3.4.5-cp311-cp311-musllinux_1_2_armv7l.whl", hash = "sha256:e09f671a54ce70b79a1fc1dc6da3072b7ef7251fadb894ed92d9aa8218465a5f", size = 183077, upload-time = "2026-03-06T06:01:04.231Z" },
    { url = "https://files.pythonhosted.org/packages/44/33/5298ad4d419a58e25b3508e87f2758d1442ff00c2471f8e0403dab8edad5/charset_normalizer-3.4.5-cp311-cp311-musllinux_1_2_ppc64le.whl", hash = "sha256:d01de5e768328646e6a3fa9e562706f8f6641708c115c62588aef2b941a4f88e", size = 206706, upload-time = "2026-03-06T06:01:05.773Z" },
    { url = "https://files.pythonhosted.org/packages/7b/17/51e7895ac0f87c3b91d276a449ef09f5532a7529818f59646d7a55089432/charset_normalizer-3.4.5-cp311-cp311-musllinux_1_2_riscv64.whl", hash = "sha256:131716d6786ad5e3dc542f5cc6f397ba3339dc0fb87f87ac30e550e8987756af", size = 191665, upload-time = "2026-03-06T06:01:07.473Z" },
    { url = "https://files.pythonhosted.org/packages/90/8f/cce9adf1883e98906dbae380d769b4852bb0fa0004bc7d7a2243418d3ea8/charset_normalizer-3.4.5-cp311-cp311-musllinux_1_2_s390x.whl", hash = "sha256:1a374cc0b88aa710e8865dc1bd6edb3743c59f27830f0293ab101e4cf3ce9f85", size = 201950, upload-time = "2026-03-06T06:01:08.973Z" },
    { url = "https://files.pythonhosted.org/packages/08/ca/bce99cd5c397a52919e2769d126723f27a4c037130374c051c00470bcd38/charset_normalizer-3.4.5-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:d31f0d1671e1534e395f9eb84a68e0fb670e1edb1fe819a9d7f564ae3bc4e53f", size = 195830, upload-time = "2026-03-06T06:01:10.155Z" },
    { url = "https://files.pythonhosted.org/packages/87/4f/2e3d023a06911f1281f97b8f036edc9872167036ca6f55cc874a0be6c12c/charset_normalizer-3.4.5-cp311-cp311-win32.whl", hash = "sha256:cace89841c0599d736d3d74a27bc5821288bb47c5441923277afc6059d7fbcb4", size = 132029, upload-time = "2026-03-06T06:01:11.706Z" },
    { url = "https://files.pythonhosted.org/packages/fe/1f/a853b73d386521fd44b7f67ded6b17b7b2367067d9106a5c4b44f9a34274/charset_normalizer-3.4.5-cp311-cp311-win_amd64.whl", hash = "sha256:f8102ae93c0bc863b1d41ea0f4499c20a83229f52ed870850892df555187154a", size = 142404, upload-time = "2026-03-06T06:01:12.865Z" },
    { url = "https://files.pythonhosted.org/packages/b4/10/dba36f76b71c38e9d391abe0fd8a5b818790e053c431adecfc98c35cd2a9/charset_normalizer-3.4.5-cp311-cp311-win_arm64.whl", hash = "sha256:ed98364e1c262cf5f9363c3eca8c2df37024f52a8fa1180a3610014f26eac51c", size = 132796, upload-time = "2026-03-06T06:01:14.106Z" },
    { url = "https://files.pythonhosted.org/packages/9c/b6/9ee9c1a608916ca5feae81a344dffbaa53b26b90be58cc2159e3332d44ec/charset_normalizer-3.4.5-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:ed97c282ee4f994ef814042423a529df9497e3c666dca19be1d4cd1129dc7ade", size = 280976, upload-time = "2026-03-06T06:01:15.276Z" },
    { url = "https://files.pythonhosted.org/packages/f8/d8/a54f7c0b96f1df3563e9190f04daf981e365a9b397eedfdfb5dbef7e5c6c/charset_normalizer-3.4.5-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:0294916d6ccf2d069727d65973c3a1ca477d68708db25fd758dd28b0827cff54", size = 189356, upload-time = "2026-03-06T06:01:16.511Z" },
    { url = "https://files.pythonhosted.org/packages/42/69/2bf7f76ce1446759a5787cb87d38f6a61eb47dbbdf035cfebf6347292a65/charset_normalizer-3.4.5-cp312-cp312-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:dc57a0baa3eeedd99fafaef7511b5a6ef4581494e8168ee086031744e2679467", size = 206369, upload-time = "2026-03-06T06:01:17.853Z" },
    { url = "https://files.pythonhosted.org/packages/10/9c/949d1a46dab56b959d9a87272482195f1840b515a3380e39986989a893ae/charset_normalizer-3.4.5-cp312-cp312-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:ed1a9a204f317ef879b32f9af507d47e49cd5e7f8e8d5d96358c98373314fc60", size = 203285, upload-time = "2026-03-06T06:01:19.473Z" },
    { url = "https://files.pythonhosted.org/packages/67/5c/ae30362a88b4da237d71ea214a8c7eb915db3eec941adda511729ac25fa2/charset_normalizer-3.4.5-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:7ad83b8f9379176c841f8865884f3514d905bcd2a9a3b210eaa446e7d2223e4d", size = 196274, upload-time = "2026-03-06T06:01:20.728Z" },
    { url = "https://files.pythonhosted.org/packages/b2/07/c9f2cb0e46cb6d64fdcc4f95953747b843bb2181bda678dc4e699b8f0f9a/charset_normalizer-3.4.5-cp312-cp312-manylinux_2_31_armv7l.whl", hash = "sha256:a118e2e0b5ae6b0120d5efa5f866e58f2bb826067a646431da4d6a2bdae7950e", size = 184715, upload-time = "2026-03-06T06:01:22.194Z" },
    { url = "https://files.pythonhosted.org/packages/36/64/6b0ca95c44fddf692cd06d642b28f63009d0ce325fad6e9b2b4d0ef86a52/charset_normalizer-3.4.5-cp312-cp312-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:754f96058e61a5e22e91483f823e07df16416ce76afa4ebf306f8e1d1296d43f", size = 193426, upload-time = "2026-03-06T06:01:23.795Z" },
    { url = "https://files.pythonhosted.org/packages/50/bc/a730690d726403743795ca3f5bb2baf67838c5fea78236098f324b965e40/charset_normalizer-3.4.5-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:0c300cefd9b0970381a46394902cd18eaf2aa00163f999590ace991989dcd0fc", size = 191780, upload-time = "2026-03-06T06:01:25.053Z" },
    { url = "https://files.pythonhosted.org/packages/97/4f/6c0bc9af68222b22951552d73df4532b5be6447cee32d58e7e8c74ecbb7b/charset_normalizer-3.4.5-cp312-cp312-musllinux_1_2_armv7l.whl", hash = "sha256:c108f8619e504140569ee7de3f97d234f0fbae338a7f9f360455071ef9855a95", size = 185805, upload-time = "2026-03-06T06:01:26.294Z" },
    { url = "https://files.pythonhosted.org/packages/dd/b9/a523fb9b0ee90814b503452b2600e4cbc118cd68714d57041564886e7325/charset_normalizer-3.4.5-cp312-cp312-musllinux_1_2_ppc64le.whl", hash = "sha256:d1028de43596a315e2720a9849ee79007ab742c06ad8b45a50db8cdb7ed4a82a", size = 208342, upload-time = "2026-03-06T06:01:27.55Z" },
    { url = "https://files.pythonhosted.org/packages/4d/61/c59e761dee4464050713e50e27b58266cc8e209e518c0b378c1580c959ba/charset_normalizer-3.4.5-cp312-cp312-musllinux_1_2_riscv64.whl", hash = "sha256:19092dde50335accf365cce21998a1c6dd8eafd42c7b226eb54b2747cdce2fac", size = 193661, upload-time = "2026-03-06T06:01:29.051Z" },
    { url = "https://files.pythonhosted.org/packages/1c/43/729fa30aad69783f755c5ad8649da17ee095311ca42024742701e202dc59/charset_normalizer-3.4.5-cp312-cp312-musllinux_1_2_s390x.whl", hash = "sha256:4354e401eb6dab9aed3c7b4030514328a6c748d05e1c3e19175008ca7de84fb1", size = 204819, upload-time = "2026-03-06T06:01:30.298Z" },
    { url = "https://files.pythonhosted.org/packages/87/33/d9b442ce5a91b96fc0840455a9e49a611bbadae6122778d0a6a79683dd31/charset_normalizer-3.4.5-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:a68766a3c58fde7f9aaa22b3786276f62ab2f594efb02d0a1421b6282e852e98", size = 198080, upload-time = "2026-03-06T06:01:31.478Z" },
    { url = "https://files.pythonhosted.org/packages/56/5a/b8b5a23134978ee9885cee2d6995f4c27cc41f9baded0a9685eabc5338f0/charset_normalizer-3.4.5-cp312-cp312-win32.whl", hash = "sha256:1827734a5b308b65ac54e86a618de66f935a4f63a8a462ff1e19a6788d6c2262", size = 132630, upload-time = "2026-03-06T06:01:33.056Z" },
    { url = "https://files.pythonhosted.org/packages/70/53/e44a4c07e8904500aec95865dc3f6464dc3586a039ef0df606eb3ac38e35/charset_normalizer-3.4.5-cp312-cp312-win_amd64.whl", hash = "sha256:728c6a963dfab66ef865f49286e45239384249672cd598576765acc2a640a636", size = 142856, upload-time = "2026-03-06T06:01:34.489Z" },
    { url = "https://files.pythonhosted.org/packages/ea/aa/c5628f7cad591b1cf45790b7a61483c3e36cf41349c98af7813c483fd6e8/charset_normalizer-3.4.5-cp312-cp312-win_arm64.whl", hash = "sha256:75dfd1afe0b1647449e852f4fb428195a7ed0588947218f7ba929f6538487f02", size = 132982, upload-time = "2026-03-06T06:01:35.641Z" },
    { url = "https://files.pythonhosted.org/packages/f5/48/9f34ec4bb24aa3fdba1890c1bddb97c8a4be1bd84ef5c42ac2352563ad05/charset_normalizer-3.4.5-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:ac59c15e3f1465f722607800c68713f9fbc2f672b9eb649fe831da4019ae9b23", size = 280788, upload-time = "2026-03-06T06:01:37.126Z" },
    { url = "https://files.pythonhosted.org/packages/0e/09/6003e7ffeb90cc0560da893e3208396a44c210c5ee42efff539639def59b/charset_normalizer-3.4.5-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:165c7b21d19365464e8f70e5ce5e12524c58b48c78c1f5a57524603c1ab003f8", size = 188890, upload-time = "2026-03-06T06:01:38.73Z" },
    { url = "https://files.pythonhosted.org/packages/42/1e/02706edf19e390680daa694d17e2b8eab4b5f7ac285e2a51168b4b22ee6b/charset_normalizer-3.4.5-cp313-cp313-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:28269983f25a4da0425743d0d257a2d6921ea7d9b83599d4039486ec5b9f911d", size = 206136, upload-time = "2026-03-06T06:01:40.016Z" },
    { url = "https://files.pythonhosted.org/packages/c7/87/942c3def1b37baf3cf786bad01249190f3ca3d5e63a84f831e704977de1f/charset_normalizer-3.4.5-cp313-cp313-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:d27ce22ec453564770d29d03a9506d449efbb9fa13c00842262b2f6801c48cce", size = 202551, upload-time = "2026-03-06T06:01:41.522Z" },
    { url = "https://files.pythonhosted.org/packages/94/0a/af49691938dfe175d71b8a929bd7e4ace2809c0c5134e28bc535660d5262/charset_normalizer-3.4.5-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:0625665e4ebdddb553ab185de5db7054393af8879fb0c87bd5690d14379d6819", size = 195572, upload-time = "2026-03-06T06:01:43.208Z" },
    { url = "https://files.pythonhosted.org/packages/20/ea/dfb1792a8050a8e694cfbde1570ff97ff74e48afd874152d38163d1df9ae/charset_normalizer-3.4.5-cp313-cp313-manylinux_2_31_armv7l.whl", hash = "sha256:c23eb3263356d94858655b3e63f85ac5d50970c6e8febcdde7830209139cc37d", size = 184438, upload-time = "2026-03-06T06:01:44.755Z" },
    { url = "https://files.pythonhosted.org/packages/72/12/c281e2067466e3ddd0595bfaea58a6946765ace5c72dfa3edc2f5f118026/charset_normalizer-3.4.5-cp313-cp313-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:e6302ca4ae283deb0af68d2fbf467474b8b6aedcd3dab4db187e07f94c109763", size = 193035, upload-time = "2026-03-06T06:01:46.051Z" },
    { url = "https://files.pythonhosted.org/packages/ba/4f/3792c056e7708e10464bad0438a44708886fb8f92e3c3d29ec5e2d964d42/charset_normalizer-3.4.5-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:e51ae7d81c825761d941962450f50d041db028b7278e7b08930b4541b3e45cb9", size = 191340, upload-time = "2026-03-06T06:01:47.547Z" },
    { url = "https://files.pythonhosted.org/packages/e7/86/80ddba897127b5c7a9bccc481b0cd36c8fefa485d113262f0fe4332f0bf4/charset_normalizer-3.4.5-cp313-cp313-musllinux_1_2_armv7l.whl", hash = "sha256:597d10dec876923e5c59e48dbd366e852eacb2b806029491d307daea6b917d7c", size = 185464, upload-time = "2026-03-06T06:01:48.764Z" },
    { url = "https://files.pythonhosted.org/packages/4d/00/b5eff85ba198faacab83e0e4b6f0648155f072278e3b392a82478f8b988b/charset_normalizer-3.4.5-cp313-cp313-musllinux_1_2_ppc64le.whl", hash = "sha256:5cffde4032a197bd3b42fd0b9509ec60fb70918d6970e4cc773f20fc9180ca67", size = 208014, upload-time = "2026-03-06T06:01:50.371Z" },
    { url = "https://files.pythonhosted.org/packages/c8/11/d36f70be01597fd30850dde8a1269ebc8efadd23ba5785808454f2389bde/charset_normalizer-3.4.5-cp313-cp313-musllinux_1_2_riscv64.whl", hash = "sha256:2da4eedcb6338e2321e831a0165759c0c620e37f8cd044a263ff67493be8ffb3", size = 193297, upload-time = "2026-03-06T06:01:51.933Z" },
    { url = "https://files.pythonhosted.org/packages/1a/1d/259eb0a53d4910536c7c2abb9cb25f4153548efb42800c6a9456764649c0/charset_normalizer-3.4.5-cp313-cp313-musllinux_1_2_s390x.whl", hash = "sha256:65a126fb4b070d05340a84fc709dd9e7c75d9b063b610ece8a60197a291d0adf", size = 204321, upload-time = "2026-03-06T06:01:53.887Z" },
    { url = "https://files.pythonhosted.org/packages/84/31/faa6c5b9d3688715e1ed1bb9d124c384fe2fc1633a409e503ffe1c6398c1/charset_normalizer-3.4.5-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:c7a80a9242963416bd81f99349d5f3fce1843c303bd404f204918b6d75a75fd6", size = 197509, upload-time = "2026-03-06T06:01:56.439Z" },
    { url = "https://files.pythonhosted.org/packages/fd/a5/c7d9dd1503ffc08950b3260f5d39ec2366dd08254f0900ecbcf3a6197c7c/charset_normalizer-3.4.5-cp313-cp313-win32.whl", hash = "sha256:f1d725b754e967e648046f00c4facc42d414840f5ccc670c5670f59f83693e4f", size = 132284, upload-time = "2026-03-06T06:01:57.812Z" },
    { url = "https://files.pythonhosted.org/packages/b9/0f/57072b253af40c8aa6636e6de7d75985624c1eb392815b2f934199340a89/charset_normalizer-3.4.5-cp313-cp313-win_amd64.whl", hash = "sha256:e37bd100d2c5d3ba35db9c7c5ba5a9228cbcffe5c4778dc824b164e5257813d7", size = 142630, upload-time = "2026-03-06T06:01:59.062Z" },
    { url = "https://files.pythonhosted.org/packages/31/41/1c4b7cc9f13bd9d369ce3bc993e13d374ce25fa38a2663644283ecf422c1/charset_normalizer-3.4.5-cp313-cp313-win_arm64.whl", hash = "sha256:93b3b2cc5cf1b8743660ce77a4f45f3f6d1172068207c1defc779a36eea6bb36", size = 133254, upload-time = "2026-03-06T06:02:00.281Z" },
    { url = "https://files.pythonhosted.org/packages/43/be/0f0fd9bb4a7fa4fb5067fb7d9ac693d4e928d306f80a0d02bde43a7c4aee/charset_normalizer-3.4.5-cp314-cp314-macosx_10_15_universal2.whl", hash = "sha256:8197abe5ca1ffb7d91e78360f915eef5addff270f8a71c1fc5be24a56f3e4873", size = 280232, upload-time = "2026-03-06T06:02:01.508Z" },
    { url = "https://files.pythonhosted.org/packages/28/02/983b5445e4bef49cd8c9da73a8e029f0825f39b74a06d201bfaa2e55142a/charset_normalizer-3.4.5-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:a2aecdb364b8a1802afdc7f9327d55dad5366bc97d8502d0f5854e50712dbc5f", size = 189688, upload-time = "2026-03-06T06:02:02.857Z" },
    { url = "https://files.pythonhosted.org/packages/d0/88/152745c5166437687028027dc080e2daed6fe11cfa95a22f4602591c42db/charset_normalizer-3.4.5-cp314-cp314-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:a66aa5022bf81ab4b1bebfb009db4fd68e0c6d4307a1ce5ef6a26e5878dfc9e4", size = 206833, upload-time = "2026-03-06T06:02:05.127Z" },
    { url = "https://files.pythonhosted.org/packages/cb/0f/ebc15c8b02af2f19be9678d6eed115feeeccc45ce1f4b098d986c13e8769/charset_normalizer-3.4.5-cp314-cp314-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:d77f97e515688bd615c1d1f795d540f32542d514242067adcb8ef532504cb9ee", size = 202879, upload-time = "2026-03-06T06:02:06.446Z" },
    { url = "https://files.pythonhosted.org/packages/38/9c/71336bff6934418dc8d1e8a1644176ac9088068bc571da612767619c97b3/charset_normalizer-3.4.5-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:01a1ed54b953303ca7e310fafe0fe347aab348bd81834a0bcd602eb538f89d66", size = 195764, upload-time = "2026-03-06T06:02:08.763Z" },
    { url = "https://files.pythonhosted.org/packages/b7/95/ce92fde4f98615661871bc282a856cf9b8a15f686ba0af012984660d480b/charset_normalizer-3.4.5-cp314-cp314-manylinux_2_31_armv7l.whl", hash = "sha256:b2d37d78297b39a9eb9eb92c0f6df98c706467282055419df141389b23f93362", size = 183728, upload-time = "2026-03-06T06:02:10.137Z" },
    { url = "https://files.pythonhosted.org/packages/1c/e7/f5b4588d94e747ce45ae680f0f242bc2d98dbd4eccfab73e6160b6893893/charset_normalizer-3.4.5-cp314-cp314-manylinux_2_31_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:e71bbb595973622b817c042bd943c3f3667e9c9983ce3d205f973f486fec98a7", size = 192937, upload-time = "2026-03-06T06:02:11.663Z" },
    { url = "https://files.pythonhosted.org/packages/f9/29/9d94ed6b929bf9f48bf6ede6e7474576499f07c4c5e878fb186083622716/charset_normalizer-3.4.5-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:4cd966c2559f501c6fd69294d082c2934c8dd4719deb32c22961a5ac6db0df1d", size = 192040, upload-time = "2026-03-06T06:02:13.489Z" },
    { url = "https://files.pythonhosted.org/packages/15/d2/1a093a1cf827957f9445f2fe7298bcc16f8fc5e05c1ed2ad1af0b239035e/charset_normalizer-3.4.5-cp314-cp314-musllinux_1_2_armv7l.whl", hash = "sha256:d5e52d127045d6ae01a1e821acfad2f3a1866c54d0e837828538fabe8d9d1bd6", size = 184107, upload-time = "2026-03-06T06:02:14.83Z" },
    { url = "https://files.pythonhosted.org/packages/0f/7d/82068ce16bd36135df7b97f6333c5d808b94e01d4599a682e2337ed5fd14/charset_normalizer-3.4.5-cp314-cp314-musllinux_1_2_ppc64le.whl", hash = "sha256:30a2b1a48478c3428d047ed9690d57c23038dac838a87ad624c85c0a78ebeb39", size = 208310, upload-time = "2026-03-06T06:02:16.165Z" },
    { url = "https://files.pythonhosted.org/packages/84/4e/4dfb52307bb6af4a5c9e73e482d171b81d36f522b21ccd28a49656baa680/charset_normalizer-3.4.5-cp314-cp314-musllinux_1_2_riscv64.whl", hash = "sha256:d8ed79b8f6372ca4254955005830fd61c1ccdd8c0fac6603e2c145c61dd95db6", size = 192918, upload-time = "2026-03-06T06:02:18.144Z" },
    { url = "https://files.pythonhosted.org/packages/08/a4/159ff7da662cf7201502ca89980b8f06acf3e887b278956646a8aeb178ab/charset_normalizer-3.4.5-cp314-cp314-musllinux_1_2_s390x.whl", hash = "sha256:c5af897b45fa606b12464ccbe0014bbf8c09191e0a66aab6aa9d5cf6e77e0c94", size = 204615, upload-time = "2026-03-06T06:02:19.821Z" },
    { url = "https://files.pythonhosted.org/packages/d6/62/0dd6172203cb6b429ffffc9935001fde42e5250d57f07b0c28c6046deb6b/charset_normalizer-3.4.5-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:1088345bcc93c58d8d8f3d783eca4a6e7a7752bbff26c3eee7e73c597c191c2e", size = 197784, upload-time = "2026-03-06T06:02:21.86Z" },
    { url = "https://files.pythonhosted.org/packages/c7/5e/1aab5cb737039b9c59e63627dc8bbc0d02562a14f831cc450e5f91d84ce1/charset_normalizer-3.4.5-cp314-cp314-win32.whl", hash = "sha256:ee57b926940ba00bca7ba7041e665cc956e55ef482f851b9b65acb20d867e7a2", size = 133009, upload-time = "2026-03-06T06:02:23.289Z" },
    { url = "https://files.pythonhosted.org/packages/40/65/e7c6c77d7aaa4c0d7974f2e403e17f0ed2cb0fc135f77d686b916bf1eead/charset_normalizer-3.4.5-cp314-cp314-win_amd64.whl", hash = "sha256:4481e6da1830c8a1cc0b746b47f603b653dadb690bcd851d039ffaefe70533aa", size = 143511, upload-time = "2026-03-06T06:02:26.195Z" },
    { url = "https://files.pythonhosted.org/packages/ba/91/52b0841c71f152f563b8e072896c14e3d83b195c188b338d3cc2e582d1d4/charset_normalizer-3.4.5-cp314-cp314-win_arm64.whl", hash = "sha256:97ab7787092eb9b50fb47fa04f24c75b768a606af1bcba1957f07f128a7219e4", size = 133775, upload-time = "2026-03-06T06:02:27.473Z" },
    { url = "https://files.pythonhosted.org/packages/c5/60/3a621758945513adfd4db86827a5bafcc615f913dbd0b4c2ed64a65731be/charset_normalizer-3.4.5-py3-none-any.whl", hash = "sha256:9db5e3fcdcee89a78c04dffb3fe33c79f77bd741a624946db2591c81b2fc85b0", size = 55455, upload-time = "2026-03-06T06:03:17.827Z" },
]

[[package]]
name = "click"
version = "8.3.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/3d/fa/656b739db8587d7b5dfa22e22ed02566950fbfbcdc20311993483657a5c0/click-8.3.1.tar.gz", hash = "sha256:12ff4785d337a1bb490bb7e9c2b1ee5da3112e94a8622f26a6c77f5d2fc6842a", size = 295065, upload-time = "2025-11-15T20:45:42.706Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/98/78/01c019cdb5d6498122777c1a43056ebb3ebfeef2076d9d026bfe15583b2b/click-8.3.1-py3-none-any.whl", hash = "sha256:981153a64e25f12d547d3426c367a4857371575ee7ad18df2a6183ab0545b2a6", size = 108274, upload-time = "2025-11-15T20:45:41.139Z" },
]

[[package]]
name = "colorama"
version = "0.4.6"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/d8/53/6f443c9a4a8358a93a6792e2acffb9d9d5cb0a5cfd8802644b7b1c9a02e4/colorama-0.4.6.tar.gz", hash = "sha256:08695f5cb7ed6e0531a20572697297273c47b8cae5a63ffc6d6ed5c201be6e44", size = 27697, upload-time = "2022-10-25T02:36:22.414Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d1/d6/3965ed04c63042e047cb6a3e6ed1a63a35087b6a609aa3a15ed8ac56c221/colorama-0.4.6-py2.py3-none-any.whl", hash = "sha256:4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6", size = 25335, upload-time = "2022-10-25T02:36:20.889Z" },
]

[[package]]
name = "fastapi"
version = "0.135.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "annotated-doc" },
    { name = "pydantic" },
    { name = "starlette" },
    { name = "typing-extensions" },
    { name = "typing-inspection" },
]
sdist = { url = "https://files.pythonhosted.org/packages/e7/7b/f8e0211e9380f7195ba3f3d40c292594fd81ba8ec4629e3854c353aaca45/fastapi-0.135.1.tar.gz", hash = "sha256:d04115b508d936d254cea545b7312ecaa58a7b3a0f84952535b4c9afae7668cd", size = 394962, upload-time = "2026-03-01T18:18:29.369Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e4/72/42e900510195b23a56bde950d26a51f8b723846bfcaa0286e90287f0422b/fastapi-0.135.1-py3-none-any.whl", hash = "sha256:46e2fc5745924b7c840f71ddd277382af29ce1cdb7d5eab5bf697e3fb9999c9e", size = 116999, upload-time = "2026-03-01T18:18:30.831Z" },
]

[[package]]
name = "fastembed"
version = "0.7.4"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "huggingface-hub" },
    { name = "loguru" },
    { name = "mmh3" },
    { name = "numpy" },
    { name = "onnxruntime" },
    { name = "pillow" },
    { name = "py-rust-stemmers" },
    { name = "requests" },
    { name = "tokenizers" },
    { name = "tqdm" },
]
sdist = { url = "https://files.pythonhosted.org/packages/4c/c2/9c708680de1b54480161e0505f9d6d3d8eb47a1dc1a1f7f3c5106ba355d2/fastembed-0.7.4.tar.gz", hash = "sha256:8b8a4ea860ca295002f4754e8f5820a636e1065a9444959e18d5988d7f27093b", size = 68807, upload-time = "2025-12-05T12:08:10.447Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/10/3b/8da01492bc8b69184257d0c951bf0e77aec8ce110f06d8ce16c6ed9084f7/fastembed-0.7.4-py3-none-any.whl", hash = "sha256:79250a775f70bd6addb0e054204df042b5029ecae501e40e5bbd08e75844ad83", size = 108491, upload-time = "2025-12-05T12:08:09.059Z" },
]

[[package]]
name = "filelock"
version = "3.25.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/94/b8/00651a0f559862f3bb7d6f7477b192afe3f583cc5e26403b44e59a55ab34/filelock-3.25.2.tar.gz", hash = "sha256:b64ece2b38f4ca29dd3e810287aa8c48182bbecd1ae6e9ae126c9b35f1382694", size = 40480, upload-time = "2026-03-11T20:45:38.487Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/a4/a5/842ae8f0c08b61d6484b52f99a03510a3a72d23141942d216ebe81fefbce/filelock-3.25.2-py3-none-any.whl", hash = "sha256:ca8afb0da15f229774c9ad1b455ed96e85a81373065fb10446672f64444ddf70", size = 26759, upload-time = "2026-03-11T20:45:37.437Z" },
]

[[package]]
name = "flatbuffers"
version = "25.12.19"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e8/2d/d2a548598be01649e2d46231d151a6c56d10b964d94043a335ae56ea2d92/flatbuffers-25.12.19-py2.py3-none-any.whl", hash = "sha256:7634f50c427838bb021c2d66a3d1168e9d199b0607e6329399f04846d42e20b4", size = 26661, upload-time = "2025-12-19T23:16:13.622Z" },
]

[[package]]
name = "fsspec"
version = "2026.2.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/51/7c/f60c259dcbf4f0c47cc4ddb8f7720d2dcdc8888c8e5ad84c73ea4531cc5b/fsspec-2026.2.0.tar.gz", hash = "sha256:6544e34b16869f5aacd5b90bdf1a71acb37792ea3ddf6125ee69a22a53fb8bff", size = 313441, upload-time = "2026-02-05T21:50:53.743Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e6/ab/fb21f4c939bb440104cc2b396d3be1d9b7a9fd3c6c2a53d98c45b3d7c954/fsspec-2026.2.0-py3-none-any.whl", hash = "sha256:98de475b5cb3bd66bedd5c4679e87b4fdfe1a3bf4d707b151b3c07e58c9a2437", size = 202505, upload-time = "2026-02-05T21:50:51.819Z" },
]

[[package]]
name = "grpcio"
version = "1.78.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/06/8a/3d098f35c143a89520e568e6539cc098fcd294495910e359889ce8741c84/grpcio-1.78.0.tar.gz", hash = "sha256:7382b95189546f375c174f53a5fa873cef91c4b8005faa05cc5b3beea9c4f1c5", size = 12852416, upload-time = "2026-02-06T09:57:18.093Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/86/c7/d0b780a29b0837bf4ca9580904dfb275c1fc321ded7897d620af7047ec57/grpcio-1.78.0-cp311-cp311-linux_armv7l.whl", hash = "sha256:2777b783f6c13b92bd7b716667452c329eefd646bfb3f2e9dabea2e05dbd34f6", size = 5951525, upload-time = "2026-02-06T09:55:01.989Z" },
    { url = "https://files.pythonhosted.org/packages/c5/b1/96920bf2ee61df85a9503cb6f733fe711c0ff321a5a697d791b075673281/grpcio-1.78.0-cp311-cp311-macosx_11_0_universal2.whl", hash = "sha256:9dca934f24c732750389ce49d638069c3892ad065df86cb465b3fa3012b70c9e", size = 11830418, upload-time = "2026-02-06T09:55:04.462Z" },
    { url = "https://files.pythonhosted.org/packages/83/0c/7c1528f098aeb75a97de2bae18c530f56959fb7ad6c882db45d9884d6edc/grpcio-1.78.0-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:459ab414b35f4496138d0ecd735fed26f1318af5e52cb1efbc82a09f0d5aa911", size = 6524477, upload-time = "2026-02-06T09:55:07.111Z" },
    { url = "https://files.pythonhosted.org/packages/8d/52/e7c1f3688f949058e19a011c4e0dec973da3d0ae5e033909677f967ae1f4/grpcio-1.78.0-cp311-cp311-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:082653eecbdf290e6e3e2c276ab2c54b9e7c299e07f4221872380312d8cf395e", size = 7198266, upload-time = "2026-02-06T09:55:10.016Z" },
    { url = "https://files.pythonhosted.org/packages/e5/61/8ac32517c1e856677282c34f2e7812d6c328fa02b8f4067ab80e77fdc9c9/grpcio-1.78.0-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:85f93781028ec63f383f6bc90db785a016319c561cc11151fbb7b34e0d012303", size = 6730552, upload-time = "2026-02-06T09:55:12.207Z" },
    { url = "https://files.pythonhosted.org/packages/bd/98/b8ee0158199250220734f620b12e4a345955ac7329cfd908d0bf0fda77f0/grpcio-1.78.0-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:f12857d24d98441af6a1d5c87442d624411db486f7ba12550b07788f74b67b04", size = 7304296, upload-time = "2026-02-06T09:55:15.044Z" },
    { url = "https://files.pythonhosted.org/packages/bd/0f/7b72762e0d8840b58032a56fdbd02b78fc645b9fa993d71abf04edbc54f4/grpcio-1.78.0-cp311-cp311-musllinux_1_2_i686.whl", hash = "sha256:5397fff416b79e4b284959642a4e95ac4b0f1ece82c9993658e0e477d40551ec", size = 8288298, upload-time = "2026-02-06T09:55:17.276Z" },
    { url = "https://files.pythonhosted.org/packages/24/ae/ae4ce56bc5bb5caa3a486d60f5f6083ac3469228faa734362487176c15c5/grpcio-1.78.0-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:fbe6e89c7ffb48518384068321621b2a69cab509f58e40e4399fdd378fa6d074", size = 7730953, upload-time = "2026-02-06T09:55:19.545Z" },
    { url = "https://files.pythonhosted.org/packages/b5/6e/8052e3a28eb6a820c372b2eb4b5e32d195c661e137d3eca94d534a4cfd8a/grpcio-1.78.0-cp311-cp311-win32.whl", hash = "sha256:6092beabe1966a3229f599d7088b38dfc8ffa1608b5b5cdda31e591e6500f856", size = 4076503, upload-time = "2026-02-06T09:55:21.521Z" },
    { url = "https://files.pythonhosted.org/packages/08/62/f22c98c5265dfad327251fa2f840b591b1df5f5e15d88b19c18c86965b27/grpcio-1.78.0-cp311-cp311-win_amd64.whl", hash = "sha256:1afa62af6e23f88629f2b29ec9e52ec7c65a7176c1e0a83292b93c76ca882558", size = 4799767, upload-time = "2026-02-06T09:55:24.107Z" },
    { url = "https://files.pythonhosted.org/packages/4e/f4/7384ed0178203d6074446b3c4f46c90a22ddf7ae0b3aee521627f54cfc2a/grpcio-1.78.0-cp312-cp312-linux_armv7l.whl", hash = "sha256:f9ab915a267fc47c7e88c387a3a28325b58c898e23d4995f765728f4e3dedb97", size = 5913985, upload-time = "2026-02-06T09:55:26.832Z" },
    { url = "https://files.pythonhosted.org/packages/81/ed/be1caa25f06594463f685b3790b320f18aea49b33166f4141bfdc2bfb236/grpcio-1.78.0-cp312-cp312-macosx_11_0_universal2.whl", hash = "sha256:3f8904a8165ab21e07e58bf3e30a73f4dffc7a1e0dbc32d51c61b5360d26f43e", size = 11811853, upload-time = "2026-02-06T09:55:29.224Z" },
    { url = "https://files.pythonhosted.org/packages/24/a7/f06d151afc4e64b7e3cc3e872d331d011c279aaab02831e40a81c691fb65/grpcio-1.78.0-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:859b13906ce098c0b493af92142ad051bf64c7870fa58a123911c88606714996", size = 6475766, upload-time = "2026-02-06T09:55:31.825Z" },
    { url = "https://files.pythonhosted.org/packages/8a/a8/4482922da832ec0082d0f2cc3a10976d84a7424707f25780b82814aafc0a/grpcio-1.78.0-cp312-cp312-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:b2342d87af32790f934a79c3112641e7b27d63c261b8b4395350dad43eff1dc7", size = 7170027, upload-time = "2026-02-06T09:55:34.7Z" },
    { url = "https://files.pythonhosted.org/packages/54/bf/f4a3b9693e35d25b24b0b39fa46d7d8a3c439e0a3036c3451764678fec20/grpcio-1.78.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:12a771591ae40bc65ba67048fa52ef4f0e6db8279e595fd349f9dfddeef571f9", size = 6690766, upload-time = "2026-02-06T09:55:36.902Z" },
    { url = "https://files.pythonhosted.org/packages/c7/b9/521875265cc99fe5ad4c5a17010018085cae2810a928bf15ebe7d8bcd9cc/grpcio-1.78.0-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:185dea0d5260cbb2d224c507bf2a5444d5abbb1fa3594c1ed7e4c709d5eb8383", size = 7266161, upload-time = "2026-02-06T09:55:39.824Z" },
    { url = "https://files.pythonhosted.org/packages/05/86/296a82844fd40a4ad4a95f100b55044b4f817dece732bf686aea1a284147/grpcio-1.78.0-cp312-cp312-musllinux_1_2_i686.whl", hash = "sha256:51b13f9aed9d59ee389ad666b8c2214cc87b5de258fa712f9ab05f922e3896c6", size = 8253303, upload-time = "2026-02-06T09:55:42.353Z" },
    { url = "https://files.pythonhosted.org/packages/f3/e4/ea3c0caf5468537f27ad5aab92b681ed7cc0ef5f8c9196d3fd42c8c2286b/grpcio-1.78.0-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:fd5f135b1bd58ab088930b3c613455796dfa0393626a6972663ccdda5b4ac6ce", size = 7698222, upload-time = "2026-02-06T09:55:44.629Z" },
    { url = "https://files.pythonhosted.org/packages/d7/47/7f05f81e4bb6b831e93271fb12fd52ba7b319b5402cbc101d588f435df00/grpcio-1.78.0-cp312-cp312-win32.whl", hash = "sha256:94309f498bcc07e5a7d16089ab984d42ad96af1d94b5a4eb966a266d9fcabf68", size = 4066123, upload-time = "2026-02-06T09:55:47.644Z" },
    { url = "https://files.pythonhosted.org/packages/ad/e7/d6914822c88aa2974dbbd10903d801a28a19ce9cd8bad7e694cbbcf61528/grpcio-1.78.0-cp312-cp312-win_amd64.whl", hash = "sha256:9566fe4ababbb2610c39190791e5b829869351d14369603702e890ef3ad2d06e", size = 4797657, upload-time = "2026-02-06T09:55:49.86Z" },
    { url = "https://files.pythonhosted.org/packages/05/a9/8f75894993895f361ed8636cd9237f4ab39ef87fd30db17467235ed1c045/grpcio-1.78.0-cp313-cp313-linux_armv7l.whl", hash = "sha256:ce3a90455492bf8bfa38e56fbbe1dbd4f872a3d8eeaf7337dc3b1c8aa28c271b", size = 5920143, upload-time = "2026-02-06T09:55:52.035Z" },
    { url = "https://files.pythonhosted.org/packages/55/06/0b78408e938ac424100100fd081189451b472236e8a3a1f6500390dc4954/grpcio-1.78.0-cp313-cp313-macosx_11_0_universal2.whl", hash = "sha256:2bf5e2e163b356978b23652c4818ce4759d40f4712ee9ec5a83c4be6f8c23a3a", size = 11803926, upload-time = "2026-02-06T09:55:55.494Z" },
    { url = "https://files.pythonhosted.org/packages/88/93/b59fe7832ff6ae3c78b813ea43dac60e295fa03606d14d89d2e0ec29f4f3/grpcio-1.78.0-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:8f2ac84905d12918e4e55a16da17939eb63e433dc11b677267c35568aa63fc84", size = 6478628, upload-time = "2026-02-06T09:55:58.533Z" },
    { url = "https://files.pythonhosted.org/packages/ed/df/e67e3734527f9926b7d9c0dde6cd998d1d26850c3ed8eeec81297967ac67/grpcio-1.78.0-cp313-cp313-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:b58f37edab4a3881bc6c9bca52670610e0c9ca14e2ea3cf9debf185b870457fb", size = 7173574, upload-time = "2026-02-06T09:56:01.786Z" },
    { url = "https://files.pythonhosted.org/packages/a6/62/cc03fffb07bfba982a9ec097b164e8835546980aec25ecfa5f9c1a47e022/grpcio-1.78.0-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:735e38e176a88ce41840c21bb49098ab66177c64c82426e24e0082500cc68af5", size = 6692639, upload-time = "2026-02-06T09:56:04.529Z" },
    { url = "https://files.pythonhosted.org/packages/bf/9a/289c32e301b85bdb67d7ec68b752155e674ee3ba2173a1858f118e399ef3/grpcio-1.78.0-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:2045397e63a7a0ee7957c25f7dbb36ddc110e0cfb418403d110c0a7a68a844e9", size = 7268838, upload-time = "2026-02-06T09:56:08.397Z" },
    { url = "https://files.pythonhosted.org/packages/0e/79/1be93f32add280461fa4773880196572563e9c8510861ac2da0ea0f892b6/grpcio-1.78.0-cp313-cp313-musllinux_1_2_i686.whl", hash = "sha256:a9f136fbafe7ccf4ac7e8e0c28b31066e810be52d6e344ef954a3a70234e1702", size = 8251878, upload-time = "2026-02-06T09:56:10.914Z" },
    { url = "https://files.pythonhosted.org/packages/65/65/793f8e95296ab92e4164593674ae6291b204bb5f67f9d4a711489cd30ffa/grpcio-1.78.0-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:748b6138585379c737adc08aeffd21222abbda1a86a0dca2a39682feb9196c20", size = 7695412, upload-time = "2026-02-06T09:56:13.593Z" },
    { url = "https://files.pythonhosted.org/packages/1c/9f/1e233fe697ecc82845942c2822ed06bb522e70d6771c28d5528e4c50f6a4/grpcio-1.78.0-cp313-cp313-win32.whl", hash = "sha256:271c73e6e5676afe4fc52907686670c7cea22ab2310b76a59b678403ed40d670", size = 4064899, upload-time = "2026-02-06T09:56:15.601Z" },
    { url = "https://files.pythonhosted.org/packages/4d/27/d86b89e36de8a951501fb06a0f38df19853210f341d0b28f83f4aa0ffa08/grpcio-1.78.0-cp313-cp313-win_amd64.whl", hash = "sha256:f2d4e43ee362adfc05994ed479334d5a451ab7bc3f3fee1b796b8ca66895acb4", size = 4797393, upload-time = "2026-02-06T09:56:17.882Z" },
    { url = "https://files.pythonhosted.org/packages/29/f2/b56e43e3c968bfe822fa6ce5bca10d5c723aa40875b48791ce1029bb78c7/grpcio-1.78.0-cp314-cp314-linux_armv7l.whl", hash = "sha256:e87cbc002b6f440482b3519e36e1313eb5443e9e9e73d6a52d43bd2004fcfd8e", size = 5920591, upload-time = "2026-02-06T09:56:20.758Z" },
    { url = "https://files.pythonhosted.org/packages/5d/81/1f3b65bd30c334167bfa8b0d23300a44e2725ce39bba5b76a2460d85f745/grpcio-1.78.0-cp314-cp314-macosx_11_0_universal2.whl", hash = "sha256:c41bc64626db62e72afec66b0c8a0da76491510015417c127bfc53b2fe6d7f7f", size = 11813685, upload-time = "2026-02-06T09:56:24.315Z" },
    { url = "https://files.pythonhosted.org/packages/0e/1c/bbe2f8216a5bd3036119c544d63c2e592bdf4a8ec6e4a1867592f4586b26/grpcio-1.78.0-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:8dfffba826efcf366b1e3ccc37e67afe676f290e13a3b48d31a46739f80a8724", size = 6487803, upload-time = "2026-02-06T09:56:27.367Z" },
    { url = "https://files.pythonhosted.org/packages/16/5c/a6b2419723ea7ddce6308259a55e8e7593d88464ce8db9f4aa857aba96fa/grpcio-1.78.0-cp314-cp314-manylinux2014_i686.manylinux_2_17_i686.whl", hash = "sha256:74be1268d1439eaaf552c698cdb11cd594f0c49295ae6bb72c34ee31abbe611b", size = 7173206, upload-time = "2026-02-06T09:56:29.876Z" },
    { url = "https://files.pythonhosted.org/packages/df/1e/b8801345629a415ea7e26c83d75eb5dbe91b07ffe5210cc517348a8d4218/grpcio-1.78.0-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:be63c88b32e6c0f1429f1398ca5c09bc64b0d80950c8bb7807d7d7fb36fb84c7", size = 6693826, upload-time = "2026-02-06T09:56:32.305Z" },
    { url = "https://files.pythonhosted.org/packages/34/84/0de28eac0377742679a510784f049738a80424b17287739fc47d63c2439e/grpcio-1.78.0-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:3c586ac70e855c721bda8f548d38c3ca66ac791dc49b66a8281a1f99db85e452", size = 7277897, upload-time = "2026-02-06T09:56:34.915Z" },
    { url = "https://files.pythonhosted.org/packages/ca/9c/ad8685cfe20559a9edb66f735afdcb2b7d3de69b13666fdfc542e1916ebd/grpcio-1.78.0-cp314-cp314-musllinux_1_2_i686.whl", hash = "sha256:35eb275bf1751d2ffbd8f57cdbc46058e857cf3971041521b78b7db94bdaf127", size = 8252404, upload-time = "2026-02-06T09:56:37.553Z" },
    { url = "https://files.pythonhosted.org/packages/3c/05/33a7a4985586f27e1de4803887c417ec7ced145ebd069bc38a9607059e2b/grpcio-1.78.0-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:207db540302c884b8848036b80db352a832b99dfdf41db1eb554c2c2c7800f65", size = 7696837, upload-time = "2026-02-06T09:56:40.173Z" },
    { url = "https://files.pythonhosted.org/packages/73/77/7382241caf88729b106e49e7d18e3116216c778e6a7e833826eb96de22f7/grpcio-1.78.0-cp314-cp314-win32.whl", hash = "sha256:57bab6deef2f4f1ca76cc04565df38dc5713ae6c17de690721bdf30cb1e0545c", size = 4142439, upload-time = "2026-02-06T09:56:43.258Z" },
    { url = "https://files.pythonhosted.org/packages/48/b2/b096ccce418882fbfda4f7496f9357aaa9a5af1896a9a7f60d9f2b275a06/grpcio-1.78.0-cp314-cp314-win_amd64.whl", hash = "sha256:dce09d6116df20a96acfdbf85e4866258c3758180e8c49845d6ba8248b6d0bbb", size = 4929852, upload-time = "2026-02-06T09:56:45.885Z" },
]

[[package]]
name = "h11"
version = "0.16.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/01/ee/02a2c011bdab74c6fb3c75474d40b3052059d95df7e73351460c8588d963/h11-0.16.0.tar.gz", hash = "sha256:4e35b956cf45792e4caa5885e69fba00bdbc6ffafbfa020300e549b208ee5ff1", size = 101250, upload-time = "2025-04-24T03:35:25.427Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/04/4b/29cac41a4d98d144bf5f6d33995617b185d14b22401f75ca86f384e87ff1/h11-0.16.0-py3-none-any.whl", hash = "sha256:63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86", size = 37515, upload-time = "2025-04-24T03:35:24.344Z" },
]

[[package]]
name = "h2"
version = "4.3.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "hpack" },
    { name = "hyperframe" },
]
sdist = { url = "https://files.pythonhosted.org/packages/1d/17/afa56379f94ad0fe8defd37d6eb3f89a25404ffc71d4d848893d270325fc/h2-4.3.0.tar.gz", hash = "sha256:6c59efe4323fa18b47a632221a1888bd7fde6249819beda254aeca909f221bf1", size = 2152026, upload-time = "2025-08-23T18:12:19.778Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/69/b2/119f6e6dcbd96f9069ce9a2665e0146588dc9f88f29549711853645e736a/h2-4.3.0-py3-none-any.whl", hash = "sha256:c438f029a25f7945c69e0ccf0fb951dc3f73a5f6412981daee861431b70e2bdd", size = 61779, upload-time = "2025-08-23T18:12:17.779Z" },
]

[[package]]
name = "hf-xet"
version = "1.4.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/09/08/23c84a26716382c89151b5b447b4beb19e3345f3a93d3b73009a71a57ad3/hf_xet-1.4.2.tar.gz", hash = "sha256:b7457b6b482d9e0743bd116363239b1fa904a5e65deede350fbc0c4ea67c71ea", size = 672357, upload-time = "2026-03-13T06:58:51.077Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/18/06/e8cf74c3c48e5485c7acc5a990d0d8516cdfb5fdf80f799174f1287cc1b5/hf_xet-1.4.2-cp313-cp313t-macosx_10_12_x86_64.whl", hash = "sha256:ac8202ae1e664b2c15cdfc7298cbb25e80301ae596d602ef7870099a126fcad4", size = 3796125, upload-time = "2026-03-13T06:58:33.177Z" },
    { url = "https://files.pythonhosted.org/packages/66/d4/b73ebab01cbf60777323b7de9ef05550790451eb5172a220d6b9845385ec/hf_xet-1.4.2-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:6d2f8ee39fa9fba9af929f8c0d0482f8ee6e209179ad14a909b6ad78ffcb7c81", size = 3555985, upload-time = "2026-03-13T06:58:31.797Z" },
    { url = "https://files.pythonhosted.org/packages/ff/e7/ded6d1bd041c3f2bca9e913a0091adfe32371988e047dd3a68a2463c15a2/hf_xet-1.4.2-cp313-cp313t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:4642a6cf249c09da8c1f87fe50b24b2a3450b235bf8adb55700b52f0ea6e2eb6", size = 4212085, upload-time = "2026-03-13T06:58:24.323Z" },
    { url = "https://files.pythonhosted.org/packages/97/c1/a0a44d1f98934f7bdf17f7a915b934f9fca44bb826628c553589900f6df8/hf_xet-1.4.2-cp313-cp313t-manylinux_2_28_aarch64.whl", hash = "sha256:769431385e746c92dc05492dde6f687d304584b89c33d79def8367ace06cb555", size = 3988266, upload-time = "2026-03-13T06:58:22.887Z" },
    { url = "https://files.pythonhosted.org/packages/7a/82/be713b439060e7d1f1d93543c8053d4ef2fe7e6922c5b31642eaa26f3c4b/hf_xet-1.4.2-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:c9dd1c1bc4cc56168f81939b0e05b4c36dd2d28c13dc1364b17af89aa0082496", size = 4188513, upload-time = "2026-03-13T06:58:40.858Z" },
    { url = "https://files.pythonhosted.org/packages/21/a6/cbd4188b22abd80ebd0edbb2b3e87f2633e958983519980815fb8314eae5/hf_xet-1.4.2-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:fca58a2ae4e6f6755cc971ac6fcdf777ea9284d7e540e350bb000813b9a3008d", size = 4428287, upload-time = "2026-03-13T06:58:42.601Z" },
    { url = "https://files.pythonhosted.org/packages/b2/4e/84e45b25e2e3e903ed3db68d7eafa96dae9a1d1f6d0e7fc85120347a852f/hf_xet-1.4.2-cp313-cp313t-win_amd64.whl", hash = "sha256:163aab46854ccae0ab6a786f8edecbbfbaa38fcaa0184db6feceebf7000c93c0", size = 3665574, upload-time = "2026-03-13T06:58:53.881Z" },
    { url = "https://files.pythonhosted.org/packages/ee/71/c5ac2b9a7ae39c14e91973035286e73911c31980fe44e7b1d03730c00adc/hf_xet-1.4.2-cp313-cp313t-win_arm64.whl", hash = "sha256:09b138422ecbe50fd0c84d4da5ff537d27d487d3607183cd10e3e53f05188e82", size = 3528760, upload-time = "2026-03-13T06:58:52.187Z" },
    { url = "https://files.pythonhosted.org/packages/1e/0f/fcd2504015eab26358d8f0f232a1aed6b8d363a011adef83fe130bff88f7/hf_xet-1.4.2-cp314-cp314t-macosx_10_12_x86_64.whl", hash = "sha256:949dcf88b484bb9d9276ca83f6599e4aa03d493c08fc168c124ad10b2e6f75d7", size = 3796493, upload-time = "2026-03-13T06:58:39.267Z" },
    { url = "https://files.pythonhosted.org/packages/82/56/19c25105ff81731ca6d55a188b5de2aa99d7a2644c7aa9de1810d5d3b726/hf_xet-1.4.2-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:41659966020d59eb9559c57de2cde8128b706a26a64c60f0531fa2318f409418", size = 3555797, upload-time = "2026-03-13T06:58:37.546Z" },
    { url = "https://files.pythonhosted.org/packages/bf/e3/8933c073186849b5e06762aa89847991d913d10a95d1603eb7f2c3834086/hf_xet-1.4.2-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:5c588e21d80010119458dd5d02a69093f0d115d84e3467efe71ffb2c67c19146", size = 4212127, upload-time = "2026-03-13T06:58:30.539Z" },
    { url = "https://files.pythonhosted.org/packages/eb/01/f89ebba4e369b4ed699dcb60d3152753870996f41c6d22d3d7cac01310e1/hf_xet-1.4.2-cp314-cp314t-manylinux_2_28_aarch64.whl", hash = "sha256:a296744d771a8621ad1d50c098d7ab975d599800dae6d48528ba3944e5001ba0", size = 3987788, upload-time = "2026-03-13T06:58:29.139Z" },
    { url = "https://files.pythonhosted.org/packages/84/4d/8a53e5ffbc2cc33bbf755382ac1552c6d9af13f623ed125fe67cc3e6772f/hf_xet-1.4.2-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:f563f7efe49588b7d0629d18d36f46d1658fe7e08dce3fa3d6526e1c98315e2d", size = 4188315, upload-time = "2026-03-13T06:58:48.017Z" },
    { url = "https://files.pythonhosted.org/packages/d1/b8/b7a1c1b5592254bd67050632ebbc1b42cc48588bf4757cb03c2ef87e704a/hf_xet-1.4.2-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:5b2e0132c56d7ee1bf55bdb638c4b62e7106f6ac74f0b786fed499d5548c5570", size = 4428306, upload-time = "2026-03-13T06:58:49.502Z" },
    { url = "https://files.pythonhosted.org/packages/a0/0c/40779e45b20e11c7c5821a94135e0207080d6b3d76e7b78ccb413c6f839b/hf_xet-1.4.2-cp314-cp314t-win_amd64.whl", hash = "sha256:2f45c712c2fa1215713db10df6ac84b49d0e1c393465440e9cb1de73ecf7bbf6", size = 3665826, upload-time = "2026-03-13T06:58:59.88Z" },
    { url = "https://files.pythonhosted.org/packages/51/4c/e2688c8ad1760d7c30f7c429c79f35f825932581bc7c9ec811436d2f21a0/hf_xet-1.4.2-cp314-cp314t-win_arm64.whl", hash = "sha256:6d53df40616f7168abfccff100d232e9d460583b9d86fa4912c24845f192f2b8", size = 3529113, upload-time = "2026-03-13T06:58:58.491Z" },
    { url = "https://files.pythonhosted.org/packages/b4/86/b40b83a2ff03ef05c4478d2672b1fc2b9683ff870e2b25f4f3af240f2e7b/hf_xet-1.4.2-cp37-abi3-macosx_10_12_x86_64.whl", hash = "sha256:71f02d6e4cdd07f344f6844845d78518cc7186bd2bc52d37c3b73dc26a3b0bc5", size = 3800339, upload-time = "2026-03-13T06:58:36.245Z" },
    { url = "https://files.pythonhosted.org/packages/64/2e/af4475c32b4378b0e92a587adb1aa3ec53e3450fd3e5fe0372a874531c00/hf_xet-1.4.2-cp37-abi3-macosx_11_0_arm64.whl", hash = "sha256:e9b38d876e94d4bdcf650778d6ebbaa791dd28de08db9736c43faff06ede1b5a", size = 3559664, upload-time = "2026-03-13T06:58:34.787Z" },
    { url = "https://files.pythonhosted.org/packages/3c/4c/781267da3188db679e601de18112021a5cb16506fe86b246e22c5401a9c4/hf_xet-1.4.2-cp37-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:77e8c180b7ef12d8a96739a4e1e558847002afe9ea63b6f6358b2271a8bdda1c", size = 4217422, upload-time = "2026-03-13T06:58:27.472Z" },
    { url = "https://files.pythonhosted.org/packages/68/47/d6cf4a39ecf6c7705f887a46f6ef5c8455b44ad9eb0d391aa7e8a2ff7fea/hf_xet-1.4.2-cp37-abi3-manylinux_2_28_aarch64.whl", hash = "sha256:c3b3c6a882016b94b6c210957502ff7877802d0dbda8ad142c8595db8b944271", size = 3992847, upload-time = "2026-03-13T06:58:25.989Z" },
    { url = "https://files.pythonhosted.org/packages/2d/ef/e80815061abff54697239803948abc665c6b1d237102c174f4f7a9a5ffc5/hf_xet-1.4.2-cp37-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:9d9a634cc929cfbaf2e1a50c0e532ae8c78fa98618426769480c58501e8c8ac2", size = 4193843, upload-time = "2026-03-13T06:58:44.59Z" },
    { url = "https://files.pythonhosted.org/packages/54/75/07f6aa680575d9646c4167db6407c41340cbe2357f5654c4e72a1b01ca14/hf_xet-1.4.2-cp37-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:6b0932eb8b10317ea78b7da6bab172b17be03bbcd7809383d8d5abd6a2233e04", size = 4432751, upload-time = "2026-03-13T06:58:46.533Z" },
    { url = "https://files.pythonhosted.org/packages/cd/71/193eabd7e7d4b903c4aa983a215509c6114915a5a237525ec562baddb868/hf_xet-1.4.2-cp37-abi3-win_amd64.whl", hash = "sha256:ad185719fb2e8ac26f88c8100562dbf9dbdcc3d9d2add00faa94b5f106aea53f", size = 3671149, upload-time = "2026-03-13T06:58:57.07Z" },
    { url = "https://files.pythonhosted.org/packages/b4/7e/ccf239da366b37ba7f0b36095450efae4a64980bdc7ec2f51354205fdf39/hf_xet-1.4.2-cp37-abi3-win_arm64.whl", hash = "sha256:32c012286b581f783653e718c1862aea5b9eb140631685bb0c5e7012c8719a87", size = 3533426, upload-time = "2026-03-13T06:58:55.46Z" },
]

[[package]]
name = "hpack"
version = "4.1.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/2c/48/71de9ed269fdae9c8057e5a4c0aa7402e8bb16f2c6e90b3aa53327b113f8/hpack-4.1.0.tar.gz", hash = "sha256:ec5eca154f7056aa06f196a557655c5b009b382873ac8d1e66e79e87535f1dca", size = 51276, upload-time = "2025-01-22T21:44:58.347Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/07/c6/80c95b1b2b94682a72cbdbfb85b81ae2daffa4291fbfa1b1464502ede10d/hpack-4.1.0-py3-none-any.whl", hash = "sha256:157ac792668d995c657d93111f46b4535ed114f0c9c8d672271bbec7eae1b496", size = 34357, upload-time = "2025-01-22T21:44:56.92Z" },
]

[[package]]
name = "httpcore"
version = "1.0.9"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "certifi" },
    { name = "h11" },
]
sdist = { url = "https://files.pythonhosted.org/packages/06/94/82699a10bca87a5556c9c59b5963f2d039dbd239f25bc2a63907a05a14cb/httpcore-1.0.9.tar.gz", hash = "sha256:6e34463af53fd2ab5d807f399a9b45ea31c3dfa2276f15a2c3f00afff6e176e8", size = 85484, upload-time = "2025-04-24T22:06:22.219Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/7e/f5/f66802a942d491edb555dd61e3a9961140fd64c90bce1eafd741609d334d/httpcore-1.0.9-py3-none-any.whl", hash = "sha256:2d400746a40668fc9dec9810239072b40b4484b640a8c38fd654a024c7a1bf55", size = 78784, upload-time = "2025-04-24T22:06:20.566Z" },
]

[[package]]
name = "httpx"
version = "0.28.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "anyio" },
    { name = "certifi" },
    { name = "httpcore" },
    { name = "idna" },
]
sdist = { url = "https://files.pythonhosted.org/packages/b1/df/48c586a5fe32a0f01324ee087459e112ebb7224f646c0b5023f5e79e9956/httpx-0.28.1.tar.gz", hash = "sha256:75e98c5f16b0f35b567856f597f06ff2270a374470a5c2392242528e3e3e42fc", size = 141406, upload-time = "2024-12-06T15:37:23.222Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/2a/39/e50c7c3a983047577ee07d2a9e53faf5a69493943ec3f6a384bdc792deb2/httpx-0.28.1-py3-none-any.whl", hash = "sha256:d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad", size = 73517, upload-time = "2024-12-06T15:37:21.509Z" },
]

[package.optional-dependencies]
http2 = [
    { name = "h2" },
]

[[package]]
name = "huggingface-hub"
version = "1.7.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "filelock" },
    { name = "fsspec" },
    { name = "hf-xet", marker = "platform_machine == 'AMD64' or platform_machine == 'aarch64' or platform_machine == 'amd64' or platform_machine == 'arm64' or platform_machine == 'x86_64'" },
    { name = "httpx" },
    { name = "packaging" },
    { name = "pyyaml" },
    { name = "tqdm" },
    { name = "typer" },
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/b4/a8/94ccc0aec97b996a3a68f3e1fa06a4bd7185dd02bf22bfba794a0ade8440/huggingface_hub-1.7.1.tar.gz", hash = "sha256:be38fe66e9b03c027ad755cb9e4b87ff0303c98acf515b5d579690beb0bf3048", size = 722097, upload-time = "2026-03-13T09:36:07.758Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/6f/75/ca21955d6117a394a482c7862ce96216239d0e3a53133ae8510727a8bcfa/huggingface_hub-1.7.1-py3-none-any.whl", hash = "sha256:38c6cce7419bbde8caac26a45ed22b0cea24152a8961565d70ec21f88752bfaa", size = 616308, upload-time = "2026-03-13T09:36:06.062Z" },
]

[[package]]
name = "hyperframe"
version = "6.1.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/02/e7/94f8232d4a74cc99514c13a9f995811485a6903d48e5d952771ef6322e30/hyperframe-6.1.0.tar.gz", hash = "sha256:f630908a00854a7adeabd6382b43923a4c4cd4b821fcb527e6ab9e15382a3b08", size = 26566, upload-time = "2025-01-22T21:41:49.302Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/48/30/47d0bf6072f7252e6521f3447ccfa40b421b6824517f82854703d0f5a98b/hyperframe-6.1.0-py3-none-any.whl", hash = "sha256:b03380493a519fce58ea5af42e4a42317bf9bd425596f7a0835ffce80f1a42e5", size = 13007, upload-time = "2025-01-22T21:41:47.295Z" },
]

[[package]]
name = "idna"
version = "3.11"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/6f/6d/0703ccc57f3a7233505399edb88de3cbd678da106337b9fcde432b65ed60/idna-3.11.tar.gz", hash = "sha256:795dafcc9c04ed0c1fb032c2aa73654d8e8c5023a7df64a53f39190ada629902", size = 194582, upload-time = "2025-10-12T14:55:20.501Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/0e/61/66938bbb5fc52dbdf84594873d5b51fb1f7c7794e9c0f5bd885f30bc507b/idna-3.11-py3-none-any.whl", hash = "sha256:771a87f49d9defaf64091e6e6fe9c18d4833f140bd19464795bc32d966ca37ea", size = 71008, upload-time = "2025-10-12T14:55:18.883Z" },
]

[[package]]
name = "iniconfig"
version = "2.3.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/72/34/14ca021ce8e5dfedc35312d08ba8bf51fdd999c576889fc2c24cb97f4f10/iniconfig-2.3.0.tar.gz", hash = "sha256:c76315c77db068650d49c5b56314774a7804df16fee4402c1f19d6d15d8c4730", size = 20503, upload-time = "2025-10-18T21:55:43.219Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/cb/b1/3846dd7f199d53cb17f49cba7e651e9ce294d8497c8c150530ed11865bb8/iniconfig-2.3.0-py3-none-any.whl", hash = "sha256:f631c04d2c48c52b84d0d0549c99ff3859c98df65b3101406327ecc7d53fbf12", size = 7484, upload-time = "2025-10-18T21:55:41.639Z" },
]

[[package]]
name = "loguru"
version = "0.7.3"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
    { name = "win32-setctime", marker = "sys_platform == 'win32'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/3a/05/a1dae3dffd1116099471c643b8924f5aa6524411dc6c63fdae648c4f1aca/loguru-0.7.3.tar.gz", hash = "sha256:19480589e77d47b8d85b2c827ad95d49bf31b0dcde16593892eb51dd18706eb6", size = 63559, upload-time = "2024-12-06T11:20:56.608Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/0c/29/0348de65b8cc732daa3e33e67806420b2ae89bdce2b04af740289c5c6c8c/loguru-0.7.3-py3-none-any.whl", hash = "sha256:31a33c10c8e1e10422bfd431aeb5d351c7cf7fa671e3c4df004162264b28220c", size = 61595, upload-time = "2024-12-06T11:20:54.538Z" },
]

[[package]]
name = "lxml"
version = "6.0.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/aa/88/262177de60548e5a2bfc46ad28232c9e9cbde697bd94132aeb80364675cb/lxml-6.0.2.tar.gz", hash = "sha256:cd79f3367bd74b317dda655dc8fcfa304d9eb6e4fb06b7168c5cf27f96e0cd62", size = 4073426, upload-time = "2025-09-22T04:04:59.287Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/77/d5/becbe1e2569b474a23f0c672ead8a29ac50b2dc1d5b9de184831bda8d14c/lxml-6.0.2-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:13e35cbc684aadf05d8711a5d1b5857c92e5e580efa9a0d2be197199c8def607", size = 8634365, upload-time = "2025-09-22T04:00:45.672Z" },
    { url = "https://files.pythonhosted.org/packages/28/66/1ced58f12e804644426b85d0bb8a4478ca77bc1761455da310505f1a3526/lxml-6.0.2-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:3b1675e096e17c6fe9c0e8c81434f5736c0739ff9ac6123c87c2d452f48fc938", size = 4650793, upload-time = "2025-09-22T04:00:47.783Z" },
    { url = "https://files.pythonhosted.org/packages/11/84/549098ffea39dfd167e3f174b4ce983d0eed61f9d8d25b7bf2a57c3247fc/lxml-6.0.2-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:8ac6e5811ae2870953390452e3476694196f98d447573234592d30488147404d", size = 4944362, upload-time = "2025-09-22T04:00:49.845Z" },
    { url = "https://files.pythonhosted.org/packages/ac/bd/f207f16abf9749d2037453d56b643a7471d8fde855a231a12d1e095c4f01/lxml-6.0.2-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:5aa0fc67ae19d7a64c3fe725dc9a1bb11f80e01f78289d05c6f62545affec438", size = 5083152, upload-time = "2025-09-22T04:00:51.709Z" },
    { url = "https://files.pythonhosted.org/packages/15/ae/bd813e87d8941d52ad5b65071b1affb48da01c4ed3c9c99e40abb266fbff/lxml-6.0.2-cp311-cp311-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:de496365750cc472b4e7902a485d3f152ecf57bd3ba03ddd5578ed8ceb4c5964", size = 5023539, upload-time = "2025-09-22T04:00:53.593Z" },
    { url = "https://files.pythonhosted.org/packages/02/cd/9bfef16bd1d874fbe0cb51afb00329540f30a3283beb9f0780adbb7eec03/lxml-6.0.2-cp311-cp311-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:200069a593c5e40b8f6fc0d84d86d970ba43138c3e68619ffa234bc9bb806a4d", size = 5344853, upload-time = "2025-09-22T04:00:55.524Z" },
    { url = "https://files.pythonhosted.org/packages/b8/89/ea8f91594bc5dbb879734d35a6f2b0ad50605d7fb419de2b63d4211765cc/lxml-6.0.2-cp311-cp311-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:7d2de809c2ee3b888b59f995625385f74629707c9355e0ff856445cdcae682b7", size = 5225133, upload-time = "2025-09-22T04:00:57.269Z" },
    { url = "https://files.pythonhosted.org/packages/b9/37/9c735274f5dbec726b2db99b98a43950395ba3d4a1043083dba2ad814170/lxml-6.0.2-cp311-cp311-manylinux_2_31_armv7l.whl", hash = "sha256:b2c3da8d93cf5db60e8858c17684c47d01fee6405e554fb55018dd85fc23b178", size = 4677944, upload-time = "2025-09-22T04:00:59.052Z" },
    { url = "https://files.pythonhosted.org/packages/20/28/7dfe1ba3475d8bfca3878365075abe002e05d40dfaaeb7ec01b4c587d533/lxml-6.0.2-cp311-cp311-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:442de7530296ef5e188373a1ea5789a46ce90c4847e597856570439621d9c553", size = 5284535, upload-time = "2025-09-22T04:01:01.335Z" },
    { url = "https://files.pythonhosted.org/packages/e7/cf/5f14bc0de763498fc29510e3532bf2b4b3a1c1d5d0dff2e900c16ba021ef/lxml-6.0.2-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:2593c77efde7bfea7f6389f1ab249b15ed4aa5bc5cb5131faa3b843c429fbedb", size = 5067343, upload-time = "2025-09-22T04:01:03.13Z" },
    { url = "https://files.pythonhosted.org/packages/1c/b0/bb8275ab5472f32b28cfbbcc6db7c9d092482d3439ca279d8d6fa02f7025/lxml-6.0.2-cp311-cp311-musllinux_1_2_armv7l.whl", hash = "sha256:3e3cb08855967a20f553ff32d147e14329b3ae70ced6edc2f282b94afbc74b2a", size = 4725419, upload-time = "2025-09-22T04:01:05.013Z" },
    { url = "https://files.pythonhosted.org/packages/25/4c/7c222753bc72edca3b99dbadba1b064209bc8ed4ad448af990e60dcce462/lxml-6.0.2-cp311-cp311-musllinux_1_2_riscv64.whl", hash = "sha256:2ed6c667fcbb8c19c6791bbf40b7268ef8ddf5a96940ba9404b9f9a304832f6c", size = 5275008, upload-time = "2025-09-22T04:01:07.327Z" },
    { url = "https://files.pythonhosted.org/packages/6c/8c/478a0dc6b6ed661451379447cdbec77c05741a75736d97e5b2b729687828/lxml-6.0.2-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:b8f18914faec94132e5b91e69d76a5c1d7b0c73e2489ea8929c4aaa10b76bbf7", size = 5248906, upload-time = "2025-09-22T04:01:09.452Z" },
    { url = "https://files.pythonhosted.org/packages/2d/d9/5be3a6ab2784cdf9accb0703b65e1b64fcdd9311c9f007630c7db0cfcce1/lxml-6.0.2-cp311-cp311-win32.whl", hash = "sha256:6605c604e6daa9e0d7f0a2137bdc47a2e93b59c60a65466353e37f8272f47c46", size = 3610357, upload-time = "2025-09-22T04:01:11.102Z" },
    { url = "https://files.pythonhosted.org/packages/e2/7d/ca6fb13349b473d5732fb0ee3eec8f6c80fc0688e76b7d79c1008481bf1f/lxml-6.0.2-cp311-cp311-win_amd64.whl", hash = "sha256:e5867f2651016a3afd8dd2c8238baa66f1e2802f44bc17e236f547ace6647078", size = 4036583, upload-time = "2025-09-22T04:01:12.766Z" },
    { url = "https://files.pythonhosted.org/packages/ab/a2/51363b5ecd3eab46563645f3a2c3836a2fc67d01a1b87c5017040f39f567/lxml-6.0.2-cp311-cp311-win_arm64.whl", hash = "sha256:4197fb2534ee05fd3e7afaab5d8bfd6c2e186f65ea7f9cd6a82809c887bd1285", size = 3680591, upload-time = "2025-09-22T04:01:14.874Z" },
    { url = "https://files.pythonhosted.org/packages/f3/c8/8ff2bc6b920c84355146cd1ab7d181bc543b89241cfb1ebee824a7c81457/lxml-6.0.2-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:a59f5448ba2ceccd06995c95ea59a7674a10de0810f2ce90c9006f3cbc044456", size = 8661887, upload-time = "2025-09-22T04:01:17.265Z" },
    { url = "https://files.pythonhosted.org/packages/37/6f/9aae1008083bb501ef63284220ce81638332f9ccbfa53765b2b7502203cf/lxml-6.0.2-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:e8113639f3296706fbac34a30813929e29247718e88173ad849f57ca59754924", size = 4667818, upload-time = "2025-09-22T04:01:19.688Z" },
    { url = "https://files.pythonhosted.org/packages/f1/ca/31fb37f99f37f1536c133476674c10b577e409c0a624384147653e38baf2/lxml-6.0.2-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:a8bef9b9825fa8bc816a6e641bb67219489229ebc648be422af695f6e7a4fa7f", size = 4950807, upload-time = "2025-09-22T04:01:21.487Z" },
    { url = "https://files.pythonhosted.org/packages/da/87/f6cb9442e4bada8aab5ae7e1046264f62fdbeaa6e3f6211b93f4c0dd97f1/lxml-6.0.2-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:65ea18d710fd14e0186c2f973dc60bb52039a275f82d3c44a0e42b43440ea534", size = 5109179, upload-time = "2025-09-22T04:01:23.32Z" },
    { url = "https://files.pythonhosted.org/packages/c8/20/a7760713e65888db79bbae4f6146a6ae5c04e4a204a3c48896c408cd6ed2/lxml-6.0.2-cp312-cp312-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:c371aa98126a0d4c739ca93ceffa0fd7a5d732e3ac66a46e74339acd4d334564", size = 5023044, upload-time = "2025-09-22T04:01:25.118Z" },
    { url = "https://files.pythonhosted.org/packages/a2/b0/7e64e0460fcb36471899f75831509098f3fd7cd02a3833ac517433cb4f8f/lxml-6.0.2-cp312-cp312-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:700efd30c0fa1a3581d80a748157397559396090a51d306ea59a70020223d16f", size = 5359685, upload-time = "2025-09-22T04:01:27.398Z" },
    { url = "https://files.pythonhosted.org/packages/b9/e1/e5df362e9ca4e2f48ed6411bd4b3a0ae737cc842e96877f5bf9428055ab4/lxml-6.0.2-cp312-cp312-manylinux_2_26_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:c33e66d44fe60e72397b487ee92e01da0d09ba2d66df8eae42d77b6d06e5eba0", size = 5654127, upload-time = "2025-09-22T04:01:29.629Z" },
    { url = "https://files.pythonhosted.org/packages/c6/d1/232b3309a02d60f11e71857778bfcd4acbdb86c07db8260caf7d008b08f8/lxml-6.0.2-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:90a345bbeaf9d0587a3aaffb7006aa39ccb6ff0e96a57286c0cb2fd1520ea192", size = 5253958, upload-time = "2025-09-22T04:01:31.535Z" },
    { url = "https://files.pythonhosted.org/packages/35/35/d955a070994725c4f7d80583a96cab9c107c57a125b20bb5f708fe941011/lxml-6.0.2-cp312-cp312-manylinux_2_31_armv7l.whl", hash = "sha256:064fdadaf7a21af3ed1dcaa106b854077fbeada827c18f72aec9346847cd65d0", size = 4711541, upload-time = "2025-09-22T04:01:33.801Z" },
    { url = "https://files.pythonhosted.org/packages/1e/be/667d17363b38a78c4bd63cfd4b4632029fd68d2c2dc81f25ce9eb5224dd5/lxml-6.0.2-cp312-cp312-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:fbc74f42c3525ac4ffa4b89cbdd00057b6196bcefe8bce794abd42d33a018092", size = 5267426, upload-time = "2025-09-22T04:01:35.639Z" },
    { url = "https://files.pythonhosted.org/packages/ea/47/62c70aa4a1c26569bc958c9ca86af2bb4e1f614e8c04fb2989833874f7ae/lxml-6.0.2-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:6ddff43f702905a4e32bc24f3f2e2edfe0f8fde3277d481bffb709a4cced7a1f", size = 5064917, upload-time = "2025-09-22T04:01:37.448Z" },
    { url = "https://files.pythonhosted.org/packages/bd/55/6ceddaca353ebd0f1908ef712c597f8570cc9c58130dbb89903198e441fd/lxml-6.0.2-cp312-cp312-musllinux_1_2_armv7l.whl", hash = "sha256:6da5185951d72e6f5352166e3da7b0dc27aa70bd1090b0eb3f7f7212b53f1bb8", size = 4788795, upload-time = "2025-09-22T04:01:39.165Z" },
    { url = "https://files.pythonhosted.org/packages/cf/e8/fd63e15da5e3fd4c2146f8bbb3c14e94ab850589beab88e547b2dbce22e1/lxml-6.0.2-cp312-cp312-musllinux_1_2_ppc64le.whl", hash = "sha256:57a86e1ebb4020a38d295c04fc79603c7899e0df71588043eb218722dabc087f", size = 5676759, upload-time = "2025-09-22T04:01:41.506Z" },
    { url = "https://files.pythonhosted.org/packages/76/47/b3ec58dc5c374697f5ba37412cd2728f427d056315d124dd4b61da381877/lxml-6.0.2-cp312-cp312-musllinux_1_2_riscv64.whl", hash = "sha256:2047d8234fe735ab77802ce5f2297e410ff40f5238aec569ad7c8e163d7b19a6", size = 5255666, upload-time = "2025-09-22T04:01:43.363Z" },
    { url = "https://files.pythonhosted.org/packages/19/93/03ba725df4c3d72afd9596eef4a37a837ce8e4806010569bedfcd2cb68fd/lxml-6.0.2-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:6f91fd2b2ea15a6800c8e24418c0775a1694eefc011392da73bc6cef2623b322", size = 5277989, upload-time = "2025-09-22T04:01:45.215Z" },
    { url = "https://files.pythonhosted.org/packages/c6/80/c06de80bfce881d0ad738576f243911fccf992687ae09fd80b734712b39c/lxml-6.0.2-cp312-cp312-win32.whl", hash = "sha256:3ae2ce7d6fedfb3414a2b6c5e20b249c4c607f72cb8d2bb7cc9c6ec7c6f4e849", size = 3611456, upload-time = "2025-09-22T04:01:48.243Z" },
    { url = "https://files.pythonhosted.org/packages/f7/d7/0cdfb6c3e30893463fb3d1e52bc5f5f99684a03c29a0b6b605cfae879cd5/lxml-6.0.2-cp312-cp312-win_amd64.whl", hash = "sha256:72c87e5ee4e58a8354fb9c7c84cbf95a1c8236c127a5d1b7683f04bed8361e1f", size = 4011793, upload-time = "2025-09-22T04:01:50.042Z" },
    { url = "https://files.pythonhosted.org/packages/ea/7b/93c73c67db235931527301ed3785f849c78991e2e34f3fd9a6663ffda4c5/lxml-6.0.2-cp312-cp312-win_arm64.whl", hash = "sha256:61cb10eeb95570153e0c0e554f58df92ecf5109f75eacad4a95baa709e26c3d6", size = 3672836, upload-time = "2025-09-22T04:01:52.145Z" },
    { url = "https://files.pythonhosted.org/packages/53/fd/4e8f0540608977aea078bf6d79f128e0e2c2bba8af1acf775c30baa70460/lxml-6.0.2-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:9b33d21594afab46f37ae58dfadd06636f154923c4e8a4d754b0127554eb2e77", size = 8648494, upload-time = "2025-09-22T04:01:54.242Z" },
    { url = "https://files.pythonhosted.org/packages/5d/f4/2a94a3d3dfd6c6b433501b8d470a1960a20ecce93245cf2db1706adf6c19/lxml-6.0.2-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:6c8963287d7a4c5c9a432ff487c52e9c5618667179c18a204bdedb27310f022f", size = 4661146, upload-time = "2025-09-22T04:01:56.282Z" },
    { url = "https://files.pythonhosted.org/packages/25/2e/4efa677fa6b322013035d38016f6ae859d06cac67437ca7dc708a6af7028/lxml-6.0.2-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:1941354d92699fb5ffe6ed7b32f9649e43c2feb4b97205f75866f7d21aa91452", size = 4946932, upload-time = "2025-09-22T04:01:58.989Z" },
    { url = "https://files.pythonhosted.org/packages/ce/0f/526e78a6d38d109fdbaa5049c62e1d32fdd70c75fb61c4eadf3045d3d124/lxml-6.0.2-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:bb2f6ca0ae2d983ded09357b84af659c954722bbf04dea98030064996d156048", size = 5100060, upload-time = "2025-09-22T04:02:00.812Z" },
    { url = "https://files.pythonhosted.org/packages/81/76/99de58d81fa702cc0ea7edae4f4640416c2062813a00ff24bd70ac1d9c9b/lxml-6.0.2-cp313-cp313-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:eb2a12d704f180a902d7fa778c6d71f36ceb7b0d317f34cdc76a5d05aa1dd1df", size = 5019000, upload-time = "2025-09-22T04:02:02.671Z" },
    { url = "https://files.pythonhosted.org/packages/b5/35/9e57d25482bc9a9882cb0037fdb9cc18f4b79d85df94fa9d2a89562f1d25/lxml-6.0.2-cp313-cp313-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:6ec0e3f745021bfed19c456647f0298d60a24c9ff86d9d051f52b509663feeb1", size = 5348496, upload-time = "2025-09-22T04:02:04.904Z" },
    { url = "https://files.pythonhosted.org/packages/a6/8e/cb99bd0b83ccc3e8f0f528e9aa1f7a9965dfec08c617070c5db8d63a87ce/lxml-6.0.2-cp313-cp313-manylinux_2_26_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:846ae9a12d54e368933b9759052d6206a9e8b250291109c48e350c1f1f49d916", size = 5643779, upload-time = "2025-09-22T04:02:06.689Z" },
    { url = "https://files.pythonhosted.org/packages/d0/34/9e591954939276bb679b73773836c6684c22e56d05980e31d52a9a8deb18/lxml-6.0.2-cp313-cp313-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:ef9266d2aa545d7374938fb5c484531ef5a2ec7f2d573e62f8ce722c735685fd", size = 5244072, upload-time = "2025-09-22T04:02:08.587Z" },
    { url = "https://files.pythonhosted.org/packages/8d/27/b29ff065f9aaca443ee377aff699714fcbffb371b4fce5ac4ca759e436d5/lxml-6.0.2-cp313-cp313-manylinux_2_31_armv7l.whl", hash = "sha256:4077b7c79f31755df33b795dc12119cb557a0106bfdab0d2c2d97bd3cf3dffa6", size = 4718675, upload-time = "2025-09-22T04:02:10.783Z" },
    { url = "https://files.pythonhosted.org/packages/2b/9f/f756f9c2cd27caa1a6ef8c32ae47aadea697f5c2c6d07b0dae133c244fbe/lxml-6.0.2-cp313-cp313-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:a7c5d5e5f1081955358533be077166ee97ed2571d6a66bdba6ec2f609a715d1a", size = 5255171, upload-time = "2025-09-22T04:02:12.631Z" },
    { url = "https://files.pythonhosted.org/packages/61/46/bb85ea42d2cb1bd8395484fd72f38e3389611aa496ac7772da9205bbda0e/lxml-6.0.2-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:8f8d0cbd0674ee89863a523e6994ac25fd5be9c8486acfc3e5ccea679bad2679", size = 5057175, upload-time = "2025-09-22T04:02:14.718Z" },
    { url = "https://files.pythonhosted.org/packages/95/0c/443fc476dcc8e41577f0af70458c50fe299a97bb6b7505bb1ae09aa7f9ac/lxml-6.0.2-cp313-cp313-musllinux_1_2_armv7l.whl", hash = "sha256:2cbcbf6d6e924c28f04a43f3b6f6e272312a090f269eff68a2982e13e5d57659", size = 4785688, upload-time = "2025-09-22T04:02:16.957Z" },
    { url = "https://files.pythonhosted.org/packages/48/78/6ef0b359d45bb9697bc5a626e1992fa5d27aa3f8004b137b2314793b50a0/lxml-6.0.2-cp313-cp313-musllinux_1_2_ppc64le.whl", hash = "sha256:dfb874cfa53340009af6bdd7e54ebc0d21012a60a4e65d927c2e477112e63484", size = 5660655, upload-time = "2025-09-22T04:02:18.815Z" },
    { url = "https://files.pythonhosted.org/packages/ff/ea/e1d33808f386bc1339d08c0dcada6e4712d4ed8e93fcad5f057070b7988a/lxml-6.0.2-cp313-cp313-musllinux_1_2_riscv64.whl", hash = "sha256:fb8dae0b6b8b7f9e96c26fdd8121522ce5de9bb5538010870bd538683d30e9a2", size = 5247695, upload-time = "2025-09-22T04:02:20.593Z" },
    { url = "https://files.pythonhosted.org/packages/4f/47/eba75dfd8183673725255247a603b4ad606f4ae657b60c6c145b381697da/lxml-6.0.2-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:358d9adae670b63e95bc59747c72f4dc97c9ec58881d4627fe0120da0f90d314", size = 5269841, upload-time = "2025-09-22T04:02:22.489Z" },
    { url = "https://files.pythonhosted.org/packages/76/04/5c5e2b8577bc936e219becb2e98cdb1aca14a4921a12995b9d0c523502ae/lxml-6.0.2-cp313-cp313-win32.whl", hash = "sha256:e8cd2415f372e7e5a789d743d133ae474290a90b9023197fd78f32e2dc6873e2", size = 3610700, upload-time = "2025-09-22T04:02:24.465Z" },
    { url = "https://files.pythonhosted.org/packages/fe/0a/4643ccc6bb8b143e9f9640aa54e38255f9d3b45feb2cbe7ae2ca47e8782e/lxml-6.0.2-cp313-cp313-win_amd64.whl", hash = "sha256:b30d46379644fbfc3ab81f8f82ae4de55179414651f110a1514f0b1f8f6cb2d7", size = 4010347, upload-time = "2025-09-22T04:02:26.286Z" },
    { url = "https://files.pythonhosted.org/packages/31/ef/dcf1d29c3f530577f61e5fe2f1bd72929acf779953668a8a47a479ae6f26/lxml-6.0.2-cp313-cp313-win_arm64.whl", hash = "sha256:13dcecc9946dca97b11b7c40d29fba63b55ab4170d3c0cf8c0c164343b9bfdcf", size = 3671248, upload-time = "2025-09-22T04:02:27.918Z" },
    { url = "https://files.pythonhosted.org/packages/03/15/d4a377b385ab693ce97b472fe0c77c2b16ec79590e688b3ccc71fba19884/lxml-6.0.2-cp314-cp314-macosx_10_13_universal2.whl", hash = "sha256:b0c732aa23de8f8aec23f4b580d1e52905ef468afb4abeafd3fec77042abb6fe", size = 8659801, upload-time = "2025-09-22T04:02:30.113Z" },
    { url = "https://files.pythonhosted.org/packages/c8/e8/c128e37589463668794d503afaeb003987373c5f94d667124ffd8078bbd9/lxml-6.0.2-cp314-cp314-macosx_10_13_x86_64.whl", hash = "sha256:4468e3b83e10e0317a89a33d28f7aeba1caa4d1a6fd457d115dd4ffe90c5931d", size = 4659403, upload-time = "2025-09-22T04:02:32.119Z" },
    { url = "https://files.pythonhosted.org/packages/00/ce/74903904339decdf7da7847bb5741fc98a5451b42fc419a86c0c13d26fe2/lxml-6.0.2-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:abd44571493973bad4598a3be7e1d807ed45aa2adaf7ab92ab7c62609569b17d", size = 4966974, upload-time = "2025-09-22T04:02:34.155Z" },
    { url = "https://files.pythonhosted.org/packages/1f/d3/131dec79ce61c5567fecf82515bd9bc36395df42501b50f7f7f3bd065df0/lxml-6.0.2-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:370cd78d5855cfbffd57c422851f7d3864e6ae72d0da615fca4dad8c45d375a5", size = 5102953, upload-time = "2025-09-22T04:02:36.054Z" },
    { url = "https://files.pythonhosted.org/packages/3a/ea/a43ba9bb750d4ffdd885f2cd333572f5bb900cd2408b67fdda07e85978a0/lxml-6.0.2-cp314-cp314-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:901e3b4219fa04ef766885fb40fa516a71662a4c61b80c94d25336b4934b71c0", size = 5055054, upload-time = "2025-09-22T04:02:38.154Z" },
    { url = "https://files.pythonhosted.org/packages/60/23/6885b451636ae286c34628f70a7ed1fcc759f8d9ad382d132e1c8d3d9bfd/lxml-6.0.2-cp314-cp314-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:a4bf42d2e4cf52c28cc1812d62426b9503cdb0c87a6de81442626aa7d69707ba", size = 5352421, upload-time = "2025-09-22T04:02:40.413Z" },
    { url = "https://files.pythonhosted.org/packages/48/5b/fc2ddfc94ddbe3eebb8e9af6e3fd65e2feba4967f6a4e9683875c394c2d8/lxml-6.0.2-cp314-cp314-manylinux_2_26_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:b2c7fdaa4d7c3d886a42534adec7cfac73860b89b4e5298752f60aa5984641a0", size = 5673684, upload-time = "2025-09-22T04:02:42.288Z" },
    { url = "https://files.pythonhosted.org/packages/29/9c/47293c58cc91769130fbf85531280e8cc7868f7fbb6d92f4670071b9cb3e/lxml-6.0.2-cp314-cp314-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:98a5e1660dc7de2200b00d53fa00bcd3c35a3608c305d45a7bbcaf29fa16e83d", size = 5252463, upload-time = "2025-09-22T04:02:44.165Z" },
    { url = "https://files.pythonhosted.org/packages/9b/da/ba6eceb830c762b48e711ded880d7e3e89fc6c7323e587c36540b6b23c6b/lxml-6.0.2-cp314-cp314-manylinux_2_31_armv7l.whl", hash = "sha256:dc051506c30b609238d79eda75ee9cab3e520570ec8219844a72a46020901e37", size = 4698437, upload-time = "2025-09-22T04:02:46.524Z" },
    { url = "https://files.pythonhosted.org/packages/a5/24/7be3f82cb7990b89118d944b619e53c656c97dc89c28cfb143fdb7cd6f4d/lxml-6.0.2-cp314-cp314-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:8799481bbdd212470d17513a54d568f44416db01250f49449647b5ab5b5dccb9", size = 5269890, upload-time = "2025-09-22T04:02:48.812Z" },
    { url = "https://files.pythonhosted.org/packages/1b/bd/dcfb9ea1e16c665efd7538fc5d5c34071276ce9220e234217682e7d2c4a5/lxml-6.0.2-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:9261bb77c2dab42f3ecd9103951aeca2c40277701eb7e912c545c1b16e0e4917", size = 5097185, upload-time = "2025-09-22T04:02:50.746Z" },
    { url = "https://files.pythonhosted.org/packages/21/04/a60b0ff9314736316f28316b694bccbbabe100f8483ad83852d77fc7468e/lxml-6.0.2-cp314-cp314-musllinux_1_2_armv7l.whl", hash = "sha256:65ac4a01aba353cfa6d5725b95d7aed6356ddc0a3cd734de00124d285b04b64f", size = 4745895, upload-time = "2025-09-22T04:02:52.968Z" },
    { url = "https://files.pythonhosted.org/packages/d6/bd/7d54bd1846e5a310d9c715921c5faa71cf5c0853372adf78aee70c8d7aa2/lxml-6.0.2-cp314-cp314-musllinux_1_2_ppc64le.whl", hash = "sha256:b22a07cbb82fea98f8a2fd814f3d1811ff9ed76d0fc6abc84eb21527596e7cc8", size = 5695246, upload-time = "2025-09-22T04:02:54.798Z" },
    { url = "https://files.pythonhosted.org/packages/fd/32/5643d6ab947bc371da21323acb2a6e603cedbe71cb4c99c8254289ab6f4e/lxml-6.0.2-cp314-cp314-musllinux_1_2_riscv64.whl", hash = "sha256:d759cdd7f3e055d6bc8d9bec3ad905227b2e4c785dc16c372eb5b5e83123f48a", size = 5260797, upload-time = "2025-09-22T04:02:57.058Z" },
    { url = "https://files.pythonhosted.org/packages/33/da/34c1ec4cff1eea7d0b4cd44af8411806ed943141804ac9c5d565302afb78/lxml-6.0.2-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:945da35a48d193d27c188037a05fec5492937f66fb1958c24fc761fb9d40d43c", size = 5277404, upload-time = "2025-09-22T04:02:58.966Z" },
    { url = "https://files.pythonhosted.org/packages/82/57/4eca3e31e54dc89e2c3507e1cd411074a17565fa5ffc437c4ae0a00d439e/lxml-6.0.2-cp314-cp314-win32.whl", hash = "sha256:be3aaa60da67e6153eb15715cc2e19091af5dc75faef8b8a585aea372507384b", size = 3670072, upload-time = "2025-09-22T04:03:38.05Z" },
    { url = "https://files.pythonhosted.org/packages/e3/e0/c96cf13eccd20c9421ba910304dae0f619724dcf1702864fd59dd386404d/lxml-6.0.2-cp314-cp314-win_amd64.whl", hash = "sha256:fa25afbadead523f7001caf0c2382afd272c315a033a7b06336da2637d92d6ed", size = 4080617, upload-time = "2025-09-22T04:03:39.835Z" },
    { url = "https://files.pythonhosted.org/packages/d5/5d/b3f03e22b3d38d6f188ef044900a9b29b2fe0aebb94625ce9fe244011d34/lxml-6.0.2-cp314-cp314-win_arm64.whl", hash = "sha256:063eccf89df5b24e361b123e257e437f9e9878f425ee9aae3144c77faf6da6d8", size = 3754930, upload-time = "2025-09-22T04:03:41.565Z" },
    { url = "https://files.pythonhosted.org/packages/5e/5c/42c2c4c03554580708fc738d13414801f340c04c3eff90d8d2d227145275/lxml-6.0.2-cp314-cp314t-macosx_10_13_universal2.whl", hash = "sha256:6162a86d86893d63084faaf4ff937b3daea233e3682fb4474db07395794fa80d", size = 8910380, upload-time = "2025-09-22T04:03:01.645Z" },
    { url = "https://files.pythonhosted.org/packages/bf/4f/12df843e3e10d18d468a7557058f8d3733e8b6e12401f30b1ef29360740f/lxml-6.0.2-cp314-cp314t-macosx_10_13_x86_64.whl", hash = "sha256:414aaa94e974e23a3e92e7ca5b97d10c0cf37b6481f50911032c69eeb3991bba", size = 4775632, upload-time = "2025-09-22T04:03:03.814Z" },
    { url = "https://files.pythonhosted.org/packages/e4/0c/9dc31e6c2d0d418483cbcb469d1f5a582a1cd00a1f4081953d44051f3c50/lxml-6.0.2-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:48461bd21625458dd01e14e2c38dd0aea69addc3c4f960c30d9f59d7f93be601", size = 4975171, upload-time = "2025-09-22T04:03:05.651Z" },
    { url = "https://files.pythonhosted.org/packages/e7/2b/9b870c6ca24c841bdd887504808f0417aa9d8d564114689266f19ddf29c8/lxml-6.0.2-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:25fcc59afc57d527cfc78a58f40ab4c9b8fd096a9a3f964d2781ffb6eb33f4ed", size = 5110109, upload-time = "2025-09-22T04:03:07.452Z" },
    { url = "https://files.pythonhosted.org/packages/bf/0c/4f5f2a4dd319a178912751564471355d9019e220c20d7db3fb8307ed8582/lxml-6.0.2-cp314-cp314t-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:5179c60288204e6ddde3f774a93350177e08876eaf3ab78aa3a3649d43eb7d37", size = 5041061, upload-time = "2025-09-22T04:03:09.297Z" },
    { url = "https://files.pythonhosted.org/packages/12/64/554eed290365267671fe001a20d72d14f468ae4e6acef1e179b039436967/lxml-6.0.2-cp314-cp314t-manylinux_2_26_i686.manylinux_2_28_i686.whl", hash = "sha256:967aab75434de148ec80597b75062d8123cadf2943fb4281f385141e18b21338", size = 5306233, upload-time = "2025-09-22T04:03:11.651Z" },
    { url = "https://files.pythonhosted.org/packages/7a/31/1d748aa275e71802ad9722df32a7a35034246b42c0ecdd8235412c3396ef/lxml-6.0.2-cp314-cp314t-manylinux_2_26_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:d100fcc8930d697c6561156c6810ab4a508fb264c8b6779e6e61e2ed5e7558f9", size = 5604739, upload-time = "2025-09-22T04:03:13.592Z" },
    { url = "https://files.pythonhosted.org/packages/8f/41/2c11916bcac09ed561adccacceaedd2bf0e0b25b297ea92aab99fd03d0fa/lxml-6.0.2-cp314-cp314t-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:2ca59e7e13e5981175b8b3e4ab84d7da57993eeff53c07764dcebda0d0e64ecd", size = 5225119, upload-time = "2025-09-22T04:03:15.408Z" },
    { url = "https://files.pythonhosted.org/packages/99/05/4e5c2873d8f17aa018e6afde417c80cc5d0c33be4854cce3ef5670c49367/lxml-6.0.2-cp314-cp314t-manylinux_2_31_armv7l.whl", hash = "sha256:957448ac63a42e2e49531b9d6c0fa449a1970dbc32467aaad46f11545be9af1d", size = 4633665, upload-time = "2025-09-22T04:03:17.262Z" },
    { url = "https://files.pythonhosted.org/packages/0f/c9/dcc2da1bebd6275cdc723b515f93edf548b82f36a5458cca3578bc899332/lxml-6.0.2-cp314-cp314t-manylinux_2_38_riscv64.manylinux_2_39_riscv64.whl", hash = "sha256:b7fc49c37f1786284b12af63152fe1d0990722497e2d5817acfe7a877522f9a9", size = 5234997, upload-time = "2025-09-22T04:03:19.14Z" },
    { url = "https://files.pythonhosted.org/packages/9c/e2/5172e4e7468afca64a37b81dba152fc5d90e30f9c83c7c3213d6a02a5ce4/lxml-6.0.2-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:e19e0643cc936a22e837f79d01a550678da8377d7d801a14487c10c34ee49c7e", size = 5090957, upload-time = "2025-09-22T04:03:21.436Z" },
    { url = "https://files.pythonhosted.org/packages/a5/b3/15461fd3e5cd4ddcb7938b87fc20b14ab113b92312fc97afe65cd7c85de1/lxml-6.0.2-cp314-cp314t-musllinux_1_2_armv7l.whl", hash = "sha256:1db01e5cf14345628e0cbe71067204db658e2fb8e51e7f33631f5f4735fefd8d", size = 4764372, upload-time = "2025-09-22T04:03:23.27Z" },
    { url = "https://files.pythonhosted.org/packages/05/33/f310b987c8bf9e61c4dd8e8035c416bd3230098f5e3cfa69fc4232de7059/lxml-6.0.2-cp314-cp314t-musllinux_1_2_ppc64le.whl", hash = "sha256:875c6b5ab39ad5291588aed6925fac99d0097af0dd62f33c7b43736043d4a2ec", size = 5634653, upload-time = "2025-09-22T04:03:25.767Z" },
    { url = "https://files.pythonhosted.org/packages/70/ff/51c80e75e0bc9382158133bdcf4e339b5886c6ee2418b5199b3f1a61ed6d/lxml-6.0.2-cp314-cp314t-musllinux_1_2_riscv64.whl", hash = "sha256:cdcbed9ad19da81c480dfd6dd161886db6096083c9938ead313d94b30aadf272", size = 5233795, upload-time = "2025-09-22T04:03:27.62Z" },
    { url = "https://files.pythonhosted.org/packages/56/4d/4856e897df0d588789dd844dbed9d91782c4ef0b327f96ce53c807e13128/lxml-6.0.2-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:80dadc234ebc532e09be1975ff538d154a7fa61ea5031c03d25178855544728f", size = 5257023, upload-time = "2025-09-22T04:03:30.056Z" },
    { url = "https://files.pythonhosted.org/packages/0f/85/86766dfebfa87bea0ab78e9ff7a4b4b45225df4b4d3b8cc3c03c5cd68464/lxml-6.0.2-cp314-cp314t-win32.whl", hash = "sha256:da08e7bb297b04e893d91087df19638dc7a6bb858a954b0cc2b9f5053c922312", size = 3911420, upload-time = "2025-09-22T04:03:32.198Z" },
    { url = "https://files.pythonhosted.org/packages/fe/1a/b248b355834c8e32614650b8008c69ffeb0ceb149c793961dd8c0b991bb3/lxml-6.0.2-cp314-cp314t-win_amd64.whl", hash = "sha256:252a22982dca42f6155125ac76d3432e548a7625d56f5a273ee78a5057216eca", size = 4406837, upload-time = "2025-09-22T04:03:34.027Z" },
    { url = "https://files.pythonhosted.org/packages/92/aa/df863bcc39c5e0946263454aba394de8a9084dbaff8ad143846b0d844739/lxml-6.0.2-cp314-cp314t-win_arm64.whl", hash = "sha256:bb4c1847b303835d89d785a18801a883436cdfd5dc3d62947f9c49e24f0f5a2c", size = 3822205, upload-time = "2025-09-22T04:03:36.249Z" },
    { url = "https://files.pythonhosted.org/packages/0b/11/29d08bc103a62c0eba8016e7ed5aeebbf1e4312e83b0b1648dd203b0e87d/lxml-6.0.2-pp311-pypy311_pp73-macosx_10_15_x86_64.whl", hash = "sha256:1c06035eafa8404b5cf475bb37a9f6088b0aca288d4ccc9d69389750d5543700", size = 3949829, upload-time = "2025-09-22T04:04:45.608Z" },
    { url = "https://files.pythonhosted.org/packages/12/b3/52ab9a3b31e5ab8238da241baa19eec44d2ab426532441ee607165aebb52/lxml-6.0.2-pp311-pypy311_pp73-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:c7d13103045de1bdd6fe5d61802565f1a3537d70cd3abf596aa0af62761921ee", size = 4226277, upload-time = "2025-09-22T04:04:47.754Z" },
    { url = "https://files.pythonhosted.org/packages/a0/33/1eaf780c1baad88224611df13b1c2a9dfa460b526cacfe769103ff50d845/lxml-6.0.2-pp311-pypy311_pp73-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:0a3c150a95fbe5ac91de323aa756219ef9cf7fde5a3f00e2281e30f33fa5fa4f", size = 4330433, upload-time = "2025-09-22T04:04:49.907Z" },
    { url = "https://files.pythonhosted.org/packages/7a/c1/27428a2ff348e994ab4f8777d3a0ad510b6b92d37718e5887d2da99952a2/lxml-6.0.2-pp311-pypy311_pp73-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:60fa43be34f78bebb27812ed90f1925ec99560b0fa1decdb7d12b84d857d31e9", size = 4272119, upload-time = "2025-09-22T04:04:51.801Z" },
    { url = "https://files.pythonhosted.org/packages/f0/d0/3020fa12bcec4ab62f97aab026d57c2f0cfd480a558758d9ca233bb6a79d/lxml-6.0.2-pp311-pypy311_pp73-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:21c73b476d3cfe836be731225ec3421fa2f048d84f6df6a8e70433dff1376d5a", size = 4417314, upload-time = "2025-09-22T04:04:55.024Z" },
    { url = "https://files.pythonhosted.org/packages/6c/77/d7f491cbc05303ac6801651aabeb262d43f319288c1ea96c66b1d2692ff3/lxml-6.0.2-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:27220da5be049e936c3aca06f174e8827ca6445a4353a1995584311487fc4e3e", size = 3518768, upload-time = "2025-09-22T04:04:57.097Z" },
]

[[package]]
name = "markdown-it-py"
version = "4.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "mdurl" },
]
sdist = { url = "https://files.pythonhosted.org/packages/5b/f5/4ec618ed16cc4f8fb3b701563655a69816155e79e24a17b651541804721d/markdown_it_py-4.0.0.tar.gz", hash = "sha256:cb0a2b4aa34f932c007117b194e945bd74e0ec24133ceb5bac59009cda1cb9f3", size = 73070, upload-time = "2025-08-11T12:57:52.854Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/94/54/e7d793b573f298e1c9013b8c4dade17d481164aa517d1d7148619c2cedbf/markdown_it_py-4.0.0-py3-none-any.whl", hash = "sha256:87327c59b172c5011896038353a81343b6754500a08cd7a4973bb48c6d578147", size = 87321, upload-time = "2025-08-11T12:57:51.923Z" },
]

[[package]]
name = "mdurl"
version = "0.1.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/d6/54/cfe61301667036ec958cb99bd3efefba235e65cdeb9c84d24a8293ba1d90/mdurl-0.1.2.tar.gz", hash = "sha256:bb413d29f5eea38f31dd4754dd7377d4465116fb207585f97bf925588687c1ba", size = 8729, upload-time = "2022-08-14T12:40:10.846Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b3/38/89ba8ad64ae25be8de66a6d463314cf1eb366222074cfda9ee839c56a4b4/mdurl-0.1.2-py3-none-any.whl", hash = "sha256:84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8", size = 9979, upload-time = "2022-08-14T12:40:09.779Z" },
]

[[package]]
name = "mmh3"
version = "5.2.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/91/1a/edb23803a168f070ded7a3014c6d706f63b90c84ccc024f89d794a3b7a6d/mmh3-5.2.1.tar.gz", hash = "sha256:bbea5b775f0ac84945191fb83f845a6fd9a21a03ea7f2e187defac7e401616ad", size = 33775, upload-time = "2026-03-05T15:55:57.716Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/65/d7/3312a59df3c1cdd783f4cf0c4ee8e9decff9c5466937182e4cc7dbbfe6c5/mmh3-5.2.1-cp311-cp311-macosx_10_9_universal2.whl", hash = "sha256:dae0f0bd7d30c0ad61b9a504e8e272cb8391eed3f1587edf933f4f6b33437450", size = 56082, upload-time = "2026-03-05T15:53:59.702Z" },
    { url = "https://files.pythonhosted.org/packages/61/96/6f617baa098ca0d2989bfec6d28b5719532cd8d8848782662f5b755f657f/mmh3-5.2.1-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:9aeaf53eaa075dd63e81512522fd180097312fb2c9f476333309184285c49ce0", size = 40458, upload-time = "2026-03-05T15:54:01.548Z" },
    { url = "https://files.pythonhosted.org/packages/c1/b4/9cd284bd6062d711e13d26c04d4778ab3f690c1c38a4563e3c767ec8802e/mmh3-5.2.1-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:0634581290e6714c068f4aa24020acf7880927d1f0084fa753d9799ae9610082", size = 40079, upload-time = "2026-03-05T15:54:02.743Z" },
    { url = "https://files.pythonhosted.org/packages/f6/09/a806334ce1d3d50bf782b95fcee8b3648e1e170327d4bb7b4bad2ad7d956/mmh3-5.2.1-cp311-cp311-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:e080c0637aea036f35507e803a4778f119a9b436617694ae1c5c366805f1e997", size = 97242, upload-time = "2026-03-05T15:54:04.536Z" },
    { url = "https://files.pythonhosted.org/packages/ee/93/723e317dd9e041c4dc4566a2eb53b01ad94de31750e0b834f1643905e97c/mmh3-5.2.1-cp311-cp311-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:db0562c5f71d18596dcd45e854cf2eeba27d7543e1a3acdafb7eef728f7fe85d", size = 103082, upload-time = "2026-03-05T15:54:06.387Z" },
    { url = "https://files.pythonhosted.org/packages/61/b5/f96121e69cc48696075071531cf574f112e1ffd08059f4bffb41210e6fc5/mmh3-5.2.1-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:1d9f9a3ce559a5267014b04b82956993270f63ec91765e13e9fd73daf2d2738e", size = 106054, upload-time = "2026-03-05T15:54:07.506Z" },
    { url = "https://files.pythonhosted.org/packages/82/49/192b987ec48d0b2aecf8ac285a9b11fbc00030f6b9c694664ae923458dde/mmh3-5.2.1-cp311-cp311-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:960b1b3efa39872ac8b6cc3a556edd6fb90ed74f08c9c45e028f1005b26aa55d", size = 112910, upload-time = "2026-03-05T15:54:09.403Z" },
    { url = "https://files.pythonhosted.org/packages/cf/a1/03e91fd334ed0144b83343a76eb11f17434cd08f746401488cfeafb2d241/mmh3-5.2.1-cp311-cp311-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:d30b650595fdbe32366b94cb14f30bb2b625e512bd4e1df00611f99dc5c27fd4", size = 120551, upload-time = "2026-03-05T15:54:10.587Z" },
    { url = "https://files.pythonhosted.org/packages/93/b9/b89a71d2ff35c3a764d1c066c7313fc62c7cc48fa48a4b3b0304a4a0146f/mmh3-5.2.1-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:82f3802bfc4751f420d591c5c864de538b71cea117fce67e4595c2afede08a15", size = 99096, upload-time = "2026-03-05T15:54:11.76Z" },
    { url = "https://files.pythonhosted.org/packages/36/b5/613772c1c6ed5f7b63df55eb131e887cc43720fec392777b95a79d34e640/mmh3-5.2.1-cp311-cp311-musllinux_1_2_i686.whl", hash = "sha256:915e7a2418f10bd1151b1953df06d896db9783c9cfdb9a8ee1f9b3a4331ab503", size = 98524, upload-time = "2026-03-05T15:54:13.122Z" },
    { url = "https://files.pythonhosted.org/packages/5e/0e/1524566fe8eaf871e4f7bc44095929fcd2620488f402822d848df19d679c/mmh3-5.2.1-cp311-cp311-musllinux_1_2_ppc64le.whl", hash = "sha256:fc78739b5ec6e4fb02301984a3d442a91406e7700efbe305071e7fd1c78278f2", size = 106239, upload-time = "2026-03-05T15:54:14.601Z" },
    { url = "https://files.pythonhosted.org/packages/04/94/21adfa7d90a7a697137ad6de33eeff6445420ca55e433a5d4919c79bc3b5/mmh3-5.2.1-cp311-cp311-musllinux_1_2_s390x.whl", hash = "sha256:41aac7002a749f08727cb91babff1daf8deac317c0b1f317adc69be0e6c375d1", size = 109797, upload-time = "2026-03-05T15:54:15.819Z" },
    { url = "https://files.pythonhosted.org/packages/b5/e6/1aacc3a219e1aa62fa65669995d4a3562b35be5200ec03680c7e4bec9676/mmh3-5.2.1-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:9d8089d853c7963a8ce87fff93e2a67075c0bc08684a08ea6ad13577c38ffc38", size = 97228, upload-time = "2026-03-05T15:54:16.992Z" },
    { url = "https://files.pythonhosted.org/packages/f1/b9/5e4cca8dcccf298add0a27f3c357bc8cf8baf821d35cdc6165e4bd5a48b0/mmh3-5.2.1-cp311-cp311-win32.whl", hash = "sha256:baeb47635cb33375dee4924cd93d7f5dcaa786c740b08423b0209b824a1ee728", size = 40751, upload-time = "2026-03-05T15:54:18.714Z" },
    { url = "https://files.pythonhosted.org/packages/72/fc/5b11d49247f499bcda591171e9cf3b6ee422b19e70aa2cef2e0ae65ca3b9/mmh3-5.2.1-cp311-cp311-win_amd64.whl", hash = "sha256:1e4ecee40ba19e6975e1120829796770325841c2f153c0e9aecca927194c6a2a", size = 41517, upload-time = "2026-03-05T15:54:19.764Z" },
    { url = "https://files.pythonhosted.org/packages/8a/5f/2a511ee8a1c2a527c77726d5231685b72312c5a1a1b7639ad66a9652aa84/mmh3-5.2.1-cp311-cp311-win_arm64.whl", hash = "sha256:c302245fd6c33d96bd169c7ccf2513c20f4c1e417c07ce9dce107c8bc3f8411f", size = 39287, upload-time = "2026-03-05T15:54:20.904Z" },
    { url = "https://files.pythonhosted.org/packages/92/94/bc5c3b573b40a328c4d141c20e399039ada95e5e2a661df3425c5165fd84/mmh3-5.2.1-cp312-cp312-macosx_10_13_universal2.whl", hash = "sha256:0cc21533878e5586b80d74c281d7f8da7932bc8ace50b8d5f6dbf7e3935f63f1", size = 56087, upload-time = "2026-03-05T15:54:21.92Z" },
    { url = "https://files.pythonhosted.org/packages/f6/80/64a02cc3e95c3af0aaa2590849d9ed24a9f14bb93537addde688e039b7c3/mmh3-5.2.1-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:4eda76074cfca2787c8cf1bec603eaebdddd8b061ad5502f85cddae998d54f00", size = 40500, upload-time = "2026-03-05T15:54:22.953Z" },
    { url = "https://files.pythonhosted.org/packages/8b/72/e6d6602ce18adf4ddcd0e48f2e13590cc92a536199e52109f46f259d3c46/mmh3-5.2.1-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:eee884572b06bbe8a2b54f424dbd996139442cf83c76478e1ec162512e0dd2c7", size = 40034, upload-time = "2026-03-05T15:54:23.943Z" },
    { url = "https://files.pythonhosted.org/packages/59/c2/bf4537a8e58e21886ef16477041238cab5095c836496e19fafc34b7445d2/mmh3-5.2.1-cp312-cp312-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:0d0b7e803191db5f714d264044e06189c8ccd3219e936cc184f07106bd17fd7b", size = 97292, upload-time = "2026-03-05T15:54:25.335Z" },
    { url = "https://files.pythonhosted.org/packages/e5/e2/51ed62063b44d10b06d975ac87af287729eeb5e3ed9772f7584a17983e90/mmh3-5.2.1-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:8e6c219e375f6341d0959af814296372d265a8ca1af63825f65e2e87c618f006", size = 103274, upload-time = "2026-03-05T15:54:26.44Z" },
    { url = "https://files.pythonhosted.org/packages/75/ce/12a7524dca59eec92e5b31fdb13ede1e98eda277cf2b786cf73bfbc24e81/mmh3-5.2.1-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:26fb5b9c3946bf7f1daed7b37e0c03898a6f062149127570f8ede346390a0825", size = 106158, upload-time = "2026-03-05T15:54:28.578Z" },
    { url = "https://files.pythonhosted.org/packages/86/1f/d3ba6dd322d01ab5d44c46c8f0c38ab6bbbf9b5e20e666dfc05bf4a23604/mmh3-5.2.1-cp312-cp312-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:3c38d142c706201db5b2345166eeef1e7740e3e2422b470b8ba5c8727a9b4c7a", size = 113005, upload-time = "2026-03-05T15:54:29.767Z" },
    { url = "https://files.pythonhosted.org/packages/b6/a9/15d6b6f913294ea41b44d901741298e3718e1cb89ee626b3694625826a43/mmh3-5.2.1-cp312-cp312-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:50885073e2909251d4718634a191c49ae5f527e5e1736d738e365c3e8be8f22b", size = 120744, upload-time = "2026-03-05T15:54:30.931Z" },
    { url = "https://files.pythonhosted.org/packages/76/b3/70b73923fd0284c439860ff5c871b20210dfdbe9a6b9dd0ee6496d77f174/mmh3-5.2.1-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:b3f99e1756fc48ad507b95e5d86f2fb21b3d495012ff13e6592ebac14033f166", size = 99111, upload-time = "2026-03-05T15:54:32.353Z" },
    { url = "https://files.pythonhosted.org/packages/dd/38/99f7f75cd27d10d8b899a1caafb9d531f3903e4d54d572220e3d8ac35e89/mmh3-5.2.1-cp312-cp312-musllinux_1_2_i686.whl", hash = "sha256:62815d2c67f2dd1be76a253d88af4e1da19aeaa1820146dec52cf8bee2958b16", size = 98623, upload-time = "2026-03-05T15:54:33.801Z" },
    { url = "https://files.pythonhosted.org/packages/fd/68/6e292c0853e204c44d2f03ea5f090be3317a0e2d9417ecb62c9eb27687df/mmh3-5.2.1-cp312-cp312-musllinux_1_2_ppc64le.whl", hash = "sha256:8f767ba0911602ddef289404e33835a61168314ebd3c729833db2ed685824211", size = 106437, upload-time = "2026-03-05T15:54:35.177Z" },
    { url = "https://files.pythonhosted.org/packages/dd/c6/fedd7284c459cfb58721d461fcf5607a4c1f5d9ab195d113d51d10164d16/mmh3-5.2.1-cp312-cp312-musllinux_1_2_s390x.whl", hash = "sha256:67e41a497bac88cc1de96eeba56eeb933c39d54bc227352f8455aa87c4ca4000", size = 110002, upload-time = "2026-03-05T15:54:36.673Z" },
    { url = "https://files.pythonhosted.org/packages/3b/ac/ca8e0c19a34f5b71390171d2ff0b9f7f187550d66801a731bb68925126a4/mmh3-5.2.1-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:3d74a03fb57757ece25aa4b3c1c60157a1cece37a020542785f942e2f827eed5", size = 97507, upload-time = "2026-03-05T15:54:37.804Z" },
    { url = "https://files.pythonhosted.org/packages/df/94/6ebb9094cfc7ac5e7950776b9d13a66bb4a34f83814f32ba2abc9494fc68/mmh3-5.2.1-cp312-cp312-win32.whl", hash = "sha256:7374d6e3ef72afe49697ecd683f3da12f4fc06af2d75433d0580c6746d2fa025", size = 40773, upload-time = "2026-03-05T15:54:40.077Z" },
    { url = "https://files.pythonhosted.org/packages/5b/3c/cd3527198cf159495966551c84a5f36805a10ac17b294f41f67b83f6a4d6/mmh3-5.2.1-cp312-cp312-win_amd64.whl", hash = "sha256:3a9fed49c6ce4ed7e73f13182760c65c816da006debe67f37635580dfb0fae00", size = 41560, upload-time = "2026-03-05T15:54:41.148Z" },
    { url = "https://files.pythonhosted.org/packages/15/96/6fe5ebd0f970a076e3ed5512871ce7569447b962e96c125528a2f9724470/mmh3-5.2.1-cp312-cp312-win_arm64.whl", hash = "sha256:bbfcb95d9a744e6e2827dfc66ad10e1020e0cac255eb7f85652832d5a264c2fc", size = 39313, upload-time = "2026-03-05T15:54:42.171Z" },
    { url = "https://files.pythonhosted.org/packages/25/a5/9daa0508a1569a54130f6198d5462a92deda870043624aa3ea72721aa765/mmh3-5.2.1-cp313-cp313-android_21_arm64_v8a.whl", hash = "sha256:723b2681ed4cc07d3401bbea9c201ad4f2a4ca6ba8cddaff6789f715dd2b391e", size = 40832, upload-time = "2026-03-05T15:54:43.212Z" },
    { url = "https://files.pythonhosted.org/packages/0a/6b/3230c6d80c1f4b766dedf280a92c2241e99f87c1504ff74205ec8cebe451/mmh3-5.2.1-cp313-cp313-android_21_x86_64.whl", hash = "sha256:3619473a0e0d329fd4aec8075628f8f616be2da41605300696206d6f36920c3d", size = 41964, upload-time = "2026-03-05T15:54:44.204Z" },
    { url = "https://files.pythonhosted.org/packages/62/fb/648bfddb74a872004b6ee751551bfdda783fe6d70d2e9723bad84dbe5311/mmh3-5.2.1-cp313-cp313-ios_13_0_arm64_iphoneos.whl", hash = "sha256:e48d4dbe0f88e53081da605ae68644e5182752803bbc2beb228cca7f1c4454d6", size = 39114, upload-time = "2026-03-05T15:54:45.205Z" },
    { url = "https://files.pythonhosted.org/packages/95/c2/ab7901f87af438468b496728d11264cb397b3574d41506e71b92128e0373/mmh3-5.2.1-cp313-cp313-ios_13_0_arm64_iphonesimulator.whl", hash = "sha256:a482ac121de6973897c92c2f31defc6bafb11c83825109275cffce54bb64933f", size = 39819, upload-time = "2026-03-05T15:54:46.509Z" },
    { url = "https://files.pythonhosted.org/packages/2f/ed/6f88dda0df67de1612f2e130ffea34cf84aaee5bff5b0aff4dbff2babe34/mmh3-5.2.1-cp313-cp313-ios_13_0_x86_64_iphonesimulator.whl", hash = "sha256:17fbb47f0885ace8327ce1235d0416dc86a211dcd8cc1e703f41523be32cfec8", size = 40330, upload-time = "2026-03-05T15:54:47.864Z" },
    { url = "https://files.pythonhosted.org/packages/3d/66/7516d23f53cdf90f43fce24ab80c28f45e6851d78b46bef8c02084edf583/mmh3-5.2.1-cp313-cp313-macosx_10_13_universal2.whl", hash = "sha256:d51fde50a77f81330523562e3c2734ffdca9c4c9e9d355478117905e1cfe16c6", size = 56078, upload-time = "2026-03-05T15:54:48.9Z" },
    { url = "https://files.pythonhosted.org/packages/bc/34/4d152fdf4a91a132cb226b671f11c6b796eada9ab78080fb5ce1e95adaab/mmh3-5.2.1-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:19bbd3b841174ae6ed588536ab5e1b1fe83d046e668602c20266547298d939a9", size = 40498, upload-time = "2026-03-05T15:54:49.942Z" },
    { url = "https://files.pythonhosted.org/packages/d4/4c/8e3af1b6d85a299767ec97bd923f12b06267089c1472c27c1696870d1175/mmh3-5.2.1-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:be77c402d5e882b6fbacfd90823f13da8e0a69658405a39a569c6b58fdb17b03", size = 40033, upload-time = "2026-03-05T15:54:50.994Z" },
    { url = "https://files.pythonhosted.org/packages/8b/f2/966ea560e32578d453c9e9db53d602cbb1d0da27317e232afa7c38ceba11/mmh3-5.2.1-cp313-cp313-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:fd96476f04db5ceba1cfa0f21228f67c1f7402296f0e73fee3513aa680ad237b", size = 97320, upload-time = "2026-03-05T15:54:52.072Z" },
    { url = "https://files.pythonhosted.org/packages/bb/0d/2c5f9893b38aeb6b034d1a44ecd55a010148054f6a516abe53b5e4057297/mmh3-5.2.1-cp313-cp313-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:707151644085dd0f20fe4f4b573d28e5130c4aaa5f587e95b60989c5926653b5", size = 103299, upload-time = "2026-03-05T15:54:53.569Z" },
    { url = "https://files.pythonhosted.org/packages/1c/fc/2ebaef4a4d4376f89761274dc274035ffd96006ab496b4ee5af9b08f21a9/mmh3-5.2.1-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:3737303ca9ea0f7cb83028781148fcda4f1dac7821db0c47672971dabcf63593", size = 106222, upload-time = "2026-03-05T15:54:55.092Z" },
    { url = "https://files.pythonhosted.org/packages/57/09/ea7ffe126d0ba0406622602a2d05e1e1a6841cc92fc322eb576c95b27fad/mmh3-5.2.1-cp313-cp313-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:2778fed822d7db23ac5008b181441af0c869455b2e7d001f4019636ac31b6fe4", size = 113048, upload-time = "2026-03-05T15:54:56.305Z" },
    { url = "https://files.pythonhosted.org/packages/85/57/9447032edf93a64aa9bef4d9aa596400b1756f40411890f77a284f6293ca/mmh3-5.2.1-cp313-cp313-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:d57dea657357230cc780e13920d7fa7db059d58fe721c80020f94476da4ca0a1", size = 120742, upload-time = "2026-03-05T15:54:57.453Z" },
    { url = "https://files.pythonhosted.org/packages/53/82/a86cc87cc88c92e9e1a598fee509f0409435b57879a6129bf3b3e40513c7/mmh3-5.2.1-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:169e0d178cb59314456ab30772429a802b25d13227088085b0d49b9fe1533104", size = 99132, upload-time = "2026-03-05T15:54:58.583Z" },
    { url = "https://files.pythonhosted.org/packages/54/f7/6b16eb1b40ee89bb740698735574536bc20d6cdafc65ae702ea235578e05/mmh3-5.2.1-cp313-cp313-musllinux_1_2_i686.whl", hash = "sha256:7e4e1f580033335c6f76d1e0d6b56baf009d1a64d6a4816347e4271ba951f46d", size = 98686, upload-time = "2026-03-05T15:55:00.078Z" },
    { url = "https://files.pythonhosted.org/packages/e8/88/a601e9f32ad1410f438a6d0544298ea621f989bd34a0731a7190f7dec799/mmh3-5.2.1-cp313-cp313-musllinux_1_2_ppc64le.whl", hash = "sha256:2bd9f19f7f1fcebd74e830f4af0f28adad4975d40d80620be19ffb2b2af56c9f", size = 106479, upload-time = "2026-03-05T15:55:01.532Z" },
    { url = "https://files.pythonhosted.org/packages/d6/5c/ce29ae3dfc4feec4007a437a1b7435fb9507532a25147602cd5b52be86db/mmh3-5.2.1-cp313-cp313-musllinux_1_2_s390x.whl", hash = "sha256:c88653877aeb514c089d1b3d473451677b8b9a6d1497dbddf1ae7934518b06d2", size = 110030, upload-time = "2026-03-05T15:55:02.934Z" },
    { url = "https://files.pythonhosted.org/packages/13/30/ae444ef2ff87c805d525da4fa63d27cda4fe8a48e77003a036b8461cfd5c/mmh3-5.2.1-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:fceef7fe67c81e1585198215e42ad3fdba3a25644beda8fbdaf85f4d7b93175a", size = 97536, upload-time = "2026-03-05T15:55:04.135Z" },
    { url = "https://files.pythonhosted.org/packages/4b/f9/dc3787ee5c813cc27fe79f45ad4500d9b5437f23a7402435cc34e07c7718/mmh3-5.2.1-cp313-cp313-win32.whl", hash = "sha256:54b64fb2433bc71488e7a449603bf8bd31fbcf9cb56fbe1eb6d459e90b86c37b", size = 40769, upload-time = "2026-03-05T15:55:05.277Z" },
    { url = "https://files.pythonhosted.org/packages/43/67/850e0b5a1e97799822ebfc4ca0e8c6ece3ed8baf7dcdf64de817dfdda2ca/mmh3-5.2.1-cp313-cp313-win_amd64.whl", hash = "sha256:cae6383181f1e345317742d2ddd88f9e7d2682fa4c9432e3a74e47d92dce0229", size = 41563, upload-time = "2026-03-05T15:55:06.283Z" },
    { url = "https://files.pythonhosted.org/packages/c0/cc/98c90b28e1da5458e19fbfaf4adb5289208d3bfccd45dd14eab216a2f0bb/mmh3-5.2.1-cp313-cp313-win_arm64.whl", hash = "sha256:022aa1a528604e6c83d0a7705fdef0b5355d897a9e0fa3a8d26709ceaa06965d", size = 39310, upload-time = "2026-03-05T15:55:07.323Z" },
    { url = "https://files.pythonhosted.org/packages/63/b4/65bc1fb2bb7f83e91c30865023b1847cf89a5f237165575e8c83aa536584/mmh3-5.2.1-cp314-cp314-android_24_arm64_v8a.whl", hash = "sha256:d771f085fcdf4035786adfb1d8db026df1eb4b41dac1c3d070d1e49512843227", size = 40794, upload-time = "2026-03-05T15:55:09.773Z" },
    { url = "https://files.pythonhosted.org/packages/c4/86/7168b3d83be8eb553897b1fac9da8bbb06568e5cfe555ffc329ebb46f59d/mmh3-5.2.1-cp314-cp314-android_24_x86_64.whl", hash = "sha256:7f196cd7910d71e9d9860da0ff7a77f64d22c1ad931f1dd18559a06e03109fc0", size = 41923, upload-time = "2026-03-05T15:55:10.924Z" },
    { url = "https://files.pythonhosted.org/packages/bf/9b/b653ab611c9060ce8ff0ba25c0226757755725e789292f3ca138a58082cd/mmh3-5.2.1-cp314-cp314-ios_13_0_arm64_iphoneos.whl", hash = "sha256:b1f12bd684887a0a5d55e6363ca87056f361e45451105012d329b86ec19dbe0b", size = 39131, upload-time = "2026-03-05T15:55:11.961Z" },
    { url = "https://files.pythonhosted.org/packages/9b/b4/5a2e0d34ab4d33543f01121e832395ea510132ea8e52cdf63926d9d81754/mmh3-5.2.1-cp314-cp314-ios_13_0_arm64_iphonesimulator.whl", hash = "sha256:d106493a60dcb4aef35a0fac85105e150a11cf8bc2b0d388f5a33272d756c966", size = 39825, upload-time = "2026-03-05T15:55:13.013Z" },
    { url = "https://files.pythonhosted.org/packages/bd/69/81699a8f39a3f8d368bec6443435c0c392df0d200ad915bf0d222b588e03/mmh3-5.2.1-cp314-cp314-ios_13_0_x86_64_iphonesimulator.whl", hash = "sha256:44983e45310ee5b9f73397350251cdf6e63a466406a105f1d16cb5baa659270b", size = 40344, upload-time = "2026-03-05T15:55:14.026Z" },
    { url = "https://files.pythonhosted.org/packages/0c/b3/71c8c775807606e8fd8acc5c69016e1caf3200d50b50b6dd4b40ce10b76c/mmh3-5.2.1-cp314-cp314-macosx_10_15_universal2.whl", hash = "sha256:368625fb01666655985391dbad3860dc0ba7c0d6b9125819f3121ee7292b4ac8", size = 56291, upload-time = "2026-03-05T15:55:15.137Z" },
    { url = "https://files.pythonhosted.org/packages/6f/75/2c24517d4b2ce9e4917362d24f274d3d541346af764430249ddcc4cb3a08/mmh3-5.2.1-cp314-cp314-macosx_10_15_x86_64.whl", hash = "sha256:72d1cc63bcc91e14933f77d51b3df899d6a07d184ec515ea7f56bff659e124d7", size = 40575, upload-time = "2026-03-05T15:55:16.518Z" },
    { url = "https://files.pythonhosted.org/packages/bf/b9/e4a360164365ac9f07a25f0f7928e3a66eb9ecc989384060747aa170e6aa/mmh3-5.2.1-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:e8b4b5580280b9265af3e0409974fb79c64cf7523632d03fbf11df18f8b0181e", size = 40052, upload-time = "2026-03-05T15:55:17.735Z" },
    { url = "https://files.pythonhosted.org/packages/97/ca/120d92223a7546131bbbc31c9174168ee7a73b1366f5463ffe69d9e691fe/mmh3-5.2.1-cp314-cp314-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:4cbbde66f1183db040daede83dd86c06d663c5bb2af6de1142b7c8c37923dd74", size = 97311, upload-time = "2026-03-05T15:55:18.959Z" },
    { url = "https://files.pythonhosted.org/packages/b6/71/c1a60c1652b8813ef9de6d289784847355417ee0f2980bca002fe87f4ae5/mmh3-5.2.1-cp314-cp314-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:8ff038d52ef6aa0f309feeba00c5095c9118d0abf787e8e8454d6048db2037fc", size = 103279, upload-time = "2026-03-05T15:55:20.448Z" },
    { url = "https://files.pythonhosted.org/packages/48/29/ad97f4be1509cdcb28ae32c15593ce7c415db47ace37f8fad35b493faa9a/mmh3-5.2.1-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:a4130d0b9ce5fad6af07421b1aecc7e079519f70d6c05729ab871794eded8617", size = 106290, upload-time = "2026-03-05T15:55:21.6Z" },
    { url = "https://files.pythonhosted.org/packages/77/29/1f86d22e281bd8827ba373600a4a8b0c0eae5ca6aa55b9a8c26d2a34decc/mmh3-5.2.1-cp314-cp314-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:f6e0bfe77d238308839699944164b96a2eeccaf55f2af400f54dc20669d8d5f2", size = 113116, upload-time = "2026-03-05T15:55:22.826Z" },
    { url = "https://files.pythonhosted.org/packages/a7/7c/339971ea7ed4c12d98f421f13db3ea576a9114082ccb59d2d1a0f00ccac1/mmh3-5.2.1-cp314-cp314-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:f963eafc0a77a6c0562397da004f5876a9bcf7265a7bcc3205e29636bc4a1312", size = 120740, upload-time = "2026-03-05T15:55:24.3Z" },
    { url = "https://files.pythonhosted.org/packages/e4/92/3c7c4bdb8e926bb3c972d1e2907d77960c1c4b250b41e8366cf20c6e4373/mmh3-5.2.1-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:92883836caf50d5255be03d988d75bc93e3f86ba247b7ca137347c323f731deb", size = 99143, upload-time = "2026-03-05T15:55:25.456Z" },
    { url = "https://files.pythonhosted.org/packages/df/0a/33dd8706e732458c8375eae63c981292de07a406bad4ec03e5269654aa2c/mmh3-5.2.1-cp314-cp314-musllinux_1_2_i686.whl", hash = "sha256:57b52603e89355ff318025dd55158f6e71396c0f1f609d548e9ea9c94cc6ce0a", size = 98703, upload-time = "2026-03-05T15:55:26.723Z" },
    { url = "https://files.pythonhosted.org/packages/51/04/76bbce05df76cbc3d396f13b2ea5b1578ef02b6a5187e132c6c33f99d596/mmh3-5.2.1-cp314-cp314-musllinux_1_2_ppc64le.whl", hash = "sha256:f40a95186a72fa0b67d15fef0f157bfcda00b4f59c8a07cbe5530d41ac35d105", size = 106484, upload-time = "2026-03-05T15:55:28.214Z" },
    { url = "https://files.pythonhosted.org/packages/d3/8f/c6e204a2c70b719c1f62ffd9da27aef2dddcba875ea9c31ca0e87b975a46/mmh3-5.2.1-cp314-cp314-musllinux_1_2_s390x.whl", hash = "sha256:58370d05d033ee97224c81263af123dea3d931025030fd34b61227a768a8858a", size = 110012, upload-time = "2026-03-05T15:55:29.532Z" },
    { url = "https://files.pythonhosted.org/packages/e3/37/7181efd8e39db386c1ebc3e6b7d1f702a09d7c1197a6f2742ed6b5c16597/mmh3-5.2.1-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:7be6dfb49e48fd0a7d91ff758a2b51336f1cd21f9d44b20f6801f072bd080cdd", size = 97508, upload-time = "2026-03-05T15:55:31.01Z" },
    { url = "https://files.pythonhosted.org/packages/42/0f/afa7ca2615fd85e1469474bb860e381443d0b868c083b62b41cb1d7ca32f/mmh3-5.2.1-cp314-cp314-win32.whl", hash = "sha256:54fe8518abe06a4c3852754bfd498b30cc58e667f376c513eac89a244ce781a4", size = 41387, upload-time = "2026-03-05T15:55:32.403Z" },
    { url = "https://files.pythonhosted.org/packages/71/0d/46d42a260ee1357db3d486e6c7a692e303c017968e14865e00efa10d09fc/mmh3-5.2.1-cp314-cp314-win_amd64.whl", hash = "sha256:3f796b535008708846044c43302719c6956f39ca2d93f2edda5319e79a29efbb", size = 42101, upload-time = "2026-03-05T15:55:33.646Z" },
    { url = "https://files.pythonhosted.org/packages/a4/7b/848a8378059d96501a41159fca90d6a99e89736b0afbe8e8edffeac8c74b/mmh3-5.2.1-cp314-cp314-win_arm64.whl", hash = "sha256:cd471ede0d802dd936b6fab28188302b2d497f68436025857ca72cd3810423fe", size = 39836, upload-time = "2026-03-05T15:55:35.026Z" },
    { url = "https://files.pythonhosted.org/packages/27/61/1dabea76c011ba8547c25d30c91c0ec22544487a8750997a27a0c9e1180b/mmh3-5.2.1-cp314-cp314t-macosx_10_15_universal2.whl", hash = "sha256:5174a697ce042fa77c407e05efe41e03aa56dae9ec67388055820fb48cf4c3ba", size = 57727, upload-time = "2026-03-05T15:55:36.162Z" },
    { url = "https://files.pythonhosted.org/packages/b7/32/731185950d1cf2d5e28979cc8593016ba1619a295faba10dda664a4931b5/mmh3-5.2.1-cp314-cp314t-macosx_10_15_x86_64.whl", hash = "sha256:0a3984146e414684a6be2862d84fcb1035f4984851cb81b26d933bab6119bf00", size = 41308, upload-time = "2026-03-05T15:55:37.254Z" },
    { url = "https://files.pythonhosted.org/packages/76/aa/66c76801c24b8c9418b4edde9b5e57c75e72c94e29c48f707e3962534f18/mmh3-5.2.1-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:bd6e7d363aa93bd3421b30b6af97064daf47bc96005bddba67c5ffbc6df426b8", size = 40758, upload-time = "2026-03-05T15:55:38.61Z" },
    { url = "https://files.pythonhosted.org/packages/9e/bb/79a1f638a02f0ae389f706d13891e2fbf7d8c0a22ecde67ba828951bb60a/mmh3-5.2.1-cp314-cp314t-manylinux1_i686.manylinux_2_28_i686.manylinux_2_5_i686.whl", hash = "sha256:113f78e7463a36dbbcea05bfe688efd7fa759d0f0c56e73c974d60dcfec3dfcc", size = 109670, upload-time = "2026-03-05T15:55:40.13Z" },
    { url = "https://files.pythonhosted.org/packages/26/94/8cd0e187a288985bcfc79bf5144d1d712df9dee74365f59d26e3a1865be6/mmh3-5.2.1-cp314-cp314t-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl", hash = "sha256:7e8ec5f606e0809426d2440e0683509fb605a8820a21ebd120dcdba61b74ef7f", size = 117399, upload-time = "2026-03-05T15:55:42.076Z" },
    { url = "https://files.pythonhosted.org/packages/42/94/dfea6059bd5c5beda565f58a4096e43f4858fb6d2862806b8bbd12cbb284/mmh3-5.2.1-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:22b0f9971ec4e07e8223f2beebe96a6cfc779d940b6f27d26604040dd74d3a44", size = 120386, upload-time = "2026-03-05T15:55:43.481Z" },
    { url = "https://files.pythonhosted.org/packages/47/cb/f9c45e62aaa67220179f487772461d891bb582bb2f9783c944832c60efd9/mmh3-5.2.1-cp314-cp314t-manylinux2014_ppc64le.manylinux_2_17_ppc64le.manylinux_2_28_ppc64le.whl", hash = "sha256:85ffc9920ffc39c5eee1e3ac9100c913a0973996fbad5111f939bbda49204bb7", size = 125924, upload-time = "2026-03-05T15:55:44.638Z" },
    { url = "https://files.pythonhosted.org/packages/a5/83/fe54a4a7c11bc9f623dfc1707decd034245602b076dfc1dcc771a4163170/mmh3-5.2.1-cp314-cp314t-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:7aec798c2b01aaa65a55f1124f3405804184373abb318a3091325aece235f67c", size = 135280, upload-time = "2026-03-05T15:55:45.866Z" },
    { url = "https://files.pythonhosted.org/packages/97/67/fe7e9e9c143daddd210cd22aef89cbc425d58ecf238d2b7d9eb0da974105/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:55dbbd8ffbc40d1697d5e2d0375b08599dae8746b0b08dea05eee4ce81648fac", size = 110050, upload-time = "2026-03-05T15:55:47.074Z" },
    { url = "https://files.pythonhosted.org/packages/43/c4/6d4b09fcbef80794de447c9378e39eefc047156b290fa3dd2d5257ca8227/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_i686.whl", hash = "sha256:6c85c38a279ca9295a69b9b088a2e48aa49737bb1b34e6a9dc6297c110e8d912", size = 111158, upload-time = "2026-03-05T15:55:48.239Z" },
    { url = "https://files.pythonhosted.org/packages/81/a6/ca51c864bdb30524beb055a6d8826db3906af0834ec8c41d097a6e8573d5/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_ppc64le.whl", hash = "sha256:6290289fa5fb4c70fd7f72016e03633d60388185483ff3b162912c81205ae2cf", size = 116890, upload-time = "2026-03-05T15:55:49.405Z" },
    { url = "https://files.pythonhosted.org/packages/cc/04/5a1fe2e2ad843d03e89af25238cbc4f6840a8bb6c4329a98ab694c71deda/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_s390x.whl", hash = "sha256:4fc6cd65dc4d2fdb2625e288939a3566e36127a84811a4913f02f3d5931da52d", size = 123121, upload-time = "2026-03-05T15:55:50.61Z" },
    { url = "https://files.pythonhosted.org/packages/af/4d/3c820c6f4897afd25905270a9f2330a23f77a207ea7356f7aadace7273c0/mmh3-5.2.1-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:623f938f6a039536cc02b7582a07a080f13fdfd48f87e63201d92d7e34d09a18", size = 110187, upload-time = "2026-03-05T15:55:52.143Z" },
    { url = "https://files.pythonhosted.org/packages/21/54/1d71cd143752361c0aebef16ad3f55926a6faf7b112d355745c1f8a25f7f/mmh3-5.2.1-cp314-cp314t-win32.whl", hash = "sha256:29bc3973676ae334412efdd367fcd11d036b7be3efc1ce2407ef8676dabfeb82", size = 41934, upload-time = "2026-03-05T15:55:53.564Z" },
    { url = "https://files.pythonhosted.org/packages/9d/e4/63a2a88f31d93dea03947cccc2a076946857e799ea4f7acdecbf43b324aa/mmh3-5.2.1-cp314-cp314t-win_amd64.whl", hash = "sha256:28cfab66577000b9505a0d068c731aee7ca85cd26d4d63881fab17857e0fe1fb", size = 43036, upload-time = "2026-03-05T15:55:55.252Z" },
    { url = "https://files.pythonhosted.org/packages/a0/0f/59204bf136d1201f8d7884cfbaf7498c5b4674e87a4c693f9bde63741ce1/mmh3-5.2.1-cp314-cp314t-win_arm64.whl", hash = "sha256:dfd51b4c56b673dfbc43d7d27ef857dd91124801e2806c69bb45585ce0fa019b", size = 40391, upload-time = "2026-03-05T15:55:56.697Z" },
]

[[package]]
name = "mpmath"
version = "1.3.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/e0/47/dd32fa426cc72114383ac549964eecb20ecfd886d1e5ccf5340b55b02f57/mpmath-1.3.0.tar.gz", hash = "sha256:7a28eb2a9774d00c7bc92411c19a89209d5da7c4c9a9e227be8330a23a25b91f", size = 508106, upload-time = "2023-03-07T16:47:11.061Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/43/e3/7d92a15f894aa0c9c4b49b8ee9ac9850d6e63b03c9c32c0367a13ae62209/mpmath-1.3.0-py3-none-any.whl", hash = "sha256:a0b2b9fe80bbcd81a6647ff13108738cfb482d481d826cc0e02f5b35e5c88d2c", size = 536198, upload-time = "2023-03-07T16:47:09.197Z" },
]

[[package]]
name = "numpy"
version = "2.4.3"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/10/8b/c265f4823726ab832de836cdd184d0986dcf94480f81e8739692a7ac7af2/numpy-2.4.3.tar.gz", hash = "sha256:483a201202b73495f00dbc83796c6ae63137a9bdade074f7648b3e32613412dd", size = 20727743, upload-time = "2026-03-09T07:58:53.426Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/f9/51/5093a2df15c4dc19da3f79d1021e891f5dcf1d9d1db6ba38891d5590f3fe/numpy-2.4.3-cp311-cp311-macosx_10_9_x86_64.whl", hash = "sha256:33b3bf58ee84b172c067f56aeadc7ee9ab6de69c5e800ab5b10295d54c581adb", size = 16957183, upload-time = "2026-03-09T07:55:57.774Z" },
    { url = "https://files.pythonhosted.org/packages/b5/7c/c061f3de0630941073d2598dc271ac2f6cbcf5c83c74a5870fea07488333/numpy-2.4.3-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:8ba7b51e71c05aa1f9bc3641463cd82308eab40ce0d5c7e1fd4038cbf9938147", size = 14968734, upload-time = "2026-03-09T07:56:00.494Z" },
    { url = "https://files.pythonhosted.org/packages/ef/27/d26c85cbcd86b26e4f125b0668e7a7c0542d19dd7d23ee12e87b550e95b5/numpy-2.4.3-cp311-cp311-macosx_14_0_arm64.whl", hash = "sha256:a1988292870c7cb9d0ebb4cc96b4d447513a9644801de54606dc7aabf2b7d920", size = 5475288, upload-time = "2026-03-09T07:56:02.857Z" },
    { url = "https://files.pythonhosted.org/packages/2b/09/3c4abbc1dcd8010bf1a611d174c7aa689fc505585ec806111b4406f6f1b1/numpy-2.4.3-cp311-cp311-macosx_14_0_x86_64.whl", hash = "sha256:23b46bb6d8ecb68b58c09944483c135ae5f0e9b8d8858ece5e4ead783771d2a9", size = 6805253, upload-time = "2026-03-09T07:56:04.53Z" },
    { url = "https://files.pythonhosted.org/packages/21/bc/e7aa3f6817e40c3f517d407742337cbb8e6fc4b83ce0b55ab780c829243b/numpy-2.4.3-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:a016db5c5dba78fa8fe9f5d80d6708f9c42ab087a739803c0ac83a43d686a470", size = 15969479, upload-time = "2026-03-09T07:56:06.638Z" },
    { url = "https://files.pythonhosted.org/packages/78/51/9f5d7a41f0b51649ddf2f2320595e15e122a40610b233d51928dd6c92353/numpy-2.4.3-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:715de7f82e192e8cae5a507a347d97ad17598f8e026152ca97233e3666daaa71", size = 16901035, upload-time = "2026-03-09T07:56:09.405Z" },
    { url = "https://files.pythonhosted.org/packages/64/6e/b221dd847d7181bc5ee4857bfb026182ef69499f9305eb1371cbb1aea626/numpy-2.4.3-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:2ddb7919366ee468342b91dea2352824c25b55814a987847b6c52003a7c97f15", size = 17325657, upload-time = "2026-03-09T07:56:12.067Z" },
    { url = "https://files.pythonhosted.org/packages/eb/b8/8f3fd2da596e1063964b758b5e3c970aed1949a05200d7e3d46a9d46d643/numpy-2.4.3-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:a315e5234d88067f2d97e1f2ef670a7569df445d55400f1e33d117418d008d52", size = 18635512, upload-time = "2026-03-09T07:56:14.629Z" },
    { url = "https://files.pythonhosted.org/packages/5c/24/2993b775c37e39d2f8ab4125b44337ab0b2ba106c100980b7c274a22bee7/numpy-2.4.3-cp311-cp311-win32.whl", hash = "sha256:2b3f8d2c4589b1a2028d2a770b0fc4d1f332fb5e01521f4de3199a896d158ddd", size = 6238100, upload-time = "2026-03-09T07:56:17.243Z" },
    { url = "https://files.pythonhosted.org/packages/76/1d/edccf27adedb754db7c4511d5eac8b83f004ae948fe2d3509e8b78097d4c/numpy-2.4.3-cp311-cp311-win_amd64.whl", hash = "sha256:77e76d932c49a75617c6d13464e41203cd410956614d0a0e999b25e9e8d27eec", size = 12609816, upload-time = "2026-03-09T07:56:19.089Z" },
    { url = "https://files.pythonhosted.org/packages/92/82/190b99153480076c8dce85f4cfe7d53ea84444145ffa54cb58dcd460d66b/numpy-2.4.3-cp311-cp311-win_arm64.whl", hash = "sha256:eb610595dd91560905c132c709412b512135a60f1851ccbd2c959e136431ff67", size = 10485757, upload-time = "2026-03-09T07:56:21.753Z" },
    { url = "https://files.pythonhosted.org/packages/a9/ed/6388632536f9788cea23a3a1b629f25b43eaacd7d7377e5d6bc7b9deb69b/numpy-2.4.3-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:61b0cbabbb6126c8df63b9a3a0c4b1f44ebca5e12ff6997b80fcf267fb3150ef", size = 16669628, upload-time = "2026-03-09T07:56:24.252Z" },
    { url = "https://files.pythonhosted.org/packages/74/1b/ee2abfc68e1ce728b2958b6ba831d65c62e1b13ce3017c13943f8f9b5b2e/numpy-2.4.3-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:7395e69ff32526710748f92cd8c9849b361830968ea3e24a676f272653e8983e", size = 14696872, upload-time = "2026-03-09T07:56:26.991Z" },
    { url = "https://files.pythonhosted.org/packages/ba/d1/780400e915ff5638166f11ca9dc2c5815189f3d7cf6f8759a1685e586413/numpy-2.4.3-cp312-cp312-macosx_14_0_arm64.whl", hash = "sha256:abdce0f71dcb4a00e4e77f3faf05e4616ceccfe72ccaa07f47ee79cda3b7b0f4", size = 5203489, upload-time = "2026-03-09T07:56:29.414Z" },
    { url = "https://files.pythonhosted.org/packages/0b/bb/baffa907e9da4cc34a6e556d6d90e032f6d7a75ea47968ea92b4858826c4/numpy-2.4.3-cp312-cp312-macosx_14_0_x86_64.whl", hash = "sha256:48da3a4ee1336454b07497ff7ec83903efa5505792c4e6d9bf83d99dc07a1e18", size = 6550814, upload-time = "2026-03-09T07:56:32.225Z" },
    { url = "https://files.pythonhosted.org/packages/7b/12/8c9f0c6c95f76aeb20fc4a699c33e9f827fa0d0f857747c73bb7b17af945/numpy-2.4.3-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:32e3bef222ad6b052280311d1d60db8e259e4947052c3ae7dd6817451fc8a4c5", size = 15666601, upload-time = "2026-03-09T07:56:34.461Z" },
    { url = "https://files.pythonhosted.org/packages/bd/79/cc665495e4d57d0aa6fbcc0aa57aa82671dfc78fbf95fe733ed86d98f52a/numpy-2.4.3-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:e7dd01a46700b1967487141a66ac1a3cf0dd8ebf1f08db37d46389401512ca97", size = 16621358, upload-time = "2026-03-09T07:56:36.852Z" },
    { url = "https://files.pythonhosted.org/packages/a8/40/b4ecb7224af1065c3539f5ecfff879d090de09608ad1008f02c05c770cb3/numpy-2.4.3-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:76f0f283506c28b12bba319c0fab98217e9f9b54e6160e9c79e9f7348ba32e9c", size = 17016135, upload-time = "2026-03-09T07:56:39.337Z" },
    { url = "https://files.pythonhosted.org/packages/f7/b1/6a88e888052eed951afed7a142dcdf3b149a030ca59b4c71eef085858e43/numpy-2.4.3-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:737f630a337364665aba3b5a77e56a68cc42d350edd010c345d65a3efa3addcc", size = 18345816, upload-time = "2026-03-09T07:56:42.31Z" },
    { url = "https://files.pythonhosted.org/packages/f3/8f/103a60c5f8c3d7fc678c19cd7b2476110da689ccb80bc18050efbaeae183/numpy-2.4.3-cp312-cp312-win32.whl", hash = "sha256:26952e18d82a1dbbc2f008d402021baa8d6fc8e84347a2072a25e08b46d698b9", size = 5960132, upload-time = "2026-03-09T07:56:44.851Z" },
    { url = "https://files.pythonhosted.org/packages/d7/7c/f5ee1bf6ed888494978046a809df2882aad35d414b622893322df7286879/numpy-2.4.3-cp312-cp312-win_amd64.whl", hash = "sha256:65f3c2455188f09678355f5cae1f959a06b778bc66d535da07bf2ef20cd319d5", size = 12316144, upload-time = "2026-03-09T07:56:47.057Z" },
    { url = "https://files.pythonhosted.org/packages/71/46/8d1cb3f7a00f2fb6394140e7e6623696e54c6318a9d9691bb4904672cf42/numpy-2.4.3-cp312-cp312-win_arm64.whl", hash = "sha256:2abad5c7fef172b3377502bde47892439bae394a71bc329f31df0fd829b41a9e", size = 10220364, upload-time = "2026-03-09T07:56:49.849Z" },
    { url = "https://files.pythonhosted.org/packages/b6/d0/1fe47a98ce0df229238b77611340aff92d52691bcbc10583303181abf7fc/numpy-2.4.3-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:b346845443716c8e542d54112966383b448f4a3ba5c66409771b8c0889485dd3", size = 16665297, upload-time = "2026-03-09T07:56:52.296Z" },
    { url = "https://files.pythonhosted.org/packages/27/d9/4e7c3f0e68dfa91f21c6fb6cf839bc829ec920688b1ce7ec722b1a6202fb/numpy-2.4.3-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:2629289168f4897a3c4e23dc98d6f1731f0fc0fe52fb9db19f974041e4cc12b9", size = 14691853, upload-time = "2026-03-09T07:56:54.992Z" },
    { url = "https://files.pythonhosted.org/packages/3a/66/bd096b13a87549683812b53ab211e6d413497f84e794fb3c39191948da97/numpy-2.4.3-cp313-cp313-macosx_14_0_arm64.whl", hash = "sha256:bb2e3cf95854233799013779216c57e153c1ee67a0bf92138acca0e429aefaee", size = 5198435, upload-time = "2026-03-09T07:56:57.184Z" },
    { url = "https://files.pythonhosted.org/packages/a2/2f/687722910b5a5601de2135c891108f51dfc873d8e43c8ed9f4ebb440b4a2/numpy-2.4.3-cp313-cp313-macosx_14_0_x86_64.whl", hash = "sha256:7f3408ff897f8ab07a07fbe2823d7aee6ff644c097cc1f90382511fe982f647f", size = 6546347, upload-time = "2026-03-09T07:56:59.531Z" },
    { url = "https://files.pythonhosted.org/packages/bf/ec/7971c4e98d86c564750393fab8d7d83d0a9432a9d78bb8a163a6dc59967a/numpy-2.4.3-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:decb0eb8a53c3b009b0962378065589685d66b23467ef5dac16cbe818afde27f", size = 15664626, upload-time = "2026-03-09T07:57:01.385Z" },
    { url = "https://files.pythonhosted.org/packages/7e/eb/7daecbea84ec935b7fc732e18f532073064a3816f0932a40a17f3349185f/numpy-2.4.3-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:d5f51900414fc9204a0e0da158ba2ac52b75656e7dce7e77fb9f84bfa343b4cc", size = 16608916, upload-time = "2026-03-09T07:57:04.008Z" },
    { url = "https://files.pythonhosted.org/packages/df/58/2a2b4a817ffd7472dca4421d9f0776898b364154e30c95f42195041dc03b/numpy-2.4.3-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:6bd06731541f89cdc01b261ba2c9e037f1543df7472517836b78dfb15bd6e476", size = 17015824, upload-time = "2026-03-09T07:57:06.347Z" },
    { url = "https://files.pythonhosted.org/packages/4a/ca/627a828d44e78a418c55f82dd4caea8ea4a8ef24e5144d9e71016e52fb40/numpy-2.4.3-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:22654fe6be0e5206f553a9250762c653d3698e46686eee53b399ab90da59bd92", size = 18334581, upload-time = "2026-03-09T07:57:09.114Z" },
    { url = "https://files.pythonhosted.org/packages/cd/c0/76f93962fc79955fcba30a429b62304332345f22d4daec1cb33653425643/numpy-2.4.3-cp313-cp313-win32.whl", hash = "sha256:d71e379452a2f670ccb689ec801b1218cd3983e253105d6e83780967e899d687", size = 5958618, upload-time = "2026-03-09T07:57:11.432Z" },
    { url = "https://files.pythonhosted.org/packages/b1/3c/88af0040119209b9b5cb59485fa48b76f372c73068dbf9254784b975ac53/numpy-2.4.3-cp313-cp313-win_amd64.whl", hash = "sha256:0a60e17a14d640f49146cb38e3f105f571318db7826d9b6fef7e4dce758faecd", size = 12312824, upload-time = "2026-03-09T07:57:13.586Z" },
    { url = "https://files.pythonhosted.org/packages/58/ce/3d07743aced3d173f877c3ef6a454c2174ba42b584ab0b7e6d99374f51ed/numpy-2.4.3-cp313-cp313-win_arm64.whl", hash = "sha256:c9619741e9da2059cd9c3f206110b97583c7152c1dc9f8aafd4beb450ac1c89d", size = 10221218, upload-time = "2026-03-09T07:57:16.183Z" },
    { url = "https://files.pythonhosted.org/packages/62/09/d96b02a91d09e9d97862f4fc8bfebf5400f567d8eb1fe4b0cc4795679c15/numpy-2.4.3-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:7aa4e54f6469300ebca1d9eb80acd5253cdfa36f2c03d79a35883687da430875", size = 14819570, upload-time = "2026-03-09T07:57:18.564Z" },
    { url = "https://files.pythonhosted.org/packages/b5/ca/0b1aba3905fdfa3373d523b2b15b19029f4f3031c87f4066bd9d20ef6c6b/numpy-2.4.3-cp313-cp313t-macosx_14_0_arm64.whl", hash = "sha256:d1b90d840b25874cf5cd20c219af10bac3667db3876d9a495609273ebe679070", size = 5326113, upload-time = "2026-03-09T07:57:21.052Z" },
    { url = "https://files.pythonhosted.org/packages/c0/63/406e0fd32fcaeb94180fd6a4c41e55736d676c54346b7efbce548b94a914/numpy-2.4.3-cp313-cp313t-macosx_14_0_x86_64.whl", hash = "sha256:a749547700de0a20a6718293396ec237bb38218049cfce788e08fcb716e8cf73", size = 6646370, upload-time = "2026-03-09T07:57:22.804Z" },
    { url = "https://files.pythonhosted.org/packages/b6/d0/10f7dc157d4b37af92720a196be6f54f889e90dcd30dce9dc657ed92c257/numpy-2.4.3-cp313-cp313t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:94f3c4a151a2e529adf49c1d54f0f57ff8f9b233ee4d44af623a81553ab86368", size = 15723499, upload-time = "2026-03-09T07:57:24.693Z" },
    { url = "https://files.pythonhosted.org/packages/66/f1/d1c2bf1161396629701bc284d958dc1efa3a5a542aab83cf11ee6eb4cba5/numpy-2.4.3-cp313-cp313t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:22c31dc07025123aedf7f2db9e91783df13f1776dc52c6b22c620870dc0fab22", size = 16657164, upload-time = "2026-03-09T07:57:27.676Z" },
    { url = "https://files.pythonhosted.org/packages/1a/be/cca19230b740af199ac47331a21c71e7a3d0ba59661350483c1600d28c37/numpy-2.4.3-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:148d59127ac95979d6f07e4d460f934ebdd6eed641db9c0db6c73026f2b2101a", size = 17081544, upload-time = "2026-03-09T07:57:30.664Z" },
    { url = "https://files.pythonhosted.org/packages/b9/c5/9602b0cbb703a0936fb40f8a95407e8171935b15846de2f0776e08af04c7/numpy-2.4.3-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:a97cbf7e905c435865c2d939af3d93f99d18eaaa3cabe4256f4304fb51604349", size = 18380290, upload-time = "2026-03-09T07:57:33.763Z" },
    { url = "https://files.pythonhosted.org/packages/ed/81/9f24708953cd30be9ee36ec4778f4b112b45165812f2ada4cc5ea1c1f254/numpy-2.4.3-cp313-cp313t-win32.whl", hash = "sha256:be3b8487d725a77acccc9924f65fd8bce9af7fac8c9820df1049424a2115af6c", size = 6082814, upload-time = "2026-03-09T07:57:36.491Z" },
    { url = "https://files.pythonhosted.org/packages/e2/9e/52f6eaa13e1a799f0ab79066c17f7016a4a8ae0c1aefa58c82b4dab690b4/numpy-2.4.3-cp313-cp313t-win_amd64.whl", hash = "sha256:1ec84fd7c8e652b0f4aaaf2e6e9cc8eaa9b1b80a537e06b2e3a2fb176eedcb26", size = 12452673, upload-time = "2026-03-09T07:57:38.281Z" },
    { url = "https://files.pythonhosted.org/packages/c4/04/b8cece6ead0b30c9fbd99bb835ad7ea0112ac5f39f069788c5558e3b1ab2/numpy-2.4.3-cp313-cp313t-win_arm64.whl", hash = "sha256:120df8c0a81ebbf5b9020c91439fccd85f5e018a927a39f624845be194a2be02", size = 10290907, upload-time = "2026-03-09T07:57:40.747Z" },
    { url = "https://files.pythonhosted.org/packages/70/ae/3936f79adebf8caf81bd7a599b90a561334a658be4dcc7b6329ebf4ee8de/numpy-2.4.3-cp314-cp314-macosx_10_15_x86_64.whl", hash = "sha256:5884ce5c7acfae1e4e1b6fde43797d10aa506074d25b531b4f54bde33c0c31d4", size = 16664563, upload-time = "2026-03-09T07:57:43.817Z" },
    { url = "https://files.pythonhosted.org/packages/9b/62/760f2b55866b496bb1fa7da2a6db076bef908110e568b02fcfc1422e2a3a/numpy-2.4.3-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:297837823f5bc572c5f9379b0c9f3a3365f08492cbdc33bcc3af174372ebb168", size = 14702161, upload-time = "2026-03-09T07:57:46.169Z" },
    { url = "https://files.pythonhosted.org/packages/32/af/a7a39464e2c0a21526fb4fb76e346fb172ebc92f6d1c7a07c2c139cc17b1/numpy-2.4.3-cp314-cp314-macosx_14_0_arm64.whl", hash = "sha256:a111698b4a3f8dcbe54c64a7708f049355abd603e619013c346553c1fd4ca90b", size = 5208738, upload-time = "2026-03-09T07:57:48.506Z" },
    { url = "https://files.pythonhosted.org/packages/29/8c/2a0cf86a59558fa078d83805589c2de490f29ed4fb336c14313a161d358a/numpy-2.4.3-cp314-cp314-macosx_14_0_x86_64.whl", hash = "sha256:4bd4741a6a676770e0e97fe9ab2e51de01183df3dcbcec591d26d331a40de950", size = 6543618, upload-time = "2026-03-09T07:57:50.591Z" },
    { url = "https://files.pythonhosted.org/packages/aa/b8/612ce010c0728b1c363fa4ea3aa4c22fe1c5da1de008486f8c2f5cb92fae/numpy-2.4.3-cp314-cp314-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:54f29b877279d51e210e0c80709ee14ccbbad647810e8f3d375561c45ef613dd", size = 15680676, upload-time = "2026-03-09T07:57:52.34Z" },
    { url = "https://files.pythonhosted.org/packages/a9/7e/4f120ecc54ba26ddf3dc348eeb9eb063f421de65c05fc961941798feea18/numpy-2.4.3-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:679f2a834bae9020f81534671c56fd0cc76dd7e5182f57131478e23d0dc59e24", size = 16613492, upload-time = "2026-03-09T07:57:54.91Z" },
    { url = "https://files.pythonhosted.org/packages/2c/86/1b6020db73be330c4b45d5c6ee4295d59cfeef0e3ea323959d053e5a6909/numpy-2.4.3-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:d84f0f881cb2225c2dfd7f78a10a5645d487a496c6668d6cc39f0f114164f3d0", size = 17031789, upload-time = "2026-03-09T07:57:57.641Z" },
    { url = "https://files.pythonhosted.org/packages/07/3a/3b90463bf41ebc21d1b7e06079f03070334374208c0f9a1f05e4ae8455e7/numpy-2.4.3-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:d213c7e6e8d211888cc359bab7199670a00f5b82c0978b9d1c75baf1eddbeac0", size = 18339941, upload-time = "2026-03-09T07:58:00.577Z" },
    { url = "https://files.pythonhosted.org/packages/a8/74/6d736c4cd962259fd8bae9be27363eb4883a2f9069763747347544c2a487/numpy-2.4.3-cp314-cp314-win32.whl", hash = "sha256:52077feedeff7c76ed7c9f1a0428558e50825347b7545bbb8523da2cd55c547a", size = 6007503, upload-time = "2026-03-09T07:58:03.331Z" },
    { url = "https://files.pythonhosted.org/packages/48/39/c56ef87af669364356bb011922ef0734fc49dad51964568634c72a009488/numpy-2.4.3-cp314-cp314-win_amd64.whl", hash = "sha256:0448e7f9caefb34b4b7dd2b77f21e8906e5d6f0365ad525f9f4f530b13df2afc", size = 12444915, upload-time = "2026-03-09T07:58:06.353Z" },
    { url = "https://files.pythonhosted.org/packages/9d/1f/ab8528e38d295fd349310807496fabb7cf9fe2e1f70b97bc20a483ea9d4a/numpy-2.4.3-cp314-cp314-win_arm64.whl", hash = "sha256:b44fd60341c4d9783039598efadd03617fa28d041fc37d22b62d08f2027fa0e7", size = 10494875, upload-time = "2026-03-09T07:58:08.734Z" },
    { url = "https://files.pythonhosted.org/packages/e6/ef/b7c35e4d5ef141b836658ab21a66d1a573e15b335b1d111d31f26c8ef80f/numpy-2.4.3-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:0a195f4216be9305a73c0e91c9b026a35f2161237cf1c6de9b681637772ea657", size = 14822225, upload-time = "2026-03-09T07:58:11.034Z" },
    { url = "https://files.pythonhosted.org/packages/cd/8d/7730fa9278cf6648639946cc816e7cc89f0d891602584697923375f801ed/numpy-2.4.3-cp314-cp314t-macosx_14_0_arm64.whl", hash = "sha256:cd32fbacb9fd1bf041bf8e89e4576b6f00b895f06d00914820ae06a616bdfef7", size = 5328769, upload-time = "2026-03-09T07:58:13.67Z" },
    { url = "https://files.pythonhosted.org/packages/47/01/d2a137317c958b074d338807c1b6a383406cdf8b8e53b075d804cc3d211d/numpy-2.4.3-cp314-cp314t-macosx_14_0_x86_64.whl", hash = "sha256:2e03c05abaee1f672e9d67bc858f300b5ccba1c21397211e8d77d98350972093", size = 6649461, upload-time = "2026-03-09T07:58:15.912Z" },
    { url = "https://files.pythonhosted.org/packages/5c/34/812ce12bc0f00272a4b0ec0d713cd237cb390666eb6206323d1cc9cedbb2/numpy-2.4.3-cp314-cp314t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:7d1ce23cce91fcea443320a9d0ece9b9305d4368875bab09538f7a5b4131938a", size = 15725809, upload-time = "2026-03-09T07:58:17.787Z" },
    { url = "https://files.pythonhosted.org/packages/25/c0/2aed473a4823e905e765fee3dc2cbf504bd3e68ccb1150fbdabd5c39f527/numpy-2.4.3-cp314-cp314t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:c59020932feb24ed49ffd03704fbab89f22aa9c0d4b180ff45542fe8918f5611", size = 16655242, upload-time = "2026-03-09T07:58:20.476Z" },
    { url = "https://files.pythonhosted.org/packages/f2/c8/7e052b2fc87aa0e86de23f20e2c42bd261c624748aa8efd2c78f7bb8d8c6/numpy-2.4.3-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:9684823a78a6cd6ad7511fc5e25b07947d1d5b5e2812c93fe99d7d4195130720", size = 17080660, upload-time = "2026-03-09T07:58:23.067Z" },
    { url = "https://files.pythonhosted.org/packages/f3/3d/0876746044db2adcb11549f214d104f2e1be00f07a67edbb4e2812094847/numpy-2.4.3-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:0200b25c687033316fb39f0ff4e3e690e8957a2c3c8d22499891ec58c37a3eb5", size = 18380384, upload-time = "2026-03-09T07:58:25.839Z" },
    { url = "https://files.pythonhosted.org/packages/07/12/8160bea39da3335737b10308df4f484235fd297f556745f13092aa039d3b/numpy-2.4.3-cp314-cp314t-win32.whl", hash = "sha256:5e10da9e93247e554bb1d22f8edc51847ddd7dde52d85ce31024c1b4312bfba0", size = 6154547, upload-time = "2026-03-09T07:58:28.289Z" },
    { url = "https://files.pythonhosted.org/packages/42/f3/76534f61f80d74cc9cdf2e570d3d4eeb92c2280a27c39b0aaf471eda7b48/numpy-2.4.3-cp314-cp314t-win_amd64.whl", hash = "sha256:45f003dbdffb997a03da2d1d0cb41fbd24a87507fb41605c0420a3db5bd4667b", size = 12633645, upload-time = "2026-03-09T07:58:30.384Z" },
    { url = "https://files.pythonhosted.org/packages/1f/b6/7c0d4334c15983cec7f92a69e8ce9b1e6f31857e5ee3a413ac424e6bd63d/numpy-2.4.3-cp314-cp314t-win_arm64.whl", hash = "sha256:4d382735cecd7bcf090172489a525cd7d4087bc331f7df9f60ddc9a296cf208e", size = 10565454, upload-time = "2026-03-09T07:58:33.031Z" },
    { url = "https://files.pythonhosted.org/packages/64/e4/4dab9fb43c83719c29241c535d9e07be73bea4bc0c6686c5816d8e1b6689/numpy-2.4.3-pp311-pypy311_pp73-macosx_10_15_x86_64.whl", hash = "sha256:c6b124bfcafb9e8d3ed09130dbee44848c20b3e758b6bbf006e641778927c028", size = 16834892, upload-time = "2026-03-09T07:58:35.334Z" },
    { url = "https://files.pythonhosted.org/packages/c9/29/f8b6d4af90fed3dfda84ebc0df06c9833d38880c79ce954e5b661758aa31/numpy-2.4.3-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:76dbb9d4e43c16cf9aa711fcd8de1e2eeb27539dcefb60a1d5e9f12fae1d1ed8", size = 14893070, upload-time = "2026-03-09T07:58:37.7Z" },
    { url = "https://files.pythonhosted.org/packages/9a/04/a19b3c91dbec0a49269407f15d5753673a09832daed40c45e8150e6fa558/numpy-2.4.3-pp311-pypy311_pp73-macosx_14_0_arm64.whl", hash = "sha256:29363fbfa6f8ee855d7569c96ce524845e3d726d6c19b29eceec7dd555dab152", size = 5399609, upload-time = "2026-03-09T07:58:39.853Z" },
    { url = "https://files.pythonhosted.org/packages/79/34/4d73603f5420eab89ea8a67097b31364bf7c30f811d4dd84b1659c7476d9/numpy-2.4.3-pp311-pypy311_pp73-macosx_14_0_x86_64.whl", hash = "sha256:bc71942c789ef415a37f0d4eab90341425a00d538cd0642445d30b41023d3395", size = 6714355, upload-time = "2026-03-09T07:58:42.365Z" },
    { url = "https://files.pythonhosted.org/packages/58/ad/1100d7229bb248394939a12a8074d485b655e8ed44207d328fdd7fcebc7b/numpy-2.4.3-pp311-pypy311_pp73-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:7e58765ad74dcebd3ef0208a5078fba32dc8ec3578fe84a604432950cd043d79", size = 15800434, upload-time = "2026-03-09T07:58:44.837Z" },
    { url = "https://files.pythonhosted.org/packages/0c/fd/16d710c085d28ba4feaf29ac60c936c9d662e390344f94a6beaa2ac9899b/numpy-2.4.3-pp311-pypy311_pp73-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:8e236dbda4e1d319d681afcbb136c0c4a8e0f1a5c58ceec2adebb547357fe857", size = 16729409, upload-time = "2026-03-09T07:58:47.972Z" },
    { url = "https://files.pythonhosted.org/packages/57/a7/b35835e278c18b85206834b3aa3abe68e77a98769c59233d1f6300284781/numpy-2.4.3-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:4b42639cdde6d24e732ff823a3fa5b701d8acad89c4142bc1d0bd6dc85200ba5", size = 12504685, upload-time = "2026-03-09T07:58:50.525Z" },
]

[[package]]
name = "onnxruntime"
version = "1.24.3"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "flatbuffers" },
    { name = "numpy" },
    { name = "packaging" },
    { name = "protobuf" },
    { name = "sympy" },
]
wheels = [
    { url = "https://files.pythonhosted.org/packages/15/41/3253db975a90c3ce1d475e2a230773a21cd7998537f0657947df6fb79861/onnxruntime-1.24.3-cp311-cp311-macosx_14_0_arm64.whl", hash = "sha256:3e6456801c66b095c5cd68e690ca25db970ea5202bd0c5b84a2c3ef7731c5a3c", size = 17332766, upload-time = "2026-03-05T17:18:59.714Z" },
    { url = "https://files.pythonhosted.org/packages/7e/c5/3af6b325f1492d691b23844d88ed26844c1164620860c5efe95c0e22782d/onnxruntime-1.24.3-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:8b2ebc54c6d8281dccff78d4b06e47d4cf07535937584ab759448390a70f4978", size = 15130330, upload-time = "2026-03-05T16:34:53.831Z" },
    { url = "https://files.pythonhosted.org/packages/03/4b/f96b46c1866a293ed23ca2cf5e5a63d413ad3a951da60dd877e3c56cbbca/onnxruntime-1.24.3-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:fb56575d7794bf0781156955610c9e651c9504c64d42ec880784b6106244882d", size = 17213247, upload-time = "2026-03-05T17:17:59.812Z" },
    { url = "https://files.pythonhosted.org/packages/36/13/27cf4d8df2578747584e8758aeb0b673b60274048510257f1f084b15e80e/onnxruntime-1.24.3-cp311-cp311-win_amd64.whl", hash = "sha256:c958222ef9eff54018332beecd32d5d94a3ab079d8821937b333811bf4da0d39", size = 12595530, upload-time = "2026-03-05T17:18:49.356Z" },
    { url = "https://files.pythonhosted.org/packages/19/8c/6d9f31e6bae72a8079be12ed8ba36c4126a571fad38ded0a1b96f60f6896/onnxruntime-1.24.3-cp311-cp311-win_arm64.whl", hash = "sha256:a8f761857ebaf58a85b9e42422d03207f1d39e6bb8fecfdbf613bac5b9710723", size = 12261715, upload-time = "2026-03-05T17:18:39.699Z" },
    { url = "https://files.pythonhosted.org/packages/d0/7f/dfdc4e52600fde4c02d59bfe98c4b057931c1114b701e175aee311a9bc11/onnxruntime-1.24.3-cp312-cp312-macosx_14_0_arm64.whl", hash = "sha256:0d244227dc5e00a9ae15a7ac1eba4c4460d7876dfecafe73fb00db9f1d914d91", size = 17342578, upload-time = "2026-03-05T17:19:02.403Z" },
    { url = "https://files.pythonhosted.org/packages/1c/dc/1f5489f7b21817d4ad352bf7a92a252bd5b438bcbaa7ad20ea50814edc79/onnxruntime-1.24.3-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:0a9847b870b6cb462652b547bc98c49e0efb67553410a082fde1918a38707452", size = 15150105, upload-time = "2026-03-05T16:34:56.897Z" },
    { url = "https://files.pythonhosted.org/packages/28/7c/fd253da53594ab8efbefdc85b3638620ab1a6aab6eb7028a513c853559ce/onnxruntime-1.24.3-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:b354afce3333f2859c7e8706d84b6c552beac39233bcd3141ce7ab77b4cabb5d", size = 17237101, upload-time = "2026-03-05T17:18:02.561Z" },
    { url = "https://files.pythonhosted.org/packages/71/5f/eaabc5699eeed6a9188c5c055ac1948ae50138697a0428d562ac970d7db5/onnxruntime-1.24.3-cp312-cp312-win_amd64.whl", hash = "sha256:44ea708c34965439170d811267c51281d3897ecfc4aa0087fa25d4a4c3eb2e4a", size = 12597638, upload-time = "2026-03-05T17:18:52.141Z" },
    { url = "https://files.pythonhosted.org/packages/cc/5c/d8066c320b90610dbeb489a483b132c3b3879b2f93f949fb5d30cfa9b119/onnxruntime-1.24.3-cp312-cp312-win_arm64.whl", hash = "sha256:48d1092b44ca2ba6f9543892e7c422c15a568481403c10440945685faf27a8d8", size = 12270943, upload-time = "2026-03-05T17:18:42.006Z" },
    { url = "https://files.pythonhosted.org/packages/51/8d/487ece554119e2991242d4de55de7019ac6e47ee8dfafa69fcf41d37f8ed/onnxruntime-1.24.3-cp313-cp313-macosx_14_0_arm64.whl", hash = "sha256:34a0ea5ff191d8420d9c1332355644148b1bf1a0d10c411af890a63a9f662aa7", size = 17342706, upload-time = "2026-03-05T16:35:10.813Z" },
    { url = "https://files.pythonhosted.org/packages/dd/25/8b444f463c1ac6106b889f6235c84f01eec001eaf689c3eff8c69cf48fae/onnxruntime-1.24.3-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:1fd2ec7bb0fabe42f55e8337cfc9b1969d0d14622711aac73d69b4bd5abb5ed7", size = 15149956, upload-time = "2026-03-05T16:34:59.264Z" },
    { url = "https://files.pythonhosted.org/packages/34/fc/c9182a3e1ab46940dd4f30e61071f59eee8804c1f641f37ce6e173633fb6/onnxruntime-1.24.3-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:df8e70e732fe26346faaeec9147fa38bef35d232d2495d27e93dd221a2d473a9", size = 17237370, upload-time = "2026-03-05T17:18:05.258Z" },
    { url = "https://files.pythonhosted.org/packages/05/7e/3b549e1f4538514118bff98a1bcd6481dd9a17067f8c9af77151621c9a5c/onnxruntime-1.24.3-cp313-cp313-win_amd64.whl", hash = "sha256:2d3706719be6ad41d38a2250998b1d87758a20f6ea4546962e21dc79f1f1fd2b", size = 12597939, upload-time = "2026-03-05T17:18:54.772Z" },
    { url = "https://files.pythonhosted.org/packages/80/41/9696a5c4631a0caa75cc8bc4efd30938fd483694aa614898d087c3ee6d29/onnxruntime-1.24.3-cp313-cp313-win_arm64.whl", hash = "sha256:b082f3ba9519f0a1a1e754556bc7e635c7526ef81b98b3f78da4455d25f0437b", size = 12270705, upload-time = "2026-03-05T17:18:44.774Z" },
    { url = "https://files.pythonhosted.org/packages/b7/65/a26c5e59e3b210852ee04248cf8843c81fe7d40d94cf95343b66efe7eec9/onnxruntime-1.24.3-cp313-cp313t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:72f956634bc2e4bd2e8b006bef111849bd42c42dea37bd0a4c728404fdaf4d34", size = 15161796, upload-time = "2026-03-05T16:35:02.871Z" },
    { url = "https://files.pythonhosted.org/packages/f3/25/2035b4aa2ccb5be6acf139397731ec507c5f09e199ab39d3262b22ffa1ac/onnxruntime-1.24.3-cp313-cp313t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:78d1f25eed4ab9959db70a626ed50ee24cf497e60774f59f1207ac8556399c4d", size = 17240936, upload-time = "2026-03-05T17:18:09.534Z" },
    { url = "https://files.pythonhosted.org/packages/f9/a4/b3240ea84b92a3efb83d49cc16c04a17ade1ab47a6a95c4866d15bf0ac35/onnxruntime-1.24.3-cp314-cp314-macosx_14_0_arm64.whl", hash = "sha256:a6b4bce87d96f78f0a9bf5cefab3303ae95d558c5bfea53d0bf7f9ea207880a8", size = 17344149, upload-time = "2026-03-05T16:35:13.382Z" },
    { url = "https://files.pythonhosted.org/packages/bb/4a/4b56757e51a56265e8c56764d9c36d7b435045e05e3b8a38bedfc5aedba3/onnxruntime-1.24.3-cp314-cp314-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:d48f36c87b25ab3b2b4c88826c96cf1399a5631e3c2c03cc27d6a1e5d6b18eb4", size = 15151571, upload-time = "2026-03-05T16:35:05.679Z" },
    { url = "https://files.pythonhosted.org/packages/cf/14/c6fb84980cec8f682a523fcac7c2bdd6b311e7f342c61ce48d3a9cb87fc6/onnxruntime-1.24.3-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:e104d33a409bf6e3f30f0e8198ec2aaf8d445b8395490a80f6e6ad56da98e400", size = 17238951, upload-time = "2026-03-05T17:18:12.394Z" },
    { url = "https://files.pythonhosted.org/packages/57/14/447e1400165aca8caf35dabd46540eb943c92f3065927bb4d9bcbc91e221/onnxruntime-1.24.3-cp314-cp314-win_amd64.whl", hash = "sha256:e785d73fbd17421c2513b0bb09eb25d88fa22c8c10c3f5d6060589efa5537c5b", size = 12903820, upload-time = "2026-03-05T17:18:57.123Z" },
    { url = "https://files.pythonhosted.org/packages/1d/ec/6b2fa5702e4bbba7339ca5787a9d056fc564a16079f8833cc6ba4798da1c/onnxruntime-1.24.3-cp314-cp314-win_arm64.whl", hash = "sha256:951e897a275f897a05ffbcaa615d98777882decaeb80c9216c68cdc62f849f53", size = 12594089, upload-time = "2026-03-05T17:18:47.169Z" },
    { url = "https://files.pythonhosted.org/packages/12/dc/cd06cba3ddad92ceb17b914a8e8d49836c79e38936e26bde6e368b62c1fe/onnxruntime-1.24.3-cp314-cp314t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:4d4e70ce578aa214c74c7a7a9226bc8e229814db4a5b2d097333b81279ecde36", size = 15162789, upload-time = "2026-03-05T16:35:08.282Z" },
    { url = "https://files.pythonhosted.org/packages/a6/d6/413e98ab666c6fb9e8be7d1c6eb3bd403b0bea1b8d42db066dab98c7df07/onnxruntime-1.24.3-cp314-cp314t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:02aaf6ddfa784523b6873b4176a79d508e599efe12ab0ea1a3a6e7314408b7aa", size = 17240738, upload-time = "2026-03-05T17:18:15.203Z" },
]

[[package]]
name = "packaging"
version = "26.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/65/ee/299d360cdc32edc7d2cf530f3accf79c4fca01e96ffc950d8a52213bd8e4/packaging-26.0.tar.gz", hash = "sha256:00243ae351a257117b6a241061796684b084ed1c516a08c48a3f7e147a9d80b4", size = 143416, upload-time = "2026-01-21T20:50:39.064Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/b7/b9/c538f279a4e237a006a2c98387d081e9eb060d203d8ed34467cc0f0b9b53/packaging-26.0-py3-none-any.whl", hash = "sha256:b36f1fef9334a5588b4166f8bcd26a14e521f2b55e6b9de3aaa80d3ff7a37529", size = 74366, upload-time = "2026-01-21T20:50:37.788Z" },
]

[[package]]
name = "pillow"
version = "11.3.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/f3/0d/d0d6dea55cd152ce3d6767bb38a8fc10e33796ba4ba210cbab9354b6d238/pillow-11.3.0.tar.gz", hash = "sha256:3828ee7586cd0b2091b6209e5ad53e20d0649bbe87164a459d0676e035e8f523", size = 47113069, upload-time = "2025-07-01T09:16:30.666Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/db/26/77f8ed17ca4ffd60e1dcd220a6ec6d71210ba398cfa33a13a1cd614c5613/pillow-11.3.0-cp311-cp311-macosx_10_10_x86_64.whl", hash = "sha256:1cd110edf822773368b396281a2293aeb91c90a2db00d78ea43e7e861631b722", size = 5316531, upload-time = "2025-07-01T09:13:59.203Z" },
    { url = "https://files.pythonhosted.org/packages/cb/39/ee475903197ce709322a17a866892efb560f57900d9af2e55f86db51b0a5/pillow-11.3.0-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:9c412fddd1b77a75aa904615ebaa6001f169b26fd467b4be93aded278266b288", size = 4686560, upload-time = "2025-07-01T09:14:01.101Z" },
    { url = "https://files.pythonhosted.org/packages/d5/90/442068a160fd179938ba55ec8c97050a612426fae5ec0a764e345839f76d/pillow-11.3.0-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:7d1aa4de119a0ecac0a34a9c8bde33f34022e2e8f99104e47a3ca392fd60e37d", size = 5870978, upload-time = "2025-07-03T13:09:55.638Z" },
    { url = "https://files.pythonhosted.org/packages/13/92/dcdd147ab02daf405387f0218dcf792dc6dd5b14d2573d40b4caeef01059/pillow-11.3.0-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:91da1d88226663594e3f6b4b8c3c8d85bd504117d043740a8e0ec449087cc494", size = 7641168, upload-time = "2025-07-03T13:10:00.37Z" },
    { url = "https://files.pythonhosted.org/packages/6e/db/839d6ba7fd38b51af641aa904e2960e7a5644d60ec754c046b7d2aee00e5/pillow-11.3.0-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:643f189248837533073c405ec2f0bb250ba54598cf80e8c1e043381a60632f58", size = 5973053, upload-time = "2025-07-01T09:14:04.491Z" },
    { url = "https://files.pythonhosted.org/packages/f2/2f/d7675ecae6c43e9f12aa8d58b6012683b20b6edfbdac7abcb4e6af7a3784/pillow-11.3.0-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:106064daa23a745510dabce1d84f29137a37224831d88eb4ce94bb187b1d7e5f", size = 6640273, upload-time = "2025-07-01T09:14:06.235Z" },
    { url = "https://files.pythonhosted.org/packages/45/ad/931694675ede172e15b2ff03c8144a0ddaea1d87adb72bb07655eaffb654/pillow-11.3.0-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:cd8ff254faf15591e724dc7c4ddb6bf4793efcbe13802a4ae3e863cd300b493e", size = 6082043, upload-time = "2025-07-01T09:14:07.978Z" },
    { url = "https://files.pythonhosted.org/packages/3a/04/ba8f2b11fc80d2dd462d7abec16351b45ec99cbbaea4387648a44190351a/pillow-11.3.0-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:932c754c2d51ad2b2271fd01c3d121daaa35e27efae2a616f77bf164bc0b3e94", size = 6715516, upload-time = "2025-07-01T09:14:10.233Z" },
    { url = "https://files.pythonhosted.org/packages/48/59/8cd06d7f3944cc7d892e8533c56b0acb68399f640786313275faec1e3b6f/pillow-11.3.0-cp311-cp311-win32.whl", hash = "sha256:b4b8f3efc8d530a1544e5962bd6b403d5f7fe8b9e08227c6b255f98ad82b4ba0", size = 6274768, upload-time = "2025-07-01T09:14:11.921Z" },
    { url = "https://files.pythonhosted.org/packages/f1/cc/29c0f5d64ab8eae20f3232da8f8571660aa0ab4b8f1331da5c2f5f9a938e/pillow-11.3.0-cp311-cp311-win_amd64.whl", hash = "sha256:1a992e86b0dd7aeb1f053cd506508c0999d710a8f07b4c791c63843fc6a807ac", size = 6986055, upload-time = "2025-07-01T09:14:13.623Z" },
    { url = "https://files.pythonhosted.org/packages/c6/df/90bd886fabd544c25addd63e5ca6932c86f2b701d5da6c7839387a076b4a/pillow-11.3.0-cp311-cp311-win_arm64.whl", hash = "sha256:30807c931ff7c095620fe04448e2c2fc673fcbb1ffe2a7da3fb39613489b1ddd", size = 2423079, upload-time = "2025-07-01T09:14:15.268Z" },
    { url = "https://files.pythonhosted.org/packages/40/fe/1bc9b3ee13f68487a99ac9529968035cca2f0a51ec36892060edcc51d06a/pillow-11.3.0-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:fdae223722da47b024b867c1ea0be64e0df702c5e0a60e27daad39bf960dd1e4", size = 5278800, upload-time = "2025-07-01T09:14:17.648Z" },
    { url = "https://files.pythonhosted.org/packages/2c/32/7e2ac19b5713657384cec55f89065fb306b06af008cfd87e572035b27119/pillow-11.3.0-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:921bd305b10e82b4d1f5e802b6850677f965d8394203d182f078873851dada69", size = 4686296, upload-time = "2025-07-01T09:14:19.828Z" },
    { url = "https://files.pythonhosted.org/packages/8e/1e/b9e12bbe6e4c2220effebc09ea0923a07a6da1e1f1bfbc8d7d29a01ce32b/pillow-11.3.0-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:eb76541cba2f958032d79d143b98a3a6b3ea87f0959bbe256c0b5e416599fd5d", size = 5871726, upload-time = "2025-07-03T13:10:04.448Z" },
    { url = "https://files.pythonhosted.org/packages/8d/33/e9200d2bd7ba00dc3ddb78df1198a6e80d7669cce6c2bdbeb2530a74ec58/pillow-11.3.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:67172f2944ebba3d4a7b54f2e95c786a3a50c21b88456329314caaa28cda70f6", size = 7644652, upload-time = "2025-07-03T13:10:10.391Z" },
    { url = "https://files.pythonhosted.org/packages/41/f1/6f2427a26fc683e00d985bc391bdd76d8dd4e92fac33d841127eb8fb2313/pillow-11.3.0-cp312-cp312-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:97f07ed9f56a3b9b5f49d3661dc9607484e85c67e27f3e8be2c7d28ca032fec7", size = 5977787, upload-time = "2025-07-01T09:14:21.63Z" },
    { url = "https://files.pythonhosted.org/packages/e4/c9/06dd4a38974e24f932ff5f98ea3c546ce3f8c995d3f0985f8e5ba48bba19/pillow-11.3.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:676b2815362456b5b3216b4fd5bd89d362100dc6f4945154ff172e206a22c024", size = 6645236, upload-time = "2025-07-01T09:14:23.321Z" },
    { url = "https://files.pythonhosted.org/packages/40/e7/848f69fb79843b3d91241bad658e9c14f39a32f71a301bcd1d139416d1be/pillow-11.3.0-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:3e184b2f26ff146363dd07bde8b711833d7b0202e27d13540bfe2e35a323a809", size = 6086950, upload-time = "2025-07-01T09:14:25.237Z" },
    { url = "https://files.pythonhosted.org/packages/0b/1a/7cff92e695a2a29ac1958c2a0fe4c0b2393b60aac13b04a4fe2735cad52d/pillow-11.3.0-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:6be31e3fc9a621e071bc17bb7de63b85cbe0bfae91bb0363c893cbe67247780d", size = 6723358, upload-time = "2025-07-01T09:14:27.053Z" },
    { url = "https://files.pythonhosted.org/packages/26/7d/73699ad77895f69edff76b0f332acc3d497f22f5d75e5360f78cbcaff248/pillow-11.3.0-cp312-cp312-win32.whl", hash = "sha256:7b161756381f0918e05e7cb8a371fff367e807770f8fe92ecb20d905d0e1c149", size = 6275079, upload-time = "2025-07-01T09:14:30.104Z" },
    { url = "https://files.pythonhosted.org/packages/8c/ce/e7dfc873bdd9828f3b6e5c2bbb74e47a98ec23cc5c74fc4e54462f0d9204/pillow-11.3.0-cp312-cp312-win_amd64.whl", hash = "sha256:a6444696fce635783440b7f7a9fc24b3ad10a9ea3f0ab66c5905be1c19ccf17d", size = 6986324, upload-time = "2025-07-01T09:14:31.899Z" },
    { url = "https://files.pythonhosted.org/packages/16/8f/b13447d1bf0b1f7467ce7d86f6e6edf66c0ad7cf44cf5c87a37f9bed9936/pillow-11.3.0-cp312-cp312-win_arm64.whl", hash = "sha256:2aceea54f957dd4448264f9bf40875da0415c83eb85f55069d89c0ed436e3542", size = 2423067, upload-time = "2025-07-01T09:14:33.709Z" },
    { url = "https://files.pythonhosted.org/packages/1e/93/0952f2ed8db3a5a4c7a11f91965d6184ebc8cd7cbb7941a260d5f018cd2d/pillow-11.3.0-cp313-cp313-ios_13_0_arm64_iphoneos.whl", hash = "sha256:1c627742b539bba4309df89171356fcb3cc5a9178355b2727d1b74a6cf155fbd", size = 2128328, upload-time = "2025-07-01T09:14:35.276Z" },
    { url = "https://files.pythonhosted.org/packages/4b/e8/100c3d114b1a0bf4042f27e0f87d2f25e857e838034e98ca98fe7b8c0a9c/pillow-11.3.0-cp313-cp313-ios_13_0_arm64_iphonesimulator.whl", hash = "sha256:30b7c02f3899d10f13d7a48163c8969e4e653f8b43416d23d13d1bbfdc93b9f8", size = 2170652, upload-time = "2025-07-01T09:14:37.203Z" },
    { url = "https://files.pythonhosted.org/packages/aa/86/3f758a28a6e381758545f7cdb4942e1cb79abd271bea932998fc0db93cb6/pillow-11.3.0-cp313-cp313-ios_13_0_x86_64_iphonesimulator.whl", hash = "sha256:7859a4cc7c9295f5838015d8cc0a9c215b77e43d07a25e460f35cf516df8626f", size = 2227443, upload-time = "2025-07-01T09:14:39.344Z" },
    { url = "https://files.pythonhosted.org/packages/01/f4/91d5b3ffa718df2f53b0dc109877993e511f4fd055d7e9508682e8aba092/pillow-11.3.0-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:ec1ee50470b0d050984394423d96325b744d55c701a439d2bd66089bff963d3c", size = 5278474, upload-time = "2025-07-01T09:14:41.843Z" },
    { url = "https://files.pythonhosted.org/packages/f9/0e/37d7d3eca6c879fbd9dba21268427dffda1ab00d4eb05b32923d4fbe3b12/pillow-11.3.0-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:7db51d222548ccfd274e4572fdbf3e810a5e66b00608862f947b163e613b67dd", size = 4686038, upload-time = "2025-07-01T09:14:44.008Z" },
    { url = "https://files.pythonhosted.org/packages/ff/b0/3426e5c7f6565e752d81221af9d3676fdbb4f352317ceafd42899aaf5d8a/pillow-11.3.0-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:2d6fcc902a24ac74495df63faad1884282239265c6839a0a6416d33faedfae7e", size = 5864407, upload-time = "2025-07-03T13:10:15.628Z" },
    { url = "https://files.pythonhosted.org/packages/fc/c1/c6c423134229f2a221ee53f838d4be9d82bab86f7e2f8e75e47b6bf6cd77/pillow-11.3.0-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:f0f5d8f4a08090c6d6d578351a2b91acf519a54986c055af27e7a93feae6d3f1", size = 7639094, upload-time = "2025-07-03T13:10:21.857Z" },
    { url = "https://files.pythonhosted.org/packages/ba/c9/09e6746630fe6372c67c648ff9deae52a2bc20897d51fa293571977ceb5d/pillow-11.3.0-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:c37d8ba9411d6003bba9e518db0db0c58a680ab9fe5179f040b0463644bc9805", size = 5973503, upload-time = "2025-07-01T09:14:45.698Z" },
    { url = "https://files.pythonhosted.org/packages/d5/1c/a2a29649c0b1983d3ef57ee87a66487fdeb45132df66ab30dd37f7dbe162/pillow-11.3.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:13f87d581e71d9189ab21fe0efb5a23e9f28552d5be6979e84001d3b8505abe8", size = 6642574, upload-time = "2025-07-01T09:14:47.415Z" },
    { url = "https://files.pythonhosted.org/packages/36/de/d5cc31cc4b055b6c6fd990e3e7f0f8aaf36229a2698501bcb0cdf67c7146/pillow-11.3.0-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:023f6d2d11784a465f09fd09a34b150ea4672e85fb3d05931d89f373ab14abb2", size = 6084060, upload-time = "2025-07-01T09:14:49.636Z" },
    { url = "https://files.pythonhosted.org/packages/d5/ea/502d938cbaeec836ac28a9b730193716f0114c41325db428e6b280513f09/pillow-11.3.0-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:45dfc51ac5975b938e9809451c51734124e73b04d0f0ac621649821a63852e7b", size = 6721407, upload-time = "2025-07-01T09:14:51.962Z" },
    { url = "https://files.pythonhosted.org/packages/45/9c/9c5e2a73f125f6cbc59cc7087c8f2d649a7ae453f83bd0362ff7c9e2aee2/pillow-11.3.0-cp313-cp313-win32.whl", hash = "sha256:a4d336baed65d50d37b88ca5b60c0fa9d81e3a87d4a7930d3880d1624d5b31f3", size = 6273841, upload-time = "2025-07-01T09:14:54.142Z" },
    { url = "https://files.pythonhosted.org/packages/23/85/397c73524e0cd212067e0c969aa245b01d50183439550d24d9f55781b776/pillow-11.3.0-cp313-cp313-win_amd64.whl", hash = "sha256:0bce5c4fd0921f99d2e858dc4d4d64193407e1b99478bc5cacecba2311abde51", size = 6978450, upload-time = "2025-07-01T09:14:56.436Z" },
    { url = "https://files.pythonhosted.org/packages/17/d2/622f4547f69cd173955194b78e4d19ca4935a1b0f03a302d655c9f6aae65/pillow-11.3.0-cp313-cp313-win_arm64.whl", hash = "sha256:1904e1264881f682f02b7f8167935cce37bc97db457f8e7849dc3a6a52b99580", size = 2423055, upload-time = "2025-07-01T09:14:58.072Z" },
    { url = "https://files.pythonhosted.org/packages/dd/80/a8a2ac21dda2e82480852978416cfacd439a4b490a501a288ecf4fe2532d/pillow-11.3.0-cp313-cp313t-macosx_10_13_x86_64.whl", hash = "sha256:4c834a3921375c48ee6b9624061076bc0a32a60b5532b322cc0ea64e639dd50e", size = 5281110, upload-time = "2025-07-01T09:14:59.79Z" },
    { url = "https://files.pythonhosted.org/packages/44/d6/b79754ca790f315918732e18f82a8146d33bcd7f4494380457ea89eb883d/pillow-11.3.0-cp313-cp313t-macosx_11_0_arm64.whl", hash = "sha256:5e05688ccef30ea69b9317a9ead994b93975104a677a36a8ed8106be9260aa6d", size = 4689547, upload-time = "2025-07-01T09:15:01.648Z" },
    { url = "https://files.pythonhosted.org/packages/49/20/716b8717d331150cb00f7fdd78169c01e8e0c219732a78b0e59b6bdb2fd6/pillow-11.3.0-cp313-cp313t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:1019b04af07fc0163e2810167918cb5add8d74674b6267616021ab558dc98ced", size = 5901554, upload-time = "2025-07-03T13:10:27.018Z" },
    { url = "https://files.pythonhosted.org/packages/74/cf/a9f3a2514a65bb071075063a96f0a5cf949c2f2fce683c15ccc83b1c1cab/pillow-11.3.0-cp313-cp313t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:f944255db153ebb2b19c51fe85dd99ef0ce494123f21b9db4877ffdfc5590c7c", size = 7669132, upload-time = "2025-07-03T13:10:33.01Z" },
    { url = "https://files.pythonhosted.org/packages/98/3c/da78805cbdbee9cb43efe8261dd7cc0b4b93f2ac79b676c03159e9db2187/pillow-11.3.0-cp313-cp313t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:1f85acb69adf2aaee8b7da124efebbdb959a104db34d3a2cb0f3793dbae422a8", size = 6005001, upload-time = "2025-07-01T09:15:03.365Z" },
    { url = "https://files.pythonhosted.org/packages/6c/fa/ce044b91faecf30e635321351bba32bab5a7e034c60187fe9698191aef4f/pillow-11.3.0-cp313-cp313t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:05f6ecbeff5005399bb48d198f098a9b4b6bdf27b8487c7f38ca16eeb070cd59", size = 6668814, upload-time = "2025-07-01T09:15:05.655Z" },
    { url = "https://files.pythonhosted.org/packages/7b/51/90f9291406d09bf93686434f9183aba27b831c10c87746ff49f127ee80cb/pillow-11.3.0-cp313-cp313t-musllinux_1_2_aarch64.whl", hash = "sha256:a7bc6e6fd0395bc052f16b1a8670859964dbd7003bd0af2ff08342eb6e442cfe", size = 6113124, upload-time = "2025-07-01T09:15:07.358Z" },
    { url = "https://files.pythonhosted.org/packages/cd/5a/6fec59b1dfb619234f7636d4157d11fb4e196caeee220232a8d2ec48488d/pillow-11.3.0-cp313-cp313t-musllinux_1_2_x86_64.whl", hash = "sha256:83e1b0161c9d148125083a35c1c5a89db5b7054834fd4387499e06552035236c", size = 6747186, upload-time = "2025-07-01T09:15:09.317Z" },
    { url = "https://files.pythonhosted.org/packages/49/6b/00187a044f98255225f172de653941e61da37104a9ea60e4f6887717e2b5/pillow-11.3.0-cp313-cp313t-win32.whl", hash = "sha256:2a3117c06b8fb646639dce83694f2f9eac405472713fcb1ae887469c0d4f6788", size = 6277546, upload-time = "2025-07-01T09:15:11.311Z" },
    { url = "https://files.pythonhosted.org/packages/e8/5c/6caaba7e261c0d75bab23be79f1d06b5ad2a2ae49f028ccec801b0e853d6/pillow-11.3.0-cp313-cp313t-win_amd64.whl", hash = "sha256:857844335c95bea93fb39e0fa2726b4d9d758850b34075a7e3ff4f4fa3aa3b31", size = 6985102, upload-time = "2025-07-01T09:15:13.164Z" },
    { url = "https://files.pythonhosted.org/packages/f3/7e/b623008460c09a0cb38263c93b828c666493caee2eb34ff67f778b87e58c/pillow-11.3.0-cp313-cp313t-win_arm64.whl", hash = "sha256:8797edc41f3e8536ae4b10897ee2f637235c94f27404cac7297f7b607dd0716e", size = 2424803, upload-time = "2025-07-01T09:15:15.695Z" },
    { url = "https://files.pythonhosted.org/packages/73/f4/04905af42837292ed86cb1b1dabe03dce1edc008ef14c473c5c7e1443c5d/pillow-11.3.0-cp314-cp314-macosx_10_13_x86_64.whl", hash = "sha256:d9da3df5f9ea2a89b81bb6087177fb1f4d1c7146d583a3fe5c672c0d94e55e12", size = 5278520, upload-time = "2025-07-01T09:15:17.429Z" },
    { url = "https://files.pythonhosted.org/packages/41/b0/33d79e377a336247df6348a54e6d2a2b85d644ca202555e3faa0cf811ecc/pillow-11.3.0-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:0b275ff9b04df7b640c59ec5a3cb113eefd3795a8df80bac69646ef699c6981a", size = 4686116, upload-time = "2025-07-01T09:15:19.423Z" },
    { url = "https://files.pythonhosted.org/packages/49/2d/ed8bc0ab219ae8768f529597d9509d184fe8a6c4741a6864fea334d25f3f/pillow-11.3.0-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:0743841cabd3dba6a83f38a92672cccbd69af56e3e91777b0ee7f4dba4385632", size = 5864597, upload-time = "2025-07-03T13:10:38.404Z" },
    { url = "https://files.pythonhosted.org/packages/b5/3d/b932bb4225c80b58dfadaca9d42d08d0b7064d2d1791b6a237f87f661834/pillow-11.3.0-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:2465a69cf967b8b49ee1b96d76718cd98c4e925414ead59fdf75cf0fd07df673", size = 7638246, upload-time = "2025-07-03T13:10:44.987Z" },
    { url = "https://files.pythonhosted.org/packages/09/b5/0487044b7c096f1b48f0d7ad416472c02e0e4bf6919541b111efd3cae690/pillow-11.3.0-cp314-cp314-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:41742638139424703b4d01665b807c6468e23e699e8e90cffefe291c5832b027", size = 5973336, upload-time = "2025-07-01T09:15:21.237Z" },
    { url = "https://files.pythonhosted.org/packages/a8/2d/524f9318f6cbfcc79fbc004801ea6b607ec3f843977652fdee4857a7568b/pillow-11.3.0-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:93efb0b4de7e340d99057415c749175e24c8864302369e05914682ba642e5d77", size = 6642699, upload-time = "2025-07-01T09:15:23.186Z" },
    { url = "https://files.pythonhosted.org/packages/6f/d2/a9a4f280c6aefedce1e8f615baaa5474e0701d86dd6f1dede66726462bbd/pillow-11.3.0-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:7966e38dcd0fa11ca390aed7c6f20454443581d758242023cf36fcb319b1a874", size = 6083789, upload-time = "2025-07-01T09:15:25.1Z" },
    { url = "https://files.pythonhosted.org/packages/fe/54/86b0cd9dbb683a9d5e960b66c7379e821a19be4ac5810e2e5a715c09a0c0/pillow-11.3.0-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:98a9afa7b9007c67ed84c57c9e0ad86a6000da96eaa638e4f8abe5b65ff83f0a", size = 6720386, upload-time = "2025-07-01T09:15:27.378Z" },
    { url = "https://files.pythonhosted.org/packages/e7/95/88efcaf384c3588e24259c4203b909cbe3e3c2d887af9e938c2022c9dd48/pillow-11.3.0-cp314-cp314-win32.whl", hash = "sha256:02a723e6bf909e7cea0dac1b0e0310be9d7650cd66222a5f1c571455c0a45214", size = 6370911, upload-time = "2025-07-01T09:15:29.294Z" },
    { url = "https://files.pythonhosted.org/packages/2e/cc/934e5820850ec5eb107e7b1a72dd278140731c669f396110ebc326f2a503/pillow-11.3.0-cp314-cp314-win_amd64.whl", hash = "sha256:a418486160228f64dd9e9efcd132679b7a02a5f22c982c78b6fc7dab3fefb635", size = 7117383, upload-time = "2025-07-01T09:15:31.128Z" },
    { url = "https://files.pythonhosted.org/packages/d6/e9/9c0a616a71da2a5d163aa37405e8aced9a906d574b4a214bede134e731bc/pillow-11.3.0-cp314-cp314-win_arm64.whl", hash = "sha256:155658efb5e044669c08896c0c44231c5e9abcaadbc5cd3648df2f7c0b96b9a6", size = 2511385, upload-time = "2025-07-01T09:15:33.328Z" },
    { url = "https://files.pythonhosted.org/packages/1a/33/c88376898aff369658b225262cd4f2659b13e8178e7534df9e6e1fa289f6/pillow-11.3.0-cp314-cp314t-macosx_10_13_x86_64.whl", hash = "sha256:59a03cdf019efbfeeed910bf79c7c93255c3d54bc45898ac2a4140071b02b4ae", size = 5281129, upload-time = "2025-07-01T09:15:35.194Z" },
    { url = "https://files.pythonhosted.org/packages/1f/70/d376247fb36f1844b42910911c83a02d5544ebd2a8bad9efcc0f707ea774/pillow-11.3.0-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:f8a5827f84d973d8636e9dc5764af4f0cf2318d26744b3d902931701b0d46653", size = 4689580, upload-time = "2025-07-01T09:15:37.114Z" },
    { url = "https://files.pythonhosted.org/packages/eb/1c/537e930496149fbac69efd2fc4329035bbe2e5475b4165439e3be9cb183b/pillow-11.3.0-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:ee92f2fd10f4adc4b43d07ec5e779932b4eb3dbfbc34790ada5a6669bc095aa6", size = 5902860, upload-time = "2025-07-03T13:10:50.248Z" },
    { url = "https://files.pythonhosted.org/packages/bd/57/80f53264954dcefeebcf9dae6e3eb1daea1b488f0be8b8fef12f79a3eb10/pillow-11.3.0-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:c96d333dcf42d01f47b37e0979b6bd73ec91eae18614864622d9b87bbd5bbf36", size = 7670694, upload-time = "2025-07-03T13:10:56.432Z" },
    { url = "https://files.pythonhosted.org/packages/70/ff/4727d3b71a8578b4587d9c276e90efad2d6fe0335fd76742a6da08132e8c/pillow-11.3.0-cp314-cp314t-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:4c96f993ab8c98460cd0c001447bff6194403e8b1d7e149ade5f00594918128b", size = 6005888, upload-time = "2025-07-01T09:15:39.436Z" },
    { url = "https://files.pythonhosted.org/packages/05/ae/716592277934f85d3be51d7256f3636672d7b1abfafdc42cf3f8cbd4b4c8/pillow-11.3.0-cp314-cp314t-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:41342b64afeba938edb034d122b2dda5db2139b9a4af999729ba8818e0056477", size = 6670330, upload-time = "2025-07-01T09:15:41.269Z" },
    { url = "https://files.pythonhosted.org/packages/e7/bb/7fe6cddcc8827b01b1a9766f5fdeb7418680744f9082035bdbabecf1d57f/pillow-11.3.0-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:068d9c39a2d1b358eb9f245ce7ab1b5c3246c7c8c7d9ba58cfa5b43146c06e50", size = 6114089, upload-time = "2025-07-01T09:15:43.13Z" },
    { url = "https://files.pythonhosted.org/packages/8b/f5/06bfaa444c8e80f1a8e4bff98da9c83b37b5be3b1deaa43d27a0db37ef84/pillow-11.3.0-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:a1bc6ba083b145187f648b667e05a2534ecc4b9f2784c2cbe3089e44868f2b9b", size = 6748206, upload-time = "2025-07-01T09:15:44.937Z" },
    { url = "https://files.pythonhosted.org/packages/f0/77/bc6f92a3e8e6e46c0ca78abfffec0037845800ea38c73483760362804c41/pillow-11.3.0-cp314-cp314t-win32.whl", hash = "sha256:118ca10c0d60b06d006be10a501fd6bbdfef559251ed31b794668ed569c87e12", size = 6377370, upload-time = "2025-07-01T09:15:46.673Z" },
    { url = "https://files.pythonhosted.org/packages/4a/82/3a721f7d69dca802befb8af08b7c79ebcab461007ce1c18bd91a5d5896f9/pillow-11.3.0-cp314-cp314t-win_amd64.whl", hash = "sha256:8924748b688aa210d79883357d102cd64690e56b923a186f35a82cbc10f997db", size = 7121500, upload-time = "2025-07-01T09:15:48.512Z" },
    { url = "https://files.pythonhosted.org/packages/89/c7/5572fa4a3f45740eaab6ae86fcdf7195b55beac1371ac8c619d880cfe948/pillow-11.3.0-cp314-cp314t-win_arm64.whl", hash = "sha256:79ea0d14d3ebad43ec77ad5272e6ff9bba5b679ef73375ea760261207fa8e0aa", size = 2512835, upload-time = "2025-07-01T09:15:50.399Z" },
    { url = "https://files.pythonhosted.org/packages/9e/e3/6fa84033758276fb31da12e5fb66ad747ae83b93c67af17f8c6ff4cc8f34/pillow-11.3.0-pp311-pypy311_pp73-macosx_10_15_x86_64.whl", hash = "sha256:7c8ec7a017ad1bd562f93dbd8505763e688d388cde6e4a010ae1486916e713e6", size = 5270566, upload-time = "2025-07-01T09:16:19.801Z" },
    { url = "https://files.pythonhosted.org/packages/5b/ee/e8d2e1ab4892970b561e1ba96cbd59c0d28cf66737fc44abb2aec3795a4e/pillow-11.3.0-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:9ab6ae226de48019caa8074894544af5b53a117ccb9d3b3dcb2871464c829438", size = 4654618, upload-time = "2025-07-01T09:16:21.818Z" },
    { url = "https://files.pythonhosted.org/packages/f2/6d/17f80f4e1f0761f02160fc433abd4109fa1548dcfdca46cfdadaf9efa565/pillow-11.3.0-pp311-pypy311_pp73-manylinux2014_aarch64.manylinux_2_17_aarch64.whl", hash = "sha256:fe27fb049cdcca11f11a7bfda64043c37b30e6b91f10cb5bab275806c32f6ab3", size = 4874248, upload-time = "2025-07-03T13:11:20.738Z" },
    { url = "https://files.pythonhosted.org/packages/de/5f/c22340acd61cef960130585bbe2120e2fd8434c214802f07e8c03596b17e/pillow-11.3.0-pp311-pypy311_pp73-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", hash = "sha256:465b9e8844e3c3519a983d58b80be3f668e2a7a5db97f2784e7079fbc9f9822c", size = 6583963, upload-time = "2025-07-03T13:11:26.283Z" },
    { url = "https://files.pythonhosted.org/packages/31/5e/03966aedfbfcbb4d5f8aa042452d3361f325b963ebbadddac05b122e47dd/pillow-11.3.0-pp311-pypy311_pp73-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:5418b53c0d59b3824d05e029669efa023bbef0f3e92e75ec8428f3799487f361", size = 4957170, upload-time = "2025-07-01T09:16:23.762Z" },
    { url = "https://files.pythonhosted.org/packages/cc/2d/e082982aacc927fc2cab48e1e731bdb1643a1406acace8bed0900a61464e/pillow-11.3.0-pp311-pypy311_pp73-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:504b6f59505f08ae014f724b6207ff6222662aab5cc9542577fb084ed0676ac7", size = 5581505, upload-time = "2025-07-01T09:16:25.593Z" },
    { url = "https://files.pythonhosted.org/packages/34/e7/ae39f538fd6844e982063c3a5e4598b8ced43b9633baa3a85ef33af8c05c/pillow-11.3.0-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:c84d689db21a1c397d001aa08241044aa2069e7587b398c8cc63020390b1c1b8", size = 6984598, upload-time = "2025-07-01T09:16:27.732Z" },
]

[[package]]
name = "pluggy"
version = "1.6.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/f9/e2/3e91f31a7d2b083fe6ef3fa267035b518369d9511ffab804f839851d2779/pluggy-1.6.0.tar.gz", hash = "sha256:7dcc130b76258d33b90f61b658791dede3486c3e6bfb003ee5c9bfb396dd22f3", size = 69412, upload-time = "2025-05-15T12:30:07.975Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/54/20/4d324d65cc6d9205fabedc306948156824eb9f0ee1633355a8f7ec5c66bf/pluggy-1.6.0-py3-none-any.whl", hash = "sha256:e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746", size = 20538, upload-time = "2025-05-15T12:30:06.134Z" },
]

[[package]]
name = "portalocker"
version = "3.2.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "pywin32", marker = "sys_platform == 'win32'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/5e/77/65b857a69ed876e1951e88aaba60f5ce6120c33703f7cb61a3c894b8c1b6/portalocker-3.2.0.tar.gz", hash = "sha256:1f3002956a54a8c3730586c5c77bf18fae4149e07eaf1c29fc3faf4d5a3f89ac", size = 95644, upload-time = "2025-06-14T13:20:40.03Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/4b/a6/38c8e2f318bf67d338f4d629e93b0b4b9af331f455f0390ea8ce4a099b26/portalocker-3.2.0-py3-none-any.whl", hash = "sha256:3cdc5f565312224bc570c49337bd21428bba0ef363bbcf58b9ef4a9f11779968", size = 22424, upload-time = "2025-06-14T13:20:38.083Z" },
]

[[package]]
name = "protobuf"
version = "7.34.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/f2/00/04a2ab36b70a52d0356852979e08b44edde0435f2115dc66e25f2100f3ab/protobuf-7.34.0.tar.gz", hash = "sha256:3871a3df67c710aaf7bb8d214cc997342e63ceebd940c8c7fc65c9b3d697591a", size = 454726, upload-time = "2026-02-27T00:30:25.421Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/13/c4/6322ab5c8f279c4c358bc14eb8aefc0550b97222a39f04eb3c1af7a830fa/protobuf-7.34.0-cp310-abi3-macosx_10_9_universal2.whl", hash = "sha256:8e329966799f2c271d5e05e236459fe1cbfdb8755aaa3b0914fa60947ddea408", size = 429248, upload-time = "2026-02-27T00:30:14.924Z" },
    { url = "https://files.pythonhosted.org/packages/45/99/b029bbbc61e8937545da5b79aa405ab2d9cf307a728f8c9459ad60d7a481/protobuf-7.34.0-cp310-abi3-manylinux2014_aarch64.whl", hash = "sha256:9d7a5005fb96f3c1e64f397f91500b0eb371b28da81296ae73a6b08a5b76cdd6", size = 325753, upload-time = "2026-02-27T00:30:17.247Z" },
    { url = "https://files.pythonhosted.org/packages/cc/79/09f02671eb75b251c5550a1c48e7b3d4b0623efd7c95a15a50f6f9fc1e2e/protobuf-7.34.0-cp310-abi3-manylinux2014_s390x.whl", hash = "sha256:4a72a8ec94e7a9f7ef7fe818ed26d073305f347f8b3b5ba31e22f81fd85fca02", size = 340200, upload-time = "2026-02-27T00:30:18.672Z" },
    { url = "https://files.pythonhosted.org/packages/b5/57/89727baef7578897af5ed166735ceb315819f1c184da8c3441271dbcfde7/protobuf-7.34.0-cp310-abi3-manylinux2014_x86_64.whl", hash = "sha256:964cf977e07f479c0697964e83deda72bcbc75c3badab506fb061b352d991b01", size = 324268, upload-time = "2026-02-27T00:30:20.088Z" },
    { url = "https://files.pythonhosted.org/packages/1f/3e/38ff2ddee5cc946f575c9d8cc822e34bde205cf61acf8099ad88ef19d7d2/protobuf-7.34.0-cp310-abi3-win32.whl", hash = "sha256:f791ec509707a1d91bd02e07df157e75e4fb9fbdad12a81b7396201ec244e2e3", size = 426628, upload-time = "2026-02-27T00:30:21.555Z" },
    { url = "https://files.pythonhosted.org/packages/cb/71/7c32eaf34a61a1bae1b62a2ac4ffe09b8d1bb0cf93ad505f42040023db89/protobuf-7.34.0-cp310-abi3-win_amd64.whl", hash = "sha256:9f9079f1dde4e32342ecbd1c118d76367090d4aaa19da78230c38101c5b3dd40", size = 437901, upload-time = "2026-02-27T00:30:22.836Z" },
    { url = "https://files.pythonhosted.org/packages/a4/e7/14dc9366696dcb53a413449881743426ed289d687bcf3d5aee4726c32ebb/protobuf-7.34.0-py3-none-any.whl", hash = "sha256:e3b914dd77fa33fa06ab2baa97937746ab25695f389869afdf03e81f34e45dc7", size = 170716, upload-time = "2026-02-27T00:30:23.994Z" },
]

[[package]]
name = "py-rust-stemmers"
version = "0.1.5"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/8e/63/4fbc14810c32d2a884e2e94e406a7d5bf8eee53e1103f558433817230342/py_rust_stemmers-0.1.5.tar.gz", hash = "sha256:e9c310cfb5c2470d7c7c8a0484725965e7cab8b1237e106a0863d5741da3e1f7", size = 9388, upload-time = "2025-02-19T13:56:28.708Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/36/9b/6b11f843c01d110db58a68ec4176cb77b37f03268831742a7241f4810fe4/py_rust_stemmers-0.1.5-cp311-cp311-macosx_10_12_x86_64.whl", hash = "sha256:e644987edaf66919f5a9e4693336930f98d67b790857890623a431bb77774c84", size = 286085, upload-time = "2025-02-19T13:55:08.484Z" },
    { url = "https://files.pythonhosted.org/packages/f2/d1/e16b587dc0ebc42916b1caad994bc37fbb19ad2c7e3f5f3a586ba2630c16/py_rust_stemmers-0.1.5-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:910d87d39ba75da1fe3d65df88b926b4b454ada8d73893cbd36e258a8a648158", size = 272019, upload-time = "2025-02-19T13:55:10.268Z" },
    { url = "https://files.pythonhosted.org/packages/41/66/8777f125720acb896b336e6f8153e3ec39754563bc9b89523cfe06ba63da/py_rust_stemmers-0.1.5-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:31ff4fb9417cec35907c18a6463e3d5a4941a5aa8401f77fbb4156b3ada69e3f", size = 310547, upload-time = "2025-02-19T13:55:11.521Z" },
    { url = "https://files.pythonhosted.org/packages/f1/f5/b79249c787c59b9ce2c5d007c0a0dc0fc1ecccfcf98a546c131cca55899e/py_rust_stemmers-0.1.5-cp311-cp311-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:07b3b8582313ef8a7f544acf2c887f27c3dd48c5ddca028fa0f498de7380e24f", size = 315238, upload-time = "2025-02-19T13:55:13.39Z" },
    { url = "https://files.pythonhosted.org/packages/62/4c/c05c266ed74c063ae31dc5633ed63c48eb3b78034afcc80fe755d0cb09e7/py_rust_stemmers-0.1.5-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:804944eeb5c5559443d81f30c34d6e83c6292d72423f299e42f9d71b9d240941", size = 324420, upload-time = "2025-02-19T13:55:15.292Z" },
    { url = "https://files.pythonhosted.org/packages/7f/65/feb83af28095397466e6e031989ff760cc89b01e7da169e76d4cf16a2252/py_rust_stemmers-0.1.5-cp311-cp311-manylinux_2_28_x86_64.whl", hash = "sha256:c52c5c326de78c70cfc71813fa56818d1bd4894264820d037d2be0e805b477bd", size = 324791, upload-time = "2025-02-19T13:55:16.45Z" },
    { url = "https://files.pythonhosted.org/packages/20/3e/162be2f9c1c383e66e510218d9d4946c8a84ee92c64f6d836746540e915f/py_rust_stemmers-0.1.5-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:d8f374c0f26ef35fb87212686add8dff394bcd9a1364f14ce40fe11504e25e30", size = 488014, upload-time = "2025-02-19T13:55:18.486Z" },
    { url = "https://files.pythonhosted.org/packages/a0/ee/ed09ce6fde1eefe50aa13a8a8533aa7ebe3cc096d1a43155cc71ba28d298/py_rust_stemmers-0.1.5-cp311-cp311-musllinux_1_2_armv7l.whl", hash = "sha256:0ae0540453843bc36937abb54fdbc0d5d60b51ef47aa9667afd05af9248e09eb", size = 575581, upload-time = "2025-02-19T13:55:19.669Z" },
    { url = "https://files.pythonhosted.org/packages/7b/31/2a48960a072e54d7cc244204d98854d201078e1bb5c68a7843a3f6d21ced/py_rust_stemmers-0.1.5-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:85944262c248ea30444155638c9e148a3adc61fe51cf9a3705b4055b564ec95d", size = 493269, upload-time = "2025-02-19T13:55:21.532Z" },
    { url = "https://files.pythonhosted.org/packages/91/33/872269c10ca35b00c5376159a2a0611a0f96372be16b616b46b3d59d09fe/py_rust_stemmers-0.1.5-cp311-none-win_amd64.whl", hash = "sha256:147234020b3eefe6e1a962173e41d8cf1dbf5d0689f3cd60e3022d1ac5c2e203", size = 209399, upload-time = "2025-02-19T13:55:22.639Z" },
    { url = "https://files.pythonhosted.org/packages/43/e1/ea8ac92454a634b1bb1ee0a89c2f75a4e6afec15a8412527e9bbde8c6b7b/py_rust_stemmers-0.1.5-cp312-cp312-macosx_10_12_x86_64.whl", hash = "sha256:29772837126a28263bf54ecd1bc709dd569d15a94d5e861937813ce51e8a6df4", size = 286085, upload-time = "2025-02-19T13:55:23.871Z" },
    { url = "https://files.pythonhosted.org/packages/cb/32/fe1cc3d36a19c1ce39792b1ed151ddff5ee1d74c8801f0e93ff36e65f885/py_rust_stemmers-0.1.5-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:4d62410ada44a01e02974b85d45d82f4b4c511aae9121e5f3c1ba1d0bea9126b", size = 272021, upload-time = "2025-02-19T13:55:25.685Z" },
    { url = "https://files.pythonhosted.org/packages/0a/38/b8f94e5e886e7ab181361a0911a14fb923b0d05b414de85f427e773bf445/py_rust_stemmers-0.1.5-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:b28ef729a4c83c7d9418be3c23c0372493fcccc67e86783ff04596ef8a208cdf", size = 310547, upload-time = "2025-02-19T13:55:26.891Z" },
    { url = "https://files.pythonhosted.org/packages/a9/08/62e97652d359b75335486f4da134a6f1c281f38bd3169ed6ecfb276448c3/py_rust_stemmers-0.1.5-cp312-cp312-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:a979c3f4ff7ad94a0d4cf566ca7bfecebb59e66488cc158e64485cf0c9a7879f", size = 315237, upload-time = "2025-02-19T13:55:28.116Z" },
    { url = "https://files.pythonhosted.org/packages/1c/b9/fc0278432f288d2be4ee4d5cc80fd8013d604506b9b0503e8b8cae4ba1c3/py_rust_stemmers-0.1.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:1c3593d895453fa06bf70a7b76d6f00d06def0f91fc253fe4260920650c5e078", size = 324419, upload-time = "2025-02-19T13:55:29.211Z" },
    { url = "https://files.pythonhosted.org/packages/6b/5b/74e96eaf622fe07e83c5c389d101540e305e25f76a6d0d6fb3d9e0506db8/py_rust_stemmers-0.1.5-cp312-cp312-manylinux_2_28_x86_64.whl", hash = "sha256:96ccc7fd042ffc3f7f082f2223bb7082ed1423aa6b43d5d89ab23e321936c045", size = 324792, upload-time = "2025-02-19T13:55:30.948Z" },
    { url = "https://files.pythonhosted.org/packages/4f/f7/b76816d7d67166e9313915ad486c21d9e7da0ac02703e14375bb1cb64b5a/py_rust_stemmers-0.1.5-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:ef18cfced2c9c676e0d7d172ba61c3fab2aa6969db64cc8f5ca33a7759efbefe", size = 488014, upload-time = "2025-02-19T13:55:32.066Z" },
    { url = "https://files.pythonhosted.org/packages/b9/ed/7d9bed02f78d85527501f86a867cd5002d97deb791b9a6b1b45b00100010/py_rust_stemmers-0.1.5-cp312-cp312-musllinux_1_2_armv7l.whl", hash = "sha256:541d4b5aa911381e3d37ec483abb6a2cf2351b4f16d5e8d77f9aa2722956662a", size = 575582, upload-time = "2025-02-19T13:55:34.005Z" },
    { url = "https://files.pythonhosted.org/packages/93/40/eafd1b33688e8e8ae946d1ef25c4dc93f5b685bd104b9c5573405d7e1d30/py_rust_stemmers-0.1.5-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:ffd946a36e9ac17ca96821963663012e04bc0ee94d21e8b5ae034721070b436c", size = 493267, upload-time = "2025-02-19T13:55:35.294Z" },
    { url = "https://files.pythonhosted.org/packages/2f/6a/15135b69e4fd28369433eb03264d201b1b0040ba534b05eddeb02a276684/py_rust_stemmers-0.1.5-cp312-none-win_amd64.whl", hash = "sha256:6ed61e1207f3b7428e99b5d00c055645c6415bb75033bff2d06394cbe035fd8e", size = 209395, upload-time = "2025-02-19T13:55:36.519Z" },
    { url = "https://files.pythonhosted.org/packages/80/b8/030036311ec25952bf3083b6c105be5dee052a71aa22d5fbeb857ebf8c1c/py_rust_stemmers-0.1.5-cp313-cp313-macosx_10_12_x86_64.whl", hash = "sha256:398b3a843a9cd4c5d09e726246bc36f66b3d05b0a937996814e91f47708f5db5", size = 286086, upload-time = "2025-02-19T13:55:37.581Z" },
    { url = "https://files.pythonhosted.org/packages/ed/be/0465dcb3a709ee243d464e89231e3da580017f34279d6304de291d65ccb0/py_rust_stemmers-0.1.5-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:4e308fc7687901f0c73603203869908f3156fa9c17c4ba010a7fcc98a7a1c5f2", size = 272019, upload-time = "2025-02-19T13:55:39.183Z" },
    { url = "https://files.pythonhosted.org/packages/ab/b6/76ca5b1f30cba36835938b5d9abee0c130c81833d51b9006264afdf8df3c/py_rust_stemmers-0.1.5-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:1f9efc4da5e734bdd00612e7506de3d0c9b7abc4b89d192742a0569d0d1fe749", size = 310545, upload-time = "2025-02-19T13:55:40.339Z" },
    { url = "https://files.pythonhosted.org/packages/56/8f/5be87618cea2fe2e70e74115a20724802bfd06f11c7c43514b8288eb6514/py_rust_stemmers-0.1.5-cp313-cp313-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:cc2cc8d2b36bc05b8b06506199ac63d437360ae38caefd98cd19e479d35afd42", size = 315236, upload-time = "2025-02-19T13:55:41.55Z" },
    { url = "https://files.pythonhosted.org/packages/00/02/ea86a316aee0f0a9d1449ad4dbffff38f4cf0a9a31045168ae8b95d8bdf8/py_rust_stemmers-0.1.5-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:a231dc6f0b2a5f12a080dfc7abd9e6a4ea0909290b10fd0a4620e5a0f52c3d17", size = 324419, upload-time = "2025-02-19T13:55:42.693Z" },
    { url = "https://files.pythonhosted.org/packages/2a/fd/1612c22545dcc0abe2f30fc08f30a2332f2224dd536fa1508444a9ca0e39/py_rust_stemmers-0.1.5-cp313-cp313-manylinux_2_28_x86_64.whl", hash = "sha256:5845709d48afc8b29e248f42f92431155a3d8df9ba30418301c49c6072b181b0", size = 324794, upload-time = "2025-02-19T13:55:43.896Z" },
    { url = "https://files.pythonhosted.org/packages/66/18/8a547584d7edac9e7ac9c7bdc53228d6f751c0f70a317093a77c386c8ddc/py_rust_stemmers-0.1.5-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:e48bfd5e3ce9d223bfb9e634dc1425cf93ee57eef6f56aa9a7120ada3990d4be", size = 488014, upload-time = "2025-02-19T13:55:45.088Z" },
    { url = "https://files.pythonhosted.org/packages/3b/87/4619c395b325e26048a6e28a365afed754614788ba1f49b2eefb07621a03/py_rust_stemmers-0.1.5-cp313-cp313-musllinux_1_2_armv7l.whl", hash = "sha256:35d32f6e7bdf6fd90e981765e32293a8be74def807147dea9fdc1f65d6ce382f", size = 575582, upload-time = "2025-02-19T13:55:46.436Z" },
    { url = "https://files.pythonhosted.org/packages/98/6e/214f1a889142b7df6d716e7f3fea6c41e87bd6c29046aa57e175d452b104/py_rust_stemmers-0.1.5-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:191ea8bf922c984631ffa20bf02ef0ad7eec0465baeaed3852779e8f97c7e7a3", size = 493269, upload-time = "2025-02-19T13:55:49.057Z" },
    { url = "https://files.pythonhosted.org/packages/e1/b9/c5185df277576f995ae34418eb2b2ac12f30835412270f9e05c52face521/py_rust_stemmers-0.1.5-cp313-none-win_amd64.whl", hash = "sha256:e564c9efdbe7621704e222b53bac265b0e4fbea788f07c814094f0ec6b80adcf", size = 209397, upload-time = "2025-02-19T13:55:50.853Z" },
]

[[package]]
name = "pydantic"
version = "2.12.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "annotated-types" },
    { name = "pydantic-core" },
    { name = "typing-extensions" },
    { name = "typing-inspection" },
]
sdist = { url = "https://files.pythonhosted.org/packages/69/44/36f1a6e523abc58ae5f928898e4aca2e0ea509b5aa6f6f392a5d882be928/pydantic-2.12.5.tar.gz", hash = "sha256:4d351024c75c0f085a9febbb665ce8c0c6ec5d30e903bdb6394b7ede26aebb49", size = 821591, upload-time = "2025-11-26T15:11:46.471Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/5a/87/b70ad306ebb6f9b585f114d0ac2137d792b48be34d732d60e597c2f8465a/pydantic-2.12.5-py3-none-any.whl", hash = "sha256:e561593fccf61e8a20fc46dfc2dfe075b8be7d0188df33f221ad1f0139180f9d", size = 463580, upload-time = "2025-11-26T15:11:44.605Z" },
]

[[package]]
name = "pydantic-core"
version = "2.41.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/71/70/23b021c950c2addd24ec408e9ab05d59b035b39d97cdc1130e1bce647bb6/pydantic_core-2.41.5.tar.gz", hash = "sha256:08daa51ea16ad373ffd5e7606252cc32f07bc72b28284b6bc9c6df804816476e", size = 460952, upload-time = "2025-11-04T13:43:49.098Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e8/72/74a989dd9f2084b3d9530b0915fdda64ac48831c30dbf7c72a41a5232db8/pydantic_core-2.41.5-cp311-cp311-macosx_10_12_x86_64.whl", hash = "sha256:a3a52f6156e73e7ccb0f8cced536adccb7042be67cb45f9562e12b319c119da6", size = 2105873, upload-time = "2025-11-04T13:39:31.373Z" },
    { url = "https://files.pythonhosted.org/packages/12/44/37e403fd9455708b3b942949e1d7febc02167662bf1a7da5b78ee1ea2842/pydantic_core-2.41.5-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:7f3bf998340c6d4b0c9a2f02d6a400e51f123b59565d74dc60d252ce888c260b", size = 1899826, upload-time = "2025-11-04T13:39:32.897Z" },
    { url = "https://files.pythonhosted.org/packages/33/7f/1d5cab3ccf44c1935a359d51a8a2a9e1a654b744b5e7f80d41b88d501eec/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:378bec5c66998815d224c9ca994f1e14c0c21cb95d2f52b6021cc0b2a58f2a5a", size = 1917869, upload-time = "2025-11-04T13:39:34.469Z" },
    { url = "https://files.pythonhosted.org/packages/6e/6a/30d94a9674a7fe4f4744052ed6c5e083424510be1e93da5bc47569d11810/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:e7b576130c69225432866fe2f4a469a85a54ade141d96fd396dffcf607b558f8", size = 2063890, upload-time = "2025-11-04T13:39:36.053Z" },
    { url = "https://files.pythonhosted.org/packages/50/be/76e5d46203fcb2750e542f32e6c371ffa9b8ad17364cf94bb0818dbfb50c/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:6cb58b9c66f7e4179a2d5e0f849c48eff5c1fca560994d6eb6543abf955a149e", size = 2229740, upload-time = "2025-11-04T13:39:37.753Z" },
    { url = "https://files.pythonhosted.org/packages/d3/ee/fed784df0144793489f87db310a6bbf8118d7b630ed07aa180d6067e653a/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:88942d3a3dff3afc8288c21e565e476fc278902ae4d6d134f1eeda118cc830b1", size = 2350021, upload-time = "2025-11-04T13:39:40.94Z" },
    { url = "https://files.pythonhosted.org/packages/c8/be/8fed28dd0a180dca19e72c233cbf58efa36df055e5b9d90d64fd1740b828/pydantic_core-2.41.5-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:f31d95a179f8d64d90f6831d71fa93290893a33148d890ba15de25642c5d075b", size = 2066378, upload-time = "2025-11-04T13:39:42.523Z" },
    { url = "https://files.pythonhosted.org/packages/b0/3b/698cf8ae1d536a010e05121b4958b1257f0b5522085e335360e53a6b1c8b/pydantic_core-2.41.5-cp311-cp311-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:c1df3d34aced70add6f867a8cf413e299177e0c22660cc767218373d0779487b", size = 2175761, upload-time = "2025-11-04T13:39:44.553Z" },
    { url = "https://files.pythonhosted.org/packages/b8/ba/15d537423939553116dea94ce02f9c31be0fa9d0b806d427e0308ec17145/pydantic_core-2.41.5-cp311-cp311-musllinux_1_1_aarch64.whl", hash = "sha256:4009935984bd36bd2c774e13f9a09563ce8de4abaa7226f5108262fa3e637284", size = 2146303, upload-time = "2025-11-04T13:39:46.238Z" },
    { url = "https://files.pythonhosted.org/packages/58/7f/0de669bf37d206723795f9c90c82966726a2ab06c336deba4735b55af431/pydantic_core-2.41.5-cp311-cp311-musllinux_1_1_armv7l.whl", hash = "sha256:34a64bc3441dc1213096a20fe27e8e128bd3ff89921706e83c0b1ac971276594", size = 2340355, upload-time = "2025-11-04T13:39:48.002Z" },
    { url = "https://files.pythonhosted.org/packages/e5/de/e7482c435b83d7e3c3ee5ee4451f6e8973cff0eb6007d2872ce6383f6398/pydantic_core-2.41.5-cp311-cp311-musllinux_1_1_x86_64.whl", hash = "sha256:c9e19dd6e28fdcaa5a1de679aec4141f691023916427ef9bae8584f9c2fb3b0e", size = 2319875, upload-time = "2025-11-04T13:39:49.705Z" },
    { url = "https://files.pythonhosted.org/packages/fe/e6/8c9e81bb6dd7560e33b9053351c29f30c8194b72f2d6932888581f503482/pydantic_core-2.41.5-cp311-cp311-win32.whl", hash = "sha256:2c010c6ded393148374c0f6f0bf89d206bf3217f201faa0635dcd56bd1520f6b", size = 1987549, upload-time = "2025-11-04T13:39:51.842Z" },
    { url = "https://files.pythonhosted.org/packages/11/66/f14d1d978ea94d1bc21fc98fcf570f9542fe55bfcc40269d4e1a21c19bf7/pydantic_core-2.41.5-cp311-cp311-win_amd64.whl", hash = "sha256:76ee27c6e9c7f16f47db7a94157112a2f3a00e958bc626e2f4ee8bec5c328fbe", size = 2011305, upload-time = "2025-11-04T13:39:53.485Z" },
    { url = "https://files.pythonhosted.org/packages/56/d8/0e271434e8efd03186c5386671328154ee349ff0354d83c74f5caaf096ed/pydantic_core-2.41.5-cp311-cp311-win_arm64.whl", hash = "sha256:4bc36bbc0b7584de96561184ad7f012478987882ebf9f9c389b23f432ea3d90f", size = 1972902, upload-time = "2025-11-04T13:39:56.488Z" },
    { url = "https://files.pythonhosted.org/packages/5f/5d/5f6c63eebb5afee93bcaae4ce9a898f3373ca23df3ccaef086d0233a35a7/pydantic_core-2.41.5-cp312-cp312-macosx_10_12_x86_64.whl", hash = "sha256:f41a7489d32336dbf2199c8c0a215390a751c5b014c2c1c5366e817202e9cdf7", size = 2110990, upload-time = "2025-11-04T13:39:58.079Z" },
    { url = "https://files.pythonhosted.org/packages/aa/32/9c2e8ccb57c01111e0fd091f236c7b371c1bccea0fa85247ac55b1e2b6b6/pydantic_core-2.41.5-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:070259a8818988b9a84a449a2a7337c7f430a22acc0859c6b110aa7212a6d9c0", size = 1896003, upload-time = "2025-11-04T13:39:59.956Z" },
    { url = "https://files.pythonhosted.org/packages/68/b8/a01b53cb0e59139fbc9e4fda3e9724ede8de279097179be4ff31f1abb65a/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:e96cea19e34778f8d59fe40775a7a574d95816eb150850a85a7a4c8f4b94ac69", size = 1919200, upload-time = "2025-11-04T13:40:02.241Z" },
    { url = "https://files.pythonhosted.org/packages/38/de/8c36b5198a29bdaade07b5985e80a233a5ac27137846f3bc2d3b40a47360/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:ed2e99c456e3fadd05c991f8f437ef902e00eedf34320ba2b0842bd1c3ca3a75", size = 2052578, upload-time = "2025-11-04T13:40:04.401Z" },
    { url = "https://files.pythonhosted.org/packages/00/b5/0e8e4b5b081eac6cb3dbb7e60a65907549a1ce035a724368c330112adfdd/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:65840751b72fbfd82c3c640cff9284545342a4f1eb1586ad0636955b261b0b05", size = 2208504, upload-time = "2025-11-04T13:40:06.072Z" },
    { url = "https://files.pythonhosted.org/packages/77/56/87a61aad59c7c5b9dc8caad5a41a5545cba3810c3e828708b3d7404f6cef/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:e536c98a7626a98feb2d3eaf75944ef6f3dbee447e1f841eae16f2f0a72d8ddc", size = 2335816, upload-time = "2025-11-04T13:40:07.835Z" },
    { url = "https://files.pythonhosted.org/packages/0d/76/941cc9f73529988688a665a5c0ecff1112b3d95ab48f81db5f7606f522d3/pydantic_core-2.41.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:eceb81a8d74f9267ef4081e246ffd6d129da5d87e37a77c9bde550cb04870c1c", size = 2075366, upload-time = "2025-11-04T13:40:09.804Z" },
    { url = "https://files.pythonhosted.org/packages/d3/43/ebef01f69baa07a482844faaa0a591bad1ef129253ffd0cdaa9d8a7f72d3/pydantic_core-2.41.5-cp312-cp312-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:d38548150c39b74aeeb0ce8ee1d8e82696f4a4e16ddc6de7b1d8823f7de4b9b5", size = 2171698, upload-time = "2025-11-04T13:40:12.004Z" },
    { url = "https://files.pythonhosted.org/packages/b1/87/41f3202e4193e3bacfc2c065fab7706ebe81af46a83d3e27605029c1f5a6/pydantic_core-2.41.5-cp312-cp312-musllinux_1_1_aarch64.whl", hash = "sha256:c23e27686783f60290e36827f9c626e63154b82b116d7fe9adba1fda36da706c", size = 2132603, upload-time = "2025-11-04T13:40:13.868Z" },
    { url = "https://files.pythonhosted.org/packages/49/7d/4c00df99cb12070b6bccdef4a195255e6020a550d572768d92cc54dba91a/pydantic_core-2.41.5-cp312-cp312-musllinux_1_1_armv7l.whl", hash = "sha256:482c982f814460eabe1d3bb0adfdc583387bd4691ef00b90575ca0d2b6fe2294", size = 2329591, upload-time = "2025-11-04T13:40:15.672Z" },
    { url = "https://files.pythonhosted.org/packages/cc/6a/ebf4b1d65d458f3cda6a7335d141305dfa19bdc61140a884d165a8a1bbc7/pydantic_core-2.41.5-cp312-cp312-musllinux_1_1_x86_64.whl", hash = "sha256:bfea2a5f0b4d8d43adf9d7b8bf019fb46fdd10a2e5cde477fbcb9d1fa08c68e1", size = 2319068, upload-time = "2025-11-04T13:40:17.532Z" },
    { url = "https://files.pythonhosted.org/packages/49/3b/774f2b5cd4192d5ab75870ce4381fd89cf218af999515baf07e7206753f0/pydantic_core-2.41.5-cp312-cp312-win32.whl", hash = "sha256:b74557b16e390ec12dca509bce9264c3bbd128f8a2c376eaa68003d7f327276d", size = 1985908, upload-time = "2025-11-04T13:40:19.309Z" },
    { url = "https://files.pythonhosted.org/packages/86/45/00173a033c801cacf67c190fef088789394feaf88a98a7035b0e40d53dc9/pydantic_core-2.41.5-cp312-cp312-win_amd64.whl", hash = "sha256:1962293292865bca8e54702b08a4f26da73adc83dd1fcf26fbc875b35d81c815", size = 2020145, upload-time = "2025-11-04T13:40:21.548Z" },
    { url = "https://files.pythonhosted.org/packages/f9/22/91fbc821fa6d261b376a3f73809f907cec5ca6025642c463d3488aad22fb/pydantic_core-2.41.5-cp312-cp312-win_arm64.whl", hash = "sha256:1746d4a3d9a794cacae06a5eaaccb4b8643a131d45fbc9af23e353dc0a5ba5c3", size = 1976179, upload-time = "2025-11-04T13:40:23.393Z" },
    { url = "https://files.pythonhosted.org/packages/87/06/8806241ff1f70d9939f9af039c6c35f2360cf16e93c2ca76f184e76b1564/pydantic_core-2.41.5-cp313-cp313-macosx_10_12_x86_64.whl", hash = "sha256:941103c9be18ac8daf7b7adca8228f8ed6bb7a1849020f643b3a14d15b1924d9", size = 2120403, upload-time = "2025-11-04T13:40:25.248Z" },
    { url = "https://files.pythonhosted.org/packages/94/02/abfa0e0bda67faa65fef1c84971c7e45928e108fe24333c81f3bfe35d5f5/pydantic_core-2.41.5-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:112e305c3314f40c93998e567879e887a3160bb8689ef3d2c04b6cc62c33ac34", size = 1896206, upload-time = "2025-11-04T13:40:27.099Z" },
    { url = "https://files.pythonhosted.org/packages/15/df/a4c740c0943e93e6500f9eb23f4ca7ec9bf71b19e608ae5b579678c8d02f/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:0cbaad15cb0c90aa221d43c00e77bb33c93e8d36e0bf74760cd00e732d10a6a0", size = 1919307, upload-time = "2025-11-04T13:40:29.806Z" },
    { url = "https://files.pythonhosted.org/packages/9a/e3/6324802931ae1d123528988e0e86587c2072ac2e5394b4bc2bc34b61ff6e/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:03ca43e12fab6023fc79d28ca6b39b05f794ad08ec2feccc59a339b02f2b3d33", size = 2063258, upload-time = "2025-11-04T13:40:33.544Z" },
    { url = "https://files.pythonhosted.org/packages/c9/d4/2230d7151d4957dd79c3044ea26346c148c98fbf0ee6ebd41056f2d62ab5/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:dc799088c08fa04e43144b164feb0c13f9a0bc40503f8df3e9fde58a3c0c101e", size = 2214917, upload-time = "2025-11-04T13:40:35.479Z" },
    { url = "https://files.pythonhosted.org/packages/e6/9f/eaac5df17a3672fef0081b6c1bb0b82b33ee89aa5cec0d7b05f52fd4a1fa/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:97aeba56665b4c3235a0e52b2c2f5ae9cd071b8a8310ad27bddb3f7fb30e9aa2", size = 2332186, upload-time = "2025-11-04T13:40:37.436Z" },
    { url = "https://files.pythonhosted.org/packages/cf/4e/35a80cae583a37cf15604b44240e45c05e04e86f9cfd766623149297e971/pydantic_core-2.41.5-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:406bf18d345822d6c21366031003612b9c77b3e29ffdb0f612367352aab7d586", size = 2073164, upload-time = "2025-11-04T13:40:40.289Z" },
    { url = "https://files.pythonhosted.org/packages/bf/e3/f6e262673c6140dd3305d144d032f7bd5f7497d3871c1428521f19f9efa2/pydantic_core-2.41.5-cp313-cp313-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:b93590ae81f7010dbe380cdeab6f515902ebcbefe0b9327cc4804d74e93ae69d", size = 2179146, upload-time = "2025-11-04T13:40:42.809Z" },
    { url = "https://files.pythonhosted.org/packages/75/c7/20bd7fc05f0c6ea2056a4565c6f36f8968c0924f19b7d97bbfea55780e73/pydantic_core-2.41.5-cp313-cp313-musllinux_1_1_aarch64.whl", hash = "sha256:01a3d0ab748ee531f4ea6c3e48ad9dac84ddba4b0d82291f87248f2f9de8d740", size = 2137788, upload-time = "2025-11-04T13:40:44.752Z" },
    { url = "https://files.pythonhosted.org/packages/3a/8d/34318ef985c45196e004bc46c6eab2eda437e744c124ef0dbe1ff2c9d06b/pydantic_core-2.41.5-cp313-cp313-musllinux_1_1_armv7l.whl", hash = "sha256:6561e94ba9dacc9c61bce40e2d6bdc3bfaa0259d3ff36ace3b1e6901936d2e3e", size = 2340133, upload-time = "2025-11-04T13:40:46.66Z" },
    { url = "https://files.pythonhosted.org/packages/9c/59/013626bf8c78a5a5d9350d12e7697d3d4de951a75565496abd40ccd46bee/pydantic_core-2.41.5-cp313-cp313-musllinux_1_1_x86_64.whl", hash = "sha256:915c3d10f81bec3a74fbd4faebe8391013ba61e5a1a8d48c4455b923bdda7858", size = 2324852, upload-time = "2025-11-04T13:40:48.575Z" },
    { url = "https://files.pythonhosted.org/packages/1a/d9/c248c103856f807ef70c18a4f986693a46a8ffe1602e5d361485da502d20/pydantic_core-2.41.5-cp313-cp313-win32.whl", hash = "sha256:650ae77860b45cfa6e2cdafc42618ceafab3a2d9a3811fcfbd3bbf8ac3c40d36", size = 1994679, upload-time = "2025-11-04T13:40:50.619Z" },
    { url = "https://files.pythonhosted.org/packages/9e/8b/341991b158ddab181cff136acd2552c9f35bd30380422a639c0671e99a91/pydantic_core-2.41.5-cp313-cp313-win_amd64.whl", hash = "sha256:79ec52ec461e99e13791ec6508c722742ad745571f234ea6255bed38c6480f11", size = 2019766, upload-time = "2025-11-04T13:40:52.631Z" },
    { url = "https://files.pythonhosted.org/packages/73/7d/f2f9db34af103bea3e09735bb40b021788a5e834c81eedb541991badf8f5/pydantic_core-2.41.5-cp313-cp313-win_arm64.whl", hash = "sha256:3f84d5c1b4ab906093bdc1ff10484838aca54ef08de4afa9de0f5f14d69639cd", size = 1981005, upload-time = "2025-11-04T13:40:54.734Z" },
    { url = "https://files.pythonhosted.org/packages/ea/28/46b7c5c9635ae96ea0fbb779e271a38129df2550f763937659ee6c5dbc65/pydantic_core-2.41.5-cp314-cp314-macosx_10_12_x86_64.whl", hash = "sha256:3f37a19d7ebcdd20b96485056ba9e8b304e27d9904d233d7b1015db320e51f0a", size = 2119622, upload-time = "2025-11-04T13:40:56.68Z" },
    { url = "https://files.pythonhosted.org/packages/74/1a/145646e5687e8d9a1e8d09acb278c8535ebe9e972e1f162ed338a622f193/pydantic_core-2.41.5-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:1d1d9764366c73f996edd17abb6d9d7649a7eb690006ab6adbda117717099b14", size = 1891725, upload-time = "2025-11-04T13:40:58.807Z" },
    { url = "https://files.pythonhosted.org/packages/23/04/e89c29e267b8060b40dca97bfc64a19b2a3cf99018167ea1677d96368273/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:25e1c2af0fce638d5f1988b686f3b3ea8cd7de5f244ca147c777769e798a9cd1", size = 1915040, upload-time = "2025-11-04T13:41:00.853Z" },
    { url = "https://files.pythonhosted.org/packages/84/a3/15a82ac7bd97992a82257f777b3583d3e84bdb06ba6858f745daa2ec8a85/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:506d766a8727beef16b7adaeb8ee6217c64fc813646b424d0804d67c16eddb66", size = 2063691, upload-time = "2025-11-04T13:41:03.504Z" },
    { url = "https://files.pythonhosted.org/packages/74/9b/0046701313c6ef08c0c1cf0e028c67c770a4e1275ca73131563c5f2a310a/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:4819fa52133c9aa3c387b3328f25c1facc356491e6135b459f1de698ff64d869", size = 2213897, upload-time = "2025-11-04T13:41:05.804Z" },
    { url = "https://files.pythonhosted.org/packages/8a/cd/6bac76ecd1b27e75a95ca3a9a559c643b3afcd2dd62086d4b7a32a18b169/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:2b761d210c9ea91feda40d25b4efe82a1707da2ef62901466a42492c028553a2", size = 2333302, upload-time = "2025-11-04T13:41:07.809Z" },
    { url = "https://files.pythonhosted.org/packages/4c/d2/ef2074dc020dd6e109611a8be4449b98cd25e1b9b8a303c2f0fca2f2bcf7/pydantic_core-2.41.5-cp314-cp314-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:22f0fb8c1c583a3b6f24df2470833b40207e907b90c928cc8d3594b76f874375", size = 2064877, upload-time = "2025-11-04T13:41:09.827Z" },
    { url = "https://files.pythonhosted.org/packages/18/66/e9db17a9a763d72f03de903883c057b2592c09509ccfe468187f2a2eef29/pydantic_core-2.41.5-cp314-cp314-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:2782c870e99878c634505236d81e5443092fba820f0373997ff75f90f68cd553", size = 2180680, upload-time = "2025-11-04T13:41:12.379Z" },
    { url = "https://files.pythonhosted.org/packages/d3/9e/3ce66cebb929f3ced22be85d4c2399b8e85b622db77dad36b73c5387f8f8/pydantic_core-2.41.5-cp314-cp314-musllinux_1_1_aarch64.whl", hash = "sha256:0177272f88ab8312479336e1d777f6b124537d47f2123f89cb37e0accea97f90", size = 2138960, upload-time = "2025-11-04T13:41:14.627Z" },
    { url = "https://files.pythonhosted.org/packages/a6/62/205a998f4327d2079326b01abee48e502ea739d174f0a89295c481a2272e/pydantic_core-2.41.5-cp314-cp314-musllinux_1_1_armv7l.whl", hash = "sha256:63510af5e38f8955b8ee5687740d6ebf7c2a0886d15a6d65c32814613681bc07", size = 2339102, upload-time = "2025-11-04T13:41:16.868Z" },
    { url = "https://files.pythonhosted.org/packages/3c/0d/f05e79471e889d74d3d88f5bd20d0ed189ad94c2423d81ff8d0000aab4ff/pydantic_core-2.41.5-cp314-cp314-musllinux_1_1_x86_64.whl", hash = "sha256:e56ba91f47764cc14f1daacd723e3e82d1a89d783f0f5afe9c364b8bb491ccdb", size = 2326039, upload-time = "2025-11-04T13:41:18.934Z" },
    { url = "https://files.pythonhosted.org/packages/ec/e1/e08a6208bb100da7e0c4b288eed624a703f4d129bde2da475721a80cab32/pydantic_core-2.41.5-cp314-cp314-win32.whl", hash = "sha256:aec5cf2fd867b4ff45b9959f8b20ea3993fc93e63c7363fe6851424c8a7e7c23", size = 1995126, upload-time = "2025-11-04T13:41:21.418Z" },
    { url = "https://files.pythonhosted.org/packages/48/5d/56ba7b24e9557f99c9237e29f5c09913c81eeb2f3217e40e922353668092/pydantic_core-2.41.5-cp314-cp314-win_amd64.whl", hash = "sha256:8e7c86f27c585ef37c35e56a96363ab8de4e549a95512445b85c96d3e2f7c1bf", size = 2015489, upload-time = "2025-11-04T13:41:24.076Z" },
    { url = "https://files.pythonhosted.org/packages/4e/bb/f7a190991ec9e3e0ba22e4993d8755bbc4a32925c0b5b42775c03e8148f9/pydantic_core-2.41.5-cp314-cp314-win_arm64.whl", hash = "sha256:e672ba74fbc2dc8eea59fb6d4aed6845e6905fc2a8afe93175d94a83ba2a01a0", size = 1977288, upload-time = "2025-11-04T13:41:26.33Z" },
    { url = "https://files.pythonhosted.org/packages/92/ed/77542d0c51538e32e15afe7899d79efce4b81eee631d99850edc2f5e9349/pydantic_core-2.41.5-cp314-cp314t-macosx_10_12_x86_64.whl", hash = "sha256:8566def80554c3faa0e65ac30ab0932b9e3a5cd7f8323764303d468e5c37595a", size = 2120255, upload-time = "2025-11-04T13:41:28.569Z" },
    { url = "https://files.pythonhosted.org/packages/bb/3d/6913dde84d5be21e284439676168b28d8bbba5600d838b9dca99de0fad71/pydantic_core-2.41.5-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:b80aa5095cd3109962a298ce14110ae16b8c1aece8b72f9dafe81cf597ad80b3", size = 1863760, upload-time = "2025-11-04T13:41:31.055Z" },
    { url = "https://files.pythonhosted.org/packages/5a/f0/e5e6b99d4191da102f2b0eb9687aaa7f5bea5d9964071a84effc3e40f997/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:3006c3dd9ba34b0c094c544c6006cc79e87d8612999f1a5d43b769b89181f23c", size = 1878092, upload-time = "2025-11-04T13:41:33.21Z" },
    { url = "https://files.pythonhosted.org/packages/71/48/36fb760642d568925953bcc8116455513d6e34c4beaa37544118c36aba6d/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:72f6c8b11857a856bcfa48c86f5368439f74453563f951e473514579d44aa612", size = 2053385, upload-time = "2025-11-04T13:41:35.508Z" },
    { url = "https://files.pythonhosted.org/packages/20/25/92dc684dd8eb75a234bc1c764b4210cf2646479d54b47bf46061657292a8/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:5cb1b2f9742240e4bb26b652a5aeb840aa4b417c7748b6f8387927bc6e45e40d", size = 2218832, upload-time = "2025-11-04T13:41:37.732Z" },
    { url = "https://files.pythonhosted.org/packages/e2/09/f53e0b05023d3e30357d82eb35835d0f6340ca344720a4599cd663dca599/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:bd3d54f38609ff308209bd43acea66061494157703364ae40c951f83ba99a1a9", size = 2327585, upload-time = "2025-11-04T13:41:40Z" },
    { url = "https://files.pythonhosted.org/packages/aa/4e/2ae1aa85d6af35a39b236b1b1641de73f5a6ac4d5a7509f77b814885760c/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:2ff4321e56e879ee8d2a879501c8e469414d948f4aba74a2d4593184eb326660", size = 2041078, upload-time = "2025-11-04T13:41:42.323Z" },
    { url = "https://files.pythonhosted.org/packages/cd/13/2e215f17f0ef326fc72afe94776edb77525142c693767fc347ed6288728d/pydantic_core-2.41.5-cp314-cp314t-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:d0d2568a8c11bf8225044aa94409e21da0cb09dcdafe9ecd10250b2baad531a9", size = 2173914, upload-time = "2025-11-04T13:41:45.221Z" },
    { url = "https://files.pythonhosted.org/packages/02/7a/f999a6dcbcd0e5660bc348a3991c8915ce6599f4f2c6ac22f01d7a10816c/pydantic_core-2.41.5-cp314-cp314t-musllinux_1_1_aarch64.whl", hash = "sha256:a39455728aabd58ceabb03c90e12f71fd30fa69615760a075b9fec596456ccc3", size = 2129560, upload-time = "2025-11-04T13:41:47.474Z" },
    { url = "https://files.pythonhosted.org/packages/3a/b1/6c990ac65e3b4c079a4fb9f5b05f5b013afa0f4ed6780a3dd236d2cbdc64/pydantic_core-2.41.5-cp314-cp314t-musllinux_1_1_armv7l.whl", hash = "sha256:239edca560d05757817c13dc17c50766136d21f7cd0fac50295499ae24f90fdf", size = 2329244, upload-time = "2025-11-04T13:41:49.992Z" },
    { url = "https://files.pythonhosted.org/packages/d9/02/3c562f3a51afd4d88fff8dffb1771b30cfdfd79befd9883ee094f5b6c0d8/pydantic_core-2.41.5-cp314-cp314t-musllinux_1_1_x86_64.whl", hash = "sha256:2a5e06546e19f24c6a96a129142a75cee553cc018ffee48a460059b1185f4470", size = 2331955, upload-time = "2025-11-04T13:41:54.079Z" },
    { url = "https://files.pythonhosted.org/packages/5c/96/5fb7d8c3c17bc8c62fdb031c47d77a1af698f1d7a406b0f79aaa1338f9ad/pydantic_core-2.41.5-cp314-cp314t-win32.whl", hash = "sha256:b4ececa40ac28afa90871c2cc2b9ffd2ff0bf749380fbdf57d165fd23da353aa", size = 1988906, upload-time = "2025-11-04T13:41:56.606Z" },
    { url = "https://files.pythonhosted.org/packages/22/ed/182129d83032702912c2e2d8bbe33c036f342cc735737064668585dac28f/pydantic_core-2.41.5-cp314-cp314t-win_amd64.whl", hash = "sha256:80aa89cad80b32a912a65332f64a4450ed00966111b6615ca6816153d3585a8c", size = 1981607, upload-time = "2025-11-04T13:41:58.889Z" },
    { url = "https://files.pythonhosted.org/packages/9f/ed/068e41660b832bb0b1aa5b58011dea2a3fe0ba7861ff38c4d4904c1c1a99/pydantic_core-2.41.5-cp314-cp314t-win_arm64.whl", hash = "sha256:35b44f37a3199f771c3eaa53051bc8a70cd7b54f333531c59e29fd4db5d15008", size = 1974769, upload-time = "2025-11-04T13:42:01.186Z" },
    { url = "https://files.pythonhosted.org/packages/11/72/90fda5ee3b97e51c494938a4a44c3a35a9c96c19bba12372fb9c634d6f57/pydantic_core-2.41.5-graalpy311-graalpy242_311_native-macosx_10_12_x86_64.whl", hash = "sha256:b96d5f26b05d03cc60f11a7761a5ded1741da411e7fe0909e27a5e6a0cb7b034", size = 2115441, upload-time = "2025-11-04T13:42:39.557Z" },
    { url = "https://files.pythonhosted.org/packages/1f/53/8942f884fa33f50794f119012dc6a1a02ac43a56407adaac20463df8e98f/pydantic_core-2.41.5-graalpy311-graalpy242_311_native-macosx_11_0_arm64.whl", hash = "sha256:634e8609e89ceecea15e2d61bc9ac3718caaaa71963717bf3c8f38bfde64242c", size = 1930291, upload-time = "2025-11-04T13:42:42.169Z" },
    { url = "https://files.pythonhosted.org/packages/79/c8/ecb9ed9cd942bce09fc888ee960b52654fbdbede4ba6c2d6e0d3b1d8b49c/pydantic_core-2.41.5-graalpy311-graalpy242_311_native-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:93e8740d7503eb008aa2df04d3b9735f845d43ae845e6dcd2be0b55a2da43cd2", size = 1948632, upload-time = "2025-11-04T13:42:44.564Z" },
    { url = "https://files.pythonhosted.org/packages/2e/1b/687711069de7efa6af934e74f601e2a4307365e8fdc404703afc453eab26/pydantic_core-2.41.5-graalpy311-graalpy242_311_native-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:f15489ba13d61f670dcc96772e733aad1a6f9c429cc27574c6cdaed82d0146ad", size = 2138905, upload-time = "2025-11-04T13:42:47.156Z" },
    { url = "https://files.pythonhosted.org/packages/09/32/59b0c7e63e277fa7911c2fc70ccfb45ce4b98991e7ef37110663437005af/pydantic_core-2.41.5-graalpy312-graalpy250_312_native-macosx_10_12_x86_64.whl", hash = "sha256:7da7087d756b19037bc2c06edc6c170eeef3c3bafcb8f532ff17d64dc427adfd", size = 2110495, upload-time = "2025-11-04T13:42:49.689Z" },
    { url = "https://files.pythonhosted.org/packages/aa/81/05e400037eaf55ad400bcd318c05bb345b57e708887f07ddb2d20e3f0e98/pydantic_core-2.41.5-graalpy312-graalpy250_312_native-macosx_11_0_arm64.whl", hash = "sha256:aabf5777b5c8ca26f7824cb4a120a740c9588ed58df9b2d196ce92fba42ff8dc", size = 1915388, upload-time = "2025-11-04T13:42:52.215Z" },
    { url = "https://files.pythonhosted.org/packages/6e/0d/e3549b2399f71d56476b77dbf3cf8937cec5cd70536bdc0e374a421d0599/pydantic_core-2.41.5-graalpy312-graalpy250_312_native-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:c007fe8a43d43b3969e8469004e9845944f1a80e6acd47c150856bb87f230c56", size = 1942879, upload-time = "2025-11-04T13:42:56.483Z" },
    { url = "https://files.pythonhosted.org/packages/f7/07/34573da085946b6a313d7c42f82f16e8920bfd730665de2d11c0c37a74b5/pydantic_core-2.41.5-graalpy312-graalpy250_312_native-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:76d0819de158cd855d1cbb8fcafdf6f5cf1eb8e470abe056d5d161106e38062b", size = 2139017, upload-time = "2025-11-04T13:42:59.471Z" },
    { url = "https://files.pythonhosted.org/packages/5f/9b/1b3f0e9f9305839d7e84912f9e8bfbd191ed1b1ef48083609f0dabde978c/pydantic_core-2.41.5-pp311-pypy311_pp73-macosx_10_12_x86_64.whl", hash = "sha256:b2379fa7ed44ddecb5bfe4e48577d752db9fc10be00a6b7446e9663ba143de26", size = 2101980, upload-time = "2025-11-04T13:43:25.97Z" },
    { url = "https://files.pythonhosted.org/packages/a4/ed/d71fefcb4263df0da6a85b5d8a7508360f2f2e9b3bf5814be9c8bccdccc1/pydantic_core-2.41.5-pp311-pypy311_pp73-macosx_11_0_arm64.whl", hash = "sha256:266fb4cbf5e3cbd0b53669a6d1b039c45e3ce651fd5442eff4d07c2cc8d66808", size = 1923865, upload-time = "2025-11-04T13:43:28.763Z" },
    { url = "https://files.pythonhosted.org/packages/ce/3a/626b38db460d675f873e4444b4bb030453bbe7b4ba55df821d026a0493c4/pydantic_core-2.41.5-pp311-pypy311_pp73-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:58133647260ea01e4d0500089a8c4f07bd7aa6ce109682b1426394988d8aaacc", size = 2134256, upload-time = "2025-11-04T13:43:31.71Z" },
    { url = "https://files.pythonhosted.org/packages/83/d9/8412d7f06f616bbc053d30cb4e5f76786af3221462ad5eee1f202021eb4e/pydantic_core-2.41.5-pp311-pypy311_pp73-manylinux_2_5_i686.manylinux1_i686.whl", hash = "sha256:287dad91cfb551c363dc62899a80e9e14da1f0e2b6ebde82c806612ca2a13ef1", size = 2174762, upload-time = "2025-11-04T13:43:34.744Z" },
    { url = "https://files.pythonhosted.org/packages/55/4c/162d906b8e3ba3a99354e20faa1b49a85206c47de97a639510a0e673f5da/pydantic_core-2.41.5-pp311-pypy311_pp73-musllinux_1_1_aarch64.whl", hash = "sha256:03b77d184b9eb40240ae9fd676ca364ce1085f203e1b1256f8ab9984dca80a84", size = 2143141, upload-time = "2025-11-04T13:43:37.701Z" },
    { url = "https://files.pythonhosted.org/packages/1f/f2/f11dd73284122713f5f89fc940f370d035fa8e1e078d446b3313955157fe/pydantic_core-2.41.5-pp311-pypy311_pp73-musllinux_1_1_armv7l.whl", hash = "sha256:a668ce24de96165bb239160b3d854943128f4334822900534f2fe947930e5770", size = 2330317, upload-time = "2025-11-04T13:43:40.406Z" },
    { url = "https://files.pythonhosted.org/packages/88/9d/b06ca6acfe4abb296110fb1273a4d848a0bfb2ff65f3ee92127b3244e16b/pydantic_core-2.41.5-pp311-pypy311_pp73-musllinux_1_1_x86_64.whl", hash = "sha256:f14f8f046c14563f8eb3f45f499cc658ab8d10072961e07225e507adb700e93f", size = 2316992, upload-time = "2025-11-04T13:43:43.602Z" },
    { url = "https://files.pythonhosted.org/packages/36/c7/cfc8e811f061c841d7990b0201912c3556bfeb99cdcb7ed24adc8d6f8704/pydantic_core-2.41.5-pp311-pypy311_pp73-win_amd64.whl", hash = "sha256:56121965f7a4dc965bff783d70b907ddf3d57f6eba29b6d2e5dabfaf07799c51", size = 2145302, upload-time = "2025-11-04T13:43:46.64Z" },
]

[[package]]
name = "pygments"
version = "2.19.2"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/b0/77/a5b8c569bf593b0140bde72ea885a803b82086995367bf2037de0159d924/pygments-2.19.2.tar.gz", hash = "sha256:636cb2477cec7f8952536970bc533bc43743542f70392ae026374600add5b887", size = 4968631, upload-time = "2025-06-21T13:39:12.283Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/c7/21/705964c7812476f378728bdf590ca4b771ec72385c533964653c68e86bdc/pygments-2.19.2-py3-none-any.whl", hash = "sha256:86540386c03d588bb81d44bc3928634ff26449851e99741617ecb9037ee5ec0b", size = 1225217, upload-time = "2025-06-21T13:39:07.939Z" },
]

[[package]]
name = "pypdf"
version = "6.8.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/b4/a3/e705b0805212b663a4c27b861c8a603dba0f8b4bb281f96f8e746576a50d/pypdf-6.8.0.tar.gz", hash = "sha256:cb7eaeaa4133ce76f762184069a854e03f4d9a08568f0e0623f7ea810407833b", size = 5307831, upload-time = "2026-03-09T13:37:40.591Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/8c/ec/4ccf3bb86b1afe5d7176e1c8abcdbf22b53dd682ec2eda50e1caadcf6846/pypdf-6.8.0-py3-none-any.whl", hash = "sha256:2a025080a8dd73f48123c89c57174a5ff3806c71763ee4e49572dc90454943c7", size = 332177, upload-time = "2026-03-09T13:37:38.774Z" },
]

[[package]]
name = "pytest"
version = "9.0.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
    { name = "iniconfig" },
    { name = "packaging" },
    { name = "pluggy" },
    { name = "pygments" },
]
sdist = { url = "https://files.pythonhosted.org/packages/d1/db/7ef3487e0fb0049ddb5ce41d3a49c235bf9ad299b6a25d5780a89f19230f/pytest-9.0.2.tar.gz", hash = "sha256:75186651a92bd89611d1d9fc20f0b4345fd827c41ccd5c299a868a05d70edf11", size = 1568901, upload-time = "2025-12-06T21:30:51.014Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/3b/ab/b3226f0bd7cdcf710fbede2b3548584366da3b19b5021e74f5bde2a8fa3f/pytest-9.0.2-py3-none-any.whl", hash = "sha256:711ffd45bf766d5264d487b917733b453d917afd2b0ad65223959f59089f875b", size = 374801, upload-time = "2025-12-06T21:30:49.154Z" },
]

[[package]]
name = "python-docx"
version = "1.2.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "lxml" },
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/a9/f7/eddfe33871520adab45aaa1a71f0402a2252050c14c7e3009446c8f4701c/python_docx-1.2.0.tar.gz", hash = "sha256:7bc9d7b7d8a69c9c02ca09216118c86552704edc23bac179283f2e38f86220ce", size = 5723256, upload-time = "2025-06-16T20:46:27.921Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d0/00/1e03a4989fa5795da308cd774f05b704ace555a70f9bf9d3be057b680bcf/python_docx-1.2.0-py3-none-any.whl", hash = "sha256:3fd478f3250fbbbfd3b94fe1e985955737c145627498896a8a6bf81f4baf66c7", size = 252987, upload-time = "2025-06-16T20:46:22.506Z" },
]

[[package]]
name = "python-multipart"
version = "0.0.22"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/94/01/979e98d542a70714b0cb2b6728ed0b7c46792b695e3eaec3e20711271ca3/python_multipart-0.0.22.tar.gz", hash = "sha256:7340bef99a7e0032613f56dc36027b959fd3b30a787ed62d310e951f7c3a3a58", size = 37612, upload-time = "2026-01-25T10:15:56.219Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/1b/d0/397f9626e711ff749a95d96b7af99b9c566a9bb5129b8e4c10fc4d100304/python_multipart-0.0.22-py3-none-any.whl", hash = "sha256:2b2cd894c83d21bf49d702499531c7bafd057d730c201782048f7945d82de155", size = 24579, upload-time = "2026-01-25T10:15:54.811Z" },
]

[[package]]
name = "pywin32"
version = "311"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/7c/af/449a6a91e5d6db51420875c54f6aff7c97a86a3b13a0b4f1a5c13b988de3/pywin32-311-cp311-cp311-win32.whl", hash = "sha256:184eb5e436dea364dcd3d2316d577d625c0351bf237c4e9a5fabbcfa5a58b151", size = 8697031, upload-time = "2025-07-14T20:13:13.266Z" },
    { url = "https://files.pythonhosted.org/packages/51/8f/9bb81dd5bb77d22243d33c8397f09377056d5c687aa6d4042bea7fbf8364/pywin32-311-cp311-cp311-win_amd64.whl", hash = "sha256:3ce80b34b22b17ccbd937a6e78e7225d80c52f5ab9940fe0506a1a16f3dab503", size = 9508308, upload-time = "2025-07-14T20:13:15.147Z" },
    { url = "https://files.pythonhosted.org/packages/44/7b/9c2ab54f74a138c491aba1b1cd0795ba61f144c711daea84a88b63dc0f6c/pywin32-311-cp311-cp311-win_arm64.whl", hash = "sha256:a733f1388e1a842abb67ffa8e7aad0e70ac519e09b0f6a784e65a136ec7cefd2", size = 8703930, upload-time = "2025-07-14T20:13:16.945Z" },
    { url = "https://files.pythonhosted.org/packages/e7/ab/01ea1943d4eba0f850c3c61e78e8dd59757ff815ff3ccd0a84de5f541f42/pywin32-311-cp312-cp312-win32.whl", hash = "sha256:750ec6e621af2b948540032557b10a2d43b0cee2ae9758c54154d711cc852d31", size = 8706543, upload-time = "2025-07-14T20:13:20.765Z" },
    { url = "https://files.pythonhosted.org/packages/d1/a8/a0e8d07d4d051ec7502cd58b291ec98dcc0c3fff027caad0470b72cfcc2f/pywin32-311-cp312-cp312-win_amd64.whl", hash = "sha256:b8c095edad5c211ff31c05223658e71bf7116daa0ecf3ad85f3201ea3190d067", size = 9495040, upload-time = "2025-07-14T20:13:22.543Z" },
    { url = "https://files.pythonhosted.org/packages/ba/3a/2ae996277b4b50f17d61f0603efd8253cb2d79cc7ae159468007b586396d/pywin32-311-cp312-cp312-win_arm64.whl", hash = "sha256:e286f46a9a39c4a18b319c28f59b61de793654af2f395c102b4f819e584b5852", size = 8710102, upload-time = "2025-07-14T20:13:24.682Z" },
    { url = "https://files.pythonhosted.org/packages/a5/be/3fd5de0979fcb3994bfee0d65ed8ca9506a8a1260651b86174f6a86f52b3/pywin32-311-cp313-cp313-win32.whl", hash = "sha256:f95ba5a847cba10dd8c4d8fefa9f2a6cf283b8b88ed6178fa8a6c1ab16054d0d", size = 8705700, upload-time = "2025-07-14T20:13:26.471Z" },
    { url = "https://files.pythonhosted.org/packages/e3/28/e0a1909523c6890208295a29e05c2adb2126364e289826c0a8bc7297bd5c/pywin32-311-cp313-cp313-win_amd64.whl", hash = "sha256:718a38f7e5b058e76aee1c56ddd06908116d35147e133427e59a3983f703a20d", size = 9494700, upload-time = "2025-07-14T20:13:28.243Z" },
    { url = "https://files.pythonhosted.org/packages/04/bf/90339ac0f55726dce7d794e6d79a18a91265bdf3aa70b6b9ca52f35e022a/pywin32-311-cp313-cp313-win_arm64.whl", hash = "sha256:7b4075d959648406202d92a2310cb990fea19b535c7f4a78d3f5e10b926eeb8a", size = 8709318, upload-time = "2025-07-14T20:13:30.348Z" },
    { url = "https://files.pythonhosted.org/packages/c9/31/097f2e132c4f16d99a22bfb777e0fd88bd8e1c634304e102f313af69ace5/pywin32-311-cp314-cp314-win32.whl", hash = "sha256:b7a2c10b93f8986666d0c803ee19b5990885872a7de910fc460f9b0c2fbf92ee", size = 8840714, upload-time = "2025-07-14T20:13:32.449Z" },
    { url = "https://files.pythonhosted.org/packages/90/4b/07c77d8ba0e01349358082713400435347df8426208171ce297da32c313d/pywin32-311-cp314-cp314-win_amd64.whl", hash = "sha256:3aca44c046bd2ed8c90de9cb8427f581c479e594e99b5c0bb19b29c10fd6cb87", size = 9656800, upload-time = "2025-07-14T20:13:34.312Z" },
    { url = "https://files.pythonhosted.org/packages/c0/d2/21af5c535501a7233e734b8af901574572da66fcc254cb35d0609c9080dd/pywin32-311-cp314-cp314-win_arm64.whl", hash = "sha256:a508e2d9025764a8270f93111a970e1d0fbfc33f4153b388bb649b7eec4f9b42", size = 8932540, upload-time = "2025-07-14T20:13:36.379Z" },
]

[[package]]
name = "pyyaml"
version = "6.0.3"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/05/8e/961c0007c59b8dd7729d542c61a4d537767a59645b82a0b521206e1e25c2/pyyaml-6.0.3.tar.gz", hash = "sha256:d76623373421df22fb4cf8817020cbb7ef15c725b9d5e45f17e189bfc384190f", size = 130960, upload-time = "2025-09-25T21:33:16.546Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/6d/16/a95b6757765b7b031c9374925bb718d55e0a9ba8a1b6a12d25962ea44347/pyyaml-6.0.3-cp311-cp311-macosx_10_13_x86_64.whl", hash = "sha256:44edc647873928551a01e7a563d7452ccdebee747728c1080d881d68af7b997e", size = 185826, upload-time = "2025-09-25T21:31:58.655Z" },
    { url = "https://files.pythonhosted.org/packages/16/19/13de8e4377ed53079ee996e1ab0a9c33ec2faf808a4647b7b4c0d46dd239/pyyaml-6.0.3-cp311-cp311-macosx_11_0_arm64.whl", hash = "sha256:652cb6edd41e718550aad172851962662ff2681490a8a711af6a4d288dd96824", size = 175577, upload-time = "2025-09-25T21:32:00.088Z" },
    { url = "https://files.pythonhosted.org/packages/0c/62/d2eb46264d4b157dae1275b573017abec435397aa59cbcdab6fc978a8af4/pyyaml-6.0.3-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:10892704fc220243f5305762e276552a0395f7beb4dbf9b14ec8fd43b57f126c", size = 775556, upload-time = "2025-09-25T21:32:01.31Z" },
    { url = "https://files.pythonhosted.org/packages/10/cb/16c3f2cf3266edd25aaa00d6c4350381c8b012ed6f5276675b9eba8d9ff4/pyyaml-6.0.3-cp311-cp311-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:850774a7879607d3a6f50d36d04f00ee69e7fc816450e5f7e58d7f17f1ae5c00", size = 882114, upload-time = "2025-09-25T21:32:03.376Z" },
    { url = "https://files.pythonhosted.org/packages/71/60/917329f640924b18ff085ab889a11c763e0b573da888e8404ff486657602/pyyaml-6.0.3-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:b8bb0864c5a28024fac8a632c443c87c5aa6f215c0b126c449ae1a150412f31d", size = 806638, upload-time = "2025-09-25T21:32:04.553Z" },
    { url = "https://files.pythonhosted.org/packages/dd/6f/529b0f316a9fd167281a6c3826b5583e6192dba792dd55e3203d3f8e655a/pyyaml-6.0.3-cp311-cp311-musllinux_1_2_aarch64.whl", hash = "sha256:1d37d57ad971609cf3c53ba6a7e365e40660e3be0e5175fa9f2365a379d6095a", size = 767463, upload-time = "2025-09-25T21:32:06.152Z" },
    { url = "https://files.pythonhosted.org/packages/f2/6a/b627b4e0c1dd03718543519ffb2f1deea4a1e6d42fbab8021936a4d22589/pyyaml-6.0.3-cp311-cp311-musllinux_1_2_x86_64.whl", hash = "sha256:37503bfbfc9d2c40b344d06b2199cf0e96e97957ab1c1b546fd4f87e53e5d3e4", size = 794986, upload-time = "2025-09-25T21:32:07.367Z" },
    { url = "https://files.pythonhosted.org/packages/45/91/47a6e1c42d9ee337c4839208f30d9f09caa9f720ec7582917b264defc875/pyyaml-6.0.3-cp311-cp311-win32.whl", hash = "sha256:8098f252adfa6c80ab48096053f512f2321f0b998f98150cea9bd23d83e1467b", size = 142543, upload-time = "2025-09-25T21:32:08.95Z" },
    { url = "https://files.pythonhosted.org/packages/da/e3/ea007450a105ae919a72393cb06f122f288ef60bba2dc64b26e2646fa315/pyyaml-6.0.3-cp311-cp311-win_amd64.whl", hash = "sha256:9f3bfb4965eb874431221a3ff3fdcddc7e74e3b07799e0e84ca4a0f867d449bf", size = 158763, upload-time = "2025-09-25T21:32:09.96Z" },
    { url = "https://files.pythonhosted.org/packages/d1/33/422b98d2195232ca1826284a76852ad5a86fe23e31b009c9886b2d0fb8b2/pyyaml-6.0.3-cp312-cp312-macosx_10_13_x86_64.whl", hash = "sha256:7f047e29dcae44602496db43be01ad42fc6f1cc0d8cd6c83d342306c32270196", size = 182063, upload-time = "2025-09-25T21:32:11.445Z" },
    { url = "https://files.pythonhosted.org/packages/89/a0/6cf41a19a1f2f3feab0e9c0b74134aa2ce6849093d5517a0c550fe37a648/pyyaml-6.0.3-cp312-cp312-macosx_11_0_arm64.whl", hash = "sha256:fc09d0aa354569bc501d4e787133afc08552722d3ab34836a80547331bb5d4a0", size = 173973, upload-time = "2025-09-25T21:32:12.492Z" },
    { url = "https://files.pythonhosted.org/packages/ed/23/7a778b6bd0b9a8039df8b1b1d80e2e2ad78aa04171592c8a5c43a56a6af4/pyyaml-6.0.3-cp312-cp312-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:9149cad251584d5fb4981be1ecde53a1ca46c891a79788c0df828d2f166bda28", size = 775116, upload-time = "2025-09-25T21:32:13.652Z" },
    { url = "https://files.pythonhosted.org/packages/65/30/d7353c338e12baef4ecc1b09e877c1970bd3382789c159b4f89d6a70dc09/pyyaml-6.0.3-cp312-cp312-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:5fdec68f91a0c6739b380c83b951e2c72ac0197ace422360e6d5a959d8d97b2c", size = 844011, upload-time = "2025-09-25T21:32:15.21Z" },
    { url = "https://files.pythonhosted.org/packages/8b/9d/b3589d3877982d4f2329302ef98a8026e7f4443c765c46cfecc8858c6b4b/pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc", size = 807870, upload-time = "2025-09-25T21:32:16.431Z" },
    { url = "https://files.pythonhosted.org/packages/05/c0/b3be26a015601b822b97d9149ff8cb5ead58c66f981e04fedf4e762f4bd4/pyyaml-6.0.3-cp312-cp312-musllinux_1_2_aarch64.whl", hash = "sha256:8dc52c23056b9ddd46818a57b78404882310fb473d63f17b07d5c40421e47f8e", size = 761089, upload-time = "2025-09-25T21:32:17.56Z" },
    { url = "https://files.pythonhosted.org/packages/be/8e/98435a21d1d4b46590d5459a22d88128103f8da4c2d4cb8f14f2a96504e1/pyyaml-6.0.3-cp312-cp312-musllinux_1_2_x86_64.whl", hash = "sha256:41715c910c881bc081f1e8872880d3c650acf13dfa8214bad49ed4cede7c34ea", size = 790181, upload-time = "2025-09-25T21:32:18.834Z" },
    { url = "https://files.pythonhosted.org/packages/74/93/7baea19427dcfbe1e5a372d81473250b379f04b1bd3c4c5ff825e2327202/pyyaml-6.0.3-cp312-cp312-win32.whl", hash = "sha256:96b533f0e99f6579b3d4d4995707cf36df9100d67e0c8303a0c55b27b5f99bc5", size = 137658, upload-time = "2025-09-25T21:32:20.209Z" },
    { url = "https://files.pythonhosted.org/packages/86/bf/899e81e4cce32febab4fb42bb97dcdf66bc135272882d1987881a4b519e9/pyyaml-6.0.3-cp312-cp312-win_amd64.whl", hash = "sha256:5fcd34e47f6e0b794d17de1b4ff496c00986e1c83f7ab2fb8fcfe9616ff7477b", size = 154003, upload-time = "2025-09-25T21:32:21.167Z" },
    { url = "https://files.pythonhosted.org/packages/1a/08/67bd04656199bbb51dbed1439b7f27601dfb576fb864099c7ef0c3e55531/pyyaml-6.0.3-cp312-cp312-win_arm64.whl", hash = "sha256:64386e5e707d03a7e172c0701abfb7e10f0fb753ee1d773128192742712a98fd", size = 140344, upload-time = "2025-09-25T21:32:22.617Z" },
    { url = "https://files.pythonhosted.org/packages/d1/11/0fd08f8192109f7169db964b5707a2f1e8b745d4e239b784a5a1dd80d1db/pyyaml-6.0.3-cp313-cp313-macosx_10_13_x86_64.whl", hash = "sha256:8da9669d359f02c0b91ccc01cac4a67f16afec0dac22c2ad09f46bee0697eba8", size = 181669, upload-time = "2025-09-25T21:32:23.673Z" },
    { url = "https://files.pythonhosted.org/packages/b1/16/95309993f1d3748cd644e02e38b75d50cbc0d9561d21f390a76242ce073f/pyyaml-6.0.3-cp313-cp313-macosx_11_0_arm64.whl", hash = "sha256:2283a07e2c21a2aa78d9c4442724ec1eb15f5e42a723b99cb3d822d48f5f7ad1", size = 173252, upload-time = "2025-09-25T21:32:25.149Z" },
    { url = "https://files.pythonhosted.org/packages/50/31/b20f376d3f810b9b2371e72ef5adb33879b25edb7a6d072cb7ca0c486398/pyyaml-6.0.3-cp313-cp313-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:ee2922902c45ae8ccada2c5b501ab86c36525b883eff4255313a253a3160861c", size = 767081, upload-time = "2025-09-25T21:32:26.575Z" },
    { url = "https://files.pythonhosted.org/packages/49/1e/a55ca81e949270d5d4432fbbd19dfea5321eda7c41a849d443dc92fd1ff7/pyyaml-6.0.3-cp313-cp313-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:a33284e20b78bd4a18c8c2282d549d10bc8408a2a7ff57653c0cf0b9be0afce5", size = 841159, upload-time = "2025-09-25T21:32:27.727Z" },
    { url = "https://files.pythonhosted.org/packages/74/27/e5b8f34d02d9995b80abcef563ea1f8b56d20134d8f4e5e81733b1feceb2/pyyaml-6.0.3-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:0f29edc409a6392443abf94b9cf89ce99889a1dd5376d94316ae5145dfedd5d6", size = 801626, upload-time = "2025-09-25T21:32:28.878Z" },
    { url = "https://files.pythonhosted.org/packages/f9/11/ba845c23988798f40e52ba45f34849aa8a1f2d4af4b798588010792ebad6/pyyaml-6.0.3-cp313-cp313-musllinux_1_2_aarch64.whl", hash = "sha256:f7057c9a337546edc7973c0d3ba84ddcdf0daa14533c2065749c9075001090e6", size = 753613, upload-time = "2025-09-25T21:32:30.178Z" },
    { url = "https://files.pythonhosted.org/packages/3d/e0/7966e1a7bfc0a45bf0a7fb6b98ea03fc9b8d84fa7f2229e9659680b69ee3/pyyaml-6.0.3-cp313-cp313-musllinux_1_2_x86_64.whl", hash = "sha256:eda16858a3cab07b80edaf74336ece1f986ba330fdb8ee0d6c0d68fe82bc96be", size = 794115, upload-time = "2025-09-25T21:32:31.353Z" },
    { url = "https://files.pythonhosted.org/packages/de/94/980b50a6531b3019e45ddeada0626d45fa85cbe22300844a7983285bed3b/pyyaml-6.0.3-cp313-cp313-win32.whl", hash = "sha256:d0eae10f8159e8fdad514efdc92d74fd8d682c933a6dd088030f3834bc8e6b26", size = 137427, upload-time = "2025-09-25T21:32:32.58Z" },
    { url = "https://files.pythonhosted.org/packages/97/c9/39d5b874e8b28845e4ec2202b5da735d0199dbe5b8fb85f91398814a9a46/pyyaml-6.0.3-cp313-cp313-win_amd64.whl", hash = "sha256:79005a0d97d5ddabfeeea4cf676af11e647e41d81c9a7722a193022accdb6b7c", size = 154090, upload-time = "2025-09-25T21:32:33.659Z" },
    { url = "https://files.pythonhosted.org/packages/73/e8/2bdf3ca2090f68bb3d75b44da7bbc71843b19c9f2b9cb9b0f4ab7a5a4329/pyyaml-6.0.3-cp313-cp313-win_arm64.whl", hash = "sha256:5498cd1645aa724a7c71c8f378eb29ebe23da2fc0d7a08071d89469bf1d2defb", size = 140246, upload-time = "2025-09-25T21:32:34.663Z" },
    { url = "https://files.pythonhosted.org/packages/9d/8c/f4bd7f6465179953d3ac9bc44ac1a8a3e6122cf8ada906b4f96c60172d43/pyyaml-6.0.3-cp314-cp314-macosx_10_13_x86_64.whl", hash = "sha256:8d1fab6bb153a416f9aeb4b8763bc0f22a5586065f86f7664fc23339fc1c1fac", size = 181814, upload-time = "2025-09-25T21:32:35.712Z" },
    { url = "https://files.pythonhosted.org/packages/bd/9c/4d95bb87eb2063d20db7b60faa3840c1b18025517ae857371c4dd55a6b3a/pyyaml-6.0.3-cp314-cp314-macosx_11_0_arm64.whl", hash = "sha256:34d5fcd24b8445fadc33f9cf348c1047101756fd760b4dacb5c3e99755703310", size = 173809, upload-time = "2025-09-25T21:32:36.789Z" },
    { url = "https://files.pythonhosted.org/packages/92/b5/47e807c2623074914e29dabd16cbbdd4bf5e9b2db9f8090fa64411fc5382/pyyaml-6.0.3-cp314-cp314-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:501a031947e3a9025ed4405a168e6ef5ae3126c59f90ce0cd6f2bfc477be31b7", size = 766454, upload-time = "2025-09-25T21:32:37.966Z" },
    { url = "https://files.pythonhosted.org/packages/02/9e/e5e9b168be58564121efb3de6859c452fccde0ab093d8438905899a3a483/pyyaml-6.0.3-cp314-cp314-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:b3bc83488de33889877a0f2543ade9f70c67d66d9ebb4ac959502e12de895788", size = 836355, upload-time = "2025-09-25T21:32:39.178Z" },
    { url = "https://files.pythonhosted.org/packages/88/f9/16491d7ed2a919954993e48aa941b200f38040928474c9e85ea9e64222c3/pyyaml-6.0.3-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:c458b6d084f9b935061bc36216e8a69a7e293a2f1e68bf956dcd9e6cbcd143f5", size = 794175, upload-time = "2025-09-25T21:32:40.865Z" },
    { url = "https://files.pythonhosted.org/packages/dd/3f/5989debef34dc6397317802b527dbbafb2b4760878a53d4166579111411e/pyyaml-6.0.3-cp314-cp314-musllinux_1_2_aarch64.whl", hash = "sha256:7c6610def4f163542a622a73fb39f534f8c101d690126992300bf3207eab9764", size = 755228, upload-time = "2025-09-25T21:32:42.084Z" },
    { url = "https://files.pythonhosted.org/packages/d7/ce/af88a49043cd2e265be63d083fc75b27b6ed062f5f9fd6cdc223ad62f03e/pyyaml-6.0.3-cp314-cp314-musllinux_1_2_x86_64.whl", hash = "sha256:5190d403f121660ce8d1d2c1bb2ef1bd05b5f68533fc5c2ea899bd15f4399b35", size = 789194, upload-time = "2025-09-25T21:32:43.362Z" },
    { url = "https://files.pythonhosted.org/packages/23/20/bb6982b26a40bb43951265ba29d4c246ef0ff59c9fdcdf0ed04e0687de4d/pyyaml-6.0.3-cp314-cp314-win_amd64.whl", hash = "sha256:4a2e8cebe2ff6ab7d1050ecd59c25d4c8bd7e6f400f5f82b96557ac0abafd0ac", size = 156429, upload-time = "2025-09-25T21:32:57.844Z" },
    { url = "https://files.pythonhosted.org/packages/f4/f4/a4541072bb9422c8a883ab55255f918fa378ecf083f5b85e87fc2b4eda1b/pyyaml-6.0.3-cp314-cp314-win_arm64.whl", hash = "sha256:93dda82c9c22deb0a405ea4dc5f2d0cda384168e466364dec6255b293923b2f3", size = 143912, upload-time = "2025-09-25T21:32:59.247Z" },
    { url = "https://files.pythonhosted.org/packages/7c/f9/07dd09ae774e4616edf6cda684ee78f97777bdd15847253637a6f052a62f/pyyaml-6.0.3-cp314-cp314t-macosx_10_13_x86_64.whl", hash = "sha256:02893d100e99e03eda1c8fd5c441d8c60103fd175728e23e431db1b589cf5ab3", size = 189108, upload-time = "2025-09-25T21:32:44.377Z" },
    { url = "https://files.pythonhosted.org/packages/4e/78/8d08c9fb7ce09ad8c38ad533c1191cf27f7ae1effe5bb9400a46d9437fcf/pyyaml-6.0.3-cp314-cp314t-macosx_11_0_arm64.whl", hash = "sha256:c1ff362665ae507275af2853520967820d9124984e0f7466736aea23d8611fba", size = 183641, upload-time = "2025-09-25T21:32:45.407Z" },
    { url = "https://files.pythonhosted.org/packages/7b/5b/3babb19104a46945cf816d047db2788bcaf8c94527a805610b0289a01c6b/pyyaml-6.0.3-cp314-cp314t-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl", hash = "sha256:6adc77889b628398debc7b65c073bcb99c4a0237b248cacaf3fe8a557563ef6c", size = 831901, upload-time = "2025-09-25T21:32:48.83Z" },
    { url = "https://files.pythonhosted.org/packages/8b/cc/dff0684d8dc44da4d22a13f35f073d558c268780ce3c6ba1b87055bb0b87/pyyaml-6.0.3-cp314-cp314t-manylinux2014_s390x.manylinux_2_17_s390x.manylinux_2_28_s390x.whl", hash = "sha256:a80cb027f6b349846a3bf6d73b5e95e782175e52f22108cfa17876aaeff93702", size = 861132, upload-time = "2025-09-25T21:32:50.149Z" },
    { url = "https://files.pythonhosted.org/packages/b1/5e/f77dc6b9036943e285ba76b49e118d9ea929885becb0a29ba8a7c75e29fe/pyyaml-6.0.3-cp314-cp314t-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl", hash = "sha256:00c4bdeba853cc34e7dd471f16b4114f4162dc03e6b7afcc2128711f0eca823c", size = 839261, upload-time = "2025-09-25T21:32:51.808Z" },
    { url = "https://files.pythonhosted.org/packages/ce/88/a9db1376aa2a228197c58b37302f284b5617f56a5d959fd1763fb1675ce6/pyyaml-6.0.3-cp314-cp314t-musllinux_1_2_aarch64.whl", hash = "sha256:66e1674c3ef6f541c35191caae2d429b967b99e02040f5ba928632d9a7f0f065", size = 805272, upload-time = "2025-09-25T21:32:52.941Z" },
    { url = "https://files.pythonhosted.org/packages/da/92/1446574745d74df0c92e6aa4a7b0b3130706a4142b2d1a5869f2eaa423c6/pyyaml-6.0.3-cp314-cp314t-musllinux_1_2_x86_64.whl", hash = "sha256:16249ee61e95f858e83976573de0f5b2893b3677ba71c9dd36b9cf8be9ac6d65", size = 829923, upload-time = "2025-09-25T21:32:54.537Z" },
    { url = "https://files.pythonhosted.org/packages/f0/7a/1c7270340330e575b92f397352af856a8c06f230aa3e76f86b39d01b416a/pyyaml-6.0.3-cp314-cp314t-win_amd64.whl", hash = "sha256:4ad1906908f2f5ae4e5a8ddfce73c320c2a1429ec52eafd27138b7f1cbe341c9", size = 174062, upload-time = "2025-09-25T21:32:55.767Z" },
    { url = "https://files.pythonhosted.org/packages/f1/12/de94a39c2ef588c7e6455cfbe7343d3b2dc9d6b6b2f40c4c6565744c873d/pyyaml-6.0.3-cp314-cp314t-win_arm64.whl", hash = "sha256:ebc55a14a21cb14062aa4162f906cd962b28e2e9ea38f9b4391244cd8de4ae0b", size = 149341, upload-time = "2025-09-25T21:32:56.828Z" },
]

[[package]]
name = "qdrant-client"
version = "1.17.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "grpcio" },
    { name = "httpx", extra = ["http2"] },
    { name = "numpy" },
    { name = "portalocker" },
    { name = "protobuf" },
    { name = "pydantic" },
    { name = "urllib3" },
]
sdist = { url = "https://files.pythonhosted.org/packages/20/fb/c9c4cecf6e7fdff2dbaeee0de40e93fe495379eb5fe2775b184ea45315da/qdrant_client-1.17.0.tar.gz", hash = "sha256:47eb033edb9be33a4babb4d87b0d8d5eaf03d52112dca0218db7f2030bf41ba9", size = 344839, upload-time = "2026-02-19T16:03:17.069Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/c1/15/dfadbc9d8c9872e8ac45fa96f5099bb2855f23426bfea1bbcdc85e64ef6e/qdrant_client-1.17.0-py3-none-any.whl", hash = "sha256:f5b452c68c42b3580d3d266446fb00d3c6e3aae89c916e16585b3c704e108438", size = 390381, upload-time = "2026-02-19T16:03:15.486Z" },
]

[[package]]
name = "requests"
version = "2.32.5"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "certifi" },
    { name = "charset-normalizer" },
    { name = "idna" },
    { name = "urllib3" },
]
sdist = { url = "https://files.pythonhosted.org/packages/c9/74/b3ff8e6c8446842c3f5c837e9c3dfcfe2018ea6ecef224c710c85ef728f4/requests-2.32.5.tar.gz", hash = "sha256:dbba0bac56e100853db0ea71b82b4dfd5fe2bf6d3754a8893c3af500cec7d7cf", size = 134517, upload-time = "2025-08-18T20:46:02.573Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/1e/db/4254e3eabe8020b458f1a747140d32277ec7a271daf1d235b70dc0b4e6e3/requests-2.32.5-py3-none-any.whl", hash = "sha256:2462f94637a34fd532264295e186976db0f5d453d1cdd31473c85a6a161affb6", size = 64738, upload-time = "2025-08-18T20:46:00.542Z" },
]

[[package]]
name = "rich"
version = "14.3.3"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "markdown-it-py" },
    { name = "pygments" },
]
sdist = { url = "https://files.pythonhosted.org/packages/b3/c6/f3b320c27991c46f43ee9d856302c70dc2d0fb2dba4842ff739d5f46b393/rich-14.3.3.tar.gz", hash = "sha256:b8daa0b9e4eef54dd8cf7c86c03713f53241884e814f4e2f5fb342fe520f639b", size = 230582, upload-time = "2026-02-19T17:23:12.474Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/14/25/b208c5683343959b670dc001595f2f3737e051da617f66c31f7c4fa93abc/rich-14.3.3-py3-none-any.whl", hash = "sha256:793431c1f8619afa7d3b52b2cdec859562b950ea0d4b6b505397612db8d5362d", size = 310458, upload-time = "2026-02-19T17:23:13.732Z" },
]

[[package]]
name = "shellingham"
version = "1.5.4"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/58/15/8b3609fd3830ef7b27b655beb4b4e9c62313a4e8da8c676e142cc210d58e/shellingham-1.5.4.tar.gz", hash = "sha256:8dbca0739d487e5bd35ab3ca4b36e11c4078f3a234bfce294b0a0291363404de", size = 10310, upload-time = "2023-10-24T04:13:40.426Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e0/f9/0595336914c5619e5f28a1fb793285925a8cd4b432c9da0a987836c7f822/shellingham-1.5.4-py2.py3-none-any.whl", hash = "sha256:7ecfff8f2fd72616f7481040475a65b2bf8af90a56c89140852d1120324e8686", size = 9755, upload-time = "2023-10-24T04:13:38.866Z" },
]

[[package]]
name = "starlette"
version = "0.52.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "anyio" },
    { name = "typing-extensions", marker = "python_full_version < '3.13'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/c4/68/79977123bb7be889ad680d79a40f339082c1978b5cfcf62c2d8d196873ac/starlette-0.52.1.tar.gz", hash = "sha256:834edd1b0a23167694292e94f597773bc3f89f362be6effee198165a35d62933", size = 2653702, upload-time = "2026-01-18T13:34:11.062Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/81/0d/13d1d239a25cbfb19e740db83143e95c772a1fe10202dda4b76792b114dd/starlette-0.52.1-py3-none-any.whl", hash = "sha256:0029d43eb3d273bc4f83a08720b4912ea4b071087a3b48db01b7c839f7954d74", size = 74272, upload-time = "2026-01-18T13:34:09.188Z" },
]

[[package]]
name = "sympy"
version = "1.14.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "mpmath" },
]
sdist = { url = "https://files.pythonhosted.org/packages/83/d3/803453b36afefb7c2bb238361cd4ae6125a569b4db67cd9e79846ba2d68c/sympy-1.14.0.tar.gz", hash = "sha256:d3d3fe8df1e5a0b42f0e7bdf50541697dbe7d23746e894990c030e2b05e72517", size = 7793921, upload-time = "2025-04-27T18:05:01.611Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/a2/09/77d55d46fd61b4a135c444fc97158ef34a095e5681d0a6c10b75bf356191/sympy-1.14.0-py3-none-any.whl", hash = "sha256:e091cc3e99d2141a0ba2847328f5479b05d94a6635cb96148ccb3f34671bd8f5", size = 6299353, upload-time = "2025-04-27T18:04:59.103Z" },
]

[[package]]
name = "tokenizers"
version = "0.22.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "huggingface-hub" },
]
sdist = { url = "https://files.pythonhosted.org/packages/73/6f/f80cfef4a312e1fb34baf7d85c72d4411afde10978d4657f8cdd811d3ccc/tokenizers-0.22.2.tar.gz", hash = "sha256:473b83b915e547aa366d1eee11806deaf419e17be16310ac0a14077f1e28f917", size = 372115, upload-time = "2026-01-05T10:45:15.988Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/92/97/5dbfabf04c7e348e655e907ed27913e03db0923abb5dfdd120d7b25630e1/tokenizers-0.22.2-cp39-abi3-macosx_10_12_x86_64.whl", hash = "sha256:544dd704ae7238755d790de45ba8da072e9af3eea688f698b137915ae959281c", size = 3100275, upload-time = "2026-01-05T10:41:02.158Z" },
    { url = "https://files.pythonhosted.org/packages/2e/47/174dca0502ef88b28f1c9e06b73ce33500eedfac7a7692108aec220464e7/tokenizers-0.22.2-cp39-abi3-macosx_11_0_arm64.whl", hash = "sha256:1e418a55456beedca4621dbab65a318981467a2b188e982a23e117f115ce5001", size = 2981472, upload-time = "2026-01-05T10:41:00.276Z" },
    { url = "https://files.pythonhosted.org/packages/d6/84/7990e799f1309a8b87af6b948f31edaa12a3ed22d11b352eaf4f4b2e5753/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64.whl", hash = "sha256:2249487018adec45d6e3554c71d46eb39fa8ea67156c640f7513eb26f318cec7", size = 3290736, upload-time = "2026-01-05T10:40:32.165Z" },
    { url = "https://files.pythonhosted.org/packages/78/59/09d0d9ba94dcd5f4f1368d4858d24546b4bdc0231c2354aa31d6199f0399/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_armv7l.manylinux2014_armv7l.whl", hash = "sha256:25b85325d0815e86e0bac263506dd114578953b7b53d7de09a6485e4a160a7dd", size = 3168835, upload-time = "2026-01-05T10:40:38.847Z" },
    { url = "https://files.pythonhosted.org/packages/47/50/b3ebb4243e7160bda8d34b731e54dd8ab8b133e50775872e7a434e524c28/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_i686.manylinux2014_i686.whl", hash = "sha256:bfb88f22a209ff7b40a576d5324bf8286b519d7358663db21d6246fb17eea2d5", size = 3521673, upload-time = "2026-01-05T10:40:56.614Z" },
    { url = "https://files.pythonhosted.org/packages/e0/fa/89f4cb9e08df770b57adb96f8cbb7e22695a4cb6c2bd5f0c4f0ebcf33b66/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_ppc64le.manylinux2014_ppc64le.whl", hash = "sha256:1c774b1276f71e1ef716e5486f21e76333464f47bece56bbd554485982a9e03e", size = 3724818, upload-time = "2026-01-05T10:40:44.507Z" },
    { url = "https://files.pythonhosted.org/packages/64/04/ca2363f0bfbe3b3d36e95bf67e56a4c88c8e3362b658e616d1ac185d47f2/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_s390x.manylinux2014_s390x.whl", hash = "sha256:df6c4265b289083bf710dff49bc51ef252f9d5be33a45ee2bed151114a56207b", size = 3379195, upload-time = "2026-01-05T10:40:51.139Z" },
    { url = "https://files.pythonhosted.org/packages/2e/76/932be4b50ef6ccedf9d3c6639b056a967a86258c6d9200643f01269211ca/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", hash = "sha256:369cc9fc8cc10cb24143873a0d95438bb8ee257bb80c71989e3ee290e8d72c67", size = 3274982, upload-time = "2026-01-05T10:40:58.331Z" },
    { url = "https://files.pythonhosted.org/packages/1d/28/5f9f5a4cc211b69e89420980e483831bcc29dade307955cc9dc858a40f01/tokenizers-0.22.2-cp39-abi3-musllinux_1_2_aarch64.whl", hash = "sha256:29c30b83d8dcd061078b05ae0cb94d3c710555fbb44861139f9f83dcca3dc3e4", size = 9478245, upload-time = "2026-01-05T10:41:04.053Z" },
    { url = "https://files.pythonhosted.org/packages/6c/fb/66e2da4704d6aadebf8cb39f1d6d1957df667ab24cff2326b77cda0dcb85/tokenizers-0.22.2-cp39-abi3-musllinux_1_2_armv7l.whl", hash = "sha256:37ae80a28c1d3265bb1f22464c856bd23c02a05bb211e56d0c5301a435be6c1a", size = 9560069, upload-time = "2026-01-05T10:45:10.673Z" },
    { url = "https://files.pythonhosted.org/packages/16/04/fed398b05caa87ce9b1a1bb5166645e38196081b225059a6edaff6440fac/tokenizers-0.22.2-cp39-abi3-musllinux_1_2_i686.whl", hash = "sha256:791135ee325f2336f498590eb2f11dc5c295232f288e75c99a36c5dbce63088a", size = 9899263, upload-time = "2026-01-05T10:45:12.559Z" },
    { url = "https://files.pythonhosted.org/packages/05/a1/d62dfe7376beaaf1394917e0f8e93ee5f67fea8fcf4107501db35996586b/tokenizers-0.22.2-cp39-abi3-musllinux_1_2_x86_64.whl", hash = "sha256:38337540fbbddff8e999d59970f3c6f35a82de10053206a7562f1ea02d046fa5", size = 10033429, upload-time = "2026-01-05T10:45:14.333Z" },
    { url = "https://files.pythonhosted.org/packages/fd/18/a545c4ea42af3df6effd7d13d250ba77a0a86fb20393143bbb9a92e434d4/tokenizers-0.22.2-cp39-abi3-win32.whl", hash = "sha256:a6bf3f88c554a2b653af81f3204491c818ae2ac6fbc09e76ef4773351292bc92", size = 2502363, upload-time = "2026-01-05T10:45:20.593Z" },
    { url = "https://files.pythonhosted.org/packages/65/71/0670843133a43d43070abeb1949abfdef12a86d490bea9cd9e18e37c5ff7/tokenizers-0.22.2-cp39-abi3-win_amd64.whl", hash = "sha256:c9ea31edff2968b44a88f97d784c2f16dc0729b8b143ed004699ebca91f05c48", size = 2747786, upload-time = "2026-01-05T10:45:18.411Z" },
    { url = "https://files.pythonhosted.org/packages/72/f4/0de46cfa12cdcbcd464cc59fde36912af405696f687e53a091fb432f694c/tokenizers-0.22.2-cp39-abi3-win_arm64.whl", hash = "sha256:9ce725d22864a1e965217204946f830c37876eee3b2ba6fc6255e8e903d5fcbc", size = 2612133, upload-time = "2026-01-05T10:45:17.232Z" },
]

[[package]]
name = "tqdm"
version = "4.67.3"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/09/a9/6ba95a270c6f1fbcd8dac228323f2777d886cb206987444e4bce66338dd4/tqdm-4.67.3.tar.gz", hash = "sha256:7d825f03f89244ef73f1d4ce193cb1774a8179fd96f31d7e1dcde62092b960bb", size = 169598, upload-time = "2026-02-03T17:35:53.048Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/16/e1/3079a9ff9b8e11b846c6ac5c8b5bfb7ff225eee721825310c91b3b50304f/tqdm-4.67.3-py3-none-any.whl", hash = "sha256:ee1e4c0e59148062281c49d80b25b67771a127c85fc9676d3be5f243206826bf", size = 78374, upload-time = "2026-02-03T17:35:50.982Z" },
]

[[package]]
name = "typer"
version = "0.24.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "annotated-doc" },
    { name = "click" },
    { name = "rich" },
    { name = "shellingham" },
]
sdist = { url = "https://files.pythonhosted.org/packages/f5/24/cb09efec5cc954f7f9b930bf8279447d24618bb6758d4f6adf2574c41780/typer-0.24.1.tar.gz", hash = "sha256:e39b4732d65fbdcde189ae76cf7cd48aeae72919dea1fdfc16593be016256b45", size = 118613, upload-time = "2026-02-21T16:54:40.609Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/4a/91/48db081e7a63bb37284f9fbcefda7c44c277b18b0e13fbc36ea2335b71e6/typer-0.24.1-py3-none-any.whl", hash = "sha256:112c1f0ce578bfb4cab9ffdabc68f031416ebcc216536611ba21f04e9aa84c9e", size = 56085, upload-time = "2026-02-21T16:54:41.616Z" },
]

[[package]]
name = "typing-extensions"
version = "4.15.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/72/94/1a15dd82efb362ac84269196e94cf00f187f7ed21c242792a923cdb1c61f/typing_extensions-4.15.0.tar.gz", hash = "sha256:0cea48d173cc12fa28ecabc3b837ea3cf6f38c6d1136f85cbaaf598984861466", size = 109391, upload-time = "2025-08-25T13:49:26.313Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/18/67/36e9267722cc04a6b9f15c7f3441c2363321a3ea07da7ae0c0707beb2a9c/typing_extensions-4.15.0-py3-none-any.whl", hash = "sha256:f0fa19c6845758ab08074a0cfa8b7aecb71c999ca73d62883bc25cc018c4e548", size = 44614, upload-time = "2025-08-25T13:49:24.86Z" },
]

[[package]]
name = "typing-inspection"
version = "0.4.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "typing-extensions" },
]
sdist = { url = "https://files.pythonhosted.org/packages/55/e3/70399cb7dd41c10ac53367ae42139cf4b1ca5f36bb3dc6c9d33acdb43655/typing_inspection-0.4.2.tar.gz", hash = "sha256:ba561c48a67c5958007083d386c3295464928b01faa735ab8547c5692e87f464", size = 75949, upload-time = "2025-10-01T02:14:41.687Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/dc/9b/47798a6c91d8bdb567fe2698fe81e0c6b7cb7ef4d13da4114b41d239f65d/typing_inspection-0.4.2-py3-none-any.whl", hash = "sha256:4ed1cacbdc298c220f1bd249ed5287caa16f34d44ef4e9c3d0cbad5b521545e7", size = 14611, upload-time = "2025-10-01T02:14:40.154Z" },
]

[[package]]
name = "urllib3"
version = "2.6.3"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/c7/24/5f1b3bdffd70275f6661c76461e25f024d5a38a46f04aaca912426a2b1d3/urllib3-2.6.3.tar.gz", hash = "sha256:1b62b6884944a57dbe321509ab94fd4d3b307075e0c2eae991ac71ee15ad38ed", size = 435556, upload-time = "2026-01-07T16:24:43.925Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/39/08/aaaad47bc4e9dc8c725e68f9d04865dbcb2052843ff09c97b08904852d84/urllib3-2.6.3-py3-none-any.whl", hash = "sha256:bf272323e553dfb2e87d9bfd225ca7b0f467b919d7bbd355436d3fd37cb0acd4", size = 131584, upload-time = "2026-01-07T16:24:42.685Z" },
]

[[package]]
name = "uvicorn"
version = "0.41.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "click" },
    { name = "h11" },
]
sdist = { url = "https://files.pythonhosted.org/packages/32/ce/eeb58ae4ac36fe09e3842eb02e0eb676bf2c53ae062b98f1b2531673efdd/uvicorn-0.41.0.tar.gz", hash = "sha256:09d11cf7008da33113824ee5a1c6422d89fbc2ff476540d69a34c87fab8b571a", size = 82633, upload-time = "2026-02-16T23:07:24.1Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/83/e4/d04a086285c20886c0daad0e026f250869201013d18f81d9ff5eada73a88/uvicorn-0.41.0-py3-none-any.whl", hash = "sha256:29e35b1d2c36a04b9e180d4007ede3bcb32a85fbdfd6c6aeb3f26839de088187", size = 68783, upload-time = "2026-02-16T23:07:22.357Z" },
]

[[package]]
name = "win32-setctime"
version = "1.2.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/b3/8f/705086c9d734d3b663af0e9bb3d4de6578d08f46b1b101c2442fd9aecaa2/win32_setctime-1.2.0.tar.gz", hash = "sha256:ae1fdf948f5640aae05c511ade119313fb6a30d7eabe25fef9764dca5873c4c0", size = 4867, upload-time = "2024-12-07T15:28:28.314Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/e1/07/c6fe3ad3e685340704d314d765b7912993bcb8dc198f0e7a89382d37974b/win32_setctime-1.2.0-py3-none-any.whl", hash = "sha256:95d644c4e708aba81dc3704a116d8cbc974d70b3bdb8be1d150e36be6e9d1390", size = 4083, upload-time = "2024-12-07T15:28:26.465Z" },
]

[[package]]
name = "yiyu-workbench-backend"
version = "0.1.0"
source = { virtual = "." }
dependencies = [
    { name = "fastapi" },
    { name = "fastembed" },
    { name = "httpx" },
    { name = "pydantic" },
    { name = "pypdf" },
    { name = "pytest" },
    { name = "python-docx" },
    { name = "python-multipart" },
    { name = "qdrant-client" },
    { name = "uvicorn" },
]

[package.metadata]
requires-dist = [
    { name = "fastapi", specifier = ">=0.111.0" },
    { name = "fastembed", specifier = ">=0.3.6" },
    { name = "httpx", specifier = ">=0.27.0" },
    { name = "pydantic", specifier = ">=2.9.0" },
    { name = "pypdf", specifier = ">=5.3.0" },
    { name = "pytest", specifier = ">=8.3.0" },
    { name = "python-docx", specifier = ">=1.1.2" },
    { name = "python-multipart", specifier = ">=0.0.22" },
    { name = "qdrant-client", specifier = ">=1.9.1" },
    { name = "uvicorn", specifier = ">=0.30.0" },
]
~~~

## `build-resources/README.md`

- 编码: `utf-8`

~~~markdown
# build-resources

这个目录用于桌面版正式打包资源。

当前必须补齐：

- `icon.icns`

生成方式：

- `python3 scripts/generate-mac-icon.py`

后续可补：

- DMG 背景图
- 分发品牌素材
- 需要配套的签名 / 公证资源说明文档

当前目录先保留在仓库中，避免打包配置继续指向一个不存在的目录。
~~~

## `cloud_backend/app/__init__.py`

- 编码: `utf-8`

~~~python
"""Cloud backend package for the Yiyu workbench."""
~~~

## `cloud_backend/app/bootstrap_security.py`

- 编码: `utf-8`

~~~python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from typing import Final

JWT_SECRET_FILENAME: Final = '.yiyu-cloud-secret'
BOOTSTRAP_USERS_FILENAME: Final = '.yiyu-cloud-bootstrap-users.json'
DEFAULT_BOOTSTRAP_ADMIN_EMAIL: Final = 'admin@yiyu-system.com'


@dataclass(frozen=True)
class SeedUser:
    user_id: str
    full_name: str
    email: str
    primary_role: str
    account_status: str
    department_id: str | None
    password: str
    password_locked: bool = False


SEED_USER_SPECS: Final = (
    {
        'user_id': 'user_admin',
        'full_name': '益语管理员',
        'email': DEFAULT_BOOTSTRAP_ADMIN_EMAIL,
        'primary_role': 'admin',
        'account_status': 'approved',
        'department_id': None,
        'password_env': 'YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD',
        'legacy_password': None,
    },
    {
        'user_id': 'user_guyuan',
        'full_name': '顾源源',
        'email': 'guyuan@klngo.org',
        'primary_role': 'admin',
        'account_status': 'approved',
        'department_id': None,
        'password_env': 'YIYU_CLOUD_GUYUAN_PASSWORD',
        'legacy_password': None,
    },
    {
        'user_id': 'user_qinghua',
        'full_name': '庆华',
        'email': 'qinghua@yiyu-system.com',
        'primary_role': 'employee',
        'account_status': 'approved',
        'department_id': 'dept_consult_strategy',
        'password_env': 'YIYU_CLOUD_QINGHUA_PASSWORD',
        'legacy_password': None,
    },
    {
        'user_id': 'user_jianing',
        'full_name': '嘉宁',
        'email': 'jianing@yiyu-system.com',
        'primary_role': 'employee',
        'account_status': 'approved',
        'department_id': 'dept_customer_service',
        'password_env': 'YIYU_CLOUD_JIANING_PASSWORD',
        'legacy_password': None,
    },
    {
        'user_id': 'user_yishuo',
        'full_name': '一朔',
        'email': 'yishuo@yiyu-system.com',
        'primary_role': 'employee',
        'account_status': 'approved',
        'department_id': 'dept_info_data',
        'password_env': 'YIYU_CLOUD_YISHUO_PASSWORD',
        'legacy_password': None,
    },
)


def _truthy(value: str | None) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def ensure_cloud_secret(data_dir: Path) -> str:
    configured = os.environ.get('YIYU_CLOUD_SECRET_KEY', '').strip()
    if configured:
        return configured
    data_dir.mkdir(parents=True, exist_ok=True)
    secret_path = data_dir / JWT_SECRET_FILENAME
    if secret_path.exists():
        existing = secret_path.read_text(encoding='utf-8').strip()
        if existing:
            return existing
    secret = token_urlsafe(48)
    secret_path.write_text(secret, encoding='utf-8')
    try:
        os.chmod(secret_path, 0o600)
    except OSError:
        pass
    return secret


def _load_bootstrap_password_store(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        normalized[key] = {str(inner_key): str(inner_value) for inner_key, inner_value in value.items()}
    return normalized


def _write_bootstrap_password_store(path: Path, payload: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def resolve_seed_users(data_dir: Path) -> list[SeedUser]:
    insecure_seed_passwords = _truthy(os.environ.get('YIYU_CLOUD_INSECURE_SEED_PASSWORDS'))
    password_store_path = data_dir / BOOTSTRAP_USERS_FILENAME
    password_store = _load_bootstrap_password_store(password_store_path)
    store_changed = False
    resolved: list[SeedUser] = []

    for spec in SEED_USER_SPECS:
        email = os.environ.get('YIYU_CLOUD_BOOTSTRAP_ADMIN_EMAIL', '').strip() if spec['user_id'] == 'user_admin' else ''
        email = email or str(spec['email'])
        password = os.environ.get(str(spec['password_env']), '').strip()
        password_locked = bool(password)
        if not password:
            if insecure_seed_passwords and spec['legacy_password']:
                password = str(spec['legacy_password'])
                password_locked = True
            else:
                stored = password_store.get(str(spec['user_id']), {})
                stored_password = str(stored.get('password', '')).strip()
                if stored_password:
                    password = stored_password
                    if stored.get('email') != email:
                        stored['email'] = email
                        password_store[str(spec['user_id'])] = stored
                        store_changed = True
                else:
                    password = token_urlsafe(18)
                    password_store[str(spec['user_id'])] = {
                        'email': email,
                        'fullName': str(spec['full_name']),
                        'primaryRole': str(spec['primary_role']),
                        'password': password,
                    }
                    store_changed = True
        resolved.append(
            SeedUser(
                user_id=str(spec['user_id']),
                full_name=str(spec['full_name']),
                email=email,
                primary_role=str(spec['primary_role']),
                account_status=str(spec['account_status']),
                department_id=str(spec['department_id']) if spec['department_id'] else None,
                password=password,
                password_locked=password_locked,
            )
        )

    if store_changed and not insecure_seed_passwords:
        _write_bootstrap_password_store(password_store_path, password_store)
    return resolved
~~~

