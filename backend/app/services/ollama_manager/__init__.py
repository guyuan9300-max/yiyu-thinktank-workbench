"""Ollama 管理服务 — 检测 Ollama 安装 + 拉模型 + 进度跟踪 + 删模型。

为什么用 Ollama：
- 它是 llama.cpp 的成熟封装，处理了模型量化、断点续传、版本管理等
- 与我们 backend 通过 OpenAI 兼容协议对接 (POST /v1/chat/completions)
- 用户安装一次（Mac 一键 .pkg），之后所有本地 LLM 都共享一个进程
- 跟我们 ASR (SenseVoice) 那种 onnxruntime 直推不一样 —— LLM 太大不适合自己嵌

设计：
- 默认 Ollama 在 http://127.0.0.1:11434
- 通过 HTTP API 调用，不 import Python SDK
- 拉模型用 /api/pull 流式 API，单例 PullManager 管理进度
- 推荐模型清单按 capability 在 recommended.py 里定义
"""
from __future__ import annotations

from dataclasses import dataclass, field


OLLAMA_DEFAULT_BASE_URL = "http://127.0.0.1:11434"


@dataclass
class OllamaInstalledModel:
    name: str
    size_bytes: int
    digest: str = ""
    modified_at: str = ""


@dataclass
class OllamaHealth:
    running: bool
    base_url: str
    installed_models: list[OllamaInstalledModel] = field(default_factory=list)
    error: str | None = None
    version: str | None = None


@dataclass
class OllamaPullProgress:
    in_progress: bool = False
    model_name: str = ""
    status: str = ""
    bytes_downloaded: int = 0
    bytes_total: int = 0
    started_at: float = 0.0
    elapsed_seconds: float = 0.0
    error: str | None = None
    completed: bool = False
