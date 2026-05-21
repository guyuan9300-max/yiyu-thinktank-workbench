"""ClientRepository · 客户数据唯一读写入口 (Phase 1 F1.1 完整实现)

模式跟 W1 OrganizationRepository / W3 GlossaryRepository 一致。
镜像 cloud_backend mobile endpoints 的 ClientRecord shape。

下游消费者:
- ClientFactView (Phase 1 F1.2) — 用本 Repository 拿 base client + 合并其他事实
- ClientScopeFilter (Phase 1 F1.3) — 用 is_frozen/is_archived 做仲裁
- main.py 中 ~127 处 clients/client_folders/client_units 直查 SQL → F1.4 切走 top 50 处
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from .types import (
    ClientCreatePayload,
    ClientRecord,
    ClientUpdatePayload,
)


# ── DB 协议 + Adapter (兼容 Database 包装器 与 raw sqlite3.Connection) ──
class _DbLike(Protocol):
    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]: ...
    def execute(self, query: str, params: tuple = ()) -> None: ...


class _ConnAdapter:
    """把 sqlite3.Connection 包成 _DbLike 接口"""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        return self._conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        return list(self._conn.execute(query, params).fetchall())

    def execute(self, query: str, params: tuple = ()) -> None:
        self._conn.execute(query, params)


def _wrap_db(db: Any) -> _DbLike:
    if isinstance(db, sqlite3.Connection):
        return _ConnAdapter(db)
    return db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_record(row: Any) -> ClientRecord:
    """sqlite3.Row → ClientRecord 不可变"""
    return ClientRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        alias=str(row["alias"] or ""),
        domain=str(row["domain"] or ""),
        type=str(row["type"] or ""),
        intro=str(row["intro"] or ""),
        stage=str(row["stage"] or "active"),  # type: ignore[arg-type]
        color=str(row["color"] or "#5B7BFE"),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class ClientRepository:
    """客户数据 SSOT — Phase 1 F1.1 完整实现"""

    def __init__(self, db: Any):
        self._db = _wrap_db(db)

    # ── 读 · 基础 ─────────────────────────────────────────────────
    def get_by_id(self, client_id: str) -> ClientRecord | None:
        """通过 id 拿单个客户。不存在返回 None。"""
        if not client_id:
            return None
        row = self._db.fetchone(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        )
        return _row_to_record(row) if row else None

    def get_by_alias(self, alias: str) -> ClientRecord | None:
        """通过 alias 拿单个客户 (alias 同名取第一个)。不存在返回 None。"""
        if not alias:
            return None
        row = self._db.fetchone(
            "SELECT * FROM clients WHERE alias = ? LIMIT 1", (alias,)
        )
        return _row_to_record(row) if row else None

    def list_active(self) -> list[ClientRecord]:
        """通过 v_active_clients view 拿所有未冻结 client。

        W1 organization 模块已经建了 v_active_clients view
        (排除 stage IN ('frozen','archived','lost'))。
        """
        rows = self._db.fetchall(
            "SELECT * FROM clients WHERE id IN (SELECT id FROM v_active_clients) "
            "ORDER BY name"
        )
        return [_row_to_record(r) for r in rows]

    def list_all(self, include_frozen: bool = False) -> list[ClientRecord]:
        """拿全部客户。

        Args:
            include_frozen: True 时包含 stage='frozen'/'archived'/'lost' 的客户
        """
        if include_frozen:
            rows = self._db.fetchall("SELECT * FROM clients ORDER BY name")
        else:
            # 排除 archived/lost, 但 frozen 默认保留 (frozen 仍是"在用,只是不同步")
            rows = self._db.fetchall(
                "SELECT * FROM clients WHERE stage NOT IN ('archived', 'lost') "
                "ORDER BY name"
            )
        return [_row_to_record(r) for r in rows]

    # ── 兼容 W2 占位接口 (其他代码已经在调) ──────────────────────────
    def list_active_client_ids(self) -> list[str]:
        """W2 占位兼容 — 拿所有活跃客户 id"""
        return [c.id for c in self.list_active()]

    def count_active(self) -> int:
        """W2 占位兼容 — 活跃客户数量"""
        return len(self.list_active())

    # ── 写 · CRUD ─────────────────────────────────────────────────
    def create(self, payload: ClientCreatePayload) -> ClientRecord:
        """创建客户。name 不能为空。alias 为空时默认用 name。"""
        if not payload.name.strip():
            raise ValueError("name 不能为空")
        timestamp = _now_iso()
        client_id = f"client_{uuid.uuid4().hex[:10]}"
        self._db.execute(
            """
            INSERT INTO clients (
                id, name, alias, domain, type, intro, stage, color,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                payload.name.strip(),
                payload.alias.strip() or payload.name.strip(),
                payload.domain.strip(),
                payload.type.strip(),
                payload.intro.strip(),
                payload.stage,
                payload.color,
                timestamp,
                timestamp,
            ),
        )
        result = self.get_by_id(client_id)
        assert result is not None, "create 后立即读不到, db 异常"
        return result

    def update(self, client_id: str, patch: ClientUpdatePayload) -> ClientRecord:
        """部分更新。patch 里 None 字段不动。

        Raises:
            ValueError: client 不存在
        """
        existing = self.get_by_id(client_id)
        if existing is None:
            raise ValueError(f"client not found: {client_id}")

        # 构建 dynamic update SQL
        updates: list[str] = []
        params: list[Any] = []
        for field_name in (
            "name", "alias", "domain", "type", "intro", "stage", "color",
        ):
            new_value = getattr(patch, field_name, None)
            if new_value is not None:
                # strip 文本字段
                if field_name in ("name", "alias", "domain", "type", "intro"):
                    new_value = str(new_value).strip()
                updates.append(f"{field_name} = ?")
                params.append(new_value)

        if not updates:
            return existing  # 没有任何字段要改

        updates.append("updated_at = ?")
        params.append(_now_iso())
        params.append(client_id)

        self._db.execute(
            f"UPDATE clients SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        result = self.get_by_id(client_id)
        assert result is not None, "update 后立即读不到"
        return result

    # ── 状态唯一真相 (L2 核心) ────────────────────────────────────
    def freeze(self, client_id: str, reason: str = "") -> ClientRecord:
        """冻结 = 不被云端同步覆盖。L2 状态字段唯一真相的入口。

        修 v1.0 'frozen_at 被云端覆盖' bug 的关键 — 只能通过本方法改 stage='frozen'。
        Phase 1 F1.7 会扩 client_stage_audit 表记录 reason + by_user。

        Args:
            client_id: 要冻结的客户 id
            reason: 冻结原因 (Phase 1 暂未持久化, F1.7 实施时再补)
        """
        existing = self.get_by_id(client_id)
        if existing is None:
            raise ValueError(f"client not found: {client_id}")
        if existing.stage == "frozen":
            return existing  # 已冻结, 幂等
        # TODO Phase 1 F1.7: INSERT INTO client_stage_audit (..., reason=reason, ...)
        _ = reason  # 当前 unused, F1.7 会用
        return self.update(client_id, ClientUpdatePayload(stage="frozen"))

    def unfreeze(self, client_id: str) -> ClientRecord:
        """解冻 → stage='active'"""
        existing = self.get_by_id(client_id)
        if existing is None:
            raise ValueError(f"client not found: {client_id}")
        return self.update(client_id, ClientUpdatePayload(stage="active"))

    def archive(self, client_id: str) -> ClientRecord:
        """归档 → stage='archived' (仍可读, 默认列表隐藏)"""
        return self.update(client_id, ClientUpdatePayload(stage="archived"))

    def is_frozen(self, client_id: str) -> bool:
        """是否处于 frozen 状态 (多账号同步时此态不被云端覆盖)"""
        client = self.get_by_id(client_id)
        return client is not None and client.stage == "frozen"

    def is_archived(self, client_id: str) -> bool:
        """是否处于 archived 或 lost 状态"""
        client = self.get_by_id(client_id)
        return client is not None and client.stage in ("archived", "lost")

    def can_write(self, client_id: str) -> bool:
        """是否允许业务写入。

        frozen / archived / lost 都不允许。这是写入前的统一守门。
        """
        client = self.get_by_id(client_id)
        if client is None:
            return False
        return client.stage not in ("frozen", "archived", "lost")


def get_client_repository(db: Any) -> ClientRepository:
    """工厂方法 - 跟 W1 OrganizationRepository 模式一致"""
    return ClientRepository(db)
