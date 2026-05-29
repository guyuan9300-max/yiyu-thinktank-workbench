from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.models import RetrievalModelSettingsRecord

try:
    from fastembed import TextEmbedding

    HAS_FASTEMBED = True
except Exception:  # pragma: no cover
    TextEmbedding = None  # type: ignore[assignment]
    HAS_FASTEMBED = False

try:
    from FlagEmbedding import BGEM3FlagModel
except Exception:  # pragma: no cover
    BGEM3FlagModel = None  # type: ignore[assignment]

DOUBAO_EMBEDDING_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_FASTEMBED_CACHE: dict[str, Any] = {}
_TOKEN_STOP = set("的是了和在对与及并将把里到什么这那")


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff]+", "", lowered)
    return lowered.strip()


def _tokenize(text: str) -> list[str]:
    normalized = text.lower()
    normalized = re.sub(r"[，。；：,.!?！？/\\-]+", " ", normalized)
    normalized = re.sub(r"[的是了和在对与及并将把里到]", " ", normalized)
    raw_tokens = re.findall(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,8}", normalized)
    seen: set[str] = set()
    tokens: list[str] = []
    for token in raw_tokens:
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            candidates = [token]
            if len(token) > 4:
                for size in (4, 3, 2):
                    for index in range(0, len(token) - size + 1):
                        candidates.append(token[index : index + size])
        else:
            candidates = [token]
        for candidate in candidates:
            if re.fullmatch(r"[\u4e00-\u9fff]+", candidate):
                if candidate[0] in _TOKEN_STOP or candidate[-1] in _TOKEN_STOP:
                    continue
            if len(candidate.strip()) < 2:
                continue
            if candidate not in seen:
                seen.add(candidate)
                tokens.append(candidate)
    return tokens


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 1e-9:
        return vector
    return [value / norm for value in vector]


def _project_embedding(values: list[float], *, size: int) -> list[float]:
    if len(values) == size:
        return _normalize_vector([float(value) for value in values])
    projected = [0.0] * size
    if not values:
        return projected
    for index, value in enumerate(values):
        projected[index % size] += float(value)
    return _normalize_vector(projected)


def _hashed_embedding(text: str, *, size: int) -> list[float]:
    counts = Counter(_tokenize(text))
    if not counts:
        normalized = _normalize_text(text)
        fallback_tokens = [normalized[index : index + 2] for index in range(0, max(0, len(normalized) - 1))]
        counts = Counter(token for token in fallback_tokens if token)
    vector = [0.0] * size
    if not counts:
        return vector
    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for offset in range(0, 8, 2):
            index = int.from_bytes(digest[offset : offset + 2], "big") % size
            sign = 1.0 if digest[offset] % 2 == 0 else -1.0
            vector[index] += float(count) * sign
    return _normalize_vector(vector)


@dataclass
class EmbeddingProviderMeta:
    provider: str
    model: str
    dimension: int
    signature: str
    fallbackUsed: bool
    error: str | None = None


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingProviderMeta]:
        ...

    def get_meta(self) -> EmbeddingProviderMeta:
        ...


@dataclass
class ConfiguredFallbackProvider:
    wrapped: EmbeddingProvider
    reason: str

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingProviderMeta]:
        vectors, meta = self.wrapped.embed_texts(texts)
        return vectors, EmbeddingProviderMeta(
            provider=meta.provider,
            model=meta.model,
            dimension=meta.dimension,
            signature=meta.signature,
            fallbackUsed=True,
            error=self.reason,
        )

    def get_meta(self) -> EmbeddingProviderMeta:
        return self.embed_texts([])[1]


@dataclass
class HashFallbackProvider:
    dimension: int = 256

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingProviderMeta]:
        vectors = [_hashed_embedding(text, size=self.dimension) for text in texts]
        meta = EmbeddingProviderMeta(
            provider="hash_fallback",
            model="",
            dimension=self.dimension,
            signature=f"hash_fallback::{self.dimension}",
            fallbackUsed=False,
            error=None,
        )
        return vectors, meta

    def get_meta(self) -> EmbeddingProviderMeta:
        return self.embed_texts([])[1]


@dataclass
class LocalFastEmbedProvider:
    model: str = "BAAI/bge-small-zh-v1.5"
    dimension: int = 256
    projection: bool = True

    def _embedder(self) -> Any | None:
        if not HAS_FASTEMBED or TextEmbedding is None:
            return None
        cache_key = self.model
        existing = _FASTEMBED_CACHE.get(cache_key)
        if existing is not None:
            return existing
        try:
            embedder = TextEmbedding(model_name=self.model, lazy_load=False)
        except Exception:
            return None
        _FASTEMBED_CACHE[cache_key] = embedder
        return embedder

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingProviderMeta]:
        signature_dimension = self.dimension if self.dimension > 0 else 256
        if not texts:
            return [], EmbeddingProviderMeta(
                provider="local_fastembed",
                model=self.model,
                dimension=signature_dimension,
                signature=f"local_fastembed:{self.model}:{signature_dimension}",
                fallbackUsed=False,
                error=None,
            )
        embedder = self._embedder()
        if embedder is None:
            vectors = [_hashed_embedding(text, size=signature_dimension) for text in texts]
            return vectors, EmbeddingProviderMeta(
                provider="hash_fallback",
                model="",
                dimension=signature_dimension,
                signature=f"hash_fallback::{signature_dimension}",
                fallbackUsed=True,
                error="fastembed_unavailable",
            )
        try:
            embeddings = list(embedder.embed(texts, batch_size=min(16, max(1, len(texts)))))
            if self.projection:
                vectors = [_project_embedding([float(value) for value in vector], size=signature_dimension) for vector in embeddings]
                output_dimension = signature_dimension
                output_signature = f"local_fastembed:{self.model}:{signature_dimension}"
            else:
                vectors = [_normalize_vector([float(value) for value in vector]) for vector in embeddings]
                output_dimension = len(vectors[0]) if vectors else signature_dimension
                output_signature = f"local_fastembed_native:{self.model}:{output_dimension}"
            return vectors, EmbeddingProviderMeta(
                provider="local_fastembed",
                model=self.model,
                dimension=output_dimension,
                signature=output_signature,
                fallbackUsed=False,
                error=None,
            )
        except Exception as exc:
            vectors = [_hashed_embedding(text, size=signature_dimension) for text in texts]
            return vectors, EmbeddingProviderMeta(
                provider="hash_fallback",
                model="",
                dimension=signature_dimension,
                signature=f"hash_fallback::{signature_dimension}",
                fallbackUsed=True,
                error=str(exc),
            )

    def get_meta(self) -> EmbeddingProviderMeta:
        return self.embed_texts([])[1]


@dataclass
class LegacyFastEmbed256Provider:
    model: str = "BAAI/bge-small-zh-v1.5"

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingProviderMeta]:
        provider = LocalFastEmbedProvider(model=self.model, dimension=256, projection=True)
        vectors, meta = provider.embed_texts(texts)
        if meta.provider == "local_fastembed":
            meta = EmbeddingProviderMeta(
                provider=meta.provider,
                model=meta.model,
                dimension=256,
                signature=f"local_fastembed:{self.model}:256",
                fallbackUsed=meta.fallbackUsed,
                error=meta.error,
            )
        return vectors, meta

    def get_meta(self) -> EmbeddingProviderMeta:
        return self.embed_texts([])[1]


@dataclass
class FastEmbedNativeProvider:
    model: str = "BAAI/bge-small-zh-v1.5"

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingProviderMeta]:
        provider = LocalFastEmbedProvider(model=self.model, dimension=256, projection=False)
        return provider.embed_texts(texts)

    def get_meta(self) -> EmbeddingProviderMeta:
        return self.embed_texts([])[1]


@dataclass
class BgeM3DenseProvider:
    model: str = "BAAI/bge-m3"
    dimension: int = 1024
    fallback_provider: EmbeddingProvider | None = None
    _model_cache: Any | None = None

    def _resolve_model(self) -> Any | None:
        if BGEM3FlagModel is None:
            return None
        if self._model_cache is not None:
            return self._model_cache
        try:
            self._model_cache = BGEM3FlagModel(self.model, use_fp16=False)
        except Exception:
            self._model_cache = None
        return self._model_cache

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingProviderMeta]:
        if not texts:
            return [], EmbeddingProviderMeta(
                provider="bge_m3_dense",
                model=self.model,
                dimension=self.dimension if self.dimension > 0 else 1024,
                signature=f"bge_m3_dense:{self.model}:{self.dimension if self.dimension > 0 else 1024}",
                fallbackUsed=False,
                error=None,
            )
        model = self._resolve_model()
        if model is None:
            if self.fallback_provider is not None:
                vectors, meta = self.fallback_provider.embed_texts(texts)
                return vectors, EmbeddingProviderMeta(
                    provider=meta.provider,
                    model=meta.model,
                    dimension=meta.dimension,
                    signature=meta.signature,
                    fallbackUsed=True,
                    error="bge_m3_unavailable",
                )
            vectors = [_hashed_embedding(text, size=max(self.dimension, 256)) for text in texts]
            return vectors, EmbeddingProviderMeta(
                provider="hash_fallback",
                model="",
                dimension=max(self.dimension, 256),
                signature=f"hash_fallback::{max(self.dimension, 256)}",
                fallbackUsed=True,
                error="bge_m3_unavailable",
            )
        try:
            encoded = model.encode(texts, batch_size=min(16, max(1, len(texts))), max_length=8192)
            dense = encoded.get("dense_vecs") if isinstance(encoded, dict) else None
            if dense is None:
                raise RuntimeError("bge_m3_dense_missing")
            raw_vectors: list[list[float]] = []
            for item in dense:
                if hasattr(item, "tolist"):
                    raw = item.tolist()
                else:
                    raw = list(item)
                raw_vectors.append([float(value) for value in raw])
            output_vectors = [
                _project_embedding(vector, size=self.dimension)
                if self.dimension > 0 and len(vector) != self.dimension
                else _normalize_vector(vector)
                for vector in raw_vectors
            ]
            output_dimension = len(output_vectors[0]) if output_vectors else self.dimension
            return output_vectors, EmbeddingProviderMeta(
                provider="bge_m3_dense",
                model=self.model,
                dimension=output_dimension,
                signature=f"bge_m3_dense:{self.model}:{output_dimension}",
                fallbackUsed=False,
                error=None,
            )
        except Exception as exc:
            if self.fallback_provider is not None:
                vectors, meta = self.fallback_provider.embed_texts(texts)
                return vectors, EmbeddingProviderMeta(
                    provider=meta.provider,
                    model=meta.model,
                    dimension=meta.dimension,
                    signature=meta.signature,
                    fallbackUsed=True,
                    error=str(exc),
                )
            vectors = [_hashed_embedding(text, size=max(self.dimension, 256)) for text in texts]
            return vectors, EmbeddingProviderMeta(
                provider="hash_fallback",
                model="",
                dimension=max(self.dimension, 256),
                signature=f"hash_fallback::{max(self.dimension, 256)}",
                fallbackUsed=True,
                error=str(exc),
            )

    def get_meta(self) -> EmbeddingProviderMeta:
        return self.embed_texts([])[1]


@dataclass
class DoubaoEmbeddingProvider:
    model: str
    dimension: int
    api_key: str
    fallback_provider: EmbeddingProvider
    base_url: str = DOUBAO_EMBEDDING_BASE_URL
    timeout_seconds: float = 12.0

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingProviderMeta]:
        if not texts:
            return [], EmbeddingProviderMeta(
                provider="doubao",
                model=self.model,
                dimension=self.dimension,
                signature=f"doubao:{self.model}:{self.dimension}",
                fallbackUsed=False,
                error=None,
            )
        try:
            payload = {"model": self.model, "input": texts}
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            embeddings = data.get("data", [])
            vectors: list[list[float]] = []
            for item in embeddings:
                if not isinstance(item, dict):
                    continue
                raw = item.get("embedding")
                if not isinstance(raw, list):
                    continue
                projected = _project_embedding([float(value) for value in raw], size=self.dimension)
                vectors.append(projected)
            if len(vectors) != len(texts):
                raise RuntimeError("doubao_embedding_size_mismatch")
            return vectors, EmbeddingProviderMeta(
                provider="doubao",
                model=self.model,
                dimension=self.dimension,
                signature=f"doubao:{self.model}:{self.dimension}",
                fallbackUsed=False,
                error=None,
            )
        except Exception as exc:
            vectors, fallback_meta = self.fallback_provider.embed_texts(texts)
            return vectors, EmbeddingProviderMeta(
                provider=fallback_meta.provider,
                model=fallback_meta.model,
                dimension=fallback_meta.dimension,
                signature=fallback_meta.signature,
                fallbackUsed=True,
                error=str(exc),
            )

    def get_meta(self) -> EmbeddingProviderMeta:
        return self.embed_texts([])[1]


def get_doubao_api_key(ai_service: Any | None) -> str:
    if ai_service is None:
        return ""
    for provider in ("openai_compatible", "doubao"):
        try:
            store = ai_service._store_for(provider)  # type: ignore[attr-defined]
        except Exception:
            store = None
        if store is None:
            continue
        try:
            api_key = str(store.get_api_key() or "").strip()
        except Exception:
            api_key = ""
        if api_key:
            return api_key
    return ""


def build_embedding_provider(
    settings: RetrievalModelSettingsRecord,
    *,
    ai_service: Any | None = None,
) -> EmbeddingProvider:
    dimension = settings.embeddingDimension if settings.embeddingDimension > 0 else 256
    local_model = (settings.embeddingModel or "").strip() or "BAAI/bge-small-zh-v1.5"
    embedding_profile = (settings.embeddingProfile or "legacy_fastembed_256").strip()
    if embedding_profile == "bge_small_native":
        local_provider: EmbeddingProvider = FastEmbedNativeProvider(model=local_model)
    elif embedding_profile == "bge_m3_dense":
        m3_model = local_model
        if not m3_model or m3_model == "BAAI/bge-small-zh-v1.5":
            m3_model = "BAAI/bge-m3"
        local_provider = BgeM3DenseProvider(
            model=m3_model,
            dimension=dimension,
            fallback_provider=LegacyFastEmbed256Provider(model="BAAI/bge-small-zh-v1.5"),
        )
    else:
        local_provider = LegacyFastEmbed256Provider(model=local_model or "BAAI/bge-small-zh-v1.5")
    hash_provider: EmbeddingProvider = HashFallbackProvider(dimension=dimension)
    provider = (settings.embeddingProvider or "local_fastembed").strip() or "local_fastembed"
    if provider == "hash_fallback":
        return hash_provider
    if provider == "doubao":
        model = (settings.embeddingModel or "").strip()
        if not model:
            return local_provider
        api_key = get_doubao_api_key(ai_service)
        if not api_key:
            return ConfiguredFallbackProvider(wrapped=local_provider, reason="doubao_api_key_missing")
        return DoubaoEmbeddingProvider(
            model=model,
            dimension=dimension,
            api_key=api_key,
            fallback_provider=local_provider if settings.embeddingMode == "local" else hash_provider,
        )
    return local_provider
