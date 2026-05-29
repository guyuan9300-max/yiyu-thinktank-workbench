"""speech_model_settings 表的读写。

DB schema 见 db.py 末尾 `speech_model_settings` 表（id PRIMARY KEY 永远 = 1，单 org 单行）。
"""
from __future__ import annotations

import json
from typing import Any

from ...db import Database
from ...models import SpeechModelSettingsPayload, SpeechModelSettingsRecord


def _row_to_record(row: Any) -> SpeechModelSettingsRecord:
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
    return SpeechModelSettingsRecord(
        provider=str(row["provider"] or ""),
        credentials={str(k): str(v) for k, v in credentials.items()},
        modelId=str(row["model_id"] or ""),
        extraConfig={str(k): str(v) for k, v in extra.items()},
        enabled=bool(row["enabled"]),
        updatedAt=str(row["updated_at"] or ""),
    )


def get_speech_model_settings(db: Database) -> SpeechModelSettingsRecord:
    """读取 org 级语音模型配置；表保证 id=1 那行存在（db.py 初始化时 INSERT OR IGNORE）。"""
    row = db.fetchone("SELECT * FROM speech_model_settings WHERE id = 1")
    if not row:
        return SpeechModelSettingsRecord()
    return _row_to_record(row)


def save_speech_model_settings(
    db: Database,
    payload: SpeechModelSettingsPayload,
    *,
    now_iso: str,
) -> SpeechModelSettingsRecord:
    credentials_json = json.dumps(payload.credentials or {}, ensure_ascii=False)
    extra_json = json.dumps(payload.extraConfig or {}, ensure_ascii=False)
    db.execute(
        """
        UPDATE speech_model_settings
        SET provider = ?,
            credentials_json = ?,
            model_id = ?,
            extra_config_json = ?,
            enabled = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (
            payload.provider,
            credentials_json,
            payload.modelId,
            extra_json,
            1 if payload.enabled else 0,
            now_iso,
        ),
    )
    return get_speech_model_settings(db)
