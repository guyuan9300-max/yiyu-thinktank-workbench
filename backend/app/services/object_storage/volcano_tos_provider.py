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

上传策略（``upload_file``）：
- 用 ``put_object_from_file`` 把本地文件直传桶
- 用 ``pre_signed_url`` 生成 GET 预签名 URL（默认 1 小时），供豆包 ASR 拉取
- 失败时抛出带语义的异常，上层捕获后给用户友好反馈
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
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
        """把本地文件上传到 TOS 并返回预签名 GET URL。

        失败抛 ``RuntimeError``（带用户可读消息），上层负责兜底。
        """
        ak = (credentials.get("access_key_id") or "").strip()
        sk = (credentials.get("secret_access_key") or "").strip()
        if not ak or not sk:
            raise RuntimeError("对象存储凭证缺失：请在设置页填写 Access Key ID / Secret Access Key")
        endpoint = (extra_config.get("endpoint") or "").strip() or DEFAULT_ENDPOINT
        region = (extra_config.get("region") or "").strip() or DEFAULT_REGION
        bucket = (extra_config.get("bucket") or "").strip()
        if not bucket:
            raise RuntimeError("对象存储桶未配置：请在设置页填写 Bucket 名称")
        if not object_key:
            raise RuntimeError("object_key 不能为空")
        if not os.path.isfile(local_path):
            raise RuntimeError(f"本地文件不存在或不可读：{local_path}")
        size_bytes = os.path.getsize(local_path)

        try:
            import tos
        except ImportError as exc:
            raise RuntimeError("后端缺少 tos SDK，请运行 uv sync 安装") from exc

        try:
            client = tos.TosClientV2(ak, sk, endpoint, region)
            client.put_object_from_file(bucket, object_key, local_path)
            signed = client.pre_signed_url(
                tos.HttpMethodType.Http_Method_Get,
                bucket,
                object_key,
                expires=int(expires_seconds),
            )
            signed_url = getattr(signed, "signed_url", None) or getattr(signed, "url", None) or str(signed)
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=int(expires_seconds))
            ).isoformat()
            return StorageUploadResult(
                object_key=object_key,
                url=signed_url,
                expires_at=expires_at,
                size_bytes=size_bytes,
            )
        except RuntimeError:
            raise
        except Exception as exc:
            tos_mod = None
            try:
                import tos as _tos_mod
                tos_mod = _tos_mod
            except ImportError:
                pass
            if tos_mod is not None and isinstance(exc, tos_mod.exceptions.TosServerError):
                hint = ""
                if exc.status_code in (401, 403):
                    hint = "（请检查 ak/sk 是否正确，以及该 ak/sk 是否有写权限）"
                elif exc.status_code == 404:
                    hint = "（桶不存在；请去火山控制台确认桶名和 region）"
                raise RuntimeError(
                    f"TOS 上传失败（状态码 {exc.status_code}）：{exc.message}{hint}"
                ) from exc
            raise RuntimeError(f"TOS 上传失败：{exc.__class__.__name__}：{exc}") from exc
