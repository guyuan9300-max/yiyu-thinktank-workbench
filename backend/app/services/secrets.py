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
        # 注意: CalledProcessError.cmd 会包含完整 argv (含 api_key 明文).
        # 直接让异常往上抛, 上层 except Exception 把 exc 拼进 HTTP 响应体就会泄漏 secret.
        # 这里 catch + 重抛 sanitized RuntimeError, 异常 message 里不能引用原 exc 或 exc.cmd.
        try:
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
        except subprocess.CalledProcessError as exc:
            # 只保留 returncode + stderr (后者通常不含 -w 后的 api_key),
            # 完全不引用 exc.cmd / exc.args
            stderr_safe = ""
            if exc.stderr:
                stderr_text = exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", errors="replace")
                # 二次防御: 显式过滤包含 api_key 的行 (虽然 stderr 通常不含)
                stderr_safe = "\n".join(line for line in stderr_text.splitlines() if api_key not in line)
            raise RuntimeError(
                f"keychain set_api_key 失败 (returncode={exc.returncode}): {stderr_safe or '无错误输出'}"
            ) from None  # from None 切断 __cause__,防止 traceback 链路里仍能看到原 exc.cmd

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
