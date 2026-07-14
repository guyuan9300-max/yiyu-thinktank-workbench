from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.services.link_material_import as link_material_import  # noqa: E402
from app.services.link_material_import import (  # noqa: E402
    LinkMaterialImportError,
    LinkMaterialImportOptions,
    build_clean_video_markdown,
    cleanup_temp_dir,
    cleanup_transcript_text,
    detect_link_material,
    extract_link_material_source,
    find_local_transcript_engine,
    read_valid_downloaded_subtitles,
    _clean_subtitle_text,
)


@pytest.fixture(autouse=True)
def _stable_public_platform_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests must not depend on external DNS while fetch guards stay active."""
    monkeypatch.setattr(
        link_material_import,
        "_resolve_hostname_addresses",
        lambda _hostname: {"93.184.216.34"},
    )


def test_detect_bilibili_link_and_bv() -> None:
    link = detect_link_material("https://www.bilibili.com/video/BV1abc123456")
    bv = detect_link_material("BV1abc123456")

    assert link.platform == "bilibili"
    assert bv.platform == "bilibili"
    assert bv.normalized_url.endswith("/BV1abc123456")


def test_detect_xiaohongshu_link() -> None:
    detected = detect_link_material("https://www.xiaohongshu.com/explore/example")

    assert detected.platform == "xiaohongshu"
    assert detected.display_name == "小红书"


def test_detect_unsupported_link_has_clear_error() -> None:
    with pytest.raises(LinkMaterialImportError, match="暂不支持"):
        detect_link_material("https://example.com/video")


@pytest.mark.parametrize(
    "source_url",
    [
        "http://www.bilibili.com/video/BV1abc123456",
        "https://evil.example/?next=https://www.bilibili.com/video/BV1abc123456",
        "https://www.bilibili.com.evil.example/video/BV1abc123456",
        "https://www.bilibili.com@127.0.0.1/private",
        "https://mp.weixin.qq.com.evil.example/s/article",
        "https://evil.mp.weixin.qq.com/s/article",
    ],
)
def test_detect_rejects_insecure_or_disguised_platform_urls(source_url: str) -> None:
    with pytest.raises(LinkMaterialImportError):
        detect_link_material(source_url)


def test_fetch_guard_rejects_allowlisted_hostname_resolving_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        link_material_import,
        "_resolve_hostname_addresses",
        lambda _hostname: {"127.0.0.1"},
    )

    with pytest.raises(LinkMaterialImportError, match="私有网络"):
        link_material_import._assert_public_link_target(
            "https://www.bilibili.com/video/BV1abc123456",
            expected_platform="bilibili",
        )


class _FakeRedirectResponse:
    def __init__(self, status_code: int, *, location: str | None = None) -> None:
        self.status_code = status_code
        self.headers = {"location": location} if location is not None else {}
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeRedirectClient:
    def __init__(self, responses: list[_FakeRedirectResponse]) -> None:
        self._responses = iter(responses)
        self.urls: list[str] = []
        self.follow_redirects: list[bool] = []

    def get(self, url: str, *, follow_redirects: bool) -> _FakeRedirectResponse:
        self.urls.append(url)
        self.follow_redirects.append(follow_redirects)
        return next(self._responses)


def test_safe_fetch_validates_each_https_redirect_hop() -> None:
    first = _FakeRedirectResponse(302, location="/s/next")
    final = _FakeRedirectResponse(200)
    client = _FakeRedirectClient([first, final])

    response = link_material_import._safe_get_with_redirects(
        client,
        "https://mp.weixin.qq.com/s/original",
        platform="wechat_article",
    )

    assert response is final
    assert first.closed is True
    assert client.urls == [
        "https://mp.weixin.qq.com/s/original",
        "https://mp.weixin.qq.com/s/next",
    ]
    assert client.follow_redirects == [False, False]


@pytest.mark.parametrize(
    "location",
    [
        "http://mp.weixin.qq.com/s/insecure",
        "https://evil.example/s/off-platform",
    ],
)
def test_safe_fetch_never_requests_insecure_or_off_platform_redirect(location: str) -> None:
    redirect_response = _FakeRedirectResponse(302, location=location)
    client = _FakeRedirectClient([redirect_response])

    with pytest.raises(LinkMaterialImportError):
        link_material_import._safe_get_with_redirects(
            client,
            "https://mp.weixin.qq.com/s/original",
            platform="wechat_article",
        )

    assert client.urls == ["https://mp.weixin.qq.com/s/original"]
    assert redirect_response.closed is True


def test_safe_fetch_rechecks_private_dns_after_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolved_addresses(hostname: str) -> set[str]:
        return {"10.0.0.8"} if hostname == "api.bilibili.com" else {"93.184.216.34"}

    monkeypatch.setattr(link_material_import, "_resolve_hostname_addresses", resolved_addresses)
    client = _FakeRedirectClient(
        [_FakeRedirectResponse(302, location="https://api.bilibili.com/video/redirected")]
    )

    with pytest.raises(LinkMaterialImportError, match="私有网络"):
        link_material_import._safe_get_with_redirects(
            client,
            "https://www.bilibili.com/video/original",
            platform="bilibili",
        )

    assert client.urls == ["https://www.bilibili.com/video/original"]


def test_clean_subtitle_text_removes_timestamps_and_dedupes() -> None:
    cleaned = _clean_subtitle_text(
        """WEBVTT

00:00:00.000 --> 00:00:01.000
大家好
大家好

2
00:00:01.000 --> 00:00:02.000
今天介绍项目
"""
    )

    assert "WEBVTT" not in cleaned
    assert "-->" not in cleaned
    assert cleaned.splitlines() == ["大家好", "今天介绍项目"]


def test_build_clean_video_markdown_only_keeps_title_link_and_body() -> None:
    markdown = build_clean_video_markdown(
        title="测试视频",
        source_url="https://www.bilibili.com/video/BV1abc123456",
        body="这是整理后的正文。\n\n不包含处理日志。",
    )

    assert markdown.startswith("# 测试视频\n\n原链接：https://www.bilibili.com/video/BV1abc123456\n\n")
    assert "下载日志" not in markdown
    assert "```" not in markdown


def test_cleanup_transcript_rejects_ai_summary_that_compresses_too_much() -> None:
    class FakeAi:
        def generate_raw_evidence_response(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            class Response:
                content = "这是压缩后的摘要。"

            return Response()

    transcript = "\n".join(f"第{i}段有效转写内容，包含完整信息、观点和事实。" for i in range(80))

    cleaned = cleanup_transcript_text(
        ai_service=FakeAi(),
        title="测试视频",
        source_url="https://www.bilibili.com/video/BV1abc123456",
        transcript_text=transcript,
    )

    assert "这是压缩后的摘要" not in cleaned
    assert "第79段有效转写内容" in cleaned
    assert len(cleaned) > 1000


def test_cleanup_transcript_keeps_long_transcripts_deterministic() -> None:
    class FailingAi:
        def generate_raw_evidence_response(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("long transcripts should not call AI cleanup")

    transcript = "\n".join(f"第{i}段完整视频转写内容，必须被保留下来。" for i in range(220))

    cleaned = cleanup_transcript_text(
        ai_service=FailingAi(),
        title="长视频",
        source_url="https://www.bilibili.com/video/BV1abc123456",
        transcript_text=transcript,
    )

    assert "第0段完整视频转写内容" in cleaned
    assert "第219段完整视频转写内容" in cleaned
    assert len(cleaned) >= 3000


def test_cleanup_temp_dir_removes_media_cache(tmp_path: Path) -> None:
    temp_dir = tmp_path / "link-run"
    temp_dir.mkdir()
    (temp_dir / "audio.wav").write_text("temporary", encoding="utf-8")

    status = cleanup_temp_dir(temp_dir)

    assert status == "cleaned"
    assert not temp_dir.exists()


def test_bilibili_cookie_mode_adds_browser_cookie_argument(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: list[list[str]] = []

    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_version", lambda _executable: "2026.03.17")
    monkeypatch.setattr("app.services.link_material_import._has_curl_cffi", lambda: True)
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_impersonate_target", lambda _executable: "chrome")

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(list(command))
        if "--cookies-from-browser" not in command:
            class Failed:
                returncode = 1
                stdout = ""
                stderr = "ERROR: HTTP Error 412: Precondition Failed"

            return Failed()
        temp_dir = Path(kwargs["cwd"])
        (temp_dir / "test.info.json").write_text('{"title": "测试视频", "extractor_key": "BiliBili"}', encoding="utf-8")
        (temp_dir / "test.mp4").write_bytes(b"media")
        (temp_dir / "test.zh.vtt").write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n这是一段有效字幕内容，足够生成资料，并且长度超过校验阈值。",
            encoding="utf-8",
        )

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    source = extract_link_material_source(
        "https://www.bilibili.com/video/BV1abc123456",
        tmp_path,
        options=LinkMaterialImportOptions(use_browser_cookies=True, cookie_browser="chrome"),
    )

    assert source.title == "测试视频"
    flattened = [item for command in captured for item in command]
    assert "--cookies-from-browser" in flattened
    assert "chrome" in flattened
    assert "--skip-download" not in flattened
    assert source.metadata["accessMode"] == "browser_cookie"
    assert source.metadata["cookieBrowser"] == "chrome"
    assert source.metadata["pipelineMode"] == "media_first"
    assert source.metadata["mediaDownloaded"] is True
    assert source.metadata["transcriptSource"] == "downloaded_subtitle"
    assert source.metadata["downloadAttemptProfile"] == "bili_cookie"
    assert source.metadata["downloadAttemptCount"] == 4


def test_http_412_is_classified_as_browser_cookie_hint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_version", lambda _executable: "2026.03.17")
    monkeypatch.setattr("app.services.link_material_import._has_curl_cffi", lambda: False)
    monkeypatch.setattr("app.services.link_material_import._find_bbdown", lambda: None)

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        class Completed:
            returncode = 1
            stdout = ""
            stderr = "ERROR: HTTP Error 412: Precondition Failed"

        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(LinkMaterialImportError) as exc_info:
        extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path)

    assert "浏览器登录态" in str(exc_info.value)
    assert exc_info.value.metadata["accessFailureKind"] == "http_412"
    assert exc_info.value.metadata["accessMode"] == "anonymous"
    assert exc_info.value.metadata["downloadAttemptCount"] == 4
    assert exc_info.value.metadata["headersApplied"] is True
    assert exc_info.value.metadata["externalDownloader"] == "BBDown:not_installed"


def test_bilibili_retry_adds_origin_headers_after_412(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_version", lambda _executable: "2026.03.17")
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_impersonate_target", lambda _executable: None)

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(list(command))
        if len(commands) == 1:
            class Failed:
                returncode = 1
                stdout = ""
                stderr = "ERROR: HTTP Error 412: Precondition Failed"

            return Failed()
        temp_dir = Path(kwargs["cwd"])
        (temp_dir / "test.info.json").write_text('{"title": "测试视频"}', encoding="utf-8")
        (temp_dir / "test.mp4").write_bytes(b"media")
        (temp_dir / "test.zh.vtt").write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n第二次带 B 站请求头后成功读取字幕，这段文本足够长。",
            encoding="utf-8",
        )

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    source = extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path)

    second_command = commands[1]
    assert "Origin:https://www.bilibili.com" in second_command
    assert "Referer:https://www.bilibili.com/" in second_command
    assert any(str(item).startswith("User-Agent:") for item in second_command)
    assert source.metadata["downloadAttemptProfile"] == "bili_headers"


def test_bilibili_impersonate_when_curl_cffi_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_version", lambda _executable: "2026.03.17")
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_impersonate_target", lambda _executable: None)
    monkeypatch.setattr("app.services.link_material_import._has_curl_cffi", lambda: True)
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_impersonate_target", lambda _executable: "chrome")

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(list(command))
        if len(commands) < 3:
            class Failed:
                returncode = 1
                stdout = ""
                stderr = "ERROR: HTTP Error 412: Precondition Failed"

            return Failed()
        temp_dir = Path(kwargs["cwd"])
        (temp_dir / "test.info.json").write_text('{"title": "测试视频"}', encoding="utf-8")
        (temp_dir / "test.mp4").write_bytes(b"media")
        (temp_dir / "test.zh.vtt").write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n浏览器模拟后成功读取字幕，这段文本足够长。",
            encoding="utf-8",
        )

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    source = extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path)

    assert "--impersonate" in commands[2]
    assert "chrome" in commands[2]
    assert source.metadata["downloadAttemptProfile"] == "bili_impersonate"
    assert source.metadata["impersonationApplied"] is True


def test_bilibili_uses_bbdown_after_yt_dlp_412(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_version", lambda _executable: "2026.03.17")
    monkeypatch.setattr("app.services.link_material_import._has_curl_cffi", lambda: True)
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_impersonate_target", lambda _executable: "chrome")
    monkeypatch.setattr("app.services.link_material_import._find_bbdown", lambda: "/usr/local/bin/BBDown")

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(list(command))
        temp_dir = Path(kwargs["cwd"])
        if command[0] == "/usr/local/bin/BBDown":
            (temp_dir / "bbdown.mp4").write_bytes(b"media")
            (temp_dir / "bbdown.zh.vtt").write_text(
                "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nBBDown 兜底下载后读取字幕，这段文本足够长。",
                encoding="utf-8",
            )

            class Completed:
                returncode = 0
                stdout = ""
                stderr = ""

            return Completed()

        class Failed:
            returncode = 1
            stdout = ""
            stderr = "ERROR: HTTP Error 412: Precondition Failed"

        return Failed()

    monkeypatch.setattr("subprocess.run", fake_run)

    source = extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path)

    assert any(command[0] == "/usr/local/bin/BBDown" for command in commands)
    assert source.metadata["externalDownloader"] == "BBDown"
    assert source.metadata["downloadAttemptProfile"] == "bbdown"
    assert source.metadata["transcriptSource"] == "downloaded_subtitle"


def test_media_first_without_subtitle_and_engine_has_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])
    monkeypatch.setattr("app.services.link_material_import.find_local_transcript_engine", lambda: None)
    # m4a 非 soundfile 友好格式 → 现在会先用 ffmpeg 转 wav；mock 掉转码，专注验证"无引擎"报错。
    monkeypatch.setattr("app.services.link_material_import.find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        "app.services.link_material_import.extract_audio_from_media",
        lambda media_path, temp_dir, *, ffmpeg: temp_dir / "audio.wav",
    )

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        temp_dir = Path(kwargs["cwd"])
        (temp_dir / "test.info.json").write_text('{"title": "无字幕视频"}', encoding="utf-8")
        (temp_dir / "test.m4a").write_bytes(b"audio")

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(LinkMaterialImportError) as exc_info:
        extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path)

    assert "已下载本地媒体" in str(exc_info.value)
    assert "未检测到本地 SenseVoice / Whisper" in str(exc_info.value)
    assert exc_info.value.metadata["transcriptSource"] == "none"
    assert exc_info.value.metadata["mediaDownloaded"] is True
    assert exc_info.value.metadata["tempMediaKind"] == "audio"


def test_media_first_uses_local_transcription_when_no_subtitles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])

    class Engine:
        name = "local_sensevoice"
        command = ["sensevoice"]
        command_template = None

    monkeypatch.setattr("app.services.link_material_import.find_local_transcript_engine", lambda: Engine())
    monkeypatch.setattr("app.services.link_material_import._transcribe_temp_audio", lambda _engine, _audio_path, _temp_dir: "本地转写后的有效正文")
    # m4a 非 soundfile 友好格式 → 现在会先用 ffmpeg 转 wav；mock 掉转码。
    monkeypatch.setattr("app.services.link_material_import.find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(
        "app.services.link_material_import.extract_audio_from_media",
        lambda media_path, temp_dir, *, ffmpeg: temp_dir / "audio.wav",
    )

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        temp_dir = Path(kwargs["cwd"])
        (temp_dir / "test.info.json").write_text('{"title": "无字幕视频"}', encoding="utf-8")
        (temp_dir / "test.m4a").write_bytes(b"audio")

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    source = extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path)

    assert source.transcript_text == "本地转写后的有效正文"
    assert source.metadata["transcriptSource"] == "local_sensevoice"
    assert source.metadata["downloadedMediaKind"] == "audio"


def test_video_download_without_ffmpeg_has_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])
    monkeypatch.setattr("app.services.link_material_import.find_ffmpeg", lambda: None)

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        temp_dir = Path(kwargs["cwd"])
        (temp_dir / "test.info.json").write_text('{"title": "视频文件"}', encoding="utf-8")
        (temp_dir / "test.mp4").write_bytes(b"video")

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(LinkMaterialImportError) as exc_info:
        extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path)

    assert "ffmpeg" in str(exc_info.value)
    assert exc_info.value.metadata["downloadedMediaKind"] == "video"
    assert exc_info.value.metadata["ffmpegAvailable"] is False


def test_video_download_falls_back_to_audio_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_version", lambda _executable: "2026.03.17")
    monkeypatch.setattr("app.services.link_material_import._get_yt_dlp_impersonate_target", lambda _executable: None)

    def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
        commands.append(list(command))
        temp_dir = Path(kwargs["cwd"])
        if "bv*+ba/best" in command:
            class Failed:
                returncode = 1
                stdout = ""
                stderr = "requested format is not available"

            return Failed()
        (temp_dir / "test.info.json").write_text('{"title": "音频回退"}', encoding="utf-8")
        (temp_dir / "test.m4a").write_bytes(b"audio")
        (temp_dir / "test.zh.vtt").write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n音频回退后读取字幕，这段字幕足够长，可以直接生成资料。",
            encoding="utf-8",
        )

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    source = extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path)

    assert len(commands) == 2
    assert source.metadata["mediaDownloadMode"] == "audio_fallback"
    assert source.metadata["downloadedMediaKind"] == "audio"
    assert source.metadata["transcriptSource"] == "downloaded_subtitle"


def test_local_transcript_engine_prefers_sensevoice_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YIYU_SENSEVOICE_CMD", "sensevoice --input {input} --output {output}")
    monkeypatch.setattr("shutil.which", lambda name: None)

    engine = find_local_transcript_engine()

    assert engine is not None
    assert engine.name == "local_sensevoice"


def test_link_material_context_refresh_event_uses_model_id() -> None:
    main_py = Path(__file__).resolve().parents[1] / "app" / "main.py"
    text = main_py.read_text(encoding="utf-8")

    assert 'refresh_event.get("id")' not in text
    assert "refresh_event.id" in text


def test_link_material_documents_archive_to_online_transcripts_folder() -> None:
    main_py = Path(__file__).resolve().parents[1] / "app" / "main.py"
    text = main_py.read_text(encoding="utf-8")
    start = text.index("def create_client_link_markdown_document(")
    end = text.index("def build_link_material_import_run", start)
    function_text = text[start:end]

    assert 'ONLINE_TRANSCRIPT_FOLDER_LABEL = "线上转写"' in text
    assert '"项目与业务") or next(iter(folders.values()))) / "链接转资料"' not in function_text
    assert "ONLINE_TRANSCRIPT_MATERIAL_LAYER" in function_text
    assert "_force_online_transcript_document_classification" in function_text


def test_online_transcripts_are_in_standard_knowledge_categories() -> None:
    knowledge_base_py = Path(__file__).resolve().parents[1] / "app" / "services" / "knowledge_base.py"
    knowledge_v2_py = Path(__file__).resolve().parents[1] / "app" / "services" / "knowledge_v2.py"

    assert 'ONLINE_TRANSCRIPT_CATEGORY = "线上转写"' in knowledge_base_py.read_text(encoding="utf-8")
    knowledge_v2_text = knowledge_v2_py.read_text(encoding="utf-8")
    assert 'ONLINE_TRANSCRIPT_CATEGORY = "线上转写"' in knowledge_v2_text
    assert "external_media_transcript" in knowledge_v2_text


def test_m4a_audio_is_transcoded_to_wav_but_wav_is_not(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """修复验证: 下载到 m4a 等 soundfile 读不了的音频 → 先 ffmpeg 转 wav;wav 直接用。"""
    monkeypatch.setattr("app.services.link_material_import._find_yt_dlp", lambda: ["yt-dlp"])

    class Engine:
        name = "builtin_sensevoice"
        command = ["sensevoice"]
        command_template = None

    monkeypatch.setattr("app.services.link_material_import.find_local_transcript_engine", lambda: Engine())
    monkeypatch.setattr("app.services.link_material_import.find_ffmpeg", lambda: "ffmpeg")
    transcribed_paths: list[str] = []
    extracted: list[str] = []
    monkeypatch.setattr(
        "app.services.link_material_import._transcribe_temp_audio",
        lambda _engine, audio_path, _temp_dir: transcribed_paths.append(str(audio_path)) or "正文",
    )

    def fake_extract(media_path, temp_dir, *, ffmpeg):  # type: ignore[no-untyped-def]
        extracted.append(str(media_path))
        out = temp_dir / "audio.wav"
        out.write_bytes(b"wav")
        return out

    monkeypatch.setattr("app.services.link_material_import.extract_audio_from_media", fake_extract)

    def make_run(ext: str):
        def fake_run(command, **kwargs):  # type: ignore[no-untyped-def]
            temp_dir = Path(kwargs["cwd"])
            (temp_dir / "test.info.json").write_text('{"title": "X"}', encoding="utf-8")
            (temp_dir / f"test{ext}").write_bytes(b"audio")

            class Completed:
                returncode = 0
                stdout = ""
                stderr = ""

            return Completed()
        return fake_run

    # m4a → 必须经 ffmpeg 转码,转写拿到的是 audio.wav
    monkeypatch.setattr("subprocess.run", make_run(".m4a"))
    extract_link_material_source("https://www.bilibili.com/video/BV1abc123456", tmp_path / "a")
    assert len(extracted) == 1 and extracted[0].endswith(".m4a")
    assert transcribed_paths[-1].endswith("audio.wav")

    # wav → 不转码,直接喂转写
    extracted.clear(); transcribed_paths.clear()
    monkeypatch.setattr("subprocess.run", make_run(".wav"))
    extract_link_material_source("https://www.bilibili.com/video/BV1def654321", tmp_path / "b")
    assert extracted == []
    assert transcribed_paths[-1].endswith(".wav")


def test_xiaohongshu_download_profiles_escalate() -> None:
    """小红书升级重试: base→headers→impersonate;开登录态再加 cookie。"""
    from app.services.link_material_import import (
        _build_download_attempt_profiles,
        LinkMaterialImportOptions,
    )
    anon = _build_download_attempt_profiles(platform="xiaohongshu", options=LinkMaterialImportOptions())
    names = [p.name for p in anon]
    assert names == ["base", "xhs_headers", "xhs_impersonate"], names
    assert anon[1].headers_applied and anon[2].impersonation_requested

    with_cookie = _build_download_attempt_profiles(
        platform="xiaohongshu",
        options=LinkMaterialImportOptions(use_browser_cookies=True),
    )
    assert [p.name for p in with_cookie][-1] == "xhs_cookie"
    assert with_cookie[-1].use_browser_cookies


def test_classify_image_note_as_no_video() -> None:
    """图文笔记(无视频流)被识别为 no_video。"""
    from app.services.link_material_import import _classify_yt_dlp_access_failure
    assert _classify_yt_dlp_access_failure("ERROR: Requested format is not available") == "no_video"
    assert _classify_yt_dlp_access_failure("No video formats found!") == "no_video"


def test_detect_extracts_url_from_share_blurb() -> None:
    """小红书/B站 App 复制的是整段分享文案,要能从中抠出真正的 URL。"""
    xhs = detect_link_material(
        "终于找到这封神演讲！治愈人间所有焦虑！ https://xhslink.com/o/6FKLX5DG6Bl 复制一下，跳转【小红书】即刻浏览笔记。"
    )
    assert xhs.platform == "xiaohongshu"
    assert xhs.normalized_url == "https://xhslink.com/o/6FKLX5DG6Bl"

    # 带 query 参数的完整分享链接也要完整保留(含 xsec_token)
    full = detect_link_material(
        "看看这个 https://www.xiaohongshu.com/discovery/item/abc?type=video&xsec_token=TOKEN123= 即刻浏览"
    )
    assert full.platform == "xiaohongshu"
    assert "xsec_token=TOKEN123=" in full.normalized_url

    # 直接粘干净链接仍然正常
    clean = detect_link_material("https://www.bilibili.com/video/BV1abc123456")
    assert clean.platform == "bilibili"
