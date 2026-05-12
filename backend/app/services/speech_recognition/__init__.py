"""语音识别 provider 抽象层。

Provider 协议（Protocol）定义所有 ASR 实现必须暴露的两个方法：
- ``test_connection``：用一段很短的静音音频验证 ak/sk + 端点联通
- ``transcribe_file``：把一个音频文件转写成文字（含 segments 时间戳）

具体实现见 volcano_provider.py 等。注册中心见 registry.py。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class TranscriptionSegment:
    """单段转写结果（带时间戳，方便后续切片拼接）。"""
    start_ms: int
    end_ms: int
    text: str
    speaker_id: str | None = None


@dataclass
class TranscriptionResult:
    """完整转写结果。"""
    text: str
    segments: list[TranscriptionSegment] = field(default_factory=list)
    language: str = ""
    duration_ms: int = 0
    provider: str = ""
    model_id: str = ""


@dataclass
class TestConnectionResult:
    """测试连接的结果。"""
    success: bool
    message: str = ""
    detail: str | None = None
    latency_ms: float | None = None


class TranscriptionProvider(Protocol):
    """所有 ASR provider 必须实现的协议。"""
    name: str

    def test_connection(
        self,
        *,
        credentials: dict[str, str],
        model_id: str,
        extra_config: dict[str, str],
        timeout_seconds: float = 30.0,
    ) -> TestConnectionResult:
        """用一段内置静音音频测试 ak/sk + 端点联通。

        返回 ``TestConnectionResult``，不抛异常 —— 失败也要返回 success=False 且
        message 是用户可读的简短说明。
        """
        ...

    def transcribe_file(
        self,
        *,
        audio_path: str,
        credentials: dict[str, str],
        model_id: str,
        extra_config: dict[str, str],
        timeout_seconds: float = 1800.0,
    ) -> TranscriptionResult:
        """把音频文件转写为文字 + segments。失败抛异常。

        I1a 不调用此接口（只做配置 UI + test_connection）；I1b 才会用。
        """
        ...
