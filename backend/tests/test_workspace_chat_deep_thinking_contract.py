"""
深度思考开关「契约」测试。

只验证 pydantic 模型字段契约，不依赖 app.main / 数据库 / FastAPI 启动。
任何环境下都能跑，覆盖：
1. ChatRequest 默认不含 deepThinking → 解析为 False
2. ChatRequest 显式 deepThinking=False → 解析为 False
3. ChatRequest 显式 deepThinking=True → 解析为 True
4. ChatRequest 接受 dict 输入并保留 deepThinking
5. ChatMessageRecord 默认 deepThinkingRequested=False
6. ChatMessageRecord 显式 deepThinkingRequested=True 能正确序列化往返

端到端路由验证由 test_workspace_chat_deep_thinking_routing.py 负责
（环境干净时自动启用，否则 skip）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import ChatMessageRecord, ChatRequest


def test_chat_request_default_deep_thinking_is_false() -> None:
    req = ChatRequest(prompt="任意问题")
    assert req.deepThinking is False


def test_chat_request_explicit_false() -> None:
    req = ChatRequest(prompt="任意问题", deepThinking=False)
    assert req.deepThinking is False


def test_chat_request_explicit_true() -> None:
    req = ChatRequest(prompt="深度问题", deepThinking=True)
    assert req.deepThinking is True


def test_chat_request_accepts_dict_with_deep_thinking() -> None:
    payload = {
        "prompt": "客户战略",
        "threadId": "th_1",
        "searchId": None,
        "workingDocumentIds": [],
        "deepThinking": True,
    }
    req = ChatRequest(**payload)
    assert req.deepThinking is True
    assert req.threadId == "th_1"


def _base_chat_message_record_payload() -> dict[str, object]:
    return {
        "id": "msg_1",
        "threadId": "th_1",
        "role": "assistant",
        "content": "答案",
        "createdAt": "2026-05-14T00:00:00",
        "status": "success",
    }


def test_chat_message_record_default_deep_thinking_requested_is_false() -> None:
    record = ChatMessageRecord(**_base_chat_message_record_payload())
    assert record.deepThinkingRequested is False


def test_chat_message_record_round_trip_deep_thinking_true() -> None:
    payload = _base_chat_message_record_payload()
    payload["deepThinkingRequested"] = True
    record = ChatMessageRecord(**payload)
    assert record.deepThinkingRequested is True
    # 序列化往返
    dumped = record.model_dump()
    assert dumped["deepThinkingRequested"] is True
    rebuilt = ChatMessageRecord(**dumped)
    assert rebuilt.deepThinkingRequested is True


def test_chat_message_record_role_user_supports_deep_thinking_flag() -> None:
    payload = _base_chat_message_record_payload()
    payload["role"] = "user"
    payload["deepThinkingRequested"] = True
    record = ChatMessageRecord(**payload)
    assert record.role == "user"
    assert record.deepThinkingRequested is True
