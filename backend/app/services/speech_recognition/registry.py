"""Provider 路由 / 注册中心。

新增 provider 时只需：
1. 在 ``backend/app/services/speech_recognition/`` 下新建 provider 类
2. 在 ``_PROVIDERS`` 字典里注册名字

前端 schema 描述符（字段定义、模型选项）写在前端 ``src/shared/speechModelProviders.ts``，
后端只负责"知道 provider 名 → 路由到具体实现"。
"""
from __future__ import annotations

from typing import Iterable

from . import TranscriptionProvider
from .volcano_provider import VolcanoTranscriptionProvider


_PROVIDERS: dict[str, TranscriptionProvider] = {
    "volcano": VolcanoTranscriptionProvider(),
    # I1a 阶段只实现火山；其他 provider 占位，UI 显示但测试连接会返回"暂未支持"。
}


def get_provider(name: str) -> TranscriptionProvider | None:
    """按名字取 provider 实例。未注册的返回 None（caller 应当回退到"暂未支持"提示）。"""
    return _PROVIDERS.get((name or "").strip())


def registered_provider_names() -> Iterable[str]:
    return tuple(_PROVIDERS.keys())
