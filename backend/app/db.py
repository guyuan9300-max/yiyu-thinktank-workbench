from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from pathlib import Path

BACKEND_SCHEMA_VERSION = 20260420


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                PRAGMA busy_timeout=5000;

                -- ══ 纯本地表（不同步到云端） ══

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                -- ══ 同步表（走云端） ══

                CREATE TABLE IF NOT EXISTS operators (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    team TEXT NOT NULL,
                    color TEXT NOT NULL,
                    is_current INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    type TEXT NOT NULL,
                    intro TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    color TEXT NOT NULL DEFAULT '#5B7BFE',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS client_units (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS client_folders (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    path TEXT NOT NULL,
                    file_count INTEGER NOT NULL DEFAULT 0,
                    last_scanned_at TEXT,
                    folder_kind TEXT NOT NULL DEFAULT 'business',
                    source_type TEXT NOT NULL DEFAULT 'legacy',
                    is_system INTEGER NOT NULL DEFAULT 0,
                    is_hidden INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 100,
                    created_by_rule TEXT NOT NULL DEFAULT '',
                    suggested INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                -- ══ 纯本地表（知识库/文件/向量 — 不同步） ══

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    folder_id TEXT,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL,
                    original_source_path TEXT,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(folder_id) REFERENCES client_folders(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS imports (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    imported_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS source_tree_snapshots (
                    id TEXT PRIMARY KEY,
                    import_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    tree_json TEXT NOT NULL,
                    file_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(import_id) REFERENCES imports(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    import_batch_id TEXT,
                    document_id TEXT NOT NULL UNIQUE,
                    doc_uid TEXT NOT NULL UNIQUE,
                    original_path TEXT NOT NULL,
                    import_source_path TEXT,
                    current_human_path TEXT,
                    human_folder_category TEXT,
                    reclassified_at TEXT,
                    reclass_reason TEXT,
                    reclass_confidence REAL NOT NULL DEFAULT 0.0,
                    normalized_path TEXT,
                    kind TEXT NOT NULL,
                    primary_category TEXT NOT NULL,
                    secondary_category TEXT NOT NULL,
                    classification_confidence REAL NOT NULL DEFAULT 0.0,
                    needs_review INTEGER NOT NULL DEFAULT 0,
                    deep_read INTEGER NOT NULL DEFAULT 0,
                    last_hit_question TEXT,
                    dedup_status TEXT NOT NULL DEFAULT 'unique',
                    vector_status TEXT NOT NULL DEFAULT 'pending',
                    version INTEGER NOT NULL DEFAULT 1,
                    binary_hash TEXT NOT NULL,
                    normalized_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(import_batch_id) REFERENCES imports(id) ON DELETE SET NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS knowledge_document_versions (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL,
                    version_no INTEGER NOT NULL,
                    raw_text TEXT NOT NULL,
                    raw_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS document_cards (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    one_line_summary TEXT NOT NULL,
                    summary_200 TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    date_range_label TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS document_chunks (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    section_label TEXT,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS document_catalog_index (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL UNIQUE,
                    searchable_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS v2_documents (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    document_id TEXT NOT NULL UNIQUE,
                    original_path TEXT NOT NULL,
                    managed_path TEXT NOT NULL,
                    markdown_path TEXT,
                    file_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    material_layer TEXT NOT NULL DEFAULT 'evidence',
                    visible_category TEXT NOT NULL DEFAULT '其他资料',
                    secondary_category TEXT NOT NULL DEFAULT '待人工复核',
                    parse_status TEXT NOT NULL DEFAULT 'queued',
                    parse_error TEXT,
                    preview_text TEXT NOT NULL DEFAULT '',
                    doc_index_text TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL DEFAULT '',
                    markdown_content TEXT NOT NULL DEFAULT '',
                    classification_confidence REAL NOT NULL DEFAULT 0.0,
                    section_count INTEGER NOT NULL DEFAULT 0,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    imported_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_v2_documents_client ON v2_documents(client_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_v2_documents_layer ON v2_documents(client_id, material_layer, parse_status);

                CREATE TABLE IF NOT EXISTS v2_sections (
                    id TEXT PRIMARY KEY,
                    v2_document_id TEXT NOT NULL,
                    section_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    searchable_text TEXT NOT NULL DEFAULT '',
                    char_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(v2_document_id) REFERENCES v2_documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_v2_sections_doc ON v2_sections(v2_document_id, section_index ASC);

                CREATE TABLE IF NOT EXISTS v2_chunks (
                    id TEXT PRIMARY KEY,
                    v2_document_id TEXT NOT NULL,
                    v2_section_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    section_label TEXT,
                    content TEXT NOT NULL,
                    searchable_text TEXT NOT NULL DEFAULT '',
                    char_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(v2_document_id) REFERENCES v2_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY(v2_section_id) REFERENCES v2_sections(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_v2_chunks_section ON v2_chunks(v2_section_id, chunk_index ASC);
                CREATE INDEX IF NOT EXISTS idx_v2_chunks_doc ON v2_chunks(v2_document_id, chunk_index ASC);

                CREATE TABLE IF NOT EXISTS knowledge_surrogates (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT UNIQUE,
                    client_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    folder_category TEXT NOT NULL,
                    surrogate_md_path TEXT NOT NULL,
                    overview_summary TEXT NOT NULL,
                    retrieval_summary TEXT NOT NULL,
                    document_role TEXT NOT NULL,
                    core_questions_json TEXT NOT NULL,
                    query_hints_json TEXT NOT NULL,
                    distinct_findings_json TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    time_markers_json TEXT NOT NULL,
                    source_links_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS knowledge_master_index (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    surrogate_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    folder_category TEXT NOT NULL,
                    document_role TEXT NOT NULL,
                    retrieval_summary TEXT NOT NULL,
                    searchable_text TEXT NOT NULL,
                    source_path TEXT,
                    surrogate_md_path TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(surrogate_id) REFERENCES knowledge_surrogates(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS logical_file_mappings (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL UNIQUE,
                    source_path TEXT NOT NULL,
                    logical_folder_category TEXT NOT NULL,
                    logical_folder_subcategory TEXT,
                    classification_confidence REAL NOT NULL DEFAULT 0.0,
                    classification_reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS knowledge_jobs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    total_items INTEGER NOT NULL DEFAULT 0,
                    processed_items INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS knowledge_job_events (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES knowledge_jobs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS knowledge_search_runs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    thread_id TEXT,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ready',
                    retrieval_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS client_analysis_runs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    user_message_id TEXT NOT NULL,
                    assistant_message_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    progress_floor REAL NOT NULL DEFAULT 0,
                    progress_ceiling REAL NOT NULL DEFAULT 25,
                    stage_label TEXT,
                    elapsed_ms REAL NOT NULL DEFAULT 0,
                    evidence_summary_json TEXT NOT NULL DEFAULT '{}',
                    long_answer TEXT,
                    structured_summary_json TEXT NOT NULL DEFAULT '{}',
                    long_answer_status TEXT NOT NULL DEFAULT 'pending',
                    summary_status TEXT NOT NULL DEFAULT 'pending',
                    answer_mode TEXT,
                    llm_invoked INTEGER NOT NULL DEFAULT 0,
                    provider_used TEXT,
                    failure_reason TEXT,
                    timing_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
                    FOREIGN KEY(assistant_message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_client_analysis_runs_client ON client_analysis_runs(client_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_client_analysis_runs_thread ON client_analysis_runs(thread_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'normal',
                    trigger_type TEXT NOT NULL DEFAULT 'manual',
                    question TEXT NOT NULL DEFAULT '',
                    source_snapshot TEXT NOT NULL DEFAULT '',
                    feature_flags_json TEXT NOT NULL DEFAULT '{}',
                    progress REAL NOT NULL DEFAULT 0,
                    stage_label TEXT,
                    run_log_id TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_jobs_client ON analysis_jobs(client_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_analysis_jobs_scope ON analysis_jobs(client_id, scope_type, scope_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS job_stage_runs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT,
                    model_name TEXT,
                    lane TEXT NOT NULL DEFAULT 'cloud_final',
                    cache_key TEXT,
                    cache_hit INTEGER NOT NULL DEFAULT 0,
                    degraded INTEGER NOT NULL DEFAULT 0,
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    topic_count INTEGER NOT NULL DEFAULT 0,
                    conflict_count INTEGER NOT NULL DEFAULT 0,
                    context_time_range TEXT,
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    detail TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_job_stage_runs_job ON job_stage_runs(job_id, created_at ASC);

                CREATE TABLE IF NOT EXISTS doc_skeletons (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    document_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    outline_json TEXT NOT NULL DEFAULT '[]',
                    entities_json TEXT NOT NULL DEFAULT '[]',
                    time_range TEXT,
                    parser_version TEXT NOT NULL DEFAULT 'analysis-center-v1',
                    source_snapshot TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_doc_skeletons_client ON doc_skeletons(client_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS evidence_cards (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_ref TEXT NOT NULL DEFAULT '',
                    quote TEXT NOT NULL,
                    normalized_claim TEXT NOT NULL,
                    evidence_type TEXT NOT NULL DEFAULT 'general',
                    polarity TEXT NOT NULL DEFAULT 'neutral',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    topic_keys_json TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    time_anchor TEXT,
                    document_id TEXT,
                    event_line_id TEXT,
                    task_id TEXT,
                    meeting_id TEXT,
                    module_id TEXT,
                    flow_id TEXT,
                    review_state TEXT NOT NULL DEFAULT 'draft',
                    fingerprint TEXT NOT NULL,
                    normalized_claim_hash TEXT NOT NULL DEFAULT '',
                    source_ref_hash TEXT NOT NULL DEFAULT '',
                    evidence_fingerprint TEXT NOT NULL DEFAULT '',
                    normalizer_version TEXT NOT NULL DEFAULT 'analysis-center-v0.3.3',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_cards_client_scope ON evidence_cards(client_id, scope_type, scope_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_evidence_cards_fingerprint ON evidence_cards(client_id, fingerprint);

                CREATE TABLE IF NOT EXISTS theme_clusters (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    theme_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    support_ids_json TEXT NOT NULL DEFAULT '[]',
                    oppose_ids_json TEXT NOT NULL DEFAULT '[]',
                    gap_summary TEXT NOT NULL DEFAULT '',
                    latest_change_summary TEXT NOT NULL DEFAULT '',
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_theme_clusters_scope ON theme_clusters(client_id, scope_type, scope_id, updated_at DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_theme_clusters_unique_key
                    ON theme_clusters(client_id, scope_type, scope_id, theme_key);

                CREATE TABLE IF NOT EXISTS conflict_groups (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    conflict_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                    unresolved_question_ids_json TEXT NOT NULL DEFAULT '[]',
                    resolution_status TEXT NOT NULL DEFAULT 'draft',
                    severity TEXT NOT NULL DEFAULT 'medium',
                    context_pack_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(context_pack_id) REFERENCES context_packs(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conflict_groups_scope ON conflict_groups(client_id, scope_type, scope_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS open_questions (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    theme_key TEXT NOT NULL,
                    question TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    blocker_level TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_open_questions_scope ON open_questions(client_id, scope_type, scope_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS context_packs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    job_id TEXT,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    prompt_version TEXT NOT NULL DEFAULT 'analysis-center-v1',
                    source_count INTEGER NOT NULL DEFAULT 0,
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    stale_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(job_id) REFERENCES analysis_jobs(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_context_packs_target ON context_packs(client_id, target_type, target_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS dna_deltas (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    previous_version TEXT,
                    proposed_change TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                    confidence TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'draft',
                    context_pack_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(context_pack_id) REFERENCES context_packs(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_dna_deltas_client_status ON dna_deltas(client_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS judgment_versions (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'draft',
                    summary TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                    context_pack_id TEXT,
                    risk_level TEXT NOT NULL DEFAULT 'medium',
                    confidence TEXT NOT NULL DEFAULT 'medium',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(context_pack_id) REFERENCES context_packs(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_judgment_versions_client_target ON judgment_versions(client_id, target_type, target_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS runtime_run_logs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    job_id TEXT,
                    provider TEXT,
                    model TEXT,
                    lane TEXT NOT NULL DEFAULT 'cloud_final',
                    cache_hit INTEGER NOT NULL DEFAULT 0,
                    degraded INTEGER NOT NULL DEFAULT 0,
                    document_count INTEGER NOT NULL DEFAULT 0,
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    conflict_count INTEGER NOT NULL DEFAULT 0,
                    context_time_range TEXT,
                    prompt_version TEXT,
                    schema_version TEXT,
                    summary TEXT NOT NULL DEFAULT '',
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(job_id) REFERENCES analysis_jobs(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runtime_run_logs_client ON runtime_run_logs(client_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS sync_memory_records (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    sync_mode TEXT NOT NULL DEFAULT 'derived_only',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    source_fingerprint TEXT NOT NULL DEFAULT '',
                    synced_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_sync_memory_scope ON sync_memory_records(client_id, scope_type, scope_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS approval_records (
                    id TEXT PRIMARY KEY,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    actor_id TEXT NOT NULL DEFAULT '',
                    actor_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_approval_records_object ON approval_records(object_type, object_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS proposal_records (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending_review',
                    risk_level TEXT NOT NULL DEFAULT 'medium',
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    rationale TEXT NOT NULL DEFAULT '',
                    target_refs_json TEXT NOT NULL DEFAULT '[]',
                    source_refs_json TEXT NOT NULL DEFAULT '[]',
                    boundary_notes_json TEXT NOT NULL DEFAULT '[]',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_by TEXT NOT NULL DEFAULT '',
                    decided_by TEXT,
                    decided_at TEXT,
                    rejected_reason TEXT,
                    execution_ticket_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_proposal_records_client_status ON proposal_records(client_id, status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_proposal_records_status ON proposal_records(status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS execution_tickets (
                    id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    execution_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    idempotency_key TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    last_error TEXT,
                    last_attempt_at TEXT,
                    error_message TEXT,
                    executed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(proposal_id) REFERENCES proposal_records(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_execution_tickets_proposal ON execution_tickets(proposal_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_execution_tickets_status ON execution_tickets(status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS execution_ticket_logs (
                    id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(ticket_id) REFERENCES execution_tickets(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_execution_ticket_logs_ticket
                    ON execution_ticket_logs(ticket_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS client_template_fill_runs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    template_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    stage_label TEXT,
                    elapsed_ms REAL NOT NULL DEFAULT 0,
                    field_count INTEGER NOT NULL DEFAULT 0,
                    processed_count INTEGER NOT NULL DEFAULT 0,
                    filled_count INTEGER NOT NULL DEFAULT 0,
                    missing_count INTEGER NOT NULL DEFAULT 0,
                    current_field_label TEXT,
                    evidence_titles_json TEXT NOT NULL DEFAULT '[]',
                    fields_json TEXT NOT NULL DEFAULT '[]',
                    output_path TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_client_template_fill_runs_client ON client_template_fill_runs(client_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS workspace_link_import_runs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    source_platform TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    title TEXT,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    document_id TEXT,
                    document_path TEXT,
                    media_cache_status TEXT NOT NULL DEFAULT 'not_downloaded',
                    error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workspace_link_import_runs_client
                    ON workspace_link_import_runs(client_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS file_reclass_events (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL,
                    from_path TEXT NOT NULL,
                    to_path TEXT NOT NULL,
                    from_category TEXT,
                    to_category TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS dedup_relations (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL,
                    related_document_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    relation_score REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY(related_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS answer_runs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    coverage_score REAL NOT NULL DEFAULT 0.0,
                    retrieval_mode TEXT NOT NULL DEFAULT 'legacy',
                    llm_invoked INTEGER NOT NULL DEFAULT 0,
                    provider_used TEXT,
                    failure_reason TEXT,
                    retrieval_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS answer_citations (
                    id TEXT PRIMARY KEY,
                    answer_run_id TEXT NOT NULL,
                    knowledge_document_id TEXT NOT NULL,
                    chunk_id TEXT,
                    source_stage TEXT NOT NULL DEFAULT 'raw_chunk',
                    drillthrough_used INTEGER NOT NULL DEFAULT 0,
                    title TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0.0,
                    coverage_contribution REAL NOT NULL DEFAULT 0.0,
                    section_label TEXT,
                    matched_terms_json TEXT NOT NULL,
                    path TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(answer_run_id) REFERENCES answer_runs(id) ON DELETE CASCADE,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS card_review_queue (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    scheduled_at TEXT,
                    transcript_text TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS meeting_sources (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS agenda_items (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS action_items (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    owner_name TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.8,
                    publish_status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS risks (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ambiguities (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    candidates_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evidence_refs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    meeting_id TEXT,
                    document_id TEXT,
                    title TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    path TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS goal_records (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    quarter TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    owner_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS dna_terms (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS organization_dna_documents (
                    module_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    markdown_content TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS organization_dna_v2_items (
                    id TEXT PRIMARY KEY,
                    module_kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content_markdown TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    evidence_level TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_label TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    source_created_at TEXT,
                    last_seen_at TEXT NOT NULL,
                    valid_until TEXT,
                    confidence_score INTEGER NOT NULL DEFAULT 60,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_org_dna_v2_items_kind_status
                    ON organization_dna_v2_items(module_kind, status, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_org_dna_v2_items_source
                    ON organization_dna_v2_items(source_type, source_id);

                CREATE TABLE IF NOT EXISTS organization_dna_refresh_runs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL DEFAULT 'organization_dna_refresh',
                    status TEXT NOT NULL,
                    trigger_source TEXT NOT NULL DEFAULT 'manual',
                    total_items INTEGER NOT NULL DEFAULT 0,
                    processed_items INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS organization_dna_refresh_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES organization_dna_refresh_runs(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_org_dna_refresh_events_run
                    ON organization_dna_refresh_events(run_id, created_at ASC);

                CREATE TABLE IF NOT EXISTS client_dna_documents (
                    client_id TEXT NOT NULL,
                    module_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    markdown_content TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_kind TEXT NOT NULL DEFAULT 'manual',
                    missing_info_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    PRIMARY KEY (client_id, module_key),
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_threads (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    structured_data_json TEXT,
                    model_route TEXT,
                    llm_invoked INTEGER NOT NULL DEFAULT 0,
                    provider_used TEXT,
                    answer_mode TEXT,
                    evidence_status TEXT,
                    failure_reason TEXT,
                    timing_json TEXT NOT NULL DEFAULT '{}',
                    retrieval_summary_json TEXT NOT NULL DEFAULT '{}',
                    evidence_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'success',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chat_thread_memory_packs (
                    client_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    context_pack_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(client_id, thread_id),
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chat_thread_memory_packs_thread
                ON chat_thread_memory_packs(thread_id);

                -- ══ 同步表（任务/事件线/复盘 — 走云端） ══

                CREATE TABLE IF NOT EXISTS task_lists (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    color TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    scope TEXT NOT NULL DEFAULT 'org',
                    archived_at TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'local',
                    cloud_id TEXT,
                    cloud_payload_json TEXT NOT NULL DEFAULT '',
                    last_synced_at TEXT NOT NULL DEFAULT '',
                    last_cloud_version TEXT NOT NULL DEFAULT '',
                    pending_sync_action TEXT NOT NULL DEFAULT '',
                    last_sync_error TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS task_tags (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL UNIQUE,
                    scope TEXT NOT NULL DEFAULT 'org',
                    color TEXT NOT NULL DEFAULT '#5B7BFE',
                    owner_operator_id TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    archived_at TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'local',
                    cloud_id TEXT,
                    cloud_payload_json TEXT NOT NULL DEFAULT '',
                    last_synced_at TEXT NOT NULL DEFAULT '',
                    last_cloud_version TEXT NOT NULL DEFAULT '',
                    pending_sync_action TEXT NOT NULL DEFAULT '',
                    last_sync_error TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS task_settings (
                    operator_id TEXT PRIMARY KEY,
                    default_list_id TEXT,
                    default_priority TEXT NOT NULL DEFAULT 'normal',
                    default_due_date_preset TEXT NOT NULL DEFAULT 'today',
                    default_view_mode TEXT NOT NULL DEFAULT 'list',
                    list_sort_mode TEXT NOT NULL DEFAULT 'manual',
                    show_completed_tasks INTEGER NOT NULL DEFAULT 0,
                    default_review_scope TEXT NOT NULL DEFAULT 'work',
                    auto_assign_self INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(operator_id) REFERENCES operators(id) ON DELETE CASCADE,
                    FOREIGN KEY(default_list_id) REFERENCES task_lists(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS task_views (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'custom',
                    description TEXT NOT NULL DEFAULT '',
                    calendar_scope TEXT NOT NULL DEFAULT 'all',
                    shareability TEXT NOT NULL DEFAULT 'private',
                    sort_by TEXT NOT NULL DEFAULT 'updatedAt',
                    sort_direction TEXT NOT NULL DEFAULT 'desc',
                    visible_fields_json TEXT NOT NULL DEFAULT '[]',
                    filter_set_json TEXT NOT NULL DEFAULT '{}',
                    built_in INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_views_kind
                    ON task_views(kind, built_in, updated_at DESC);

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    list_id TEXT NOT NULL,
                    creator_id TEXT NOT NULL DEFAULT '',
                    owner_id TEXT,
                    owner_name TEXT NOT NULL,
                    progress_status TEXT NOT NULL DEFAULT 'todo',
                    ddl TEXT NOT NULL,
                    deadline_at TEXT,
                    scheduled_start_at TEXT,
                    scheduled_end_at TEXT,
                    completed_at TEXT,
                    start_date TEXT,
                    due_date TEXT,
                    duration_minutes INTEGER NOT NULL DEFAULT 60,
                    scope_mode TEXT NOT NULL DEFAULT 'COLLAB_SHARED',
                    event_line_id TEXT,
                    business_category TEXT,
                    current_blocker TEXT,
                    next_action TEXT,
                    recent_decision TEXT,
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    source_type TEXT NOT NULL,
                    source_id TEXT,
                    tags_json TEXT NOT NULL,
                    tag_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_synced_at TEXT NOT NULL DEFAULT '',
                    last_cloud_version TEXT NOT NULL DEFAULT '',
                    pending_sync_action TEXT NOT NULL DEFAULT '',
                    last_sync_error TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(list_id) REFERENCES task_lists(id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS task_collaborators (
                    task_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL DEFAULT '',
                    user_id TEXT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    order_index INTEGER NOT NULL DEFAULT 0,
                    is_owner INTEGER NOT NULL DEFAULT 0,
                    inbox_status TEXT NOT NULL DEFAULT 'pending',
                    return_reason TEXT,
                    handled_at TEXT,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (task_id, user_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_task_collaborators_user
                    ON task_collaborators(user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS event_lines (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'custom',
                    status TEXT NOT NULL DEFAULT 'active',
                    business_category TEXT,
                    stage TEXT,
                    summary TEXT,
                    intent TEXT,
                    current_blocker TEXT,
                    recent_decision TEXT,
                    next_step TEXT,
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    owner_id TEXT,
                    owner_name TEXT,
                    primary_client_id TEXT,
                    primary_client_name TEXT,
                    primary_department_id TEXT,
                    primary_department_name TEXT,
                    participant_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'local',
                    cloud_id TEXT,
                    cloud_payload_json TEXT NOT NULL DEFAULT '',
                    last_synced_at TEXT NOT NULL DEFAULT '',
                    last_cloud_version TEXT NOT NULL DEFAULT '',
                    pending_sync_action TEXT NOT NULL DEFAULT '',
                    last_sync_error TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS event_line_activities (
                    id TEXT PRIMARY KEY,
                    event_line_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    happened_at TEXT NOT NULL,
                    actor_id TEXT,
                    actor_name TEXT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    is_key INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS organization_notebook_snapshots (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL UNIQUE,
                    organization_intro TEXT NOT NULL DEFAULT '',
                    collaboration_relationship TEXT NOT NULL DEFAULT '',
                    current_stage TEXT NOT NULL DEFAULT '',
                    business_modules_json TEXT NOT NULL DEFAULT '[]',
                    key_people_json TEXT NOT NULL DEFAULT '[]',
                    key_products_json TEXT NOT NULL DEFAULT '[]',
                    current_challenges_json TEXT NOT NULL DEFAULT '[]',
                    collaboration_goals_json TEXT NOT NULL DEFAULT '[]',
                    recent_facts_json TEXT NOT NULL DEFAULT '[]',
                    information_gaps_json TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_org_notebooks_client
                    ON organization_notebook_snapshots(client_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS event_line_memory_snapshots (
                    id TEXT PRIMARY KEY,
                    event_line_id TEXT NOT NULL UNIQUE,
                    line_name TEXT NOT NULL,
                    current_stage TEXT NOT NULL DEFAULT '',
                    current_work TEXT NOT NULL DEFAULT '',
                    current_blocker TEXT NOT NULL DEFAULT '',
                    recent_decision TEXT NOT NULL DEFAULT '',
                    next_step TEXT NOT NULL DEFAULT '',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    clarification_needs_json TEXT NOT NULL DEFAULT '[]',
                    analysis_signals_json TEXT NOT NULL DEFAULT '[]',
                    prediction_readiness REAL NOT NULL DEFAULT 0.0,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_event_line_memory_event_line
                    ON event_line_memory_snapshots(event_line_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS event_line_attachments (
                    id TEXT PRIMARY KEY,
                    event_line_id TEXT NOT NULL,
                    document_id TEXT,
                    file_name TEXT NOT NULL DEFAULT '',
                    file_type TEXT NOT NULL DEFAULT '',
                    display_mode TEXT NOT NULL DEFAULT 'collapsed',
                    description TEXT NOT NULL DEFAULT '',
                    uploaded_by TEXT NOT NULL DEFAULT '',
                    uploaded_at TEXT NOT NULL DEFAULT '',
                    local_path TEXT,
                    preview_url TEXT,
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_el_attachments_line
                    ON event_line_attachments(event_line_id);

                CREATE TABLE IF NOT EXISTS event_line_approval_nodes (
                    id TEXT PRIMARY KEY,
                    event_line_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    requested_by TEXT NOT NULL DEFAULT '',
                    approver_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    resolved_at TEXT,
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_el_approvals_line
                    ON event_line_approval_nodes(event_line_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS memory_facts (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    freshness REAL NOT NULL DEFAULT 0.0,
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    valid_from TEXT,
                    valid_to TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope_type, scope_id, fact_key, source_type, source_id)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_facts_scope
                    ON memory_facts(scope_type, scope_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS clarification_records (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    slot_key TEXT NOT NULL,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    answer_text TEXT,
                    write_scope_json TEXT NOT NULL DEFAULT '[]',
                    resolved_fact_ids_json TEXT NOT NULL DEFAULT '[]',
                    reusable INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    answered_at TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_clarification_scope
                    ON clarification_records(scope_type, scope_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS strategic_cockpit_snapshots (
                    client_id TEXT PRIMARY KEY,
                    week_summary TEXT NOT NULL DEFAULT '',
                    main_contradiction TEXT NOT NULL DEFAULT '',
                    core_breakthrough TEXT NOT NULL DEFAULT '',
                    focus_items_json TEXT NOT NULL DEFAULT '[]',
                    confirmed_by_user_id TEXT,
                    confirmed_by_user_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_strategic_cockpit_snapshots_updated
                    ON strategic_cockpit_snapshots(updated_at DESC);

                CREATE TABLE IF NOT EXISTS strategic_thought_reviews (
                    id TEXT PRIMARY KEY,
                    thought_id TEXT NOT NULL UNIQUE,
                    client_id TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    note TEXT NOT NULL DEFAULT '',
                    task_id TEXT,
                    judgment_id TEXT,
                    source_type TEXT NOT NULL DEFAULT '',
                    source_id TEXT NOT NULL DEFAULT '',
                    reviewed_by_id TEXT NOT NULL DEFAULT '',
                    reviewed_by_name TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_strategic_thought_reviews_client_status
                    ON strategic_thought_reviews(client_id, status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_strategic_thought_reviews_thought
                    ON strategic_thought_reviews(thought_id);

                CREATE TABLE IF NOT EXISTS strategic_thought_insights (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL DEFAULT 'client',
                    client_id TEXT,
                    client_name TEXT NOT NULL DEFAULT '',
                    project_module_id TEXT,
                    project_module_name TEXT,
                    title TEXT NOT NULL,
                    insight_type TEXT NOT NULL DEFAULT 'strategic_shift',
                    insight_text TEXT NOT NULL,
                    future_judgment TEXT NOT NULL DEFAULT '',
                    recommended_action TEXT NOT NULL DEFAULT '',
                    evidence_summary TEXT NOT NULL DEFAULT '',
                    evidence_labels_json TEXT NOT NULL DEFAULT '[]',
                    source_refs_json TEXT NOT NULL DEFAULT '[]',
                    source_fingerprint TEXT NOT NULL DEFAULT '',
                    signal_score INTEGER NOT NULL DEFAULT 0,
                    raw_payload_json TEXT NOT NULL DEFAULT '{}',
                    is_favorite INTEGER NOT NULL DEFAULT 0,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    generated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(project_module_id) REFERENCES project_modules(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_strategic_thought_insights_scope
                    ON strategic_thought_insights(client_id, project_module_id, is_deleted, signal_score DESC, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_strategic_thought_insights_favorite
                    ON strategic_thought_insights(is_favorite, is_deleted, updated_at DESC);

                CREATE TABLE IF NOT EXISTS digital_asset_narrative_snapshots (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL DEFAULT '',
                    content_markdown TEXT NOT NULL DEFAULT '',
                    material_audit_json TEXT NOT NULL DEFAULT '{}',
                    quality_warnings_json TEXT NOT NULL DEFAULT '[]',
                    raw_output TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    generated_at TEXT NOT NULL,
                    failure_reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_digital_asset_narrative_client
                    ON digital_asset_narrative_snapshots(client_id, failure_reason, generated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_digital_asset_narrative_fingerprint
                    ON digital_asset_narrative_snapshots(client_id, source_fingerprint, generated_at DESC);

                CREATE TABLE IF NOT EXISTS project_modules (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    alias TEXT,
                    goal TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    owner_name TEXT,
                    deliverables_json TEXT NOT NULL DEFAULT '[]',
                    keywords_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_project_modules_client_updated
                    ON project_modules(client_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS project_flows (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    module_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    scenario TEXT NOT NULL DEFAULT '',
                    trigger_condition TEXT NOT NULL DEFAULT '',
                    steps_json TEXT NOT NULL DEFAULT '[]',
                    inputs_json TEXT NOT NULL DEFAULT '[]',
                    outputs_json TEXT NOT NULL DEFAULT '[]',
                    collaborators_json TEXT NOT NULL DEFAULT '[]',
                    risk_points_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(module_id) REFERENCES project_modules(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_project_flows_client_module_updated
                    ON project_flows(client_id, module_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS task_notes (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL UNIQUE,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_notes_cloud (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL UNIQUE,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_attachments (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    event_line_id TEXT,
                    document_id TEXT,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_attachments_task_created
                    ON task_attachments(task_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_attachments_event_line
                    ON task_attachments(event_line_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS task_attachments_cloud (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    event_line_id TEXT,
                    document_id TEXT,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_attachments_cloud_task_created
                    ON task_attachments_cloud(task_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_attachments_cloud_event_line
                    ON task_attachments_cloud(event_line_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS weekly_reviews (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    week_label TEXT NOT NULL,
                    operator_id TEXT NOT NULL DEFAULT '',
                    user_id TEXT NOT NULL DEFAULT '',
                    work_progress TEXT NOT NULL DEFAULT '',
                    work_blocker TEXT NOT NULL DEFAULT '',
                    blocker_type TEXT NOT NULL DEFAULT '',
                    work_direction TEXT NOT NULL DEFAULT '',
                    next_week_focus TEXT NOT NULL DEFAULT '',
                    support_needed TEXT NOT NULL DEFAULT '',
                    related_plan_ids_json TEXT NOT NULL DEFAULT '[]',
                    summary TEXT NOT NULL,
                    work_free_note TEXT NOT NULL DEFAULT '',
                    personal_growth_note TEXT NOT NULL DEFAULT '',
                    personal_private_note TEXT NOT NULL DEFAULT '',
                    submitted_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    sync_status TEXT NOT NULL DEFAULT 'local',
                    cloud_id TEXT,
                    cloud_payload_json TEXT NOT NULL DEFAULT '',
                    last_synced_at TEXT NOT NULL DEFAULT '',
                    last_cloud_version TEXT NOT NULL DEFAULT '',
                    pending_sync_action TEXT NOT NULL DEFAULT '',
                    last_sync_error TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS weekly_review_task_entries (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    review_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT '',
                    week_label TEXT NOT NULL,
                    content_domain TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    structured_note_json TEXT NOT NULL DEFAULT '{}',
                    reviewed_at TEXT NOT NULL,
                    task_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(review_id, task_id),
                    FOREIGN KEY(review_id) REFERENCES weekly_reviews(id) ON DELETE CASCADE,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS sync_outbox (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    queued_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    UNIQUE(entity_type, entity_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sync_outbox_queue
                    ON sync_outbox(updated_at ASC, queued_at ASC);

                CREATE TABLE IF NOT EXISTS sync_conflicts (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    cloud_id TEXT,
                    local_version TEXT NOT NULL DEFAULT '',
                    cloud_version TEXT NOT NULL DEFAULT '',
                    local_payload_json TEXT NOT NULL DEFAULT '{}',
                    cloud_payload_json TEXT NOT NULL DEFAULT '{}',
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (entity_type, entity_id)
                );

                CREATE TABLE IF NOT EXISTS task_smart_brief_action_adoptions (
                    source_task_id TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    adopted_by_user_id TEXT NOT NULL DEFAULT '',
                    created_task_id TEXT NOT NULL,
                    action_text TEXT NOT NULL DEFAULT '',
                    adopted_at TEXT NOT NULL,
                    PRIMARY KEY (source_task_id, action_key, adopted_by_user_id)
                );

                CREATE TABLE IF NOT EXISTS task_context_brief_snapshots (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    client_id TEXT,
                    event_line_id TEXT,
                    brief TEXT NOT NULL DEFAULT '',
                    should_display INTEGER NOT NULL DEFAULT 0,
                    material_pack_hash TEXT NOT NULL DEFAULT '',
                    used_project_signals_json TEXT NOT NULL DEFAULT '[]',
                    material_boundary TEXT NOT NULL DEFAULT '',
                    quality_flags_json TEXT NOT NULL DEFAULT '[]',
                    generation_model TEXT NOT NULL DEFAULT '',
                    generation_prompt_version TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_context_brief_task_hash
                    ON task_context_brief_snapshots(task_id, material_pack_hash, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_context_brief_client_updated
                    ON task_context_brief_snapshots(client_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS agent_weekly_plan_overrides (
                    id TEXT PRIMARY KEY,
                    week_label TEXT NOT NULL,
                    agent_key TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    plan_items_json TEXT NOT NULL DEFAULT '[]',
                    updated_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(week_label, agent_key)
                );

                CREATE TABLE IF NOT EXISTS topic_radars (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    time_range TEXT NOT NULL,
                    preferred_sources_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS topic_candidates (
                    id TEXT PRIMARY KEY,
                    radar_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_url TEXT,
                    published_at TEXT,
                    capture_method TEXT NOT NULL DEFAULT 'manual',
                    captured_by TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(radar_id) REFERENCES topic_radars(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS topic_candidate_insights (
                    id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL UNIQUE,
                    overview TEXT NOT NULL,
                    key_points_json TEXT NOT NULL,
                    recommendation_reasons_json TEXT NOT NULL,
                    practical_uses_json TEXT NOT NULL,
                    editorial_note TEXT NOT NULL DEFAULT '',
                    discussion_prompts_json TEXT NOT NULL DEFAULT '[]',
                    source_excerpt TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES topic_candidates(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS topic_candidate_seen (
                    id TEXT PRIMARY KEY,
                    radar_id TEXT NOT NULL,
                    source_url_key TEXT NOT NULL DEFAULT '',
                    title_source_key TEXT NOT NULL DEFAULT '',
                    source_url TEXT,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    deleted_at TEXT,
                    FOREIGN KEY(radar_id) REFERENCES topic_radars(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_topic_candidate_seen_radar_url_key
                    ON topic_candidate_seen(radar_id, source_url_key);
                CREATE INDEX IF NOT EXISTS idx_topic_candidate_seen_radar_title_source_key
                    ON topic_candidate_seen(radar_id, title_source_key);

                CREATE TABLE IF NOT EXISTS intelligence_profiles (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    org_id TEXT NOT NULL DEFAULT 'local_org',
                    client_id TEXT,
                    project_module_id TEXT,
                    radar_id TEXT,
                    title TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    opportunity_hypotheses_json TEXT NOT NULL DEFAULT '[]',
                    monitor_signals_json TEXT NOT NULL DEFAULT '[]',
                    search_intents_json TEXT NOT NULL DEFAULT '[]',
                    source_strategies_json TEXT NOT NULL DEFAULT '[]',
                    exclude_terms_json TEXT NOT NULL DEFAULT '[]',
                    feedback_summary_json TEXT NOT NULL DEFAULT '{}',
                    input_hash TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    confidence REAL NOT NULL DEFAULT 0,
                    generator TEXT NOT NULL DEFAULT 'rule',
                    error TEXT NOT NULL DEFAULT '',
                    last_generated_at TEXT,
                    last_trial_run_at TEXT,
                    last_trial_run_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    profile_kind TEXT NOT NULL DEFAULT 'auto',
                    admin_summary_override TEXT NOT NULL DEFAULT '',
                    admin_focus_json TEXT NOT NULL DEFAULT '[]',
                    admin_exclude_terms_json TEXT NOT NULL DEFAULT '[]',
                    admin_priority_urls_json TEXT NOT NULL DEFAULT '[]',
                    admin_push_enabled INTEGER NOT NULL DEFAULT 0,
                    admin_push_frequency TEXT NOT NULL DEFAULT 'manual',
                    admin_push_time TEXT,
                    admin_push_weekday INTEGER,
                    source_radar_id TEXT,
                    deleted_at TEXT,
                    admin_profile_refresh_enabled INTEGER NOT NULL DEFAULT 0,
                    admin_profile_refresh_frequency TEXT NOT NULL DEFAULT 'manual',
                    admin_profile_refresh_time TEXT,
                    admin_profile_refresh_weekday INTEGER,
                    work_context_json TEXT NOT NULL DEFAULT '[]',
                    priority_needs_json TEXT NOT NULL DEFAULT '[]',
                    target_beneficiaries_json TEXT NOT NULL DEFAULT '[]',
                    regions_json TEXT NOT NULL DEFAULT '[]',
                    opportunity_types_json TEXT NOT NULL DEFAULT '[]',
                    material_gaps_json TEXT NOT NULL DEFAULT '[]',
                    grounding_facts_json TEXT NOT NULL DEFAULT '[]',
                    UNIQUE(scope_type, scope_id),
                    FOREIGN KEY(radar_id) REFERENCES topic_radars(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_profiles_scope
                    ON intelligence_profiles(scope_type, scope_id);
                CREATE INDEX IF NOT EXISTS idx_intelligence_profiles_radar
                    ON intelligence_profiles(radar_id);

                CREATE TABLE IF NOT EXISTS analysis_templates (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    template_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    parent_run_id TEXT,
                    coach_payload_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(template_id) REFERENCES analysis_templates(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS handbook_entries (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    client_id TEXT,
                    source_object_type TEXT,
                    source_object_id TEXT,
                    source_title TEXT,
                    event_line_id TEXT,
                    event_line_name TEXT,
                    project_module_id TEXT,
                    project_module_name TEXT,
                    project_flow_id TEXT,
                    project_flow_name TEXT,
                    project_stage TEXT,
                    business_category TEXT,
                    ability_keys_json TEXT NOT NULL DEFAULT '[]',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    context_summary TEXT NOT NULL DEFAULT '',
                    reuse_count INTEGER NOT NULL DEFAULT 0,
                    last_reused_at TEXT,
                    author_user_id TEXT,
                    author_user_name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS growth_ability_profiles (
                    id TEXT PRIMARY KEY,
                    ability_key TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    stage_rules_json TEXT NOT NULL DEFAULT '[]',
                    positive_signals_json TEXT NOT NULL DEFAULT '[]',
                    negative_signals_json TEXT NOT NULL DEFAULT '[]',
                    weights_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS growth_signal_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    review_id TEXT,
                    task_id TEXT,
                    week_label TEXT NOT NULL DEFAULT '',
                    raw_text TEXT NOT NULL DEFAULT '',
                    context_json TEXT NOT NULL DEFAULT '{}',
                    dedupe_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_growth_signal_user_created
                    ON growth_signal_events(user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS growth_evidence_records (
                    id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL DEFAULT '',
                    ability_key TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    confidence TEXT NOT NULL DEFAULT 'medium',
                    reason TEXT NOT NULL DEFAULT '',
                    review_id TEXT,
                    task_id TEXT,
                    handbook_entry_id TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    contribution_tags_json TEXT NOT NULL DEFAULT '[]',
                    org_contribution_score INTEGER NOT NULL DEFAULT 0,
                    suggested_premium_rate REAL NOT NULL DEFAULT 0,
                    validation_state TEXT NOT NULL DEFAULT 'candidate',
                    ai_reason TEXT NOT NULL DEFAULT '',
                    ai_confidence REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(signal_id) REFERENCES growth_signal_events(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_growth_evidence_user_ability_created
                    ON growth_evidence_records(user_id, ability_key, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_growth_evidence_review
                    ON growth_evidence_records(review_id);

                CREATE TABLE IF NOT EXISTS xp_ledger (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL DEFAULT '',
                    ability_key TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    xp_type TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    base_xp INTEGER NOT NULL DEFAULT 0,
                    premium_rate REAL NOT NULL DEFAULT 0,
                    premium_xp INTEGER NOT NULL DEFAULT 0,
                    total_xp INTEGER NOT NULL DEFAULT 0,
                    contribution_tags_json TEXT NOT NULL DEFAULT '[]',
                    validation_state TEXT NOT NULL DEFAULT 'candidate',
                    org_contribution_score INTEGER NOT NULL DEFAULT 0,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    week_label TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    reversed_at TEXT,
                    FOREIGN KEY(evidence_id) REFERENCES growth_evidence_records(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_xp_ledger_user_created
                    ON xp_ledger(user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS growth_validation_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL DEFAULT '',
                    actor_name TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL DEFAULT '',
                    source_id TEXT,
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(evidence_id) REFERENCES growth_evidence_records(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_growth_validation_evidence_created
                    ON growth_validation_events(evidence_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS growth_capture_states (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    signal_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'open',
                    reason TEXT NOT NULL DEFAULT '',
                    promoted_handbook_entry_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(signal_id) REFERENCES growth_signal_events(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_growth_capture_state_user_status_updated
                    ON growth_capture_states(user_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS badge_unlock_records (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL DEFAULT '',
                    badge_id TEXT NOT NULL,
                    badge_code TEXT NOT NULL,
                    badge_name TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    ability_key TEXT NOT NULL,
                    xp INTEGER NOT NULL DEFAULT 0,
                    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                    unlocked_at TEXT NOT NULL,
                    historical INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, badge_id)
                );
                CREATE INDEX IF NOT EXISTS idx_badge_unlock_user_created
                    ON badge_unlock_records(user_id, unlocked_at DESC);

                CREATE TABLE IF NOT EXISTS learning_content_items (
                    id TEXT PRIMARY KEY,
                    content_type TEXT NOT NULL,
                    ability_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    body TEXT NOT NULL,
                    practice_task TEXT NOT NULL DEFAULT '',
                    acceptance_criteria_json TEXT NOT NULL DEFAULT '[]',
                    source_kind TEXT NOT NULL DEFAULT 'system_rule',
                    source_ref_id TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_content_ability_status
                    ON learning_content_items(ability_key, status);

                CREATE TABLE IF NOT EXISTS learning_recommendations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL DEFAULT '',
                    ability_key TEXT NOT NULL,
                    content_item_id TEXT NOT NULL,
                    trigger_source_type TEXT NOT NULL,
                    trigger_source_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    linked_task_id TEXT,
                    client_id TEXT,
                    client_name TEXT,
                    event_line_id TEXT,
                    event_line_name TEXT,
                    project_stage TEXT,
                    trigger_node TEXT,
                    why_now TEXT NOT NULL DEFAULT '',
                    linked_contexts_json TEXT NOT NULL DEFAULT '[]',
                    priority TEXT NOT NULL DEFAULT 'normal',
                    status TEXT NOT NULL DEFAULT 'active',
                    accepted_task_id TEXT,
                    dismissed_reason TEXT,
                    dedupe_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(content_item_id) REFERENCES learning_content_items(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_learning_recommendations_user_status
                    ON learning_recommendations(user_id, status, created_at DESC);

                CREATE TABLE IF NOT EXISTS activity_logs (
                    id TEXT PRIMARY KEY,
                    actor_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_understanding_cache (
                    task_id TEXT PRIMARY KEY,
                    snapshot_json TEXT NOT NULL,
                    task_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS client_strategic_profiles (
                    client_id TEXT PRIMARY KEY,
                    industry TEXT NOT NULL DEFAULT '',
                    scale TEXT NOT NULL DEFAULT '',
                    influence TEXT NOT NULL DEFAULT '',
                    current_needs TEXT NOT NULL DEFAULT '',
                    pain_points TEXT NOT NULL DEFAULT '',
                    strategic_value_to_yiyu TEXT NOT NULL DEFAULT '',
                    decision_chain TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS cooperation_relationships (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    client_name TEXT NOT NULL DEFAULT '',
                    why_connected TEXT NOT NULL DEFAULT '',
                    meaning_to_yiyu TEXT NOT NULL DEFAULT '',
                    meaning_to_client TEXT NOT NULL DEFAULT '',
                    cooperation_type TEXT NOT NULL DEFAULT 'exploring',
                    relationship_health TEXT NOT NULL DEFAULT 'steady',
                    key_stakeholders_json TEXT NOT NULL DEFAULT '[]',
                    milestones TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS event_line_weekly_snapshots (
                    id TEXT PRIMARY KEY,
                    event_line_id TEXT NOT NULL,
                    event_line_name TEXT NOT NULL DEFAULT '',
                    week_label TEXT NOT NULL,
                    stage_at_that_time TEXT NOT NULL DEFAULT '',
                    key_decisions_json TEXT NOT NULL DEFAULT '[]',
                    turning_points_json TEXT NOT NULL DEFAULT '[]',
                    blockers_then_json TEXT NOT NULL DEFAULT '[]',
                    progress_delta TEXT NOT NULL DEFAULT '',
                    task_count INTEGER NOT NULL DEFAULT 0,
                    completed_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT '',
                    UNIQUE(event_line_id, week_label),
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_el_weekly_snapshots_line_week
                    ON event_line_weekly_snapshots(event_line_id, week_label DESC);

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_master_index_fts USING fts5(
                    entry_id UNINDEXED,
                    client_id UNINDEXED,
                    title,
                    retrieval_summary,
                    searchable_text,
                    folder_category,
                    document_role,
                    tokenize = 'unicode61'
                );

                -- 迭代 2：跨文档实体抽取
                -- entities = 客户范围内归一化后的实体（person / company / project / product /
                -- competitor / amount / date）；同 (client_id, entity_type, normalized_name) 唯一
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    attributes_json TEXT NOT NULL DEFAULT '{}',
                    mention_count INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_client_type_name
                    ON entities(client_id, entity_type, normalized_name);
                CREATE INDEX IF NOT EXISTS idx_entities_client_status
                    ON entities(client_id, status);
                CREATE INDEX IF NOT EXISTS idx_entities_last_seen
                    ON entities(client_id, last_seen_at DESC);

                -- entity_mentions = 每条实体在某 chunk / 文档里的具体出现
                CREATE TABLE IF NOT EXISTS entity_mentions (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    v2_document_id TEXT NOT NULL,
                    v2_chunk_id TEXT,
                    mention_text TEXT NOT NULL,
                    position_start INTEGER,
                    position_end INTEGER,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY(v2_document_id) REFERENCES v2_documents(id) ON DELETE CASCADE,
                    FOREIGN KEY(v2_chunk_id) REFERENCES v2_chunks(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity
                    ON entity_mentions(entity_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_entity_mentions_chunk
                    ON entity_mentions(v2_chunk_id);
                CREATE INDEX IF NOT EXISTS idx_entity_mentions_doc
                    ON entity_mentions(v2_document_id);
                """
            )
            # 迭代 2：v2_chunks 追加 entity_ids_json 字段（JSON 数组）
            self._ensure_column("v2_chunks", "entity_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("documents", "original_source_path", "TEXT")
            self._ensure_column("client_folders", "folder_kind", "TEXT NOT NULL DEFAULT 'business'")
            self._ensure_column("client_folders", "source_type", "TEXT NOT NULL DEFAULT 'legacy'")
            self._ensure_column("client_folders", "is_system", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("client_folders", "is_hidden", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("client_folders", "sort_order", "INTEGER NOT NULL DEFAULT 100")
            self._ensure_column("client_folders", "created_by_rule", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("client_folders", "suggested", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("client_folders", "confidence", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("knowledge_documents", "import_source_path", "TEXT")
            self._ensure_column("knowledge_documents", "current_human_path", "TEXT")
            self._ensure_column("knowledge_documents", "human_folder_category", "TEXT")
            self._ensure_column("knowledge_documents", "reclassified_at", "TEXT")
            self._ensure_column("knowledge_documents", "reclass_reason", "TEXT")
            self._ensure_column("analysis_runs", "parent_run_id", "TEXT")
            self._ensure_column("analysis_runs", "coach_payload_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("handbook_entries", "source_object_type", "TEXT")
            self._ensure_column("handbook_entries", "source_object_id", "TEXT")
            self._ensure_column("handbook_entries", "source_title", "TEXT")
            self._ensure_column("handbook_entries", "event_line_id", "TEXT")
            self._ensure_column("handbook_entries", "event_line_name", "TEXT")
            self._ensure_column("handbook_entries", "project_module_id", "TEXT")
            self._ensure_column("handbook_entries", "project_module_name", "TEXT")
            self._ensure_column("handbook_entries", "project_flow_id", "TEXT")
            self._ensure_column("handbook_entries", "project_flow_name", "TEXT")
            self._ensure_column("handbook_entries", "project_stage", "TEXT")
            self._ensure_column("handbook_entries", "business_category", "TEXT")
            self._ensure_column("handbook_entries", "ability_keys_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("handbook_entries", "evidence_refs_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("handbook_entries", "context_summary", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("handbook_entries", "reuse_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("handbook_entries", "last_reused_at", "TEXT")
            self._ensure_column("learning_recommendations", "linked_task_id", "TEXT")
            self._ensure_column("learning_recommendations", "client_id", "TEXT")
            self._ensure_column("learning_recommendations", "client_name", "TEXT")
            self._ensure_column("learning_recommendations", "event_line_id", "TEXT")
            self._ensure_column("learning_recommendations", "event_line_name", "TEXT")
            self._ensure_column("learning_recommendations", "project_stage", "TEXT")
            self._ensure_column("learning_recommendations", "trigger_node", "TEXT")
            self._ensure_column("learning_recommendations", "why_now", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("learning_recommendations", "linked_contexts_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("knowledge_documents", "reclass_confidence", "REAL NOT NULL DEFAULT 0.0")
            # 迭代 2 F3：版本链字段。lifecycle_status 控制检索是否召回；
            # version_chain_id 同一份资料的所有版本共享；version_number 是顺序号。
            self._ensure_column("knowledge_documents", "lifecycle_status", "TEXT NOT NULL DEFAULT 'current'")
            self._ensure_column("knowledge_documents", "superseded_by_id", "TEXT")
            self._ensure_column("knowledge_documents", "version_chain_id", "TEXT")
            self._ensure_column("knowledge_documents", "version_number", "INTEGER NOT NULL DEFAULT 1")
            # 索引：检索默认 WHERE lifecycle_status='current' 必须命中索引
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_docs_lifecycle "
                "ON knowledge_documents(client_id, lifecycle_status)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_knowledge_docs_chain "
                "ON knowledge_documents(version_chain_id, version_number DESC)"
            )
            # 一次性 backfill：把已有文档的 version_chain_id 设为自己的 id
            # （每份资料独立成链）。lifecycle_status 在 ALTER 时已默认 'current'。
            self.conn.execute(
                "UPDATE knowledge_documents SET version_chain_id = id "
                "WHERE version_chain_id IS NULL"
            )
            # 迭代 2 F1+F2：imports 表拆分跳过原因（duplicate / unsupported / version_upgrade）
            self._ensure_column("imports", "duplicate_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("imports", "unsupported_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("imports", "version_upgrade_count", "INTEGER NOT NULL DEFAULT 0")
            # 修复：document_cards 缺 9 个列（多处 SELECT 引用但 schema 未建）
            self._ensure_column("document_cards", "purpose", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("document_cards", "audience", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("document_cards", "project_context", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("document_cards", "key_topics_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("document_cards", "good_questions_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("document_cards", "risk_notes", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("document_cards", "generated_model", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("document_cards", "input_hash", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("document_cards", "prompt_version", "TEXT NOT NULL DEFAULT ''")
            # 迭代 4：chunk 语义分类。fact / judgment / opinion / action /
            # question / conclusion / background / unclassified
            self._ensure_column("v2_chunks", "semantic_type", "TEXT NOT NULL DEFAULT 'unclassified'")
            self._ensure_column("v2_chunks", "semantic_confidence", "REAL NOT NULL DEFAULT 0.0")
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_v2_chunks_semantic_type "
                "ON v2_chunks(v2_document_id, semantic_type)"
            )
            # 迭代 5：关系三元组
            # subject 是实体；object 可以是实体（object_entity_id）或自由文本（object_text）
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS relationship_triples (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    subject_entity_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object_entity_id TEXT,
                    object_text TEXT,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    source_v2_chunk_id TEXT,
                    source_v2_document_id TEXT,
                    evidence_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(subject_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                    FOREIGN KEY(object_entity_id) REFERENCES entities(id) ON DELETE SET NULL,
                    FOREIGN KEY(source_v2_chunk_id) REFERENCES v2_chunks(id) ON DELETE SET NULL,
                    FOREIGN KEY(source_v2_document_id) REFERENCES v2_documents(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rel_triples_client_subject
                    ON relationship_triples(client_id, subject_entity_id, predicate);
                CREATE INDEX IF NOT EXISTS idx_rel_triples_client_object
                    ON relationship_triples(client_id, object_entity_id);
                CREATE INDEX IF NOT EXISTS idx_rel_triples_predicate
                    ON relationship_triples(client_id, predicate, created_at DESC);

                -- 迭代 6：原子事实 + 矛盾检测
                -- atomic_facts = (subject, attribute, value) 三元组，
                -- subject 可以是 entity_id 也可以是自由文本（如"客户"作为
                -- 通用 sentinel）
                CREATE TABLE IF NOT EXISTS atomic_facts (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    subject_entity_id TEXT,
                    subject_text TEXT NOT NULL,
                    attribute TEXT NOT NULL,
                    value_text TEXT NOT NULL,
                    value_normalized TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    source_v2_chunk_id TEXT,
                    source_v2_document_id TEXT,
                    evidence_text TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(subject_entity_id) REFERENCES entities(id) ON DELETE SET NULL,
                    FOREIGN KEY(source_v2_chunk_id) REFERENCES v2_chunks(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_atomic_facts_subject_attr
                    ON atomic_facts(client_id, subject_text, attribute, status);
                CREATE INDEX IF NOT EXISTS idx_atomic_facts_recent
                    ON atomic_facts(client_id, created_at DESC);

                -- fact_contradictions = 两条事实之间的冲突记录
                -- contradiction_type: value_diff / temporal / scope
                -- review_status: pending / dismissed / resolved
                CREATE TABLE IF NOT EXISTS fact_contradictions (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    fact_a_id TEXT NOT NULL,
                    fact_b_id TEXT NOT NULL,
                    contradiction_type TEXT NOT NULL DEFAULT 'value_diff',
                    severity TEXT NOT NULL DEFAULT 'medium',
                    review_status TEXT NOT NULL DEFAULT 'pending',
                    resolution_note TEXT,
                    detected_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(fact_a_id) REFERENCES atomic_facts(id) ON DELETE CASCADE,
                    FOREIGN KEY(fact_b_id) REFERENCES atomic_facts(id) ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_contradictions_pair
                    ON fact_contradictions(client_id, fact_a_id, fact_b_id);
                CREATE INDEX IF NOT EXISTS idx_fact_contradictions_pending
                    ON fact_contradictions(client_id, review_status, detected_at DESC);

                -- 迭代 3：实体合并日志（审计 + undo 用）
                CREATE TABLE IF NOT EXISTS entity_merge_log (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    surviving_entity_id TEXT NOT NULL,
                    merged_entity_id TEXT NOT NULL,
                    mentions_moved INTEGER NOT NULL DEFAULT 0,
                    triples_moved INTEGER NOT NULL DEFAULT 0,
                    facts_moved INTEGER NOT NULL DEFAULT 0,
                    merge_reason TEXT,
                    merged_by TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(surviving_entity_id) REFERENCES entities(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_entity_merge_log_client
                    ON entity_merge_log(client_id, created_at DESC);

                -- 修复：补建 document_path_optimizations 表
                -- 代码里多处 SELECT/INSERT 引用此表，但 schema 一直没建。
                -- 是 local_model_optimizer 在用的"路径优化"功能，按 INSERT
                -- 语句的列序还原 schema。表为空时所有 LEFT JOIN 都返回
                -- NULL，等同于"功能未启用"，不影响主流程。
                CREATE TABLE IF NOT EXISTS document_path_optimizations (
                    id TEXT PRIMARY KEY,
                    knowledge_document_id TEXT NOT NULL UNIQUE,
                    client_id TEXT NOT NULL DEFAULT '',
                    virtual_path TEXT NOT NULL DEFAULT '',
                    classification_tags_json TEXT NOT NULL DEFAULT '[]',
                    recommended_owner TEXT NOT NULL DEFAULT '',
                    recommended_project TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    reason TEXT NOT NULL DEFAULT '',
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    apply_status TEXT NOT NULL DEFAULT 'pending_confirmation',
                    generated_model TEXT NOT NULL DEFAULT '',
                    input_hash TEXT NOT NULL DEFAULT '',
                    prompt_version TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(knowledge_document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_document_path_optimizations_client
                    ON document_path_optimizations(client_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_document_path_optimizations_kd
                    ON document_path_optimizations(knowledge_document_id);

                -- 修复：补建 local_model_tasks 表（local_model_optimizer 用）
                CREATE TABLE IF NOT EXISTS local_model_tasks (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    client_id TEXT NOT NULL DEFAULT '',
                    knowledge_document_id TEXT NOT NULL DEFAULT '',
                    model_profile_id TEXT NOT NULL DEFAULT '',
                    model_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    input_hash TEXT NOT NULL DEFAULT '',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    last_error TEXT,
                    locked_by TEXT,
                    locked_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(task_type, knowledge_document_id, input_hash)
                );
                CREATE INDEX IF NOT EXISTS idx_local_model_tasks_status
                    ON local_model_tasks(status, priority DESC, created_at ASC);
                CREATE INDEX IF NOT EXISTS idx_local_model_tasks_client
                    ON local_model_tasks(client_id, status);

                -- 迭代 7：客户私有术语库
                -- term: 原始术语；normalized_term: 归一化（用于 dedup + 查找）
                -- definition: 术语含义解释；aliases: 别名列表（用于检索时召回）
                CREATE TABLE IF NOT EXISTS client_glossary (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    term TEXT NOT NULL,
                    normalized_term TEXT NOT NULL,
                    definition TEXT NOT NULL DEFAULT '',
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    category TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_client_glossary_client_term
                    ON client_glossary(client_id, normalized_term);
                """
            )
            self._ensure_column("v2_documents", "markdown_path", "TEXT")
            self._ensure_column("v2_documents", "markdown_content", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("answer_runs", "retrieval_mode", "TEXT NOT NULL DEFAULT 'legacy'")
            self._ensure_column("answer_runs", "llm_invoked", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("answer_runs", "provider_used", "TEXT")
            self._ensure_column("answer_runs", "failure_reason", "TEXT")
            self._ensure_column("answer_citations", "source_stage", "TEXT NOT NULL DEFAULT 'raw_chunk'")
            self._ensure_column("answer_citations", "drillthrough_used", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("chat_messages", "llm_invoked", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("chat_messages", "provider_used", "TEXT")
            self._ensure_column("chat_messages", "answer_mode", "TEXT")
            self._ensure_column("chat_messages", "evidence_status", "TEXT")
            self._ensure_column("chat_messages", "failure_reason", "TEXT")
            self._ensure_column("chat_messages", "timing_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("chat_messages", "retrieval_summary_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("execution_tickets", "idempotency_key", "TEXT")
            self._ensure_column("execution_tickets", "retry_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("execution_tickets", "max_retries", "INTEGER NOT NULL DEFAULT 3")
            self._ensure_column("execution_tickets", "last_error", "TEXT")
            self._ensure_column("execution_tickets", "last_attempt_at", "TEXT")
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_execution_tickets_idempotency
                ON execution_tickets(idempotency_key, updated_at DESC)
                """
            )
            self._ensure_column("topic_candidates", "source_url", "TEXT")
            self._ensure_column("topic_candidates", "published_at", "TEXT")
            self._ensure_column("topic_candidates", "capture_method", "TEXT NOT NULL DEFAULT 'manual'")
            self._ensure_column("topic_candidates", "captured_by", "TEXT")
            self._ensure_column("topic_candidates", "insight_status", "TEXT NOT NULL DEFAULT 'pending'")
            self._ensure_column("topic_candidates", "insight_updated_at", "TEXT")
            self._ensure_column("topic_candidates", "insight_error", "TEXT")
            self._ensure_column("topic_radars", "preferred_sources_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("topic_candidate_insights", "editorial_note", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("topic_candidate_insights", "discussion_prompts_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("topic_candidate_insights", "advisor_memo", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("topic_candidates", "deep_analysis_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("intelligence_profiles", "profile_kind", "TEXT NOT NULL DEFAULT 'auto'")
            self._ensure_column("intelligence_profiles", "admin_summary_override", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("intelligence_profiles", "admin_focus_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "admin_exclude_terms_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "admin_priority_urls_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "admin_push_enabled", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("intelligence_profiles", "admin_push_frequency", "TEXT NOT NULL DEFAULT 'manual'")
            self._ensure_column("intelligence_profiles", "admin_push_time", "TEXT")
            self._ensure_column("intelligence_profiles", "admin_push_weekday", "INTEGER")
            self._ensure_column("intelligence_profiles", "source_radar_id", "TEXT")
            self._ensure_column("intelligence_profiles", "deleted_at", "TEXT")
            self._ensure_column("intelligence_profiles", "admin_profile_refresh_enabled", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("intelligence_profiles", "admin_profile_refresh_frequency", "TEXT NOT NULL DEFAULT 'manual'")
            self._ensure_column("intelligence_profiles", "admin_profile_refresh_time", "TEXT")
            self._ensure_column("intelligence_profiles", "admin_profile_refresh_weekday", "INTEGER")
            self._ensure_column("intelligence_profiles", "work_context_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "priority_needs_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "target_beneficiaries_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "regions_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "opportunity_types_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "material_gaps_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_profiles", "grounding_facts_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("task_tags", "scope", "TEXT NOT NULL DEFAULT 'org'")
            self._ensure_column("task_tags", "color", "TEXT NOT NULL DEFAULT '#5B7BFE'")
            self._ensure_column("task_tags", "owner_operator_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "operator_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "created_by", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "created_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "updated_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "archived_at", "TEXT")
            self._ensure_column("task_tags", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("task_tags", "cloud_id", "TEXT")
            self._ensure_column("task_tags", "cloud_payload_json", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "last_cloud_version", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_tags", "last_sync_error", "TEXT NOT NULL DEFAULT ''")
            self.conn.execute(
                """
                UPDATE task_tags
                SET operator_id = COALESCE(NULLIF(operator_id, ''), owner_operator_id, '')
                """
            )
            self.conn.execute(
                """
                UPDATE task_tags
                SET owner_operator_id = COALESCE(NULLIF(owner_operator_id, ''), operator_id, '')
                WHERE scope = 'self'
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_tags_operator_id
                ON task_tags(operator_id)
                """
            )
            self._ensure_column("task_lists", "is_default", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("task_lists", "scope", "TEXT NOT NULL DEFAULT 'org'")
            self._ensure_column("task_lists", "archived_at", "TEXT")
            self._ensure_column("task_lists", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_lists", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("task_lists", "cloud_id", "TEXT")
            self._ensure_column("task_lists", "cloud_payload_json", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_lists", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_lists", "last_cloud_version", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_lists", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_lists", "last_sync_error", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("clients", "color", "TEXT NOT NULL DEFAULT '#5B7BFE'")
            self._ensure_column("tasks", "tag_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("tasks", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "creator_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "owner_id", "TEXT")
            self._ensure_column("tasks", "progress_status", "TEXT NOT NULL DEFAULT 'todo'")
            self._ensure_column("tasks", "client_id", "TEXT")
            self._ensure_column("project_modules", "template_tasks_json", "TEXT")
            self._ensure_column("tasks", "project_module_id", "TEXT")
            self._ensure_column("tasks", "project_flow_id", "TEXT")
            self._ensure_column("tasks", "deadline_at", "TEXT")
            self._ensure_column("tasks", "scheduled_start_at", "TEXT")
            self._ensure_column("tasks", "scheduled_end_at", "TEXT")
            self._ensure_column("tasks", "completed_at", "TEXT")
            self._ensure_column("tasks", "start_date", "TEXT")
            self._ensure_column("tasks", "due_date", "TEXT")
            self._ensure_column("tasks", "duration_minutes", "INTEGER NOT NULL DEFAULT 60")
            self._ensure_column("tasks", "scope_mode", "TEXT NOT NULL DEFAULT 'COLLAB_SHARED'")
            self._ensure_column("tasks", "event_line_id", "TEXT")
            self._ensure_column("tasks", "business_category", "TEXT")
            self._ensure_column("tasks", "current_blocker", "TEXT")
            self._ensure_column("tasks", "next_action", "TEXT")
            self._ensure_column("tasks", "recent_decision", "TEXT")
            self._ensure_column("tasks", "evidence_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("tasks", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("tasks", "cloud_id", "TEXT")
            self._ensure_column("tasks", "cloud_payload_json", "TEXT")
            self._ensure_column("tasks", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "last_cloud_version", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "last_sync_error", "TEXT NOT NULL DEFAULT ''")
            self.conn.execute(
                """
                UPDATE tasks
                SET deadline_at = due_date
                WHERE deadline_at IS NULL
                  AND due_date IS NOT NULL
                  AND due_date != ''
                  AND (start_date IS NULL OR start_date = '')
                  AND due_date GLOB '????-??-??'
                """
            )
            self.conn.execute(
                """
                UPDATE tasks
                SET scheduled_start_at = COALESCE(NULLIF(start_date, ''), due_date)
                WHERE scheduled_start_at IS NULL
                  AND (
                    (start_date IS NOT NULL AND start_date != '')
                    OR due_date LIKE '%T%'
                    OR due_date GLOB '????-??-?? ??:??*'
                  )
                """
            )
            self.conn.execute(
                """
                UPDATE tasks
                SET scheduled_end_at = due_date
                WHERE scheduled_end_at IS NULL
                  AND start_date IS NOT NULL
                  AND start_date != ''
                  AND due_date IS NOT NULL
                  AND due_date != ''
                  AND due_date != start_date
                  AND (due_date LIKE '%T%' OR due_date GLOB '????-??-?? ??:??*')
                """
            )
            self.conn.execute(
                """
                UPDATE tasks
                SET completed_at = COALESCE(NULLIF(updated_at, ''), datetime('now'))
                WHERE completed_at IS NULL
                  AND (status = 'done' OR progress_status = 'done')
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_collaborators (
                    task_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL DEFAULT '',
                    user_id TEXT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    order_index INTEGER NOT NULL DEFAULT 0,
                    is_owner INTEGER NOT NULL DEFAULT 0,
                    inbox_status TEXT NOT NULL DEFAULT 'pending',
                    return_reason TEXT,
                    handled_at TEXT,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (task_id, user_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
                """
            )
            self._ensure_column("event_lines", "business_category", "TEXT")
            self._ensure_column("event_lines", "current_blocker", "TEXT")
            self._ensure_column("event_lines", "recent_decision", "TEXT")
            self._ensure_column("event_lines", "evidence_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("event_lines", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_lines", "visibility_scope", "TEXT NOT NULL DEFAULT 'project_public'")
            self._ensure_column("event_lines", "closed_at", "TEXT")
            self._ensure_column("event_lines", "closed_by_user_id", "TEXT")
            self._ensure_column("event_lines", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("event_lines", "cloud_id", "TEXT")
            self._ensure_column("event_lines", "cloud_payload_json", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_lines", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_lines", "last_cloud_version", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_lines", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_lines", "last_sync_error", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_line_activities", "created_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_line_activities", "is_key", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("event_line_attachments", "document_id", "TEXT")
            # Backfill is_key: key events = task created, manual note, attachment
            self.conn.execute("""
                UPDATE event_line_activities SET is_key = 1
                WHERE is_key = 0 AND (
                    source_type IN ('manual_note', 'attachment')
                    OR (source_type = 'task_activity' AND json_extract(metadata_json, '$.eventType') = 'created')
                )
            """)
            # Ensure status changes and other task activities are system traces
            self.conn.execute("""
                UPDATE event_line_activities SET is_key = 0
                WHERE is_key = 1 AND source_type = 'task_activity'
                AND json_extract(metadata_json, '$.eventType') != 'created'
            """)
            self._ensure_column("client_dna_documents", "source_kind", "TEXT NOT NULL DEFAULT 'manual'")
            self._ensure_column("client_dna_documents", "missing_info_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("weekly_reviews", "operator_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "user_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "work_progress", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "work_blocker", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "blocker_type", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "work_direction", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "next_week_focus", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "support_needed", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "related_plan_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("weekly_reviews", "updated_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "work_free_note", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "personal_growth_note", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "personal_private_note", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "submitted_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("weekly_reviews", "cloud_id", "TEXT")
            self._ensure_column("weekly_reviews", "cloud_payload_json", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "last_cloud_version", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_reviews", "last_sync_error", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_review_task_entries", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_review_task_entries", "user_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("weekly_review_task_entries", "structured_note_json", "TEXT NOT NULL DEFAULT '{}'")
            for table_name in ("documents", "document_chunks", "v2_documents"):
                self._ensure_column(table_name, "document_family_id", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(table_name, "canonical_kind", "TEXT NOT NULL DEFAULT 'raw_file'")
                self._ensure_column(table_name, "origin_type", "TEXT NOT NULL DEFAULT 'file_import'")
                self._ensure_column(table_name, "origin_id", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(table_name, "is_searchable", "INTEGER NOT NULL DEFAULT 1")
            for table_name in ("documents", "v2_documents"):
                self._ensure_column(table_name, "organization_id", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(table_name, "department_id", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(table_name, "department_ids_json", "TEXT NOT NULL DEFAULT '[]'")
                self._ensure_column(table_name, "owner_user_id", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(table_name, "source_entity_type", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(table_name, "source_entity_id", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(table_name, "visibility_scope", "TEXT NOT NULL DEFAULT 'project_public'")
                self._ensure_column(table_name, "content_domain", "TEXT NOT NULL DEFAULT 'work'")
                self._ensure_column(table_name, "lifecycle_status", "TEXT NOT NULL DEFAULT 'active'")
            self._ensure_column("memory_facts", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("memory_facts", "department_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("memory_facts", "department_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("memory_facts", "owner_user_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("memory_facts", "source_entity_type", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("memory_facts", "source_entity_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("memory_facts", "visibility_scope", "TEXT NOT NULL DEFAULT 'project_public'")
            self._ensure_column("memory_facts", "content_domain", "TEXT NOT NULL DEFAULT 'work'")
            self._ensure_column("memory_facts", "lifecycle_status", "TEXT NOT NULL DEFAULT 'active'")
            self._ensure_column("memory_facts", "superseded_by_event_id", "TEXT NOT NULL DEFAULT ''")
            for table_name in ("documents", "v2_documents", "memory_facts"):
                rows = self.conn.execute(
                    f"""
                    SELECT id, department_id
                    FROM {table_name}
                    WHERE COALESCE(department_id, '') != ''
                      AND COALESCE(department_ids_json, '[]') IN ('', '[]')
                    """
                ).fetchall()
                for row in rows:
                    self.conn.execute(
                        f"UPDATE {table_name} SET department_ids_json = ? WHERE id = ?",
                        (to_json([str(row["department_id"])]), str(row["id"])),
                    )

            self.conn.execute(
                """
                UPDATE documents
                SET
                    document_family_id = CASE
                        WHEN COALESCE(document_family_id, '') != '' THEN document_family_id
                        ELSE 'doc:' || id
                    END,
                    canonical_kind = CASE
                        WHEN COALESCE(canonical_kind, '') != '' THEN canonical_kind
                        ELSE 'raw_file'
                    END,
                    origin_type = CASE
                        WHEN COALESCE(origin_type, '') != '' THEN origin_type
                        ELSE 'file_import'
                    END,
                    is_searchable = COALESCE(is_searchable, 1)
                """
            )
            self.conn.execute(
                """
                UPDATE document_chunks
                SET
                    document_family_id = COALESCE(
                        NULLIF(document_family_id, ''),
                        (
                            SELECT COALESCE(NULLIF(d.document_family_id, ''), 'doc:' || d.id)
                            FROM knowledge_documents kd
                            JOIN documents d ON d.id = kd.document_id
                            WHERE kd.id = document_chunks.knowledge_document_id
                            LIMIT 1
                        ),
                        'chunk:' || id
                    ),
                    canonical_kind = COALESCE(
                        NULLIF(canonical_kind, ''),
                        (
                            SELECT COALESCE(NULLIF(d.canonical_kind, ''), 'raw_file')
                            FROM knowledge_documents kd
                            JOIN documents d ON d.id = kd.document_id
                            WHERE kd.id = document_chunks.knowledge_document_id
                            LIMIT 1
                        ),
                        'raw_file'
                    ),
                    origin_type = COALESCE(
                        NULLIF(origin_type, ''),
                        (
                            SELECT COALESCE(NULLIF(d.origin_type, ''), 'file_import')
                            FROM knowledge_documents kd
                            JOIN documents d ON d.id = kd.document_id
                            WHERE kd.id = document_chunks.knowledge_document_id
                            LIMIT 1
                        ),
                        'file_import'
                    ),
                    origin_id = COALESCE(
                        NULLIF(origin_id, ''),
                        (
                            SELECT COALESCE(d.origin_id, '')
                            FROM knowledge_documents kd
                            JOIN documents d ON d.id = kd.document_id
                            WHERE kd.id = document_chunks.knowledge_document_id
                            LIMIT 1
                        ),
                        ''
                    ),
                    is_searchable = COALESCE(
                        is_searchable,
                        (
                            SELECT COALESCE(d.is_searchable, 1)
                            FROM knowledge_documents kd
                            JOIN documents d ON d.id = kd.document_id
                            WHERE kd.id = document_chunks.knowledge_document_id
                            LIMIT 1
                        ),
                        1
                    )
                """
            )
            self.conn.execute(
                """
                UPDATE v2_documents
                SET
                    document_family_id = COALESCE(
                        NULLIF(document_family_id, ''),
                        (
                            SELECT COALESCE(NULLIF(d.document_family_id, ''), 'doc:' || d.id)
                            FROM documents d
                            WHERE d.id = v2_documents.document_id
                            LIMIT 1
                        ),
                        'doc:' || document_id
                    ),
                    canonical_kind = COALESCE(
                        NULLIF(canonical_kind, ''),
                        (
                            SELECT COALESCE(NULLIF(d.canonical_kind, ''), 'raw_file')
                            FROM documents d
                            WHERE d.id = v2_documents.document_id
                            LIMIT 1
                        ),
                        'raw_file'
                    ),
                    origin_type = COALESCE(
                        NULLIF(origin_type, ''),
                        (
                            SELECT COALESCE(NULLIF(d.origin_type, ''), 'file_import')
                            FROM documents d
                            WHERE d.id = v2_documents.document_id
                            LIMIT 1
                        ),
                        'file_import'
                    ),
                    origin_id = COALESCE(
                        NULLIF(origin_id, ''),
                        (
                            SELECT COALESCE(d.origin_id, '')
                            FROM documents d
                            WHERE d.id = v2_documents.document_id
                            LIMIT 1
                        ),
                        ''
                    ),
                    is_searchable = COALESCE(
                        is_searchable,
                        (
                            SELECT COALESCE(d.is_searchable, 1)
                            FROM documents d
                            WHERE d.id = v2_documents.document_id
                            LIMIT 1
                        ),
                        1
                    )
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_family_search
                ON documents(client_id, document_family_id, canonical_kind, is_searchable)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_v2_documents_family_search
                ON v2_documents(client_id, document_family_id, canonical_kind, is_searchable)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_data_center_scope
                ON documents(client_id, visibility_scope, content_domain, lifecycle_status, created_at)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_v2_documents_data_center_scope
                ON v2_documents(client_id, visibility_scope, content_domain, lifecycle_status, updated_at)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_v2_documents_source_entity
                ON v2_documents(source_entity_type, source_entity_id, lifecycle_status, updated_at)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_facts_data_center_scope
                ON memory_facts(scope_type, scope_id, visibility_scope, content_domain, lifecycle_status, updated_at)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_access_scope
                ON documents(organization_id, department_id, owner_user_id, lifecycle_status, is_searchable)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_v2_documents_access_scope
                ON v2_documents(organization_id, department_id, owner_user_id, lifecycle_status, is_searchable)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_facts_access_scope
                ON memory_facts(organization_id, department_id, owner_user_id, lifecycle_status)
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_outbox (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    queued_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    UNIQUE(entity_type, entity_id)
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_conflicts (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    cloud_id TEXT,
                    local_version TEXT NOT NULL DEFAULT '',
                    cloud_version TEXT NOT NULL DEFAULT '',
                    local_payload_json TEXT NOT NULL DEFAULT '{}',
                    cloud_payload_json TEXT NOT NULL DEFAULT '{}',
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (entity_type, entity_id)
                )
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sync_outbox_queue
                ON sync_outbox(updated_at ASC, queued_at ASC)
                """
            )
            self._ensure_column("growth_evidence_records", "contribution_tags_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("growth_evidence_records", "org_contribution_score", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("growth_evidence_records", "suggested_premium_rate", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("growth_evidence_records", "validation_state", "TEXT NOT NULL DEFAULT 'candidate'")
            self._ensure_column("growth_evidence_records", "ai_reason", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_evidence_records", "ai_confidence", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("xp_ledger", "base_xp", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("xp_ledger", "premium_rate", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("xp_ledger", "premium_xp", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("xp_ledger", "total_xp", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("xp_ledger", "contribution_tags_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("xp_ledger", "validation_state", "TEXT NOT NULL DEFAULT 'candidate'")
            self._ensure_column("xp_ledger", "org_contribution_score", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("client_template_fill_runs", "processed_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("client_template_fill_runs", "current_field_label", "TEXT")
            self._ensure_column("handbook_entries", "author_user_id", "TEXT")
            self._ensure_column("handbook_entries", "author_user_name", "TEXT")
            self._ensure_column("topic_candidates", "event_line_id", "TEXT")
            self._ensure_column("memory_facts", "valid_from", "TEXT")
            self._ensure_column("memory_facts", "valid_to", "TEXT")
            self._ensure_column("analysis_jobs", "source_snapshot_hash", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("analysis_jobs", "dedupe_key", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("analysis_jobs", "intent_profile", "TEXT NOT NULL DEFAULT 'client_overview'")
            self._ensure_column("analysis_jobs", "locked_by", "TEXT")
            self._ensure_column("analysis_jobs", "locked_at", "TEXT")
            self._ensure_column("analysis_jobs", "lock_expires_at", "TEXT")
            self._ensure_column("analysis_jobs", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("analysis_jobs", "last_error", "TEXT")
            self._ensure_column("job_stage_runs", "correlation_id", "TEXT")
            self._ensure_column("evidence_cards", "normalized_claim_hash", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("evidence_cards", "source_ref_hash", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("evidence_cards", "evidence_fingerprint", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("evidence_cards", "normalizer_version", "TEXT NOT NULL DEFAULT 'analysis-center-v0.3.3'")
            for table_name in (
                "evidence_cards",
                "theme_clusters",
                "conflict_groups",
                "open_questions",
                "context_packs",
                "dna_deltas",
                "judgment_versions",
            ):
                self._ensure_column(table_name, "origin_type", "TEXT NOT NULL DEFAULT 'projection'")
                self._ensure_column(table_name, "authority_level", "TEXT NOT NULL DEFAULT 'fallback'")
                self._ensure_column(table_name, "quality_tier", "TEXT NOT NULL DEFAULT 'legacy'")
            for table_name in ("context_packs", "dna_deltas", "judgment_versions"):
                self._ensure_column(table_name, "supersedes_id", "TEXT")
                self._ensure_column(table_name, "source_snapshot_hash", "TEXT NOT NULL DEFAULT ''")
                self._ensure_column(table_name, "stale_reason", "TEXT")
                self._ensure_column(table_name, "invalidated_by", "TEXT")
            self._ensure_column("conflict_groups", "context_pack_id", "TEXT")
            self._ensure_column("runtime_run_logs", "analysis_job_id", "TEXT")
            self._ensure_column("runtime_run_logs", "stage_run_id", "TEXT")
            self._ensure_column("runtime_run_logs", "context_pack_id", "TEXT")
            self._ensure_column("runtime_run_logs", "judgment_version_id", "TEXT")
            self._ensure_column("runtime_run_logs", "correlation_id", "TEXT")
            self._ensure_column("approval_records", "approval_target_type", "TEXT")
            self._ensure_column("approval_records", "approval_target_id", "TEXT")
            self._ensure_column("approval_records", "policy_type", "TEXT NOT NULL DEFAULT 'analysis_review'")
            self._ensure_column("approval_records", "decision", "TEXT")
            self._ensure_column("approval_records", "comment", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("approval_records", "decided_by", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("approval_records", "decided_at", "TEXT")
            self._ensure_column("approval_records", "metadata_json", "TEXT NOT NULL DEFAULT '{}'")
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status_priority
                ON analysis_jobs(status, priority, updated_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_jobs_active_dedupe
                ON analysis_jobs(dedupe_key)
                WHERE status IN ('queued', 'running')
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_job_stage_runs_status
                ON job_stage_runs(job_id, stage_name, status, updated_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evidence_cards_event_line
                ON evidence_cards(client_id, event_line_id, updated_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evidence_cards_dedupe
                ON evidence_cards(client_id, scope_type, scope_id, evidence_fingerprint)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_theme_clusters_theme_key
                ON theme_clusters(client_id, theme_key, updated_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conflict_groups_severity
                ON conflict_groups(client_id, severity, updated_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_judgment_versions_status
                ON judgment_versions(client_id, target_type, target_id, status, updated_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_run_logs_job
                ON runtime_run_logs(job_id, created_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_approval_records_target_decided
                ON approval_records(approval_target_type, approval_target_id, decided_at DESC)
                """
            )
            current_schema_version = int(self.conn.execute("PRAGMA user_version").fetchone()[0] or 0)
            if current_schema_version < BACKEND_SCHEMA_VERSION:
                self.conn.execute(f"PRAGMA user_version={BACKEND_SCHEMA_VERSION}")
            analysis_truth_tables = (
                "evidence_cards",
                "theme_clusters",
                "conflict_groups",
                "open_questions",
                "context_packs",
                "dna_deltas",
                "judgment_versions",
            )
            for table_name in analysis_truth_tables:
                for operation in ("INSERT", "UPDATE"):
                    self.conn.execute(
                        f"""
                        CREATE TRIGGER IF NOT EXISTS trg_{table_name}_{operation.lower()}_truth_boundary
                        BEFORE {operation} ON {table_name}
                        FOR EACH ROW
                        WHEN
                            (NEW.origin_type = 'human_override' AND NEW.authority_level = 'fallback')
                            OR (NEW.authority_level = 'approved' AND NEW.quality_tier != 'reviewed')
                            OR (NEW.origin_type = 'projection' AND NEW.authority_level = 'approved')
                        BEGIN
                            SELECT RAISE(ABORT, 'invalid_analysis_truth_boundary');
                        END;
                        """
                    )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_settings (
                    operator_id TEXT PRIMARY KEY,
                    default_list_id TEXT,
                    default_priority TEXT NOT NULL DEFAULT 'normal',
                    default_due_date_preset TEXT NOT NULL DEFAULT 'today',
                    default_view_mode TEXT NOT NULL DEFAULT 'list',
                    list_sort_mode TEXT NOT NULL DEFAULT 'manual',
                    show_completed_tasks INTEGER NOT NULL DEFAULT 0,
                    default_review_scope TEXT NOT NULL DEFAULT 'work',
                    auto_assign_self INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(operator_id) REFERENCES operators(id) ON DELETE CASCADE,
                    FOREIGN KEY(default_list_id) REFERENCES task_lists(id) ON DELETE SET NULL
                );
                """
            )
            # === 输入广度线程（input-breadth）新增 ===
            # 语音识别模型配置：单行 org 级，provider + JSON credentials + JSON extra_config
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS speech_model_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    provider TEXT NOT NULL DEFAULT '',
                    credentials_json TEXT NOT NULL DEFAULT '{}',
                    model_id TEXT NOT NULL DEFAULT '',
                    extra_config_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                """
            )
            self.conn.execute(
                """
                INSERT OR IGNORE INTO speech_model_settings(id, provider, credentials_json, model_id, extra_config_json, enabled, updated_at)
                VALUES (1, '', '{}', '', '{}', 0, '')
                """
            )
            # 对象存储配置（I1b-1）：单行 org 级，承载音频文件中转所需的桶/凭证
            # 用 JSON 字段灵活承载，未来扩展阿里 OSS / AWS S3 等只需新建 provider 不动 schema
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS object_storage_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    provider TEXT NOT NULL DEFAULT '',
                    credentials_json TEXT NOT NULL DEFAULT '{}',
                    extra_config_json TEXT NOT NULL DEFAULT '{}',
                    enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                """
            )
            self.conn.execute(
                """
                INSERT OR IGNORE INTO object_storage_settings(id, provider, credentials_json, extra_config_json, enabled, updated_at)
                VALUES (1, '', '{}', '{}', 0, '')
                """
            )
            # ───────────────────────────────────────────────────────────────
            # 报告生成器（report-gen）· 状态机表
            # 对应执行计划：docs/报告生成器-Claude-Code执行计划-2026-05-12.md
            # report_runs: 一次报告生成任务的整体状态（含 blueprint + artifact）
            # report_section_runs: 每个章节的填充状态（支持单章节重跑/幂等）
            # ───────────────────────────────────────────────────────────────
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS report_runs (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    event_line_id TEXT,
                    period_start TEXT,
                    period_end TEXT,
                    intent_hint TEXT,
                    audience_hint TEXT,
                    tone_hint TEXT,
                    status TEXT NOT NULL DEFAULT 'blueprint_pending',
                    -- 状态机:
                    --   blueprint_pending → blueprint_confirmed → drafting
                    --   → rendered → published
                    --   任一阶段失败 → failed
                    blueprint_json TEXT,
                    artifact_json TEXT,
                    docx_path TEXT,
                    pdf_path TEXT,
                    md_path TEXT,
                    total_llm_tokens INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_report_runs_client
                ON report_runs(client_id, created_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_report_runs_event_line
                ON report_runs(event_line_id, created_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS report_section_runs (
                    id TEXT PRIMARY KEY,
                    report_run_id TEXT NOT NULL REFERENCES report_runs(id) ON DELETE CASCADE,
                    section_idx INTEGER NOT NULL,
                    plan_json TEXT NOT NULL,
                    content_json TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    -- 章节级状态: pending | drafting | done | failed
                    error_message TEXT,
                    llm_tokens INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT,
                    finished_at TEXT,
                    UNIQUE(report_run_id, section_idx)
                );
                """
            )
            self.conn.execute(
                "UPDATE task_lists SET is_default = CASE WHEN id = 'list-0' THEN 1 ELSE COALESCE(is_default, 0) END WHERE is_default IS NULL OR is_default = ''"
            )
            self.conn.execute(
                """
                UPDATE topic_candidates
                SET insight_status = CASE
                    WHEN id IN (SELECT candidate_id FROM topic_candidate_insights) THEN 'ready'
                    WHEN COALESCE(insight_status, '') = '' THEN 'pending'
                    ELSE insight_status
                END
                """
            )
            self.conn.execute(
                """
                INSERT OR IGNORE INTO topic_candidate_seen(
                    id, radar_id, source_url_key, title_source_key, source_url, title, source, created_at, deleted_at
                )
                SELECT
                    'seen_' || id,
                    radar_id,
                    LOWER(TRIM(COALESCE(source_url, ''))),
                    LOWER(TRIM(title)) || '||' || LOWER(TRIM(source)),
                    source_url,
                    title,
                    source,
                    created_at,
                    NULL
                FROM topic_candidates candidate
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM topic_candidate_seen seen
                    WHERE seen.radar_id = candidate.radar_id
                      AND (
                        (LOWER(TRIM(COALESCE(candidate.source_url, ''))) <> '' AND seen.source_url_key = LOWER(TRIM(COALESCE(candidate.source_url, ''))))
                        OR seen.title_source_key = LOWER(TRIM(candidate.title)) || '||' || LOWER(TRIM(candidate.source))
                      )
                )
                """
            )
            self.conn.commit()

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        existing = {
            str(row["name"])
            for row in self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing:
            return
        self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def has_column(self, table_name: str, column_name: str) -> bool:
        with self._lock:
            existing = {
                str(row["name"])
                for row in self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            return column_name in existing

    def ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        with self._lock:
            try:
                self._ensure_column(table_name, column_name, definition)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def get_schema_version(self) -> int:
        with self._lock:
            row = self.conn.execute("PRAGMA user_version").fetchone()
        return int(row[0] or 0) if row else 0

    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            cur = self.conn.execute(query, params)
            return cur.fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self.conn.execute(query, params)
            return cur.fetchall()

    def execute(self, query: str, params: tuple = ()) -> None:
        with self._lock:
            try:
                self.conn.execute(query, params)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def executemany(self, query: str, params: list[tuple]) -> None:
        with self._lock:
            try:
                self.conn.executemany(query, params)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def executescript(self, script: str) -> None:
        with self._lock:
            try:
                self.conn.executescript(script)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def run_in_transaction(self, callback, mode: str = "IMMEDIATE"):
        with self._lock:
            try:
                self.conn.execute(f"BEGIN {mode}")
                result = callback(self.conn)
                self.conn.commit()
                return result
            except Exception:
                self.conn.rollback()
                raise

    def scalar(self, query: str, params: tuple = ()) -> int:
        row = self.fetchone(query, params)
        if not row:
            return 0
        first_key = row.keys()[0]
        return int(row[first_key])

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return str(row["value"]) if row else default

    def backup_to(self, target_path: Path) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.conn.commit()
            shutil.copy2(self.db_path, target_path)
        return target_path


def to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value: str | None, default: object) -> object:
    if not value:
        return default
    return json.loads(value)
