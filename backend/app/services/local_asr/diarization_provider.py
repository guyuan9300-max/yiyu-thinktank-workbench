"""本地说话人分离（speaker diarization）provider。

依赖 sherpa-onnx 的 ``OfflineSpeakerDiarization`` pipeline：
- Pyannote segmentation 模型负责 VAD + 切分
- 3D-Speaker embedding 模型负责说话人特征向量
- 内置 FastClustering（AHC 余弦聚类）自动决定簇数

调用方式：
1. 输入：本地 wav 文件路径（必须是 16kHz 单声道 float32 PCM）
2. 输出：``list[DiarizationSegment]``（按 start_ms 升序），speaker 是 0-based
3. 模型未下载时抛 ``DiarizationNotReadyError``，上层可降级到单说话人 ASR

线程模型：与 sense_voice 类似，单 instance 推荐串行调用。
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from . import DiarizationSegment
from .model_paths import (
    SPEAKER_EMBEDDING_MODEL_NAME,
    SPEAKER_SEGMENTATION_MODEL_NAME,
    get_model_files,
    is_diarization_ready,
)


class DiarizationNotReadyError(RuntimeError):
    """diarization 双模型未就绪 — 上层应降级或提示用户先下载模型。"""


_DIARIZER_LOCK = threading.Lock()
_DIARIZER_CACHE: dict[str, Any] = {}  # cache_key -> OfflineSpeakerDiarization


def _build_cache_key(num_threads: int, threshold: float) -> str:
    return f"t{num_threads}:thr{threshold:.3f}"


def _load_diarizer(
    *,
    num_threads: int = 2,
    cluster_threshold: float = 0.5,
    min_duration_on: float = 0.3,
    min_duration_off: float = 0.5,
):
    """懒加载 + cache OfflineSpeakerDiarization 单例。"""
    cache_key = _build_cache_key(num_threads, cluster_threshold)
    with _DIARIZER_LOCK:
        if cache_key in _DIARIZER_CACHE:
            return _DIARIZER_CACHE[cache_key]
        if not is_diarization_ready():
            raise DiarizationNotReadyError(
                "说话人分离模型未就绪。请先在「系统设置 → 语音识别模型 → 说话人分离」里下载。"
            )
        # 延迟 import：避免没装 sherpa_onnx 时阻断其他模块加载
        import sherpa_onnx  # type: ignore[import-untyped]

        seg_model = get_model_files(SPEAKER_SEGMENTATION_MODEL_NAME)["model"]
        emb_model = get_model_files(SPEAKER_EMBEDDING_MODEL_NAME)["model"]

        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=str(seg_model),
                ),
                num_threads=num_threads,
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(emb_model),
                num_threads=num_threads,
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=-1,  # -1 = 自动聚类决定簇数
                threshold=cluster_threshold,
            ),
            min_duration_on=min_duration_on,
            min_duration_off=min_duration_off,
        )
        diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
        _DIARIZER_CACHE[cache_key] = diarizer
        return diarizer


def _read_audio_as_float32_mono(file_path: str) -> tuple[Any, int]:
    """读音频 → float32 mono numpy array + sample_rate。"""
    import numpy as np
    import soundfile as sf  # type: ignore[import-untyped]

    audio, sr = sf.read(file_path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1).astype(np.float32)
    return audio, int(sr)


def diarize_audio_file(
    file_path: str,
    *,
    cluster_threshold: float = 0.5,
    num_threads: int = 2,
) -> list[DiarizationSegment]:
    """对一个本地音频文件做说话人分离。

    参数：
    - file_path: 本地音频文件绝对路径
    - cluster_threshold: 余弦距离聚类阈值（0.4-0.7 常见，越大越保守 = 簇越少）
    - num_threads: ONNX 推理线程数

    返回：按 start_ms 升序的 ``list[DiarizationSegment]``，可能为空。

    抛错：
    - ``FileNotFoundError``：音频不存在
    - ``DiarizationNotReadyError``：模型未下载
    - ``ValueError``：音频采样率不匹配模型期望
    """
    src = Path(file_path)
    if not src.is_file():
        raise FileNotFoundError(f"音频文件不存在：{file_path}")

    diarizer = _load_diarizer(
        num_threads=num_threads,
        cluster_threshold=cluster_threshold,
    )

    audio, sample_rate = _read_audio_as_float32_mono(file_path)
    expected_sr = int(diarizer.sample_rate)
    if sample_rate != expected_sr:
        raise ValueError(
            f"音频采样率 {sample_rate} 与模型期望 {expected_sr} 不一致；"
            "上游应先用 ffmpeg 强制转 16kHz 单声道。"
        )

    started = time.perf_counter()
    result = diarizer.process(audio).sort_by_start_time()
    elapsed = time.perf_counter() - started

    # sort_by_start_time 在 sherpa-onnx 里实际是 in-place + return list
    segments_raw: list[Any]
    if isinstance(result, list):
        segments_raw = result
    else:
        # 兼容：如果是 OfflineSpeakerDiarizationResult，遍历它的索引
        try:
            segments_raw = list(result)
        except TypeError:
            # 退而求其次：用 num_segments 索引
            segments_raw = [result[i] for i in range(result.num_segments)]

    out: list[DiarizationSegment] = []
    for seg in segments_raw:
        start_s = float(getattr(seg, "start", 0.0))
        end_s = float(getattr(seg, "end", start_s))
        speaker_idx = int(getattr(seg, "speaker", 0))
        out.append(
            DiarizationSegment(
                start_ms=int(round(start_s * 1000)),
                end_ms=int(round(end_s * 1000)),
                speaker=speaker_idx,
            )
        )

    # 兜底：start_ms <= end_ms
    out = [s for s in out if s.end_ms > s.start_ms]
    out.sort(key=lambda s: s.start_ms)
    return out


def is_diarizer_loaded() -> bool:
    with _DIARIZER_LOCK:
        return bool(_DIARIZER_CACHE)
