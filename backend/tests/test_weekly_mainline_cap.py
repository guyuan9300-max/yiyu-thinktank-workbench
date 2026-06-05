"""meeting-spine: 重点主线放宽到 6 + 逐卡跳过(不再整份回退)单测。

覆盖:
- 放宽到 WEEKLY_MAINLINE_MAX(原硬截 3 的 bug)
- 逐卡质量门改为"跳过不合格卡", 不把整份打回 fallback(零回归核心)
- 全部不合格才回退 None
- 违禁词/内部词只跳那一条
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.review_narrative import (
    WEEKLY_MAINLINE_MAX,
    _coerce_weekly_mainline_cards,
)

GOOD_PROGRESS = "本周完成了任务管理模块的优化和上线前自测，整体进展顺利，符合既定排期安排。"
GOOD_NEXTGOAL = "下一步优先完成移动端联调，确认负责人与交付时间，避免拖期影响发布节奏。"  # 含"完成/确认"动作词
SUMMARY = "本周组织重点集中在平台迭代与客户交付，整体推进顺利，多数任务按计划完成并已复盘。"


def _card(title: str, *, progress: str = GOOD_PROGRESS, nextgoal: str = GOOD_NEXTGOAL) -> dict:
    return {
        "title": title, "progressText": progress, "nextGoalText": nextgoal,
        "taskCount": 3, "completedCount": 1, "pendingCount": 2,
    }


def _raw(cards: list[dict], summary: str = SUMMARY) -> dict:
    return {"summaryText": summary, "mainlines": cards}


EVID = {"evidenceMeta": {}}


def test_coerce_allows_up_to_max_and_caps_there() -> None:
    rec, reason = _coerce_weekly_mainline_cards(_raw([_card(f"主线{i}") for i in range(8)]), EVID)
    assert rec is not None, reason
    assert rec.generatedBy == "ai"
    assert len(rec.mainlines) == WEEKLY_MAINLINE_MAX  # 6: 放宽到上限且封顶


def test_coerce_skips_bad_cards_instead_of_whole_fallback() -> None:
    cards = [
        _card("好卡A"),
        _card("短卡", progress="太短"),               # progress<24 → 跳过
        _card("无动作卡", nextgoal="这是一段没有任何动作词的下一步描述文本填充长度。"),  # 无动作 → 跳过
        _card("好卡B"),
    ]
    rec, reason = _coerce_weekly_mainline_cards(_raw(cards), EVID)
    assert rec is not None, reason  # ★关键: 不因坏卡整份回退
    titles = [m.title for m in rec.mainlines]
    assert titles == ["好卡A", "好卡B"]


def test_coerce_all_bad_falls_back_none() -> None:
    cards = [_card("坏A", progress="短"), _card("坏B", nextgoal="没有动作词的纯描述文本用于凑够长度阈值。")]
    rec, reason = _coerce_weekly_mainline_cards(_raw(cards), EVID)
    assert rec is None
    assert reason == "mainlines_empty_after_clean"


def test_coerce_banned_phrase_skips_only_that_card() -> None:
    cards = [
        _card("正常卡"),
        _card("违禁卡", progress="本周继续推进各项工作，整体按部就班向前走，没有明显卡点出现。"),  # 含"继续推进" → 跳过
        _card("另一正常卡"),
    ]
    rec, _ = _coerce_weekly_mainline_cards(_raw(cards), EVID)
    assert rec is not None
    titles = [m.title for m in rec.mainlines]
    assert "违禁卡" not in titles
    assert titles == ["正常卡", "另一正常卡"]
