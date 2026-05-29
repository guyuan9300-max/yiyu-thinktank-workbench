"""I1a · 语音识别模型配置 pytest

覆盖：
- 默认值（首次启动表里 INSERT OR IGNORE 应该有空配置）
- 保存 + 重新加载（确保 credentials/extra dict 往返 JSON 不丢字段）
- 切换 provider 不污染老 credentials（前端逻辑，但后端必须能存）
- 测试连接 - 未知 provider 返回 success=False 但不抛异常
- 测试连接 - 空 provider 返回友好错误
"""
from __future__ import annotations

import json
import sys
import sqlite3
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import SpeechModelSettingsPayload  # noqa: E402
from app.services.speech_recognition import (  # noqa: E402
    TestConnectionResult,
    TranscriptionProvider,
)
from app.services.speech_recognition.registry import (  # noqa: E402
    get_provider,
    registered_provider_names,
)
from app.services.speech_recognition.settings_store import (  # noqa: E402
    get_speech_model_settings,
    save_speech_model_settings,
)


class _InMemoryDb:
    """最小化 DB stub，足够给 settings_store 用（fetchone + execute）。"""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS speech_model_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                provider TEXT NOT NULL DEFAULT '',
                credentials_json TEXT NOT NULL DEFAULT '{}',
                model_id TEXT NOT NULL DEFAULT '',
                extra_config_json TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            INSERT OR IGNORE INTO speech_model_settings(id) VALUES (1);
            """
        )

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(query, params).fetchone()

    def execute(self, query: str, params: tuple = ()) -> None:
        self.conn.execute(query, params)
        self.conn.commit()


@pytest.fixture
def db() -> _InMemoryDb:
    return _InMemoryDb()


class TestSettingsStoreRoundtrip:
    def test_default_is_empty(self, db: _InMemoryDb) -> None:
        record = get_speech_model_settings(db)  # type: ignore[arg-type]
        assert record.provider == ""
        assert record.credentials == {}
        assert record.modelId == ""
        assert record.extraConfig == {}
        assert record.enabled is False

    def test_save_and_reload_preserves_all_fields(self, db: _InMemoryDb) -> None:
        payload = SpeechModelSettingsPayload(
            provider="volcano",
            credentials={"app_id": "X1", "access_key": "AK", "access_token": "AT"},
            modelId="bigmodel",
            extraConfig={"language": "zh-CN"},
            enabled=True,
        )
        save_speech_model_settings(db, payload, now_iso="2026-05-12T10:00:00Z")  # type: ignore[arg-type]
        record = get_speech_model_settings(db)  # type: ignore[arg-type]
        assert record.provider == "volcano"
        assert record.credentials == {"app_id": "X1", "access_key": "AK", "access_token": "AT"}
        assert record.modelId == "bigmodel"
        assert record.extraConfig == {"language": "zh-CN"}
        assert record.enabled is True
        assert record.updatedAt == "2026-05-12T10:00:00Z"

    def test_overwrite_credentials_when_switching_provider(self, db: _InMemoryDb) -> None:
        """切 provider 时前端会清空老 credentials；后端必须能干净覆盖。"""
        first = SpeechModelSettingsPayload(
            provider="volcano",
            credentials={"app_id": "X1"},
            modelId="bigmodel",
            extraConfig={},
            enabled=False,
        )
        save_speech_model_settings(db, first, now_iso="t1")  # type: ignore[arg-type]
        second = SpeechModelSettingsPayload(
            provider="openai_whisper",
            credentials={"api_key": "sk-..."},
            modelId="whisper-1",
            extraConfig={},
            enabled=False,
        )
        save_speech_model_settings(db, second, now_iso="t2")  # type: ignore[arg-type]
        record = get_speech_model_settings(db)  # type: ignore[arg-type]
        assert record.provider == "openai_whisper"
        assert record.credentials == {"api_key": "sk-..."}
        assert "app_id" not in record.credentials, "切 provider 后旧字段必须被覆盖"

    def test_corrupt_json_falls_back_to_empty_dict(self, db: _InMemoryDb) -> None:
        """如果手动改了 DB 让 JSON 损坏，settings_store 应当返回空 dict 而不是崩。"""
        db.execute(
            "UPDATE speech_model_settings SET credentials_json = ?, extra_config_json = ? WHERE id = 1",
            ("not-valid-json", "{also bad}"),
        )
        record = get_speech_model_settings(db)  # type: ignore[arg-type]
        assert record.credentials == {}
        assert record.extraConfig == {}


class TestProviderRegistry:
    def test_volcano_is_registered(self) -> None:
        provider = get_provider("volcano")
        assert provider is not None
        assert provider.name == "volcano"

    def test_unknown_returns_none(self) -> None:
        assert get_provider("nonexistent_provider") is None
        assert get_provider("") is None

    def test_registered_names_include_volcano(self) -> None:
        assert "volcano" in tuple(registered_provider_names())


class TestVolcanoProviderTestConnection:
    """火山 provider.test_connection 不能抛异常，必须返回 TestConnectionResult。"""

    def test_missing_credentials_returns_user_friendly_message(self) -> None:
        provider = get_provider("volcano")
        assert provider is not None
        result = provider.test_connection(
            credentials={},  # 空凭证
            model_id="bigmodel",
            extra_config={},
        )
        assert isinstance(result, TestConnectionResult)
        assert result.success is False
        assert "App ID" in result.message or "Access Token" in result.message
        # 不能把技术细节直接抛出
        assert "Traceback" not in result.message
