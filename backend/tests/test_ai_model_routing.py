from __future__ import annotations

from pathlib import Path

from app.db import Database
from app.services.ai import AiService
from app.services.sandbox_registry import get_active_sandbox_id, get_sandbox_setting


class FakeSecretStore:
    def __init__(self) -> None:
        self.value = ""

    def get_api_key(self) -> str:
        return self.value

    def set_api_key(self, value: str) -> None:
        self.value = value

    def delete_api_key(self) -> None:
        self.value = ""

    def get_source_label(self) -> str:
        return "test"

    def get_api_key_fingerprint(self) -> str | None:
        if not self.value:
            return None
        return "test-fingerprint"


def make_ai_service(tmp_path: Path) -> tuple[AiService, Database, dict[str, FakeSecretStore]]:
    db = Database(tmp_path / "app.db")
    stores = {
        "openai_compatible": FakeSecretStore(),
        "qwen": FakeSecretStore(),
        "doubao": FakeSecretStore(),
        "ai_profile:online_primary": FakeSecretStore(),
        "ai_profile:local_text_deep": FakeSecretStore(),
        "ai_profile:local_vision_ocr": FakeSecretStore(),
        "ai_profile:local_fast": FakeSecretStore(),
    }
    return AiService(db, stores), db, stores


def test_unified_model_is_preserved_when_advanced_routing_is_disabled(tmp_path: Path) -> None:
    service, _db, stores = make_ai_service(tmp_path)
    stores["openai_compatible"].set_api_key("remote-key")
    service.configure(
        "openai_compatible",
        "doubao-seed-2-0-pro-260215",
        None,
        False,
        provider_label="统一大模型",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )

    health = service.get_health(task_kind="deep_analysis")

    assert health.ready is True
    assert health.profile_key == "unified"
    assert health.model == "doubao-seed-2-0-pro-260215"


def test_local_only_does_not_fall_back_to_remote_unified_model(tmp_path: Path) -> None:
    service, _db, stores = make_ai_service(tmp_path)
    stores["openai_compatible"].set_api_key("remote-key")
    service.configure(
        "openai_compatible",
        "remote-model",
        None,
        False,
        provider_label="远程统一模型",
        base_url="https://example.com/v1",
    )
    service.configure_advanced_ai(
        advanced_enabled=True,
        model_mode="local_only",
        profiles={
            "online_primary": {
                "enabled": True,
                "provider": "openai_compatible",
                "providerLabel": "线上主模型",
                "baseUrl": "https://example.com/v1",
                "model": "remote-model",
                "capability": "online_primary",
            }
        },
        profile_api_keys={"online_primary": "remote-profile-key"},
    )

    health = service.get_health(task_kind="deep_analysis")

    assert health.ready is False
    assert health.profile_key == "unavailable"
    assert service._resolve_llm_candidates(task_kind="deep_analysis") == []


def test_vision_and_fast_tasks_prefer_matching_local_profiles(tmp_path: Path) -> None:
    service, _db, _stores = make_ai_service(tmp_path)
    service.configure_advanced_ai(
        advanced_enabled=True,
        model_mode="auto",
        profiles={
            "online_primary": {
                "enabled": True,
                "provider": "openai_compatible",
                "providerLabel": "线上主模型",
                "baseUrl": "https://example.com/v1",
                "model": "remote-model",
                "capability": "online_primary",
            },
            "local_vision_ocr": {
                "enabled": True,
                "provider": "openai_compatible",
                "providerLabel": "本地视觉",
                "baseUrl": "http://127.0.0.1:11434/v1",
                "model": "qwen3-vl:30b",
                "capability": "vision_ocr",
            },
            "local_fast": {
                "enabled": True,
                "provider": "openai_compatible",
                "providerLabel": "本地快速",
                "baseUrl": "http://127.0.0.1:11434/v1",
                "model": "qwen3:8b",
                "capability": "fast_structured",
            },
        },
    )

    assert service.get_health(task_kind="vision_ocr").profile_key == "local_vision_ocr"
    assert service.get_health(task_kind="fast_structured").profile_key == "local_fast"


def test_profile_api_keys_are_kept_out_of_settings(tmp_path: Path) -> None:
    service, db, stores = make_ai_service(tmp_path)

    service.configure_advanced_ai(
        advanced_enabled=True,
        profiles={
            "local_text_deep": {
                "enabled": True,
                "provider": "openai_compatible",
                "providerLabel": "本地深度",
                "baseUrl": "http://127.0.0.1:11434/v1",
                "model": "qwen2.5:72b",
                "capability": "deep_analysis",
            }
        },
        profile_api_keys={"local_text_deep": "local-secret"},
    )

    active_sandbox_id = get_active_sandbox_id(db)
    assert "local-secret" not in get_sandbox_setting(db, active_sandbox_id, "settings.ai_model_profiles", "")
    scoped_store = service._store_for("ai_profile:local_text_deep", base_url="http://127.0.0.1:11434/v1")  # noqa: SLF001
    assert scoped_store is not None
    assert scoped_store.get_api_key() == "local-secret"
