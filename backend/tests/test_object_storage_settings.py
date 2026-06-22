from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import ObjectStorageSettingsPayload  # noqa: E402
from app.services.object_storage.settings_store import (  # noqa: E402
    get_object_storage_settings,
    save_object_storage_settings,
)


class _InMemoryDb:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS object_storage_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                provider TEXT NOT NULL DEFAULT '',
                credentials_json TEXT NOT NULL DEFAULT '{}',
                extra_config_json TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            INSERT OR IGNORE INTO object_storage_settings(id) VALUES (1);
            CREATE TABLE IF NOT EXISTS sandbox_settings (
                sandbox_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (sandbox_id, key)
            );
            """
        )
        self.settings: dict[str, str] = {}

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(query, params).fetchone()

    def execute(self, query: str, params: tuple = ()) -> None:
        self.conn.execute(query, params)
        self.conn.commit()


def test_object_storage_settings_roundtrip_and_redaction() -> None:
    db = _InMemoryDb()
    payload = ObjectStorageSettingsPayload(
        provider="volcano_tos",
        credentials={"access_key_id": "AK", "secret_access_key": "SK"},
        extraConfig={"endpoint": "tos-cn-beijing.volces.com", "region": "cn-beijing", "bucket": "yiyu-files"},
        enabled=True,
    )

    save_object_storage_settings(db, payload, now_iso="2026-05-21T10:00:00+08:00")  # type: ignore[arg-type]

    record = get_object_storage_settings(db)  # type: ignore[arg-type]
    assert record.provider == "volcano_tos"
    assert record.credentials["secret_access_key"] == "SK"
    assert record.extraConfig["bucket"] == "yiyu-files"
    assert record.enabled is True
    assert record.hasCredentials is True

    redacted = get_object_storage_settings(  # type: ignore[arg-type]
        db,
        redact_credentials=True,
        managed_by_cloud=True,
        configured_by="user_admin",
    )
    assert redacted.credentials == {}
    assert redacted.hasCredentials is True
    assert redacted.managedByCloud is True
    assert redacted.configuredBy == "user_admin"


def test_object_storage_settings_are_scoped_by_sandbox() -> None:
    db = _InMemoryDb()
    payload_a = ObjectStorageSettingsPayload(
        provider="volcano_tos",
        credentials={"access_key_id": "AK_A", "secret_access_key": "SK_A"},
        extraConfig={"bucket": "bucket-a"},
        enabled=True,
    )
    payload_b = ObjectStorageSettingsPayload(
        provider="volcano_tos",
        credentials={},
        extraConfig={"bucket": "bucket-b"},
        enabled=True,
    )

    save_object_storage_settings(  # type: ignore[arg-type]
        db,
        payload_a,
        now_iso="2026-06-22T10:00:00+08:00",
        sandbox_id="sbx_org_a",
        managed_by_cloud=True,
        configured_by="admin-a",
    )
    save_object_storage_settings(  # type: ignore[arg-type]
        db,
        payload_b,
        now_iso="2026-06-22T10:01:00+08:00",
        sandbox_id="sbx_org_b",
        managed_by_cloud=True,
        configured_by="admin-b",
    )

    record_a = get_object_storage_settings(db, sandbox_id="sbx_org_a")  # type: ignore[arg-type]
    record_b = get_object_storage_settings(db, sandbox_id="sbx_org_b")  # type: ignore[arg-type]
    local_record = get_object_storage_settings(db, sandbox_id="sbx_local_default")  # type: ignore[arg-type]

    assert record_a.extraConfig["bucket"] == "bucket-a"
    assert record_a.credentials["secret_access_key"] == "SK_A"
    assert record_a.managedByCloud is True
    assert record_a.configuredBy == "admin-a"
    assert record_b.extraConfig["bucket"] == "bucket-b"
    assert record_b.credentials == {}
    assert record_b.hasCredentials is False
    assert local_record.provider == ""
