"""本地 ASR 模型下载器（从 HuggingFace 镜像 / 直链拉取 sherpa-onnx 量化模型）。

下载是后台异步任务，前端通过轮询 /api/v1/local-asr/model/status 拿进度。

下载源：
- 主源：HuggingFace 官方
- 镜像：HF-Mirror (国内可达)
- 通过环境变量 YIYU_ASR_DOWNLOAD_MIRROR 切换

模型清单（SenseVoice 量化版 sherpa-onnx 官方发布）：
- model.int8.onnx (~234MB)
- tokens.txt (~250KB)
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx

from .model_paths import (
    DEFAULT_MODEL_NAME,
    get_model_dir,
    get_model_files,
    is_model_ready,
    total_size_bytes,
)


# sherpa-onnx 官方发布在 HuggingFace 上的 SenseVoice int8 量化版
_HF_BASE = "https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main"
# 国内镜像（hf-mirror.com）
_HF_MIRROR = "https://hf-mirror.com/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main"

_DOWNLOAD_FILES = [
    ("model.int8.onnx", "model"),
    ("tokens.txt", "tokens"),
]


@dataclass
class DownloadProgress:
    """下载状态，单例存在 ModelDownloadManager 里。"""
    in_progress: bool = False
    bytes_downloaded: int = 0
    bytes_total: int = 0
    current_file: str = ""
    error_message: str | None = None
    completed: bool = False
    started_at: float = 0.0
    elapsed_seconds: float = 0.0


class ModelDownloadManager:
    """单例：管理 SenseVoice 模型的下载任务，前端通过轮询接口拿状态。

    设计要点：
    - 单例 + lock：同时只允许一个下载任务跑
    - 进度状态是内存的（重启 backend 后丢；用户可以重新点下载）
    - 取消：调 cancel() 设置标志位，下载线程检测后退出
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress = DownloadProgress()
        self._cancel_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def status(self) -> DownloadProgress:
        with self._lock:
            # 返回 dataclass 副本，避免外部修改
            return DownloadProgress(
                in_progress=self._progress.in_progress,
                bytes_downloaded=self._progress.bytes_downloaded,
                bytes_total=self._progress.bytes_total,
                current_file=self._progress.current_file,
                error_message=self._progress.error_message,
                completed=self._progress.completed,
                started_at=self._progress.started_at,
                elapsed_seconds=(time.time() - self._progress.started_at) if self._progress.in_progress else self._progress.elapsed_seconds,
            )

    def start_download(self, *, model_name: str = DEFAULT_MODEL_NAME, prefer_mirror: bool = True) -> tuple[bool, str]:
        """启动下载（异步）。返回 (started, message)。

        如果模型已存在，返回 (False, "已就绪")。
        如果正在下载，返回 (False, "正在下载中")。
        否则启动后台线程，立即返回 (True, "已开始下载")。
        """
        with self._lock:
            if is_model_ready(model_name):
                return False, "模型已就绪，无需重复下载"
            if self._progress.in_progress:
                return False, "已有下载任务在进行中"
            self._cancel_flag.clear()
            self._progress = DownloadProgress(
                in_progress=True,
                started_at=time.time(),
            )
        self._thread = threading.Thread(
            target=self._download_loop,
            args=(model_name, prefer_mirror),
            name=f"asr-model-download-{model_name}",
            daemon=True,
        )
        self._thread.start()
        return True, "已开始下载"

    def cancel(self) -> bool:
        """请求取消下载。返回是否真的设置了取消标志。"""
        with self._lock:
            if not self._progress.in_progress:
                return False
            self._cancel_flag.set()
            return True

    def _set_error(self, msg: str) -> None:
        with self._lock:
            self._progress.in_progress = False
            self._progress.error_message = msg
            self._progress.completed = False
            self._progress.elapsed_seconds = time.time() - self._progress.started_at if self._progress.started_at else 0.0

    def _set_done(self) -> None:
        with self._lock:
            self._progress.in_progress = False
            self._progress.completed = True
            self._progress.elapsed_seconds = time.time() - self._progress.started_at if self._progress.started_at else 0.0

    def _download_loop(self, model_name: str, prefer_mirror: bool) -> None:
        """实际下载工作，跑在后台线程里。"""
        try:
            target_dir = get_model_dir(model_name)
            target_dir.mkdir(parents=True, exist_ok=True)

            # 先轻量探测每个文件的大小（HEAD 请求）以算总进度
            base_urls = [_HF_MIRROR, _HF_BASE] if prefer_mirror else [_HF_BASE, _HF_MIRROR]
            file_sizes: dict[str, int] = {}
            chosen_base: str | None = None
            last_probe_error: str | None = None
            for base in base_urls:
                try:
                    sizes: dict[str, int] = {}
                    for fname, _ in _DOWNLOAD_FILES:
                        url = f"{base}/{fname}"
                        with httpx.Client(follow_redirects=True, timeout=15.0) as client:
                            resp = client.head(url)
                            if resp.status_code >= 400:
                                raise httpx.HTTPError(f"HEAD {url} -> {resp.status_code}")
                            sizes[fname] = int(resp.headers.get("Content-Length", "0"))
                    chosen_base = base
                    file_sizes = sizes
                    break
                except Exception as exc:  # noqa: BLE001
                    last_probe_error = f"探测 {base} 失败：{exc}"
                    continue
            if chosen_base is None:
                self._set_error(last_probe_error or "无法连接到任何下载源")
                return

            with self._lock:
                self._progress.bytes_total = sum(file_sizes.values()) or 0
                self._progress.bytes_downloaded = 0

            # 逐文件下载
            for fname, _ in _DOWNLOAD_FILES:
                if self._cancel_flag.is_set():
                    self._set_error("用户已取消下载")
                    return
                with self._lock:
                    self._progress.current_file = fname
                url = f"{chosen_base}/{fname}"
                target_path = target_dir / fname
                ok, err = self._download_one(url, target_path)
                if not ok:
                    self._set_error(f"下载 {fname} 失败：{err}")
                    return

            # 完整性 sanity check：必须文件都在
            if not is_model_ready(model_name):
                missing = [str(p) for _, _ in _DOWNLOAD_FILES for p in [get_model_files(model_name)["model"]] if not p.exists()]
                self._set_error(f"下载完成但文件不完整：{missing}")
                return

            self._set_done()
        except Exception as exc:  # noqa: BLE001
            self._set_error(f"内部错误：{exc.__class__.__name__}: {exc}")

    def _download_one(self, url: str, target_path: Path, *, chunk_size: int = 1024 * 256) -> tuple[bool, str | None]:
        """单文件流式下载，支持取消，更新进度。"""
        tmp_path = target_path.with_suffix(target_path.suffix + ".part")
        try:
            with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(30.0, read=120.0)) as client:
                with client.stream("GET", url) as resp:
                    if resp.status_code >= 400:
                        return False, f"HTTP {resp.status_code}"
                    with open(tmp_path, "wb") as fh:
                        for chunk in resp.iter_bytes(chunk_size):
                            if self._cancel_flag.is_set():
                                fh.close()
                                tmp_path.unlink(missing_ok=True)
                                return False, "用户已取消"
                            fh.write(chunk)
                            with self._lock:
                                self._progress.bytes_downloaded += len(chunk)
            tmp_path.replace(target_path)
            return True, None
        except Exception as exc:  # noqa: BLE001
            tmp_path.unlink(missing_ok=True)
            return False, str(exc)


# 全局单例
_DOWNLOAD_MANAGER: ModelDownloadManager | None = None


def get_download_manager() -> ModelDownloadManager:
    global _DOWNLOAD_MANAGER
    if _DOWNLOAD_MANAGER is None:
        _DOWNLOAD_MANAGER = ModelDownloadManager()
    return _DOWNLOAD_MANAGER
