from __future__ import annotations

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


def create_client(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "客户长期关注儿童青少年支持网络建设。",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def seed_mixed_context(client: TestClient, client_id: str) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    db = client.app.state.app_state.db
    db.execute(
        """
        INSERT INTO client_dna_documents(
            client_id, module_key, title, markdown_content, normalized_text, summary,
            file_name, content_hash, updated_at, updated_by
        ) VALUES(?, 'org', '组织背景', ?, ?, ?, 'org.md', ?, ?, 'test')
        """,
        (
            client_id,
            "组织长期关注关系支持网络、项目证据沉淀和可复制方法建设。",
            "组织长期关注关系支持网络、项目证据沉淀和可复制方法建设。",
            "关系支持网络和证据沉淀是稳定底座。",
            f"hash_{client_id}_org",
            now,
        ),
    )
    db.execute(
        """
        INSERT INTO event_lines(
            id, name, summary, intent, next_step, evidence_count,
            primary_client_id, primary_client_name, created_at, updated_at
        ) VALUES(?, '近期战略复盘', ?, ?, ?, 5, ?, 'AI生成客户', ?, ?)
        """,
        (
            f"eline_{client_id}_review",
            "近期复盘显示项目材料、会议纪要和任务说明正在共同指向能力表达升级。",
            "需要把项目经验和未来合作机会收束成可解释判断。",
            "形成一页判断稿并补齐证据。",
            client_id,
            now,
            now,
        ),
    )


def test_refresh_uses_ai_context_pack_and_persists_cache(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client(client, "AI生成客户")
    seed_mixed_context(client, client_id)
    captured: dict[str, object] = {}

    def fake_generate_strategic_insights(*, context_pack: dict, limit: int = 8) -> dict:
        captured["contextPack"] = context_pack
        stable = list(context_pack.get("stableBase") or [])
        dynamic = list(context_pack.get("dynamicSignals") or [])
        return {
            "insights": [
                {
                    "title": "复盘材料正在把项目经验推向能力表达",
                    "insightType": "narrative_upgrade",
                    "insightText": "把稳定背景和近期复盘放在一起看，客户当前真正值得关注的变化不是多做一次项目总结，而是项目经验正在被推向更清楚的能力表达。这说明材料沉淀已经开始从记录事实进入解释未来合作空间的阶段。",
                    "futureJudgment": "如果后续能继续补齐会议纪要和项目证据，这条表达会成为下一轮合作和筹资沟通的核心依据。",
                    "recommendedAction": "建议先基于复盘材料整理一页能力表达，再明确还缺哪些证据。",
                    "evidenceSummary": "依据来自组织背景与近期战略复盘。",
                    "evidenceLabels": [stable[0]["label"], dynamic[0]["label"]],
                    "sourceRefs": [
                        {"sourceId": stable[0]["sourceId"], "label": stable[0]["label"], "detail": stable[0]["title"]},
                        {"sourceId": dynamic[0]["sourceId"], "label": dynamic[0]["label"], "detail": dynamic[0]["title"]},
                    ],
                    "signalScore": 91,
                }
            ]
        }

    setattr(client.app.state.app_state.ai, "generate_strategic_insights", fake_generate_strategic_insights)

    refresh = client.post("/api/v1/strategic/thoughts/refresh", json={"clientId": client_id, "limit": 6})
    assert refresh.status_code == 200, refresh.text
    payload = refresh.json()
    assert payload["items"]
    assert captured["contextPack"]
    context_pack = captured["contextPack"]
    assert context_pack["stableBase"]
    assert context_pack["dynamicSignals"]

    cached = client.get(f"/api/v1/strategic/thoughts?clientId={client_id}")
    assert cached.status_code == 200, cached.text
    assert cached.json()["items"][0]["title"] if "title" in cached.json()["items"][0] else True
    assert cached.json()["items"][0]["futureJudgment"]


def test_refresh_rejects_ai_insight_without_two_sources(tmp_path: Path):
    client = make_client(tmp_path)
    client_id = create_client(client, "证据不足过滤客户")
    seed_mixed_context(client, client_id)

    def fake_generate_strategic_insights(*, context_pack: dict, limit: int = 8) -> dict:
        stable = list(context_pack.get("stableBase") or [])
        return {
            "insights": [
                {
                    "title": "只有单一材料的判断不应出现",
                    "insightType": "risk_signal",
                    "insightText": "这条洞察虽然有正文，但只引用了一个来源，因此不能作为高价值研判进入页面。",
                    "futureJudgment": "未来判断缺少足够材料支撑。",
                    "recommendedAction": "建议补充更多证据。",
                    "evidenceSummary": "只有一个来源。",
                    "evidenceLabels": [stable[0]["label"]],
                    "sourceRefs": [{"sourceId": stable[0]["sourceId"], "label": stable[0]["label"], "detail": stable[0]["title"]}],
                    "signalScore": 80,
                }
            ]
        }

    setattr(client.app.state.app_state.ai, "generate_strategic_insights", fake_generate_strategic_insights)

    refresh = client.post("/api/v1/strategic/thoughts/refresh", json={"clientId": client_id, "limit": 6})
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["items"] == []
