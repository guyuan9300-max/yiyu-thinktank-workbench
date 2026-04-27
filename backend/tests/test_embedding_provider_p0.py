from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models import RetrievalModelSettingsRecord
from app.services.embedding_provider import build_embedding_provider


def test_local_fastembed_provider_or_hash_fallback_is_safe():
    settings = RetrievalModelSettingsRecord(
        embeddingProvider="local_fastembed",
        embeddingModel="BAAI/bge-small-zh-v1.5",
        embeddingDimension=256,
        embeddingMode="local",
        routerEnabled=False,
        routerProvider="rules",
        routerModel="",
        rerankEnabled=False,
        rerankProvider="rules",
        shadowMode=True,
        updatedAt="",
    )
    provider = build_embedding_provider(settings, ai_service=None)
    vectors, meta = provider.embed_texts(["你好，向量检索", "P0 fallback check"])
    assert len(vectors) == 2
    assert meta.dimension == 256
    assert meta.provider in {"local_fastembed", "hash_fallback"}


def test_doubao_provider_without_key_falls_back_safely():
    settings = RetrievalModelSettingsRecord(
        embeddingProvider="doubao",
        embeddingModel="doubao-embedding-large",
        embeddingDimension=1024,
        embeddingMode="doubao",
        routerEnabled=False,
        routerProvider="rules",
        routerModel="",
        rerankEnabled=False,
        rerankProvider="rules",
        shadowMode=True,
        updatedAt="",
    )
    provider = build_embedding_provider(settings, ai_service=None)
    vectors, meta = provider.embed_texts(["没有 key 时也不能崩溃"])
    assert len(vectors) == 1
    assert meta.provider in {"local_fastembed", "hash_fallback"}
    assert meta.fallbackUsed is True
    assert "doubao_api_key_missing" in str(meta.error or "")
