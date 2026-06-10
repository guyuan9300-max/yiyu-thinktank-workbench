from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    client.__enter__()
    return client


def test_growth_workbench_understands_agreement_task(tmp_path: Path):
    client = make_client(tmp_path)

    created_client = client.post(
        "/api/v1/clients",
        json={
            "name": "测试论坛A",
            "alias": "测试论坛A",
            "domain": "公益合作",
            "type": "client",
            "intro": "测试论坛A 当前正在推进战略合作说明与协议边界确认。",
            "stage": "推进中",
        },
    )
    assert created_client.status_code == 200
    client_id = created_client.json()["id"]

    board = client.get("/api/v1/tasks")
    assert board.status_code == 200
    default_list_id = board.json()["lists"][0]["id"]

    created_task = client.post(
        "/api/v1/tasks",
        json={
            "title": "下午找 测试论坛A 沟通战略合作协议",
            "desc": "需要和冯梅老师对齐战略合作协议的边界、待确认点和下一轮修改动作。",
            "priority": "high",
            "listId": default_list_id,
            "dueDate": "2026-03-24",
            "ddl": "2026-03-24",
            "clientId": client_id,
            "ownerName": "测试用户",
            "collaboratorIds": [],
            "tagIds": [],
            "businessCategory": "strategic_accompaniment",
            "currentBlocker": "缺上次沟通纪要和条款差异说明",
            "nextAction": "先整理本次必须确认的 3 个条款，再和冯梅老师沟通",
            "recentDecision": "本次先确认合作边界，不直接承诺资源与交付",
            "evidenceCount": 1,
        },
    )
    assert created_task.status_code == 200
    task_id = created_task.json()["id"]

    uploaded = client.post(
        f"/api/v1/tasks/{task_id}/attachments",
        files={"file": ("agreement-draft.md", b"# 测试论坛A \xe5\x8d\x8f\xe8\xae\xae\xe8\x8d\x89\xe6\xa1\x88", "text/markdown")},
        data={"clientId": client_id, "taskTitle": "下午找 测试论坛A 沟通战略合作协议"},
    )
    assert uploaded.status_code == 200

    snapshot = client.get("/api/v1/growth/workbench")
    assert snapshot.status_code == 200
    payload = snapshot.json()

    matching = next((item for item in payload["tasks"] if item.get("linkedTaskId") == task_id), None)
    assert matching is not None
    assert matching["taskIntent"]["taskKind"] in {"agreement_alignment", "external_communication"}
    assert any(risk in matching["taskIntent"]["riskTypes"] for risk in ("boundary_risk", "commitment_risk", "negotiation_risk"))
    assert matching["universalSkills"]
    assert matching["universalSkills"][0]["sourceKind"] == "rule"
    assert matching["projectContextPack"]["taskNotes"] or matching["projectContextPack"]["clientSummary"]
    assert matching["projectContextPack"]["attachments"]
    action_groups = {item["phaseGroup"] for item in matching["actionPlan"]}
    assert {"before", "during", "after"}.issubset(action_groups)
