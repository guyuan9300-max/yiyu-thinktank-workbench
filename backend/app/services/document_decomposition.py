"""R11.1：文档结构化解构层。

把"自由文本文档"转化为"结构化字段记录"，让任务型查询（如做员工合同表）
直接从 db 读结构化字段，不再依赖检索 chunk recall。

设计：
- 第 1 步：分类（classify_document_kind）→ 写入 document_kinds 表
- 第 2 步：按 kind 加载 schema → 调 LLM 提取字段 → 写入 document_fields 表
- 幂等：重复调用不重复入库（按 (document_id, field_name) 主键覆盖）

MVP 只实现 employee_contract 一种类型。后续可扩展 meeting_minute / project_proposal / financial_report。
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ===== Schema 定义 ============================================================

# R11.1 MVP：只支持员工劳动合同
# R12: 加 universal schema 普惠所有文档
SCHEMA_VERSION = "v1"

# R12 普惠层：每份文档都跑这 16 个字段（不论类型）
UNIVERSAL_SCHEMA_NAME = "universal"
EMPLOYEE_CONTRACT_SCHEMA_NAME = "employee_contract"

UNIVERSAL_FIELDS: tuple[dict[str, str], ...] = (
    {"name": "document_kind", "label": "文档类型", "hint": "如「员工合同/会议纪要/财务报表/项目方案/资讯简报/录音转写/笔记/服务协议/捐赠协议/其他」"},
    {"name": "title_inferred", "label": "文档主题", "hint": "从内容推断的标题/主题（一句话）"},
    {"name": "main_purpose", "label": "核心主旨", "hint": "一句话点明这份文档要说/做的核心事项（≤40 字）"},
    {"name": "summary", "label": "全文摘要", "hint": "150-250 字的浓缩摘要，含主要事实+关键判断"},
    {"name": "key_people", "label": "关键人物", "hint": "人名 + 角色（如「张三-项目负责人」），逗号分隔"},
    {"name": "key_dates", "label": "关键日期", "hint": "重要日期 + 事件（如「2026-03-15 项目启动」），逗号分隔"},
    {"name": "key_amounts", "label": "关键金额", "hint": "金额 + 含义（如「6 万元-季度预算」），逗号分隔"},
    {"name": "key_numbers", "label": "关键数字", "hint": "百分比/规模/数量等关键数字 + 语义（如「覆盖 27 省」「提升 32%」）"},
    {"name": "key_locations", "label": "关键地点", "hint": "城市/区/具体地址或场所，逗号分隔"},
    {"name": "mentioned_projects", "label": "提及的项目/产品", "hint": "项目名/产品名/活动名，逗号分隔"},
    {"name": "mentioned_organizations", "label": "提及的机构/合作方", "hint": "组织/公司/单位/合作方，逗号分隔"},
    {"name": "key_decisions", "label": "关键决策", "hint": "做出的决定/选择/方案选定（如有），逗号分隔；无则填「-」"},
    {"name": "action_items", "label": "行动项", "hint": "明确的待办/下一步动作 + 责任人（如有），逗号分隔；无则填「-」"},
    {"name": "key_claims", "label": "关键判断/结论", "hint": "核心论断/结论/观点（如有），分号分隔；无则填「-」"},
    {"name": "risks_or_concerns", "label": "风险/隐患", "hint": "提及的风险/问题/隐患（如有），分号分隔；无则填「-」"},
    {"name": "open_questions", "label": "未决/待澄清", "hint": "尚未解决/需要进一步确认的事项（如有），分号分隔；无则填「-」"},
)

EMPLOYEE_CONTRACT_FIELDS: tuple[dict[str, str], ...] = (
    {"name": "employee_name", "label": "员工姓名", "hint": "甲乙双方中乙方/员工的姓名"},
    {"name": "position", "label": "岗位", "hint": "合同约定的聘任职位"},
    {"name": "department", "label": "所属部门", "hint": "员工所在的部门或业务线"},
    {"name": "effective_date", "label": "合同生效日期", "hint": "格式 YYYY-MM-DD"},
    {"name": "expiration_date", "label": "合同终止日期", "hint": "格式 YYYY-MM-DD"},
    {"name": "probation_period", "label": "试用期", "hint": "如「3个月」「无试用期」"},
    {"name": "probation_salary", "label": "试用期月薪资", "hint": "税前数字 + 元/月"},
    {"name": "regular_salary", "label": "转正后月薪资", "hint": "税前数字 + 元/月"},
    {"name": "work_location", "label": "工作地点", "hint": "城市/区/具体地址"},
    {"name": "contract_type", "label": "合同类型", "hint": "如「全日制」「劳务派遣」「固定期限」"},
)


# 支持的 kind 类型（后续可扩）
SUPPORTED_KINDS = (
    "employee_contract",
    "meeting_minute",  # 占位，prompt 引导分类器识别，提取仅 MVP 实现 contract
    "project_proposal",
    "financial_report",
    "other",
)


# ===== 数据类 ================================================================


@dataclass(frozen=True)
class ExtractedField:
    name: str
    value: str
    confidence: float
    raw_evidence: str = ""


@dataclass(frozen=True)
class ClassificationResult:
    kind: str
    confidence: float


@dataclass(frozen=True)
class DecompositionOutcome:
    document_id: str
    kind: str
    schema_version: str
    fields: list[ExtractedField]
    success: bool
    error: str = ""


# ===== Prompt 模板 ===========================================================

_CLASSIFICATION_SYSTEM = (
    "你是文档分类专家。任务：判断给定文档属于哪一类。\n"
    f"可用类别（必须从这里选一个）：{', '.join(SUPPORTED_KINDS)}\n"
    "- employee_contract: 员工劳动合同/聘用合同（含甲乙双方/岗位/期限/薪资条款）\n"
    "- meeting_minute: 会议纪要/会议记录（含日期/参会人/议题/决议）\n"
    "- project_proposal: 项目方案/项目立项书（含项目目标/预算/里程碑）\n"
    "- financial_report: 财务报表（含收入/支出/利润/科目）\n"
    "- other: 不属于以上类别\n"
    "\n"
    "输出**严格 JSON**，禁止任何 markdown 包裹或解释：\n"
    '{"kind": "employee_contract", "confidence": 0.95}\n'
    "confidence 是 0-1 之间的浮点数。"
)


_EXTRACTION_SYSTEM_TEMPLATE = (
    "你是合同结构化解构专家。任务：从员工劳动合同文档中提取指定字段。\n"
    "\n"
    "字段定义（输出 JSON 时必须用 name 作为 key）：\n"
    "{schema_lines}\n"
    "\n"
    "输出**严格 JSON 对象**，禁止任何 markdown 包裹或解释。格式：\n"
    "{{\n"
    '  "employee_name": {{"value": "张三", "confidence": 0.95, "evidence": "甲方与乙方张三..."}},\n'
    '  "position": {{"value": "顾问", "confidence": 0.95, "evidence": "..."}},\n'
    "  ...每个字段一行\n"
    "}}\n"
    "\n"
    "规则：\n"
    "1. 资料中**没有**的字段，输出 value=\"待补全\", confidence=0\n"
    "2. value 用原文表述（不要意译），如薪资写「3500 元/月」而不是「3500」\n"
    "3. 试用期+转正分开两个字段；如合同写「2024.2.18-2024.5.17：2800 元；2024.5.18 起：3500 元」，\n"
    "   probation_salary=「2800 元」，regular_salary=「3500 元」\n"
    "4. evidence 是支持该字段值的原文片段，截取 30-100 字\n"
    "5. confidence: 资料里明确写明=0.95；推断=0.7；无依据=0\n"
    "6. **禁止编造**：原文没有的字段必须 value=\"待补全\"\n"
)


def _build_extraction_system() -> str:
    schema_lines = "\n".join(
        f"- {f['name']} ({f['label']})：{f['hint']}"
        for f in EMPLOYEE_CONTRACT_FIELDS
    )
    return _EXTRACTION_SYSTEM_TEMPLATE.format(schema_lines=schema_lines)


# R12 普惠浅解构 prompt
_UNIVERSAL_EXTRACTION_SYSTEM_TEMPLATE = (
    "你是文档结构化解构专家。任务：从任意类型的文档（合同/会议纪要/财报/项目方案/资讯/录音转写/笔记 等）"
    "提取通用关键信息。**所有文档都跑这一遍**，无论它是什么类型。\n"
    "\n"
    "字段定义（输出 JSON 时必须用 name 作为 key）：\n"
    "{schema_lines}\n"
    "\n"
    "输出**严格 JSON 对象**，禁止任何 markdown 包裹或解释。格式：\n"
    "{{\n"
    '  "document_kind": {{"value": "员工合同", "confidence": 0.95, "evidence": ""}},\n'
    '  "title_inferred": {{"value": "张三 副秘书长 劳动合同", "confidence": 0.95, "evidence": ""}},\n'
    "  ...每个字段一行\n"
    "}}\n"
    "\n"
    "规则：\n"
    "1. **不存在**的字段：value=\"-\"（不是「待补全」），confidence=0\n"
    "2. value 用中文，简洁、信息密度高、可直接索引\n"
    "3. 列表型字段（key_people / key_dates / key_amounts / key_numbers / key_locations / mentioned_projects / mentioned_organizations）：\n"
    "   用半角逗号 `,` 分隔多条目。每条≤25 字。最多 12 条。\n"
    "4. 长文本字段（summary）：150-250 字，含**核心事实**+**关键判断**。\n"
    "5. 短文本字段（main_purpose / title_inferred）：≤40 字\n"
    "6. **不要编造**：原文没有的内容必须写「-」\n"
    "7. evidence 字段可以留空（universal 解构不强制溯源，节省 token）\n"
    "8. confidence: 资料里明确写明=0.95；推断/概括=0.7；不存在=0\n"
    "9. document_kind 用中文（如「员工合同」「会议纪要」「财务报表」「项目方案」「资讯简报」「录音转写」「笔记」「服务协议」「捐赠协议」「其他」）\n"
)


def _build_universal_extraction_system() -> str:
    schema_lines = "\n".join(
        f"- {f['name']} ({f['label']})：{f['hint']}"
        for f in UNIVERSAL_FIELDS
    )
    return _UNIVERSAL_EXTRACTION_SYSTEM_TEMPLATE.format(schema_lines=schema_lines)


def decompose_universal(
    db,
    ai_service,
    document_id: str,
    *,
    max_chars: int = 5500,  # R11.1.G：缩短避免超时
) -> DecompositionOutcome:
    """R12 普惠浅解构：从任意文档提取 16 个通用字段。

    失败返回 success=False。每份文档都应该跑这一遍（不论类型）。
    """
    row = db.fetchone(
        """
        SELECT v2.markdown_content, v2.preview_text, v2.file_name
        FROM v2_documents v2
        WHERE v2.document_id = ?
        """,
        (document_id,),
    )
    if not row:
        return DecompositionOutcome(
            document_id=document_id,
            kind="universal",
            schema_version=SCHEMA_VERSION,
            fields=[],
            success=False,
            error="document not found in v2_documents",
        )
    content = str(row["markdown_content"] or "").strip()
    if not content:
        content = str(row["preview_text"] or "").strip()
    if not content:
        return DecompositionOutcome(
            document_id=document_id,
            kind="universal",
            schema_version=SCHEMA_VERSION,
            fields=[],
            success=False,
            error="document content is empty",
        )

    body = content[:max_chars]
    file_name = str(row["file_name"] or "")
    user_prompt = (
        f"文档文件名：{file_name}\n\n"
        f"文档内容：\n{body}\n\n"
        "请按系统指令提取所有 16 个字段，输出严格 JSON。"
    )
    try:
        raw = ai_service._qwen_generate(  # noqa: SLF001
            prompt=user_prompt,
            system_instruction=_build_universal_extraction_system(),
            response_schema=None,
            timeout_seconds=180.0,  # R11.1.G：universal 16 字段提取给 3 分钟避免超时
            max_tokens=1800,
            temperature=0.2,
            top_p=0.9,
            enable_thinking=False,
            task_kind="fast_structured",
        )
    except Exception as exc:
        logger.warning("[universal-decompose] failed for %s: %s", document_id, exc)
        return DecompositionOutcome(
            document_id=document_id,
            kind="universal",
            schema_version=SCHEMA_VERSION,
            fields=[],
            success=False,
            error=f"llm_call_failed: {exc}",
        )
    parsed = _parse_json_response(str(raw))
    if not isinstance(parsed, dict):
        return DecompositionOutcome(
            document_id=document_id,
            kind="universal",
            schema_version=SCHEMA_VERSION,
            fields=[],
            success=False,
            error=f"llm_response_not_json: {str(raw)[:200]}",
        )

    fields: list[ExtractedField] = []
    for field_def in UNIVERSAL_FIELDS:
        field_name = field_def["name"]
        entry = parsed.get(field_name)
        if not isinstance(entry, dict):
            fields.append(ExtractedField(
                name=field_name,
                value="-",
                confidence=0.0,
                raw_evidence="",
            ))
            continue
        value = str(entry.get("value") or "-").strip() or "-"
        try:
            confidence = float(entry.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        evidence = str(entry.get("evidence") or "").strip()[:300]
        fields.append(ExtractedField(
            name=field_name,
            value=value,
            confidence=max(0.0, min(1.0, confidence)),
            raw_evidence=evidence,
        ))
    return DecompositionOutcome(
        document_id=document_id,
        kind="universal",
        schema_version=SCHEMA_VERSION,
        fields=fields,
        success=True,
        error="",
    )


# ===== 分类 =================================================================


def classify_document_kind(
    db,
    ai_service,
    document_id: str,
    *,
    max_chars: int = 2500,  # R11.1.G：缩短输入避免超时
) -> ClassificationResult | None:
    """用 LLM 看文档首部判断类型。返回 None 表示无法读取文档。"""
    row = db.fetchone(
        """
        SELECT v2.markdown_content, v2.preview_text, v2.file_name
        FROM v2_documents v2
        WHERE v2.document_id = ?
        """,
        (document_id,),
    )
    if not row:
        return None
    content = str(row["markdown_content"] or "").strip()
    if not content:
        content = str(row["preview_text"] or "").strip()
    if not content:
        return None
    head = content[:max_chars]
    file_name = str(row["file_name"] or "")

    user_prompt = (
        f"文档文件名：{file_name}\n\n"
        f"文档内容（前 {max_chars} 字）：\n{head}\n\n"
        "请判断这份文档的类别，输出 JSON：{kind, confidence}"
    )
    try:
        raw = ai_service._qwen_generate(  # noqa: SLF001
            prompt=user_prompt,
            system_instruction=_CLASSIFICATION_SYSTEM,
            response_schema=None,
            timeout_seconds=45.0,  # R11.1.G：分类调用预留 45s（短输出但豆包冷启动慢）
            max_tokens=120,
            temperature=0.2,
            top_p=0.9,
            enable_thinking=False,
            task_kind="fast_structured",
        )
    except Exception as exc:
        logger.warning("[decompose] classify failed for %s: %s", document_id, exc)
        return None
    parsed = _parse_json_response(str(raw))
    if not isinstance(parsed, dict):
        return None
    kind = str(parsed.get("kind") or "other").strip().lower()
    if kind not in SUPPORTED_KINDS:
        kind = "other"
    try:
        confidence = float(parsed.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return ClassificationResult(kind=kind, confidence=max(0.0, min(1.0, confidence)))


# ===== 解构 =================================================================


def decompose_employee_contract(
    db,
    ai_service,
    document_id: str,
    *,
    max_chars: int = 5500,  # R11.1.G：缩短避免超时
) -> DecompositionOutcome:
    """从员工劳动合同提取 9 个字段。失败返回 success=False + error。"""
    row = db.fetchone(
        """
        SELECT v2.markdown_content, v2.preview_text, v2.file_name
        FROM v2_documents v2
        WHERE v2.document_id = ?
        """,
        (document_id,),
    )
    if not row:
        return DecompositionOutcome(
            document_id=document_id,
            kind="employee_contract",
            schema_version=SCHEMA_VERSION,
            fields=[],
            success=False,
            error="document not found in v2_documents",
        )
    content = str(row["markdown_content"] or "").strip()
    if not content:
        content = str(row["preview_text"] or "").strip()
    if not content:
        return DecompositionOutcome(
            document_id=document_id,
            kind="employee_contract",
            schema_version=SCHEMA_VERSION,
            fields=[],
            success=False,
            error="document content is empty",
        )

    body = content[:max_chars]
    file_name = str(row["file_name"] or "")
    user_prompt = (
        f"合同文件名：{file_name}\n\n"
        f"合同内容：\n{body}\n\n"
        "请按系统指令提取所有字段，输出严格 JSON 对象。"
    )
    try:
        raw = ai_service._qwen_generate(  # noqa: SLF001
            prompt=user_prompt,
            system_instruction=_build_extraction_system(),
            response_schema=None,
            timeout_seconds=180.0,  # R11.1.G：合同字段提取给 3 分钟避免超时
            max_tokens=1500,
            temperature=0.2,
            top_p=0.9,
            enable_thinking=False,
            task_kind="fast_structured",
        )
    except Exception as exc:
        logger.warning("[decompose] extract failed for %s: %s", document_id, exc)
        return DecompositionOutcome(
            document_id=document_id,
            kind="employee_contract",
            schema_version=SCHEMA_VERSION,
            fields=[],
            success=False,
            error=f"llm_call_failed: {exc}",
        )
    parsed = _parse_json_response(str(raw))
    if not isinstance(parsed, dict):
        return DecompositionOutcome(
            document_id=document_id,
            kind="employee_contract",
            schema_version=SCHEMA_VERSION,
            fields=[],
            success=False,
            error=f"llm_response_not_json: {str(raw)[:200]}",
        )

    fields: list[ExtractedField] = []
    for field_def in EMPLOYEE_CONTRACT_FIELDS:
        field_name = field_def["name"]
        entry = parsed.get(field_name)
        if not isinstance(entry, dict):
            # 字段没返回 → 待补全
            fields.append(ExtractedField(
                name=field_name,
                value="待补全",
                confidence=0.0,
                raw_evidence="",
            ))
            continue
        value = str(entry.get("value") or "待补全").strip() or "待补全"
        try:
            confidence = float(entry.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        evidence = str(entry.get("evidence") or "").strip()[:500]
        fields.append(ExtractedField(
            name=field_name,
            value=value,
            confidence=max(0.0, min(1.0, confidence)),
            raw_evidence=evidence,
        ))
    return DecompositionOutcome(
        document_id=document_id,
        kind="employee_contract",
        schema_version=SCHEMA_VERSION,
        fields=fields,
        success=True,
        error="",
    )


# ===== 入库 =================================================================


def upsert_document_kind(
    db,
    *,
    document_id: str,
    kind: str,
    confidence: float,
    decomposition_status: str = "pending",
    error: str = "",
) -> None:
    timestamp = _now_iso()
    existing = db.fetchone(
        "SELECT document_id FROM document_kinds WHERE document_id = ?",
        (document_id,),
    )
    if existing:
        db.execute(
            """
            UPDATE document_kinds
            SET kind = ?, schema_version = ?, classification_confidence = ?,
                classified_at = ?, decomposition_status = ?, last_error = ?
            WHERE document_id = ?
            """,
            (kind, SCHEMA_VERSION, confidence, timestamp, decomposition_status,
             error or None, document_id),
        )
    else:
        db.execute(
            """
            INSERT INTO document_kinds(
                document_id, kind, schema_version, classification_confidence,
                classified_at, decomposition_status, last_error
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (document_id, kind, SCHEMA_VERSION, confidence, timestamp,
             decomposition_status, error or None),
        )


def upsert_document_fields(
    db,
    *,
    document_id: str,
    fields: list[ExtractedField],
    schema_name: str = EMPLOYEE_CONTRACT_SCHEMA_NAME,
    update_kind_status: bool = True,
) -> int:
    """覆盖式 upsert（同 document_id + schema_name + field_name 唯一）。

    schema_name: 字段属于哪个 schema（'universal' / 'employee_contract' / 'meeting_minute' / ...）。
    update_kind_status: 是否把 document_kinds.decomposition_status 标为 success（R12 编排器统一管理）。
    """
    timestamp = _now_iso()
    count = 0
    for field in fields:
        row_id = f"docfield_{uuid.uuid4().hex[:10]}"
        existing = db.fetchone(
            "SELECT id FROM document_fields WHERE document_id = ? AND schema_name = ? AND field_name = ?",
            (document_id, schema_name, field.name),
        )
        if existing:
            db.execute(
                """
                UPDATE document_fields
                SET field_value = ?, field_confidence = ?, extraction_method = 'llm',
                    raw_evidence = ?, updated_at = ?
                WHERE id = ?
                """,
                (field.value, field.confidence, field.raw_evidence,
                 timestamp, str(existing["id"])),
            )
        else:
            db.execute(
                """
                INSERT INTO document_fields(
                    id, document_id, schema_name, field_name, field_value, field_confidence,
                    extraction_method, raw_evidence, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, 'llm', ?, ?, ?)
                """,
                (row_id, document_id, schema_name, field.name, field.value, field.confidence,
                 field.raw_evidence, timestamp, timestamp),
            )
        count += 1
    if update_kind_status:
        db.execute(
            """
            UPDATE document_kinds
            SET decomposition_status = 'success', decomposed_at = ?, last_error = NULL
            WHERE document_id = ?
            """,
            (timestamp, document_id),
        )
    return count


def mark_decomposition_failed(db, *, document_id: str, error: str) -> None:
    """标记解构失败，便于后续重试或诊断。"""
    timestamp = _now_iso()
    db.execute(
        """
        UPDATE document_kinds
        SET decomposition_status = 'failed', decomposed_at = ?, last_error = ?
        WHERE document_id = ?
        """,
        (timestamp, error[:500], document_id),
    )


# ===== 编排：classify + decompose + 入库 =====================================


def classify_and_decompose(
    db,
    ai_service,
    document_id: str,
) -> DecompositionOutcome | None:
    """R12 编排器：分类 + universal 解构（所有文档）+ 特化解构（按类型）+ 入库。

    流程：
    1. classify_document_kind → 写 document_kinds
    2. decompose_universal → 写 document_fields (schema_name='universal') —— **所有文档都跑**
    3. 如果分类为 employee_contract → 额外跑 decompose_employee_contract，写 document_fields (schema_name='employee_contract')
    4. 后续可加 meeting_minute / financial_report / ... 等更多 specialized schema
    """
    classification = classify_document_kind(db, ai_service, document_id)
    if classification is None:
        return None
    upsert_document_kind(
        db,
        document_id=document_id,
        kind=classification.kind,
        confidence=classification.confidence,
        decomposition_status="pending",
    )

    # R12: 普惠层 —— 所有文档都跑 universal 解构
    universal_outcome = decompose_universal(db, ai_service, document_id)
    if universal_outcome.success:
        upsert_document_fields(
            db,
            document_id=document_id,
            fields=universal_outcome.fields,
            schema_name=UNIVERSAL_SCHEMA_NAME,
            update_kind_status=False,  # 留给最后统一标
        )
    else:
        mark_decomposition_failed(
            db, document_id=document_id,
            error=f"universal_failed: {universal_outcome.error}",
        )
        return universal_outcome

    # 特化层：按分类决定是否做更细的解构
    if classification.kind == "employee_contract":
        contract_outcome = decompose_employee_contract(db, ai_service, document_id)
        if contract_outcome.success:
            upsert_document_fields(
                db,
                document_id=document_id,
                fields=contract_outcome.fields,
                schema_name=EMPLOYEE_CONTRACT_SCHEMA_NAME,
                update_kind_status=True,
            )
            return contract_outcome
        else:
            # universal 成功但 contract 失败：仍算部分成功
            mark_decomposition_failed(
                db, document_id=document_id,
                error=f"contract_failed: {contract_outcome.error}",
            )
            return contract_outcome
    else:
        # 其他类型：universal 已成功，标 success
        db.execute(
            """
            UPDATE document_kinds
            SET decomposition_status = 'success', decomposed_at = ?, last_error = NULL
            WHERE document_id = ?
            """,
            (_now_iso(), document_id),
        )
        return universal_outcome


# ===== 查询助手（main.py task_mode 用）========================================


def fetch_employee_contracts_for_client(
    db,
    client_id: str,
) -> list[dict[str, Any]]:
    """读取客户所有已解构的员工合同字段（schema='employee_contract'）。

    每条记录：{document_id, file_name, fields: {field_name: {value, confidence}}}
    """
    return _fetch_fields_by_schema(db, client_id, EMPLOYEE_CONTRACT_SCHEMA_NAME)


def fetch_universal_fields_for_client(
    db,
    client_id: str,
) -> list[dict[str, Any]]:
    """R12：读取客户所有文档的 universal 浅解构字段。

    每条记录：{document_id, file_name, kind, fields: {field_name: {value, confidence}}}
    """
    return _fetch_fields_by_schema(db, client_id, UNIVERSAL_SCHEMA_NAME)


def _fetch_fields_by_schema(
    db,
    client_id: str,
    schema_name: str,
) -> list[dict[str, Any]]:
    """按 schema 过滤读取客户全部已解构字段。"""
    rows = db.fetchall(
        """
        SELECT
          d.id AS document_id,
          d.title AS file_name,
          dk.kind AS kind,
          df.field_name AS field_name,
          df.field_value AS field_value,
          df.field_confidence AS field_confidence
        FROM documents d
        LEFT JOIN document_kinds dk ON dk.document_id = d.id
        LEFT JOIN document_fields df ON df.document_id = d.id AND df.schema_name = ?
        WHERE d.client_id = ?
          AND df.field_name IS NOT NULL
        ORDER BY d.title ASC, df.field_name ASC
        """,
        (schema_name, client_id),
    )
    records_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        doc_id = str(row["document_id"])
        if doc_id not in records_map:
            records_map[doc_id] = {
                "document_id": doc_id,
                "file_name": str(row["file_name"] or ""),
                "kind": str(row["kind"] or "unknown"),
                "fields": {},
            }
        field_name = row["field_name"]
        if field_name:
            records_map[doc_id]["fields"][str(field_name)] = {
                "value": str(row["field_value"] or ""),
                "confidence": float(row["field_confidence"] or 0.0),
            }
    return list(records_map.values())


# ===== Helpers ==============================================================


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _parse_json_response(raw: str) -> Any:
    """容错 JSON 解析（剥 markdown 包裹、try literal_eval）。"""
    text = (raw or "").strip()
    if not text:
        return None
    # 剥 ```json 或 ``` 包裹
    text = re.sub(r"^```(?:json|markdown|md)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 抽出 {...} 块再试
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None
