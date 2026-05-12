"""本地 ASR 模型路径管理。

模型放在 Application Support / yiyu / runtime / asr-models/<model_name>/
便于跟 backend-venv 等运行时文件统一管理。
"""
from __future__ import annotations

import os
from pathlib import Path


# 当前唯一支持的本地模型（SenseVoice 量化版，sherpa-onnx 官方发布）
DEFAULT_MODEL_NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"


def get_model_root_dir() -> Path:
    """模型根目录。优先用环境变量，否则用 Application Support 默认路径。"""
    env_override = os.environ.get("YIYU_ASR_MODEL_DIR", "").strip()
    if env_override:
        return Path(env_override)
    # macOS 默认：~/Library/Application Support/YiyuThinkTankWorkbench2/runtime/asr-models
    base = Path.home() / "Library" / "Application Support" / "YiyuThinkTankWorkbench2"
    if not base.exists():
        # 非 macOS 或路径不存在时 fallback 到 ~/.yiyu/asr-models
        base = Path.home() / ".yiyu"
    return base / "runtime" / "asr-models"


def get_model_dir(model_name: str = DEFAULT_MODEL_NAME) -> Path:
    return get_model_root_dir() / model_name


def get_model_files(model_name: str = DEFAULT_MODEL_NAME) -> dict[str, Path]:
    """SenseVoice (sherpa-onnx int8 量化版) 必须的文件清单。"""
    root = get_model_dir(model_name)
    return {
        "model": root / "model.int8.onnx",
        "tokens": root / "tokens.txt",
    }


def is_model_ready(model_name: str = DEFAULT_MODEL_NAME) -> bool:
    """所有必需文件都在 + 模型 onnx 非空 → 视为就绪。"""
    files = get_model_files(model_name)
    for path in files.values():
        if not path.exists() or path.stat().st_size <= 0:
            return False
    return True


def total_size_bytes(model_name: str = DEFAULT_MODEL_NAME) -> int:
    """统计模型目录总大小（已存在的文件）。"""
    root = get_model_dir(model_name)
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total
