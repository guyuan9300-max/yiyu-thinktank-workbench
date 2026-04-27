# 源码文件：`backend/tests/test_workspace_chat_regression.py`

- 导出时间：2026-04-20
- 说明：以下为当前工作区中的完整文件内容。

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as app_main
from app.main import create_app
from app.models import AiStructuredResponse
from app.services.ai import AiInvocationError
from app.services.knowledge_v2 import CitationMatch, RetrievalBundle


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def create_test_client_record(client: TestClient, name: str = "问答回归客户") -> str:
    response = client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "alias": name,
            "domain": "公益",
            "type": "战略陪伴",
            "intro": "用于问答主链回归测试",
            "stage": "推进中",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_scoped_task(client: TestClient, *, client_id: str, title: str, desc: str = "") -> str:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "desc": desc,
            "priority": "high",
            "listId": "list-0",
            "clientId": client_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def insert_candidate_judgment(
    client: TestClient,
    *,
    client_id: str,
    judgment_id: str,
    topic: str,
    summary: str,
) -> None:
    client.app.state.app_state.db.execute(
        """
        INSERT INTO judgment_versions(
            id, client_id, target_type, target_id, topic, version, status, summary,
            evidence_ids_json, context_pack_id, risk_level, confidence,
            created_at, updated_at, origin_type, authority_level, quality_tier,
            supersedes_id, source_snapshot_hash, stale_reason, invalidated_by
        )
        VALUES(
            ?, ?, 'client', ?, ?, 1, 'awaiting_review', ?, '[]', NULL, 'medium', 'medium',
            '2026-04-18T11:00:00', '2026-04-18T11:00:00', 'analysis', 'candidate', 'normalized',
            NULL, 'snapshot_regression_candidate', NULL, NULL
        )
        """,
        (
            judgment_id,
            client_id,
            client_id,
            topic,
            summary,
        ),
    )


def _build_retrieval_bundle(title_prefix: str, excerpts: list[str]) -> RetrievalBundle:
    citations = [
        CitationMatch(
            knowledge_document_id=f"kd_{index}",
            chunk_id=f"chunk_{index}",
            title=f"{title_prefix}{index}",
            excerpt=excerpt,
            score=0.86 - (index * 0.03),
            coverage=0.81,
            section_label="关键片段",
            source_stage="raw_chunk",
            drillthrough_used=True,
            matched_terms=["资料", "原文"],
            path=f"/tmp/{title_prefix}{index}.md",
        )
        for index, excerpt in enumerate(excerpts, start=1)
    ]
    return RetrievalBundle(
        citations=citations,
        coverage=0.81,
        retrieval_summary={
            "docHitCount": len(citations),
            "sectionHitCount": len(citations),
            "rawChunkHitCount": len(citations),
            "masterHitCount": len(citations),
            "surrogateHitCount": len(citations),
            "preferredCategories": ["组织与战略", "项目与业务"],
            "categoryCoverage": ["组织与战略", "项目与业务"],
        },
        context_text="",
        matched_terms=["资料", "原文"],
        failure_reason=None,
    )


def test_workspace_chat_intro_timeout_still_returns_deliverable_intro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="日慈基金会")
    create_scoped_task(client, client_id=client_id, title="补齐项目介绍", desc="补齐项目介绍与会议纪要引用。")

    retrieval_bundle = _build_retrieval_bundle(
        "日慈基金会资料",
        [
            "日慈基金会聚焦教师赋能，围绕学校协同与长期能力建设开展项目。",
            "心盛计划聚焦青少年社群与心理健康支持，强调阶段性陪伴机制。",
            "繁星计划强调生态协同、传播联动与项目执行节奏。",
            "一季度沟通会议纪要明确下一阶段需要补齐负责人和里程碑。",
        ],
    )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: retrieval_bundle)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AiInvocationError("doubao", "read timeout")),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "介绍日慈基金会，给一版简洁清晰的项目资料，并引用原文。"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["answerIntent"] in {"intro_profile", "project_intro"}
    assert payload["retrievalSummary"]["answerIntent"] in {"intro_profile", "project_intro"}
    assert payload["retrievalSummary"]["retrievalDecisionReason"] in {
        "intro_query_needs_evidence",
        "project_intro_needs_evidence",
    }
    assert payload["retrievalSummary"]["pageContextQuality"] in {"none", "weak", "usable", "strong"}
    assert isinstance(payload["retrievalSummary"]["stateObjectCount"], int)
    assert payload["retrievalSummary"]["rawFallbackTriggered"] is True
    assert payload["retrievalSummary"]["legacyFallbackUsed"] in {True, False}
    assert "日慈基金会" in payload["content"]
    assert any(token in payload["content"] for token in ("教师赋能", "心盛计划", "繁星计划"))
    assert "当前最值得抓住的原始观察包括" not in payload["content"]
    assert "正式长回答阶段没有成功完成" not in payload["content"]
    assert len(payload["evidence"]) >= 3


def test_workspace_chat_meeting_summary_forces_evidence_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="会议证据回归客户")
    create_scoped_task(client, client_id=client_id, title="跟进会议行动项", desc="补齐负责人和截止时间。")

    retrieval_bundle = _build_retrieval_bundle(
        "一季度沟通会议纪要",
        [
            "会议重点是项目推进节奏与资源分工，明确下周完成材料对齐。",
            "会议决定先收敛范围，再进入执行协同，避免并行扩散。",
            "行动项包括：确认负责人、更新时间表、同步风险清单。",
        ],
    )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: retrieval_bundle)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="最近会议已形成阶段决定，并明确了下一步行动与风险待确认项。",
            judgment="会议类问题应以会议纪要与行动项为主来源。",
            analysis="这次回答已经命中会议与原文证据。",
            actions="继续核对负责人、截止时间和风险项。",
            timeline="本周内完成对齐。",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "提炼最新会议纪要"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerIntent"] == "meeting_summary"
    assert payload["retrievalSummary"]["answerIntent"] == "meeting_summary"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "meeting_summary_needs_evidence"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] != "state_first_default"
    assert payload["retrievalSummary"]["retrievalDeferred"] is False
    assert payload["retrievalSummary"]["rawChunkHitCount"] > 0
    assert "会议" in payload["content"]
    assert any(token in payload["content"] for token in ("决定", "行动", "风险", "待确认"))


def test_workspace_chat_next_actions_timeout_uses_three_section_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="下一步回归客户")
    create_scoped_task(client, client_id=client_id, title="确认行动负责人", desc="本周补齐负责人和截止时间。")
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_next_action_candidate",
        topic="候选判断",
        summary="当前推进节奏仍需会议与任务证据交叉确认。",
    )

    retrieval_bundle = _build_retrieval_bundle(
        "行动跟进资料",
        [
            "后续安排包括：本周确认负责人、下周同步风险和未决问题。",
            "会议行动项强调先补证据，再推进执行分工。",
            "任务记录显示仍有两项待办尚未确认截止时间。",
        ],
    )

    monkeypatch.setattr(app_main, "retrieve_knowledge_bundle", lambda *_args, **_kwargs: retrieval_bundle)
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_chat_response",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AiInvocationError("doubao", "read timeout")),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "接下来这个客户要做什么？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerMode"] == "grounded_fallback"
    assert payload["answerIntent"] == "next_actions"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "next_actions_needs_evidence"
    assert "一、已经比较明确的行动" in payload["content"]
    assert "二、需要先补证据 / 补沟通的信息" in payload["content"]
    assert "三、系统里的候选提醒（暂不当成确定事实）" in payload["content"]
    assert any(token in payload["content"] for token in ("负责人", "风险", "待确认", "行动"))


def test_workspace_chat_official_registry_keeps_candidate_out_of_official_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = make_client(tmp_path)
    client_id = create_test_client_record(client, name="正式判断边界客户")
    insert_candidate_judgment(
        client,
        client_id=client_id,
        judgment_id="judgment_candidate_only",
        topic="候选判断",
        summary="当前只有候选判断，尚未进入 approved 层。",
    )

    monkeypatch.setattr(
        app_main,
        "retrieve_knowledge_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("official registry query should stay state-only")),
    )
    monkeypatch.setattr(
        client.app.state.app_state.ai,
        "generate_workspace_state_response",
        lambda *_args, **_kwargs: AiStructuredResponse(
            content="当前暂无正式判断，候选判断需继续补证据。",
            judgment="正式层为空。",
            analysis="候选判断与正式判断边界清晰。",
            actions="继续补证据后再申请审批。",
            timeline="补齐后再推进。",
        ),
    )

    response = client.post(
        f"/api/v1/clients/{client_id}/workspace/chat",
        json={"prompt": "现在有哪些正式判断？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["answerIntent"] == "official_judgment_registry"
    assert payload["retrievalSummary"]["retrievalDecisionReason"] == "official_registry_requested"
    assert payload["retrievalSummary"]["retrievalDeferred"] is True
    assert payload["retrievalSummary"]["rawFallbackTriggered"] is False
    assert payload["stateAnswerSections"]["official"] == []
    assert payload["stateAnswerSections"]["candidate"]

```
