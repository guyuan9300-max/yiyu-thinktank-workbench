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
