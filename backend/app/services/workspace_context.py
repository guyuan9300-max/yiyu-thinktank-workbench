from __future__ import annotations

import json
from dataclasses import dataclass
from sqlite3 import Row
from typing import Any

from app.db import Database
from app.services.sandbox_registry import (
    DEFAULT_LOCAL_SANDBOX_ID,
    get_active_sandbox_id,
    get_sandbox_setting,
)


def _load_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class WorkspaceContext:
    sandbox_id: str
    kind: str
    name: str = ""
    cloud_instance_id: str = ""
    organization_id: str = ""
    organization_name: str = ""
    cloud_api_url: str = ""
    user_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    session_user: dict[str, Any] | None = None
    session_snapshot: dict[str, Any] | None = None
    identity_state: str = "unverified"
    identity_verified_at: str | None = None
    identity_error: str = ""
    last_active_at: str | None = None

    @property
    def is_local_draft(self) -> bool:
        return self.kind == "local"

    @property
    def has_cloud_session(self) -> bool:
        return bool(self.cloud_api_url and (self.access_token or self.refresh_token))

    @property
    def session_organization_id(self) -> str:
        return str((self.session_user or {}).get("organizationId") or "").strip()

    @property
    def session_matches_workspace(self) -> bool:
        if self.kind != "organization":
            return True
        has_session_material = bool(
            self.access_token
            or self.refresh_token
            or self.session_user
        )
        if not has_session_material:
            return True
        return bool(self.organization_id) and bool(self.session_organization_id) and (
            self.organization_id == self.session_organization_id
        )

    def immutable_cloud_tuple(self) -> tuple[str, str, str, str, str]:
        return (
            self.sandbox_id,
            self.cloud_instance_id,
            self.organization_id,
            self.cloud_api_url,
            self.access_token,
        )


def _row_value(row: Row, key: str, default: str = "") -> str:
    try:
        value = row[key]
    except Exception:
        value = default
    return str(value or "")


def load_workspace_context(db: Database, sandbox_id: str | None = None) -> WorkspaceContext:
    explicit_sandbox_id = str(sandbox_id or "").strip()
    target_sandbox_id = (explicit_sandbox_id or get_active_sandbox_id(db) or DEFAULT_LOCAL_SANDBOX_ID).strip()
    row = db.fetchone("SELECT * FROM sandboxes WHERE id = ?", (target_sandbox_id,))
    if not row and explicit_sandbox_id:
        return WorkspaceContext(
            sandbox_id=target_sandbox_id,
            kind="missing",
            identity_state="error",
            identity_error="工作空间记录不存在，已停止当前空间的同步和写入。",
        )
    if not row:
        target_sandbox_id = DEFAULT_LOCAL_SANDBOX_ID
        row = db.fetchone("SELECT * FROM sandboxes WHERE id = ?", (target_sandbox_id,))
    if not row:
        return WorkspaceContext(sandbox_id=DEFAULT_LOCAL_SANDBOX_ID, kind="local")
    raw_session_user = get_sandbox_setting(db, target_sandbox_id, "cloud_session_user", "")
    session_user = _load_json_object(raw_session_user)
    session_snapshot = (
        _load_json_object(get_sandbox_setting(db, target_sandbox_id, "cloud_session_user_snapshot", ""))
        or session_user
    )
    return WorkspaceContext(
        sandbox_id=target_sandbox_id,
        kind=_row_value(row, "kind", "local"),
        name=_row_value(row, "name"),
        cloud_instance_id=_row_value(row, "cloud_instance_id"),
        organization_id=_row_value(row, "organization_id"),
        organization_name=_row_value(row, "organization_name"),
        cloud_api_url=get_sandbox_setting(db, target_sandbox_id, "cloud_api_url", _row_value(row, "cloud_api_url")),
        user_id=str(session_user.get("id") or ""),
        access_token=get_sandbox_setting(db, target_sandbox_id, "cloud_access_token", ""),
        refresh_token=get_sandbox_setting(db, target_sandbox_id, "cloud_refresh_token", ""),
        session_user=session_user,
        session_snapshot=session_snapshot,
        identity_state=_row_value(row, "identity_state", "unverified") or "unverified",
        identity_verified_at=_row_value(row, "identity_verified_at") or None,
        identity_error=_row_value(row, "identity_error"),
        last_active_at=_row_value(row, "last_active_at") or None,
    )


def load_active_workspace_context(db: Database) -> WorkspaceContext:
    return load_workspace_context(db, None)


def list_workspace_contexts(db: Database) -> list[WorkspaceContext]:
    rows = db.fetchall(
        """
        SELECT id
          FROM sandboxes
         WHERE (kind = 'organization' AND status = 'active')
            OR id = ?
         ORDER BY kind DESC, COALESCE(last_active_at, created_at) DESC, created_at ASC
        """,
        (DEFAULT_LOCAL_SANDBOX_ID,),
    )
    return [load_workspace_context(db, str(row["id"])) for row in rows]
