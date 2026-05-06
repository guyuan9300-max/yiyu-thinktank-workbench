from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.services.workspace_thread_memory import (
    WorkspaceThreadContextPack,
    build_contextual_prompt,
    empty_thread_context_pack,
    fallback_update_thread_context,
    load_thread_context_pack,
    render_thread_memory_context,
    resolve_thread_references,
    save_thread_context_pack,
    update_thread_context_after_answer,
)


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "app.db")
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_a', '日慈基金会', '日慈基金会', '公益', '客户', '', '推进中', '2026-05-05T00:00:00', '2026-05-05T00:00:00')
        """
    )
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES('client_b', '同名对照客户', '同名对照客户', '公益', '客户', '', '推进中', '2026-05-05T00:00:00', '2026-05-05T00:00:00')
        """
    )
    db.execute(
        """
        INSERT INTO chat_threads(id, client_id, title, created_at, updated_at)
        VALUES('thread_a', 'client_a', '日慈线程', '2026-05-05T00:00:00', '2026-05-05T00:00:00')
        """
    )
    db.execute(
        """
        INSERT INTO chat_threads(id, client_id, title, created_at, updated_at)
        VALUES('thread_b', 'client_b', '对照线程', '2026-05-05T00:00:00', '2026-05-05T00:00:00')
        """
    )
    return db


class _NoModelAi:
    def get_health(self):  # type: ignore[no-untyped-def]
        class Health:
            provider = "mock"
            ready = False

        return Health()


def test_thread_memory_records_projects_then_resolves_followup_chain(tmp_path: Path) -> None:
    db = _db(tmp_path)
    pack = empty_thread_context_pack("client_a", "thread_a")

    first = fallback_update_thread_context(
        pack,
        prompt="请你帮我总结日慈基金会的核心项目",
        answer_content="核心项目包括心灵魔法学院、心松松-教师心理关怀计划、心盛计划、繁心计划。",
        retrieval_summary={},
        created_at="2026-05-05T00:01:00",
    )
    save_thread_context_pack(db, first, timestamp="2026-05-05T00:01:00")

    loaded = load_thread_context_pack(db, "client_a", "thread_a")
    refs = resolve_thread_references("你认为这些项目当中哪一个是最具有战略发展潜力的", loaded)
    rendered = render_thread_memory_context(loaded, refs)
    contextual_prompt = build_contextual_prompt("你认为这些项目当中哪一个是最具有战略发展潜力的", rendered)

    assert "心灵魔法学院" in contextual_prompt
    assert "心松松-教师心理关怀计划" in contextual_prompt
    assert any(item.expression == "这些" for item in refs)

    second = fallback_update_thread_context(
        loaded,
        prompt="你认为这些项目当中哪一个是最具有战略发展潜力的",
        answer_content="明确判断：当前战略潜力最高的项目是「心松松-教师心理关怀计划」。",
        retrieval_summary={},
        created_at="2026-05-05T00:02:00",
    )
    save_thread_context_pack(db, second, timestamp="2026-05-05T00:02:00")

    third_pack = load_thread_context_pack(db, "client_a", "thread_a")
    third_refs = resolve_thread_references("你认为这一个项目的核心价值是什么", third_pack)

    assert third_pack.lastSelectedObject
    assert "心松松-教师心理关怀计划" in str(third_pack.lastSelectedObject)
    assert any("心松松-教师心理关怀计划" in item.resolvedTo for item in third_refs)


def test_non_referential_new_question_does_not_apply_thread_memory(tmp_path: Path) -> None:
    db = _db(tmp_path)
    save_thread_context_pack(
        db,
        WorkspaceThreadContextPack(
            clientId="client_a",
            threadId="thread_a",
            mentionedObjects=["某份原文", "文件检索结果"],
            confirmedJudgments=["上一轮是在找原文和文件。"],
            lastSelectedObject={"name": "某份原文"},
        ),
        timestamp="2026-05-05T00:01:00",
    )

    pack = load_thread_context_pack(db, "client_a", "thread_a")
    refs = resolve_thread_references("你最喜欢顾源源文章当中的哪一篇", pack)

    assert refs == []


def test_thread_memory_is_isolated_by_client_and_thread(tmp_path: Path) -> None:
    db = _db(tmp_path)
    save_thread_context_pack(
        db,
        WorkspaceThreadContextPack(
            clientId="client_a",
            threadId="thread_a",
            mentionedObjects=["心松松-教师心理关怀计划"],
            lastSelectedObject={"name": "心松松-教师心理关怀计划"},
        ),
        timestamp="2026-05-05T00:01:00",
    )

    other = load_thread_context_pack(db, "client_b", "thread_b")

    assert other.mentionedObjects == []
    assert other.lastSelectedObject is None


def test_system_failure_does_not_update_thread_memory(tmp_path: Path) -> None:
    db = _db(tmp_path)
    save_thread_context_pack(
        db,
        WorkspaceThreadContextPack(
            clientId="client_a",
            threadId="thread_a",
            mentionedObjects=["心盛计划"],
            lastSelectedObject={"name": "心盛计划"},
            turns=[],
        ),
        timestamp="2026-05-05T00:01:00",
    )

    pack, mode = update_thread_context_after_answer(
        db,
        ai_service=_NoModelAi(),
        client_id="client_a",
        thread_id="thread_a",
        prompt="这一个项目的核心价值是什么",
        answer_content="本轮模型没有成功完成回答。",
        retrieval_summary={},
        answer_mode="system_failure",
        timestamp="2026-05-05T00:02:00",
    )

    assert mode == "skipped_system_failure"
    assert pack.lastSelectedObject == {"name": "心盛计划"}
    reloaded = load_thread_context_pack(db, "client_a", "thread_a")
    assert reloaded.turns == []


def test_bootstrap_existing_thread_messages(tmp_path: Path) -> None:
    db = _db(tmp_path)
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, evidence_json, status, created_at
        )
        VALUES('u1', 'thread_a', 'user', '请总结核心项目', NULL, NULL, '[]', 'success', '2026-05-05T00:01:00')
        """
    )
    db.execute(
        """
        INSERT INTO chat_messages(
            id, thread_id, role, content, structured_data_json, model_route, evidence_json, status, answer_mode, created_at
        )
        VALUES(
            'a1', 'thread_a', 'assistant',
            '日慈核心项目包括心灵魔法学院、心松松-教师心理关怀计划、心盛计划、繁心计划。',
            NULL, NULL, '[]', 'success', 'grounded_answer', '2026-05-05T00:02:00'
        )
        """
    )

    pack = load_thread_context_pack(db, "client_a", "thread_a", bootstrap=True)

    assert len(pack.turns) == 1
    assert "心松松-教师心理关怀计划" in pack.mentionedObjects
