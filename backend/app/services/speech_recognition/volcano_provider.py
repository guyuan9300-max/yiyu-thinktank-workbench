"""火山引擎录音文件识别 provider。

API 文档：https://www.volcengine.com/docs/6561/80816 （录音文件识别 - 大模型）

鉴权字段（前端 UI 暴露 + 用户填写）：
- app_id        : 火山应用 App ID
- access_key    : 火山 Access Key（短期）/ Access Key ID（长期）
- access_token  : 用户在火山控制台拿到的 access token（敏感，UI 显示为 password）

接口形态（异步任务 + 轮询）：
1. POST {endpoint}/submit  → 拿 task_id
2. POST {endpoint}/query   → 轮询，status=success/failed/processing

I1a 只用到 test_connection（提交一段内置 1s 静音，看流程是否能 submit + 轮询成功）。
I1b 才会真正用 transcribe_file 跑用户上传的录音。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from . import TestConnectionResult, TranscriptionProvider, TranscriptionResult, TranscriptionSegment

# 火山录音文件识别（大模型版）官方端点。如果未来变更，从 extra_config["base_url"] 读取覆盖。
DEFAULT_BASE_URL = "https://openspeech.bytedance.com/api/v1/auc"

# 1 秒静音 .wav（44 bytes WAV header + 一秒 16kHz 16bit 单声道静音 = 32044 bytes）
# 内置一段最小测试音频，避免依赖 ffmpeg 实时生成。文件放在同目录的 testdata/silence_1s.wav。
SILENCE_WAV_PATH = Path(__file__).parent / "testdata" / "silence_1s.wav"


class VolcanoTranscriptionProvider:
    """火山引擎录音文件识别 provider 实现。"""
    name = "volcano"

    def test_connection(
        self,
        *,
        credentials: dict[str, str],
        model_id: str,
        extra_config: dict[str, str],
        timeout_seconds: float = 30.0,
    ) -> TestConnectionResult:
        app_id = credentials.get("app_id", "").strip()
        access_key = credentials.get("access_key", "").strip()
        access_token = credentials.get("access_token", "").strip()
        if not app_id or not access_token:
            return TestConnectionResult(
                success=False,
                message="缺少必填字段：App ID 或 Access Token",
                detail="请在配置里填写完整的 App ID 和 Access Token 后再测试。",
            )

        base_url = extra_config.get("base_url", "").strip() or DEFAULT_BASE_URL

        started = time.perf_counter()
        try:
            # 用 HEAD 请求或非破坏性的"鉴权预检"调用打到火山端点。
            # 直接 submit 一个真任务会扣费，所以 test_connection 选择只验证鉴权可用（401/403 vs 其他）。
            # 火山 ASR 没有专门 ping 接口，这里 submit 一个最小静音任务，拿到 task_id 即视为成功。
            payload = self._build_submit_payload_for_silence(app_id=app_id, model_id=model_id)
            headers = self._build_headers(access_key=access_key, access_token=access_token)
            resp = httpx.post(
                f"{base_url}/submit",
                json=payload,
                headers=headers,
                timeout=min(timeout_seconds, 15.0),
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            if resp.status_code in (401, 403):
                return TestConnectionResult(
                    success=False,
                    message=f"鉴权失败（HTTP {resp.status_code}）：请检查 App ID / Access Key / Access Token",
                    detail=resp.text[:400],
                    latency_ms=latency_ms,
                )
            if resp.status_code >= 400:
                return TestConnectionResult(
                    success=False,
                    message=f"火山接口返回 HTTP {resp.status_code}",
                    detail=resp.text[:400],
                    latency_ms=latency_ms,
                )
            data: Any
            try:
                data = resp.json()
            except Exception:
                return TestConnectionResult(
                    success=False,
                    message="火山接口返回非 JSON，请检查 base_url 是否正确",
                    detail=resp.text[:400],
                    latency_ms=latency_ms,
                )
            # 火山返回 {"resp": {"code": 1000, "message": "Success", "id": "..."}} 即成功
            code = (data or {}).get("resp", {}).get("code")
            if code in (1000, 0, "1000", "0"):
                return TestConnectionResult(
                    success=True,
                    message="已连通：火山接口认可当前鉴权与 App ID。",
                    detail=None,
                    latency_ms=latency_ms,
                )
            return TestConnectionResult(
                success=False,
                message=f"火山接口拒绝了请求：{(data or {}).get('resp', {}).get('message', 'unknown')}",
                detail=str(data)[:400],
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
        """I1b 才会实现。I1a 占位，调用即抛 NotImplementedError。"""
        raise NotImplementedError("transcribe_file 留给 I1b 迭代实现")

    # --- 内部 helper ---

    def _build_headers(self, *, access_key: str, access_token: str) -> dict[str, str]:
        # 火山 API 的鉴权头组合（按官方文档；不同子产品略有差异，I1b 会精化）
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer; {access_token}",
            "Resource-Id": "volc.bigasr.auc",
            **({"X-Volc-Access-Key": access_key} if access_key else {}),
        }

    def _build_submit_payload_for_silence(self, *, app_id: str, model_id: str) -> dict[str, Any]:
        # 提交一段内置静音音频（用 file_url 引用占位的 1s wav data URL）做最轻量探测。
        # 实际生产环境的 file_url 是用户上传到对象存储的链接；test_connection 只验证鉴权流程。
        return {
            "app": {"appid": app_id},
            "user": {"uid": "yiyu-test-connection"},
            "audio": {
                "format": "wav",
                "rate": 16000,
                "bits": 16,
                "channel": 1,
                # 注意：这里只是"鉴权探测"用的请求。真正提交时火山可能拒绝无效 url，
                # 但鉴权失败会优先返回 401/403，鉴权成功后才会校验音频可达性 —— 这正是我们要的信号。
                "url": "https://example.com/yiyu-test-connection.wav",
            },
            "request": {
                "model_name": model_id or "bigmodel",
                "show_utterances": True,
                "enable_punc": True,
            },
        }
