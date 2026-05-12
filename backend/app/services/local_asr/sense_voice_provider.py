"""SenseVoice 本地推理 provider（sherpa-onnx 后端）。

负责：
- 加载 ONNX 模型（lazy load，单例）
- 用 sherpa_onnx.OfflineRecognizer 跑推理
- 支持本地音频文件（wav/mp3/m4a/flac 等，soundfile 解码）
- 返回纯文本 + segments（含 SenseVoice 特有的情绪/事件标签）

线程模型：
- recognizer 是 thread-safe（sherpa-onnx 内部用 C++ 内核）
- 但单 instance 不要并发太多 stream，建议 worker 串行处理
"""
from __future__ import annotations

import threading
import time
import wave
from pathlib import Path
from typing import Any

from . import LocalAsrTranscriptionResult, LocalAsrTranscriptionSegment
from .model_paths import DEFAULT_MODEL_NAME, get_model_files, is_model_ready


_RECOGNIZER_LOCK = threading.Lock()
_RECOGNIZER_CACHE: dict[str, Any] = {}  # model_name -> sherpa_onnx.OfflineRecognizer


def _load_recognizer(model_name: str = DEFAULT_MODEL_NAME, *, num_threads: int = 4):
    """懒加载 + cache 单例 recognizer。"""
    with _RECOGNIZER_LOCK:
        if model_name in _RECOGNIZER_CACHE:
            return _RECOGNIZER_CACHE[model_name]
        if not is_model_ready(model_name):
            raise RuntimeError(
                f"本地 ASR 模型未就绪：{model_name}。请先在系统设置 → 语音识别模型 里点「下载模型」。"
            )
        # 延迟 import：在模型缺失时避免影响 backend 启动
        import sherpa_onnx  # type: ignore[import-untyped]

        files = get_model_files(model_name)
        recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(files["model"]),
            tokens=str(files["tokens"]),
            num_threads=num_threads,
            use_itn=True,
            language="auto",
            debug=False,
        )
        _RECOGNIZER_CACHE[model_name] = recognizer
        return recognizer


def _read_audio_as_pcm(file_path: str) -> tuple[Any, int]:
    """读取音频文件 → (numpy.float32 单声道, sample_rate)。

    支持 wav/mp3/m4a/flac/ogg 等所有 soundfile 能读的格式。
    sherpa-onnx 需要 float32 PCM in [-1, 1]，单声道。
    """
    import numpy as np
    import soundfile as sf  # type: ignore[import-untyped]

    audio, sr = sf.read(file_path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        # 多声道 → 取平均合并成单声道
        audio = np.mean(audio, axis=1).astype(np.float32)
    return audio, int(sr)


def transcribe_local_audio(
    file_path: str,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    language: str = "auto",
    use_itn: bool = True,
    num_threads: int = 4,
) -> LocalAsrTranscriptionResult:
    """转写本地音频文件。

    参数：
    - file_path: 本地音频文件绝对路径
    - language: "auto" / "zh" / "en" / "ja" / "ko" / "yue"
    - use_itn: 数字规整（"二零二六" → "2026"）
    - num_threads: ONNX 推理线程数

    返回：LocalAsrTranscriptionResult（含 text + segments）
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"音频文件不存在：{file_path}")

    started = time.perf_counter()
    recognizer = _load_recognizer(model_name, num_threads=num_threads)

    # 读音频
    audio, sample_rate = _read_audio_as_pcm(file_path)
    duration_ms = int(len(audio) * 1000 / sample_rate)

    # 推理
    stream = recognizer.create_stream()
    stream.accept_waveform(sample_rate, audio)
    recognizer.decode_stream(stream)
    result = stream.result

    # SenseVoice 输出的 text 可能含特殊 token：
    # <|zh|><|HAPPY|><|Speech|><|withitn|> 你好世界
    # 这些标签是模型自带的语言/情感/事件指示符。
    raw_text = (result.text or "").strip()
    cleaned_text, lang_tag, emotion_tag, event_tag = _strip_sense_voice_tags(raw_text)

    # SenseVoice 不会返回 utterance 级 segments（它一次性给整段文本），
    # 但我们至少给一个覆盖全音频的 segment 当 fallback；I1b-3 加切片才会有多 segment。
    segments = [
        LocalAsrTranscriptionSegment(
            start_ms=0,
            end_ms=duration_ms,
            text=cleaned_text,
            emotion=emotion_tag,
            event=event_tag,
        )
    ]

    return LocalAsrTranscriptionResult(
        text=cleaned_text,
        segments=segments,
        language=lang_tag or language,
        duration_ms=duration_ms,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
        model_name=model_name,
    )


def _strip_sense_voice_tags(text: str) -> tuple[str, str, str, str]:
    """从 SenseVoice 原始 text 抽出 lang/emotion/event 标签并清理。

    输入示例: '<|zh|><|HAPPY|><|Speech|><|withitn|>这是一段中文'
    输出: ('这是一段中文', 'zh', 'HAPPY', 'Speech')
    """
    lang_tag, emotion_tag, event_tag = "", "", ""
    remaining = text
    # 简单解析：扫描所有 <|...|> token，按已知白名单分类
    while remaining.startswith("<|") and "|>" in remaining:
        end = remaining.index("|>")
        token = remaining[2:end]
        remaining = remaining[end + 2:]
        upper = token.upper()
        if token in {"zh", "en", "ja", "ko", "yue"}:
            lang_tag = lang_tag or token
        elif upper in {"HAPPY", "ANGRY", "SAD", "NEUTRAL", "SURPRISED", "FEARFUL", "DISGUSTED"}:
            emotion_tag = emotion_tag or upper
        elif token in {"Speech", "BGM", "Applause", "Laughter", "Cry"}:
            event_tag = event_tag or token
        else:
            # 未知 token（如 withitn / woitn）跳过不输出
            continue
    return remaining.strip(), lang_tag, emotion_tag, event_tag


def is_recognizer_loaded(model_name: str = DEFAULT_MODEL_NAME) -> bool:
    """诊断用：当前 recognizer 是否已加载到内存。"""
    with _RECOGNIZER_LOCK:
        return model_name in _RECOGNIZER_CACHE
