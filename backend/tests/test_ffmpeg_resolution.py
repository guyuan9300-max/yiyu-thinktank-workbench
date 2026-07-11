from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services import link_material_import  # noqa: E402


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake ffmpeg")
    path.chmod(0o700)
    return path


def test_find_ffmpeg_prefers_explicit_environment_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured = _make_executable(tmp_path / "configured" / "ffmpeg")
    path_binary = _make_executable(tmp_path / "path" / "ffmpeg")
    monkeypatch.setenv("YIYU_FFMPEG_PATH", str(configured))
    monkeypatch.setattr(link_material_import.shutil, "which", lambda _name: str(path_binary))
    monkeypatch.setattr(link_material_import, "_FFMPEG_COMMON_PATHS", (), raising=False)

    assert link_material_import.find_ffmpeg() == str(configured.resolve())


def test_find_ffmpeg_uses_path_before_common_locations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path_binary = _make_executable(tmp_path / "path" / "ffmpeg")
    common_binary = _make_executable(tmp_path / "common" / "ffmpeg")
    monkeypatch.delenv("YIYU_FFMPEG_PATH", raising=False)
    monkeypatch.setattr(link_material_import.shutil, "which", lambda _name: str(path_binary))
    monkeypatch.setattr(link_material_import, "_FFMPEG_COMMON_PATHS", (str(common_binary),), raising=False)

    assert link_material_import.find_ffmpeg() == str(path_binary.resolve())


def test_find_ffmpeg_falls_back_to_user_local_location(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    user_local_binary = _make_executable(tmp_path / ".local" / "bin" / "ffmpeg")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("YIYU_FFMPEG_PATH", raising=False)
    monkeypatch.setattr(link_material_import.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        link_material_import,
        "_FFMPEG_COMMON_PATHS",
        ("~/.local/bin/ffmpeg",),
        raising=False,
    )

    assert link_material_import.find_ffmpeg() == str(user_local_binary.resolve())


def test_find_ffmpeg_rejects_missing_directory_and_non_executable_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    directory = tmp_path / "ffmpeg-directory"
    directory.mkdir()
    non_executable = tmp_path / "ffmpeg-no-exec"
    non_executable.write_bytes(b"fake ffmpeg")
    non_executable.chmod(0o600)
    missing = tmp_path / "missing-ffmpeg"
    monkeypatch.setenv("YIYU_FFMPEG_PATH", str(directory))
    monkeypatch.setattr(link_material_import.shutil, "which", lambda _name: str(non_executable))
    monkeypatch.setattr(
        link_material_import,
        "_FFMPEG_COMMON_PATHS",
        (str(missing), str(directory), str(non_executable)),
        raising=False,
    )

    assert link_material_import.find_ffmpeg() is None
