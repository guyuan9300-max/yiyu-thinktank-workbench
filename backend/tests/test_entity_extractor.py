"""实体抽取测试（迭代 2）。

覆盖：
- 规则层：amount / date / person(称谓) / company(后缀)
- LLM 输出解析（含 ```json 包裹、混入文本等容错）
- 主入口合并去重
- LLM 失败时降级到规则层
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.entity_extractor import (
    ExtractedEntity,
    extract_amounts,
    extract_by_rules,
    extract_companies_by_suffix,
    extract_dates,
    extract_entities_from_chunk,
    extract_persons_by_title,
    merge_extractions,
    parse_llm_output,
)


# ---- 规则层 · 金额 -----------------------------------------------------


@pytest.mark.unit
def test_extract_amounts_recognizes_common_chinese_forms() -> None:
    text = "客户预算 50万元，备用资金 100,000元，海外报价 5000美元，留学经费 2万刀。"
    entities = extract_amounts(text)

    normalized = {e.normalized_name for e in entities}
    assert "50万元" in normalized
    assert "100000元" in normalized
    assert "5000美元" in normalized
    assert "2万美元" in normalized


@pytest.mark.unit
def test_extract_amounts_returns_empty_for_no_match() -> None:
    assert extract_amounts("纯文本不带任何金额") == []


# ---- 规则层 · 日期 -----------------------------------------------------


@pytest.mark.unit
def test_extract_dates_normalizes_common_forms() -> None:
    text = "项目 2026年6月1日 上线；2026-12-31 截止；6月15日 review。"
    entities = extract_dates(text)

    normalized = {e.normalized_name for e in entities}
    assert "2026-06-01" in normalized
    assert "2026-12-31" in normalized
    assert "06-15" in normalized


# ---- 规则层 · 人物 -----------------------------------------------------


@pytest.mark.unit
def test_extract_persons_by_title_finds_chinese_titles() -> None:
    text = "今天和张总开会，李工提了三个建议，王经理后续跟进。"
    entities = extract_persons_by_title(text)

    names = {e.normalized_name for e in entities}
    assert "张总" in names
    assert "李工" in names
    assert "王经理" in names


@pytest.mark.unit
def test_extract_persons_does_not_match_when_no_title() -> None:
    """无称谓的人名留给 LLM 层，不要规则层乱抓。"""
    text = "今天我和小红讨论了一下。"
    entities = extract_persons_by_title(text)
    assert entities == []


# ---- 规则层 · 公司 -----------------------------------------------------


@pytest.mark.unit
def test_extract_companies_by_suffix_finds_common_forms() -> None:
    text = "A组织科技和阿里集团合作，对手是百度公司，还有腾讯实验室。"
    entities = extract_companies_by_suffix(text)

    names = {e.normalized_name for e in entities}
    assert "A组织科技" in names
    assert "阿里集团" in names
    assert "百度公司" in names
    assert "腾讯实验室" in names


# ---- LLM 输出解析 ------------------------------------------------------


@pytest.mark.unit
def test_parse_llm_output_handles_plain_json_array() -> None:
    raw = '[{"entity_type":"person","text":"张三","normalized_name":"张三","confidence":0.9}]'
    entities = parse_llm_output(raw)
    assert len(entities) == 1
    assert entities[0].entity_type == "person"
    assert entities[0].normalized_name == "张三"
    assert entities[0].confidence == 0.9


@pytest.mark.unit
def test_parse_llm_output_handles_markdown_code_fence() -> None:
    raw = """这是 LLM 的废话回复，下面是 JSON：
```json
[
  {"entity_type": "company", "text": "A组织科技", "normalized_name": "A组织科技", "confidence": 0.85}
]
```
没了。"""
    entities = parse_llm_output(raw)
    assert len(entities) == 1
    assert entities[0].entity_type == "company"
    assert entities[0].normalized_name == "A组织科技"


@pytest.mark.unit
def test_parse_llm_output_drops_invalid_type_and_empty_text() -> None:
    raw = """[
        {"entity_type": "unknown_type", "text": "xxx", "normalized_name": "xxx"},
        {"entity_type": "person", "text": "", "normalized_name": ""},
        {"entity_type": "person", "text": "张三", "normalized_name": "张三", "confidence": 0.8}
    ]"""
    entities = parse_llm_output(raw)
    assert len(entities) == 1
    assert entities[0].normalized_name == "张三"


@pytest.mark.unit
def test_parse_llm_output_returns_empty_on_malformed_json() -> None:
    assert parse_llm_output("这不是 JSON") == []
    assert parse_llm_output("") == []


# ---- 合并去重 ----------------------------------------------------------


@pytest.mark.unit
def test_merge_extractions_dedupes_by_type_and_normalized_name() -> None:
    primary = [
        ExtractedEntity("person", "张总", "张总", "张总", 0.9),
        ExtractedEntity("company", "A组织科技", "A组织科技", "A组织科技", 0.7),
    ]
    secondary = [
        ExtractedEntity("person", "张总", "张总", "张总", 0.6),  # 应被 primary 吃掉
        ExtractedEntity("project", "X 计划", "X 计划", "X 计划", 0.8),
    ]
    merged = merge_extractions(primary, secondary)
    assert len(merged) == 3
    names = [(e.entity_type, e.normalized_name) for e in merged]
    assert ("person", "张总") in names
    assert ("company", "A组织科技") in names
    assert ("project", "X 计划") in names
    # 同 key 的 primary 优先（置信度 0.9 而不是 0.6）
    person_record = next(e for e in merged if e.entity_type == "person")
    assert person_record.confidence == 0.9


# ---- 主入口 ------------------------------------------------------------


@pytest.mark.unit
def test_extract_entities_rule_only_when_no_llm() -> None:
    text = "张总说预算 50万元，6月1日截止。"
    entities = extract_entities_from_chunk(text, llm_extractor=None)
    types = {e.entity_type for e in entities}
    assert "person" in types
    assert "amount" in types
    assert "date" in types


@pytest.mark.unit
def test_extract_entities_combines_rule_and_llm() -> None:
    text = "张总说预算 50万元。"

    def fake_llm(chunk: str) -> list[ExtractedEntity]:
        return [
            ExtractedEntity("project", "曙光计划", "曙光计划", "曙光计划", 0.8),
            ExtractedEntity("person", "张总", "张总", "张总", 0.7),  # dup with rule
        ]

    entities = extract_entities_from_chunk(text, llm_extractor=fake_llm)
    keys = {(e.entity_type, e.normalized_name) for e in entities}
    assert ("person", "张总") in keys
    assert ("amount", "50万元") in keys
    assert ("project", "曙光计划") in keys
    # 规则层的 张总 (0.75) 应当优先于 LLM 的 张总 (0.7)
    person = next(e for e in entities if e.entity_type == "person")
    assert person.confidence == 0.75


@pytest.mark.unit
def test_extract_entities_falls_back_when_llm_raises() -> None:
    """LLM 抛异常 → 降级到规则层，不影响入库。"""
    text = "李工说要 100万美元 预算。"

    def broken_llm(chunk: str) -> list[ExtractedEntity]:
        raise RuntimeError("LLM 后端挂了")

    entities = extract_entities_from_chunk(text, llm_extractor=broken_llm)
    types = {e.entity_type for e in entities}
    assert "person" in types
    assert "amount" in types


@pytest.mark.unit
def test_extract_entities_empty_input_returns_empty() -> None:
    assert extract_entities_from_chunk("") == []
    assert extract_entities_from_chunk("   \n  ") == []
