from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class MemorySecretStore:
    api_key: str = ""

    def set_api_key(self, value: str) -> None:
        self.api_key = value.strip()

    def get_api_key(self) -> str:
        return self.api_key

    def delete_api_key(self) -> None:
        self.api_key = ""

    def get_api_key_fingerprint(self) -> str | None:
        if not self.api_key:
            return None
        return hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()[:12]

    def get_source_label(self) -> str:
        return "memory"

    def seed_from_env(self) -> bool:
        seed = (
            os.getenv("YIYU_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("REPORT_FORMATTER_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("MINIMAX_API_KEY_SEED", "").strip()
        )
        if not seed or self.api_key:
            return False
        self.api_key = seed
        return True


class MacOSKeychainSecretStore:
    def __init__(self, service_name: str = "com.yiyu.self-workbench.ai", account_name: str = "default"):
        self.service_name = service_name
        self.account_name = account_name

    def _ensure_supported(self) -> None:
        if sys.platform != "darwin":
            raise RuntimeError("当前仅支持在 macOS 上使用系统钥匙串保存密钥。")

    def set_api_key(self, value: str) -> None:
        self._ensure_supported()
        api_key = value.strip()
        if not api_key:
            raise RuntimeError("API 密钥不能为空。")
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-a",
                self.account_name,
                "-s",
                self.service_name,
                "-w",
                api_key,
                "-U",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def get_api_key(self) -> str:
        self._ensure_supported()
        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-a",
                    self.account_name,
                    "-s",
                    self.service_name,
                    "-w",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or "").lower()
            if "could not be found" in stderr or "item could not be found" in stderr:
                return ""
            raise RuntimeError("读取 macOS 钥匙串失败。") from error

    def delete_api_key(self) -> None:
        self._ensure_supported()
        result = subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a",
                self.account_name,
                "-s",
                self.service_name,
            ],
            capture_output=True,
            text=True,
        )
        stderr = (result.stderr or "").lower()
        if result.returncode == 0 or "could not be found" in stderr or "item could not be found" in stderr:
            return
        raise RuntimeError("清除 macOS 钥匙串中的 API 密钥失败。")

    def get_api_key_fingerprint(self) -> str | None:
        api_key = self.get_api_key()
        if not api_key:
            return None
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]

    def get_source_label(self) -> str:
        return "keychain"

    def seed_from_env(self) -> bool:
        seed = (
            os.getenv("YIYU_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("REPORT_FORMATTER_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("MINIMAX_API_KEY_SEED", "").strip()
        )
        if not seed:
            return False
        if self.get_api_key():
            return False
        self.set_api_key(seed)
        return True
