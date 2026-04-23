from __future__ import annotations

import json
import re
import shutil
import sqlite3
import threading
from pathlib import Path


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

                -- ══ 同步表（任务/事件线/复盘 — 走云端） ══

                CREATE TABLE IF NOT EXISTS task_lists (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    color TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
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
                    list_id TEXT,
                    creator_id TEXT NOT NULL DEFAULT '',
                    owner_id TEXT,
                    owner_name TEXT NOT NULL,
                    progress_status TEXT NOT NULL DEFAULT 'todo',
                    ddl TEXT NOT NULL,
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

                CREATE TABLE IF NOT EXISTS task_list_links (
                    task_id TEXT NOT NULL,
                    list_id TEXT NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (task_id, list_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(list_id) REFERENCES task_lists(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_task_list_links_list
                    ON task_list_links(list_id, updated_at DESC);

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
                    owner_ids_json TEXT NOT NULL DEFAULT '[]',
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

                CREATE TABLE IF NOT EXISTS event_line_notifications (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    event_line_id TEXT NOT NULL,
                    event_line_name TEXT NOT NULL DEFAULT '',
                    operation_label TEXT NOT NULL DEFAULT '',
                    actor_id TEXT,
                    actor_name TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    main_owner_names_json TEXT NOT NULL DEFAULT '[]',
                    participant_names_json TEXT NOT NULL DEFAULT '[]',
                    operated_at TEXT NOT NULL,
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
                CREATE INDEX IF NOT EXISTS idx_event_line_notifications_org_created
                    ON event_line_notifications(organization_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_event_line_notifications_line_created
                    ON event_line_notifications(event_line_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS event_line_notification_receipts (
                    notification_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL DEFAULT '',
                    user_id TEXT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    read_at TEXT,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (notification_id, user_id),
                    FOREIGN KEY(notification_id) REFERENCES event_line_notifications(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_event_line_notification_receipts_user
                    ON event_line_notification_receipts(user_id, read_at, updated_at DESC);

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
                    file_name TEXT NOT NULL DEFAULT '',
                    file_type TEXT NOT NULL DEFAULT '',
                    display_mode TEXT NOT NULL DEFAULT 'collapsed',
                    description TEXT NOT NULL DEFAULT '',
                    uploaded_by TEXT NOT NULL DEFAULT '',
                    uploaded_at TEXT NOT NULL DEFAULT '',
                    local_path TEXT,
                    preview_url TEXT,
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE
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

                CREATE TABLE IF NOT EXISTS task_group_templates (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    scope TEXT NOT NULL DEFAULT 'local',
                    work_object_id TEXT,
                    name TEXT NOT NULL,
                    scenario_desc TEXT NOT NULL DEFAULT '',
                    steps_json TEXT NOT NULL DEFAULT '[]',
                    legacy_module_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'local',
                    cloud_id TEXT,
                    cloud_payload_json TEXT NOT NULL DEFAULT '',
                    last_synced_at TEXT NOT NULL DEFAULT '',
                    last_cloud_version TEXT NOT NULL DEFAULT '',
                    pending_sync_action TEXT NOT NULL DEFAULT '',
                    last_sync_error TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(work_object_id) REFERENCES clients(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_group_templates_scope_updated
                    ON task_group_templates(organization_id, scope, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_group_templates_legacy_module
                    ON task_group_templates(legacy_module_id);

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
                """
            )
            self._ensure_column("documents", "original_source_path", "TEXT")
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
            self._ensure_column("v2_documents", "markdown_path", "TEXT")
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
            self._ensure_column("task_tags", "scope", "TEXT NOT NULL DEFAULT 'org'")
            self._ensure_column("task_tags", "color", "TEXT NOT NULL DEFAULT '#5B7BFE'")
            self._ensure_column("task_tags", "owner_operator_id", "TEXT NOT NULL DEFAULT ''")
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
            self._ensure_column("task_lists", "description", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "tag_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("tasks", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "creator_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("tasks", "owner_id", "TEXT")
            self._ensure_column("tasks", "progress_status", "TEXT NOT NULL DEFAULT 'todo'")
            self._ensure_column("tasks", "client_id", "TEXT")
            self._ensure_column("project_modules", "template_tasks_json", "TEXT")
            self._ensure_column("tasks", "project_module_id", "TEXT")
            self._ensure_column("tasks", "project_flow_id", "TEXT")
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
            self._repair_stale_task_legacy_references()
            self._migrate_tasks_allow_empty_list_id()
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
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_list_links (
                    task_id TEXT NOT NULL,
                    list_id TEXT NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (task_id, list_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY(list_id) REFERENCES task_lists(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_task_list_links_list
                    ON task_list_links(list_id, updated_at DESC);
                """
            )
            self.conn.execute(
                """
                INSERT OR IGNORE INTO task_list_links(task_id, list_id, order_index, created_at, updated_at)
                SELECT id, list_id, 0, COALESCE(created_at, ''), COALESCE(updated_at, '')
                FROM tasks
                WHERE TRIM(COALESCE(list_id, '')) <> ''
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
            self._ensure_column("event_lines", "owner_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("event_line_notifications", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("event_line_notifications", "cloud_id", "TEXT")
            self._ensure_column("event_line_notifications", "cloud_payload_json", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_line_notifications", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_line_notifications", "last_cloud_version", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_line_notifications", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_line_notifications", "last_sync_error", "TEXT NOT NULL DEFAULT ''")
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_group_templates (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL DEFAULT '',
                    scope TEXT NOT NULL DEFAULT 'local',
                    work_object_id TEXT,
                    name TEXT NOT NULL,
                    scenario_desc TEXT NOT NULL DEFAULT '',
                    steps_json TEXT NOT NULL DEFAULT '[]',
                    legacy_module_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'local',
                    cloud_id TEXT,
                    cloud_payload_json TEXT NOT NULL DEFAULT '',
                    last_synced_at TEXT NOT NULL DEFAULT '',
                    last_cloud_version TEXT NOT NULL DEFAULT '',
                    pending_sync_action TEXT NOT NULL DEFAULT '',
                    last_sync_error TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(work_object_id) REFERENCES clients(id) ON DELETE SET NULL
                )
                """
            )
            self._ensure_column("task_group_templates", "organization_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_group_templates", "scope", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("task_group_templates", "work_object_id", "TEXT")
            self._ensure_column("task_group_templates", "scenario_desc", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_group_templates", "steps_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("task_group_templates", "legacy_module_id", "TEXT")
            self._ensure_column("task_group_templates", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("task_group_templates", "cloud_id", "TEXT")
            self._ensure_column("task_group_templates", "cloud_payload_json", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_group_templates", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_group_templates", "last_cloud_version", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_group_templates", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("task_group_templates", "last_sync_error", "TEXT NOT NULL DEFAULT ''")
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_group_templates_scope_updated
                ON task_group_templates(organization_id, scope, updated_at DESC)
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_task_group_templates_legacy_module
                ON task_group_templates(legacy_module_id)
                """
            )
            self._ensure_column("event_line_activities", "created_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("event_line_activities", "is_key", "INTEGER NOT NULL DEFAULT 0")
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
                INSERT INTO topic_candidate_seen(
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
            self._backfill_legacy_event_line_notifications()
            self._delete_legacy_event_line_notification_tasks()
            self.conn.commit()

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        existing = {
            str(row["name"])
            for row in self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing:
            return
        self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _rewrite_schema_sql(self, updates: list[tuple[str, str, str]]) -> None:
        if not updates:
            return
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.execute("PRAGMA writable_schema=ON")
        for obj_type, name, sql in updates:
            self.conn.execute(
                "UPDATE sqlite_master SET sql = ? WHERE type = ? AND name = ?",
                (sql, obj_type, name),
            )
        self.conn.execute("PRAGMA writable_schema=OFF")
        current_version = int(self.conn.execute("PRAGMA schema_version").fetchone()[0] or 0)
        self.conn.execute(f"PRAGMA schema_version = {current_version + 1}")
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys=ON")

    def _repair_stale_task_legacy_references(self) -> None:
        rows = self.conn.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE sql IS NOT NULL AND sql LIKE '%tasks_legacy_list_id%'
            """
        ).fetchall()
        updates: list[tuple[str, str, str]] = []
        for row in rows:
            raw_sql = str(row["sql"] or "")
            if "tasks_legacy_list_id" not in raw_sql:
                continue
            updates.append(
                (
                    str(row["type"]),
                    str(row["name"]),
                    raw_sql.replace("tasks_legacy_list_id", "tasks"),
                )
            )
        self._rewrite_schema_sql(updates)

    def _migrate_tasks_allow_empty_list_id(self) -> None:
        task_row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()
        if task_row is None:
            return
        task_sql = str(task_row["sql"] or "")
        if "list_id TEXT NOT NULL" not in task_sql:
            return
        self._rewrite_schema_sql(
            [("table", "tasks", task_sql.replace("list_id TEXT NOT NULL", "list_id TEXT"))]
        )

    def _parse_legacy_event_line_notification(self, title: str, description: str) -> dict[str, object]:
        values: dict[str, str] = {}
        for raw_line in description.splitlines():
            line = raw_line.strip()
            if not line or "：" not in line:
                continue
            label, value = line.split("：", 1)
            label = label.strip()
            value = value.strip()
            if label and value:
                values[label] = value
        operation = values.get("事件线操作", "").strip()
        if not operation:
            match = re.match(r"^事件线(.+?)：", title.strip())
            if match:
                operation = match.group(1).strip()
        return {
            "event_line_name": values.get("事件线标题", "").strip(),
            "operation_label": operation,
            "actor_name": values.get("操作者", "").strip(),
            "operated_at": values.get("操作时间", "").strip(),
            "main_owner_names": [item.strip() for item in values.get("主要负责人", "").split("、") if item.strip()],
            "participant_names": [item.strip() for item in values.get("参与者", "").split("、") if item.strip()],
        }

    def _backfill_legacy_event_line_notifications(self) -> None:
        rows = self.conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE source_type = 'event_line_notification'
            ORDER BY created_at ASC
            """
        ).fetchall()
        for row in rows:
            notification_id = str(row["id"] or "").strip()
            if not notification_id:
                continue
            existing = self.conn.execute(
                "SELECT 1 FROM event_line_notifications WHERE id = ?",
                (notification_id,),
            ).fetchone()
            if existing is not None:
                continue
            parsed = self._parse_legacy_event_line_notification(
                str(row["title"] or ""),
                str(row["description"] or ""),
            )
            event_line_id = str(row["event_line_id"] or row["source_id"] or "").strip()
            if not event_line_id:
                continue
            self.conn.execute(
                """
                INSERT INTO event_line_notifications(
                    id, organization_id, event_line_id, event_line_name, operation_label, actor_id, actor_name,
                    title, summary, metadata_json, main_owner_names_json, participant_names_json, operated_at,
                    created_at, updated_at, sync_status, cloud_id, cloud_payload_json, last_synced_at, last_cloud_version,
                    pending_sync_action, last_sync_error
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?, ?, ?, 'synced', ?, '{}', ?, ?, '', '')
                """,
                (
                    notification_id,
                    str(row["organization_id"] or ""),
                    event_line_id,
                    str(parsed["event_line_name"] or ""),
                    str(parsed["operation_label"] or ""),
                    str(row["creator_id"] or "") or None,
                    str(parsed["actor_name"] or ""),
                    str(row["title"] or ""),
                    str(row["description"] or ""),
                    json.dumps(parsed["main_owner_names"], ensure_ascii=False),
                    json.dumps(parsed["participant_names"], ensure_ascii=False),
                    str(parsed["operated_at"] or row["created_at"] or row["updated_at"] or ""),
                    str(row["created_at"] or ""),
                    str(row["updated_at"] or row["created_at"] or ""),
                    notification_id,
                    str(row["updated_at"] or row["created_at"] or ""),
                    str(row["updated_at"] or row["created_at"] or ""),
                ),
            )
            collaborator_rows = self.conn.execute(
                """
                SELECT user_id, full_name, email, handled_at, created_at, updated_at
                FROM task_collaborators
                WHERE task_id = ?
                ORDER BY order_index ASC
                """,
                (notification_id,),
            ).fetchall()
            for collaborator_row in collaborator_rows:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO event_line_notification_receipts(
                        notification_id, organization_id, user_id, full_name, email, read_at, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        notification_id,
                        str(row["organization_id"] or ""),
                        str(collaborator_row["user_id"] or ""),
                        str(collaborator_row["full_name"] or ""),
                        str(collaborator_row["email"] or ""),
                        str(collaborator_row["handled_at"]) if collaborator_row["handled_at"] else None,
                        str(collaborator_row["created_at"] or row["created_at"] or ""),
                        str(collaborator_row["updated_at"] or row["updated_at"] or row["created_at"] or ""),
                    ),
                )

    def _delete_legacy_event_line_notification_tasks(self) -> None:
        rows = self.conn.execute(
            """
            SELECT id
            FROM tasks
            WHERE source_type = 'event_line_notification'
            """
        ).fetchall()
        legacy_task_ids = [str(row["id"] or "").strip() for row in rows if str(row["id"] or "").strip()]
        for task_id in legacy_task_ids:
            self.conn.execute("DELETE FROM task_collaborators WHERE task_id = ?", (task_id,))
            self.conn.execute("DELETE FROM task_list_links WHERE task_id = ?", (task_id,))
            self.conn.execute("DELETE FROM task_notes WHERE task_id = ?", (task_id,))
            self.conn.execute("DELETE FROM task_attachments WHERE task_id = ?", (task_id,))
            self.conn.execute("DELETE FROM weekly_review_task_entries WHERE task_id = ?", (task_id,))
            self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

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
            self.conn.execute(query, params)
            self.conn.commit()

    def executemany(self, query: str, params: list[tuple]) -> None:
        with self._lock:
            self.conn.executemany(query, params)
            self.conn.commit()

    def executescript(self, script: str) -> None:
        with self._lock:
            self.conn.executescript(script)
            self.conn.commit()

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
