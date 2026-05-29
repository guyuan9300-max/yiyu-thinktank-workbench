"""对象存储 Provider 路由 / 注册中心。"""
from __future__ import annotations

from typing import Iterable

from . import ObjectStorageProvider
from .volcano_tos_provider import VolcanoTosObjectStorageProvider


_PROVIDERS: dict[str, ObjectStorageProvider] = {
    "volcano_tos": VolcanoTosObjectStorageProvider(),
    # I1b-1 阶段只实现火山 TOS；其他 provider（阿里 OSS / AWS S3）占位。
}


def get_provider(name: str) -> ObjectStorageProvider | None:
    return _PROVIDERS.get((name or "").strip())


def registered_provider_names() -> Iterable[str]:
    return tuple(_PROVIDERS.keys())
