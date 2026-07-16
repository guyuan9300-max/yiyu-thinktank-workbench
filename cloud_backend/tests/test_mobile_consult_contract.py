from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import main as cloud_main  # noqa: E402
from app.main import DEFAULT_ORG_ID, create_app, now_iso  # noqa: E402


def _is_scope_classifier(chat_payload: dict) -> bool:
    messages = chat_payload.get("messages") or []
    return bool(messages and "只输出一个词：IN 或 OUT" in str(messages[0].get("content", "")))


def _set_seed_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("YIYU_CLOUD_DATA_DIR", str(tmp_path / "cloud-data"))
    monkeypatch.setenv("YIYU_CLOUD_BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    monkeypatch.setenv("YIYU_CLOUD_QINGHUA_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_JIANING_PASSWORD", "Simulate123!")
    monkeypatch.setenv("YIYU_CLOUD_YISHUO_PASSWORD", "Simulate123!")


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@yiyu-system.com", "password": "Admin123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _configure_org_ai(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/settings/org-ai-config",
        headers=headers,
        json={
            "aiProvider": "openai-compatible",
            "aiProviderLabel": "当前组织测试模型",
            "aiBaseUrl": "https://models.example.com/v1",
            "aiModel": "org-test-model",
            "apiKey": "org-test-key",
        },
    )
    assert response.status_code == 200, response.text


def _insert_empty_client(
    app,
    client_id: str = "client_empty_mobile_contract",
    client_name: str = "空白测试客户",
) -> tuple[str, str]:
    timestamp = now_iso()
    app.state.app_state.db.execute(
        """
        INSERT INTO clients(id, organization_id, name, alias, created_at, updated_at)
        VALUES(?, ?, ?, NULL, ?, ?)
        """,
        (client_id, DEFAULT_ORG_ID, client_name, timestamp, timestamp),
    )
    return client_id, client_name


def _insert_client_dna(app, client_id: str) -> None:
    timestamp = now_iso()
    app.state.app_state.db.execute(
        """
        INSERT INTO cloud_client_dna_summaries(
            id, organization_id, client_id, source_type, source_id, snapshot_version,
            snapshot_hash, payload_json, evidence_refs_json, updated_at, published_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"dna_{client_id}",
            DEFAULT_ORG_ID,
            client_id,
            "client_dna",
            f"{client_id}:dna:v1",
            1,
            "dna-test-hash",
            json.dumps(
                {
                    "summary": "该客户正在推进年度计划并明确重点工作。",
                    "modules": [
                        {
                            "moduleKey": "organization_intro",
                            "title": "组织介绍",
                            "summary": "该客户是一家正在推进组织升级的公益机构。",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            "[]",
            timestamp,
            timestamp,
        ),
    )


def test_mobile_capabilities_and_openapi_contract(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    client = TestClient(create_app())
    headers = _auth_headers(client)

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200, openapi.text
    paths = openapi.json()["paths"]
    assert "/api/v1/mobile/capabilities" in paths
    assert "/api/v1/clients/{client_id}/workspace" in paths
    assert "/api/v1/clients/{client_id}/strategic-cockpit" in paths

    chat_payload_fields = openapi.json()["components"]["schemas"]["ConsultationChatPayload"]["properties"]
    chat_response_fields = openapi.json()["components"]["schemas"]["ConsultationChatResponse"]["properties"]
    assert "workspaceContext" in chat_payload_fields
    assert "taskBoardContext" in chat_payload_fields
    assert "answerMode" in chat_response_fields
    assert "contextQuality" in chat_response_fields
    assert "reply" in chat_response_fields

    capabilities = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert capabilities.status_code == 200, capabilities.text
    body = capabilities.json()
    assert body["consultationChat"] is True
    assert body["clientWorkspace"] is True
    assert body["strategicCockpit"] is True
    assert body["consultationPayloadVersion"] == "v2"


def test_workspace_and_cockpit_return_structured_missing_for_valid_client(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    app = create_app()
    client_id, _ = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)

    workspace = client.get(f"/api/v1/clients/{client_id}/workspace", headers=headers)
    assert workspace.status_code == 200, workspace.text
    workspace_body = workspace.json()
    assert workspace_body["status"] == "missing"
    assert workspace_body["updatedAt"] is None
    assert "workspace_snapshot" in workspace_body["missingSources"]
    assert workspace_body["goals"] == []

    cockpit = client.get(f"/api/v1/clients/{client_id}/strategic-cockpit", headers=headers)
    assert cockpit.status_code == 200, cockpit.text
    cockpit_body = cockpit.json()
    assert cockpit_body["status"] == "missing"
    assert cockpit_body["updatedAt"] is None
    assert cockpit_body["headline"]["summary"] == ""
    assert cockpit_body["pendingMaterials"] == []
    assert "strategic_cockpit" in cockpit_body["missingSources"]


def test_thin_context_chat_returns_limited_context_metadata(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setenv("ARK_API_KEY", "poison-global-key")
    captured: dict[str, object] = {}

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        assert api_key == "org-test-key"
        assert base_url == "https://models.example.com/v1"
        captured["systemPrompt"] = chat_payload["messages"][0]["content"]
        return "当前已知事实：只锁定了客户名，缺少工作台、DNA、会议和战略判断资料。"

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={"message": "介绍一下这个客户", "clientId": client_id, "clientName": client_name},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answerMode"] == "limited_context"
    assert body["contextQuality"]["level"] == "thin"
    assert {"workspace", "client_dna", "meeting", "strategic_cockpit"}.issubset(
        set(body["contextQuality"]["missingSources"]),
    )
    system_prompt = str(captured["systemPrompt"])
    assert "严禁依据客户名字" in system_prompt
    assert "组织类型或常识脑补" in system_prompt
    assert "任何判断必须可在【已知事实】中找到出处" in system_prompt


def _publish_understanding_snapshot(client: TestClient, headers: dict[str, str], client_id: str) -> None:
    """Push a calculation-center understanding snapshot via the existing
    knowledge-mirror publish RPC. Mirrors the desktop's expected payload shape
    so the cloud-side reader can be exercised end-to-end."""
    timestamp = now_iso()
    resp = client.post(
        "/api/v1/mobile/knowledge-mirror/publish",
        headers=headers,
        json={
            "items": [
                {
                    "clientId": client_id,
                    "sourceType": "client_understanding",
                    "sourceId": f"{client_id}:v1",
                    "snapshotVersion": 1,
                    "snapshotHash": "test-hash-1",
                    "updatedAt": timestamp,
                    "payload": {
                        "entities": [
                            {"id": "e1", "name": "示例公司", "type": "company", "mentions": 6, "confidence": 0.92},
                            {"id": "e2", "name": "张三", "type": "person", "mentions": 3},
                        ],
                        "relations": [
                            {
                                "id": "r1",
                                "subject": "张三",
                                "predicate": "供职于",
                                "object": "示例公司",
                                "confidence": 0.81,
                                "evidenceCount": 2,
                            }
                        ],
                        "atomicFacts": [
                            {"id": "f1", "statement": "示例公司 Q1 营收 1200 万", "semanticType": "fact", "confidence": 0.88}
                        ],
                        "contradictions": [
                            {
                                "id": "c1",
                                "topic": "Q1 营收口径分歧",
                                "conflictingStatements": ["营收 1200 万", "营收 1500 万"],
                                "severity": "medium",
                            }
                        ],
                        "glossary": [
                            {"id": "g1", "term": "双飞轮", "definition": "客户主业 + 第二增长曲线的并行模型"}
                        ],
                        "freshness": {"halfLifeDays": 90.0, "score": 0.74},
                    },
                    "evidenceRefs": [],
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text


def test_client_understanding_endpoint_returns_published_snapshot(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    app = create_app()
    client_id, _ = _insert_empty_client(app, client_id="client_understanding_endpoint", client_name="理解快照客户")
    client = TestClient(app)
    headers = _auth_headers(client)

    # Initially missing
    initial = client.get(f"/api/v1/clients/{client_id}/understanding", headers=headers)
    assert initial.status_code == 200, initial.text
    initial_body = initial.json()
    assert initial_body["status"] == "missing"
    assert initial_body["entities"] == []
    assert initial_body["relations"] == []

    # Publish and re-read
    _publish_understanding_snapshot(client, headers, client_id)

    refreshed = client.get(f"/api/v1/clients/{client_id}/understanding", headers=headers)
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["status"] in {"ready", "partial"}
    assert body["snapshotHash"] == "test-hash-1"
    entity_names = {item["name"] for item in body["entities"]}
    assert {"示例公司", "张三"}.issubset(entity_names)
    assert body["relations"][0]["predicate"] == "供职于"
    assert body["atomicFacts"][0]["statement"].startswith("示例公司")
    assert body["contradictions"][0]["topic"] == "Q1 营收口径分歧"
    assert body["glossary"][0]["term"] == "双飞轮"
    assert body["freshness"]["halfLifeDays"] == 90.0

    capabilities = client.get("/api/v1/mobile/capabilities", headers=headers)
    assert capabilities.status_code == 200, capabilities.text
    assert capabilities.json()["understandingMirror"] is True


def test_chat_folds_understanding_into_context_and_evidence(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setenv("ARK_API_KEY", "poison-global-key")
    captured: dict[str, object] = {}

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        assert api_key == "org-test-key"
        assert base_url == "https://models.example.com/v1"
        captured["systemPrompt"] = chat_payload["messages"][0]["content"]
        return "理解快照已读取，按已有结构化知识作答。"

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(
        app, client_id="client_understanding_chat", client_name="理解链路客户"
    )
    test_client = TestClient(app)
    headers = _auth_headers(test_client)
    _configure_org_ai(test_client, headers)

    _publish_understanding_snapshot(test_client, headers, client_id)

    response = test_client.post(
        "/api/v1/consultation/chat",
        json={"message": "Q1 营收分歧怎么处理", "clientId": client_id, "clientName": client_name},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    evidence_types = {item["type"] for item in body.get("evidence", [])}
    assert "understanding" in evidence_types
    assert "entity" in evidence_types
    assert "atomic_fact" in evidence_types
    available = set(body["contextQuality"]["availableSources"])
    assert "understanding" in available
    assert "理解快照" in str(captured["systemPrompt"])
    assert "示例公司" in str(captured["systemPrompt"])


def test_chat_out_of_scope_question_is_refused(tmp_path: Path, monkeypatch) -> None:
    """项目边界闸门: 在某客户上下文下问跑题问题 → out_of_scope 拒答, 不编答案/不标 grounded。"""
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setenv("ARK_API_KEY", "poison-global-key")

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        assert api_key == "org-test-key"
        assert base_url == "https://models.example.com/v1"
        # 模拟分类器判定 OUT; 若闸门生效, 主答案调用不应发生(out_of_scope 短路)
        return "OUT"

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={"message": "推荐北京火锅", "clientId": client_id, "clientName": client_name},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answerMode"] == "out_of_scope"
    assert body["evidence"] == []
    assert client_name in body["reply"]


def test_chat_in_scope_question_not_gated(tmp_path: Path, monkeypatch) -> None:
    """分类器判 IN 时, 闸门不拦截, 仍按原 limited/grounded 正常作答。"""
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setenv("ARK_API_KEY", "poison-global-key")

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        assert api_key == "org-test-key"
        assert base_url == "https://models.example.com/v1"
        return "IN"

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={"message": "这个客户下一步该确认什么", "clientId": client_id, "clientName": client_name},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["answerMode"] != "out_of_scope"


def test_chat_timeout_retries_once_with_compact_non_thinking_payload(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setenv("ARK_API_KEY", "poison-global-key")
    calls: list[tuple[dict, object]] = []

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        assert api_key == "org-test-key"
        assert base_url == "https://models.example.com/v1"
        calls.append((chat_payload, timeout))
        if _is_scope_classifier(chat_payload):
            return "IN"
        if len([payload for payload, _ in calls if not _is_scope_classifier(payload)]) == 1:
            raise httpx.ReadTimeout("simulated provider read timeout")
        return "当前核心工作是聚焦重点任务、核实风险并明确下一步。"

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={
            "message": "请结合当前任务板和已有资料，分析这个客户现阶段的核心工作、主要风险以及下一步行动建议。",
            "clientId": client_id,
            "clientName": client_name,
            "taskBoardContext": "正在推进年度计划，并核对关键责任人。",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "当前核心工作是聚焦重点任务、核实风险并明确下一步。"
    answer_calls = [(payload, timeout) for payload, timeout in calls if not _is_scope_classifier(payload)]
    assert len(answer_calls) == 2
    primary_payload, primary_timeout = answer_calls[0]
    fallback_payload, fallback_timeout = answer_calls[1]
    assert calls[0][1].read <= 5.0
    assert primary_payload is not fallback_payload
    assert primary_payload["enable_thinking"] is False
    assert primary_payload["max_tokens"] <= 560
    assert primary_timeout.read <= 24.0
    assert "超时降级" not in primary_payload["messages"][0]["content"]
    assert fallback_payload["enable_thinking"] is False
    assert fallback_payload["max_tokens"] <= 220
    assert fallback_timeout.read <= 10.0
    assert "超时降级" in fallback_payload["messages"][0]["content"]
    assert "140 字以内" in fallback_payload["messages"][0]["content"]


def test_intro_chat_with_client_dna_uses_mobile_safe_primary_budget(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    calls: list[tuple[dict, object]] = []

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        calls.append((chat_payload, timeout))
        if _is_scope_classifier(chat_payload):
            return "IN"
        return "该客户正在推进组织升级与年度重点工作。"

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app, client_id="client_intro_budget", client_name="介绍预算客户")
    _insert_client_dna(app, client_id)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={"message": "请介绍这个客户", "clientId": client_id, "clientName": client_name},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    answer_calls = [(payload, timeout) for payload, timeout in calls if not _is_scope_classifier(payload)]
    assert len(answer_calls) == 1
    payload, timeout = answer_calls[0]
    assert payload["enable_thinking"] is False
    assert payload["max_tokens"] <= 420
    assert timeout.read <= 24.0


def test_chat_second_timeout_returns_mobile_compatible_504(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    answer_call_count = 0

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        nonlocal answer_call_count
        if _is_scope_classifier(chat_payload):
            return "IN"
        answer_call_count += 1
        raise httpx.ReadTimeout("simulated provider read timeout")

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={
            "message": "请分析当前工作重点并给出下一步建议。",
            "clientId": client_id,
            "clientName": client_name,
            "taskBoardContext": "正在核对重点任务。",
        },
        headers=headers,
    )

    assert response.status_code == 504, response.text
    assert "超时" in response.json()["detail"]
    assert answer_call_count == 2


def test_chat_enforces_absolute_deadline_before_mobile_abort(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    monkeypatch.setattr(cloud_main, "CONSULTATION_TOTAL_DEADLINE_SECONDS", 0.50)
    classifier_cancelled = [False]

    async def slow_classifier(*args, **kwargs):  # noqa: ANN002, ANN003
        try:
            await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            classifier_cancelled[0] = True
            raise
        return None

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        return "不应到达模型调用"

    monkeypatch.setattr(cloud_main, "_classify_consultation_out_of_scope", slow_classifier)
    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    started = time.monotonic()
    response = client.post(
        "/api/v1/consultation/chat",
        json={
            "message": "请分析当前工作重点并给出下一步建议。",
            "clientId": client_id,
            "clientName": client_name,
            "taskBoardContext": "正在核对重点任务。",
        },
        headers=headers,
    )
    elapsed = time.monotonic() - started

    assert response.status_code == 504, response.text
    assert "超时" in response.json()["detail"]
    assert classifier_cancelled[0] is True
    assert elapsed < 0.90
    assert cloud_main.CONSULTATION_TOTAL_DEADLINE_SECONDS < 45.0


def test_classifier_timeout_keeps_scope_guard_in_answer_prompt(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    captured: dict[str, str] = {}

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        if _is_scope_classifier(chat_payload):
            raise TimeoutError("simulated classifier deadline")
        captured["systemPrompt"] = str(chat_payload["messages"][0]["content"])
        return "当前应先核对重点任务。"

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={
            "message": "请分析当前工作重点。",
            "clientId": client_id,
            "clientName": client_name,
            "taskBoardContext": "正在核对重点任务。",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert "项目边界降级守护" in captured["systemPrompt"]
    assert "其他客户" in captured["systemPrompt"]


def test_chat_upstream_504_retries_once(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    answer_call_count = 0

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        nonlocal answer_call_count
        if _is_scope_classifier(chat_payload):
            return "IN"
        answer_call_count += 1
        if answer_call_count == 1:
            request = httpx.Request("POST", "https://models.example.com/v1/chat/completions")
            upstream = httpx.Response(504, request=request)
            raise httpx.HTTPStatusError("upstream timeout", request=request, response=upstream)
        return "已通过紧凑模式恢复回答。"

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={
            "message": "请分析当前工作重点。",
            "clientId": client_id,
            "clientName": client_name,
            "taskBoardContext": "正在核对重点任务。",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "已通过紧凑模式恢复回答。"
    assert answer_call_count == 2


def test_consultation_retryable_timeout_matrix() -> None:
    request = httpx.Request("POST", "https://models.example.com/v1/chat/completions")

    for error in (
        TimeoutError("wall deadline"),
        httpx.ConnectTimeout("connect", request=request),
        httpx.ReadTimeout("read", request=request),
        httpx.PoolTimeout("pool", request=request),
    ):
        assert cloud_main._is_retryable_consultation_timeout(error) is True

    assert cloud_main._is_retryable_consultation_timeout(
        httpx.WriteTimeout("write", request=request),
    ) is False

    for status_code, expected in ((408, True), (504, True), (401, False), (429, False), (500, False)):
        upstream = httpx.Response(status_code, request=request)
        error = httpx.HTTPStatusError("upstream", request=request, response=upstream)
        assert cloud_main._is_retryable_consultation_timeout(error) is expected


def test_chat_non_timeout_provider_error_is_not_retried(tmp_path: Path, monkeypatch) -> None:
    _set_seed_env(tmp_path, monkeypatch)
    answer_call_count = 0

    async def fake_qwen_chat(api_key, chat_payload, timeout, *, base_url):  # noqa: ANN001
        nonlocal answer_call_count
        if _is_scope_classifier(chat_payload):
            return "IN"
        answer_call_count += 1
        request = httpx.Request("POST", "https://models.example.com/v1/chat/completions")
        upstream = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=upstream)

    monkeypatch.setattr(cloud_main, "_async_qwen_chat", fake_qwen_chat)
    app = create_app()
    client_id, client_name = _insert_empty_client(app)
    client = TestClient(app)
    headers = _auth_headers(client)
    _configure_org_ai(client, headers)

    response = client.post(
        "/api/v1/consultation/chat",
        json={
            "message": "请分析当前工作重点。",
            "clientId": client_id,
            "clientName": client_name,
            "taskBoardContext": "正在核对重点任务。",
        },
        headers=headers,
    )

    assert response.status_code == 502, response.text
    assert answer_call_count == 1
