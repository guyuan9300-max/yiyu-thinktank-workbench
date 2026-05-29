"""llm_context schema · prompt_log 表(LLM 调用全量持久化)

设计原则:
- 每次 LLM 调用都记一条 row(prompt + system + output + 耗时 + tokens)
- 不裁剪 / 不压缩 prompt 文本(数据驱动的根基)
- 索引按 intent / client_id / created_at,便于回查
- 评分字段 score 可选(人工标注 / 自动评分)
"""

LLM_CONTEXT_SCHEMA_VERSION = 1


SCHEMA_SQL = """
-- ══════════════════════════════════════════════════════════════════════════════
-- llm_context 模块 · prompt_log
-- v2.1 Karpathy 原则:LLM context 是一等公民,所有调用全持久化用于数据驱动改进
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS prompt_log (
    id              TEXT PRIMARY KEY,
    intent          TEXT NOT NULL,           -- narrative / qa / intelligence_query / task_brief / ...
    client_id       TEXT,                    -- 关联 client(可空,如全局 qa)
    user_id         TEXT,                    -- 调用者 user_id(可空)
    system_text     TEXT NOT NULL DEFAULT '',
    prompt_text     TEXT NOT NULL,
    output_text     TEXT NOT NULL DEFAULT '',
    duration_ms     REAL NOT NULL DEFAULT 0,
    tokens_used     INTEGER NOT NULL DEFAULT 0,
    model_id        TEXT NOT NULL DEFAULT '', -- 像 'qwen3-vl:32b' / 'gpt-4o'
    error           TEXT NOT NULL DEFAULT '', -- 失败时的错误信息
    score           REAL,                     -- 人工或自动评分 0.0-1.0
    score_note      TEXT NOT NULL DEFAULT '',
    metadata_json   TEXT NOT NULL DEFAULT '{}', -- 额外元数据(像 retry_count / 用户反馈)
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prompt_log_intent_created
    ON prompt_log(intent, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_prompt_log_client_created
    ON prompt_log(client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_prompt_log_user_created
    ON prompt_log(user_id, created_at DESC);
"""
