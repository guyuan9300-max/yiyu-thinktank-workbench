"""本地 ASR 模型路径管理 + 模型规范注册中心。

模型统一放在 Application Support / yiyu / runtime / asr-models/<model_name>/
便于跟 backend-venv 等运行时文件统一管理。

每个模型用 ``ModelSpec`` 描述：必填文件清单 + 各文件的主/镜像下载 URL。
下载器从这里读规范，不再硬编码 URL。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# SenseVoice（单说话人 ASR，必装）
DEFAULT_MODEL_NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"

# 说话人切分（Pyannote segmentation）— diarization 必需之一
SPEAKER_SEGMENTATION_MODEL_NAME = "sherpa-onnx-pyannote-segmentation-3-0"

# 说话人 embedding（3D-Speaker eres2net 中文优化）— diarization 必需之二
SPEAKER_EMBEDDING_MODEL_NAME = "3dspeaker-speech-eres2net-base-sv-zh-cn-16k-common"


@dataclass(frozen=True)
class ModelFileSpec:
    """模型里的一个文件：主源 URL + 镜像 URL + 角色（用于 sense_voice 等下游代码引用）。"""
    name: str            # 落地后的文件名（也是相对模型目录的子路径）
    role: str            # 在 get_model_files() 返回 dict 里的 key
    url_main: str        # 官方主源（一般是 HuggingFace 或 GitHub releases）
    url_mirror: str      # 镜像（国内可达，hf-mirror.com 等；没镜像则与 url_main 一致）


@dataclass(frozen=True)
class ModelSpec:
    """模型规范。"""
    name: str
    files: tuple[ModelFileSpec, ...]


# === 模型规范注册中心 =====================================================

_HF_SENSE_VOICE = "https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main"
_HFM_SENSE_VOICE = "https://hf-mirror.com/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main"

_HF_PYANNOTE_SEG = "https://huggingface.co/csukuangfj/sherpa-onnx-pyannote-segmentation-3-0/resolve/main"
_HFM_PYANNOTE_SEG = "https://hf-mirror.com/csukuangfj/sherpa-onnx-pyannote-segmentation-3-0/resolve/main"

# 注意：sherpa-onnx 的 release tag 名有 typo 是 ``speaker-recongition-models``（保留原样）
# 选 base_200k 中文版（37 MB），是 zh-cn 阵营里最小、覆盖一般会议场景够用的；
# 更准更大的还有 ``eres2net_sv_zh-cn_16k-common.onnx`` (210 MB) 或 v2 (68 MB)。
_GH_3DSPK = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
    "3dspeaker_speech_eres2net_base_200k_sv_zh-cn_16k-common.onnx"
)


_MODEL_REGISTRY: dict[str, ModelSpec] = {
    DEFAULT_MODEL_NAME: ModelSpec(
        name=DEFAULT_MODEL_NAME,
        files=(
            ModelFileSpec(
                name="model.int8.onnx",
                role="model",
                url_main=f"{_HF_SENSE_VOICE}/model.int8.onnx",
                url_mirror=f"{_HFM_SENSE_VOICE}/model.int8.onnx",
            ),
            ModelFileSpec(
                name="tokens.txt",
                role="tokens",
                url_main=f"{_HF_SENSE_VOICE}/tokens.txt",
                url_mirror=f"{_HFM_SENSE_VOICE}/tokens.txt",
            ),
        ),
    ),
    SPEAKER_SEGMENTATION_MODEL_NAME: ModelSpec(
        name=SPEAKER_SEGMENTATION_MODEL_NAME,
        files=(
            ModelFileSpec(
                name="model.onnx",
                role="model",
                url_main=f"{_HF_PYANNOTE_SEG}/model.onnx",
                url_mirror=f"{_HFM_PYANNOTE_SEG}/model.onnx",
            ),
        ),
    ),
    SPEAKER_EMBEDDING_MODEL_NAME: ModelSpec(
        name=SPEAKER_EMBEDDING_MODEL_NAME,
        files=(
            ModelFileSpec(
                name="model.onnx",
                role="model",
                url_main=_GH_3DSPK,
                url_mirror=_GH_3DSPK,  # GitHub releases 没单独镜像，复用主源
            ),
        ),
    ),
}


def list_model_names() -> tuple[str, ...]:
    return tuple(_MODEL_REGISTRY.keys())


def get_model_spec(model_name: str) -> ModelSpec | None:
    return _MODEL_REGISTRY.get(model_name)


# === 路径 + 就绪检测 =====================================================


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
    """返回 ``{role: absolute_path}``。未知模型返回空 dict。"""
    spec = _MODEL_REGISTRY.get(model_name)
    if spec is None:
        return {}
    root = get_model_dir(model_name)
    return {f.role: root / f.name for f in spec.files}


def is_model_ready(model_name: str = DEFAULT_MODEL_NAME) -> bool:
    """所有必需文件都在且非空 → 视为就绪。"""
    files = get_model_files(model_name)
    if not files:
        return False
    for path in files.values():
        if not path.exists() or path.stat().st_size <= 0:
            return False
    return True


def is_diarization_ready() -> bool:
    """diarization 需要切分 + embedding 两个模型同时就绪。"""
    return (
        is_model_ready(SPEAKER_SEGMENTATION_MODEL_NAME)
        and is_model_ready(SPEAKER_EMBEDDING_MODEL_NAME)
    )


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
