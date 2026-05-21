"""ClientScopeFilter · client_id 写入路径统一守门 (Phase 1 F1.3)

服务: V2.2_NORTH_STAR.md 目标 A (现有功能不掉链)
按: docs/V2.2_PHASE1_SPEC_F13.md

关键场景:
1. main.py 写入 task/event_line/commitment 之前: scope.assert_writable(client_id)
2. 批量查询 (按 client_id 过滤): scope.scope_query(client_ids)
3. 多账号同步: F1.7 client_stage_audit + 同步前 scope.assert_writable

依赖: F1.1 ClientRepository (复用 is_frozen / is_archived / can_write)
"""
from __future__ import annotations

from typing import Any, TypeVar

from .repository import ClientRepository, get_client_repository


T = TypeVar("T")


# ── 异常 + reason 常量 ──────────────────────────────────────
class ScopeFilterError(Exception):
    """写入被拦截时抛出"""

    def __init__(self, client_id: str, reason: str):
        self.client_id = client_id
        self.reason = reason
        super().__init__(f"client {client_id!r} 不可写: {reason}")


# reason 枚举
REASON_NOT_FOUND = "client_not_found"
REASON_FROZEN = "client_frozen"
REASON_ARCHIVED = "client_archived"
REASON_LOST = "client_lost"


class ClientScopeFilter:
    """所有 client_id 写入/查询的统一守门"""

    def __init__(self, client_repo: ClientRepository) -> None:
        self._repo = client_repo

    # ── 1. 写入守门 (最高频) ─────────────────────────────────
    def assert_writable(self, client_id: str) -> None:
        """如果 client 不可写, raise ScopeFilterError. 写入前必调."""
        if not client_id:
            raise ScopeFilterError("", REASON_NOT_FOUND)
        client = self._repo.get_by_id(client_id)
        if client is None:
            raise ScopeFilterError(client_id, REASON_NOT_FOUND)
        if client.stage == "frozen":
            raise ScopeFilterError(client_id, REASON_FROZEN)
        if client.stage == "archived":
            raise ScopeFilterError(client_id, REASON_ARCHIVED)
        if client.stage == "lost":
            raise ScopeFilterError(client_id, REASON_LOST)
        # 其他 stage 都可写 (active / lead / discovery / paused / 自定义 stage)

    def is_writable(self, client_id: str) -> bool:
        """不抛异常版本 — 一行 bool check, 用于条件分支"""
        try:
            self.assert_writable(client_id)
            return True
        except ScopeFilterError:
            return False

    # ── 2. 批量查询过滤 ──────────────────────────────────────
    def scope_query(
        self,
        client_ids: list[str] | None = None,
        *,
        include_frozen: bool = False,
        include_archived: bool = False,
        require_writable: bool = False,
    ) -> list[str]:
        """过滤一组 client_id 返回 in-scope 的子集 (按 name 排序).

        Args:
            client_ids: None = 全部活跃; 否则按这组过滤
            include_frozen: True 时不过滤 stage='frozen'
            include_archived: True 时不过滤 stage='archived'/'lost'
            require_writable: True 时只返回可写的 (覆盖其他 flag)

        Returns:
            合规 client_id 列表, 按 name 排序
        """
        if require_writable:
            # 强制收紧
            include_frozen = False
            include_archived = False

        # 决定候选池
        if client_ids is None:
            # 没传 ids: 从 repo 拿全部
            all_clients = self._repo.list_all(include_frozen=True)
            candidates = []
            for c in all_clients:
                if c.stage == "frozen" and not include_frozen:
                    continue
                if c.stage in ("archived", "lost") and not include_archived:
                    continue
                candidates.append(c)
        else:
            # 给定 ids, 一个个 check
            candidates = []
            for cid in client_ids:
                client = self._repo.get_by_id(cid)
                if client is None:
                    continue
                if client.stage == "frozen" and not include_frozen:
                    continue
                if client.stage in ("archived", "lost") and not include_archived:
                    continue
                candidates.append(client)

        # 按 name 排序
        candidates.sort(key=lambda c: c.name)
        return [c.id for c in candidates]

    # ── 3. 记录字典过滤 ──────────────────────────────────────
    def filter_records_by_client(
        self,
        records_by_client: dict[str, T],
        *,
        include_frozen: bool = False,
        include_archived: bool = False,
        require_writable: bool = False,
    ) -> dict[str, T]:
        """已经按 client_id 分组的字典 → 过滤掉不在 scope 的 key."""
        valid_ids = set(
            self.scope_query(
                list(records_by_client.keys()),
                include_frozen=include_frozen,
                include_archived=include_archived,
                require_writable=require_writable,
            )
        )
        return {
            cid: records_by_client[cid]
            for cid in valid_ids
            if cid in records_by_client
        }


def get_client_scope_filter(db_or_repo: Any) -> ClientScopeFilter:
    """工厂. 接受 db 或 ClientRepository, 自动判断"""
    if isinstance(db_or_repo, ClientRepository):
        return ClientScopeFilter(db_or_repo)
    return ClientScopeFilter(get_client_repository(db_or_repo))
