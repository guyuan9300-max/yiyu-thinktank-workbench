from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.event_line_timeline import build_event_line_timeline_nodes


def _attachment(
    attachment_id: str,
    title: str,
    preview: str,
    *,
    task_id: str = "",
    created_at: str = "2026-04-02T09:55:00",
    size: int = 1200,
) -> dict:
    return {
        "id": attachment_id,
        "taskId": task_id,
        "documentId": f"doc_{attachment_id}",
        "sourceKind": "task_attachment" if task_id else "event_line_attachment",
        "title": title,
        "kind": title.rsplit(".", 1)[-1] if "." in title else "file",
        "mimeType": "image/jpeg" if title.endswith(".jpeg") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "sizeBytes": size,
        "downloadUrl": f"/api/public/task-attachments/{attachment_id}",
        "actorName": "顾源源",
        "createdAt": created_at,
        "parseStatus": "ready",
        "parsedPreview": preview,
        "chunkCount": 3,
        "sectionCount": 2,
    }


def test_dici_fixture_generates_business_timeline_nodes() -> None:
    event_line = {
        "id": "eline_dici",
        "name": "日慈战略陪伴",
        "status": "paused",
        "stage": "本周推进",
        "summary": "日慈基金会Q1三个项目复盘中，教师赋能项目设计待补完善",
        "intent": "承接日慈基金会一季度多个项目复盘后的判断、材料和后续动作。",
        "ownerName": "顾源源",
        "primaryClientName": "日慈基金会",
        "createdAt": "2026-03-22T16:38:00",
        "updatedAt": "2026-04-22T16:38:00",
    }
    tasks = [
        {
            "id": "task_training",
            "title": "跟进日慈基金会继续推进当前轮次的带领者培训、演练与实践带领，并记录运行中的关键卡点",
            "desc": "继续观察培训、演练、实践带领和反馈。",
            "status": "doing",
            "ownerName": "顾源源",
            "creatorName": "顾源源",
            "createdAt": "2026-04-02T21:00:00",
            "updatedAt": "2026-04-18T11:00:00",
        },
        {
            "id": "task_reimburse",
            "title": "日慈报销",
            "desc": "报销任务测试首先发票和收据先存在本地铺，然后后台继续上传这个功能需要继续优化。",
            "status": "done",
            "ownerName": "佳乐",
            "creatorName": "顾源源",
            "createdAt": "2026-04-15T11:45:00",
            "updatedAt": "2026-04-15T12:05:00",
        },
    ]
    activities = [
        {
            "id": "act_create",
            "sourceType": "manual_note",
            "sourceId": "eline_dici",
            "happenedAt": "2026-03-22T16:38:00",
            "actorName": "顾源源",
            "title": "创建事件线",
            "summary": "创建事件线：日慈战略陪伴",
            "metadata": {"eventType": "event_line_created"},
        },
        {
            "id": "act_training_created",
            "sourceType": "task_activity",
            "sourceId": "task_training",
            "happenedAt": "2026-04-02T21:00:00",
            "actorName": "顾源源",
            "title": "新增任务",
            "summary": "创建任务：跟进日慈基金会继续推进当前轮次的带领者培训、演练与实践带领，并记录运行中的关键卡点",
            "metadata": {"taskId": "task_training", "eventType": "created"},
        },
        {
            "id": "act_training_update",
            "sourceType": "task_activity",
            "sourceId": "task_training",
            "happenedAt": "2026-04-18T11:00:00",
            "actorName": "顾源源",
            "title": "更新任务",
            "summary": "记录当前轮次带领者培训运行中的关键卡点。",
            "metadata": {"taskId": "task_training", "eventType": "updated"},
        },
    ]
    attachments = [
        _attachment(
            "teacher_1",
            "日慈基金会-教师赋能一季度沟通会议纪要-整理版.docx",
            "日慈基金会「教师赋能」一季度沟通会会议纪要。带领者培养路径已经形成首版闭环，需要补齐项目设计、成效证据和数字化试点。",
        ),
        _attachment(
            "teacher_2",
            "日慈基金会-教师赋能一季度沟通会议纪要-整理版.docx",
            "日慈基金会「教师赋能」一季度沟通会会议纪要。工具链路较碎，成效表达还停留在过程指标。",
            size=1200,
        ),
        _attachment(
            "xinsheng",
            "日慈基金会-心盛计划一季度沟通会议纪要-整理版.docx",
            "日慈基金会「心盛计划」一季度沟通会会议纪要。青年社群已经重新活跃，关怀员培训需要用唯一 ID 串起反馈，品牌和项目材料更新需要系统推进。",
        ),
        _attachment(
            "fanxing",
            "日慈基金会-繁星计划一季度沟通会议纪要-整理版.docx",
            "日慈基金会「繁星计划」一季度沟通会会议纪要。资源库、行动营、个人 IP 与公众入口需要重新定义战略方向。",
        ),
        *[
            _attachment(
                f"invoice_{index}",
                f"{index}fd9d票据.jpeg",
                "图片 OCR 显示材料包括餐费发票、增值税电子发票、公益性捐赠票据、通行费票据。",
                task_id="task_reimburse",
                created_at=f"2026-04-15T11:{40 + index:02d}:00",
            )
            for index in range(6)
        ],
        _attachment(
            "test_doc",
            "test_attachment.txt",
            "测试附件",
            created_at="2026-04-06T00:11:00",
        ),
    ]

    nodes = build_event_line_timeline_nodes(
        event_line=event_line,
        tasks=tasks,
        activities=activities,
        attachments=attachments,
        snapshot_at="2026-04-22T12:00:00",
    )

    titles = [node["title"] for node in nodes]
    assert "项目启动" in titles
    assert "Q1项目复盘材料集中入库" in titles
    assert "教师赋能项目进入设计校准" in titles
    assert "心盛计划从活动运营转向数据与品牌协同" in titles
    assert "繁星计划进入战略方向重定" in titles
    assert "带领者培训与实践继续推进" in titles
    assert "日慈报销材料归档" in titles
    assert all("主线形成" not in title and "未归属" not in title for title in titles)

    material_node = next(node for node in nodes if node["title"] == "Q1项目复盘材料集中入库")
    assert len(material_node["attachments"]) == 4
    assert "教师赋能" in material_node["summary"]
    assert any("重复" in warning for warning in material_node["warnings"])

    admin_node = next(node for node in nodes if node["title"] == "日慈报销材料归档")
    assert admin_node["kind"] == "admin_archive"
    assert len(admin_node["attachments"]) == 6

    test_node = next(node for node in nodes if node["kind"] == "needs_review")
    assert test_node["title"] == "待确认测试材料"
    assert "test_attachment.txt" in test_node["summary"]
