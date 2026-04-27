# backend/app/services/knowledge_base.py:1030-1715

```python
        hasher.update(fallback_text.encode("utf-8"))
    return hasher.hexdigest()


def compute_normalized_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def generate_doc_uid(client_id: str, original_path: str, binary_hash: str) -> str:
    digest = hashlib.sha1(f"{client_id}:{original_path}:{binary_hash}".encode("utf-8")).hexdigest()
    return f"dock_{digest[:12]}"


def safe_filename(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", name).strip("_") or "document"


def human_workspace_root(data_dir: Path, client_id: str) -> Path:
    return data_dir / "client_workspace" / client_id


def vector_store_root(data_dir: Path, client_id: str) -> Path:
    return data_dir / "vector_store" / client_id


def qdrant_store_root(data_dir: Path) -> Path:
    return data_dir / "vector_store" / "_qdrant"


def collection_name(prefix: str, client_id: str, embedding_signature: str | None = None) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", client_id)
    if not embedding_signature:
        return f"{prefix}_{normalized}"
    suffix = hashlib.sha1(embedding_signature.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{normalized}_{suffix}"


def legacy_collection_name(prefix: str, client_id: str) -> str:
    return collection_name(prefix, client_id, embedding_signature=None)


def active_collection_name(prefix: str, client_id: str, embedding_signature: str) -> str:
    return collection_name(prefix, client_id, embedding_signature=embedding_signature)


def qdrant_client_for(data_dir: Path) -> Any | None:
    if not HAS_QDRANT or QdrantClient is None:
        return None
    root = qdrant_store_root(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    key = str(root)
    existing = _QDRANT_CLIENTS.get(key)
    if existing is not None:
        return existing
    try:
        client = QdrantClient(path=key)
    except Exception as exc:
        logger.warning("Embedded Qdrant unavailable for %s: %s", key, exc)
        return None
    _QDRANT_CLIENTS[key] = client
    return client


def qdrant_point_id(namespace: str, raw_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"yiyu:{namespace}:{raw_id}"))


def hashed_embedding(text: str, *, size: int = QDRANT_VECTOR_SIZE) -> list[float]:
    counts = Counter(tokenize(text))
    if not counts:
        normalized = normalize_text(text)
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
    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 1e-9:
        return vector
    return [value / norm for value in vector]


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 1e-9:
        return vector
    return [value / norm for value in vector]


def project_embedding(values: list[float], *, size: int = QDRANT_VECTOR_SIZE) -> list[float]:
    if len(values) == size:
        return _normalize_vector([float(value) for value in values])
    projected = [0.0] * size
    if not values:
        return projected
    for index, value in enumerate(values):
        projected[index % size] += float(value)
    return _normalize_vector(projected)


def embedding_cache_root(data_dir: Path) -> Path:
    root = qdrant_store_root(data_dir) / "_models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _set_embedding_state(data_dir: Path, *, mode: str, model: str | None, error: str | None = None) -> None:
    _EMBEDDING_STATE[str(data_dir)] = {"mode": mode, "model": model, "error": error}


def embedding_backend_status(data_dir: Path) -> dict[str, Any]:
    state = _EMBEDDING_STATE.get(str(data_dir))
    if state:
        return dict(state)
    if _EMBEDDING_MODE_SETTING == "hash":
        return {"mode": "hash_fallback", "model": None, "error": None}
    if HAS_FASTEMBED:
        return {"mode": "fastembed_available", "model": _FASTEMBED_MODEL_NAME, "error": None}
    return {"mode": "hash_fallback", "model": None, "error": "fastembed_not_installed"}


def current_embedding_signature(
    data_dir: Path,
    *,
    db: Database | None = None,
    ensure_ready: bool = False,
    ai_service: Any | None = None,
) -> str:
    if db is not None:
        settings = get_retrieval_model_settings(db)
        if ensure_ready:
            embed_texts(["知识底座"], data_dir=data_dir, db=db, ai_service=ai_service)
        return retrieval_embedding_signature(settings)
    if ensure_ready:
        embed_texts(["知识底座"], data_dir=data_dir)
    status = embedding_backend_status(data_dir)
    mode = str(status.get("mode") or "hash_fallback")
    model = str(status.get("model") or "")
    return f"{mode}:{model}:qdrant{QDRANT_VECTOR_SIZE}"


def embedding_backend_for(data_dir: Path) -> Any | None:
    if _EMBEDDING_MODE_SETTING == "hash":
        _set_embedding_state(data_dir, mode="hash_fallback", model=None)
        return None
    if not HAS_FASTEMBED or TextEmbedding is None:
        _set_embedding_state(data_dir, mode="hash_fallback", model=None, error="fastembed_not_installed")
        return None
    key = str(data_dir)
    existing = _EMBEDDERS.get(key)
    if existing is not None:
        return existing
    try:
        embedder = TextEmbedding(
            model_name=_FASTEMBED_MODEL_NAME,
            cache_dir=str(embedding_cache_root(data_dir)),
            lazy_load=False,
        )
        _EMBEDDERS[key] = embedder
        _set_embedding_state(data_dir, mode="fastembed", model=_FASTEMBED_MODEL_NAME)
        return embedder
    except Exception as exc:  # pragma: no cover - depends on runtime env/downloads
        _set_embedding_state(data_dir, mode="hash_fallback", model=None, error=str(exc))
        return None


def embed_texts(
    texts: list[str],
    *,
    data_dir: Path,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> tuple[list[list[float]], str]:
    if not texts:
        return [], "hash_fallback"
    if db is not None:
        settings = get_retrieval_model_settings(db)
        provider = build_embedding_provider(settings, ai_service=ai_service)
        vectors, meta = provider.embed_texts(texts)
        _set_embedding_state(
            data_dir,
            mode=meta.provider,
            model=meta.model if meta.model else None,
            error=meta.error,
        )
        return vectors, meta.provider
    embedder = embedding_backend_for(data_dir)
    if embedder is None:
        return [hashed_embedding(text) for text in texts], "hash_fallback"
    try:
        embeddings = list(embedder.embed(texts, batch_size=min(_FASTEMBED_BATCH_SIZE, max(1, len(texts)))))
        projected = [project_embedding([float(value) for value in vector]) for vector in embeddings]
        _set_embedding_state(data_dir, mode="fastembed", model=_FASTEMBED_MODEL_NAME)
        return projected, "fastembed"
    except Exception as exc:  # pragma: no cover - runtime fallback
        _set_embedding_state(data_dir, mode="hash_fallback", model=None, error=str(exc))
        return [hashed_embedding(text) for text in texts], "hash_fallback"


def ensure_qdrant_collection(client: Any, name: str, *, vector_size: int = QDRANT_VECTOR_SIZE) -> None:
    existing = {item.name for item in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def ensure_qdrant_collections(
    data_dir: Path,
    client_id: str,
    *,
    embedding_signature: str | None = None,
    vector_size: int = QDRANT_VECTOR_SIZE,
) -> Any | None:
    client = qdrant_client_for(data_dir)
    if client is None:
        return None
    ensure_qdrant_collection(
        client,
        collection_name("master_index", client_id, embedding_signature=embedding_signature),
        vector_size=vector_size,
    )
    ensure_qdrant_collection(
        client,
        collection_name("raw_chunk", client_id, embedding_signature=embedding_signature),
        vector_size=vector_size,
    )
    return client


def qdrant_payload_count(client: Any, name: str) -> int:
    try:
        count_response = client.count(collection_name=name, exact=True)
        return int(count_response.count)
    except Exception:
        return 0


def _resolve_vector_runtime(
    db: Database | None,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> tuple[str | None, int]:
    if db is None:
        return None, QDRANT_VECTOR_SIZE
    settings = get_retrieval_model_settings(db)
    signature = retrieval_embedding_signature(settings)
    dimension = int(settings.embeddingDimension or QDRANT_VECTOR_SIZE)
    if dimension <= 0:
        dimension = QDRANT_VECTOR_SIZE
    _ = ai_service
    return signature, dimension


def resolve_vector_collection_names(
    db: Database | None,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> dict[str, str]:
    signature, _dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    return {
        "masterActive": collection_name("master_index", client_id, embedding_signature=signature),
        "chunkActive": collection_name("raw_chunk", client_id, embedding_signature=signature),
        "masterLegacy": legacy_collection_name("master_index", client_id),
        "chunkLegacy": legacy_collection_name("raw_chunk", client_id),
        "signature": signature or "",
    }


def _pick_collection_with_fallback(
    client: Any,
    *,
    active_name: str,
    legacy_name: str,
) -> str:
    active_count = qdrant_payload_count(client, active_name)
    if active_count > 0:
        return active_name
    legacy_count = qdrant_payload_count(client, legacy_name)
    if legacy_count > 0:
        return legacy_name
    return active_name


def qdrant_ready(
    data_dir: Path,
    client_id: str,
    *,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> bool:
    client = qdrant_client_for(data_dir)
    if client is None:
        return False
    try:
        signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
        ensure_qdrant_collections(
            data_dir,
            client_id,
            embedding_signature=signature,
            vector_size=dimension,
        )
        return True
    except Exception:
        return False


def upsert_master_index_vector(
    *,
    data_dir: Path,
    client_id: str,
    entry_id: str,
    title: str,
    searchable_text: str,
    source_path: str | None,
    surrogate_md_path: str,
    folder_category: str,
    document_role: str,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> None:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None or PointStruct is None:
        return
    vector, _ = embed_texts([searchable_text], data_dir=data_dir, db=db, ai_service=ai_service)
    payload = {
        "entry_id": entry_id,
        "client_id": client_id,
        "title": title,
        "source_path": source_path,
        "surrogate_md_path": surrogate_md_path,
        "folder_category": folder_category,
        "document_role": document_role,
    }
    client.upsert(
        collection_name=collection_name("master_index", client_id, embedding_signature=signature),
        points=[
            PointStruct(
                id=qdrant_point_id("master", entry_id),
                vector=vector[0] if vector else hashed_embedding(searchable_text, size=dimension),
                payload=payload,
            )
        ],
    )


def upsert_chunk_vectors(
    *,
    db: Database,
    data_dir: Path,
    client_id: str,
    knowledge_document_id: str,
    ai_service: Any | None = None,
) -> None:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None or PointStruct is None:
        return
    rows = db.fetchall(
        """
        SELECT c.id, c.section_label, c.content, kd.doc_uid, kd.current_human_path, dc.title
        FROM document_chunks c
        JOIN knowledge_documents kd ON kd.id = c.knowledge_document_id
        JOIN document_cards dc ON dc.knowledge_document_id = kd.id
        WHERE c.knowledge_document_id = ?
        ORDER BY c.chunk_index ASC
        """,
        (knowledge_document_id,),
    )
    if not rows:
        return
    texts = [f"{row['section_label'] or '概览'}\n{row['content']}" for row in rows]
    vectors, _ = embed_texts(texts, data_dir=data_dir, db=db, ai_service=ai_service)
    points = []
    for index, row in enumerate(rows):
        text = texts[index]
        points.append(
            PointStruct(
                id=qdrant_point_id("chunk", str(row["id"])),
                vector=vectors[index] if index < len(vectors) else hashed_embedding(text, size=dimension),
                payload={
                    "chunk_id": str(row["id"]),
                    "knowledge_document_id": knowledge_document_id,
                    "doc_uid": str(row["doc_uid"]),
                    "title": str(row["title"]),
                    "section_label": str(row["section_label"]) if row["section_label"] else None,
                    "source_path": str(row["current_human_path"]) if row["current_human_path"] else None,
                },
            )
        )
    client.upsert(
        collection_name=collection_name("raw_chunk", client_id, embedding_signature=signature),
        points=points,
    )


def sync_qdrant_for_client(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> None:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None:
        return
    current_signature = current_embedding_signature(data_dir, db=db, ensure_ready=True, ai_service=ai_service)
    signature_key = f"knowledge.embedding_signature:{client_id}"
    stored_signature = db.get_setting(signature_key, "")
    master_name = collection_name("master_index", client_id, embedding_signature=signature)
    chunk_name = collection_name("raw_chunk", client_id, embedding_signature=signature)
    master_count = int(
        db.scalar("SELECT COUNT(1) AS count FROM knowledge_master_index WHERE client_id = ?", (client_id,))
    )
    chunk_count = int(
        db.scalar(
            """
            SELECT COUNT(1) AS count
            FROM document_chunks c
            JOIN knowledge_documents kd ON kd.id = c.knowledge_document_id
            WHERE kd.client_id = ?
            """,
            (client_id,),
        )
    )
    signature_changed = stored_signature != current_signature
    needs_master_sync = signature_changed or qdrant_payload_count(client, master_name) < master_count
    needs_chunk_sync = signature_changed or qdrant_payload_count(client, chunk_name) < chunk_count
    if not needs_master_sync and not needs_chunk_sync:
        return
    master_rows = db.fetchall(
        """
        SELECT id, title, folder_category, document_role, retrieval_summary, searchable_text, source_path, surrogate_md_path
        FROM knowledge_master_index
        WHERE client_id = ?
        """,
        (client_id,),
    )
    if needs_master_sync and PointStruct is not None:
        texts = [str(row["searchable_text"]) for row in master_rows]
        vectors, _ = embed_texts(texts, data_dir=data_dir, db=db, ai_service=ai_service)
        points = [
            PointStruct(
                id=qdrant_point_id("master", str(row["id"])),
                vector=vectors[index] if index < len(vectors) else hashed_embedding(str(row["searchable_text"]), size=dimension),
                payload={
                    "entry_id": str(row["id"]),
                    "client_id": client_id,
                    "title": str(row["title"]),
                    "source_path": str(row["source_path"]) if row["source_path"] else None,
                    "surrogate_md_path": str(row["surrogate_md_path"]),
                    "folder_category": str(row["folder_category"]),
                    "document_role": str(row["document_role"]),
                },
            )
            for index, row in enumerate(master_rows)
        ]
        if points:
            client.upsert(collection_name=master_name, points=points)
    if needs_chunk_sync:
        document_rows = db.fetchall("SELECT id FROM knowledge_documents WHERE client_id = ?", (client_id,))
        for row in document_rows:
            upsert_chunk_vectors(
                db=db,
                data_dir=data_dir,
                client_id=client_id,
                knowledge_document_id=str(row["id"]),
                ai_service=ai_service,
            )
    if needs_master_sync or needs_chunk_sync:
        db.set_setting(signature_key, current_signature)


def search_master_index_qdrant(
    data_dir: Path,
    client_id: str,
    prompt: str,
    limit: int = 8,
    *,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> dict[str, float]:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None:
        return {}
    vectors, _ = embed_texts([prompt], data_dir=data_dir, db=db, ai_service=ai_service)
    active_name = collection_name("master_index", client_id, embedding_signature=signature)
    legacy_name = legacy_collection_name("master_index", client_id)
    target_collection = _pick_collection_with_fallback(client, active_name=active_name, legacy_name=legacy_name)
    try:
        results = client.search(
            collection_name=target_collection,
            query_vector=vectors[0] if vectors else hashed_embedding(prompt, size=dimension),
            limit=limit,
            with_payload=True,
        )
    except Exception:
        return {}
    scores: dict[str, float] = {}
    for item in results:
        payload = getattr(item, "payload", {}) or {}
        entry_id = str(payload.get("entry_id", ""))
        if entry_id:
            scores[entry_id] = float(getattr(item, "score", 0.0))
    return scores


def search_raw_chunks_qdrant(
    data_dir: Path,
    client_id: str,
    prompt: str,
    knowledge_document_ids: list[str],
    limit: int = 12,
    *,
    db: Database | None = None,
    ai_service: Any | None = None,
) -> dict[str, float]:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None:
        return {}
    scores: dict[str, float] = {}
    vectors, _ = embed_texts([prompt], data_dir=data_dir, db=db, ai_service=ai_service)
    active_name = collection_name("raw_chunk", client_id, embedding_signature=signature)
    legacy_name = legacy_collection_name("raw_chunk", client_id)
    target_collection = _pick_collection_with_fallback(client, active_name=active_name, legacy_name=legacy_name)
    try:
        results = client.search(
            collection_name=target_collection,
            query_vector=vectors[0] if vectors else hashed_embedding(prompt, size=dimension),
            limit=max(limit, 24),
            with_payload=True,
        )
    except Exception:
        return scores
    allowed = set(knowledge_document_ids)
    for item in results:
        payload = getattr(item, "payload", {}) or {}
        knowledge_document_id = str(payload.get("knowledge_document_id", ""))
        if knowledge_document_id not in allowed:
            continue
        chunk_id = str(payload.get("chunk_id", ""))
        if not chunk_id:
            continue
        scores[chunk_id] = float(getattr(item, "score", 0.0))
        if len(scores) >= limit:
            break
    return scores


def reindex_client_vector(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    signature, dimension = _resolve_vector_runtime(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    if signature is None:
        signature = current_embedding_signature(data_dir, db=db, ensure_ready=True, ai_service=ai_service)
    client = ensure_qdrant_collections(
        data_dir,
        client_id,
        embedding_signature=signature,
        vector_size=dimension,
    )
    if client is None:
        return {
            "clientId": client_id,
            "embeddingSignature": signature,
            "masterIndexed": 0,
            "chunkIndexed": 0,
            "fallbackUsed": True,
            "status": "failed",
        }
    sync_qdrant_for_client(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    names = resolve_vector_collection_names(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    master_indexed = qdrant_payload_count(client, names["masterActive"])
    chunk_indexed = qdrant_payload_count(client, names["chunkActive"])
    db.set_setting(f"knowledge.active_embedding_signature:{client_id}", signature)
    return {
        "clientId": client_id,
        "embeddingSignature": signature,
        "masterIndexed": int(master_indexed),
        "chunkIndexed": int(chunk_indexed),
        "fallbackUsed": False,
        "status": "completed",
    }


def get_vector_runtime_status(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any | None = None,
) -> dict[str, Any]:
    settings = get_retrieval_model_settings(db)
    signature = retrieval_embedding_signature(settings)
    active_signature = db.get_setting(f"knowledge.active_embedding_signature:{client_id}", "")
    names = resolve_vector_collection_names(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)
    client = qdrant_client_for(data_dir)
    active_master_count = qdrant_payload_count(client, names["masterActive"]) if client is not None else 0
    active_chunk_count = qdrant_payload_count(client, names["chunkActive"]) if client is not None else 0
    legacy_master_count = qdrant_payload_count(client, names["masterLegacy"]) if client is not None else 0
    legacy_chunk_count = qdrant_payload_count(client, names["chunkLegacy"]) if client is not None else 0
    active_ready = (active_master_count + active_chunk_count) > 0 and active_signature == signature
    if client is None:
        vector_index_status = "failed"
    elif active_ready:
        vector_index_status = "ready"
    elif (legacy_master_count + legacy_chunk_count) > 0:
        vector_index_status = "stale"
    else:
        vector_index_status = "building"

    provider_error = None
    embedding_status = embedding_backend_status(data_dir)
    if settings.embeddingProvider == "doubao" and ai_service is not None:
        try:
            store = ai_service._store_for("doubao")  # type: ignore[attr-defined]
            has_key = bool(store and str(store.get_api_key() or "").strip())
        except Exception:
            has_key = False
        if not has_key:
            provider_error = "doubao_api_key_missing"
    if provider_error is None:
        provider_error = embedding_status.get("error")

    active_collection = names["masterActive"] if active_ready else (names["masterLegacy"] if legacy_master_count > 0 else names["masterActive"])
    return {
        "embeddingProvider": settings.embeddingProvider,
        "embeddingModel": settings.embeddingModel,
        "embeddingDimension": int(settings.embeddingDimension or QDRANT_VECTOR_SIZE),
        "embeddingSignature": signature,
        "activeVectorCollection": active_collection,
        "vectorIndexStatus": vector_index_status,
        "qdrantReady": client is not None,
        "embeddingMode": settings.embeddingMode,
        "embeddingError": provider_error,
        "routerEnabled": settings.routerEnabled,
        "routerModel": settings.routerModel or None,
        "rerankEnabled": settings.rerankEnabled,
    }
```
