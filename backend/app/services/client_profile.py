"""Client profile block generation — Phase 2 of the dual-layer vector architecture.

This module generates high-level "profile blocks" (画像卡片) for a client by:
1. Inventorying the client's existing surrogates and their category distribution
2. Using AI to diagnose which profile dimensions are supported by the data
3. Generating one memory_answer block per recommended dimension
4. Writing each block to disk, DB, and Qdrant
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.db import Database, from_json
from app.services.knowledge_base import (
    upsert_master_index_record,
    upsert_surrogate_record,
    write_surrogate_markdown,
)

logger = logging.getLogger(__name__)


def _inventory_client(db: Database, client_id: str) -> dict[str, Any]:
    """Gather statistics about a client's surrogates for AI diagnosis."""
    client_row = db.fetchone("SELECT name, type, stage FROM clients WHERE id = ?", (client_id,))
    client_name = str(client_row["name"]) if client_row else client_id
    client_type = str(client_row["type"]) if client_row else "未知"
    client_stage = str(client_row["stage"]) if client_row else "未知"

    rows = db.fetchall(
        """
        SELECT title, folder_category, overview_summary, distinct_findings_json, source_type
        FROM knowledge_surrogates
        WHERE client_id = ?
        ORDER BY updated_at DESC
        """,
        (client_id,),
    )

    category_counter: Counter[str] = Counter()
    titles_by_category: dict[str, list[str]] = {}
    memory_count = 0

    for row in rows:
        source_type = str(row["source_type"] or "document")
        if source_type == "memory_answer":
            memory_count += 1
            continue
        cat = str(row["folder_category"] or "其他资料")
        category_counter[cat] += 1
        titles_by_category.setdefault(cat, []).append(str(row["title"]))

    return {
        "client_name": client_name,
        "client_type": client_type,
        "client_stage": client_stage,
        "category_distribution": dict(category_counter),
        "top_titles_per_category": {cat: titles[:3] for cat, titles in titles_by_category.items()},
        "existing_memory_count": memory_count,
        "all_rows": rows,
    }


def _aggregate_summaries_for_dimension(
    rows: list[dict[str, Any]],
    source_categories: list[str],
) -> str:
    """Collect overview_summary + distinct_findings from surrogates matching the given categories."""
    parts: list[str] = []
    total_chars = 0
    for row in rows:
        if str(row["source_type"] or "document") == "memory_answer":
            continue
        cat = str(row["folder_category"] or "其他资料")
        if cat not in source_categories:
            continue
        title = str(row["title"])
        overview = str(row["overview_summary"] or "")
        findings_raw = from_json(row["distinct_findings_json"]) if row["distinct_findings_json"] else []
        findings = [str(f) for f in findings_raw] if isinstance(findings_raw, list) else []

        part = f"【{title}】\n{overview}"
        if findings:
            part += "\n关键发现：" + "；".join(findings)
        parts.append(part)
        total_chars += len(part)
        if total_chars > 4000:
            break
    return "\n\n".join(parts)


def build_client_profile(
    db: Database,
    *,
    data_dir: Path,
    client_id: str,
    ai_service: Any,
) -> dict[str, Any]:
    """Generate adaptive client profile blocks based on the client's actual data.

    Returns a summary dict with the list of generated blocks.
    """
    inventory = _inventory_client(db, client_id)
    client_name = inventory["client_name"]

    # Step 1: AI diagnosis — which dimensions to generate
    diagnosis = ai_service.diagnose_profile_dimensions(
        client_name=client_name,
        client_type=inventory["client_type"],
        client_stage=inventory["client_stage"],
        category_distribution=inventory["category_distribution"],
        top_titles_per_category=inventory["top_titles_per_category"],
        existing_memory_count=inventory["existing_memory_count"],
    )
    if not diagnosis or not diagnosis.get("recommended_blocks"):
        return {
            "clientId": client_id,
            "clientName": client_name,
            "generated": [],
            "skipped": diagnosis.get("skipped_dimensions", []) if diagnosis else [],
            "error": "AI diagnosis returned no recommendations" if not diagnosis else None,
        }

    recommended = diagnosis["recommended_blocks"]
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    generated: list[dict[str, Any]] = []

    # Step 2: Generate each profile block
    for block_spec in recommended:
        dimension = str(block_spec.get("dimension", ""))
        source_categories = block_spec.get("source_categories", [])
        if not dimension:
            continue

        aggregated = _aggregate_summaries_for_dimension(inventory["all_rows"], source_categories)
        if len(aggregated.strip()) < 50:
            continue

        payload_result = ai_service.generate_profile_block(
            client_name=client_name,
            dimension=dimension,
            aggregated_summaries=aggregated,
        )
        if not payload_result:
            continue

        # Build surrogate payload with defaults for missing fields
        payload: dict[str, Any] = {
            "overview_summary": payload_result.get("overview_summary", ""),
            "retrieval_summary": payload_result.get("retrieval_summary", ""),
            "document_role": payload_result.get("document_role", f"{client_name}客户画像·{dimension}"),
            "core_questions": payload_result.get("core_questions", []),
            "query_hints": payload_result.get("query_hints", [dimension, client_name]),
            "distinct_findings": payload_result.get("distinct_findings", []),
            "entities": payload_result.get("entities", []),
            "time_markers": payload_result.get("time_markers", []),
            "source_links": [],
        }

        doc_uid = f"prof_{hashlib.sha1(f'{client_id}:{dimension}'.encode('utf-8')).hexdigest()[:12]}"
        title = f"{client_name} · {dimension}"

        # Write .md file
        surrogate_md_path = write_surrogate_markdown(
            data_dir,
            client_id=client_id,
            doc_uid=doc_uid,
            folder_category="客户画像",
            title=title,
            source_type="memory_answer",
            source_path=None,
            payload=payload,
        )

        # Write DB surrogate record
        surrogate_id = f"sur_{doc_uid}"
        upsert_surrogate_record(
            db,
            surrogate_id=surrogate_id,
            knowledge_document_id=None,
            client_id=client_id,
            source_type="memory_answer",
            title=title,
            folder_category="客户画像",
            surrogate_md_path=surrogate_md_path,
            payload=payload,
            timestamp=timestamp,
        )

        # Write master index + Qdrant vector
        searchable_text = "\n".join([
            title,
            str(payload.get("retrieval_summary", "")),
            " ".join(str(q) for q in payload.get("core_questions", [])),
            " ".join(str(h) for h in payload.get("query_hints", [])),
            " ".join(str(f) for f in payload.get("distinct_findings", [])),
            "客户画像",
        ])
        entry_id = f"midx_{doc_uid}"
        upsert_master_index_record(
            db,
            data_dir=data_dir,
            entry_id=entry_id,
            client_id=client_id,
            surrogate_id=surrogate_id,
            title=title,
            folder_category="客户画像",
            document_role=str(payload.get("document_role", "")),
            retrieval_summary=str(payload.get("retrieval_summary", "")),
            searchable_text=searchable_text,
            source_path=None,
            surrogate_md_path=surrogate_md_path,
            timestamp=timestamp,
        )

        generated.append({
            "dimension": dimension,
            "surrogateId": surrogate_id,
            "title": title,
            "mdPath": surrogate_md_path,
            "priority": block_spec.get("priority", 99),
        })

    return {
        "clientId": client_id,
        "clientName": client_name,
        "generated": generated,
        "skipped": diagnosis.get("skipped_dimensions", []),
    }


def backfill_all_clients(
    db: Database,
    *,
    data_dir: Path,
    ai_service: Any,
) -> dict[str, Any]:
    """One-time backfill: enrich surrogates + build profile blocks for ALL clients with existing surrogates."""
    from app.services.knowledge_base import batch_enrich_surrogates

    client_rows = db.fetchall("SELECT id, name FROM clients ORDER BY name")
    results: list[dict[str, Any]] = []

    for row in client_rows:
        client_id = str(row["id"])
        client_name = str(row["name"])

        # Count existing surrogates
        surrogate_count = db.fetchone(
            "SELECT COUNT(*) AS cnt FROM knowledge_surrogates WHERE client_id = ? AND source_type = 'document'",
            (client_id,),
        )
        count = int(surrogate_count["cnt"]) if surrogate_count else 0
        if count == 0:
            results.append({"clientId": client_id, "clientName": client_name, "skipped": True, "reason": "no surrogates"})
            continue

        # Step 1: Enrich existing surrogates
        enrich_result = batch_enrich_surrogates(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)

        # Step 2: Build profile blocks
        profile_result = build_client_profile(db, data_dir=data_dir, client_id=client_id, ai_service=ai_service)

        results.append({
            "clientId": client_id,
            "clientName": client_name,
            "skipped": False,
            "enriched": enrich_result.get("enriched", 0),
            "profileBlocksGenerated": len(profile_result.get("generated", [])),
        })

    return {"clients": results, "totalProcessed": sum(1 for r in results if not r.get("skipped"))}


def _sync_to_cloud(db: Database, client_id: str) -> dict[str, Any]:
    """Sync a client's surrogates and profile blocks directly into the shared ChromaDB.

    Both desktop and cloud processes use the same ChromaDB directory, so we write
    directly using chromadb without needing to import from cloud_backend.
    """
    import json as _json
    import os

    client_row = db.fetchone("SELECT name FROM clients WHERE id = ?", (client_id,))
    client_name = str(client_row["name"]) if client_row else client_id

    org_row = db.fetchone("SELECT organization_id FROM consultation_answers WHERE client_id = ? LIMIT 1", (client_id,))
    organization_id = str(org_row["organization_id"]) if org_row else "default"

    # Use the same ChromaDB path as cloud_backend
    chroma_dir = os.path.join(
        os.path.expanduser("~"),
        "Library", "Application Support", "YiyuThinkTankCloud", "chromadb",
    )
    os.makedirs(chroma_dir, exist_ok=True)

    try:
        import chromadb
    except ImportError:
        logger.warning("chromadb not installed in desktop env, skipping cloud sync")
        return {"clientId": client_id, "clientName": client_name, "synced": 0, "error": "chromadb not installed"}

    try:
        chroma_client = chromadb.PersistentClient(path=chroma_dir)
        collection = chroma_client.get_or_create_collection(
            name="yiyu_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:
        logger.warning("ChromaDB init failed: %s", exc)
        return {"clientId": client_id, "clientName": client_name, "synced": 0, "error": str(exc)}

    rows = db.fetchall(
        """
        SELECT id, title, folder_category, source_type, overview_summary,
               retrieval_summary, document_role, distinct_findings_json
        FROM knowledge_surrogates
        WHERE client_id = ?
        ORDER BY updated_at DESC
        """,
        (client_id,),
    )

    synced = 0
    ids_batch: list[str] = []
    docs_batch: list[str] = []
    metas_batch: list[dict[str, str]] = []

    for row in rows:
        title = str(row["title"] or "")
        overview = str(row["overview_summary"] or "")
        retrieval = str(row["retrieval_summary"] or "")
        category = str(row["folder_category"] or "")
        role = str(row["document_role"] or "")
        source_type = str(row["source_type"] or "document")

        content_parts = [f"【{title}】"]
        if role:
            content_parts.append(f"角色：{role}")
        if overview:
            content_parts.append(overview[:1500])
        if retrieval:
            content_parts.append(f"检索摘要：{retrieval}")
        try:
            findings = _json.loads(row["distinct_findings_json"]) if row["distinct_findings_json"] else []
            if isinstance(findings, list) and findings:
                content_parts.append("关键发现：" + "；".join(str(f) for f in findings[:5]))
        except Exception:
            pass

        content = "\n".join(content_parts)
        if len(content.strip()) < 50:
            continue

        doc_type = "profile_block" if source_type == "memory_answer" else "surrogate"
        doc_id_hash = hashlib.sha256(f"{organization_id}:desktop_{doc_type}:{content}".encode()).hexdigest()[:16]
        doc_id = f"{organization_id}-desktop_{doc_type}-{doc_id_hash}"

        ids_batch.append(doc_id)
        docs_batch.append(content)
        metas_batch.append({
            "organization_id": organization_id,
            "source": f"desktop_{doc_type}",
            "client_id": client_id,
            "client_name": client_name,
            "type": doc_type,
            "category": category,
        })

        if len(ids_batch) >= 20:
            try:
                collection.upsert(ids=ids_batch, documents=docs_batch, metadatas=metas_batch)
                synced += len(ids_batch)
            except Exception as exc:
                logger.warning("ChromaDB batch upsert failed: %s", exc)
            ids_batch, docs_batch, metas_batch = [], [], []

    if ids_batch:
        try:
            collection.upsert(ids=ids_batch, documents=docs_batch, metadatas=metas_batch)
            synced += len(ids_batch)
        except Exception as exc:
            logger.warning("ChromaDB final batch upsert failed: %s", exc)

    return {"clientId": client_id, "clientName": client_name, "synced": synced, "total": len(rows)}
