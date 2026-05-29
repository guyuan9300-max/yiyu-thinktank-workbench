"""本地 ASR 模型下载器：按 ModelSpec 驱动，支持单模型 + 批量串行下载。

下载是后台异步任务，前端通过轮询 /api/v1/local-asr/model/status 拿进度。
也提供 /api/v1/local-asr/diarization/* 给 diarization 双模型用。

下载源：从 ``model_paths._MODEL_REGISTRY`` 里的 ``ModelFileSpec`` 拿
- url_main：官方源（HuggingFace / GitHub releases）
- url_mirror：国内镜像（hf-mirror.com），没镜像就跟 url_main 一致
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .model_paths import (
    DEFAULT_MODEL_NAME,
    ModelSpec,
    get_model_dir,
    get_model_spec,
    is_model_ready,
)


@dataclass
class DownloadProgress:
    """下载状态。单例存在 ModelDownloadManager 里。

    单文件视图（前端旧逻辑用）：
    - ``bytes_downloaded`` / ``bytes_total`` —— 当前 batch 的累计字节
    - ``current_file`` —— 当前正在下的文件名

    批量视图（diarization 多模型用）：
    - ``current_model`` —— 当前正在下哪个 model_name
    - ``pending_models`` —— batch 里还没开始的模型
    - ``completed_models`` —— 已完成的模型列表
    """
    in_progress: bool = False
    bytes_downloaded: int = 0
    bytes_total: int = 0
    current_file: str = ""
    current_model: str = ""
    pending_models: list[str] = field(default_factory=list)
    completed_models: list[str] = field(default_factory=list)
    error_message: str | None = None
    completed: bool = False
    started_at: float = 0.0
    elapsed_seconds: float = 0.0


class ModelDownloadManager:
    """单例：管理本地 ASR 模型下载任务。

    设计要点：
    - 单例 + lock：同时只允许一个 batch 任务跑
    - 进度状态是内存的；重启 backend 后丢失
    - 取消：调 cancel() 设置标志位，下载线程检测后退出
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress = DownloadProgress()
        self._cancel_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def status(self) -> DownloadProgress:
        with self._lock:
            return DownloadProgress(
                in_progress=self._progress.in_progress,
                bytes_downloaded=self._progress.bytes_downloaded,
                bytes_total=self._progress.bytes_total,
                current_file=self._progress.current_file,
                current_model=self._progress.current_model,
                pending_models=list(self._progress.pending_models),
                completed_models=list(self._progress.completed_models),
                error_message=self._progress.error_message,
                completed=self._progress.completed,
                started_at=self._progress.started_at,
                elapsed_seconds=(
                    (time.time() - self._progress.started_at)
                    if self._progress.in_progress else self._progress.elapsed_seconds
                ),
            )

    def start_download(
        self,
        *,
        model_name: str | list[str] = DEFAULT_MODEL_NAME,
        prefer_mirror: bool = True,
    ) -> tuple[bool, str]:
        """启动下载（异步）。返回 (started, message)。

        - ``model_name``：单个 model name 或 list[model name]，list 时顺序下载
        - 已就绪的模型会被跳过
        - 任一未注册的 model name 返回 (False, "...未注册")
        - 正在下载中返回 (False, "...进行中")
        """
        names = [model_name] if isinstance(model_name, str) else list(model_name)
        if not names:
            return False, "未指定要下载的模型"

        specs: list[ModelSpec] = []
        for name in names:
            spec = get_model_spec(name)
            if spec is None:
                return False, f"未注册的模型：{name}"
            specs.append(spec)

        # 跳过已就绪的
        pending = [s for s in specs if not is_model_ready(s.name)]
        already = [s.name for s in specs if is_model_ready(s.name)]
        if not pending:
            return False, f"模型已就绪：{', '.join(already) or names[0]}"

        with self._lock:
            if self._progress.in_progress:
                return False, "已有下载任务在进行中"
            self._cancel_flag.clear()
            self._progress = DownloadProgress(
                in_progress=True,
                started_at=time.time(),
                pending_models=[s.name for s in pending],
                completed_models=list(already),
            )

        self._thread = threading.Thread(
            target=self._run_batch,
            args=(pending, prefer_mirror),
            name=f"asr-model-download-batch-{len(pending)}",
            daemon=True,
        )
        self._thread.start()
        return True, (
            f"已开始下载 {len(pending)} 个模型"
            + (f"（跳过已就绪：{', '.join(already)}）" if already else "")
        )

    def cancel(self) -> bool:
        with self._lock:
            if not self._progress.in_progress:
                return False
            self._cancel_flag.set()
            return True

    # ------------------------------------------------------------------

    def _set_error(self, msg: str) -> None:
        with self._lock:
            self._progress.in_progress = False
            self._progress.error_message = msg
            self._progress.completed = False
            self._progress.elapsed_seconds = (
                time.time() - self._progress.started_at if self._progress.started_at else 0.0
            )

    def _set_done(self) -> None:
        with self._lock:
            self._progress.in_progress = False
            self._progress.completed = True
            self._progress.current_model = ""
            self._progress.current_file = ""
            self._progress.pending_models = []
            self._progress.elapsed_seconds = (
                time.time() - self._progress.started_at if self._progress.started_at else 0.0
            )

    def _run_batch(self, specs: list[ModelSpec], prefer_mirror: bool) -> None:
        try:
            for spec in specs:
                if self._cancel_flag.is_set():
                    self._set_error("用户已取消下载")
                    return
                with self._lock:
                    self._progress.current_model = spec.name
                    if spec.name in self._progress.pending_models:
                        self._progress.pending_models.remove(spec.name)
                ok = self._download_one_model(spec, prefer_mirror)
                if not ok:
                    return  # _set_error 已经被调用
                with self._lock:
                    self._progress.completed_models.append(spec.name)
            self._set_done()
        except Exception as exc:  # noqa: BLE001
            self._set_error(f"内部错误：{exc.__class__.__name__}: {exc}")

    def _download_one_model(self, spec: ModelSpec, prefer_mirror: bool) -> bool:
        """下载一个模型（按 spec.files 顺序）。失败返回 False（且已调 _set_error）。"""
        target_dir = get_model_dir(spec.name)
        target_dir.mkdir(parents=True, exist_ok=True)

        # 探测每个文件：优先 mirror，失败 fallback main
        url_pairs: list[tuple[str, str]] = []  # (file_name, chosen_url)
        sizes: dict[str, int] = {}
        for file_spec in spec.files:
            candidates = (
                [file_spec.url_mirror, file_spec.url_main]
                if prefer_mirror else [file_spec.url_main, file_spec.url_mirror]
            )
            picked: str | None = None
            picked_size = 0
            last_err: str | None = None
            for url in candidates:
                if not url:
                    continue
                try:
                    with httpx.Client(follow_redirects=True, timeout=15.0) as client:
                        resp = client.head(url)
                        if resp.status_code >= 400:
                            raise httpx.HTTPError(f"HEAD {url} -> {resp.status_code}")
                        picked_size = int(resp.headers.get("Content-Length", "0"))
                    picked = url
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = f"{url} 探测失败：{exc}"
                    continue
            if not picked:
                self._set_error(f"模型 {spec.name} 文件 {file_spec.name} 无可用下载源：{last_err}")
                return False
            url_pairs.append((file_spec.name, picked))
            sizes[file_spec.name] = picked_size

        with self._lock:
            self._progress.bytes_total = sum(sizes.values()) or 0
            self._progress.bytes_downloaded = 0

        for file_name, url in url_pairs:
            if self._cancel_flag.is_set():
                self._set_error("用户已取消下载")
                return False
            with self._lock:
                self._progress.current_file = file_name
            target_path = target_dir / file_name
            ok, err = self._download_one_file(url, target_path)
            if not ok:
                self._set_error(f"下载 {spec.name}/{file_name} 失败：{err}")
                return False

        if not is_model_ready(spec.name):
            self._set_error(f"下载完成但模型 {spec.name} 不完整")
            return False
        return True

    def _download_one_file(
        self,
        url: str,
        target_path: Path,
        *,
        chunk_size: int = 1024 * 256,
    ) -> tuple[bool, str | None]:
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
