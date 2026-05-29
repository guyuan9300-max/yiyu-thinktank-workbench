from datetime import date

from app.models import EventLineRecord
from app.smart_input import build_smart_task_draft


def test_build_smart_task_draft_extracts_range_title_and_match():
    event_lines = [
        EventLineRecord(
            id="event_yunnan",
            name="云南儿童调研工作坊",
            primaryClientId="client_yunnan",
            primaryClientName="云南儿童调研",
            createdAt="2026-03-01T10:00:00",
            updatedAt="2026-03-01T10:00:00",
        )
    ]

    result = build_smart_task_draft(
        "帮我建一个日程，3月7号到3月9号去云南，做儿童协作工作坊，这个项目是关于云南儿童调研的。",
        event_lines,
        reference_date=date(2026, 3, 1),
    )

    assert result.draft.title == "云南儿童调研｜儿童调研工作坊｜云南儿童协作工作坊"
    assert result.draft.dueDate == "2026-03-07"
    assert result.draft.endDate == "2026-03-09"
    assert result.draft.clientId == "client_yunnan"
    assert result.draft.eventLineId == "event_yunnan"
    assert result.intent == "task_schedule"


def test_build_smart_task_draft_handles_relative_day_and_analysis_tag():
    result = build_smart_task_draft(
        "明天下午3点调研广州项目的现状，先做一版摸底分析。",
        [],
        reference_date=date(2026, 3, 30),
    )

    assert result.draft.dueDate == "2026-03-31"
    assert result.draft.dueTime == "15:00"
    assert result.draft.tags == ["内部分析"]
    assert result.draft.title


def test_build_smart_task_draft_builds_structured_title_for_client_event_line_and_action():
    event_lines = [
        EventLineRecord(
            id="event_rc",
            name="A组织跟老师戊核对她的教师项目进度",
            primaryClientId="client_rc",
            primaryClientName="A组织",
            createdAt="2026-03-01T10:00:00",
            updatedAt="2026-03-01T10:00:00",
        )
    ]

    result = build_smart_task_draft(
        "A组织老师乙周五之前会发一个关于A组织品牌改造的时间规划过来。",
        event_lines,
        reference_date=date(2026, 3, 31),
    )

    assert result.draft.clientId == "client_rc"
    assert result.draft.eventLineId == "event_rc"
    assert result.draft.title == "A组织｜教师项目｜周五前发品牌改造规划"
