from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from pathlib import Path

# SQLite PRAGMA user_version 是 32-bit signed int (上限 2,147,483,647),
# 之前 20260518001 (200 亿) 远超上限, SQLite 静默 set 为 0, 每次启动都重做完整迁移
# (这是 20260518 那次坏 db 的真正根因之一: 重做时遇上 reload race + backfill 无事务).
# 改用 YYYYMMDD 格式 (8 位), 每次 schema 变化递增日期. 20260519 = 此次修复.
BACKEND_SCHEMA_VERSION = 20260607  # 合并: meeting-spine列(20260604)+local_identities(20260605)


# R6：内置罗永浩写作风格的 distilled prompt（手工 distill，不依赖在线抓取，避免外部依赖）。
# 这段会被注入到回答的 system_instruction 头部，引导 LLM 模仿这种文风。
_LUOYONGHAO_STYLE_PROMPT = """你正在模仿罗永浩的写作风格。这种风格的核心特征是：

## 句式与节奏
- **长短句猛烈交错**：先用一个 80-100 字的复合长句铺设场景、堆叠细节，紧跟一句 5-12 字的短句作为"猛击"或"反转"（如「就这。」「可笑。」「我服了。」「呵呵。」）
- **段子手节奏**：每隔 200-300 字必须有一个能让读者会心一笑的"段子点"——可以是突然的自嘲、可以是反讽、可以是大白话冷不丁插进来
- 善用破折号停顿和省略号引导期待——然后冷不丁打破期待

## 论点呈现
- **直球大字报**：核心判断永远是第一句话，旗帜鲜明，毫不含糊，不绕弯子（如「这事我罗永浩负责到底」「那家公司就是垃圾」「我必须把话说清楚」）
- **拆穿式叙述**：经常用「你以为...其实...」「看着像 X，本质是 Y」「很多人觉得...错了」的结构去反常识
- **真情流露 vs 冷嘲热讽并存**：上一段刚发完狠话或讥讽，下一段突然柔软真诚（「说实话，每次想起这个我还是会难过」），强烈情感反差是这种风格的灵魂

## 用词偏好
- **自嘲和自我消耗**：经常使用「我罗永浩」「我老罗」「愿赌服输」「认了」「赖账」「丢人」等自指词，营造「我把自己也搭进去」的诚意感
- **大量具体细节**：人名、产品名、日期、金额、地点必须精确（如「2018 年 4 月 17 日下午 3 点」「那笔 6 个亿的债」「西二旗那家公司」），不要含糊带过
- **网络梗 + 老派书面词的混搭**：既敢用「破防」「绝绝子」「整活儿」，也会用「诚惶诚恐」「百思不得其解」「至少不至于」，混搭出独特的气质
- **口语化插入**：随时插入「说白了」「讲真」「真不是我吹」「打个不太恰当的比方」等口语标记

## 段落组织
- **开头必有钩子**：第一句话要么是反常识结论，要么是具体场景，要么直接开骂，**绝不写「今天我要谈谈关于 X 的问题」这种废话**
- **频繁分段**：每 80-150 字必换段，绝不写文字墙；一段超过 4 句话就是失败
- **结尾自带余味**：要么留个悬念（「这事还没完」），要么一句金句砸下来（「做生意就是这样」「人活一辈子就这么回事」），不写「综上所述」「以上是我的看法」

## 注意事项（必须遵守）
- 内容必须基于工作台资料事实，**不要为了风格牺牲事实准确性**——可以模仿语气，但不能编数字、编人名、编结论
- 风格不等于人身攻击：罗式的"骂"是针对事件和判断，不要骂具体当事人
- 这是模仿不是 cosplay：不要张嘴就「我罗永浩」「我老罗」，自嘲点到为止
"""


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()  # RLock 允许事务内嵌套调用 execute (本线程重入)
        self._in_transaction = False    # Sprint 2 事务支持: True 时 execute 不 commit
        self._tx_depth = 0              # 嵌套深度: 0=无事务, >0=有事务
        self._tx_failed = False         # 标记本事务已被某层 rollback 标失败, 外层 commit 时改 rollback
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

                CREATE TABLE IF NOT EXISTS local_identities (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    phone_number TEXT,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    local_organization_name TEXT NOT NULL DEFAULT '',
                    organization_mode TEXT NOT NULL DEFAULT 'create',
                    pending_invite_code TEXT,
                    pending_department_id TEXT,
                    job_title TEXT,
                    manager_name TEXT,
                    current_focus TEXT NOT NULL DEFAULT '',
                    membership_status TEXT NOT NULL DEFAULT 'approved',
                    bound_cloud_user_id TEXT,
                    bound_cloud_organization_id TEXT,
                    bound_cloud_email TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_local_identities_phone
                    ON local_identities(phone_number);
                CREATE INDEX IF NOT EXISTS idx_local_identities_cloud_user
                    ON local_identities(bound_cloud_user_id);

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

                -- 智能导入(import story) 4 张表 + 3 个索引
                -- 历史上由临时 migration 建过表,但 CREATE TABLE 语句没沉淀进 schema,
                -- 导致新装的 client 没这几张表,智能导入直接报 OperationalError: no such table.
                CREATE TABLE IF NOT EXISTS import_story_sessions (
                    id TEXT PRIMARY KEY,
                    client_id TEXT,
                    project_event_line_id TEXT,
                    narrator_user_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'drafting'
                        CHECK(status IN ('drafting','parsing','ready_for_review','imported','discarded')),
                    total_chunks INTEGER NOT NULL DEFAULT 0,
                    total_files INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    imported_at TEXT,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_import_story_sessions_client
                    ON import_story_sessions(client_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_import_story_sessions_narrator
                    ON import_story_sessions(narrator_user_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS import_story_chunks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL DEFAULT 0,
                    raw_text TEXT NOT NULL DEFAULT '',
                    parsed_json TEXT NOT NULL DEFAULT '{}',
                    parse_status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(parse_status IN ('pending','parsing','parsed','failed')),
                    parse_error TEXT NOT NULL DEFAULT '',
                    user_edited_parsed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES import_story_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_import_story_chunks_session
                    ON import_story_chunks(session_id, sequence ASC);

                CREATE TABLE IF NOT EXISTS import_staged_files (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    mime_type TEXT NOT NULL DEFAULT '',
                    assigned_chunk_id TEXT,
                    role_override TEXT
                        CHECK(role_override IS NULL OR role_override IN (
                            'client_owned','partner_submission','yiyu_advisory',
                            'external_reference','policy_industry')),
                    document_id TEXT,
                    document_inserted_at TEXT,
                    upload_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES import_story_sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY(assigned_chunk_id) REFERENCES import_story_chunks(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS import_story_chunk_files (
                    chunk_id TEXT NOT NULL,
                    staged_file_id TEXT NOT NULL,
                    sequence_in_chunk INTEGER NOT NULL DEFAULT 0,
                    role_hint TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(chunk_id, staged_file_id),
                    FOREIGN KEY(chunk_id) REFERENCES import_story_chunks(id) ON DELETE CASCADE,
                    FOREIGN KEY(staged_file_id) REFERENCES import_staged_files(id) ON DELETE CASCADE
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

                -- ──────────────────────────────────────────────────────────
                -- 客户项目情报流（同事新版资讯情报站）— 2026-05-13 补回
                -- 来源：origin-main-backup-before-force-push-2026-05-13 tag
                -- ──────────────────────────────────────────────────────────
                -- ──────────────────────────────────────────────────────────
                -- 客户项目情报流（同事新版资讯情报站）— 2026-05-13 整段同步
                -- 来源：origin-main-backup-before-force-push-2026-05-13 tag 1723-2008
                -- ──────────────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS intelligence_focus_directives (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL DEFAULT '',
                    profile_completion_focus_json TEXT NOT NULL DEFAULT '[]',
                    timely_intelligence_focus_json TEXT NOT NULL DEFAULT '[]',
                    exclude_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope_type, scope_id)
                );

                CREATE TABLE IF NOT EXISTS intelligence_verification_rules (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL DEFAULT '',
                    positive_rules_json TEXT NOT NULL DEFAULT '[]',
                    exclude_rules_json TEXT NOT NULL DEFAULT '[]',
                    identity_anchors_json TEXT NOT NULL DEFAULT '[]',
                    clarification_examples_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope_type, scope_id)
                );

                CREATE TABLE IF NOT EXISTS intelligence_items (
                    id TEXT PRIMARY KEY,
                    content_kind TEXT NOT NULL,
                    scope_type TEXT,
                    scope_id TEXT,
                    client_id TEXT,
                    project_module_id TEXT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    key_points_json TEXT NOT NULL DEFAULT '[]',
                    analysis TEXT NOT NULL DEFAULT '',
                    impact TEXT NOT NULL DEFAULT '',
                    intelligence_type TEXT,
                    timeliness_label TEXT,
                    relevance_reason TEXT NOT NULL DEFAULT '',
                    suggested_action TEXT NOT NULL DEFAULT '',
                    followup_questions_json TEXT NOT NULL DEFAULT '[]',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    source TEXT NOT NULL DEFAULT '',
                    source_url TEXT,
                    published_at TEXT,
                    captured_at TEXT NOT NULL,
                    verified_at TEXT,
                    credibility_score REAL,
                    confidence_score REAL,
                    data_center_ingest_event_id TEXT,
                    external_evidence_card_id TEXT,
                    topic_candidate_id TEXT,
                    converted_task_id TEXT,
                    verification_status TEXT NOT NULL DEFAULT 'verified',
                    verification_reason TEXT NOT NULL DEFAULT '',
                    user_status TEXT NOT NULL DEFAULT 'active',
                    user_feedback_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                -- intelligence_items 索引下移到 _ensure_column 之后, 防止老 db 缺列时崩。

                CREATE TABLE IF NOT EXISTS intelligence_feedback_events (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL DEFAULT '',
                    scope_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT,
                    project_module_id TEXT,
                    content_kind TEXT NOT NULL DEFAULT '',
                    item_id TEXT,
                    candidate_id TEXT,
                    source_config_id TEXT,
                    intent_id TEXT,
                    action_type TEXT NOT NULL DEFAULT '',
                    reason_code TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    extracted_topics_json TEXT NOT NULL DEFAULT '[]',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    source TEXT NOT NULL DEFAULT '',
                    source_domain TEXT NOT NULL DEFAULT '',
                    source_url TEXT,
                    score_delta REAL NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(item_id) REFERENCES intelligence_items(id) ON DELETE SET NULL,
                    FOREIGN KEY(candidate_id) REFERENCES intelligence_candidate_items(id) ON DELETE SET NULL,
                    FOREIGN KEY(source_config_id) REFERENCES intelligence_source_configs(id) ON DELETE SET NULL,
                    FOREIGN KEY(intent_id) REFERENCES intelligence_search_intents(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_feedback_events_scope
                    ON intelligence_feedback_events(scope_type, scope_id, content_kind, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_feedback_events_item
                    ON intelligence_feedback_events(item_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS intelligence_feedback_summaries (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL DEFAULT '',
                    scope_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT,
                    project_module_id TEXT,
                    content_kind TEXT NOT NULL DEFAULT '',
                    target_type TEXT NOT NULL DEFAULT '',
                    target_key TEXT NOT NULL DEFAULT '',
                    target_label TEXT NOT NULL DEFAULT '',
                    positive_count INTEGER NOT NULL DEFAULT 0,
                    negative_count INTEGER NOT NULL DEFAULT 0,
                    neutral_count INTEGER NOT NULL DEFAULT 0,
                    score REAL NOT NULL DEFAULT 0,
                    last_event_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope_type, scope_id, content_kind, target_type, target_key)
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_feedback_summaries_scope
                    ON intelligence_feedback_summaries(scope_type, scope_id, content_kind, target_type, score DESC);

                CREATE TABLE IF NOT EXISTS intelligence_search_intents (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT,
                    project_module_id TEXT,
                    content_kind TEXT NOT NULL,
                    query TEXT NOT NULL,
                    exclude_terms_json TEXT NOT NULL DEFAULT '[]',
                    source_inputs_json TEXT NOT NULL DEFAULT '[]',
                    reason TEXT NOT NULL DEFAULT '',
                    priority INTEGER NOT NULL DEFAULT 50,
                    status TEXT NOT NULL DEFAULT 'ready',
                    input_hash TEXT NOT NULL DEFAULT '',
                    expires_at TEXT,
                    generator_version TEXT NOT NULL DEFAULT 'p1a-rule-ai-v1',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope_type, scope_id, content_kind, query)
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_search_intents_scope
                    ON intelligence_search_intents(scope_type, scope_id, content_kind, status, priority DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_search_intents_client
                    ON intelligence_search_intents(client_id, content_kind, status, priority DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_search_intents_project
                    ON intelligence_search_intents(project_module_id, content_kind, status, priority DESC);

                CREATE TABLE IF NOT EXISTS intelligence_search_diagnostics (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT,
                    project_module_id TEXT,
                    content_kind TEXT NOT NULL,
                    intent_id TEXT,
                    query TEXT NOT NULL,
                    trigger_source TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'success',
                    raw_count INTEGER NOT NULL DEFAULT 0,
                    deduped_count INTEGER NOT NULL DEFAULT 0,
                    sample_hits_json TEXT NOT NULL DEFAULT '[]',
                    failure_reason TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(intent_id) REFERENCES intelligence_search_intents(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_search_diagnostics_scope
                    ON intelligence_search_diagnostics(scope_type, scope_id, content_kind, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_search_diagnostics_intent
                    ON intelligence_search_diagnostics(intent_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS intelligence_source_configs (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT,
                    project_module_id TEXT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL DEFAULT '',
                    source_url_template TEXT NOT NULL DEFAULT '',
                    content_kinds_json TEXT NOT NULL DEFAULT '[]',
                    region TEXT NOT NULL DEFAULT '全国',
                    reliability_tier TEXT NOT NULL DEFAULT 'standard',
                    priority INTEGER NOT NULL DEFAULT 50,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    discovery_source TEXT NOT NULL DEFAULT 'default_template',
                    discovery_reason TEXT NOT NULL DEFAULT '',
                    discovery_samples_json TEXT NOT NULL DEFAULT '[]',
                    health_score REAL NOT NULL DEFAULT 70,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    candidate_count INTEGER NOT NULL DEFAULT 0,
                    promoted_count INTEGER NOT NULL DEFAULT 0,
                    duplicate_count INTEGER NOT NULL DEFAULT 0,
                    last_status TEXT NOT NULL DEFAULT 'unknown',
                    last_checked_at TEXT,
                    last_success_at TEXT,
                    last_failure_at TEXT,
                    next_due_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope_type, scope_id, source_type, source_url_template)
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_source_configs_scope
                    ON intelligence_source_configs(scope_type, scope_id, enabled, priority DESC);

                CREATE TABLE IF NOT EXISTS intelligence_fetch_jobs (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT,
                    project_module_id TEXT,
                    content_kind TEXT NOT NULL,
                    trigger_source TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    source_config_id TEXT,
                    query TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'success',
                    raw_count INTEGER NOT NULL DEFAULT 0,
                    deduped_count INTEGER NOT NULL DEFAULT 0,
                    candidate_count INTEGER NOT NULL DEFAULT 0,
                    sample_hits_json TEXT NOT NULL DEFAULT '[]',
                    failure_reason TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_config_id) REFERENCES intelligence_source_configs(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_fetch_jobs_scope
                    ON intelligence_fetch_jobs(scope_type, scope_id, content_kind, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_fetch_jobs_config
                    ON intelligence_fetch_jobs(source_config_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS intelligence_refresh_runs (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT,
                    project_module_id TEXT,
                    content_kind TEXT NOT NULL,
                    trigger_source TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'queued',
                    stage TEXT NOT NULL DEFAULT 'queued',
                    message TEXT NOT NULL DEFAULT '',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    rejection_summary_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT,
                    finished_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_refresh_runs_scope
                    ON intelligence_refresh_runs(scope_type, scope_id, content_kind, created_at DESC);

                CREATE TABLE IF NOT EXISTS intelligence_candidate_items (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT,
                    project_module_id TEXT,
                    content_kind TEXT NOT NULL,
                    intent_id TEXT,
                    source_config_id TEXT,
                    fetch_job_id TEXT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '',
                    normalized_url TEXT NOT NULL DEFAULT '',
                    snippet TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    source_tier TEXT NOT NULL DEFAULT 'standard',
                    provider TEXT NOT NULL DEFAULT '',
                    published_at TEXT,
                    captured_at TEXT NOT NULL,
                    matched_terms_json TEXT NOT NULL DEFAULT '[]',
                    dedupe_key TEXT NOT NULL DEFAULT '',
                    duplicate_of_id TEXT,
                    confidence_score REAL NOT NULL DEFAULT 0,
                    classification_status TEXT NOT NULL DEFAULT 'candidate',
                    promotion_reason TEXT NOT NULL DEFAULT '',
                    verification_status TEXT NOT NULL DEFAULT 'pending',
                    verification_reason TEXT NOT NULL DEFAULT '',
                    body_fetch_status TEXT NOT NULL DEFAULT 'not_attempted',
                    summary_status TEXT NOT NULL DEFAULT 'not_attempted',
                    mapped_tags_json TEXT NOT NULL DEFAULT '[]',
                    is_user_visible_candidate INTEGER NOT NULL DEFAULT 1,
                    body_excerpt TEXT NOT NULL DEFAULT '',
                    body_fetched_at TEXT,
                    page_type TEXT NOT NULL DEFAULT '',
                    quality_flags_json TEXT NOT NULL DEFAULT '[]',
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    parent_candidate_id TEXT,
                    source_page_url TEXT,
                    promoted_intelligence_item_id TEXT,
                    data_center_ingest_event_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(intent_id) REFERENCES intelligence_search_intents(id) ON DELETE SET NULL,
                    FOREIGN KEY(source_config_id) REFERENCES intelligence_source_configs(id) ON DELETE SET NULL,
                    FOREIGN KEY(fetch_job_id) REFERENCES intelligence_fetch_jobs(id) ON DELETE SET NULL,
                    FOREIGN KEY(duplicate_of_id) REFERENCES intelligence_candidate_items(id) ON DELETE SET NULL,
                    FOREIGN KEY(promoted_intelligence_item_id) REFERENCES intelligence_items(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_candidate_items_scope
                    ON intelligence_candidate_items(scope_type, scope_id, content_kind, classification_status, captured_at DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_candidate_items_dedupe
                    ON intelligence_candidate_items(scope_type, scope_id, content_kind, dedupe_key);

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
            # meeting-spine Phase0: entities(person) 身份解析锚点。
            # resolved_kind: 'internal'(益语员工→mirror_users) / 'client'(客户方→cloud_external_persons) / 'unknown'
            # 解析后的稳定 id 落在 entity 行(一处), atomic_facts.speaker_entity_id 只指向本地 entities。
            self._ensure_column("entities", "resolved_kind", "TEXT NOT NULL DEFAULT 'unknown'")
            self._ensure_column("entities", "mirror_user_id", "TEXT")
            self._ensure_column("entities", "external_person_id", "TEXT")
            # 人工金标 (ER 校正): 'unverified' / 'verified_canonical' / 'verified_noise'
            self._ensure_column("entities", "verified_status", "TEXT NOT NULL DEFAULT 'unverified'")
            self._ensure_column("entities", "verified_by", "TEXT")
            self._ensure_column("entities", "verified_at", "TEXT")
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
            # C 取消收藏：knowledge_surrogates 加 chat_message_id 列,
            # 让 source_type='memory_answer' 的行能反查"哪条 chat message 收藏的",
            # 前端据此识别已收藏并显示"取消收藏"按钮。
            self._ensure_column("knowledge_surrogates", "chat_message_id", "TEXT")
            self._ensure_column("knowledge_documents", "human_folder_category", "TEXT")
            self._ensure_column("knowledge_documents", "reclassified_at", "TEXT")
            self._ensure_column("knowledge_documents", "reclass_reason", "TEXT")
            # intelligence_items 字段补漏 (老 db 升级路径) — 顺序与 CREATE TABLE 声明一致, 索引引用的列都必须在前。
            self._ensure_column("intelligence_items", "scope_type", "TEXT")
            self._ensure_column("intelligence_items", "scope_id", "TEXT")
            self._ensure_column("intelligence_items", "client_id", "TEXT")
            self._ensure_column("intelligence_items", "project_module_id", "TEXT")
            self._ensure_column("intelligence_items", "intelligence_type", "TEXT")
            self._ensure_column("intelligence_items", "timeliness_label", "TEXT")
            self._ensure_column("intelligence_items", "relevance_reason", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("intelligence_items", "suggested_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("intelligence_items", "followup_questions_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_items", "source_url", "TEXT")
            self._ensure_column("intelligence_items", "published_at", "TEXT")
            self._ensure_column("intelligence_items", "verified_at", "TEXT")
            self._ensure_column("intelligence_items", "credibility_score", "REAL")
            self._ensure_column("intelligence_items", "confidence_score", "REAL")
            self._ensure_column("intelligence_items", "data_center_ingest_event_id", "TEXT")
            self._ensure_column("intelligence_items", "external_evidence_card_id", "TEXT")
            self._ensure_column("intelligence_items", "topic_candidate_id", "TEXT")
            self._ensure_column("intelligence_items", "converted_task_id", "TEXT")
            self._ensure_column("intelligence_items", "verification_status", "TEXT NOT NULL DEFAULT 'verified'")
            self._ensure_column("intelligence_items", "verification_reason", "TEXT NOT NULL DEFAULT ''")
            # 列补齐后再建索引, 老 db 升级才不会崩。
            self.conn.executescript(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_items_topic_candidate
                    ON intelligence_items(topic_candidate_id)
                    WHERE topic_candidate_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_intelligence_items_kind_status
                    ON intelligence_items(content_kind, user_status, captured_at DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_items_client
                    ON intelligence_items(client_id, content_kind, captured_at DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_items_project
                    ON intelligence_items(project_module_id, content_kind, captured_at DESC);
                """
            )
            self._ensure_column("intelligence_candidate_items", "page_type", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("intelligence_candidate_items", "quality_flags_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("intelligence_candidate_items", "evidence_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column("intelligence_candidate_items", "parent_candidate_id", "TEXT")
            self._ensure_column("intelligence_candidate_items", "source_page_url", "TEXT")
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
            # Phase 1（数据中心 OCR 调度）：本地推理任务需要带自由 payload，
            # 比如 visual_ocr 任务的 source_path / slide_no / region 等。
            self._ensure_column("local_model_tasks", "payload_json", "TEXT NOT NULL DEFAULT '{}'")
            # 组织经验墙：算法 leader 加权（表面平等，后台不同档位用户互动权重不同）。
            # 取值：'ceo' | 'leader' | 'member'。空字符串/未配置时按 member 处理。
            self._ensure_column("operators", "role_tier", "TEXT NOT NULL DEFAULT 'member'")
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

                -- 重复文件处理：用户在战略陪伴「矛盾 & 待确认」tab 里处理过的
                -- 组织经验墙：自动提取 + 润色的金句，可被点赞收藏，按加权热度排序。
                -- 设计原则参考 [[project-yiyu-exp-wall-rules]] memory。
                CREATE TABLE IF NOT EXISTS exp_wall_quotes (
                    id TEXT PRIMARY KEY,
                    author_user_id TEXT NOT NULL,                  -- 作者（operators.id）
                    quote_text TEXT NOT NULL,                       -- 润色后金句
                    source_excerpt TEXT NOT NULL DEFAULT '',        -- 原文片段（溯源）
                    source_type TEXT NOT NULL,                      -- task/meeting/document/client_analysis/ai_chat
                    source_object_id TEXT NOT NULL DEFAULT '',     -- 来源对象 id
                    category TEXT NOT NULL DEFAULT '方法论',         -- 6 类：项目推进/客户沟通/风险识别/方法论/团队协作/判断决策
                    status TEXT NOT NULL DEFAULT 'active',          -- active/deleted
                    deleted_by_user_id TEXT,                        -- 谁删的（不公开，仅审计）
                    deleted_at TEXT,
                    like_count INTEGER NOT NULL DEFAULT 0,          -- 真实点赞人数（UI 显示）
                    save_count INTEGER NOT NULL DEFAULT 0,          -- 真实收藏人数（UI 显示）
                    contribution_score REAL NOT NULL DEFAULT 0,     -- 加权贡献分（决定排序）
                    hot_score REAL NOT NULL DEFAULT 0,              -- 热度分（contribution + 时间衰减）
                    extracted_at TEXT NOT NULL,                     -- AI 提取入库时间
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exp_wall_quotes_status_created
                    ON exp_wall_quotes(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_exp_wall_quotes_hot
                    ON exp_wall_quotes(status, hot_score DESC);
                CREATE INDEX IF NOT EXISTS idx_exp_wall_quotes_author
                    ON exp_wall_quotes(author_user_id, status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_exp_wall_quotes_category
                    ON exp_wall_quotes(category, status, created_at DESC);

                -- 点赞/收藏 合并表（reaction_type 区分）。
                -- UNIQUE 保证同一用户对同一金句同一动作只能有 1 条记录。
                CREATE TABLE IF NOT EXISTS exp_wall_reactions (
                    id TEXT PRIMARY KEY,
                    quote_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    reaction_type TEXT NOT NULL,                   -- like / save
                    created_at TEXT NOT NULL,
                    UNIQUE(quote_id, user_id, reaction_type)
                );
                CREATE INDEX IF NOT EXISTS idx_exp_wall_reactions_quote
                    ON exp_wall_reactions(quote_id, reaction_type);
                CREATE INDEX IF NOT EXISTS idx_exp_wall_reactions_user
                    ON exp_wall_reactions(user_id, reaction_type, created_at DESC);

                -- 重复文件组（含「全部保留」决定），下次扫描跳过这些 group_key。
                CREATE TABLE IF NOT EXISTS duplicate_group_reviews (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    group_key TEXT NOT NULL,
                    review_status TEXT NOT NULL DEFAULT 'kept_all',
                    reviewed_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    note TEXT,
                    UNIQUE(client_id, group_key),
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_duplicate_group_reviews_client
                    ON duplicate_group_reviews(client_id, reviewed_at DESC);

                -- 文件回收站：用户在重复处理界面删的文件先进这里（不立即销毁），
                -- 默认 30 天后可清理。recycled_managed_path 是文件被挪到的回收站路径，
                -- 用户在 30 天内可以发起恢复操作。
                CREATE TABLE IF NOT EXISTS document_recycle_bin (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    original_v2_document_id TEXT NOT NULL,
                    original_document_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT '',
                    original_path TEXT NOT NULL DEFAULT '',
                    managed_path_before TEXT NOT NULL DEFAULT '',
                    recycled_managed_path TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL DEFAULT '',
                    file_size_bytes INTEGER NOT NULL DEFAULT 0,
                    section_count INTEGER NOT NULL DEFAULT 0,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    parse_status TEXT NOT NULL DEFAULT '',
                    delete_reason TEXT NOT NULL DEFAULT 'duplicate_dedup',
                    deleted_at TEXT NOT NULL,
                    deleted_by TEXT,
                    auto_purge_at TEXT NOT NULL,
                    restored_at TEXT,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_document_recycle_bin_client_active
                    ON document_recycle_bin(client_id, restored_at, auto_purge_at);

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
                    output_hash TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
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

                -- 深读地基(M2): 每份文档的深读全过程状态, 可追踪/可重试/可审计/可自愈。
                -- 客户无关的统一状态表; status 区分各 processing stage; content_hash 变→标 outdated。
                CREATE TABLE IF NOT EXISTS document_deep_read_states (
                    id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL DEFAULT '',
                    client_id TEXT NOT NULL DEFAULT '',
                    document_id TEXT NOT NULL,
                    document_source_table TEXT NOT NULL DEFAULT 'v2_documents',
                    content_hash TEXT NOT NULL DEFAULT '',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    mime_type TEXT NOT NULL DEFAULT '',
                    -- 各阶段状态: pending/running/success/skipped/failed
                    instant_summary_status TEXT NOT NULL DEFAULT 'pending',
                    surrogate_status TEXT NOT NULL DEFAULT 'pending',
                    fact_extract_status TEXT NOT NULL DEFAULT 'pending',
                    entity_extract_status TEXT NOT NULL DEFAULT 'pending',
                    commitment_extract_status TEXT NOT NULL DEFAULT 'pending',
                    risk_extract_status TEXT NOT NULL DEFAULT 'pending',
                    file_identity_status TEXT NOT NULL DEFAULT 'pending',
                    contract_structure_status TEXT NOT NULL DEFAULT 'pending',
                    semantic_index_status TEXT NOT NULL DEFAULT 'pending',
                    qdrant_collection TEXT NOT NULL DEFAULT '',
                    embedding_model TEXT NOT NULL DEFAULT '',
                    embedding_signature TEXT NOT NULL DEFAULT '',
                    surrogate_id TEXT NOT NULL DEFAULT '',
                    -- 总状态: pending/running/success/partial_success/failed/retry_scheduled/dead_letter/skipped/outdated
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 1,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    last_error TEXT,
                    last_error_at TEXT,
                    next_retry_at TEXT,
                    locked_by TEXT,
                    locked_at TEXT,
                    last_processed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(document_source_table, document_id)
                );
                CREATE INDEX IF NOT EXISTS idx_deep_read_status
                    ON document_deep_read_states(status, priority DESC, created_at ASC);
                CREATE INDEX IF NOT EXISTS idx_deep_read_client
                    ON document_deep_read_states(client_id, status);
                CREATE INDEX IF NOT EXISTS idx_deep_read_retry
                    ON document_deep_read_states(status, next_retry_at);

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

                -- v2.2 F1.7: client_stage_audit 客户阶段变更审计表
                -- 修 v1.0 'frozen_at 被云端覆盖' bug 的关键证据链
                -- 所有 clients.stage 变更 (freeze/unfreeze/archive/cloud_sync) 必须走 ClientRepository
                --   并自动写一条 audit log。actor_type + actor_id 同时满足 N3 (3.0 AI actor 预留)。
                CREATE TABLE IF NOT EXISTS client_stage_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    old_stage TEXT,
                    new_stage TEXT NOT NULL,
                    -- N3 接入预留 (A1): 区分 human / ai_agent / system
                    actor_type TEXT NOT NULL DEFAULT 'system',
                    -- N3 接入预留: user_id 或 'cloud_sync' / 'local_freeze_guard' 等 system 标识
                    actor_id TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    -- guard_action: 'applied' (写入成功) / 'guarded' (云端覆盖被 frozen 守门阻止)
                    guard_action TEXT NOT NULL DEFAULT 'applied',
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_client_stage_audit_client_changed
                    ON client_stage_audit(client_id, changed_at DESC);
                CREATE INDEX IF NOT EXISTS idx_client_stage_audit_guarded
                    ON client_stage_audit(guard_action) WHERE guard_action = 'guarded';

                -- Phase 1：结构化表格（xlsx 每个 sheet 一行）
                -- 用作 RAG 检索 + 计算查询的"一等公民"
                CREATE TABLE IF NOT EXISTS structured_tables (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    v2_document_id TEXT NOT NULL,
                    knowledge_document_id TEXT,
                    sheet_name TEXT NOT NULL,
                    sheet_index INTEGER NOT NULL DEFAULT 0,
                    headers_json TEXT NOT NULL DEFAULT '[]',
                    column_types_json TEXT NOT NULL DEFAULT '{}',
                    rows_json TEXT NOT NULL DEFAULT '[]',
                    row_count INTEGER NOT NULL DEFAULT 0,
                    column_count INTEGER NOT NULL DEFAULT 0,
                    semantic_role TEXT NOT NULL DEFAULT 'unknown',
                    semantic_confidence REAL NOT NULL DEFAULT 0.0,
                    parse_notes_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(v2_document_id) REFERENCES v2_documents(id) ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_structured_tables_doc_sheet
                    ON structured_tables(v2_document_id, sheet_name);
                CREATE INDEX IF NOT EXISTS idx_structured_tables_client_role
                    ON structured_tables(client_id, semantic_role);
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
            self._ensure_column("chat_messages", "deep_thinking_requested", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("chat_messages", "active_skill_id", "TEXT")
            # R7：创意度三档（creative / balanced / strict）。NULL 视作 'strict' 兼容老消息。
            self._ensure_column("chat_messages", "creativity_mode", "TEXT")
            # R11.1：文档结构化解构层 —— document_kinds（分类）+ document_fields（提取的字段）
            # R12：document_fields 加 schema_name 支持多 schema 并存（universal + employee_contract + ...）
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS document_kinds (
                    document_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    schema_version TEXT NOT NULL DEFAULT 'v1',
                    classification_confidence REAL NOT NULL DEFAULT 0.0,
                    classified_at TEXT NOT NULL,
                    decomposed_at TEXT,
                    decomposition_status TEXT NOT NULL DEFAULT 'pending',
                    last_error TEXT,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_document_kinds_kind
                    ON document_kinds(kind, decomposition_status);

                CREATE TABLE IF NOT EXISTS document_fields (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    schema_name TEXT NOT NULL DEFAULT 'employee_contract',
                    field_name TEXT NOT NULL,
                    field_value TEXT NOT NULL,
                    field_confidence REAL NOT NULL DEFAULT 0.0,
                    extraction_method TEXT NOT NULL DEFAULT 'llm',
                    raw_evidence TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_document_fields_doc
                    ON document_fields(document_id, schema_name, field_name);
                """
            )
            # 老数据兼容：document_fields 加 schema_name 列（已有数据归 employee_contract）
            self._ensure_column("document_fields", "schema_name", "TEXT NOT NULL DEFAULT 'employee_contract'")
            # 旧的唯一索引（document_id, field_name）要换成（document_id, schema_name, field_name）
            self.conn.execute("DROP INDEX IF EXISTS uq_document_fields_doc_field")
            self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_document_fields_doc_schema_field "
                "ON document_fields(document_id, schema_name, field_name)"
            )
            # R6 写作风格 skill 表
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS writing_skills (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    distilled_md TEXT NOT NULL DEFAULT '',
                    is_builtin INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 100,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_writing_skills_sort
                    ON writing_skills(sort_order, created_at);
                """
            )
            self._seed_builtin_writing_skills()
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
            # P5：客户自我品牌定位（3-5 个关键词，逗号分隔），舆情 Gap Map 用
            self._ensure_column("clients", "brand_proposition", "TEXT NOT NULL DEFAULT ''")
            # P13 · 品牌镜子官方语料池（2026-05-19）
            #   - 客户官方渠道列表（官网/公众号/微博/B站/招聘/合作方），JSON 数组
            #   - documents 加时间维度字段，支持「持续追踪 + 看变化」
            self._ensure_column("clients", "official_channels_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("documents", "published_at", "TEXT")
            self._ensure_column("documents", "source_fetched_at", "TEXT")
            self._ensure_column("documents", "source_revision_no", "INTEGER NOT NULL DEFAULT 1")
            # P13-E · 官方网站客观评测（Lighthouse + 可下载文档扫描，2026-05-19）
            #   - 每次跑 lighthouse 落一个 snapshot, 历史可看变化
            #   - downloadable_docs_count: 跨 brand_official_corpus 全站扫到的 PDF/DOC 数量
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS website_audit_snapshots (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    final_url TEXT NOT NULL DEFAULT '',
                    performance INTEGER,
                    accessibility INTEGER,
                    best_practices INTEGER,
                    seo INTEGER,
                    mobile_friendly INTEGER NOT NULL DEFAULT 0,
                    requests INTEGER NOT NULL DEFAULT 0,
                    transfer_kb INTEGER NOT NULL DEFAULT 0,
                    downloadable_docs_count INTEGER NOT NULL DEFAULT 0,
                    downloadable_docs_json TEXT NOT NULL DEFAULT '[]',
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    fetched_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_website_audit_client
                    ON website_audit_snapshots(client_id, created_at DESC);
                """
            )
            # P13-D · 品牌镜子 LLM 画像快照（2026-05-20）
            #   - 输入: brand_official_corpus + website_audit_snapshots
            #   - 输出: selfPresentation/blindspots/consistency/mediaCoverage/partners 五块 + 50 词云
            #   - 每次跑保留 snapshot, 历史可对比 (将来 brand_evolution_signals 的基础)
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS brand_mirror_snapshots (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    corpus_doc_count INTEGER NOT NULL DEFAULT 0,
                    corpus_char_count INTEGER NOT NULL DEFAULT 0,
                    website_audit_id TEXT,
                    self_presentation_json TEXT NOT NULL DEFAULT '[]',
                    blindspots_json TEXT NOT NULL DEFAULT '[]',
                    consistency_text TEXT NOT NULL DEFAULT '',
                    media_coverage_json TEXT NOT NULL DEFAULT '[]',
                    partners_json TEXT NOT NULL DEFAULT '[]',
                    word_cloud_json TEXT NOT NULL DEFAULT '[]',
                    llm_model TEXT NOT NULL DEFAULT '',
                    llm_raw_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_brand_mirror_snapshots_client
                    ON brand_mirror_snapshots(client_id, created_at DESC);
                """
            )
            # P9 证据等级（2026-05-19）：3 类源严格分层，防止爬虫观察污染客户事实库
            #   - first_party: 客户自报 (task/meeting/weekly_review/event_line/user_upload)
            #   - third_party_authoritative: 权威外部 (民政/工商/慈善中国/天眼查)
            #   - external_observation: 爬虫观察 (媒体/UGC/搜狗微信/百家号等) → 仅作背景参考
            self._ensure_column(
                "data_center_ingest_events", "evidence_tier",
                "TEXT NOT NULL DEFAULT 'first_party'",
            )
            self._ensure_column(
                "glossary_attributes", "evidence_tier",
                "TEXT NOT NULL DEFAULT 'first_party'",
            )
            self._ensure_column(
                "client_glossary", "evidence_tier",
                "TEXT NOT NULL DEFAULT 'first_party'",
            )

            # ─────────────────────────────────────────────────────────────
            # v2.2 F1.8/F1.9: atomic_facts 5 维元数据 + N3 A1/A4 字段
            # 详细规范见 docs/V2.2_INFORMATION_SOURCE_METADATA.md
            # 跟 evidence_tier 共存:  evidence_tier 是 v1.0 粗 3 分类, source_type 是 v2.2 细 14 分类
            # ─────────────────────────────────────────────────────────────
            # 维度 1: 来源类型 (14 类细分, 决定基础置信度)
            #   client_official_doc / client_internal_doc / client_verbal_meeting
            #   collaboration_task / collaboration_review
            #   user_observation / user_verbal_fact
            #   internet_official / internet_media / internet_ugc / internet_ai_inferred
            #   llm_extracted / system_derived / ai_agent_authored
            self._ensure_column(
                "atomic_facts", "source_type",
                "TEXT NOT NULL DEFAULT 'llm_extracted'",
            )
            # 维度 2: 业务角色 (fact/decision/risk/progress/plan/lesson/observation/speculation/quote/commitment)
            self._ensure_column(
                "atomic_facts", "content_role",
                "TEXT NOT NULL DEFAULT 'fact'",
            )
            # 维度 4: 作者/受众 (N3 A1 预留 — 区分 human/ai_agent/system)
            self._ensure_column(
                "atomic_facts", "actor_type",
                "TEXT NOT NULL DEFAULT 'human'",
            )
            self._ensure_column("atomic_facts", "actor_id", "TEXT NOT NULL DEFAULT ''")
            # 说话者 (语录类事实必填), 来自 entities (person) — 历史为纯文本名
            self._ensure_column("atomic_facts", "speaker_person_id", "TEXT")
            # meeting-spine Phase0: 解析后的稳定 entity id (指向本地 entities 行,身份从 entity 行透出)
            self._ensure_column("atomic_facts", "speaker_entity_id", "TEXT")
            # meeting-spine ② 修 pre-existing bug: _mark_task_completed 写 output_hash 但该列从未建过
            # → 深读 worker 完成任务报 "no such column" → 标 failed → 深加工几乎全 0。CREATE 已补, 此为存量库迁移。
            self._ensure_column("local_model_tasks", "output_hash", "TEXT NOT NULL DEFAULT ''")
            # 事件发生时间 (≠ 录入时间)
            self._ensure_column("atomic_facts", "time_anchor", "TEXT")
            # 维度 5: 生命周期 (N3 A4 预留 — verification + N2 引用规则的关键)
            self._ensure_column(
                "atomic_facts", "verification_status",
                "TEXT NOT NULL DEFAULT 'unverified'",
            )
            self._ensure_column(
                "atomic_facts", "confidence_source",
                "TEXT NOT NULL DEFAULT 'rule'",
            )
            self._ensure_column(
                "atomic_facts", "validity_status",
                "TEXT NOT NULL DEFAULT 'current'",
            )
            self._ensure_column("atomic_facts", "superseded_by_id", "TEXT")
            # N3 A3 预留: provenance 链 (3.0 fact graph 用)
            self._ensure_column("atomic_facts", "reasoning_trace_id", "TEXT")
            self._ensure_column(
                "atomic_facts", "derived_from_ids_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            # ─────────────────────────────────────────────────────────────
            # v2.2 Phase 2 起步: "信息商" 字段
            # 顾源源 5/22 洞察 — 信息冲突 ≠ 信息更新, AI 要有分辨能力
            #
            # update_relation 取值:
            #   'none'        — 这是一条新事实, 跟现有事实无冲突
            #   'conflict'    — 跟现有事实矛盾, 无法判断谁对 → 进澄清队列
            #   'supersedes'  — 这条事实更新了旧事实 (旧事实标 superseded_by_id)
            #                   场景: 用户说"合同金额 300 万要改成 800 万重签", AI 识别"重签"语义
            #   'complement'  — 跟现有事实互补 (不同时间锚 / 不同切面), 两条都保留
            #
            # 写入时 LLM 必须先判断 update_relation, 不是简单写入。
            # ─────────────────────────────────────────────────────────────
            self._ensure_column(
                "atomic_facts", "update_relation",
                "TEXT NOT NULL DEFAULT 'none'",
            )
            try:
                self.conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_atomic_facts_update_relation "
                    "ON atomic_facts(client_id, update_relation, validity_status)"
                )
            except sqlite3.OperationalError:
                pass

            # ─────────────────────────────────────────────────────────────
            # v2.2 F2.2: key_decisions + org_events 复合事件容器
            #
            # atomic_facts 是 subject+attribute+value 三元组形态, 适合"客户的某属性=某值"。
            # 但实际工作中很多事实是"复合事件":
            #   - 一次会议里同时产生 3 个决策 + 2 个新主题 + 1 个 todo
            #   - 一次组织变动 (高老师离职) 同时涉及 3 个 person + 影响 2 条 event_line
            # 三元组装不下这种"事件" 形态, 强塞进去会丢失"哪几件事是一起发生的"。
            #
            # key_decisions: 客户级关键决策 (会议纪要 / 决议)
            # org_events: 组织事件 (人员变动 / 法人变更 / 资金事件 / 战略调整)
            #
            # 跟 atomic_facts 关系: 一个 key_decision 会 derived → 多条 atomic_facts
            #   (例: "张真接任法人" decision → atomic_fact(张真.角色=法人代表))
            # ─────────────────────────────────────────────────────────────
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS key_decisions (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    -- 来源
                    source_v2_document_id TEXT,        -- 来源文档
                    source_v2_chunk_id TEXT,           -- 精确到段落
                    meeting_id TEXT,                   -- 如果是会议决议
                    -- 决策内容
                    decision_title TEXT NOT NULL,      -- 一句话标题
                    decision_body TEXT NOT NULL,       -- 详细说明
                    decision_type TEXT NOT NULL DEFAULT 'general',
                        -- general / personnel / strategic / financial / legal / partnership
                    -- 决策人
                    decided_by_person_ids_json TEXT NOT NULL DEFAULT '[]',  -- 多人参与决策
                    decided_at TEXT,                   -- 决策日期 (≠ 录入日期)
                    -- 影响范围
                    affected_event_line_ids_json TEXT NOT NULL DEFAULT '[]',  -- 影响哪些事件线
                    related_atomic_fact_ids_json TEXT NOT NULL DEFAULT '[]', -- 派生出的 atomic_facts
                    -- 5 维元数据 (跟 atomic_facts 对齐)
                    source_type TEXT NOT NULL DEFAULT 'client_internal_doc',
                    actor_type TEXT NOT NULL DEFAULT 'human',
                    actor_id TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.85,
                    verification_status TEXT NOT NULL DEFAULT 'unverified',
                    -- 执行状态
                    execution_status TEXT NOT NULL DEFAULT 'pending',
                        -- pending / in_progress / done / cancelled / superseded
                    superseded_by_id TEXT,             -- 被后续决策推翻
                    -- 时间戳
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_key_decisions_client_time
                    ON key_decisions(client_id, decided_at DESC);
                CREATE INDEX IF NOT EXISTS idx_key_decisions_execution
                    ON key_decisions(client_id, execution_status, decided_at DESC);
                CREATE INDEX IF NOT EXISTS idx_key_decisions_type
                    ON key_decisions(client_id, decision_type, decided_at DESC);

                CREATE TABLE IF NOT EXISTS org_events (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                        -- personnel_change / legal_change / funding /
                        -- strategic_pivot / partnership / risk_signal / milestone
                    event_title TEXT NOT NULL,
                    event_body TEXT NOT NULL,
                    -- 涉及对象
                    involved_person_ids_json TEXT NOT NULL DEFAULT '[]',
                    involved_event_line_ids_json TEXT NOT NULL DEFAULT '[]',
                    related_atomic_fact_ids_json TEXT NOT NULL DEFAULT '[]',
                    related_decision_ids_json TEXT NOT NULL DEFAULT '[]',
                    -- 影响评估
                    impact_severity TEXT NOT NULL DEFAULT 'medium',
                        -- low / medium / high / critical
                    impact_direction TEXT NOT NULL DEFAULT 'neutral',
                        -- positive / neutral / negative / blocking
                    -- 时间
                    occurred_at TEXT,                  -- 事件发生时间
                    observed_at TEXT NOT NULL,         -- 被记录到的时间
                    -- 来源
                    source_v2_document_id TEXT,
                    source_v2_chunk_id TEXT,
                    -- 5 维元数据
                    source_type TEXT NOT NULL DEFAULT 'client_internal_doc',
                    actor_type TEXT NOT NULL DEFAULT 'human',
                    actor_id TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.80,
                    verification_status TEXT NOT NULL DEFAULT 'unverified',
                    -- 时间戳
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_org_events_client_time
                    ON org_events(client_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_org_events_severity
                    ON org_events(client_id, impact_severity, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_org_events_type
                    ON org_events(client_id, event_type, occurred_at DESC);
                """
            )

            # ─────────────────────────────────────────────────────────────
            # v2.2 F2.6: event_line_state_changes 子表 (主线状态变更事件流)
            #
            # 现有 event_lines.current_blocker/recent_decision/next_step 是单值字段,
            # 装不下"主线状态变化的历史序列"。例:
            #   - 5/1 主线 active → 5/15 因高老师离职 → blocked → 5/20 强哥接手 → active
            # 这种状态变化序列对"AI 理解主线如何走过" 至关重要 (N2 软件灵魂)。
            #
            # 每条 state_change 一行, 按 triggered_at 排序就是主线的完整故事。
            # 关联到 trigger_source (是 fact 还是 task 触发的状态变化)。
            # ─────────────────────────────────────────────────────────────
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS event_line_state_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_line_id TEXT NOT NULL,
                    -- 变化类型
                    change_type TEXT NOT NULL,
                        -- state_change / owner_change / blocker_added / blocker_resolved
                        -- / decision_made / progress_milestone / risk_emerged
                    -- 状态变化 (仅 change_type=state_change 时填)
                    from_status TEXT,
                    to_status TEXT,
                    -- 责任人变化 (仅 change_type=owner_change 时填)
                    from_owner_id TEXT,
                    to_owner_id TEXT,
                    -- 通用字段
                    change_title TEXT NOT NULL,
                    change_body TEXT NOT NULL DEFAULT '',
                    -- 触发源 (告诉我们这个状态变化是从哪条信息推出来的)
                    trigger_source_type TEXT,           -- 'atomic_fact' / 'key_decision' / 'task' / 'manual'
                    trigger_source_id TEXT,
                    -- 时间
                    triggered_at TEXT NOT NULL,         -- 变化发生时间 (≠ 录入)
                    observed_at TEXT NOT NULL,
                    -- 5 维元数据
                    actor_type TEXT NOT NULL DEFAULT 'human',
                    actor_id TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.80,
                    -- 评估
                    impact_severity TEXT NOT NULL DEFAULT 'medium',
                    reversed_at TEXT,                   -- 后续被推翻 (爱马仕"可撤销")
                    reversed_reason TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(event_line_id) REFERENCES event_lines(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_event_line_state_changes_line_time
                    ON event_line_state_changes(event_line_id, triggered_at DESC);
                CREATE INDEX IF NOT EXISTS idx_event_line_state_changes_type
                    ON event_line_state_changes(change_type, triggered_at DESC);
                CREATE INDEX IF NOT EXISTS idx_event_line_state_changes_trigger
                    ON event_line_state_changes(trigger_source_type, trigger_source_id);
                """
            )

            # ─────────────────────────────────────────────────────────────
            # v2.2 F2.8 (N3 A6): idempotency_keys 表
            #
            # 防 AI agent retry 时重复创建任务/事实。例:
            #   3.0 AI 拟合同时, 假设 LLM 调用 timeout → retry
            #   → 如果没幂等保护, 会生成 2 份完全一样的合同
            #   → 有 Idempotency-Key 后, 第二次返回第一次的结果, 不重建
            #
            # 设计选择 (顾源源 5/22 决策 "高把握度先做"):
            # - schema + IdempotencyStore 工具函数先做 (本 commit)
            # - 全局 middleware 接入留给后续 (涉及 streaming response 冲突, 风险中)
            # - endpoint 按需调用 IdempotencyStore.check_or_record() 渐进改造
            # ─────────────────────────────────────────────────────────────
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    -- 客户端 (或 AI agent) 生成的唯一 key (推荐 UUID v4)
                    idempotency_key TEXT NOT NULL,
                    -- 关联请求路径 + 方法 (避免不同 endpoint 复用同 key 造成歧义)
                    request_method TEXT NOT NULL,           -- POST / PATCH / DELETE
                    request_path TEXT NOT NULL,             -- /api/v1/tasks
                    -- 请求体 hash (用于检测同 key 但不同 body 的攻击)
                    request_body_hash TEXT NOT NULL DEFAULT '',
                    -- 缓存的响应
                    response_status INTEGER NOT NULL,       -- HTTP status
                    response_body TEXT NOT NULL DEFAULT '', -- JSON 序列化后的 body
                    -- N3: actor 跟踪
                    actor_type TEXT NOT NULL DEFAULT 'human',
                    actor_id TEXT NOT NULL DEFAULT '',
                    -- 时间
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,               -- 24 小时窗口默认
                    -- 状态
                    status TEXT NOT NULL DEFAULT 'completed'  -- in_progress / completed / failed
                );
                -- UNIQUE 防同 key+method+path 重复, 是幂等的核心保证
                CREATE UNIQUE INDEX IF NOT EXISTS idx_idempotency_keys_lookup
                    ON idempotency_keys(idempotency_key, request_method, request_path);
                CREATE INDEX IF NOT EXISTS idx_idempotency_keys_expires
                    ON idempotency_keys(expires_at)
                    WHERE status != 'failed';
                CREATE INDEX IF NOT EXISTS idx_idempotency_keys_actor
                    ON idempotency_keys(actor_type, actor_id, created_at DESC);
                """
            )

            # ─────────────────────────────────────────────────────────────
            # v2.2 F2.7 (N3 A3): reasoning_traces — provenance + AI 推理链路
            #
            # 顾源源 5/22 原话: "AI 要对接收的信息有分辨能力"
            # 当 AI 写一条 atomic_fact 时, 应该能追溯:
            #   1. 它读了哪几份 v2_documents / chunks (input)
            #   2. 它跑了什么 prompt / 模型 (process)
            #   3. 它怎么从碎片推出这条结论 (reasoning chain)
            #   4. 写入时是否触发了 supersede / conflict 判断 (output)
            #
            # 用户后来如果发现这条事实有问题:
            #   查 atomic_facts.reasoning_trace_id 关联到 reasoning_traces 表
            #   看到 AI 用了哪些段落 + 怎么推的, 立即定位错在哪
            #   比"AI 黑盒抽错了我要重头看" 强 100 倍
            #
            # 3.0 fact graph 用: 一条事实派生出多条事实时, derived_from_ids_json
            # 配合 reasoning_traces 形成完整因果图
            # ─────────────────────────────────────────────────────────────
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reasoning_traces (
                    id TEXT PRIMARY KEY,
                    -- 谁跑的 (LLM 调用 session / AI agent)
                    ai_session_id TEXT NOT NULL,
                    -- 输出关联 (这个 trace 派生出哪条 fact / decision / event)
                    output_entity_type TEXT NOT NULL,    -- 'atomic_fact' / 'key_decision' / 'org_event' / 'task'
                    output_entity_id TEXT,                -- 关联 id (写完才回填)
                    -- 输入: 用了哪些资料
                    input_doc_ids_json TEXT NOT NULL DEFAULT '[]',     -- v2_documents
                    input_chunk_ids_json TEXT NOT NULL DEFAULT '[]',   -- v2_chunks
                    input_fact_ids_json TEXT NOT NULL DEFAULT '[]',    -- 上游 atomic_facts
                    -- 过程: prompt + 模型
                    prompt_summary TEXT NOT NULL DEFAULT '',           -- 给的 prompt 摘要 (≤500 字, 不存全文避免重复存储)
                    prompt_log_id TEXT,                                -- 关联到 llm_context.prompt_log
                    model_name TEXT NOT NULL DEFAULT '',
                    model_version TEXT NOT NULL DEFAULT '',
                    -- 输出: AI 推理痕迹
                    reasoning_steps_json TEXT NOT NULL DEFAULT '[]',   -- ['观察 X 说 Y', '考虑 Z', '结论...']
                    output_summary TEXT NOT NULL DEFAULT '',           -- 最终结论 (一句话)
                    -- 结果元数据
                    confidence REAL NOT NULL DEFAULT 0.5,
                    triggered_update_relation TEXT NOT NULL DEFAULT 'none',
                        -- 'none' / 'conflict' / 'supersedes' / 'complement'
                    -- 时间 + 性能
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_ms INTEGER,
                    -- 状态
                    status TEXT NOT NULL DEFAULT 'pending',
                        -- 'pending' / 'completed' / 'failed' / 'reverted'
                    error_message TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_reasoning_traces_session
                    ON reasoning_traces(ai_session_id, started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_reasoning_traces_output_entity
                    ON reasoning_traces(output_entity_type, output_entity_id);
                CREATE INDEX IF NOT EXISTS idx_reasoning_traces_status
                    ON reasoning_traces(status, started_at DESC);
                """
            )
            # 索引: 按 verification_status 找待审 + 按 validity 过滤 superseded
            try:
                self.conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_atomic_facts_verification "
                    "ON atomic_facts(client_id, verification_status, content_role)"
                )
                self.conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_atomic_facts_validity "
                    "ON atomic_facts(client_id, validity_status, time_anchor DESC)"
                )
            except sqlite3.OperationalError:
                pass

            # ─────────────────────────────────────────────────────────────
            # v2.2 F1.9 (N3 A2 预留): event_log 持久化事件总线
            # 现有 broadcast_data_changed 是临时分发, 不落地。
            # 3.0 AI agent 需要看历史 (我上周做了什么) + 反馈学习信号 (用户撤销了哪些操作)
            # → 必须持久化每次写操作的事件流。
            #
            # 此表只写不读 (v2.2 阶段), 真实读取逻辑留 3.0 实施。
            # 现有 broadcast_data_changed 触发点会顺手写一行进来。
            # ─────────────────────────────────────────────────────────────
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,           -- e.g. 'client.fact_created' / 'task.completed'
                    actor_type TEXT NOT NULL DEFAULT 'human',  -- N3: human/ai_agent/system
                    actor_id TEXT NOT NULL DEFAULT '',
                    entity_type TEXT NOT NULL,          -- 'client' / 'task' / 'event_line' / 'fact'
                    entity_id TEXT NOT NULL,
                    client_id TEXT,                     -- 关联客户 (可空, 组织级事件无)
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    occurred_at TEXT NOT NULL,
                    reversed_at TEXT,                   -- 爱马仕"终身保修"原则: 可撤销时填这里
                    reversed_by TEXT,                   -- 撤销人
                    reversed_reason TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_event_log_entity
                    ON event_log(entity_type, entity_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_event_log_client_time
                    ON event_log(client_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_event_log_event_type
                    ON event_log(event_type, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_event_log_actor
                    ON event_log(actor_type, actor_id, occurred_at DESC);
                """
            )

            # ─────────────────────────────────────────────────────────────
            # v2.2 F2.0 (N3 A5 预留): AI Memory 5 张表占位
            # 配合 NORTH_STAR N3 "为 3.0 埋好接入基础, 不返工"
            #
            # 3.0 是"给 AI 配共享办公室" — AI 跟人共享同一工作空间, 越用越聪明。
            # 越用越聪明的具体机制需要 4 类记忆 (我跟 Claude 自己的 memory 系统验证过):
            #   1. 事件记忆 (AI 做了什么) → ai_episode_log
            #   2. 反馈学习 (用户纠正过的) → ai_learned_rules
            #   3. 用户偏好 (写作风格/忌讳) → user_ai_preferences
            #   4. 程序记忆 (工作套路) → project_procedures
            #   + 用户对 AI 输出的评价 → ai_feedback_signals
            #
            # v2.2 阶段: 只 CREATE + 单向写入, 不读取。
            # 上线那天就开始积累真实数据, 3.0 启动时有 N 个月样本, 不是空白账户。
            # 这是 Anthropic dogfood 哲学: 启动越晚越亏。
            # ─────────────────────────────────────────────────────────────
            self.conn.executescript(
                """
                -- ① ai_episode_log: AI 每次行动的日志 (干了什么、为什么、引用了哪些 fact)
                CREATE TABLE IF NOT EXISTS ai_episode_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ai_session_id TEXT NOT NULL,
                    user_id TEXT,                       -- 跟哪个用户协作 (空 = 后台 AI 任务)
                    client_id TEXT,                     -- 关联客户 (可空)
                    action_type TEXT NOT NULL,          -- 'extracted_fact' / 'created_task' / 'sent_clarification' / ...
                    action_summary TEXT NOT NULL DEFAULT '',
                    referenced_fact_ids_json TEXT NOT NULL DEFAULT '[]',  -- AI 引用了哪些 atomic_facts
                    referenced_doc_ids_json TEXT NOT NULL DEFAULT '[]',   -- 引用了哪些 v2_documents
                    outcome TEXT NOT NULL DEFAULT 'pending',  -- 'pending' / 'accepted' / 'rejected' / 'reverted'
                    occurred_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ai_episode_log_session
                    ON ai_episode_log(ai_session_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_ai_episode_log_user_client
                    ON ai_episode_log(user_id, client_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_ai_episode_log_outcome
                    ON ai_episode_log(outcome, occurred_at DESC);

                -- ② ai_learned_rules: 从用户纠错中抽出的规则 (类似我的 feedback_* memory)
                CREATE TABLE IF NOT EXISTS ai_learned_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT NOT NULL,             -- e.g. 'never_use_word_empowerment'
                    rule_body TEXT NOT NULL,             -- 规则正文
                    rule_why TEXT NOT NULL DEFAULT '',   -- 用户给的理由
                    rule_how_to_apply TEXT NOT NULL DEFAULT '',  -- 什么场景下激活
                    learned_from_episode_id INTEGER,     -- 从哪条 episode 抽出来的
                    confidence REAL NOT NULL DEFAULT 0.5, -- 用户重复纠正会涨
                    activated_count INTEGER NOT NULL DEFAULT 0,  -- 这条规则被激活几次
                    user_id TEXT,                        -- 哪个用户的规则 (空 = 全局)
                    client_id TEXT,                      -- 哪个客户的规则 (空 = 全用户/全客户)
                    learned_at TEXT NOT NULL,
                    last_activated_at TEXT,
                    FOREIGN KEY(learned_from_episode_id) REFERENCES ai_episode_log(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ai_learned_rules_user_client
                    ON ai_learned_rules(user_id, client_id, confidence DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_learned_rules_name_scope
                    ON ai_learned_rules(rule_name, COALESCE(user_id, ''), COALESCE(client_id, ''));

                -- ③ user_ai_preferences: 用户级别的 AI 协作偏好 (类似我的 user_* memory)
                CREATE TABLE IF NOT EXISTS user_ai_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    preference_key TEXT NOT NULL,        -- e.g. 'writing_style' / 'response_length' / 'preferred_format'
                    preference_value TEXT NOT NULL,      -- e.g. '直接不绕弯' / 'short' / 'markdown_table'
                    inferred_from TEXT NOT NULL DEFAULT 'user_explicit',  -- 'user_explicit' / 'ai_inferred' / 'history_pattern'
                    confidence REAL NOT NULL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_user_ai_preferences_key
                    ON user_ai_preferences(user_id, preference_key);

                -- ④ project_procedures: 项目级别的执行套路 (e.g. 给日慈写工作坊方案的 6 步)
                CREATE TABLE IF NOT EXISTS project_procedures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_name TEXT NOT NULL,        -- e.g. 'workshop_proposal_for_rici'
                    client_id TEXT,                      -- 哪个客户 (空 = 通用套路)
                    project_category TEXT NOT NULL DEFAULT '',  -- 'workshop' / 'contract' / 'review' / ...
                    steps_json TEXT NOT NULL DEFAULT '[]',  -- 步骤序列, 每步含 {step_name, expected_output, ai_can_do, requires_human}
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_executed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_project_procedures_client_category
                    ON project_procedures(client_id, project_category);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_project_procedures_name
                    ON project_procedures(procedure_name, COALESCE(client_id, ''));

                -- ⑤ ai_feedback_signals: 用户对 AI 输出的明确反馈 (👍/👎/修改)
                CREATE TABLE IF NOT EXISTS ai_feedback_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER NOT NULL,         -- 关联到 ai_episode_log
                    user_id TEXT NOT NULL,
                    signal_type TEXT NOT NULL,           -- 'thumbs_up' / 'thumbs_down' / 'edited' / 'reverted' / 'accepted'
                    signal_target TEXT NOT NULL DEFAULT '',  -- 反馈针对的具体字段 ('action_summary' / 'reasoning' / ...)
                    user_correction TEXT NOT NULL DEFAULT '',  -- 用户的修正内容 (用于训练 ai_learned_rules)
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(episode_id) REFERENCES ai_episode_log(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_ai_feedback_signals_episode
                    ON ai_feedback_signals(episode_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_ai_feedback_signals_user_signal
                    ON ai_feedback_signals(user_id, signal_type, created_at DESC);

                -- ⑥ ai_improvement_suggestions (顾源源 5/22 洞察 — AI 反向给人类提流程建议)
                -- 不是给单条事实澄清, 而是 AI 在执行多次任务后发现"工具/流程本身缺什么"
                -- 例: AI 多次拟合同时分不清"服务类 vs 销售类", 建议系统加一个新标签
                --
                -- 被动展示模式 (顾源源原话): 不主动 push, 用户进 "设置 → AI 管理" 才看 list
                -- 跟"AI 不主动讨好/扩张"的偏好一致
                CREATE TABLE IF NOT EXISTS ai_improvement_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ai_session_id TEXT,                  -- 哪个 AI session 提的
                    suggestion_category TEXT NOT NULL,   -- 'add_tag' / 'add_field' / 'change_workflow' / 'fix_naming'
                    suggestion_title TEXT NOT NULL,      -- 一句话标题
                    suggestion_body TEXT NOT NULL,       -- 详细说明
                    observed_pain_count INTEGER NOT NULL DEFAULT 1,  -- AI 遇到这个痛点几次了 (重复 → 升优先级)
                    related_episode_ids_json TEXT NOT NULL DEFAULT '[]',  -- 关联到哪些 ai_episode_log
                    suggested_at TEXT NOT NULL,
                    last_observed_at TEXT NOT NULL,
                    review_status TEXT NOT NULL DEFAULT 'pending',  -- pending/accepted/rejected/implemented
                    reviewed_by TEXT,                    -- 用户 id
                    reviewed_at TEXT,
                    review_note TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_ai_improvement_suggestions_pending
                    ON ai_improvement_suggestions(review_status, observed_pain_count DESC, last_observed_at DESC);
                CREATE INDEX IF NOT EXISTS idx_ai_improvement_suggestions_category
                    ON ai_improvement_suggestions(suggestion_category, suggested_at DESC);
                """
            )
            # 回填：external_* / 社交平台 / 公众号等外部观察源
            # 容错: data_center_ingest_events 表可能在某些精简 db 里不存在, 不阻塞启动
            try:
                self.conn.execute(
                    """
                    UPDATE data_center_ingest_events
                    SET evidence_tier = 'external_observation'
                    WHERE source_type IN (
                        'external_search_engine', 'external_sentiment', 'external_timely',
                        'wechat_article', 'weibo_post', 'xiaohongshu_note',
                        'zhihu_answer', 'bilibili_video', 'baijiahao_article',
                        'douyin_video'
                    ) AND evidence_tier = 'first_party'
                    """
                )
                # 回填：权威外部源
                self.conn.execute(
                    """
                    UPDATE data_center_ingest_events
                    SET evidence_tier = 'third_party_authoritative'
                    WHERE source_type IN (
                        'tianyancha_basic', 'tianyancha_risk',
                        'foundation_registry', 'enterprise_credit'
                    ) AND evidence_tier = 'first_party'
                    """
                )
            except sqlite3.OperationalError:
                pass  # 表不存在 → 跳过 backfill
            # P6: 客户 canonical 化 - 多别名 (e.g. 日慈基金会 / 日慈公益基金会 / 日慈慈善基金会)
            # 建客户时实时模糊匹配防止多人重复建客户, collaborator 加入既有客户的基础
            self._ensure_column("clients", "aliases_json", "TEXT NOT NULL DEFAULT '[]'")
            # P7: 项目编辑弹窗扩展字段
            #   related_user_ids_json: 选中的相关同事 user.id 列表（多对多关联，方便初期用 JSON 列；
            #     批 3 接通 cloud 时复用 cloud_backend 的 task_collaborators 模式建独立关联表）
            #   is_data_center_included: 0 = 仅工作台可见（不进入战略陪伴/咨询/情报/任务计算），
            #     1 = 参与全局数据中心（默认）。本地过滤靠这一列。
            self._ensure_column("clients", "related_user_ids_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column("clients", "is_data_center_included", "INTEGER NOT NULL DEFAULT 1")
            # 全局冷冻字段:用户主动把项目"冷冻"后,所有自动 job 跳过这个客户
            # (爬取/数据中心计算/资讯抓取/知识库索引等),所有列客户的 endpoint 默认不返回它
            # NULL = 未冷冻;有值 = 冷冻时间(ISO 字符串,审计用)
            self._ensure_column("clients", "frozen_at", "TEXT")
            # 批 3：clients 接通 cloud sync 所需字段（mimic event_lines / tasks 的 sync schema）
            self._ensure_column("clients", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("clients", "cloud_id", "TEXT")
            self._ensure_column("clients", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("clients", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("clients", "last_sync_error", "TEXT NOT NULL DEFAULT ''")
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
            self._ensure_column("tasks", "reminder_minutes_before", "INTEGER")  # 5/29 任务提醒: 0=准时 5=提前5分 NULL=不提醒
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
            # 第一档 #2 fix: tasks 4 个 backfill UPDATE 包显式事务. 中途崩 → rollback 不留半成品.
            # 这些 backfill 都是 idempotent (带 WHERE IS NULL), 重做安全.
            self.conn.commit()  # 先 commit 之前累积的 _ensure_column, 让 backfill 独立成段
            try:
                self.conn.execute("BEGIN IMMEDIATE")
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
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
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
            # 第一档 #3 fix: 逐行 UPDATE 循环 三表 (documents/v2_documents/memory_facts) 包事务.
            # 原 bug: 每行独立 commit, 循环跑到一半崩 → 留下部分 department_ids_json 已填部分未填
            # 的半脏数据. 现在: 三表整体作为一个事务, 中途崩全部 rollback, 下次启动重做完整循环.
            self.conn.commit()
            try:
                self.conn.execute("BEGIN IMMEDIATE")
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
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

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
            # 中断恢复重试计数：进程崩溃/重启时把残留 run 重新入队，attempt 累加，达上限才判失败。
            self._ensure_column("client_template_fill_runs", "attempt", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("workspace_link_import_runs", "attempt", "INTEGER NOT NULL DEFAULT 0")
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
            # Stage B 扇出 #4：矛盾检测命中已有 confirmed judgment 时打标，提示用户重新评估
            self._ensure_column("judgment_versions", "needs_reevaluation", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("judgment_versions", "reevaluation_reason", "TEXT")
            self._ensure_column("judgment_versions", "reevaluation_triggered_at", "TEXT")
            # Stage B 扇出 #7：深度资料 ingest 时标记客户画像需要复审
            self._ensure_column("client_strategic_profiles", "needs_review", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("client_strategic_profiles", "review_reason", "TEXT")
            self._ensure_column("client_strategic_profiles", "review_triggered_at", "TEXT")
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

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # P0 · 项目画像三大缺口表 (关联/风险/承诺) + tasks 挂字典字段
            # 用户视角: 字典就是项目画像 = 项目档案 = 事实澄清页面
            # 现在补的是: 节点之间的"边"(关联), 落散的风险信号, 结构化承诺
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS glossary_relations (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    subject_term_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object_term_id TEXT,
                    object_external_type TEXT,
                    object_external_id TEXT,
                    source TEXT NOT NULL DEFAULT 'ai_inferred',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_glossary_relations_client_subject
                    ON glossary_relations(client_id, subject_term_id);
                CREATE INDEX IF NOT EXISTS idx_glossary_relations_client_predicate
                    ON glossary_relations(client_id, predicate);
                CREATE INDEX IF NOT EXISTS idx_glossary_relations_object_external
                    ON glossary_relations(object_external_type, object_external_id);

                CREATE TABLE IF NOT EXISTS risk_signals (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    signal_kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    severity TEXT NOT NULL DEFAULT 'medium',
                    related_term_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_type TEXT NOT NULL DEFAULT '',
                    source_id TEXT NOT NULL DEFAULT '',
                    captured_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    resolution_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_risk_signals_client_status
                    ON risk_signals(client_id, status, captured_at DESC);
                CREATE INDEX IF NOT EXISTS idx_risk_signals_severity
                    ON risk_signals(severity, status);

                CREATE TABLE IF NOT EXISTS commitments (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    committer TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    commitment_type TEXT NOT NULL DEFAULT 'delivery',
                    content TEXT NOT NULL,
                    deadline TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    related_term_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_type TEXT NOT NULL DEFAULT '',
                    source_id TEXT NOT NULL DEFAULT '',
                    fulfilled_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_commitments_client_status
                    ON commitments(client_id, status, deadline);
                CREATE INDEX IF NOT EXISTS idx_commitments_committer
                    ON commitments(client_id, committer, status);

                -- narrative 建议消费日志 (用户对 AI 建议的操作历史)
                -- 用户视角: 推荐 → 我点 → / 完成 / 删除 → 进日志卡, 不再被抽
                -- fingerprint = hash(actor + suggestion_text 前 50 字), 跨 regen 永久去重
                -- action ∈ ('promoted', 'completed', 'dismissed')
                CREATE TABLE IF NOT EXISTS narrative_suggestion_log (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL DEFAULT '',
                    suggestion_text TEXT NOT NULL,
                    source_doc_title TEXT NOT NULL DEFAULT '',
                    source_doc_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_suggestion_log_client_fingerprint
                    ON narrative_suggestion_log(client_id, fingerprint);
                CREATE INDEX IF NOT EXISTS idx_suggestion_log_client_action_at
                    ON narrative_suggestion_log(client_id, action, created_at DESC);

                -- "下一步要做什么" 背景说明缓存 (转任务时瞬时返回)
                -- next-steps endpoint 返回列表时, 后台线程并发预生成 LLM 背景写入此表
                -- 用户点 → 时直接读 cache, 体感瞬时
                CREATE TABLE IF NOT EXISTS next_step_background_cache (
                    client_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    background TEXT NOT NULL,
                    source_label TEXT NOT NULL DEFAULT '',
                    has_source INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (client_id, fingerprint),
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_nsb_cache_client_at
                    ON next_step_background_cache(client_id, created_at DESC);

                -- narrative 待重生标记 (战略陪伴页面打开时检测, 自动后台 regenerate)
                -- ingest fanout 完成时 upsert 一行, 前端通过 /narrative/stale-status 查
                -- 当 marked_at > narrative.generatedAt 即 stale
                CREATE TABLE IF NOT EXISTS narrative_stale_signals (
                    client_id TEXT PRIMARY KEY,
                    marked_at TEXT NOT NULL,
                    last_doc_title TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                -- 战略陪伴叙事「本地优先镜像」(5/29): 把生成/拉取到的整段叙事存本地一份,
                -- GET 本地优先读它(断网/慢网/VPN误路由可读上次版本, 且不每次打开都拉云端);
                -- regenerate 成功/失败都写它(本地生成的 dims 一定落地, 线上混合更新);
                -- stale-status 用它的 generated_at 比对, 省掉每次打开的云端往返。
                -- 整段存 record_json, 不分维度列(避开云端新旧维度列不一致)。一客户存最新一版。
                CREATE TABLE IF NOT EXISTS client_narrative_local_mirror (
                    client_id TEXT PRIMARY KEY,
                    rev INTEGER NOT NULL DEFAULT 0,
                    generator TEXT NOT NULL DEFAULT '',
                    model_name TEXT NOT NULL DEFAULT '',
                    generated_at TEXT NOT NULL DEFAULT '',
                    overall_confidence REAL NOT NULL DEFAULT 0.0,
                    open_clarifications_count INTEGER NOT NULL DEFAULT 0,
                    record_json TEXT NOT NULL DEFAULT '{}',
                    source TEXT NOT NULL DEFAULT 'cloud',
                    mirrored_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );

                -- L1: 能力周快照（让"方向感"成为成长中心一等公民）
                -- 每周日（或懒触发）写入一行，记录当周末该用户每个能力的 currentScore / totalXp。
                -- 前端拉最近 8 周即可画 mini 折线图，看出每个能力是涨/跌/横盘。
                CREATE TABLE IF NOT EXISTS growth_ability_weekly_snapshot (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    week_label TEXT NOT NULL,
                    ability_key TEXT NOT NULL,
                    current_score INTEGER NOT NULL DEFAULT 0,
                    total_xp INTEGER NOT NULL DEFAULT 0,
                    snapshot_at TEXT NOT NULL,
                    UNIQUE(user_id, week_label, ability_key)
                );
                CREATE INDEX IF NOT EXISTS idx_growth_weekly_user_week
                    ON growth_ability_weekly_snapshot(user_id, week_label DESC, ability_key);

                -- L6: 学习推荐反馈闭环（用户对推荐内容的行为信号）
                CREATE TABLE IF NOT EXISTS growth_recommendation_feedback (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    source TEXT NOT NULL,                -- handbook / exp_wall / github / exa
                    source_id TEXT NOT NULL,
                    action TEXT NOT NULL,                -- clicked / saved / dismissed / completed
                    matched_ability TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_growth_rec_feedback_user
                    ON growth_recommendation_feedback(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_growth_rec_feedback_source
                    ON growth_recommendation_feedback(source, source_id);
                """
            )
            self._ensure_column("tasks", "glossary_term_ids", "TEXT NOT NULL DEFAULT '[]'")

            # ── 组织经验墙云端同步字段 (顾源源 5/27 方案 A) ──
            # 同步状态机:
            #   local   → 仅本地, 没推过云端 (默认值)
            #   pending → 改了, 等待 push (本地写入/删除/reaction 触发设置)
            #   synced  → push 成功, 云端已收到
            #   failed  → push 失败, 等下次 background 重试
            # pending_sync_action: 'upsert' = 推内容; 'delete' = 推软删除
            self._ensure_column("exp_wall_quotes", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("exp_wall_quotes", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("exp_wall_quotes", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("exp_wall_reactions", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("exp_wall_reactions", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("exp_wall_reactions", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")

            # 真 handbook_entries 真**才是前端真用真"经验墙"** (顾源源 5/27)
            # 真同 sync 状态机模式 (local/pending/synced/failed + upsert/delete)
            self._ensure_column("handbook_entries", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("handbook_entries", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("handbook_entries", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")

            # 真 成长积分云端同步字段 (顾源源 5/27 阶段 1 · "卷"机制核心)
            # 真同步: signal_events (信号源) + evidence_records (证据/积分) + validation_events (验证)
            # 真不同步: ability_profiles (seed) / capture_states (派生) / weekly_snapshot (派生)
            self._ensure_column("growth_signal_events", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("growth_signal_events", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_signal_events", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_signal_events", "updated_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_evidence_records", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("growth_evidence_records", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_evidence_records", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_evidence_records", "updated_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_validation_events", "sync_status", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("growth_validation_events", "last_synced_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_validation_events", "pending_sync_action", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("growth_validation_events", "updated_at", "TEXT NOT NULL DEFAULT ''")

            # event_line_delete_tombstones 表早就有了，但缺一列 merged_to_id —
            # 合并事件线时记录"源被合并到了哪条目标 event_line"。
            # 之后云端 pull 拉回 tasks 时，如果发现 task.eventLineId 命中了
            # 这个 tombstone，会把它重定向到 merged_to_id（而不是写回已删的源 id），
            # 否则本地 task 的 event_line_id 会被云端反向覆盖、任务数对不上。
            self._ensure_column("event_line_delete_tombstones", "merged_to_id", "TEXT NOT NULL DEFAULT ''")

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # P0.5 · 字典属性表 (数值/事实型属性 → cite 锚点, 防幻觉核心)
            # 跟 glossary_relations 并列, 专装 "term.attribute = value" 这类事实
            # 经过 verification_status='verified' 的属性才能被 chat cite
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS glossary_attributes (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    term_id TEXT NOT NULL,
                    attribute_name TEXT NOT NULL,
                    value_category TEXT NOT NULL DEFAULT 'text',
                    value_text TEXT NOT NULL,
                    value_normalized REAL,
                    value_unit TEXT NOT NULL DEFAULT '',
                    scope TEXT NOT NULL DEFAULT '',
                    as_of_date TEXT,
                    source_type TEXT NOT NULL DEFAULT 'ai_inferred',
                    source_doc_id TEXT,
                    source_evidence TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    verification_status TEXT NOT NULL DEFAULT 'pending',
                    verified_by TEXT,
                    verified_at TEXT,
                    rejection_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_glossary_attr_client_term
                    ON glossary_attributes(client_id, term_id, verification_status);
                CREATE INDEX IF NOT EXISTS idx_glossary_attr_name
                    ON glossary_attributes(client_id, attribute_name, verification_status);
                CREATE INDEX IF NOT EXISTS idx_glossary_attr_verified
                    ON glossary_attributes(client_id, verification_status, as_of_date DESC);

                CREATE TABLE IF NOT EXISTS glossary_drift_alerts (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    glossary_attribute_id TEXT NOT NULL,
                    new_fact_id TEXT NOT NULL,
                    verified_value_text TEXT NOT NULL,
                    new_value_text TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'medium',
                    review_status TEXT NOT NULL DEFAULT 'pending',
                    review_note TEXT NOT NULL DEFAULT '',
                    detected_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewed_by TEXT,
                    FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
                    FOREIGN KEY(glossary_attribute_id) REFERENCES glossary_attributes(id) ON DELETE CASCADE,
                    FOREIGN KEY(new_fact_id) REFERENCES atomic_facts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_glossary_drift_client_pending
                    ON glossary_drift_alerts(client_id, review_status, detected_at DESC);
                """
            )

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
            # 第一档 #1 fix: schema_version 写入时机从这里 (3819) 移到 _init_schema 最末
            # (4088 commit 之前). 原 bug: user_version 早写, 后续 _ensure_column/UPDATE backfill
            # 跨多个 executescript auto-commit, 任意一段崩了 → user_version 已写=系统认为
            # "迁移完成"=下次跳过重做 → B-tree 半改状态永久保留. 这就是 20260518 那次坏 db
            # 的根因. 新规则: 整个 _init_schema 跑完才写 user_version, 中途崩 → 重做迁移
            # (DDL/UPDATE backfill 全部 idempotent, 重做安全).
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
            # 对象存储配置（I1b-1）：单行配置，承载文件中转/归档所需的桶/凭证
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
                """
                CREATE TABLE IF NOT EXISTS trashed_files (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL DEFAULT '',
                    original_path TEXT NOT NULL,
                    trashed_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL DEFAULT 0,
                    original_document_id TEXT NOT NULL DEFAULT '',
                    original_title TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT 'dedup_merge',
                    trashed_at TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_trashed_files_trashed_at
                    ON trashed_files(trashed_at)
                """
            )
            # ──────────────────────────────────────────────────────────
            # 舆情印象主题簇（P5）：跨多条 items 聚出 3-7 个 brand impression
            # ──────────────────────────────────────────────────────────
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS intelligence_sentiment_themes (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    theme_label TEXT NOT NULL,
                    theme_summary TEXT NOT NULL DEFAULT '',
                    sentiment_tone TEXT NOT NULL DEFAULT 'neutral',
                    item_count INTEGER NOT NULL DEFAULT 0,
                    representative_quote TEXT NOT NULL DEFAULT '',
                    representative_item_id TEXT,
                    item_ids_json TEXT NOT NULL DEFAULT '[]',
                    computed_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_intelligence_sentiment_themes_scope
                    ON intelligence_sentiment_themes(scope_type, scope_id, expires_at DESC)
                """
            )
            # ──────────────────────────────────────────────────────────
            # 品牌印象速读（P6）：LLM 把 themes/gap/items 合成公关风格简报
            # 单 scope 单条记录，重算时整条覆盖
            # ──────────────────────────────────────────────────────────
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS intelligence_brand_audits (
                    id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    headline TEXT NOT NULL DEFAULT '',
                    narrative_md TEXT NOT NULL DEFAULT '',
                    tensions_json TEXT NOT NULL DEFAULT '[]',
                    recommendations_json TEXT NOT NULL DEFAULT '[]',
                    content_angles_json TEXT NOT NULL DEFAULT '{}',
                    evidence_theme_ids_json TEXT NOT NULL DEFAULT '[]',
                    computed_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope_type, scope_id)
                )
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_intelligence_brand_audits_scope
                    ON intelligence_brand_audits(scope_type, scope_id, expires_at DESC)
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

            # v2.1 Modular Monolith:加载模块 schema(每模块自包含)
            # 第一砖:organization 模块(4 张 cloud mirror 表 + readonly 触发器)
            from app.modules.organization import SCHEMA_SQL as ORGANIZATION_SCHEMA_SQL
            self.conn.executescript(ORGANIZATION_SCHEMA_SQL)

            # 第二砖:llm_context 模块(prompt_log 表 · Karpathy 一等公民)
            from app.llm_context import SCHEMA_SQL as LLM_CONTEXT_SCHEMA_SQL
            self.conn.executescript(LLM_CONTEXT_SCHEMA_SQL)

            # P0-freeze 统一:stage 是冻结状态的云安全唯一真相源。历史上 /freeze 端点
            # 只写 frozen_at,把这些行迁移到 stage='frozen',否则 v_active_clients 改用
            # stage 过滤后(WHERE stage != 'frozen')这些历史冻结客户会错误地重新出现。
            # 幂等:仅命中 frozen_at 有值但 stage 未冻结/归档/丢失的行,跑一次后即空集。
            self.conn.execute(
                "UPDATE clients SET stage = 'frozen' "
                "WHERE frozen_at IS NOT NULL AND stage NOT IN ('frozen', 'archived', 'lost')"
            )

            # 6 个核心 SQL Views(CQRS read model · 临时聚合在 organization 模块)
            # 必须最后建,因为引用了 mirror 表 + clients/event_lines/tasks 等业务表
            from app.modules.organization import VIEWS_SQL as ORGANIZATION_VIEWS_SQL
            self.conn.executescript(ORGANIZATION_VIEWS_SQL)

            # 第一档 #1 fix: user_version 现在在所有迁移完 + 最后 commit 之前的一步写,
            # 确保中途崩不会被错标"已迁移". 这是上次 (20260518) db 损坏的根因修复.
            current_schema_version = int(self.conn.execute("PRAGMA user_version").fetchone()[0] or 0)
            if current_schema_version < BACKEND_SCHEMA_VERSION:
                self.conn.execute(f"PRAGMA user_version={BACKEND_SCHEMA_VERSION}")
            self.conn.commit()

    def _seed_builtin_writing_skills(self) -> None:
        """启动时 seed 内置写作风格 skill。

        策略：每个内置 skill 用固定的 id（如 'skill_builtin_luoyonghao'），
        如果该 id 不存在则插入；如果存在则不动（不覆盖用户可能改过的 sort_order）。
        """
        from datetime import datetime, timezone

        builtins = [
            {
                "id": "skill_builtin_luoyonghao",
                "name": "罗永浩风格",
                "description": "段子手 + 大字报 + 自嘲。直球判断，长短句猛烈交错，每隔几段必有金句。",
                "distilled_md": _LUOYONGHAO_STYLE_PROMPT,
                "sort_order": 10,
            },
        ]
        now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        for entry in builtins:
            existing = self.conn.execute(
                "SELECT id FROM writing_skills WHERE id = ?", (entry["id"],)
            ).fetchone()
            if existing:
                continue
            self.conn.execute(
                """
                INSERT INTO writing_skills(
                    id, name, description, distilled_md, is_builtin, sort_order, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    entry["id"],
                    entry["name"],
                    entry["description"],
                    entry["distilled_md"],
                    entry["sort_order"],
                    now,
                    now,
                ),
            )

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        existing = {
            str(row["name"])
            for row in self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if not existing:
            return
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
                if not self._in_transaction:
                    self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def executemany(self, query: str, params: list[tuple]) -> None:
        with self._lock:
            try:
                self.conn.executemany(query, params)
                if not self._in_transaction:
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
        """callback 签名: (conn) -> Any. 内部建议直接用 conn.execute,
        但因为 _lock 是 RLock + _in_transaction 标志, callback 内调
        state.db.execute(...) 也安全 (不会死锁, 不会提前 commit)."""
        with self._lock:
            already_in_tx = self._in_transaction
            if already_in_tx:
                # 嵌套调用: 不开新事务, 直接走 callback (外层会 commit)
                return callback(self.conn)
            self._in_transaction = True
            try:
                self.conn.execute(f"BEGIN {mode}")
                result = callback(self.conn)
                self.conn.commit()
                return result
            except Exception:
                self.conn.rollback()
                raise
            finally:
                self._in_transaction = False

    def begin_transaction(self, mode: str = "IMMEDIATE") -> None:
        """显式事务 API. 必须配对调用 commit_transaction() 或 rollback_transaction().

        嵌套语义: 内层 begin/commit 只增减深度, 不真 BEGIN/COMMIT.
        任意一层 rollback 标记整体失败, 最外层 commit 时改成 rollback (安全).
        """
        self._lock.acquire()
        try:
            if self._tx_depth == 0:
                self.conn.execute(f"BEGIN {mode}")
                self._tx_failed = False
            self._tx_depth += 1
            self._in_transaction = True
        except Exception:
            self._lock.release()
            raise

    def commit_transaction(self) -> None:
        """提交本层. 仅最外层真的 COMMIT; 内层只减深度.
        若任意层已标失败 (rollback_transaction 调过), 最外层改成 ROLLBACK."""
        try:
            if self._tx_depth == 0:
                return  # 配对错误的容错, 不抛
            self._tx_depth -= 1
            if self._tx_depth == 0:
                try:
                    if self._tx_failed:
                        self.conn.rollback()
                    else:
                        self.conn.commit()
                finally:
                    self._tx_failed = False
                    self._in_transaction = False
        finally:
            self._lock.release()

    def rollback_transaction(self) -> None:
        """标记整体失败. 仅最外层真的 ROLLBACK; 内层只标 _tx_failed + 减深度."""
        try:
            if self._tx_depth == 0:
                return
            self._tx_failed = True
            self._tx_depth -= 1
            if self._tx_depth == 0:
                try:
                    self.conn.rollback()
                finally:
                    self._tx_failed = False
                    self._in_transaction = False
        finally:
            self._lock.release()

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
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        # P0 修复: 损坏 JSON 不应该让上层崩溃; 用 default 兜底
        return default
