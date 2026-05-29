"""对象存储 provider 抽象层。

目标：把录音、附件或其他后台处理文件中转到一个公网可访问的 URL，
供火山 ASR（或其他 ASR provider）和后续文件处理流程拉取。

Provider 协议：
- ``test_connection``：用一个小探针对象验证桶可读可写
- ``upload_file``：把本地文件上传到桶，返回公网可访问的 URL（预签名或公开桶 URL）

具体实现见 volcano_tos_provider.py 等。注册中心见 registry.py。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class StorageTestResult:
    success: bool
    message: str = ""
    detail: str | None = None
    latency_ms: float | None = None


@dataclass
class StorageUploadResult:
    object_key: str
    url: str  # 完整的公网可访问 URL（可能是预签名 URL，有过期时间）
    expires_at: str | None = None  # ISO 时间，预签名 URL 失效时间；公开桶 URL 留空
    size_bytes: int = 0


class ObjectStorageProvider(Protocol):
    """所有对象存储 provider 必须实现的协议。"""
    name: str

    def test_connection(
        self,
        *,
        credentials: dict[str, str],
        extra_config: dict[str, str],
        timeout_seconds: float = 30.0,
    ) -> StorageTestResult:
        """用一个小探针对象（如 /yiyu-probe.txt）验证桶可读可写。

        返回 ``StorageTestResult``；不抛异常 —— 失败也要返回 success=False。
        """
        ...

    def upload_file(
        self,
        *,
        local_path: str,
        object_key: str,
        credentials: dict[str, str],
        extra_config: dict[str, str],
        expires_seconds: int = 3600,
    ) -> StorageUploadResult:
        """把本地文件上传到桶，返回公网可访问 URL（默认预签名 1 小时）。

        I1b-1 不调用此接口；I1b-2 上传录音时才会用。
        """
        ...
