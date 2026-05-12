"""每个 capability 推荐的 Ollama 模型清单。

前端按 capability 显示对应推荐选项（同时支持用户自填任意模型名）。

选型原则：
- deep_analysis: 14B-32B 中文模型，质量优先
- vision_ocr: 多模态视觉模型（qwen3-vl 系列）
- fast_structured: 3B 以下小模型，速度优先
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecommendedModel:
    name: str          # Ollama 模型名（含 tag）, 如 'qwen2.5:7b'
    size_gb: float     # 约模型大小 GB
    description: str   # UI 上一句话说明
    default: bool = False  # 是否该 capability 的默认推荐


# 注意：size_gb 是约值，实际以 Ollama pull 时 manifest 为准
RECOMMENDED_BY_CAPABILITY: dict[str, list[RecommendedModel]] = {
    "deep_analysis": [
        RecommendedModel("qwen2.5:7b", 4.7, "通用文本对话 + 长文整理，7B 入门档", default=False),
        RecommendedModel("qwen2.5:14b", 9.0, "中文质量明显提升，推荐档", default=True),
        RecommendedModel("qwen2.5:32b", 20.0, "高级档，需 ≥32GB 内存", default=False),
        RecommendedModel("qwen3-vl:32b", 20.0, "视觉 + 文本统一模型（可替代 vision_ocr）", default=False),
        RecommendedModel("deepseek-r1:8b", 5.2, "推理强（链式思考），适合复杂判断", default=False),
    ],
    "vision_ocr": [
        RecommendedModel("qwen3-vl:7b", 5.5, "视觉小模型，OCR + 图理解，入门", default=False),
        RecommendedModel("qwen3-vl:32b", 20.0, "视觉大模型，PDF/PPT 高质量 OCR", default=True),
        RecommendedModel("minicpm-v:8b", 5.5, "经典中文视觉模型", default=False),
        RecommendedModel("llava:13b", 8.0, "多模态通用模型", default=False),
    ],
    "fast_structured": [
        RecommendedModel("qwen2.5:1.5b", 1.0, "极速档，0.5 秒以内 JSON 抽取", default=False),
        RecommendedModel("qwen2.5:3b", 2.0, "标准档，2-3 秒结构化结果", default=True),
        RecommendedModel("llama3.2:3b", 2.0, "Meta 出品，英文场景更稳", default=False),
        RecommendedModel("gemma2:2b", 1.6, "Google 出品，轻量备选", default=False),
    ],
    # online_primary 是云端 LLM 配置（豆包等），不在 Ollama 范围
}


def get_recommended(capability: str) -> list[RecommendedModel]:
    return RECOMMENDED_BY_CAPABILITY.get(capability, [])
