"""[B-V2.1] F2.8 验证 · 3 个 P0 endpoint 接入幂等性 端到端集成测试

跑法:
    cd backend && .venv/bin/python3 -m pytest tests/test_v22_f28_endpoint_idempotency.py -v

服务:
- V2.2_NORTH_STAR.md N3 A6 (3.0 AI agent retry 容错)
- V2.2_F28_ENDPOINT_PATCHES.md §4 集成测试要求

测试场景:
1. 不带 Idempotency-Key → 向后兼容 (旧客户端原样工作)
2. 同 key + 同 body 两次 → 第 2 次返回缓存,不重复创建
3. 同 key + 不同 body → 422 IdempotencyKeyMismatchError
4. 3 个 endpoint method+path 隔离 (同 key 用 /clients 不冲突 /event-lines)
5. AI agent header (X-Actor-Type: ai_agent) → idempotency_keys 表能查到
"""
from __future__ import annotations

import sys
import threading
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """每个测试独立 app + tmp data_dir,完全隔离"""
    app = create_app(tmp_path / "data")
    test_client = TestClient(app)
    test_client.__enter__()
    yield test_client
    test_client.__exit__(None, None, None)


def _new_key() -> str:
    """生成唯一 Idempotency-Key"""
    return f"test-{uuid.uuid4().hex[:12]}"


def _task_payload(title: str) -> dict[str, object]:
    return {
        "title": title,
        "desc": "幂等端到端测试",
        "priority": "normal",
        "listId": "",
        "clientId": None,
        "sourceType": "manual",
    }


def _create_workspace(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/workspaces",
        json={
            "kind": "organization",
            "name": name,
            "cloudApiUrl": f"https://{name}.example.test",
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["activeSandboxId"])


def _activate_workspace(client: TestClient, sandbox_id: str) -> None:
    response = client.post(f"/api/v1/workspaces/{sandbox_id}/activate")
    assert response.status_code == 200, response.text


# ── 场景 1: 向后兼容 ──────────────────────────────────────────


def test_event_lines_without_idempotency_key_works(client: TestClient) -> None:
    """不带 Idempotency-Key header → 行为跟旧 endpoint 完全一致"""
    response = client.post(
        "/api/v1/event-lines",
        json={"name": "测试事件线-无幂等"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "测试事件线-无幂等"


def test_clients_without_idempotency_key_works(client: TestClient) -> None:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": "测试客户-无幂等",
            "alias": "test1",
            "domain": "测试",
            "type": "战略陪伴",
            "intro": "",
            "stage": "active",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "测试客户-无幂等"


# ── 场景 2: 同 key + 同 body retry → 不重复创建 ─────────────


def test_event_lines_same_key_same_body_returns_cached(
    client: TestClient,
) -> None:
    """关键场景: 网络 retry → 第 2 次返回第 1 次的结果,db 里只有 1 条事件线"""
    key = _new_key()
    payload = {"name": "幂等测试-同 key 同 body"}

    # 第 1 次
    r1 = client.post(
        "/api/v1/event-lines",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert r1.status_code == 200
    id_1 = r1.json()["id"]

    # 第 2 次 (模拟 retry)
    r2 = client.post(
        "/api/v1/event-lines",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert r2.status_code == 200
    id_2 = r2.json()["id"]

    # 同一个 event_line id (没重复创建)
    assert id_1 == id_2

    # 通过 GET 列表确认 db 里只有 1 条
    list_response = client.get("/api/v1/event-lines")
    assert list_response.status_code == 200
    items = list_response.json()
    matching = [e for e in items if e.get("name") == payload["name"]]
    assert len(matching) == 1, (
        f"期望只创建 1 条 event_line, 实际 {len(matching)} 条"
    )


def test_clients_same_key_same_body_returns_cached(client: TestClient) -> None:
    key = _new_key()
    payload = {
        "name": "幂等测试客户",
        "alias": "idem_test",
        "domain": "测试",
        "type": "战略陪伴",
        "intro": "",
        "stage": "active",
    }

    r1 = client.post(
        "/api/v1/clients",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert r1.status_code == 200
    id_1 = r1.json()["id"]

    r2 = client.post(
        "/api/v1/clients",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert r2.status_code == 200
    id_2 = r2.json()["id"]

    assert id_1 == id_2

    # GET 列表验证只创建了 1 条
    list_response = client.get("/api/v1/clients")
    assert list_response.status_code == 200
    items = list_response.json()
    matching = [c for c in items if c.get("name") == payload["name"]]
    assert len(matching) == 1


def test_tasks_same_key_same_body_returns_cached(client: TestClient) -> None:
    key = _new_key()
    payload = _task_payload("幂等测试任务")

    r1 = client.post(
        "/api/v1/tasks",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert r1.status_code == 200, r1.text

    r2 = client.post(
        "/api/v1/tasks",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["id"] == r1.json()["id"]


# ── 场景 3: 同 key + 不同 body → 422 ──────────────────────


def test_event_lines_same_key_different_body_rejects(
    client: TestClient,
) -> None:
    """同 key 但 body 不同 → 422 (客户端 bug 或被攻击)"""
    key = _new_key()

    r1 = client.post(
        "/api/v1/event-lines",
        json={"name": "原始事件线"},
        headers={"Idempotency-Key": key},
    )
    assert r1.status_code == 200

    # 同 key 但改了 body
    r2 = client.post(
        "/api/v1/event-lines",
        json={"name": "篡改的事件线"},
        headers={"Idempotency-Key": key},
    )
    assert r2.status_code == 422
    assert "previously used with a different request body" in r2.text


# ── 场景 4: method+path 隔离 ──────────────────────────────


def test_same_key_different_endpoint_treated_separately(
    client: TestClient,
) -> None:
    """同 idempotency_key 用 POST /event-lines 跟用 POST /clients 是不同记录"""
    shared_key = _new_key()

    # POST /event-lines
    r1 = client.post(
        "/api/v1/event-lines",
        json={"name": "事件线 X"},
        headers={"Idempotency-Key": shared_key},
    )
    assert r1.status_code == 200

    # 同 key 但用 POST /clients → 不冲突 (不同 path)
    r2 = client.post(
        "/api/v1/clients",
        json={
            "name": "客户 X",
            "alias": "ax",
            "domain": "",
            "type": "战略陪伴",
            "intro": "",
            "stage": "active",
        },
        headers={"Idempotency-Key": shared_key},
    )
    assert r2.status_code == 200

    # 都建了 (因为 method+path 不同, 即使 key 一样)
    assert r1.json()["name"] == "事件线 X"
    assert r2.json()["name"] == "客户 X"


# ── 场景 5: AI agent header → idempotency_keys 表能查到 ────


def test_ai_agent_actor_recorded_in_idempotency_table(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """N3 核心场景: AI agent retry header (X-Actor-Type: ai_agent) 被记录到 idempotency_keys 表"""
    import sqlite3

    key = _new_key()
    response = client.post(
        "/api/v1/event-lines",
        json={"name": "AI 起草的事件线"},
        headers={
            "Idempotency-Key": key,
            "X-Actor-Type": "ai_agent",
            "X-Actor-Id": "agent_contract_drafter",
        },
    )
    assert response.status_code == 200

    # 直接查 idempotency_keys 表验证 actor 跟踪
    db_path = tmp_path / "data" / "app.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT idempotency_key, actor_type, actor_id, status "
        "FROM idempotency_keys "
        "WHERE idempotency_key = ? AND request_path = ?",
        (key, "/api/v1/event-lines"),
    ).fetchone()
    conn.close()

    assert row is not None, "idempotency_keys 表里应该有这条记录"
    assert row["idempotency_key"] == key
    assert row["actor_type"] == "ai_agent"
    assert row["actor_id"] == "agent_contract_drafter"
    assert row["status"] == "completed"


def test_same_key_is_independent_for_different_authenticated_actors(
    client: TestClient,
) -> None:
    key = _new_key()
    payload = {"name": "两个 AI 各自创建的事件线"}

    def post_as(actor_id: str):
        return client.post(
            "/api/v1/event-lines",
            json=payload,
            headers={
                "Idempotency-Key": key,
                "X-Actor-Type": "ai_agent",
                "X-Actor-Id": actor_id,
            },
        )

    first_a = post_as("agent_a")
    first_b = post_as("agent_b")
    retry_a = post_as("agent_a")
    retry_b = post_as("agent_b")

    assert first_a.status_code == first_b.status_code == 200
    assert first_a.json()["id"] != first_b.json()["id"]
    assert retry_a.json()["id"] == first_a.json()["id"]
    assert retry_b.json()["id"] == first_b.json()["id"]


def test_same_key_is_independent_across_sandboxes(client: TestClient) -> None:
    key = _new_key()
    payload = {"name": "跨沙箱同 key 事件线"}

    sandbox_a = _create_workspace(client, "idem-sandbox-a")
    first_a = client.post(
        "/api/v1/event-lines",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert first_a.status_code == 200, first_a.text

    sandbox_b = _create_workspace(client, "idem-sandbox-b")
    first_b = client.post(
        "/api/v1/event-lines",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert first_b.status_code == 200, first_b.text
    assert first_b.json()["id"] != first_a.json()["id"]

    _activate_workspace(client, sandbox_a)
    retry_a = client.post(
        "/api/v1/event-lines",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert retry_a.status_code == 200, retry_a.text
    assert retry_a.json()["id"] == first_a.json()["id"]

    _activate_workspace(client, sandbox_b)
    retry_b = client.post(
        "/api/v1/event-lines",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert retry_b.status_code == 200, retry_b.text
    assert retry_b.json()["id"] == first_b.json()["id"]


def test_concurrent_same_key_returns_409_then_replays_completed_result(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = _new_key()
    payload = {"name": "并发幂等事件线"}
    db = client.app.state.app_state.db
    original_execute = db.execute
    entered_business_write = threading.Event()
    release_business_write = threading.Event()
    blocked_once = False

    def blocking_execute(query: str, params=()):
        nonlocal blocked_once
        if "INSERT INTO event_lines(" in query and not blocked_once:
            blocked_once = True
            entered_business_write.set()
            if not release_business_write.wait(timeout=5):
                raise AssertionError("timed out waiting to release business write")
        return original_execute(query, params)

    monkeypatch.setattr(db, "execute", blocking_execute)
    first_result: dict[str, object] = {}

    def first_request() -> None:
        first_result["response"] = client.post(
            "/api/v1/event-lines",
            json=payload,
            headers={"Idempotency-Key": key},
        )

    worker = threading.Thread(target=first_request, daemon=True)
    worker.start()
    assert entered_business_write.wait(timeout=5)
    try:
        concurrent = client.post(
            "/api/v1/event-lines",
            json=payload,
            headers={"Idempotency-Key": key},
        )
        assert concurrent.status_code == 409, concurrent.text
    finally:
        release_business_write.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    first = first_result["response"]
    assert getattr(first, "status_code") == 200
    replay = client.post(
        "/api/v1/event-lines",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]


@pytest.mark.parametrize(
    ("path", "payload", "insert_marker"),
    [
        (
            "/api/v1/event-lines",
            {"name": "失败后重试事件线"},
            "INSERT INTO event_lines(",
        ),
        (
            "/api/v1/clients",
            {
                "name": "失败后重试客户",
                "alias": "retry_after_failure",
                "domain": "测试",
                "type": "战略陪伴",
                "intro": "",
                "stage": "active",
            },
            "INSERT INTO clients(",
        ),
        (
            "/api/v1/tasks",
            _task_payload("失败后重试任务"),
            "INSERT INTO tasks(",
        ),
    ],
)
def test_business_failure_releases_claim_for_immediate_retry(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    payload: dict[str, object],
    insert_marker: str,
) -> None:
    key = _new_key()
    db = client.app.state.app_state.db
    original_execute = db.execute
    failed_once = False

    def fail_business_insert_once(query: str, params=()):
        nonlocal failed_once
        if insert_marker in query and not failed_once:
            failed_once = True
            raise RuntimeError("simulated business write failure")
        return original_execute(query, params)

    monkeypatch.setattr(db, "execute", fail_business_insert_once)
    with pytest.raises(RuntimeError, match="simulated business write failure"):
        client.post(
            path,
            json=payload,
            headers={"Idempotency-Key": key},
        )
    assert failed_once

    retry = client.post(
        path,
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert retry.status_code == 200, retry.text

    replay = client.post(
        path,
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == retry.json()["id"]


# ── 场景 6: Stripe 风格完整 retry 流程 (端到端) ────────────


def test_stripe_style_full_retry_flow(client: TestClient) -> None:
    """完整端到端: AI agent 提交建客户请求,模拟首次成功 + 网络超时 retry + 后续 retry 改 body → 422"""
    key = "ai-retry-end2end"
    payload_v1 = {
        "name": "Stripe 风格客户",
        "alias": "stripe_test",
        "domain": "",
        "type": "战略陪伴",
        "intro": "",
        "stage": "active",
    }

    # 第 1 次成功
    r1 = client.post(
        "/api/v1/clients",
        json=payload_v1,
        headers={
            "Idempotency-Key": key,
            "X-Actor-Type": "ai_agent",
            "X-Actor-Id": "agent_001",
        },
    )
    assert r1.status_code == 200
    first_id = r1.json()["id"]

    # 第 2 次 retry (模拟客户端超时, 实际服务端已经返回)
    r2 = client.post(
        "/api/v1/clients",
        json=payload_v1,
        headers={
            "Idempotency-Key": key,
            "X-Actor-Type": "ai_agent",
            "X-Actor-Id": "agent_001",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == first_id  # 同一个 client

    # 第 3 次 retry 但 body 改了 → 422
    payload_v2 = {**payload_v1, "name": "被篡改的名字"}
    r3 = client.post(
        "/api/v1/clients",
        json=payload_v2,
        headers={
            "Idempotency-Key": key,
            "X-Actor-Type": "ai_agent",
            "X-Actor-Id": "agent_001",
        },
    )
    assert r3.status_code == 422
