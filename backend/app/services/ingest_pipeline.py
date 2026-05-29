"""v2.2 Phase 2 F2.4 · IngestPipeline · 4 主路径统一入口

服务: V2.2_NORTH_STAR.md
- N2 (数据中心理解信息源): 4 路径走同一通道, 每路径填对应默认 5 维元数据
- N3 (3.0 接入预留): 写入时顺手往 ai_episode_log + event_log 写一条 (统一事件总线)

4 主路径 (见 V2.2_INFORMATION_SOURCE_METADATA.md §3):
1. 工作台进入的文件 (file / smart_file_import / docx / pdf 等)
2. 任务/计划/复盘/协作信息
3. 互联网爬虫补全
4. 手机 AI 聊天澄清

每个路径有专属 normalizer 决定默认 source_type / content_role 等元数据,
但写入出口统一走 IngestPipeline.ingest(), 不再各路径自己 INSERT INTO atomic_facts。
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)


# ─── 类型 ─────────────────────────────────────────────────────────


IngestPath = Literal[
    "workbench_file",       # 路径 1: 工作台文件
    "task_review",          # 路径 2: 任务/复盘/协作
    "internet_crawler",     # 路径 3: 爬虫
    "mobile_ai_chat",       # 路径 4: 手机 AI 聊天澄清
]

# 用户甲 5/22 洞察 — 渠道驱动判断 content_role
# 优先用 source_type 兜底, LLM 语义判断作为二次精化
SourceType = Literal[
    # 客户自报
    "client_official_doc",      # 已签合同 / 章程 / 官网公告 → fact 高
    "client_internal_doc",      # 会议纪要 / 内部邮件 → decision/fact 高
    "client_verbal_meeting",    # 跟客户当面记录 → fact/decision 中高
    # 协作记录
    "collaboration_task",       # tasks 表 → plan
    "collaboration_review",     # weekly_review / 复盘 → lesson/observation
    # 用户
    "user_observation",         # 用户主观判断 → observation
    "user_verbal_fact",         # 用户口述客户的事实 → fact (待确认)
    # 互联网
    "internet_official",        # 政府公示 / 客户官网 → fact 高
    "internet_media",           # 主流媒体 → observation
    "internet_ugc",             # 公众号/微博 → speculation
    "internet_ai_inferred",     # AI 分析稿 → speculation (极低)
    # 系统
    "llm_extracted",            # ExtractionRunner 抽出 → 待 verify
    "system_derived",           # join 推断 → fact 中
    "ai_agent_authored",        # 3.0 AI agent 自写 → 待 verify
]

ContentRole = Literal[
    "fact",
    "decision",
    "risk",
    "progress",
    "plan",
    "lesson",
    "observation",
    "speculation",
    "quote",
    "commitment",
]

ActorType = Literal["human", "ai_agent", "system"]


# ─── DB 协议 ─────────────────────────────────────────────────────


class _DbLike(Protocol):
    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]: ...
    def execute(self, query: str, params: tuple = ()) -> None: ...


# ─── 渠道驱动 content_role 判断 (用户甲 5/22 规则) ─────────────


# 默认 content_role 映射 (基于 source_type 兜底)
# LLM extractor 可以基于段落语义 override, 但必有兜底
SOURCE_TYPE_TO_DEFAULT_ROLE: dict[str, str] = {
    # 已签合同 / 章程 → fact (用户甲原话: "已经签署的文件合同, 它就是事实")
    "client_official_doc": "fact",
    # 会议纪要 → decision (用户甲原话: "会议纪要确定的事情, 他可能就是决策")
    "client_internal_doc": "decision",
    # 当面记录 → fact (中高置信度)
    "client_verbal_meeting": "fact",
    # 协作 task → plan
    "collaboration_task": "plan",
    # 复盘 → lesson (用户甲原话: "主观的人的复盘 ... 即便是人类社会也需要丰富经验区分")
    "collaboration_review": "lesson",
    # 用户主观 → observation
    "user_observation": "observation",
    "user_verbal_fact": "fact",
    # 互联网
    "internet_official": "fact",
    "internet_media": "observation",
    "internet_ugc": "speculation",
    "internet_ai_inferred": "speculation",
    # 系统
    "llm_extracted": "fact",
    "system_derived": "fact",
    "ai_agent_authored": "speculation",
}

# 基础置信度映射 (跟 SOURCE_TYPE 一一对应, 用户校正后会动态更新)
SOURCE_TYPE_BASE_CONFIDENCE: dict[str, float] = {
    "client_official_doc": 0.95,
    "client_internal_doc": 0.90,
    "client_verbal_meeting": 0.85,
    "collaboration_task": 0.90,
    "collaboration_review": 0.85,
    "user_observation": 0.65,
    "user_verbal_fact": 0.75,
    "internet_official": 0.85,
    "internet_media": 0.60,
    "internet_ugc": 0.30,
    "internet_ai_inferred": 0.20,
    "llm_extracted": 0.50,
    "system_derived": 0.70,
    "ai_agent_authored": 0.40,
}


def default_role_for_source(source_type: str) -> str:
    """渠道驱动判断 — 如果 LLM 没明确判断 content_role, 用 source_type 兜底"""
    return SOURCE_TYPE_TO_DEFAULT_ROLE.get(source_type, "fact")


def base_confidence_for_source(source_type: str) -> float:
    """渠道驱动判断 — 基础置信度 (user_confirmed 后会跳到 1.0)"""
    return SOURCE_TYPE_BASE_CONFIDENCE.get(source_type, 0.50)


# ─── 4 路径默认元数据生成器 (路径 normalizer 的核心) ──────────


@dataclass(frozen=True)
class IngestMetadata:
    """每条事实写入数据中心时的完整元数据 (5 维)"""
    source_type: str
    content_role: str
    actor_type: str = "human"
    actor_id: str = ""
    speaker_person_id: str | None = None
    time_anchor: str | None = None
    verification_status: str = "unverified"
    confidence_source: str = "rule"
    confidence_score: float = 0.5
    validity_status: str = "current"
    update_relation: str = "none"  # v2.2 Phase 2 起步: 信息商
    reasoning_trace_id: str | None = None
    derived_from_ids: list[str] = field(default_factory=list)


def metadata_for_workbench_file(
    *,
    file_doc_type: Literal["contract", "meeting_minute", "article", "proposal", "other"],
    actor_id: str,
    time_anchor: str | None = None,
) -> IngestMetadata:
    """路径 1: 工作台文件 — 按 doc_type 分细 source_type

    用户甲 5/22 原话:
    - 合同类: '决策方/分工/时间/干什么/交付内容写得很清楚' → fact 高
    - 文章/方案: '背景什么很难分得清楚' → observation, 待 verify
    """
    if file_doc_type == "contract":
        source_type = "client_official_doc"
    elif file_doc_type == "meeting_minute":
        source_type = "client_internal_doc"
    elif file_doc_type in ("article", "proposal"):
        source_type = "client_internal_doc"
    else:
        source_type = "client_internal_doc"
    return IngestMetadata(
        source_type=source_type,
        content_role=default_role_for_source(source_type),
        actor_type="human",
        actor_id=actor_id,
        time_anchor=time_anchor,
        verification_status="unverified",
        confidence_source="rule",
        confidence_score=base_confidence_for_source(source_type),
    )


def metadata_for_task_review(
    *,
    sub_kind: Literal["task", "weekly_review", "collaboration_msg"],
    actor_id: str,
    time_anchor: str | None = None,
) -> IngestMetadata:
    """路径 2: 任务/复盘/协作

    用户甲 5/22 原话:
    - 日程的说明/总结/复盘 → 经验性
    - 组织任务的执行度更高 → 置信度更高
    """
    if sub_kind == "task":
        source_type = "collaboration_task"
        verification = "user_confirmed"  # 用户主动写的 task, 直接信
        score = 0.90
    elif sub_kind == "weekly_review":
        source_type = "collaboration_review"
        verification = "user_confirmed"
        score = 0.85
    else:  # collaboration_msg
        source_type = "collaboration_task"
        verification = "user_confirmed"
        score = 0.85
    return IngestMetadata(
        source_type=source_type,
        content_role=default_role_for_source(source_type),
        actor_type="human",
        actor_id=actor_id,
        time_anchor=time_anchor,
        verification_status=verification,
        confidence_source="user",
        confidence_score=score,
    )


def metadata_for_internet_crawler(
    *,
    crawler_kind: Literal["official", "media", "ugc", "ai_inferred"],
    crawler_run_id: str,
    time_anchor: str | None = None,
) -> IngestMetadata:
    """路径 3: 互联网爬虫 — 按来源域名/类型分细 source_type"""
    source_type_map = {
        "official": "internet_official",
        "media": "internet_media",
        "ugc": "internet_ugc",
        "ai_inferred": "internet_ai_inferred",
    }
    source_type = source_type_map[crawler_kind]
    return IngestMetadata(
        source_type=source_type,
        content_role=default_role_for_source(source_type),
        actor_type="system",
        actor_id=crawler_run_id,
        time_anchor=time_anchor,
        verification_status="unverified",
        confidence_source="rule",
        confidence_score=base_confidence_for_source(source_type),
    )


def metadata_for_mobile_ai_chat(
    *,
    user_id: str,
    speaker_person_id: str | None = None,
    is_user_subjective: bool = False,
    time_anchor: str | None = None,
) -> IngestMetadata:
    """路径 4: 手机 AI 朋友式聊天澄清

    用户甲 5/22 场景:
    - 早晨通勤路上跟 AI 聊, 既排解情绪 + 梳理思路 + 让 AI 理解
    - 用户口述事实 (转述客户) → user_verbal_fact
    - 用户主观判断 → user_observation
    """
    source_type = "user_observation" if is_user_subjective else "user_verbal_fact"
    return IngestMetadata(
        source_type=source_type,
        content_role=default_role_for_source(source_type),
        actor_type="human",
        actor_id=user_id,
        speaker_person_id=speaker_person_id,
        time_anchor=time_anchor,
        verification_status="user_confirmed" if not is_user_subjective else "unverified",
        confidence_source="user",
        confidence_score=base_confidence_for_source(source_type),
    )


# ─── ai_episode_log 写入封装 (用户甲 5/22 决策: v2.2 阶段就开始写) ──


def log_ai_episode(
    db: _DbLike,
    *,
    ai_session_id: str,
    action_type: str,
    action_summary: str,
    user_id: str | None = None,
    client_id: str | None = None,
    referenced_fact_ids: list[str] | None = None,
    referenced_doc_ids: list[str] | None = None,
    outcome: Literal["pending", "accepted", "rejected", "reverted"] = "pending",
    completed_at: str | None = None,
) -> None:
    """每次 LLM 调用顺手往 ai_episode_log 写一条。

    Anthropic dogfood 哲学: 从今天起积累, 3.0 启动有 N 个月样本可看。

    action_type 标准值 (建议):
    - 'extracted_fact'         — F2.1 LLM extractor 抽出一条 fact
    - 'requested_clarification' — F2.5 触发主动澄清
    - 'requested_human_help'   — 用户甲 5/22 洞察: AI 反向给人类提请求
    - 'suggested_improvement'  — AI 提流程改进建议 (写 ai_improvement_suggestions)
    - 'generated_narrative'    — F3.1 NarrativeKernel 生成叙事
    - 'created_task'           — 3.0 AI 主动建任务
    """
    db.execute(
        """
        INSERT INTO ai_episode_log (
            ai_session_id, user_id, client_id,
            action_type, action_summary,
            referenced_fact_ids_json, referenced_doc_ids_json,
            outcome, occurred_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ai_session_id,
            user_id,
            client_id,
            action_type,
            action_summary,
            json.dumps(referenced_fact_ids or [], ensure_ascii=False),
            json.dumps(referenced_doc_ids or [], ensure_ascii=False),
            outcome,
            _now_iso(),
            completed_at,
        ),
    )


# ─── event_log 写入封装 (用户甲 5/22 没明确说 v2.2 写不写, 但跟 ai_episode_log 一样属于"事件流") ──


def log_event(
    db: _DbLike,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor_type: ActorType = "human",
    actor_id: str = "",
    client_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """事件总线写一行。所有数据中心写入操作都该顺手调它。

    event_type 命名规范 (参考 segment.io):
    - 'client.fact_created' / 'client.fact_corrected' / 'client.fact_superseded'
    - 'task.created_by_ai' / 'task.completed' / 'task.reverted'
    - 'clarification.asked' / 'clarification.resolved'
    - 'ai.action_taken' / 'ai.action_reverted'
    """
    db.execute(
        """
        INSERT INTO event_log (
            event_type, actor_type, actor_id,
            entity_type, entity_id, client_id,
            payload_json, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            actor_type,
            actor_id,
            entity_type,
            entity_id,
            client_id,
            json.dumps(payload or {}, ensure_ascii=False),
            _now_iso(),
        ),
    )


# ─── R2 重设计: 冲突 vs 更新 vs 互补 判断 (用户甲"信息商" 洞察) ──


@dataclass(frozen=True)
class UpdateRelationVerdict:
    relation: Literal["none", "conflict", "supersedes", "complement"]
    target_fact_id: str | None    # supersedes 时指向被推翻的事实
    reasoning: str                # AI 给出的判断理由 (写到 reasoning_trace_id)


# 关键词触发"信息更新"识别 (用户甲原话: "用户说要重签/要改/不对了" 类语义)
_SUPERSEDE_KEYWORDS = [
    "重签", "改成", "改为", "不对", "不是", "弄错", "搞错", "更新", "应该是",
    "其实是", "实际上", "纠正", "修正", "替换", "失效", "作废",
]


def detect_update_relation(
    *,
    new_value: str,
    existing_facts: list[dict[str, Any]],  # 已有的同 subject+attribute 事实
    new_source_type: str,
) -> UpdateRelationVerdict:
    """信息商: 判断新事实跟已有事实的关系。

    用户甲 5/22 原话:
    - "合同金额 800 万但合同写错成 300 万要重签" — 这不是冲突, 是信息更新
    - "AI 要对接收的信息有分辨能力"

    判断逻辑 (规则版, v2.2 阶段; F2.1 LLM extractor 可以扩展):
    1. 没有同 subject+attribute 已有事实 → none
    2. 新事实值跟已有事实一致 → none (重复信息, 不写)
    3. 新事实文本含"重签/改成/不对" 等更新语义关键词 → supersedes
       + 找最新的同主题事实做 target
    4. 新事实来自 user_verbal_fact 且现有事实来自 client_official_doc → conflict
       (除非有更新语义)
    5. 时间锚不同 → complement (不同时间切面, 都保留)
    6. 否则 → conflict
    """
    if not existing_facts:
        return UpdateRelationVerdict(relation="none", target_fact_id=None,
                                      reasoning="no prior fact")

    # 检查是否有完全相同 value (重复信息)
    same_value = [f for f in existing_facts if str(f.get("value_text", "")).strip() == new_value.strip()]
    if same_value:
        return UpdateRelationVerdict(relation="none", target_fact_id=None,
                                      reasoning="duplicate value, no write needed")

    # 检查"信息更新" 语义关键词
    has_update_keyword = any(kw in new_value for kw in _SUPERSEDE_KEYWORDS)
    if has_update_keyword:
        # 找最新的活跃事实做 target
        active = [f for f in existing_facts if f.get("validity_status") == "current"]
        target = active[0] if active else existing_facts[0]
        return UpdateRelationVerdict(
            relation="supersedes",
            target_fact_id=str(target.get("id")),
            reasoning=f"new value contains update keyword (e.g. '重签'/'改为')",
        )

    # 检查时间锚 — 不同时间锚算 complement
    new_time = ""  # 调用方应该传入新事实的 time_anchor, 这里简化
    diff_time = any(
        f.get("time_anchor") and f.get("time_anchor") != new_time
        for f in existing_facts
    )
    if diff_time:
        return UpdateRelationVerdict(relation="complement", target_fact_id=None,
                                      reasoning="different time anchors, complementary facts")

    # 默认: conflict
    target = existing_facts[0]
    return UpdateRelationVerdict(
        relation="conflict",
        target_fact_id=str(target.get("id")),
        reasoning=f"value mismatch with no update semantic, source_type={new_source_type}",
    )


# ─── IngestPipeline 主入口 ──────────────────────────────────────


@dataclass(frozen=True)
class IngestRequest:
    """4 路径都用这个 shape 喂给 IngestPipeline"""
    path: IngestPath
    client_id: str
    subject_text: str
    attribute: str
    value_text: str
    metadata: IngestMetadata
    source_v2_chunk_id: str | None = None
    source_v2_document_id: str | None = None
    evidence_text: str | None = None
    ai_session_id: str | None = None  # 如果是 AI 抽的, 关联 ai_episode_log


@dataclass(frozen=True)
class IngestResult:
    fact_id: str
    update_relation: str
    superseded_target_id: str | None
    confidence_score: float
    written: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _value_normalize(text: str) -> str:
    return text.strip().lower()


# ─── V2.3 阶段 1 P2 · source_registry 映射辅助 ──────────


_PATH_TO_CHANNEL: dict[str, dict[str, str]] = {
    "workbench_file": {
        "client_internal_doc": "smart_file_import",
        "client_official_doc": "workbench_upload",
        "default": "workbench_upload",
    },
    "task_review": {
        "collaboration_task": "task_create",
        "collaboration_review": "weekly_review",
        "default": "task_create",
    },
    "internet_crawler": {
        "internet_official": "intelligence_radar",
        "internet_media": "intelligence_radar",
        "internet_ugc": "intelligence_radar",
        "default": "intelligence_radar",
    },
    "mobile_ai_chat": {
        "user_verbal_fact": "workspace_chat",
        "user_observation": "workspace_chat",
        "default": "workspace_chat",
    },
}


_SOURCE_TYPE_TO_ROLE: dict[str, str] = {
    # 蓝图 § 四 机制一: source_type → 默认 source_role
    "client_official_doc": "client_official",
    "client_internal_doc": "client_internal",
    "collaboration_task": "yiyu_advisory",
    "collaboration_review": "yiyu_advisory",
    "user_verbal_fact": "user_oral",
    "user_observation": "user_oral",
    "internet_official": "client_official",
    "internet_media": "media_observation",
    "internet_ugc": "ugc_signal",
    "internet_ai_inferred": "ai_derived",
    "llm_extracted": "ai_derived",
    "system_derived": "system_internal",
    "ai_agent_authored": "ai_derived",
}


def _infer_channel(path: str, source_type: str) -> str:
    """根据 IngestPath + source_type 推 source_channel (V2.3 阶段 1 P2)."""
    mapping = _PATH_TO_CHANNEL.get(path, {})
    return mapping.get(source_type, mapping.get("default", "unknown"))


def _infer_role_from_source_type(source_type: str) -> str:
    """根据 source_type 推默认 source_role (V2.3 阶段 1 P2)."""
    return _SOURCE_TYPE_TO_ROLE.get(source_type, "unknown")


class IngestPipeline:
    """4 主路径统一入口 — N2 核心。

    职责:
    1. 接受任意路径的 IngestRequest
    2. 用 IngestMetadata 填默认 5 维元数据 (本类不改 metadata, 由 normalizer 决定)
    3. 跑 detect_update_relation 判断 conflict/supersedes/complement
    4. 写 atomic_facts (或不写, 如果 update_relation='none' 且 value 重复)
    5. 顺手写 event_log (3.0 看历史用)
    6. 如果 ai_session_id 给了, 顺手写 ai_episode_log
    7. ★ M-A · 写后调 broadcast_data_changed 触发 L1+L2 扩散 (用户甲 5/22 钦定)
       Karpathy §2 LLM as OS · 一处写全局刷, 不让 IngestPipeline 成为孤立写入点
    """

    def __init__(self, db: _DbLike, ai: Any | None = None,
                 *, ensure_v23_schema: bool = True,
                 v25_auto_derive: bool = True,
                 v25_auto_conflict: bool = True):
        """初始化.

        Args:
            db: sqlite Database wrapper.
            ai: AI service (可选). 传了之后写完 atomic_facts 自动调 broadcast_data_changed.
                不传 (None) 时跳过 broadcast (向后兼容旧调用方).
            ensure_v23_schema: 默认 True, 启动时确保 V2.3 阶段 1 新表已建
            v25_auto_derive: V2.5 P0-1 — 写完 atomic_facts 自动派生到 4 张语义表
                · event_line_activities / risk_signals / commitments / strategic_thought_insights
                · 解决 B 报告 38 分 §六 修复项 1 (语义表 7 张 0 流量)
            v25_auto_conflict: V2.5 P0-2 — 写完 atomic_facts 自动跑冲突检测 + 写 clarifications
                · 解决 B 报告 §六 修复项 2 (clarification_records 0 行)
                · 限流: 每个 client_id 60s 内只跑一次 (避免热写入路径慢)
        """
        self._db = db
        self._ai = ai
        self._v25_auto_derive = v25_auto_derive
        self._v25_auto_conflict = v25_auto_conflict
        self._v25_last_derive_at: dict[str, float] = {}  # client_id → last unix ts
        self._v25_throttle_seconds = 30
        if ensure_v23_schema:
            self._ensure_v23_schema()

    def _v25_maybe_derive(self, client_id: str) -> None:
        """V2.5 P0-1 + P0-2: 写完 atomic_facts 后实时派生 + 冲突检测.

        限流: 同 client 30s 内只跑一次 (避免热写入路径每条 fact 都全扫).
        失败不阻塞主流程 (写 atomic_facts 已经成功).
        """
        import time
        if not client_id:
            return
        now_ts = time.time()
        last = self._v25_last_derive_at.get(client_id, 0)
        if now_ts - last < self._v25_throttle_seconds:
            return
        self._v25_last_derive_at[client_id] = now_ts

        if self._v25_auto_derive:
            try:
                from app.services.atomic_fact_semantic_deriver import derive_all
                d = derive_all(self._db, client_id)
                logger.info(
                    "V2.5 auto-derive client=%s: ela+%d risk+%d com+%d insight+%d",
                    client_id, d.event_line_activities_new,
                    d.risk_signals_new, d.commitments_new, d.strategic_insights_new,
                )
            except Exception as exc:
                logger.warning("V2.5 auto-derive 失败 client=%s: %s", client_id, exc)
        if self._v25_auto_conflict:
            try:
                from app.services.formal_conflict_detector import detect_all
                c = detect_all(self._db, client_id)
                logger.info(
                    "V2.5 auto-conflict client=%s: contradictions+%d clarifications+%d",
                    client_id, c.fact_contradictions_written, c.clarifications_written,
                )
            except Exception as exc:
                logger.warning("V2.5 auto-conflict 失败 client=%s: %s", client_id, exc)

    def _ensure_v23_schema(self) -> None:
        """V2.3 阶段 1 P2: 确保 source_registry / confidence_history 表 + atomic_facts 新列."""
        try:
            from app.services.source_registry_store import ensure_schema as ensure_sr
            from app.services.atomic_fact_confidence_history import ensure_schema as ensure_ch
            ensure_sr(self._db)
            ensure_ch(self._db)
            # atomic_facts 加 source_registry_id 列 (向后兼容, 旧数据 NULL)
            try:
                self._db.execute(
                    "ALTER TABLE atomic_facts ADD COLUMN source_registry_id TEXT"
                )
            except Exception:
                pass  # 列已存在 (SQLite idempotent 友好)
            try:
                self._db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_atomic_facts_source_registry "
                    "ON atomic_facts (source_registry_id)"
                )
            except Exception:
                pass
        except Exception as exc:
            logger.warning("V2.3 schema 启动失败 (跳过, 旧路径仍可用): %s", exc)

    def ingest(self, req: IngestRequest) -> IngestResult:
        # ★ V2.3 阶段 1 P2 · 4 必填强校验 (蓝图 § 一 核心问题 2 "属于谁")
        # client_id 必填 (其他 3 个 project_id/user_id/org_id 至少 IngestRequest 携带 metadata.actor_id)
        if not req.client_id:
            raise ValueError(
                "V2.3 P2 强校验: IngestRequest.client_id 必填 "
                f"(path={req.path}, subject={req.subject_text[:30]})"
            )

        # ★ V2.3 阶段 1 P2 · 先 register_source (蓝图 § 八 步骤 1 进入前先分型)
        source_registry_id: str | None = None
        try:
            from app.services.source_registry_store import register_source
            source_registry_id = register_source(
                self._db,
                source_type=req.metadata.source_type,
                source_channel=_infer_channel(req.path, req.metadata.source_type),
                source_owner=req.metadata.actor_id or None,
                client_id=req.client_id,
                user_id=req.metadata.actor_id if req.metadata.actor_type == "human" else None,
                source_time=req.metadata.time_anchor,
                content=f"{req.subject_text}|{req.attribute}|{req.value_text}",
                source_role=_infer_role_from_source_type(req.metadata.source_type),
                raw_reference=req.source_v2_document_id or req.source_v2_chunk_id,
                strict_4_required=False,  # 暂宽松 (向后兼容 backfill); client_id 已强校验
            )
        except Exception as exc:
            logger.warning(
                "V2.3 register_source 失败 (继续写 atomic_facts, source_id 为 None): %s", exc
            )

        # 1. 查同 subject+attribute 的已有事实
        existing_rows = self._db.fetchall(
            """
            SELECT id, value_text, value_normalized, time_anchor,
                   validity_status, source_type, confidence
            FROM atomic_facts
            WHERE client_id = ? AND subject_text = ? AND attribute = ?
              AND status = 'active'
            ORDER BY created_at DESC
            """,
            (req.client_id, req.subject_text, req.attribute),
        )
        existing = [
            {
                "id": r["id"], "value_text": r["value_text"],
                "time_anchor": r["time_anchor"] if "time_anchor" in r.keys() else None,
                "validity_status": r["validity_status"] if "validity_status" in r.keys() else "current",
                "source_type": r["source_type"] if "source_type" in r.keys() else "llm_extracted",
            }
            for r in existing_rows
        ]

        # 2. 跑信息商 判断
        verdict = detect_update_relation(
            new_value=req.value_text,
            existing_facts=existing,
            new_source_type=req.metadata.source_type,
        )

        # 3. 'none' 且重复 → 不写
        if verdict.relation == "none" and any(
            _value_normalize(str(e.get("value_text"))) == _value_normalize(req.value_text)
            for e in existing
        ):
            return IngestResult(
                fact_id="", update_relation="none",
                superseded_target_id=None,
                confidence_score=req.metadata.confidence_score,
                written=False,
            )

        # 4. 如果是 supersedes, 把旧事实标 superseded
        if verdict.relation == "supersedes" and verdict.target_fact_id:
            self._db.execute(
                """
                UPDATE atomic_facts
                SET validity_status = 'superseded',
                    superseded_by_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (None, _now_iso(), verdict.target_fact_id),  # superseded_by_id 后面 set
            )

        # 5. 写新事实
        fact_id = f"af_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        self._db.execute(
            """
            INSERT INTO atomic_facts (
                id, client_id, subject_text, attribute,
                value_text, value_normalized,
                confidence, source_v2_chunk_id, source_v2_document_id,
                evidence_text, status, created_at, updated_at,
                source_type, content_role, actor_type, actor_id,
                speaker_person_id, time_anchor,
                verification_status, confidence_source, validity_status,
                update_relation, reasoning_trace_id, derived_from_ids_json,
                source_registry_id
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, 'active', ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, 'current',
                ?, ?, ?,
                ?
            )
            """,
            (
                fact_id, req.client_id, req.subject_text, req.attribute,
                req.value_text, _value_normalize(req.value_text),
                req.metadata.confidence_score,
                req.source_v2_chunk_id, req.source_v2_document_id,
                req.evidence_text, now, now,
                req.metadata.source_type, req.metadata.content_role,
                req.metadata.actor_type, req.metadata.actor_id,
                req.metadata.speaker_person_id, req.metadata.time_anchor,
                req.metadata.verification_status, req.metadata.confidence_source,
                verdict.relation,
                req.metadata.reasoning_trace_id,
                json.dumps(req.metadata.derived_from_ids, ensure_ascii=False),
                source_registry_id,  # V2.3 阶段 1 P2 · 关联 source_registry
            ),
        )

        # ★ V2.3 阶段 1 P2 · 写 atomic_fact_confidence_history (initial_extract)
        # 蓝图 § 四 机制一 "置信度不是固定数字, 而是不断变化的状态"
        try:
            from app.services.atomic_fact_confidence_history import record_confidence_change
            record_confidence_change(
                self._db,
                fact_id=fact_id,
                new_confidence=req.metadata.confidence_score,
                trigger_event="initial_extract",
                evidence_link=source_registry_id,
                actor_id=req.metadata.actor_id or "ingest_pipeline",
                reasoning_note=f"ingest({req.path}) initial_confidence",
            )
        except Exception as exc:
            logger.warning(
                "V2.3 confidence_history 写入失败 (跳过, atomic_facts 主写入已成功): %s", exc
            )

        # 6. 如果是 supersedes, 回填新事实 id 到旧事实的 superseded_by_id
        if verdict.relation == "supersedes" and verdict.target_fact_id:
            self._db.execute(
                "UPDATE atomic_facts SET superseded_by_id = ? WHERE id = ?",
                (fact_id, verdict.target_fact_id),
            )

        # 7. 写 event_log
        event_type = {
            "none": "client.fact_created",
            "conflict": "client.fact_conflict_detected",
            "supersedes": "client.fact_superseded",
            "complement": "client.fact_complement_added",
        }[verdict.relation]
        log_event(
            self._db,
            event_type=event_type,
            entity_type="atomic_fact",
            entity_id=fact_id,
            actor_type=req.metadata.actor_type,
            actor_id=req.metadata.actor_id,
            client_id=req.client_id,
            payload={
                "path": req.path,
                "subject": req.subject_text,
                "attribute": req.attribute,
                "update_relation": verdict.relation,
                "superseded_target": verdict.target_fact_id,
                "reasoning": verdict.reasoning,
            },
        )

        # 8. 如果是 AI 抽的, 顺手写 ai_episode_log
        if req.ai_session_id:
            log_ai_episode(
                self._db,
                ai_session_id=req.ai_session_id,
                action_type="extracted_fact",
                action_summary=f"{req.subject_text}.{req.attribute} = {req.value_text[:50]}",
                user_id=req.metadata.actor_id if req.metadata.actor_type == "human" else None,
                client_id=req.client_id,
                referenced_fact_ids=[fact_id],
                referenced_doc_ids=[req.source_v2_document_id] if req.source_v2_document_id else [],
                outcome="pending",
            )

        # ★ V2.5 P0-1 + P0-2 · 实时派生 + 冲突检测 (用户甲 5/23 用户感知第 1 / 第 3 价值缺口)
        # 解决 B 报告 38 分: 语义表 7 张 0 流量 + clarification_records 0 行
        self._v25_maybe_derive(req.client_id)

        # ★ M-A · broadcast 接通 (用户甲 5/22 钦定 + Karpathy §2 LLM-as-OS syslog 启用)
        # 写完 atomic_facts + event_log + ai_episode_log 之后, 触发数据中心 L1+L2 扩散.
        # 让 4 主路径 (workbench_file / task_review / internet_crawler / mobile_ai_chat)
        # 任何一路写入都触发 narrative regenerate + portrait_build + L3 自校验.
        # 不传 ai 时跳过 (向后兼容). 失败不阻塞 ingest 主流程.
        if self._ai is not None:
            try:
                from app.services.data_center_broadcast import broadcast_data_changed
                broadcast_data_changed(
                    self._db, self._ai,
                    client_id=req.client_id,
                    scope=f"ingest_pipeline:{req.path}",
                )
            except Exception as exc:
                logger.warning(
                    "ingest_pipeline broadcast failed for client=%s fact=%s: %s",
                    req.client_id, fact_id, exc,
                )

        return IngestResult(
            fact_id=fact_id,
            update_relation=verdict.relation,
            superseded_target_id=verdict.target_fact_id,
            confidence_score=req.metadata.confidence_score,
            written=True,
        )


def get_ingest_pipeline(db: _DbLike, ai: Any | None = None) -> IngestPipeline:
    return IngestPipeline(db, ai)
