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
