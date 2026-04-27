# backend/app/services/retrieval_model_settings.py

```python
from __future__ import annotations

from datetime import datetime

from app.db import Database, from_json, to_json
from app.models import RetrievalModelSettingsPayload, RetrievalModelSettingsRecord

_SETTINGS_KEY = "settings.retrieval_models"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _default_settings() -> RetrievalModelSettingsRecord:
    return RetrievalModelSettingsRecord(updatedAt=_now_iso())


def _normalize_dimension(value: int | None, fallback: int) -> int:
    if value is None:
        return fallback
    try:
        parsed = int(value)
    except Exception:
        return fallback
    return parsed if parsed > 0 else fallback


def _normalize_settings(record: RetrievalModelSettingsRecord) -> RetrievalModelSettingsRecord:
    dimension = _normalize_dimension(record.embeddingDimension, 256)
    embedding_provider = (record.embeddingProvider or "local_fastembed").strip() or "local_fastembed"
    embedding_model = (record.embeddingModel or "").strip()
    if not embedding_model and embedding_provider == "local_fastembed":
        embedding_model = "BAAI/bge-small-zh-v1.5"
    embedding_mode = record.embeddingMode
    if embedding_provider == "doubao":
        embedding_mode = "doubao"
    elif embedding_provider == "hash_fallback":
        embedding_mode = "hash_fallback"
    elif embedding_mode not in {"local", "doubao", "hash_fallback"}:
        embedding_mode = "local"
    return record.model_copy(
        update={
            "embeddingProvider": embedding_provider,
            "embeddingModel": embedding_model,
            "embeddingDimension": dimension,
            "embeddingMode": embedding_mode,
            "routerProvider": (record.routerProvider or "rules").strip() or "rules",
            "rerankProvider": (record.rerankProvider or "rules").strip() or "rules",
            "updatedAt": record.updatedAt or _now_iso(),
        }
    )


def get_retrieval_model_settings(db: Database) -> RetrievalModelSettingsRecord:
    raw = db.get_setting(_SETTINGS_KEY, "")
    if not raw:
        return _normalize_settings(_default_settings())
    parsed = from_json(raw, {})
    if not isinstance(parsed, dict):
        return _normalize_settings(_default_settings())
    try:
        record = RetrievalModelSettingsRecord(**parsed)
    except Exception:
        return _normalize_settings(_default_settings())
    return _normalize_settings(record)


def save_retrieval_model_settings(
    db: Database,
    payload: RetrievalModelSettingsPayload,
) -> RetrievalModelSettingsRecord:
    current = get_retrieval_model_settings(db)
    patch = payload.model_dump(exclude_none=True)
    next_record = current.model_copy(update={**patch, "updatedAt": _now_iso()})
    normalized = _normalize_settings(next_record)
    db.set_setting(_SETTINGS_KEY, to_json(normalized.model_dump(mode="json")))
    return normalized


def retrieval_embedding_signature(settings: RetrievalModelSettingsRecord) -> str:
    provider = (settings.embeddingProvider or "local_fastembed").strip() or "local_fastembed"
    model = (settings.embeddingModel or "").strip()
    dimension = _normalize_dimension(settings.embeddingDimension, 256)
    return f"{provider}:{model}:{dimension}"


def retrieval_router_signature(settings: RetrievalModelSettingsRecord) -> str:
    provider = (settings.routerProvider or "rules").strip() or "rules"
    model = (settings.routerModel or "").strip()
    enabled = "1" if settings.routerEnabled else "0"
    return f"{provider}:{model}:{enabled}"
```
