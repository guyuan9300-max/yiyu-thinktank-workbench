"""火山引擎大模型录音文件识别 provider。

官方文档（旧版控制台）：
- 提交：POST https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit
- 查询：POST https://openspeech.bytedance.com/api/v3/auc/bigmodel/query

鉴权 headers（不是 Bearer！火山有自己的 X-Api-* 协议）：
- X-Api-App-Key       : 用户在火山控制台的 App ID
- X-Api-Access-Key    : 用户在火山控制台拿到的 Access Token（敏感）
- X-Api-Resource-Id   : 资源 ID — volc.bigasr.auc（1.0）/ volc.seedasr.auc（2.0）
- X-Api-Request-Id    : 用户生成的任务 UUID
- X-Api-Sequence      : 固定 -1

Payload 结构（**无 app 节点，无 cluster**）：
  {"user": {"uid": "..."}, "audio": {"url": "...", "format": "mp3"},
   "request": {"model_name": "bigmodel", ...}}

应答：Body 为空，所有状态都在 Response Header 里：
- X-Api-Status-Code   : "20000000" = 成功；"45000001" = 请求参数无效
- X-Api-Message       : 文本描述
- X-Tt-Logid          : 服务端日志 ID（查询任务时要传回去）

I1a 只用 test_connection（用一个明显不可达的 audio.url 探测鉴权层）。
I1b 才会真正实现 transcribe_file（上传到对象存储 → submit → 轮询 query）。
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from . import TestConnectionResult, TranscriptionProvider, TranscriptionResult, TranscriptionSegment

DEFAULT_BASE_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel"
DEFAULT_RESOURCE_ID = "volc.bigasr.auc"  # 豆包录音文件识别 1.0

# 鉴权失败的 X-Api-Status-Code（前缀映射；火山没有公开列出所有 4xxx）
_AUTH_FAILURE_CODES = {"45000001"}  # 参数无效（含鉴权字段错），有时鉴权问题也走这条
_PARAM_INVALID_CODES = {"45000001", "45000002", "45000131", "45000132", "45000151"}
_SUCCESS_OR_PROCESSING = {"20000000", "20000001", "20000002", "20000003"}


class VolcanoTranscriptionProvider:
    """火山引擎大模型录音文件识别（豆包）provider 实现。"""
    name = "volcano"

    def test_connection(
        self,
        *,
        credentials: dict[str, str],
        model_id: str,
        extra_config: dict[str, str],
        timeout_seconds: float = 30.0,
    ) -> TestConnectionResult:
        app_id = (credentials.get("app_id") or "").strip()
        access_token = (credentials.get("access_token") or "").strip()
        if not app_id or not access_token:
            return TestConnectionResult(
                success=False,
                message="缺少必填字段：App ID 或 Access Token",
                detail="请在配置里填写完整的 App ID 和 Access Token 后再测试。",
            )

        resource_id = (extra_config.get("resource_id") or "").strip() or DEFAULT_RESOURCE_ID
        base_url = (extra_config.get("base_url") or "").strip() or DEFAULT_BASE_URL
        submit_url = f"{base_url.rstrip('/')}/submit"

        started = time.perf_counter()
        try:
            # test_connection 提交一个明显假的 audio URL：火山会先做鉴权 + 参数校验，
            # 鉴权失败 → X-Api-Status-Code 走 4xxxxxx 且包含"auth"语义
            # 鉴权通过但参数无效 → 也走 45000001 但 message 含 "url" / "invalid url" 等
            # 不管哪条 4xxxxxx，鉴权层已通过 = 我们要的成功信号
            headers = {
                "Content-Type": "application/json",
                "X-Api-App-Key": app_id,
                "X-Api-Access-Key": access_token,
                "X-Api-Resource-Id": resource_id,
                "X-Api-Request-Id": str(uuid.uuid4()),
                "X-Api-Sequence": "-1",
            }
            payload: dict[str, Any] = {
                "user": {"uid": "yiyu-test-connection"},
                "audio": {
                    "url": "https://yiyu-internal-probe.invalid/silence.mp3",
                    "format": "mp3",
                },
                "request": {
                    "model_name": "bigmodel",
                    "enable_itn": True,
                },
            }
            resp = httpx.post(
                submit_url,
                json=payload,
                headers=headers,
                timeout=min(timeout_seconds, 15.0),
            )
            latency_ms = (time.perf_counter() - started) * 1000.0

            # 火山把状态全放在 response header 里，body 是空的
            status_code = resp.headers.get("X-Api-Status-Code", "").strip()
            api_message = resp.headers.get("X-Api-Message", "").strip()
            logid = resp.headers.get("X-Tt-Logid", "").strip()

            # 401/403 = 完全的 HTTP 层鉴权拒绝（火山 v3 一般不走这条，但 v1 / 旧 API 会）
            if resp.status_code in (401, 403):
                return TestConnectionResult(
                    success=False,
                    message=f"鉴权失败（HTTP {resp.status_code}）：请检查 App ID 和 Access Token",
                    detail=f"X-Api-Message: {api_message or '无'} / X-Tt-Logid: {logid}",
                    latency_ms=latency_ms,
                )

            # 成功 / 处理中 / 队列中 / 静音音频 — 都说明鉴权 + endpoint + resource_id 全过
            if status_code in _SUCCESS_OR_PROCESSING:
                return TestConnectionResult(
                    success=True,
                    message="已连通：火山接口认可你的 App ID + Access Token + Resource ID。",
                    detail=f"X-Api-Status-Code: {status_code} / X-Api-Message: {api_message}",
                    latency_ms=latency_ms,
                )

            # 45000001 参数无效 — 我们故意传了假 url，火山会因为 url 不可达而报错
            # 但这意味着 *鉴权层完全通过了*，是我们要的连通成功信号
            if status_code in _PARAM_INVALID_CODES:
                # 但要排除"鉴权字段错误"这种 4xxxxxx —— 检查 message 是不是含鉴权关键词
                msg_lower = api_message.lower()
                auth_indicators = ("auth", "token", "appid", "app_key", "access_key",
                                   "resource", "grant", "permission", "denied", "not granted")
                if any(ind in msg_lower for ind in auth_indicators):
                    return TestConnectionResult(
                        success=False,
                        message=f"鉴权失败：{api_message}",
                        detail=f"X-Api-Status-Code: {status_code} / X-Tt-Logid: {logid}",
                        latency_ms=latency_ms,
                    )
                return TestConnectionResult(
                    success=True,
                    message="鉴权已通过（火山反馈测试请求参数无效是预期的，因为 test_connection 故意传了假音频 URL）。",
                    detail=f"X-Api-Status-Code: {status_code} / X-Api-Message: {api_message}",
                    latency_ms=latency_ms,
                )

            # 其他情况：5500xxxx 服务内部错误等
            return TestConnectionResult(
                success=False,
                message=(
                    f"火山接口异常（X-Api-Status-Code: {status_code or 'unknown'}）"
                    + (f"：{api_message}" if api_message else "")
                ),
                detail=f"HTTP {resp.status_code} / X-Tt-Logid: {logid} / body: {resp.text[:200]}",
                latency_ms=latency_ms,
            )

        except httpx.TimeoutException:
            return TestConnectionResult(
                success=False,
                message=f"请求超时（> {timeout_seconds}s）：检查网络或火山端点是否可达",
            )
        except httpx.HTTPError as exc:
            return TestConnectionResult(
                success=False,
                message=f"网络错误：{exc}",
                detail=str(exc)[:400],
            )
        except Exception as exc:  # noqa: BLE001 — 兜底，永远不让 test_connection 抛出
            return TestConnectionResult(
                success=False,
                message=f"内部错误：{exc}",
                detail=str(exc)[:400],
            )

    def transcribe_file(
        self,
        *,
        audio_path: str,
        credentials: dict[str, str],
        model_id: str,
        extra_config: dict[str, str],
        timeout_seconds: float = 1800.0,
    ) -> TranscriptionResult:
        """I1b 才会实现：上传文件到对象存储 → submit → 轮询 query 拿结果。"""
        raise NotImplementedError("transcribe_file 留给 I1b 迭代实现")
