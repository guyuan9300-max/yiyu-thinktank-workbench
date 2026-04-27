from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.models import WeeklyReviewTaskEntryRecord
from app.services.review_narrative import (
    build_weekly_event_review_cards_draft,
    build_weekly_event_review_cards_fallback,
    build_weekly_mainline_cards_draft,
    build_weekly_mainline_evidence_pack,
)


NOW = "2026-04-20T09:00:00"


def _insert_client(db: Database, client_id: str = "client_1") -> None:
    db.execute(
        """
        INSERT INTO clients(id, name, alias, domain, type, intro, stage, created_at, updated_at)
        VALUES(?, '测试客户', '测试客户', '公益', '战略陪伴', '用于周复盘主线测试', '推进中', ?, ?)
        """,
        (client_id, NOW, NOW),
    )


def _insert_task(db: Database, task_id: str, title: str, *, client_id: str = "client_1") -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO task_lists(id, organization_id, name, color, sort_order, is_default, scope)
        VALUES('list_1', '', '测试列表', '#5B7BFE', 0, 1, 'org')
        """,
    )
    db.execute(
        """
        INSERT INTO tasks(
            id, organization_id, title, description, status, priority, list_id, creator_id, owner_id, owner_name,
            progress_status, ddl, due_date, duration_minutes, scope_mode, source_type, source_id,
            tags_json, tag_ids_json, created_at, updated_at
        ) VALUES(?, '', ?, '', 'done', 'normal', 'list_1', '', '', '', 'done', '', ?, 60,
            'COLLAB_SHARED', 'manual', NULL, '[]', '[]', ?, ?)
        """,
        (task_id, title, NOW, NOW, NOW),
    )


def _insert_document(
    db: Database,
    *,
    document_id: str,
    client_id: str = "client_1",
    title: str = "测试材料",
    kind: str = "md",
    markdown_content: str = "",
    preview_text: str = "",
    excerpt: str = "",
) -> None:
    db.execute(
        """
        INSERT INTO documents(id, client_id, folder_id, title, path, kind, source, excerpt, tags_json, created_at)
        VALUES(?, ?, NULL, ?, ?, ?, 'task_attachment', ?, '[]', ?)
        """,
        (document_id, client_id, title, f"/tmp/{title}", kind, excerpt, NOW),
    )
    if markdown_content or preview_text:
        db.execute(
            """
            INSERT INTO v2_documents(
                id, client_id, document_id, original_path, managed_path, file_name, kind,
                material_layer, visible_category, secondary_category, parse_status, preview_text,
                doc_index_text, content_hash, markdown_content, classification_confidence,
                section_count, chunk_count, imported_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, 'evidence', '项目资料', '周复盘材料', 'ready', ?,
                ?, ?, ?, 1.0, 1, 1, ?, ?)
            """,
            (
                f"v2_{document_id}",
                client_id,
                document_id,
                f"/tmp/{title}",
                f"/tmp/{title}",
                title,
                kind,
                preview_text,
                preview_text,
                f"hash_{document_id}",
                markdown_content,
                NOW,
                NOW,
            ),
        )


def _insert_attachment(
    db: Database,
    *,
    attachment_id: str,
    task_id: str,
    document_id: str | None,
    title: str,
    kind: str,
    client_id: str = "client_1",
) -> None:
    db.execute(
        """
        INSERT INTO task_attachments(
            id, task_id, client_id, event_line_id, document_id, title, path, kind, source, size_bytes, created_at
        ) VALUES(?, ?, ?, NULL, ?, ?, ?, ?, 'upload', 1024, ?)
        """,
        (attachment_id, task_id, client_id, document_id, title, f"/tmp/{title}", kind, NOW),
    )


def _review_item(task_id: str, title: str, *, status: str = "done") -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id=f"entry_{task_id}",
        taskId=task_id,
        weekLabel="2026-W17",
        contentDomain="work",
        note="本周已经完成核心材料整理，下一步需要确认交付版本边界。",
        structuredNote={
            "progress": "完成核心材料整理，并进入交付版本校准。",
            "nextAction": "确认最终修改清单和交付标准。",
        },
        taskSnapshot={
            "title": title,
            "status": status,
            "createdAt": NOW,
            "clientId": "client_1",
            "clientName": "测试客户",
            "eventLineId": "event_1",
            "eventLineName": "测试主线",
            "listName": "测试列表",
            "listColor": "#5B7BFE",
        },
    )


def test_weekly_mainline_evidence_reads_attachments_by_current_week_task_ids(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task(db, "task_current", "本周任务")
    _insert_task(db, "task_other", "其他周任务")
    _insert_document(
        db,
        document_id="doc_current",
        title="本周材料.md",
        markdown_content="这是一份本周任务关联材料，说明了本周已经完成材料结构调整和交付对象校准。",
    )
    _insert_document(
        db,
        document_id="doc_other",
        title="其他周材料.md",
        markdown_content="这是一份其他周材料，不应该进入本周复盘主线证据。",
    )
    _insert_attachment(db, attachment_id="att_current", task_id="task_current", document_id="doc_current", title="本周材料.md", kind="md")
    _insert_attachment(db, attachment_id="att_other", task_id="task_other", document_id="doc_other", title="其他周材料.md", kind="md")

    evidence_pack = build_weekly_mainline_evidence_pack(
        db=db,
        data_dir=tmp_path,
        week_label="2026-W17",
        items=[_review_item("task_current", "本周任务")],
        include_data_center=False,
    )

    attachments = evidence_pack["attachments"]
    assert [item["attachmentId"] for item in attachments] == ["att_current"]
    assert "其他周材料" not in str(evidence_pack)


def test_weekly_mainline_evidence_suggests_material_value_without_unread_wording(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    _insert_client(db)
    _insert_task(db, "task_ppt", "演示材料任务")
    _insert_document(db, document_id="doc_ppt", title="交付演示.pptx", kind="pptx")
    _insert_attachment(db, attachment_id="att_ppt", task_id="task_ppt", document_id="doc_ppt", title="交付演示.pptx", kind="pptx")

    evidence_pack = build_weekly_mainline_evidence_pack(
        db=db,
        data_dir=tmp_path,
        week_label="2026-W17",
        items=[_review_item("task_ppt", "演示材料任务")],
        include_data_center=False,
    )

    attachment = evidence_pack["attachments"][0]
    assert attachment["readableText"] == ""
    assert "文字大纲" in attachment["suggestedMaterial"]
    assert "决策" in attachment["suggestedMaterial"]
    assert "未读" not in attachment["suggestedMaterial"]
    assert "失败" not in attachment["suggestedMaterial"]


class _Health:
    provider = "qwen"
    ready = True


class _FakeAi:
    def __init__(self, payload: Any):
        self.payload = payload
        self.prompt = ""

    def get_health(self) -> _Health:
        return _Health()

    def _qwen_generate(self, **kwargs: Any) -> Any:
        self.prompt = str(kwargs.get("prompt") or "")
        return self.payload


def _minimal_evidence_pack() -> dict[str, Any]:
    return {
        "weekLabel": "2026-W17",
        "tasks": [
            {
                "taskId": "task_1",
                "title": "益语平台开源页调整",
                "status": "done",
                "clientName": "益语",
                "eventLineName": "益语平台",
                "reviewNote": "本周完成开源页面修改，表达正在从功能说明转向价值表达。",
                "structuredNote": {"progress": "完成开源页面修改。", "nextAction": "重写首屏价值表达。"},
                "projectContext": {"goalSummary": "让业务负责人理解平台价值。"},
                "eventLineContext": {},
            }
        ],
        "attachments": [
            {
                "title": "开源页说明",
                "taskTitle": "益语平台开源页调整",
                "readableText": "",
                "suggestedMaterial": "建议补充首屏价值表达草稿；补齐后可以判断是否服务业务负责人转化沟通。",
            }
        ],
        "dataContext": [],
        "evidenceMeta": {"taskCount": 1, "attachmentCount": 1, "readableAttachmentCount": 0},
    }


def _event_pack(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "weekLabel": "2026-W17",
        "tasks": tasks,
        "attachments": [],
        "dataContext": [],
        "evidenceMeta": {"taskCount": len(tasks), "attachmentCount": 0, "readableAttachmentCount": 0},
    }


def _event_task(
    task_id: str,
    title: str,
    *,
    event_line_id: str = "",
    event_line_name: str = "",
    description: str = "",
    next_action: str = "",
) -> dict[str, Any]:
    return {
        "taskId": task_id,
        "title": title,
        "status": "done",
        "clientName": "测试客户" if event_line_id else "",
        "eventLineId": event_line_id,
        "eventLineName": event_line_name,
        "taskDescription": description,
        "reviewNote": "",
        "structuredNote": {"progress": "", "nextAction": next_action},
        "projectContext": {},
        "eventLineContext": {"summary": "", "nextStep": ""},
    }


def test_weekly_event_review_fallback_groups_duplicate_titles():
    pack = _event_pack(
        [
            _event_task("task_a", "确定县域落地计划", description="明确每个县域拟落地学校数量。"),
            _event_task("task_b", "确定县域落地计划", description="排出各县域推进顺序和时间节奏。"),
            _event_task("task_c", "教育双年会朋友圈"),
        ]
    )

    result = build_weekly_event_review_cards_fallback(pack)

    duplicate_card = next(card for card in result.cards if set(card.taskIds) == {"task_a", "task_b"})
    assert duplicate_card.cardKind == "task_cluster"
    assert duplicate_card.taskTitles == ["确定县域落地计划", "确定县域落地计划"]
    assert any(card.taskIds == ["task_c"] and card.cardKind == "single_task" for card in result.cards)


def test_weekly_event_review_fallback_keeps_event_line_priority():
    pack = _event_pack(
        [
            _event_task("task_event", "确定县域落地计划", event_line_id="event_1", event_line_name="真实事件线"),
            _event_task("task_plain", "确定县域落地计划"),
            _event_task("task_plain_2", "确定县域落地计划"),
        ]
    )

    result = build_weekly_event_review_cards_fallback(pack)

    event_card = next(card for card in result.cards if card.cardKind == "event_line")
    assert event_card.taskIds == ["task_event"]
    duplicate_card = next(card for card in result.cards if set(card.taskIds) == {"task_plain", "task_plain_2"})
    assert duplicate_card.cardKind == "task_cluster"


def test_weekly_event_review_ai_missing_task_falls_back():
    pack = _event_pack(
        [
            _event_task("task_a", "确定县域落地计划"),
            _event_task("task_b", "确定县域落地计划"),
        ]
    )
    fake_ai = _FakeAi(
        {
            "cards": [
                {
                    "id": "ai-1",
                    "title": "县域落地计划",
                    "cardKind": "task_cluster",
                    "taskIds": ["task_a"],
                    "reflectionPromptText": "可以回想一下：县域计划整理后，项目准备度有什么变化。也可以写下还缺哪个判断、谁需要接手，以及下周最小可推进事项是什么。",
                    "confidence": "medium",
                }
            ]
        }
    )

    result = build_weekly_event_review_cards_draft(ai=fake_ai, week_label="2026-W17", evidence_pack=pack)

    assert result.generatedBy == "fallback"
    assert result.evidenceMeta.get("failureReason") == "task_coverage_mismatch"


def test_weekly_event_review_ai_banned_phrase_falls_back():
    pack = _event_pack(
        [
            _event_task("task_a", "确定县域落地计划"),
            _event_task("task_b", "确定县域落地计划"),
        ]
    )
    fake_ai = _FakeAi(
        {
            "cards": [
                {
                    "id": "fallback-weekly-event-1",
                    "title": "县域落地计划",
                    "cardKind": "task_cluster",
                    "taskIds": ["task_a", "task_b"],
                    "reflectionPromptText": "可以回想一下：县域落地计划整理后，项目准备度有没有打下坚实基础。也可以写下还缺哪个判断、谁需要接手，以及下周最小可推进事项是什么。",
                    "confidence": "medium",
                }
            ]
        }
    )

    result = build_weekly_event_review_cards_draft(ai=fake_ai, week_label="2026-W17", evidence_pack=pack)

    assert result.generatedBy == "fallback"
    assert str(result.evidenceMeta.get("failureReason")).startswith("banned_phrase")


def test_weekly_event_review_fallback_suggests_material_value_without_background():
    pack = _event_pack([_event_task("task_a", "乡基会报价合同确认")])

    result = build_weekly_event_review_cards_fallback(pack)

    assert result.cards[0].cardKind == "single_task"
    assert "可以回想一下" in result.cards[0].reflectionPromptText
    assert "乡基会报价合同确认" in result.cards[0].reflectionPromptText


def test_weekly_event_review_ai_draft_text_falls_back():
    pack = _event_pack(
        [
            _event_task("task_a", "确定县域落地计划"),
            _event_task("task_b", "确定县域落地计划"),
        ]
    )
    fake_ai = _FakeAi(
        {
            "cards": [
                {
                    "id": "fallback-weekly-event-1",
                    "title": "县域落地计划",
                    "cardKind": "task_cluster",
                    "taskIds": ["task_a", "task_b"],
                    "progressText": "本周完成县域落地计划相关任务整理，任务目标一致，适合统一复盘。",
                    "nextActionText": "下一步先确认县域推进清单，并明确负责人、时间和交付物。",
                    "materialSuggestionText": "",
                    "reflectionPromptText": "可以回想一下：县域计划整理后，项目准备度有什么变化。",
                    "confidence": "medium",
                }
            ]
        }
    )

    result = build_weekly_event_review_cards_draft(ai=fake_ai, week_label="2026-W17", evidence_pack=pack)

    assert result.generatedBy == "fallback"
    assert str(result.evidenceMeta.get("failureReason")).startswith("unexpected_draft_text")


def test_weekly_event_review_ai_open_prompt_is_accepted():
    pack = _event_pack(
        [
            _event_task("task_a", "确定县域落地计划"),
            _event_task("task_b", "确定县域落地计划"),
        ]
    )
    fake_ai = _FakeAi(
        {
            "cards": [
                {
                    "id": "fallback-weekly-event-1",
                    "title": "县域落地计划",
                    "cardKind": "task_cluster",
                    "taskIds": ["task_a", "task_b"],
                    "reflectionPromptText": "可以回想一下：县域计划整理后，项目准备度发生了什么变化。也可以写下名单、筛选标准或沟通节奏里，哪一项最影响后续推进。",
                    "confidence": "medium",
                }
            ]
        }
    )

    result = build_weekly_event_review_cards_draft(ai=fake_ai, week_label="2026-W17", evidence_pack=pack)

    assert result.generatedBy == "ai"
    assert "可以回想一下" in result.cards[0].reflectionPromptText
    assert "progressText" not in fake_ai.prompt


def test_weekly_mainline_ai_rejects_internal_terms_and_vague_next_goal():
    bad_ai = _FakeAi(
        {
            "summaryText": "本周组织重点集中在益语平台开源页调整，核心任务已经形成阶段性完成，需要进入下一步表达校准。",
            "mainlines": [
                {
                    "title": "益语平台",
                    "taskCount": 1,
                    "completedCount": 1,
                    "pendingCount": 0,
                    "progressText": "本周完成开源页面修改，页面表达开始从技术功能说明转向价值表达。这个变化有助于让外部用户更快理解平台用途。",
                    "nextGoalText": "下一步确认页面负责人后继续推进收束，并判断是否闭环，同时保持当前任务节奏。",
                }
            ],
        }
    )

    result = build_weekly_mainline_cards_draft(ai=bad_ai, week_label="2026-W17", evidence_pack=_minimal_evidence_pack())

    assert result.generatedBy == "fallback"
    assert result.mainlines == []
    assert "banned_phrase" in str(result.evidenceMeta.get("failureReason"))


def test_weekly_mainline_ai_accepts_actionable_cards_and_prompt_uses_suggestions():
    good_ai = _FakeAi(
        {
            "summaryText": "本周组织重点集中在益语平台开源页调整，任务已经完成，重点从页面修改进入价值表达校准。下一步应把平台价值写给明确对象看，避免只停留在技术功能说明。",
            "mainlines": [
                {
                    "title": "益语平台",
                    "taskCount": 1,
                    "completedCount": 1,
                    "pendingCount": 0,
                    "progressText": "本周完成益语平台开源页面修改，页面表达从功能展示推进到业务价值解释。当前阶段的意义，是让外部业务负责人不只看到功能清单，而能理解平台为什么能支持组织协作和判断力沉淀。",
                    "nextGoalText": "下一步先重写首屏价值表达，并确认目标读者是中小企业负责人还是公益机构管理者。产出标准是一版可直接放到页面上的标题、副标题和三个价值点，补齐后可以判断页面是否支撑转化沟通。",
                }
            ],
        }
    )

    result = build_weekly_mainline_cards_draft(ai=good_ai, week_label="2026-W17", evidence_pack=_minimal_evidence_pack())

    assert result.generatedBy == "ai"
    assert result.mainlines[0].title == "益语平台"
    assert "重写首屏价值表达" in result.mainlines[0].nextGoalText
    assert "首屏价值表达草稿" in good_ai.prompt
    assert "附件未读" not in good_ai.prompt
