from __future__ import annotations

import json
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


def seed_core_insight_material(client: TestClient, client_id: str) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO client_dna_documents(
            client_id, module_key, title, markdown_content, normalized_text, summary,
            file_name, content_hash, updated_at, updated_by
        ) VALUES(?, 'strategy', '战略背景', ?, ?, ?, 'strategy.md', ?, ?, 'test')
        """,
        (
            client_id,
            "客户正在从项目服务组织转向关系生态组织，核心是关系支持、数据资产和第二曲线。",
            "客户正在从项目服务组织转向关系生态组织，核心是关系支持、数据资产和第二曲线。",
            "关系生态、数据资产、第二曲线已经成为客户当前战略背景。",
            f"hash_{client_id}_strategy",
            now,
        ),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, summary, intent, next_step, evidence_count,
            primary_client_id, primary_client_name, created_at, updated_at
        ) VALUES(?, '战略转型事件线', ?, ?, ?, 3, ?, '测试客户', ?, ?)
        """,
        (
            f"eline_{client_id}_strategy",
            "战略陪伴进入关系生态与数据资产沉淀阶段，不再只是项目执行。",
            "需要把核心项目统一到对象、处境、动作、机制、证据的表达中。",
            "先重写核心项目表达，再推进工具和传播。",
            client_id,
            now,
            now,
        ),
    )


def seed_rici_like_insight_material(client: TestClient, client_id: str) -> None:
    seed_core_insight_material(client, client_id)
    now = datetime.now().replace(microsecond=0).isoformat()
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO client_dna_documents(
            client_id, module_key, title, markdown_content, normalized_text, summary,
            file_name, content_hash, updated_at, updated_by
        ) VALUES(?, 'business', '项目组合', ?, ?, ?, 'business.md', ?, ?, 'test')
        """,
        (
            client_id,
            "教师赋能项目包含带领者培训、实践带领和认证入池；心盛计划面向青年社群与关怀员培训，是第二曲线验证场；对外介绍需要从项目罗列升级为战略能力表达。",
            "教师赋能项目包含带领者培训、实践带领和认证入池；心盛计划面向青年社群与关怀员培训，是第二曲线验证场；对外介绍需要从项目罗列升级为战略能力表达。",
            "教师赋能、心盛计划、品牌传播和对外介绍共同构成战略转型素材。",
            f"hash_{client_id}_business",
            now,
        ),
    )
    rows = [
        (
            "teacher",
            "教师赋能项目进度",
            "教师赋能项目已经跑通报名筛选、体验培训、录播学习、小组演练、实践带领、入池认证，当前要沉淀成效证据。",
            "下一步做一轮小样本深复盘。",
        ),
        (
            "xingsheng",
            "心盛计划推进",
            "心盛计划正在验证青年社群、关怀员培训、内容沉淀和数据复盘，属于第二曲线验证场。",
            "先明确心盛证明了什么能力。",
        ),
        (
            "singapore",
            "新加坡合作窗口",
            "张真正在推进新加坡一对一咖啡聊天项目资助，这是关系支持系统产品化和筹资化的机会窗口。",
            "先用一页纸说明该合作在关系生态战略中的位置。",
        ),
        (
            "brand",
            "使命愿景与对外介绍升级",
            "使命愿景价值观确认后，需要把对外项目介绍和机构介绍从项目罗列升级为战略能力表达。",
            "重写对外介绍一级结构。",
        ),
    ]
    for suffix, name, summary, next_step in rows:
        db.execute(
            """
            INSERT INTO event_lines(
                id, name, summary, intent, next_step, evidence_count,
                primary_client_id, primary_client_name, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 4, ?, '日慈模拟客户', ?, ?)
            """,
            (
                f"eline_{client_id}_{suffix}",
                name,
                summary,
                summary,
                next_step,
                client_id,
                now,
                now,
            ),
        )
    db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence, created_at, updated_at
        ) VALUES(?, ?, 'client', ?, 'client_overview', 1, 'awaiting_review', ?, '[]', NULL, 'medium', 'medium', ?, ?)
        """,
        (
            f"judgment_{client_id}_overview",
            client_id,
            client_id,
            "客户正在从课程服务交付转向关系生态建设，教师赋能、心盛计划、新加坡合作和品牌叙事需要被收束到同一套战略表达。",
            now,
            now,
        ),
    )


def seed_narrative_and_digital_material(client: TestClient, client_id: str) -> None:
    seed_core_insight_material(client, client_id)
    now = datetime.now().replace(microsecond=0).isoformat()
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO client_dna_documents(
            client_id, module_key, title, markdown_content, normalized_text, summary,
            file_name, content_hash, updated_at, updated_by
        ) VALUES(?, 'narrative', '项目介绍与数字化背景', ?, ?, ?, 'narrative.md', ?, ?, 'test')
        """,
        (
            client_id,
            "项目介绍、机构介绍、品牌传播和官网表达需要升级；数字化、数据、工具、业务流和仪表盘需要先定义对象。",
            "项目介绍、机构介绍、品牌传播和官网表达需要升级；数字化、数据、工具、业务流和仪表盘需要先定义对象。",
            "对外介绍和数字化都进入收束阶段。",
            f"hash_{client_id}_narrative",
            now,
        ),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, summary, intent, next_step, evidence_count,
            primary_client_id, primary_client_name, created_at, updated_at
        ) VALUES(?, '对外介绍与数字化收束', ?, ?, ?, 5, ?, '为爱黔行', ?, ?)
        """,
        (
            f"eline_{client_id}_narrative",
            "品牌传播、项目介绍和数字化工具都需要围绕项目成效证据重新组织。",
            "先确认对外表达结构，再定义数据对象和仪表盘字段。",
            "重写项目介绍一级结构，补齐数字化证据字段。",
            client_id,
            now,
            now,
        ),
    )


def seed_polluted_analysis_run(client: TestClient, client_id: str, question: str) -> str:
    now = datetime.now().replace(microsecond=0).isoformat()
    db = client.app.state.app_state.db
    thread_id = f"thread_{client_id}_polluted"
    user_message_id = f"msg_user_{client_id}_polluted"
    assistant_message_id = f"msg_assistant_{client_id}_polluted"
    run_id = f"analysis_{client_id}_polluted"
    db.execute(
        "INSERT INTO chat_threads(id, client_id, title, created_at, updated_at) VALUES(?, ?, '污染分析线程', ?, ?)",
        (thread_id, client_id, now, now),
    )
    db.execute(
        "INSERT INTO chat_messages(id, thread_id, role, content, evidence_json, created_at) VALUES(?, ?, 'user', ?, '[]', ?)",
        (user_message_id, thread_id, question, now),
    )
    db.execute(
        "INSERT INTO chat_messages(id, thread_id, role, content, evidence_json, created_at) VALUES(?, ?, 'assistant', ?, '[]', ?)",
        (
            assistant_message_id,
            thread_id,
            "为爱黔行需要围绕项目介绍、品牌传播、数字化工具和证据字段完成表达收束。",
            now,
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
            ?, ?, ?, ?, ?, ?, 'completed', 'completed', 100, 0, 100, '已完成', 900,
            '{"masterHitCount": 1, "surrogateHitCount": 0, "evidenceList": []}',
            ?, '{}', 'ready', 'ready', 'grounded_answer', 1, 'analysis-center', NULL, '{}',
            ?, ?
        )
        """,
        (
            run_id,
            client_id,
            thread_id,
            user_message_id,
            assistant_message_id,
            question,
            "为爱黔行需要围绕项目介绍、品牌传播、数字化工具和证据字段完成表达收束。",
            now,
            now,
        ),
    )
    return run_id


def _first_client_thought(payload: dict, client_id: str) -> dict:
    for item in payload.get("items", []):
        if item.get("scope") == "client" and item.get("clientId") == client_id:
            return item
    raise AssertionError(f"未找到 client={client_id} 的思考卡")


def install_fake_strategic_insight_generator(client: TestClient, *, count: int = 1, banned_title: bool = False) -> None:
    def fake_generate_strategic_insights(*, context_pack: dict, limit: int = 8) -> dict:
        stable = list(context_pack.get("stableBase") or [])
        dynamic = list(context_pack.get("dynamicSignals") or [])
        sources = stable + dynamic
        selected: list[dict] = []
        seen_labels: set[str] = set()
        for source in sources:
            if not isinstance(source, dict):
                continue
            label = str(source.get("label") or "")
            if label in seen_labels:
                continue
            selected.append(source)
            seen_labels.add(label)
            if len(selected) >= 3:
                break
        if len(selected) < 2:
            return {"insights": []}
        refs = [
            {"sourceId": str(source.get("sourceId") or ""), "label": str(source.get("label") or ""), "detail": str(source.get("title") or "")}
            for source in selected[:3]
        ]
        labels = [ref["label"] for ref in refs]
        titles = [
            "关系支持能力正在成为新的战略承载位",
            "项目证据沉淀会决定下一轮合作空间",
            "对外沟通需要先讲清能力而不是活动",
            "数字化价值取决于业务对象是否先被定义",
        ]
        if banned_title:
            titles[0] = "关键事项依赖少数关键人，战略节奏需要收束"
        insights = []
        for index, title in enumerate(titles[: max(1, min(count, limit))]):
            insights.append(
                {
                    "title": title,
                    "insightType": ["strategic_shift", "opportunity_window", "narrative_upgrade", "operating_model"][index % 4],
                    "insightText": (
                        "系统把稳定背景和最近推进材料放在一起看，能看到这个客户的关键变化并不只是某个任务推进，"
                        "而是项目说明、事件线和历史分析正在共同指向一组需要被组织化表达的能力。"
                        "这条洞察保留了当前处境、约束和可行动空间，适合作为下一步判断入口。"
                    ),
                    "futureJudgment": "如果后续会议和复盘继续沉淀同类证据，这条能力会从经验判断进入可对外说明、可筹资、可复制的阶段。",
                    "recommendedAction": "建议先围绕这条能力整理一页判断稿，再把需要补充的证据挂到项目任务里。",
                    "evidenceSummary": "依据来自稳定底座与近期动态材料的共同指向。",
                    "evidenceLabels": labels,
                    "sourceRefs": refs,
                    "signalScore": 88 - index,
                }
            )
        return {"insights": insights}

    setattr(client.app.state.app_state.ai, "generate_strategic_insights", fake_generate_strategic_insights)


def refresh_thoughts(client: TestClient, client_id: str, *, project_module_id: str | None = None, limit: int = 8) -> dict:
    response = client.post(
        "/api/v1/strategic/thoughts/refresh",
        json={"clientId": client_id, "projectModuleId": project_module_id, "limit": limit},
    )
    assert response.status_code == 200, response.text
    return response.json()


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
    seed_core_insight_material(client, client_a)
    install_fake_strategic_insight_generator(client)
    refresh_thoughts(client, client_a)

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_a}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert any(item.get("clientId") == client_a for item in payload.get("items", []))
    assert all(item.get("clientId") != client_b for item in payload.get("items", []))


def test_strategic_thoughts_insufficient_data_returns_no_placeholder_insights(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "资料不足客户")

    first = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    second = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    first_payload = first.json()
    second_payload = second.json()

    client_items = [item for item in first_payload.get("items", []) if item.get("clientId") == client_id]
    second_client_items = [item for item in second_payload.get("items", []) if item.get("clientId") == client_id]
    assert client_items == []
    assert second_client_items == []


def test_strategic_thought_review_confirm_persists(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "确认持久化客户")
    seed_core_insight_material(client, client_id)
    install_fake_strategic_insight_generator(client)
    refresh_thoughts(client, client_id)

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
    seed_core_insight_material(client, client_id)
    install_fake_strategic_insight_generator(client)
    refresh_thoughts(client, client_id)

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


def test_strategic_thoughts_rich_client_returns_multiple_insight_types(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "日慈模拟客户")
    seed_rici_like_insight_material(client, client_id)
    install_fake_strategic_insight_generator(client, count=4)
    refresh_thoughts(client, client_id, limit=8)

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20")
    assert response.status_code == 200, response.text
    items = response.json()["items"]

    insight_types = {item.get("insightType") for item in items}
    assert {"strategic_shift", "operating_model", "opportunity_window", "narrative_upgrade"} <= insight_types
    assert all(item.get("status") != "waiting_evidence" for item in items)
    for item in items:
        assert item.get("insightText")
        assert item.get("whyItMatters")
        assert item.get("recommendedAction")
        assert len(item.get("evidenceLabels") or []) >= 2
        assert item.get("signalScore", 0) > 0


def test_strategic_thoughts_do_not_leak_other_client_material_or_template_names(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "为爱黔行")
    create_test_client_record(client, "日慈基金会")
    seed_narrative_and_digital_material(client, client_id)
    polluted_run_id = seed_polluted_analysis_run(client, client_id, "介绍日慈基金会")
    install_fake_strategic_insight_generator(client)
    refresh_thoughts(client, client_id)

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20&includeDismissed=true")
    assert response.status_code == 200, response.text
    items = response.json()["items"]

    assert items
    joined = "\n".join(
        "\n".join(
            [
                str(item.get("line", "")),
                str(item.get("insightText", "")),
                str(item.get("whyItMatters", "")),
                str(item.get("recommendedAction", "")),
                str(item.get("evidenceSummary", "")),
                str(item.get("sources", "")),
            ]
        )
        for item in items
    )
    assert "日慈" not in joined
    assert all(
        source.get("sourceId") != polluted_run_id
        for item in items
        for source in item.get("sources", [])
    )


def test_strategic_thoughts_get_does_not_generate_without_refresh(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "缓存语义客户")
    seed_core_insight_material(client, client_id)

    def fail_generate(*, context_pack: dict, limit: int = 8) -> dict:
        raise AssertionError("GET should not invoke AI")

    setattr(client.app.state.app_state.ai, "generate_strategic_insights", fail_generate)
    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


def test_strategic_thought_refresh_filters_legacy_template_title(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "模板过滤客户")
    seed_core_insight_material(client, client_id)
    install_fake_strategic_insight_generator(client, banned_title=True)

    payload = refresh_thoughts(client, client_id)
    assert payload["items"] == []


def test_strategic_thoughts_soft_delete_legacy_cached_titles(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "旧缓存客户")
    now = datetime.now().replace(microsecond=0).isoformat()
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO strategic_thought_insights(
            id, scope_type, client_id, client_name, title, insight_type, insight_text,
            future_judgment, recommended_action, evidence_summary, evidence_labels_json,
            source_refs_json, source_fingerprint, signal_score, raw_payload_json,
            is_favorite, is_deleted, generated_at, created_at, updated_at
        ) VALUES(
            'legacy_cached_template', 'client', ?, '旧缓存客户', '关键事项依赖少数关键人，战略节奏需要收束',
            'risk_signal', '旧模板正文', '旧模板未来判断', '旧模板动作', '旧模板证据',
            ?, ?, 'fingerprint', 90, '{}', 1, 0, ?, ?, ?
        )
        """,
        (
            client_id,
            json.dumps(["客户DNA", "事件线"], ensure_ascii=False),
            json.dumps(
                [
                    {"sourceType": "client_dna", "sourceId": f"{client_id}:dna", "label": "客户DNA"},
                    {"sourceType": "event_line", "sourceId": f"eline_{client_id}", "label": "事件线"},
                ],
                ensure_ascii=False,
            ),
            now,
            now,
            now,
        ),
    )

    hidden = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["items"] == []

    visible = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&includeDeleted=true")
    assert visible.status_code == 200, visible.text
    item = next((entry for entry in visible.json()["items"] if entry["id"] == "legacy_cached_template"), None)
    assert item is not None
    assert item["isDeleted"] is True


def test_strategic_thought_favorite_and_delete_state(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "收藏删除客户")
    seed_core_insight_material(client, client_id)
    install_fake_strategic_insight_generator(client)
    payload = refresh_thoughts(client, client_id)
    thought = _first_client_thought(payload, client_id)

    favorite = client.post(f"/api/v1/strategic/thoughts/{thought['id']}/state", json={"action": "favorite"})
    assert favorite.status_code == 200, favorite.text
    assert favorite.json()["isFavorite"] is True

    delete = client.post(f"/api/v1/strategic/thoughts/{thought['id']}/state", json={"action": "delete"})
    assert delete.status_code == 200, delete.text
    assert delete.json()["isDeleted"] is True

    hidden = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert hidden.status_code == 200, hidden.text
    assert all(item["id"] != thought["id"] for item in hidden.json()["items"])

    visible = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&includeDeleted=true")
    assert visible.status_code == 200, visible.text
    restored = next((item for item in visible.json()["items"] if item["id"] == thought["id"]), None)
    assert restored is not None
    assert restored["isFavorite"] is True
    assert restored["isDeleted"] is True


def test_strategic_thought_project_scope_uses_project_material(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "项目范围客户")
    seed_core_insight_material(client, client_id)
    now = datetime.now().replace(microsecond=0).isoformat()
    db = client.app.state.app_state.db
    project_id = "module_teacher_scope"
    db.execute(
        """
        INSERT INTO project_modules(
            id, client_id, name, alias, goal, description, deliverables_json, keywords_json, created_at, updated_at
        ) VALUES(?, ?, '教师赋能', '', '形成教师支持网络', '教师项目说明', '[]', '["教师赋能"]', ?, ?)
        """,
        (project_id, client_id, now, now),
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, title, description, status, priority, list_id, owner_name, ddl, source_type, source_id,
            tags_json, client_id, project_module_id, created_at, updated_at
        ) VALUES(
            'task_teacher_scope', '教师赋能复盘', '教师赋能需要沉淀复盘证据', 'todo', 'normal', 'list-1',
            '顾问', '', 'manual', '', '[]', ?, ?, ?, ?
        )
        """,
        (client_id, project_id, now, now),
    )
    install_fake_strategic_insight_generator(client)

    payload = refresh_thoughts(client, client_id, project_module_id=project_id)
    assert payload["selectedProjectModuleId"] == project_id
    thought = next((item for item in payload["items"] if item["scope"] == "project"), None)
    assert thought is not None
    assert thought["scope"] == "project"
    assert thought["projectModuleId"] == project_id
    source_ids = {source["sourceId"] for source in thought["sources"]}
    assert project_id in source_ids
