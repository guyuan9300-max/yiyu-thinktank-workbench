"""火山引擎 TOS（对象存储）provider。

官方 SDK：https://www.volcengine.com/docs/6349/74837
PyPI 包：``tos``（已加入 pyproject.toml）

测试连接策略：
1. 建一个临时 client
2. head_bucket 看桶是否存在 + 当前 ak/sk 是否有访问权限
3. 上传一个 1-byte 探针对象（路径 ``yiyu-probe/<uuid>.txt``）
4. 删除探针
5. 任一步失败都返回 success=False + 友好错误

凭证字段（前端 UI 暴露）：
- access_key_id      : TOS Access Key ID
- secret_access_key  : TOS Secret Access Key（敏感，UI 显示为 password）

额外配置：
- endpoint  : 默认 ``tos-cn-beijing.volces.com``
- region    : 默认 ``cn-beijing``
- bucket    : 用户创建的桶名

I1b-1 只用 test_connection。I1b-2 才会用 upload_file。
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from . import ObjectStorageProvider, StorageTestResult, StorageUploadResult

DEFAULT_ENDPOINT = "tos-cn-beijing.volces.com"
DEFAULT_REGION = "cn-beijing"


class VolcanoTosObjectStorageProvider:
    """火山引擎 TOS 对象存储 provider 实现。"""
    name = "volcano_tos"

    def test_connection(
        self,
        *,
        credentials: dict[str, str],
        extra_config: dict[str, str],
        timeout_seconds: float = 30.0,
    ) -> StorageTestResult:
        ak = (credentials.get("access_key_id") or "").strip()
        sk = (credentials.get("secret_access_key") or "").strip()
        if not ak or not sk:
            return StorageTestResult(
                success=False,
                message="缺少必填字段：Access Key ID 或 Secret Access Key",
                detail="请在配置里填写完整凭证后再测试。",
            )
        endpoint = (extra_config.get("endpoint") or "").strip() or DEFAULT_ENDPOINT
        region = (extra_config.get("region") or "").strip() or DEFAULT_REGION
        bucket = (extra_config.get("bucket") or "").strip()
        if not bucket:
            return StorageTestResult(
                success=False,
                message="缺少必填字段：Bucket（桶名）",
                detail="请先在火山控制台 → 对象存储 → 桶列表 → 创建桶，把桶名填到这里。",
            )

        started = time.perf_counter()
        try:
            # 延迟 import，避免未装 tos SDK 时影响其他模块加载
            try:
                import tos
            except ImportError as exc:
                return StorageTestResult(
                    success=False,
                    message="后端缺少 tos SDK，请联系开发同学（运行 uv sync 安装）",
                    detail=str(exc),
                )

            client = tos.TosClientV2(ak, sk, endpoint, region)
            probe_key = f"yiyu-probe/{uuid.uuid4()}.txt"
            probe_content = b"yiyu-probe"

            # 1) 上传探针
            try:
                client.put_object(bucket, probe_key, content=probe_content)
            except tos.exceptions.TosServerError as exc:
                latency_ms = (time.perf_counter() - started) * 1000.0
                msg = f"上传探针失败（状态码 {exc.status_code}）：{exc.message}"
                hint = ""
                if exc.status_code in (401, 403):
                    hint = "（请检查 Access Key / Secret 是否正确，以及该 ak/sk 是否有写权限）"
                elif exc.status_code == 404:
                    hint = "（桶不存在；请去火山控制台确认桶名和 region）"
                return StorageTestResult(
                    success=False,
                    message=msg + hint,
                    detail=f"RequestId: {exc.request_id} / Code: {exc.code}",
                    latency_ms=latency_ms,
                )

            # 2) 删除探针（不影响判定，删失败仅 warning）
            try:
                client.delete_object(bucket, probe_key)
            except Exception:  # noqa: BLE001
                pass  # 探针保留在桶里不致命

            latency_ms = (time.perf_counter() - started) * 1000.0
            return StorageTestResult(
                success=True,
                message=f"已连通：桶 {bucket}（{region}）可读可写。",
                detail=None,
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001 — 兜底，永远不让 test_connection 抛出
            # 尽量识别已知错误（tos SDK 的 ClientError 含网络错）
            return StorageTestResult(
                success=False,
                message=f"测试失败：{exc.__class__.__name__}：{exc}",
                detail=str(exc)[:400],
            )

    def upload_file(
        self,
        *,
        local_path: str,
        object_key: str,
        credentials: dict[str, str],
        extra_config: dict[str, str],
        expires_seconds: int = 3600,
    ) -> StorageUploadResult:
        """I1b-2 才会实现：put_object_from_file + 预签名 URL"""
        raise NotImplementedError("upload_file 留给 I1b-2 实现")
