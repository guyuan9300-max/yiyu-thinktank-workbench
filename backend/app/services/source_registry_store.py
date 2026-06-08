"""[A] V2.3 阶段 1 P0 · Source Registry · 数据中心第 1 层 来源登记

服务: docs/V2.3_DATA_CENTER_MASTER_PLAN.md § 七 第 1 层 + 顾源源 5/22 22:30 钦定

定位:
  所有数据进入数据中心**先到 source_registry**登记,然后才能进入第 2-7 层.
  没有 source_registry record 的数据不允许写入 atomic_facts / fact_clusters 等.

蓝图 § 七 14 字段:
  source_id / source_type / source_channel / source_owner
  client_id / project_id / user_id / org_id
  source_time / capture_time
  visibility_scope / content_hash / version_id
  source_role / initial_confidence / raw_reference

A 视角扩字段(蓝图 § 末尾 A 补充):
  prev_version_id (版本链)
  status (active/archived/dismissed)

跟 atomic_facts 关系:
  · atomic_facts.source_registry_id → source_registry.source_id (N:1)
  · 一条 source 可抽出多条 atomic_facts (1 docx → 30 facts)
  · 一条 source 也可不抽 (附件 / 仅引用)
"""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Protocol


# ─── 类型 ──────────────────────────────────────────────


SourceType = Literal[
    # 顾源源蓝图 4 大主路径 + 系统
    "workbench_file",       # 路径 2: 工作台上传文件 / 智能文件导入
    "task_review",          # 路径 1: 任务 / 复盘 / 承诺 / 会议
    "internet_crawl",       # 路径 3: 爬虫 / 资讯情报
    "oral_claim",           # 路径 4: 用户口述 / 对话 / 手机 AI 聊天
    # 子源
    "user_correction",      # 工作台 / 战略陪伴 用户纠错(高置信)
    "user_verification",    # 战略陪伴 用户采纳 / 修正 / 忽略
    "ai_extracted",         # LLM 从其他源抽出的结构化(派生)
    "ai_inference",         # AI 主动研判 (战略陪伴思考研判)
    "system_log",           # broadcast / 自校验 / reaper (技术性)
    "external_intel",       # 外部情报 (公开舆情 / 政策)
    "method_card",          # 成长中心方法卡 (有限域置信)
    "plan_item",            # 组织计划工坊计划项
    "feishu_sync",          # 飞书同步资料 (有显式绑定)
]

SourceChannel = Literal[
    # workbench_file 子 channel
    "smart_file_import",
    "workbench_upload",
    "link_material_import",
    # task_review 子 channel
    "task_create",
    "weekly_review",
    "meeting_action_item",
    "decision_record",
    # internet_crawl 子 channel
    "intelligence_radar",
    "intelligence_brand_audit",
    "website_audit",
    # oral_claim 子 channel
    "workspace_chat",       # 工作台对话框
    "smart_import_narration",  # 智能导入讲述框
    "mobile_ai_chat",       # 手机 AI 朋友式聊天 (未启动)
    # user_correction 子 channel
    "narrative_clarification",  # 战略陪伴澄清面板
    "glossary_attribute_verify",  # 字典属性 verify
    "fact_edit_inline",         # 就地编辑 ✏️
    # ai_* 子 channel
    "document_llm_extractor",
    "narrative_generator",
    "ai_self_verify",       # L3 自校验
    "strategic_thought_generator",  # 战略思考研判
    # 兜底
    "unknown",
]

# 蓝图 § 三智能导入: 文件角色
SourceRole = Literal[
    "client_official",      # 客户合同/章程/正式方案 — 最高
    "client_internal",      # 客户内部讨论/草稿
    "partner_submission",   # 合作方提交方案
    "yiyu_advisory",        # 益语顾问产出 — 我方判断
    "external_reference",   # 外部对标
    "policy_industry",      # 行业政策
    "media_observation",    # 外部媒体观察 (L2)
    "ugc_signal",          # UGC 信号 (L3)
    "user_oral",           # 用户口述
    "ai_derived",          # AI 派生
    "system_internal",     # 系统内部
    "unknown",
]

VisibilityScope = Literal[
    "org",                  # 组织内全员可见
    "client",               # 该客户协作者可见
    "user",                 # 仅 owner 可见
    "public",               # 公开 (低敏感外部信号)
]

# 蓝图 § 四机制一: 来源置信度先验
CONFIDENCE_PRIOR_BY_SOURCE_TYPE: dict[str, float] = {
    "workbench_file": 0.90,       # 客户官方文件(细分按 role 调)
    "task_review": 0.85,
    "user_correction": 0.95,      # 用户纠错最高
    "user_verification": 1.00,    # 用户裁决权威
    "internet_crawl": 0.60,       # 中等(细分按 role L1/L2/L3 调)
    "oral_claim": 0.70,
    "ai_extracted": 0.50,         # 派生需要原 source 支撑
    "ai_inference": 0.40,         # 研判更需要佐证
    "system_log": 0.95,           # 技术真,业务弱
    "external_intel": 0.55,
    "method_card": 0.85,          # 高但限域
    "plan_item": 0.85,
    "feishu_sync": 0.80,
}

CONFIDENCE_PRIOR_BY_SOURCE_ROLE: dict[str, float] = {
    "client_official": 0.95,
    "client_internal": 0.80,
    "partner_submission": 0.75,
    "yiyu_advisory": 0.70,
    "external_reference": 0.55,
    "policy_industry": 0.90,
    "media_observation": 0.60,    # L2
    "ugc_signal": 0.30,           # L3
    "user_oral": 0.70,
    "ai_derived": 0.50,
    "system_internal": 0.95,
    "unknown": 0.50,
}


# ─── DB Protocol ───────────────────────────────────────


class _DbLike(Protocol):
    def execute(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchone(self, sql: str, params: tuple = ...) -> Any: ...
    def fetchall(self, sql: str, params: tuple = ...) -> Any: ...


# ─── Schema ──────────────────────────────────────────


def ensure_schema(db: _DbLike) -> None:
    """创建 source_registry 表 (idempotent)."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS source_registry (
            -- 主键
            source_id TEXT PRIMARY KEY,

            -- 谁说的(蓝图 § 一 核心问题 2)
            source_type TEXT NOT NULL,
            source_channel TEXT NOT NULL,
            source_owner TEXT,

            -- 属于谁(4 必填, IngestPipeline 强校验)
            client_id TEXT,
            project_id TEXT,
            user_id TEXT,
            org_id TEXT,

            -- 时间
            source_time TEXT,           -- 事件发生时间
            capture_time TEXT NOT NULL, -- 系统捕获时间

            -- 权限 + 追溯
            visibility_scope TEXT NOT NULL DEFAULT 'org',
            content_hash TEXT NOT NULL,  -- 去重 key
            version_id TEXT,             -- 版本号 (e.g. 'v1')
            prev_version_id TEXT,        -- 上一版 source_id (版本链)

            -- 角色 + 置信度
            source_role TEXT,
            initial_confidence REAL,

            -- 原文引用
            raw_reference TEXT,          -- file_path / chunk_id / msg_id / url 等

            -- 系统
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # 关键索引
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_source_registry_client ON source_registry (client_id)",
        "CREATE INDEX IF NOT EXISTS idx_source_registry_project ON source_registry (project_id)",
        "CREATE INDEX IF NOT EXISTS idx_source_registry_type ON source_registry (source_type)",
        "CREATE INDEX IF NOT EXISTS idx_source_registry_channel ON source_registry (source_channel)",
        "CREATE INDEX IF NOT EXISTS idx_source_registry_hash ON source_registry (content_hash)",
        "CREATE INDEX IF NOT EXISTS idx_source_registry_capture_time ON source_registry (capture_time DESC)",
        "CREATE INDEX IF NOT EXISTS idx_source_registry_prev ON source_registry (prev_version_id)",
    ]:
        db.execute(sql)


# ─── Utility ────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_content_hash(content: str) -> str:
    """SHA-256 前 16 字符作 content_hash (去重 key)."""
    if not content:
        content = ""
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:16]


def initial_confidence_for(source_type: str, source_role: str | None) -> float:
    """蓝图 § 四 机制一: 按 source_type + source_role 算初始置信度."""
    type_prior = CONFIDENCE_PRIOR_BY_SOURCE_TYPE.get(source_type, 0.50)
    if source_role:
        role_prior = CONFIDENCE_PRIOR_BY_SOURCE_ROLE.get(source_role, 0.50)
        # 加权平均 (role 影响 60%)
        return round(0.4 * type_prior + 0.6 * role_prior, 2)
    return type_prior


# ─── Main API ────────────────────────────────────────


def register_source(
    db: _DbLike,
    *,
    source_type: str,
    source_channel: str,
    source_owner: str | None = None,
    client_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    org_id: str | None = None,
    source_time: str | None = None,
    visibility_scope: str = "org",
    content: str = "",
    source_role: str | None = None,
    raw_reference: str | None = None,
    prev_version_id: str | None = None,
    version_id: str = "v1",
    # 4 必填强校验 (V2.3 阶段 1 P2)
    strict_4_required: bool = True,
) -> str:
    """登记一条 source 到 source_registry. 返回 source_id.

    蓝图 § 八 步骤 1: 进入前先分型.

    Args:
        source_type: 蓝图 4 大主路径 + 子源 (SourceType enum)
        source_channel: 具体来源通道 (SourceChannel enum)
        source_owner: actor_id (谁产生, 可空但建议有)
        client_id / project_id / user_id / org_id: 4 必填强校验 (V2.3)
        content: 用于 content_hash 计算 (去重)
        source_role: 蓝图 § 三 智能导入文件角色 (SourceRole enum)
        strict_4_required: True 时 client_id + project_id + user_id + org_id 至少 3 个非空,
                           不满足抛 ValueError

    Raises:
        ValueError: strict_4_required 且 4 必填全空时
    """
    # 4 必填强校验 (V2.3 P2)
    if strict_4_required:
        filled = [x for x in (client_id, project_id, user_id, org_id) if x]
        if not filled:
            raise ValueError(
                "V2.3 P2 强校验: client_id / project_id / user_id / org_id "
                "至少必须填一个 (建议 client_id 必填)"
            )

    now = _now_iso()
    content_hash = _compute_content_hash(content)
    initial_conf = initial_confidence_for(source_type, source_role)
    source_id = f"src_{uuid.uuid4().hex[:24]}"

    db.execute(
        """
        INSERT INTO source_registry (
            source_id, source_type, source_channel, source_owner,
            client_id, project_id, user_id, org_id,
            source_time, capture_time,
            visibility_scope, content_hash, version_id, prev_version_id,
            source_role, initial_confidence, raw_reference,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """,
        (
            source_id, source_type, source_channel, source_owner,
            client_id, project_id, user_id, org_id,
            source_time, now,
            visibility_scope, content_hash, version_id, prev_version_id,
            source_role, initial_conf, raw_reference,
            now, now,
        ),
    )

    # ★ V2.3 PUSH 自动化 · register_source 末尾自动入队 team_sync_state
    # 让 ingest 完成的新文档/事实立即进入推送队列, 后台 team-sync-worker daemon 自动消化.
    # 不阻塞主流程: try/except + INSERT OR IGNORE 兜底.
    # 隔离: visibility_scope=private/personal/self 不推 (个人独享不入云)
    if org_id and visibility_scope not in {"private", "personal", "self"}:
        try:
            db.execute(
                """
                INSERT OR IGNORE INTO team_sync_state(
                    source_id, client_id, organization_id, content_hash,
                    status, attempts, last_error, created_at, updated_at
                ) VALUES(?, ?, ?, ?, 'pending', 0, '', ?, ?)
                """,
                (source_id, client_id or "", org_id, content_hash, now, now),
            )
        except Exception:
            # team_sync_state 表可能还没建 (旧版本 db) — 静默, 不阻塞 register_source 主流程
            # 表建好后 (启动 ensure_team_sync_schema 会建), 下次注册自然进队
            pass

    return source_id


def find_by_content_hash(
    db: _DbLike, content_hash: str, client_id: str | None = None
) -> dict[str, Any] | None:
    """查重 — 同 content_hash 已存在 source 返回 row, 否则 None.

    用于 IngestPipeline 写入前去重判断.
    """
    if client_id:
        row = db.fetchone(
            "SELECT * FROM source_registry WHERE content_hash = ? AND client_id = ? "
            "AND status = 'active' LIMIT 1",
            (content_hash, client_id),
        )
    else:
        row = db.fetchone(
            "SELECT * FROM source_registry WHERE content_hash = ? AND status = 'active' LIMIT 1",
            (content_hash,),
        )
    if not row:
        return None
    return dict(row) if hasattr(row, "keys") else dict(zip([d[0] for d in row.description], row))


def list_sources_for_client(
    db: _DbLike, client_id: str, source_type: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """拉某客户的 source 列表 (用于排查 / 故事网构建)."""
    if source_type:
        rows = db.fetchall(
            """SELECT * FROM source_registry
               WHERE client_id = ? AND source_type = ? AND status = 'active'
               ORDER BY capture_time DESC LIMIT ?""",
            (client_id, source_type, limit),
        )
    else:
        rows = db.fetchall(
            """SELECT * FROM source_registry
               WHERE client_id = ? AND status = 'active'
               ORDER BY capture_time DESC LIMIT ?""",
            (client_id, limit),
        )
    return [dict(r) for r in rows]


def supersede_version(db: _DbLike, source_id: str, new_source_id: str) -> None:
    """版本链: 把旧 source 标 superseded, 新 source 的 prev_version_id 指向旧."""
    now = _now_iso()
    db.execute(
        """UPDATE source_registry SET status = 'superseded', updated_at = ?
           WHERE source_id = ?""",
        (now, source_id),
    )
    db.execute(
        """UPDATE source_registry SET prev_version_id = ?, updated_at = ?
           WHERE source_id = ?""",
        (source_id, now, new_source_id),
    )


def get_source(db: _DbLike, source_id: str) -> dict[str, Any] | None:
    row = db.fetchone(
        "SELECT * FROM source_registry WHERE source_id = ?",
        (source_id,),
    )
    if not row:
        return None
    return dict(row) if hasattr(row, "keys") else None
