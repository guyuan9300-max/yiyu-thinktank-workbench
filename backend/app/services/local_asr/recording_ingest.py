"""录音 ingest：把前端落到本地的录音文件转写成文字（含说话人分离）。

设计意图：
- 前端通过 IPC 把 MediaRecorder 产生的 Blob 写到 ``userData/recordings/{uuid}.{ext}``
- 后端从 ``audioPath`` 字符串接手，统一用 ffmpeg 转成 16kHz 单声道 wav
- 如果说话人分离模型就绪：走 "diarize → 分段 ASR → 拼对话稿" 链路
- 否则降级为整段 ASR（保留原行为，跟之前一致）

将来加云端对象存储后，会另起一个 ``transcribe_remote_audio_url``，公用相同的 result 结构。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .sense_voice_provider import (
    transcribe_local_audio,
    transcribe_local_audio_segments,
)
from . import (
    DiarizationSegment,
    LocalAsrTranscriptionResult,
    LocalAsrTranscriptionSegment,
    speaker_label_from_index,
)
from .model_paths import is_diarization_ready


# soundfile/libsndfile 1.2.2 原生能直接读的容器（在用户机器上确认过）
_SOUNDFILE_NATIVE_EXTS: frozenset[str] = frozenset({
    "wav", "flac", "ogg", "mp3", "aiff", "aif", "au", "caf", "w64",
})

# 必须用 ffmpeg 转码到 wav 才能喂给 sherpa-onnx 的容器
_TRANSCODE_REQUIRED_EXTS: frozenset[str] = frozenset({
    "webm", "opus", "m4a", "mp4", "aac",
})


@dataclass
class RecordingTranscribeOutcome:
    """ingest 完成后的统一返回结构。

    - ``result.text``：去说话人的完整 transcript（原行为）
    - ``dialogue_text``：含说话人前缀的对话稿（"说话人A：xxx\\n说话人B：xxx\\n…"）
      diarization 未启用时与 ``result.text`` 相同
    - ``num_speakers``：检测出的说话人数（diarization 未启用时为 1）
    - ``diarization_used``：是否真的走了说话人分离
    """
    result: LocalAsrTranscriptionResult
    source_format: str
    transcoded_to_wav: bool
    dialogue_text: str = ""
    num_speakers: int = 1
    diarization_used: bool = False
    diarization_error: str | None = None


def transcribe_recording_local_path(
    audio_path: str,
    *,
    language: str = "auto",
) -> RecordingTranscribeOutcome:
    """从本地路径转写录音（diarization 就绪时含说话人分离）。

    - audio_path 必须是绝对路径且文件存在
    - 任何非 wav 都会用 ffmpeg 转 16kHz 单声道 wav
    - **wav 也会被转一次**——确保采样率统一为 diarizer/SenseVoice 的 16kHz
    - 临时 wav 在函数返回后会被删除
    """
    src = Path(audio_path)
    if not src.is_file():
        raise FileNotFoundError(f"录音文件不存在：{audio_path}")

    ext = src.suffix.lstrip(".").lower()
    if not ext:
        raise RuntimeError("无法识别录音文件扩展名，请确保文件名带后缀")

    # 为了让 diarization + 分段 ASR 拿到一致的 16kHz 单声道 wav，
    # 即使源就是 wav，也走 ffmpeg 一遍统一采样率
    working_wav = _transcode_to_wav(src)
    cleanup_working = True
    try:
        if is_diarization_ready():
            outcome = _transcribe_with_diarization(working_wav, language=language)
            outcome.source_format = ext
            outcome.transcoded_to_wav = (ext not in _SOUNDFILE_NATIVE_EXTS) or True
            return outcome

        # 降级：单说话人整段 ASR
        result = transcribe_local_audio(str(working_wav), language=language)
        return RecordingTranscribeOutcome(
            result=result,
            source_format=ext,
            transcoded_to_wav=True,
            dialogue_text=result.text,
            num_speakers=1 if result.text.strip() else 0,
            diarization_used=False,
            diarization_error=None,
        )
    finally:
        if cleanup_working:
            try:
                working_wav.unlink(missing_ok=True)
            except OSError:
                pass


def _transcribe_with_diarization(
    wav_path: Path,
    *,
    language: str,
) -> RecordingTranscribeOutcome:
    """对一个已经转好的 16kHz 单声道 wav 走 diarization + 分段 ASR。

    任何 diarization 内部错误都会被捕获并降级到整段 ASR，错误写到 ``diarization_error``。
    """
    from .diarization_provider import diarize_audio_file, DiarizationNotReadyError

    diar_segments: list[DiarizationSegment] = []
    diarization_error: str | None = None
    try:
        diar_segments = diarize_audio_file(str(wav_path))
    except DiarizationNotReadyError as exc:
        diarization_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        diarization_error = f"{exc.__class__.__name__}：{exc}"

    if not diar_segments:
        # diarization 失败或者整段没人说话 → 降级
        result = transcribe_local_audio(str(wav_path), language=language)
        return RecordingTranscribeOutcome(
            result=result,
            source_format="",
            transcoded_to_wav=True,
            dialogue_text=result.text,
            num_speakers=1 if result.text.strip() else 0,
            diarization_used=False,
            diarization_error=diarization_error,
        )

    # 对每个 diarization segment 单独跑 SenseVoice
    segments_ms = [(s.start_ms, s.end_ms) for s in diar_segments]
    asr_results = transcribe_local_audio_segments(
        str(wav_path),
        segments_ms,
        language=language,
    )

    dialogue_lines: list[str] = []
    merged_segments: list[LocalAsrTranscriptionSegment] = []
    speaker_set: set[int] = set()
    full_text_chunks: list[str] = []

    last_speaker: int | None = None
    pending_buf: list[str] = []

    def flush_pending() -> None:
        nonlocal pending_buf, last_speaker
        if pending_buf and last_speaker is not None:
            joined = "".join(pending_buf).strip()
            if joined:
                dialogue_lines.append(f"{speaker_label_from_index(last_speaker)}：{joined}")
        pending_buf = []

    for diar, asr in zip(diar_segments, asr_results):
        text = (asr.text or "").strip()
        if not text:
            continue
        speaker_set.add(diar.speaker)
        full_text_chunks.append(text)
        merged_segments.append(
            LocalAsrTranscriptionSegment(
                start_ms=diar.start_ms,
                end_ms=diar.end_ms,
                text=text,
                speaker_id=speaker_label_from_index(diar.speaker),
                emotion=asr.segments[0].emotion if asr.segments else None,
                event=asr.segments[0].event if asr.segments else None,
            )
        )
        # 合并同一说话人的连续片段 → 一行对话
        if last_speaker is None or diar.speaker != last_speaker:
            flush_pending()
            last_speaker = diar.speaker
        pending_buf.append(text)
    flush_pending()

    full_text = "".join(full_text_chunks)
    duration_ms = diar_segments[-1].end_ms if diar_segments else 0
    elapsed_total = sum(r.elapsed_ms for r in asr_results)

    aggregated = LocalAsrTranscriptionResult(
        text=full_text,
        segments=merged_segments,
        language=language,
        duration_ms=duration_ms,
        elapsed_ms=elapsed_total,
    )

    return RecordingTranscribeOutcome(
        result=aggregated,
        source_format="",
        transcoded_to_wav=True,
        dialogue_text="\n".join(dialogue_lines),
        num_speakers=len(speaker_set),
        diarization_used=True,
        diarization_error=None,
    )


def _transcode_to_wav(src: Path) -> Path:
    """ffmpeg 把 src 转成 16kHz 单声道 16-bit wav，返回临时文件路径。"""
    ffmpeg_bin = _resolve_ffmpeg()
    if ffmpeg_bin is None:
        raise RuntimeError(
            "未找到 ffmpeg：本地 ASR 需要 ffmpeg 把 webm/opus/m4a 等容器转成 wav。"
            "请先 ``brew install ffmpeg`` 或确保 ffmpeg 在 PATH 中。"
        )

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="yiyu-asr-", suffix=".wav")
    os.close(tmp_fd)
    cmd: list[str] = [
        ffmpeg_bin,
        "-y",
        "-loglevel", "error",
        "-i", str(src),
        "-ac", "1",
        "-ar", "16000",
        "-sample_fmt", "s16",
        tmp_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        _safe_unlink(tmp_path)
        raise RuntimeError(f"ffmpeg 转码超时（>10 分钟）：{src.name}") from exc
    except OSError as exc:
        _safe_unlink(tmp_path)
        raise RuntimeError(f"ffmpeg 启动失败：{exc}") from exc

    if proc.returncode != 0:
        _safe_unlink(tmp_path)
        stderr_tail = (proc.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()
        tail = "\n".join(stderr_tail[-4:]) if stderr_tail else ""
        raise RuntimeError(
            f"ffmpeg 转码失败（exit {proc.returncode}）{('：' + tail) if tail else ''}"
        )

    output = Path(tmp_path)
    if not output.is_file() or output.stat().st_size == 0:
        _safe_unlink(tmp_path)
        raise RuntimeError("ffmpeg 转码后没有生成有效 wav 文件")
    return output


def _resolve_ffmpeg() -> str | None:
    """优先 PATH，其次几个常见安装位置兜底。"""
    found = shutil.which("ffmpeg")
    if found:
        return found
    fallback_candidates: Iterable[str] = (
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/Users/example_user/.local/bin/ffmpeg",
    )
    for candidate in fallback_candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _safe_unlink(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
