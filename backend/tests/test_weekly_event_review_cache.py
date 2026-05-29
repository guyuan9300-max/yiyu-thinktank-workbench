from app.models import WeeklyEventReviewCardRecord, WeeklyEventReviewCardsRecord
from app.services.review_narrative import weekly_event_review_cards_cover_task_ids


def _cards(groups: list[list[str]]) -> WeeklyEventReviewCardsRecord:
    return WeeklyEventReviewCardsRecord(
        generatedBy="ai",
        cards=[
            WeeklyEventReviewCardRecord(
                title=f"事件复盘 {index}",
                taskIds=task_ids,
                generatedBy="ai",
            )
            for index, task_ids in enumerate(groups, start=1)
        ],
    )


def test_weekly_event_review_cards_cover_exact_task_ids() -> None:
    cards = _cards([["task_a", "task_b"], ["task_c"]])

    assert weekly_event_review_cards_cover_task_ids(cards, ["task_a", "task_b", "task_c"])


def test_weekly_event_review_cards_reject_missing_task_ids() -> None:
    cards = _cards([["task_a", "task_b"]])

    assert not weekly_event_review_cards_cover_task_ids(cards, ["task_a", "task_b", "task_c"])


def test_weekly_event_review_cards_reject_unknown_task_ids() -> None:
    cards = _cards([["task_a", "task_b"], ["task_old"]])

    assert not weekly_event_review_cards_cover_task_ids(cards, ["task_a", "task_b", "task_c"])


def test_weekly_event_review_cards_reject_duplicate_task_ids() -> None:
    cards = _cards([["task_a", "task_b"], ["task_b", "task_c"]])

    assert not weekly_event_review_cards_cover_task_ids(cards, ["task_a", "task_b", "task_c"])
