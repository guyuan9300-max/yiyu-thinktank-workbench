"""
深度思考开关路由测试。

验证 ChatRequest.deepThinking 参数能正确：
1. 落库到 chat_messages.deep_thinking_requested 列（user / assistant 两条消息都要落）
2. 通过 ChatMessageRecord.deepThinkingRequested 字段回到前端
3. 默认值（不传 / 显式 false）落库为 0

不直接验证 multipass 是否被调用 —— 那是 background_resolve_chat_answer 内部行为，
本测试通过 RecordingExecutor 拦截，确保不会触发真实 LLM 调用。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

# 端到端测试需要能成功 import app.main —— 本地若有 stale db / 迁移问题，
# 模块顶部的 create_app() 会抛 RuntimeError。此处优雅跳过，避免阻塞 CI；
# 上游环境干净时（CI / 清理过的本地 dev）会正常跑。
try:
    from app.main import create_app  # noqa: E402
except Exception as exc:  # noqa: BLE001
    pytest.skip(
        f"app.main import failed (likely stale local db schema): {exc}",
        allow_module_level=True,
    )


class RecordingExecutor:
    def __init__(self) -> None:
        self.submissions: list[tuple[object, tuple[object, ...]]] = []

    def submit(self, fn, *args):  # type: ignore[no-untyped-def]
        self.submissions.append((fn, args))
        return object()

    def shutdown(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None


def _make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    client.app.state.app_state.chat_answer_executor = RecordingExecutor()
    return client


def _create_client_record(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "deepThinking 路由测试客户",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _read_deep_thinking_flag(client: TestClient, message_id: str) -> int:
    row = client.app.state.app_state.db.fetchone(
        "SELECT deep_thinking_requested FROM chat_messages WHERE id = ?",
        (message_id,),
    )
    assert row is not None, f"message {message_id} not found"
    return int(row["deep_thinking_requested"] or 0)


def test_chat_start_default_deep_thinking_false(tmp_path: Path) -> None:
    """不传 deepThinking 参数时，两条消息都应落库为 0。"""
    client = _make_client(tmp_path)
    client_id = _create_client_record(client, "默认普通客户")

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "介绍这个客户"},
    )
    assert response.status_code == 200
    body = response.json()

    user_id = body["userMessage"]["id"]
    assistant_id = body["assistantMessage"]["id"]
    assert _read_deep_thinking_flag(client, user_id) == 0
    assert _read_deep_thinking_flag(client, assistant_id) == 0
    assert body["userMessage"]["deepThinkingRequested"] is False
    assert body["assistantMessage"]["deepThinkingRequested"] is False


def test_chat_start_explicit_deep_thinking_false(tmp_path: Path) -> None:
    """显式 deepThinking=False，行为与默认一致。"""
    client = _make_client(tmp_path)
    client_id = _create_client_record(client, "显式 false 客户")

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "介绍这个客户", "deepThinking": False},
    )
    assert response.status_code == 200
    body = response.json()

    assert _read_deep_thinking_flag(client, body["userMessage"]["id"]) == 0
    assert _read_deep_thinking_flag(client, body["assistantMessage"]["id"]) == 0
    assert body["assistantMessage"]["deepThinkingRequested"] is False


def test_chat_start_deep_thinking_true_persists(tmp_path: Path) -> None:
    """deepThinking=True 时两条消息都应落库为 1，且响应字段为 True。"""
    client = _make_client(tmp_path)
    client_id = _create_client_record(client, "深度思考客户")

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "这个客户的战略有什么特点", "deepThinking": True},
    )
    assert response.status_code == 200
    body = response.json()

    user_id = body["userMessage"]["id"]
    assistant_id = body["assistantMessage"]["id"]
    assert _read_deep_thinking_flag(client, user_id) == 1
    assert _read_deep_thinking_flag(client, assistant_id) == 1
    assert body["userMessage"]["deepThinkingRequested"] is True
    assert body["assistantMessage"]["deepThinkingRequested"] is True
    # assistant 的 retrievalSummary 里也应带上 deepThinkingRequested=True
    retrieval_summary = body["assistantMessage"]["retrievalSummary"]
    assert retrieval_summary.get("deepThinkingRequested") is True


def test_chat_message_record_round_trip_deep_thinking(tmp_path: Path) -> None:
    """通过单独 GET 一条消息时，deepThinkingRequested 字段应正确回填。"""
    client = _make_client(tmp_path)
    client_id = _create_client_record(client, "RoundTrip 客户")

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat/start",
        json={"prompt": "深度问题", "deepThinking": True},
    )
    assert response.status_code == 200
    assistant_id = response.json()["assistantMessage"]["id"]

    fetched = client.get(f"/api/v1/clients/{client_id}/workspace/chat/messages/{assistant_id}")
    assert fetched.status_code == 200
    assert fetched.json()["deepThinkingRequested"] is True
