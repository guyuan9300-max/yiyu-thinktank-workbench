"""KnowledgeRepository · 知识数据唯一读写入口(W2 骨架占位)

W4 完整实施(v1/v2 双模型迁移)。当前提供 v_searchable_knowledge 验证。
"""
from __future__ import annotations

from typing import Any


class KnowledgeRepository:
    def __init__(self, db: Any):
        self._db = db

    def count_searchable(self, *, client_id: str | None = None) -> int:
        if client_id:
            row = self._db.fetchone(
                "SELECT COUNT(*) AS n FROM v_searchable_knowledge WHERE client_id = ?",
                (client_id,),
            )
        else:
            row = self._db.fetchone("SELECT COUNT(*) AS n FROM v_searchable_knowledge")
        return int(row["n"]) if row else 0


def get_knowledge_repository(db: Any) -> KnowledgeRepository:
    return KnowledgeRepository(db)
