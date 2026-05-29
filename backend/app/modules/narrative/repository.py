"""NarrativeRepository · 叙事/事件线数据唯一读写入口(W2 骨架占位)

W5 完整实施。当前提供 v_active_event_lines 验证。
"""
from __future__ import annotations

from typing import Any


class NarrativeRepository:
    def __init__(self, db: Any):
        self._db = db

    def count_active_event_lines(self, *, client_id: str | None = None) -> int:
        """通过 v_active_event_lines view(已过滤 frozen client)"""
        if client_id:
            row = self._db.fetchone(
                "SELECT COUNT(*) AS n FROM v_active_event_lines WHERE primary_client_id = ?",
                (client_id,),
            )
        else:
            row = self._db.fetchone("SELECT COUNT(*) AS n FROM v_active_event_lines")
        return int(row["n"]) if row else 0


def get_narrative_repository(db: Any) -> NarrativeRepository:
    return NarrativeRepository(db)
