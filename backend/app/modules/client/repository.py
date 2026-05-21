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
    def _write_stage_audit(
        self,
        *,
        client_id: str,
        old_stage: str | None,
        new_stage: str,
        actor_type: str = "human",
        actor_id: str = "",
        reason: str = "",
        guard_action: str = "applied",
    ) -> None:
        """v2.2 F1.7: 客户阶段变更审计落地。

        所有 clients.stage 变化必须经此. 用法:
        - freeze/unfreeze/archive 内部自动调用
        - cloud sync 覆盖被守门时也写一条 guard_action='guarded' (用于诊断 v1.0 bug)

        N3 (3.0 接入预留): actor_type 区分 human/ai_agent/system, 后续 AI agent 改阶段时一致。
        """
        self._db.execute(
            """
            INSERT INTO client_stage_audit (
                client_id, old_stage, new_stage,
                actor_type, actor_id, reason, guard_action, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                old_stage,
                new_stage,
                actor_type,
                actor_id,
                reason,
                guard_action,
                _now_iso(),
            ),
        )

    def freeze(
        self,
        client_id: str,
        reason: str = "",
        *,
        actor_type: str = "human",
        actor_id: str = "",
    ) -> ClientRecord:
        """冻结 = 不被云端同步覆盖。L2 状态字段唯一真相的入口。

        修 v1.0 'frozen_at 被云端覆盖' bug 的关键 — 只能通过本方法改 stage='frozen'。
        v2.2 F1.7 落地: 写 client_stage_audit log 记录 actor + reason。

        N3 (3.0 接入预留): actor_type='ai_agent' 时表示 AI 主动冻结, 跟人触发区分。

        Args:
            client_id: 要冻结的客户 id
            reason: 冻结原因 (持久化到 audit log)
            actor_type: 'human' / 'ai_agent' / 'system'
            actor_id: user_id 或 ai_session_id
        """
        existing = self.get_by_id(client_id)
        if existing is None:
            raise ValueError(f"client not found: {client_id}")
        if existing.stage == "frozen":
            return existing  # 已冻结, 幂等
        old_stage = existing.stage
        result = self.update(client_id, ClientUpdatePayload(stage="frozen"))
        self._write_stage_audit(
            client_id=client_id,
            old_stage=old_stage,
            new_stage="frozen",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
        )
        return result

    def unfreeze(
        self,
        client_id: str,
        reason: str = "",
        *,
        actor_type: str = "human",
        actor_id: str = "",
    ) -> ClientRecord:
        """解冻 → stage='active', 写 audit log"""
        existing = self.get_by_id(client_id)
        if existing is None:
            raise ValueError(f"client not found: {client_id}")
        if existing.stage == "active":
            return existing
        old_stage = existing.stage
        result = self.update(client_id, ClientUpdatePayload(stage="active"))
        self._write_stage_audit(
            client_id=client_id,
            old_stage=old_stage,
            new_stage="active",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
        )
        return result

    def archive(
        self,
        client_id: str,
        reason: str = "",
        *,
        actor_type: str = "human",
        actor_id: str = "",
    ) -> ClientRecord:
        """归档 → stage='archived' (仍可读, 默认列表隐藏), 写 audit log"""
        existing = self.get_by_id(client_id)
        if existing is None:
            raise ValueError(f"client not found: {client_id}")
        if existing.stage == "archived":
            return existing
        old_stage = existing.stage
        result = self.update(client_id, ClientUpdatePayload(stage="archived"))
        self._write_stage_audit(
            client_id=client_id,
            old_stage=old_stage,
            new_stage="archived",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
        )
        return result

    # ── v2.2 F1.7: 多账号同步守门(给 main.py _upsert_cloud_client_shadow_local 用) ─
    def apply_cloud_stage_change(
        self,
        client_id: str,
        cloud_stage: str,
        *,
        actor_id: str = "cloud_sync",
    ) -> tuple[bool, str]:
        """从云端同步过来的 stage 变化,本地 frozen 时拒绝覆盖。

        修 v1.0 bug: 'local 冷冻被云端 active 覆盖' 的核心守门。

        Args:
            client_id: 客户 id
            cloud_stage: 云端要写入的新 stage
            actor_id: 标识同步来源, 默认 'cloud_sync'

        Returns:
            (applied, message)
            - applied=True: 已写入, message=''
            - applied=False: 守门拒绝, message='local frozen, cloud stage X rejected'
        """
        existing = self.get_by_id(client_id)
        if existing is None:
            # 新客户, 直接走云端 stage (没有本地状态可保护)
            return (True, "")

        old_stage = existing.stage
        if old_stage == cloud_stage:
            return (True, "")  # 一致, 无需变化

        # ★ 守门规则: 本地 frozen 不被云端覆盖
        if old_stage == "frozen" and cloud_stage != "frozen":
            self._write_stage_audit(
                client_id=client_id,
                old_stage=old_stage,
                new_stage=cloud_stage,  # 记录云端想改的目标
                actor_type="system",
                actor_id=actor_id,
                reason=f"local frozen, cloud stage='{cloud_stage}' rejected (v1.0 bug guard)",
                guard_action="guarded",
            )
            return (False, f"local frozen, cloud stage '{cloud_stage}' rejected")

        # 其他 stage 变化照常应用 + 写 audit
        self.update(client_id, ClientUpdatePayload(stage=cloud_stage))
        self._write_stage_audit(
            client_id=client_id,
            old_stage=old_stage,
            new_stage=cloud_stage,
            actor_type="system",
            actor_id=actor_id,
            reason=f"cloud sync stage change",
        )
        return (True, "")

    def list_stage_audit(
        self,
        client_id: str,
        *,
        limit: int = 50,
        guarded_only: bool = False,
    ) -> list[dict[str, Any]]:
        """读 client_stage_audit log. 用于 dogfood 时诊断 v1.0 bug 是否复现。

        Args:
            client_id: 客户 id
            limit: 返回最近 N 条
            guarded_only: 只看被云端覆盖守门挡下的记录
        """
        where = "WHERE client_id = ?"
        params: tuple[Any, ...] = (client_id,)
        if guarded_only:
            where += " AND guard_action = 'guarded'"
        rows = self._db.fetchall(
            f"""
            SELECT id, client_id, old_stage, new_stage, actor_type, actor_id,
                   reason, guard_action, changed_at
            FROM client_stage_audit
            {where}
            ORDER BY changed_at DESC
            LIMIT ?
            """,
            (*params, limit),
        )
        return [
            {
                "id": int(r["id"]),
                "client_id": str(r["client_id"]),
                "old_stage": str(r["old_stage"]) if r["old_stage"] else None,
                "new_stage": str(r["new_stage"]),
                "actor_type": str(r["actor_type"]),
                "actor_id": str(r["actor_id"]),
                "reason": str(r["reason"]),
                "guard_action": str(r["guard_action"]),
                "changed_at": str(r["changed_at"]),
            }
            for r in rows
        ]

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
