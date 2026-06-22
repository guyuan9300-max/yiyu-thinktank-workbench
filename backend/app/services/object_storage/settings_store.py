"""对象存储配置读写。

旧版只有全局 ``object_storage_settings`` 单行表。沙箱化后，运行时优先
使用 ``sandbox_settings`` 中的工作空间级缓存；旧表只作为升级/回滚兜底。
"""
from __future__ import annotations

import json
from typing import Any

from ...db import Database
from ...models import ObjectStorageSettingsPayload, ObjectStorageSettingsRecord

_SANDBOX_OBJECT_STORAGE_KEY = "settings.object_storage"


def _now_fallback() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_active_sandbox_id(db: Database) -> str:
    try:
        from app.services.sandbox_registry import get_active_sandbox_id

        return get_active_sandbox_id(db)
    except Exception:
        return ""


def _sandbox_settings_available(db: Database) -> bool:
    try:
        row = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='sandbox_settings'")
        return bool(row)
    except Exception:
        return False


def _load_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _record_from_payload(
    payload: dict[str, Any],
    *,
    redact_credentials: bool = False,
) -> ObjectStorageSettingsRecord:
    credentials_raw = payload.get("credentials")
    extra_raw = payload.get("extraConfig")
    credentials = {
        str(k): str(v)
        for k, v in (credentials_raw.items() if isinstance(credentials_raw, dict) else [])
        if str(v).strip()
    }
    extra = {
        str(k): str(v)
        for k, v in (extra_raw.items() if isinstance(extra_raw, dict) else [])
        if str(v).strip()
    }
    return ObjectStorageSettingsRecord(
        provider=str(payload.get("provider") or ""),
        credentials={} if redact_credentials else credentials,
        extraConfig=extra,
        enabled=bool(payload.get("enabled")),
        updatedAt=str(payload.get("updatedAt") or ""),
        hasCredentials=bool(credentials),
        managedByCloud=bool(payload.get("managedByCloud")),
        configuredBy=str(payload.get("configuredBy") or "") or None,
    )


def _row_to_record(
    row: Any,
    *,
    redact_credentials: bool = False,
    managed_by_cloud: bool = False,
    configured_by: str | None = None,
) -> ObjectStorageSettingsRecord:
    try:
        credentials = json.loads(row["credentials_json"] or "{}")
        if not isinstance(credentials, dict):
            credentials = {}
    except Exception:
        credentials = {}
    try:
        extra = json.loads(row["extra_config_json"] or "{}")
        if not isinstance(extra, dict):
            extra = {}
    except Exception:
        extra = {}
    return ObjectStorageSettingsRecord(
        provider=str(row["provider"] or ""),
        credentials={} if redact_credentials else {str(k): str(v) for k, v in credentials.items()},
        extraConfig={str(k): str(v) for k, v in extra.items()},
        enabled=bool(row["enabled"]),
        updatedAt=str(row["updated_at"] or ""),
        hasCredentials=bool(credentials),
        managedByCloud=managed_by_cloud,
        configuredBy=configured_by,
    )


def _get_sandbox_record(
    db: Database,
    sandbox_id: str,
    *,
    redact_credentials: bool = False,
) -> ObjectStorageSettingsRecord | None:
    if not sandbox_id or not _sandbox_settings_available(db):
        return None
    try:
        row = db.fetchone(
            "SELECT value FROM sandbox_settings WHERE sandbox_id = ? AND key = ?",
            (sandbox_id, _SANDBOX_OBJECT_STORAGE_KEY),
        )
    except Exception:
        return None
    if not row:
        return None
    payload = _load_json_object(str(row["value"] or ""))
    if not payload:
        return None
    return _record_from_payload(payload, redact_credentials=redact_credentials)


def get_object_storage_settings(
    db: Database,
    *,
    redact_credentials: bool = False,
    managed_by_cloud: bool = False,
    configured_by: str | None = None,
    sandbox_id: str | None = None,
) -> ObjectStorageSettingsRecord:
    resolved_sandbox_id = sandbox_id if sandbox_id is not None else _resolve_active_sandbox_id(db)
    sandbox_record = _get_sandbox_record(db, resolved_sandbox_id, redact_credentials=redact_credentials)
    if sandbox_record is not None:
        return sandbox_record

    row = db.fetchone("SELECT * FROM object_storage_settings WHERE id = 1")
    if not row:
        return ObjectStorageSettingsRecord()
    return _row_to_record(
        row,
        redact_credentials=redact_credentials,
        managed_by_cloud=managed_by_cloud,
        configured_by=configured_by,
    )


def save_object_storage_settings(
    db: Database,
    payload: ObjectStorageSettingsPayload,
    *,
    now_iso: str,
    sandbox_id: str | None = None,
    managed_by_cloud: bool = False,
    configured_by: str | None = None,
) -> ObjectStorageSettingsRecord:
    resolved_sandbox_id = sandbox_id if sandbox_id is not None else _resolve_active_sandbox_id(db)
    if resolved_sandbox_id and _sandbox_settings_available(db):
        record_payload = {
            "provider": payload.provider,
            "credentials": dict(payload.credentials or {}),
            "extraConfig": dict(payload.extraConfig or {}),
            "enabled": bool(payload.enabled),
            "updatedAt": now_iso or _now_fallback(),
            "managedByCloud": bool(managed_by_cloud),
            "configuredBy": configured_by or None,
        }
        db.execute(
            """
            INSERT INTO sandbox_settings(sandbox_id, key, value, updated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(sandbox_id, key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (
                resolved_sandbox_id,
                _SANDBOX_OBJECT_STORAGE_KEY,
                json.dumps(record_payload, ensure_ascii=False),
                now_iso or _now_fallback(),
            ),
        )
        return get_object_storage_settings(db, sandbox_id=resolved_sandbox_id)

    credentials_json = json.dumps(payload.credentials or {}, ensure_ascii=False)
    extra_json = json.dumps(payload.extraConfig or {}, ensure_ascii=False)
    db.execute(
        """
        UPDATE object_storage_settings
        SET provider = ?,
            credentials_json = ?,
            extra_config_json = ?,
            enabled = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (
            payload.provider,
            credentials_json,
            extra_json,
            1 if payload.enabled else 0,
            now_iso,
        ),
    )
    return get_object_storage_settings(db)
