from __future__ import annotations

import sys
from uuid import uuid4

import pytest

import app.main as app_main
from app.services.secrets import UnavailableSecretStore, WindowsCredentialManagerSecretStore


def test_unavailable_secret_store_never_accepts_secret() -> None:
    store = UnavailableSecretStore("系统凭据存储不可用")

    assert store.get_api_key() == ""
    assert store.get_api_key_fingerprint() is None
    assert store.get_source_label() == "unavailable"
    with pytest.raises(RuntimeError, match="系统凭据存储不可用"):
        store.set_api_key("must-not-be-kept-in-memory")


def test_packaged_runtime_never_falls_back_to_memory_secret_store(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("YIYU_USE_SYSTEM_SECRET_STORE_IN_TESTS", "1")
    monkeypatch.setattr(app_main, "BACKEND_RUNTIME_MODE", "packaged")
    monkeypatch.setattr(app_main.sys, "platform", "linux")
    app = app_main.create_app(tmp_path / "data")

    with pytest.raises(RuntimeError, match="安全凭据存储"):
        app.state.app_state.ai.configure(
            "openai_compatible",
            "model",
            "must-not-be-kept-in-memory",
            False,
            provider_label="test",
            base_url="https://models.example.test/v1",
        )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Credential Manager integration test")
def test_windows_credential_manager_persists_across_store_instances() -> None:
    service = f"com.yiyu.self-workbench.test.{uuid4().hex}"
    account = f"sandbox:{uuid4().hex}"
    first = WindowsCredentialManagerSecretStore(service, account)
    second = WindowsCredentialManagerSecretStore(service, account)
    try:
        first.set_api_key("windows-persistent-secret")
        assert second.get_api_key() == "windows-persistent-secret"
        assert second.get_api_key_fingerprint()
    finally:
        first.delete_api_key()
    assert second.get_api_key() == ""
