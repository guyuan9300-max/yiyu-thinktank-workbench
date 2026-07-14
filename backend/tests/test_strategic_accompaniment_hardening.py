from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.services.sandbox_registry import ensure_organization_sandbox_for_session, set_active_sandbox_setting


NOW = "2026-05-03T10:00:00"


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "战略陪伴边界客户") -> str:
    created = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "内部陪伴",
            "intro": "用于战略陪伴边界测试",
            "stage": "推进中",
        },
    )
    assert created.status_code == 200, created.text
    return str(created.json()["id"])


def _insert_internal_smoke_client(client: TestClient) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, color, created_at, updated_at)
        VALUES('client_smoke', '安装态冒烟客户', 'workspace-smoke', '测试', '内部测试', '不应进入战略陪伴', '测试', '#94a3b8', ?, ?)
        """,
        (NOW, NOW),
    )


def _insert_cached_insight(
    client: TestClient,
    *,
    client_id: str,
    insight_id: str,
    title: str,
    is_favorite: int,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO strategic_thought_insights(
            id, scope_type, client_id, client_name, project_module_id, project_module_name,
            title, insight_type, insight_text, future_judgment, recommended_action,
            evidence_summary, evidence_labels_json, source_refs_json, source_fingerprint,
            signal_score, raw_payload_json, is_favorite, is_deleted, generated_at, created_at, updated_at
        ) VALUES(?, 'client', ?, '战略陪伴边界客户', NULL, NULL, ?, 'strategic_shift',
            '这是一条旧的缓存洞察，用于确认刷新失败或资料不足时不会被误当成本次新结果。',
            '如果仍展示非收藏旧洞察，用户会误以为刷新已经基于最新材料完成判断。',
            '保留收藏内容，隐藏非收藏旧内容，等待下一次有足够材料后再生成。',
            '旧缓存测试依据',
            ?,
            ?,
            'old-fingerprint',
            70,
            '{}',
            ?,
            0,
            ?,
            ?,
            ?
        )
        """,
        (
            insight_id,
            client_id,
            title,
            json.dumps(["客户DNA", "事件线"], ensure_ascii=False),
            json.dumps(
                [
                    {"sourceType": "client_dna", "sourceId": f"{client_id}:profile", "label": "客户DNA"},
                    {"sourceType": "event_line", "sourceId": "event_boundary", "label": "事件线"},
                ],
                ensure_ascii=False,
            ),
            is_favorite,
            NOW,
            NOW,
            NOW,
        ),
    )


def _insert_strategic_context(client: TestClient, client_id: str) -> None:
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO client_dna_documents(
            client_id, module_key, title, markdown_content, normalized_text, summary,
            file_name, content_hash, source_kind, missing_info_json, updated_at, updated_by
        ) VALUES(?, 'strategy', '组织战略说明', '客户长期目标、项目结构和合作边界。', '客户长期目标、项目结构和合作边界。', '已有稳定战略说明。', 'strategy.md', 'hash_strategy', 'manual', '[]', ?, 'test')
        """,
        (client_id, NOW),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, kind, status, stage, summary, intent, current_blocker,
            recent_decision, next_step, evidence_count, primary_client_id,
            primary_client_name, created_at, updated_at
        ) VALUES('event_boundary', '边界测试事件线', 'project_line', 'active', '推进中',
            '近期任务和会议正在形成新的判断信号。', '确认项目推进边界。',
            '仍缺少足够稳定的证据。', '先不把旧判断当成本次新结论。',
            '等待模型输出新的可引用洞察。', 2, ?, '战略陪伴边界客户', ?, ?)
        """,
        (client_id, NOW, NOW),
    )


def test_brain_dashboard_excludes_private_tasks_and_internal_smoke_clients(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    db = client.app.state.app_state.db
    ensure_organization_sandbox_for_session(
        db,
        organization_id="org-dashboard-test",
        organization_name="战略陪伴测试组织",
    )
    set_active_sandbox_setting(
        db,
        "cloud_session_user",
        json.dumps(
            {
                "id": "dashboard-user",
                "organizationId": "org-dashboard-test",
                "email": "dashboard@example.com",
                "fullName": "战略陪伴测试成员",
                "primaryRole": "employee",
                "accountStatus": "approved",
                "membershipStatus": "approved",
            },
            ensure_ascii=False,
        ),
    )
    client_id = create_test_client_record(client)
    _insert_internal_smoke_client(client)

    shared = client.post(
        "/api/v1/tasks",
        json={
            "title": "共享推进任务",
            "desc": "这条任务可以进入组织统计。",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
            "scopeMode": "COLLAB_SHARED",
        },
    )
    assert shared.status_code == 200, shared.text
    private = client.post(
        "/api/v1/tasks",
        json={
            "title": "私人安排任务",
            "desc": "私人任务不应进入战略陪伴统计。",
            "priority": "normal",
            "listId": "list-0",
            "clientId": client_id,
            "scopeMode": "PERSONAL_ONLY",
        },
    )
    assert private.status_code == 200, private.text

    response = client.get("/api/v1/brain/dashboard")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["pulse"]["taskCount"] == 1
    assert "安装态冒烟客户" not in [item["name"] for item in payload["clients"]]


def test_refresh_strategic_thoughts_hides_unfavorite_cache_when_materials_are_insufficient(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    _insert_cached_insight(client, client_id=client_id, insight_id="thought_keep", title="收藏洞察", is_favorite=1)
    _insert_cached_insight(client, client_id=client_id, insight_id="thought_hide", title="非收藏旧洞察", is_favorite=0)

    response = client.post("/api/v1/strategic/thoughts/refresh", json={"clientId": client_id, "limit": 8})
    assert response.status_code == 200, response.text
    payload = response.json()

    assert [item["id"] for item in payload["items"]] == ["thought_keep"]
    assert client.app.state.app_state.db.scalar(
        "SELECT is_deleted FROM strategic_thought_insights WHERE id = 'thought_hide'"
    ) == 1
    assert client.app.state.app_state.db.scalar(
        "SELECT is_deleted FROM strategic_thought_insights WHERE id = 'thought_keep'"
    ) == 0


def test_refresh_strategic_thoughts_hides_unfavorite_cache_when_ai_returns_empty(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    client_id = create_test_client_record(client)
    _insert_strategic_context(client, client_id)
    _insert_cached_insight(client, client_id=client_id, insight_id="thought_keep", title="收藏洞察", is_favorite=1)
    _insert_cached_insight(client, client_id=client_id, insight_id="thought_hide", title="非收藏旧洞察", is_favorite=0)
    called = {"count": 0}

    def fake_generate_strategic_insights(*, context_pack: dict[str, object], limit: int) -> dict[str, object]:
        called["count"] += 1
        assert context_pack["stableBase"]
        assert context_pack["dynamicSignals"]
        return {"insights": []}

    monkeypatch.setattr(client.app.state.app_state.ai, "generate_strategic_insights", fake_generate_strategic_insights)

    response = client.post("/api/v1/strategic/thoughts/refresh", json={"clientId": client_id, "limit": 8})
    assert response.status_code == 200, response.text
    payload = response.json()

    assert called["count"] == 1
    assert [item["id"] for item in payload["items"]] == ["thought_keep"]
    assert client.app.state.app_state.db.scalar(
        "SELECT is_deleted FROM strategic_thought_insights WHERE id = 'thought_hide'"
    ) == 1
