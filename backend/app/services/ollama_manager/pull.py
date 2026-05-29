"""Ollama 拉模型 — 调用 /api/pull 流式接口，进度跟踪 + 可取消。

Ollama /api/pull 是 newline-delimited JSON 流：
  {"status":"pulling manifest"}
  {"status":"downloading","digest":"...","total":NNN,"completed":NNN}
  {"status":"verifying sha256 digest"}
  {"status":"writing manifest"}
  {"status":"success"}

设计：
- 单例 PullManager，同时只允许一个 pull
- 后台 daemon 线程跑 POST，前端轮询 status 拿进度
- 可取消（设置标志位，下载线程检测）
"""
from __future__ import annotations

import json
import threading
import time

import httpx

from . import OLLAMA_DEFAULT_BASE_URL, OllamaPullProgress


class OllamaPullManager:
    """单例 - 同时只允许一个 ollama pull 任务。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress = OllamaPullProgress()
        self._cancel_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def status(self) -> OllamaPullProgress:
        with self._lock:
            elapsed = (time.time() - self._progress.started_at) if self._progress.in_progress and self._progress.started_at else self._progress.elapsed_seconds
            return OllamaPullProgress(
                in_progress=self._progress.in_progress,
                model_name=self._progress.model_name,
                status=self._progress.status,
                bytes_downloaded=self._progress.bytes_downloaded,
                bytes_total=self._progress.bytes_total,
                started_at=self._progress.started_at,
                elapsed_seconds=elapsed,
                error=self._progress.error,
                completed=self._progress.completed,
            )

    def start_pull(self, model_name: str, *, base_url: str = OLLAMA_DEFAULT_BASE_URL) -> tuple[bool, str]:
        model_name = (model_name or "").strip()
        if not model_name:
            return False, "缺少模型名"
        with self._lock:
            if self._progress.in_progress:
                return False, f"已有拉取任务在进行中：{self._progress.model_name}"
            self._cancel_flag.clear()
            self._progress = OllamaPullProgress(
                in_progress=True,
                model_name=model_name,
                status="初始化",
                started_at=time.time(),
            )
        self._thread = threading.Thread(
            target=self._pull_loop,
            args=(model_name, base_url),
            name=f"ollama-pull-{model_name}",
            daemon=True,
        )
        self._thread.start()
        return True, f"已开始拉取 {model_name}"

    def cancel(self) -> bool:
        with self._lock:
            if not self._progress.in_progress:
                return False
            self._cancel_flag.set()
            return True

    def _set_error(self, msg: str) -> None:
        with self._lock:
            self._progress.in_progress = False
            self._progress.error = msg
            self._progress.completed = False
            self._progress.elapsed_seconds = (time.time() - self._progress.started_at) if self._progress.started_at else 0.0

    def _set_done(self) -> None:
        with self._lock:
            self._progress.in_progress = False
            self._progress.completed = True
            self._progress.elapsed_seconds = (time.time() - self._progress.started_at) if self._progress.started_at else 0.0

    def _pull_loop(self, model_name: str, base_url: str) -> None:
        url = f"{base_url.rstrip('/')}/api/pull"
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, read=600.0)) as client:
                with client.stream("POST", url, json={"name": model_name, "stream": True}) as resp:
                    if resp.status_code >= 400:
                        body = resp.read().decode("utf-8", "replace")[:300]
                        self._set_error(f"Ollama 拒绝请求（HTTP {resp.status_code}）：{body}")
                        return
                    for line in resp.iter_lines():
                        if self._cancel_flag.is_set():
                            self._set_error("用户已取消")
                            return
                        if not line:
                            continue
                        try:
                            evt = json.loads(line)
                        except Exception:  # noqa: BLE001
                            continue
                        if not isinstance(evt, dict):
                            continue
                        # 字段：status / digest / total / completed / error
                        if evt.get("error"):
                            self._set_error(str(evt["error"])[:400])
                            return
                        with self._lock:
                            status = str(evt.get("status") or "").strip()
                            if status:
                                self._progress.status = status
                            total = int(evt.get("total") or 0)
                            done = int(evt.get("completed") or 0)
                            if total > 0:
                                self._progress.bytes_total = total
                            if done > 0:
                                self._progress.bytes_downloaded = done
                            # 关键里程碑
                            if status == "success":
                                pass  # finish in finally
            self._set_done()
        except httpx.ConnectError:
            self._set_error("无法连接到 Ollama。请先去 ollama.com 下载并启动 Ollama。")
        except Exception as exc:  # noqa: BLE001
            self._set_error(f"内部错误：{exc.__class__.__name__}: {exc}")


_PULL_MANAGER: OllamaPullManager | None = None


def get_pull_manager() -> OllamaPullManager:
    global _PULL_MANAGER
    if _PULL_MANAGER is None:
        _PULL_MANAGER = OllamaPullManager()
    return _PULL_MANAGER


def delete_model(model_name: str, *, base_url: str = OLLAMA_DEFAULT_BASE_URL) -> tuple[bool, str]:
    """删除一个本地 Ollama 模型。"""
    model_name = (model_name or "").strip()
    if not model_name:
        return False, "缺少模型名"
    try:
        resp = httpx.request(
            "DELETE",
            f"{base_url.rstrip('/')}/api/delete",
            json={"name": model_name},
            timeout=10.0,
        )
        if resp.status_code >= 400:
            return False, f"Ollama 返回 HTTP {resp.status_code}：{resp.text[:200]}"
        return True, f"已删除模型 {model_name}"
    except Exception as exc:  # noqa: BLE001
        return False, f"删除失败：{exc.__class__.__name__}: {exc}"
