"""回归测试:parse_task_date_value / is_task_overdue 幽灵函数补实现 (P0-R4/R5)。

根因:main.py 在 _sort_tasks_for_view.due_timestamp(13279)调
parse_task_date_value(task.dueDate),在 _task_is_risky(13227)调
is_task_overdue(task),但两个函数全后端从未定义(幽灵函数)→ 任务视图
按截止日排序 / 风险视图(onlyRisky)一走到就 NameError。
静态扫描(pyflakes undefined-name + 全后端 0 定义核查)系统性发现。

修法:在 main.py 模块级补两个 helper(parse_task_date_value 照既有局部
parse_task_date 逻辑;is_task_overdue = 有截止日+未完成+早于今天)。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.main import is_task_overdue, parse_task_date_value


def test_parse_task_date_value() -> None:
    assert parse_task_date_value(None) is None
    assert parse_task_date_value("") is None
    assert parse_task_date_value("not-a-date") is None
    d_date_only = parse_task_date_value("2030-01-15")
    assert d_date_only is not None and d_date_only.year == 2030 and d_date_only.hour == 0
    # 返回 datetime(带 .timestamp()),供排序用
    assert d_date_only.timestamp() > 0
    d_full = parse_task_date_value("2030-01-15T08:30:00")
    assert d_full is not None and d_full.hour == 8


class _Task:
    """鸭子 stub:is_task_overdue 只读 status / dueDate。"""

    def __init__(self, status: str, due: str | None) -> None:
        self.status = status
        self.dueDate = due


def test_is_task_overdue() -> None:
    past = (datetime.now() - timedelta(days=3)).date().isoformat()
    future = (datetime.now() + timedelta(days=3)).date().isoformat()
    assert is_task_overdue(_Task("todo", past)) is True       # 过去 + 未完成 → 逾期
    assert is_task_overdue(_Task("todo", future)) is False     # 未来
    assert is_task_overdue(_Task("done", past)) is False       # 已完成不算逾期
    assert is_task_overdue(_Task("todo", None)) is False        # 无截止日
    assert is_task_overdue(_Task("todo", "")) is False
