"""I1b · 火山豆包 transcribe_file 单测

覆盖：
- audio_path 非 URL 抛错（不应静默接收本地路径）
- 凭证缺失抛错
- submit 成功 + 第二次 query 返回 20000000 → 拿到完整 TranscriptionResult
- submit 失败状态码（鉴权 / 401）抛 RuntimeError
- query 返回 4xx 错误抛 RuntimeError
- query 一直处理中超时抛 RuntimeError
- 解析 utterances 正确映射成 segments + speaker_id
- _infer_audio_format 推断带 query string 的 URL
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.speech_recognition.volcano_provider import (  # noqa: E402
    VolcanoTranscriptionProvider,
    _infer_audio_format,
    _parse_query_result,
)


# ---- httpx mock 工具 ----------------------------------------------------


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        api_status: str = "",
        api_message: str = "",
        logid: str = "",
        body: dict[str, Any] | None = None,
        raise_on_json: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = {
            "X-Api-Status-Code": api_status,
            "X-Api-Message": api_message,
            "X-Tt-Logid": logid,
        }
        self._body = body or {}
        self._raise_on_json = raise_on_json

    def json(self) -> dict[str, Any]:
        if self._raise_on_json is not None:
            raise self._raise_on_json
        return self._body


class _FakeHttpxClient:
    """记录 POST 调用并按队列返回预设响应。"""

    def __init__(self, responses_by_url: dict[str, list[_FakeResponse]]) -> None:
        self.responses_by_url = responses_by_url
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self) -> "_FakeHttpxClient":
        return self

    def __exit__(self, *_a: Any) -> None:
        pass

    def post(self, url: str, json: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> _FakeResponse:
        self.calls.append((url, json or {}))
        bucket = self.responses_by_url.get(url, [])
        if not bucket:
            raise AssertionError(f"unexpected POST to {url}")
        return bucket.pop(0)


@pytest.fixture
def provider() -> VolcanoTranscriptionProvider:
    return VolcanoTranscriptionProvider()


def _full_creds() -> dict[str, str]:
    return {"app_id": "appid-fake", "access_token": "token-fake"}


def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """加速轮询测试：把 time.sleep 改成 no-op。"""
    monkeypatch.setattr("app.services.speech_recognition.volcano_provider.time.sleep", lambda *_a, **_kw: None)


# ---- 输入校验 ------------------------------------------------------------


class TestTranscribeFileValidation:
    def test_local_path_rejected_with_hint(self, provider) -> None:
        with pytest.raises(RuntimeError, match="公网 URL"):
            provider.transcribe_file(
                audio_path="/tmp/audio.mp3",
                credentials=_full_creds(),
                model_id="bigmodel",
                extra_config={},
            )

    def test_empty_audio_path_rejected(self, provider) -> None:
        with pytest.raises(RuntimeError):
            provider.transcribe_file(
                audio_path="",
                credentials=_full_creds(),
                model_id="bigmodel",
                extra_config={},
            )

    def test_missing_credentials_rejected(self, provider) -> None:
        with pytest.raises(RuntimeError, match="凭证缺失"):
            provider.transcribe_file(
                audio_path="https://example.com/audio.mp3",
                credentials={"app_id": ""},
                model_id="bigmodel",
                extra_config={},
            )


# ---- 成功路径 ------------------------------------------------------------


class TestTranscribeFileSuccess:
    def test_submit_then_processing_then_success(
        self, provider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _no_sleep(monkeypatch)

        submit_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
        query_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
        fake_client = _FakeHttpxClient({
            submit_url: [_FakeResponse(api_status="20000000", api_message="ok")],
            query_url: [
                _FakeResponse(api_status="20000001", api_message="processing"),
                _FakeResponse(
                    api_status="20000000",
                    api_message="ok",
                    body={
                        "result": {
                            "text": "你好世界",
                            "utterances": [
                                {"text": "你好", "start_time": 0, "end_time": 500, "speaker_id": "0"},
                                {"text": "世界", "start_time": 500, "end_time": 1200, "speaker_id": "1"},
                            ],
                        },
                        "audio_info": {"duration": 1200, "language": "zh-CN"},
                    },
                ),
            ],
        })

        monkeypatch.setattr(httpx, "Client", lambda *a, **kw: fake_client)

        result = provider.transcribe_file(
            audio_path="https://cdn.example.com/foo.mp3?sig=abc",
            credentials=_full_creds(),
            model_id="bigmodel",
            extra_config={"poll_interval_seconds": "1"},
            timeout_seconds=30.0,
        )

        assert result.text == "你好世界"
        assert result.language == "zh-CN"
        assert result.duration_ms == 1200
        assert result.provider == "volcano"
        assert result.model_id == "bigmodel"
        assert len(result.segments) == 2
        assert result.segments[0].text == "你好"
        assert result.segments[0].start_ms == 0
        assert result.segments[0].end_ms == 500
        assert result.segments[0].speaker_id == "0"
        assert result.segments[1].speaker_id == "1"

        # submit + 2 次 query
        assert len(fake_client.calls) == 3
        assert fake_client.calls[0][0] == submit_url
        assert fake_client.calls[0][1]["audio"]["url"] == "https://cdn.example.com/foo.mp3?sig=abc"
        assert fake_client.calls[0][1]["audio"]["format"] == "mp3"

    def test_audio_format_inferred_from_extension(self) -> None:
        assert _infer_audio_format("https://x.com/a.wav") == "wav"
        assert _infer_audio_format("https://x.com/a.m4a?sig=1") == "m4a"
        assert _infer_audio_format("https://x.com/no-ext") == "mp3"
        assert _infer_audio_format("https://x.com/a.MP3") == "mp3"

    def test_parse_query_result_fills_text_from_utterances_when_top_text_missing(self) -> None:
        body = {
            "result": {
                "text": "",
                "utterances": [
                    {"text": "alpha", "start_time": 0, "end_time": 100},
                    {"text": "beta", "start_time": 100, "end_time": 200},
                ],
            },
            "audio_info": {"duration": 200},
        }
        out = _parse_query_result(body=body, provider_name="volcano", model_id="bigmodel", elapsed_seconds=1.0)
        assert "alpha" in out.text and "beta" in out.text
        assert out.duration_ms == 200

    def test_parse_query_result_handles_empty_body(self) -> None:
        out = _parse_query_result(body={}, provider_name="volcano", model_id="bigmodel", elapsed_seconds=0.0)
        assert out.text == ""
        assert out.segments == []
        assert out.duration_ms == 0


# ---- 失败路径 ------------------------------------------------------------


class TestTranscribeFileFailures:
    def test_submit_401_raises_auth_error(self, provider, monkeypatch: pytest.MonkeyPatch) -> None:
        _no_sleep(monkeypatch)
        fake_client = _FakeHttpxClient({
            "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit": [
                _FakeResponse(status_code=401, api_status="40300001", api_message="Unauthorized"),
            ],
        })
        monkeypatch.setattr(httpx, "Client", lambda *a, **kw: fake_client)
        with pytest.raises(RuntimeError, match="鉴权失败"):
            provider.transcribe_file(
                audio_path="https://cdn.example.com/foo.mp3",
                credentials=_full_creds(),
                model_id="bigmodel",
                extra_config={},
            )

    def test_submit_bad_status_raises(self, provider, monkeypatch: pytest.MonkeyPatch) -> None:
        _no_sleep(monkeypatch)
        fake_client = _FakeHttpxClient({
            "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit": [
                _FakeResponse(api_status="45000001", api_message="Bad URL"),
            ],
        })
        monkeypatch.setattr(httpx, "Client", lambda *a, **kw: fake_client)
        with pytest.raises(RuntimeError, match="submit 失败"):
            provider.transcribe_file(
                audio_path="https://cdn.example.com/foo.mp3",
                credentials=_full_creds(),
                model_id="bigmodel",
                extra_config={},
            )

    def test_query_4xx_raises(self, provider, monkeypatch: pytest.MonkeyPatch) -> None:
        _no_sleep(monkeypatch)
        submit_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
        query_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
        fake_client = _FakeHttpxClient({
            submit_url: [_FakeResponse(api_status="20000000")],
            query_url: [_FakeResponse(api_status="55000000", api_message="server boom", logid="lg-1")],
        })
        monkeypatch.setattr(httpx, "Client", lambda *a, **kw: fake_client)
        with pytest.raises(RuntimeError) as excinfo:
            provider.transcribe_file(
                audio_path="https://cdn.example.com/foo.mp3",
                credentials=_full_creds(),
                model_id="bigmodel",
                extra_config={},
            )
        assert "55000000" in str(excinfo.value)
        assert "server boom" in str(excinfo.value)

    def test_query_always_processing_times_out(self, provider, monkeypatch: pytest.MonkeyPatch) -> None:
        _no_sleep(monkeypatch)
        submit_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
        query_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
        # 提供超过 deadline 仍能持续返回 processing 的响应（pop_left 不会越界）
        processing_responses = [_FakeResponse(api_status="20000001", api_message="processing") for _ in range(50)]
        fake_client = _FakeHttpxClient({
            submit_url: [_FakeResponse(api_status="20000000")],
            query_url: processing_responses,
        })
        monkeypatch.setattr(httpx, "Client", lambda *a, **kw: fake_client)

        # 用 time.perf_counter 控制让"流逝时间"快速跨过 deadline
        clock = [0.0]

        def _fake_perf_counter() -> float:
            clock[0] += 5.0
            return clock[0]

        monkeypatch.setattr(
            "app.services.speech_recognition.volcano_provider.time.perf_counter",
            _fake_perf_counter,
        )

        with pytest.raises(RuntimeError, match="轮询超时"):
            provider.transcribe_file(
                audio_path="https://cdn.example.com/foo.mp3",
                credentials=_full_creds(),
                model_id="bigmodel",
                extra_config={},
                timeout_seconds=10.0,
            )

    def test_http_error_wrapped(self, provider, monkeypatch: pytest.MonkeyPatch) -> None:
        _no_sleep(monkeypatch)

        class _BoomClient:
            def __enter__(self) -> "_BoomClient":
                return self

            def __exit__(self, *_a: Any) -> None:
                pass

            def post(self, *_a: Any, **_kw: Any) -> Any:
                raise httpx.ConnectError("dns failed")

        monkeypatch.setattr(httpx, "Client", lambda *a, **kw: _BoomClient())
        with pytest.raises(RuntimeError, match="网络错误"):
            provider.transcribe_file(
                audio_path="https://cdn.example.com/foo.mp3",
                credentials=_full_creds(),
                model_id="bigmodel",
                extra_config={},
            )
