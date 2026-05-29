"""检测 Ollama 是否在跑 + 列出已安装模型。"""
from __future__ import annotations

import httpx

from . import OLLAMA_DEFAULT_BASE_URL, OllamaHealth, OllamaInstalledModel


def check_health(base_url: str = OLLAMA_DEFAULT_BASE_URL, *, timeout_seconds: float = 3.0) -> OllamaHealth:
    """探测 Ollama 健康状态。

    返回 OllamaHealth，永远不抛异常：
    - running=True/False
    - installed_models: 已安装的本地模型清单
    - error: 失败原因（如果失败）
    """
    url = base_url.rstrip("/")
    try:
        # /api/tags 是 Ollama 已安装模型列表接口，最轻量的健康检测
        resp = httpx.get(f"{url}/api/tags", timeout=timeout_seconds)
        if resp.status_code >= 400:
            return OllamaHealth(
                running=False,
                base_url=base_url,
                error=f"Ollama 返回 HTTP {resp.status_code}",
            )
        data = resp.json() if resp.content else {}
        models_raw = data.get("models", []) if isinstance(data, dict) else []
        installed: list[OllamaInstalledModel] = []
        for entry in models_raw:
            if not isinstance(entry, dict):
                continue
            installed.append(OllamaInstalledModel(
                name=str(entry.get("name") or entry.get("model") or "").strip(),
                size_bytes=int(entry.get("size") or 0),
                digest=str(entry.get("digest") or ""),
                modified_at=str(entry.get("modified_at") or ""),
            ))
        # 尝试拿版本号（可选）
        version = None
        try:
            v_resp = httpx.get(f"{url}/api/version", timeout=timeout_seconds)
            if v_resp.status_code == 200:
                version = str(v_resp.json().get("version") or "").strip() or None
        except Exception:  # noqa: BLE001
            pass
        return OllamaHealth(
            running=True,
            base_url=base_url,
            installed_models=installed,
            version=version,
        )
    except httpx.ConnectError:
        return OllamaHealth(
            running=False,
            base_url=base_url,
            error="无法连接到 Ollama（默认 127.0.0.1:11434）。请先去 ollama.com 下载安装。",
        )
    except httpx.TimeoutException:
        return OllamaHealth(
            running=False,
            base_url=base_url,
            error=f"连接超时（>{timeout_seconds}s）",
        )
    except Exception as exc:  # noqa: BLE001
        return OllamaHealth(
            running=False,
            base_url=base_url,
            error=f"内部错误：{exc.__class__.__name__}: {exc}",
        )
