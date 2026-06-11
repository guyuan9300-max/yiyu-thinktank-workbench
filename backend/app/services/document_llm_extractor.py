"""v2.2 F2.1 · DocumentLLMExtractor — 从客户 docx 抽取 atomic_facts (5 维元数据)

服务: V2.2_NORTH_STAR.md
- N2 (核心): 让数据中心理解信息源, 4 主路径之一 (路径 1 工作台文件) 跑通
- N3: 走 IngestPipeline + 写 reasoning_traces + ai_episode_log

设计依据:
- docs/V2.2_F21_AI_INFORMATION_NEEDS.md (9 个场景倒推出的 9 层抽取范围)
- docs/V2.2_INFORMATION_SOURCE_METADATA.md (14 类 source_type + 10 类 content_role)
- 顾源源 5/22 铁律: 通识不抽取
- 顾源源 5/22 信息商: AI 抽出新事实时调 IngestPipeline.detect_update_relation

用法 (后续 F2.3 trigger 接入):
    extractor = DocumentLLMExtractor(db, ai_service)
    result = extractor.extract_from_document(
        v2_document_id="v2doc_xxx",
        ai_session_id="ai_sess_001",
        actor_id="user_guyuanyuan",
    )
    # result.facts_written = 实际写入 atomic_facts 的条数
    # result.skipped_general = 被判定为"通识"跳过的条数
    # result.errors = 跑挂的事实数
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.services.ingest_pipeline import (
    IngestMetadata,
    IngestPipeline,
    IngestRequest,
    base_confidence_for_source,
    default_role_for_source,
)
from app.services.reasoning_trace_store import ReasoningTraceStore


logger = logging.getLogger(__name__)


# ─── Prompt 模板 (顾源源 5/22 信息商 + 通识规则) ────────────────


SYSTEM_INSTRUCTION = """你是一个为益语智库数据中心抽取客户事实的 AI 助手。

# 任务
从用户提供的客户资料中, 按 5 维元数据模型抽取**客户特定的结构化事实**。

# 关键原则 (按重要性排序)

## 1. 通识不抽 (★ 铁律)
- 一个陈述如果对**任何同类客户**都成立 → 是通识, **不抽**
- 一个陈述只对**这家客户特定**成立 → 抽
- 例: "公益基金会需要捐赠" 不抽 / "测试机构A主要捐赠来自腾讯基金会" 抽
- 例: "心理健康教育对儿童重要" 不抽 / "测试机构A测试项目A针对乡村 6-14 岁儿童" 抽

## 2. 9 层抽取范围 (基于"AI 作为人类同事"日常工作场景反推)
- L1 客户身份: 机构性质 / 注册 / 业务规模 / 价值观 / 业务模式
- L2 关键人物: 创始人 / 核心员工 / 合作伙伴 / 决策人 + 当前状态
- L3 业务主线: 当前项目 / 里程碑 / 交付物 / 阻塞 / 下一步
- L4 决策与变化: 历史决策 / 近期变化 / 状态变更 / 未来计划
- L5 关系网络: 合作伙伴 / 客户/资方 / 内部协作
- L6 风险信号: 资金 / 人员 / 业务 / 合规 / 战略 风险
- L7 客户偏好与文化: 决策风格 / 沟通偏好 / 忌讳 / 品牌调性
- L8 历史合作记录 (我方-客户): 服务历史 / 反馈 / 承诺
- L9 量化指标: 客户规模 / 项目数字 / 关键时间

## 3. content_role 判断 (渠道驱动 + 语义二次精化)
- 已签合同 → fact / 会议纪要决议段 → decision / 复盘 → lesson / observation
- 当事人原话 → quote (必带 speaker_person_id)
- 风险信号 → risk
- 主观判断 → observation
- 未验证假设 → speculation + confidence < 0.5

## 4. 必带证据 (★ 不能凭空)
- 每条抽出的事实必须带 evidence_text (≤200 字原文摘录, 不允许改写)
- 没有原文支持的 → 不抽

## 5. 时间锚 (time_anchor)
- 是事件发生时间, 不是文档创建时间
- 例: "5/19 决议张真接任" → time_anchor='2026-05-19'
- 无法判断 → null (不要瞎填)

## 6. speaker_person_id (谁说的话)
- 文中说"张真讲了 X" → speaker = 张真
- 文档作者写的客观陈述 → speaker = null

## 7. ★ 强制抽取 3 大类 (顾源源 5/22 M-C.2 加, 防 LLM 漏关键事实)

文档若涉及以下任一类内容, **必须**抽出来 (即使原文简短):

### 7.1 人事变更 (角色 / 职位 / 关系 转换)
- 任何人 "接任 / 担任 / 转任 / 卸任 / 升任 / 调岗" 角色 → 必抽
- 任何机构 "法人 / 理事长 / 秘书长 / CEO / 创始人" 变更 → 必抽
- 任何人 "新加入 / 离职 / 退休" → 必抽
- 例: "强哥接任秘书长" → subject=强哥, attribute=新任职务, value=秘书长
- 例: "张真接任法人代表" → subject=张真, attribute=新任职务, value=法人代表

### 7.2 项目合并 / 拆分 / 重组
- 任何项目 "合并 / 拆分 / 重组 / 整合 / 改名" → 必抽
- 例: "兴盛和心理魔法学院合并为项目部" → subject=兴盛+心理魔法学院, attribute=合并, value=项目部
- 例: "项目 X 拆出 Y 子项目" → 必抽

### 7.3 产品 / 项目命名(尤其是带具体名称的新产品)
- 任何项目 / 产品 / 计划 第一次被命名 → 必抽
- 例: "安心妈妈" 计划 → subject=安心妈妈, attribute=类型, value=项目/计划/产品
- 例: "心智素养研究院" → subject=心智素养研究院, attribute=类型, value=研究机构

### 7.4 资金 / 预算变化(顾源源 5/22 P1.4 扩展)
- 任何项目 / 客户 提到具体金额变化 (新增预算 / 削减 / 拨款 / 募款) → 必抽
- 时间锚必带 (year-month-day 或至少 year-month)
- 例: "测试项目A获 200 万腾讯捐赠" → subject=测试项目A, attribute=资助方/金额, value=腾讯200万
- 例: "项目预算从 800 万削减到 500 万" → subject=项目X, attribute=预算变更, value=800万→500万

### 7.5 合规 / 监管 / 政策影响(顾源源 5/22 P1.4 扩展)
- 任何政策出台 / 监管要求 / 合规审计 对客户业务有直接影响 → 必抽
- 例: "教育部新规要求心理课时不少于 6 课时/周" → subject=教育政策, attribute=要求, value=心理课时≥6
- 例: "民政厅审计要求基金会公开 X 信息" → subject=审计要求, attribute=合规, value=公开X信息

### 7.6 战略 / 风险信号(顾源源 5/22 P1.4 扩展)
- 任何战略转向 / 业务重点变化 / 竞争威胁 / 资金风险 / 人员流失风险 → 必抽
- 例: "决定砍掉 X 业务转向 Y" → subject=机构, attribute=战略转向, value=砍X转Y
- 例: "核心员工 50% 在过去半年离职" → subject=机构, attribute=人员风险, value=核心员工流失50%
- 例: "主要资助方腾讯停止合作" → subject=机构, attribute=资金风险, value=失去腾讯

**判定方法**: 写每个段落时, 在脑子里检查 6 大类 (角色变化 / 项目合并 / 产品命名 / 资金变化 / 政策影响 / 战略风险), 答有 → 必抽 (即使原文一句话也要抽出对应 fact)。

# 输出格式 (严格 JSON)
{
  "extracted_facts": [
    {
      "subject_text": "<主语,例: 测试机构A / 张真>",
      "attribute": "<属性,例: 法人代表 / 核心业务 / 年度预算>",
      "value_text": "<值,例: 张真 / 乡村心理教育 / 800 万>",
      "content_role": "fact|decision|risk|progress|plan|lesson|observation|quote|commitment",
      "layer": "L1|L2|L3|L4|L5|L6|L7|L8|L9",
      "evidence_text": "<原文摘录 ≤200 字, 不允许改写>",
      "time_anchor": "<事件发生时间 YYYY-MM-DD 或 null>",
      "speaker_person_id": "<人名 (后续会映射 entity_id) 或 null>",
      "confidence": 0.0-1.0,
      "reasoning_steps": [
        "段落 X 说 Y",
        "结合段落 Z 确认 ...",
        "结论: ..."
      ]
    }
  ],
  "skipped_general_count": <被判为通识跳过的数量>,
  "extraction_summary": "本文档抽出 N 条事实 / 跳过 M 条通识 / 主要覆盖 LX/LY 层"
}

# 不要做的事
- ❌ 不要用 markdown 代码块包裹 JSON
- ❌ 不要在 JSON 外加解释
- ❌ 不要抽通用陈述 ("公益事业很重要" / "我们要做更好的事")
- ❌ 不要瞎填 time_anchor (没有就 null)
- ❌ 不要超过 evidence_text 200 字 (截断 + ... 即可)
"""


# JSON schema 给 LLM 强约束
EXTRACTION_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "extracted_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject_text": {"type": "string"},
                    "attribute": {"type": "string"},
                    "value_text": {"type": "string"},
                    "content_role": {"type": "string"},
                    "layer": {"type": "string"},
                    "evidence_text": {"type": "string"},
                    "time_anchor": {"type": ["string", "null"]},
                    "speaker_person_id": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "reasoning_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "subject_text", "attribute", "value_text",
                    "content_role", "evidence_text", "confidence",
                ],
            },
        },
        "skipped_general_count": {"type": "number"},
        "extraction_summary": {"type": "string"},
    },
    "required": ["extracted_facts"],
}


# ─── 类型 ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExtractionResult:
    """一次 docx 抽取的最终结果"""
    v2_document_id: str
    facts_written: int            # 实际写 atomic_facts 的条数 (走 IngestPipeline)
    facts_skipped_duplicate: int  # IngestPipeline 判 duplicate 跳过
    facts_skipped_general: int    # LLM 自己判通识跳过
    facts_failed: int             # 写入失败的条数
    update_relations: dict[str, int]  # {'none': N, 'supersedes': M, 'conflict': K, 'complement': L}
    layer_coverage: dict[str, int]    # {'L1': N, 'L2': M, ...} 覆盖度
    extraction_summary: str
    errors: list[str] = field(default_factory=list)
    trace_ids: list[str] = field(default_factory=list)


# ─── DB / AI service 协议 ─────────────────────────────────────


class _DbLike(Protocol):
    def fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None: ...
    def fetchall(self, query: str, params: tuple = ()) -> list[sqlite3.Row]: ...
    def execute(self, query: str, params: tuple = ()) -> None: ...


# ─── 服务 ────────────────────────────────────────────────────


class DocumentLLMExtractor:
    """从 v2_documents.markdown_content 抽取 atomic_facts。

    工作流:
    1. 读 v2_document 元数据 + markdown_content
    2. 根据 v2_documents.kind / source_type 决定 IngestMetadata 默认值
    3. 切 chunk (>20k 字分批, 保证 LLM 单次输入安全)
    4. 每批调 generate_intelligence_json + EXTRACTION_RESPONSE_SCHEMA
    5. 合并所有批的 facts
    6. 每条 fact:
       - 跑 IngestPipeline.ingest (内部跑 update_relation 判断 + 写 atomic_facts + event_log)
       - 跑 ReasoningTraceStore start/complete (记录推理链)
    7. 返回 ExtractionResult
    """

    # 分批大小 — LLM 单次输入安全上限 (Doubao Seed / Qwen 通常 32k token, 留余量)
    BATCH_CHARS = 12000

    def __init__(
        self,
        db: _DbLike,
        ai_service: object | None,
        ingest_pipeline: IngestPipeline | None = None,
        reasoning_trace_store: ReasoningTraceStore | None = None,
    ):
        self._db = db
        self._ai_service = ai_service
        self._pipeline = ingest_pipeline or IngestPipeline(db)
        self._trace_store = reasoning_trace_store or ReasoningTraceStore(db)

    def extract_from_document(
        self,
        *,
        v2_document_id: str,
        ai_session_id: str,
        actor_id: str = "system_extractor",
        client_id_override: str | None = None,
    ) -> ExtractionResult:
        """从指定 v2_document 抽取事实, 全程走数据中心统一通道"""
        doc_row = self._db.fetchone(
            """
            SELECT id, client_id, file_name, kind, markdown_content,
                   imported_at, content_domain
            FROM v2_documents WHERE id = ?
            """,
            (v2_document_id,),
        )
        if not doc_row:
            return ExtractionResult(
                v2_document_id=v2_document_id, facts_written=0,
                facts_skipped_duplicate=0, facts_skipped_general=0,
                facts_failed=0, update_relations={}, layer_coverage={},
                extraction_summary="document not found",
                errors=[f"v2_document {v2_document_id} not found"],
            )

        client_id = client_id_override or str(doc_row["client_id"])
        file_name = str(doc_row["file_name"] or "")
        doc_kind = str(doc_row["kind"] or "")
        markdown = str(doc_row["markdown_content"] or "")
        imported_at = str(doc_row["imported_at"] or "")

        if not markdown.strip():
            return ExtractionResult(
                v2_document_id=v2_document_id, facts_written=0,
                facts_skipped_duplicate=0, facts_skipped_general=0,
                facts_failed=0, update_relations={}, layer_coverage={},
                extraction_summary="empty markdown content",
                errors=["markdown_content is empty"],
            )

        # 根据 v2_documents.kind 映射 source_type (顾源源 5/22 渠道驱动)
        source_type = _map_kind_to_source_type(doc_kind, file_name)

        # meeting-spine Phase1③: 把客户名册(益语员工+已知人物)注入抽取 prompt,
        # 提高 owner / speaker_person_id 对齐到已知人名的准确度。失败不影响抽取。
        roster_hint = ""
        _conn = getattr(self._db, "conn", None)
        if _conn is not None:
            try:
                from app.services.person_resolver import build_client_roster_hint
                roster_hint = build_client_roster_hint(_conn, client_id)
            except Exception:
                roster_hint = ""

        # 分批
        batches = _split_to_batches(markdown, self.BATCH_CHARS)
        logger.info(
            "F2.1 extractor: doc=%s file=%s batches=%d total_chars=%d",
            v2_document_id, file_name, len(batches), len(markdown),
        )

        all_facts: list[dict[str, Any]] = []
        total_skipped_general = 0
        summaries: list[str] = []
        errors: list[str] = []

        for batch_idx, batch_text in enumerate(batches):
            trace_id = self._trace_store.start(
                ai_session_id=ai_session_id,
                output_entity_type="atomic_fact",
                input_doc_ids=[v2_document_id],
                prompt_summary=f"F2.1 extract batch {batch_idx + 1}/{len(batches)} from {file_name}",
                model_name="ai_service",  # 实际 model_name 由 ai_service 决定
            )
            try:
                payload = self._call_llm(
                    batch_text=batch_text,
                    file_name=file_name,
                    doc_kind=doc_kind,
                    source_type=source_type,
                    imported_at=imported_at,
                    roster_hint=roster_hint,
                )
                if not payload:
                    self._trace_store.fail(trace_id, error_message="LLM returned empty payload")
                    errors.append(f"batch {batch_idx + 1}: LLM empty payload")
                    continue
                facts = payload.get("extracted_facts") or []
                if not isinstance(facts, list):
                    facts = []
                skipped = int(payload.get("skipped_general_count") or 0)
                summary = str(payload.get("extraction_summary") or "")

                all_facts.extend(facts)
                total_skipped_general += skipped
                summaries.append(f"[batch {batch_idx + 1}] {summary}")
                # 完成这个 batch 的 trace
                self._trace_store.complete(
                    trace_id,
                    output_entity_id=None,  # 一批 trace 对应多 facts, output_entity_id 由 IngestPipeline 写时关联
                    reasoning_steps=[
                        f"批 {batch_idx + 1}/{len(batches)} ({len(batch_text)} 字)",
                        f"抽出 {len(facts)} 条客户特定事实, 跳过 {skipped} 条通识",
                    ],
                    output_summary=summary,
                    confidence=0.8,  # 整批 confidence, 单条 fact 用自己的
                )
            except Exception as exc:
                logger.warning("F2.1 batch %d failed: %s", batch_idx + 1, exc)
                self._trace_store.fail(trace_id, error_message=str(exc)[:500])
                errors.append(f"batch {batch_idx + 1}: {exc}")

        # 写入 atomic_facts 走 IngestPipeline
        facts_written = 0
        facts_skipped_duplicate = 0
        facts_failed = 0
        update_relations: dict[str, int] = {"none": 0, "conflict": 0, "supersedes": 0, "complement": 0}
        layer_coverage: dict[str, int] = {}
        trace_ids: list[str] = []

        for fact in all_facts:
            try:
                content_role = str(fact.get("content_role") or default_role_for_source(source_type))
                # 通过 IngestPipeline 写入 (含信息商判断 + event_log + ai_episode_log)
                metadata = IngestMetadata(
                    source_type=source_type,
                    content_role=content_role,
                    actor_type="ai_agent",  # F2.1 是 AI 抽的
                    actor_id=ai_session_id,
                    speaker_person_id=fact.get("speaker_person_id"),
                    time_anchor=fact.get("time_anchor"),
                    verification_status="unverified",  # AI 抽的默认未验证
                    confidence_source="llm",
                    confidence_score=float(fact.get("confidence") or 0.5),
                )
                req = IngestRequest(
                    path="workbench_file",
                    client_id=client_id,
                    subject_text=str(fact.get("subject_text") or "").strip()[:200],
                    attribute=str(fact.get("attribute") or "").strip()[:100],
                    value_text=str(fact.get("value_text") or "").strip()[:1000],
                    metadata=metadata,
                    source_v2_document_id=v2_document_id,
                    evidence_text=str(fact.get("evidence_text") or "").strip()[:500],
                    ai_session_id=ai_session_id,
                )
                if not req.subject_text or not req.attribute or not req.value_text:
                    facts_failed += 1
                    errors.append(f"fact missing required fields: {fact}")
                    continue

                result = self._pipeline.ingest(req)
                if result.written:
                    facts_written += 1
                else:
                    facts_skipped_duplicate += 1
                update_relations[result.update_relation] = update_relations.get(result.update_relation, 0) + 1

                # 层覆盖度
                layer = str(fact.get("layer") or "?")
                if layer != "?":
                    layer_coverage[layer] = layer_coverage.get(layer, 0) + 1

            except Exception as exc:
                logger.warning("F2.1 ingest fact failed: %s | fact=%s", exc, fact)
                facts_failed += 1
                errors.append(f"ingest failed: {exc}")

        return ExtractionResult(
            v2_document_id=v2_document_id,
            facts_written=facts_written,
            facts_skipped_duplicate=facts_skipped_duplicate,
            facts_skipped_general=total_skipped_general,
            facts_failed=facts_failed,
            update_relations=update_relations,
            layer_coverage=layer_coverage,
            extraction_summary=" | ".join(summaries),
            errors=errors,
            trace_ids=trace_ids,
        )

    def _call_llm(
        self,
        *,
        batch_text: str,
        file_name: str,
        doc_kind: str,
        source_type: str,
        imported_at: str,
        roster_hint: str = "",
    ) -> dict[str, Any] | None:
        """调 LLM 抽取一批"""
        # 延迟 import 避免循环依赖
        from app.services.intelligence_ai_runner import generate_intelligence_json

        user_prompt = (
            f"# 资料背景\n"
            f"文件名: {file_name}\n"
            f"类型: {doc_kind}\n"
            f"来源 source_type: {source_type}\n"
            f"导入时间: {imported_at}\n\n"
            f"# 资料正文\n{batch_text}\n\n"
            + (f"{roster_hint}\n\n" if roster_hint else "")
            + f"# 任务\n"
            f"按 system instruction 规则抽取**这家客户特定的**事实, 输出 JSON。\n"
            f"特别注意:\n"
            f"- 不要抽通用陈述 (对任何同类客户都成立的 → 不抽)\n"
            f"- 每条带 evidence_text 原文摘录\n"
            f"- 当事人原话标 content_role='quote' + speaker_person_id\n"
            f"- 数字类必须带具体数字\n"
        )

        result = generate_intelligence_json(
            self._ai_service,
            prompt=user_prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            response_schema=EXTRACTION_RESPONSE_SCHEMA,
            timeout_seconds=180.0,
            max_tokens=4000,
            temperature=0.2,    # 抽取任务低温保稳定
            top_p=0.85,
            task_kind="deep_analysis",
        )
        if not result.ok or not result.payload:
            logger.warning("F2.1 LLM call failed: %s", result.error)
            return None
        return result.payload


# ─── 工具函数 ─────────────────────────────────────────────────


def _map_kind_to_source_type(doc_kind: str, file_name: str) -> str:
    """根据 v2_documents.kind / file_name 映射到 IngestMetadata.source_type

    顾源源 5/22 原话:
    - 已签合同/章程 → client_official_doc (置信度 0.95)
    - 会议纪要/内部邮件 → client_internal_doc (0.90)
    - 用户上传的方案/文章 → client_internal_doc
    - 微信公众号摘录 → internet_ugc (0.30)
    - 互联网官方 → internet_official
    """
    kind = doc_kind.lower()
    fname = file_name.lower()

    if "contract" in kind or "合同" in fname:
        return "client_official_doc"
    if "战略" in fname or "手册" in fname or "manual" in fname or "annual" in fname:
        return "client_official_doc"
    if "meeting" in kind or "会议" in fname or "纪要" in fname:
        return "client_internal_doc"
    if "review" in kind or "复盘" in fname or "周复盘" in fname:
        return "collaboration_review"
    if "task_doc" in kind:
        return "collaboration_task"
    if "wechat" in kind or "微信" in fname:
        return "internet_ugc"
    if "weibo" in kind or "微博" in fname:
        return "internet_ugc"
    if "official" in kind or "官网" in fname or "gov" in fname:
        return "internet_official"

    # docx / pdf 默认 client_internal_doc (用户主动上传的资料)
    return "client_internal_doc"


def _split_to_batches(text: str, batch_chars: int) -> list[str]:
    """简单按字符切分。后续 F2.3 触发器接入时可以按段落 / 章节切。"""
    if len(text) <= batch_chars:
        return [text]
    batches: list[str] = []
    pos = 0
    while pos < len(text):
        end = min(pos + batch_chars, len(text))
        # 尽量在段落边界切 (找最近的 \n\n)
        if end < len(text):
            next_break = text.rfind("\n\n", pos, end)
            if next_break > pos + batch_chars // 2:
                end = next_break + 2
        batches.append(text[pos:end])
        pos = end
    return batches


def get_document_llm_extractor(
    db: _DbLike,
    ai_service: object | None,
) -> DocumentLLMExtractor:
    return DocumentLLMExtractor(db, ai_service)
