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


@dataclass
class UnavailableSecretStore:
    reason: str

    def set_api_key(self, value: str) -> None:
        del value
        raise RuntimeError(self.reason)

    def get_api_key(self) -> str:
        return ""

    def delete_api_key(self) -> None:
        return None

    def get_api_key_fingerprint(self) -> str | None:
        return None

    def get_source_label(self) -> str:
        return "unavailable"

    def seed_from_env(self) -> bool:
        return False


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


class WindowsCredentialManagerSecretStore:
    """Persist a small secret in the current Windows user's Credential Manager."""

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    def __init__(self, service_name: str, account_name: str = "default"):
        self.service_name = service_name
        self.account_name = account_name
        self.target_name = f"{service_name}/{account_name}"

    def _ensure_supported(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("当前仅支持在 Windows 上使用凭据管理器保存密钥。")

    @staticmethod
    def _bindings():
        import ctypes
        from ctypes import wintypes

        class Credential(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", wintypes.LPVOID),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        advapi32.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        advapi32.CredWriteW.restype = wintypes.BOOL
        advapi32.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(Credential)),
        ]
        advapi32.CredReadW.restype = wintypes.BOOL
        advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        advapi32.CredDeleteW.restype = wintypes.BOOL
        advapi32.CredFree.argtypes = [wintypes.LPVOID]
        advapi32.CredFree.restype = None
        return ctypes, Credential, advapi32

    def set_api_key(self, value: str) -> None:
        self._ensure_supported()
        api_key = value.strip()
        if not api_key:
            raise RuntimeError("API 密钥不能为空。")
        ctypes, Credential, advapi32 = self._bindings()
        raw = api_key.encode("utf-8")
        blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        credential = Credential()
        credential.Flags = 0
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = self.target_name
        credential.Comment = "益语智库组织 AI 运行凭据"
        credential.CredentialBlobSize = len(raw)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.AttributeCount = 0
        credential.Attributes = None
        credential.TargetAlias = None
        credential.UserName = self.account_name
        if not advapi32.CredWriteW(ctypes.byref(credential), 0):
            raise RuntimeError(f"写入 Windows 凭据管理器失败（错误码 {ctypes.get_last_error()}）。")

    def get_api_key(self) -> str:
        self._ensure_supported()
        ctypes, Credential, advapi32 = self._bindings()
        pointer = ctypes.POINTER(Credential)()
        if not advapi32.CredReadW(
            self.target_name,
            self.CRED_TYPE_GENERIC,
            0,
            ctypes.byref(pointer),
        ):
            error_code = ctypes.get_last_error()
            if error_code == self.ERROR_NOT_FOUND:
                return ""
            raise RuntimeError(f"读取 Windows 凭据管理器失败（错误码 {error_code}）。")
        try:
            credential = pointer.contents
            if not credential.CredentialBlob or credential.CredentialBlobSize <= 0:
                return ""
            raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return raw.decode("utf-8")
        finally:
            advapi32.CredFree(pointer)

    def delete_api_key(self) -> None:
        self._ensure_supported()
        ctypes, _credential, advapi32 = self._bindings()
        if advapi32.CredDeleteW(self.target_name, self.CRED_TYPE_GENERIC, 0):
            return
        error_code = ctypes.get_last_error()
        if error_code != self.ERROR_NOT_FOUND:
            raise RuntimeError(f"删除 Windows 凭据失败（错误码 {error_code}）。")

    def get_api_key_fingerprint(self) -> str | None:
        api_key = self.get_api_key()
        if not api_key:
            return None
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]

    def get_source_label(self) -> str:
        return "windows_credential_manager"

    def seed_from_env(self) -> bool:
        seed = (
            os.getenv("YIYU_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("REPORT_FORMATTER_MODEL_API_KEY_SEED", "").strip()
            or os.getenv("MINIMAX_API_KEY_SEED", "").strip()
        )
        if not seed or self.get_api_key():
            return False
        self.set_api_key(seed)
        return True
