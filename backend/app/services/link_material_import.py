from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal


LinkMaterialPlatform = Literal["bilibili", "xiaohongshu"]
CookieBrowser = Literal["firefox", "chrome", "edge", "safari"]


class LinkMaterialImportError(Exception):
    """User-facing error raised by the link material import pipeline."""

    def __init__(self, message: str, *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}


@dataclass(frozen=True)
class LinkMaterialDetection:
    platform: LinkMaterialPlatform
    normalized_url: str
    display_name: str


@dataclass
class LinkMaterialSource:
    platform: LinkMaterialPlatform
    source_url: str
    title: str
    transcript_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    downloaded_paths: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class LinkMaterialImportOptions:
    use_browser_cookies: bool = False
    cookie_browser: CookieBrowser = "firefox"
    stage_callback: Callable[[str, float, dict[str, object] | None], None] | None = None


@dataclass(frozen=True)
class _DownloadAttemptProfile:
    name: str
    headers_applied: bool = False
    impersonation_requested: bool = False
    use_browser_cookies: bool = False


@dataclass(frozen=True)
class LocalTranscriptEngine:
    name: Literal["local_sensevoice", "local_whisper"]
    command: list[str]
    command_template: str | None = None


class LinkMaterialPlatformAdapter:
    platform: LinkMaterialPlatform
    display_name: str

    def extract(self, source_url: str, temp_dir: Path, *, options: LinkMaterialImportOptions | None = None) -> LinkMaterialSource:
        raise NotImplementedError


_BILIBILI_URL_RE = re.compile(r"(bilibili\.com|b23\.tv)", re.I)
_BILIBILI_BV_RE = re.compile(r"^BV[0-9A-Za-z]{8,}$", re.I)
_XHS_URL_RE = re.compile(r"(xiaohongshu\.com|xhslink\.com|xhs\.cn)", re.I)
_AUDIO_EXTENSIONS = {".aac", ".aiff", ".alac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav", ".weba", ".wma"}
_VIDEO_EXTENSIONS = {".avi", ".flv", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm", ".wmv"}
_NON_MEDIA_EXTENSIONS = {".ass", ".description", ".info.json", ".json", ".part", ".srt", ".ssa", ".txt", ".vtt"}
_SUPPORTED_COOKIE_BROWSERS = ["firefox", "chrome", "edge", "safari"]
_BILIBILI_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_BILIBILI_HEADER_ARGS = [
    "--add-header",
    "Origin:https://www.bilibili.com",
    "--add-header",
    "Referer:https://www.bilibili.com/",
    "--add-header",
    f"User-Agent:{_BILIBILI_USER_AGENT}",
]


def detect_link_material(value: str) -> LinkMaterialDetection:
    raw = str(value or "").strip()
    if not raw:
        raise LinkMaterialImportError("请先粘贴 B 站或小红书链接。")
    if _BILIBILI_BV_RE.match(raw):
        return LinkMaterialDetection(
            platform="bilibili",
            normalized_url=f"https://www.bilibili.com/video/{raw}",
            display_name="B站",
        )
    if _BILIBILI_URL_RE.search(raw):
        return LinkMaterialDetection(platform="bilibili", normalized_url=raw, display_name="B站")
    if _XHS_URL_RE.search(raw):
        return LinkMaterialDetection(platform="xiaohongshu", normalized_url=raw, display_name="小红书")
    raise LinkMaterialImportError("暂不支持这个链接。当前仅支持 B 站链接、BV 号和小红书链接。")


def adapter_for_platform(platform: LinkMaterialPlatform) -> LinkMaterialPlatformAdapter:
    if platform == "bilibili":
        return BilibiliLinkAdapter()
    if platform == "xiaohongshu":
        return XiaohongshuLinkAdapter()
    raise LinkMaterialImportError("暂不支持这个链接平台。")


def extract_link_material_source(
    source_url: str,
    temp_dir: Path,
    *,
    options: LinkMaterialImportOptions | None = None,
) -> LinkMaterialSource:
    detection = detect_link_material(source_url)
    temp_dir.mkdir(parents=True, exist_ok=True)
    return adapter_for_platform(detection.platform).extract(detection.normalized_url, temp_dir, options=options)


class _YtDlpAdapter(LinkMaterialPlatformAdapter):
    def extract(self, source_url: str, temp_dir: Path, *, options: LinkMaterialImportOptions | None = None) -> LinkMaterialSource:
        options = options or LinkMaterialImportOptions()
        executable = _find_yt_dlp()
        if not executable:
            raise LinkMaterialImportError(
                f"{self.display_name}链接已识别，但当前未安装可用的链接提取器 yt-dlp，无法下载本地媒体。"
            )
        output_template = str(temp_dir / "%(id)s.%(ext)s")
        base_metadata = {
            "accessMode": "browser_cookie" if options.use_browser_cookies else "anonymous",
            "cookieBrowser": options.cookie_browser if options.use_browser_cookies else None,
            "pipelineMode": "media_first",
            "mediaDownloadMode": None,
            "mediaDownloaded": False,
            "downloadedMediaKind": "unknown",
            "tempDirStatus": "created",
            "tempMediaKind": "none",
            "subtitleAvailable": False,
            "transcriptSource": "none",
            "audioExtracted": False,
            "ffmpegAvailable": bool(find_ffmpeg()),
            "keepMedia": False,
            "curlCffiAvailable": _has_curl_cffi(),
            "ytDlpVersion": _get_yt_dlp_version(executable),
            "impersonationTarget": _get_yt_dlp_impersonate_target(executable),
            "impersonationAvailable": bool(_get_yt_dlp_impersonate_target(executable)),
            "supportedCookieBrowsers": _SUPPORTED_COOKIE_BROWSERS,
        }
        _notify_stage(options, "下载临时媒体中", 18.0, base_metadata)
        media_path, media_metadata = download_temp_media(
            executable=executable,
            source_url=source_url,
            temp_dir=temp_dir,
            output_template=output_template,
            options=options,
            base_metadata=base_metadata,
            display_name=self.display_name,
            platform=self.platform,
        )
        metadata = _read_downloaded_info_json(temp_dir)
        title = _clean_title(str(metadata.get("title") or "")) or f"{self.display_name}视频资料"
        source_metadata = {
            **base_metadata,
            **media_metadata,
            "extractor": metadata.get("extractor_key") or metadata.get("extractor"),
            "uploader": metadata.get("uploader") or metadata.get("channel"),
            "duration": metadata.get("duration"),
            "webpageUrl": metadata.get("webpage_url") or source_url,
            "keepMedia": False,
        }
        _notify_stage(options, "检查字幕中", 38.0, source_metadata)
        transcript_text = read_valid_downloaded_subtitles(temp_dir)
        downloaded_paths = [item for item in temp_dir.iterdir() if item.is_file()]
        if transcript_text:
            source_metadata.update({"subtitleAvailable": True, "transcriptSource": "downloaded_subtitle"})
        else:
            source_metadata.update({"subtitleAvailable": False, "transcriptSource": "none"})
            media_kind = str(media_metadata.get("downloadedMediaKind") or _guess_media_kind(media_path))
            if media_kind == "audio":
                audio_path = media_path
                source_metadata.update({"tempMediaKind": "audio", "audioExtracted": False})
            else:
                ffmpeg = find_ffmpeg()
                source_metadata["ffmpegAvailable"] = bool(ffmpeg)
                if not ffmpeg:
                    raise LinkMaterialImportError(
                        "已下载本地视频，但当前未检测到 ffmpeg，无法抽取音频用于转写。",
                        metadata=source_metadata,
                    )
                _notify_stage(options, "抽取音频中", 44.0, source_metadata)
                audio_path = extract_audio_from_media(media_path, temp_dir, ffmpeg=ffmpeg)
                source_metadata.update({"tempMediaKind": "audio", "audioExtracted": True})
            engine = find_local_transcript_engine()
            if engine is None:
                raise LinkMaterialImportError(
                    "已下载本地媒体，但当前未检测到本地 SenseVoice / Whisper 转写引擎。",
                    metadata=source_metadata,
                )
            _notify_stage(options, "本地转写中", 48.0, {**source_metadata, "transcriptSource": engine.name, "transcriptEngine": engine.name})
            transcript_text = _transcribe_temp_audio(engine, audio_path, temp_dir)
            source_metadata.update(
                {
                    "transcriptSource": engine.name,
                    "transcriptEngine": engine.name,
                    "tempMediaKind": "audio",
                }
            )
            downloaded_paths = [item for item in temp_dir.iterdir() if item.is_file()]
        return LinkMaterialSource(
            platform=self.platform,
            source_url=source_url,
            title=title,
            transcript_text=transcript_text,
            metadata=source_metadata,
            downloaded_paths=downloaded_paths,
        )


class BilibiliLinkAdapter(_YtDlpAdapter):
    platform: LinkMaterialPlatform = "bilibili"
    display_name = "B站"


class XiaohongshuLinkAdapter(_YtDlpAdapter):
    platform: LinkMaterialPlatform = "xiaohongshu"
    display_name = "小红书"


def cleanup_transcript_text(*, ai_service: Any | None, title: str, source_url: str, transcript_text: str) -> str:
    cleaned = _strip_low_value_transcript_text(transcript_text)
    if len(cleaned) < 20:
        raise LinkMaterialImportError("转写文本过短，无法生成有效资料。")
    # Long transcripts must stay complete. LLM cleanup is useful for short,
    # messy snippets, but for full videos it can silently summarize or omit
    # sections. Keep long video transcripts deterministic and lossless.
    if len(cleaned) >= 3000:
        return cleaned
    if ai_service is not None and hasattr(ai_service, "generate_raw_evidence_response"):
        system_instruction = (
            "你是资料整理助手。请把视频字幕或转写稿整理成干净、可入库的中文资料正文。"
            "只输出正文，不要写标题、原链接、处理过程、时间戳、下载日志或自我介绍。"
            "必须保留原始转写中的全部有效信息、观点、结构和事实；只去掉口头禅、重复语气词和无意义寒暄。"
            "不要摘要，不要压缩，不要只保留重点，不要改写成短文。"
            "不要编造字幕里没有的内容。"
        )
        prompt = (
            f"视频题目：{title}\n"
            f"原链接：{source_url}\n\n"
            "请整理为一份可被知识库读取的完整正文资料。"
        )
        try:
            structured = ai_service.generate_raw_evidence_response(
                prompt,
                system_instruction,
                cleaned[:60000],
                timeout_seconds=180.0,
                max_tokens=8000,
                enable_thinking=False,
            )
            ai_body = _strip_low_value_transcript_text(str(getattr(structured, "content", "") or ""))
            min_preserved_chars = max(40, int(len(cleaned) * 0.7))
            if len(ai_body) >= min_preserved_chars:
                return ai_body
        except Exception:
            # Fallback to deterministic cleaning. Import should not fail solely
            # because the cleanup LLM is temporarily unavailable.
            pass
    return cleaned


def build_clean_video_markdown(*, title: str, source_url: str, body: str) -> str:
    clean_title = _clean_title(title) or "视频转文字资料"
    clean_body = _strip_low_value_transcript_text(body)
    return f"# {clean_title}\n\n原链接：{source_url}\n\n{clean_body}\n"


def cleanup_temp_dir(temp_dir: Path) -> Literal["cleaned", "failed"]:
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        return "cleaned"
    except Exception:
        return "failed"


def _notify_stage(options: LinkMaterialImportOptions, stage: str, progress: float, metadata: dict[str, object] | None = None) -> None:
    if options.stage_callback is None:
        return
    try:
        options.stage_callback(stage, progress, metadata)
    except Exception:
        # Progress reporting must never make media extraction fail.
        return


def find_local_transcript_engine() -> LocalTranscriptEngine | None:
    sensevoice_template = os.environ.get("YIYU_SENSEVOICE_CMD", "").strip()
    if sensevoice_template:
        return LocalTranscriptEngine(
            name="local_sensevoice",
            command=shlex.split(sensevoice_template),
            command_template=sensevoice_template,
        )
    sensevoice = shutil.which("sensevoice")
    if sensevoice and _command_available([sensevoice, "--help"]):
        return LocalTranscriptEngine(name="local_sensevoice", command=[sensevoice])
    for whisper in _find_all_executables("whisper"):
        if not _command_available([whisper, "--help"]):
            continue
        return LocalTranscriptEngine(name="local_whisper", command=[whisper])
    python = shutil.which("python3") or shutil.which("python")
    if python:
        if _command_available([python, "-m", "whisper", "--help"]):
            return LocalTranscriptEngine(name="local_whisper", command=[python, "-m", "whisper"])
    return None


def _find_all_executables(name: str) -> list[str]:
    seen: set[str] = set()
    matches: list[str] = []
    for raw_dir in os.get_exec_path():
        candidate = Path(raw_dir) / name
        if not candidate.exists() or not os.access(candidate, os.X_OK):
            continue
        resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        matches.append(resolved)
    return matches


def _command_available(command: list[str]) -> bool:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return False
    return completed.returncode == 0


def download_temp_media(
    *,
    executable: list[str],
    source_url: str,
    temp_dir: Path,
    output_template: str,
    options: LinkMaterialImportOptions,
    base_metadata: dict[str, Any],
    display_name: str,
    platform: LinkMaterialPlatform,
) -> tuple[Path, dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    profiles = _build_download_attempt_profiles(platform=platform, options=options)
    last_detail = ""
    last_failure_kind = "unknown"
    last_exit_code: int | None = None
    last_profile = profiles[-1].name if profiles else "default"
    for profile in profiles:
        _remove_media_candidates(temp_dir)
        video_result = _attempt_yt_dlp_media_download(
            executable=executable,
            source_url=source_url,
            temp_dir=temp_dir,
            output_template=output_template,
            options=options,
            profile=profile,
            mode="video_first",
        )
        attempts.append(video_result["attempt"])
        if video_result["media_path"] is not None:
            return video_result["media_path"], _successful_download_metadata(
                base_metadata=base_metadata,
                profile=profile,
                mode="video_first",
                media_path=video_result["media_path"],
                attempts=attempts,
            )
        last_detail = str(video_result["detail"] or "")
        last_failure_kind = str(video_result["failure_kind"] or "unknown")
        last_exit_code = int(video_result["returncode"])
        last_profile = profile.name
        if last_failure_kind in {"http_412", "login_required", "cookie_required"}:
            # Access failures happen before media format negotiation, so retry
            # with stronger request profiles instead of wasting an audio pass.
            continue

        _remove_media_candidates(temp_dir)
        audio_result = _attempt_yt_dlp_media_download(
            executable=executable,
            source_url=source_url,
            temp_dir=temp_dir,
            output_template=output_template,
            options=options,
            profile=profile,
            mode="audio_fallback",
        )
        attempts.append(audio_result["attempt"])
        if audio_result["media_path"] is not None:
            return audio_result["media_path"], _successful_download_metadata(
                base_metadata=base_metadata,
                profile=profile,
                mode="audio_fallback",
                media_path=audio_result["media_path"],
                attempts=attempts,
                downloaded_media_kind="audio",
            )
        last_detail = str(audio_result["detail"] or last_detail or "")
        last_failure_kind = str(audio_result["failure_kind"] or last_failure_kind or "unknown")
        last_exit_code = int(audio_result["returncode"])
        last_profile = profile.name

    if platform == "bilibili" and last_failure_kind in {"http_412", "login_required", "cookie_required"}:
        bbdown_result = _try_bbdown_download(
            source_url=source_url,
            temp_dir=temp_dir,
            base_metadata=base_metadata,
            attempts=attempts,
        )
        attempts.append(bbdown_result["attempt"])
        if bbdown_result["media_path"] is not None:
            media_path = bbdown_result["media_path"]
            media_kind = _guess_media_kind(media_path)
            return media_path, {
                **base_metadata,
                "mediaDownloadMode": "video_first",
                "mediaDownloaded": True,
                "downloadedMediaKind": media_kind,
                "tempMediaKind": media_kind,
                "accessFailureKind": None,
                "externalDownloader": "BBDown",
                "downloadAttemptProfile": "bbdown",
                "downloadAttemptCount": len(attempts),
                "downloadAttempts": attempts[-6:],
                "headersApplied": any(bool(item.get("headersApplied")) for item in attempts),
                "impersonationApplied": any(bool(item.get("impersonationApplied")) for item in attempts),
            }
        last_detail = str(bbdown_result["detail"] or last_detail or "")
        last_exit_code = int(bbdown_result["returncode"])
        last_profile = "bbdown"

    metadata = {
        **base_metadata,
        "mediaDownloadMode": "video_first",
        "mediaDownloaded": False,
        "accessFailureKind": last_failure_kind or "unknown",
        "downloadAttemptProfile": last_profile,
        "downloadAttemptCount": len(attempts),
        "downloadAttempts": attempts[-8:],
        "headersApplied": any(bool(item.get("headersApplied")) for item in attempts),
        "impersonationApplied": any(bool(item.get("impersonationApplied")) for item in attempts),
        "cookieMode": "browser_cookie" if any(item.get("cookieMode") == "browser_cookie" for item in attempts) else "none",
        "ytDlpExitCode": last_exit_code,
        "ytDlpErrorTail": _error_tail(last_detail),
        "externalDownloader": _summarize_external_downloader(attempts),
    }
    if platform == "bilibili" and last_failure_kind in {"http_412", "login_required", "cookie_required"}:
        if not bool(base_metadata.get("impersonationAvailable")):
            reason = "B站返回 HTTP 412。已尝试 Origin/Referer/User-Agent，但当前 yt-dlp 浏览器模拟不可用；可安装/修复 curl-cffi、启用浏览器登录态或安装 BBDown 后重试。"
        elif options.use_browser_cookies:
            reason = "B站仍拒绝访问。已尝试请求头、浏览器模拟和浏览器登录态；可检查浏览器是否已登录，或安装 BBDown 后重试。"
        else:
            reason = "B站返回 HTTP 412。已尝试请求头与浏览器模拟；可启用浏览器登录态，或安装 BBDown 后重试。"
        raise LinkMaterialImportError(reason, metadata=metadata)
    raise LinkMaterialImportError(
        f"临时媒体下载失败：{_error_tail(last_detail, limit=240) or '未知错误'}",
        metadata=metadata,
    )


def _build_download_attempt_profiles(
    *,
    platform: LinkMaterialPlatform,
    options: LinkMaterialImportOptions,
) -> list[_DownloadAttemptProfile]:
    if platform != "bilibili":
        return [
            _DownloadAttemptProfile(
                name="default_cookie" if options.use_browser_cookies else "default",
                use_browser_cookies=options.use_browser_cookies,
            )
        ]
    profiles = [
        _DownloadAttemptProfile(name="base"),
        _DownloadAttemptProfile(name="bili_headers", headers_applied=True),
        _DownloadAttemptProfile(name="bili_impersonate", headers_applied=True, impersonation_requested=True),
    ]
    if options.use_browser_cookies:
        profiles.append(
            _DownloadAttemptProfile(
                name="bili_cookie",
                headers_applied=True,
                impersonation_requested=True,
                use_browser_cookies=True,
            )
        )
    return profiles


def _attempt_yt_dlp_media_download(
    *,
    executable: list[str],
    source_url: str,
    temp_dir: Path,
    output_template: str,
    options: LinkMaterialImportOptions,
    profile: _DownloadAttemptProfile,
    mode: Literal["video_first", "audio_fallback"],
) -> dict[str, Any]:
    impersonation_target = _get_yt_dlp_impersonate_target(executable) if profile.impersonation_requested else None
    format_args = (
        [
            "-f",
            "bv*+ba/best",
            "--merge-output-format",
            "mp4",
        ]
        if mode == "video_first"
        else ["-f", "ba/bestaudio/best"]
    )
    command = _build_yt_dlp_command(
        executable,
        options,
        *format_args,
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "zh.*,en",
        "--sub-format",
        "vtt",
        "--write-info-json",
        "--no-playlist",
        "-o",
        output_template,
        source_url,
        headers_applied=profile.headers_applied,
        impersonation_requested=profile.impersonation_requested,
        impersonation_target=impersonation_target,
        use_browser_cookies=profile.use_browser_cookies,
    )
    completed = _run_yt_dlp_download(command, temp_dir=temp_dir)
    detail = (completed.stderr or completed.stdout or "").strip()
    failure_kind = _classify_yt_dlp_access_failure(detail) if completed.returncode != 0 else None
    media_path = find_downloaded_media_file(temp_dir) if completed.returncode == 0 else None
    if completed.returncode == 0 and media_path is None:
        detail = "yt-dlp returned success but no media file was found"
        failure_kind = "unknown"
    return {
        "media_path": media_path,
        "returncode": completed.returncode,
        "detail": detail,
        "failure_kind": failure_kind,
        "attempt": {
            "profile": profile.name,
            "mode": mode,
            "returncode": completed.returncode,
            "failureKind": failure_kind,
            "errorTail": _error_tail(detail),
            "headersApplied": profile.headers_applied,
            "impersonationApplied": bool(impersonation_target),
            "impersonationTarget": impersonation_target,
            "impersonationRequested": profile.impersonation_requested,
            "cookieMode": "browser_cookie" if profile.use_browser_cookies else "none",
            "cookieBrowser": options.cookie_browser if profile.use_browser_cookies else None,
        },
    }


def _successful_download_metadata(
    *,
    base_metadata: dict[str, Any],
    profile: _DownloadAttemptProfile,
    mode: Literal["video_first", "audio_fallback"],
    media_path: Path,
    attempts: list[dict[str, Any]],
    downloaded_media_kind: str | None = None,
) -> dict[str, Any]:
    media_kind = downloaded_media_kind or _guess_media_kind(media_path)
    return {
        **base_metadata,
        "mediaDownloadMode": mode,
        "mediaDownloaded": True,
        "downloadedMediaKind": media_kind,
        "tempMediaKind": media_kind,
        "accessFailureKind": None,
        "downloadAttemptProfile": profile.name,
        "downloadAttemptCount": len(attempts),
        "downloadAttempts": attempts[-6:],
        "headersApplied": any(bool(item.get("headersApplied")) for item in attempts),
        "impersonationApplied": any(bool(item.get("impersonationApplied")) for item in attempts),
        "cookieMode": "browser_cookie" if any(item.get("cookieMode") == "browser_cookie" for item in attempts) else "none",
        "ytDlpExitCode": 0,
        "ytDlpErrorTail": "",
        "externalDownloader": None,
    }


def _try_bbdown_download(
    *,
    source_url: str,
    temp_dir: Path,
    base_metadata: dict[str, Any],
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    bbdown = _find_bbdown()
    if not bbdown:
        return {
            "media_path": None,
            "returncode": 127,
            "detail": "BBDown is not installed",
            "attempt": {
                "profile": "bbdown",
                "mode": "external_downloader",
                "returncode": 127,
                "failureKind": "not_installed",
                "errorTail": "BBDown is not installed",
                "headersApplied": any(bool(item.get("headersApplied")) for item in attempts),
                "impersonationApplied": any(bool(item.get("impersonationApplied")) for item in attempts),
                "cookieMode": "none",
                "externalDownloader": "BBDown:not_installed",
            },
        }
    _remove_media_candidates(temp_dir)
    command = [bbdown, source_url, "--work-dir", str(temp_dir)]
    completed = _run_external_downloader(command, temp_dir=temp_dir)
    detail = (completed.stderr or completed.stdout or "").strip()
    media_path = find_downloaded_media_file(temp_dir) if completed.returncode == 0 else None
    return {
        "media_path": media_path,
        "returncode": completed.returncode,
        "detail": detail,
        "attempt": {
            "profile": "bbdown",
            "mode": "external_downloader",
            "returncode": completed.returncode,
            "failureKind": None if media_path else "external_downloader_failed",
            "errorTail": _error_tail(detail),
            "headersApplied": any(bool(item.get("headersApplied")) for item in attempts),
            "impersonationApplied": any(bool(item.get("impersonationApplied")) for item in attempts),
            "cookieMode": "none",
            "externalDownloader": "BBDown",
        },
    }


def _run_external_downloader(command: list[str], *, temp_dir: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(temp_dir),
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=f"external downloader timeout: {exc}")


def _summarize_external_downloader(attempts: list[dict[str, Any]]) -> str | None:
    for attempt in reversed(attempts):
        value = attempt.get("externalDownloader")
        if value:
            return str(value)
    return None


def build_link_material_runtime_diagnostics() -> dict[str, Any]:
    executable = _find_yt_dlp()
    impersonation_target = _get_yt_dlp_impersonate_target(executable) if executable else None
    return {
        "ytDlpVersion": _get_yt_dlp_version(executable) if executable else None,
        "curlCffiAvailable": _has_curl_cffi(),
        "impersonationAvailable": bool(impersonation_target),
        "impersonationTarget": impersonation_target,
        "ffmpegAvailable": bool(find_ffmpeg()),
        "supportedCookieBrowsers": _SUPPORTED_COOKIE_BROWSERS,
        "bbdownAvailable": bool(_find_bbdown()),
    }


def _run_yt_dlp_download(command: list[str], *, temp_dir: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(temp_dir),
            capture_output=True,
            text=True,
            timeout=1200,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=f"download timeout: {exc}")


def find_downloaded_media_file(temp_dir: Path) -> Path | None:
    candidates = sorted(
        (item for item in temp_dir.iterdir() if _is_media_candidate(item)),
        key=lambda item: item.stat().st_size,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _remove_media_candidates(temp_dir: Path) -> None:
    for item in list(temp_dir.iterdir()):
        if not _is_media_candidate(item):
            continue
        try:
            item.unlink()
        except Exception:
            pass


def _is_media_candidate(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.stat().st_size <= 0:
        return False
    name = path.name.lower()
    if name.endswith(".info.json"):
        return False
    suffix = path.suffix.lower()
    return suffix not in _NON_MEDIA_EXTENSIONS


def _guess_media_kind(path: Path) -> Literal["audio", "video", "unknown"]:
    suffix = path.suffix.lower()
    if suffix in _AUDIO_EXTENSIONS:
        return "audio"
    if suffix in _VIDEO_EXTENSIONS:
        return "video"
    return "unknown"


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def extract_audio_from_media(media_path: Path, temp_dir: Path, *, ffmpeg: str) -> Path:
    output_path = temp_dir / "audio.wav"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(media_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        cwd=str(temp_dir),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    if completed.returncode != 0 or not output_path.exists() or output_path.stat().st_size <= 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise LinkMaterialImportError(
            f"本地音频抽取失败：{detail[:240] or 'ffmpeg 没有生成可用音频'}",
            metadata={"audioExtracted": False, "ffmpegAvailable": True, "tempMediaKind": "video"},
        )
    return output_path


def _transcribe_temp_audio(engine: LocalTranscriptEngine, audio_path: Path, temp_dir: Path) -> str:
    output_path = temp_dir / "transcript.txt"
    if engine.command_template:
        command = [
            part.format(input=str(audio_path), output=str(output_path))
            for part in shlex.split(engine.command_template)
        ]
    elif engine.name == "local_sensevoice":
        command = [*engine.command, "--input", str(audio_path), "--output", str(output_path)]
    else:
        command = [
            *engine.command,
            str(audio_path),
            "--language",
            "Chinese",
            "--output_format",
            "txt",
            "--output_dir",
            str(temp_dir),
        ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(temp_dir),
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
            env=_transcription_subprocess_env(),
        )
    except FileNotFoundError as exc:
        raise LinkMaterialImportError(
            f"本地转写引擎不可用：{exc}",
            metadata={"transcriptSource": engine.name, "transcriptEngine": engine.name, "tempMediaKind": "audio"},
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise LinkMaterialImportError(
            f"本地转写失败：{detail[:240] or '未知错误'}",
            metadata={"transcriptSource": engine.name, "transcriptEngine": engine.name, "tempMediaKind": "audio"},
        )
    transcript_candidates = [output_path]
    transcript_candidates.extend(sorted(temp_dir.glob("*.txt"), key=lambda item: item.stat().st_mtime, reverse=True))
    for candidate in transcript_candidates:
        if not candidate.exists():
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        cleaned = _strip_low_value_transcript_text(text)
        if len(cleaned) >= 20:
            return cleaned
    raise LinkMaterialImportError(
        "本地转写完成，但没有生成可用正文。",
        metadata={"transcriptSource": engine.name, "transcriptEngine": engine.name, "tempMediaKind": "audio"},
    )


def _transcription_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    try:
        import certifi  # type: ignore

        ca_bundle = certifi.where()
    except Exception:
        ca_bundle = ""
    if ca_bundle:
        env.setdefault("SSL_CERT_FILE", ca_bundle)
        env.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
    return env


def _classify_yt_dlp_access_failure(detail: str) -> str:
    lowered = str(detail or "").lower()
    if "412" in lowered or "precondition failed" in lowered:
        return "http_412"
    if "login" in lowered or "sign in" in lowered or "登录" in lowered:
        return "login_required"
    if "cookie" in lowered:
        return "cookie_required"
    return "unknown"


def _error_tail(detail: str, *, limit: int = 1000) -> str:
    text = re.sub(r"\s+", " ", str(detail or "")).strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _build_yt_dlp_command(
    executable: list[str],
    options: LinkMaterialImportOptions,
    *args: str,
    headers_applied: bool = False,
    impersonation_requested: bool = False,
    impersonation_target: str | None = None,
    use_browser_cookies: bool | None = None,
) -> list[str]:
    command = [*executable]
    if headers_applied:
        command.extend(_BILIBILI_HEADER_ARGS)
    if impersonation_requested and impersonation_target:
        command.extend(["--impersonate", impersonation_target])
    if bool(use_browser_cookies):
        command.extend(["--cookies-from-browser", options.cookie_browser])
    command.extend(args)
    return command


def _has_curl_cffi() -> bool:
    return importlib.util.find_spec("curl_cffi") is not None


def _get_yt_dlp_version(executable: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            [*executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or completed.stderr or "").strip() or None


def _get_yt_dlp_impersonate_target(executable: list[str]) -> str | None:
    if not _has_curl_cffi():
        return None
    try:
        completed = subprocess.run(
            [*executable, "--list-impersonate-targets"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout or completed.stderr or ""
    candidates: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("[") or line.startswith("-") or line.lower().startswith("client"):
            continue
        if "unavailable" in line.lower():
            continue
        first = line.split()[0].strip().lower()
        if first in {"chrome", "edge", "firefox", "safari"} or first.startswith("chrome"):
            candidates.append(first)
    for preferred in ("chrome", "edge", "firefox", "safari"):
        if preferred in candidates:
            return preferred
    return candidates[0] if candidates else None


def _find_bbdown() -> str | None:
    return shutil.which("BBDown") or shutil.which("bbdown")


def _find_yt_dlp() -> list[str] | None:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    python = shutil.which("python3") or shutil.which("python")
    if python:
        try:
            completed = subprocess.run(
                [python, "-m", "yt_dlp", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if completed.returncode == 0:
                return [python, "-m", "yt_dlp"]
        except Exception:
            return None
    return None


def _parse_yt_dlp_json(stdout: str) -> dict[str, Any]:
    for raw_line in reversed(str(stdout or "").splitlines()):
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            continue
    return {}


def _read_downloaded_info_json(temp_dir: Path) -> dict[str, Any]:
    info_paths = sorted(
        temp_dir.glob("*.info.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in info_paths:
        try:
            parsed = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def read_valid_downloaded_subtitles(temp_dir: Path) -> str:
    subtitle_paths = sorted(
        [
            item
            for item in temp_dir.glob("*")
            if item.is_file() and item.suffix.lower() in {".vtt", ".srt", ".ass", ".ssa"}
        ],
        key=lambda item: (
            0 if re.search(r"(zh|cn|hans|chinese)", item.name, re.I) else 1,
            item.name,
        ),
    )
    for path in subtitle_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        cleaned = _clean_subtitle_text(text)
        if len(cleaned) >= 20:
            return cleaned
    return ""


def _read_downloaded_subtitles(temp_dir: Path) -> str:
    return read_valid_downloaded_subtitles(temp_dir)


def _clean_subtitle_text(text: str) -> str:
    lines: list[str] = []
    previous = ""
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        if re.match(r"^\d+$", line):
            continue
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{\\.*?\}", "", line)
        line = re.sub(r"^\[.*?\]\s*", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines).strip()


def _strip_low_value_transcript_text(text: str) -> str:
    text = str(text or "").replace("\r\n", "\n")
    text = re.sub(r"(?im)^原链接：.*$", "", text)
    text = re.sub(r"(?im)^#\s+.*$", "", text)
    text = re.sub(r"(?im)^(以下是|这是|我将|作为).{0,40}$", "", text)
    text = re.sub(r"(?m)^\s*\d{1,2}:\d{2}(?::\d{2})?.*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _clean_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "")).strip()
    cleaned = re.sub(r"[\\/:*?\"<>|]", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned[:80]
