"""ClientRepository · 客户数据唯一读写入口(W2 骨架占位)

W3 完整实施。当前提供:
- 1 个最小读方法,验证 SSOT 通过 v_active_clients 走得通
"""
from __future__ import annotations

from typing import Any


class ClientRepository:
    """W2 占位 · W3 扩展到所有 client_* / clients / client_units SQL"""

    def __init__(self, db: Any):
        self._db = db

    def list_active_client_ids(self) -> list[str]:
        """通过 v_active_clients view 拿所有未冻结 client id"""
        rows = self._db.fetchall("SELECT id FROM v_active_clients ORDER BY name")
        return [str(r["id"]) for r in rows]

    def count_active(self) -> int:
        row = self._db.fetchone("SELECT COUNT(*) AS n FROM v_active_clients")
        return int(row["n"]) if row else 0


def get_client_repository(db: Any) -> ClientRepository:
    return ClientRepository(db)
