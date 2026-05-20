"""IntelligenceRepository · 情报数据唯一读写入口(W2 骨架占位)

W3-4 完整实施。当前 1 个 count 方法验证。
"""
from __future__ import annotations

from typing import Any


class IntelligenceRepository:
    def __init__(self, db: Any):
        self._db = db

    def count_items(self, *, user_status: str = "active") -> int:
        """情报条目计数 · user_status='active' 默认过滤掉 resolved/misclassified"""
        try:
            row = self._db.fetchone(
                "SELECT COUNT(*) AS n FROM intelligence_items WHERE user_status = ?",
                (user_status,),
            )
            return int(row["n"]) if row else 0
        except Exception:
            return 0


def get_intelligence_repository(db: Any) -> IntelligenceRepository:
    return IntelligenceRepository(db)
