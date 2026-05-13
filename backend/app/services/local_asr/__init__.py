"""本地 ASR provider 模块（SenseVoice-Small via sherpa-onnx）。

跟云端 ASR provider 并列（services/speech_recognition/）的本地实现。

特点：
- 完全离线：模型下载完成后无需联网
- 零额外配置：用户在 UI 上点"下载模型"即可
- 隐私友好：音频不出本机
- 不需要对象存储（TOS）
- 走项目已有的 onnxruntime（sherpa-onnx 内部用），无 PyTorch 依赖

模型：iic/SenseVoiceSmall（约 240MB）+ sherpa-onnx 量化版
来源：HuggingFace（k2-fsa/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-...）
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LocalAsrModelStatus:
    """本地 ASR 模型状态。"""
    installed: bool
    model_name: str
    model_dir: str | None = None
    size_bytes: int = 0
    downloaded_at: str | None = None
    download_in_progress: bool = False
    download_progress_percent: float = 0.0
    download_progress_bytes: int = 0
    download_total_bytes: int = 0
    download_error: str | None = None


@dataclass
class LocalAsrTranscriptionSegment:
    start_ms: int
    end_ms: int
    text: str
    speaker_id: str | None = None
    emotion: str | None = None  # SenseVoice 自带情绪识别（happy/angry/sad/neutral/surprise）
    event: str | None = None    # SenseVoice 自带声学事件（laughter/applause 等）


@dataclass
class LocalAsrTranscriptionResult:
    text: str
    segments: list[LocalAsrTranscriptionSegment]
    language: str = ""
    duration_ms: int = 0
    elapsed_ms: float = 0.0
    model_name: str = "sense-voice-small"


@dataclass
class DiarizationSegment:
    """说话人分离后的一段：(start, end) 毫秒 + speaker 簇 ID。

    speaker 是 0-based 整数，由 sherpa-onnx 聚类决定。展示用 "说话人A/B/C…"
    时由前端按 ``speaker_label_from_index`` 映射。
    """
    start_ms: int
    end_ms: int
    speaker: int


def speaker_label_from_index(index: int) -> str:
    """0 → '说话人A'，1 → '说话人B'，…，超过 26 退化成 '说话人AA' 等。"""
    if index < 0:
        return "说话人未知"
    label = ""
    n = index
    while True:
        label = chr(ord("A") + (n % 26)) + label
        n = n // 26 - 1
        if n < 0:
            break
    return f"说话人{label}"
