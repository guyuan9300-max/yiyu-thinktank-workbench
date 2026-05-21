"""object_storage_settings 表的读写。"""
from __future__ import annotations

import json
from typing import Any

from ...db import Database
from ...models import ObjectStorageSettingsPayload, ObjectStorageSettingsRecord


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


def get_object_storage_settings(
    db: Database,
    *,
    redact_credentials: bool = False,
    managed_by_cloud: bool = False,
    configured_by: str | None = None,
) -> ObjectStorageSettingsRecord:
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
) -> ObjectStorageSettingsRecord:
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
