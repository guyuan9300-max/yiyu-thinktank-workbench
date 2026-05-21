"""organization 模块 · 云端 → 本地 mirror 表同步

入口:
    sync_organization_directory(db, settings_store) -> SyncReport

数据流:
    火山云 cloud_backend HTTP API
        ├─ GET /api/v1/settings/org-model/profile   → mirror_organizations + mirror_departments
        └─ GET /api/v1/employees/directory          → mirror_users(主体 + 部门绑定)
    本地 clients 表(已经被现有 cloud sync 同步)
        └─ clients.related_user_ids_json           → mirror_client_related_users(派生,不再调云端)

设计原则:
1. 单次 sync 是原子事务:要么 4 张表全更新,要么全回滚
2. 失败降级:HTTP 报错 / 网络断 → 保留旧 mirror,业务继续跑
3. 全量同步(数据量小,几十-几百行)+ 删除云端不再存在的行
4. sync 程序写 mirror 表时刷新 synced_from_cloud_at,绕过 readonly trigger
5. 调用方决定时机:启动时跑一次 / 手动触发 / 定时器
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 返回报告
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SyncTableReport:
    table: str
    upserted: int
    deleted: int
    skipped: int = 0


@dataclass(frozen=True)
class SyncReport:
    status: str  # "ok" / "skipped" / "failed"
    synced_at: str
    error: str | None = None
    tables: list[SyncTableReport] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# HTTP 帮手(stdlib only,避免引入新依赖)
# ─────────────────────────────────────────────────────────────────────────────


def _http_get_json(
    base_url: str,
    path: str,
    token: str,
    *,
    timeout: float = 10.0,
) -> Any:
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else None


# ─────────────────────────────────────────────────────────────────────────────
# 数据转换:云端 JSON → mirror row
# ─────────────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _normalize_organization(record: dict, synced_at: str) -> dict:
    """从 org-model/profile.organization 字段提取"""
    return {
        "id": record["organizationId"],
        "name": record.get("name", ""),
        "slug": record.get("slug", ""),
        "cloud_updated_at": record.get("updatedAt", ""),
        "synced_from_cloud_at": synced_at,
    }


def _normalize_department(record: dict, organization_id: str, synced_at: str) -> dict:
    return {
        "id": record["id"],
        "organization_id": organization_id,
        "name": record.get("name", ""),
        "color": record.get("color", ""),
        "leader_user_id": record.get("leaderUserId"),
        "leader_name": record.get("leaderName", ""),
        "parent_department_id": record.get("parentDepartmentId"),
        "active": 1 if record.get("active", True) else 0,
        "cloud_updated_at": record.get("updatedAt", ""),
        "synced_from_cloud_at": synced_at,
    }


def _normalize_user(
    employee: dict,
    binding: dict | None,
    organization_id: str,
    synced_at: str,
) -> dict:
    """合并 employee record 跟 org_employee_role_binding(可能 None)"""
    return {
        "id": employee["id"],
        "organization_id": organization_id,
        "department_id": employee.get("departmentId") or (binding.get("departmentId") if binding else None),
        "full_name": employee.get("fullName", ""),
        "email": employee.get("email") or "",
        "primary_role": employee.get("primaryRole") or "",
        "account_status": employee.get("accountStatus") or "",
        "membership_status": employee.get("membershipStatus") or "",
        "is_department_lead": 1 if employee.get("isDepartmentLead") else 0,
        "is_manager": 1 if (binding and binding.get("isManager")) else 0,
        "manager_user_id": (binding.get("managerUserId") if binding else None),
        "task_edit_scope": (binding.get("taskEditScope") if binding else "self") or "self",
        "can_approve_tasks": 1 if (binding and binding.get("canApproveTasks")) else 0,
        "can_reassign_tasks": 1 if (binding and binding.get("canReassignTasks")) else 0,
        "can_change_deadline": 1 if (binding and binding.get("canChangeDeadline")) else 0,
        "project_role_labels_json": json.dumps(
            (binding.get("projectRoleLabels") if binding else []) or [],
            ensure_ascii=False,
        ),
        "avatar_url": employee.get("avatarUrl") or "",
        "cloud_updated_at": employee.get("updatedAt", ""),
        "synced_from_cloud_at": synced_at,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────


def sync_organization_directory(
    db: Any,
    *,
    cloud_base_url: str,
    cloud_token: str,
    derive_cru_from_local: bool = True,
    http_get: Callable[..., Any] | None = None,
    now_iso: Callable[[], str] | None = None,
) -> SyncReport:
    """从火山云同步组织目录到本地 4 张 mirror 表

    参数:
        db: app.db.Database 实例
        cloud_base_url: 火山云地址(http://101.126.34.232)
        cloud_token: JWT
        derive_cru_from_local: True = 从本地 clients.related_user_ids_json 派生
                              mirror_client_related_users(默认开)
        http_get: 注入点(测试用 mock)
        now_iso: 注入点(测试用固定时间)

    返回 SyncReport:
        - status='ok' / 'skipped' / 'failed'
        - tables 列表:每张 mirror 表的 upserted/deleted 计数
    """
    http = http_get or _http_get_json
    clock = now_iso or _now_iso

    if not cloud_base_url or not cloud_token:
        return SyncReport(status="skipped", synced_at=clock(), error="missing cloud_base_url or token")

    synced_at = clock()

    # ─── 第 1 步:拉 3 个 API ───
    try:
        org_profile = http(cloud_base_url, "/api/v1/settings/org-model/profile", cloud_token)
        employees = http(cloud_base_url, "/api/v1/employees/directory", cloud_token)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        logger.warning("organization sync HTTP failed, keeping old mirror: %r", exc)
        return SyncReport(status="failed", synced_at=synced_at, error=f"http: {exc}")
    except json.JSONDecodeError as exc:
        return SyncReport(status="failed", synced_at=synced_at, error=f"json: {exc}")

    if not isinstance(org_profile, dict) or "organization" not in org_profile:
        return SyncReport(status="failed", synced_at=synced_at, error="org_profile shape unexpected")
    if not isinstance(employees, list):
        return SyncReport(status="failed", synced_at=synced_at, error="employees not a list")

    # ─── 第 2 步:转换 ───
    org_record = _normalize_organization(org_profile["organization"], synced_at)
    org_id = org_record["id"]

    dept_records = [
        _normalize_department(d, org_id, synced_at) for d in org_profile.get("departments", [])
    ]

    bindings_by_user = {
        b["userId"]: b for b in org_profile.get("bindings", []) if isinstance(b, dict) and b.get("userId")
    }
    user_records = [
        _normalize_user(emp, bindings_by_user.get(emp["id"]), org_id, synced_at)
        for emp in employees
        if isinstance(emp, dict) and emp.get("id")
    ]

    # ─── 第 3 步:从本地 clients.related_user_ids_json 派生 mirror_client_related_users ───
    # 注意:client_related_users 数据走的不是独立云端 endpoint,
    # 而是本地 clients 表的 JSON 列(已被现有 cloud sync 同步)
    cru_records: list[dict] = []
    cru_client_ids: list[str] = []
    cru_skipped = 0
    if derive_cru_from_local:
        try:
            client_rows = db.fetchall(
                "SELECT id, related_user_ids_json, updated_at FROM clients"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("local clients fetch for CRU derive failed: %r", exc)
            client_rows = []
        for row in client_rows:
            cid = row["id"]
            cru_client_ids.append(cid)
            raw = row["related_user_ids_json"] or "[]"
            try:
                user_ids = json.loads(raw) if raw else []
            except json.JSONDecodeError:
                cru_skipped += 1
                continue
            if not isinstance(user_ids, list):
                continue
            for idx, uid in enumerate(user_ids):
                if not uid:
                    continue
                cru_records.append({
                    "client_id": cid,
                    "user_id": str(uid),
                    "order_index": idx,
                    "cloud_updated_at": row["updated_at"] or "",
                    "synced_from_cloud_at": synced_at,
                })

    # ─── 第 4 步:原子写入(事务)───
    reports: list[SyncTableReport] = []
    try:
        with db._lock:  # 复用 Database 的 RLock
            db.conn.execute("BEGIN")

            reports.append(_upsert_table(
                db.conn,
                "mirror_organizations",
                ["id", "name", "slug", "cloud_updated_at", "synced_from_cloud_at"],
                [org_record],
                id_columns=["id"],
            ))
            reports.append(_upsert_table(
                db.conn,
                "mirror_departments",
                ["id", "organization_id", "name", "color", "leader_user_id", "leader_name",
                 "parent_department_id", "active", "cloud_updated_at", "synced_from_cloud_at"],
                dept_records,
                id_columns=["id"],
            ))
            reports.append(_upsert_table(
                db.conn,
                "mirror_users",
                ["id", "organization_id", "department_id", "full_name", "email", "primary_role",
                 "account_status", "membership_status", "is_department_lead", "is_manager",
                 "manager_user_id", "task_edit_scope", "can_approve_tasks", "can_reassign_tasks",
                 "can_change_deadline", "project_role_labels_json", "avatar_url",
                 "cloud_updated_at", "synced_from_cloud_at"],
                user_records,
                id_columns=["id"],
            ))
            if derive_cru_from_local:
                # scope = 本地 clients 表里所有 client_id
                # 这样能正确处理:client 删了 → 它的 cru row 也删
                #                 client 的 related_user_ids 缩减 → 多出来的 user_id 删
                cru_report = _upsert_table(
                    db.conn,
                    "mirror_client_related_users",
                    ["client_id", "user_id", "order_index", "cloud_updated_at", "synced_from_cloud_at"],
                    cru_records,
                    id_columns=["client_id", "user_id"],
                    delete_scope_sql=(
                        "client_id IN ({})".format(",".join("?" * len(cru_client_ids)))
                        if cru_client_ids else "1=1"
                    ),
                    delete_scope_params=cru_client_ids,
                )
                reports.append(SyncTableReport(
                    table=cru_report.table,
                    upserted=cru_report.upserted,
                    deleted=cru_report.deleted,
                    skipped=cru_skipped,
                ))

            db.conn.commit()
    except Exception as exc:  # noqa: BLE001
        db.conn.rollback()
        logger.error("organization sync DB write failed: %r", exc, exc_info=True)
        return SyncReport(status="failed", synced_at=synced_at, error=f"db: {exc}")

    return SyncReport(status="ok", synced_at=synced_at, tables=reports)


_ALLOWED_SYNC_TABLES = {
    "mirror_organizations",
    "mirror_departments",
    "mirror_users",
    "mirror_client_related_users",
}
_IDENT_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


def _assert_safe_ident(name: str, kind: str) -> None:
    """白名单 + 正则校验, 防止表名/列名 SQL 注入 (P0 防御)."""
    if not name or not _IDENT_PATTERN.match(name):
        raise ValueError(f"unsafe {kind} identifier: {name!r}")


def _upsert_table(
    conn,
    table: str,
    columns: list[str],
    rows: list[dict],
    *,
    id_columns: list[str],
    delete_scope_sql: str | None = None,
    delete_scope_params: list[str] | None = None,
) -> SyncTableReport:
    """UPSERT + 删除 scope 内云端不再存在的行.

    P0 安全: table 必须在 _ALLOWED_SYNC_TABLES 白名单, 所有 columns/id_columns
    都过 _assert_safe_ident 防止 SQL injection.
    """
    if table not in _ALLOWED_SYNC_TABLES:
        raise ValueError(f"table {table!r} not in sync whitelist")
    for col in columns:
        _assert_safe_ident(col, "column")
    for col in id_columns:
        _assert_safe_ident(col, "id_column")
    # 1. UPSERT
    placeholders = ",".join("?" * len(columns))
    col_list = ",".join(columns)
    update_set = ",".join(f"{c}=excluded.{c}" for c in columns if c not in id_columns)
    pk_list = ",".join(id_columns)
    sql = (
        f"INSERT INTO {table}({col_list}) VALUES({placeholders}) "
        f"ON CONFLICT({pk_list}) DO UPDATE SET {update_set}"
    )
    upserted = 0
    for row in rows:
        conn.execute(sql, tuple(row.get(c) for c in columns))
        upserted += 1

    # 2. 删除 scope 内云端不再存在的 row
    if rows:
        kept_ids_sql = " OR ".join(
            "(" + " AND ".join(f"{c}=?" for c in id_columns) + ")"
            for _ in rows
        )
        kept_params: list = []
        for row in rows:
            kept_params.extend(row.get(c) for c in id_columns)
        scope_where = delete_scope_sql or "1=1"
        scope_params = delete_scope_params or []
        delete_sql = f"DELETE FROM {table} WHERE {scope_where} AND NOT ({kept_ids_sql})"
        cur = conn.execute(delete_sql, list(scope_params) + kept_params)
        deleted = cur.rowcount or 0
    else:
        # 空 rows + 有 scope = 删 scope 内全部
        if delete_scope_sql:
            cur = conn.execute(
                f"DELETE FROM {table} WHERE {delete_scope_sql}",
                list(delete_scope_params or []),
            )
            deleted = cur.rowcount or 0
        else:
            deleted = 0

    return SyncTableReport(table=table, upserted=upserted, deleted=deleted)
