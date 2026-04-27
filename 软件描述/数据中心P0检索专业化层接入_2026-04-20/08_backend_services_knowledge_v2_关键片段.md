# backend/app/services/knowledge_v2.py:1280-1410

```python
        """,
        (imported, finished_at, finished_at, job_id),
    )
    return {
        "importId": import_id,
        "jobId": job_id,
        "sourceRoot": str(workspace_root),
        "discovered": len(candidates),
        "imported": imported,
        "skipped": skipped,
    }


def compute_knowledge_status(db: Database, client_id: str, data_dir: Path | None = None) -> dict[str, Any]:
    runtime_status = (
        get_vector_runtime_status(db, data_dir=data_dir, client_id=client_id)
        if data_dir is not None
        else {
            "qdrantReady": True,
            "embeddingMode": "hash_fallback",
            "embeddingModel": None,
            "embeddingError": None,
            "embeddingProvider": None,
            "embeddingDimension": None,
            "embeddingSignature": None,
            "activeVectorCollection": None,
            "vectorIndexStatus": "ready",
            "routerEnabled": False,
            "routerModel": None,
            "rerankEnabled": False,
        }
    )
    main_job_placeholders = ",".join("?" for _ in MAIN_KNOWLEDGE_STATUS_JOB_TYPES)
    job_filter = f"client_id = ? AND job_type IN ({main_job_placeholders})"
    job_params = (client_id, *MAIN_KNOWLEDGE_STATUS_JOB_TYPES)
    document_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence'", (client_id,)) or 0)
    v2_background_docs = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND material_layer = 'background'", (client_id,)) or 0)
    section_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_sections WHERE v2_document_id IN (SELECT id FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence')", (client_id,)) or 0)
    chunk_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_chunks WHERE v2_document_id IN (SELECT id FROM v2_documents WHERE client_id = ? AND material_layer = 'evidence')", (client_id,)) or 0)
    failed_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND parse_status != 'ready'", (client_id,)) or 0)
    review_count = int(db.scalar("SELECT COUNT(1) AS count FROM v2_documents WHERE client_id = ? AND classification_confidence < 0.62", (client_id,)) or 0)
    dna_background_docs = int(db.scalar("SELECT COUNT(1) AS count FROM client_dna_documents WHERE client_id = ?", (client_id,)) or 0)
    memory_docs = int(db.scalar("SELECT COUNT(1) AS count FROM knowledge_surrogates WHERE client_id = ? AND source_type = 'memory_answer'", (client_id,)) or 0)
    pending_jobs = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM knowledge_jobs WHERE {job_filter} AND status = 'queued'",
            job_params,
        )
        or 0
    )
    running_jobs = int(
        db.scalar(
            f"SELECT COUNT(1) AS count FROM knowledge_jobs WHERE {job_filter} AND status = 'running'",
            job_params,
        )
        or 0
    )
    last_job = db.fetchone(
        f"SELECT * FROM knowledge_jobs WHERE {job_filter} ORDER BY created_at DESC LIMIT 1",
        job_params,
    )
    last_status = str(last_job["status"]) if last_job else "idle"
    last_error = str(last_job["last_error"]) if last_job and last_job["last_error"] else None
    last_success_row = db.fetchone(
        f"""
        SELECT finished_at
        FROM knowledge_jobs
        WHERE {job_filter} AND status = 'completed'
        ORDER BY finished_at DESC
        LIMIT 1
        """,
        job_params,
    )
    last_updated_row = db.fetchone(
        """
        SELECT updated_at
        FROM v2_documents
        WHERE client_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (client_id,),
    )
    last_success = str(last_success_row["finished_at"]) if last_success_row and last_success_row["finished_at"] else None
    last_updated = str(last_updated_row["updated_at"]) if last_updated_row and last_updated_row["updated_at"] else None
    return {
        "totalDocuments": document_count,
        "evidenceDocuments": document_count,
        "backgroundDocuments": dna_background_docs + v2_background_docs,
        "methodDocuments": 0,
        "totalSections": section_count,
        "totalChunks": chunk_count,
        "parseFailedDocuments": failed_count,
        "vectorizedDocuments": 0,
        "dedupedDocuments": 0,
        "reviewPendingDocuments": review_count,
        "surrogateCount": document_count,
        "memoryDocCount": memory_docs,
        "masterIndexCount": document_count,
        "reclassifiedDocumentCount": document_count,
        "qdrantReady": bool(runtime_status.get("qdrantReady", True)),
        "lastUpdatedAt": last_updated,
        "pendingJobs": pending_jobs,
        "runningJobs": running_jobs,
        "lastJobStatus": last_status,
        "lastJobError": last_error,
        "lastSuccessfulRunAt": last_success,
        "embeddingMode": str(runtime_status.get("embeddingMode") or "hash_fallback"),
        "embeddingModel": runtime_status.get("embeddingModel"),
        "embeddingError": runtime_status.get("embeddingError"),
        "embeddingProvider": runtime_status.get("embeddingProvider"),
        "embeddingDimension": runtime_status.get("embeddingDimension"),
        "embeddingSignature": runtime_status.get("embeddingSignature"),
        "activeVectorCollection": runtime_status.get("activeVectorCollection"),
        "vectorIndexStatus": runtime_status.get("vectorIndexStatus"),
        "routerEnabled": runtime_status.get("routerEnabled"),
        "routerModel": runtime_status.get("routerModel"),
        "rerankEnabled": runtime_status.get("rerankEnabled"),
        "lastPipelineVersion": V2_PIPELINE_VERSION,
    }


def fetch_document_cards(db: Database, client_id: str, data_dir: Path | None = None, limit: int | None = 120) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT vd.*, d.created_at AS document_created_at, d.excerpt AS legacy_excerpt
        FROM v2_documents vd
        JOIN documents d ON d.id = vd.document_id
        WHERE vd.client_id = ? AND vd.material_layer = 'evidence'
        ORDER BY vd.updated_at DESC
        LIMIT ?
```
