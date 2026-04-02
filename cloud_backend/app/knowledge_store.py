"""
向量知识库 — ChromaDB + 本地 Embedding

使用 ChromaDB 内置的 default embedding function（基于 all-MiniLM-L6-v2），
提供语义检索能力：
1. 把咨询问答、任务摘要、事件线资料等写入向量库
2. 咨询时按语义相关性检索最相关的知识片段
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── ChromaDB Knowledge Store ───────────────────

_chroma_client = None
_chroma_collection = None

CHROMA_COLLECTION_NAME = "yiyu_knowledge"


def _data_dir() -> Path:
    base = os.getenv(
        "YIYU_CLOUD_DATA_DIR",
        str(Path.home() / "Library" / "Application Support" / "YiyuThinkTankCloud"),
    )
    return Path(base) / "chromadb"


def _get_collection():
    """Lazy-init ChromaDB persistent client + collection.

    Uses ChromaDB's default embedding function which auto-downloads
    and runs a lightweight model (all-MiniLM-L6-v2) locally.
    No external API calls needed for embedding.
    """
    global _chroma_client, _chroma_collection
    if _chroma_collection is not None:
        return _chroma_collection

    import chromadb

    persist_dir = str(_data_dir())
    os.makedirs(persist_dir, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=persist_dir)
    _chroma_collection = _chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        "ChromaDB collection '%s' ready at %s (%d docs)",
        CHROMA_COLLECTION_NAME,
        persist_dir,
        _chroma_collection.count(),
    )
    return _chroma_collection


def _doc_id(org_id: str, source: str, content: str) -> str:
    """Deterministic ID to avoid duplicates."""
    h = hashlib.sha256(f"{org_id}:{source}:{content}".encode()).hexdigest()[:16]
    return f"{org_id}-{source}-{h}"


# ─── Public API ─────────────────────────────────


def add_knowledge(
    *,
    organization_id: str,
    source: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Add a knowledge document to the vector store.

    ChromaDB handles embedding automatically using its default model.
    """
    if not content.strip():
        return False

    doc_id = _doc_id(organization_id, source, content)
    meta = {"organization_id": organization_id, "source": source}
    if metadata:
        meta.update({k: str(v) for k, v in metadata.items() if v is not None})

    try:
        collection = _get_collection()
        collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[meta],
        )
        return True
    except Exception as exc:
        logger.error("ChromaDB upsert error: %s", exc)
        return False


def query_knowledge(
    *,
    organization_id: str,
    query: str,
    n_results: int = 5,
    client_id: str | None = None,
) -> list[str]:
    """Retrieve relevant knowledge snippets by semantic similarity.

    ChromaDB handles query embedding automatically.
    Returns list of document texts, most relevant first.
    """
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []

        if client_id:
            where_filter: dict[str, Any] = {
                "$and": [
                    {"organization_id": organization_id},
                    {"client_id": client_id},
                ]
            }
        else:
            where_filter = {"organization_id": organization_id}

        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, 10),
            where=where_filter,
        )
        documents = results.get("documents", [[]])[0]
        return [doc for doc in documents if doc]
    except Exception as exc:
        logger.error("ChromaDB query error: %s", exc)
        return []


def ingest_consultation_answer(
    *,
    organization_id: str,
    question: str,
    answer: str,
    client_id: str | None = None,
    client_name: str | None = None,
    event_line_id: str | None = None,
) -> bool:
    """Convenience: ingest a Q&A pair into the knowledge store."""
    content = f"问题：{question}\n回答：{answer}"
    return add_knowledge(
        organization_id=organization_id,
        source="consultation",
        content=content,
        metadata={
            "client_id": client_id,
            "client_name": client_name,
            "event_line_id": event_line_id,
            "type": "qa",
        },
    )


def ingest_event_line_summary(
    *,
    organization_id: str,
    event_line_id: str,
    client_id: str | None = None,
    client_name: str | None = None,
    name: str,
    summary: str | None = None,
    blocker: str | None = None,
    next_step: str | None = None,
) -> bool:
    """Ingest event line context into the knowledge store."""
    parts = [f"事件线：{name}"]
    if summary:
        parts.append(f"摘要：{summary}")
    if blocker:
        parts.append(f"当前阻塞：{blocker}")
    if next_step:
        parts.append(f"下一步：{next_step}")
    content = "\n".join(parts)
    return add_knowledge(
        organization_id=organization_id,
        source="event_line",
        content=content,
        metadata={
            "client_id": client_id,
            "client_name": client_name,
            "event_line_id": event_line_id,
            "type": "event_line",
        },
    )


def sync_desktop_surrogates_to_cloud(
    *,
    organization_id: str,
    client_id: str,
    client_name: str,
) -> dict[str, int]:
    """Sync desktop surrogate blocks (enriched + profile) into cloud ChromaDB.

    Reads from the desktop app.db and vector_store directory, then upserts
    the AI-enriched retrieval_summary + overview_summary into ChromaDB.
    """
    import os
    import sqlite3 as _sqlite3

    desktop_db_path = os.path.join(
        os.path.expanduser("~"),
        "Library", "Application Support", "YiyuThinkTankWorkbench", "app.db",
    )
    if not os.path.exists(desktop_db_path):
        return {"synced": 0, "error": "desktop db not found"}

    synced = 0
    try:
        conn = _sqlite3.connect(desktop_db_path)
        conn.row_factory = _sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, title, folder_category, source_type, overview_summary, retrieval_summary,
                   document_role, distinct_findings_json
            FROM knowledge_surrogates
            WHERE client_id = ?
            ORDER BY updated_at DESC
            """,
            (client_id,),
        ).fetchall()
        conn.close()
    except Exception as exc:
        logger.error("Desktop DB read failed: %s", exc)
        return {"synced": 0, "error": str(exc)}

    for row in rows:
        source_type = str(row["source_type"] or "document")
        title = str(row["title"] or "")
        overview = str(row["overview_summary"] or "")
        retrieval = str(row["retrieval_summary"] or "")
        category = str(row["folder_category"] or "")
        role = str(row["document_role"] or "")

        # Build a rich content block for ChromaDB
        content_parts = [f"【{title}】"]
        if role:
            content_parts.append(f"角色：{role}")
        if category:
            content_parts.append(f"分类：{category}")
        if overview:
            content_parts.append(overview[:1500])
        if retrieval:
            content_parts.append(f"检索摘要：{retrieval}")

        # Parse distinct findings
        try:
            import json
            findings = json.loads(row["distinct_findings_json"]) if row["distinct_findings_json"] else []
            if isinstance(findings, list) and findings:
                content_parts.append("关键发现：" + "；".join(str(f) for f in findings[:5]))
        except Exception:
            pass

        content = "\n".join(content_parts)
        if len(content.strip()) < 50:
            continue

        doc_type = "profile_block" if source_type == "memory_answer" else "surrogate"
        success = add_knowledge(
            organization_id=organization_id,
            source=f"desktop_{doc_type}",
            content=content,
            metadata={
                "client_id": client_id,
                "client_name": client_name,
                "type": doc_type,
                "category": category,
                "surrogate_id": str(row["id"]),
            },
        )
        if success:
            synced += 1

    return {"synced": synced, "total": len(rows)}
