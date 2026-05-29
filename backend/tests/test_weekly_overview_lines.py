import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    OrganizationDnaModuleRecord,
    WeeklyReviewTaskEntryRecord,
    WeeklyReviewTaskSnapshotRecord,
    WeeklyReviewTaskStructuredNoteRecord,
)
from app.services.review_narrative import _build_weekly_line_cards


def _make_snapshot(**overrides) -> WeeklyReviewTaskSnapshotRecord:
    defaults = {
        "title": "测试任务",
        "status": "doing",
        "createdAt": "2026-03-25T10:00:00Z",
        "listName": "任务清单",
        "listColor": "#5B7BFE",
        "ownerName": "管理员甲",
        "clientName": "",
        "eventLineId": "",
        "eventLineName": "",
        "desc": "",
        "note": "",
        "evidenceCount": 0,
    }
    defaults.update(overrides)
    return WeeklyReviewTaskSnapshotRecord(**defaults)


def _make_entry(task_id: str, snapshot: WeeklyReviewTaskSnapshotRecord, note: str = "") -> WeeklyReviewTaskEntryRecord:
    return WeeklyReviewTaskEntryRecord(
        id=f"entry_{task_id}",
        reviewId="review_w13",
        taskId=task_id,
        weekLabel="2026-W13",
        contentDomain="work",
        note=note,
        structuredNote=WeeklyReviewTaskStructuredNoteRecord(),
        taskSnapshot=snapshot,
    )


def test_debug_tasks_group_into_software_line():
    items = [
        _make_entry("task_1", _make_snapshot(title="codex-attachment-save-debug", desc="排查附件保存链路")),
        _make_entry("task_2", _make_snapshot(title="CODEx新建任务可见性排查", desc="验证任务可见性问题")),
    ]
    cards = _build_weekly_line_cards(items, [], [])
    line_names = [card.line_name for card in cards]
    assert "软件底层修复与验证线" in line_names


def test_hub_line_uses_client_background_for_importance():
    org_modules = [
        OrganizationDnaModuleRecord(
            moduleKey="organization_intro",
            title="组织介绍",
            markdownContent="",
            normalizedText="示例工作台是一家咨询公司",
            summary="示例工作台是一家咨询公司。",
        ),
        OrganizationDnaModuleRecord(
            moduleKey="business_intro",
            title="B客户 业务背景",
            markdownContent="",
            normalizedText="B客户是公益行业的重要枢纽组织，连接大量基金会，具备很强的行业影响力。",
            summary="B客户是公益行业的重要枢纽组织，连接大量基金会，具备很强的行业影响力。",
        ),
    ]
    items = [
        _make_entry(
            "task_demo_hub_1",
            _make_snapshot(
                title="和联系人甲老师沟通B客户的战略说明迭代",
                clientName="B客户",
                eventLineId="el_demo_hub",
                eventLineName="联系人乙讨论赋能合作",
                desc="推进合作说明迭代",
            ),
        )
    ]
    cards = _build_weekly_line_cards(items, org_modules, [])
    assert cards
    hub_card = cards[0]
    assert "B客户" in hub_card.line_name
    assert "枢纽" in hub_card.why_it_matters or "基金会" in hub_card.why_it_matters
