from app.main import _task_in_week
from app.models import TaskRecord


def _task(**overrides) -> TaskRecord:
    data = {
        "id": "task_test",
        "title": "测试任务",
        "description": "",
        "creatorId": "user_test",
        "creatorName": "管理员甲",
        "listName": "默认清单",
        "listColor": "#5B7BFE",
        "priority": "normal",
        "listId": "list_test",
        "progressStatus": "doing",
        "sourceType": "manual",
        "tags": [],
        "collaborators": [],
        "collaborationSummary": {},
        "createdAt": "2026-04-01T10:00:00",
        "updatedAt": "2026-04-01T10:00:00",
    }
    data.update(overrides)
    return TaskRecord(**data)


def test_unfinished_review_week_uses_schedule_or_deadline_not_created_at():
    no_date_task = _task(createdAt="2026-04-20T10:00:00")
    assert not _task_in_week(no_date_task, "2026-W17")

    scheduled_task = _task(scheduledStartAt="2026-04-20T09:00")
    assert _task_in_week(scheduled_task, "2026-W17")

    deadline_task = _task(deadlineAt="2026-04-22")
    assert _task_in_week(deadline_task, "2026-W17")


def test_completed_review_week_prefers_completed_at():
    completed_task = _task(
        progressStatus="done",
        dueDate="2026-04-20",
        completedAt="2026-04-30T18:00:00",
        updatedAt="2026-04-30T18:00:00",
    )
    assert not _task_in_week(completed_task, "2026-W17")
    assert _task_in_week(completed_task, "2026-W18")
