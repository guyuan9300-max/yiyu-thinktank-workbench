from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from sqlite3 import Row
from typing import Any
from uuid import uuid4

from app.db import Database
from app.models import SandboxLocalDraftSummary, SandboxWorkspaceRecord, SandboxWorkspacesResponse


ACTIVE_SANDBOX_SETTING_KEY = "active_sandbox_id"
DEFAULT_LOCAL_SANDBOX_ID = "sbx_local_default"
LOCAL_DRAFT_MIGRATION_SETTING_KEY = "local_draft_migrated_to_sandbox_id"
CLOUD_SANDBOX_SETTING_KEYS = (
    "cloud_api_url",
    "cloud_access_token",
    "cloud_refresh_token",
    "cloud_session_user",
)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _safe_slug(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return (normalized or fallback)[:80]


def _normalize_cloud_api_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/")


def _cloud_id_suffix(cloud_api_url: str) -> str:
    normalized = _normalize_cloud_api_url(cloud_api_url)
    if not normalized:
        return "no_cloud"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]


def _load_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _cloud_session_user(db: Database) -> dict[str, Any]:
    return _load_json_object(db.get_setting("cloud_session_user", ""))


def _default_sandbox_values(db: Database, now: str) -> dict[str, Any]:
    session_user = _cloud_session_user(db)
    organization_id = str(session_user.get("organizationId") or "").strip()
    organization_name = str(session_user.get("organizationName") or "").strip()
    cloud_api_url = _normalize_cloud_api_url(db.get_setting("cloud_api_url", ""))
    if organization_id:
        safe_org = _safe_slug(organization_id, "legacy_org")
        display_name = organization_name or "组织工作空间"
        return {
            "id": f"sbx_org_{safe_org}",
            "kind": "organization",
            "name": display_name,
            "status": "active",
            "cloud_api_url": cloud_api_url,
            "organization_id": organization_id,
            "organization_name": organization_name or None,
            "local_identity_id": None,
            "is_legacy_default": 1,
            "metadata_json": json.dumps({"createdBy": "stage1_legacy_bootstrap"}, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
            "last_active_at": now,
        }
    return {
        "id": DEFAULT_LOCAL_SANDBOX_ID,
        "kind": "local",
        "name": "未连接组织的本机草稿",
        "status": "active",
        "cloud_api_url": "",
        "organization_id": None,
        "organization_name": None,
        "local_identity_id": db.get_setting("local_session_user_id", "").strip() or None,
        "is_legacy_default": 1,
        "metadata_json": json.dumps({"createdBy": "stage1_legacy_bootstrap"}, ensure_ascii=False),
        "created_at": now,
        "updated_at": now,
        "last_active_at": now,
    }


def _default_local_sandbox_values(db: Database, now: str, *, is_legacy_default: bool = False) -> dict[str, Any]:
    return {
        "id": DEFAULT_LOCAL_SANDBOX_ID,
        "kind": "local",
        "name": "未连接组织的本机草稿",
        "status": "active",
        "cloud_api_url": "",
        "organization_id": None,
        "organization_name": None,
        "local_identity_id": db.get_setting("local_session_user_id", "").strip() or None,
        "is_legacy_default": 1 if is_legacy_default else 0,
        "metadata_json": json.dumps({"createdBy": "stage7_local_workspace"}, ensure_ascii=False),
        "created_at": now,
        "updated_at": now,
        "last_active_at": now if is_legacy_default else None,
    }


def _insert_sandbox(conn: Any, values: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO sandboxes(
            id, kind, name, status, cloud_api_url, organization_id, organization_name,
            local_identity_id, is_legacy_default, metadata_json, created_at, updated_at, last_active_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (
            values["id"],
            values["kind"],
            values["name"],
            values["status"],
            values["cloud_api_url"],
            values["organization_id"],
            values["organization_name"],
            values["local_identity_id"],
            values["is_legacy_default"],
            values["metadata_json"],
            values["created_at"],
            values["updated_at"],
            values["last_active_at"],
        ),
    )


def _write_sandbox_setting_to_conn(conn: Any, sandbox_id: str, key: str, value: str) -> None:
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO sandbox_settings(sandbox_id, key, value, updated_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(sandbox_id, key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (sandbox_id, key, value or "", now),
    )
    if key == "cloud_api_url":
        conn.execute(
            "UPDATE sandboxes SET cloud_api_url = ?, updated_at = ? WHERE id = ?",
            (value or "", now, sandbox_id),
        )


def _copy_legacy_cloud_settings_if_needed(conn: Any, sandbox_id: str) -> None:
    sandbox_row = conn.execute("SELECT is_legacy_default FROM sandboxes WHERE id = ?", (sandbox_id,)).fetchone()
    is_legacy_default = bool(sandbox_row and int((sandbox_row["is_legacy_default"] if isinstance(sandbox_row, Row) else sandbox_row[0]) or 0))
    if not is_legacy_default:
        return
    row = conn.execute(
        "SELECT COUNT(1) AS count FROM sandbox_settings WHERE sandbox_id = ? AND key IN (?, ?, ?, ?)",
        (sandbox_id, *CLOUD_SANDBOX_SETTING_KEYS),
    ).fetchone()
    existing_count = int((row["count"] if isinstance(row, Row) else row[0]) or 0) if row else 0
    if existing_count > 0:
        return
    for key in CLOUD_SANDBOX_SETTING_KEYS:
        legacy_row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        legacy_value = str(legacy_row["value"] if isinstance(legacy_row, Row) else legacy_row[0]) if legacy_row else ""
        if legacy_value:
            _write_sandbox_setting_to_conn(conn, sandbox_id, key, legacy_value)


def _conn_has_column(conn: Any, table: str, column: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return False
    for row in rows:
        name = row["name"] if isinstance(row, Row) else row[1]
        if str(name) == column:
            return True
    return False


def _ensure_business_data_sandbox_scope(db: Database, sandbox_id: str) -> None:
    """Backfill Stage 5 root business data into the active/default workspace.

    This is intentionally narrow: it only stamps root business tables that now
    carry sandbox_id. Documents continue to inherit visibility through clients.
    """

    normalized_sandbox_id = (sandbox_id or DEFAULT_LOCAL_SANDBOX_ID).strip() or DEFAULT_LOCAL_SANDBOX_ID

    def _txn(conn: Any) -> None:
        for table in ("clients", "tasks", "task_lists", "task_tags"):
            if not _conn_has_column(conn, table, "sandbox_id"):
                continue
            conn.execute(
                f"UPDATE {table} SET sandbox_id = ? WHERE COALESCE(sandbox_id, '') = ''",
                (normalized_sandbox_id,),
            )

    db.run_in_transaction(_txn)


def _table_has_column(conn: Any, table: str, column: str) -> bool:
    return _conn_has_column(conn, table, column)


def _local_draft_counts_from_conn(conn: Any) -> dict[str, int]:
    counts: dict[str, int] = {
        "clients": 0,
        "tasks": 0,
        "taskLists": 0,
        "taskTags": 0,
        "documents": 0,
        "experienceQuotes": 0,
    }
    for table, key in (
        ("clients", "clients"),
        ("tasks", "tasks"),
        ("task_lists", "taskLists"),
        ("task_tags", "taskTags"),
        ("exp_wall_quotes", "experienceQuotes"),
    ):
        if _table_has_column(conn, table, "sandbox_id"):
            row = conn.execute(
                f"SELECT COUNT(1) AS count FROM {table} WHERE sandbox_id = ?",
                (DEFAULT_LOCAL_SANDBOX_ID,),
            ).fetchone()
            counts[key] = int((row["count"] if isinstance(row, Row) else row[0]) or 0) if row else 0
    if _table_has_column(conn, "clients", "sandbox_id"):
        row = conn.execute(
            """
            SELECT COUNT(1) AS count
              FROM documents d
              JOIN clients c ON c.id = d.client_id
             WHERE c.sandbox_id = ?
            """,
            (DEFAULT_LOCAL_SANDBOX_ID,),
        ).fetchone()
        counts["documents"] = int((row["count"] if isinstance(row, Row) else row[0]) or 0) if row else 0
    return counts


def _counts_have_data(counts: dict[str, int]) -> bool:
    return any(int(value or 0) > 0 for value in counts.values())


def _best_organization_target_from_conn(conn: Any, active_id: str = "") -> str:
    if active_id:
        row = conn.execute(
            "SELECT id FROM sandboxes WHERE id = ? AND kind = 'organization' AND status = 'active'",
            (active_id,),
        ).fetchone()
        if row:
            return str(row["id"] if isinstance(row, Row) else row[0])
    row = conn.execute(
        """
        SELECT id FROM sandboxes
         WHERE kind = 'organization' AND status = 'active'
         ORDER BY COALESCE(last_active_at, created_at) DESC, created_at ASC
         LIMIT 1
        """
    ).fetchone()
    return str(row["id"] if isinstance(row, Row) else row[0]) if row else ""


def _merge_local_metadata(raw: str | None, patch: dict[str, Any]) -> str:
    metadata = _load_json_object(raw)
    metadata.update(patch)
    return json.dumps(metadata, ensure_ascii=False)


def migrate_local_draft_to_organization_if_possible(db: Database, target_sandbox_id: str | None = None) -> dict[str, Any]:
    """Move visible draft data out of the old local workspace when an org exists.

    The local row is kept as an internal historical container for rollback and
    no-org draft compatibility, but it is no longer a user-manageable workspace.
    """

    now = _now_iso()

    def _txn(conn: Any) -> dict[str, Any]:
        active_row = conn.execute("SELECT value FROM settings WHERE key = ?", (ACTIVE_SANDBOX_SETTING_KEY,)).fetchone()
        active_id = str(active_row["value"] if isinstance(active_row, Row) else active_row[0]).strip() if active_row else ""
        target_id = (target_sandbox_id or "").strip() or _best_organization_target_from_conn(conn, active_id)
        local_row = conn.execute("SELECT * FROM sandboxes WHERE id = ?", (DEFAULT_LOCAL_SANDBOX_ID,)).fetchone()
        counts = _local_draft_counts_from_conn(conn)
        has_data = _counts_have_data(counts)
        if not local_row:
            return {"migrated": False, "reason": "no_local_draft", "counts": counts}
        if not target_id:
            metadata_json = _merge_local_metadata(
                str(local_row["metadata_json"] or "{}"),
                {"internalDraft": True, "hiddenFromWorkspaceList": True, "updatedAt": now},
            )
            conn.execute(
                "UPDATE sandboxes SET name = ?, metadata_json = ?, updated_at = ? WHERE id = ?",
                ("未连接组织的本机草稿", metadata_json, now, DEFAULT_LOCAL_SANDBOX_ID),
            )
            return {"migrated": False, "reason": "no_organization_target", "counts": counts}
        target = conn.execute(
            "SELECT id FROM sandboxes WHERE id = ? AND kind = 'organization' AND status = 'active'",
            (target_id,),
        ).fetchone()
        if not target:
            return {"migrated": False, "reason": "invalid_organization_target", "counts": counts}

        if has_data:
            local_task_list_ids: set[str] = set()
            if _table_has_column(conn, "tasks", "sandbox_id"):
                for row in conn.execute(
                    """
                    SELECT DISTINCT list_id FROM tasks
                     WHERE sandbox_id = ?
                       AND list_id IS NOT NULL
                       AND list_id != ''
                    """,
                    (DEFAULT_LOCAL_SANDBOX_ID,),
                ).fetchall():
                    raw = row["list_id"] if isinstance(row, Row) else row[0]
                    if raw:
                        local_task_list_ids.add(str(raw))
            if _table_has_column(conn, "clients", "sandbox_id"):
                conn.execute("UPDATE clients SET sandbox_id = ? WHERE sandbox_id = ?", (target_id, DEFAULT_LOCAL_SANDBOX_ID))
            if _table_has_column(conn, "tasks", "sandbox_id"):
                conn.execute("UPDATE tasks SET sandbox_id = ? WHERE sandbox_id = ?", (target_id, DEFAULT_LOCAL_SANDBOX_ID))
            if _table_has_column(conn, "task_lists", "sandbox_id"):
                id_placeholders = ",".join(["?"] * len(local_task_list_ids))
                id_filter = f" OR id IN ({id_placeholders})" if id_placeholders else ""
                conn.execute(
                    f"""
                    UPDATE task_lists
                       SET sandbox_id = ?
                     WHERE sandbox_id = ?
                       AND (
                            name NOT IN ('收集箱', '健身', '约会', '吃饭', '学习')
                            {id_filter}
                       )
                    """,
                    (target_id, DEFAULT_LOCAL_SANDBOX_ID, *sorted(local_task_list_ids)),
                )
            if _table_has_column(conn, "task_tags", "sandbox_id"):
                conn.execute(
                    """
                    UPDATE task_tags
                       SET sandbox_id = ?
                     WHERE sandbox_id = ?
                       AND name NOT IN (
                           SELECT target.name
                             FROM task_tags target
                            WHERE target.sandbox_id = ?
                       )
                    """,
                    (target_id, DEFAULT_LOCAL_SANDBOX_ID, target_id),
                )
            if _table_has_column(conn, "exp_wall_quotes", "sandbox_id"):
                conn.execute("UPDATE exp_wall_quotes SET sandbox_id = ? WHERE sandbox_id = ?", (target_id, DEFAULT_LOCAL_SANDBOX_ID))
            if _table_has_column(conn, "exp_wall_reactions", "sandbox_id"):
                conn.execute("UPDATE exp_wall_reactions SET sandbox_id = ? WHERE sandbox_id = ?", (target_id, DEFAULT_LOCAL_SANDBOX_ID))
            for table in (
                "handbook_entries",
                "growth_signal_events",
                "growth_evidence_records",
                "growth_validation_events",
                "xp_ledger",
                "badge_unlock_records",
                "learning_recommendations",
            ):
                if _table_has_column(conn, table, "sandbox_id"):
                    conn.execute(
                        f"UPDATE {table} SET sandbox_id = ? WHERE sandbox_id = ?",
                        (target_id, DEFAULT_LOCAL_SANDBOX_ID),
                    )

        metadata_json = _merge_local_metadata(
            str(local_row["metadata_json"] or "{}"),
            {
                "internalDraft": True,
                "hiddenFromWorkspaceList": True,
                "migrated": bool(has_data),
                "migratedToSandboxId": target_id,
                "migratedAt": now,
                "migrationCounts": counts,
            },
        )
        conn.execute(
            """
            UPDATE sandboxes
               SET status = 'archived',
                   name = ?,
                   metadata_json = ?,
                   updated_at = ?
             WHERE id = ?
            """,
            ("本机历史草稿（已归档）", metadata_json, now, DEFAULT_LOCAL_SANDBOX_ID),
        )
        conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (LOCAL_DRAFT_MIGRATION_SETTING_KEY, target_id),
        )
        if active_id == DEFAULT_LOCAL_SANDBOX_ID:
            conn.execute(
                """
                INSERT INTO settings(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (ACTIVE_SANDBOX_SETTING_KEY, target_id),
            )
            conn.execute("UPDATE sandboxes SET last_active_at = ?, updated_at = ? WHERE id = ?", (now, now, target_id))
        return {"migrated": bool(has_data), "targetSandboxId": target_id, "counts": counts}

    return dict(db.run_in_transaction(_txn))


def get_local_draft_summary(db: Database, active_id: str | None = None) -> SandboxLocalDraftSummary:
    def _txn(conn: Any) -> SandboxLocalDraftSummary:
        local_row = conn.execute("SELECT * FROM sandboxes WHERE id = ?", (DEFAULT_LOCAL_SANDBOX_ID,)).fetchone()
        if not local_row:
            return SandboxLocalDraftSummary()
        counts = _local_draft_counts_from_conn(conn)
        metadata = _load_json_object(str(local_row["metadata_json"] or "{}"))
        return SandboxLocalDraftSummary(
            available=True,
            active=(active_id or "") == DEFAULT_LOCAL_SANDBOX_ID,
            hasData=_counts_have_data(counts),
            migrated=bool(metadata.get("migrated")),
            migratedToSandboxId=str(metadata.get("migratedToSandboxId") or "") or None,
            migratedAt=str(metadata.get("migratedAt") or "") or None,
            clients=counts["clients"],
            tasks=counts["tasks"],
            taskLists=counts["taskLists"],
            taskTags=counts["taskTags"],
            documents=counts["documents"],
            experienceQuotes=counts["experienceQuotes"],
        )

    return db.run_in_transaction(_txn, mode="DEFERRED")


def ensure_sandbox_registry(db: Database) -> str:
    """Ensure the workspace shell exists without migrating business data."""

    now = _now_iso()
    default_values = _default_sandbox_values(db, now)

    def _txn(conn: Any) -> str:
        count_row = conn.execute("SELECT COUNT(1) FROM sandboxes").fetchone()
        sandbox_count = int(count_row[0] or 0) if count_row else 0
        if sandbox_count == 0:
            _insert_sandbox(conn, default_values)
        local_row = conn.execute("SELECT id, local_identity_id FROM sandboxes WHERE id = ?", (DEFAULT_LOCAL_SANDBOX_ID,)).fetchone()
        if not local_row:
            _insert_sandbox(
                conn,
                _default_local_sandbox_values(
                    db,
                    now,
                    is_legacy_default=default_values["id"] == DEFAULT_LOCAL_SANDBOX_ID,
                ),
            )
        else:
            legacy_local_identity_id = db.get_setting("local_session_user_id", "").strip()
            existing_raw = local_row["local_identity_id"] if isinstance(local_row, Row) else local_row[1]
            existing_local_identity_id = str(existing_raw or "").strip()
            if legacy_local_identity_id and not existing_local_identity_id:
                conn.execute(
                    "UPDATE sandboxes SET local_identity_id = ?, updated_at = ? WHERE id = ?",
                    (legacy_local_identity_id, now, DEFAULT_LOCAL_SANDBOX_ID),
                )

        active_row = conn.execute("SELECT value FROM settings WHERE key = ?", (ACTIVE_SANDBOX_SETTING_KEY,)).fetchone()
        active_id = str(active_row["value"] if isinstance(active_row, Row) else active_row[0]).strip() if active_row else ""
        if active_id:
            exists = conn.execute("SELECT id FROM sandboxes WHERE id = ?", (active_id,)).fetchone()
            if exists:
                conn.execute("UPDATE sandboxes SET last_active_at = ?, updated_at = ? WHERE id = ?", (now, now, active_id))
                _copy_legacy_cloud_settings_if_needed(conn, active_id)
                return active_id

        fallback = conn.execute(
            """
            SELECT id FROM sandboxes
            WHERE status = 'active'
            ORDER BY is_legacy_default DESC, COALESCE(last_active_at, created_at) DESC, created_at ASC
            LIMIT 1
            """
        ).fetchone()
        fallback_id = str(fallback["id"] if isinstance(fallback, Row) else fallback[0]) if fallback else default_values["id"]
        conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (ACTIVE_SANDBOX_SETTING_KEY, fallback_id),
        )
        conn.execute("UPDATE sandboxes SET last_active_at = ?, updated_at = ? WHERE id = ?", (now, now, fallback_id))
        _copy_legacy_cloud_settings_if_needed(conn, fallback_id)
        return fallback_id

    active_id = str(db.run_in_transaction(_txn))
    migration_result = migrate_local_draft_to_organization_if_possible(db)
    if migration_result.get("targetSandboxId") and active_id == DEFAULT_LOCAL_SANDBOX_ID:
        active_id = str(migration_result["targetSandboxId"])
    if active_id == DEFAULT_LOCAL_SANDBOX_ID:
        target_id = ""
        def _target_txn(conn: Any) -> str:
            return _best_organization_target_from_conn(conn, "")
        target_id = str(db.run_in_transaction(_target_txn, mode="DEFERRED") or "")
        if target_id:
            activate_sandbox(db, target_id)
            active_id = target_id
    _ensure_business_data_sandbox_scope(db, active_id)
    return active_id


def _record_from_row(db: Database, row: Row) -> SandboxWorkspaceRecord:
    cloud_api_url = get_sandbox_setting(db, str(row["id"]), "cloud_api_url", str(row["cloud_api_url"] or ""))
    access_token = get_sandbox_setting(db, str(row["id"]), "cloud_access_token", "")
    refresh_token = get_sandbox_setting(db, str(row["id"]), "cloud_refresh_token", "")
    session_user = _load_json_object(get_sandbox_setting(db, str(row["id"]), "cloud_session_user", ""))
    return SandboxWorkspaceRecord(
        id=str(row["id"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        name=str(row["name"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        cloudApiUrl=cloud_api_url,
        cloudConnected=bool(access_token or refresh_token or session_user),
        cloudUserFullName=str(session_user.get("fullName") or "") or None,
        cloudUserEmail=str(session_user.get("email") or "") or None,
        organizationId=str(row["organization_id"]) if row["organization_id"] else None,
        organizationName=str(row["organization_name"]) if row["organization_name"] else None,
        localIdentityId=str(row["local_identity_id"]) if row["local_identity_id"] else None,
        isLegacyDefault=bool(row["is_legacy_default"]),
        metadata=_load_json_object(row["metadata_json"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        lastActiveAt=str(row["last_active_at"]) if row["last_active_at"] else None,
    )


def list_sandboxes(db: Database) -> list[SandboxWorkspaceRecord]:
    ensure_sandbox_registry(db)
    rows = db.fetchall(
        """
        SELECT * FROM sandboxes
        WHERE kind = 'organization'
          AND status = 'active'
        ORDER BY is_legacy_default DESC, COALESCE(last_active_at, created_at) DESC, created_at ASC
        """
    )
    return [_record_from_row(db, row) for row in rows]


def get_active_sandbox(db: Database) -> SandboxWorkspaceRecord:
    active_id = ensure_sandbox_registry(db)
    row = db.fetchone("SELECT * FROM sandboxes WHERE id = ?", (active_id,))
    if row:
        return _record_from_row(db, row)
    ensure_sandbox_registry(db)
    row = db.fetchone("SELECT * FROM sandboxes WHERE id = ?", (db.get_setting(ACTIVE_SANDBOX_SETTING_KEY, ""),))
    if not row:
        raise RuntimeError("active sandbox not found after registry repair")
    return _record_from_row(db, row)


def build_workspaces_response(db: Database) -> SandboxWorkspacesResponse:
    active_id = ensure_sandbox_registry(db)
    return SandboxWorkspacesResponse(
        activeSandboxId=active_id,
        workspaces=list_sandboxes(db),
        localDraftSummary=get_local_draft_summary(db, active_id),
    )


def get_sandbox_setting(db: Database, sandbox_id: str, key: str, default: str = "") -> str:
    ensure_sandbox_registry(db)
    row = db.fetchone(
        "SELECT value FROM sandbox_settings WHERE sandbox_id = ? AND key = ?",
        (sandbox_id, key),
    )
    return str(row["value"]) if row else default


def set_sandbox_setting(db: Database, sandbox_id: str, key: str, value: str) -> None:
    ensure_sandbox_registry(db)

    def _txn(conn: Any) -> None:
        exists = conn.execute(
            """
            SELECT id FROM sandboxes
             WHERE id = ?
               AND (
                    (kind = 'organization' AND status = 'active')
                    OR id = ?
               )
            """,
            (sandbox_id, DEFAULT_LOCAL_SANDBOX_ID),
        ).fetchone()
        if not exists:
            raise ValueError("工作空间不存在")
        _write_sandbox_setting_to_conn(conn, sandbox_id, key, value or "")

    db.run_in_transaction(_txn)


def _ensure_visible_organization_sandbox(conn: Any, sandbox_id: str) -> None:
    exists = conn.execute(
        "SELECT id FROM sandboxes WHERE id = ? AND kind = 'organization' AND status = 'active'",
        (sandbox_id,),
    ).fetchone()
    if not exists:
        raise ValueError("工作空间不存在")


def _ensure_any_internal_sandbox(conn: Any, sandbox_id: str) -> None:
    exists = conn.execute(
        """
        SELECT id FROM sandboxes
        WHERE id = ?
           AND (
                (kind = 'organization' AND status = 'active')
                OR id = ?
           )
        """,
            (sandbox_id, DEFAULT_LOCAL_SANDBOX_ID),
        ).fetchone()
    if not exists:
        raise ValueError("工作空间不存在")


def get_sandbox_kind(db: Database, sandbox_id: str) -> str:
    ensure_sandbox_registry(db)
    row = db.fetchone("SELECT kind FROM sandboxes WHERE id = ?", (sandbox_id,))
    return str(row["kind"]) if row else ""


def get_sandbox_local_identity_id(db: Database, sandbox_id: str) -> str:
    ensure_sandbox_registry(db)
    row = db.fetchone("SELECT local_identity_id FROM sandboxes WHERE id = ?", (sandbox_id,))
    return str(row["local_identity_id"] or "") if row else ""


def set_sandbox_local_identity_id(db: Database, sandbox_id: str, identity_id: str | None) -> None:
    ensure_sandbox_registry(db)
    now = _now_iso()

    def _txn(conn: Any) -> None:
        row = conn.execute("SELECT kind FROM sandboxes WHERE id = ?", (sandbox_id,)).fetchone()
        if not row:
            raise ValueError("工作空间不存在")
        kind = str(row["kind"] if isinstance(row, Row) else row[0])
        if kind != "local":
            raise ValueError("本机草稿身份只能绑定到内部本机草稿容器")
        conn.execute(
            "UPDATE sandboxes SET local_identity_id = ?, updated_at = ? WHERE id = ?",
            ((identity_id or "").strip() or None, now, sandbox_id),
        )

    db.run_in_transaction(_txn)


def get_active_sandbox_id(db: Database) -> str:
    return ensure_sandbox_registry(db)


def get_active_sandbox_setting(db: Database, key: str, default: str = "") -> str:
    return get_sandbox_setting(db, ensure_sandbox_registry(db), key, default)


def set_active_sandbox_setting(db: Database, key: str, value: str) -> None:
    set_sandbox_setting(db, ensure_sandbox_registry(db), key, value)


def clear_active_cloud_session(db: Database) -> None:
    sandbox_id = ensure_sandbox_registry(db)
    for key in ("cloud_access_token", "cloud_refresh_token", "cloud_session_user"):
        set_sandbox_setting(db, sandbox_id, key, "")


def activate_sandbox(db: Database, sandbox_id: str) -> SandboxWorkspaceRecord:
    now = _now_iso()

    def _txn(conn: Any) -> None:
        exists = conn.execute(
            "SELECT id FROM sandboxes WHERE id = ? AND kind = 'organization' AND status = 'active'",
            (sandbox_id,),
        ).fetchone()
        if not exists:
            raise ValueError("工作空间不存在")
        conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (ACTIVE_SANDBOX_SETTING_KEY, sandbox_id),
        )
        conn.execute("UPDATE sandboxes SET last_active_at = ?, updated_at = ? WHERE id = ?", (now, now, sandbox_id))
        _copy_legacy_cloud_settings_if_needed(conn, sandbox_id)

    db.run_in_transaction(_txn)
    return get_active_sandbox(db)


def create_sandbox(db: Database, *, kind: str, name: str, cloud_api_url: str = "") -> SandboxWorkspaceRecord:
    now = _now_iso()
    if kind == "local":
        raise ValueError("本机草稿不是可创建或切换的工作空间")
    normalized_kind = "organization"
    normalized_name = name.strip() or "组织工作空间"
    sandbox_id = f"sbx_{normalized_kind}_{_safe_slug(normalized_name, 'workspace')}_{uuid4().hex[:8]}"

    def _txn(conn: Any) -> None:
        _insert_sandbox(
            conn,
            {
                "id": sandbox_id,
                "kind": normalized_kind,
                "name": normalized_name,
                "status": "active",
                "cloud_api_url": _normalize_cloud_api_url(cloud_api_url),
                "organization_id": None,
                "organization_name": None,
                "local_identity_id": None,
                "is_legacy_default": 0,
                "metadata_json": json.dumps({"createdBy": "stage2_workspace_manager"}, ensure_ascii=False),
                "created_at": now,
                "updated_at": now,
                "last_active_at": None,
            },
        )
        normalized_cloud_api_url = _normalize_cloud_api_url(cloud_api_url)
        if normalized_cloud_api_url:
            _write_sandbox_setting_to_conn(conn, sandbox_id, "cloud_api_url", normalized_cloud_api_url)

    db.run_in_transaction(_txn)
    row = db.fetchone("SELECT * FROM sandboxes WHERE id = ?", (sandbox_id,))
    if not row:
        raise RuntimeError("workspace creation failed")
    return _record_from_row(db, row)


def update_sandbox(db: Database, sandbox_id: str, *, name: str | None = None, cloud_api_url: str | None = None) -> SandboxWorkspaceRecord:
    now = _now_iso()

    def _txn(conn: Any) -> None:
        _ensure_visible_organization_sandbox(conn, sandbox_id)
        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                raise ValueError("工作空间名称不能为空")
            conn.execute("UPDATE sandboxes SET name = ?, updated_at = ? WHERE id = ?", (normalized_name, now, sandbox_id))
        if cloud_api_url is not None:
            _write_sandbox_setting_to_conn(conn, sandbox_id, "cloud_api_url", cloud_api_url)

    db.run_in_transaction(_txn)
    row = db.fetchone("SELECT * FROM sandboxes WHERE id = ?", (sandbox_id,))
    if not row:
        raise RuntimeError("workspace update failed")
    return _record_from_row(db, row)


def ensure_organization_sandbox_for_session(
    db: Database,
    *,
    organization_id: str,
    organization_name: str = "",
    cloud_api_url: str = "",
) -> SandboxWorkspaceRecord:
    normalized_org_id = organization_id.strip()
    if not normalized_org_id:
        raise ValueError("organization_id is required")
    safe_org = _safe_slug(normalized_org_id, "org")
    legacy_sandbox_id = f"sbx_org_{safe_org}"
    normalized_cloud_api_url = _normalize_cloud_api_url(cloud_api_url)
    now = _now_iso()
    display_name = organization_name.strip() or "组织工作空间"

    def _txn(conn: Any) -> None:
        sandbox_id = ""
        rows = conn.execute(
            """
            SELECT id, cloud_api_url FROM sandboxes
             WHERE kind = 'organization' AND organization_id = ?
             ORDER BY is_legacy_default DESC, created_at ASC
            """,
            (normalized_org_id,),
        ).fetchall()
        for candidate in rows:
            candidate_id = str(candidate["id"] if isinstance(candidate, Row) else candidate[0])
            candidate_cloud_row = conn.execute(
                "SELECT value FROM sandbox_settings WHERE sandbox_id = ? AND key = 'cloud_api_url'",
                (candidate_id,),
            ).fetchone()
            if candidate_cloud_row:
                candidate_cloud = str(
                    candidate_cloud_row["value"] if isinstance(candidate_cloud_row, Row) else candidate_cloud_row[0]
                )
            else:
                candidate_cloud = str(candidate["cloud_api_url"] if isinstance(candidate, Row) else candidate[1] or "")
            if _normalize_cloud_api_url(candidate_cloud) == normalized_cloud_api_url:
                sandbox_id = candidate_id
                break

        if not sandbox_id:
            legacy_row = conn.execute("SELECT id FROM sandboxes WHERE id = ?", (legacy_sandbox_id,)).fetchone()
            sandbox_id = (
                legacy_sandbox_id
                if not legacy_row
                else f"{legacy_sandbox_id}_{_cloud_id_suffix(normalized_cloud_api_url)}"
            )

        row = conn.execute("SELECT id FROM sandboxes WHERE id = ?", (sandbox_id,)).fetchone()
        values = {
            "id": sandbox_id,
            "kind": "organization",
            "name": display_name,
            "status": "active",
            "cloud_api_url": normalized_cloud_api_url,
            "organization_id": normalized_org_id,
            "organization_name": organization_name.strip() or None,
            "local_identity_id": None,
            "is_legacy_default": 0,
            "metadata_json": json.dumps({"createdBy": "stage2_cloud_login"}, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
            "last_active_at": now,
        }
        if not row:
            _insert_sandbox(conn, values)
        else:
            conn.execute(
                """
                UPDATE sandboxes
                   SET kind = 'organization',
                       name = ?,
                       organization_id = ?,
                       organization_name = ?,
                       cloud_api_url = ?,
                       updated_at = ?,
                       last_active_at = ?
                 WHERE id = ?
                """,
                (
                    display_name,
                    normalized_org_id,
                    organization_name.strip() or None,
                    normalized_cloud_api_url,
                    now,
                    now,
                    sandbox_id,
                ),
            )
        if normalized_cloud_api_url:
            _write_sandbox_setting_to_conn(conn, sandbox_id, "cloud_api_url", normalized_cloud_api_url)
        conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (ACTIVE_SANDBOX_SETTING_KEY, sandbox_id),
        )

    db.run_in_transaction(_txn)
    return get_active_sandbox(db)
