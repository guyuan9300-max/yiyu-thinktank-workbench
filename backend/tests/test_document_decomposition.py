"""R11.1：文档结构化解构模块单测（不依赖真实 LLM 调用）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.document_decomposition import (
    EMPLOYEE_CONTRACT_FIELDS,
    EMPLOYEE_CONTRACT_SCHEMA_NAME,
    SCHEMA_VERSION,
    SUPPORTED_KINDS,
    UNIVERSAL_FIELDS,
    UNIVERSAL_SCHEMA_NAME,
    ClassificationResult,
    DecompositionOutcome,
    ExtractedField,
    _build_extraction_system,
    _build_universal_extraction_system,
    _parse_json_response,
)


def test_schema_has_9_fields() -> None:
    """R11.1 MVP 定义 9 个员工合同字段（用户提到的全部 + 几个补充）。"""
    field_names = [f["name"] for f in EMPLOYEE_CONTRACT_FIELDS]
    # 关键字段必须存在
    assert "employee_name" in field_names
    assert "position" in field_names
    assert "department" in field_names
    assert "effective_date" in field_names
    assert "expiration_date" in field_names
    assert "probation_salary" in field_names
    assert "regular_salary" in field_names
    # 至少 9 个字段
    assert len(EMPLOYEE_CONTRACT_FIELDS) >= 9


def test_supported_kinds_includes_employee_contract() -> None:
    assert "employee_contract" in SUPPORTED_KINDS
    assert "other" in SUPPORTED_KINDS


def test_schema_version_constant() -> None:
    assert SCHEMA_VERSION == "v1"


def test_extraction_system_includes_all_fields() -> None:
    """提取 prompt 必须包含全部 schema 字段名（避免 LLM 漏字段）。"""
    instruction = _build_extraction_system()
    for field in EMPLOYEE_CONTRACT_FIELDS:
        assert field["name"] in instruction
        assert field["label"] in instruction


def test_extraction_system_includes_safety_rules() -> None:
    instruction = _build_extraction_system()
    # 禁止编造
    assert "禁止编造" in instruction or "待补全" in instruction
    # 输出 JSON
    assert "JSON" in instruction


# ---- JSON 解析 ----------------------------------------------------------

def test_parse_clean_json() -> None:
    raw = '{"kind": "employee_contract", "confidence": 0.95}'
    parsed = _parse_json_response(raw)
    assert parsed == {"kind": "employee_contract", "confidence": 0.95}


def test_parse_markdown_wrapped_json() -> None:
    raw = "```json\n{\"kind\": \"employee_contract\", \"confidence\": 0.9}\n```"
    parsed = _parse_json_response(raw)
    assert parsed is not None
    assert parsed["kind"] == "employee_contract"


def test_parse_json_with_extra_text() -> None:
    """LLM 偶尔会加前后说明，应能从中提取 {...} 块。"""
    raw = "以下是分类结果：\n{\"kind\": \"meeting_minute\", \"confidence\": 0.7}\n以上。"
    parsed = _parse_json_response(raw)
    assert parsed is not None
    assert parsed["kind"] == "meeting_minute"


def test_parse_empty_returns_none() -> None:
    assert _parse_json_response("") is None
    assert _parse_json_response("   ") is None


def test_parse_non_json_returns_none() -> None:
    assert _parse_json_response("这不是 JSON 内容") is None


# ---- Dataclass 行为 -----------------------------------------------------

def test_extracted_field_immutable() -> None:
    field = ExtractedField(name="employee_name", value="张三", confidence=0.95)
    # frozen dataclass 不能改
    import pytest
    with pytest.raises(Exception):
        field.value = "李四"  # type: ignore[misc]


def test_classification_result_basic() -> None:
    result = ClassificationResult(kind="employee_contract", confidence=0.9)
    assert result.kind == "employee_contract"


def test_decomposition_outcome_failure_shape() -> None:
    outcome = DecompositionOutcome(
        document_id="d1",
        kind="employee_contract",
        schema_version=SCHEMA_VERSION,
        fields=[],
        success=False,
        error="llm_call_failed: timeout",
    )
    assert not outcome.success
    assert outcome.error.startswith("llm_call_failed")


# ---- R12: Universal schema ---------------------------------------------

def test_universal_schema_has_16_fields() -> None:
    """R12 普惠解构定义 16 个通用字段，覆盖任意文档类型。"""
    field_names = [f["name"] for f in UNIVERSAL_FIELDS]
    expected = [
        "document_kind", "title_inferred", "main_purpose", "summary",
        "key_people", "key_dates", "key_amounts", "key_numbers",
        "key_locations", "mentioned_projects", "mentioned_organizations",
        "key_decisions", "action_items", "key_claims",
        "risks_or_concerns", "open_questions",
    ]
    for name in expected:
        assert name in field_names, f"必须含 universal 字段 {name}"
    assert len(UNIVERSAL_FIELDS) >= 16


def test_universal_schema_name_constant() -> None:
    assert UNIVERSAL_SCHEMA_NAME == "universal"
    assert EMPLOYEE_CONTRACT_SCHEMA_NAME == "employee_contract"
    assert UNIVERSAL_SCHEMA_NAME != EMPLOYEE_CONTRACT_SCHEMA_NAME


def test_universal_extraction_system_includes_all_fields() -> None:
    instruction = _build_universal_extraction_system()
    for field in UNIVERSAL_FIELDS:
        assert field["name"] in instruction, f"prompt 必须含字段 {field['name']}"
        assert field["label"] in instruction


def test_universal_extraction_system_includes_safety_rules() -> None:
    instruction = _build_universal_extraction_system()
    # 含「不存在则填 -」「禁止编造」「JSON 输出」等关键规则
    assert "不存在" in instruction or "-" in instruction
    assert "不要编造" in instruction or "禁止" in instruction
    assert "JSON" in instruction
    # universal 应说明"所有文档都跑"
    assert "所有文档都跑" in instruction or "无论它是什么类型" in instruction


def test_universal_fields_have_chinese_labels() -> None:
    """字段标签都用中文，方便提示词描述。"""
    for field in UNIVERSAL_FIELDS:
        # label 应该是中文（含 Unicode 中文字符）
        assert any("一" <= ch <= "鿿" for ch in field["label"])
