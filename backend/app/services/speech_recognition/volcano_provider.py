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

转写流程（``transcribe_file``）：
1. 接收 audio_path：必须是 https/http URL（本地路径请上层先调 TOS upload）
2. submit 提交转写任务，带 X-Api-Request-Id（UUID）
3. 轮询 query 直到 status_code = 20000000（成功）或 4xx/5xx 失败
4. 解析 result.text + result.utterances 映射成 TranscriptionResult
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
_SUCCESS_CODE = "20000000"
_PROCESSING_CODES = {"20000001", "20000002", "20000003"}

# transcribe_file 轮询默认参数
_DEFAULT_POLL_INTERVAL_SECONDS = 5.0
_DEFAULT_INITIAL_POLL_DELAY_SECONDS = 3.0


def _infer_audio_format(url: str) -> str:
    """从 URL 推断音频格式给火山 payload.audio.format 字段。

    火山 v3 接受 mp3 / wav / m4a / flac / ogg / mp4 等。
    取 URL path 的扩展名；未知 → 默认 'mp3'（火山兜底也走 mp3）。
    """
    lower = url.lower().split("?", 1)[0]
    for ext in ("mp3", "wav", "m4a", "flac", "ogg", "mp4", "aac", "opus"):
        if lower.endswith(f".{ext}"):
            return ext
    return "mp3"


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
        """提交并轮询豆包 ASR 大模型，返回完整转写结果。

        约束：``audio_path`` 必须是公网 https/http URL（火山只接受 URL）；
        本地文件请上层先调 ``volcano_tos_provider.upload_file`` 拿到预签名 URL。

        失败抛 ``RuntimeError``（带用户可读消息）。
        """
        if not audio_path or not isinstance(audio_path, str):
            raise RuntimeError("audio_path 必须是有效的 URL 字符串")
        if not (audio_path.startswith("http://") or audio_path.startswith("https://")):
            raise RuntimeError(
                "火山豆包 ASR 只接受公网 URL；请先把本地文件上传到对象存储再传 URL。"
            )

        app_id = (credentials.get("app_id") or "").strip()
        access_token = (credentials.get("access_token") or "").strip()
        if not app_id or not access_token:
            raise RuntimeError("豆包凭证缺失：请在设置页填写 App ID / Access Token")

        resource_id = (extra_config.get("resource_id") or "").strip() or DEFAULT_RESOURCE_ID
        base_url = (extra_config.get("base_url") or "").strip() or DEFAULT_BASE_URL
        submit_url = f"{base_url.rstrip('/')}/submit"
        query_url = f"{base_url.rstrip('/')}/query"
        uid = (extra_config.get("uid") or "").strip() or "yiyu-thinktank-workbench"
        model_name = (model_id or "").strip() or "bigmodel"
        try:
            poll_interval = float(extra_config.get("poll_interval_seconds") or _DEFAULT_POLL_INTERVAL_SECONDS)
        except (TypeError, ValueError):
            poll_interval = _DEFAULT_POLL_INTERVAL_SECONDS
        if poll_interval < 1.0:
            poll_interval = 1.0

        request_id = str(uuid.uuid4())
        audio_format = _infer_audio_format(audio_path)
        headers = {
            "Content-Type": "application/json",
            "X-Api-App-Key": app_id,
            "X-Api-Access-Key": access_token,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
            "X-Api-Sequence": "-1",
        }
        payload: dict[str, Any] = {
            "user": {"uid": uid},
            "audio": {"url": audio_path, "format": audio_format},
            "request": {
                "model_name": model_name,
                "enable_itn": True,
                "enable_punc": True,
                "enable_speaker_info": True,
            },
        }

        started = time.perf_counter()
        try:
            with httpx.Client(timeout=min(timeout_seconds, 60.0)) as client:
                submit_resp = client.post(submit_url, json=payload, headers=headers)
                submit_status = submit_resp.headers.get("X-Api-Status-Code", "").strip()
                submit_message = submit_resp.headers.get("X-Api-Message", "").strip()
                submit_logid = submit_resp.headers.get("X-Tt-Logid", "").strip()

                if submit_resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"鉴权失败（HTTP {submit_resp.status_code}）：请检查 App ID / Access Token"
                    )
                if submit_status not in _SUCCESS_OR_PROCESSING:
                    raise RuntimeError(
                        f"豆包 submit 失败（X-Api-Status-Code: {submit_status or 'unknown'}）"
                        + (f"：{submit_message}" if submit_message else "")
                        + (f" / X-Tt-Logid: {submit_logid}" if submit_logid else "")
                    )

                deadline = started + max(timeout_seconds, 60.0)
                # 首次查询前小睡一下，避免立刻 query 返回"任务排队中"
                time.sleep(_DEFAULT_INITIAL_POLL_DELAY_SECONDS)
                while True:
                    elapsed = time.perf_counter() - started
                    if time.perf_counter() > deadline:
                        raise RuntimeError(
                            f"豆包 query 轮询超时（> {timeout_seconds:.0f}s）— 任务 {request_id} 仍在处理中"
                        )

                    query_resp = client.post(query_url, json={}, headers=headers)
                    status_code = query_resp.headers.get("X-Api-Status-Code", "").strip()
                    message = query_resp.headers.get("X-Api-Message", "").strip()
                    logid = query_resp.headers.get("X-Tt-Logid", "").strip()

                    if status_code == _SUCCESS_CODE:
                        try:
                            body = query_resp.json()
                        except Exception as exc:
                            raise RuntimeError(
                                f"豆包返回成功但 body 非法 JSON：{exc}"
                            ) from exc
                        return _parse_query_result(
                            body=body if isinstance(body, dict) else {},
                            provider_name=self.name,
                            model_id=model_name,
                            elapsed_seconds=elapsed,
                        )

                    if status_code in _PROCESSING_CODES:
                        time.sleep(poll_interval)
                        continue

                    # 4xx / 5xx 错误
                    raise RuntimeError(
                        f"豆包 query 失败（X-Api-Status-Code: {status_code or 'unknown'}）"
                        + (f"：{message}" if message else "")
                        + (f" / X-Tt-Logid: {logid}" if logid else "")
                    )

        except httpx.TimeoutException as exc:
            raise RuntimeError(f"豆包 ASR 请求超时：{exc}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"豆包 ASR 网络错误：{exc}") from exc


def _parse_query_result(
    *,
    body: dict[str, Any],
    provider_name: str,
    model_id: str,
    elapsed_seconds: float,
) -> TranscriptionResult:
    """把火山 query 返回 body 映射成 TranscriptionResult。

    火山 v3 典型结构（不同模型版本字段可能略有偏差，做容错）：
        {
          "result": {
            "text": "...",
            "utterances": [{"text": "...", "start_time": 0, "end_time": 1234,
                              "speaker_id": "0"}, ...]
          },
          "audio_info": {"duration": 12345}
        }
    """
    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    text = str(result.get("text") or "").strip()

    utterances_raw = result.get("utterances")
    if not isinstance(utterances_raw, list):
        utterances_raw = []

    segments: list[TranscriptionSegment] = []
    for item in utterances_raw:
        if not isinstance(item, dict):
            continue
        seg_text = str(item.get("text") or "").strip()
        if not seg_text:
            continue
        start_ms = _safe_int(item.get("start_time"), default=0)
        end_ms = _safe_int(item.get("end_time"), default=start_ms)
        speaker_raw = item.get("speaker_id")
        speaker_id = str(speaker_raw).strip() if speaker_raw not in (None, "") else None
        segments.append(
            TranscriptionSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=seg_text,
                speaker_id=speaker_id,
            )
        )

    if not text and segments:
        text = "\n".join(seg.text for seg in segments)

    audio_info = body.get("audio_info") if isinstance(body.get("audio_info"), dict) else {}
    duration_ms = _safe_int(audio_info.get("duration"), default=0)
    if duration_ms == 0 and segments:
        duration_ms = segments[-1].end_ms

    language = str((audio_info or {}).get("language") or "").strip()

    return TranscriptionResult(
        text=text,
        segments=segments,
        language=language,
        duration_ms=duration_ms,
        provider=provider_name,
        model_id=model_id,
    )


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
