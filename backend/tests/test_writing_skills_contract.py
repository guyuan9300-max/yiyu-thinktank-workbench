"""
写作风格 skill 契约测试（R6）：

验证：
1. ChatRequest 默认 activeSkillId=None；显式传值能解析
2. ChatMessageRecord 默认 activeSkillId=None；显式传值能解析
3. WritingSkillRecord / WritingSkillCreatePayload / WritingSkillUpdatePayload 字段约束
4. WritingSkillDistillPayload 接收 samples list
5. WritingSkillDistillResult 返回 distilledMd

纯 pydantic 模型契约测试，不依赖 db / FastAPI。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import (
    ChatMessageRecord,
    ChatRequest,
    WritingSkillCreatePayload,
    WritingSkillDistillPayload,
    WritingSkillDistillResult,
    WritingSkillRecord,
    WritingSkillUpdatePayload,
)


def test_chat_request_default_active_skill_is_none() -> None:
    req = ChatRequest(prompt="x")
    assert req.activeSkillId is None


def test_chat_request_explicit_active_skill() -> None:
    req = ChatRequest(prompt="x", activeSkillId="skill_builtin_luoyonghao")
    assert req.activeSkillId == "skill_builtin_luoyonghao"


def test_chat_message_record_default_active_skill_is_none() -> None:
    record = ChatMessageRecord(
        id="m1",
        threadId="t1",
        role="assistant",
        content="answer",
        createdAt="2026-05-14T00:00:00",
        status="success",
    )
    assert record.activeSkillId is None


def test_chat_message_record_with_active_skill() -> None:
    record = ChatMessageRecord(
        id="m1",
        threadId="t1",
        role="assistant",
        content="answer",
        createdAt="2026-05-14T00:00:00",
        status="success",
        activeSkillId="skill_xyz",
    )
    assert record.activeSkillId == "skill_xyz"


def test_writing_skill_record_basic_fields() -> None:
    skill = WritingSkillRecord(
        id="skill_luo",
        name="罗永浩风格",
        description="段子手 + 大字报",
        distilledMd="## 风格特征\n...",
        isBuiltin=True,
        sortOrder=10,
        createdAt="2026-05-14T00:00:00",
        updatedAt="2026-05-14T00:00:00",
    )
    assert skill.id == "skill_luo"
    assert skill.isBuiltin is True
    assert skill.sortOrder == 10


def test_writing_skill_create_payload_defaults() -> None:
    payload = WritingSkillCreatePayload(name="x", distilledMd="md")
    assert payload.description == ""
    assert payload.sortOrder == 100


def test_writing_skill_update_payload_partial() -> None:
    payload = WritingSkillUpdatePayload(name="新名字")
    assert payload.name == "新名字"
    assert payload.distilledMd is None
    assert payload.sortOrder is None


def test_writing_skill_distill_payload() -> None:
    payload = WritingSkillDistillPayload(
        samples=["篇 1 " * 100, "篇 2 " * 100, "篇 3 " * 100],
        skillName="测试",
    )
    assert len(payload.samples) == 3
    assert payload.skillName == "测试"


def test_writing_skill_distill_result() -> None:
    result = WritingSkillDistillResult(
        distilledMd="## 风格特征\n...",
        samplesProcessed=3,
        suggestedName="测试风格",
    )
    assert result.samplesProcessed == 3
    assert "风格" in result.distilledMd


# R7：创意度三档契约测试
def test_chat_request_default_creativity_mode_is_balanced() -> None:
    req = ChatRequest(prompt="x")
    assert req.creativityMode == "balanced"


def test_chat_request_accepts_creative_mode() -> None:
    req = ChatRequest(prompt="x", creativityMode="creative")
    assert req.creativityMode == "creative"


def test_chat_request_accepts_strict_mode() -> None:
    req = ChatRequest(prompt="x", creativityMode="strict")
    assert req.creativityMode == "strict"


def test_chat_request_rejects_invalid_creativity_mode() -> None:
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ChatRequest(prompt="x", creativityMode="nonsense")  # type: ignore[arg-type]


def test_chat_message_record_creativity_mode_default_none() -> None:
    record = ChatMessageRecord(
        id="m1",
        threadId="t1",
        role="assistant",
        content="answer",
        createdAt="2026-05-15T00:00:00",
        status="success",
    )
    assert record.creativityMode is None


def test_chat_message_record_creativity_mode_persists() -> None:
    record = ChatMessageRecord(
        id="m1",
        threadId="t1",
        role="assistant",
        content="answer",
        createdAt="2026-05-15T00:00:00",
        status="success",
        creativityMode="creative",
    )
    assert record.creativityMode == "creative"
