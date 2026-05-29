"""TaskRepository · 任务数据唯一读写入口(W2 骨架占位)

W3-4 完整实施。当前提供 1 个最小读方法,验证 v_pending_tasks view 走得通。
"""
from __future__ import annotations

from typing import Any


class TaskRepository:
    """W2 占位 · W3-4 扩展到所有 tasks / task_lists / task_collaborators SQL"""

    def __init__(self, db: Any):
        self._db = db

    def count_pending(self, *, client_id: str | None = None) -> int:
        """v_pending_tasks 是 status IN ('todo','doing')"""
        if client_id:
            row = self._db.fetchone(
                "SELECT COUNT(*) AS n FROM v_pending_tasks WHERE client_id = ?",
                (client_id,),
            )
        else:
            row = self._db.fetchone("SELECT COUNT(*) AS n FROM v_pending_tasks")
        return int(row["n"]) if row else 0


def get_task_repository(db: Any) -> TaskRepository:
    return TaskRepository(db)
