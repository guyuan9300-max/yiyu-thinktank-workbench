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


def install_fake_strategic_insight_generator(client: TestClient) -> None:
    def fake_generate_strategic_insights(*, context_pack: dict, limit: int = 8) -> dict:
        stable = list(context_pack.get("stableBase") or [])
        dynamic = list(context_pack.get("dynamicSignals") or [])
        if not stable or not dynamic:
            return {"insights": []}
        refs = [
            {"sourceId": str(stable[0].get("sourceId") or ""), "label": str(stable[0].get("label") or ""), "detail": str(stable[0].get("title") or "")},
            {"sourceId": str(dynamic[0].get("sourceId") or ""), "label": str(dynamic[0].get("label") or ""), "detail": str(dynamic[0].get("title") or "")},
        ]
        return {
            "insights": [
                {
                    "title": "稳定资料和近期推进正在形成同一条判断线",
                    "insightType": "strategic_shift",
                    "insightText": "系统把客户稳定背景和近期事件线放在一起看，可以看到这个客户正在从零散推进转向更清晰的能力沉淀。这个判断不是来自单个任务，而是来自客户DNA与动态材料共同形成的方向。",
                    "futureJudgment": "如果后续会议和复盘继续补足证据，这条判断会变成可对外表达和可转任务推进的战略判断。",
                    "recommendedAction": "建议先整理一页判断稿，并把需要补充的证据挂到后续任务中。",
                    "evidenceSummary": "依据来自客户稳定背景和近期事件线。",
                    "evidenceLabels": [refs[0]["label"], refs[1]["label"]],
                    "sourceRefs": refs,
                    "signalScore": 86,
                }
            ]
        }

    setattr(client.app.state.app_state.ai, "generate_strategic_insights", fake_generate_strategic_insights)


def refresh_thoughts(client: TestClient, client_id: str) -> None:
    response = client.post("/api/v1/strategic/thoughts/refresh", json={"clientId": client_id, "limit": 8})
    assert response.status_code == 200, response.text


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
    assert not placeholder_line_cards
    assert all(item.get("status") != "waiting_evidence" for item in items)
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
    seed_core_insight_material(client, client_id)
    install_fake_strategic_insight_generator(client)
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

    refresh_thoughts(client, client_id)
    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20")
    assert response.status_code == 200, response.text
    payload = response.json()
    joined = "\n".join(
        f"{item.get('line', '')}\n{item.get('observation', '')}\n{item.get('suggestion', '')}"
        for item in payload.get("items", [])
    )
    assert "client_overview" not in joined
    assert any(item.get("insightText") for item in payload.get("items", []))


def test_waiting_evidence_cards_not_returned_for_thin_clients(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "缺口合并客户")
    create_placeholder_event_line(client, client_id, "资料待补线")

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20")
    assert response.status_code == 200, response.text
    items = [item for item in response.json()["items"] if item.get("clientId") == client_id]
    waiting_items = [item for item in items if item.get("status") == "waiting_evidence"]
    assert waiting_items == []
    assert items == []


def test_weak_evidence_never_gets_high_confidence(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, "弱证据客户")
    create_placeholder_event_line(client, client_id, "默认占位线")

    response = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}&limit=20")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    weak_items = [item for item in items if item.get("evidenceLevel") in {"none", "weak"}]
    assert all(item.get("status") != "waiting_evidence" for item in items)
    assert all(item.get("confidenceLevel") in {"none", "low"} for item in weak_items)


def test_all_clients_not_flooded_with_waiting_cards(tmp_path: Path):
    client = make_client(tmp_path)
    created_ids = [create_test_client_record(client, f"全局客户{i}") for i in range(1, 6)]
    for cid in created_ids:
        create_placeholder_event_line(client, cid, f"占位线-{cid[-4:]}")

    response = client.get("/api/v1/strategic/thoughts?limit=10")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert all(item.get("status") != "waiting_evidence" for item in items)
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
    assert "Conf " not in text
    assert "客户/项目" in text
    assert "clientId: thoughtClientId || null" in text
    assert "projectModuleId: thoughtProjectModuleId || null" in text
    assert "selectedClientId={thoughtClientId || null}" in text
    assert "这里展示系统基于客户资料提炼出的高价值分析信号。" not in text
    assert "为什么重要" not in text
    assert "依据来源" not in text
    thought_card_source = text.split("function ThoughtCard", 1)[1].split("function ThoughtsTab", 1)[0]
    assert "条线索" not in thought_card_source
    assert "refreshStrategicThoughts" in text
    assert "updateStrategicThoughtState" in text
    assert "数字资产中心" in text
    assert "项目认知" not in text
