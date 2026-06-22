from __future__ import annotations

from pathlib import Path

from app.db import Database
from app.services.ai import AiService
from app.services.sandbox_registry import (
    DEFAULT_LOCAL_SANDBOX_ID,
    activate_sandbox,
    create_sandbox,
    ensure_sandbox_registry,
    get_active_sandbox_id,
    get_sandbox_setting,
)


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
        return "test-fingerprint" if self.value else None


def make_ai_service(tmp_path: Path) -> tuple[AiService, Database]:
    db = Database(tmp_path / "app.db")
    ensure_sandbox_registry(db)
    stores = {
        "openai_compatible": FakeSecretStore(),
        "qwen": FakeSecretStore(),
        "doubao": FakeSecretStore(),
        "ai_profile:online_primary": FakeSecretStore(),
        "ai_profile:local_text_deep": FakeSecretStore(),
        "ai_profile:local_vision_ocr": FakeSecretStore(),
        "ai_profile:local_fast": FakeSecretStore(),
    }
    return AiService(db, stores), db


def test_remote_ai_config_and_key_are_scoped_by_workspace(tmp_path: Path) -> None:
    service, db = make_ai_service(tmp_path)

    service.configure(
        "openai_compatible",
        "model-a",
        "key-a",
        False,
        provider_label="组织 A 模型",
        base_url="https://a.example.test/v1",
    )
    assert service.current_model() == "model-a"
    assert service.export_current_api_key() == "key-a"

    org = create_sandbox(db, kind="organization", name="组织 B", cloud_api_url="https://cloud-b.example.test")
    activate_sandbox(db, org.id)
    assert service.export_current_api_key() == ""

    service.configure(
        "openai_compatible",
        "model-b",
        "key-b",
        False,
        provider_label="组织 B 模型",
        base_url="https://b.example.test/v1",
    )
    assert service.current_model() == "model-b"
    assert service.export_current_api_key() == "key-b"

    activate_sandbox(db, DEFAULT_LOCAL_SANDBOX_ID)
    assert service.current_model() == "model-a"
    assert service.current_base_url() == "https://a.example.test/v1"
    assert service.export_current_api_key() == "key-a"


def test_local_model_is_shared_device_resource_but_remote_is_not(tmp_path: Path) -> None:
    service, db = make_ai_service(tmp_path)

    service.configure(
        "openai_compatible",
        "qwen-local:8b",
        "local-token",
        False,
        provider_label="本地 Ollama",
        base_url="http://127.0.0.1:11434/v1",
    )
    assert service.current_base_url() == "http://127.0.0.1:11434/v1"
    assert service.export_current_api_key() == "local-token"
    active_id = get_active_sandbox_id(db)
    assert "127.0.0.1" not in get_sandbox_setting(db, active_id, "ai_base_url", "")
    assert "qwen-local:8b" not in get_sandbox_setting(db, active_id, "ai_model", "")

    org = create_sandbox(db, kind="organization", name="组织 C", cloud_api_url="https://cloud-c.example.test")
    activate_sandbox(db, org.id)

    assert service.current_base_url() == "http://127.0.0.1:11434/v1"
    assert service.current_model() == "qwen-local:8b"
    assert service.export_current_api_key() == "local-token"

    service.configure(
        "openai_compatible",
        "remote-c",
        "key-c",
        False,
        provider_label="组织 C 远程模型",
        base_url="https://c.example.test/v1",
    )
    assert service.export_current_api_key() == "key-c"

    activate_sandbox(db, DEFAULT_LOCAL_SANDBOX_ID)
    assert service.current_base_url() == "http://127.0.0.1:11434/v1"
    assert service.export_current_api_key() == "local-token"


def test_local_profile_resource_is_shared_without_auto_enabling_other_workspaces(tmp_path: Path) -> None:
    service, db = make_ai_service(tmp_path)
    service.configure_advanced_ai(
        advanced_enabled=True,
        model_mode="local_first",
        profiles={
            "local_text_deep": {
                "enabled": True,
                "provider": "openai_compatible",
                "providerLabel": "本地深度",
                "baseUrl": "http://127.0.0.1:11434/v1",
                "model": "qwen-local:72b",
                "capability": "deep_analysis",
            }
        },
        profile_api_keys={"local_text_deep": "local-profile-token"},
    )
    assert service.current_ai_model_profiles()["local_text_deep"]["enabled"] is True

    org = create_sandbox(db, kind="organization", name="组织 D", cloud_api_url="https://cloud-d.example.test")
    activate_sandbox(db, org.id)
    profile = service.current_ai_model_profiles()["local_text_deep"]

    assert profile["baseUrl"] == "http://127.0.0.1:11434/v1"
    assert profile["model"] == "qwen-local:72b"
    assert profile["enabled"] is False
    raw_workspace_profiles = get_sandbox_setting(db, org.id, "settings.ai_model_profiles", "")
    assert "127.0.0.1" not in raw_workspace_profiles
    assert "qwen-local:72b" not in raw_workspace_profiles
