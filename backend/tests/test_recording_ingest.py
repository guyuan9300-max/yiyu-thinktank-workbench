"""I1b-3 · 录音 ingest 单测

覆盖：
- 文件不存在 → FileNotFoundError
- 无扩展名 → RuntimeError
- 原生支持格式（wav/flac/...）→ 直接调 transcribe_local_audio，不转码
- 需要转码格式（webm/opus/m4a）→ 走 ffmpeg → 再调 transcribe_local_audio
- ffmpeg 不存在 → RuntimeError 带定向提示
- ffmpeg 返回非零 → RuntimeError 带 stderr 尾部
- 转码完成后临时 wav 被清理
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.local_asr import (  # noqa: E402
    LocalAsrTranscriptionResult,
    LocalAsrTranscriptionSegment,
)
from app.services.local_asr import recording_ingest as ingest_mod  # noqa: E402


def _fake_result(text: str = "你好") -> LocalAsrTranscriptionResult:
    return LocalAsrTranscriptionResult(
        text=text,
        segments=[LocalAsrTranscriptionSegment(start_ms=0, end_ms=1000, text=text)],
        language="zh",
        duration_ms=1000,
        elapsed_ms=10.0,
        model_name="sense-voice-small",
    )


@pytest.fixture
def stub_transcribe(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """替换底层 transcribe_local_audio，记录被调用的文件路径，返回固定 result。"""
    calls: list[str] = []

    def _fake(path: str, *, language: str = "auto") -> LocalAsrTranscriptionResult:
        calls.append(path)
        return _fake_result(f"text-for-{Path(path).name}")

    monkeypatch.setattr(ingest_mod, "transcribe_local_audio", _fake)
    return calls


def _touch(path: Path, *, content: bytes = b"FAKE") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class TestValidation:
    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            ingest_mod.transcribe_recording_local_path("/tmp/yiyu-does-not-exist.wav")

    def test_no_extension_raises(self, tmp_path: Path) -> None:
        target = tmp_path / "noext"
        _touch(target)
        with pytest.raises(RuntimeError, match="扩展名"):
            ingest_mod.transcribe_recording_local_path(str(target))


class TestNativeFormats:
    """所有格式都强制走 ffmpeg 转 16kHz 单声道 wav（diarization 要求统一采样率）。"""

    def test_wav_source_normalized_via_ffmpeg(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        stub_transcribe: list[str],
    ) -> None:
        target = tmp_path / "rec.wav"
        _touch(target)
        monkeypatch.setattr(ingest_mod, "_resolve_ffmpeg", lambda: "/fake/ffmpeg")

        def _fake_run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[bytes]:
            Path(cmd[-1]).write_bytes(b"RIFF1234WAVEfmt ")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", _fake_run)

        outcome = ingest_mod.transcribe_recording_local_path(str(target))
        assert outcome.source_format == "wav"
        assert outcome.transcoded_to_wav is True

    def test_mp3_source_normalized_via_ffmpeg(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        stub_transcribe: list[str],
    ) -> None:
        target = tmp_path / "voice.MP3"
        _touch(target)
        monkeypatch.setattr(ingest_mod, "_resolve_ffmpeg", lambda: "/fake/ffmpeg")

        def _fake_run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[bytes]:
            Path(cmd[-1]).write_bytes(b"RIFF1234WAVEfmt ")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", _fake_run)

        outcome = ingest_mod.transcribe_recording_local_path(str(target))
        assert outcome.source_format == "mp3"
        assert outcome.transcoded_to_wav is True


class TestTranscodePath:
    def test_webm_invokes_ffmpeg_then_cleans_temp(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        stub_transcribe: list[str],
    ) -> None:
        target = tmp_path / "rec.webm"
        _touch(target, content=b"FAKEWEBM-PAYLOAD")

        monkeypatch.setattr(ingest_mod, "_resolve_ffmpeg", lambda: "/fake/ffmpeg")
        produced_wav_paths: list[str] = []

        def _fake_run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[bytes]:
            # cmd 末尾是输出 wav 路径
            out = cmd[-1]
            produced_wav_paths.append(out)
            # 让"ffmpeg"写一个非空文件，模拟成功
            Path(out).write_bytes(b"RIFF1234WAVEfmt ")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", _fake_run)

        outcome = ingest_mod.transcribe_recording_local_path(str(target))

        assert outcome.transcoded_to_wav is True
        assert outcome.source_format == "webm"
        # transcribe 被调用的路径应该是 ffmpeg 产生的临时 wav
        assert len(stub_transcribe) == 1
        called_with = stub_transcribe[0]
        assert called_with.endswith(".wav")
        assert called_with in produced_wav_paths
        # 完事后临时 wav 已被清理
        assert not Path(called_with).exists()

    def test_ffmpeg_missing_raises_hint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "rec.webm"
        _touch(target)
        monkeypatch.setattr(ingest_mod, "_resolve_ffmpeg", lambda: None)
        with pytest.raises(RuntimeError, match="未找到 ffmpeg"):
            ingest_mod.transcribe_recording_local_path(str(target))

    def test_ffmpeg_nonzero_exit_raises_with_stderr_tail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "rec.webm"
        _touch(target)
        monkeypatch.setattr(ingest_mod, "_resolve_ffmpeg", lambda: "/fake/ffmpeg")

        def _fake_run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[bytes]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout=b"",
                stderr=b"weird codec\ninvalid data found\n",
            )

        monkeypatch.setattr(subprocess, "run", _fake_run)
        with pytest.raises(RuntimeError) as excinfo:
            ingest_mod.transcribe_recording_local_path(str(target))
        msg = str(excinfo.value)
        assert "exit 1" in msg
        assert "invalid data found" in msg

    def test_ffmpeg_produces_empty_file_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "rec.webm"
        _touch(target)
        monkeypatch.setattr(ingest_mod, "_resolve_ffmpeg", lambda: "/fake/ffmpeg")

        def _fake_run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[bytes]:
            # 返回 0 但不写文件
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        monkeypatch.setattr(subprocess, "run", _fake_run)
        with pytest.raises(RuntimeError, match="没有生成有效 wav"):
            ingest_mod.transcribe_recording_local_path(str(target))
