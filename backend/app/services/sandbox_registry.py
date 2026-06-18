from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from sqlite3 import Row
from typing import Any

from app.db import Database
from app.models import SandboxWorkspaceRecord, SandboxWorkspacesResponse


ACTIVE_SANDBOX_SETTING_KEY = "active_sandbox_id"
DEFAULT_LOCAL_SANDBOX_ID = "sbx_local_default"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _safe_slug(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return (normalized or fallback)[:80]


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
    cloud_api_url = db.get_setting("cloud_api_url", "").strip()
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
        "name": "本机工作空间",
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


def ensure_sandbox_registry(db: Database) -> str:
    """Ensure the stage-1 workspace shell exists without migrating business data."""

    now = _now_iso()
    default_values = _default_sandbox_values(db, now)

    def _txn(conn: Any) -> str:
        count_row = conn.execute("SELECT COUNT(1) FROM sandboxes").fetchone()
        sandbox_count = int(count_row[0] or 0) if count_row else 0
        if sandbox_count == 0:
            _insert_sandbox(conn, default_values)

        active_row = conn.execute("SELECT value FROM settings WHERE key = ?", (ACTIVE_SANDBOX_SETTING_KEY,)).fetchone()
        active_id = str(active_row["value"] if isinstance(active_row, Row) else active_row[0]).strip() if active_row else ""
        if active_id:
            exists = conn.execute("SELECT id FROM sandboxes WHERE id = ?", (active_id,)).fetchone()
            if exists:
                conn.execute("UPDATE sandboxes SET last_active_at = ?, updated_at = ? WHERE id = ?", (now, now, active_id))
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
        return fallback_id

    return str(db.run_in_transaction(_txn))


def _record_from_row(row: Row) -> SandboxWorkspaceRecord:
    return SandboxWorkspaceRecord(
        id=str(row["id"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        name=str(row["name"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        cloudApiUrl=str(row["cloud_api_url"] or ""),
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
        ORDER BY is_legacy_default DESC, COALESCE(last_active_at, created_at) DESC, created_at ASC
        """
    )
    return [_record_from_row(row) for row in rows]


def get_active_sandbox(db: Database) -> SandboxWorkspaceRecord:
    active_id = ensure_sandbox_registry(db)
    row = db.fetchone("SELECT * FROM sandboxes WHERE id = ?", (active_id,))
    if row:
        return _record_from_row(row)
    ensure_sandbox_registry(db)
    row = db.fetchone("SELECT * FROM sandboxes WHERE id = ?", (db.get_setting(ACTIVE_SANDBOX_SETTING_KEY, ""),))
    if not row:
        raise RuntimeError("active sandbox not found after registry repair")
    return _record_from_row(row)


def build_workspaces_response(db: Database) -> SandboxWorkspacesResponse:
    active_id = ensure_sandbox_registry(db)
    return SandboxWorkspacesResponse(activeSandboxId=active_id, workspaces=list_sandboxes(db))
